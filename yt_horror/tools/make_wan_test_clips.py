"""Prove the wan assembly path without waiting on Colab.

Builds synthetic clips with the exact shape the notebook produces (480x832, 16fps,
81 frames, 5.0s) under the manifest's own filenames, then exercises the real assemble
step. If this passes, a Colab run returning real clips will drop straight in.

These are TEST PATTERNS, not footage. They are written to a `_selftest` directory and
never to the real clip directory, so they cannot be assembled into an episode by
accident. Pass --in-place only if you are deliberately re-running the self-test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config, ffmpeg
from lib.visuals.wan import wan_path

MANIFEST = config.episode_dir(1) / "video_jobs.json"
SELF_DIRNAME = "_selftest"


def build() -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    in_place = "--in-place" in sys.argv
    if not in_place:
        print(f"NOTE: writing to {SELF_DIRNAME}/. Pass --in-place to target the real "
              f"clip directory.\n")
    # The real directory is the wan subdirectory the provider reads from, not
    # config.CLIPS_DIR, which is the procedural provider's flat folder.
    d = wan_path() if in_place else config.CLIPS_DIR / SELF_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    tints = ["0", "20", "40", "60", "80", "100", "120"]
    for job, tint in zip(m["jobs"], tints):
        out = d / job["out_name"]
        # testsrc2 already carries moving bars and a frame counter, so a wrong trim,
        # a frozen tail or a dropped frame is visible rather than subtle.
        ffmpeg.run([
            "-y", "-v", "error",
            "-f", "lavfi", "-i",
            f"testsrc2=s={job['width']}x{job['height']}:r={job['fps']}:d=5",
            "-vf", f"hue=h={tint}",
            "-frames:v", str(job["num_frames"]),
            "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
            str(out),
        ])
        print(f"{out.name:<36} {ffmpeg.duration_s(out):6.3f}s  {job['width']}x{job['height']}")


if __name__ == "__main__":
    build()