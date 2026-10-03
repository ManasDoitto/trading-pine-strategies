"""Short-hold BTC perpetual breakout system: the middle ground between the 5m chart-
pattern family already proven dead (archived lab, 0/32 profitable) and the daily
swing-trend system from the last round (works, but holds for days-to-weeks, which this
user explicitly doesn't want). Same Donchian-breakout-with-ATR-trail engine as
backtest_btc_perp_trend.py, generalized to:
  - run on 1h or 4h bars instead of daily
  - cap the maximum holding period in bars (force a short hold regardless of trail)
  - report results sized for a small ($100) account: cost as % of equity per trade,
    and a feasibility check against Delta Exchange's practical minimums
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from backtest_btc_perp_trend import load_klines, DATA_DIR, TAKER_FEE, atr

TF_FILES = {"1h": "btcusdt_perp_1h.json", "4h": "btcusdt_perp_4h.json"}
TF_PER_DAY = {"1h": 24, "4h": 6}


def simulate(df: pd.DataFrame, entry_n: int, atr_mult: float, max_hold_bars: int | None) -> pd.DataFrame:
    d = df.reset_index(drop=True)
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    n = len(d)
    a = atr(d, 14)
    upper = pd.Series(h).rolling(entry_n).max().shift(1).to_numpy()
    lower = pd.Series(l).rolling(entry_n).min().shift(1).to_numpy()

    trades = []
    pos = 0
    entry_px = hh = ll = 0.0
    entry_i = 0
    warmup = entry_n + 1

    for i in range(warmup, n):
        if pos == 1:
            hh = max(hh, h[i])
            trail = hh - atr_mult * a[i]
            timed_out = max_hold_bars is not None and (i - entry_i) >= max_hold_bars
            if l[i] <= trail or timed_out:
                exit_px = min(trail, c[i]) if l[i] <= trail else c[i]
                gross_r = (exit_px - entry_px) / entry_px
                trades.append((1, entry_i, i, i - entry_i, entry_px, exit_px, gross_r))
                pos = 0
        elif pos == -1:
            ll = min(ll, l[i])
            trail = ll + atr_mult * a[i]
            timed_out = max_hold_bars is not None and (i - entry_i) >= max_hold_bars
            if h[i] >= trail or timed_out:
                exit_px = max(trail, c[i]) if h[i] >= trail else c[i]
                gross_r = (entry_px - exit_px) / entry_px
                trades.append((-1, entry_i, i, i - entry_i, entry_px, exit_px, gross_r))
                pos = 0

        if pos == 0:
            if c[i] > upper[i] and not np.isnan(upper[i]):
                pos, entry_px, hh, entry_i = 1, c[i], h[i], i
            elif c[i] < lower[i] and not np.isnan(lower[i]):
                pos, entry_px, ll, entry_i = -1, c[i], l[i], i

    return pd.DataFrame(trades, columns=["dir", "entry_i", "exit_i", "hold_bars", "entry_px", "exit_px", "gross_r"])


def summarize(trades: pd.DataFrame, bars_per_day: int, label: str):
    print(f"\n=== {label} ===")
    n = len(trades)
    if n == 0:
        print("no trades"); return
    net_r = trades["gross_r"] - 2 * TAKER_FEE  # entry + exit taker fee
    win_rate = (net_r > 0).mean()
    avg_hold_days = trades["hold_bars"].mean() / bars_per_day
    eq = (1 + net_r).cumprod()
    total_return = eq.iloc[-1] - 1
    span_bars = trades["exit_i"].max() - trades["entry_i"].min()
    years = span_bars / bars_per_day / 365.25
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 and eq.iloc[-1] > 0 else float("nan")
    running_max = eq.cummax()
    dd = (eq / running_max - 1).min()
    print(f"trades: {n}  (long {(trades['dir']==1).sum()} / short {(trades['dir']==-1).sum()})")
    print(f"avg hold: {avg_hold_days:.2f} days ({trades['hold_bars'].mean():.1f} bars)  max hold: {trades['hold_bars'].max()} bars")
    print(f"win rate (net): {win_rate:.1%}")
    print(f"total net return (compounded, full size each trade): {total_return:+.1%}  CAGR: {cagr:+.1%}  max DD: {dd:.1%}")
    print(f"avg net return/trade: {net_r.mean():+.3%}   fee as % of avg |gross move|: "
          f"{2*TAKER_FEE/trades['gross_r'].abs().mean():.1%}" if trades['gross_r'].abs().mean() > 0 else "")


def main():
    for tf in ["4h", "1h"]:
        df = load_klines(os.path.join(DATA_DIR, TF_FILES[tf]))
        bars_per_day = TF_PER_DAY[tf]
        print(f"\n########## {tf} bars: {len(df)}  ({df['day'].iloc[0]} .. {df['day'].iloc[-1]}) ##########")
        configs = [
            (20, 2.5, None),
            (20, 1.5, bars_per_day * 1),   # cap ~1 day
            (20, 1.5, bars_per_day * 3),   # cap ~3 days
            (10, 1.5, bars_per_day * 1),
            (10, 1.0, bars_per_day * 1),
        ]
        for n, mult, cap in configs:
            trades = simulate(df, n, mult, cap)
            cap_label = f"max {cap} bars (~{cap/bars_per_day:.1f}d)" if cap else "no cap (ATR trail only)"
            summarize(trades, bars_per_day, f"{tf} Donchian{n} ATRx{mult}, {cap_label}")


if __name__ == "__main__":
    main()
