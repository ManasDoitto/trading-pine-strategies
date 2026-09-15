import os
import time
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dhanhq import dhanhq

# Load credentials
load_dotenv()
client_id = os.getenv("DHAN_CLIENT_ID")
access_token = os.getenv("DHAN_ACCESS_TOKEN")

if not client_id or not access_token or client_id == "your_client_id_here":
    print("❌ Dhan credentials not set. Please update the .env file with DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN.")
    exit(1)

print("[INFO] Connecting to Dhan API...")

# Try new v2+ syntax first, fallback to v1 syntax if it fails
try:
    from dhanhq import DhanContext
    dhan_context = DhanContext(client_id, access_token)
    dhan = dhanhq(dhan_context)
except ImportError:
    dhan = dhanhq(client_id, access_token)

# -------------------------------------------------------------
# Function: Fetch Option Chain / ATM Strike for BankNifty
# -------------------------------------------------------------
def get_atm_option(symbol="BANKNIFTY", expiry_date=None, spot_price=0, option_type="CE"):
    """
    Finds the ATM strike Security ID for BankNifty options.
    Note: Dhan uses specific security IDs for options.
    """
    print(f"[INFO] Looking up {symbol} Options around {spot_price} {option_type}...")
    
    # In a fully production system, we would query Dhan's master security list (CSV/JSON)
    # to resolve the exact security ID for BANKNIFTY <Expiry> <Strike> <CE/PE>.
    # Dhan provides this at: https://images.dhan.co/api-data/api-scrip-master.csv
    
    # For this script, we'll download and parse the master scrip list dynamically.
    scrip_url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    try:
        print(f"[INFO] Downloading Dhan Scrip Master from {scrip_url}...")
        df_scrip = pd.read_csv(scrip_url, low_memory=False)
        
        # Filter for NSE F&O (EXCH_ID = 'NSE') and OPTIDX (Index Options)
        df_options = df_scrip[(df_scrip['SEM_EXM_EXCH_ID'] == 'NSE') & 
                              (df_scrip['SEM_INSTRUMENT_NAME'] == 'OPTIDX') & 
                              (df_scrip['SEM_CUSTOM_SYMBOL'].str.startswith(symbol))]
        
        if df_options.empty:
            print("[ERROR] No options found for symbol.")
            return None
            
        # Determine ATM Strike (BankNifty strikes are multiples of 100)
        atm_strike = round(spot_price / 100) * 100
        print(f"[SUCCESS] ATM Strike determined as: {atm_strike}")
        
        # Filter by Strike and Option Type
        opt_type_str = "CE" if option_type.upper() == "CE" else "PE"
        
        # Filter for the specific strike and type
        df_target = df_options[(df_options['SEM_STRIKE_PRICE'] == atm_strike) & 
                               (df_options['SEM_OPTION_TYPE'] == opt_type_str)]
        
        if df_target.empty:
            print(f"[ERROR] No {atm_strike} {opt_type_str} contracts found.")
            return None
            
        # Sort by Expiry Date to get the closest weekly expiry
        df_target['SEM_EXPIRY_DATE'] = pd.to_datetime(df_target['SEM_EXPIRY_DATE'])
        # Filter out past expiries
        df_target = df_target[df_target['SEM_EXPIRY_DATE'] >= pd.Timestamp(datetime.now().date())]
        
        if df_target.empty:
            print("[ERROR] All contracts for this strike are expired.")
            return None
            
        df_target = df_target.sort_values(by='SEM_EXPIRY_DATE')
        target_contract = df_target.iloc[0]
        
        sec_id = str(target_contract['SEM_SMST_SECURITY_ID'])
        trading_symbol = target_contract['SEM_TRADING_SYMBOL']
        print(f"[SUCCESS] Found ATM Contract: {trading_symbol} (Security ID: {sec_id})")
        return sec_id, trading_symbol
        
    except Exception as e:
        print(f"[ERROR] Error fetching scrip master: {e}")
        return None

# -------------------------------------------------------------
# Function: Fetch Historical Minute Data for the Option
# -------------------------------------------------------------
def get_historical_minute_data(sec_id, exchange_segment="NFO_OPT", from_date=None, to_date=None):
    """
    Fetches historical 1-minute OHLC data for the given Security ID.
    """
    if not from_date:
        from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")
        
    print(f"[INFO] Fetching 1-min data for Security ID {sec_id} from {from_date} to {to_date}...")
    
    try:
        req = dhan.intraday_minute_data(
            security_id=sec_id,
            exchange_segment="NSE_FNO",
            instrument_type="OPTIDX",
            from_date=from_date,
            to_date=to_date
        )
        
        if req.get("status") == "success":
            print(f"[DEBUG] Full response: {req}")
            data = req.get("data", {})
            print(f"[DEBUG] Raw data length: {len(data.get('timestamp', []))}")
            df = pd.DataFrame({
                "timestamp": data.get("timestamp", []),
                "open": data.get("open", []),
                "high": data.get("high", []),
                "low": data.get("low", []),
                "close": data.get("close", []),
                "volume": data.get("volume", [])
            })
            # Convert timestamp from epoch or string to IST datetime
            if len(df) > 0:
                if pd.api.types.is_numeric_dtype(df["timestamp"]):
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                else:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Convert to IST if not timezone aware
                if df['timestamp'].dt.tz is None:
                    df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=5, minutes=30)
            
            return df
        else:
            print(f"[ERROR] API Error: {req.get('remarks')}")
            return None
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return None

# ==============================================================
# MAIN TEST EXECUTION
# ==============================================================
if __name__ == "__main__":
    print("\n--- Testing Dhan API Option Lookup ---")
    
    # 1. Dynamically get the current BankNifty Spot Price
    today_str = datetime.now().strftime("%Y-%m-%d")
    past_str = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    
    # BankNifty Index Security ID is 25
    spot_req = dhan.intraday_minute_data(security_id='25', exchange_segment='IDX_I', instrument_type='INDEX', from_date=past_str, to_date=today_str)
    
    spot_px = 56600 # Fallback
    try:
        if spot_req.get("status") == "success" and spot_req.get("data", {}).get("close"):
            spot_px = spot_req["data"]["close"][-1]
            print(f"[INFO] Fetched Real-Time BankNifty Spot Price: {spot_px}")
        else:
            print("[WARNING] Could not fetch Spot price, using fallback 56600")
    except Exception as e:
        print(f"[ERROR] Spot price fetch error: {e}")
    
    # 2. Look up the ATM CE Option based on the actual spot price
    result = get_atm_option(symbol="BANKNIFTY", spot_price=spot_px, option_type="CE")
    
    if result:
        sec_id, trading_symbol = result
        today_str = datetime.now().strftime("%Y-%m-%d")
        past_str = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        df_ohlc = get_historical_minute_data(sec_id, from_date=past_str, to_date=today_str)
        
        if df_ohlc is not None and not df_ohlc.empty:
            print(f"\n[SUCCESS] Data fetched successfully! {len(df_ohlc)} minute bars.")
            print("\nRecent 5 minutes:")
            print(df_ohlc.tail(5).to_string(index=False))
        else:
            print("[WARNING] No data returned for the selected contract today.")
