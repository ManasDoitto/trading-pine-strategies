"""With the 0.35% stop filter now live, what do the hour filters add? Three equal-time samples, SILVERM1 and SILVER1."""
import tomllib
from pathlib import Path
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P0 = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
VAR = {"A  live now (filter, skip 15-16h)": [15, 16], "B  + skip hours 13 and 17": [13, 15, 16, 17], "C  skip whole 13:00-17:00 (hours 13-16)": [13, 14, 15, 16], "D  skip hours 13 and 14-17 too (13-17)": [13, 14, 15, 16, 17]}
pd.set_option("display.width", 250)


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


for dname, key in (("SILVERM1", "MCX_SILVERM1"), ("SILVER1", "MCX_SILVER1")):
    bars = rs.load(key)
    t0, t1 = bars.time.iloc[400], bars.time.iloc[-1]
    cuts = [t0 + (t1 - t0) * k / 3 for k in range(4)]
    rows = {}
    for v, ex in VAR.items():
        p = dict(P0, exclude_hours=ex)
        t = pd.DataFrame(rs.simulate(rs.v40.v40_frame(bars, p), p))
        t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
        t["R"] = t.net / t.risk_pts
        r = {}
        for i, lab in enumerate(("S1", "S2", "S3")):
            s = t[(t.entry_time >= cuts[i]) & ((t.entry_time < cuts[i + 1]) if i < 2 else (t.entry_time <= cuts[3]))]
            r[f"PF {lab}"] = pf(s.net)
            r[f"net {lab}"] = round(s.net.sum())
        mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
        eq = t.net.cumsum()
        r.update({"trades": len(t), "PF all": pf(t.net), "net all": round(t.net.sum()), "exp R": round(t.R.mean(), 3), "max DD": round((eq.cummax() - eq).max()),
                  "months +": f"{int((mo > 0).sum())}/{len(mo)}", "worst month": round(mo.min())})
        rows[v] = r
    print(f"\n===== {dname} =====")
    print(pd.DataFrame(rows).to_string())
