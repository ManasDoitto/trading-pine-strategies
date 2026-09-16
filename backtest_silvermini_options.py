import os
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Try importing dhanhq
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

def compute_strategy_signals(df):
    """
    Computes Master Adaptive Strategy v2 signals on the Futures dataframe.
    """
    # EMA 9 and 21
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    
    # ATR
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    # VWAP (Daily)
    # Using pandas-ta vwap which needs high, low, close, volume and DatetimeIndex
    df = df.set_index('timestamp', drop=False)
    df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    df = df.reset_index(drop=True)
    
    # Heikin Ashi (Smoothed)
    df['o_ema'] = ta.ema(df['open'], length=10)
    df['h_ema'] = ta.ema(df['high'], length=10)
    df['l_ema'] = ta.ema(df['low'], length=10)
    df['c_ema'] = ta.ema(df['close'], length=10)
    
    # Calculate HA
    ha_o = []
    ha_c = (df['o_ema'] + df['h_ema'] + df['l_ema'] + df['c_ema']) / 4
    for i in range(len(df)):
        if i == 0 or pd.isna(ha_o[-1]):
            ha_o.append((df['o_ema'].iloc[i] + df['c_ema'].iloc[i]) / 2)
        else:
            ha_o.append((ha_o[-1] + ha_c.iloc[i-1]) / 2)
    df['ha_o'] = ha_o
    df['ha_c'] = ha_c
    
    df['sha_o'] = ta.ema(pd.Series(df['ha_o']), length=10)
    df['sha_c'] = ta.ema(pd.Series(df['ha_c']), length=10)
    
    df['shaGreen'] = df['sha_c'] > df['sha_o']
    df['shaRed'] = df['sha_c'] < df['sha_o']
    
    df['shaFlipGreen'] = df['shaGreen'] & df['shaRed'].shift(1)
    df['shaFlipRed'] = df['shaRed'] & df['shaGreen'].shift(1)
    
    # Trend Alignment
    df['bullTrend'] = (df['close'] > df['vwap']) & (df['ema9'] > df['ema21'])
    df['bearTrend'] = (df['close'] < df['vwap']) & (df['ema9'] < df['ema21'])
    
    # Session Filter (17:30 to 23:30 IST)
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    time_val = df['hour'] * 100 + df['minute']
    df['inSession'] = (time_val >= 1730) & (time_val <= 2330)
    
    df['longCondition'] = df['inSession'] & df['shaFlipGreen'] & df['bullTrend']
    df['shortCondition'] = df['inSession'] & df['shaFlipRed'] & df['bearTrend']
    
    # Rolling min/max for SL
    df['swingLow'] = df['low'].rolling(10).min()
    df['swingHigh'] = df['high'].rolling(10).max()
    
    return df

def run_backtest():
    print("[INFO] Fetching Silver Mini Futures (SILVERM) for last 500 days...")
    sec_id = "483080"  # SILVERM-30Nov2026-FUT
    
    from fetch_mcx_historical_batches import fetch_mcx_historical_in_batches
    end_date = datetime.now()
    start_date = end_date - timedelta(days=500)
    
    df = fetch_mcx_historical_in_batches(dhan, sec_id, start_date, end_date, batch_days=90)
    if df.empty:
        print("[ERROR] No data fetched for Futures!")
        return
        
    df = compute_strategy_signals(df)
    
    trades = []
    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl_level = 0
    tp_level = 0
    entry_time = None
    
    inp_rr = 2.5
    inp_sl_atr = 1.5
    inp_max_sl_percent = 0.5
    
    print("[INFO] Running execution loop on Futures...")
    for idx, row in df.iterrows():
        if pd.isna(row['atr']):
            continue
            
        current_time = row['timestamp'].hour * 100 + row['timestamp'].minute
        
        if not in_trade:
            if row['longCondition']:
                in_trade = True
                trade_dir = 1
                entry_price = row['close']
                entry_time = row['timestamp']
                
                sl_raw = row['swingLow'] - (0.1 * row['atr'])
                max_sl = row['close'] - (inp_sl_atr * row['atr'])
                sl_raw = max(sl_raw, max_sl)
                max_sl_cap = (row['close'] * inp_max_sl_percent) / 100
                
                sl_level = max(sl_raw, row['close'] - max_sl_cap)
                tp_level = row['close'] + ((row['close'] - sl_level) * inp_rr)
                
            elif row['shortCondition']:
                in_trade = True
                trade_dir = -1
                entry_price = row['close']
                entry_time = row['timestamp']
                
                sl_raw = row['swingHigh'] + (0.1 * row['atr'])
                max_sl = row['close'] + (inp_sl_atr * row['atr'])
                sl_raw = min(sl_raw, max_sl)
                max_sl_cap = (row['close'] * inp_max_sl_percent) / 100
                
                sl_level = min(sl_raw, row['close'] + max_sl_cap)
                tp_level = row['close'] - ((sl_level - row['close']) * inp_rr)
        else:
            exit_reason = None
            exit_price = row['close']
            
            if current_time >= 2330:
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
                # Silver Mini lot size is 5kg. 2 lots = 10 units.
                pnl_inr_futures = pnl_pts * 10 
                # Slightly OTM options have roughly 0.45 delta.
                pnl_inr_options = pnl_inr_futures * 0.45
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": row['timestamp'],
                    "direction": "Long" if trade_dir == 1 else "Short",
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "reason": exit_reason,
                    "pnl_pts": pnl_pts,
                    "pnl_inr_futures": pnl_inr_futures,
                    "pnl_inr_options": pnl_inr_options
                })
                in_trade = False
                
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        wins = trades_df[trades_df['pnl_pts'] > 0]
        win_rate = len(wins) / len(trades_df) * 100
        total_pnl_futures = trades_df['pnl_inr_futures'].sum()
        total_pnl_options = trades_df['pnl_inr_options'].sum()
        
        print("\n=== BACKTEST RESULTS (SILVER MINI 2 LOTS) ===")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Total Net PnL (Futures, 2 Lots): INR {total_pnl_futures:,.2f}")
        print(f"Total Net PnL (OTM Options, 2 Lots, ~0.45 Delta): INR {total_pnl_options:,.2f}")
        print("\nLast 5 Trades:")
        print(trades_df.tail(5).to_string())
    else:
        print("[INFO] No trades executed in this period.")

if __name__ == "__main__":
    run_backtest()
