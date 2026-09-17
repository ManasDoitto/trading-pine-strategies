import itertools
import pandas as pd
from datetime import datetime, timedelta
from fetch_mcx_historical_batches import fetch_mcx_historical_in_batches, get_dhan_client
from silver_strategy_backtester import prepare_data, run_simulation

def run_grid_search():
    print("Fetching Silver Mini 1m data for Grid Search...")
    dhan = get_dhan_client()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    test_sec_id = "483080" # SILVERM NOV FUT
    
    df_1m = fetch_mcx_historical_in_batches(dhan, test_sec_id, start_date, end_date, batch_days=30, instrument_type="FUTCOM")
    
    if df_1m.empty:
        print("No data fetched. Aborting Grid Search.")
        return
        
    print(f"Data fetched successfully. Rows: {len(df_1m)}")
    
    print("Preparing data and calculating valid ranges...")
    df_1m, df_1h, df_15m, df_5m, events_1h, events_15m, events_5m = prepare_data(df_1m, verbose=False)
    
    # Define grid parameters
    fib_levels = [0.5, 0.618, 0.705, 0.786]
    sweep_durations = [2, 4, 8, 24]
    sl_buffers = [0, 10, 25]
    tp_targets = ['structure', 2, 3, 5]
    
    # Generate all combinations
    combinations = list(itertools.product(fib_levels, sweep_durations, sl_buffers, tp_targets))
    total_combinations = len(combinations)
    
    print(f"Starting grid search on {total_combinations} combinations...\n")
    
    results = []
    
    for i, combo in enumerate(combinations):
        fib, duration, sl_buff, tp = combo
        
        df_trades = run_simulation(
            df_1m, events_1h, events_15m, events_5m,
            fib_level=fib, 
            sweep_duration_hours=duration, 
            sl_buffer=sl_buff, 
            tp_target_type=tp, 
            verbose=False
        )
        
        if not df_trades.empty:
            wins = len(df_trades[df_trades['result'] == 'win'])
            total_trades = len(df_trades)
            win_rate = (wins / total_trades) * 100
            
            df_trades['risk'] = abs(df_trades['entry_price'] - df_trades['sl'])
            df_trades['r_multiple'] = df_trades['pnl'] / df_trades['risk']
            total_r = df_trades['r_multiple'].sum()
        else:
            wins = 0
            total_trades = 0
            win_rate = 0
            total_r = 0
            
        results.append({
            'fib_level': fib,
            'sweep_hours': duration,
            'sl_buffer': sl_buff,
            'tp_target': tp,
            'trades': total_trades,
            'win_rate': round(win_rate, 2),
            'total_r': round(total_r, 2)
        })
        
        if (i+1) % 20 == 0:
            print(f"Processed {i+1}/{total_combinations} combinations...")
            
    # Convert to DataFrame, sort by Total R
    df_results = pd.DataFrame(results)
    df_sorted = df_results.sort_values(by='total_r', ascending=False)
    
    print("\n================ GRID SEARCH RESULTS ================")
    print("Top 15 Parameter Combinations by Total R Generated:")
    print(df_sorted.head(15).to_string(index=False))
    
    print("\nCombinations with Highest Win Rate (minimum 3 trades):")
    min_trades_df = df_sorted[df_sorted['trades'] >= 3]
    print(min_trades_df.sort_values(by='win_rate', ascending=False).head(5).to_string(index=False))

if __name__ == "__main__":
    run_grid_search()
