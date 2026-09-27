import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crude_50cfg as C
import crude_round4 as R4
import research_sim as rs
import silver_sweep as SS

def sim(v, comm=0.0):
    d = C.data(9, 22)
    rr = v.get("rr", 4.0)
    p = dict(sha_len1=10, sha_len2=10, sha_min_hold=0, sw_len=10, sw_buf=0.1, min_sl=1.5, max_sl=3.0, rr=rr, adx_min=0.0, pb_atr_mult=99.0, atr_min_pts=0,
             use_vol_filter=False, vol_sma_len=50, use200=False, day_loss_limit=0.0, session=[v["start"], "23:30"], force_flat_window=["23:59", "23:59"])
    if "rr_l" in v: p["rr_l"], p["rr_s"] = v["rr_l"], v["rr_s"]
    f = SS.frame(d, p)
    atr, c, h, l, o = f["atr"], f["close"], f["high"], f["low"], f["open"]
    date = f["time"].dt.date
    gate = f["in_sess"] & ~f["in_flat_window"]
    T = pd.Series(True, index=f.index); ml, ms = T.copy(), T.copy()
    if v.get("dir") == "long": ms = ms & False
    if "dayrange" in v:
        dr = (h.groupby(date).cummax() - l.groupby(date).cummin()) / atr; ml = ml & (dr >= v["dayrange"]); ms = ms & (dr >= v["dayrange"])
    if v.get("gap"):
        do = date.map(o.groupby(date).first()).astype(float); pc = date.map(c.groupby(date).last().shift(1)).astype(float)
        ml = ml & (do > pc); ms = ms & (do < pc)
    if v.get("prior_mid"):
        pm = date.map(((h.groupby(date).max() + l.groupby(date).min()) / 2).shift(1)).astype(float); ml = ml & (c > pm); ms = ms & (c < pm)
    if "strength" in v:
        s = (f["e9"] - f["e22"]).abs() / atr >= v["strength"]; ml = ml & s; ms = ms & s
    if v.get("tue_thu"):
        m = f["time"].dt.dayofweek.isin([1, 2, 3]); ml = ml & m; ms = ms & m
    if v.get("atr_ratio"):
        m = atr / atr.rolling(100).mean() >= v["atr_ratio"]; ml = ml & m; ms = ms & m
    if "roc" in v:
        ml = ml & (c > c.shift(v["roc"])); ms = ms & (c < c.shift(v["roc"]))
    if "slope" in v:
        s = f["e9"] - f["e9"].shift(v["slope"]); ml = ml & (s > 0); ms = ms & (s < 0)
    ml_cap, ms_cap = v.get("max_l", 3.0) * atr, v.get("max_s", 3.0) * atr
    L = f["flip_up"] & (f["e9"] > f["e22"]); S = f["flip_dn"] & (f["e9"] < f["e22"])
    g = f.copy()
    g["ok_l"] = gate & L & ml.fillna(False) & (f["risk_l"] <= ml_cap)
    g["ok_s"] = gate & S & ms.fillna(False) & (f["risk_s"] <= ms_cap) & ~g["ok_l"]
    s0 = max(int((g["time"] >= C.T0).idxmax()), rs.WARMUP)
    kw = {}
    if v.get("be"): kw["be_at_r"] = v["be"]
    if v.get("trail"): kw["trail_start_r"], kw["trail_dist_r"] = v["trail"]
    return rs.simulate(g, dict(p, day_loss_limit_pts=0.0), start=s0, commission=comm, **kw)

R4.sim = sim   # reuse summ() from round 4 with this simulator

def cfgs():
    ideas = {
        "RR L5/S4": dict(rr_l=5.0, rr_s=4.0), "RR L5/S3": dict(rr_l=5.0, rr_s=3.0), "RR L6/S4": dict(rr_l=6.0, rr_s=4.0), "RR L4/S3": dict(rr_l=4.0, rr_s=3.0), "RR L6/S3": dict(rr_l=6.0, rr_s=3.0),
        "long only RR5": dict(dir="long", rr=5.0), "long only RR6": dict(dir="long", rr=6.0),
        "maxSL L3.5/S2.5": dict(max_l=3.5, max_s=2.5), "maxSL L2.5/S3.5": dict(max_l=2.5, max_s=3.5),
        "day range>=6": dict(dayrange=6.0), "day range>=10": dict(dayrange=10.0), "gap dir": dict(gap=True), "prior-day mid": dict(prior_mid=True),
        "strength>=0.5": dict(strength=0.5), "strength>=1.0": dict(strength=1.0), "Tue-Thu": dict(tue_thu=True), "ATR/ATR100>=0.8": dict(atr_ratio=0.8),
        "roc12": dict(roc=12), "roc24": dict(roc=24),
        "slope 3": dict(slope=3), "slope 12": dict(slope=12), "slope 24": dict(slope=24),
        "slope6 +be 2R": dict(slope=6, be=2.0), "slope6 +trail 2R/2R": dict(slope=6, trail=(2.0, 2.0)), "slope6 +RR L5/S4": dict(slope=6, rr_l=5.0, rr_s=4.0),
    }
    out = []
    for st in ("09:15", "17:30"):
        out.append((f"CTRL @{st}", dict(start=st)))
        out.append((f"slope 6 (round-4 lead) @{st}", dict(start=st, slope=6)))
        for k, o in ideas.items(): out.append((f"{k} @{st}", dict(start=st, **o)))
    return out

if __name__ == "__main__":
    R = pd.DataFrame([R4.summ(t, v) for t, v in cfgs()]); R.to_csv(C.ROOT / "research_data" / "crude_round5.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(R[["id", "full_n", "full_pf", "full_net", "full_cnet", "tr_net", "ho_net", "ho_cnet", "full_dd"]].to_string(index=False))
