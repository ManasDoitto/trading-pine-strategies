"""Test additional filters for BankNifty v5.0."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, '.')
from run_exact_backtests import compute_stats
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()
df = pd.read_csv('journal_data/cache/backtest/BANKNIFTY_5min.csv', parse_dates=['time'])
bars = df.copy()
bars['time'] = pd.to_datetime(bars['time'])

base = v50.v50_params_for('BANKNIFTY', cfg)
base['entry_mode'] = 'flip'
base['use_quality_filters'] = False

# Build base frame
frame = v50.v50_frame(bars, base)

# v0.4 baseline for reference
from trading_agents.core import signals_v04 as v04
p04 = cfg['strategy']['BANKNIFTY']
frame04 = v04.v04_frame(bars, p04)
sim04 = v04.simulate(frame04, p04, start=v04.WARMUP_BARS)
s04 = compute_stats(sim04['trades'])
print(f"v0.4 baseline:          {s04['trades']} trades, PF={s04['pf']}, net={s04['net']}, win%={s04['winrate']}")

# Current best: ADX=30, hold=3, RR=3.0
base['adx_min'] = 30.0
base['sha_min_hold'] = 3
base['rr'] = 3.0
trades, _, _ = v50.simulate(frame, base, start=v50.WARMUP_BARS)
s = compute_stats(trades)
print(f"v5.0 ADX30 hold3:       {s['trades']} trades, PF={s['pf']}, net={s['net']}, win%={s['winrate']}")

# Test 1: Volatility regime filter (ATR > ATR_SMA50)
print("\n=== With volatility regime filter (ATR > ATR_SMA50) ===")
frame['atr_sma50'] = frame['atr'].rolling(50).mean()
frame['vol_regime_ok'] = frame['atr'] > frame['atr_sma50']
f1 = frame.copy()
f1['ok_l'] = f1['ok_l'] & f1['vol_regime_ok']
f1['ok_s'] = f1['ok_s'] & f1['vol_regime_ok']
trades, _, _ = v50.simulate(f1, base, start=v50.WARMUP_BARS)
s = compute_stats(trades)
print(f"  ADX30 hold3 + vol:   {s['trades']} trades, PF={s['pf']}, net={s['net']}, win%={s['winrate']}")

# Test 2: Momentum confirmation (flip bar closes in top/bottom 30% of range)
print("\n=== With momentum confirmation (close in top/bottom 30% of bar) ===")
bar_rng = np.maximum(frame['high'] - frame['low'], 0.05)
frame['close_pos'] = (frame['close'] - frame['low']) / bar_rng  # 0=lowest close, 1=highest close
frame['momentum_l'] = frame['close_pos'] > 0.5  # Long flip: close in upper half
frame['momentum_s'] = frame['close_pos'] < 0.5   # Short flip: close in lower half
f2 = frame.copy()
f2['ok_l'] = f2['ok_l'] & f2['momentum_l']
f2['ok_s'] = f2['ok_s'] & f2['momentum_s']
trades, _, _ = v50.simulate(f2, base, start=v50.WARMUP_BARS)
s = compute_stats(trades)
print(f"  ADX30 hold3 + mom:   {s['trades']} trades, PF={s['pf']}, net={s['net']}, win%={s['winrate']}")

# Test 3: Both filters combined
print("\n=== Combined: vol regime + momentum ===")
f3 = frame.copy()
f3['ok_l'] = f3['ok_l'] & f3['vol_regime_ok'] & f3['momentum_l']
f3['ok_s'] = f3['ok_s'] & f3['vol_regime_ok'] & f3['momentum_s']
trades, _, _ = v50.simulate(f3, base, start=v50.WARMUP_BARS)
s = compute_stats(trades)
print(f"  ADX30 hold3 + vol+mom: {s['trades']} trades, PF={s['pf']}, net={s['net']}, win%={s['winrate']}")

# Test 4: Vary ADX with combined filters
print("\n=== Combined filters, varying ADX ===")
for adx in [20, 25, 30, 35, 40]:
    for rr in [2.5, 3.0, 3.5, 4.0]:
        p = dict(base)
        p['adx_min'] = float(adx)
        p['rr'] = rr
        f = frame.copy()
        f['ok_l'] = f['ok_l'] & f['vol_regime_ok'] & f['momentum_l']
        f['ok_s'] = f['ok_s'] & f['vol_regime_ok'] & f['momentum_s']
        # Recompute ok with new ADX
        f['adx_ok'] = f['adx15_prev'] >= adx
        f['ok_l'] = (frame['in_sess'] & frame['flip_up'] & frame['trend_l']
                     & frame['sha_stable'] & frame['atr_ok']
                     & (frame['risk_l'] <= p['max_sl'] * frame['atr'])
                     & ~frame['in_flat_window'] & f['vol_regime_ok'] & f['momentum_l'])
        f['ok_s'] = (frame['in_sess'] & frame['flip_dn'] & frame['trend_s']
                     & frame['sha_stable'] & frame['atr_ok']
                     & (frame['risk_s'] <= p['max_sl'] * frame['atr'])
                     & ~frame['ok_l'] & ~frame['in_flat_window'] & f['vol_regime_ok'] & f['momentum_s'])
        trades, _, _ = v50.simulate(f, p, start=v50.WARMUP_BARS)
        s = compute_stats(trades)
        if s['trades'] >= 10:
            print(f"  ADX={adx:>2} RR={rr:>3}: {s['trades']:>4} trades, PF={s['pf']:>6.3f}, net={s['net']:>8.1f}")
