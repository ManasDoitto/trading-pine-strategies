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
        
        print(f"[INFO] Fetching BankNifty Index batch: {from_str} to {to_str}")
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
                    print(f"       [SUCCESS] Fetched {len(df_batch)} records.")
            time.sleep(0.5)
        except Exception as e:
            print(f"       [ERROR] Exception: {e}")
            
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

# ==================== STRATEGY 1: v0.4 EMA Pullback (5m) ====================
def run_strategy1(df_raw):
    print("\n--- Running Strategy 1: v0.4 EMA Pullback (15m ADX Gate) ---")
    df = df_raw.copy()
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema200'] = ta.ema(df['close'], length=200)
    df['atr14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['rsi3'] = ta.rsi(df['close'], length=3)
    
    # Session filter: 09:30 to 15:00
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    time_val = df['hour'] * 100 + df['minute']
    df['inSession'] = (time_val >= 930) & (time_val <= 1500)
    
    df['swingLow'] = df['low'].rolling(10).min()
    df['swingHigh'] = df['high'].rolling(10).max()
    
    trades = []
    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl_level = 0
    tp_level = 0
    entry_time = None
    
    for idx, row in df.iterrows():
        if pd.isna(row['atr14']) or pd.isna(row['ema21']):
            continue
            
        current_time = row['timestamp'].hour * 100 + row['timestamp'].minute
        
        if not in_trade:
            # Long setup: close > ema9 and ema9 > ema21
            if row['inSession'] and row['close'] > row['ema9'] and row['ema9'] > row['ema21'] and row['rsi3'] < 80:
                risk_raw = row['close'] - (row['swingLow'] - 0.15 * row['atr14'])
                riskL = max(risk_raw, 0.5 * row['atr14'])
                if riskL <= 2.0 * row['atr14']:
                    in_trade = True
                    trade_dir = 1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] - riskL
                    tp_level = row['close'] + 2.5 * riskL
            # Short setup
            elif row['inSession'] and row['close'] < row['ema9'] and row['ema9'] < row['ema21'] and row['rsi3'] > 20:
                risk_raw = (row['swingHigh'] + 0.15 * row['atr14']) - row['close']
                riskS = max(risk_raw, 0.5 * row['atr14'])
                if riskS <= 2.0 * row['atr14']:
                    in_trade = True
                    trade_dir = -1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] + riskS
                    tp_level = row['close'] - 2.5 * riskS
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
                # BankNifty Lot Size = 15. 1 Lot Option Delta ~0.50
                pnl_opt = pnl_pts * 15 * 0.50
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

# ==================== STRATEGY 2: v1.1 MTF Pullback ====================
def run_strategy2(df_raw):
    print("\n--- Running Strategy 2: v1.1 MTF Pullback (Selective) ---")
    df = df_raw.copy()
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['atr14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['adx14'] = ta.adx(df['high'], df['low'], df['close'], length=14)['ADX_14']
    
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    time_val = df['hour'] * 100 + df['minute']
    df['inSession'] = (time_val >= 925) & (time_val <= 1500)
    
    df['swingLow'] = df['low'].rolling(12).min()
    df['swingHigh'] = df['high'].rolling(12).max()
    
    trades = []
    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl_level = 0
    tp_level = 0
    entry_time = None
    
    for idx, row in df.iterrows():
        if pd.isna(row['atr14']) or pd.isna(row['adx14']):
            continue
            
        current_time = row['timestamp'].hour * 100 + row['timestamp'].minute
        adx_ok = row['adx14'] >= 20.0
        
        if not in_trade:
            if row['inSession'] and adx_ok and row['close'] > row['ema9'] and row['ema9'] > row['ema21']:
                risk_raw = row['close'] - (row['swingLow'] - 0.15 * row['atr14'])
                riskL = max(risk_raw, 0.5 * row['atr14'])
                if riskL <= 2.0 * row['atr14']:
                    in_trade = True
                    trade_dir = 1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] - riskL
                    tp_level = row['close'] + 2.5 * riskL
            elif row['inSession'] and adx_ok and row['close'] < row['ema9'] and row['ema9'] < row['ema21']:
                risk_raw = (row['swingHigh'] + 0.15 * row['atr14']) - row['close']
                riskS = max(risk_raw, 0.5 * row['atr14'])
                if riskS <= 2.0 * row['atr14']:
                    in_trade = True
                    trade_dir = -1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] + riskS
                    tp_level = row['close'] - 2.5 * riskS
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
                pnl_opt = pnl_pts * 15 * 0.50
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

# ==================== STRATEGY 3: Combined Portfolio v0.4 + v1.3 ====================
def run_strategy3(df_raw):
    print("\n--- Running Strategy 3: v0.4 + v1.3 Combined Portfolio ---")
    df = df_raw.copy()
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema200'] = ta.ema(df['close'], length=200)
    df['atr14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['rsi3'] = ta.rsi(df['close'], length=3)
    
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    time_val = df['hour'] * 100 + df['minute']
    df['inSession'] = (time_val >= 920) & (time_val <= 1500)
    
    df['swingLow'] = df['low'].rolling(10).min()
    df['swingHigh'] = df['high'].rolling(10).max()
    
    trades = []
    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl_level = 0
    tp_level = 0
    entry_time = None
    
    for idx, row in df.iterrows():
        if pd.isna(row['atr14']) or pd.isna(row['ema21']):
            continue
            
        current_time = row['timestamp'].hour * 100 + row['timestamp'].minute
        
        if not in_trade:
            # Dual Entry Trigger: EMA alignment or RSI extreme mean reversion
            long_cond = row['inSession'] and ((row['close'] > row['ema9'] and row['ema9'] > row['ema21']) or (row['rsi3'] < 20))
            short_cond = row['inSession'] and ((row['close'] < row['ema9'] and row['ema9'] < row['ema21']) or (row['rsi3'] > 80))
            
            if long_cond:
                risk_raw = row['close'] - (row['swingLow'] - 0.2 * row['atr14'])
                riskL = max(risk_raw, 0.5 * row['atr14'])
                if riskL <= 2.5 * row['atr14']:
                    in_trade = True
                    trade_dir = 1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] - riskL
                    tp_level = row['close'] + 2.0 * riskL
            elif short_cond:
                risk_raw = (row['swingHigh'] + 0.2 * row['atr14']) - row['close']
                riskS = max(risk_raw, 0.5 * row['atr14'])
                if riskS <= 2.5 * row['atr14']:
                    in_trade = True
                    trade_dir = -1
                    entry_price = row['close']
                    entry_time = row['timestamp']
                    sl_level = row['close'] + riskS
                    tp_level = row['close'] - 2.0 * riskS
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
                pnl_opt = pnl_pts * 15 * 0.50
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

def print_summary(name, trades_df):
    if trades_df.empty:
        print(f"[{name}] No trades executed.")
        return
        
    wins = trades_df[trades_df['pnl_pts'] > 0]
    losses = trades_df[trades_df['pnl_pts'] < 0]
    win_rate = len(wins) / len(trades_df) * 100
    total_pts = trades_df['pnl_pts'].sum()
    total_pnl_opt = trades_df['pnl_opt'].sum()
    
    trades_df['date'] = trades_df['entry_time'].dt.date
    daily = trades_df.groupby('date')['pnl_opt'].sum().reset_index()
    win_days = daily[daily['pnl_opt'] > 0]
    loss_days = daily[daily['pnl_opt'] < 0]
    
    trades_df['is_win'] = trades_df['pnl_opt'] > 0
    trades_df['streak_id'] = (trades_df['is_win'] != trades_df['is_win'].shift()).cumsum()
    t_streaks = trades_df.groupby(['streak_id', 'is_win']).size()
    max_w_streak = t_streaks[t_streaks.index.get_level_values('is_win') == True].max() if True in t_streaks.index.get_level_values('is_win') else 0
    max_l_streak = t_streaks[t_streaks.index.get_level_values('is_win') == False].max() if False in t_streaks.index.get_level_values('is_win') else 0
    
    print(f"\n==================== {name} ====================")
    print(f"Total Trades: {len(trades_df)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total Net Index Points: {total_pts:,.2f} pts")
    print(f"Total Net Options PnL (1 Lot, ~0.50 Delta): INR {total_pnl_opt:,.2f}")
    print(f"Total Trading Days: {len(daily)} (Win Days: {len(win_days)}, Loss Days: {len(loss_days)})")
    print(f"Max Win Streak: {max_w_streak} trades | Max Loss Streak: {max_l_streak} trades")
    print(f"Avg Win Day: +INR {win_days['pnl_opt'].mean():,.2f} | Avg Loss Day: -INR {abs(loss_days['pnl_opt'].mean()):,.2f}")

def main():
    print("[INFO] Starting BankNifty Multi-Strategy Backtest Engine...")
    df_raw = fetch_banknifty_history(dhan, days=500)
    if df_raw.empty:
        print("[ERROR] Failed to fetch BankNifty data!")
        return
        
    actual_days = (df_raw['timestamp'].max() - df_raw['timestamp'].min()).days
    print(f"[INFO] Successfully fetched BankNifty Index data covering {actual_days} days ({len(df_raw)} candles).")
    
    t1 = run_strategy1(df_raw)
    print_summary("STRATEGY 1: v0.4 EMA Pullback (15m ADX Gate)", t1)
    
    t2 = run_strategy2(df_raw)
    print_summary("STRATEGY 2: v1.1 MTF Pullback (Selective)", t2)
    
    t3 = run_strategy3(df_raw)
    print_summary("STRATEGY 3: Combined Portfolio (v0.4 + v1.3)", t3)

if __name__ == "__main__":
    main()
