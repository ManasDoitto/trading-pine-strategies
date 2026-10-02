"""LONGER stop-loss swing lookback variants for the deployed SILVERM strategy (pre_registration_silverm_swing_longer_2026_10_03.md)."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
BARS = {"SILVERM1": rs.load("MCX_SILVERM1"), "SILVER1": rs.load("MCX_SILVER1")}


def build(name, mode):
    f = rs.v40.v40_frame(BARS[name], P)
    if mode == "orig10":
        return f
    if mode == "day":
        d = f.time.dt.date
        f["sw_lo"] = f.low.groupby(d).cummin()
        f["sw_hi"] = f.high.groupby(d).cummax()
    else:
        f["sw_lo"] = f.low.rolling(mode).min()
        f["sw_hi"] = f.high.rolling(mode).max()
    f["risk_l"] = np.maximum(f.close - (f.sw_lo - P["sw_buf"] * f.atr), P["min_sl"] * f.atr)
    f["risk_s"] = np.maximum((f.sw_hi + P["sw_buf"] * f.atr) - f.close, P["min_sl"] * f.atr)
    cap = P["max_sl"] * f.atr
    bo = P["bo_lookback"]
    el = f.flip_up | (f.close > f.high.rolling(bo).max().shift(1))
    es = f.flip_dn | (f.close < f.low.rolling(bo).min().shift(1))
    f["ok_l"] = f.in_sess & el & (f.e9 > f.e22) & (f.risk_l <= cap)
    f["ok_s"] = f.in_sess & es & (f.e9 < f.e22) & (f.risk_s <= cap) & ~f.ok_l
    return f


# the rebuild must reproduce the original at 10 bars
chk = build("SILVERM1", 10)
ref = build("SILVERM1", "orig10")
assert (chk.ok_l == ref.ok_l).all() and (chk.ok_s == ref.ok_s).all(), "rebuild differs from v40_frame"
print("sanity: rebuilt 10-bar frame == production v40_frame (entries identical)")

VARS = {"10 bars (current)": 10, "12 bars": 12, "15 bars": 15, "20 bars": 20, "30 bars": 30}


def run(n, mode):
    t = pd.DataFrame(rs.simulate(build(n, mode), P))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def streak(flags):
    best = cur = 0
    for v in flags:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def metrics(t):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    eq, ep = t.R.cumsum(), t.net.cumsum()
    return dict(trades=len(t), stop_avg=round(t.risk_pts.mean()), stop_med=round(t.risk_pts.median()), win=round(100 * (t.net > 0).mean(), 1), pf=pf(t.net), net=round(t.net.sum()),
                expR=round(t.R.mean(), 3), dd_pts=round((ep.cummax() - ep).max()), dd_R=round((eq.cummax() - eq).max(), 1), net_dd=round(t.net.sum() / (ep.cummax() - ep).max(), 2),
                pos_m=round(100 * (mo > 0).mean()), months_pos=f"{int((mo > 0).sum())}/{len(mo)}", worst_month=round(mo.min()), longest_loss_run=streak((mo < 0).to_numpy()),
                best_share=round(100 * mo.max() / t.net.sum()) if t.net.sum() > 0 else 999, hold_h=round(t.hold_h.mean(), 1), hit_tp=round(100 * (t.result == "TP").mean(), 1))


T = {(v, n): run(n, m) for v, m in VARS.items() for n in BARS}
CUT = {n: T[("10 bars (current)", n)].exit_time.quantile(.8) for n in BARS}
dev = lambda t, n: t[t.exit_time <= CUT[n]]
hold = lambda t, n: t[t.exit_time > CUT[n]]
pd.set_option("display.width", 250)
for n in BARS:
    print(f"\n===== FULL HISTORY {n} (descriptive) =====")
    print(pd.DataFrame({v: metrics(T[(v, n)]) for v in VARS}).to_string())
D = {k: metrics(dev(t, k[1])) for k, t in T.items()}
base = "10 bars (current)"
print("\n===== DEVELOPMENT (older 80%) =====")
for n in BARS:
    print(n)
    print(pd.DataFrame({v: {k: D[(v, n)][k] for k in ("trades", "stop_avg", "pf", "net", "expR", "dd_R", "pos_m", "hold_h")} for v in VARS}).to_string())
acc = [v for v in VARS if v != base and all(D[(v, n)]["pf"] >= D[(base, n)]["pf"] + .05 and D[(v, n)]["net"] >= D[(base, n)]["net"] and D[(v, n)]["dd_R"] <= 1.05 * D[(base, n)]["dd_R"]
                                            and D[(v, n)]["pos_m"] >= D[(base, n)]["pos_m"] - 3 for n in BARS)]
print("\nACCEPTED on development:", acc)
if not acc:
    print("NOTHING ACCEPTED: the 10-bar stop stays; no holdout look taken.")
    raise SystemExit(0)
w = max(acc, key=lambda v: D[(v, "SILVERM1")]["pf"])
print("WINNER:", w, "\nHOLDOUT (once):")
for n in BARS:
    print(n)
    print(pd.DataFrame({base: metrics(hold(T[(base, n)], n)), w: metrics(hold(T[(w, n)], n))}).to_string())
b, c, s1 = metrics(hold(T[(base, "SILVERM1")], "SILVERM1")), metrics(hold(T[(w, "SILVERM1")], "SILVERM1")), metrics(hold(T[(w, "SILVER1")], "SILVER1"))
print("HOLDOUT VERDICT:", "PASS" if (c["pf"] >= b["pf"] and c["net"] >= b["net"] and c["expR"] >= b["expR"] and c["dd_R"] <= 1.10 * b["dd_R"] and s1["expR"] > 0) else "FAIL")
