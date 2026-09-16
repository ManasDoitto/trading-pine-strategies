import os
import time
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Try importing dhanhq
try:
    from dhanhq import dhanhq, DhanContext
except ImportError:
    print("❌ dhanhq library is required. Please install it using: pip install dhanhq")
    exit(1)

def get_dhan_client():
    load_dotenv()
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")

    if not client_id or not access_token or client_id == "your_client_id_here":
        print("❌ Dhan credentials not set. Please update the .env file with DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN.")
        exit(1)

    try:
        dhan_context = DhanContext(client_id, access_token)
        return dhanhq(dhan_context)
    except Exception:
        # Fallback for older versions
        return dhanhq(client_id, access_token)

def fetch_mcx_historical_in_batches(dhan, security_id, start_date, end_date=None, batch_days=90, instrument_type="OPTFUT"):
    """
    Fetches historical 1-minute data for MCX options in batches of `batch_days` days.

    :param dhan: Authenticated dhanhq client
    :param security_id: Security ID for the MCX contract
    :param start_date: datetime object representing the start date
    :param end_date: datetime object representing the end date (defaults to today)
    :param batch_days: Number of days to fetch per API call (max 90 for Dhan API)
    :param instrument_type: "OPTFUT" for options (default) or "FUTCOM" for futures
    :return: pandas DataFrame containing the concatenated historical data
    """
    if end_date is None:
        end_date = datetime.now()

    all_data = []
    
    current_end = end_date
    while current_end > start_date:
        current_start = max(start_date, current_end - timedelta(days=batch_days - 1))
        
        from_str = current_start.strftime("%Y-%m-%d")
        to_str = current_end.strftime("%Y-%m-%d")
        
        print(f"[INFO] Fetching batch: {from_str} to {to_str}")
        
        try:
            req = dhan.intraday_minute_data(
                security_id=str(security_id),
                exchange_segment="MCX_COMM",
                instrument_type=instrument_type,
                from_date=from_str,
                to_date=to_str
            )
            
            if req.get("status") == "success":
                data = req.get("data", {})
                if data and data.get("timestamp"):
                    df_batch = pd.DataFrame({
                        "timestamp": data.get("timestamp", []),
                        "open": data.get("open", []),
                        "high": data.get("high", []),
                        "low": data.get("low", []),
                        "close": data.get("close", []),
                        "volume": data.get("volume", [])
                    })
                    all_data.append(df_batch)
                    print(f"       [SUCCESS] Fetched {len(df_batch)} records.")
                else:
                    print(f"       [WARNING] No data returned for this period.")
            else:
                print(f"       [ERROR] API Error: {req.get('remarks', req)}")
                
            # Sleep to respect API rate limits (e.g., 5-10 requests per second typically)
            time.sleep(0.5)
            
        except Exception as e:
            print(f"       [ERROR] Exception occurred: {e}")
            
        # Move to the previous batch window
        current_end = current_start - timedelta(days=1)

    if all_data:
        # Combine all batches and sort by timestamp
        final_df = pd.concat(all_data, ignore_index=True)
        
        # Convert timestamp to IST
        if pd.api.types.is_numeric_dtype(final_df["timestamp"]):
            final_df['timestamp'] = pd.to_datetime(final_df['timestamp'], unit='s')
        else:
            final_df['timestamp'] = pd.to_datetime(final_df['timestamp'])
            
        if final_df['timestamp'].dt.tz is None:
            final_df['timestamp'] = final_df['timestamp'] + pd.Timedelta(hours=5, minutes=30)
            
        final_df = final_df.sort_values(by="timestamp").reset_index(drop=True)
        return final_df
    else:
        return pd.DataFrame()

if __name__ == "__main__":
    dhan = get_dhan_client()
    
    # Example Usage: Replace with actual MCX OPTFUT Security ID
    # Note: MCX option security IDs can be found in the scrip master (api-scrip-master.csv)
    # where SEM_EXM_EXCH_ID = 'MCX' and SEM_INSTRUMENT_NAME = 'OPTFUT'
    test_sec_id = "431269" # Example MCX OPTFUT Security ID

    # Fetch for the last 6 months (approx 180 days) -- only returns real data for
    # the portion of this range the contract was actually active/unexpired (see SKILL.md)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)

    print(f"Starting historical data fetch for MCX Security ID: {test_sec_id}")
    df = fetch_mcx_historical_in_batches(dhan, test_sec_id, start_date, end_date, batch_days=90, instrument_type="OPTFUT")
    
    if not df.empty:
        print("\n[SUCCESS] Successfully fetched combined historical data!")
        print(f"Total rows: {len(df)}")
        print("\nFirst 5 rows:")
        print(df.head())
        print("\nLast 5 rows:")
        print(df.tail())
        
        # Optionally save to CSV
        # df.to_csv(f"mcx_optfut_{test_sec_id}_history.csv", index=False)
    else:
        print("\n[WARNING] Failed to fetch data or no data exists for the specified period.")
