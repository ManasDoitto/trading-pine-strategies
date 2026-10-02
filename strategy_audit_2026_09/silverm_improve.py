"""Improvement tests for the CURRENT SILVERM strategy (pre_registration_silverm_improve_2026_10_03.md). Selection on development only; holdout once."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
BARS = {"SILVERM1": rs.load("MCX_SILVERM1"), "SILVER1": rs.load("MCX_SILVER1")}
FRAMES = {n: rs.v40.v40_frame(b, P) for n, b in BARS.items()}
for n, f in FRAMES.items():
    bo = P["bo_lookback"]
    f["bo_l"] = f.close > f.high.rolling(bo).max().shift(1)
    f["bo_s"] = f.close < f.low.rolling(bo).min().shift(1)
    f["atr_q33"] = f.atr.rolling(2000, min_periods=500).quantile(0.33)
    f["hour"] = f.time.dt.hour


def run(name, mods, ban_hours=()):
    f = FRAMES[name].copy()
    kw = {}
    if "C1" in mods:
        f["ok_l"] &= f.bo_l
        f["ok_s"] &= f.bo_s
    if ban_hours:
        h = f.hour.isin(ban_hours)
        f["ok_l"] &= ~h
        f["ok_s"] &= ~h
    if "C4" in mods:
        low = f.atr < f.atr_q33
        f["ok_l"] &= ~low
        f["ok_s"] &= ~low
    if "C3" in mods:
        kw["be_at_r"] = 1.0
    if "C5" in mods:
        kw["cooldown_bars"] = 12
    t = pd.DataFrame(rs.simulate(f, P, **kw))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    t["hour"] = t.signal_time.dt.hour
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def metrics(t):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    eq = t.R.cumsum()
    eqp = t.net.cumsum()
    return dict(n=len(t), win=round(100 * (t.net > 0).mean(), 1), pf=pf(t.net), pf_R=pf(t.R), net=round(t.net.sum()), expR=round(t.R.mean(), 3),
                dd_R=round((eq.cummax() - eq).max(), 1), dd_pts=round((eqp.cummax() - eqp).max()), net_dd=round(t.net.sum() / (eqp.cummax() - eqp).max(), 2),
                months=len(mo), pos_m=round(100 * (mo > 0).mean()), best_share=round(100 * mo.max() / t.net.sum()) if t.net.sum() > 0 else 999,
                hold_h=round(t.hold_h.mean(), 1))


base = {n: run(n, ()) for n in BARS}
CUT = {n: base[n].exit_time.quantile(.8) for n in BARS}
dev = lambda t, n: t[t.exit_time <= CUT[n]]
hold = lambda t, n: t[t.exit_time > CUT[n]]
print({n: str(CUT[n].date()) for n in BARS}, "<- development ends / holdout starts")
BD = {n: metrics(dev(base[n], n)) for n in BARS}
print("BASELINE development:", pd.DataFrame(BD).to_string(), sep="\n")


def accepts(m, b):
    return m["pf"] >= b["pf"] + 0.05 and m["net"] >= b["net"] and m["dd_R"] <= b["dd_R"] * 1.05 and m["pos_m"] >= b["pos_m"] - 3 and m["n"] >= 400


# C2: hours chosen on development data only
hr = {n: dev(base[n], n).groupby("hour").agg(n=("net", "size"), net=("net", "sum")) for n in BARS}
cand = [h for h in sorted(set(hr["SILVERM1"].index) & set(hr["SILVER1"].index))
        if hr["SILVERM1"].at[h, "n"] >= 25 and hr["SILVER1"].at[h, "n"] >= 25 and hr["SILVERM1"].at[h, "net"] < 0 and hr["SILVER1"].at[h, "net"] < 0]
print("\nC2 hours (dev net < 0 on both contracts, n>=25 each):", cand)
print("dev net by hour (SILVERM1 | SILVER1):", {h: (round(hr['SILVERM1'].at[h, 'net']), round(hr['SILVER1'].at[h, 'net'])) for h in sorted(set(hr['SILVERM1'].index) & set(hr['SILVER1'].index))})

TESTS = {"C1": ((), "C1 breakout only"), "C2": ((), "C2 hour rule"), "C3": (("C3",), "C3 breakeven +1R"), "C4": (("C4",), "C4 vol floor p33"), "C5": (("C5",), "C5 60-min cooldown")}
rows, accepted = [], []
for key, (mods, label) in TESTS.items():
    m = ("C1",) if key == "C1" else mods
    ban = tuple(cand) if key == "C2" else ()
    if key == "C2" and not cand:
        print("C2: no hours qualify -> not testable, recorded as rejected")
        continue
    res = {n: metrics(dev(run(n, m, ban), n)) for n in BARS}
    ok = all(accepts(res[n], BD[n]) for n in BARS)
    for n in BARS:
        rows.append(dict(test=label, data=n, ok=ok, **{k: res[n][k] for k in ("n", "pf", "net", "expR", "dd_R", "pos_m", "best_share", "hold_h", "win")}))
    if ok:
        accepted.append(key)
R = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print("\nDEVELOPMENT results (baseline first):")
print(pd.concat([pd.DataFrame([dict(test="BASELINE", data=n, ok="", **{k: BD[n][k] for k in ("n", "pf", "net", "expR", "dd_R", "pos_m", "best_share", "hold_h", "win")}) for n in BARS]), R]).to_string(index=False))
print("\nACCEPTED on development:", accepted)
if not accepted:
    print("NOTHING ACCEPTED: the current strategy stays; no holdout look taken.")
    raise SystemExit(0)

mods = tuple(k for k in ("C3", "C4", "C5") if k in accepted) + (("C1",) if "C1" in accepted else ())
ban = tuple(cand) if "C2" in accepted else ()
cres = {n: run(n, mods, ban) for n in BARS}
print("\nC6 = combination of accepted:", accepted, "-> development:", {n: metrics(dev(cres[n], n)) for n in BARS})
print("\nHOLDOUT (looked at once):")
for n in BARS:
    print(n, "\n", pd.DataFrame({"baseline": metrics(hold(base[n], n)), "C6 combined": metrics(hold(cres[n], n))}).to_string())
bm, cm = metrics(hold(base["SILVERM1"], "SILVERM1")), metrics(hold(cres["SILVERM1"], "SILVERM1"))
s1 = metrics(hold(cres["SILVER1"], "SILVER1"))
ok = cm["pf"] >= bm["pf"] and cm["net"] >= bm["net"] and cm["expR"] >= bm["expR"] and cm["dd_R"] <= bm["dd_R"] * 1.10 and s1["expR"] > 0
print("\nHOLDOUT VERDICT:", "PASS" if ok else "FAIL")
print("\nFULL HISTORY (descriptive), SILVERM1:")
print(pd.DataFrame({"baseline": metrics(base["SILVERM1"]), "C6 combined": metrics(cres["SILVERM1"])}).to_string())
print("FULL HISTORY, SILVER1:")
print(pd.DataFrame({"baseline": metrics(base["SILVER1"]), "C6 combined": metrics(cres["SILVER1"])}).to_string())
# each accepted single on the holdout, for transparency (not used for selection)
