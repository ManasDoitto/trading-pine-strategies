"""What does the '350-point daily loss limit' actually do on SILVERM1, given stops that are 450-1000+ points wide?"""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
f = rs.v40.v40_frame(rs.load("MCX_SILVERM1"), P)
pd.set_option("display.width", 250, "display.max_rows", 100)


def run(limit):
    p = dict(P, day_loss_limit_pts=limit)
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


base = run(350)
print("STOP DISTANCE of the strategy's trades on SILVERM1 (points between entry and stop):")
print(base.risk_pts.describe(percentiles=[.05, .1, .25, .5, .75, .9]).round(0).to_string())
print(f"\ntrades whose stop is SMALLER than 350 pts: {(base.risk_pts < 350).sum()} of {len(base)} ({100*(base.risk_pts < 350).mean():.1f}%)")
print(f"losing trades that lost MORE than 350 pts (net): {((base.net < -350)).sum()} of {(base.net < 0).sum()} losers ({100*(base.net < -350).sum()/(base.net < 0).sum():.0f}%)")
print(f"exits tagged 'DAY LIMIT' (position force-closed by the limit): {(base.result == 'DAY LIMIT').sum()}")

rows = []
for lim in (0, 350, 700, 1500, 3000, 6000):
    t = run(lim)
    day = t.groupby(t.exit_time.dt.date).net.sum()
    cum = t.assign(d=t.exit_time.dt.date).groupby("d").net.cumsum()
    locked_days = int((t.assign(d=t.exit_time.dt.date, c=cum).groupby("d").c.min() <= -lim).sum()) if lim else 0
    eq = t.net.cumsum()
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    rows.append(dict(limit=lim or "none", trades=len(t), days_locked=locked_days, pf=pf(t.net), net=round(t.net.sum()), dd=round((eq.cummax() - eq).max()),
                     months_pos=f"{int((mo > 0).sum())}/{len(mo)}", worst_day=round(day.min()), trades_per_day=round(len(t) / t.exit_time.dt.date.nunique(), 2)))
print("\nEFFECT OF THE DAILY LIMIT (SILVERM1, live v4.1 otherwise unchanged):")
print(pd.DataFrame(rows).to_string(index=False))

t = base.assign(d=base.exit_time.dt.date)
multi = t.groupby("d").size()
print(f"\ntrading days: {len(multi)}; days with 2+ trades under the 350 limit: {(multi >= 2).sum()}; days with 3+: {(multi >= 3).sum()}")
print("\nEXAMPLE: the last 6 days on which the limit locked the day (a stop-out ended trading for that day):")
cum = t.groupby("d").net.cumsum()
locked = t.assign(c=cum).groupby("d").c.min()
ld = locked[locked <= -350].index[-6:]
raw = f[(f.ok_l | f.ok_s)].assign(d=lambda x: x.time.dt.date)
for d in ld:
    g = t[t.d == d]
    first_loss = g[g.net < 0].iloc[0]
    after = raw[(raw.d == d) & (raw.time > first_loss.exit_time)]
    print(f"{d}: lost {first_loss.net:,.0f} pts (stop was {first_loss.risk_pts:,.0f} away) at {first_loss.exit_time:%H:%M} -> {len(after)} later entry flags that day were NOT taken")
