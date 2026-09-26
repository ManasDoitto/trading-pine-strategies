"""Large randomized parameter search for the silver v5.0 family on 5m.
Pre-registration: pre_registration_silver_sweep_2026_09_26.md

Fast path: the expensive parts of v50_frame (the haO recursion, the 15m ADX resample, EMAs/ATR) depend only on
(sha_len1, sha_len2) / (sw_len) / the bars, so they are cached and every other parameter is derived vectorized.
validate_fast() asserts this reproduces trading_agents.core.signals_v50.v50_frame exactly before any sweeping.
"""
import sys, itertools, random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
from trading_agents.core import signals_v50 as v50
from trading_agents.core.levels import true_range, wilder

T0 = pd.Timestamp("2024-03-25")
_sha_cache, _sw_cache = {}, {}


def base(bars_name):
    df = rs.load(bars_name)
    d = df.reset_index(drop=True).copy()
    d["e9"] = v50.ema(d["close"], 9)
    d["e22"] = v50.ema(d["close"], 22)
    d["e200"] = v50.ema(d["close"], 200)
    d["atr"] = wilder(true_range(d["high"], d["low"], d["close"]), 14)
    d["adx15_prev"] = v50.adx_15m_prev(df.reset_index(drop=True))
    d["tmin"] = d["time"].dt.hour * 60 + d["time"].dt.minute
    return d


def sha(d, l1, l2, min_hold):
    key = (id(d), l1, l2)
    if key not in _sha_cache:
        o1, c1, h1, l1e = (v50.ema(d[c], l1) for c in ("open", "close", "high", "low"))
        ha_c = ((o1 + h1 + l1e + c1) / 4).to_numpy()
        ha_o = np.empty(len(d))
        ha_o[0] = (o1.iat[0] + c1.iat[0]) / 2
        for i in range(1, len(d)):
            ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2
        up = v50.ema(pd.Series(ha_c), l2) > v50.ema(pd.Series(ha_o), l2)
        prev = up.shift(1, fill_value=bool(up.iat[0])).astype(bool)
        grp = (up != up.shift(1)).cumsum()
        gs = grp.map(grp.value_counts())
        _sha_cache[key] = (up, up & ~prev, ~up & prev, gs.shift(1).fillna(1).astype(int))
    up, fu, fd, prev_gs = _sha_cache[key]
    return up, fu, fd, (prev_gs >= min_hold)


def swings(d, n):
    key = (id(d), n)
    if key not in _sw_cache:
        _sw_cache[key] = (d["low"].rolling(n).min(), d["high"].rolling(n).max())
    return _sw_cache[key]


def frame(d, p):
    f = d.copy()
    _, fu, fd, stable = sha(d, p["sha_len1"], p["sha_len2"], p["sha_min_hold"])
    f["flip_up"], f["flip_dn"], f["sha_stable"] = fu, fd, stable
    lo, hi = swings(d, p["sw_len"])
    f["sw_lo"], f["sw_hi"] = lo, hi
    atr = f["atr"]
    f["risk_l"] = np.maximum(f["close"] - (lo - p["sw_buf"] * atr), p["min_sl"] * atr)
    f["risk_s"] = np.maximum((hi + p["sw_buf"] * atr) - f["close"], p["min_sl"] * atr)
    s0, s1 = [int(x[:2]) * 60 + int(x[3:]) for x in p["session"]]
    ff0, ff1 = [int(x[:2]) * 60 + int(x[3:]) for x in p["force_flat_window"]]
    f["in_sess"] = (f["tmin"] >= s0) & (f["tmin"] < s1)
    f["in_flat_window"] = (f["tmin"] >= ff0) & (f["tmin"] < ff1)
    f["atr_ok"] = True if p["atr_min_pts"] == 0 else (atr >= p["atr_min_pts"])
    f["adx_ok"] = f["adx15_prev"] >= p["adx_min"] if p["adx_min"] > 0 else True
    f["near_ema9_l"] = f["close"] <= f["e9"] + p["pb_atr_mult"] * atr
    f["near_ema9_s"] = f["close"] >= f["e9"] - p["pb_atr_mult"] * atr
    vol = (atr > atr.rolling(p["vol_sma_len"]).mean()) if p["use_vol_filter"] else True
    cap = p["max_sl"] * atr
    tl = (f["e9"] > f["e22"]) & (f["close"] > f["e200"])
    ts = (f["e9"] < f["e22"]) & (f["close"] < f["e200"])
    g = f["in_sess"] & f["sha_stable"] & f["atr_ok"] & vol & f["adx_ok"] & ~f["in_flat_window"]
    f["ok_l"] = g & fu & tl & (f["risk_l"] <= cap) & f["near_ema9_l"]
    f["ok_s"] = g & fd & ts & (f["risk_s"] <= cap) & f["near_ema9_s"] & ~f["ok_l"]
    return f


def validate_fast(bars_name="MCX_SILVER1"):
    """Assert the fast frame reproduces v50_frame's entry signals exactly on the shipped config."""
    p = dict(v50.V50_INSTRUMENT_PARAMS["SILVER"]); p["atr_min_pts"] = 0
    ref = v50.v50_frame(rs.load(bars_name), p)
    cap = p["max_sl"] * ref["atr"]
    tl = (ref["e9"] > ref["e22"]) & (ref["close"] > ref["e200"])
    ts = (ref["e9"] < ref["e22"]) & (ref["close"] < ref["e200"])
    g = ref["in_sess"] & ref["sha_stable"] & ref["atr_ok"] & ref["adx_ok"] & ~ref["in_flat_window"]
    rl = g & ref["flip_up"] & tl & (ref["risk_l"] <= cap) & ref["near_ema9_l"]
    rsx = g & ref["flip_dn"] & ts & (ref["risk_s"] <= cap) & ref["near_ema9_s"] & ~rl
    f = frame(base(bars_name), p)
    ok = bool((f["ok_l"] == rl).all() and (f["ok_s"] == rsx).all())
    print(f"fast frame == v50_frame on shipped config: {ok}  (signals: {int(rl.sum())}L / {int(rsx.sum())}S)")
    assert ok
    return ok


if __name__ == "__main__":
    validate_fast()
