"""Focused BankNifty optimization for v5.0."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from run_exact_backtests import compute_stats
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()
df = pd.read_csv('journal_data/cache/backtest/BANKNIFTY_5min.csv', parse_dates=['time'])
bars = df.copy()
bars['time'] = pd.to_datetime(bars['time'])

# Base params from config
base = V50 = v50.v50_params_for('BANKNIFTY', cfg)

print(f"v0.4 baseline: PF=1.298, net=757.7 (reference)\n")

# Test 1: Flip mode, varying ADX, no quality filters
print("=== Flip mode (no QF) ===")
for adx in [25, 30, 35, 40, 45]:
    for rr in [2.5, 3.0, 3.5]:
        p = dict(base)
        p['entry_mode'] = 'flip'
        p['adx_min'] = float(adx)
        p['rr'] = rr
        p['use_quality_filters'] = False
        frame = v50.v50_frame(bars, p)
        trades, _, _ = v50.simulate(frame, p, start=v50.WARMUP_BARS)
        s = compute_stats(trades)
        if s['trades'] >= 10:
            print(f"  ADX={adx:>2} RR={rr:>3}: {s['trades']:>4} trades, {s['winrate']:>6}, PF={s['pf']:>6}, net={s['net']:>8.1f}, maxDD={s['max_dd']:>7.1f}")

# Test 2: Flip mode + wick-only filter (no VWAP)
print("\n=== Flip mode + wick-only filter ===")
for adx in [25, 30, 35, 40]:
    for rr in [2.5, 3.0, 3.5]:
        p = dict(base)
        p['entry_mode'] = 'flip'
        p['adx_min'] = float(adx)
        p['rr'] = rr
        p['wick_frac'] = 0.3  # More lenient wick (0.3 instead of 0.5)
        # Override: only use wick filter, not VWAP
        p['use_quality_filters'] = True
        frame = v50.v50_frame(bars, p)
        # Override: manually require wick but skip VWAP
        frame['ok_l'] = frame['ok_l'] & frame['big_lower_wick']
        frame['ok_s'] = frame['ok_s'] & frame['big_upper_wick']
        trades, _, _ = v50.simulate(frame, p, start=v50.WARMUP_BARS)
        s = compute_stats(trades)
        if s['trades'] >= 5:
            print(f"  ADX={adx:>2} RR={rr:>3}: {s['trades']:>4} trades, {s['winrate']:>6}, PF={s['pf']:>6}, net={s['net']:>8.1f}, maxDD={s['max_dd']:>7.1f}")

# Test 3: Breakout mode, varying lookback and ADX
print("\n=== Breakout mode ===")
for bo in [5, 10, 15, 20]:
    for adx in [25, 30, 35]:
        p = dict(base)
        p['entry_mode'] = 'breakout'
        p['breakout_lookback'] = bo
        p['adx_min'] = float(adx)
        p['rr'] = 3.0
        p['use_quality_filters'] = False
        frame = v50.v50_frame(bars, p)
        trades, _, _ = v50.simulate(frame, p, start=v50.WARMUP_BARS)
        s = compute_stats(trades)
        if s['trades'] >= 5:
            print(f"  BO={bo:>2} ADX={adx:>2}: {s['trades']:>4} trades, {s['winrate']:>6}, PF={s['pf']:>6}, net={s['net']:>8.1f}, maxDD={s['max_dd']:>7.1f}")

# Test 4: Flip mode + sha_min_hold variations
print("\n=== Flip mode, varying sha_min_hold ===")
for hold in [3, 5, 8, 10, 15]:
    for adx in [30, 35, 40]:
        p = dict(base)
        p['entry_mode'] = 'flip'
        p['adx_min'] = float(adx)
        p['sha_min_hold'] = hold
        p['rr'] = 3.0
        p['use_quality_filters'] = False
        frame = v50.v50_frame(bars, p)
        trades, _, _ = v50.simulate(frame, p, start=v50.WARMUP_BARS)
        s = compute_stats(trades)
        if s['trades'] >= 5:
            print(f"  hold={hold:>2} ADX={adx:>2}: {s['trades']:>4} trades, {s['winrate']:>6}, PF={s['pf']:>6}, net={s['net']:>8.1f}, maxDD={s['max_dd']:>7.1f}")
