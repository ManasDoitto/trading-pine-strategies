"""Quick test of updated v5.0 with quality filters."""
import sys
import pandas as pd
sys.path.insert(0, '.')
from run_exact_backtests import compute_stats
from trading_agents.core import signals as v40, signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()

# v0.4 baseline
df_bn = pd.read_csv('journal_data/cache/backtest/BANKNIFTY_5min.csv', parse_dates=['time'])
bars_bn = df_bn.copy()
bars_bn['time'] = pd.to_datetime(bars_bn['time'])

from trading_agents.core import signals_v04 as v04
p04 = cfg['strategy']['BANKNIFTY']
frame04 = v04.v04_frame(bars_bn, p04)
sim04 = v04.simulate(frame04, p04, start=v04.WARMUP_BARS)
s04 = compute_stats(sim04['trades'])
print(f"v0.4 BankNifty:       {s04['trades']} trades, {s04['winrate']}, PF={s04['pf']}, net={s04['net']}, maxDD={s04['max_dd']}")

# v5.0 with quality filters (flip + wick + VWAP + ADX=30)
p50 = v50.v50_params_for('BANKNIFTY', cfg)
p50['entry_mode'] = 'flip'
p50['adx_min'] = 30.0
p50['use_quality_filters'] = True
p50['wick_frac'] = 0.5
frame50 = v50.v50_frame(bars_bn, p50)
sim50 = v50.simulate(frame50, p50, start=v50.WARMUP_BARS)
s50 = compute_stats(sim50[0])
print(f"v5.0 flip+QF(ADX30):  {s50['trades']} trades, {s50['winrate']}, PF={s50['pf']}, net={s50['net']}, maxDD={s50['max_dd']}")

# Try different ADX thresholds with quality filters
for adx in [25, 30, 35, 40]:
    for rr in [2.5, 3.0, 3.5]:
        p = v50.v50_params_for('BANKNIFTY', cfg)
        p['entry_mode'] = 'flip'
        p['adx_min'] = float(adx)
        p['rr'] = rr
        p['use_quality_filters'] = True
        frame = v50.v50_frame(bars_bn, p)
        trades, _, _ = v50.simulate(frame, p, start=v50.WARMUP_BARS)
        s = compute_stats(trades)
        if s['trades'] > 5:
            print(f"  ADX={adx:>2} RR={rr:>3}: {s['trades']:>4} trades, {s['winrate']:>6}, PF={s['pf']:>6}, net={s['net']:>8.1f}")
