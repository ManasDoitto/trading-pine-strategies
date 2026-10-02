"""18-variant holding-time grid on live silver v4.1 (pre_registration_silver_holdtime_2026_10_03.md)."""
import itertools, tomllib
from pathlib import Path
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

base = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
df = rs.load("MCX_SILVER1")
rows = []
for rr, ts, flat in itertools.product([1.5, 2.0, 3.0], [None, 240, 120], [False, True]):
    p = dict(base, rr=rr)
    f = rs.v40.v40_frame(df, p)
    t = pd.DataFrame(rs.simulate(f, p, time_stop_min=ts, flat_at="23:25" if flat else None))
    t["exit_time"] = pd.to_datetime(t.exit_time)
    q = t.exit_time.quantile([.6, .8])
    pf = lambda x: round(x.net[x.net > 0].sum() / -x.net[x.net < 0].sum(), 2)
    hold = (t.exit_time - pd.to_datetime(t.entry_time)).dt.total_seconds() / 3600
    eq = t.net.cumsum()
    m = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    r = dict(rr=rr, tstop=ts or 0, flat=flat, n=len(t), pf=pf(t), net=round(t.net.sum()), dd=round((eq.cummax() - eq).max()),
             hold_h=round(hold.mean(), 1), med_h=round(hold.median(), 1), pct24=round(100 * (hold > 24).mean()),
             pf_tr=pf(t[t.exit_time <= q[.6]]), pf_va=pf(t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])]),
             pf_ho=pf(t[t.exit_time > q[.8]]), pos_m=round(100 * (m > 0).mean()))
    r["PASS"] = (r["hold_h"] <= 4 and r["n"] >= 600 and min(r["pf_tr"], r["pf_va"], r["pf_ho"]) >= 1.15
                 and r["pos_m"] >= 50 and r["pf"] >= 1.15 and r["net"] > 0)
    rows.append(r)
R = pd.DataFrame(rows)
R.to_csv("research_data/silver_holdtime_grid.csv", index=False)
pd.set_option("display.width", 250)
print(R.to_string(index=False))
print("\nPASSES:", int(R.PASS.sum()), "of", len(R))
