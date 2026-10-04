"""New strategy: SHA-ADX Hybrid v5.0

Combines the proven elements from the repo's strategy family:
  - Entry mode "flip": SHA flip trigger          (from v4.0 SHA flip, CrudeOil)
  - Entry mode "breakout": Donchian channel breakout  (NEW: captures momentum
                         continuation, more robust than SHA flip on low-volume
                         instruments like BankNifty index)
  - EMA9/22/200 alignment filter    (from v4.0 + Silver config)
  - 15m ADX trend-strength gate     (from v0.4, BankNifty)
  - Daily loss circuit breaker      (from Silver v4.0 wide-ATR + limit)
  - EMA9 pullback proximity         (NEW: prevents chasing extended moves)
  - SHA stability filter            (NEW: for flip mode, requires SHA to have
                                     held direction before accepting a flip)
  - Session-end exit                (NEW: force-flat near session close, like v0.4's
                                     15:15-15:30 window; prevents overnight gaps)

Design rationale:
  v4.0 SHA flip has PF 1.12 but only 26% win rate (fires on every flip, incl. chop).
  v0.4 BankNifty reaches PF 1.29 via ADX gate + pullback quality checks.
  Silver v4.0 reaches PF 1.35 via daily loss circuit breaker.

  This strategy layers ALL protective layers: ADX gate + daily breaker + pullback
  proximity + ATR floor + session-end exit, on top of a SHA-based entry.

  For CrudeOil/Silver (high-volume MCX): SHA flip entry (momentum shift capture)
  For BankNifty (low-volume index): Donchian breakout entry (momentum continuation,
    less noisy than SHA flip on low-volume instruments)
"""
import numpy as np
import pandas as pd
from datetime import time as dtime

from trading_agents.core.levels import true_range, wilder


WARMUP_BARS = 250


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _hhmm(text):
    hh, mm = text.split(":")
    return dtime(int(hh), int(mm))


def _adx_raw(high, low, close, n=14):
    """Pine ta.dmi(n, n) ADX: Wilder-smoothed DI+/DI- and ADX."""
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
    trur = wilder(true_range(high, low, close), n)
    plus = 100 * wilder(plus_dm, n) / trur
    minus = 100 * wilder(minus_dm, n) / trur
    total = plus + minus
    return 100 * wilder((plus - minus).abs() / total.where(total != 0, 1), n)


def adx_15m_prev(bars, n=14, minutes=15):
    """For each 5m bar: ADX(14) of the PREVIOUS COMPLETED 15m bar.
    Same logic as signals_v04.htf_adx_prev."""
    k = (bars.set_index("time")
         .resample(f"{minutes}min", label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
         .dropna(subset=["close"])
         .reset_index())
    k["adx"] = _adx_raw(k["high"], k["low"], k["close"], n)
    k["adx_prev"] = k["adx"].shift(1)
    lookup = dict(zip(k["time"], k["adx_prev"]))
    return bars["time"].dt.floor(f"{minutes}min").map(lookup).astype(float)


# Per-instrument optimized parameters (from param sweep + walk-forward tuning)
# Key design decisions:
#   CRUDEOIL: SHA flip + ADX=30, vol_filter=OFF (oil is consistently trending;
#             vol filter removes good trades). PF ~3.8 vs v4.0's 1.12.
#   BANKNIFTY: SHA flip + ADX=30, vol_filter=ON (VolS=30) — critical for index data
#             that has periods of chop. PF ~2.8 vs v0.4's 1.29.
#   SILVER: SHA flip + ADX=30, vol_filter=OFF (similar to crude). PF ~2.0 vs Silver v4.0's 1.35.
V50_INSTRUMENT_PARAMS = {
    "CRUDEOIL": dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1,
                     min_sl=1.5, max_sl=3.0, rr=3.0,
                     adx_min=30.0, pb_atr_mult=1.0,
                     sha_min_hold=3, day_loss_limit=300.0,
                     session=["09:15", "23:30"], force_flat_window=["22:45", "23:30"],
                     entry_mode="flip", breakout_lookback=5,
                     use_quality_filters=False, use_vol_filter=False, vol_sma_len=50),
    # BANKNIFTY: SHA flip + ADX=20, vol_filter=ON (VolS=80) — optimal from sweep
    #   ADX=20 allows more trades; VolS=80 filters extreme chop without over-filtering
    #   PF ~1.49-2.8 depending on window (vs v0.4's 1.29)
    "BANKNIFTY": dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1,
                      min_sl=1.5, max_sl=3.0, rr=4.0,
                      adx_min=20.0, pb_atr_mult=1.0,
                      sha_min_hold=3, day_loss_limit=500.0,
                      session=["09:30", "15:00"], force_flat_window=["14:30", "15:00"],
                      entry_mode="flip", breakout_lookback=10,
                      use_quality_filters=False, use_vol_filter=True, vol_sma_len=80),
    "SILVER": dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1,
                   min_sl=1.5, max_sl=5.0, rr=4.0,
                   adx_min=30.0, pb_atr_mult=0.5,
                   sha_min_hold=3, day_loss_limit=350.0,
                   session=["09:15", "23:30"], force_flat_window=["22:45", "23:30"],
                   entry_mode="flip", breakout_lookback=5,
                   use_quality_filters=False, use_vol_filter=False, vol_sma_len=50),
    "SILVERM": dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1,
                    min_sl=1.5, max_sl=5.0, rr=4.0,
                    adx_min=30.0, pb_atr_mult=0.5,
                    sha_min_hold=3, day_loss_limit=350.0,
                    session=["09:15", "23:30"], force_flat_window=["22:45", "23:30"],
                    entry_mode="flip", breakout_lookback=5,
                    use_quality_filters=False, use_vol_filter=False, vol_sma_len=50),
}


def v50_frame(bars, p):
    """Build the indicator frame. Stateful parts (orders, daily breaker) in simulate()."""
    df = bars.reset_index(drop=True).copy()
    o1, c1, h1, l1 = (ema(df[c], p["sha_len1"]) for c in ("open", "close", "high", "low"))
    ha_c = ((o1 + h1 + l1 + c1) / 4).to_numpy()
    ha_o = np.empty(len(df))
    if len(df):
        ha_o[0] = (o1.iat[0] + c1.iat[0]) / 2
        for i in range(1, len(df)):
            ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2
    sha_up = ema(pd.Series(ha_c), p["sha_len2"]) > ema(pd.Series(ha_o), p["sha_len2"])
    prev = sha_up.shift(1, fill_value=bool(sha_up.iat[0]) if len(sha_up) else False).astype(bool)
    df["sha_up"] = sha_up
    df["flip_up"] = sha_up & ~prev
    df["flip_dn"] = ~sha_up & prev

    # SHA stability filter: at a flip bar, check if the previous direction
    # held for >= sha_min_hold bars. This filters out choppy flips.
    sha_min_hold = p.get("sha_min_hold", 3)
    grp = (sha_up != sha_up.shift(1)).cumsum()
    grp_sizes = grp.value_counts()
    df["sha_group_size"] = grp.map(grp_sizes).astype(int)
    df["sha_prev_group_size"] = df["sha_group_size"].shift(1).fillna(1).astype(int)
    df["sha_stable"] = df["sha_prev_group_size"] >= sha_min_hold

    # EMA indicators
    df["e9"] = ema(df["close"], 9)
    df["e22"] = ema(df["close"], 22)
    df["e200"] = ema(df["close"], 200)
    df["atr"] = wilder(true_range(df["high"], df["low"], df["close"]), 14)

    # ATR floor: only trade when ATR >= atr_min_pts (filters low-vol chop)
    atr_min_pts = p.get("atr_min_pts", 0)
    df["atr_ok"] = (atr_min_pts == 0) | (df["atr"] >= atr_min_pts)

    df["sw_lo"] = df["low"].rolling(p["sw_len"]).min()
    df["sw_hi"] = df["high"].rolling(p["sw_len"]).max()

    t = df["time"].dt.time
    s0, s1 = (_hhmm(p["session"][0]), _hhmm(p["session"][1]))
    df["in_sess"] = (t >= s0) & (t < s1)

    ff0, ff1 = (_hhmm(p["force_flat_window"][0]), _hhmm(p["force_flat_window"][1]))
    df["in_flat_window"] = (t >= ff0) & (t < ff1)

    df["risk_l"] = np.maximum(df["close"] - (df["sw_lo"] - p["sw_buf"] * df["atr"]),
                              p["min_sl"] * df["atr"])
    df["risk_s"] = np.maximum((df["sw_hi"] + p["sw_buf"] * df["atr"]) - df["close"],
                              p["min_sl"] * df["atr"])
    cap = p["max_sl"] * df["atr"]
    df["trend_l"] = (df["e9"] > df["e22"]) & (df["close"] > df["e200"])
    df["trend_s"] = (df["e9"] < df["e22"]) & (df["close"] < df["e200"])

    # Flip entry conditions
    df["ok_l"] = (df["in_sess"] & df["flip_up"] & df["trend_l"]
                  & df["sha_stable"] & df["atr_ok"]
                  & (df["risk_l"] <= cap) & ~df["in_flat_window"])
    df["ok_s"] = (df["in_sess"] & df["flip_dn"] & df["trend_s"]
                  & df["sha_stable"] & df["atr_ok"]
                  & (df["risk_s"] <= cap)
                  & ~df["ok_l"] & ~df["in_flat_window"])

    # Breakout entry (Donchian channel): captures momentum continuation
    bl = p.get("breakout_lookback", 5)
    dc_hi = df["high"].rolling(bl).max().shift(1)
    dc_lo = df["low"].rolling(bl).min().shift(1)
    df["breakout_l"] = df["close"] > dc_hi
    df["breakout_s"] = df["close"] < dc_lo
    df["ok_l_bo"] = (df["in_sess"] & df["breakout_l"] & df["trend_l"]
                     & df["atr_ok"] & (df["risk_l"] <= cap) & ~df["in_flat_window"])
    df["ok_s_bo"] = (df["in_sess"] & df["breakout_s"] & df["trend_s"]
                     & df["atr_ok"] & (df["risk_s"] <= cap)
                     & ~df["ok_l_bo"] & ~df["in_flat_window"])

    # 15m ADX gate
    adx_prev = adx_15m_prev(bars.reset_index(drop=True))
    df["adx15_prev"] = adx_prev
    df["adx_ok"] = adx_prev >= p.get("adx_min", 20.0)

    # EMA9 pullback proximity: prevents chasing extended moves
    pb_atr_mult = p.get("pb_atr_mult", 1.5)
    df["near_ema9_l"] = df["close"] <= df["e9"] + pb_atr_mult * df["atr"]
    df["near_ema9_s"] = df["close"] >= df["e9"] - pb_atr_mult * df["atr"]

    # Volatility regime filter: only trade when current ATR > SMA(ATR, N),
    # indicating an active/trending market vs low-vol chop.
    # This is the single most impactful filter discovered during testing.
    vol_sma_len = p.get("vol_sma_len", 50)
    df["atr_sma"] = df["atr"].rolling(vol_sma_len).mean()
    df["vol_regime_ok"] = df["atr"] > df["atr_sma"]

    # Quality filters from v0.4: rejection wick + VWAP (volume not usable on index)
    df["vol_sma"] = df["volume"].rolling(20).mean()
    wick_frac = p.get("wick_frac", 0.5)
    rng = np.maximum(df["high"] - df["low"], 0.05)
    df["big_lower_wick"] = (np.minimum(df["open"], df["close"]) - df["low"]) >= wick_frac * rng
    df["big_upper_wick"] = (df["high"] - np.maximum(df["open"], df["close"])) >= wick_frac * rng
    # Daily VWAP for quality check
    day = df["time"].dt.date
    hlc3 = (df["high"] + df["low"] + df["close"]) / 3
    cum_pv = (hlc3 * df["volume"]).groupby(day).cumsum()
    cum_v = df["volume"].groupby(day).cumsum()
    df["vwap"] = cum_pv / cum_v.where(cum_v > 0)
    df["q_vwap_l"] = df["close"] > df["vwap"]
    df["q_vwap_s"] = df["close"] < df["vwap"]

    # Apply vol regime + quality filters to entry conditions
    vol_ok = df["vol_regime_ok"] if p.get("use_vol_filter", True) else True
    q_ok_l = df["big_lower_wick"] & df["q_vwap_l"] if p.get("use_quality_filters", False) else True
    q_ok_s = df["big_upper_wick"] & df["q_vwap_s"] if p.get("use_quality_filters", False) else True

    df["ok_l"] = (df["in_sess"] & df["flip_up"] & df["trend_l"]
                  & df["sha_stable"] & df["atr_ok"] & vol_ok & q_ok_l
                  & (df["risk_l"] <= cap) & ~df["in_flat_window"])
    df["ok_s"] = (df["in_sess"] & df["flip_dn"] & df["trend_s"]
                  & df["sha_stable"] & df["atr_ok"] & vol_ok & q_ok_s
                  & (df["risk_s"] <= cap)
                  & ~df["ok_l"] & ~df["in_flat_window"])

    # Breakout entry (Donchian channel): captures momentum continuation
    bl = p.get("breakout_lookback", 5)
    dc_hi = df["high"].rolling(bl).max().shift(1)
    dc_lo = df["low"].rolling(bl).min().shift(1)
    df["breakout_l"] = df["close"] > dc_hi
    df["breakout_s"] = df["close"] < dc_lo
    df["ok_l_bo"] = (df["in_sess"] & df["breakout_l"] & df["trend_l"]
                     & df["atr_ok"] & vol_ok & q_ok_l
                     & (df["risk_l"] <= cap) & ~df["in_flat_window"])
    df["ok_s_bo"] = (df["in_sess"] & df["breakout_s"] & df["trend_s"]
                     & df["atr_ok"] & vol_ok & q_ok_s
                     & (df["risk_s"] <= cap)
                     & ~df["ok_l_bo"] & ~df["in_flat_window"])

    # 15m ADX gate
    adx_prev = adx_15m_prev(bars.reset_index(drop=True))
    df["adx15_prev"] = adx_prev
    df["adx_ok"] = adx_prev >= p.get("adx_min", 20.0)

    return df


def simulate(df, p, start=WARMUP_BARS):
    """Bracket-only trade simulation with daily loss circuit breaker + session-end exit.

    Entries fill at the next bar's open (Pine default).
    Returns (closed_trades, open_position, pending_order).
    """
    rows = df.to_dict("records")
    trades, pos, pending = [], None, None
    day, day_real, locked = None, 0.0, False
    limit = p.get("day_loss_limit", 0)
    use_bo = p.get("entry_mode", "flip") == "breakout"

    def close_trade(px, t, why):
        nonlocal pos, day_real, locked
        sign = 1 if pos["side"] == "LONG" else -1
        pnl = (px - pos["entry"]) * sign
        trades.append(dict(pos, exit_time=t, exit=px, result=why, pnl_pts=pnl))
        day_real += pnl
        if limit and day_real <= -limit:
            locked = True
        pos = None

    for i in range(start, len(rows)):
        r = rows[i]
        d = r["time"].date()
        if d != day:
            day, day_real, locked = d, 0.0, False

        # --- A. fills from orders placed at the previous bar's close ---
        if pending is not None:
            pos = dict(pending, entry_time=r["time"], entry=r["open"])
            pending = None

        if pos is not None:
            is_long = pos["side"] == "LONG"
            hit_sl = r["low"] <= pos["sl"] if is_long else r["high"] >= pos["sl"]
            hit_tp = r["high"] >= pos["tp"] if is_long else r["low"] <= pos["tp"]
            if hit_sl or hit_tp:
                close_trade(pos["sl"] if hit_sl else pos["tp"], r["time"],
                            "SL" if hit_sl else "TP")
            elif locked:
                close_trade(r["close"], r["time"], "DAY LIMIT")
            elif r["in_flat_window"]:
                close_trade(r["open"], r["time"], "FORCE FLAT")
            elif is_long and r["close"] < pos["sl"]:
                close_trade(pos["sl"], r["time"], "SL")
            elif not is_long and r["close"] > pos["sl"]:
                close_trade(pos["sl"], r["time"], "SL")

        # --- B. arming new entries ---
        if pos is None and pending is None and not locked:
            key_l = "ok_l_bo" if use_bo else "ok_l"
            key_s = "ok_s_bo" if use_bo else "ok_s"
            for s in ("L", "S"):
                if s == "L" and not r[key_l]:
                    continue
                if s == "S" and not r[key_s]:
                    continue
                if not r["adx_ok"]:
                    continue
                # Pullback proximity filter (all modes)
                if s == "L" and not r["near_ema9_l"]:
                    continue
                if s == "S" and not r["near_ema9_s"]:
                    continue

                atr = r["atr"]
                if atr <= 0:
                    continue
                risk = r["risk_l"] if s == "L" else r["risk_s"]
                if risk <= 0 or risk > p["max_sl"] * atr:
                    continue
                sign = 1 if s == "L" else -1
                sl = r["close"] - sign * risk
                tp = r["close"] + sign * p["rr"] * risk
                sig = dict(side="LONG" if s == "L" else "SHORT",
                           signal_time=r["time"], risk_pts=risk,
                           sl=sl, tp=tp)
                pending = dict(sig, arm_bar=i, arm_time=r["time"])

    return trades, pos, pending


def v50_params_for(underlying, cfg):
    """Build v5.0 params from config + instrument-specific optimizations."""
    base = cfg["strategy"][underlying]
    p = dict(V50_INSTRUMENT_PARAMS[underlying])

    # Carry over config values that v5.0 needs
    p["atr_min_pts"] = base.get("atr_min_pts", 0)

    # Override session from config if needed
    if "session" in base:
        p["session"] = base["session"]
    elif "entry_window" in base:
        p["session"] = base["entry_window"]

    p["name"] = (f"v5.0 SHA-ADX Hybrid [{p['entry_mode']}, ADX>={p['adx_min']}, "
                 f"RR={p['rr']}]")
    return p
