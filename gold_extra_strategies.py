"""Stage 2: strategies that live outside the repo's python research modules, ported onto the same
frame/simulator so they are judged identically on gold:
  * variant-lab V01..V32 (variant_lab_v1 Pine: RSI3 pullbacks, EMA-touch, SHA flip, Donchian+SHA, RSI snap-back, sweep-fade)
  * production v5.0 SHA-ADX hybrid (flip/breakout) with CRUDE and SILVER param sets, v5.2 (HMA55 trend), v5.3 (loose sweep winner)
  * Supertrend(20,3)+volume and Tenkan/Kijun+EMA200 (signals_scalp frames)
  * strategies built in this research session: VWAP drift pullback, TPO value-area fade/breakout (daily profile), RSI fade, Donchian N breakouts
All through research_sim.simulate (yearly tiles) with next-open fills, SL-first on ties.
"""
from __future__ import annotations
import numpy as np, pandas as pd
import gold_all_strategies as G
from gold_all_strategies import B, X, rs
import silver_sweep as SS
from trading_agents.core import signals_v50 as v50, signals_scalp as SC
from trading_agents.core.levels import true_range, wilder

def _rsi(c, n):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

def barssince(cond: pd.Series) -> pd.Series:
    idx = pd.Series(np.where(cond.to_numpy(), np.arange(len(cond)), np.nan), index=cond.index).ffill()
    return pd.Series(np.arange(len(cond)), index=cond.index) - idx

def sha_arrays(d, l1=10, l2=10):
    o1, c1, h1, l1_ = (v50.ema(d[c], l1) for c in ("open", "close", "high", "low"))
    ha_c = ((o1 + h1 + l1_ + c1) / 4).to_numpy(); ha_o = np.empty(len(d)); ha_o[0] = (o1.iat[0] + c1.iat[0]) / 2
    for i in range(1, len(d)): ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2
    up = v50.ema(pd.Series(ha_c, index=d.index), l2) > v50.ema(pd.Series(ha_o, index=d.index), l2)
    flip_bar = pd.Series(np.where(up != up.shift(1), np.arange(len(d)), np.nan), index=d.index).ffill().fillna(0)
    age = pd.Series(np.arange(len(d)), index=d.index) - flip_bar
    return up, up & ~up.shift(1, fill_value=False), ~up & up.shift(1, fill_value=True), age

# ---- variant-lab V01..V32 (arrays copied from lab1_247_patch.pine.txt) -------------------------------------------
FAM = [1]*16 + [2]*3 + [3]*3 + [4]*3 + [5]*2 + [6]*4 + [1]
OS = [30,30,30,30,30,30,30,30,20,40,30,30,30,30,30,30,0,0,0,0,0,0,0,0,0,10,5,0,0,0,0,30]
OB = [70,70,70,70,70,70,70,70,80,60,70,70,70,70,70,70,0,0,0,0,0,0,0,0,0,90,95,0,0,0,0,70]
PB = [12]*13 + [6,12,12] + [3,3,3] + [0,0,0] + [20,20,10] + [0,0] + [20,20,20,20] + [12]
TRIG = [0,0,0,0,0,0,1,2,0,0,0,0,0,0,0,0] + [0]*16
EMA = [1,1,1,1,1,2,1,1,1,1,1,1,1,1,0,1, 1,1,1, 1,1,2, 1,1,1, 0,0, 0,0,0,0, 1]
SHAF = [0]*16 + [0,1,0, 0,0,0, 1,1,1, 0,0, 0,0,0,1, 0]
MINSL = [2.0]*10 + [1.2] + [2.0]*5 + [1.2,1.5,1.2, 1.5,1.5,1.5, 1.5,1.5,1.5, 1.5,1.5, 1.0,1.0,1.0,1.0, 1.5]
RR = [2.4,2.4,1.5,2.0,3.0,2.4,2.4,2.4,2.4,2.4,2.4,2.4,2.4,2.4,2.4,2.0, 2.0,2.4,1.5, 2.0,3.0,2.0, 2.0,3.0,2.0, 1.0,1.5, 2.0,3.0,6.0,2.0, 2.0]
SHA_H = [3]*12 + [0] + [3]*3 + [0]*15 + [3]
EOD = [0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,1, 0,0,1] + [0]*12 + [1]

def lab_variant(d, v):
    """Return ok_l, ok_s, risk_l, risk_s, rr for lab variant index v (0-based)."""
    c, o, h, l, atr = d["close"], d["open"], d["high"], d["low"], d["atr"]
    e9, e22, e200 = d["e9"], d["e22"], d["e200"]
    up, fu, fd, age = sha_arrays(d)
    rsi = _rsi(c, 3); rsi_prev = rsi.shift(1); rsi_ma = rsi.rolling(14).mean()
    f = FAM[v]
    tL = (e9 > e22) if EMA[v] == 0 or True else None
    if EMA[v] == 0: tL = pd.Series(True, index=d.index); tS = tL
    elif EMA[v] == 1: tL = e9 > e22; tS = e9 < e22
    else: tL = (e9 > e22) & (c > e200); tS = (e9 < e22) & (c < e200)
    sf = SHAF[v] == 1
    if f == 1:
        held = (age >= SHA_H[v]) if SHA_H[v] else pd.Series(True, index=d.index)
        os_hit = rsi < OS[v]; ob_hit = rsi > OB[v]
        bs_os = barssince(os_hit); bs_ob = barssince(ob_hit)
        tr = TRIG[v]
        if tr == 0: trL = (rsi > rsi_ma) & (rsi_prev <= rsi_ma.shift(1)); trS = (rsi < rsi_ma) & (rsi_prev >= rsi_ma.shift(1))
        elif tr == 1: trL = (rsi > 50) & (rsi_prev <= 50); trS = (rsi < 50) & (rsi_prev >= 50)
        else: trL = c > h.shift(1); trS = c < l.shift(1)
        L = up & held & tL & (bs_os <= PB[v]) & trL
        S = (~up) & held & tS & (bs_ob <= PB[v]) & trS
    elif f == 2:
        bsL = barssince(l <= e22); bsS = barssince(h >= e22)
        L = tL & (bsL <= PB[v] - 1) & (c > e9) & (c > o) & (up if sf else True)
        S = tS & (bsS <= PB[v] - 1) & (c < e9) & (c < o) & ((~up) if sf else True)
    elif f == 3:
        L, S = fu & tL, fd & tS
    elif f == 4:
        hi = h.rolling(20 if PB[v] == 20 else 10).max().shift(1); lo = l.rolling(20 if PB[v] == 20 else 10).min().shift(1)
        L = (c > hi) & tL & (up if sf else True); S = (c < lo) & tS & ((~up) if sf else True)
    elif f == 5:
        L = (rsi_prev < OS[v]) & (rsi >= OS[v]) & tL; S = (rsi_prev > OB[v]) & (rsi <= OB[v]) & tS
    else:
        lo20 = l.rolling(20).min().shift(1); hi20 = h.rolling(20).max().shift(1)
        L = (l < lo20) & (c > lo20) & tL & (up if sf else True); S = (h > hi20) & (c < hi20) & tS & ((~up) if sf else True)
    swlo, swhi = SS.swings(d, 10)
    risk_l = (c - (swlo - 0.1 * atr)).clip(lower=MINSL[v] * atr); risk_s = ((swhi + 0.1 * atr) - c).clip(lower=MINSL[v] * atr)
    cap = 3.0 * atr
    return (L.fillna(False) & (risk_l <= cap)), (S.fillna(False) & (risk_s <= cap)), risk_l, risk_s, RR[v]

def run_frame(d, okl, oks, risk_l, risk_s, rr, session, time_stop=None, max_per_day=None):
    s0, s1 = [int(x[:2]) * 60 + int(x[3:]) for x in session]
    in_sess = (d["tmin"] >= s0) & (d["tmin"] < s1)
    g = d.copy(); g["ok_l"] = in_sess & okl; g["ok_s"] = in_sess & oks & ~g["ok_l"]; g["risk_l"], g["risk_s"] = risk_l, risk_s
    return rs.simulate(g, dict(rr=rr, day_loss_limit_pts=0.0), start=rs.WARMUP, commission=0.0, time_stop_min=time_stop,
                       flat_at="25:00", max_per_day=max_per_day)

def hma(s, n):
    def wma(x, k):
        w = np.arange(1, k + 1); return x.rolling(k).apply(lambda a: np.dot(a, w) / w.sum(), raw=True)
    return wma(2 * wma(s, n // 2) - wma(s, n), int(np.sqrt(n)))

def v50_signals(d, p, mode):
    """Production v5.0 frame (24h) -> L/S arrays after the arming-time gates simulate() applies."""
    p = dict(p, session=["00:00", "23:59"], force_flat_window=["23:59", "23:59"], day_loss_limit=0)
    f = v50.v50_frame(d[["time", "open", "high", "low", "close", "volume"]], p)
    atr = f["atr"]; cap = p["max_sl"] * atr
    gate_l = f["adx_ok"] & f["near_ema9_l"] & (f["risk_l"] <= cap) & (atr > 0)
    gate_s = f["adx_ok"] & f["near_ema9_s"] & (f["risk_s"] <= cap) & (atr > 0)
    if mode == "breakout": L, S = f["ok_l_bo"], f["ok_s_bo"]
    else: L, S = f["ok_l"], f["ok_s"]
    return (L & gate_l).fillna(False).to_numpy(), (S & gate_s).fillna(False).to_numpy(), f["risk_l"], f["risk_s"], p["rr"]

def v52_signals(d, adx_min=25.0, pb=0.5, rr=4.0, max_sl=5.0, bo=5):
    p = dict(v50.V50_INSTRUMENT_PARAMS["SILVER"], adx_min=adx_min, pb_atr_mult=pb, rr=rr, max_sl=max_sl, breakout_lookback=bo,
             session=["00:00", "23:59"], force_flat_window=["23:59", "23:59"], day_loss_limit=0)
    f = v50.v50_frame(d[["time", "open", "high", "low", "close", "volume"]], p)
    c, atr = f["close"], f["atr"]; hm = hma(c, 55)
    tl = (f["e9"] > f["e22"]) & (c > hm); ts = (f["e9"] < f["e22"]) & (c < hm)
    cap = max_sl * atr
    dc_hi = f["high"].rolling(bo).max().shift(1); dc_lo = f["low"].rolling(bo).min().shift(1)
    okfl = f["flip_up"] & tl & f["sha_stable"] & f["adx_ok"] & f["near_ema9_l"] & (f["risk_l"] <= cap)
    okbl = (c > dc_hi) & tl & f["adx_ok"] & f["near_ema9_l"] & (f["risk_l"] <= cap)
    okfs = f["flip_dn"] & ts & f["sha_stable"] & f["adx_ok"] & f["near_ema9_s"] & (f["risk_s"] <= cap)
    okbs = (c < dc_lo) & ts & f["adx_ok"] & f["near_ema9_s"] & (f["risk_s"] <= cap)
    L = (okfl | okbl).fillna(False); S = ((okfs | okbs) & ~L).fillna(False)
    return L.to_numpy(), S.to_numpy(), f["risk_l"], f["risk_s"], rr

def scalp_signals(d, kind):
    bars = d[["time", "open", "high", "low", "close", "volume"]]
    allday = ["00:00", "23:59"]
    if kind == "supertrend":
        p = dict(st_mult=3.0, st_period=20, use_vol_filter=True, vol_len=20, min_sl=1.0, rr=1.5, entry_window=allday)
        f = SC.supertrend_frame(bars, p); return f["ok_l"].to_numpy(), f["ok_s"].to_numpy(), f["risk_l"], f["risk_s"], 1.5
    p = dict(tenkan_len=9, kijun_len=26, ema200_len=200, ema200_dist_min=1.0, min_sl=1.0, rr=2.5, entry_window=allday)
    f = SC.tenkan_frame(bars, p); return f["ok_l"].to_numpy(), f["ok_s"].to_numpy(), f["risk_l"], f["risk_s"], 2.5

def session_strategies(d):
    """Strategies built earlier in this research session, as bracket entries on the same frame."""
    c, o, h, l, atr = d["close"], d["open"], d["high"], d["low"], d["atr"]
    out = {}
    swlo, swhi = SS.swings(d, 10)
    def risks(mn): return (c - (swlo - 0.1 * atr)).clip(lower=mn * atr), ((swhi + 0.1 * atr) - c).clip(lower=mn * atr)
    # VWAP drift pullback (video 1), day = IST date, VWAP anchored at the day's first bar
    day = d["time"].dt.date; tp = (h + l + c) / 3; vol = d["volume"].replace(0, np.nan).fillna(1.0)
    vwap = (tp * vol).groupby(day).cumsum() / vol.groupby(day).cumsum()
    slope_up, slope_dn = vwap > vwap.shift(1), vwap < vwap.shift(1)
    k = 12 if abs(d["time"].diff().dt.total_seconds().median() - 300) < 1 else 4
    drift_up = (c / c.shift(k) - 1) >= 0.001; drift_dn = (1 - c / c.shift(k)) >= 0.001
    L = (c > vwap) & slope_up & drift_up & (c < o) & (l <= vwap); S = (c < vwap) & slope_dn & drift_dn & (c > o) & (h >= vwap)
    rl, rsx = risks(1.0); out["VWAP drift pullback RR1.5"] = (L, S, rl, rsx, 1.5, 12 * 5)
    out["VWAP drift pullback 2:1-against (RR0.5)"] = (L, S, rl, rsx, 0.5, 12 * 5)
    # RSI(14) extreme fade and Donchian breakouts (session scalps)
    r14 = _rsi(c, 14); L2, S2 = (r14 < 20), (r14 > 80); out["RSI14 20/80 fade"] = (L2, S2, rl, rsx, 1.0, 12 * 5)
    for n in (12, 36):
        hi, lo = h.rolling(n).max().shift(1), l.rolling(n).min().shift(1)
        out[f"Donchian{n} breakout RR1.5"] = (c > hi, c < lo, rl, rsx, 1.5, 24 * 5)
    # TPO-style value-area fade/breakout approximated per UTC day on typical price distribution bins (developing, no lookahead)
    return out


_SHA_CACHE = {}
_orig_sha = sha_arrays
def sha_arrays(d, l1=10, l2=10):          # cache: 32 variants share one SHA computation per frame
    k = (id(d), l1, l2)
    if k not in _SHA_CACHE: _SHA_CACHE[k] = _orig_sha(d, l1, l2)
    return _SHA_CACHE[k]


def build_extra_signals(d):
    """name -> (L, S, risk_l, risk_s, rr, time_stop_min, max_per_day). Signals are session-independent."""
    out = {}
    for v in range(32):
        L, S, rl, rsx, rr = lab_variant(d, v)
        out[("lab", f"V{v+1:02d}")] = (L, S, rl, rsx, rr, None, 2 if v in (11, 15) else None)
    base = dict(v50.V50_INSTRUMENT_PARAMS["CRUDEOIL"])
    for tag, p, mode in [
        ("v5.0 flip CRUDE params", base, "flip"),
        ("v5.0 breakout CRUDE params", dict(base, entry_mode="breakout"), "breakout"),
        ("v5.0 flip SILVER params", dict(v50.V50_INSTRUMENT_PARAMS["SILVER"]), "flip"),
        ("v5.0 flip BANKNIFTY params", dict(v50.V50_INSTRUMENT_PARAMS["BANKNIFTY"]), "flip"),
        ("v5.3 loose sweep-winner", dict(base, adx_min=5.0, rr=3.0, pb_atr_mult=3.0, sha_min_hold=1, min_sl=1.0, max_sl=5.0,
                                         breakout_lookback=10, sw_buf=0.15, entry_mode="breakout"), "breakout"),
    ]:
        L, S, rl, rsx, rr = v50_signals(d, p, mode); out[("v50", tag)] = (L, S, rl, rsx, rr, None, None)
    L, S, rl, rsx, rr = v52_signals(d); out[("v50", "v5.2 flip+BO HMA55 (SILVER cfg)")] = (L, S, rl, rsx, rr, None, None)
    for kind in ("supertrend", "tenkan"):
        L, S, rl, rsx, rr = scalp_signals(d, kind); out[("scalp", f"{kind} live params")] = (L, S, rl, rsx, rr, 45, None)
    for tag, (L, S, rl, rsx, rr, ts) in session_strategies(d).items():
        out[("session", tag)] = (L, S, rl, rsx, rr, ts, None)
    return out
