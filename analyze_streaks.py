import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import backtest_silvermini_v4 as b
from fetch_mcx_historical_batches import fetch_mcx_historical_in_batches

def run_analysis():
    sec_id = '483080'
    end_date = datetime.now()
    start_date = end_date - timedelta(days=500)
    df = fetch_mcx_historical_in_batches(b.dhan, sec_id, start_date, end_date, batch_days=90)
    df = b.compute_strategy_signals(df)

    trades = []
    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl_level = 0
    tp_level = 0
    entry_time = None
    inp_rr = 3.0
    swBuf = 0.1
    minSL = 2.5
    maxSL = 5.0
    dayLossLimit = 350.0
    day_realized = 0.0
    day_locked = False
    last_day = None

    for idx, row in df.iterrows():
        if pd.isna(row['atr']): continue
        current_date = row['timestamp'].date()
        current_time = row['timestamp'].hour * 100 + row['timestamp'].minute
        
        if last_day != current_date:
            day_realized = 0.0
            day_locked = False
            last_day = current_date
            
        if day_locked and in_trade:
            exit_reason = 'Daily Limit Hit'
            exit_price = row['close']
            pnl_pts = (exit_price - entry_price) * trade_dir
            day_realized += pnl_pts
            trades.append({'entry_time': entry_time, 'exit_time': row['timestamp'], 'date': current_date, 'pnl_pts': pnl_pts, 'pnl_opt': pnl_pts * 10 * 0.45})
            in_trade = False
            continue
            
        if not in_trade:
            if row['longCondition'] and not day_locked:
                risk_raw = row['close'] - (row['swingLow'] - swBuf * row['atr'])
                riskL = max(risk_raw, minSL * row['atr'])
                if riskL <= maxSL * row['atr']:
                    in_trade = True; trade_dir = 1; entry_price = row['close']; entry_time = row['timestamp']
                    sl_level = row['close'] - riskL; tp_level = row['close'] + (inp_rr * riskL)
            elif row['shortCondition'] and not day_locked:
                risk_raw = (row['swingHigh'] + swBuf * row['atr']) - row['close']
                riskS = max(risk_raw, minSL * row['atr'])
                if riskS <= maxSL * row['atr']:
                    in_trade = True; trade_dir = -1; entry_price = row['close']; entry_time = row['timestamp']
                    sl_level = row['close'] + riskS; tp_level = row['close'] - (inp_rr * riskS)
        else:
            exit_reason = None; exit_price = row['close']
            if current_time >= 2330: exit_reason = 'EOD'
            elif trade_dir == 1:
                if row['low'] <= sl_level: exit_reason = 'SL'; exit_price = sl_level
                elif row['high'] >= tp_level: exit_reason = 'TP'; exit_price = tp_level
            elif trade_dir == -1:
                if row['high'] >= sl_level: exit_reason = 'SL'; exit_price = sl_level
                elif row['low'] <= tp_level: exit_reason = 'TP'; exit_price = tp_level
            if exit_reason:
                pnl_pts = (exit_price - entry_price) * trade_dir
                day_realized += pnl_pts
                if day_realized <= -dayLossLimit: day_locked = True
                trades.append({'entry_time': entry_time, 'exit_time': row['timestamp'], 'date': current_date, 'pnl_pts': pnl_pts, 'pnl_opt': pnl_pts * 10 * 0.45})
                in_trade = False

    tdf = pd.DataFrame(trades)

    # Day by day PnL
    daily = tdf.groupby('date')['pnl_opt'].sum().reset_index()
    win_days = daily[daily['pnl_opt'] > 0]
    loss_days = daily[daily['pnl_opt'] < 0]

    print(f"Total Active Trading Days: {len(daily)}")
    print(f"Profitable Days: {len(win_days)} ({len(win_days)/len(daily)*100:.1f}%)")
    print(f"Losing Days: {len(loss_days)} ({len(loss_days)/len(daily)*100:.1f}%)")

    # Streaks (Trade level)
    tdf['win'] = tdf['pnl_opt'] > 0
    tdf['streak_id'] = (tdf['win'] != tdf['win'].shift()).cumsum()
    streaks = tdf.groupby(['streak_id', 'win']).size()
    max_win_streak_trades = streaks[streaks.index.get_level_values('win') == True].max()
    max_loss_streak_trades = streaks[streaks.index.get_level_values('win') == False].max()

    # Streaks (Day level)
    daily['win'] = daily['pnl_opt'] > 0
    daily['streak_id'] = (daily['win'] != daily['win'].shift()).cumsum()
    day_streaks = daily.groupby(['streak_id', 'win']).size()
    max_win_streak_days = day_streaks[day_streaks.index.get_level_values('win') == True].max()
    max_loss_streak_days = day_streaks[day_streaks.index.get_level_values('win') == False].max()

    print(f"Max Winning Streak (Trades): {max_win_streak_trades} consecutive trades")
    print(f"Max Losing Streak (Trades): {max_loss_streak_trades} consecutive trades")
    print(f"Max Winning Streak (Days): {max_win_streak_days} consecutive days")
    print(f"Max Losing Streak (Days): {max_loss_streak_days} consecutive days")

    avg_win = win_days['pnl_opt'].mean()
    avg_loss = abs(loss_days['pnl_opt'].mean())
    max_win = daily['pnl_opt'].max()
    max_loss = abs(daily['pnl_opt'].min())

    print("\n--- Daily PnL Distribution (INR for 2 Lots Options) ---")
    print(f"Average Winning Day: +INR {avg_win:,.2f}")
    print(f"Average Losing Day: -INR {avg_loss:,.2f}")
    print(f"Max Profit Day: +INR {max_win:,.2f}")
    print(f"Max Loss Day (capped by circuit breaker): -INR {max_loss:,.2f}")

if __name__ == "__main__":
    run_analysis()
