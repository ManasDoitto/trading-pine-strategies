"""Broad edge search for the deployed SILVERM strategy (pre_registration_silverm_edge_search_2026_10_03.md)."""
import sys
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs
from trading_agents.core.signals import ema

P0 = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
BARS = {"SILVERM1": rs.load("MCX_SILVERM1"), "SILVER1": rs.load("MCX_SILVER1")}
CACHE = {}


def base_frame(name, p):
    key = (name, p["bo_lookback"], p["sw_buf"])
    if key not in CACHE:
        f = rs.v40.v40_frame(BARS[name], p)
        f["ema200"] = ema(f.close, 200)
        f["gap"] = (f.e9 - f.e22) / f.atr
        f["pos_in_bar"] = (f.close - f.low) / (f.high - f.low).replace(0, np.nan)
        f["rng_atr"] = (f.high - f.low) / f.atr
        f["vol_ratio"] = f.volume / f.volume.rolling(20).mean().shift(1)
        bo = p["bo_lookback"]
        f["dc_hi"] = f.high.rolling(bo).max().shift(1)
        f["dc_lo"] = f.low.rolling(bo).min().shift(1)
        f["bo_l"] = f.close > f.dc_hi
        f["bo_s"] = f.close < f.dc_lo
        f["atr_pct"] = f.atr.rolling(2000, min_periods=500).rank(pct=True)
        f["hour"] = f.time.dt.hour
        for tf, lab in (("15min", "t15"), ("60min", "t60")):
            s = f.set_index("time").close
            c = s.resample(tf).last().dropna()
            up = (ema(c, 9) > ema(c, 22))
            prev = up.shift(1)                                    # previous COMPLETED higher-timeframe bar
            f[lab] = f.time.dt.floor(tf).map(prev).to_numpy()
        CACHE[key] = f
    return CACHE[key]


def entry_masks(f, key):
    """(allow_long, allow_short) boolean Series for entry filter `key` (applied on the signal bar)."""
    T = pd.Series(True, index=f.index)
    F = pd.Series(False, index=f.index)
    if key == "F1": return f.gap >= 0.2, f.gap <= -0.2
    if key == "F2": return f.close > f.ema200, f.close < f.ema200
    if key == "F3": return f.t15.fillna(False).astype(bool), ~f.t15.fillna(True).astype(bool)
    if key == "F4": return f.t60.fillna(False).astype(bool), ~f.t60.fillna(True).astype(bool)
    if key == "F5": return T, F
    if key == "F6": return f.pos_in_bar >= 0.7, f.pos_in_bar <= 0.3
    if key == "F7": return f.rng_atr >= 0.8, f.rng_atr >= 0.8
    if key == "F8": return f.vol_ratio >= 1.2, f.vol_ratio >= 1.2
    if key == "F9": return (f.close - f.dc_hi) >= 0.1 * f.atr, (f.dc_lo - f.close) >= 0.1 * f.atr
    if key == "F10": return f.atr_pct >= 0.5, f.atr_pct >= 0.5
    if key == "F11": return f.atr_pct >= 0.67, f.atr_pct >= 0.67
    if key == "F12": return f.atr_pct <= 0.95, f.atr_pct <= 0.95
    if key == "F13": return ~f.hour.isin([13, 17]), ~f.hour.isin([13, 17])
    if key == "F14": return f.bo_l, f.bo_s
    return T, T


ENTRY = [f"F{i}" for i in range(1, 15)]                           # F15 changes the frame itself
EXITS = {"X1": dict(scale_r=1.5, scale_frac=0.5), "X2": dict(scale_r=1.0, scale_frac=0.5), "X3": dict(be_at_r=2.0),
         "X4": dict(trail_start_r=2.0, trail_dist_r=1.5), "X5": dict(reversal_exit=True)}
ALL = ENTRY + ["F15"] + list(EXITS) + ["X6"]


def run(name, keys):
    p = dict(P0)
    if "F15" in keys: p["bo_lookback"] = 5
    if "X6" in keys: p["sw_buf"] = 0.3
    f = base_frame(name, p).copy()
    kw = {}
    for k in keys:
        if k in ENTRY:
            al, as_ = entry_masks(f, k)
            f["ok_l"] &= al.fillna(False)
            f["ok_s"] &= as_.fillna(False)
        elif k in EXITS:
            kw.update(EXITS[k])
    t = pd.DataFrame(rs.simulate(f, p, **kw))
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
    return dict(n=len(t), win=round(100 * (t.net > 0).mean(), 1), pf=pf(t.net), net=round(t.net.sum()), expR=round(t.R.mean(), 3), dd_R=round((eq.cummax() - eq).max(), 1),
                dd_pts=round((ep.cummax() - ep).max()), pos_m=round(100 * (mo > 0).mean()), hold_h=round(t.hold_h.mean(), 1))


base = {n: run(n, []) for n in BARS}
CUT = {n: base[n].exit_time.quantile(.8) for n in BARS}
dev = lambda t, n: t[t.exit_time <= CUT[n]]
hold = lambda t, n: t[t.exit_time > CUT[n]]
BD = {n: metrics(dev(base[n], n)) for n in BARS}
pd.set_option("display.width", 250, "display.max_rows", 200)
print("BASELINE development:", pd.DataFrame(BD).to_string(), sep="\n")


def blocked_fraction(key, n):
    """share of baseline development trades whose signal bar fails entry filter `key`"""
    f = base_frame(n, P0)
    al, as_ = entry_masks(f, key)
    idx = f.set_index("time")
    d = dev(base[n], n)
    ok = [bool(al[idx.index.get_loc(s)] if sd == "LONG" else as_[idx.index.get_loc(s)]) for s, sd in zip(d.signal_time, d.side)]
    return 1 - float(np.mean(ok))


rng = np.random.default_rng(11)


def null_p90(n, frac):
    d = dev(base[n], n).R.to_numpy()
    k = int(round(len(d) * (1 - frac)))
    gains = [d[rng.choice(len(d), k, replace=False)].mean() - d.mean() for _ in range(2000)]
    return float(np.percentile(gains, 90))


def eligible(m, b):
    return (m["expR"] >= b["expR"] + 0.03 and m["dd_R"] <= 1.10 * b["dd_R"] and m["pos_m"] >= b["pos_m"] - 3 and m["pf"] >= b["pf"] - 0.03 and m["n"] >= 350)


rows, elig = [], []
for k in ALL:
    m = {n: metrics(dev(run(n, [k]), n)) for n in BARS}
    ok = all(eligible(m[n], BD[n]) for n in BARS)
    nullp = None
    if k in ENTRY:
        fr = blocked_fraction(k, "SILVERM1")
        nullp = round(null_p90("SILVERM1", fr), 3)
        gain = m["SILVERM1"]["expR"] - BD["SILVERM1"]["expR"]
        ok = ok and gain > nullp
    if ok:
        elig.append(k)
    for n in BARS:
        rows.append(dict(cand=k, data=n, ok=ok if n == "SILVERM1" else "", n=m[n]["n"], expR=m[n]["expR"], d_expR=round(m[n]["expR"] - BD[n]["expR"], 3), pf=m[n]["pf"], net=m[n]["net"],
                         dd_R=m[n]["dd_R"], pos_m=m[n]["pos_m"], null_p90=nullp if n == "SILVERM1" else "", hold_h=m[n]["hold_h"]))
    print(f"done {k}", flush=True)
R = pd.DataFrame(rows)
R.to_csv("research_data/silverm_edge_search_dev.csv", index=False)
print("\nDEVELOPMENT results, one change at a time (SILVERM1 then SILVER1 per candidate):")
print(R.to_string(index=False))
print("\nELIGIBLE after Stage 1:", elig)
if not elig:
    print("NOTHING ELIGIBLE: the deployed strategy stays; no holdout look taken.")
    sys.exit(0)

order = sorted(elig, key=lambda k: -(metrics(dev(run("SILVERM1", [k]), "SILVERM1"))["expR"]))
combo, cur = [], None
for k in order:
    trial = combo + [k]
    m = {n: metrics(dev(run(n, trial), n)) for n in BARS}
    if all(eligible(m[n], BD[n]) for n in BARS) and (cur is None or m["SILVERM1"]["expR"] >= cur + 0.01) and len(trial) <= 3:
        combo, cur = trial, m["SILVERM1"]["expR"]
print("\nCOMBINATION chosen on development:", combo)
if not combo:
    print("No valid combination.")
    sys.exit(0)
final = {n: run(n, combo) for n in BARS}
print("development:", {n: metrics(dev(final[n], n)) for n in BARS})
print("\nHOLDOUT (one look):")
H = {n: (metrics(hold(base[n], n)), metrics(hold(final[n], n))) for n in BARS}
for n in BARS:
    print(n, "\n", pd.DataFrame({"baseline": H[n][0], "final": H[n][1]}).to_string())
b, c, s1 = H["SILVERM1"][0], H["SILVERM1"][1], H["SILVER1"][1]
ok = c["expR"] >= b["expR"] and c["pf"] >= b["pf"] and c["dd_R"] <= 1.10 * b["dd_R"] and c["net"] >= .9 * b["net"] and s1["expR"] > 0
print("\nHOLDOUT VERDICT:", "PASS" if ok else "FAIL")
months = None
A, B = base["SILVERM1"], final["SILVERM1"]
mlist = sorted(set(A.exit_time.dt.to_period("M")) | set(B.exit_time.dt.to_period("M")))
ga = {m: g for m, g in A.groupby(A.exit_time.dt.to_period("M"))}
gb = {m: g for m, g in B.groupby(B.exit_time.dt.to_period("M"))}
rg = np.random.default_rng(3)
de = []
for _ in range(3000):
    pk = [mlist[i] for i in rg.choice(len(mlist), len(mlist))]
    de.append(pd.concat([gb[m] for m in pk if m in gb]).R.mean() - pd.concat([ga[m] for m in pk if m in ga]).R.mean())
print(f"FULL HISTORY SILVERM1 expectancy difference (final - baseline): median {np.median(de):.3f}, P(final better) {100*np.mean(np.array(de) > 0):.0f}% (optimistic: pick used part of this data)")
print(pd.DataFrame({"baseline": metrics(A), "final": metrics(B)}).to_string())
