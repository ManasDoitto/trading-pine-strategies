from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config, ffmpeg

for ep in (1,):
    m = json.loads((config.episode_dir(ep) / "video_jobs.json").read_text(encoding="utf-8"))
    d = config.CLIPS_DIR / "wan"
    hdr = "%-5s %8s %8s %6s %12s" % ("shot", "want", "got", "fps", "res")
    print(hdr)
    print("-" * len(hdr))
    bad = 0
    for j in m["jobs"]:
        f = d / f"{j['id']}_fit_{j['want_frames']}.mp4"
        if not f.exists():
            print(f"{j['id']:<5} MISSING FIT")
            bad += 1
            continue
        st = ffmpeg.probe(f)["streams"][0]
        got = int(round(float(st["nb_frames"])))
        fps = round(float(st["r_frame_rate"].split("/")[0]))
        flag = "" if got == j["want_frames"] else "  <-- MISMATCH"
        if got != j["want_frames"]:
            bad += 1
        print("%-5s %8d %8d %6d %12s%s" % (
            j["id"], j["want_frames"], got, fps,
            f"{st['width']}x{st['height']}", flag))
    print(f"\n{'OK - every clip is frame-exact' if not bad else f'{bad} PROBLEM(S)'}")