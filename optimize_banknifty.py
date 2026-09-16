import os
import pandas as pd
import pandas_ta as ta
import time
import itertools
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from dhanhq import dhanhq, DhanContext
except ImportError:
    print("[ERROR] dhanhq library is required. Please install it using: pip install dhanhq")
    exit(1)

def get_dhan_client():
    load_dotenv()
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token or client_id == "your_client_id_here":
        print("[ERROR] Dhan credentials not set.")
        exit(1)
    try:
        return dhanhq(DhanContext(client_id, access_token))
    except Exception:
        return dhanhq(client_id, access_token)

dhan = get_dhan_client()

def fetch_banknifty_history(dhan, days=500):
    sec_id = "25" # BANKNIFTY Index
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    all_data = []
    current_end = end_date
    batch_days = 90
    
    while current_end > start_date:
        current_start = max(start_date, current_end - timedelta(days=batch_days - 1))
        from_str = current_start.strftime("%Y-%m-%d")
        to_str = current_end.strftime("%Y-%m-%d")
        
        print(f"Fetching {from_str} to {to_str}...")
        try:
            req = dhan.intraday_minute_data(
                security_id=sec_id,
                exchange_segment="IDX_I",
                instrument_type="INDEX",
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
                        "volume": data.get("volume", [0]*len(data.get("timestamp", [])))
                    })
                    all_data.append(df_batch)
            time.sleep(0.5)
        except Exception as e:
            print(f"Error: {e}")
            
        current_end = current_start - timedelta(days=1)
        
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        if pd.api.types.is_numeric_dtype(final_df["timestamp"]):
            final_df['timestamp'] = pd.to_datetime(final_df['timestamp'], unit='s')
        else:
            final_df['timestamp'] = pd.to_datetime(final_df['timestamp'])
        if final_df['timestamp'].dt.tz is None:
            final_df['timestamp'] = final_df['timestamp'] + pd.Timedelta(hours=5, minutes=30)
        final_df = final_df.sort_values(by="timestamp").reset_index(drop=True)
        return final_df
    return pd.DataFrame()


def run_strategy2_variant(df_raw, dayLossLimit, adxMin, rMultiple, skipOpenMin):
    df = df_raw.copy()
    
    trades = []
    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl_level = 0
    tp_level = 0
    entry_time = None
    
    start_time_val = 915 + skipOpenMin
    if start_time_val % 100 >= 60: # Handle hour overflow
        start_time_val = (start_time_val // 100 + 1) * 100 + (start_time_val % 100 - 60)
        
    current_day = None
    daily_pnl = 0
    stop_trading_day = False
    
    for idx, row in df.iterrows():
        if pd.isna(row['atr14']) or pd.isna(row['adx14']):
            continue
            
        date_str = row['timestamp'].date()
        if date_str != current_day:
            current_day = date_str
            daily_pnl = 0
            stop_trading_day = False
            
        current_time = row['timestamp'].hour * 100 + row['timestamp'].minute
        
        # Stop trading for the day if circuit breaker hit
        if stop_trading_day:
            continue
            
        inSession = (current_time >= start_time_val) and (current_time <= 1500)
        adx_ok = row['adx14'] >= adxMin
        
        if not in_trade:
            if inSession and adx_ok and row['close'] > row['ema9'] and row['ema9'] > row['ema21']:
                risk_raw = row['close'] - (row['swingLow'] - 0.15 * row['atr14'])
                riskL = max(risk_raw, 0.5 * row['atr14'])
                if riskL <= 2.0 * row['atr14']:
                    in_trade = True
                    trade_dir = 1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] - riskL
                    tp_level = row['close'] + rMultiple * riskL
            elif inSession and adx_ok and row['close'] < row['ema9'] and row['ema9'] < row['ema21']:
                risk_raw = (row['swingHigh'] + 0.15 * row['atr14']) - row['close']
                riskS = max(risk_raw, 0.5 * row['atr14'])
                if riskS <= 2.0 * row['atr14']:
                    in_trade = True
                    trade_dir = -1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] + riskS
                    tp_level = row['close'] - rMultiple * riskS
        else:
            exit_reason = None
            exit_price = row['close']
            if current_time >= 1515:
                exit_reason = "EOD"
            elif trade_dir == 1:
                if row['low'] <= sl_level:
                    exit_reason = "SL"
                    exit_price = sl_level
                elif row['high'] >= tp_level:
                    exit_reason = "TP"
                    exit_price = tp_level
            elif trade_dir == -1:
                if row['high'] >= sl_level:
                    exit_reason = "SL"
                    exit_price = sl_level
                elif row['low'] <= tp_level:
                    exit_reason = "TP"
                    exit_price = tp_level
                    
            if exit_reason:
                pnl_pts = (exit_price - entry_price) * trade_dir
                pnl_opt = pnl_pts * 15 * 0.50 # BankNifty 15 lot size, ~0.5 delta
                
                daily_pnl += pnl_pts
                if dayLossLimit > 0 and daily_pnl <= -dayLossLimit:
                    stop_trading_day = True
                    
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": row['timestamp'],
                    "direction": "Long" if trade_dir == 1 else "Short",
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "reason": exit_reason,
                    "pnl_pts": pnl_pts,
                    "pnl_opt": pnl_opt
                })
                in_trade = False
                
    return pd.DataFrame(trades)

def get_performance(trades_df):
    if trades_df.empty:
        return 0, 0, 0, 0
    wins = trades_df[trades_df['pnl_pts'] > 0]
    win_rate = len(wins) / len(trades_df) * 100
    total_pnl = trades_df['pnl_opt'].sum()
    gross_profit = wins['pnl_opt'].sum()
    gross_loss = abs(trades_df[trades_df['pnl_pts'] < 0]['pnl_opt'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999
    
    trades_df['cum_pnl'] = trades_df['pnl_opt'].cumsum()
    trades_df['high_water_mark'] = trades_df['cum_pnl'].cummax()
    trades_df['drawdown'] = trades_df['high_water_mark'] - trades_df['cum_pnl']
    max_dd = trades_df['drawdown'].max()
    
    return total_pnl, win_rate, profit_factor, max_dd

def main():
    print("Fetching historical BankNifty data...")
    df_raw = fetch_banknifty_history(dhan, days=500)
    if df_raw.empty:
        print("Failed to fetch data.")
        return
        
    print(f"Data fetched. Preparing indicators...")
    # Pre-calculate indicators ONCE to speed up loop
    df_raw['ema9'] = ta.ema(df_raw['close'], length=9)
    df_raw['ema21'] = ta.ema(df_raw['close'], length=21)
    df_raw['atr14'] = ta.atr(df_raw['high'], df_raw['low'], df_raw['close'], length=14)
    df_raw['adx14'] = ta.adx(df_raw['high'], df_raw['low'], df_raw['close'], length=14)['ADX_14']
    df_raw['swingLow'] = df_raw['low'].rolling(12).min()
    df_raw['swingHigh'] = df_raw['high'].rolling(12).max()
    
    variations = [
        # Baseline tweaks (No Loss Limit)
        (0, 15, 2.0, 15),
        (0, 20, 2.0, 15),
        (0, 25, 2.5, 30),
        (0, 30, 2.0, 30),
        
        # Loss Limit 250 pts (~INR 1,875 options max loss per day)
        (250, 15, 2.0, 15),
        (250, 20, 2.0, 15),
        (250, 25, 2.5, 30),
        (250, 30, 3.0, 45),
        
        # Loss Limit 350 pts (~INR 2,625 options max loss per day)
        (350, 15, 2.0, 15),
        (350, 20, 2.5, 15),
        (350, 25, 2.5, 30),
        (350, 25, 2.0, 45),
        
        # Loss Limit 500 pts (~INR 3,750 options max loss per day)
        (500, 15, 2.0, 15),
        (500, 20, 2.5, 30),
        (500, 25, 2.5, 30),
        (500, 30, 3.0, 45),
        
        # Aggressive R-Multiple tweaks
        (350, 20, 3.0, 15),
        (500, 20, 3.0, 30),
        (250, 25, 1.5, 45),
        (500, 25, 1.5, 15)
    ]
    
    results = []
    print(f"\nTesting {len(variations)} variations...\n")
    
    for i, (dl, adx, r, skip) in enumerate(variations):
        print(f"[{i+1}/{len(variations)}] Testing DL={dl}, ADX={adx}, R={r}, Skip={skip}m")
        trades_df = run_strategy2_variant(df_raw, dl, adx, r, skip)
        pnl, win_rate, pf, max_dd = get_performance(trades_df)
        trades_count = len(trades_df)
        
        results.append({
            "LossLimit": dl,
            "ADX_Min": adx,
            "R_Multiple": r,
            "Skip_Open_Min": skip,
            "Total_Trades": trades_count,
            "Win_Rate": round(win_rate, 2),
            "Profit_Factor": round(pf, 2),
            "Max_DD": round(max_dd, 2),
            "Net_PnL": round(pnl, 2)
        })
        
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by="Net_PnL", ascending=False).reset_index(drop=True)
    
    print("\n================== TOP 10 STRATEGY VARIATIONS ==================")
    print(results_df.head(10).to_string())
    
    results_df.to_csv("banknifty_optimization_results.csv", index=False)
    print("\nSaved full results to banknifty_optimization_results.csv")

if __name__ == "__main__":
    main()
