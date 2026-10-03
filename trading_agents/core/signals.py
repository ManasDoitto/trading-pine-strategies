"""Python port of the v4.0 SHA-flip strategy.

Source: working_strategies/CrudeOil/1_*.pine.txt lines 24-66 (Silver/1 adds a fixed daily
loss limit). Exits are the fixed stop/limit bracket only, as in the Pine; there is no
session-end exit.

Approximate vs TradingView: Pine seeds EMAs with an SMA, and Dhan's bars for the specific
futures contract can differ from TradingView's continuous contract. A flip can occasionally
land one bar apart, and the simulated position is indicative only.
"""
from datetime import time as dtime

import numpy as np
import pandas as pd

from .levels import true_range, wilder

WARMUP_BARS = 250


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _t(hhmm):
    h, m = hhmm.split(":")
    return dtime(int(h), int(m))


def v40_frame(bars, p):
    df = bars.reset_index(drop=True).copy()
    o1, c1, h1, l1 = (ema(df[c], p["sha_len1"]) for c in ("open", "close", "high", "low"))
    ha_c = ((o1 + h1 + l1 + c1) / 4).to_numpy()
    ha_o = np.empty(len(df))
    if len(df):
        ha_o[0] = (o1.iat[0] + c1.iat[0]) / 2                  # haO := na(haO[1]) ? (o1+c1)/2
        for i in range(1, len(df)):
            ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2          #      : (haO[1] + haC[1]) / 2
    up = ema(pd.Series(ha_c), p["sha_len2"]) > ema(pd.Series(ha_o), p["sha_len2"])
    prev = up.shift(1, fill_value=bool(up.iat[0]) if len(up) else False).astype(bool)
    df["sha_up"], df["flip_up"], df["flip_dn"] = up, up & ~prev, ~up & prev
    df["e9"], df["e22"] = ema(df["close"], 9), ema(df["close"], 22)
    df["atr"] = wilder(true_range(df["high"], df["low"], df["close"]), 14)
    df["sw_lo"] = df["low"].rolling(p["sw_len"]).min()
    df["sw_hi"] = df["high"].rolling(p["sw_len"]).max()
    t = df["time"].dt.time
    s0, s1 = (_t(x) for x in p["session"])
    df["in_sess"] = (t >= s0) & (t < s1)
    # exclude_hours (Silver, 2026-09-28): a structural low-liquidity window (verified via 5m volume
    # rank, stable 0.87 train/holdout correlation) - the gap between the Indian morning session
    # winding down and London/COMEX building volume. Holdout-validated across 4 split points
    # (+25k to +32k net, every window) - unlike an hour picked by backward-looking P&L, which failed
    # every holdout check tried (see strategy_audit_2026_09 chat log, 2026-09-28). None/empty -> no-op.
    exclude_hours = set(p.get("exclude_hours") or [])
    if exclude_hours:
        df["in_sess"] = df["in_sess"] & ~df["time"].dt.hour.isin(exclude_hours)
    df["risk_l"] = np.maximum(df["close"] - (df["sw_lo"] - p["sw_buf"] * df["atr"]), p["min_sl"] * df["atr"])
    df["risk_s"] = np.maximum((df["sw_hi"] + p["sw_buf"] * df["atr"]) - df["close"], p["min_sl"] * df["atr"])
    cap = p["max_sl"] * df["atr"]
    # bo_lookback (v4.1): entry = SHA flip OR a Donchian breakout of the prior N-bar high/low, channel
    # shifted one bar so the current bar cannot see itself. None/0 -> identical to the plain flip entry.
    bo = p.get("bo_lookback")
    entry_l, entry_s = df["flip_up"], df["flip_dn"]
    if bo:
        entry_l = entry_l | (df["close"] > df["high"].rolling(bo).max().shift(1))
        entry_s = entry_s | (df["close"] < df["low"].rolling(bo).min().shift(1))
    df["ok_l"] = df["in_sess"] & entry_l & (df["e9"] > df["e22"]) & (df["risk_l"] <= cap)
    df["ok_s"] = df["in_sess"] & entry_s & (df["e9"] < df["e22"]) & (df["risk_s"] <= cap) & ~df["ok_l"]
    # min_stop_pct (2026-10-03): skip a signal whose stop is closer than this % of the signal-bar close. A stop of
    # a few hundred points is mostly noise, and the round-trip cost (0.04% of price) is a large share of it. It helped
    # the quiet 2025 sample (PF 1.18 -> 1.35) and is a no-op in today's wide-stop regime. None/0 -> unchanged.
    # Applied AFTER ok_l/ok_s are built, so a long dropped here does not free the short side of the same bar.
    min_stop_pct = p.get("min_stop_pct")
    if min_stop_pct:
        floor_pts = df["close"] * (float(min_stop_pct) / 100.0)
        df["ok_l"] = df["ok_l"] & (df["risk_l"] >= floor_pts)
        df["ok_s"] = df["ok_s"] & (df["risk_s"] >= floor_pts)
    return df


def simulate(df, p, start=WARMUP_BARS, next_open=True):
    """Bracket-only trade simulation. Entries fill at the next bar's open (Pine default) with
    SL/TP fixed from the signal bar's close. Returns (closed_trades, open_position, pending).

    reversal_exit (v4.2, off by default): no fixed target - the only exits are the stop, or an
    opposite-direction ok_l/ok_s signal while a position is open. That decision, like a fresh
    entry, fills at the NEXT bar's open (Pine's default order timing), via `pending_close`."""
    rows = df.to_dict("records")
    trades, pos, pending = [], None, None
    day, day_real, locked = None, 0.0, False
    limit = p.get("day_loss_limit_pts") or 0
    reversal_exit = bool(p.get("reversal_exit"))
    pending_close = None

    def close(px, t, why):
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
        just_reversed = False
        if pending_close is not None and pos is not None:
            close(r["open"], r["time"], pending_close)
            pending_close = None
            just_reversed = True
        if pending is not None:
            pos = dict(pending, entry_time=r["time"], entry=r["open"])
            pending = None
        if pos is not None:
            is_long = pos["side"] == "LONG"
            hit_sl = r["low"] <= pos["sl"] if is_long else r["high"] >= pos["sl"]
            hit_tp = (not reversal_exit) and (r["high"] >= pos["tp"] if is_long else r["low"] <= pos["tp"])
            if hit_sl or hit_tp:                                 # both in one bar: assume the stop
                close(pos["sl"] if hit_sl else pos["tp"], r["time"], "SL" if hit_sl else "TP")
            elif locked:
                close(r["close"], r["time"], "DAY LIMIT")
            elif reversal_exit and pos is not None and (r["ok_s"] if is_long else r["ok_l"]):
                pending_close = "REV"
        if (not just_reversed and pos is None and pending is None and not locked
                and (r["ok_l"] or r["ok_s"])):
            side = "LONG" if r["ok_l"] else "SHORT"
            risk = r["risk_l"] if side == "LONG" else r["risk_s"]
            sign = 1 if side == "LONG" else -1
            sig = dict(side=side, signal_time=r["time"], risk_pts=risk,
                       sl=r["close"] - sign * risk,
                       tp=(None if reversal_exit else r["close"] + sign * p["rr"] * risk))
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


def v40_state(bars, p):
    if len(bars) < WARMUP_BARS + 50:
        return dict(modelled=True, available=False, name=p["name"], note=f"only {len(bars)} 5m bars of history")
    df = v40_frame(bars, p)
    trades, pos, pending = simulate(df, p)
    last = df.iloc[-1]

    flips = np.flatnonzero((df["flip_up"] | df["flip_dn"]).to_numpy())
    last_flip = None
    if len(flips):
        j = int(flips[-1])
        last_flip = dict(time=df["time"].iat[j], direction="up" if df["flip_up"].iat[j] else "down",
                         close=float(df["close"].iat[j]), bars_ago=len(df) - 1 - j)

    trend = "bull" if last["e9"] > last["e22"] else "bear" if last["e9"] < last["e22"] else "flat"
    sha = "green" if last["sha_up"] else "red"
    alignment = ("long-aligned" if sha == "green" and trend == "bull"
                 else "short-aligned" if sha == "red" and trend == "bear" else "mixed")
    cap = p["max_sl"] * last["atr"]

    def if_flip(side):
        is_long = side == "long"
        risk = float(last["risk_l"] if is_long else last["risk_s"])
        sign = 1 if is_long else -1
        return dict(needs="SHA flip red->green with EMA9 > EMA22" if is_long else "SHA flip green->red with EMA9 < EMA22",
                    trend_ok=trend == ("bull" if is_long else "bear"),
                    risk_pts=risk, within_max_sl=bool(risk <= cap), reward_pts=p["rr"] * risk,
                    sl=float(last["close"]) - sign * risk, tp=float(last["close"]) + sign * p["rr"] * risk)

    last_day = last["time"].date()
    days = sorted({t["entry_time"].date() for t in trades})[-5:]
    recent = [t for t in trades if t["entry_time"].date() in days]
    day_trades = [t for t in trades if t["entry_time"].date() == last_day]
    return dict(
        modelled=True, available=True, approximate=True, name=p["name"], rr=p["rr"],
        last_bar=last["time"], close=float(last["close"]), sha=sha,
        ema9=float(last["e9"]), ema22=float(last["e22"]), ema_trend=trend, alignment=alignment,
        atr_5m=float(last["atr"]), last_flip=last_flip,
        position=_trade_view(pos, float(last["close"])) if pos else None,
        pending_entry=_trade_view(pending) if pending else None,
        last_trade=_trade_view(trades[-1]) if trades else None,
        last_session=dict(date=last_day, trades=len(day_trades), net_pts=sum(t["pnl_pts"] for t in day_trades)),
        recent_5_sessions=dict(trades=len(recent), wins=sum(t["pnl_pts"] > 0 for t in recent),
                               net_pts=sum(t["pnl_pts"] for t in recent)),
        if_flip_now=dict(long=if_flip("long"), short=if_flip("short")),
        sim_window=dict(start=df["time"].iat[WARMUP_BARS], end=last["time"], trades=len(trades)),
    )
