"""Procedural motion-graphics renderer for the 'motion' visual provider.

Why this exists: the diffusion provider needs >=8 GB VRAM and cannot run on this
machine. This provider is the free, CPU-only path. It is not stock footage and it
is not a placeholder — every shot kind is a composed scene (geometry, backlight,
fog, grain, vignette, character silhouettes) so that 30 episodes share one look.

Rendering strategy: compose at a reduced scale (fast, and the sources are all soft),
upscale, then add full-resolution grain and vignette. Frames are piped straight to
ffmpeg as rawvideo so no PNG round-trip is needed.
"""

from __future__ import annotations

import math
import random
import subprocess
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFilter

from lib import ffmpeg

MAXC = 255


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
    )


def _mix_s(c1, c2, t):
    """Scaled mix for a flat colour triple."""
    return tuple(max(0, min(MAXC, int(v))) for v in _mix(c1, c2, t))


def _vgrad(size, top, bottom):
    w, h = size
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        px[0, y] = _mix(top, bottom, y / max(1, h - 1))
    return img.resize(size, Image.BILINEAR)


class MotionRenderer:
    def __init__(self, cfg: dict, grammar: dict, width: int, height: int, fps: int):
        self.cfg = cfg
        self.g = grammar
        self.W = width
        self.H = height
        self.fps = fps
        self.scale = float(cfg["visual"]["motion"]["render_scale"])
        self.cw = max(160, int(width * self.scale))
        self.ch = max(280, int(height * self.scale))
        self.pal = grammar["palette"]
        self.cams = grammar["camera"]
        self.chars = grammar["characters"]
        self.kinds = grammar["shot_kinds"]
        self.motion = grammar["motion_motifs"]

        self._vignette_mask = self._build_vignette(float(cfg["visual"]["motion"]["vignette"]))

    # ---------- helpers ----------

    def _build_vignette(self, strength: float) -> Image.Image:
        w, h = 64, 114
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        cx, cy = w / 2, h / 2
        maxd = math.hypot(cx, cy)
        for y in range(h):
            for x in range(w):
                dist = math.hypot(x - cx, y - cy) / maxd
                v = 1.0 - strength * (dist ** 2.2)
                mask.putpixel((x, y), int(max(0.0, min(1.0, v)) * MAXC))
        return mask.resize((self.W, self.H), Image.BILINEAR)

    def _flicker(self, t: float, seed: int) -> float:
        hz = float(self.motion["flicker_hz"])
        r = random.Random(seed * 9973 + int(t * hz))
        base = 0.72 + 0.28 * math.sin(t * hz * math.tau)
        return max(0.15, min(1.35, base + (r.random() - 0.5) * 0.16))

    def _pal(self, name: str) -> dict[str, tuple[int, int, int]]:
        p = self.pal[name]
        return {
            "bg": tuple(p["bg"]), "glow": tuple(p["glow"]), "fill": tuple(p["fill"]),
        }

    def _fog(self, canvas: Image.Image, t: float, amount: float, seed: int) -> Image.Image:
        """Volumetric fog at reduced resolution (the draw surface size)."""
        if amount <= 0:
            return canvas
        fw, fh = max(48, self.cw // 3), max(80, self.ch // 3)
        layer = Image.new("RGB", (fw, fh), (0, 0, 0))
        d = ImageDraw.Draw(layer)
        rnd = random.Random(seed + 17)
        for i in range(3):
            cx = rnd.uniform(-0.2, 1.2) * fw + math.sin(t * 0.31 + i) * 10
            cy = rnd.uniform(0.15, 0.95) * fh + math.cos(t * 0.24 + i) * 7
            r = rnd.uniform(0.28, 0.55) * fw * (0.8 + amount * 0.5)
            v = int(26 * amount)
            d.ellipse((cx - r, cy - r * 0.55, cx + r, cy + r * 0.55), fill=(v, v, int(v * 1.06)))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=fw * 0.06))
        layer = layer.resize(canvas.size, Image.BILINEAR)
        return Image.blend(canvas, layer, 0.20 * amount + 0.06)

    def _glow(self, canvas: Image.Image, cx: float, cy: float, radius: float,
              colour, strength: float = 1.0) -> Image.Image:
        layer = Image.new("RGB", (self.W, self.H), (0, 0, 0))
        d = ImageDraw.Draw(layer)
        c = _mix_s(colour, (0, 0, 0), 0.15)
        d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=c)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=radius * 0.42))
        return Image.blend(canvas, layer, max(0.0, min(0.85, 0.55 * strength)))

    def _grain(self, img: Image.Image, t: float, amount: float, seed: int) -> Image.Image:
        if amount <= 0:
            return img
        # half-res noise then upscale: ~4x faster than full-res and reads as softer,
        # more filmic grain, which suits this grade
        nw, nh = self.W // 2, self.H // 2
        noise = Image.effect_noise((nw, nh), amount * 90)
        noise_rgb = Image.merge("RGB", (noise, noise, noise)).resize((self.W, self.H), Image.BILINEAR)
        return Image.blend(img, noise_rgb, 0.055)

    def _finish(self, img: Image.Image, amount: float, seed: int) -> Image.Image:
        img = img.convert("RGB")
        img = self._grain(img, 0.0, amount, seed)
        img = Image.composite(img, Image.new("RGB", (self.W, self.H), (0, 0, 0)), self._vignette_mask)
        return img

    def _figure(self, d: ImageDraw.ImageDraw, kind: str, cx: float, base_y: float,
                frame_h: float, colour, rim) -> None:
        """Draw a character silhouette plus a one-sided rim light."""
        spec = self.chars.get(kind)
        if not spec:
            return
        h = frame_h * float(spec["height_frac"])
        w = h * 0.34

        def body(offset: int, col) -> None:
            ox = cx + offset
            head_r = h * 0.115
            head_cy = base_y - h + head_r
            d.ellipse((ox - head_r, head_cy - head_r, ox + head_r, head_cy + head_r), fill=col)
            top = head_cy + head_r * 0.75
            if kind == "sari_silhouette":
                hip = base_y - h * 0.42
                d.polygon([(ox - w * 0.55, top), (ox + w * 0.55, top),
                           (ox + w * 0.92, base_y), (ox - w * 0.92, base_y)], fill=col)
                d.polygon([(ox - w * 0.5, top), (ox + w * 0.2, top),
                           (ox + w * 0.45, hip + h * 0.06), (ox - w * 0.62, hip)], fill=col)
            elif kind == "cane_silhouette":
                d.polygon([(ox - w * 0.42, top), (ox + w * 0.42, top),
                           (ox + w * 0.52, base_y), (ox - w * 0.5, base_y)], fill=col)
                d.line((ox + w * 0.62, base_y, ox + w * 0.5, top + h * 0.08), fill=col, width=max(1, int(h * 0.012)))
            else:  # doorway_presence
                d.polygon([(ox - w * 0.40, top), (ox + w * 0.40, top),
                           (ox + w * 0.66, base_y), (ox - w * 0.66, base_y)], fill=col)

        dark = tuple(max(0, int(c * 0.25)) for c in colour)
        if spec.get("rim_light", 0):
            body(-max(3, self.cw // 200), rim)
        body(0, dark)

    # ---------- shot kinds ----------

    def _scene_corridor(self, d, t, p, presence, rim):
        vx, vy = self.cw * 0.5, self.ch * 0.46
        push = 1.0 - min(0.30, t * 0.010)
        for i in range(7, 0, -1):
            s = (i / 7.0) ** 1.55 * push
            hw, hh = self.cw * 0.62 * s, self.ch * 0.46 * s
            rect = (vx - hw, vy - hh * 1.25, vx + hw, vy + hh * 1.25)
            d.rectangle(rect, outline=_mix_s(p["fill"], p["glow"], 0.16 + 0.05 * i),
                        width=max(1, int(self.cw * 0.006)))
        d.ellipse((vx - self.cw * 0.06, vy - self.ch * 0.05,
                   vx + self.cw * 0.06, vy + self.ch * 0.05), fill=_mix_s(p["glow"], (255, 255, 255), 0.35))
        if presence:
            self._figure(d, presence, vx + self.cw * 0.19, vy + self.ch * 0.30, self.ch * 0.52, p["bg"], rim)

    def _scene_stairwell(self, d, t, p, presence, rim):
        step_n = 9
        for i in range(step_n):
            x0 = self.cw * (0.10 + 0.075 * i) + math.sin(t * 0.4) * 1.5
            y = self.ch * (0.80 - 0.062 * i)
            d.rectangle((x0, y, self.cw * 0.98, y + self.ch * 0.030),
                        fill=_mix_s(p["bg"], p["fill"], 0.45 + 0.03 * i))
            d.line((x0, y, x0 + self.cw * 0.055, y - self.ch * 0.030),
                   fill=_mix_s(p["fill"], p["glow"], 0.30), width=max(1, int(self.cw * 0.004)))
        for i in range(6):
            x = self.cw * (0.16 + 0.13 * i)
            top = self.ch * (0.80 - 0.062 * i) - self.ch * 0.20
            d.line((x, top, x, self.ch * (0.80 - 0.062 * i)), fill=_mix_s(p["fill"], p["glow"], 0.22),
                   width=max(1, int(self.cw * 0.005)))
        if presence:
            self._figure(d, presence, self.cw * 0.62, self.ch * 0.50, self.ch * 0.40, p["bg"], rim)

    def _scene_doorway_figure(self, d, t, p, presence, rim):
        dx0, dy0 = self.cw * 0.22, self.ch * 0.16
        dx1, dy1 = self.cw * 0.78, self.ch * 0.86
        d.rectangle((dx0, dy0, dx1, dy1), fill=_mix_s(p["fill"], (255, 255, 255), 0.06))
        d.rectangle((dx0, dy0, dx1, dy1), outline=_mix_s(p["glow"], (0, 0, 0), 0.25),
                    width=max(2, int(self.cw * 0.010)))
        fl = self._flicker(t, 7)
        d.ellipse((dx0 + (dx1 - dx0) * 0.18, dy0 + (dy1 - dy0) * 0.12,
                   dx1 - (dx1 - dx0) * 0.18, dy0 + (dy1 - dy0) * 0.62),
                  fill=_mix_s(p["glow"], (255, 255, 255), 0.10 * fl))
        self._figure(d, presence or "doorway_presence", (dx0 + dx1) / 2, dy1 - (dy1 - dy0) * 0.02,
                     (dy1 - dy0) * 0.86, p["bg"], rim)

    def _scene_door_crack(self, d, t, p, presence, rim):
        d.rectangle((0, 0, self.cw, self.ch), fill=p["bg"])
        cx = self.cw * (0.5 + math.sin(t * 0.22) * 0.006)
        w = self.cw * 0.008
        d.polygon([(cx - w, self.ch * 0.10), (cx + w, self.ch * 0.08),
                   (cx + w * 2.6, self.ch * 0.94), (cx - w * 2.6, self.ch * 0.94)],
                  fill=_mix_s(p["glow"], (255, 255, 255), 0.20 * self._flicker(t, 3)))
        if presence:
            self._figure(d, presence, cx + self.cw * 0.03, self.ch * 0.94, self.ch * 0.60, p["bg"], rim)

    def _scene_mirror_hall(self, d, t, p, presence, rim):
        mx0, my0 = self.cw * 0.20, self.ch * 0.10
        mx1, my1 = self.cw * 0.80, self.ch * 0.78
        # interior must be brighter than the room, otherwise a silhouette has nothing
        # to read against
        d.rectangle((mx0, my0, mx1, my1), fill=_mix_s(p["fill"], p["glow"], 0.34))
        d.rectangle((mx0 - self.cw * 0.03, my0 - self.ch * 0.014,
                     mx1 + self.cw * 0.03, my0 + self.ch * 0.006), fill=_mix_s(p["fill"], p["glow"], 0.35))
        d.rectangle((mx0 - self.cw * 0.03, my1 - self.ch * 0.008,
                     mx1 + self.cw * 0.03, my1 + self.ch * 0.012), fill=_mix_s(p["fill"], p["glow"], 0.35))
        d.rectangle((mx0 - self.cw * 0.028, my0 - self.ch * 0.014, mx0, my1 + self.ch * 0.012),
                    fill=_mix_s(p["fill"], p["glow"], 0.30))
        d.rectangle((mx1, my0 - self.ch * 0.014, mx1 + self.cw * 0.028, my1 + self.ch * 0.012),
                    fill=_mix_s(p["fill"], p["glow"], 0.30))
        step = self.cw * 0.16
        off = (t * step) % step
        for k in range(9):
            yy = my0 + ((k * step + off) % (my1 - my0))
            band = _mix_s(p["fill"], p["glow"], 0.10 + 0.05 * (k % 3))
            d.rectangle((mx0 + self.cw * 0.01, yy, mx1 - self.cw * 0.01, yy + self.ch * 0.006), fill=band)
        if presence:
            self._figure(d, presence, self.cw * 0.5, my1, (my1 - my0) * 0.92, _mix_s(p["fill"], p["glow"], 0.55), rim)

    def _scene_window_bars(self, d, t, p, presence, rim):
        wx0, wy0 = self.cw * 0.16, self.ch * 0.12
        wx1, wy1 = self.cw * 0.84, self.ch * 0.58
        d.rectangle((wx0, wy0, wx1, wy1), fill=_mix_s(p["bg"], p["glow"], 0.10))
        for i in range(5):
            x = wx0 + (wx1 - wx0) * (i + 1) / 6
            d.line((x, wy0, x, wy1), fill=_mix_s(p["bg"], (0, 0, 0), 0.2), width=max(2, int(self.cw * 0.012)))
        d.line((wx0, (wy0 + wy1) / 2, wx1, (wy0 + wy1) / 2), fill=_mix_s(p["bg"], (0, 0, 0), 0.2),
               width=max(2, int(self.cw * 0.010)))
        for i in range(5):
            x = wx0 + (wx1 - wx0) * (i + 1) / 6
            d.polygon([(x, wy1), (x + self.cw * 0.09, wy1), (x + self.cw * 0.22, self.ch * 0.92),
                       (x - self.cw * 0.03, self.ch * 0.92)], fill=_mix_s(p["glow"], (0, 0, 0), 0.72))
        d.rectangle((wx0 - self.cw * 0.03, wy0 - self.ch * 0.012,
                     wx1 + self.cw * 0.03, wy1 + self.ch * 0.012), fill=_mix_s(p["fill"], p["glow"], 0.25))
        if presence:
            self._figure(d, presence, self.cw * 0.30, self.ch * 0.94, self.ch * 0.30, p["bg"], rim)

    def _scene_kitchen_clock(self, d, t, p, presence, rim):
        cx, cy = self.cw * 0.5, self.ch * 0.40
        r = self.cw * 0.30
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_mix_s(p["fill"], p["glow"], 0.18),
                  outline=_mix_s(p["glow"], (0, 0, 0), 0.35), width=max(2, int(self.cw * 0.012)))
        for i in range(12):
            a = math.radians(i * 30 - 90)
            x0, y0 = cx + math.cos(a) * r * 0.80, cy + math.sin(a) * r * 0.80
            x1, y1 = cx + math.cos(a) * r * 0.90, cy + math.sin(a) * r * 0.90
            d.line((x0, y0, x1, y1), fill=_mix_s(p["glow"], (0, 0, 0), 0.45), width=max(1, int(self.cw * 0.005)))
        for label, ang in (("hour", -90 + 2.5 * 30), ("minute", -90 + 30 * 6)):
            ln = r * (0.46 if label == "hour" else 0.72)
            a = math.radians(ang)
            d.line((cx, cy, cx + math.cos(a) * ln, cy + math.sin(a) * ln),
                   fill=_mix_s(p["glow"], (255, 255, 255), 0.25), width=max(2, int(self.cw * 0.010)))
        tick = self._flicker(t, 11)
        d.ellipse((cx - self.cw * 0.012, cy - self.cw * 0.012, cx + self.cw * 0.012, cy + self.cw * 0.012),
                  fill=_mix_s(p["glow"], (0, 0, 0), 0.2 * (1 - tick)))
        d.rectangle((0, self.ch * 0.78, self.cw, self.ch), fill=_mix_s(p["bg"], p["fill"], 0.30))
        if presence:
            self._figure(d, presence, self.cw * 0.82, self.ch * 0.86, self.ch * 0.26, p["bg"], rim)

    def _scene_courtyard_night(self, d, t, p, presence, rim):
        horizon = self.ch * 0.62
        rnd = random.Random(99)
        for i in range(60):
            x, y = rnd.uniform(0, self.cw), rnd.uniform(0, horizon * 0.9)
            b = int(60 + 120 * (1 - y / horizon))
            d.point((x, y), fill=(b, b, min(MAXC, int(b * 1.15))))
        d.rectangle((0, horizon, self.cw, self.ch), fill=_mix_s(p["bg"], (0, 0, 0), 0.45))
        for i in range(7):
            x = self.cw * (0.06 + 0.14 * i)
            th = self.ch * rnd.uniform(0.05, 0.10)
            d.polygon([(x - self.cw * 0.02, horizon), (x + self.cw * 0.02, horizon),
                       (x, horizon - th)], fill=(4, 5, 8))
        d.rectangle((self.cw * 0.30, horizon - self.ch * 0.16, self.cw * 0.70, horizon),
                    fill=(4, 5, 8))
        d.polygon([(self.cw * 0.28, horizon - self.ch * 0.16), (self.cw * 0.72, horizon - self.ch * 0.16),
                   (self.cw * 0.50, horizon - self.ch * 0.25)], fill=(4, 5, 8))
        wx, wy = self.cw * 0.44, horizon - self.ch * 0.10
        d.rectangle((wx, wy, wx + self.cw * 0.09, wy + self.ch * 0.035),
                    fill=_mix_s((200, 150, 70), (0, 0, 0), 0.35 * self._flicker(t, 5)))
        if presence:
            self._figure(d, presence, self.cw * 0.5, horizon + self.ch * 0.02, self.ch * 0.28, (3, 4, 6), rim)

    def _scene_courtyard_mogra(self, d, t, p, presence, rim):
        horizon = self.ch * 0.58
        d.rectangle((0, horizon, self.cw, self.ch), fill=_mix_s(p["bg"], p["fill"], 0.55))
        for i in range(6):
            x = self.cw * (0.12 + 0.15 * i)
            d.line((x, horizon + self.ch * 0.16, x + math.sin(t * 0.7 + i) * self.cw * 0.01,
                    horizon - self.ch * 0.12), fill=_mix_s(p["fill"], (0, 0, 0), 0.45),
                   width=max(2, int(self.cw * 0.006)))
        rnd = random.Random(41)
        for _ in range(90):
            x = rnd.uniform(self.cw * 0.08, self.cw * 0.94)
            y = rnd.uniform(horizon - self.ch * 0.14, horizon + self.ch * 0.14)
            r = self.cw * rnd.uniform(0.006, 0.013)
            b = self._flicker(t, 3)
            d.ellipse((x - r, y - r, x + r, y + r),
                      fill=_mix_s((232, 238, 224), (0, 0, 0), 0.30 * b))
        if presence:
            self._figure(d, presence, self.cw * 0.78, self.ch * 0.90, self.ch * 0.34, _mix_s(p["bg"], (0, 0, 0), 0.5), rim)

    def _scene_well_dry(self, d, t, p, presence, rim):
        cx, cy = self.cw * 0.5, self.ch * 0.58
        rx, ry = self.cw * 0.42, self.ch * 0.11
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=_mix_s(p["fill"], (0, 0, 0), 0.35))
        d.ellipse((cx - rx * 0.86, cy - ry * 0.74, cx + rx * 0.86, cy + ry * 0.74), fill=(2, 3, 5))
        for k in range(4):
            a = 0.25 + 0.16 * k + 0.02 * math.sin(t * 0.9 + k)
            d.arc((cx - rx * 0.86, cy - ry * 0.74, cx + rx * 0.86, cy + ry * 0.74),
                  start=int(190 + k * 8), end=int(250 + k * 8), fill=_mix_s(p["glow"], (0, 0, 0), 0.62))
        d.ellipse((cx - rx * 0.30, cy - ry * 0.16, cx + rx * 0.30, cy + ry * 0.16),
                  fill=_mix_s(p["glow"], (0, 0, 0), 0.80))
        for i in range(8):
            x = self.cw * (0.02 + 0.14 * i)
            d.line((x, self.ch * 0.58, x + self.cw * 0.05, self.ch), fill=_mix_s(p["bg"], p["fill"], 0.4),
                   width=max(1, int(self.cw * 0.004)))
        if presence:
            self._figure(d, presence, self.cw * 0.5, cy + self.ch * 0.02, self.ch * 0.20, (1, 2, 3), rim)

    def _scene_almirah_notes(self, d, t, p, presence, rim):
        d.rectangle((0, 0, self.cw, self.ch), fill=_mix_s(p["bg"], (0, 0, 0), 0.25))
        ax0, ay0 = self.cw * 0.08, self.ch * 0.14
        ax1, ay1 = self.cw * 0.92, self.ch * 0.86
        d.rectangle((ax0, ay0, ax1, ay1), fill=_mix_s(p["fill"], p["glow"], 0.10))
        d.rectangle((ax0, ay0, ax1, ay1), outline=_mix_s(p["glow"], (0, 0, 0), 0.5),
                    width=max(2, int(self.cw * 0.008)))
        d.line((self.cw * 0.5, ay0, self.cw * 0.5, ay1), fill=_mix_s(p["bg"], (0, 0, 0), 0.45),
               width=max(2, int(self.cw * 0.006)))
        px, py = self.cw * 0.56, self.ch * 0.34
        pw, ph = self.cw * 0.34, self.ch * 0.34
        sway = math.sin(t * 0.6) * self.cw * 0.004
        d.rectangle((px + sway, py, px + pw + sway, py + ph),
                    fill=_mix_s((206, 196, 168), (0, 0, 0), 0.30 + 0.05 * self._flicker(t, 13)))
        for k in range(7):
            yy = py + ph * (0.16 + 0.10 * k)
            wfrac = 0.55 + 0.28 * ((k * 7) % 5) / 5
            d.line((px + pw * 0.12 + sway, yy, px + pw * (0.12 + wfrac * 0.62) + sway, yy),
                   fill=_mix_s((60, 50, 40), (0, 0, 0), 0.25), width=max(1, int(self.cw * 0.006)))

    def _scene_cassette(self, d, t, p, presence, rim):
        d.rectangle((0, 0, self.cw, self.ch), fill=_mix_s(p["bg"], (0, 0, 0), 0.30))
        cx, cy = self.cw * 0.5, self.ch * 0.46
        w, h = self.cw * 0.68, self.ch * 0.34
        d.rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                    fill=_mix_s(p["fill"], (0, 0, 0), 0.25),
                    outline=_mix_s(p["glow"], (0, 0, 0), 0.55), width=max(2, int(self.cw * 0.008)))
        d.rectangle((cx - w * 0.40, cy - h * 0.22, cx + w * 0.40, cy + h * 0.02),
                    fill=_mix_s(p["bg"], (0, 0, 0), 0.35))
        spin = t * 2.2
        for sx in (cx - w * 0.22, cx + w * 0.22):
            r = h * 0.16
            d.ellipse((sx - r, cy - h * 0.10 - r, sx + r, cy - h * 0.10 + r),
                      fill=_mix_s(p["glow"], (0, 0, 0), 0.55), outline=_mix_s(p["glow"], (255, 255, 255), 0.2),
                      width=max(1, int(self.cw * 0.004)))
            a = math.radians((spin * 40) % 360)
            d.line((sx, cy - h * 0.10, sx + math.cos(a) * r * 0.7, cy - h * 0.10 + math.sin(a) * r * 0.7),
                   fill=_mix_s(p["glow"], (255, 255, 255), 0.35), width=max(1, int(self.cw * 0.004)))
        for k in range(3):
            d.rectangle((cx - w * 0.34, cy + h * 0.10 + k * h * 0.07, cx + w * 0.34, cy + h * 0.13 + k * h * 0.07),
                        fill=_mix_s(p["glow"], (0, 0, 0), 0.45 + 0.1 * k))

    def _scene_lamp_table(self, d, t, p, presence, rim):
        d.rectangle((0, 0, self.cw, self.ch), fill=_mix_s(p["bg"], (0, 0, 0), 0.35))
        d.rectangle((0, self.ch * 0.66, self.cw, self.ch), fill=_mix_s(p["fill"], (0, 0, 0), 0.30))
        cx = self.cw * 0.5
        d.rectangle((cx - self.cw * 0.012, self.ch * 0.44, cx + self.cw * 0.012, self.ch * 0.66),
                    fill=_mix_s((226, 214, 186), (0, 0, 0), 0.25))
        fl = self._flicker(t, 21)
        fh = self.ch * (0.045 + 0.012 * fl)
        fw = self.cw * (0.018 + 0.006 * fl)
        d.ellipse((cx - fw, self.ch * 0.44 - fh, cx + fw, self.ch * 0.44 + fh * 0.4),
                  fill=_mix_s((255, 226, 150), (0, 0, 0), 0.10 * fl))
        if presence:
            self._figure(d, presence, self.cw * 0.18, self.ch * 0.70, self.ch * 0.30, (2, 2, 3), rim)

    def _scene_phone_dark(self, d, t, p, presence, rim):
        d.rectangle((0, 0, self.cw, self.ch), fill=_mix_s(p["bg"], (0, 0, 0), 0.40))
        d.rectangle((0, self.ch * 0.72, self.cw, self.ch), fill=(2, 3, 5))
        sx, sy = self.cw * 0.34, self.ch * 0.56
        w, h = self.cw * 0.32, self.ch * 0.13
        pulse = 0.55 + 0.45 * abs(math.sin(t * 2.4))
        d.rectangle((sx, sy, sx + w, sy + h), fill=_mix_s(p["glow"], (255, 255, 255), 0.55 * pulse),
                    outline=_mix_s(p["glow"], (0, 0, 0), 0.35), width=max(1, int(self.cw * 0.006)))
        d.rectangle((sx + w * 0.10, sy + h * 0.72, sx + w * 0.30, sy + h * 0.86),
                    fill=_mix_s(p["glow"], (0, 0, 0), 0.25))

    def _scene_nana_room_dark(self, d, t, p, presence, rim):
        d.rectangle((0, 0, self.cw, self.ch), fill=p["bg"])
        dx0, dy0 = self.cw * 0.34, self.ch * 0.22
        dx1, dy1 = self.cw * 0.66, self.ch * 0.74
        fl = self._flicker(t, 29)
        d.rectangle((dx0, dy0, dx1, dy1), fill=_mix_s(p["glow"], (0, 0, 0), 0.55 + 0.12 * fl))
        d.rectangle((dx0 - self.cw * 0.02, dy0 - self.ch * 0.01, dx0, dy1), fill=(3, 3, 5))
        d.rectangle((dx1, dy0 - self.ch * 0.01, dx1 + self.cw * 0.02, dy1), fill=(3, 3, 5))
        d.rectangle((0, self.ch * 0.74, self.cw, self.ch), fill=(3, 3, 5))
        d.rectangle((self.cw * 0.06, self.ch * 0.56, self.cw * 0.26, self.ch * 0.74), fill=(5, 5, 8))
        if presence:
            self._figure(d, presence, (dx0 + dx1) / 2, dy1, (dy1 - dy0) * 0.95, (2, 2, 3), rim)

    _SCENES: dict[str, str] = {}

    def scene_fn(self, kind: str) -> Callable[..., None]:
        table = {
            "corridor": self._scene_corridor,
            "stairwell": self._scene_stairwell,
            "doorway_figure": self._scene_doorway_figure,
            "door_crack": self._scene_door_crack,
            "mirror_hall": self._scene_mirror_hall,
            "window_bars": self._scene_window_bars,
            "kitchen_clock": self._scene_kitchen_clock,
            "courtyard_night": self._scene_courtyard_night,
            "courtyard_mogra": self._scene_courtyard_mogra,
            "well_dry": self._scene_well_dry,
            "almirah_notes": self._scene_almirah_notes,
            "cassette": self._scene_cassette,
            "lamp_table": self._scene_lamp_table,
            "phone_dark": self._scene_phone_dark,
            "nana_room_dark": self._scene_nana_room_dark,
        }
        return table.get(kind, self._scene_corridor)

    # ---------- public API ----------

    def render_shot(self, shot: dict[str, Any], out_mp4: Path, seed: int) -> Path:
        kind = shot.get("kind", "corridor")
        duration = float(shot["duration"])
        spec = self.kinds.get(kind, self.kinds["corridor"])
        pal = self._pal(spec["palette"])
        presence = shot.get("character_visual")
        rim = _mix_s(pal["glow"], (255, 255, 255), 0.15)
        frames = int(shot.get("frames") or round(duration * self.fps))
        grain = float(self.cfg["visual"]["motion"]["grain"])

        cmd = [
            str(ffmpeg.ffmpeg_bin()), "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{self.W}x{self.H}",
            "-r", str(self.fps), "-i", "-",
            "-an",
            "-c:v", self.cfg["video"]["vcodec"], "-crf", str(self.cfg["video"]["crf"]),
            "-preset", self.cfg["video"]["preset"], "-pix_fmt", self.cfg["video"]["pix_fmt"],
            str(out_mp4),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        scene = self.scene_fn(kind)
        push = spec.get("camera", "")
        drift = float(self.motion["drift_px"])

        try:
            for i in range(frames):
                t = i / self.fps
                small = _vgrad((self.cw, self.ch),
                               _mix_s(pal["bg"], (0, 0, 0), 0.35),
                               _mix_s(pal["bg"], pal["fill"], 0.45))
                small = self._fog(small, t, float(spec.get("fog", 0.3)), seed)
                d = ImageDraw.Draw(small)

                # handheld drift + scripted push-in (zoom a centred crop back to frame)
                ox = math.sin(t * 0.7 + seed) * drift
                oy = math.cos(t * 0.53 + seed) * drift * 0.6

                scene(d, t, pal, presence, rim)

                if "push" in push:
                    # 6% push shots move more than the standard 4%
                    k = max(0.86, 1.0 - (t / max(duration, 0.001)) * (0.06 if "6%" in push else 0.04))
                else:
                    k = 1.0

                if ox or oy or k < 1.0:
                    cw2 = int(self.cw * k)
                    ch2 = int(self.ch * k)
                    cw2, ch2 = max(8, min(self.cw, cw2)), max(8, min(self.ch, ch2))
                    box = ((self.cw - cw2) // 2, (self.ch - ch2) // 2,
                           (self.cw - cw2) // 2 + cw2, (self.ch - ch2) // 2 + ch2)
                    zoomed = small.crop(box).resize((self.cw, self.ch), Image.BILINEAR)
                    if ox or oy:
                        layer = Image.new("RGB", (self.cw, self.ch), _mix_s(pal["bg"], (0, 0, 0), 0.35))
                        layer.paste(zoomed, (int(ox), int(oy)))
                        small = layer
                    else:
                        small = zoomed

                full = small.resize((self.W, self.H), Image.BILINEAR)
                full = self._finish(full, grain, seed + i)
                try:
                    proc.stdin.write(full.tobytes())
                except (BrokenPipeError, OSError) as exc:
                    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
                    proc.wait()
                    raise RuntimeError(
                        f"ffmpeg stopped while encoding {out_mp4.name} "
                        f"({type(exc).__name__}: {exc}):\n{err[-1500:]}"
                    ) from exc
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

        err = (proc.stderr.read().decode("utf-8", "replace") if proc.stderr else "")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg encode failed for {out_mp4.name}:\n{err[-1500:]}")
        return out_mp4