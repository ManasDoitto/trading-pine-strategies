"""Fetch BankNifty FUTURES 5m OHLCV data from Dhan and stitch contracts for continuous series.
Handles monthly contract rolling using front_future(as_of=...) for each expiry window.
"""
import sys
import os
from pathlib import Path
from datetime import datetime, date, timedelta

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from trading_agents.core.dhan_client import get_dhan_client
from trading_agents.core.market_data import intraday_bars
from trading_agents.core.instruments import front_future, load_scrip_master
from trading_agents.core.config import load_config, data_dir

CACHE_DIR = data_dir("backtest")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT = CACHE_DIR / "BANKNIFTY_FUT_5min.csv"
INTERVAL = 5
DAYS_BACK = 730
BATCH_DAYS = 90


def main():
    cfg = load_config()
    client = get_dhan_client()

    # Get all BankNifty FUTIDX contracts from the scrip master
    sm = load_scrip_master()
    nse = sm[sm.SEM_EXM_EXCH_ID == "NSE"]
    bn_fut = nse[(nse.SEM_INSTRUMENT_NAME == "FUTIDX") &
                 (nse.SEM_TRADING_SYMBOL.str.startswith("BANKNIFTY"))].copy()
    bn_fut["expiry"] = pd.to_datetime(bn_fut["SEM_EXPIRY_DATE"], errors="coerce").dt.date
    bn_fut = bn_fut.dropna(subset=["expiry"]).sort_values("expiry")

    print(f"Found {len(bn_fut)} BANKNIFTY FUTIDX contracts")
    for _, r in bn_fut.iterrows():
        print(f"  {r.SEM_TRADING_SYMBOL}  sec_id={r.SEM_SMST_SECURITY_ID}  expiry={r['expiry']}")

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=DAYS_BACK)

    # Build a list of (start, end, security_id, segment, instrument) for each contract's active window
    contracts = []
    for _, r in bn_fut.iterrows():
        exp = r["expiry"]
        sec_id = str(int(r.SEM_SMST_SECURITY_ID))
        contracts.append((exp, sec_id, "NSE_FNO", "FUTIDX"))

    # Sort by expiry and create rolling windows
    # Each contract is active from the day AFTER the previous contract's expiry until its own expiry
    contracts.sort()  # sort by expiry date
    windows = []
    prev_exp = None
    for exp, sec_id, seg, inst in contracts:
        if prev_exp is not None:
            win_start = prev_exp + timedelta(days=1)
        else:
            win_start = date(2000, 1, 1)  # earliest
        win_end = exp
        if win_start <= end_date and win_end >= start_date:
            windows.append((win_start, win_end, sec_id, seg, inst))
        prev_exp = exp

    # Also add the current front-month contract for recent data
    today = datetime.now().date()
    ff = front_future("BANKNIFTY")
    if ff:
        windows.append((today - timedelta(days=30), today, ff["security_id"], ff["segment"], ff["instrument"]))

    print(f"\nContract windows to fetch: {len(windows)}")
    for ws, we, sid, seg, inst in windows:
        print(f"  {ws} to {we}  sec_id={sid}")

    all_frames = []
    for ws, we, sec_id, seg, inst in windows:
        actual_start = max(ws, start_date)
        actual_end = min(we, end_date)
        if actual_start > actual_end:
            continue
        print(f"\nFetching sec_id={sec_id}: {actual_start} to {actual_end}...")
        df = intraday_bars(client, sec_id, seg, inst,
                           start=actual_start, end=actual_end,
                           interval=INTERVAL, batch_days=BATCH_DAYS)
        if df.empty:
            print(f"  No data for sec_id={sec_id}")
            continue
        print(f"  Got {len(df)} bars")
        all_frames.append(df)

    if not all_frames:
        print("ERROR: No data fetched for any contract!")
        return

    # Concatenate and deduplicate (prefer later contract data for overlapping dates)
    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)

    print(f"\nCombined: {len(combined)} bars, {combined['time'].iloc[0]} to {combined['time'].iloc[-1]}")
    print(f"Volume stats: {combined['volume'].describe()}")
    zero_vol = (combined['volume'] == 0).sum()
    print(f"Zero-volume bars: {zero_vol} ({100*zero_vol/len(combined):.1f}%)")

    combined.to_csv(OUT, index=False)
    print(f"\nSaved {len(combined)} bars to {OUT}")

    # Quick sanity check
    print(f"\nPrice range: {combined['close'].min():.1f} - {combined['close'].max():.1f}")
    print(f"Date range: {combined['time'].iloc[0]} - {combined['time'].iloc[-1]}")


if __name__ == "__main__":
    main()
