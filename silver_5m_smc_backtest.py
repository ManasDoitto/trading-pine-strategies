import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def prepare_data(df_1m, htf_len=200, pivot_len=3):
    # Resample to 5m and 1h
    if not pd.api.types.is_datetime64_any_dtype(df_1m['timestamp']):
        df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'])
        
    df_indexed = df_1m.set_index('timestamp')
    
    # 5m
    agg_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    df_5m = df_indexed.resample('5min').agg(agg_dict).dropna().reset_index()
    
    # 1h for HTF Bias
    df_1h = df_indexed.resample('60min').agg(agg_dict).dropna().reset_index()
    df_1h['htf_ema'] = df_1h['close'].ewm(span=htf_len, adjust=False).mean()
    
    # Map 1H EMA to 5m data using forward fill (lookahead_off equivalent)
    # TradingView request.security with lookahead_off fetches the LAST CLOSED 1H bar's EMA
    df_1h['timestamp_merge'] = df_1h['timestamp'] + pd.Timedelta(hours=1) 
    df_5m = pd.merge_asof(df_5m, df_1h[['timestamp_merge', 'htf_ema']].rename(columns={'timestamp_merge':'timestamp'}), on='timestamp', direction='backward')
    
    # Calculate Pivots (PivotHigh/Low)
    df_5m['pivH'] = np.nan
    df_5m['pivL'] = np.nan
    
    highs = df_5m['high'].values
    lows = df_5m['low'].values
    
    for i in range(pivot_len, len(df_5m) - pivot_len):
        # A pivot high occurs if the high at i is the strict maximum of the window
        # PineScript ta.pivothigh(high, 3, 3) checks if i is > left and >= right.
        left_highs = highs[i-pivot_len:i]
        right_highs = highs[i+1:i+pivot_len+1]
        
        if all(highs[i] > left_highs) and all(highs[i] >= right_highs):
            # Pivot confirmed at i + pivot_len
            df_5m.at[i + pivot_len, 'pivH'] = highs[i]
            
        left_lows = lows[i-pivot_len:i]
        right_lows = lows[i+1:i+pivot_len+1]
        
        if all(lows[i] < left_lows) and all(lows[i] <= right_lows):
            # Pivot confirmed at i + pivot_len
            df_5m.at[i + pivot_len, 'pivL'] = lows[i]
            
    df_5m['lastPivotHigh'] = df_5m['pivH'].ffill()
    df_5m['lastPivotLow'] = df_5m['pivL'].ffill()
    
    return df_5m

def run_simulation(df_5m, reward_multiple=3.6, max_trades_day=2, session_start=17, session_end=23):
    trades = []
    
    active_trade = None
    daily_trades = 0
    current_date = None
    
    pending_bull = False
    pending_bear = False
    active_bull_sweep_low = np.nan
    active_bear_sweep_high = np.nan
    
    for i in range(2, len(df_5m)):
        row = df_5m.iloc[i]
        prev1 = df_5m.iloc[i-1]
        prev2 = df_5m.iloc[i-2]
        
        dt = row['timestamp']
        d_str = dt.date()
        
        if current_date != d_str:
            current_date = d_str
            daily_trades = 0
            
        # Session check (IST)
        hour = dt.hour
        in_session = (session_start <= hour < session_end)
        
        can_trade = in_session and (daily_trades < max_trades_day)
        
        bias_bull = pd.notna(row['htf_ema']) and row['close'] > row['htf_ema']
        bias_bear = pd.notna(row['htf_ema']) and row['close'] < row['htf_ema']
        
        # Reset pendings
        if not in_session or not bias_bull:
            pending_bull = False
        if not in_session or not bias_bear:
            pending_bear = False
            
        # Check active trade exit BEFORE finding new entries (to match TV calc_on_every_tick=false)
        if active_trade is not None:
            # Assuming SL/TP hit evaluated on high/low
            # In TV without calc_on_every_tick, intra-bar dynamics can be tricky. We'll use pessimistic execution.
            if active_trade['dir'] == 1:
                if row['low'] <= active_trade['sl']:
                    active_trade['exit_price'] = active_trade['sl']
                    active_trade['exit_time'] = dt
                    active_trade['pnl'] = active_trade['sl'] - active_trade['entry_price']
                    active_trade['result'] = 'loss'
                    trades.append(active_trade)
                    active_trade = None
                elif row['high'] >= active_trade['tp']:
                    active_trade['exit_price'] = active_trade['tp']
                    active_trade['exit_time'] = dt
                    active_trade['pnl'] = active_trade['tp'] - active_trade['entry_price']
                    active_trade['result'] = 'win'
                    trades.append(active_trade)
                    active_trade = None
            else: # Short
                if row['high'] >= active_trade['sl']:
                    active_trade['exit_price'] = active_trade['sl']
                    active_trade['exit_time'] = dt
                    active_trade['pnl'] = active_trade['entry_price'] - active_trade['sl']
                    active_trade['result'] = 'loss'
                    trades.append(active_trade)
                    active_trade = None
                elif row['low'] <= active_trade['tp']:
                    active_trade['exit_price'] = active_trade['tp']
                    active_trade['exit_time'] = dt
                    active_trade['pnl'] = active_trade['entry_price'] - active_trade['tp']
                    active_trade['result'] = 'win'
                    trades.append(active_trade)
                    active_trade = None
                    
            if active_trade is not None:
                # Still in trade, skip entry logic
                continue
            else:
                # Trade just closed, pendings reset
                pending_bull = False
                pending_bear = False

        # Sweep Detection
        last_pivot_low = row['lastPivotLow']
        last_pivot_high = row['lastPivotHigh']
        
        bull_sweep = pd.notna(last_pivot_low) and (row['low'] < last_pivot_low) and (row['close'] >= last_pivot_low)
        bear_sweep = pd.notna(last_pivot_high) and (row['high'] > last_pivot_high) and (row['close'] <= last_pivot_high)
        
        if bull_sweep and bias_bull and can_trade:
            active_bull_sweep_low = row['low']
            pending_bull = True
            pending_bear = False
            
        if bear_sweep and bias_bear and can_trade:
            active_bear_sweep_high = row['high']
            pending_bear = True
            pending_bull = False
            
        # FVG Detection
        bull_fvg = (row['low'] > prev2['high']) and (row['close'] > row['open']) and (row['close'] > prev1['high'])
        bear_fvg = (row['high'] < prev2['low']) and (row['close'] < row['open']) and (row['close'] < prev1['low'])
        
        if pending_bull and bull_fvg and can_trade:
            order_sl = active_bull_sweep_low - 2
            risk = row['close'] - order_sl
            if risk > 0:
                order_tp = row['close'] + (risk * reward_multiple)
                active_trade = {
                    'entry_time': dt,
                    'dir': 1,
                    'entry_price': row['close'],
                    'sl': order_sl,
                    'tp': order_tp
                }
                daily_trades += 1
                pending_bull = False
                
        if pending_bear and bear_fvg and can_trade:
            order_sl = active_bear_sweep_high + 2
            risk = order_sl - row['close']
            if risk > 0:
                order_tp = row['close'] - (risk * reward_multiple)
                active_trade = {
                    'entry_time': dt,
                    'dir': -1,
                    'entry_price': row['close'],
                    'sl': order_sl,
                    'tp': order_tp
                }
                daily_trades += 1
                pending_bear = False

    return pd.DataFrame(trades)

if __name__ == "__main__":
    from fetch_mcx_historical_batches import fetch_mcx_historical_in_batches, get_dhan_client
    import os
    
    print("Initializing Dhan Client...")
    dhan = get_dhan_client()
    
    test_sec_id = "483080" # SILVERM NOV FUT
    end_date_full = datetime.now()
    start_date_full = end_date_full - timedelta(days=900)
    
    total_periods = 12
    days_per_period = 900 // total_periods
    
    all_trades = []
    
    for period in range(total_periods):
        period_start = start_date_full + timedelta(days=period * days_per_period)
        period_end = period_start + timedelta(days=days_per_period)
        if period == total_periods - 1:
            period_end = end_date_full
            
        print(f"\n--- Period {period + 1}/{total_periods}: {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')} ---")
        try:
            df_1m = fetch_mcx_historical_in_batches(dhan, test_sec_id, period_start, period_end, batch_days=90, instrument_type="FUTCOM")
            
            if not df_1m.empty:
                df_5m = prepare_data(df_1m, htf_len=200, pivot_len=3)
                df_trades = run_simulation(df_5m, reward_multiple=3.6, max_trades_day=2, session_start=17, session_end=23)
                
                if not df_trades.empty:
                    trades_list = df_trades.to_dict('records')
                    all_trades.extend(trades_list)
                    print(f"Found {len(trades_list)} trades.")
                else:
                    print(f"No trades found.")
            else:
                print(f"No data fetched.")
                
        except Exception as e:
            print(f"Error: {e}")
            
    if all_trades:
        df_all = pd.DataFrame(all_trades)
        df_all.to_csv("silver_5m_smc_results.csv", index=False)
        wins = len(df_all[df_all['result'] == 'win'])
        total = len(df_all)
        wr = (wins/total)*100
        df_all['risk'] = abs(df_all['entry_price'] - df_all['sl'])
        df_all['r'] = df_all['pnl'] / df_all['risk']
        total_r = df_all['r'].sum()
        
        print("\n=== FINAL RESULTS ===")
        print(f"Total Trades: {total}")
        print(f"Win Rate: {wr:.2f}%")
        print(f"Total R Generated: {total_r:.2f} R")
    else:
        print("\nNo trades executed across all periods.")
