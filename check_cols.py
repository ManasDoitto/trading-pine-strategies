"""Check what columns v50_frame produces."""
import pandas as pd
import tomllib
from trading_agents.core.signals_v50 import V50_INSTRUMENT_PARAMS, v50_frame

bars = pd.read_csv('journal_data/cache/backtest/SILVER_5min.csv', parse_dates=['time'])
base = dict(V50_INSTRUMENT_PARAMS['SILVER'])

with open('trading_agents/config.toml', 'rb') as f:
    cfg = tomllib.load(f)
base['atr_min_pts'] = float(cfg['strategy']['SILVER'].get('atr_min_pts', 0))

df = v50_frame(bars, base)
print("Columns produced by v50_frame:")
for c in df.columns:
    print(f"  - {c}")
print(f"\nTotal columns: {len(df.columns)}")
