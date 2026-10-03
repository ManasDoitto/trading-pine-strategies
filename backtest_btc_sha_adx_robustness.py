"""Robustness check on the one promising config from backtest_btc_sha_adx_hybrid.py:
1h base bars, SHA-flip entry, 4h HTF ADX>=30 gate, vol_filter OFF, RR=3 (CrudeOil's
exact live parameters). A single lucky config out of six is not "trustable" on its own --
this checks:
  1. Parameter sensitivity: is performance a stable plateau across nearby ADX/RR values,
     or an isolated spike (overfitting tell)?
  2. Temporal stability: walk-forward split into halves/thirds -- does the edge show up
     consistently across different market regimes, or just one lucky stretch?
"""
from __future__ import annotations

import pandas as pd

from backtest_btc_sha_adx_hybrid import load_bars, btc_params, run, TAKER_FEE


def trade_net_r(trades: pd.DataFrame) -> pd.Series:
    r_mult = trades["pnl_pts"] / trades["risk_pts"]
    cost_r = (2 * TAKER_FEE) / (trades["risk_pts"] / trades["entry"])
    return r_mult - cost_r


def quick_stats(trades: pd.DataFrame) -> dict:
    if len(trades) == 0:
        return dict(n=0, win=float("nan"), pf=float("nan"), avg_r=float("nan"))
    net_r = trade_net_r(trades)
    win = (net_r > 0).mean()
    pos, neg = net_r[net_r > 0].sum(), -net_r[net_r < 0].sum()
    pf = pos / neg if neg > 0 else float("inf")
    return dict(n=len(trades), win=win, pf=pf, avg_r=net_r.mean())


def main():
    bars_1h = load_bars("btcusdt_perp_1h.json")

    print("### 1. Parameter sensitivity grid (1h base, flip, vol_filter=OFF, HTF=4h) ###")
    print(f"{'ADX_min':>8} {'RR':>5} {'n':>5} {'win%':>7} {'PF':>6} {'avg_R':>8}")
    for adx_min in [20, 25, 30, 35, 40]:
        for rr in [2.0, 2.5, 3.0, 3.5, 4.0]:
            p = btc_params("flip", False, adx_min, rr)
            trades = run(bars_1h, 240, p)
            s = quick_stats(trades)
            print(f"{adx_min:>8} {rr:>5.1f} {s['n']:>5} {s['win']*100:>6.1f}% {s['pf']:>6.2f} {s['avg_r']:>+8.3f}")

    print("\n### 2. Temporal stability -- same config (ADX>=30, RR=3), split into thirds ###")
    p = btc_params("flip", False, 30.0, 3.0)
    full_trades = run(bars_1h, 240, p)
    full_trades = full_trades.sort_values("entry_time").reset_index(drop=True)
    n = len(full_trades)
    thirds = [full_trades.iloc[:n//3], full_trades.iloc[n//3:2*n//3], full_trades.iloc[2*n//3:]]
    labels = ["first third", "second third", "third third"]
    for lab, sub in zip(labels, thirds):
        if len(sub) == 0:
            print(f"{lab}: no trades"); continue
        s = quick_stats(sub)
        span = f"{sub['entry_time'].min().date()} .. {sub['entry_time'].max().date()}"
        print(f"{lab} ({span}): n={s['n']} win={s['win']*100:.1f}% PF={s['pf']:.2f} avg_R={s['avg_r']:+.3f}")

    print("\n### 3. Same split by calendar year ###")
    full_trades["year"] = full_trades["entry_time"].dt.year
    for yr, sub in full_trades.groupby("year"):
        s = quick_stats(sub)
        print(f"{yr}: n={s['n']} win={s['win']*100:.1f}% PF={s['pf']:.2f} avg_R={s['avg_r']:+.3f}")


if __name__ == "__main__":
    main()
