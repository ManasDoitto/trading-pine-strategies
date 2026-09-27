import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crude_50cfg as C
import research_sim as rs
import silver_sweep as SS

def masks(f, name):
    """returns (long_ok, short_ok) boolean Series"""
    c, o, h, l, atr = f["close"], f["open"], f["high"], f["low"], f["atr"]
    T = pd.Series(True, index=f.index)
    rng = (h - l).replace(0, np.nan)
    pos = (c - l) / rng
    date = f["time"].dt.date
    if name.startswith("body>="):
        k = float(name[6:]); b = (c - o).abs() / atr >= k
        return b & (c > o), b & (c < o)
    if name.startswith("cpos"):
        k = int(name[4:]) / 100
        return pos >= 1 - k, pos <= k
    if name == "e60": e = c.ewm(span=60, adjust=False).mean(); return c > e, c < e
    if name == "e240": e = c.ewm(span=240, adjust=False).mean(); return c > e, c < e
    if name == "prevday close":
        lastc = c.groupby(date).last(); pc = date.map(lastc.shift(1)).astype(float); return c > pc, c < pc
    if name == "day open":
        do = date.map(o.groupby(date).first()).astype(float); return c > do, c < do
    if name == "atr>p50": p = atr.rolling(500).median(); return atr > p, atr > p
    if name == "atr<p90": p = atr.rolling(500).quantile(0.9); return atr < p, atr < p
    if name.startswith("vol>sma"):
        n = int(name[7:]); v = f["volume"] > f["volume"].rolling(n).mean(); return v, v
    if name == "slope22": s = f["e22"] - f["e22"].shift(6); return s > 0, s < 0
    if name.startswith("dist<"):
        k = float(name[5:]); d = (c - f["e22"]).abs() / atr < k; return d, d
    if name == "skip Mon": m = f["time"].dt.dayofweek != 0; return m, m
    if name.startswith("rsi>"):
        k = float(name[4:]); dlt = c.diff(); g = dlt.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); ls = (-dlt.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        r = 100 - 100 / (1 + g / ls.replace(0, np.nan)); return r > k, r < 100 - k
    if name == "vwap":
        tp = (h + l + c) / 3; pv = (tp * f["volume"]).groupby(date).cumsum(); vv = f["volume"].groupby(date).cumsum().replace(0, np.nan); w = pv / vv; return c > w, c < w
    if name == "don20mid": mid = (h.rolling(20).max() + l.rolling(20).min()) / 2; return c > mid, c < mid
    if name == "sq10": r10 = (h.rolling(10).max() - l.rolling(10).min()) / atr < 3; return r10, r10
    if name == "wide10": r10 = (h.rolling(10).max() - l.rolling(10).min()) / atr >= 3; return r10, r10
    if name == "sigrange<1.5": r = (h - l) / atr < 1.5; return r, r
    return T, T

NAMES = ["body>=0.3", "body>=0.5", "cpos30", "cpos50", "e60", "e240", "prevday close", "day open", "atr>p50", "atr<p90", "vol>sma20", "vol>sma50", "slope22",
         "dist<2", "dist<3", "skip Mon", "rsi>50", "rsi>55", "vwap", "don20mid", "sq10", "wide10", "sigrange<1.5", "fixed 2.0", "fixed 2.5"]

def sim(v, name, comm=0.0):
    d = C.data(9, 22)
    p = dict(sha_len1=10, sha_len2=10, sha_min_hold=0, sw_len=10, sw_buf=0.1, min_sl=1.5, max_sl=3.0, rr=4.0, adx_min=0.0, pb_atr_mult=99.0, atr_min_pts=0,
             use_vol_filter=False, vol_sma_len=50, use200=False, day_loss_limit=0.0, session=[v["start"], "23:30"], force_flat_window=["23:59", "23:59"])
    f = SS.frame(d, p)
    atr = f["atr"]
    gate = f["in_sess"] & ~f["in_flat_window"]
    ml, ms = masks(f, name)
    if name.startswith("fixed"):
        k = float(name[6:]); f["risk_l"] = k * atr; f["risk_s"] = k * atr; ml = ms = pd.Series(True, index=f.index)
    cap = 3.0 * atr
    L = f["flip_up"] & (f["e9"] > f["e22"]); S = f["flip_dn"] & (f["e9"] < f["e22"])
    g = f.copy()
    g["ok_l"] = gate & L & ml.fillna(False) & (f["risk_l"] <= cap)
    g["ok_s"] = gate & S & ms.fillna(False) & (f["risk_s"] <= cap) & ~g["ok_l"]
    s0 = max(int((g["time"] >= C.T0).idxmax()), rs.WARMUP)
    return rs.simulate(g, dict(p, day_loss_limit_pts=0.0), start=s0, commission=comm)

def summ(tag, v, name):
    tr, trn = sim(v, name), sim(v, name, 0.0002)
    row = dict(id=tag, start=v["start"], name=name)
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

if __name__ == "__main__":
    rows = []
    for st in ("09:15", "17:30"):
        v = dict(C.BASE, start=st)
        rows.append(summ(f"CTRL @{st}", v, "none"))
        for n in NAMES: rows.append(summ(f"{n} @{st}", v, n))
    R = pd.DataFrame(rows); R.to_csv(C.ROOT / "research_data" / "crude_round3.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(R[["id", "full_n", "full_pf", "full_net", "full_cnet", "tr_net", "ho_net", "ho_cnet", "full_dd"]].to_string(index=False))
