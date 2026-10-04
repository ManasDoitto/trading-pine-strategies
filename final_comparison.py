"""Final consolidated backtest: v4.0/v0.4 baselines vs v5.0 SHA-ADX Hybrid."""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from run_exact_backtests import fetch_or_load, compute_stats, CACHE_DIR, print_stats
from trading_agents.core import signals as v40, signals_v04 as v04, signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()


def print_comparison(name, baseline_stats, v50_stats):
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")
    print(f"  {'Metric':<14} {'Baseline':>14} {'v5.0':>14} {'Delta':>14}")
    print(f"  {'-'*66}")
    metrics = [("trades", "trades"), ("wins", "wins"), ("winrate", "winrate"),
               ("pf", "pf"), ("net", "net"), ("max_dd", "max_dd"), ("sharpe", "sharpe")]
    for label, key in metrics:
        b = baseline_stats[key]
        v = v50_stats[key]
        b_str = f"{b:.1f}" if isinstance(b, float) else str(b)
        v_str = f"{v:.1f}" if isinstance(v, float) else str(v)
        if isinstance(b, float):
            delta = v - b
            delta_str = f"{delta:+.1f} ({100*delta/b:.0f}%)" if b != 0 else f"{delta:+.1f}"
        else:
            delta_str = "N/A"
        print(f"  {label:<14} {b_str:>14} {v_str:>14} {delta_str:>14}")


def run_comparison(underlying, baseline_mod, baseline_fn_name, baseline_warmup):
    """Run baseline and v5.0 on the same instrument."""
    df = fetch_or_load(underlying, interval=5, days=900)
    if df.empty:
        return None, None

    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])
    p_base = cfg["strategy"][underlying]

    # Baseline
    if baseline_fn_name == "v40":
        frame = v40.v40_frame(bars, p_base)
        trades, _, _ = v40.simulate(frame, p_base, start=v40.WARMUP_BARS, next_open=True)
    elif baseline_fn_name == "v04":
        frame = v04.v04_frame(bars, p_base)
        sim = v04.simulate(frame, p_base, start=v04.WARMUP_BARS)
        trades = sim["trades"]

    baseline_stats = compute_stats(trades)

    # v5.0
    p_v50 = v50.v50_params_for(underlying, cfg)
    frame_v50 = v50.v50_frame(bars, p_v50)
    v50_trades, _, _ = v50.simulate(frame_v50, p_v50, start=v50.WARMUP_BARS)
    v50_stats = compute_stats(v50_trades)

    return baseline_stats, v50_stats


def walk_forward_compare(underlying, window_days=90, step_days=30):
    """Compare baseline vs v5.0 across walk-forward windows."""
    df = fetch_or_load(underlying, interval=5, days=900)
    if df.empty:
        return
    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])
    p_base = cfg["strategy"][underlying]
    p_v50 = v50.v50_params_for(underlying, cfg)

    # Determine which baseline to use
    if underlying in ("CRUDEOIL", "SILVER", "SILVERM"):
        baseline_mod = v40
        baseline_fn = "v40"
        warmup = v40.WARMUP_BARS
    else:
        baseline_mod = v04
        baseline_fn = "v04"
        warmup = v04.WARMUP_BARS

    # Build frames once
    if baseline_fn == "v40":
        frame_base = v40.v40_frame(bars, p_base)
    else:
        frame_base = v04.v04_frame(bars, p_base)
    frame_v50 = v50.v50_frame(bars, p_v50)

    all_times = bars["time"].values
    start = pd.Timestamp(all_times[warmup])
    end = pd.Timestamp(all_times[-1])
    window = pd.Timedelta(days=window_days)
    step = pd.Timedelta(days=step_days)

    print(f"\n  Walk-forward comparison: {underlying}")
    print(f"  {'Window':<14} {'Baseline PF':>12} {'v5.0 PF':>10} {'Baseline Net':>12} {'v5.0 Net':>10} {'B trades':>9} {'V trades':>9}")

    base_pfs, v50_pfs, base_nets, v50_nets = [], [], [], []
    while start < end:
        mask = (bars["time"] >= start) & (bars["time"] < start + window)
        idxs = np.where(mask.values)[0]
        if len(idxs) > warmup:
            w_start = max(idxs[0], warmup)
            # Baseline
            if baseline_fn == "v40":
                bt, _, _ = baseline_mod.simulate(frame_base, p_base, start=w_start, next_open=True)
            else:
                sim = baseline_mod.simulate(frame_base, p_base, start=w_start)
                bt = sim["trades"]
            bt_in = [t for t in bt if pd.Timestamp(t["entry_time"]) >= start
                     and pd.Timestamp(t["entry_time"]) < start + window]
            bs = compute_stats(bt_in)
            # v5.0
            vt, _, _ = v50.simulate(frame_v50, p_v50, start=w_start)
            vt_in = [t for t in vt if pd.Timestamp(t["entry_time"]) >= start
                     and pd.Timestamp(t["entry_time"]) < start + window]
            vs = compute_stats(vt_in)
            print(f"  {start.strftime('%Y-%m-%d'):<14} {bs['pf']:>12.3f} {vs['pf']:>10.3f} "
                  f"{bs['net']:>12.1f} {vs['net']:>10.1f} {bs['trades']:>9} {vs['trades']:>9}")
            if bs["pf"] > 0 or bs["trades"] > 0:
                base_pfs.append(bs["pf"])
            if vs["pf"] > 0 or vs["trades"] > 0:
                v50_pfs.append(vs["pf"])
            if bs["trades"] > 0:
                base_nets.append(bs["net"])
            if vs["trades"] > 0:
                v50_nets.append(vs["net"])
        start += step

    print(f"\n  Baseline: avg PF={np.mean(base_pfs):.2f}, avg net={np.mean(base_nets):.1f}, "
          f"profitable={sum(1 for n in base_nets if n > 0)}/{len(base_nets)}")
    print(f"  v5.0:     avg PF={np.mean(v50_pfs):.2f}, avg net={np.mean(v50_nets):.1f}, "
          f"profitable={sum(1 for n in v50_nets if n > 0)}/{len(v50_nets)}")


if __name__ == "__main__":
    print("=" * 70)
    print("  FINAL CONSOLIDATED BACKTEST: Baselines vs v5.0 SHA-ADX Hybrid")
    print("=" * 70)

    # Full backtest comparisons
    for inst, baseline_fn in [("CRUDEOIL", "v40"), ("BANKNIFTY", "v04")]:
        # Fetch/cache data
        fetch_or_load(inst, interval=5, days=900)
        bars = pd.read_csv(f'journal_data/cache/backtest/{inst}_5min.csv')
        bars["time"] = pd.to_datetime(bars["time"])

        # Baseline
        if baseline_fn == "v40":
            frame = v40.v40_frame(bars, cfg["strategy"][inst])
            trades, _, _ = v40.simulate(frame, cfg["strategy"][inst], start=v40.WARMUP_BARS, next_open=True)
        else:
            frame = v04.v04_frame(bars, cfg["strategy"][inst])
            sim = v04.simulate(frame, cfg["strategy"][inst], start=v04.WARMUP_BARS)
            trades = sim["trades"]
        base_stats = compute_stats(trades)

        # v5.0
        p50 = v50.v50_params_for(inst, cfg)
        frame50 = v50.v50_frame(bars, p50)
        v50_trades, _, _ = v50.simulate(frame50, p50, start=v50.WARMUP_BARS)
        v50_stats = compute_stats(v50_trades)

        print_comparison(f"{inst} ({baseline_fn} vs v5.0)", base_stats, v50_stats)

    # Silver
    fetch_or_load("SILVER", interval=5, days=900)
    bars = pd.read_csv('journal_data/cache/backtest/SILVER_5min.csv')
    bars["time"] = pd.to_datetime(bars["time"])

    frame = v40.v40_frame(bars, cfg["strategy"]["SILVER"])
    trades, _, _ = v40.simulate(frame, cfg["strategy"]["SILVER"], start=v40.WARMUP_BARS, next_open=True)
    base_stats = compute_stats(trades)

    p50 = v50.v50_params_for("SILVER", cfg)
    frame50 = v50.v50_frame(bars, p50)
    v50_trades, _, _ = v50.simulate(frame50, p50, start=v50.WARMUP_BARS)
    v50_stats = compute_stats(v50_trades)

    print_comparison("SILVER (v4.0 vs v5.0)", base_stats, v50_stats)

    # Walk-forward comparisons
    print("\n" + "=" * 70)
    print("  WALK-FORWARD COMPARISON")
    print("=" * 70)
    for inst in ["CRUDEOIL", "BANKNIFTY", "SILVER"]:
        walk_forward_compare(inst)
