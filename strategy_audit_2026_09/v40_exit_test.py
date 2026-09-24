"""Six pre-registered exit variants on the frozen SILVERM v4.0 entries (pre_registration_v40_exits_2026_09_25.md)."""
import tomllib
from pathlib import Path
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs
import numpy as np

def gates(trades):
    """Pre-registered criteria. Returns (dict of metrics, pass bool)."""
    if len(trades) < 30:
        return dict(n=len(trades)), False
    t = pd.DataFrame(trades)
    t["exit_time"] = pd.to_datetime(t.exit_time)
    q = t.exit_time.quantile([.6, .8]).tolist()
    segs = (t[t.exit_time <= q[0]], t[(t.exit_time > q[0]) & (t.exit_time <= q[1])], t[t.exit_time > q[1]])

    def pf(x):
        w, ls = x.net[x.net > 0].sum(), -x.net[x.net < 0].sum()
        return w / ls if ls > 0 else (9.9 if w > 0 else 0)
    m = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    net = t.net.sum()
    r = dict(n=len(t), pf=round(pf(t), 2), net=round(net, 1), pf_tr=round(pf(segs[0]), 2), pf_va=round(pf(segs[1]), 2),
             pf_ho=round(pf(segs[2]), 2), pos_m=round(100 * (m > 0).mean()), best_m=round(100 * m.max() / net) if net > 0 else None)
    ok = (min(r["pf_tr"], r["pf_va"], r["pf_ho"]) >= 1.30 and r["n"] >= 150 and r["pos_m"] >= 70
          and r["best_m"] is not None and r["best_m"] <= 25)
    return r, ok



p = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
frame = rs.v40.v40_frame(rs.load("MCX_SILVERM1"), p)
V = {"BASE": {}, "V1 time90+flat": dict(time_stop_min=90, flat_at="23:25"), "V2 time120+flat": dict(time_stop_min=120, flat_at="23:25"),
     "V3 time180+flat": dict(time_stop_min=180, flat_at="23:25"), "V4 flat only": dict(flat_at="23:25"),
     "V5 breakeven +1R": dict(be_at_r=1.0), "V6 trail 1.5R/1R": dict(trail_start_r=1.5, trail_dist_r=1.0)}
rows = []
for k, kw in V.items():
    t = rs.simulate(frame, p, **kw)
    r, ok = gates(t)
    st = rs.stats(t)
    rows.append(dict(variant=k, passed=ok, **r, max_dd=st["max_dd"], avg_hold_h=st["avg_hold_h"], win=st["win_pct"]))
pd.set_option("display.width", 250)
print(pd.DataFrame(rows).to_string(index=False))
