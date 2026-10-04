"""AI-cinematic still provider: photorealistic frames + Ken Burns, free.

Why this provider exists
------------------------
The `motion` provider draws geometry: corridors, silhouettes, fog, grain. That is
not what an "AI cinematic story" Short looks like, and on screen it read as abstract
motion graphics rather than a filmed scene. Those channels get their look from
photorealistic AI imagery with a slow push over it, so that is what this provider
does.

It calls a public text-to-image endpoint that needs no API key, so software cost
stays zero. That endpoint has two behaviours that are easy to get wrong, and both
are handled explicitly below because getting either one wrong produces a silently
broken render:

1. It rate-limits with HTTP 402 and no body. A burst of requests trips it; the same
   request succeeds again after a cooldown. So 402 is treated as "slow down", not
   as "this is impossible", and retried with a growing backoff.
2. Above roughly 590k pixels it ignores the requested size and silently returns a
   768x768 square. A 9:16 request therefore comes back as a square with a 200 status.
   Every response is dimension-checked, because feeding a square into a vertical
   timeline would crop the composition to nothing.

The frames come back at 576x1024. They are upscaled with a Lanczos pass and an
unsharp mask to the delivery size, then given a slow push-in, grain and a vignette,
which is what makes an upscaled frame read as a moving shot rather than a still.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

from lib import config, ffmpeg

STILLS_DIRNAME = "stills"


class ImageProviderUnavailable(RuntimeError):
    """Raised when stills cannot be obtained after every retry."""


def _endpoint() -> str:
    return str(config.load_config()["visual"]["aiimage"]["endpoint"])


def _settings(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg["visual"]["aiimage"]


def _prompt_for(shot: dict[str, Any]) -> str:
    """The visual prompt for this shot, already carrying the locked style base.

    Built by the prompt-engineer agent and carried on the shot record, so the same
    prompt drives the still, the cache key and the reproducibility check.
    """
    return (shot.get("visual_prompt") or "").strip()


def _cache_key(shot: dict[str, Any], seed: int, w: int, h: int, model: str) -> str:
    raw = f"{_prompt_for(shot)}|{seed}|{w}x{h}|{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def fetch_still(prompt: str, out_jpg: Path, seed: int, cfg: dict[str, Any]) -> Path:
    """Download one still, with rate-limit backoff and a hard size check."""
    s = _settings(cfg)
    w, h = int(s["width"]), int(s["height"])
    model = str(s.get("model", "flux"))
    endpoint = str(s["endpoint"]).rstrip("/")
    attempts = int(s.get("max_attempts", 6))
    base_sleep = float(s.get("retry_sleep_s", 20))

    last = ""
    for attempt in range(1, attempts + 1):
        url = (f"{endpoint}/{urllib.parse.quote(prompt, safe='')}"
               f"?width={w}&height={h}&model={model}&seed={seed}&nologo=true")
        out_jpg.parent.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sheesha-pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=float(s.get("timeout_s", 120))) as resp:
                payload = resp.read()
            if len(payload) < 2048:
                raise ImageProviderUnavailable(f"still too small ({len(payload)} B)")

            tmp = out_jpg.with_suffix(".part")
            tmp.write_bytes(payload)
            with Image.open(tmp) as im:
                actual = im.size
            if actual != (w, h):
                # The endpoint silently substitutes 768x768 for oversized requests.
                # Trusting the status code here is how a square frame reaches a
                # vertical timeline, so it is rejected outright.
                tmp.unlink(missing_ok=True)
                raise ImageProviderUnavailable(
                    f"endpoint returned {actual[0]}x{actual[1]}, asked for {w}x{h}")
            tmp.replace(out_jpg)
            return out_jpg
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code in (402, 429, 503):
                # rate limited / busy: back off and try again
                wait = base_sleep * attempt
                config.log_line("aiimage", f"rate limited ({last}), retry {attempt} in {wait:.0f}s")
                time.sleep(wait)
                continue
            raise ImageProviderUnavailable(f"{last} for seed {seed}") from exc
        except ImageProviderUnavailable:
            # a real size/shape failure, not a rate limit
            last = "bad response"
            time.sleep(base_sleep)
        except Exception as exc:  # network reset, DNS, timeout
            last = type(exc).__name__
            config.log_line("aiimage", f"{last}, retry {attempt}")
            time.sleep(base_sleep * attempt)

    raise ImageProviderUnavailable(f"gave up after {attempts} attempts (last: {last})")


def upscale_for_motion(src_jpg: Path, dst_png: Path, width: int, height: int,
                       margin: float) -> Path:
    """Lanczos upscale plus a light unsharp mask.

    The still arrives at 576x1024 and has to fill 1080x1920, so it is enlarged with
    headroom (`margin`) to give the push-in room to move without running out of
    pixels. The unsharp mask counteracts the softness Lanczos leaves behind; the film
    grain added afterwards hides what is left.
    """
    dst_png.parent.mkdir(parents=True, exist_ok=True)
    tw, th = int(width * margin), int(height * margin)
    with Image.open(src_jpg) as im:
        im = im.convert("RGB").resize((tw, th), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=110, threshold=3))
        im.save(dst_png, "PNG")
    return dst_png


class AIImageProvider:
    """Photorealistic stills, animated to shot length. Same shape as the other providers."""

    name = "aiimage"

    def __init__(self, cfg: dict[str, Any], width: int, height: int, fps: int) -> None:
        self.cfg = cfg
        self.W, self.H, self.fps = width, height, fps
        self.stills = config.RENDER_DIR / STILLS_DIRNAME

    def render_shot(self, shot: dict[str, Any], out_mp4: Path, seed: int) -> Path:
        s = _settings(self.cfg)
        prompt = _prompt_for(shot)
        if not prompt:
            raise ImageProviderUnavailable(f"shot {shot.get('id')} has no visual_prompt")
        if int(shot.get("character_visual") or 0):
            # Silhouettes are fine, faces are not; the channel is face-free by design.
            prompt += ", face not visible, silhouette only, backlit shadow"

        w, h = int(s["width"]), int(s["height"])
        key = _cache_key(shot, seed, w, h, str(s.get("model", "flux")))
        still = self.stills / f"{shot['id']}_{key}.jpg"
        if not still.exists():
            fetch_still(prompt, still, seed, self.cfg)

        big = self.stills / f"{shot['id']}_{key}_big.png"
        upscale_for_motion(still, big, self.W, self.H, float(s.get("upscale_margin", 1.3)))

        frames = int(shot.get("frames") or round(float(shot["duration"]) * self.fps))
        push = float(s.get("push_in", 0.12))
        dur = max(0.1, frames / self.fps)

        # A crop that tightens over time is the push-in. Cropping from an oversized
        # source and scaling down keeps it judder-free, which zoompan does not.
        crop = (f"crop=w='{self.W}*(1+{push}*t/{dur:.4f})':"
                f"h='{self.H}*(1+{push}*t/{dur:.4f})':"
                f"x='(iw-ow)/2':y='(ih-oh)/2',"
                f"scale={self.W}:{self.H}:flags=lanczos")
        grade = (f"eq=contrast=1.06:saturation=0.92:gamma=0.98,"
                 f"noise=alls={int(s.get('grain', 9))}:allf=t+u,"
                 f"vignette=PI/5.2")
        vf = f"{crop},{grade}"

        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg.run([
            "-y", "-v", "error", "-loop", "1", "-i", str(big),
            "-vf", vf,
            "-frames:v", str(frames), "-r", str(self.fps),
            "-c:v", str(self.cfg["video"]["vcodec"]),
            "-crf", str(self.cfg["video"]["crf"]),
            "-preset", str(self.cfg["video"]["preset"]),
            "-pix_fmt", str(self.cfg["video"]["pix_fmt"]),
            str(out_mp4),
        ])
        big.unlink(missing_ok=True)
        return out_mp4

    def render_batch(self, shots: list[dict[str, Any]], out_dir: Path,
                     seed_base: int) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        made: list[Path] = []
        for i, shot in enumerate(shots):
            target = out_dir / (
                f"{shot['id']}_{config.slug(shot['kind'])}_"
                f"ai_{shot['duration']:.2f}.mp4")
            if not target.exists():
                self.render_shot(shot, target, seed_base + i * 101)
            made.append(target)
        return made


def probe() -> dict[str, Any]:
    """Report whether stills are reachable, for `preflight`."""
    cfg = config.load_config()
    s = _settings(cfg)
    info: dict[str, Any] = {
        "endpoint": s["endpoint"],
        "requested": f"{s['width']}x{s['height']}",
        "max_px": int(s["width"]) * int(s["height"]),
        "reachable": False,
        "detail": "",
    }
    if info["max_px"] > 600_000:
        # Above this the endpoint quietly returns a square instead of the request.
        info["detail"] = f"requested size is over the endpoint's ~590k px limit"
        return info
    probe_path = config.RENDER_DIR / STILLS_DIRNAME / "_probe.jpg"
    try:
        fetch_still("a dim empty room, cinematic film still", probe_path, 1, cfg)
        probe_path.unlink(missing_ok=True)
        info["reachable"] = True
        info["detail"] = "still fetch ok"
    except Exception as exc:
        info["detail"] = str(exc)
    return info