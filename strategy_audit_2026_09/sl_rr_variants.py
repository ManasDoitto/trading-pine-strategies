"""EXPLORATORY SL/RR variants of the v4.0 family beside the untouched baseline (points, net of 0.02%/side).
Not one of the pre-registered H1-H3; every variant counts as a trial. Split by time 60/20/20 per instrument."""
import itertools, tomllib, json
from pathlib import Path
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

cfg = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]
CASES = [("MCX_SILVER1", "SILVER"), ("MCX_CRUDEOIL1", "CRUDEOIL"), ("MCX_SILVERM1", "SILVERM")]
RR = [2.0, 2.5, 3.0, 4.0, 5.0]
SL = [(-1, 0), (0, 0), (0, 1), (1, 1)]          # (delta min_sl, delta max_sl) in ATR units
out = []
for name, key in CASES:
    base = cfg[key]
    df = rs.load(name)
    for rr, (dmin, dmax) in itertools.product(RR, SL):
        p = dict(base, rr=rr, min_sl=base["min_sl"] + dmin, max_sl=base["max_sl"] + dmax)
        t = pd.DataFrame(rs.simulate(rs.v40.v40_frame(df, p), p))
        t["exit_time"] = pd.to_datetime(t.exit_time)
        cut = t.exit_time.quantile([.6, .8]).tolist()
        segs = {"train": t[t.exit_time <= cut[0]], "val": t[(t.exit_time > cut[0]) & (t.exit_time <= cut[1])], "hold": t[t.exit_time > cut[1]]}
        row = dict(inst=key, rr=rr, min_sl=p["min_sl"], max_sl=p["max_sl"], baseline=(rr == base["rr"] and dmin == 0 and dmax == 0))
        row.update({k: v for k, v in rs.stats(t.to_dict("records")).items() if k in ("n", "pf", "net", "max_dd", "pos_months_pct", "best_month_share")})
        for k, s in segs.items():
            st = rs.stats(s.to_dict("records")); row[f"pf_{k}"] = st.get("pf")
        out.append(row)
r = pd.DataFrame(out)
r.to_csv("research_data/sl_rr_variants.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
for k, g in r.groupby("inst"):
    print(k); print(g.drop(columns="inst").round(2).to_string(index=False))
