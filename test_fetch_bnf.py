"""Quick test: verify Dhan token + fetch BankNifty futures data."""
import sys
from pathlib import Path
from datetime import datetime, date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trading_agents.core.dhan_client import get_dhan_client
from trading_agents.core.market_data import intraday_bars
from trading_agents.core.instruments import front_future
from trading_agents.core.config import data_dir

# Test token
client = get_dhan_client()
ff = front_future("BANKNIFTY")
print(f"Futures: sec_id={ff['security_id']}, seg={ff['segment']}, inst={ff['instrument']}, expiry={ff['expiry']}")

# Test with OHLC
r = client.ohlc_data({"NSE_FNO": [ff["security_id"]]})
print(f"OHLC test: {r}")

# Fetch data for the past 730 days
end_date = datetime.now()
start_date = end_date - timedelta(days=730)
print(f"\nFetching BankNifty futures 5m: {start_date.date()} to {end_date.date()}...")

df = intraday_bars(
    client, ff["security_id"], ff["segment"], ff["instrument"],
    start=start_date, end=end_date, interval=5, batch_days=90
)

print(f"Got {len(df)} bars")
print(f"Date range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
print(f"Close range: {df['close'].min():.1f} - {df['close'].max():.1f}")
print(f"Volume range: {df['volume'].min():.0f} - {df['volume'].max():.0f}")
print(f"Zero vol: {(df['volume']==0).sum()} ({100*(df['volume']==0).sum()/len(df):.1f}%)")

# Save
CACHE_DIR = data_dir("cache") / "backtest"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT = CACHE_DIR / "BANKNIFTY_FUT_5min.csv"
df.to_csv(OUT, index=False)
print(f"\nSaved to {OUT}")
