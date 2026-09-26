import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crude_50cfg as C
B = dict(C.BASE, fast=9, slow=34)
STARTS = ("09:15", "17:30")
cfgs = []
for st in STARTS:
    for s in (28, 30, 32, 36, 40, 45, 50): cfgs.append((f"slow {s} @{st}", dict(C.BASE, start=st, slow=s)))
    for f in (7, 10, 11): cfgs.append((f"fast {f}/34 @{st}", dict(C.BASE, start=st, fast=f, slow=34)))
    for k, o in {"+trail 2R/2R": dict(trail=(2.0, 2.0)), "+skip 22h": dict(skip_h=22), "+be 2R": dict(be=2.0), "+be 1.5R": dict(be=1.5), "+hold 4": dict(hold=4),
                 "+rr 4.5": dict(rr=4.5), "+max 2/day": dict(maxday=2), "+trail 3R/2R": dict(trail=(3.0, 2.0)), "+maxSL 2.75": dict(max_sl=2.75),
                 "+maxSL 3.25": dict(max_sl=3.25), "+minSL 2.0": dict(min_sl=2.0), "+sw 8": dict(sw=8), "+sw 12": dict(sw=12)}.items():
        cfgs.append((f"9/34 {k} @{st}", dict(B, start=st, **o)))
for st in ("15:00", "16:00", "17:00", "18:00"): cfgs.append((f"9/34 @{st}", dict(B, start=st)))
cfgs = [("CTRL 09:15", dict(C.BASE)), ("CTRL 17:30", dict(C.BASE, start="17:30")), ("9/34 @09:15", dict(B))] + cfgs
print(len(cfgs) - 3, "configs", flush=True)
R = pd.DataFrame([C.summ(t, v) for t, v in cfgs]); R.to_csv(C.ROOT / "research_data" / "crude_round2.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(R[["id", "full_n", "full_pf", "full_net", "full_cnet", "tr_net", "ho_net", "ho_cnet", "full_dd", "full_conc"]].to_string(index=False))
