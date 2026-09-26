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




# ============================ SWEEP DRIVER (pre_registration_silver_sweep_2026_09_26.md) ============================
# User target 2026-09-26: >= 40 trades/month COMBINED across the three scripts over 30 months = >= 1200 trades.
# Enforced at portfolio level (see portfolio selection), not per instrument, because BankNifty cannot reach
# 20/mo profitably on its own (measured: 20.7/mo only at PF 0.944).
MIN_TRADES = 90                      # per-config floor, 3/mo; the 40/mo target is applied to the chosen triple
COMBINED_TRADES_TARGET = 1200
INSTRUMENTS = {
    "SILVER":    dict(bars="MCX_SILVER1",   key="SILVER"),
    "CRUDEOIL":  dict(bars="MCX_CRUDEOIL1", key="CRUDEOIL"),
    "BANKNIFTY": dict(bars="NSE_BANKNIFTY1", key="BANKNIFTY"),
}
SPACE = dict(
    sha_len1=[5, 8, 10, 15], sha_len2=[5, 8, 10, 15], sha_min_hold=[1, 2, 3],
    sw_len=[5, 8, 10, 15], sw_buf=[0.0, 0.1, 0.25],
    min_sl=[1.0, 1.5, 2.0, 2.5, 3.0], max_sl=[3.0, 4.0, 5.0, 6.0, 8.0],
    rr=[1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0],
    adx_min=[0, 12, 15, 18, 20, 25],
    pb_atr_mult=[0.5, 1.0, 1.5, 2.0, 3.0, 99],
    atr_min_pts=[0, 20],
    use_vol_filter=[True, False], vol_sma_len=[30, 50, 80],
    day_loss_limit=[0, 350, 700, 1500],
    sess_id=[0, 1, 2],
)
WINDOWS = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in (
    ("2024-03-25", "2024-08-25"), ("2024-08-25", "2025-01-25"), ("2025-01-25", "2025-06-25"),
    ("2025-06-25", "2025-11-25"), ("2025-11-25", "2026-04-25"), ("2026-04-25", "2026-09-25"))]
SESSIONS_MCX = {0: (["09:15", "23:30"], ["22:45", "23:30"]),
                1: (["09:15", "23:30"], ["23:25", "23:30"]),
                2: (["17:00", "23:30"], ["23:25", "23:30"])}
SESSIONS_NSE = {0: (["09:30", "15:00"], ["14:30", "15:00"]),
                1: (["09:30", "15:00"], ["15:00", "15:30"]),
                2: (["09:15", "15:00"], ["15:15", "15:30"])}
SESSIONS = SESSIONS_MCX


def draw(rng, sessions=None):
    while True:
        p = {k: rng.choice(v) for k, v in SPACE.items()}
        if p["max_sl"] > p["min_sl"]:
            break
    p["session"], p["force_flat_window"] = (sessions or SESSIONS)[p["sess_id"]]
    return p


def evaluate(d, p, s0_cache):
    """Per-config stats on FIXED CALENDAR windows, identical for every config (see WINDOWS).
    Trade-count splits were rejected: they put the boundary at a different DATE for every config,
    so configs were not being compared over the same market."""
    f = frame(d, p)
    key = (p["session"][0],)
    if key not in s0_cache:
        s0_cache[key] = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    tr = rs.simulate(f, dict(p, day_loss_limit_pts=p["day_loss_limit"]),
                     start=s0_cache[key], flat_at=p["force_flat_window"][0], commission=0.0)
    if len(tr) < 10:
        return None
    t = pd.DataFrame(tr)
    t["exit_time"] = pd.to_datetime(t["exit_time"])
    out = dict({k: p[k] for k in SPACE})
    F = rs.stats(tr)
    out.update(n=F["n"], pf=F["pf"], net=F["net"], max_dd=F["max_dd"], win=F["win_pct"],
               pos_m=F["pos_months_pct"], best_m=F["best_month_share"])
    for i, (a, b) in enumerate(WINDOWS, 1):
        w = t[(t.exit_time >= a) & (t.exit_time < b)]
        s = rs.stats(w.to_dict("records")) if len(w) else {}
        out[f"w{i}_n"] = s.get("n", 0)
        out[f"w{i}_pf"] = s.get("pf")
        out[f"w{i}_net"] = s.get("net", 0.0)
    return out


def sweep(inst="SILVER", n_draws=1000, seed=20260926, out=None):
    """Randomized search for one instrument. Per-config stats on the six fixed calendar windows."""
    validate_fast()
    meta = INSTRUMENTS[inst]
    sessions = SESSIONS_NSE if inst == "BANKNIFTY" else SESSIONS_MCX
    from trading_agents.core.config import load_config
    floor = load_config()["strategy"].get(meta["key"], {}).get("atr_min_pts", 0)
    rng = random.Random(seed)
    d = base(meta["bars"])
    s0_cache, rows = {}, []
    for i in range(n_draws):
        p = draw(rng, sessions)
        if p["atr_min_pts"] == 20 and floor:
            p["atr_min_pts"] = floor
        r = evaluate(d, p, s0_cache)
        if r:
            r["inst"] = inst
            rows.append(r)
        if (i + 1) % 200 == 0:
            print(f"  [{inst}] {i+1}/{n_draws} draws, {len(rows)} usable", flush=True)
    R = pd.DataFrame(rows)
    out = out or f"sweep_{inst}.csv"
    R.to_csv(ROOT / "research_data" / out, index=False)
    print(f"DONE {inst}: {len(R)} configs, {int((R.n>=MIN_TRADES).sum())} with >=90 trades "
          f"-> research_data/{out}", flush=True)
    return R


def sweep_all(n_draws=1000):
    for inst in ("SILVER", "CRUDEOIL", "BANKNIFTY"):
        sweep(inst, n_draws=n_draws)


if __name__ == "__main__":
    if "--sweep" in sys.argv:
        sweep_all()
    else:
        validate_fast()
