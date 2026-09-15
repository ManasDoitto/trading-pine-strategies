"""
Read-only pull of EXPIRED option OHLC/IV/OI data from Dhan's rollingoption endpoint,
for simulating what option P&L would have looked like on already-backtested
TradingView signals. Never places orders -- calls exactly one GET-like POST
endpoint documented at https://dhanhq.co/docs/v2/expired-options-data/.

Usage:
    python dhan_expired_options.py lookup <SYMBOL>          # find securityId in scrip master
    python dhan_expired_options.py fetch  <args...>          # pull expired option OHLC
"""
import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
ROLLING_OPTION_URL = "https://api.dhan.co/v2/charts/rollingoption"

_scrip_cache = None


def load_scrip_master():
    global _scrip_cache
    if _scrip_cache is None:
        print(f"[INFO] Downloading scrip master from {SCRIP_MASTER_URL} ...", file=sys.stderr)
        _scrip_cache = pd.read_csv(SCRIP_MASTER_URL, low_memory=False)
    return _scrip_cache


def lookup_underlying(symbol_substr, exch_filter=None, instr_filter=None):
    df = load_scrip_master()
    m = df['SEM_CUSTOM_SYMBOL'].astype(str).str.contains(symbol_substr, case=False, na=False) | \
        df['SEM_TRADING_SYMBOL'].astype(str).str.contains(symbol_substr, case=False, na=False)
    sub = df[m]
    if exch_filter:
        sub = sub[sub['SEM_EXM_EXCH_ID'] == exch_filter]
    if instr_filter:
        sub = sub[sub['SEM_INSTRUMENT_NAME'] == instr_filter]
    cols = ['SEM_SMST_SECURITY_ID', 'SEM_TRADING_SYMBOL', 'SEM_CUSTOM_SYMBOL',
            'SEM_EXM_EXCH_ID', 'SEM_INSTRUMENT_NAME', 'SEM_EXPIRY_DATE', 'SEM_STRIKE_PRICE', 'SEM_OPTION_TYPE']
    cols = [c for c in cols if c in sub.columns]
    return sub[cols].drop_duplicates()


def fetch_expired_option(exchange_segment, security_id, instrument, expiry_code, expiry_flag,
                          option_type, strike, interval, from_date, to_date,
                          required_data=None):
    if not CLIENT_ID or not ACCESS_TOKEN:
        raise RuntimeError("DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set (.env)")
    headers = {
        "access-token": ACCESS_TOKEN,
        "client-id": CLIENT_ID,
        "Content-Type": "application/json",
    }
    payload = {
        "exchangeSegment": exchange_segment,
        "securityId": str(security_id),
        "instrument": instrument,
        "expiryCode": expiry_code,
        "expiryFlag": expiry_flag,
        "drvOptionType": option_type,
        "strike": strike,
        "interval": interval,
        "requiredData": required_data or ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "OI", "IV"],
        "fromDate": from_date,
        "toDate": to_date,
    }
    resp = requests.post(ROLLING_OPTION_URL, headers=headers, data=json.dumps(payload), timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Dhan API error {resp.status_code}: {resp.text}")
    return resp.json()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "lookup":
        symbol = sys.argv[2]
        exch = sys.argv[3] if len(sys.argv) > 3 else None
        instr = sys.argv[4] if len(sys.argv) > 4 else None
        res = lookup_underlying(symbol, exch, instr)
        print(f"[INFO] {len(res)} matches")
        print(res.head(40).to_string(index=False))
    elif cmd == "raw_scrip_columns":
        df = load_scrip_master()
        print(list(df.columns))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
