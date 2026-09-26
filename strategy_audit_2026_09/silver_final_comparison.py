"""Every silver variant tested 2026-09-26, against working_strategies/Silver #1, on one harness.
Adds the question the tables cannot answer: is any difference distinguishable from noise?"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
from trading_agents.core import signals as v40
from trading_agents.core import signals_v50 as v50

BARS = "MCX_SILVER1"
T0 = pd.Timestamp("2024-03-25")
INC = dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, min_sl=2.5, max_sl=5.0, rr=3.0,
           session=["09:15", "23:30"])


def v40_variant(min_sl=2.5, max_sl=5.0, rr=3.0, day=350.0, bo=None, comm=0.0):
    p = dict(INC, min_sl=min_sl, max_sl=max_sl, rr=rr)
    f = v40.v40_frame(rs.load(BARS), p).copy()
    cap = p["max_sl"] * f["atr"]
    L, S = f["flip_up"].copy(), f["flip_dn"].copy()
    if bo:
        L = L | (f["close"] > f["high"].rolling(bo).max().shift(1))
        S = S | (f["close"] < f["low"].rolling(bo).min().shift(1))
    f["ok_l"] = f["in_sess"] & L & (f["e9"] > f["e22"]) & (f["risk_l"] <= cap)
    f["ok_s"] = f["in_sess"] & S & (f["e9"] < f["e22"]) & (f["risk_s"] <= cap) & ~f["ok_l"]
    s0 = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    return rs.simulate(f, dict(p, day_loss_limit_pts=day), start=s0, commission=comm)


def v50_variant(bo=None, comm=0.0):
    p = dict(v50.V50_INSTRUMENT_PARAMS["SILVER"]); p["atr_min_pts"] = 0
    f = v50.v50_frame(rs.load(BARS), p)
    cap = p["max_sl"] * f["atr"]
    tl = (f["e9"] > f["e22"]) & (f["close"] > f["e200"])
    ts = (f["e9"] < f["e22"]) & (f["close"] < f["e200"])
    g = f["in_sess"] & f["sha_stable"] & f["atr_ok"] & f["adx_ok"] & ~f["in_flat_window"]
    L, S = f["flip_up"].copy(), f["flip_dn"].copy()
    if bo:
        L = L | (f["close"] > f["high"].rolling(bo).max().shift(1))
        S = S | (f["close"] < f["low"].rolling(bo).min().shift(1))
    ff = f.copy()
    ff["ok_l"] = g & L & tl & (f["risk_l"] <= cap) & f["near_ema9_l"]
    ff["ok_s"] = g & S & ts & (f["risk_s"] <= cap) & f["near_ema9_s"] & ~ff["ok_l"]
    s0 = max(int((ff["time"] >= T0).idxmax()), rs.WARMUP)
    return rs.simulate(ff, dict(p, day_loss_limit_pts=p["day_loss_limit"]), start=s0,
                       flat_at=p["force_flat_window"][0], commission=comm)


def monthly(tr):
    t = pd.DataFrame(tr); t["exit_time"] = pd.to_datetime(t["exit_time"])
    return t.groupby(t.exit_time.dt.to_period("M")).net.sum()


def summarise(tr):
    s = rs.stats(tr)
    m = monthly(tr)
    return dict(n=s["n"], per_mo=round(s["n"]/30, 1), pf=s["pf"], net=round(s["net"], 0),
                dd=round(s["max_dd"], 0), win=s["win_pct"], pos_m=s["pos_months_pct"],
                conc=s["best_month_share"], eff=round(s["net"]/s["max_dd"], 2))


VARIANTS = {
    "Silver #1 INCUMBENT (v4.0 wideATR+350)": lambda c: v40_variant(comm=c),
    "Silver #2 wideATR no breaker":           lambda c: v40_variant(day=0.0, comm=c),
    "Silver #3 v4.0 vanilla":                 lambda c: v40_variant(min_sl=1.5, max_sl=3.0, day=0.0, comm=c),
    "v4.1 = #1 + breakout(5)  [B2]":          lambda c: v40_variant(bo=5, comm=c),
    "v4.1 = #1 + breakout(3)  [B1]":          lambda c: v40_variant(bo=3, comm=c),
    "v4.1 = #1 + breakout(10)":               lambda c: v40_variant(bo=10, comm=c),
    "v5.0 SHA-ADX hybrid":                    lambda c: v50_variant(comm=c),
    "v5.1 = v5.0 + breakout(5)":              lambda c: v50_variant(bo=5, comm=c),
}

if __name__ == "__main__":
    pd.set_option("display.width", 250)
    for comm, label in ((0.0, "GROSS"), (0.0002, "NET of 0.02%/side")):
        rows = []
        for name, fn in VARIANTS.items():
            tr = fn(comm)
            rows.append(dict(strategy=name, **summarise(tr)))
        R = pd.DataFrame(rows)
        inc = R.iloc[0]
        R["vs_#1_net"] = (R.net - inc.net).astype(int)
        print(f"\n{'='*40} {label} {'='*40}")
        print(R.to_string(index=False))
    # ---- is the v4.1 advantage distinguishable from noise? ----
    print("\n" + "="*95)
    print("IS IT REAL? paired monthly comparison, incumbent vs v4.1 breakout(5), GROSS")
    a, b = monthly(v40_variant()), monthly(v40_variant(bo=5))
    idx = a.index.union(b.index)
    a, b = a.reindex(idx, fill_value=0.0), b.reindex(idx, fill_value=0.0)
    d = b - a
    print(f"  months: {len(d)} | v4.1 better in {int((d>0).sum())}, worse in {int((d<0).sum())}")
    print(f"  total difference: {d.sum():+,.0f} pts | median monthly difference: {d.median():+,.1f} pts")
    print(f"  biggest single month difference: {d.abs().max():,.0f} pts ({d.abs().idxmax()})")
    print(f"  difference excluding the single largest month: {d.drop(d.abs().idxmax()).sum():+,.0f} pts")
    rng = np.random.default_rng(20260926)
    boot = np.array([rng.choice(d.values, len(d), replace=True).sum() for _ in range(20000)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"  bootstrap 95% CI on the total difference: [{lo:+,.0f} , {hi:+,.0f}] pts")
    print(f"  share of bootstrap samples where v4.1 is WORSE: {100*(boot<0).mean():.1f}%")
    k = int((d > 0).sum()); n = int((d != 0).sum())
    from math import comb
    p_two = 2 * sum(comb(n, i) for i in range(k, n+1)) / 2**n
    print(f"  sign test on monthly wins ({k}/{n}): two-sided p = {min(p_two,1.0):.3f}")
