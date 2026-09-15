"""Daily levels built from 5m bars.

Dhan's daily endpoint lagged 1-2 sessions in the 2026-09-16 probe, so daily OHLC is
aggregated from the intraday bars of the same series that underlies the options.
"""
import math

import numpy as np
import pandas as pd


def daily_from_intraday(bars):
    if bars.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "bars"])
    df = bars.assign(date=bars["time"].dt.date)
    g = df.groupby("date", sort=True)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "volume": g["volume"].sum(), "bars": g.size()})
    return out.reset_index()


def true_range(high, low, close):
    pc = close.shift(1)
    return pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)


def wilder(series, n):
    """Wilder / RMA smoothing, as Pine's ta.atr uses."""
    return series.ewm(alpha=1 / n, adjust=False).mean()


def pivots(h, l, c):
    p = (h + l + c) / 3
    return dict(P=p, R1=2 * p - l, S1=2 * p - h, R2=p + (h - l), S2=p - (h - l))


def atr_regime(ratio):
    if ratio is None:
        return None
    return "high" if ratio > 1.2 else "low" if ratio < 0.8 else "normal"


def level_summary(bars, as_of, atr_len=14, avg_len=20, rv_len=20):
    """Prior-session levels and volatility regime, using only sessions before `as_of`."""
    daily = daily_from_intraday(bars[bars["time"].dt.date < as_of])
    if len(daily) < 2:
        return dict(available=False, note=f"only {len(daily)} prior session(s) of bars")
    daily["atr"] = wilder(true_range(daily["high"], daily["low"], daily["close"]), atr_len)
    last, prev = daily.iloc[-1], daily.iloc[-2]
    h, l, c = float(last["high"]), float(last["low"]), float(last["close"])
    rng = h - l
    atr = float(last["atr"])
    avg = float(daily["atr"].tail(avg_len).mean())
    ratio = atr / avg if avg else None
    rets = np.log(daily["close"] / daily["close"].shift(1)).dropna().tail(rv_len)
    week = daily.tail(5)
    out = dict(
        available=True,
        sessions_used=len(daily),
        prev_day=dict(date=last["date"], open=float(last["open"]), high=h, low=l, close=c, range=rng,
                      close_position_pct=(c - l) / rng * 100 if rng else None),
        prev_day_change_pts=c - float(prev["close"]),
        prev_day_change_pct=(c / float(prev["close"]) - 1) * 100,
        prev_day_range_vs_atr=rng / atr if atr else None,
        pivots=pivots(h, l, c),
        atr14=atr,
        atr14_avg20=avg,
        atr_ratio=ratio,
        atr_regime=atr_regime(ratio),
        rv20_pct=float(rets.std() * math.sqrt(252) * 100) if len(rets) >= 5 else None,
        five_day_high=float(week["high"].max()),
        five_day_low=float(week["low"].min()),
    )
    if len(daily) < atr_len + avg_len:
        out["note"] = f"only {len(daily)} sessions; ATR14 average over 20 sessions is partly warm-up"
    return out
