import pandas as pd
import numpy as np

def resample_data(df_1m, timeframe='15min'):
    """Resamples 1-minute OHLCV data to a higher timeframe."""
    if not pd.api.types.is_datetime64_any_dtype(df_1m['timestamp']):
        df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
        
    df_indexed = df_1m.set_index('timestamp')
    agg_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    df_resampled = df_indexed.resample(timeframe).agg(agg_dict).dropna()
    return df_resampled.reset_index()

def identify_valid_ranges(df):
    """
    Core Logic for the Day Trading System.
    Identifies Valid Swing Highs and Valid Swing Lows based on the Opposite Candle (OC)
    and Pullback Candle (PBC) rules.
    """
    df = df.copy()
    
    df['is_valid_high'] = False
    df['is_valid_low'] = False
    df['swing_high_price'] = np.nan
    df['swing_low_price'] = np.nan
    df['validated_at'] = pd.NaT # Track when the structure was confirmed to prevent lookahead bias

    current_push_direction = 0 # 1 for UP, -1 for DOWN
    highest_high = 0
    lowest_low = float('inf')
    highest_idx = 0
    lowest_idx = 0
    
    for i in range(1, len(df)):
        _open, _high, _low, _close = df.loc[i, 'open'], df.loc[i, 'high'], df.loc[i, 'low'], df.loc[i, 'close']
        prev_high, prev_low = df.loc[i-1, 'high'], df.loc[i-1, 'low']
        timestamp = df.loc[i, 'timestamp']
        
        if current_push_direction == 0:
            if _high > prev_high:
                current_push_direction = 1
                highest_high = _high
                highest_idx = i
            elif _low < prev_low:
                current_push_direction = -1
                lowest_low = _low
                lowest_idx = i

        if current_push_direction == 1:
            if _high > highest_high:
                highest_high = _high
                highest_idx = i
                
            is_oc = _close < _open 
            is_pbc = _high <= highest_high 
            
            if is_oc and is_pbc and _high < highest_high: 
                df.at[highest_idx, 'is_valid_high'] = True
                df.at[highest_idx, 'swing_high_price'] = highest_high
                df.at[highest_idx, 'validated_at'] = timestamp
                
                current_push_direction = -1
                lowest_low = _low
                lowest_idx = i

        elif current_push_direction == -1:
            if _low < lowest_low:
                lowest_low = _low
                lowest_idx = i
                
            is_oc = _close > _open 
            is_pbc = _low >= lowest_low 
            
            if is_oc and is_pbc and _low > lowest_low:
                df.at[lowest_idx, 'is_valid_low'] = True
                df.at[lowest_idx, 'swing_low_price'] = lowest_low
                df.at[lowest_idx, 'validated_at'] = timestamp
                
                current_push_direction = 1
                highest_high = _high
                highest_idx = i

    return df

def prepare_data(df_1m, verbose=True):
    if verbose: print("Resampling Timeframes...")
    df_1h = resample_data(df_1m, '60min')
    df_15m = resample_data(df_1m, '15min')
    df_5m = resample_data(df_1m, '5min')
    
    if verbose: print("Mapping Valid Ranges (OC+PBC)...")
    df_1h = identify_valid_ranges(df_1h)
    df_15m = identify_valid_ranges(df_15m)
    df_5m = identify_valid_ranges(df_5m)
    
    # Calculate 1H 200 EMA
    df_1h['htf_ema'] = df_1h['close'].ewm(span=200, adjust=False).mean()
    
    # Map previous session high/low
    df_1m = df_1m.copy()
    df_1m['date'] = df_1m['timestamp'].dt.date
    daily_stats = df_1m.groupby('date').agg({'high': 'max', 'low': 'min'})
    daily_stats['prev_high'] = daily_stats['high'].shift(1)
    daily_stats['prev_low'] = daily_stats['low'].shift(1)
    df_1m = df_1m.merge(daily_stats[['prev_high', 'prev_low']], left_on='date', right_index=True, how='left')
    
    # Map 1H EMA to 1m data
    df_1m = pd.merge_asof(df_1m, df_1h[['timestamp', 'htf_ema']], on='timestamp', direction='backward')
    
    # Extract confirmed events
    events_1h = df_1h.dropna(subset=['validated_at'])[['validated_at', 'is_valid_high', 'is_valid_low', 'swing_high_price', 'swing_low_price']]
    events_15m = df_15m.dropna(subset=['validated_at'])[['validated_at', 'is_valid_high', 'is_valid_low', 'swing_high_price', 'swing_low_price']]
    events_5m = df_5m.dropna(subset=['validated_at'])[['validated_at', 'is_valid_high', 'is_valid_low', 'swing_high_price', 'swing_low_price']]
    
    # Sort events
    events_1h = events_1h.sort_values('validated_at')
    events_15m = events_15m.sort_values('validated_at')
    events_5m = events_5m.sort_values('validated_at')
    
    return df_1m, df_1h, df_15m, df_5m, events_1h, events_15m, events_5m


def run_simulation(df_1m, events_1h, events_15m, events_5m, max_trades_per_day=2, tp_target_type=3.6, sl_buffer=0, verbose=True):
    trades = []
    
    # State tracking
    active_trade = None # dict
    
    last_1h_trend = 0 # 1=bull, -1=bear
    last_15m_high = None
    last_15m_low = None
    last_5m_high = None
    last_5m_low = None
    
    active_sweep = 0 # 1=swept high (looking short), -1=swept low (looking long)
    sweep_extreme = None
    
    # Daily limits
    daily_trades = 0
    current_date = None
    
    # Iterators for events
    idx_1h = 0
    idx_15m = 0
    idx_5m = 0
    
    if verbose: print("Executing bar-by-bar simulation...")
    for row in df_1m.itertuples(index=False):
        current_time = row.timestamp
        high = row.high
        low = row.low
        close = row.close
        prev_session_high = row.prev_high
        prev_session_low = row.prev_low
        htf_ema = row.htf_ema
        
        # Reset daily trades
        date_str = current_time.date()
        if current_date != date_str:
            current_date = date_str
            daily_trades = 0

        # --- Update HTF States ---
        # 1H State
        while idx_1h < len(events_1h) and events_1h.iloc[idx_1h]['validated_at'] <= current_time:
            ev = events_1h.iloc[idx_1h]
            if ev['is_valid_high']: last_1h_trend = -1
            if ev['is_valid_low']:  last_1h_trend = 1
            idx_1h += 1
            
        # 15m State (for Take Profit targets)
        while idx_15m < len(events_15m) and events_15m.iloc[idx_15m]['validated_at'] <= current_time:
            ev = events_15m.iloc[idx_15m]
            if ev['is_valid_high']: last_15m_high = ev['swing_high_price']
            if ev['is_valid_low']:  last_15m_low = ev['swing_low_price']
            idx_15m += 1
            
        # 5m State (for Trend Changes)
        tc_occurred = 0
        tc_price = None
        while idx_5m < len(events_5m) and events_5m.iloc[idx_5m]['validated_at'] <= current_time:
            ev = events_5m.iloc[idx_5m]
            if ev['is_valid_high']: 
                last_5m_high = ev['swing_high_price']
                tc_occurred = -1
                tc_price = ev['swing_high_price']
            if ev['is_valid_low']:  
                last_5m_low = ev['swing_low_price']
                tc_occurred = 1
                tc_price = ev['swing_low_price']
            idx_5m += 1

        # --- Session Management ---
        entry_window = (17, 0) <= (current_time.hour, current_time.minute) <= (23, 0)
        hold_window = (17, 0) <= (current_time.hour, current_time.minute) <= (23, 30)
            
        # Force close active trades if outside hold window
        if active_trade and not hold_window:
            active_trade['exit_price'] = close
            active_trade['exit_time'] = current_time
            if active_trade['dir'] == 1:
                active_trade['pnl'] = close - active_trade['entry_price']
            else:
                active_trade['pnl'] = active_trade['entry_price'] - close
            active_trade['result'] = 'win' if active_trade['pnl'] > 0 else 'loss'
            trades.append(active_trade)
            active_trade = None
            continue

        # --- Active Trade Management ---
        if active_trade:
            # Check Stop Loss
            if active_trade['dir'] == 1 and low <= active_trade['sl']:
                active_trade['exit_price'] = active_trade['sl']
                active_trade['exit_time'] = current_time
                active_trade['pnl'] = active_trade['exit_price'] - active_trade['entry_price']
                active_trade['result'] = 'loss'
                trades.append(active_trade)
                active_trade = None
            elif active_trade['dir'] == -1 and high >= active_trade['sl']:
                active_trade['exit_price'] = active_trade['sl']
                active_trade['exit_time'] = current_time
                active_trade['pnl'] = active_trade['entry_price'] - active_trade['exit_price']
                active_trade['result'] = 'loss'
                trades.append(active_trade)
                active_trade = None
            # Check Take Profit
            elif active_trade and active_trade['dir'] == 1 and high >= active_trade['tp']:
                active_trade['exit_price'] = active_trade['tp']
                active_trade['exit_time'] = current_time
                active_trade['pnl'] = active_trade['exit_price'] - active_trade['entry_price']
                active_trade['result'] = 'win'
                trades.append(active_trade)
                active_trade = None
            elif active_trade and active_trade['dir'] == -1 and low <= active_trade['tp']:
                active_trade['exit_price'] = active_trade['tp']
                active_trade['exit_time'] = current_time
                active_trade['pnl'] = active_trade['entry_price'] - active_trade['exit_price']
                active_trade['result'] = 'win'
                trades.append(active_trade)
                active_trade = None
                
            continue # Don't look for new setups while in a trade

        # Only allow trades if daily limit not reached and within entry window
        if not entry_window or daily_trades >= max_trades_per_day:
            continue

        # --- Setup Detection ---
        # 1. Sweep Phase (must hit session hi/lo AND have correct EMA bias)
        # Bullish Bias = close > 1H 200 EMA
        # Bearish Bias = close < 1H 200 EMA
        bias_bull = pd.notna(htf_ema) and close > htf_ema
        bias_bear = pd.notna(htf_ema) and close < htf_ema
        
        if pd.notna(prev_session_high) and high > prev_session_high and bias_bear:
            active_sweep = 1
            sweep_extreme = max(high, sweep_extreme) if sweep_extreme else high
                
        if pd.notna(prev_session_low) and low < prev_session_low and bias_bull:
            active_sweep = -1
            sweep_extreme = min(low, sweep_extreme) if sweep_extreme else low
            
        # Look for TC if we have an active sweep
        if active_sweep == 1 and tc_occurred == -1:
            # Swept high, now 5m trend changed bearish.
            if sweep_extreme > tc_price:
                # Market Entry
                sl_level = sweep_extreme + sl_buffer
                risk_amount = sl_level - close
                tp_target = close - (risk_amount * tp_target_type)
                
                if risk_amount > 0:
                    active_trade = {
                        'entry_time': current_time,
                        'dir': -1,
                        'entry_price': close,
                        'sl': sl_level,
                        'tp': tp_target
                    }
                    daily_trades += 1
                active_sweep = 0 
                
        elif active_sweep == -1 and tc_occurred == 1:
            # Swept low, now 5m trend changed bullish.
            if tc_price > sweep_extreme:
                # Market Entry
                sl_level = sweep_extreme - sl_buffer
                risk_amount = close - sl_level
                tp_target = close + (risk_amount * tp_target_type)
                
                if risk_amount > 0:
                    active_trade = {
                        'entry_time': current_time,
                        'dir': 1,
                        'entry_price': close,
                        'sl': sl_level,
                        'tp': tp_target
                    }
                    daily_trades += 1
                active_sweep = 0

    if verbose: print(f"Simulation complete. Total trades taken: {len(trades)}")
    
    if len(trades) > 0:
        df_trades = pd.DataFrame(trades)
        wins = len(df_trades[df_trades['result'] == 'win'])
        losses = len(df_trades[df_trades['result'] == 'loss'])
        win_rate = (wins / len(trades)) * 100
        
        # Calculate Risk and Reward assuming 1 Risk unit = entry - SL
        df_trades['risk'] = abs(df_trades['entry_price'] - df_trades['sl'])
        df_trades['r_multiple'] = df_trades['pnl'] / df_trades['risk']
        total_r = df_trades['r_multiple'].sum()
        
        if verbose:
            print(f"\n--- Strategy Performance ---")
            print(f"Total Trades: {len(trades)}")
            print(f"Wins: {wins} | Losses: {losses}")
            print(f"Win Rate: {win_rate:.2f}%")
            print(f"Total R Generated: {total_r:.2f} R")
            print("\nAll Trades:")
            print(df_trades)
    else:
        df_trades = pd.DataFrame(trades)
        
    return df_trades

if __name__ == "__main__":
    from fetch_mcx_historical_batches import fetch_mcx_historical_in_batches, get_dhan_client
    from datetime import datetime, timedelta
    import os
    
    print("Initializing Dhan Client...")
    dhan = get_dhan_client()
    
    test_sec_id = "483080" # SILVERM NOV FUT
    end_date_full = datetime.now()
    start_date_full = end_date_full - timedelta(days=900)
    
    total_periods = 12
    days_per_period = 900 // total_periods
    
    print(f"Dividing 30 months (900 days) into {total_periods} periods of {days_per_period} days each.")
    
    all_trades = []
    
    for period in range(total_periods):
        period_start = start_date_full + timedelta(days=period * days_per_period)
        period_end = period_start + timedelta(days=days_per_period)
        if period == total_periods - 1:
            period_end = end_date_full # Ensure we cover exactly up to now
            
        print(f"\n--- Executing Period {period + 1}/{total_periods} ---")
        print(f"Fetching data from {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}...")
        
        try:
            df_1m = fetch_mcx_historical_in_batches(dhan, test_sec_id, period_start, period_end, batch_days=90, instrument_type="FUTCOM")
            
            if not df_1m.empty:
                df_1m, df_1h, df_15m, df_5m, events_1h, events_15m, events_5m = prepare_data(df_1m, verbose=False)
                df_trades = run_simulation(df_1m, events_1h, events_15m, events_5m, max_trades_per_day=2, tp_target_type=3.6, verbose=False)
                
                if not df_trades.empty:
                    # Convert trades to dicts to append to all_trades
                    trades_list = df_trades.to_dict('records')
                    all_trades.extend(trades_list)
                    print(f"Period {period + 1} complete. Found {len(trades_list)} trades.")
                else:
                    print(f"Period {period + 1} complete. No trades found.")
                
                # SAVE CHECKPOINT after each period
                if all_trades:
                    checkpoint_df = pd.DataFrame(all_trades)
                    checkpoint_path = f"silver_period_{period+1}_checkpoint.csv"
                    checkpoint_df.to_csv(checkpoint_path, index=False)
                    print(f"Savepoint created: {checkpoint_path}")
                    
                    # Update cumulative dashboard
                    wins = len(checkpoint_df[checkpoint_df['result'] == 'win'])
                    total = len(checkpoint_df)
                    wr = (wins/total)*100 if total > 0 else 0
                    with open("silver_30_month_dashboard.md", "w") as f:
                        f.write(f"# Silver 30-Month Backtest Checkpoint\n")
                        f.write(f"Completed Periods: {period + 1}/{total_periods}\n")
                        f.write(f"Total Trades: {total}\n")
                        f.write(f"Win Rate: {wr:.2f}%\n")
                        f.write(f"Total R Generated: {checkpoint_df['r_multiple'].sum():.2f} R\n")
            else:
                print(f"No data fetched for Period {period + 1}.")
                
        except Exception as e:
            print(f"Error executing Period {period + 1}: {e}")
            
    print("\n--- All Periods Complete ---")
