"""Shared clip-fitting step: fit a generated clip to an exact frame budget.

Every visual provider ends up holding a clip of the wrong length and size. A video
model returns whatever it returns - typically a fixed 5 seconds at its own fps and
resolution - while the edit needs a specific integer frame count at the delivery
size. This is where that is reconciled, once, for all providers.

The rule for a short clip is to *slow* it rather than freeze it. A held final frame
reads as a freeze-frame, and it is very obvious in a 30-second Short. A modest
slow-down reads as ordinary slow camera work, which is idiomatic for this kind of
footage. Only the sub-second gap left over by rounding is cloned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib import ffmpeg


def fit(src: Path, dst: Path, frames: int, cfg: dict[str, Any],
        grain: int = 6) -> Path:
    """Normalise one generated clip to exactly `frames` frames at delivery size."""
    v = cfg["video"]
    fps = int(v["fps"])
    need_s = frames / fps
    src_s = ffmpeg.duration_s(src)
    if src_s <= 0:
        raise RuntimeError(f"{src.name}: unreadable or empty clip")

    ratio = need_s / src_s if src_s < need_s - 0.08 else 1.0

    grade = (f"eq=contrast=1.05:saturation=0.95:gamma=0.99,"
             f"noise=alls={int(grain)}:allf=t+u,vignette=PI/5.0")
    vf = (f"setpts=PTS*{ratio:.6f},fps={fps},"
          f"scale={v['width']}:{v['height']}:flags=lanczos,"
          f"tpad=stop_mode=clone:stop_duration=3,{grade}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run([
        "-y", "-v", "error", "-i", str(src),
        "-vf", vf,
        "-frames:v", str(frames), "-r", str(fps),
        "-c:v", str(v["vcodec"]), "-crf", str(v["crf"]), "-preset", str(v["preset"]),
        "-pix_fmt", str(v["pix_fmt"]),
        str(dst),
    ])
    return dst