"""
Backtest the PROVEN strategies from repo using Dhan data:
1. BankNifty v0.4: EMA Pullback + 15m ADX Gate (PF 1.29 in repo)
2. CrudeOil/Gold/Silver v4.0: SHA Flip with ATR stops (PF 1.12-1.35 in repo)
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
        "index_segment": "IDX_I",
        "index_type": "INDEX",
        "futures_segment": "NSE_FNO",
        "instrument_type": "FUTIDX",
        "point_value": 30,
        "lot_size": 15,
        "slippage_per_fill": 5,
    },
    "NIFTY": {
        "index_id": "13",
        "index_segment": "IDX_I",
        "index_type": "INDEX",
        "futures_segment": "NSE_FNO",
        "instrument_type": "FUTIDX",
        "point_value": 50,
        "lot_size": 50,
        "slippage_per_fill": 3,
    },
    "CRUDEOIL": {
        "index_id": None,
        "futures_segment": "MCX_COMM",
        "instrument_type": "FUTCOM",
        "point_value": 100,
        "lot_size": 100,
        "slippage_per_fill": 2,
    },
    "GOLD": {
        "index_id": None,
        "futures_segment": "MCX_COMM",
        "instrument_type": "FUTCOM",
        "point_value": 100,
        "lot_size": 100,
        "slippage_per_fill": 2,
    },
    "SILVER": {
        "index_id": None,
        "futures_segment": "MCX_COMM",
        "instrument_type": "FUTCOM",
        "point_value": 30,
        "lot_size": 30,
        "slippage_per_fill": 3,
    },
}

# ==============================================================
# STRATEGY PARAMETERS (FROM REPO - PROVEN TO WORK)
# ==============================================================

# BankNifty v0.4 params (from repo: PF 1.29, 41.9% WR)
BNF_PARAMS = {
    "ema_fast": 9,
    "ema_slow": 21,
    "ema_trend": 200,
    "adx_period_15m": 14,
    "adx_threshold": 25,      # 15m ADX >= 25
    "atr_period": 14,
    "atr_sl_mult": 1.5,       # SL: min(pullback_low - 0.15*ATR, entry - 0.5*ATR), capped at 2*ATR
    "target_r": 2.5,          # 2.5R target
    "wick_ratio": 0.5,        # rejection wick >= 50%
    "volume_mult": 1.0,       # volume >= 20-bar avg
    "session_start": "09:30",
    "session_end": "15:00",
    "no_trade_first_min": 15,
    "close_by": "15:15",
    "commission_pct": 0.0002,
    "min_atr_pts": 50,        # ATR14 >= 50 pts
}

# MCX SHA Flip v4.0 params (from repo: Crude PF 1.12, Gold PF 1.13, Silver PF 1.35)
SHA_PARAMS = {
    "sha_ema": 10,            # EMA10 of OHLC -> HA -> EMA10
    "ema_fast": 9,
    "ema_slow": 22,
    "atr_period": 14,
    "atr_sl_min_mult": 1.5,   # min SL: 1.5 ATR (Crude/Gold), 2.5 ATR (Silver)
    "atr_sl_max_mult": 3.0,   # max SL: 3.0 ATR (Crude/Gold), 5.0 ATR (Silver)
    "target_r": 4.0,          # 4R target (Crude RR4), 3R (Gold/Silver base)
    "session_start": "09:15",
    "session_end": "23:30",   # Crude: 09:15-23:30, Gold: 17:30-00:30 (COMEX)
    "commission_pct": 0.0002,
    # Silver specific
    "silver_atr_sl_min_mult": 2.5,
    "silver_atr_sl_max_mult": 5.0,
    "silver_target_r": 3.0,
    "silver_daily_loss_limit": 350,  # pts
}

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
        
        print(f"  Fetching {from_str} to {to_str}...")
        
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
                    print(f"    Got {len(df_batch)} bars")
                else:
                    print(f"    No data returned")
            else:
                print(f"    API Error: {req.get('remarks', req)}")
            
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


def fetch_index_data(index_id, start_date, end_date=None, batch_days=90):
    return fetch_historical_data(index_id, "IDX_I", "INDEX", start_date, end_date, batch_days)


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
    
    if df_fut.empty:
        return None
    
    return str(df_fut.iloc[0]['SEM_SMST_SECURITY_ID'])


# ==============================================================
# INDICATORS
# ==============================================================
def calculate_bnf_indicators(df_5m, df_15m=None):
    """Calculate indicators for BankNifty v0.4 strategy."""
    df = df_5m.copy()
    
    # EMAs on 5m
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    # Volume avg
    df['vol_avg'] = df['volume'].rolling(20).mean()
    
    # Candle properties
    df['body'] = (df['close'] - df['open']).abs()
    df['range'] = df['high'] - df['low']
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    
    # Trend regime
    df['trend_up'] = (df['ema9'] > df['ema21'])
    df['trend_down'] = (df['ema9'] < df['ema21'])
    
    # Coil: EMA9, EMA21, EMA200 within 1 ATR
    df['coil'] = ((df['ema9'] - df['ema21']).abs() < df['atr']) & \
                 ((df['ema21'] - df['ema200']).abs() < df['atr'])
    
    # Pullback to EMA9
    df['pullback_long'] = (df['low'].shift(1) <= df['ema9'].shift(1)) & (df['close'] > df['ema9'])
    df['pullback_short'] = (df['high'].shift(1) >= df['ema9'].shift(1)) & (df['close'] < df['ema9'])
    
    # Rejection wick
    df['wick_long'] = np.where(df['range'].shift(1) > 0, 
                                df['lower_wick'].shift(1) / df['range'].shift(1) >= 0.5, False)
    df['wick_short'] = np.where(df['range'].shift(1) > 0, 
                                 df['upper_wick'].shift(1) / df['range'].shift(1) >= 0.5, False)
    
    # VWAP
    df['date'] = df['timestamp'].dt.date
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['pv'] = df['typical_price'] * df['volume']
    df['vwap'] = df.groupby('date')['pv'].cumsum() / df.groupby('date')['volume'].cumsum()
    
    # 15m ADX gate (resample 5m to 15m)
    if df_15m is not None:
        df_15m = df_15m.copy()
        # ADX on 15m
        high_low_15 = df_15m['high'] - df_15m['low']
        high_close_15 = (df_15m['high'] - df_15m['close'].shift()).abs()
        low_close_15 = (df_15m['low'] - df_15m['close'].shift()).abs()
        tr_15 = pd.concat([high_low_15, high_close_15, low_close_15], axis=1).max(axis=1)
        
        plus_dm_15 = df_15m['high'].diff()
        minus_dm_15 = df_15m['low'].shift().diff() * -1
        plus_dm_15[plus_dm_15 < 0] = 0
        minus_dm_15[minus_dm_15 < 0] = 0
        
        tr_smooth_15 = tr_15.ewm(span=14, adjust=False).mean()
        plus_di_15 = 100 * (plus_dm_15.ewm(span=14, adjust=False).mean() / tr_smooth_15)
        minus_di_15 = 100 * (minus_dm_15.ewm(span=14, adjust=False).mean() / tr_smooth_15)
        dx_15 = 100 * (plus_di_15 - minus_di_15).abs() / (plus_di_15 + minus_di_15)
        df_15m['adx'] = dx_15.ewm(span=14, adjust=False).mean()
        
        # Map 15m ADX to 5m bars (last completed 15m bar)
        df_15m['adx_signal'] = df_15m['adx'] >= 25
        df = df.set_index('timestamp')
        df_15m = df_15m.set_index('timestamp')
        df['adx_15m'] = df_15m['adx_signal'].reindex(df.index, method='ffill')
        df = df.reset_index()
    else:
        df['adx_15m'] = True  # No gate if no 15m data
    
    return df


def calculate_sha_indicators(df):
    """Calculate SHA (Smoothed Heikin Ashi) indicators for MCX v4.0."""
    df = df.copy()
    
    # Step 1: EMA10 of OHLC
    df['ema10_o'] = df['open'].ewm(span=10, adjust=False).mean()
    df['ema10_h'] = df['high'].ewm(span=10, adjust=False).mean()
    df['ema10_l'] = df['low'].ewm(span=10, adjust=False).mean()
    df['ema10_c'] = df['close'].ewm(span=10, adjust=False).mean()
    
    # Step 2: Heikin Ashi from EMA10 OHLC
    df['ha_open'] = (df['ema10_o'].shift(1) + df['ema10_c'].shift(1)) / 2
    df.loc[0, 'ha_open'] = (df.loc[0, 'ema10_o'] + df.loc[0, 'ema10_c']) / 2
    df['ha_close'] = (df['ema10_o'] + df['ema10_h'] + df['ema10_l'] + df['ema10_c']) / 4
    df['ha_high'] = df[['ema10_h', 'ha_open', 'ha_close']].max(axis=1)
    df['ha_low'] = df[['ema10_l', 'ha_open', 'ha_close']].min(axis=1)
    
    # Step 3: EMA10 of HA
    df['sha_open'] = df['ha_open'].ewm(span=10, adjust=False).mean()
    df['sha_high'] = df['ha_high'].ewm(span=10, adjust=False).mean()
    df['sha_low'] = df['ha_low'].ewm(span=10, adjust=False).mean()
    df['sha_close'] = df['ha_close'].ewm(span=10, adjust=False).mean()
    
    # SHA color: green if sha_close > sha_open
    df['sha_green'] = (df['sha_close'] > df['sha_open']).astype(bool)
    df['sha_red'] = (df['sha_close'] < df['sha_open']).astype(bool)
    
    # Color flip signals
    df['sha_flip_long'] = (~df['sha_green'].shift(1).fillna(False)) & df['sha_green']  # red -> green
    df['sha_flip_short'] = (~df['sha_red'].shift(1).fillna(False)) & df['sha_red']    # green -> red
    
    # EMA9/22 filter
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema22'] = df['close'].ewm(span=22, adjust=False).mean()
    df['ema9_gt_ema22'] = df['ema9'] > df['ema22']
    df['ema9_lt_ema22'] = df['ema9'] < df['ema22']
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    # Swing high/low (10 bar)
    df['swing_high'] = df['high'].rolling(10).max()
    df['swing_low'] = df['low'].rolling(10).min()
    
    return df


# ==============================================================
# STRATEGY SIGNALS
# ==============================================================
def generate_bnf_signals(df, params):
    """BankNifty v0.4: EMA Pullback + 15m ADX Gate."""
    signals = []
    position = None
    entry_bar_idx = None
    armed = False
    arm_price = None
    arm_side = None
    arm_sl = None
    arm_tp = None
    arm_expiry = None
    
    for i in range(len(df)):
        row = df.iloc[i]
        ts = row['timestamp']
        
        # Session filter
        session_start = pd.Timestamp(f"{ts.date()} {params['session_start']}").tz_localize(None)
        session_end = pd.Timestamp(f"{ts.date()} {params['session_end']}").tz_localize(None)
        close_by = pd.Timestamp(f"{ts.date()} {params['close_by']}").tz_localize(None)
        no_trade_until = session_start + pd.Timedelta(minutes=params['no_trade_first_min'])
        
        if ts < no_trade_until or ts > close_by:
            if position and ts >= close_by:
                signals.append({'timestamp': ts, 'type': 'EXIT', 'price': row['close'], 
                               'reason': 'SESSION_END', 'position': position})
                position = None
                armed = False
            continue
        
        # --- EXIT LOGIC ---
        if position:
            if position['side'] == 'LONG':
                if row['low'] <= position['sl']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                    armed = False
                elif row['high'] >= position['tp']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
                    armed = False
            else:
                if row['high'] >= position['sl']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                    armed = False
                elif row['low'] <= position['tp']:
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
                    armed = False
        
        # --- ARMED STOP ORDER LOGIC ---
        if armed and not position:
            # Stop order active for 8 bars
            if i >= arm_expiry:
                armed = False
                continue
            
            if arm_side == 'LONG' and row['high'] >= arm_price:
                # Filled
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                sl = min(row['low'] - 0.15 * atr_val, arm_price - 0.5 * atr_val)
                sl = max(sl, arm_price - 2 * atr_val)
                tp = arm_price + params['target_r'] * (arm_price - sl)
                
                position = {'side': 'LONG', 'entry_price': arm_price, 'sl': sl, 'tp': tp, 
                           'entry_time': ts, 'entry_bar': i}
                armed = False
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': arm_price,
                               'side': 'LONG', 'sl': sl, 'tp': tp, 'reason': 'ARMED_STOP'})
            
            elif arm_side == 'SHORT' and row['low'] <= arm_price:
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                sl = max(row['high'] + 0.15 * atr_val, arm_price + 0.5 * atr_val)
                sl = min(sl, arm_price + 2 * atr_val)
                tp = arm_price - params['target_r'] * (sl - arm_price)
                
                position = {'side': 'SHORT', 'entry_price': arm_price, 'sl': sl, 'tp': tp,
                           'entry_time': ts, 'entry_bar': i}
                armed = False
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': arm_price,
                               'side': 'SHORT', 'sl': sl, 'tp': tp, 'reason': 'ARMED_STOP'})
        
        # --- ENTRY LOGIC (arm stop orders) ---
        if not position and not armed:
            atr_val = row['atr'] if not pd.isna(row['atr']) else 0
            atr_ok = atr_val >= params['min_atr_pts']
            adx_ok = row['adx_15m'] if 'adx_15m' in row else True
            vol_ok = row['volume'] >= row['vol_avg'] * params['volume_mult']
            vwap_ok_long = row['close'] > row['vwap']
            vwap_ok_short = row['close'] < row['vwap']
            
            # Long setup
            trend_ok_long = row['trend_up'] or row['coil']
            pullback_ok_long = row['pullback_long']
            wick_ok_long = row['wick_long']
            rsi_ok_long = row['close'] < row['ema9'] + 2 * atr_val  # RSI(3) not > 80 approx
            
            long_setup = trend_ok_long and adx_ok and atr_ok and vol_ok and \
                        pullback_ok_long and wick_ok_long and vwap_ok_long and rsi_ok_long
            
            # Short setup
            trend_ok_short = row['trend_down'] or row['coil']
            pullback_ok_short = row['pullback_short']
            wick_ok_short = row['wick_short']
            rsi_ok_short = row['close'] > row['ema9'] - 2 * atr_val
            
            short_setup = trend_ok_short and adx_ok and atr_ok and vol_ok and \
                         pullback_ok_short and wick_ok_short and vwap_ok_short and rsi_ok_short
            
            if long_setup:
                # Arm stop at signal bar high for 8 bars
                arm_price = row['high']
                arm_side = 'LONG'
                arm_expiry = i + 8
                armed = True
            
            elif short_setup:
                arm_price = row['low']
                arm_side = 'SHORT'
                arm_expiry = i + 8
                armed = True
    
    return signals


def generate_sha_signals(df, params, symbol):
    """MCX v4.0: SHA Flip with ATR-based SL/TP."""
    signals = []
    position = None
    daily_loss = 0
    current_day = None
    
    # Symbol-specific params
    if symbol == "SILVER":
        sl_min_mult = params['silver_atr_sl_min_mult']
        sl_max_mult = params['silver_atr_sl_max_mult']
        target_r = params['silver_target_r']
        daily_limit = params['silver_daily_loss_limit']
    else:
        sl_min_mult = params['atr_sl_min_mult']
        sl_max_mult = params['atr_sl_max_mult']
        target_r = params['target_r']
        daily_limit = None
    
    # Session times
    if symbol == "GOLD":
        sess_start = "17:30"
        sess_end = "00:30"
    else:
        sess_start = params['session_start']
        sess_end = params['session_end']
    
    for i in range(len(df)):
        row = df.iloc[i]
        ts = row['timestamp']
        day_key = ts.date()
        
        # Reset daily loss
        if current_day != day_key:
            daily_loss = 0
            current_day = day_key
        
        # Check daily loss limit (Silver)
        if daily_limit and daily_loss <= -daily_limit:
            continue  # No new trades today
        
        # Session filter
        if symbol == "GOLD" and sess_end == "00:30":
            # Crosses midnight
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
                    pnl = (position['sl'] - position['entry_price']) * 1  # pts
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                elif row['high'] >= position['tp']:
                    pnl = (position['tp'] - position['entry_price']) * 1
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
            
            else:  # SHORT
                if row['high'] >= position['sl']:
                    pnl = (position['entry_price'] - position['sl']) * 1
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['sl'],
                                   'reason': 'STOP_LOSS', 'position': position})
                    position = None
                elif row['low'] <= position['tp']:
                    pnl = (position['entry_price'] - position['tp']) * 1
                    daily_loss += pnl
                    signals.append({'timestamp': ts, 'type': 'EXIT', 'price': position['tp'],
                                   'reason': 'TAKE_PROFIT', 'position': position})
                    position = None
        
        # --- ENTRY ---
        if not position:
            atr_val = row['atr'] if not pd.isna(row['atr']) else 0
            if atr_val == 0:
                continue
            
            # Long: SHA flip green + EMA9 > EMA22
            if row['sha_flip_long'] and row['ema9_gt_ema22']:
                swing_low = row['swing_low']
                sl_candidate = min(swing_low + 0.1 * atr_val, row['close'] - sl_min_mult * atr_val)
                sl = max(sl_candidate, row['close'] - sl_max_mult * atr_val)
                tp = row['close'] + target_r * (row['close'] - sl)
                
                position = {'side': 'LONG', 'entry_price': row['close'], 'sl': sl, 'tp': tp,
                           'entry_time': ts, 'atr_at_entry': atr_val}
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': row['close'],
                               'side': 'LONG', 'sl': sl, 'tp': tp, 'reason': 'SHA_FLIP'})
            
            # Short: SHA flip red + EMA9 < EMA22
            elif row['sha_flip_short'] and row['ema9_lt_ema22']:
                swing_high = row['swing_high']
                sl_candidate = max(swing_high - 0.1 * atr_val, row['close'] + sl_min_mult * atr_val)
                sl = min(sl_candidate, row['close'] + sl_max_mult * atr_val)
                tp = row['close'] - target_r * (sl - row['close'])
                
                position = {'side': 'SHORT', 'entry_price': row['close'], 'sl': sl, 'tp': tp,
                           'entry_time': ts, 'atr_at_entry': atr_val}
                signals.append({'timestamp': ts, 'type': 'ENTRY', 'price': row['close'],
                               'side': 'SHORT', 'sl': sl, 'tp': tp, 'reason': 'SHA_FLIP'})
    
    return signals


# ==============================================================
# RESAMPLE 5M TO 15M FOR ADX
# ==============================================================
def resample_to_15m(df_5m):
    """Resample 5m data to 15m for ADX calculation."""
    df = df_5m.set_index('timestamp')
    df_15m = df.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    return df_15m.reset_index()


# ==============================================================
# BACKTEST ENGINE
# ==============================================================
def run_bnf_backtest(config, start_date, end_date=None):
    """Run BankNifty v0.4 backtest."""
    print(f"\n{'='*60}")
    print(f"BACKTESTING: BANKNIFTY v0.4 (EMA Pullback + 15m ADX)")
    print(f"{'='*60}")
    
    # Fetch index data (for signals)
    print(f"  Fetching INDEX data (signals) from {start_date.date()}...")
    index_df = fetch_index_data(config["index_id"], start_date, end_date)
    
    # Fetch 15m data for ADX
    print(f"  Resampling to 15m for ADX...")
    df_15m = resample_to_15m(index_df)
    
    # Fetch futures data (for P&L)
    print(f"  Fetching FUTURES data (P&L) from {start_date.date()}...")
    fut_sec_id = get_active_futures_contract("BANKNIFTY", start_date)
    if not fut_sec_id:
        print(f"  No active futures contract")
        return None
    print(f"  Using futures contract ID: {fut_sec_id}")
    
    futures_df = fetch_historical_data(
        fut_sec_id, config["futures_segment"], config["instrument_type"],
        start_date, end_date
    )
    
    if index_df.empty or futures_df.empty:
        print(f"  No data retrieved")
        return None
    
    # Align futures to index timestamps
    index_df = index_df.set_index('timestamp')
    futures_df = futures_df.set_index('timestamp')
    aligned = index_df.join(futures_df, how='left', rsuffix='_fut').ffill().reset_index()
    
    print(f"  Index bars: {len(index_df)}, Futures bars: {len(futures_df)}, Aligned: {len(aligned)}")
    
    # Calculate indicators
    print("  Calculating indicators...")
    df = calculate_bnf_indicators(aligned, df_15m)
    
    # Generate signals
    print("  Generating signals...")
    signals = generate_bnf_signals(df, BNF_PARAMS)
    
    # Process trades
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
            
            commission = entry_price * config['lot_size'] * BNF_PARAMS['commission_pct'] * 2
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


def run_sha_backtest(symbol, config, params, start_date, end_date=None):
    """Run MCX SHA Flip backtest."""
    print(f"\n{'='*60}")
    print(f"BACKTESTING: {symbol} SHA Flip v4.0")
    print(f"{'='*60}")
    
    sec_id = get_active_futures_contract(symbol, start_date)
    if not sec_id:
        print(f"  No active futures contract")
        return None
    print(f"  Using futures contract ID: {sec_id}")
    
    print(f"  Fetching historical data from {start_date.date()}...")
    df = fetch_historical_data(sec_id, config["futures_segment"], config["instrument_type"],
                               start_date, end_date)
    
    if df.empty:
        print(f"  No data retrieved")
        return None
    
    print(f"  Total bars: {len(df)}")
    
    # Calculate SHA indicators
    print("  Calculating SHA indicators...")
    df = calculate_sha_indicators(df)
    
    # Generate signals
    print("  Generating signals...")
    signals = generate_sha_signals(df, params, symbol)
    
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
            
            commission = entry_price * config['lot_size'] * params['commission_pct'] * 2
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
    print(f"Testing PROVEN repo strategies on Dhan data")
    
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
    
    # 2. CrudeOil SHA Flip (RR4)
    try:
        result = run_sha_backtest("CRUDEOIL", INSTRUMENTS["CRUDEOIL"], SHA_PARAMS, start_date, end_date)
        if result is not None and not result.empty:
            all_results["CRUDEOIL"] = result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Gold SHA Flip (COMEX session)
    try:
        result = run_sha_backtest("GOLD", INSTRUMENTS["GOLD"], SHA_PARAMS, start_date, end_date)
        if result is not None and not result.empty:
            all_results["GOLD"] = result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Silver SHA Flip (wide ATR + daily limit)
    try:
        result = run_sha_backtest("SILVER", INSTRUMENTS["SILVER"], SHA_PARAMS, start_date, end_date)
        if result is not None and not result.empty:
            all_results["SILVER"] = result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # Portfolio summary
    if all_results:
        print(f"\n{'='*60}")
        print("PORTFOLIO SUMMARY (PROVEN STRATEGIES)")
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
        
        output_path = f"dhan_proven_strategies_{datetime.now().strftime('%Y%m%d')}.csv"
        all_trades.to_csv(output_path, index=False)
        print(f"\nSaved results to: {output_path}")