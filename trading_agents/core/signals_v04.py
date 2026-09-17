"""Python port of BankNifty v0.4 - EMA pullback reclaim + 15m ADX gate.

Source: working_strategies/BankNifty/1_v0.4_EMA_pullback_15mADX_gate.pine.txt, default inputs.
Chart: NSE:BANKNIFTY1! 5m - the front-month FUTURE, because the core filter needs volume and VWAP
(Dhan's BankNifty index has volume on only ~40% of bars). Inputs that are OFF in the Pine (EMA200
hard filter, midday skip, ATR max, quality score, gap lock, day skips, daily ADX, break-even, trail,
partial TP) are not ported.

Mechanics reproduced bar by bar, in the order the Pine script and TradingView's broker emulator use:

  A. fills, from orders placed at the previous bar's close
     - an ARMED stop entry fills at the trigger, or at the open if the bar gaps through it
     - an open position's stop/target (placed only after its fill bar closed, so never active on the
       fill bar itself) - a bar opening through a level exits at the open
     - a force-flat order from the 15:15 window exits at the next bar's open
  B. the script at the bar's close
     - pullback tracker, cooldown after an exit, the gate stack, then arming: trigger = the setup
       bar's high (long) / low (short), stop below the pullback extreme (or the EMA band in a coil),
       floored at 0.5 ATR, skipped if wider than 2 ATR, target 2.5R
     - an armed order expires after `reclaim_win` bars or when the regime flips

Approximations: when one bar touches both stop and target the stop is assumed first (TradingView may
pick by distance from the open); a live opposite-side stop order during a position (only possible in a
coil regime) is ignored rather than reversing; commission and slippage are not modelled.
"""
from datetime import time as dtime

import numpy as np
import pandas as pd

from .levels import true_range, wilder

WARMUP_BARS = 250          # EMA200 and the 15m ADX both need history before signals are meaningful
MINTICK = 0.05


def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()


def rsi(close, n):
    delta = close.diff()
    gain = wilder(delta.clip(lower=0), n)
    loss = wilder((-delta).clip(lower=0), n)
    return 100 - 100 / (1 + gain / loss)


def adx(bars, n=14):
    """Pine ta.dmi(n, n) ADX: Wilder-smoothed DI+/DI- and ADX."""
    up = bars["high"].diff()
    down = -bars["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=bars.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=bars.index)
    trur = wilder(true_range(bars["high"], bars["low"], bars["close"]), n)
    plus = 100 * wilder(plus_dm, n) / trur
    minus = 100 * wilder(minus_dm, n) / trur
    total = plus + minus
    return 100 * wilder((plus - minus).abs() / total.where(total != 0, 1), n)


def htf_adx_prev(bars, minutes=15, n=14):
    """For each 5m bar: ADX(14) of the PREVIOUS COMPLETED 15m bar - the Pine's
    request.security("15", ta.dmi(...)[1], lookahead_on), which never sees the forming 15m bar."""
    k = (bars.set_index("time")
         .resample(f"{minutes}min", label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
         .dropna(subset=["close"])
         .reset_index())
    k["adx_prev"] = adx(k, n).shift(1)
    lookup = dict(zip(k["time"], k["adx_prev"]))
    return bars["time"].dt.floor(f"{minutes}min").map(lookup).astype(float)


def _hhmm(text):
    hh, mm = text.split(":")
    return dtime(int(hh), int(mm))


def v04_frame(bars, p):
    """Indicators and per-bar conditions. Stateful parts (pullback tracker, orders) live in simulate()."""
    df = bars.reset_index(drop=True).copy()
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

    df["ema9"], df["ema21"], df["ema200"] = ema(c, p["ema_fast"]), ema(c, p["ema_med"]), ema(c, p["ema_slow"])
    df["rsi3"] = rsi(c, p["rsi_len"])
    df["atr14"] = wilder(true_range(h, l, c), 14)
    df["vol_sma"] = v.rolling(20).mean()
    df["ema_hi3"] = df[["ema9", "ema21", "ema200"]].max(axis=1)
    df["ema_lo3"] = df[["ema9", "ema21", "ema200"]].min(axis=1)
    df["coil"] = bool(p["allow_coil"]) & ((df["ema_hi3"] - df["ema_lo3"]) <= p["cluster_mlt"] * df["atr14"])

    t = df["time"].dt.time
    s0, s1 = (_hhmm(x) for x in p["entry_window"])
    f0, f1 = (_hhmm(x) for x in p["flat_window"])
    df["in_flat"] = (t >= f0) & (t < f1)
    day = df["time"].dt.date
    first_bar = df.groupby(day)["time"].transform("min")
    after_open = (df["time"] - first_bar) >= pd.Timedelta(minutes=p["skip_open_min"])
    df["in_session"] = (t >= s0) & (t < s1) & after_open & ~df["in_flat"]

    hlc3 = (h + l + c) / 3
    cum_pv = (hlc3 * v).groupby(day).cumsum()
    cum_v = v.groupby(day).cumsum()
    df["vwap"] = cum_pv / cum_v.where(cum_v > 0)

    df["atr_ok"] = (p["atr_min_pts"] == 0) | (df["atr14"] >= p["atr_min_pts"])
    df["regime_up"] = (df["ema9"] > df["ema21"]) | df["coil"]
    df["regime_dn"] = (df["ema9"] < df["ema21"]) | df["coil"]
    df["above_both"] = np.where(df["coil"], c > df["ema_hi3"], (c > df["ema9"]) & (c > df["ema21"]))
    df["below_both"] = np.where(df["coil"], c < df["ema_lo3"], (c < df["ema9"]) & (c < df["ema21"]))

    rng = np.maximum(h - l, MINTICK)
    df["big_lower_wick"] = (np.minimum(o, c) - l) >= p["wick_frac"] * rng
    df["big_upper_wick"] = (h - np.maximum(o, c)) >= p["wick_frac"] * rng
    df["q_vol"] = v >= p["vol_mlt"] * df["vol_sma"]
    df["q_vwap_l"] = c > df["vwap"]
    df["q_vwap_s"] = c < df["vwap"]
    df["adx15_prev"] = htf_adx_prev(bars.reset_index(drop=True), n=14)
    df["adx_ok"] = (p["htf_adx_min"] == 0) | (df["adx15_prev"] >= p["htf_adx_min"])
    return df


def simulate(df, p, start=0):
    """Run the strategy over a v04_frame. Returns dict(trades, position, live, events):
    `live` = stop entry orders active for the NEXT bar; `events` = armed / filled / exited / expired."""
    rows = df.to_dict("records")
    pb = {s: dict(act=False, ext=None, bar=None, last=None, wick=False, hold=False) for s in "LS"}
    wait = {"L": None, "S": None}
    live = {"L": None, "S": None}
    pos, eod_pending, last_exit_bar, prev_size = None, False, None, 0
    trades, events = [], []

    for i in range(start, len(rows)):
        r = rows[i]

        # ---------------- A. fills from orders placed at the previous bar's close
        if pos is None:
            for s in "LS":
                o = live[s]
                if o is None:
                    continue
                if s == "L":
                    px = r["open"] if r["open"] >= o["trig"] else (o["trig"] if r["high"] >= o["trig"] else None)
                else:
                    px = r["open"] if r["open"] <= o["trig"] else (o["trig"] if r["low"] <= o["trig"] else None)
                if px is None:
                    continue
                pos = dict(side=o["side"], arm_time=o["arm_time"], entry_bar=i, entry_time=r["time"], entry=float(px),
                           sl=o["sl"], tp=o["tp"], risk_pts=abs(float(px) - o["sl"]))
                events.append(dict(kind="filled", bar=i, time=r["time"], **pos))
                break
        elif pos["entry_bar"] < i:
            is_long = pos["side"] == "LONG"
            exit_px = reason = None
            if eod_pending:
                exit_px, reason = r["open"], "EOD"
            elif is_long:
                if r["open"] <= pos["sl"]:
                    exit_px, reason = r["open"], "SL"
                elif r["open"] >= pos["tp"]:
                    exit_px, reason = r["open"], "TARGET"
                elif r["low"] <= pos["sl"]:
                    exit_px, reason = pos["sl"], "SL"
                elif r["high"] >= pos["tp"]:
                    exit_px, reason = pos["tp"], "TARGET"
            else:
                if r["open"] >= pos["sl"]:
                    exit_px, reason = r["open"], "SL"
                elif r["open"] <= pos["tp"]:
                    exit_px, reason = r["open"], "TARGET"
                elif r["high"] >= pos["sl"]:
                    exit_px, reason = pos["sl"], "SL"
                elif r["low"] <= pos["tp"]:
                    exit_px, reason = pos["tp"], "TARGET"
            if reason:
                sign = 1 if is_long else -1
                done = dict(pos, exit_bar=i, exit_time=r["time"], exit=float(exit_px), result=reason,
                            pnl_pts=(float(exit_px) - pos["entry"]) * sign)
                trades.append(done)
                events.append(dict(kind="exited", bar=i, time=r["time"], **done))
                pos = None
        eod_pending = False
        size = 0 if pos is None else (1 if pos["side"] == "LONG" else -1)

        # ---------------- B. the script at this bar's close
        for s in "LS":                                             # pullback tracker
            st = pb[s]
            if not (r["regime_up"] if s == "L" else r["regime_dn"]):
                st.update(act=False, ext=None, bar=None, wick=False, hold=False)
                continue
            if r["above_both"] if s == "L" else r["below_both"]:
                st["last"] = i
            touched = r["low"] <= r["ema9"] if s == "L" else r["high"] >= r["ema9"]
            if touched and st["last"] is not None and i - st["last"] <= p["pb_lookback"]:
                fresh = (not st["act"]) or (st["bar"] is not None and st["last"] >= st["bar"])
                wick = bool(r["big_lower_wick"] if s == "L" else r["big_upper_wick"])
                extreme = r["low"] if s == "L" else r["high"]
                if fresh:
                    st["ext"], st["wick"] = extreme, wick
                else:
                    st["ext"] = min(st["ext"], extreme) if s == "L" else max(st["ext"], extreme)
                    st["wick"] = st["wick"] or wick
                st["hold"] = bool(r["close"] > r["ema21"] if s == "L" else r["close"] < r["ema21"])
                st["act"], st["bar"] = True, i

        if size == 0 and prev_size != 0:                           # cooldown
            last_exit_bar = i
        cool_ok = p["cool_bars"] == 0 or last_exit_bar is None or (i - last_exit_bar) > p["cool_bars"]

        for s in "LS":                                             # gate stack + arming
            st = pb[s]
            if s == "L":
                qual = st["wick"] and r["q_vol"] and r["q_vwap_l"] and st["hold"]
                gate = (r["regime_up"] and r["above_both"] and r["in_session"] and r["atr_ok"] and qual
                        and r["adx_ok"] and r["rsi3"] < p["rsi_max_long"])
            else:
                qual = st["wick"] and r["q_vol"] and r["q_vwap_s"] and st["hold"]
                gate = (r["regime_dn"] and r["below_both"] and r["in_session"] and r["atr_ok"] and qual
                        and r["adx_ok"] and r["rsi3"] > p["rsi_min_short"])
            if not (pos is None and cool_ok and wait[s] is None and st["act"] and gate
                    and st["bar"] is not None and i - st["bar"] <= p["reclaim_win"]):
                continue
            atr = r["atr14"]
            if s == "L":
                tight = (r["ema_lo3"] - p["cluster_buf"] * atr) if r["coil"] else (st["ext"] - p["atr_buff"] * atr)
                sl = min(tight, r["high"] - p["stop_floor_atr"] * atr) if p["stop_floor_atr"] > 0 else tight
                trig, risk = r["high"], r["high"] - sl
                tp = trig + risk * p["rr"]
            else:
                tight = (r["ema_hi3"] + p["cluster_buf"] * atr) if r["coil"] else (st["ext"] + p["atr_buff"] * atr)
                sl = max(tight, r["low"] + p["stop_floor_atr"] * atr) if p["stop_floor_atr"] > 0 else tight
                trig, risk = r["low"], sl - r["low"]
                tp = trig - risk * p["rr"]
            if risk > 0 and (p["max_stop_atr"] == 0 or risk <= p["max_stop_atr"] * atr):
                wait[s] = dict(side="LONG" if s == "L" else "SHORT", arm_bar=i, arm_time=r["time"],
                               trig=float(trig), sl=float(sl), tp=float(tp), risk_pts=float(risk))
                st["act"] = False
                events.append(dict(kind="armed", bar=i, time=r["time"], **wait[s]))

        for s in "LS":                                             # armed orders expire
            w = wait[s]
            if w and (i - w["arm_bar"] > p["reclaim_win"] or not (r["regime_up"] if s == "L" else r["regime_dn"])):
                events.append(dict(kind="expired", bar=i, time=r["time"], **w))
                wait[s] = None

        for s in "LS":                                             # stop entries live for the next bar
            live[s] = wait[s] if (wait[s] is not None and not r["in_flat"]) else None

        if pos is not None:                                        # in a position: no waiting order on its side
            wait["L" if pos["side"] == "LONG" else "S"] = None
            if r["in_flat"]:
                eod_pending = True                                 # strategy.close -> next bar's open
        prev_size = size

    return dict(trades=trades, position=pos, live=live, events=events)
