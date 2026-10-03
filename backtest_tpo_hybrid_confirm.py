"""Combine the mean-reversion and trend-breakout TPO setups as confirmation filters for
each other, instead of running them independently (gated only by a POC-percentile
balance/imbalance proxy, which the earlier robustness check showed barely mattered).

The hybrid logic, within a single excursion outside the value area:
  1. DEFAULT HYPOTHESIS = mean reversion. First poke past VAH/VAL that closes back inside
     -> fade toward POC, tight stop beyond the excess extreme (same as
     backtest_tpo_value_area_mr.py).
  2. If that fade gets STOPPED OUT, that failure is itself the confirmation signal: the
     level didn't hold, so on the next bar that closes back beyond the same edge with a
     genuine margin, switch to trend-following that breakout (same as
     backtest_tpo_breakout_trend.py), stop back at the value-area edge, target a reward_r
     multiple of that risk.
  3. Only one setup is "live" per excursion per side -- once a fade has failed and we're
     trend-following, we don't flip back to fading until price returns inside the value
     area (which also re-arms the fade-first logic for the next excursion).

This replaces the independent POC-percentile day-regime filter with price action itself
confirming regime (a fade that holds IS the balance signal; a fade that fails IS the
imbalance signal) -- arguably a better regime proxy than the static percentile heuristic,
and it directly answers whether cross-confirming the two setups helps vs. running them
separately.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest_tpo_value_area_mr import INSTRUMENTS, VALUE_AREA_PCT, MIN_BARS_BEFORE_SIGNAL, load
from backtest_tpo_breakout_trend import MIN_BREAKOUT_TICKS

EXCESS_BUFFER_TICKS = 1.0  # same as the standalone mean-reversion script


def simulate_day(day_df: pd.DataFrame, bin_size: float, trend_reward_r: float):
    o = day_df["open"].to_numpy(np.float64)
    h = day_df["high"].to_numpy(np.float64)
    l = day_df["low"].to_numpy(np.float64)
    c = day_df["close"].to_numpy(np.float64)
    n = len(o)
    if n < MIN_BARS_BEFORE_SIGNAL + 2:
        return []

    counts: dict[int, int] = {}
    trades = []  # (dir, entry, stop, target, exit_px, setup)  setup: 'mr' or 'trend'
    pos_dir = 0
    pos_entry = pos_stop = pos_target = 0.0
    pos_setup = ""
    upper_fade_failed = False
    lower_fade_failed = False
    upper_trend_taken = False
    lower_trend_taken = False

    def bins_for_bar(lo, hi):
        b0 = int(np.floor(lo / bin_size))
        b1 = int(np.floor(hi / bin_size))
        return range(b0, b1 + 1)

    def value_area():
        if not counts:
            return None
        poc_bin = max(counts, key=counts.get)
        total = sum(counts.values())
        tgt = total * VALUE_AREA_PCT
        acc = counts[poc_bin]
        lo_b = hi_b = poc_bin
        while acc < tgt:
            lo_cand, hi_cand = lo_b - 1, hi_b + 1
            v_lo, v_hi = counts.get(lo_cand, 0), counts.get(hi_cand, 0)
            if v_lo == 0 and v_hi == 0:
                break
            if v_lo >= v_hi:
                lo_b = lo_cand; acc += v_lo
            else:
                hi_b = hi_cand; acc += v_hi
        return poc_bin, lo_b, hi_b

    for i in range(n):
        if pos_dir == 1:
            hit_stop, hit_target = l[i] <= pos_stop, h[i] >= pos_target
            if hit_stop or hit_target:
                exit_px = pos_stop if hit_stop else pos_target
                trades.append((1, pos_entry, pos_stop, pos_target, exit_px, pos_setup))
                if hit_stop and pos_setup == "mr":
                    lower_fade_failed = True
                pos_dir = 0
        elif pos_dir == -1:
            hit_stop, hit_target = h[i] >= pos_stop, l[i] <= pos_target
            if hit_stop or hit_target:
                exit_px = pos_stop if hit_stop else pos_target
                trades.append((-1, pos_entry, pos_stop, pos_target, exit_px, pos_setup))
                if hit_stop and pos_setup == "mr":
                    upper_fade_failed = True
                pos_dir = 0

        if counts:
            va = value_area()
            if va is not None:
                poc_bin, val_bin, vah_bin = va
                poc_px = (poc_bin + 0.5) * bin_size
                vah_px = (vah_bin + 1) * bin_size
                val_px = val_bin * bin_size

                if val_px <= c[i] <= vah_px:
                    upper_fade_failed = lower_fade_failed = False
                    upper_trend_taken = lower_trend_taken = False

                if pos_dir == 0 and i >= MIN_BARS_BEFORE_SIGNAL:
                    excess_hi = vah_px + EXCESS_BUFFER_TICKS * bin_size
                    excess_lo = val_px - EXCESS_BUFFER_TICKS * bin_size
                    min_risk = MIN_BREAKOUT_TICKS * bin_size

                    if not upper_fade_failed and h[i] >= excess_hi and c[i] < vah_px:
                        entry = c[i]; stop = h[i] + EXCESS_BUFFER_TICKS * bin_size
                        if stop > entry > poc_px:
                            pos_dir, pos_entry, pos_stop, pos_target, pos_setup = -1, entry, stop, poc_px, "mr"
                    elif not lower_fade_failed and l[i] <= excess_lo and c[i] > val_px:
                        entry = c[i]; stop = l[i] - EXCESS_BUFFER_TICKS * bin_size
                        if stop < entry < poc_px:
                            pos_dir, pos_entry, pos_stop, pos_target, pos_setup = 1, entry, stop, poc_px, "mr"
                    elif upper_fade_failed and not upper_trend_taken and c[i] > vah_px + min_risk:
                        entry = c[i]; stop = vah_px; risk = entry - stop
                        pos_dir, pos_entry, pos_stop, pos_target, pos_setup = 1, entry, stop, entry + trend_reward_r * risk, "trend"
                        upper_trend_taken = True
                    elif lower_fade_failed and not lower_trend_taken and c[i] < val_px - min_risk:
                        entry = c[i]; stop = val_px; risk = stop - entry
                        pos_dir, pos_entry, pos_stop, pos_target, pos_setup = -1, entry, stop, entry - trend_reward_r * risk, "trend"
                        lower_trend_taken = True

        for b in bins_for_bar(l[i], h[i]):
            counts[b] = counts.get(b, 0) + 1

    if pos_dir != 0:
        trades.append((pos_dir, pos_entry, pos_stop, pos_target, c[-1], pos_setup))

    return trades


def run(symbol: str, trend_reward_r: float) -> pd.DataFrame:
    cfg = INSTRUMENTS[symbol]
    df = load(cfg["path"])
    rows = []
    for day, day_df in df.groupby("day", sort=True):
        day_df = day_df.reset_index(drop=True)
        for d, entry, stop, target, exit_px, setup in simulate_day(day_df, cfg["bin_size"], trend_reward_r):
            risk = abs(entry - stop)
            raw = (exit_px - entry) if d == 1 else (entry - exit_px)
            gross_r = raw / risk
            cost_r = cfg["cost_pts"] / risk
            rows.append((symbol, day, d, setup, gross_r, gross_r - cost_r))
    return pd.DataFrame(rows, columns=["symbol", "day", "dir", "setup", "gross_r", "net_r"])


def summarize(trades: pd.DataFrame, label: str):
    n = len(trades)
    if n == 0:
        print(f"[{label}] no trades"); return
    print(f"\n=== {label} ===")
    print(f"trades: {n}  (long {(trades['dir']==1).sum()} / short {(trades['dir']==-1).sum()})")
    win_rate = (trades["net_r"] > 0).mean()
    print(f"win rate (net of costs): {win_rate:.1%}")
    print(f"avg R/trade: gross={trades['gross_r'].mean():+.3f}R  net={trades['net_r'].mean():+.3f}R")
    eq = trades["net_r"].cumsum()
    print(f"total net R: {trades['net_r'].sum():+.1f}R  max drawdown: {(eq-eq.cummax()).min():.1f}R")
    days = trades["day"].nunique()
    print(f"trading days with >=1 signal: {days}  (avg {n/max(days,1):.2f} trades/day)")
    for setup in ["mr", "trend"]:
        sub = trades[trades["setup"] == setup]
        if len(sub):
            wr = (sub["net_r"] > 0).mean()
            print(f"  [{setup}] n={len(sub)} win_rate={wr:.1%} avg_net_r={sub['net_r'].mean():+.3f}R total={sub['net_r'].sum():+.1f}R")


def main():
    for symbol in INSTRUMENTS:
        for trend_reward_r in [1.0, 2.0]:
            trades = run(symbol, trend_reward_r)
            summarize(trades, f"{symbol} | hybrid (fade-fails-then-follow), trend target={trend_reward_r}R")


if __name__ == "__main__":
    main()
