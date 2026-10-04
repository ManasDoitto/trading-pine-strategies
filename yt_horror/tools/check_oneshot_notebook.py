from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

path = ROOT / "notebooks" / "sheesha_wan_oneshot.ipynb"
nb = json.loads(path.read_text(encoding="utf-8"))
print("valid JSON | cells:", len(nb["cells"]))

src = "".join(nb["cells"][2]["source"])
line = next(l for l in src.splitlines() if l.startswith("MANIFEST_B64"))
blob = line.split('"')[1]
m = json.loads(base64.b64decode(blob))
print("manifest round-trips OK | episode", m["episode"], "| jobs", len(m["jobs"]))
for j in m["jobs"]:
    print("  ", j["out_name"], "|", j["width"], "x", j["height"],
          "|", j["num_frames"], "f @", j["fps"], "fps")
    print("   prompt:", j["prompt"][:90], "...")

# no drive.mount anywhere
bad = [i for i, c in enumerate(nb["cells"])
       if "drive.mount" in "".join(c["source"])]
print("cells calling drive.mount:", bad or "none")
print("has files.download:", any("files.download" in "".join(c["source"])
                                 for c in nb["cells"]))