"""Skip early-day / big-stop silver v4.1 entries (pre_registration_silver_bigsl_later_2026_10_03.md)."""
import tomllib
from pathlib import Path
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

p = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
df = rs.load("MCX_SILVER1")
base = rs.v40.v40_frame(df, p)
mins = base.time.dt.hour * 60 + base.time.dt.minute


def variant(kind, hh):
    f = base.copy()
    early = mins < hh * 60
    if kind == "E":
        f["ok_l"] &= ~early; f["ok_s"] &= ~early
    elif kind == "B":
        f["ok_l"] &= ~(early & (f.risk_l > 1500)); f["ok_s"] &= ~(early & (f.risk_s > 1500))
    return f


span = (df.time.iloc[-1] - df.time.iloc[0]).days / 30.4
rows = []
for name, kind, hh in [("current", None, 0), ("E1 none before 10:00", "E", 10), ("E2 none before 11:00", "E", 11),
                       ("E3 none before 12:00", "E", 12), ("B1 big stop skipped before 12:00", "B", 12),
                       ("B2 big stop skipped before 15:00", "B", 15)]:
    t = pd.DataFrame(rs.simulate(variant(kind, hh), p))
    t["exit_time"] = pd.to_datetime(t.exit_time)
    q = t.exit_time.quantile([.6, .8])
    pf = lambda x: round(x.net[x.net > 0].sum() / -x.net[x.net < 0].sum(), 2)
    hold = (t.exit_time - pd.to_datetime(t.entry_time)).dt.total_seconds() / 3600
    eq = t.net.cumsum()
    m = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    rows.append(dict(variant=name, n=len(t), per_m=round(len(t) / span, 1), pf=pf(t), net=round(t.net.sum()), dd=round((eq.cummax() - eq).max()),
                     hold_h=round(hold.mean(), 1), big=int((t.risk_pts > 1500).sum()), pf_tr=pf(t[t.exit_time <= q[.6]]),
                     pf_va=pf(t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])]), pf_ho=pf(t[t.exit_time > q[.8]]),
                     pos_m=round(100 * (m > 0).mean())))
R = pd.DataFrame(rows)
cur = R.net.iloc[0]
R["PASS"] = [False] + [bool(r.pf >= 1.3 and min(r.pf_tr, r.pf_va, r.pf_ho) >= 1.15 and r.n >= 600 and r.pos_m >= 50 and r.net >= .8 * cur)
                       for r in R.iloc[1:].itertuples()]
pd.set_option("display.width", 250)
print(R.to_string(index=False))
t = pd.DataFrame(rs.simulate(base, p))
t["hr"] = pd.to_datetime(t.signal_time).dt.hour
g = t.groupby("hr").agg(n=("net", "size"), big=("risk_pts", lambda s: int((s > 1500).sum())), med_risk=("risk_pts", "median"),
                        net=("net", "sum")).round(0)
print("\nBaseline by signal hour:\n", g.to_string())
