import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crude_50cfg as C, crude_round3 as R3
import research_sim as rs
import silver_sweep as SS

def sim(v, comm=0.0):
    d = C.data(v.get("fast", 9), v.get("slow", 22))
    p = dict(sha_len1=10, sha_len2=10, sha_min_hold=v.get("hold", 0), sw_len=10, sw_buf=0.1, min_sl=1.5, max_sl=3.0, rr=4.0, adx_min=0.0, pb_atr_mult=99.0, atr_min_pts=0,
             use_vol_filter=False, vol_sma_len=50, use200=False, day_loss_limit=0.0, session=[v["start"], v.get("end", "23:30")], force_flat_window=["23:59", "23:59"])
    f = SS.frame(d, p)
    atr, c = f["atr"], f["close"]
    gate = f["in_sess"] & ~f["in_flat_window"]
    ml = ms = pd.Series(True, index=f.index)
    if "atrp" in v:
        W, q = v["atrp"]; m = atr < atr.rolling(W).quantile(q / 100); ml = ml & m; ms = ms & m
    if v.get("skip_22"): gate = gate & (f["time"].dt.hour != 22)
    if v.get("dir") == "long": ms = ms & False
    if v.get("dir") == "short": ml = ml & False
    date = f["time"].dt.date
    if v.get("prior_range"):
        dr = (f["high"].groupby(date).max() - f["low"].groupby(date).min()); med = dr.rolling(20).median()
        m = (dr > med).shift(1); m = date.map(m).astype(float) == 1.0; ml = ml & m; ms = ms & m
    if v.get("atr_rising"): m = atr > atr.shift(12); ml = ml & m; ms = ms & m
    if v.get("slope9"): s = f["e9"] - f["e9"].shift(6); ml = ml & (s > 0); ms = ms & (s < 0)
    cap = 3.0 * atr
    L = f["flip_up"] & f["sha_stable"] & (f["e9"] > f["e22"]); S = f["flip_dn"] & f["sha_stable"] & (f["e9"] < f["e22"])
    g = f.copy()
    g["ok_l"] = gate & L & ml.fillna(False) & (f["risk_l"] <= cap)
    g["ok_s"] = gate & S & ms.fillna(False) & (f["risk_s"] <= cap) & ~g["ok_l"]
    s0 = max(int((g["time"] >= C.T0).idxmax()), rs.WARMUP)
    kw = {}
    if v.get("be"): kw["be_at_r"] = v["be"]
    if v.get("trail"): kw["trail_start_r"], kw["trail_dist_r"] = v["trail"]
    return rs.simulate(g, dict(p, day_loss_limit_pts=0.0), start=s0, commission=comm, **kw)

def summ(tag, v):
    tr, trn = sim(v), sim(v, 0.0002)
    row = dict(id=tag, start=v["start"])
    if len(tr) < 20: row["full_n"] = len(tr); return row
    for nm, sub in (("full", None), ("tr", "<"), ("ho", ">=")):
        for suf, T in (("", tr), ("c", trn)):
            t = pd.DataFrame(T); t["x"] = pd.to_datetime(t["exit_time"])
            if sub == "<": t = t[t.x < C.SPLIT]
            elif sub == ">=": t = t[t.x >= C.SPLIT]
            s = rs.stats(t.to_dict("records")) if len(t) else dict(n=0, pf=0, net=0, max_dd=0)
            if suf == "": row.update({f"{nm}_n": s["n"], f"{nm}_pf": s["pf"], f"{nm}_net": round(s["net"]), f"{nm}_dd": round(s["max_dd"])})
            else: row[f"{nm}_cnet"] = round(s["net"])
    return row

def cfgs():
    out = []
    for st in ("09:15", "17:30"):
        b = dict(start=st)
        out.append((f"CTRL @{st}", b))
        for W, qs in ((250, (80, 90, 95)), (500, (80, 85, 95)), (1000, (80, 90, 95))):
            for q in qs: out.append((f"A atr<p{q} W{W} @{st}", dict(b, atrp=(W, q))))
        a = dict(b, atrp=(500, 90))
        for k, o in {"+be 2R": dict(be=2.0), "+trail 2R/2R": dict(trail=(2.0, 2.0)), "+skip 22h": dict(skip_22=True), "+ema 9/34": dict(slow=34), "+hold 4": dict(hold=4)}.items():
            out.append((f"B p90 {k} @{st}", dict(a, **o)))
        out += [(f"C long only @{st}", dict(b, dir="long")), (f"C short only @{st}", dict(b, dir="short"))]
        for e in ("23:00", "22:00", "21:00"): out.append((f"D entries end {e} @{st}", dict(b, end=e)))
        out += [(f"E prior-day range > med20 @{st}", dict(b, prior_range=True)), (f"E ATR rising @{st}", dict(b, atr_rising=True)), (f"E EMA9 slope @{st}", dict(b, slope9=True))]
        out += [(f"F hold 6 @{st}", dict(b, hold=6)), (f"F hold 8 @{st}", dict(b, hold=8))]
    return out

if __name__ == "__main__":
    R = pd.DataFrame([summ(t, v) for t, v in cfgs()]); R.to_csv(C.ROOT / "research_data" / "crude_round4.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(len(R) - 2, "configs")
    print(R[["id", "full_n", "full_pf", "full_net", "full_cnet", "tr_net", "ho_net", "ho_cnet", "full_dd"]].to_string(index=False))
