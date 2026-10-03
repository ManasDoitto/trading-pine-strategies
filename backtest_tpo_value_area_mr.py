"""Validate a mechanical version of Fabio Valentini's "mean reversion in balance" model
(youtube.com/watch?v=tvERE-Beu2U, Chart Fanatics x Fabervaale) on NSE indices.

What the video actually describes (from chapters + captions, see conversation):
  - A 3-step model: Location (where is price vs. the volume-profile value area) ->
    Refinement (order-flow confirmation: aggression/absorption at that level) ->
    Execution (discretionary, "you cannot just automate it").
  - Mean reversion is applied specifically in BALANCE sessions, "usually in indices":
    price pushes outside the value area with "aggression and out of balance", and the
    read is that it "snaps back inside" -- fade the excess back toward value.
  - Risk is tight and fast: "I want to be wrong immediately" -- small invalidation-based
    stops, not the wide stops from the other video.
  - His actual edge leans on footprint/DOM order flow (bid/ask aggression), which needs
    tick-level order-book data we don't have historically for NSE. What IS testable
    mechanically is the skeleton underneath it: value-area mean reversion.

Translation to NSE, and why:
  - He says "usually in indices" -> test on BANKNIFTY / NIFTY index, not single stocks
    (also the only segment where retail NSE traders get comparable liquidity/continuity
    to what he trades on NQ/ES).
  - Dhan's historical index volume is ~70-84% zero (see research_data/bars/*.csv), so a
    true VOLUME profile is unreliable. Market Profile/TPO (time spent at each price, the
    pre-volume-profile original form of the same Auction Market Theory) needs no volume
    field at all, so that's what this builds: a developing intraday TPO profile per day,
    POC = most-time price, value area = 70% of time around POC.
  - Entry: price pokes beyond today's (developing, no-lookahead) value area high/low and
    the SAME bar closes back inside it (a rejection/excess bar) -> fade back toward
    value. Stop = just beyond the excess extreme (tight, per "wrong immediately"). Two
    targets are tested: back-to-VA-edge (conservative) and POC (the fuller "snap back").
  - Balance filter: only take the trade if the developing POC sits away from the day's
    current extremes (20th-80th percentile of today's range-so-far), i.e. today is
    rotating two-sided, not running in one direction (his explicit "not a trend day"
    condition).
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))

INSTRUMENTS = {
    # cost_pts: round-trip STT + brokerage + ~1-tick slippage each side on BANKNIFTY/NIFTY
    # futures, priced in index points (NOT the ~5bp equity-cash assumption used for the
    # NSE-stocks backtest -- these are far more liquid, tight-spread instruments).
    "BANKNIFTY": dict(path="research_data/bars/DHAN_BANKNIFTY_5m.csv", bin_size=5.0, cost_pts=4.0),
    "NIFTY":     dict(path="research_data/bars/DHAN_NIFTY_5m.csv",     bin_size=2.0, cost_pts=2.0),
}

VALUE_AREA_PCT = 0.70
MIN_BARS_BEFORE_SIGNAL = 12   # ~60 min "initial balance" on a 5m chart before we trust the profile
BALANCE_LO, BALANCE_HI = 0.20, 0.80  # developing POC must sit within this percentile of today's range-so-far
EXCESS_BUFFER_TICKS = 1.0     # in bin units, how far past the VA edge counts as a genuine poke


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(ROOT, path))
    df = df[df["volume"].notna()]
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("Asia/Kolkata")
    df = df.sort_values("dt").reset_index(drop=True)
    df["day"] = df["dt"].dt.date
    # keep regular session bars only, drop stray pre/post-session ticks some Dhan dumps include
    df = df[(df["dt"].dt.time >= pd.Timestamp("09:15").time()) & (df["dt"].dt.time <= pd.Timestamp("15:30").time())]
    return df.reset_index(drop=True)


def simulate_day(day_df: pd.DataFrame, bin_size: float, reward_mode: str):
    """reward_mode: 'va_edge' (conservative target = back to the value-area edge) or
    'poc' (target = point of control)."""
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
        return poc_bin, lo_b, hi_b  # poc, val_bin, vah_bin

    for i in range(n):
        # 1) manage open position first against this bar's range
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

        # 2) evaluate a fresh signal off the PRE-this-bar profile (no lookahead), only if flat
        if pos_dir == 0 and i >= MIN_BARS_BEFORE_SIGNAL and counts:
            va = value_area()
            if va is not None:
                poc_bin, val_bin, vah_bin = va
                poc_px = (poc_bin + 0.5) * bin_size
                vah_px = (vah_bin + 1) * bin_size
                val_px = val_bin * bin_size
                rng = max(day_hi - day_lo, bin_size)
                poc_pct = (poc_px - day_lo) / rng
                balanced = BALANCE_LO <= poc_pct <= BALANCE_HI

                if balanced:
                    excess_hi = vah_px + EXCESS_BUFFER_TICKS * bin_size
                    excess_lo = val_px - EXCESS_BUFFER_TICKS * bin_size
                    # short: this bar poked above VAH then closed back under it
                    if h[i] >= excess_hi and c[i] < vah_px:
                        entry = c[i]
                        stop = h[i] + EXCESS_BUFFER_TICKS * bin_size
                        target = (entry + poc_px) / 2.0 if reward_mode == "midpoint" else poc_px
                        if stop > entry > target:
                            pos_dir, pos_entry, pos_stop, pos_target = -1, entry, stop, target
                    # long: poked below VAL then closed back above it
                    elif l[i] <= excess_lo and c[i] > val_px:
                        entry = c[i]
                        stop = l[i] - EXCESS_BUFFER_TICKS * bin_size
                        target = (entry + poc_px) / 2.0 if reward_mode == "midpoint" else poc_px
                        if stop < entry < target:
                            pos_dir, pos_entry, pos_stop, pos_target = 1, entry, stop, target

        # 3) update the developing profile with this bar's own range (becomes visible from bar i+1)
        day_hi = max(day_hi, h[i])
        day_lo = min(day_lo, l[i])
        for b in bins_for_bar(l[i], h[i]):
            counts[b] = counts.get(b, 0) + 1

    if pos_dir != 0:
        trades.append((pos_dir, pos_entry, pos_stop, pos_target, c[-1]))

    return trades


def run(symbol: str, reward_mode: str) -> pd.DataFrame:
    cfg = INSTRUMENTS[symbol]
    df = load(cfg["path"])
    all_trades = []
    for day, day_df in df.groupby("day", sort=True):
        day_df = day_df.reset_index(drop=True)
        for d, entry, stop, target, exit_px in simulate_day(day_df, cfg["bin_size"], reward_mode):
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
        for reward_mode in ["midpoint", "poc"]:
            trades = run(symbol, reward_mode)
            summarize(trades, f"{symbol} | target={reward_mode}")


if __name__ == "__main__":
    main()
