"""Trend-following counterpart to backtest_tpo_value_area_mr.py.

A viewer comment on the Fabio Valentini video (youtube.com/watch?v=tvERE-Beu2U) claimed
trend following is "way more easy" than the mean-reversion setup he teaches. Fabio
himself doesn't give his own trend-day rules in the portion of the video covered (the
"Market structure pitfalls" chapter is actually him CRITIQUING naive trend-following --
CHoCH / order-block / supply-demand-style entries -- as a common mistake, not endorsing
a method of his own). So this tests the natural Auction-Market-Theory COMPLEMENT to the
mean-reversion model already built, using the exact same engine and data:

  - Mean reversion (already tested): balance day (POC centered in day's range-so-far),
    price pokes past the value-area edge and SNAPS BACK inside the same bar -> fade
    toward POC/midpoint.
  - Trend following (this script): imbalance day (POC skewed to one edge of the day's
    range-so-far, i.e. one-sided/trending so far), price CLOSES beyond the value-area
    edge and does NOT snap back -> follow the breakout, stop back inside the value area,
    target a multiple of that risk (classic breakout convention: risk the retest, let
    the move extend).

Same TPO (time-at-price) profile as the mean-reversion script, for the same reason:
Dhan's historical BANKNIFTY/NIFTY volume field is ~70-84% zero, so a real volume profile
isn't reliable; Market Profile/TPO needs no volume field.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from backtest_tpo_value_area_mr import INSTRUMENTS, VALUE_AREA_PCT, MIN_BARS_BEFORE_SIGNAL, load

TREND_LO, TREND_HI = 0.20, 0.80  # developing POC must sit OUTSIDE this band (one-sided day)
MIN_BREAKOUT_TICKS = 2.0  # close must clear the VA edge by at least this many bins -- a near-zero
                           # "breakout" (close a paisa past the edge) isn't a real signal, and
                           # without this floor a handful of razor-thin-risk trades blow up the
                           # cost-as-fraction-of-risk math


def simulate_day(day_df: pd.DataFrame, bin_size: float, reward_r: float):
    o = day_df["open"].to_numpy(np.float64)
    h = day_df["high"].to_numpy(np.float64)
    l = day_df["low"].to_numpy(np.float64)
    c = day_df["close"].to_numpy(np.float64)
    n = len(o)
    if n < MIN_BARS_BEFORE_SIGNAL + 2:
        return []

    counts: dict[int, int] = {}
    day_hi = -np.inf
    day_lo = np.inf
    trades = []
    pos_dir = 0
    pos_entry = pos_stop = pos_target = 0.0
    long_taken = False   # already took (or are in) a long breakout since price last was inside VA
    short_taken = False

    def bins_for_bar(lo, hi):
        b0 = int(np.floor(lo / bin_size))
        b1 = int(np.floor(hi / bin_size))
        return range(b0, b1 + 1)

    def value_area():
        if not counts:
            return None
        poc_bin = max(counts, key=counts.get)
        total = sum(counts.values())
        target = total * VALUE_AREA_PCT
        acc = counts[poc_bin]
        lo_b = hi_b = poc_bin
        while acc < target:
            lo_cand = lo_b - 1
            hi_cand = hi_b + 1
            v_lo = counts.get(lo_cand, 0)
            v_hi = counts.get(hi_cand, 0)
            if v_lo == 0 and v_hi == 0:
                break
            if v_lo >= v_hi:
                lo_b = lo_cand
                acc += v_lo
            else:
                hi_b = hi_cand
                acc += v_hi
        return poc_bin, lo_b, hi_b

    for i in range(n):
        if pos_dir == 1:
            hit_stop = l[i] <= pos_stop
            hit_target = h[i] >= pos_target
            if hit_stop or hit_target:
                exit_px = pos_stop if hit_stop else pos_target
                trades.append((1, pos_entry, pos_stop, pos_target, exit_px))
                pos_dir = 0
        elif pos_dir == -1:
            hit_stop = h[i] >= pos_stop
            hit_target = l[i] <= pos_target
            if hit_stop or hit_target:
                exit_px = pos_stop if hit_stop else pos_target
                trades.append((-1, pos_entry, pos_stop, pos_target, exit_px))
                pos_dir = 0

        if counts:
            va = value_area()
            if va is not None:
                poc_bin, val_bin, vah_bin = va
                poc_px = (poc_bin + 0.5) * bin_size
                vah_px = (vah_bin + 1) * bin_size
                val_px = val_bin * bin_size

                # reset "already took this breakout" once price comes back inside value
                if val_px <= c[i] <= vah_px:
                    long_taken = False
                    short_taken = False

                if pos_dir == 0 and i >= MIN_BARS_BEFORE_SIGNAL:
                    rng = max(day_hi - day_lo, bin_size)
                    poc_pct = (poc_px - day_lo) / rng
                    trending = poc_pct <= TREND_LO or poc_pct >= TREND_HI

                    min_risk = MIN_BREAKOUT_TICKS * bin_size
                    if trending:
                        if c[i] > vah_px + min_risk and not long_taken:
                            entry = c[i]
                            stop = vah_px
                            risk = entry - stop
                            target = entry + reward_r * risk
                            pos_dir, pos_entry, pos_stop, pos_target = 1, entry, stop, target
                            long_taken = True
                        elif c[i] < val_px - min_risk and not short_taken:
                            entry = c[i]
                            stop = val_px
                            risk = stop - entry
                            target = entry - reward_r * risk
                            pos_dir, pos_entry, pos_stop, pos_target = -1, entry, stop, target
                            short_taken = True

        day_hi = max(day_hi, h[i])
        day_lo = min(day_lo, l[i])
        for b in bins_for_bar(l[i], h[i]):
            counts[b] = counts.get(b, 0) + 1

    if pos_dir != 0:
        trades.append((pos_dir, pos_entry, pos_stop, pos_target, c[-1]))

    return trades


def run(symbol: str, reward_r: float) -> pd.DataFrame:
    cfg = INSTRUMENTS[symbol]
    df = load(cfg["path"])
    all_trades = []
    for day, day_df in df.groupby("day", sort=True):
        day_df = day_df.reset_index(drop=True)
        for d, entry, stop, target, exit_px in simulate_day(day_df, cfg["bin_size"], reward_r):
            risk = abs(entry - stop)
            raw = (exit_px - entry) if d == 1 else (entry - exit_px)
            gross_r = raw / risk
            cost_r = cfg["cost_pts"] / risk
            all_trades.append((symbol, day, d, gross_r, gross_r - cost_r))
    return pd.DataFrame(all_trades, columns=["symbol", "day", "dir", "gross_r", "net_r"])


def summarize(trades: pd.DataFrame, label: str):
    n = len(trades)
    if n == 0:
        print(f"[{label}] no trades")
        return
    win_rate = (trades["net_r"] > 0).mean()
    print(f"\n=== {label} ===")
    print(f"trades: {n}  (long {(trades['dir']==1).sum()} / short {(trades['dir']==-1).sum()})")
    print(f"win rate (net of costs): {win_rate:.1%}")
    print(f"avg R/trade: gross={trades['gross_r'].mean():+.3f}R  net={trades['net_r'].mean():+.3f}R")
    eq = trades["net_r"].cumsum()
    print(f"total net R: {trades['net_r'].sum():+.1f}R  max drawdown: {(eq-eq.cummax()).min():.1f}R")
    days = trades["day"].nunique()
    print(f"trading days with >=1 signal: {days}  (avg {n/max(days,1):.2f} trades/day)")


def main():
    for symbol in INSTRUMENTS:
        for reward_r in [1.0, 2.0]:
            trades = run(symbol, reward_r)
            summarize(trades, f"{symbol} | trend breakout, target={reward_r}R")


if __name__ == "__main__":
    main()
