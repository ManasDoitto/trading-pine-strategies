"""Video generation over the Pollinations API. Fully unattended, no browser.

Why this provider exists
------------------------
The `wan` provider needs a Colab session, which means a browser, a Google login and
three or four hours of the user's attention. This provider is a single HTTP call per
shot, so `python pipeline.py episode N` produces the finished Short by itself.

It costs a little money. Video models there are priced per generated second and are
marked paid-only, so a free-quest balance will not cover them. For a 30-second Short
that is roughly:

    alibaba/wan-2.2-fast          0.01 pollen/s   ->  about 0.30 USD
    bytedance/seedance-1-pro-fast 0.025 pollen/s  ->  about 0.75 USD
    alibaba/wan-3.0              0.068 pollen/s  ->  about 2.04 USD
    alibaba/wan-2.7              0.1   pollen/s  ->  about 3.00 USD

Three details this has to get right, each learned from the API rather than guessed:

* There is no ``negative_prompt`` parameter. The models here do not accept one, so
  the negative vocabulary is folded into the positive prompt as explicit "without"
  clauses rather than silently dropped.
* ``duration`` and ``aspectRatio`` are model-dependent and are only sent when the
  model is known to accept them; sending them blindly is rejected.
* The endpoint returns the MP4 in the response body, with no status field. A model
  that is down still returns 200 with a short JSON error, so every response is
  content-checked with ffprobe before it is trusted as a clip.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from lib import config, ffmpeg
from lib.visuals.fit import fit

BASE = "https://gen.pollinations.ai"

# duration/aspectRatio are per-model. Sending either to a model that ignores them
# gets the request rejected, so they are declared rather than guessed.
SUPPORTS_DURATION = {
    "alibaba/wan-3.0", "alibaba/wan-2.7", "alibaba/wan-2.6", "alibaba/wan-2.2-fast",
    "bytedance/seedance-1-pro-fast", "bytedance/seedance-2.0",
    "bytedance/seedance-2.0-mini", "bytedance/seedance-2.0-fast",
}


class VideoUnavailable(RuntimeError):
    """Raised when the API cannot produce a clip after every retry."""


def api_key(cfg: dict[str, Any]) -> str:
    """Read the key from config, or from the environment.

    The environment is checked first so the key can stay out of a tracked file.
    """
    env = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if env:
        return env
    key = str(cfg["visual"]["pollinations"].get("api_key", "")).strip()
    if key:
        return key
    raise VideoUnavailable(
        "no Pollinations API key.\n"
        "  set it in the environment:   set POLLINATIONS_API_KEY=sk_...\n"
        "  or in config/pipeline.json -> visual.pollinations.api_key\n"
        "  get one at https://enter.pollinations.ai"
    )


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg["visual"]["pollinations"]


def video_style_base() -> str:
    raw = config.read_text(config.STYLE_VIDEO_PATH, "")
    body = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return ", ".join(body)


def _negative_clause(shot: dict[str, Any]) -> str:
    """Fold the negative vocabulary into the prompt.

    These models have no negative_prompt field, so the exclusions are restated as
    things to avoid. Kept short on purpose: a long clause of negations reads as noise
    to a video model and can start pulling the very thing it names into frame.
    """
    bits = ["without subtitles or text on screen", "no visible faces",
            "no logos or watermarks"]
    if shot.get("character_visual"):
        bits.append("the figure stays a dark backlit silhouette")
    return ", ".join(bits)


def _join(*parts: str) -> str:
    seen: dict[str, str] = {}
    for part in parts:
        for term in (part or "").split(","):
            key = term.strip().lower()
            if key and key not in seen:
                seen[key] = term.strip()
    return ", ".join(seen.values())


def build_prompt(shot: dict[str, Any], cfg: dict[str, Any],
                 camera: str = "") -> str:
    style = video_style_base()
    text = _join(style, shot.get("visual_prompt", ""), camera)
    if shot.get("character_visual"):
        text += ", unidentifiable figure, face hidden, backlit silhouette only"
    return f"{text}. {_negative_clause(shot)}"


def generate(prompt: str, out_mp4: Path, seed: int, cfg: dict[str, Any]) -> Path:
    """Call the video endpoint once, with retries, and validate what came back."""
    s = settings(cfg)
    key = api_key(cfg)
    model = str(s["model"])
    w, h = int(s["width"]), int(s["height"])
    dur = int(s.get("duration_s", 5))
    attempts = int(s.get("max_attempts", 4))

    q = {
        "model": model,
        "width": str(w),
        "height": str(h),
        "seed": str(seed),
        "quality": str(s.get("quality", "medium")),
    }
    if model in SUPPORTS_DURATION:
        q["duration"] = str(dur)
    if s.get("aspect_ratio"):
        q["aspectRatio"] = str(s["aspect_ratio"])

    url = f"{BASE}/video/{urllib.parse.quote(prompt, safe='')}?{urllib.parse.urlencode(q)}"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    last = ""
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {key}",
                "User-Agent": "sheesha-pipeline/1.0",
            })
            with urllib.request.urlopen(req, timeout=float(s.get("timeout_s", 600))) as resp:
                payload = resp.read()
                ctype = resp.headers.get("Content-Type", "")

            if len(payload) < 50_000:
                # A failing model returns 200 with a short JSON body, so size is the
                # cheapest reliable tell before ffprobe.
                detail = payload[:300].decode("utf-8", "replace")
                raise VideoUnavailable(f"short response ({len(payload)} B, {ctype}): {detail}")

            tmp = out_mp4.with_suffix(".part")
            tmp.write_bytes(payload)
            try:
                info = ffmpeg.probe(tmp)
            except Exception:
                tmp.unlink(missing_ok=True)
                raise VideoUnavailable("response was not a readable video")
            if not info.get("streams"):
                tmp.unlink(missing_ok=True)
                raise VideoUnavailable("response had no video stream")
            tmp.replace(out_mp4)
            config.log_line("pollinations", f"{out_mp4.name} ok seed={seed}")
            return out_mp4
        except urllib.error.HTTPError as exc:
            body = (exc.read() or b"")[:300].decode("utf-8", "replace")
            last = f"HTTP {exc.code}: {body}"
            if exc.code in (402, 429, 500, 502, 503, 504):
                wait = float(s.get("retry_sleep_s", 20)) * attempt
                config.log_line("pollinations", f"{last} -> retry {attempt} in {wait:.0f}s")
                time.sleep(wait)
                continue
            # 401/403 will not fix themselves: bad or unpaid key.
            raise VideoUnavailable(last) from exc
        except VideoUnavailable as exc:
            last = str(exc)
            time.sleep(float(s.get("retry_sleep_s", 20)) * attempt)
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(float(s.get("retry_sleep_s", 20)) * attempt)

    raise VideoUnavailable(f"gave up after {attempts} attempts (last: {last})")


class PollinationsProvider:
    """Video clips straight from the API. Same shape as the other providers."""

    name = "pollinations"

    def __init__(self, cfg: dict[str, Any], width: int, height: int, fps: int) -> None:
        self.cfg = cfg
        self.W, self.H, self.fps = width, height, fps

    def _dir(self) -> Path:
        d = config.CLIPS_DIR / "pollinations"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def render_shot(self, shot: dict[str, Any], out_mp4: Path, seed: int) -> Path:
        prompt = build_prompt(shot, self.cfg, str(shot.get("camera", "")))
        raw = self._dir() / f"{config.slug(shot['id'])}_seed{seed}.mp4"
        if not raw.exists():
            generate(prompt, raw, seed, self.cfg)
        return fit(raw, out_mp4, int(shot["frames"]), self.cfg,
                   int(settings(self.cfg).get("grain", 6)))

    def render_batch(self, shots: list[dict[str, Any]], out_dir: Path,
                     seed_base: int) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        made: list[Path] = []
        for i, shot in enumerate(shots):
            target = out_dir / (
                f"{shot['id']}_{config.slug(shot['kind'])}_"
                f"{shot['duration']:.2f}.mp4")
            if not target.exists():
                self.render_shot(shot, target, seed_base + i * 101)
            made.append(target)
        return made


def probe() -> dict[str, Any]:
    """Report reachability and whether a key is configured. No spend, no generation."""
    cfg = config.load_config()
    s = settings(cfg)
    info: dict[str, Any] = {
        "model": s["model"],
        "key_configured": False,
        "reachable": False,
        "detail": "",
    }
    try:
        api_key(cfg)
        info["key_configured"] = True
    except VideoUnavailable as exc:
        info["detail"] = str(exc).splitlines()[0]
        return info

    try:
        req = urllib.request.Request(f"{BASE}/video/models",
                                     headers={"User-Agent": "sheesha-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        items = data if isinstance(data, list) else data.get("data") or []
        hit = next((m for m in items if (m.get("name") or "") == s["model"]), None)
        if hit:
            info["reachable"] = True
            price = (hit.get("pricing") or {}).get("completionVideoSeconds")
            info["price_per_second"] = price
            info["health"] = (hit.get("health") or {}).get("status")
            info["detail"] = f"{s['model']} healthy, {price} pollen/s"
        else:
            info["detail"] = f"{s['model']} not in the model list"
    except Exception as exc:
        info["detail"] = f"model list unreachable: {type(exc).__name__}"
    return info