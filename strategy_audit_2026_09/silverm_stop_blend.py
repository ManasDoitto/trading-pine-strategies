"""Does blending several swing lookbacks make the stop less sensitive to the exact setting? (robustness test, not a profit search)
Blended stop = average of the swing extremes over a SET of lookbacks, then the usual 0.1 ATR buffer / 2.5-5.0 ATR floor and cap.
Judged by: PF at the deployed set AND at neighbouring sets (how much it moves), not by the best PF."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
pd.set_option("display.width", 250, "display.max_rows", 100)
DATA = {"SILVERM1": rs.load("MCX_SILVERM1"), "SILVER1": rs.load("MCX_SILVER1")}


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def frame(bars, lookbacks):
    f = rs.v40.v40_frame(bars, P)
    lo = np.mean([bars.low.rolling(n).min().to_numpy() for n in lookbacks], axis=0)
    hi = np.mean([bars.high.rolling(n).max().to_numpy() for n in lookbacks], axis=0)
    f["sw_lo"], f["sw_hi"] = lo, hi
    f["risk_l"] = np.maximum(f.close - (f.sw_lo - P["sw_buf"] * f.atr), P["min_sl"] * f.atr)
    f["risk_s"] = np.maximum((f.sw_hi + P["sw_buf"] * f.atr) - f.close, P["min_sl"] * f.atr)
    cap = P["max_sl"] * f.atr
    bo = P["bo_lookback"]
    el = f.flip_up | (f.close > f.high.rolling(bo).max().shift(1))
    es = f.flip_dn | (f.close < f.low.rolling(bo).min().shift(1))
    f["ok_l"] = f.in_sess & el & (f.e9 > f.e22) & (f.risk_l <= cap)
    f["ok_s"] = f.in_sess & es & (f.e9 < f.e22) & (f.risk_s <= cap) & ~f.ok_l
    fl = f.close * P["min_stop_pct"] / 100
    f["ok_l"] &= f.risk_l >= fl
    f["ok_s"] &= f.risk_s >= fl
    return f


def run(name, lookbacks):
    t = pd.DataFrame(rs.simulate(frame(DATA[name], lookbacks), P))
    t["exit_time"] = pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    eq = t.net.cumsum()
    return dict(trades=len(t), PF=pf(t.net), net=round(t.net.sum()), expR=round(t.R.mean(), 3), maxDD=round((eq.cummax() - eq).max()), months_pos=f"{int((mo > 0).sum())}/{len(mo)}")


SETS = {"single 10 (deployed)": [10], "single 8": [8], "single 12": [12],
        "blend 8,10,12": [8, 10, 12], "blend 7,9,11": [7, 9, 11], "blend 9,10,11": [9, 10, 11], "blend 10,12,14": [10, 12, 14], "blend 6..14 (5 values)": [6, 8, 10, 12, 14]}
for n in DATA:
    res = {k: run(n, v) for k, v in SETS.items()}
    print(f"\n===== {n} =====")
    print(pd.DataFrame(res).T.to_string())
    singles = [res[k]["PF"] for k in ("single 10 (deployed)", "single 8", "single 12")]
    blends = [res[k]["PF"] for k in ("blend 8,10,12", "blend 7,9,11", "blend 9,10,11", "blend 10,12,14")]
    print(f"PF spread across neighbouring SINGLE lookbacks 8/10/12: {min(singles)}-{max(singles)} (range {max(singles)-min(singles):.2f}) | across 4 BLEND sets: {min(blends)}-{max(blends)} (range {max(blends)-min(blends):.2f})")
