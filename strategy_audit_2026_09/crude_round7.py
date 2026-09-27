"""Round 7: new mechanisms (reversal exit, cooldown, HTF gates, dual-SHA, cross-asset filter, adaptive stop/RR, etc).
Pre-registration: pre_registration_crude_round7_2026_09_27.md"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crude_50cfg as C
import crude_round4 as R4
import research_sim as rs
import silver_sweep as SS

_SIL = None
def silver_trend():
    global _SIL
    if _SIL is None:
        s = SS.base("MCX_SILVER1")
        s = s[["time", "e9", "e22"]].rename(columns={"e9": "s_e9", "e22": "s_e22"})
        _SIL = s
    return _SIL

_EXTRA = {}
def extra(d):
    if "done" in _EXTRA:
        return
    _EXTRA["done"] = True
    # 15m SHA(10,10) and EMA9/22, previous COMPLETED 15m bar, no lookahead (same convention as v50.adx_15m_prev)
    k = (d.set_index("time").resample("15min", label="left", closed="left")
           .agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(subset=["close"]).reset_index())
    up15, _, _, _ = SS.sha(k, 10, 10, 0)
    up15_prev = up15.shift(1)
    e9_15, e22_15 = k["close"].ewm(span=9, adjust=False).mean(), k["close"].ewm(span=22, adjust=False).mean()
    trend15_up_prev = (e9_15 > e22_15).shift(1)
    trend15_dn_prev = (e9_15 < e22_15).shift(1)
    k["sha15_up_prev"], k["trend15_up_prev"], k["trend15_dn_prev"] = up15_prev, trend15_up_prev, trend15_dn_prev
    lu = dict(zip(k["time"], k["sha15_up_prev"])); ltu = dict(zip(k["time"], k["trend15_up_prev"])); ltd = dict(zip(k["time"], k["trend15_dn_prev"]))
    floor15 = d["time"].dt.floor("15min")
    d["sha15_up_prev"] = floor15.map(lu)
    d["trend15_up_prev"] = floor15.map(ltu)
    d["trend15_dn_prev"] = floor15.map(ltd)
    # dual-length SHA(5,5) and SHA(20,20) states
    for L in (5, 20):
        up, _, _, _ = SS.sha(d, L, L, 0)
        d[f"sha{L}_up"] = up
    # silver trend agreement
    st = silver_trend()
    m = pd.merge_asof(d[["time"]].assign(_i=np.arange(len(d))), st.sort_values("time"), on="time", direction="backward")
    d["s_e9"] = m["s_e9"].to_numpy(); d["s_e22"] = m["s_e22"].to_numpy()
    # ATR tercile regime (trailing 500 bars)
    r1, r2 = d["atr"].rolling(500).quantile(1/3), d["atr"].rolling(500).quantile(2/3)
    d["atr_lo"], d["atr_hi"] = r1, r2
    # close-based swing
    d["sw_lo_c"] = d["close"].rolling(10).min(); d["sw_hi_c"] = d["close"].rolling(10).max()

def base():
    d = C.data(9, 22)
    extra(d)
    return d

def sim(v, comm=0.0):
    d = base()
    tmin = d["tmin"]
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in (v["start"], "23:30")]
    in_sess = (tmin >= s0m) & (tmin < s1m)
    atr = d["atr"]; c = d["close"]
    cap_mult = pd.Series(3.0, index=d.index)
    rr_mult = pd.Series(4.0, index=d.index)
    if v.get("adaptive_cap"):
        cap_mult = np.where(atr >= d["atr_hi"], 2.5, np.where(atr <= d["atr_lo"], 3.5, 3.0))
        cap_mult = pd.Series(cap_mult, index=d.index)
    if v.get("adaptive_rr"):
        rr_mult = np.where(atr >= d["atr_hi"], 3.0, np.where(atr <= d["atr_lo"], 5.0, 4.0))
        rr_mult = pd.Series(rr_mult, index=d.index)
    cap = cap_mult * atr
    L = d["e9"] > d["e22"]
    S = d["e9"] < d["e22"]
    if "flip_up" not in d.columns:
        _, fu, fd, _ = SS.sha(d, 10, 10, 0)
        d["flip_up"], d["flip_dn"] = fu, fd
    flipL, flipS = d["flip_up"], d["flip_dn"]
    if v.get("delay"):
        flipL, flipS = flipL.shift(1).fillna(False), flipS.shift(1).fillna(False)
    ml = flipL & L
    ms = flipS & S
    if v.get("htf_sha"):
        ml = ml & d["sha15_up_prev"].fillna(False)
        ms = ms & ~d["sha15_up_prev"].fillna(True)
    if v.get("htf_ema"):
        ml = ml & d["trend15_up_prev"].fillna(False)
        ms = ms & d["trend15_dn_prev"].fillna(False)
    if v.get("dual_sha"):
        ml = ml & d["sha5_up"] & d["sha20_up"]
        ms = ms & ~d["sha5_up"] & ~d["sha20_up"]
    if v.get("silver_agree"):
        ml = ml & (d["s_e9"] > d["s_e22"])
        ms = ms & (d["s_e9"] < d["s_e22"])
    if v.get("round_skip"):
        dist = (c % 50).where(c % 50 <= 25, 50 - (c % 50))
        far = dist >= 0.3 * atr
        ml = ml & far; ms = ms & far
    if v.get("two_bar_confirm"):
        ml = ml & (c > d["high"].shift(1))
        ms = ms & (c < d["low"].shift(1))
    swlo = d["sw_lo_c"] if v.get("close_swing") else d["sw_lo"] if "sw_lo" in d.columns else d["low"].rolling(10).min()
    swhi = d["sw_hi_c"] if v.get("close_swing") else d["sw_hi"] if "sw_hi" in d.columns else d["high"].rolling(10).max()
    risk_l = np.maximum(c - (swlo - 0.1 * atr), 1.5 * atr)
    risk_s = np.maximum((swhi + 0.1 * atr) - c, 1.5 * atr)
    g = d.copy()
    g["risk_l"], g["risk_s"] = risk_l, risk_s
    g["ok_l"] = in_sess & ml.fillna(False) & (risk_l <= cap)
    g["ok_s"] = in_sess & ms.fillna(False) & (risk_s <= cap) & ~g["ok_l"]
    p = dict(rr=4.0, day_loss_limit_pts=0.0)
    if v.get("no_target"):
        p["rr"] = 1000.0   # effectively no target; reversal_exit / stop close it
    if not v.get("adaptive_rr"):
        pass
    else:
        g["_rr"] = rr_mult
    s0 = max(int((g["time"] >= C.T0).idxmax()), rs.WARMUP)
    kw = dict(cooldown_bars=v.get("cooldown"), reversal_exit=bool(v.get("reversal")))
    if v.get("adaptive_rr"):
        # simulate() only reads p["rr"]; approximate adaptive RR by running the fixed-RR engine per regime is
        # too slow to re-derive per bar inside the loop, so instead widen the frame with a precomputed tp via rr_l/rr_s
        # NOTE: kept simple -- use the median regime RR as a fixed proxy is inaccurate, so this idea instead patches
        # p to carry a per-row rr array the engine does not read; skip precision, use average-regime RR=4 fallback disabled.
        pass
    return rs.simulate(g, p, start=s0, commission=comm, **kw)

IDEAS = {
    "reversal exit": dict(reversal=True),
    "reversal exit, no target": dict(reversal=True, no_target=True),
    "cooldown 6 bars": dict(cooldown=6),
    "cooldown 24 bars": dict(cooldown=24),
    "cooldown 6 + reversal": dict(cooldown=6, reversal=True),
    "15m SHA agreement": dict(htf_sha=True),
    "15m EMA9/22 agreement": dict(htf_ema=True),
    "dual SHA 5/20 confirm": dict(dual_sha=True),
    "silver trend agreement": dict(silver_agree=True),
    "round-number skip": dict(round_skip=True),
    "adaptive stop cap": dict(adaptive_cap=True),
    "close-based swing stop": dict(close_swing=True),
    "two-bar confirm": dict(two_bar_confirm=True),
    "delayed entry (+1 bar)": dict(delay=True),
}

def cfgs():
    out = []
    for st in ("09:15", "17:30"):
        out.append((f"CTRL @{st}", dict(start=st)))
        for k, o in IDEAS.items():
            out.append((f"{k} @{st}", dict(start=st, **o)))
    return out

def summ(tag, v):
    tr, trn = sim(v), sim(v, 0.0002)
    row = dict(id=tag, start=v["start"])
    if len(tr) < 20:
        row["full_n"] = len(tr)
        return row
    for nm, sub in (("full", None), ("tr", "<"), ("ho", ">=")):
        for suf, T in (("", tr), ("c", trn)):
            t = pd.DataFrame(T); t["x"] = pd.to_datetime(t["exit_time"])
            if sub == "<": t = t[t.x < C.SPLIT]
            elif sub == ">=": t = t[t.x >= C.SPLIT]
            s = rs.stats(t.to_dict("records")) if len(t) else dict(n=0, pf=0, net=0, max_dd=0)
            if suf == "":
                row.update({f"{nm}_n": s["n"], f"{nm}_pf": s["pf"], f"{nm}_net": round(s["net"]), f"{nm}_dd": round(s["max_dd"])})
            else:
                row[f"{nm}_cnet"] = round(s["net"])
    return row

if __name__ == "__main__":
    rows = []
    for i, (t, v) in enumerate(cfgs()):
        rows.append(summ(t, v))
        print(f"{i + 1}/{len(cfgs())} {t}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(C.ROOT / "research_data" / "crude_round7.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(R[["id", "full_n", "full_pf", "full_net", "full_cnet", "tr_net", "ho_net", "ho_cnet", "full_dd"]].to_string(index=False))
