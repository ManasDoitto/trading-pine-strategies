"""Compare v5.0 entry modes on BankNifty, plus Silver v4.0 baseline."""
import sys
import pandas as pd
sys.path.insert(0, '.')
from run_exact_backtests import compute_stats
from trading_agents.core import signals as v40, signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()

# --- BankNifty: compare flip vs breakout vs v0.4 ---
df_bn = pd.read_csv('journal_data/cache/backtest/BANKNIFTY_5min.csv', parse_dates=['time'])
bars_bn = df_bn.copy()
bars_bn['time'] = pd.to_datetime(bars_bn['time'])

# v0.4 baseline
p04 = cfg['strategy']['BANKNIFTY']
from trading_agents.core import signals_v04 as v04
frame04 = v04.v04_frame(bars_bn, p04)
sim04 = v04.simulate(frame04, p04, start=v04.WARMUP_BARS)
s04 = compute_stats(sim04['trades'])
print(f"v0.4 BankNifty: {s04['trades']} trades, {s04['winrate']}, PF={s04['pf']}, net={s04['net']}")

# v5.0 flip mode (ADX=30)
p_flip = v50.v50_params_for('BANKNIFTY', cfg)
p_flip['entry_mode'] = 'flip'
p_flip['adx_min'] = 30.0
p_flip['pb_atr_mult'] = 1.0
p_flip['breakout_lookback'] = 5
frame_flip = v50.v50_frame(bars_bn, p_flip)
sim_flip = v50.simulate(frame_flip, p_flip, start=v50.WARMUP_BARS)
s_flip = compute_stats(sim_flip[0])
print(f"v5.0 flip (ADX=30): {s_flip['trades']} trades, {s_flip['winrate']}, PF={s_flip['pf']}, net={s_flip['net']}")

# v5.0 breakout mode (ADX=30, BO=10)
p_bo = v50.v50_params_for('BANKNIFTY', cfg)
p_bo['entry_mode'] = 'breakout'
p_bo['adx_min'] = 30.0
p_bo['pb_atr_mult'] = 1.0
p_bo['breakout_lookback'] = 10
frame_bo = v50.v50_frame(bars_bn, p_bo)
sim_bo = v50.simulate(frame_bo, p_bo, start=v50.WARMUP_BARS)
s_bo = compute_stats(sim_bo[0])
print(f"v5.0 breakout (ADX=30, BO=10): {s_bo['trades']} trades, {s_bo['winrate']}, PF={s_bo['pf']}, net={s_bo['net']}")

# --- Silver: v4.0 baseline vs v5.0 ---
df_ag = pd.read_csv('journal_data/cache/backtest/SILVER_5min.csv', parse_dates=['time'])
bars_ag = df_ag.copy()
bars_ag['time'] = pd.to_datetime(bars_ag['time'])

# Silver v4.0
p_ag_v40 = cfg['strategy']['SILVER']
frame_ag_v40 = v40.v40_frame(bars_ag, p_ag_v40)
trades_ag_v40, _, _ = v40.simulate(frame_ag_v40, p_ag_v40, start=v40.WARMUP_BARS)
s_ag_v40 = compute_stats(trades_ag_v40)
print(f"\nv4.0 Silver baseline: {s_ag_v40['trades']} trades, {s_ag_v40['winrate']}, PF={s_ag_v40['pf']}, net={s_ag_v40['net']}")

# Silver v5.0 (flip mode with ADX=30)
p_ag_v50 = v50.v50_params_for('SILVER', cfg)
p_ag_v50['adx_min'] = 30.0
p_ag_v50['pd_atr_mult'] = 0.5
frame_ag_v50 = v50.v50_frame(bars_ag, p_ag_v50)
sim_ag_v50 = v50.simulate(frame_ag_v50, p_ag_v50, start=v50.WARMUP_BARS)
s_ag_v50 = compute_stats(sim_ag_v50[0])
print(f"v5.0 Silver (ADX=30): {s_ag_v50['trades']} trades, {s_ag_v50['winrate']}, PF={s_ag_v50['pf']}, net={s_ag_v50['net']}")
