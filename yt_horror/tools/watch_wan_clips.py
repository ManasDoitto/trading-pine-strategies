"""Wait for the Colab clips to land, then assemble and open the episode.

The notebook runs on Google's side, so the only way this side learns a generation
finished is by the clips appearing on disk. This checks for them and, once they are
all present, runs the real assemble step.

Designed to be run repeatedly from a scheduler:

* If clips are missing it prints one line and exits 0. Nothing is touched.
* It opens the finished episode exactly once per distinct set of clips, tracked by a
  fingerprint of every clip's name, size and mtime. Regenerating a shot changes the
  fingerprint, so a better Colab run re-opens the episode instead of going unnoticed.
* Assembly still goes through QC. A failed QC never opens anything.

Exit codes: 0 waiting, 2 assembled and opened, 3 assembled but QC failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from lib import config  # noqa: E402

STATE = config.STATE_DIR


def manifest(ep: int) -> dict:
    p = config.episode_dir(ep) / "video_jobs.json"
    if not p.exists():
        raise SystemExit(
            f"no manifest at {p}\n  run: python pipeline.py video-jobs {ep}")
    return json.loads(p.read_text(encoding="utf-8"))


def fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}\n".encode())
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=int, nargs="?", default=1)
    ap.add_argument("--open", dest="open_video", action="store_true", default=True)
    ap.add_argument("--no-open", dest="open_video", action="store_false")
    args = ap.parse_args()
    ep = args.episode

    m = manifest(ep)
    d = config.CLIPS_DIR / "wan"
    want = [j["out_name"] for j in m["jobs"]]
    present = [n for n in want if (d / n).exists()]
    missing = [n for n in want if not (d / n).exists()]

    if missing:
        print(f"ep{ep:02d}: {len(present)}/{len(want)} clips in {d} - "
              f"waiting on {len(missing)}")
        return 0

    paths = [d / n for n in want]
    fp = fingerprint(paths)
    STATE.mkdir(parents=True, exist_ok=True)
    marker = STATE / f"wan_ep{ep:02d}_{fp}.opened"

    print(f"ep{ep:02d}: all {len(want)} clips present (fingerprint {fp}) - assembling")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "pipeline.py"), "episode", str(ep),
         "--provider", "wan", "--force"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    tail = (proc.stdout or "") + (proc.stderr or "")
    for line in tail.strip().splitlines()[-4:]:
        print("   ", line)

    if proc.returncode != 0:
        print(f"ep{ep:02d}: assemble FAILED (exit {proc.returncode})")
        return 3

    final = config.OUT_DIR / f"ep{ep:02d}.mp4"
    qc = config.read_json(config.QC_DIR / f"ep{ep:02d}_qc.json", {}) or {}
    if not qc.get("pass"):
        print(f"ep{ep:02d}: QC did not pass - not opening")
        for k, v in (qc.get("checks") or {}).items():
            if not v:
                print(f"    failed check: {k}")
        return 3

    print(f"ep{ep:02d}: {final}  {qc.get('actual_duration_s')}s  "
          f"{qc.get('resolution')}  {qc.get('measured_lufs')} LUFS  "
          f"{final.stat().st_size // 1024} KB")

    if args.open_video and not marker.exists():
        marker.write_text(str(final), encoding="utf-8")
        os.startfile(str(final))  # noqa: S606 - Windows shell open, user-initiated
        print(f"ep{ep:02d}: opened in the default player")
    elif marker.exists():
        print(f"ep{ep:02d}: already opened this build; not reopening")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())