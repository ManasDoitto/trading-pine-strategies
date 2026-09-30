"""Two scalp engines added 2026-09-28, both dashboard best-picks:

- Supertrend(20,3) + above-average volume (BankNifty). Needs volume, so it runs on the
  front-month FUTURE (like v0.4), not the index.
- Tenkan(9)/Kijun(26) + EMA200 (Nifty). Volume-free, runs directly on the index.

They share the same exit mechanics, unlike v4.0 (signals.py) and v0.4 (signals_v04.py):
a fixed R:R bracket, next-bar-open fill (Pine default) for both entries and decision-based
exits, a minutes time-stop, and a same-day force-flat window. No daily loss limit (neither
Pine source has one).
"""
from datetime import time as dtime

import numpy as np
import pandas as pd

from .levels import true_range, wilder

WARMUP_BARS = 400          # matches strategy_audit_2026_09/research_sim.py's WARMUP (the validation harness)


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _t(hhmm):
    h, m = hhmm.split(":")
    return dtime(int(h), int(m))


def _supertrend(high, low, close, mult, period):
    """Standard Supertrend recurrence. Returns (line, uptrend_bool)."""
    atr = wilder(true_range(high, low, close), period)
    hl2 = (high + low) / 2
    basic_upper = (hl2 + mult * atr).to_numpy()
    basic_lower = (hl2 - mult * atr).to_numpy()
    c = close.to_numpy()
    n = len(c)
    final_upper = np.empty(n)
    final_lower = np.empty(n)
    up = np.empty(n, dtype=bool)
    line = np.empty(n)
    for i in range(n):
        if i == 0:
            final_upper[i], final_lower[i], up[i] = basic_upper[i], basic_lower[i], True
            line[i] = final_lower[i]
            continue
        final_upper[i] = (min(basic_upper[i], final_upper[i - 1]) if c[i - 1] <= final_upper[i - 1]
                          else basic_upper[i])
        final_lower[i] = (max(basic_lower[i], final_lower[i - 1]) if c[i - 1] >= final_lower[i - 1]
                          else basic_lower[i])
        if up[i - 1] and c[i] < final_lower[i]:
            up[i] = False
        elif (not up[i - 1]) and c[i] > final_upper[i]:
            up[i] = True
        else:
            up[i] = up[i - 1]
        line[i] = final_lower[i] if up[i] else final_upper[i]
    idx = close.index
    return pd.Series(line, index=idx), pd.Series(up, index=idx)


def supertrend_frame(bars, p):
    df = bars.reset_index(drop=True).copy()
    st, up = _supertrend(df["high"], df["low"], df["close"], p["st_mult"], p["st_period"])
    prev_up = up.shift(1, fill_value=bool(up.iat[0]) if len(up) else True).astype(bool)
    df["supertrend"], df["st_up"] = st, up
    df["flip_up"], df["flip_dn"] = up & ~prev_up, ~up & prev_up
    df["atr"] = wilder(true_range(df["high"], df["low"], df["close"]), 14)
    df["sw_lo"] = df["low"].rolling(10).min()
    df["sw_hi"] = df["high"].rolling(10).max()
    df["vol_sma"] = df["volume"].rolling(p.get("vol_len", 20)).mean()
    vol_ok = (not p.get("use_vol_filter", True)) | (df["volume"] > df["vol_sma"])
    t = df["time"].dt.time
    s0, s1 = (_t(x) for x in p["entry_window"])
    df["in_sess"] = (t >= s0) & (t < s1)
    df["risk_l"] = np.maximum(df["close"] - (df["sw_lo"] - 0.1 * df["atr"]), p["min_sl"] * df["atr"])
    df["risk_s"] = np.maximum((df["sw_hi"] + 0.1 * df["atr"]) - df["close"], p["min_sl"] * df["atr"])
    df["ok_l"] = df["in_sess"] & df["flip_up"] & vol_ok
    df["ok_s"] = df["in_sess"] & df["flip_dn"] & vol_ok & ~df["ok_l"]
    return df


def tenkan_frame(bars, p):
    df = bars.reset_index(drop=True).copy()
    tenkan = (df["high"].rolling(p["tenkan_len"]).max() + df["low"].rolling(p["tenkan_len"]).min()) / 2
    kijun = (df["high"].rolling(p["kijun_len"]).max() + df["low"].rolling(p["kijun_len"]).min()) / 2
    e200 = ema(df["close"], p["ema200_len"])
    df["tenkan"], df["kijun"], df["e200"] = tenkan, kijun, e200
    cross_up = (tenkan > kijun) & (tenkan.shift(1) <= kijun.shift(1))
    cross_dn = (tenkan < kijun) & (tenkan.shift(1) >= kijun.shift(1))
    df["atr"] = wilder(true_range(df["high"], df["low"], df["close"]), 14)
    df["sw_lo"] = df["low"].rolling(10).min()
    df["sw_hi"] = df["high"].rolling(10).max()
    t = df["time"].dt.time
    s0, s1 = (_t(x) for x in p["entry_window"])
    df["in_sess"] = (t >= s0) & (t < s1)
    df["risk_l"] = np.maximum(df["close"] - (df["sw_lo"] - 0.1 * df["atr"]), p["min_sl"] * df["atr"])
    df["risk_s"] = np.maximum((df["sw_hi"] + 0.1 * df["atr"]) - df["close"], p["min_sl"] * df["atr"])
    # ema200_dist_min (Nifty, 2026-09-29): require price to be genuinely clear of EMA200, not just
    # barely crossed - a real trend-strength gate, not a backward-looking hour/day filter. Holdout-
    # validated across a 70/30 split: 11% fewer trades, PF 1.152->1.175, holdout net +2,392->+2,731,
    # 10/10-years record preserved. ~20 stricter alternatives tested and rejected (ADX, cross-gap,
    # RSI bands, confirmation delays, longer Tenkan/Kijun periods, EMA200 slope) - none held up
    # better on holdout. None/0 -> no-op, identical to the original filter.
    ema_gate = (df["close"] - e200).abs() >= p.get("ema200_dist_min", 0) * df["atr"]
    df["ok_l"] = df["in_sess"] & cross_up & (df["close"] > e200) & ema_gate
    df["ok_s"] = df["in_sess"] & cross_dn & (df["close"] < e200) & ema_gate & ~df["ok_l"]
    return df


def simulate_scalp(df, p, start=WARMUP_BARS, next_open=True):
    """Bracket entries (next-bar-open fill) with a fixed R:R target/stop, a minutes time-stop, and a
    same-day force-flat window. Matches strategy_audit_2026_09/research_sim.py's validated convention
    (the harness these strategies were picked on): the time-stop/flat-window is a same-bar exit at
    that bar's own open, once enough time has passed since the fill - NOT delayed to the next bar
    like a signal-based exit, since here the trigger is just the clock, already known at the bar's
    own open. (An opposite-signal reversal exit, if this engine ever needs one, is the one thing that
    DOES need the next-bar-open delay - see signals.py's reversal_exit - because it can only be known
    once the bar closes.)"""
    rows = df.to_dict("records")
    trades, pos, pending = [], None, None
    time_stop_bars = int(round(p["time_stop_min"] / 5)) if p.get("time_stop_min") else None
    flat0, flat1 = (_t(x) for x in p["flat_window"]) if p.get("flat_window") else (None, None)

    def close(px, t, why):
        nonlocal pos
        sign = 1 if pos["side"] == "LONG" else -1
        pnl = (px - pos["entry"]) * sign
        trades.append(dict(pos, exit_time=t, exit=px, result=why, pnl_pts=pnl))
        pos = None

    for i in range(start, len(rows)):
        r = rows[i]
        in_flat = flat0 is not None and flat0 <= r["time"].time() < flat1
        if pending is not None:
            if in_flat:
                pending = None                                     # would fill inside the flat window: skip
            else:
                pos = dict(pending, entry_time=r["time"], entry=r["open"])
                pending = None
        if pos is not None:
            is_long = pos["side"] == "LONG"
            just_filled = pos["entry_time"] == r["time"]
            hit_time = (not just_filled and time_stop_bars is not None
                       and (r["time"] - pos["entry_time"]).total_seconds() / 300 >= time_stop_bars)
            if in_flat and not just_filled:
                close(r["open"], r["time"], "FLAT")
            elif hit_time:
                close(r["open"], r["time"], "TIME")
            else:
                hit_sl = r["low"] <= pos["sl"] if is_long else r["high"] >= pos["sl"]
                hit_tp = r["high"] >= pos["tp"] if is_long else r["low"] <= pos["tp"]
                if hit_sl or hit_tp:
                    close(pos["sl"] if hit_sl else pos["tp"], r["time"], "SL" if hit_sl else "TP")
        if pos is None and pending is None and not in_flat and (r["ok_l"] or r["ok_s"]):
            side = "LONG" if r["ok_l"] else "SHORT"
            risk = r["risk_l"] if side == "LONG" else r["risk_s"]
            sign = 1 if side == "LONG" else -1
            sig = dict(side=side, signal_time=r["time"], risk_pts=risk,
                       sl=r["close"] - sign * risk, tp=r["close"] + sign * p["rr"] * risk)
            if next_open:
                pending = sig
            else:
                pos = dict(sig, entry_time=r["time"], entry=r["close"])
    return trades, pos, pending


def _trade_view(t, last_close=None):
    v = {k: t.get(k) for k in ("side", "signal_time", "entry_time", "entry", "sl", "tp", "risk_pts",
                               "exit_time", "exit", "result", "pnl_pts")}
    if last_close is not None and t.get("exit") is None:
        v["open_pts"] = (last_close - t["entry"]) * (1 if t["side"] == "LONG" else -1)
    return {k: v[k] for k in v if v[k] is not None}


def _scalp_state(frame_fn, bars, p, engine_name):
    if len(bars) < WARMUP_BARS + 50:
        return dict(modelled=True, available=False, name=p["name"], note=f"only {len(bars)} 5m bars of history")
    df = frame_fn(bars, p)
    trades, pos, pending = simulate_scalp(df, p)
    last = df.iloc[-1]
    last_day = last["time"].date()
    days = sorted({t["entry_time"].date() for t in trades})[-5:]
    recent = [t for t in trades if t["entry_time"].date() in days]
    day_trades = [t for t in trades if t["entry_time"].date() == last_day]
    return dict(
        modelled=True, available=True, approximate=True, engine=engine_name, name=p["name"], rr=p["rr"],
        last_bar=last["time"], close=float(last["close"]),
        position=_trade_view(pos, float(last["close"])) if pos else None,
        pending_entry=_trade_view(pending) if pending else None,
        last_trade=_trade_view(trades[-1]) if trades else None,
        last_session=dict(date=last_day, trades=len(day_trades), net_pts=sum(t["pnl_pts"] for t in day_trades)),
        recent_5_sessions=dict(trades=len(recent), wins=sum(t["pnl_pts"] > 0 for t in recent),
                               net_pts=sum(t["pnl_pts"] for t in recent)),
        sim_window=dict(start=df["time"].iat[WARMUP_BARS], end=last["time"], trades=len(trades)),
    )


def supertrend_state(bars, p):
    return _scalp_state(supertrend_frame, bars, p, "supertrend")


def tenkan_state(bars, p):
    return _scalp_state(tenkan_frame, bars, p, "tenkan_kijun")
