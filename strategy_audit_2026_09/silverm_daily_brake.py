"""Daily-brake variants for the current SILVERM strategy (pre_registration_silverm_daily_brake_2026_10_03.md)."""
import tomllib
from pathlib import Path
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
BARS = {"SILVERM1": rs.load("MCX_SILVERM1"), "SILVER1": rs.load("MCX_SILVER1")}
FR = {n: rs.v40.v40_frame(b, P) for n, b in BARS.items()}
VARS = {"B0 limit 350 (current)": (350, None), "B1 limit 1000": (1000, None), "B2 limit 1500": (1500, None), "B3 limit 2000": (2000, None),
        "B4 limit 3000": (3000, None), "B5 no limit": (0, None), "B6 max 2 trades/day": (0, 2)}


def run(n, lim, mpd):
    t = pd.DataFrame(rs.simulate(FR[n], dict(P, day_loss_limit_pts=lim), max_per_day=mpd))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def metrics(t):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    eq, ep = t.R.cumsum(), t.net.cumsum()
    day = t.groupby(t.exit_time.dt.date).net.sum()
    return dict(n=len(t), per_day=round(len(t) / t.exit_time.dt.date.nunique(), 2), win=round(100 * (t.net > 0).mean(), 1), pf=pf(t.net), pf_R=pf(t.R), net=round(t.net.sum()),
                expR=round(t.R.mean(), 3), dd_R=round((eq.cummax() - eq).max(), 1), dd_pts=round((ep.cummax() - ep).max()), pos_m=round(100 * (mo > 0).mean()),
                pos_m_cnt=f"{int((mo > 0).sum())}/{len(mo)}", worst_day=round(day.min()), best_share=round(100 * mo.max() / t.net.sum()) if t.net.sum() > 0 else 999,
                hold_h=round(t.hold_h.mean(), 1))


T = {(v, n): run(n, *a) for v, a in VARS.items() for n in BARS}
CUT = {n: T[("B0 limit 350 (current)", n)].exit_time.quantile(.8) for n in BARS}
dev = lambda t, n: t[t.exit_time <= CUT[n]]
hold = lambda t, n: t[t.exit_time > CUT[n]]
D = {k: metrics(dev(t, k[1])) for k, t in T.items()}
pd.set_option("display.width", 250)
cols = ["n", "per_day", "win", "pf", "net", "expR", "dd_R", "pos_m_cnt", "pos_m", "worst_day", "best_share", "hold_h"]
print("cut dates (dev ends / holdout starts):", {n: str(CUT[n].date()) for n in BARS})
for n in BARS:
    print(f"\nDEVELOPMENT, {n}")
    print(pd.DataFrame({v: {c: D[(v, n)][c] for c in cols} for v in VARS}).T.to_string())
base = "B0 limit 350 (current)"
acc = []
for v in VARS:
    if v == base:
        continue
    ok = all(D[(v, n)]["net"] >= .95 * D[(base, n)]["net"] and D[(v, n)]["pos_m"] >= D[(base, n)]["pos_m"] + 5 and D[(v, n)]["dd_R"] <= 1.15 * D[(base, n)]["dd_R"]
             and D[(v, n)]["pf"] >= D[(base, n)]["pf"] - .05 and D[(v, n)]["n"] >= 400 for n in BARS)
    if ok:
        acc.append(v)
print("\nACCEPTED on development:", acc)
if not acc:
    print("NOTHING ACCEPTED: the 350 limit stays; no holdout look taken.")
    raise SystemExit(0)
win = sorted(acc, key=lambda v: (-D[(v, "SILVERM1")]["pos_m"], D[(v, "SILVERM1")]["dd_R"]))[0]
print("WINNER:", win)
print("\nHOLDOUT (looked at once):")
for n in BARS:
    print(n)
    print(pd.DataFrame({base: metrics(hold(T[(base, n)], n)), win: metrics(hold(T[(win, n)], n))}).to_string())
b, w, s1 = metrics(hold(T[(base, "SILVERM1")], "SILVERM1")), metrics(hold(T[(win, "SILVERM1")], "SILVERM1")), metrics(hold(T[(win, "SILVER1")], "SILVER1"))
ok = w["net"] >= b["net"] and w["expR"] >= b["expR"] and w["pos_m"] >= b["pos_m"] and w["dd_R"] <= 1.10 * b["dd_R"] and s1["expR"] > 0
print("\nHOLDOUT VERDICT:", "PASS" if ok else "FAIL")
print("\nFULL HISTORY SILVERM1:")
print(pd.DataFrame({v: metrics(T[(v, "SILVERM1")]) for v in (base, win)}).to_string())
