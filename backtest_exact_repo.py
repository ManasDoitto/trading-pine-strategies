"""
EXACT REPO STRATEGY IMPLEMENTATIONS - Matched to backtest_proven_strategies.py logic
Based on: BEST STRATEGY PER SCRIPT document

1. BankNifty v0.4: EMA Pullback + 15m ADX25 Gate
2. Crude/Gold/Silver v4.0: SHA Flip (EMA10->HA->EMA10) + EMA9/22 filter
"""
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

try:
    from dhanhq import dhanhq, DhanContext
except ImportError:
    os.system("pip install dhanhq -q")
    from dhanhq import dhanhq, DhanContext

load_dotenv()
client_id = os.getenv("DHAN_CLIENT_ID")
access_token = os.getenv("DHAN_ACCESS_TOKEN")

try:
    dhan_context = DhanContext(client_id, access_token)
    dhan = dhanhq(dhan_context)
except Exception:
    dhan = dhanhq(client_id, access_token)

# ==============================================================
# INSTRUMENT CONFIG
# ==============================================================
INSTRUMENTS = {
    "BANKNIFTY": {
        "index_id": "25",
        "futures_segment": "NSE_FNO",
        "instrument_type": "FUTIDX",
        "point_value": 30,
        "lot_size": 15,
        "slippage_per_fill": 5,
    },
    "CRUDEOIL": {
        "futures_segment": "MCX_COMM",
        "instrument_type": "FUTCOM",
        "point_value": 100,
        "lot_size": 100,
        "slippage_per_fill": 2,
    },
    "GOLD": {
        "futures_segment": "MCX_COMM",
        "instrument_type": "FUTCOM",
        "point_value": 100,
        "lot_size": 100,
        "slippage_per_fill": 2,
    },
    "SILVER": {
        "futures_segment": "MCX_COMM",
        "instrument_type": "FUTCOM",
        "point_value": 30,
        "lot_size": 30,
        "slippage_per_fill": 3,
    },
}

COMMISSION_PCT = 0.0002

# ==============================================================
# DATA FETCHING
# ==============================================================
def fetch_historical_data(security_id, exchange_segment, instrument_type, 
                          start_date, end_date=None, batch_days=90):
    if end_date is None:
        end_date = datetime.now()
    
    all_data = []
    current_end = end_date
    
    while current_end > start_date:
        current_start = max(start_date, current_end - timedelta(days=batch_days - 1))
        from_str = current_start.strftime("%Y-%m-%d")
        to_str = current_end.strftime("%Y-%m-%d")
        
        try:
            req = dhan.intraday_minute_data(
                security_id=str(security_id),
                exchange_segment=exchange_segment,
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
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"    Exception: {e}")
        
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
    else:
        return pd.DataFrame()


def fetch_index_data(index_id, start_date, end_date=None):
    return fetch_historical_data(index_id, "IDX_I", "INDEX", start_date, end_date)


def get_active_futures_contract(symbol, date):
    scrip_url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    df_scrip = pd.read_csv(scrip_url, low_memory=False)
    
    if symbol in ["CRUDEOIL", "GOLD", "SILVER"]:
        df_fut = df_scrip[(df_scrip['SEM_EXM_EXCH_ID'] == 'MCX') & 
                          (df_scrip['SEM_INSTRUMENT_NAME'] == 'FUTCOM') &
                          (df_scrip['SEM_CUSTOM_SYMBOL'].str.startswith(symbol))]
    else:
        df_fut = df_scrip[(df_scrip['SEM_EXM_EXCH_ID'] == 'NSE') & 
                          (df_scrip['SEM_INSTRUMENT_NAME'] == 'FUTIDX') &
                          (df_scrip['SEM_CUSTOM_SYMBOL'].str.startswith(symbol))]
    
    if df_fut.empty:
        return None
    
    df_fut['SEM_EXPIRY_DATE'] = pd.to_datetime(df_fut['SEM_EXPIRY_DATE'])
    df_fut = df_fut[df_fut['SEM_EXPIRY_DATE'] >= pd.Timestamp(date)]
    df_fut = df_fut.sort_values(by='SEM_EXPIRY_DATE')
    
    return str(df_fut.iloc[0]['SEM_SMST_SECURITY_ID']) if not df_fut.empty else None


# ==============================================================
# 1. BANKNIFTY v0.4 - EXACT REPO LOGIC
# ==============================================================
def calculate_bnf_indicators(df):
    """Exact indicators from repo v0.4"""
    df = df.copy()
    
    # EMAs
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR14
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    # RSI(3) - for "not above 80 / below 20" filter
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/3, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/3, adjust=False).mean()
    rs = gain / loss
    df['rsi3'] = 100 - (100 / (1 + rs))
    
    # Volume avg
    df['vol_avg'] = df['volume'].rolling(20).mean()
    
    # Candle properties
    df['body'] = (df['close'] - df['open']).abs()
    df['range'] = df['high'] - df['low']
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    df['wick_ratio'] = np.where(df['range'] > 0, 
                                 df[['upper_wick', 'lower_wick']].max(axis=1) / df['range'], 0)
    
    # Trend regime: EMA9 > EMA21 for long, < for short
    df['trend_up'] = df['ema9'] > df['ema21']
    df['trend_down'] = df['ema9'] < df['ema21']
    
    # Coil: EMA9, EMA21, EMA200 all within 1 ATR
    df['coil'] = ((df['ema9'] - df['ema21']).abs() < df['atr']) & \
                 ((df['ema21'] - df['ema200']).abs() < df['atr']) & \
                 ((df['ema9'] - df['ema200']).abs() < df['atr'])
    
    # VWAP
    df['date'] = df['timestamp'].dt.date
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['pv'] = df['typical_price'] * df['volume']
    df['vwap'] = df.groupby('date')['pv'].cumsum() / df.groupby('date')['volume'].cumsum()
    
    return df


def resample_to_15m(df_5m):
    df = df_5m.set_index('timestamp')
    df_15m = df.resample('15min').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    }).dropna()
    return df_15m.reset_index()


def calculate_15m_adx(df_15m):
    """ADX(14) on 15m bars"""
    df = df_15m.copy()
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    plus_dm = df['high'].diff()
    minus_dm = df['low'].shift().diff() * -1
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr_smooth = tr.ewm(span=14, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=14, adjust=False).mean() / tr_smooth)
    minus_di = 100 * (minus_dm.ewm(span=14, adjust=False).mean() / tr_smooth)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df['adx'] = dx.ewm(span=14, adjust=False).mean()
    df['adx_gate'] = df['adx'] >= 25
    return df[['timestamp', 'adx', 'adx_gate']]


def generate_bnf_signals(df_5m, df_15m_adx):
    """
    EXACT v0.4 LOGIC:
    1. Trend: EMA9 > EMA21 (long) or EMA9 < EMA21 (short) OR coil
    2. 15m ADX(14) >= 25 (last COMPLETED 15m bar) - NO LOOKAHEAD
    3. ATR14 >= 50
    4. Pullback: within 10 bars of closing on trend side, price pulls back to EMA9
       AND candle shows rejection wick (>=50% of range)
    5. Confirmation: Within 8 bars, a reclaim bar that:
       - Closes back on trend side of EMAs
       - Volume >= 20-bar avg
       - On correct side of day's VWAP
       - Pullback held EMA21
       - RSI(3) not >80 (long) / not <20 (short)
    6. Entry: STOP ORDER at signal bar high (long) / low (short), lives 8 bars
    7. SL: min(pullback_low - 0.15*ATR, signal_high - 0.5*ATR), capped at 2*ATR
    8. Target: 2.5R
    9. Exit by 15:15, wait 3 bars before re-arming
    """
    signals = []
    position = None
    armed = False
    arm_price = None
    arm_side = None
    arm_sl = None
    arm_tp = None
    arm_expiry = None
    bars_since_exit = 0
    pullback_low_for_sl = None
    pullback_high_for_sl = None
    
    # Map 15m ADX to 5m (use LAST COMPLETED 15m bar - no lookahead)
    df_15m_adx = df_15m_adx.set_index('timestamp')
    df_5m = df_5m.set_index('timestamp')
    df_5m['adx_15m_gate'] = df_15m_adx['adx_gate'].reindex(df_5m.index, method='ffill')
    df_5m = df_5m.reset_index()
    
    for i in range(len(df_5m)):
        row = df_5m.iloc[i]
        ts = row['timestamp']
        
        # Session: 09:30-15:00, no trades first 15 min, close by 15:15
        session_start = pd.Timestamp(f"{ts.date()} 09:30").tz_localize(None)
        session_end = pd.Timestamp(f"{ts.date()} 15:00").tz_localize(None)
        close_by = pd.Timestamp(f"{ts.date()} 15:15").tz_localize(None)
        no_trade_until = session_start + pd.Timedelta(minutes=15)
        
        if ts < no_trade_until or ts > close_by:
            if position and ts >= close_by:
                signals.append({'timestamp': ts, 'type': 'EXIT', 'price': row['close'], 
                               'reason': 'SESSION_END', 'position': position})
                position = None
                armed = False
                bars_since_exit = 0
            continue
        
        # Wait 3 bars after exit before re-arming
        if bars_since_exit > 0:
            bars_since_exit += 1
            if bars_since_exit > 3:
                bars_since_exit = 0
        
        # --- EXIT ---
        if position:
            if position['side'] == 'LONG':
                if row['low'] <= position['sl']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                    armed = False
                    bars_since_exit = 1
                elif row['high'] >= position['tp']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
                    armed = False
                    bars_since_exit = 1
            else:
                if row['high'] >= position['sl']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                    armed = False
                    bars_since_exit = 1
                elif row['low'] <= position['tp']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
                    armed = False
                    bars_since_exit = 1
        
        # --- ARMED STOP ORDER (lives 8 bars) ---
        if armed and not position:
            if i >= arm_expiry:
                armed = False
                continue
            
            if arm_side == 'LONG' and row['high'] >= arm_price:
                # Filled at arm_price (stop order)
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                # SL: min(pullback_low - 0.15*ATR, entry - 0.5*ATR), capped at 2*ATR
                pullback_low = pullback_low_for_sl if pullback_low_for_sl is not None else row['low']
                sl = min(pullback_low - 0.15 * atr_val, arm_price - 0.5 * atr_val)
                sl = max(sl, arm_price - 2 * atr_val)
                tp = arm_price + 2.5 * (arm_price - sl)
                
                position = {'side': 'LONG', 'entry_price': arm_price, 'sl': sl, 'tp': tp,
                           'entry_time': ts, 'entry_bar': i}
                armed = False
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': arm_price,
                               'side': 'LONG', 'sl': sl, 'tp': tp, 'reason': 'ARMED_STOP'})
            
            elif arm_side == 'SHORT' and row['low'] <= arm_price:
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                pullback_high = pullback_high_for_sl if pullback_high_for_sl is not None else row['high']
                sl = max(pullback_high + 0.15 * atr_val, arm_price + 0.5 * atr_val)
                sl = min(sl, arm_price + 2 * atr_val)
                tp = arm_price - 2.5 * (sl - arm_price)
                
                position = {'side': 'SHORT', 'entry_price': arm_price, 'sl': sl, 'tp': tp,
                           'entry_time': ts, 'entry_bar': i}
                armed = False
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': arm_price,
                               'side': 'SHORT', 'sl': sl, 'tp': tp, 'reason': 'ARMED_STOP'})
        
        # --- ENTRY LOGIC: Detect pullback + reclaim to ARM stop order ---
        if not position and not armed and bars_since_exit == 0:
            atr_val = row['atr'] if not pd.isna(row['atr']) else 0
            if atr_val < 50:  # ATR14 >= 50
                continue
            
            adx_ok = row['adx_15m_gate'] if not pd.isna(row['adx_15m_gate']) else False
            vol_ok = row['volume'] >= row['vol_avg']
            rsi_ok_long = row['rsi3'] <= 80 if not pd.isna(row['rsi3']) else True
            rsi_ok_short = row['rsi3'] >= 20 if not pd.isna(row['rsi3']) else True
            
            # LONG SETUP
            trend_ok = row['trend_up'] or row['coil']
            
            # Pullback to EMA9 within last 10 bars (check recent bars)
            pullback_detected = False
            pullback_low = None
            pullback_bar = None
            wick_ok = False
            
            for lookback in range(1, 11):
                if i - lookback < 0:
                    break
                pb_row = df_5m.iloc[i - lookback]
                # Price pulled back to EMA9 (low <= EMA9) and had rejection wick
                if pb_row['low'] <= pb_row['ema9'] and pb_row['wick_ratio'] >= 0.5:
                    pullback_detected = True
                    pullback_low = pb_row['low']
                    pullback_bar = i - lookback
                    wick_ok = True
                    break
            
            # Confirmation: reclaim bar within 8 bars of pullback
            reclaim_ok = False
            if pullback_detected and (i - pullback_bar) <= 8:
                # Current bar closes above EMA9 (trend side)
                if row['close'] > row['ema9']:
                    # On correct side of VWAP
                    if row['close'] > row['vwap']:
                        # Pullback held EMA21 (low > EMA21 during pullback)
                        if pullback_low > df_5m.iloc[pullback_bar]['ema21']:
                            if rsi_ok_long and trend_ok and adx_ok and vol_ok and wick_ok:
                                reclaim_ok = True
            
            # SHORT SETUP (mirror)
            trend_ok_s = row['trend_down'] or row['coil']
            
            pullback_detected_s = False
            pullback_high = None
            pullback_bar_s = None
            wick_ok_s = False
            
            for lookback in range(1, 11):
                if i - lookback < 0:
                    break
                pb_row = df_5m.iloc[i - lookback]
                if pb_row['high'] >= pb_row['ema9'] and pb_row['wick_ratio'] >= 0.5:
                    pullback_detected_s = True
                    pullback_high = pb_row['high']
                    pullback_bar_s = i - lookback
                    wick_ok_s = True
                    break
            
            reclaim_ok_s = False
            if pullback_detected_s and (i - pullback_bar_s) <= 8:
                if row['close'] < row['ema9']:
                    if row['close'] < row['vwap']:
                        if pullback_high < df_5m.iloc[pullback_bar_s]['ema21']:
                            if rsi_ok_short and trend_ok_s and adx_ok and vol_ok and wick_ok_s:
                                reclaim_ok_s = True
            
            if reclaim_ok:
                # ARM stop order at THIS bar's high for 8 bars
                arm_price = row['high']
                arm_side = 'LONG'
                arm_expiry = i + 8
                armed = True
                pullback_low_for_sl = pullback_low
            
            elif reclaim_ok_s:
                arm_price = row['low']
                arm_side = 'SHORT'
                arm_expiry = i + 8
                armed = True
                pullback_high_for_sl = pullback_high
    
    return signals


def run_bnf_backtest(config, start_date, end_date=None):
    print(f"\n{'='*60}")
    print(f"BANKNIFTY v0.4: EMA Pullback + 15m ADX25 Gate")
    print(f"{'='*60}")
    
    # Fetch index data
    print(f"  Fetching INDEX data...")
    index_df = fetch_index_data(config["index_id"], start_date, end_date)
    
    # 15m ADX
    print(f"  Calculating 15m ADX...")
    df_15m = resample_to_15m(index_df)
    df_15m_adx = calculate_15m_adx(df_15m)
    
    # Fetch futures
    print(f"  Fetching FUTURES data...")
    fut_sec_id = get_active_futures_contract("BANKNIFTY", start_date)
    if not fut_sec_id:
        return None
    futures_df = fetch_historical_data(fut_sec_id, config["futures_segment"], 
                                        config["instrument_type"], start_date, end_date)
    
    if index_df.empty or futures_df.empty:
        return None
    
    # Align
    index_df = index_df.set_index('timestamp')
    futures_df = futures_df.set_index('timestamp')
    aligned = index_df.join(futures_df, how='left', rsuffix='_fut').ffill().reset_index()
    
    # Indicators on index data
    df = calculate_bnf_indicators(aligned)
    
    # Generate signals
    signals = generate_bnf_signals(df, df_15m_adx)
    
    # Process trades using FUTURES prices
    trades = []
    current_trade = None
    
    for sig in signals:
        if sig['type'] == 'ENTRY':
            current_trade = {
                'symbol': 'BANKNIFTY',
                'side': sig['side'],
                'entry_time': sig['timestamp'],
                'entry_price': sig['price'],
                'sl': sig['sl'],
                'tp': sig['tp'],
                'reason': sig['reason']
            }
        elif sig['type'] == 'EXIT' and current_trade:
            exit_price = sig['price']
            entry_price = current_trade['entry_price']
            
            if current_trade['side'] == 'LONG':
                gross_pnl = (exit_price - entry_price) * config['point_value']
            else:
                gross_pnl = (entry_price - exit_price) * config['point_value']
            
            commission = entry_price * config['lot_size'] * COMMISSION_PCT * 2
            slippage = config['slippage_per_fill'] * config['point_value'] * 2
            total_costs = commission + slippage
            net_pnl = gross_pnl - total_costs
            
            trades.append({
                **current_trade,
                'exit_time': sig['timestamp'],
                'exit_price': exit_price,
                'exit_reason': sig['reason'],
                'gross_pnl': gross_pnl,
                'costs': total_costs,
                'net_pnl': net_pnl,
                'hold_minutes': (sig['timestamp'] - current_trade['entry_time']).total_seconds() / 60
            })
            current_trade = None
    
    return print_results(trades, "BANKNIFTY", config)


# ==============================================================
# 2. MCX v4.0 SHA FLIP - EXACT REPO LOGIC
# ==============================================================
def calculate_sha_indicators(df):
    """
    EXACT SHA LOGIC from repo:
    1. EMA10 of OHLC
    2. Heikin Ashi from EMA10 OHLC
    3. EMA10 of HA
    4. Color flip = signal
    """
    df = df.copy()
    
    # EMA10 of OHLC
    df['e10_o'] = df['open'].ewm(span=10, adjust=False).mean()
    df['e10_h'] = df['high'].ewm(span=10, adjust=False).mean()
    df['e10_l'] = df['low'].ewm(span=10, adjust=False).mean()
    df['e10_c'] = df['close'].ewm(span=10, adjust=False).mean()
    
    # HA from EMA10
    df['ha_o'] = (df['e10_o'].shift(1) + df['e10_c'].shift(1)) / 2
    df.loc[0, 'ha_o'] = (df.loc[0, 'e10_o'] + df.loc[0, 'e10_c']) / 2
    df['ha_c'] = (df['e10_o'] + df['e10_h'] + df['e10_l'] + df['e10_c']) / 4
    df['ha_h'] = df[['e10_h', 'ha_o', 'ha_c']].max(axis=1)
    df['ha_l'] = df[['e10_l', 'ha_o', 'ha_c']].min(axis=1)
    
    # EMA10 of HA
    df['sha_o'] = df['ha_o'].ewm(span=10, adjust=False).mean()
    df['sha_h'] = df['ha_h'].ewm(span=10, adjust=False).mean()
    df['sha_l'] = df['ha_l'].ewm(span=10, adjust=False).mean()
    df['sha_c'] = df['ha_c'].ewm(span=10, adjust=False).mean()
    
    # SHA Color
    df['sha_green'] = (df['sha_c'] > df['sha_o']).astype(bool)
    df['sha_red'] = (df['sha_c'] < df['sha_o']).astype(bool)
    
    # Color FLIP (not just color, but CHANGE of color)
    df['sha_flip_long'] = (~df['sha_green'].shift(1).fillna(False)) & df['sha_green']
    df['sha_flip_short'] = (~df['sha_red'].shift(1).fillna(False)) & df['sha_red']
    
    # EMA9/22 filter
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema22'] = df['close'].ewm(span=22, adjust=False).mean()
    df['ema9_gt_ema22'] = df['ema9'] > df['ema22']
    df['ema9_lt_ema22'] = df['ema9'] < df['ema22']
    
    # ATR14
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    # 10-bar swing high/low
    df['swing_high_10'] = df['high'].rolling(10).max()
    df['swing_low_10'] = df['low'].rolling(10).min()
    
    return df


def generate_sha_signals(df, symbol):
    """
    EXACT v4.0 LOGIC from repo:
    - LONG: SHA flips green AND EMA9 > EMA22
    - SHORT: SHA flips red AND EMA9 < EMA22
    - Entry: MARKET ORDER at close of flip bar
    - SL: Beyond 10-bar swing low/high + 0.1*ATR, AT LEAST 1.5*ATR (Crude/Gold) or 2.5*ATR (Silver)
          Skip if SL > 3*ATR (Crude/Gold) or 5*ATR (Silver)
    - Target: 4R (Crude), 3R (Gold/Silver base)
    - Session: Crude 09:15-23:30, Gold 17:30-00:30 (COMEX), Silver 09:15-23:30
    - One position at a time
    - Silver: Daily loss limit 350 pts
    """
    signals = []
    position = None
    daily_loss = 0
    current_day = None
    
    # Symbol-specific params
    if symbol == "SILVER":
        sl_min_mult = 2.5
        sl_max_mult = 5.0
        target_r = 3.0
        daily_limit = 350
        sess_start, sess_end = "09:15", "23:30"
    elif symbol == "GOLD":
        sl_min_mult = 1.5
        sl_max_mult = 3.0
        target_r = 3.0
        daily_limit = None
        sess_start, sess_end = "17:30", "00:30"  # COMEX session
    else:  # CRUDEOIL
        sl_min_mult = 1.5
        sl_max_mult = 3.0
        target_r = 4.0  # RR4 per repo update
        daily_limit = None
        sess_start, sess_end = "09:15", "23:30"
    
    for i in range(len(df)):
        row = df.iloc[i]
        ts = row['timestamp']
        day_key = ts.date()
        
        # Reset daily loss
        if current_day != day_key:
            daily_loss = 0
            current_day = day_key
        
        # Daily loss limit (Silver)
        if daily_limit and daily_loss <= -daily_limit:
            continue
        
        # Session filter
        if symbol == "GOLD" and sess_end == "00:30":
            sess_start_ts = pd.Timestamp(f"{ts.date()} {sess_start}").tz_localize(None)
            sess_end_ts = pd.Timestamp(f"{(ts + timedelta(days=1)).date()} {sess_end}").tz_localize(None)
            in_session = sess_start_ts <= ts <= sess_end_ts
        else:
            sess_start_ts = pd.Timestamp(f"{ts.date()} {sess_start}").tz_localize(None)
            sess_end_ts = pd.Timestamp(f"{ts.date()} {sess_end}").tz_localize(None)
            in_session = sess_start_ts <= ts <= sess_end_ts
        
        if not in_session:
            if position:
                signals.append({'timestamp': ts, 'type': 'EXIT', 'price': row['close'],
                               'reason': 'SESSION_END', 'position': position})
                position = None
            continue
        
        # --- EXIT ---
        if position:
            atr_val = position['atr_at_entry']
            
            if position['side'] == 'LONG':
                if row['low'] <= position['sl']:
                    pnl = (position['sl'] - position['entry_price'])
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                elif row['high'] >= position['tp']:
                    pnl = (position['tp'] - position['entry_price'])
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
            else:
                if row['high'] >= position['sl']:
                    pnl = (position['entry_price'] - position['sl'])
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                elif row['low'] <= position['tp']:
                    pnl = (position['entry_price'] - position['tp'])
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
        
        # --- ENTRY ---
        if not position:
            atr_val = row['atr'] if not pd.isna(row['atr']) else 0
            if atr_val == 0:
                continue
            
            # LONG: SHA flip green + EMA9 > EMA22
            if row['sha_flip_long'] and row['ema9_gt_ema22']:
                swing_low = row['swing_low_10']
                if pd.isna(swing_low):
                    continue
                
                # SL: Beyond swing low + 0.1*ATR, AT LEAST sl_min_mult*ATR away
                # = MAX(swing_low - 0.1*ATR, close - sl_min_mult*ATR)  [further from entry]
                sl_candidate = swing_low - 0.1 * atr_val
                min_sl_dist = sl_min_mult * atr_val
                sl = max(sl_candidate, row['close'] - min_sl_dist)
                
                # Skip if SL distance > sl_max_mult * ATR
                if (row['close'] - sl) > sl_max_mult * atr_val:
                    continue
                
                tp = row['close'] + target_r * (row['close'] - sl)
                
                position = {'side': 'LONG', 'entry_price': row['close'], 'sl': sl, 'tp': tp,
                           'entry_time': ts, 'atr_at_entry': atr_val}
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': row['close'],
                               'side': 'LONG', 'sl': sl, 'tp': tp, 'reason': 'SHA_FLIP'})
            
            # SHORT: SHA flip red + EMA9 < EMA22
            elif row['sha_flip_short'] and row['ema9_lt_ema22']:
                swing_high = row['swing_high_10']
                if pd.isna(swing_high):
                    continue
                
                sl_candidate = swing_high + 0.1 * atr_val
                min_sl_dist = sl_min_mult * atr_val
                sl = min(sl_candidate, row['close'] + min_sl_dist)
                
                if (sl - row['close']) > sl_max_mult * atr_val:
                    continue
                
                tp = row['close'] - target_r * (sl - row['close'])
                
                position = {'side': 'SHORT', 'entry_price': row['close'], 'sl': sl, 'tp': tp,
                           'entry_time': ts, 'atr_at_entry': atr_val}
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': row['close'],
                               'side': 'SHORT', 'sl': sl, 'tp': tp, 'reason': 'SHA_FLIP'})
    
    return signals


def run_sha_backtest(symbol, config, start_date, end_date=None):
    print(f"\n{'='*60}")
    print(f"{symbol} v4.0: SHA Flip (EMA10->HA->EMA10)")
    print(f"{'='*60}")
    
    sec_id = get_active_futures_contract(symbol, start_date)
    if not sec_id:
        return None
    print(f"  Contract ID: {sec_id}")
    
    df = fetch_historical_data(sec_id, config["futures_segment"], config["instrument_type"],
                               start_date, end_date)
    
    if df.empty:
        return None
    
    print(f"  Bars: {len(df)}")
    df = calculate_sha_indicators(df)
    
    signals = generate_sha_signals(df, symbol)
    
    # Process trades
    trades = []
    current_trade = None
    daily_loss = 0
    current_day = None
    
    for sig in signals:
        ts = sig['timestamp']
        day_key = ts.date()
        
        if current_day != day_key:
            daily_loss = 0
            current_day = day_key
        
        if sig['type'] == 'ENTRY':
            current_trade = {
                'symbol': symbol,
                'side': sig['side'],
                'entry_time': ts,
                'entry_price': sig['price'],
                'sl': sig['sl'],
                'tp': sig['tp'],
                'reason': sig['reason']
            }
        elif sig['type'] == 'EXIT' and current_trade:
            exit_price = sig['price']
            entry_price = current_trade['entry_price']
            
            if current_trade['side'] == 'LONG':
                gross_pnl = (exit_price - entry_price) * config['point_value']
            else:
                gross_pnl = (entry_price - exit_price) * config['point_value']
            
            commission = entry_price * config['lot_size'] * COMMISSION_PCT * 2
            slippage = config['slippage_per_fill'] * config['point_value'] * 2
            total_costs = commission + slippage
            net_pnl = gross_pnl - total_costs
            
            daily_loss += net_pnl
            
            trades.append({
                **current_trade,
                'exit_time': ts,
                'exit_price': exit_price,
                'exit_reason': sig['reason'],
                'gross_pnl': gross_pnl,
                'costs': total_costs,
                'net_pnl': net_pnl,
                'hold_minutes': (ts - current_trade['entry_time']).total_seconds() / 60
            })
            current_trade = None
    
    return print_results(trades, symbol, config)


def print_results(trades, symbol, config):
    if trades:
        trades_df = pd.DataFrame(trades)
        print(f"\n  === RESULTS for {symbol} ===")
        print(f"  Total trades: {len(trades_df)}")
        wr = (trades_df['net_pnl'] > 0).mean() * 100
        print(f"  Win rate: {wr:.1f}%")
        print(f"  Net P&L: {trades_df['net_pnl'].sum():,.2f} pts")
        print(f"  Gross P&L: {trades_df['gross_pnl'].sum():,.2f} pts")
        print(f"  Total costs: {trades_df['costs'].sum():,.2f} pts")
        
        wins = trades_df[trades_df['net_pnl'] > 0]
        losses = trades_df[trades_df['net_pnl'] <= 0]
        if len(wins) > 0 and len(losses) > 0:
            pf = wins['net_pnl'].sum() / abs(losses['net_pnl'].sum())
            print(f"  Profit Factor: {pf:.2f}")
        print(f"  Avg win: {wins['net_pnl'].mean():.2f}" if len(wins) > 0 else "  Avg win: N/A")
        print(f"  Avg loss: {losses['net_pnl'].mean():.2f}" if len(losses) > 0 else "  Avg loss: N/A")
        print(f"  Avg hold: {trades_df['hold_minutes'].mean():.0f} min")
        print(f"  Trades/month: {len(trades_df) / 6:.1f}")
        
        print(f"\n  By exit reason:")
        for reason, grp in trades_df.groupby('exit_reason'):
            wr = (grp['net_pnl'] > 0).mean() * 100
            print(f"    {reason}: {len(grp)} trades, WR={wr:.1f}%, Net={grp['net_pnl'].sum():.2f}")
        
        trades_df['month'] = trades_df['exit_time'].dt.to_period('M')
        print(f"\n  Monthly P&L:")
        for month, grp in trades_df.groupby('month'):
            wr = (grp['net_pnl'] > 0).mean() * 100
            print(f"    {month}: {len(grp)} trades, Net={grp['net_pnl'].sum():.2f}, WR={wr:.1f}%")
        
        return trades_df
    else:
        print("  No trades generated")
        return pd.DataFrame()


# ==============================================================
# MAIN
# ==============================================================
if __name__ == "__main__":
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    print(f"Backtest period: {start_date.date()} to {end_date.date()}")
    print(f"Testing EXACT repo strategies on Dhan data")
    
    all_results = {}
    
    # 1. BankNifty v0.4
    try:
        result = run_bnf_backtest(INSTRUMENTS["BANKNIFTY"], start_date, end_date)
        if result is not None and not result.empty:
            all_results["BANKNIFTY"] = result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. CrudeOil v4.0 (RR4)
    try:
        result = run_sha_backtest("CRUDEOIL", INSTRUMENTS["CRUDEOIL"], start_date, end_date)
        if result is not None and not result.empty:
            all_results["CRUDEOIL"] = result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Gold v4.0 (COMEX session)
    try:
        result = run_sha_backtest("GOLD", INSTRUMENTS["GOLD"], start_date, end_date)
        if result is not None and not result.empty:
            all_results["GOLD"] = result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Silver v4.0 (wide ATR + daily limit)
    try:
        result = run_sha_backtest("SILVER", INSTRUMENTS["SILVER"], start_date, end_date)
        if result is not None and not result.empty:
            all_results["SILVER"] = result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # Portfolio summary
    if all_results:
        print(f"\n{'='*60}")
        print("PORTFOLIO SUMMARY (EXACT REPO STRATEGIES)")
        print(f"{'='*60}")
        
        all_trades = pd.concat(all_results.values(), ignore_index=True)
        all_trades = all_trades.sort_values('exit_time')
        
        print(f"\nTotal trades: {len(all_trades)}")
        wr = (all_trades['net_pnl'] > 0).mean() * 100
        print(f"Win rate: {wr:.1f}%")
        print(f"Net P&L: {all_trades['net_pnl'].sum():,.2f} pts")
        print(f"Gross P&L: {all_trades['gross_pnl'].sum():,.2f} pts")
        print(f"Total costs: {all_trades['costs'].sum():,.2f} pts")
        
        wins = all_trades[all_trades['net_pnl'] > 0]
        losses = all_trades[all_trades['net_pnl'] <= 0]
        if len(wins) > 0 and len(losses) > 0:
            pf = wins['net_pnl'].sum() / abs(losses['net_pnl'].sum())
            print(f"Profit Factor: {pf:.2f}")
        
        print(f"\nPer Instrument:")
        for sym, grp in all_trades.groupby('symbol'):
            wr = (grp['net_pnl'] > 0).mean() * 100
            pf = grp[grp['net_pnl'] > 0]['net_pnl'].sum() / abs(grp[grp['net_pnl'] <= 0]['net_pnl'].sum()) if len(grp[grp['net_pnl'] <= 0]) > 0 else float('inf')
            print(f"  {sym}: {len(grp)} trades, Net={grp['net_pnl'].sum():.2f}, WR={wr:.1f}%, PF={pf:.2f}")
        
        output_path = f"dhan_exact_repo_strategies_{datetime.now().strftime('%Y%m%d')}.csv"
        all_trades.to_csv(output_path, index=False)
        print(f"\nSaved results to: {output_path}")