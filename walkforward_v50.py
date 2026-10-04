"""Walk-forward validation for v5.0 SHA-ADX Hybrid.

Verifies that the optimized parameters are robust across time windows,
not just overfit to the full backtest period.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from run_exact_backtests import fetch_or_load, compute_stats, CACHE_DIR
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()


def walk_forward(underlying, window_days=90, step_days=30):
    cache_file = CACHE_DIR / f"{underlying}_5min.csv"
    if not cache_file.exists():
        print(f"  {underlying}: fetching data...")
        fetch_or_load(underlying, interval=5, days=900)
    df = pd.read_csv(cache_file, parse_dates=["time"])
    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])

    p = v50.v50_params_for(underlying, cfg)
    frame = v50.v50_frame(bars, p)

    all_times = bars["time"].values
    warmup = v50.WARMUP_BARS
    window = pd.Timedelta(days=window_days)
    step = pd.Timedelta(days=step_days)

    start = pd.Timestamp(all_times[warmup])
    end = pd.Timestamp(all_times[-1])
    results = []

    while start < end:
        mask = (bars["time"] >= start) & (bars["time"] < start + window)
        idxs = np.where(mask.values)[0]
        if len(idxs) > warmup:
            w_start = max(idxs[0], warmup)
            trades, _, _ = v50.simulate(frame, p, start=w_start)
            in_window = [t for t in trades
                         if pd.Timestamp(t["entry_time"]) >= start
                         and pd.Timestamp(t["entry_time"]) < start + window]
            s = compute_stats(in_window)
            results.append(dict(window_start=start.strftime("%Y-%m-%d"),
                                window_end=(start + window).strftime("%Y-%m-%d"), **s))
        start += step

    if not results:
        print(f"  {underlying}: no walk-forward results")
        return

    pf_values = [r["pf"] for r in results]
    win_rates = [float(str(r["winrate"]).rstrip('%')) if r["trades"] > 0 else 0.0 for r in results]
    n_trades = [r["trades"] for r in results]
    net_values = [r["net"] for r in results]

    print(f"\n  Walk-forward: v5.0 SHA-ADX Hybrid ({underlying})")
    print(f"  {'Window':<14} {'To':<14} {'Trades':>7} {'Win%':>6} {'PF':>6} {'Net':>10} {'MaxDD':>8}")
    for r in results:
        print(f"  {r['window_start']:<14} {r['window_end']:<14} {r['trades']:>7} {r['winrate']:>6} {r['pf']:>6} {r['net']:>10.1f} {r['max_dd']:>8.1f}")

    positive = sum(1 for r in results if r["net"] > 0)
    positive_pf = [r for r in results if r["pf"] > 1.0]
    print(f"\n  Summary: {len(results)} windows, avg PF={np.mean(pf_values):.2f} "
          f"(min={min(pf_values):.2f}, max={max(pf_values):.2f}), "
          f"avg win%={np.mean(win_rates):.1f}%, avg trades={np.mean(n_trades):.0f}")
    print(f"  Profitable windows (positive net): {positive}/{len(results)} ({100*positive/len(results):.0f}%)")
    print(f"  Windows with PF > 1.0: {len(positive_pf)}/{len(results)} ({100*len(positive_pf)/len(results):.0f}%)")


if __name__ == "__main__":
    print("=" * 70)
    print("  v5.0 WALK-FORWARD VALIDATION (With session-end exit + ADX gate)")
    print("=" * 70)

    for underlying in ["CRUDEOIL", "BANKNIFTY", "SILVER"]:
        walk_forward(underlying)
