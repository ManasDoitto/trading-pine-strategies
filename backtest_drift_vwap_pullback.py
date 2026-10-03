"""Validate the "Drift VWAP Pullback" strategy from the IQCapital/Matteo Conti video
(youtube.com/watch?v=wm4A6qo0g3I) on NSE stocks, using the already-harvested 5m bars
in research_data/nse5m/ (2018-01 .. 2026-09, 210 F&O-underlying stocks).

Rules exactly as stated in the video (NQ futures, 15m chart, VWAP anchored at session open):
  1. Bias: long only if close > VWAP, short only if close < VWAP
  2. VWAP slope: VWAP must be moving in the trade direction over the past 15 min
     (on a 15m chart: VWAP[i] > VWAP[i-1] for longs, < for shorts)
  3. Drift: price must have moved >= 0.1% in the trade direction over the prior hour
     (4 bars back on a 15m chart)
  4. Trigger: first pullback candle toward VWAP (red candle wicking down to touch VWAP
     for longs, green candle wicking up to touch VWAP for shorts)
  5. Entry: stop order on the break of the signal candle's high (long) / low (short)
  6. Exit: risk is stated as 80 points to make 40 on NQ -- i.e. a NEGATIVE 2:1 reward:risk.
     We translate this the only way that is comparable across stocks of very different
     prices: risk = distance from entry to the signal candle's opposite extreme (its low
     for longs), target = 0.5x that risk. Also runs a 1:1 variant for comparison.
  7. EOD flatten (any open position is closed at the session's last bar close).

This is NOT the US-prop-firm "93.6% funded" claim (that's a Monte Carlo pass-probability
for a specific eval's drawdown/profit-target rules, not a trading edge -- see video at
21:27-22:30 where the speaker himself calls the setup's reward:risk "negative"). What we
CAN test on NSE data: does the pullback actually produce a high enough win rate to clear
the >66.7% breakeven needed for a 2:1-against-you risk:reward, before costs.
"""
from __future__ import annotations

import glob
import os
import sys
import time

import numpy as np
import pandas as pd
from numba import njit

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "research_data", "nse5m")
DRIFT_PCT = 0.001          # 0.1% drift filter over prior hour
DRIFT_LOOKBACK_BARS = 4    # 1 hour on a 15m chart
TICK = 0.05
COST_PCT = 0.0007          # round-trip slippage+cost assumption for NSE intraday equity (~7bps)


@njit(cache=True)
def simulate(o, h, l, c, vwap, day_id, sig_long, sig_short, reward_mult):
    n = len(o)
    max_trades = n  # generous upper bound
    dirs = np.zeros(max_trades, dtype=np.int8)
    entries = np.zeros(max_trades, dtype=np.float64)
    stops = np.zeros(max_trades, dtype=np.float64)
    targets = np.zeros(max_trades, dtype=np.float64)
    exits = np.zeros(max_trades, dtype=np.float64)
    nt = 0

    pending_dir = 0      # 0 none, 1 long, -1 short
    pending_entry = 0.0
    pending_stop = 0.0
    pending_target = 0.0

    pos_dir = 0
    pos_entry = 0.0
    pos_stop = 0.0
    pos_target = 0.0

    for i in range(n):
        new_day = (i == 0) or (day_id[i] != day_id[i - 1])
        if new_day:
            # EOD flatten any open position / cancel any pending order from prior day
            if pos_dir != 0:
                dirs[nt] = pos_dir
                entries[nt] = pos_entry
                stops[nt] = pos_stop
                targets[nt] = pos_target
                exits[nt] = c[i - 1]
                nt += 1
                pos_dir = 0
            pending_dir = 0

        # 1) manage an open position first (check stop/target against this bar's range)
        if pos_dir == 1:
            hit_stop = l[i] <= pos_stop
            hit_target = h[i] >= pos_target
            if hit_stop and hit_target:
                exit_px = pos_stop  # conservative: assume stop first if both touched
            elif hit_stop:
                exit_px = pos_stop
            elif hit_target:
                exit_px = pos_target
            else:
                exit_px = np.nan
            if not np.isnan(exit_px):
                dirs[nt] = 1
                entries[nt] = pos_entry
                stops[nt] = pos_stop
                targets[nt] = pos_target
                exits[nt] = exit_px
                nt += 1
                pos_dir = 0
        elif pos_dir == -1:
            hit_stop = h[i] >= pos_stop
            hit_target = l[i] <= pos_target
            if hit_stop and hit_target:
                exit_px = pos_stop
            elif hit_stop:
                exit_px = pos_stop
            elif hit_target:
                exit_px = pos_target
            else:
                exit_px = np.nan
            if not np.isnan(exit_px):
                dirs[nt] = -1
                entries[nt] = pos_entry
                stops[nt] = pos_stop
                targets[nt] = pos_target
                exits[nt] = exit_px
                nt += 1
                pos_dir = 0

        # 2) if flat, check pending stop order for a fill (using this bar, only if the
        #    pending order wasn't just created off THIS bar's own signal -- handled below
        #    by checking fills before placing a new signal from the same bar)
        if pos_dir == 0 and pending_dir == 1:
            if h[i] >= pending_entry:
                pos_dir = 1
                pos_entry = pending_entry
                pos_stop = pending_stop
                pos_target = pending_target
                pending_dir = 0
        elif pos_dir == 0 and pending_dir == -1:
            if l[i] <= pending_entry:
                pos_dir = -1
                pos_entry = pending_entry
                pos_stop = pending_stop
                pos_target = pending_target
                pending_dir = 0

        # 3) if still flat (no fill this bar), (re)place a pending order off a fresh signal
        if pos_dir == 0:
            if sig_long[i]:
                entry_lvl = h[i] + TICK
                stop_lvl = l[i] - TICK
                risk = entry_lvl - stop_lvl
                if risk > 0:
                    pending_dir = 1
                    pending_entry = entry_lvl
                    pending_stop = stop_lvl
                    pending_target = entry_lvl + reward_mult * risk
            elif sig_short[i]:
                entry_lvl = l[i] - TICK
                stop_lvl = h[i] + TICK
                risk = stop_lvl - entry_lvl
                if risk > 0:
                    pending_dir = -1
                    pending_entry = entry_lvl
                    pending_stop = stop_lvl
                    pending_target = entry_lvl - reward_mult * risk

    # final EOD flatten for the very last bar if still open
    if pos_dir != 0:
        dirs[nt] = pos_dir
        entries[nt] = pos_entry
        stops[nt] = pos_stop
        targets[nt] = pos_target
        exits[nt] = c[n - 1]
        nt += 1

    return dirs[:nt], entries[:nt], stops[:nt], targets[:nt], exits[:nt]


def resample_15m(df: pd.DataFrame) -> pd.DataFrame:
    d = df.set_index("dt")
    r = d.resample("15min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    r = r.reset_index()
    r["day"] = r["dt"].dt.date
    return r


def compute_daily_trend_ok(df: pd.DataFrame, sma_len: int = 50, slope_lookback: int = 10) -> dict:
    """Day -> bool: daily close above a rising SMA(sma_len), i.e. a structurally
    confirmed uptrend on the daily chart (not just an intraday drift blip)."""
    d = df.set_index("dt")
    daily = d["close"].resample("1D").last().dropna()
    sma = daily.rolling(sma_len).mean()
    ok = (daily > sma) & (sma > sma.shift(slope_lookback))
    ok.index = ok.index.date
    return ok.to_dict()


def add_signals(r: pd.DataFrame, drift_pct: float = DRIFT_PCT, slope_persist_bars: int = 1,
                 long_only: bool = False, daily_trend_ok: dict | None = None) -> pd.DataFrame:
    """slope_persist_bars=N requires VWAP to have risen (fallen) on each of the last N
    bars, not just the most recent one -- a stronger "confirmed trend" than the video's
    literal 1-bar slope check. daily_trend_ok, if given, additionally requires the day's
    close to sit above a rising 50-day SMA (a higher-timeframe uptrend confirmation)."""
    g = r.groupby("day", sort=False)
    tp = (r["high"] + r["low"] + r["close"]) / 3.0
    pv = tp * r["volume"]
    r["vwap"] = pv.groupby(r["day"]).cumsum() / r["volume"].groupby(r["day"]).cumsum()

    bar_in_day = g.cumcount()
    vwap_grp = r.groupby("day")["vwap"]
    vwap_diff = vwap_grp.diff()

    slope_long = vwap_diff > 0
    slope_short = vwap_diff < 0
    # rolling-min trick: persistence over N bars == min of the last N diffs has the right sign
    if slope_persist_bars > 1:
        diff_pos = (vwap_diff > 0).astype(float)
        diff_neg = (vwap_diff < 0).astype(float)
        persist_pos = diff_pos.groupby(r["day"]).rolling(slope_persist_bars, min_periods=slope_persist_bars).min().reset_index(level=0, drop=True)
        persist_neg = diff_neg.groupby(r["day"]).rolling(slope_persist_bars, min_periods=slope_persist_bars).min().reset_index(level=0, drop=True)
        slope_long = persist_pos == 1.0
        slope_short = persist_neg == 1.0

    drift_lookback_bars = max(DRIFT_LOOKBACK_BARS, 1)
    close_prevN = r.groupby("day")["close"].shift(drift_lookback_bars)

    bias_long = r["close"] > r["vwap"]
    bias_short = r["close"] < r["vwap"]
    drift_long = (r["close"] / close_prevN - 1.0) >= drift_pct
    drift_short = (1.0 - r["close"] / close_prevN) >= drift_pct
    red_candle = r["close"] < r["open"]
    green_candle = r["close"] > r["open"]
    touch_long = r["low"] <= r["vwap"]
    touch_short = r["high"] >= r["vwap"]

    enough_history = bar_in_day >= max(drift_lookback_bars, slope_persist_bars)
    sig_long = bias_long & slope_long & drift_long & red_candle & touch_long & enough_history
    sig_short = bias_short & slope_short & drift_short & green_candle & touch_short & enough_history

    if daily_trend_ok is not None:
        day_ok = r["day"].map(daily_trend_ok).fillna(False)
        sig_long &= day_ok

    r["sig_long"] = sig_long.fillna(False)
    r["sig_short"] = (sig_short & (not long_only)).fillna(False)
    return r


def run_symbol(path: str, reward_mult: float, drift_pct: float = DRIFT_PCT, slope_persist_bars: int = 1,
               long_only: bool = False, use_daily_trend: bool = False) -> pd.DataFrame | None:
    df = pd.read_parquet(path)
    if len(df) < 2000:
        return None
    r = resample_15m(df)
    if len(r) < 2000:
        return None
    daily_trend_ok = compute_daily_trend_ok(df) if use_daily_trend else None
    r = add_signals(r, drift_pct=drift_pct, slope_persist_bars=slope_persist_bars,
                     long_only=long_only, daily_trend_ok=daily_trend_ok)

    day_id = pd.factorize(r["day"])[0].astype(np.int64)
    o = r["open"].to_numpy(np.float64)
    h = r["high"].to_numpy(np.float64)
    l = r["low"].to_numpy(np.float64)
    c = r["close"].to_numpy(np.float64)
    vwap = r["vwap"].to_numpy(np.float64)
    sig_long = r["sig_long"].to_numpy()
    sig_short = r["sig_short"].to_numpy()

    dirs, entries, stops, targets, exits = simulate(o, h, l, c, vwap, day_id, sig_long, sig_short, reward_mult)
    if len(dirs) == 0:
        return None

    risk = np.abs(entries - stops)
    raw_move = np.where(dirs == 1, exits - entries, entries - exits)
    gross_r = raw_move / risk
    cost_r = (entries * COST_PCT) / risk  # round-trip cost expressed in R
    net_r = gross_r - cost_r

    sym = os.path.splitext(os.path.basename(path))[0]
    return pd.DataFrame({
        "symbol": sym,
        "dir": dirs,
        "gross_r": gross_r,
        "net_r": net_r,
    })


def summarize(trades: pd.DataFrame, label: str):
    n = len(trades)
    if n == 0:
        print(f"[{label}] no trades")
        return
    win_rate = (trades["net_r"] > 0).mean()
    avg_gross_r = trades["gross_r"].mean()
    avg_net_r = trades["net_r"].mean()
    total_net_r = trades["net_r"].sum()
    eq = trades["net_r"].cumsum()
    dd = (eq - eq.cummax()).min()
    long_n = (trades["dir"] == 1).sum()
    short_n = (trades["dir"] == -1).sum()
    print(f"\n=== {label} ===")
    print(f"trades: {n}  (long {long_n} / short {short_n})")
    print(f"win rate (net of costs): {win_rate:.1%}")
    print(f"avg R per trade: gross={avg_gross_r:+.3f}R  net={avg_net_r:+.3f}R")
    print(f"total net R: {total_net_r:+.1f}R  max drawdown: {dd:.1f}R")


def run_baseline(paths):
    for reward_mult, label in [(0.5, "reward:risk = 0.5 (video's stated 40:80, i.e. 2:1 against you)"),
                                (1.0, "reward:risk = 1.0 (1:1, for comparison)")]:
        t0 = time.time()
        frames = []
        for p in paths:
            try:
                res = run_symbol(p, reward_mult)
            except Exception as e:
                print(f"  skip {os.path.basename(p)}: {e}")
                continue
            if res is not None:
                frames.append(res)
        if not frames:
            print(f"[{label}] no trades across universe")
            continue
        trades = pd.concat(frames, ignore_index=True)
        breakeven = 1.0 / (1.0 + reward_mult)
        summarize(trades, label)
        print(f"breakeven win rate needed: {breakeven:.1%}")
        print(f"elapsed: {time.time()-t0:.1f}s")

        long_trades = trades[trades["dir"] == 1]
        short_trades = trades[trades["dir"] == -1]
        for sub, name in [(long_trades, "LONG only"), (short_trades, "SHORT only")]:
            if len(sub):
                wr = (sub["net_r"] > 0).mean()
                print(f"  {name}: n={len(sub)} win_rate={wr:.1%} avg_net_r={sub['net_r'].mean():+.3f}R total={sub['net_r'].sum():+.1f}R")


# "Confirmed strong uptrend" variants, long-only, progressively stricter trend confirmation:
#   weak_long       -- the video's literal filters (0.1% drift, 1-bar VWAP slope), long side only
#   daily_trend     -- + daily close above a rising 50-day SMA (structural uptrend, not just an
#                       intraday blip)
#   strong_uptrend  -- + VWAP must have risen on each of the last 3 bars (45 min of persistent
#                       push, not a single tick) + drift threshold raised to 0.3% over the prior hour
STRONG_UPTREND_VARIANTS = {
    "weak_long (video's literal filters, long only)": dict(
        drift_pct=DRIFT_PCT, slope_persist_bars=1, long_only=True, use_daily_trend=False),
    "+ daily close > rising 50d SMA": dict(
        drift_pct=DRIFT_PCT, slope_persist_bars=1, long_only=True, use_daily_trend=True),
    "+ 3-bar persistent VWAP slope + 0.3% drift (confirmed strong uptrend)": dict(
        drift_pct=0.003, slope_persist_bars=3, long_only=True, use_daily_trend=True),
}


def run_strong_uptrend_variants(paths):
    for variant_label, kwargs in STRONG_UPTREND_VARIANTS.items():
        for reward_mult, rr_label in [(0.5, "2:1 against you (video's stated 80:40)"), (1.0, "1:1")]:
            t0 = time.time()
            frames = []
            for p in paths:
                try:
                    res = run_symbol(p, reward_mult, **kwargs)
                except Exception as e:
                    print(f"  skip {os.path.basename(p)}: {e}")
                    continue
                if res is not None:
                    frames.append(res)
            label = f"{variant_label} | R:R {rr_label}"
            if not frames:
                print(f"\n=== {label} ===\nno trades")
                continue
            trades = pd.concat(frames, ignore_index=True)
            summarize(trades, label)
            breakeven = 1.0 / (1.0 + reward_mult)
            print(f"breakeven win rate needed: {breakeven:.1%}  |  elapsed: {time.time()-t0:.1f}s")


def main():
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*.parquet")))
    if not paths:
        print("No parquet files found in", DATA_DIR)
        sys.exit(1)
    limit = int(os.environ.get("LIMIT", "0")) or len(paths)
    paths = paths[:limit]
    print(f"Running on {len(paths)} NSE stocks, 15m bars resampled from 5m, {DATA_DIR}")

    mode = os.environ.get("MODE", "strong_uptrend")
    if mode == "baseline":
        run_baseline(paths)
    elif mode == "strong_uptrend":
        run_strong_uptrend_variants(paths)
    else:
        run_baseline(paths)
        run_strong_uptrend_variants(paths)


if __name__ == "__main__":
    main()
