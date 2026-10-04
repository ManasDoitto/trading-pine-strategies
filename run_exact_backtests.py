"""Backtest runner using the exact trading_agents strategy ports.
Caches Dhan OHLC data to CSV so results are reproducible without re-fetching.

Usage:
    python run_exact_backtests.py                # run all baselines
    python run_exact_backtests.py --new          # also run the new strategy
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

# Make trading_agents importable
sys.path.insert(0, str(Path(__file__).parent))
from trading_agents.core.config import load_config
from trading_agents.core.dhan_client import get_dhan_client
from trading_agents.core.market_data import intraday_bars
from trading_agents.core.instruments import front_future, reference_series
from trading_agents.core import signals as v40
from trading_agents.core import signals_v04 as v04
from trading_agents.core import signals_v50 as v50_module
from trading_agents.core.signals_v50 import v50_params_for

CACHE_DIR = Path("D:/Trading code-Claude/journal_data/cache/backtest")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_path(underlying, interval=5):
    return CACHE_DIR / f"{underlying}_{interval}min.csv"


def fetch_or_load(underlying, interval=5, start=None, end=None, days=600):
    """Fetch intraday bars, caching to CSV. Returns DataFrame with time, open, high, low, close, volume."""
    path = cache_path(underlying, interval)
    if path.exists():
        df = pd.read_csv(path, parse_dates=["time"])
        print(f"  [CACHE] Loaded {len(df)} bars from {path.name} ({df['time'].iloc[0]} to {df['time'].iloc[-1]})")
        return df

    cfg = load_config()["instruments"][underlying]
    ref = reference_series(underlying)
    if ref is None:
        print(f"  ERROR: no reference series for {underlying}")
        return pd.DataFrame()

    if start is None:
        start = datetime.now() - timedelta(days=days)
    if end is None:
        end = datetime.now()

    client = get_dhan_client()
    ref_str = f"sec_id={ref['security_id']} seg={ref['segment']} inst={ref['instrument']}"
    print(f"  Fetching {underlying} ({ref_str}) {start.date()} to {end.date()} from Dhan...")
    df = intraday_bars(
        client, ref["security_id"], ref["segment"], ref["instrument"],
        start, end, interval=interval
    )
    if df.empty:
        print(f"  ERROR: no data returned for {underlying}")
        return df

    df.to_csv(path, index=False)
    print(f"  [SAVED] {len(df)} bars cached to {path.name}")
    return df


def compute_stats(trades):
    """Compute performance stats from a list of trade dicts."""
    if not trades:
        return dict(trades=0, wins=0, losses=0, winrate=0, pf=0, net=0,
                    avg_win=0, avg_loss=0, max_dd=0)

    pnls = [t["pnl_pts"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_w = sum(wins) if wins else 0
    gross_l = abs(sum(losses)) if losses else 0.001
    pf = gross_w / gross_l if gross_l > 0 else float("inf")

    # Max drawdown (running equity)
    equity = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity)
    dd_series = running_max - equity
    max_dd = float(np.max(dd_series)) if len(dd_series) > 0 else 0

    # Daily equity for Sharpe
    trade_days = pd.Series([t["entry_time"].date() for t in trades])
    daily_pnl = pd.Series(pnls).groupby(trade_days).sum()
    daily_pnl = daily_pnl.reindex(pd.date_range(daily_pnl.index.min(), daily_pnl.index.max(), freq="D").date).fillna(0)
    if len(daily_pnl) > 1:
        sharpe = daily_pnl.mean() / daily_pnl.std() * np.sqrt(252)
    else:
        sharpe = 0

    return dict(
        trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        winrate=f"{100*len(wins)/max(len(trades),1):.1f}%",
        pf=round(pf, 3),
        net=round(sum(pnls), 1),
        avg_win=round(gross_w/len(wins), 1) if wins else 0,
        avg_loss=round(gross_l/len(losses), 1) if losses else 0,
        max_dd=round(max_dd, 1),
        sharpe=round(sharpe, 2),
    )


def print_stats(name, stats):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    for k, v in stats.items():
        print(f"  {k:12s}: {v}")


def run_v40_sha_flip():
    """Run v4.0 SHA flip on CrudeOil futures (front month)."""
    print("\n--- v4.0 SHA flip (CrudeOil) ---")
    df = fetch_or_load("CRUDEOIL", interval=5, days=700)
    if df.empty:
        return None

    cfg = load_config()
    p = cfg["strategy"]["CRUDEOIL"]
    bars = df.rename(columns={"time": "time"}).copy()
    bars["time"] = pd.to_datetime(bars["time"])

    frame = v40.v40_frame(bars, p)
    trades, pos, pending = v40.simulate(frame, p, start=v40.WARMUP_BARS)
    stats = compute_stats(trades)
    print_stats("v4.0 SHA flip (CrudeOil)", stats)
    return trades, frame


def run_v04_banknifty():
    """Run v0.4 BankNifty EMA pullback + 15m ADX gate."""
    print("\n--- v0.4 BankNifty EMA pullback ---")
    df = fetch_or_load("BANKNIFTY", interval=5, days=700)
    if df.empty:
        return None

    cfg = load_config()
    p = cfg["strategy"]["BANKNIFTY"]
    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])

    frame = v04.v04_frame(bars, p)
    sim = v04.simulate(frame, p, start=v04.WARMUP_BARS)
    trades = sim["trades"]
    stats = compute_stats(trades)
    print_stats("v0.4 BankNifty EMA pullback", stats)
    return trades, frame


def run_walk_forward_v40():
    """Walk-forward analysis: 90-day rolling windows on CrudeOil v4.0."""
    print("\n--- Walk-forward: v4.0 SHA flip (CrudeOil, 90-day windows) ---")
    df = fetch_or_load("CRUDEOIL", interval=5, days=700)
    if df.empty:
        return

    cfg = load_config()
    p = cfg["strategy"]["CRUDEOIL"]
    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])

    frame = v40.v40_frame(bars, p)
    _run_walk_forward(frame, bars, p, v40, v40.WARMUP_BARS, "v4.0 SHA flip")


def run_walk_forward_v50():
    """Walk-forward analysis: 90-day rolling windows on v5.0 (CrudeOil)."""
    print("\n--- Walk-forward: v5.0 SHA-ADX Hybrid (CrudeOil, 90-day windows) ---")
    df = fetch_or_load("CRUDEOIL", interval=5, days=700)
    if df.empty:
        return

    cfg = load_config()
    p = v50_params_for("CRUDEOIL", cfg)
    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])

    frame = v50_module.v50_frame(bars, p)
    _run_walk_forward(frame, bars, p, v50_module, v50_module.WARMUP_BARS, "v5.0 SHA-ADX Hybrid")


def _run_walk_forward(frame, bars, p, mod, warmup, label):
    """Shared walk-forward runner."""
    all_times = bars["time"].values
    window_td = pd.Timedelta(days=90)
    step_td = pd.Timedelta(days=30)

    start = pd.Timestamp(all_times[warmup])
    end = pd.Timestamp(all_times[-1])
    results = []
    while start < end:
        mask = (bars["time"] >= start) & (bars["time"] < start + window_td)
        idxs = np.where(mask.values)[0]
        if len(idxs) > warmup:
            w_start = max(idxs[0], warmup)
            try:
                trades, _, _ = mod.simulate(frame, p, start=w_start, next_open=True)
            except TypeError:
                trades, _, _ = mod.simulate(frame, p, start=w_start)

            in_window = [t for t in trades
                         if pd.Timestamp(t["entry_time"]) >= start
                         and pd.Timestamp(t["entry_time"]) < start + window_td]
            s = compute_stats(in_window)
            results.append(dict(window_start=start.strftime("%Y-%m-%d"), **s))
        start += step_td

    print(f"\n  {'Window':<14} {'Trades':>7} {'Win%':>6} {'PF':>6} {'Net':>10} {'MaxDD':>8}")
    for r in results:
        print(f"  {r['window_start']:<14} {r['trades']:>7} {r['winrate']:>6} {r['pf']:>6} {r['net']:>10.1f} {r['max_dd']:>8.1f}")


def run_v50_hybrid():
    """Run v5.0 SHA-ADX Hybrid on all instruments with cached data."""
    print("\n--- v5.0 SHA-ADX Hybrid ---")
    cfg = load_config()

    for underlying in ["CRUDEOIL", "BANKNIFTY", "SILVER", "SILVERM"]:
        cache_file = CACHE_DIR / f"{underlying}_5min.csv"
        if not cache_file.exists():
            print(f"  {underlying}: no cached data, skipping")
            continue

        print(f"\n  Testing on {underlying}...")
        df = pd.read_csv(cache_file, parse_dates=["time"])
        bars = df.copy()
        bars["time"] = pd.to_datetime(bars["time"])

        p = v50_params_for(underlying, cfg)
        frame = v50_module.v50_frame(bars, p)
        trades, pos, pending = v50_module.simulate(frame, p, start=v50_module.WARMUP_BARS)

        stats = compute_stats(trades)
        print_stats(f"v5.0 SHA-ADX Hybrid ({underlying})", stats)


if __name__ == "__main__":
    print("=" * 60)
    print("  EXACT BACKTESTS (using trading_agents ports)")
    print("=" * 60)

    # Baseline 1: v4.0 SHA flip on CrudeOil
    crude_result = run_v40_sha_flip()

    # Baseline 2: v0.4 BankNifty
    bn_result = run_v04_banknifty()

    # Fetch Silver data for additional testing
    print("\n--- Fetching Silver data ---")
    fetch_or_load("SILVER", interval=5, days=700)

    # Walk-forward v4.0 (CrudeOil)
    run_walk_forward_v40()

    # Run v5.0 SHA-ADX Hybrid
    run_v50_hybrid()

    # Walk-forward v5.0 (CrudeOil)
    run_walk_forward_v50()

    print("\nDone.")
