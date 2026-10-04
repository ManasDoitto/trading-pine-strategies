from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config, ffmpeg
from lib.visuals import wan

m = json.loads((config.episode_dir(1) / "video_jobs.json").read_text(encoding="utf-8"))
job = m["jobs"][0]
d = wan.wan_dir()

# a clip that is already delivery-sized rather than generation-sized: the exact
# mistake the guard exists to catch
bad = d / job["out_name"]
ffmpeg.run([
    "-y", "-v", "error", "-f", "lavfi", "-i",
    "testsrc2=s=1080x1920:r=16:d=2",
    "-frames:v", "32", "-c:v", "libx264", "-crf", "24", "-pix_fmt", "yuv420p", str(bad),
])
print(f"planted {bad.name} at 1080x1920 (manifest asked for "
      f"{job['width']}x{job['height']})")

try:
    wan._reject_placeholder(config.load_config(), bad, job)
    print("FAIL: guard accepted a wrongly-sized clip")
except wan.ClipsMissing as exc:
    print("PASS: guard rejected it ->")
    for line in str(exc).splitlines():
        print("   ", line)

bad.unlink(missing_ok=True)
print("\ncleaned up")