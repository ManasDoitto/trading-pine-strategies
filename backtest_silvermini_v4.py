import os
import pandas as pd
import pandas_ta as ta
import time
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

def compute_strategy_signals(df):
    """
    Computes v4.0 wide-ATR signals on the Futures dataframe.
    """
    # EMA 9 and 22
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema22'] = ta.ema(df['close'], length=22)
    
    # ATR
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
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
    df['bullTrend'] = (df['ema9'] > df['ema22'])
    df['bearTrend'] = (df['ema9'] < df['ema22'])
    
    # Session Filter (09:15 to 23:30 IST)
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    time_val = df['hour'] * 100 + df['minute']
    df['inSession'] = (time_val >= 915) & (time_val <= 2330)
    
    df['longCondition'] = df['inSession'] & df['shaFlipGreen'] & df['bullTrend']
    df['shortCondition'] = df['inSession'] & df['shaFlipRed'] & df['bearTrend']
    
    # Rolling min/max for SL (swing lookback 10)
    df['swingLow'] = df['low'].rolling(10).min()
    df['swingHigh'] = df['high'].rolling(10).max()
    
    return df

def run_backtest():
    print("[INFO] Fetching Silver Mini Futures (SILVERM) for last 500 days...")
    sec_id = "483080"  # SILVERM-30Nov2026-FUT
    
    from fetch_mcx_historical_batches import fetch_mcx_historical_in_batches
    end_date = datetime.now()
    start_date = end_date - timedelta(days=500)
    
    df = fetch_mcx_historical_in_batches(dhan, sec_id, start_date, end_date, batch_days=90, instrument_type="FUTCOM")
    if df.empty:
        print("[ERROR] No data fetched for Futures!")
        return
    
    actual_days = (df['timestamp'].max() - df['timestamp'].min()).days
    print(f"[INFO] Fetched data covers {actual_days} days of history.")
    
    df = compute_strategy_signals(df)
    
    trades = []
    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl_level = 0
    tp_level = 0
    entry_time = None
    
    # v4.0 wide-ATR parameters
    inp_rr = 3.0
    swBuf = 0.1
    minSL = 2.5
    maxSL = 5.0
    dayLossLimit = 350.0
    
    # Daily tracker
    day_realized = 0.0
    day_locked = False
    last_day = None
    
    print("[INFO] Running execution loop on Futures...")
    for idx, row in df.iterrows():
        if pd.isna(row['atr']):
            continue
            
        current_date = row['timestamp'].date()
        current_time = row['timestamp'].hour * 100 + row['timestamp'].minute
        
        if last_day != current_date:
            day_realized = 0.0
            day_locked = False
            last_day = current_date
            
        if day_locked and in_trade:
            # Force close all
            exit_reason = "Daily Limit Hit"
            exit_price = row['close']
            pnl_pts = (exit_price - entry_price) * trade_dir
            day_realized += pnl_pts
            
            pnl_inr_futures = pnl_pts * 10 
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
            continue
            
        if not in_trade:
            if row['longCondition'] and not day_locked:
                risk_raw = row['close'] - (row['swingLow'] - swBuf * row['atr'])
                riskL = max(risk_raw, minSL * row['atr'])
                
                if riskL <= maxSL * row['atr']:
                    in_trade = True
                    trade_dir = 1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] - riskL
                    tp_level = row['close'] + (inp_rr * riskL)
                
            elif row['shortCondition'] and not day_locked:
                risk_raw = (row['swingHigh'] + swBuf * row['atr']) - row['close']
                riskS = max(risk_raw, minSL * row['atr'])
                
                if riskS <= maxSL * row['atr']:
                    in_trade = True
                    trade_dir = -1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] + riskS
                    tp_level = row['close'] - (inp_rr * riskS)
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
                day_realized += pnl_pts
                
                if day_realized <= -dayLossLimit:
                    day_locked = True
                
                pnl_inr_futures = pnl_pts * 10 
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
        
        print(f"\n=== BACKTEST RESULTS (SILVER MINI 2 LOTS) [{actual_days} DAYS] ===")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Total Net PnL (Futures, 2 Lots): INR {total_pnl_futures:,.2f}")
        print(f"Total Net PnL (OTM Options, 2 Lots, ~0.45 Delta): INR {total_pnl_options:,.2f}")
        
        # Day level analysis
        trades_df['date'] = trades_df['entry_time'].dt.date
        daily = trades_df.groupby('date')['pnl_inr_options'].sum().reset_index()
        win_days = daily[daily['pnl_inr_options'] > 0]
        loss_days = daily[daily['pnl_inr_options'] < 0]
        
        print("\n--- DAY-BY-DAY DISTRIBUTION ---")
        print(f"Total Trading Days: {len(daily)}")
        print(f"Profitable Days: {len(win_days)} ({len(win_days)/len(daily)*100:.1f}%)")
        print(f"Losing Days: {len(loss_days)} ({len(loss_days)/len(daily)*100:.1f}%)")
        
        # Streaks (Trades)
        trades_df['is_win'] = trades_df['pnl_inr_options'] > 0
        trades_df['streak_id'] = (trades_df['is_win'] != trades_df['is_win'].shift()).cumsum()
        trade_streaks = trades_df.groupby(['streak_id', 'is_win']).size()
        max_win_streak_t = trade_streaks[trade_streaks.index.get_level_values('is_win') == True].max()
        max_loss_streak_t = trade_streaks[trade_streaks.index.get_level_values('is_win') == False].max()
        
        # Streaks (Days)
        daily['is_win'] = daily['pnl_inr_options'] > 0
        daily['streak_id'] = (daily['is_win'] != daily['is_win'].shift()).cumsum()
        day_streaks = daily.groupby(['streak_id', 'is_win']).size()
        max_win_streak_d = day_streaks[day_streaks.index.get_level_values('is_win') == True].max()
        max_loss_streak_d = day_streaks[day_streaks.index.get_level_values('is_win') == False].max()
        
        print("\n--- STREAK ANALYSIS ---")
        print(f"Max Winning Streak (Trades): {max_win_streak_t} consecutive trades")
        print(f"Max Losing Streak (Trades): {max_loss_streak_t} consecutive trades")
        print(f"Max Winning Streak (Days): {max_win_streak_d} consecutive days")
        print(f"Max Losing Streak (Days): {max_loss_streak_d} consecutive days")
        
        print("\n--- DAILY PNL DISTRIBUTION ---")
        print(f"Average Winning Day: +INR {win_days['pnl_inr_options'].mean():,.2f}")
        print(f"Average Losing Day: -INR {abs(loss_days['pnl_inr_options'].mean()):,.2f}")
        print(f"Max Single-Day Profit: +INR {daily['pnl_inr_options'].max():,.2f}")
        print(f"Max Single-Day Loss (Breaker Capped): -INR {abs(daily['pnl_inr_options'].min()):,.2f}")
        
        print("\nLast 5 Trades:")
        print(trades_df.tail(5).to_string())
    else:
        print("[INFO] No trades executed in this period.")

if __name__ == "__main__":
    run_backtest()
