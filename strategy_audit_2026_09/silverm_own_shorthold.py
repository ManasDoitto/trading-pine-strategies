"""SILVERM-native short-hold search (pre_registration_silverm_own_shorthold_2026_10_03.md). Holdout printed once, for the top 3 + live."""
import itertools
import sys
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

LIVE_P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
BARS = {"SILVERM1": rs.load("MCX_SILVERM1"), "SILVER1": rs.load("MCX_SILVER1")}
WIN = {"allday": (0, 24 * 60), "evening": (17 * 60, 23 * 60), "from12": (12 * 60, 24 * 60)}
EXITS = {"overnight": dict(), "flat": dict(flat_at="23:25"), "t240+flat": dict(time_stop_min=240, flat_at="23:25"),
         "t120+flat": dict(time_stop_min=120, flat_at="23:25")}
SLS = {"2.5/5.0": (2.5, 5.0), "1.5/3.0": (1.5, 3.0)}
LIVE = ("allday", 3.0, "2.5/5.0", "overnight")
FR = {}


def frame(name, sl):
    if (name, sl) not in FR:
        p = dict(LIVE_P, min_sl=SLS[sl][0], max_sl=SLS[sl][1])
        FR[(name, sl)] = rs.v40.v40_frame(BARS[name], p)
    return FR[(name, sl)]


def run(cfg, name):
    win, rr, sl, ex = cfg
    p = dict(LIVE_P, rr=rr, min_sl=SLS[sl][0], max_sl=SLS[sl][1])
    f = frame(name, sl).copy()
    m = f.time.dt.hour * 60 + f.time.dt.minute
    lo, hi = WIN[win]
    outside = ~((m >= lo) & (m < hi))
    f["ok_l"] &= ~outside
    f["ok_s"] &= ~outside
    t = pd.DataFrame(rs.simulate(f, p, **EXITS[ex]))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return w / l if l > 0 else 9.9


def metrics(t):
    if len(t) < 20:
        return dict(n=len(t))
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    eq = t.R.cumsum()
    q = t.exit_time.quantile([.6, .8])
    a, b = t[t.exit_time <= q[.6]], t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])]
    return dict(n=len(t), exp_R=t.R.mean(), pf_R=pf(t.R), pf_pts=pf(t.net), net_pts=t.net.sum(), net_tr=a.net.sum(), net_va=b.net.sum(),
                exp_tr=a.R.mean(), exp_va=b.R.mean(), dd_R=(eq.cummax() - eq).max(), win=100 * (t.net > 0).mean(), pos_m=100 * (mo > 0).mean(),
                best_share=100 * mo.max() / t.net.sum() if t.net.sum() > 0 else 999, months=len(mo), hold_h=t.hold_h.mean(), med_hold=t.hold_h.median())


def split(t):
    cut = t.exit_time.quantile(.8)
    return t[t.exit_time <= cut], t[t.exit_time > cut]


GRID = list(itertools.product(WIN, [1.5, 2.0, 3.0], SLS, EXITS))
assert len(GRID) == 72 and LIVE in GRID
lab = lambda c: f"{c[0]}/rr{c[1]:g}/sl{c[2]}/{c[3]}"
TR, DEV = {}, {}
for i, c in enumerate(GRID):
    for n in BARS:
        TR[(c, n)] = run(c, n)
        DEV[(c, n)] = metrics(split(TR[(c, n)])[0])
    print(f"{i + 1}/72 {lab(c)}", flush=True)


def eligible(c):
    m, k = DEV[(c, "SILVERM1")], DEV[(c, "SILVER1")]
    return (m.get("n", 0) >= 400 and m["hold_h"] <= 5.0 and m["net_tr"] > 0 and m["net_va"] > 0 and m["exp_tr"] > 0 and m["exp_va"] > 0
            and m["pos_m"] >= 55 and m["best_share"] <= 30 and k.get("n", 0) > 0 and k["exp_R"] > 0 and k["pos_m"] >= 50)


rows = []
for c in GRID:
    m, k = DEV[(c, "SILVERM1")], DEV[(c, "SILVER1")]
    rows.append(dict(cfg=lab(c), eligible=eligible(c), n=m.get("n"), hold_h=m.get("hold_h"), med_hold=m.get("med_hold"), exp_R=m.get("exp_R"),
                     pf_R=m.get("pf_R"), exp_tr=m.get("exp_tr"), exp_va=m.get("exp_va"), pos_m=m.get("pos_m"), best_share=m.get("best_share"),
                     dd_R=m.get("dd_R"), win=m.get("win"), s1_exp=k.get("exp_R"), s1_pos_m=k.get("pos_m"), net_pts=m.get("net_pts")))
R = pd.DataFrame(rows)
R.to_csv("research_data/silverm_own_shorthold_dev.csv", index=False)
pd.set_option("display.width", 250, "display.max_rows", 100)
cols = ["cfg", "n", "hold_h", "med_hold", "exp_R", "pf_R", "exp_tr", "exp_va", "pos_m", "best_share", "dd_R", "win", "s1_exp", "s1_pos_m"]
print("\nLIVE on development:", R[R.cfg == lab(LIVE)][cols].round(2).to_string(index=False))
print(f"\nELIGIBLE: {int(R.eligible.sum())} of 72")
print(R[R.eligible][cols].round(2).to_string(index=False))
short = R[(R.hold_h <= 5.0) & (R.n >= 400)]
print("\nCONFIGS WITH AVG HOLD <= 5h (n>=400): how each criterion fares (information only), best 12 by SILVERM dev expectancy:")
print(short.sort_values("exp_R", ascending=False).head(12)[cols].round(2).to_string(index=False))
if not R.eligible.any():
    print("\nNOTHING ELIGIBLE.")
    sys.exit(0)

top = R[R.eligible].assign(sc=lambda d: d[["exp_R", "s1_exp"]].min(axis=1)).sort_values("sc", ascending=False).head(3).cfg.tolist()
by = {lab(c): c for c in GRID}
print("\nTOP 3 for the holdout:", top)
print("\nHOLDOUT (newest 20%, SILVERM1), looked at once:")
H = {"LIVE v4.1": metrics(split(TR[(LIVE, 'SILVERM1')])[1])}
for k in top:
    H[k] = metrics(split(TR[(by[k], 'SILVERM1')])[1])
print(pd.DataFrame(H).round(3).to_string())
print("\nSILVER1 holdout (confirmation):")
print(pd.DataFrame({"LIVE v4.1": metrics(split(TR[(LIVE, 'SILVER1')])[1]), **{k: metrics(split(TR[(by[k], 'SILVER1')])[1]) for k in top}}).round(3).to_string())
live_h = H["LIVE v4.1"]
for k in top:
    h = H[k]
    ok = h["exp_R"] > 0 and h["pf_R"] >= 1.0 and h["pos_m"] >= 50 and h["hold_h"] <= 5.0 and h["dd_R"] <= live_h["dd_R"]
    print(k, "HOLDOUT", "PASS" if ok else "FAIL")
print("\nFULL HISTORY (SILVERM1) live vs top 3:")
print(pd.DataFrame({"LIVE v4.1": metrics(TR[(LIVE, 'SILVERM1')]), **{k: metrics(TR[(by[k], 'SILVERM1')]) for k in top}}).round(3).to_string())
