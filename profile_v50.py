"""Profile v50_frame to find the bottleneck."""
import pandas as pd
import tomllib
import time

bars = pd.read_csv('journal_data/cache/backtest/SILVER_5min.csv', parse_dates=['time'])
print(f"Data: {len(bars)} bars")

from trading_agents.core.signals_v50 import V50_INSTRUMENT_PARAMS, adx_15m_prev, _adx_raw

base = dict(V50_INSTRUMENT_PARAMS['SILVER'])

with open('trading_agents/config.toml', 'rb') as f:
    cfg = tomllib.load(f)
base['atr_min_pts'] = float(cfg['strategy']['SILVER'].get('atr_min_pts', 0))

# Time each major step
t0 = time.time()

# Test ADX calculation
t1 = time.time()
try:
    adx_prev = adx_15m_prev(bars.reset_index(drop=True))
    t2 = time.time()
    print(f"adx_15m_prev: {t2-t1:.1f}s")
except Exception as e:
    t2 = time.time()
    print(f"adx_15m_prev failed after {t2-t1:.1f}s: {e}")

# Test the rest of v50_frame (without ADX)
from trading_agents.core.signals_v50 import v50_frame, WARMUP_BARS
t3 = time.time()
try:
    df = v50_frame(bars, base)
    t4 = time.time()
    print(f"v50_frame (full): {t4-t3:.1f}s")
    print(f"Columns: {list(df.columns)[:5]}... ({len(df.columns)} total)")
except Exception as e:
    t4 = time.time()
    print(f"v50_frame failed after {t4-t3:.1f}s: {e}")
    import traceback
    traceback.print_exc()

total = time.time() - t0
print(f"\nTotal elapsed: {total:.1f}s")
