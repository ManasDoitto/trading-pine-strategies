"""
Backtest a new day trading strategy using Dhan API historical data.
Strategy: VWAP + EMA Pullback with ATR-based risk management
Instruments: BankNifty Futures, Nifty Futures, CrudeOil, Gold, Silver
"""
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import deque

try:
    from dhanhq import dhanhq, DhanContext
except ImportError:
    print("Installing dhanhq...")
    os.system("pip install dhanhq -q")
    from dhanhq import dhanhq, DhanContext

load_dotenv()
client_id = os.getenv("DHAN_CLIENT_ID")
access_token = os.getenv("DHAN_ACCESS_TOKEN")

if not client_id or not access_token or client_id == "your_client_id_here":
    raise RuntimeError("DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set in .env")

try:
    dhan_context = DhanContext(client_id, access_token)
    dhan = dhanhq(dhan_context)
except Exception:
    dhan = dhanhq(client_id, access_token)

# ==============================================================
# INSTRUMENT CONFIGURATION
# ==============================================================
INSTRUMENTS = {
    "BANKNIFTY": {
        "index_id": "25",          # Nifty Bank index (spot)
        "index_segment": "IDX_I",
        "index_type": "INDEX",
        "futures_segment": "NSE_FNO",
        "instrument_type": "FUTIDX",
        "point_value": 30,         # 1 lot = 30 pts
        "lot_size": 15,
        "slippage_per_fill": 5,    # points
    },
    "NIFTY": {
        "index_id": "13",          # Nifty 50 index (spot)
        "index_segment": "IDX_I",
        "index_type": "INDEX",
        "futures_segment": "NSE_FNO",
        "instrument_type": "FUTIDX",
        "point_value": 50,         # 1 lot = 50 pts (adjust based on current lot)
        "lot_size": 50,
        "slippage_per_fill": 3,
    },
    "CRUDEOIL": {
        "index_id": None,          # Use futures directly
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
# STRATEGY PARAMETERS (IMPROVED BASED ON FAILED BACKTEST)
# ==============================================================
PARAMS = {
    "ema_fast": 9,
    "ema_slow": 21,
    "ema_trend": 200,
    "adx_period": 14,
    "adx_threshold": 25,
    "atr_period": 14,
    "atr_sl_mult": 2.0,       # Wider SL: 2 ATR (was 1.5)
    "atr_tp_mult": 3.0,       # Higher R:R: 3R (was 2.5)
    "vwap_lookback": 20,
    "wick_ratio": 0.5,         # Rejection wick >= 50% of candle range
    "volume_mult": 1.0,        # Volume >= 20-bar avg
    "session_start": "09:30",
    "session_end": "15:00",
    "no_trade_first_min": 15,  # Skip first 15 min
    "max_hold_minutes": 345,   # Close by 15:15
    "commission_pct": 0.0002,  # 0.02% per side
    # New filters
    "min_atr_threshold": 0.001,  # Minimum ATR as % of price (avoid dead markets)
    "max_trades_per_day": 3,     # Cap daily trades
}

# ==============================================================
# DATA FETCHING
# ==============================================================
def fetch_historical_data(security_id, exchange_segment, instrument_type, 
                          start_date, end_date=None, batch_days=90):
    """Fetch 1-minute historical data in batches from Dhan."""
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
            
            time.sleep(0.5)  # Rate limit
            
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
    """Fetch index (spot) data using IDX_I segment."""
    return fetch_historical_data(index_id, "IDX_I", "INDEX", start_date, end_date, batch_days)


def get_active_futures_contract(symbol, date):
    """Get the active futures contract security ID for a given date."""
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
def calculate_indicators(df):
    """Calculate all required indicators."""
    df = df.copy()
    
    # EMAs
    df['ema_fast'] = df['close'].ewm(span=PARAMS['ema_fast'], adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=PARAMS['ema_slow'], adjust=False).mean()
    df['ema_trend'] = df['close'].ewm(span=PARAMS['ema_trend'], adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=PARAMS['atr_period'], adjust=False).mean()
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].shift().diff() * -1
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr_smooth = tr.ewm(span=PARAMS['adx_period'], adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=PARAMS['adx_period'], adjust=False).mean() / tr_smooth)
    minus_di = 100 * (minus_dm.ewm(span=PARAMS['adx_period'], adjust=False).mean() / tr_smooth)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df['adx'] = dx.ewm(span=PARAMS['adx_period'], adjust=False).mean()
    
    # VWAP (session-based)
    df['date'] = df['timestamp'].dt.date
    df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
    df['pv'] = df['typical_price'] * df['volume']
    
    vwap_data = df.groupby('date').apply(
        lambda g: g.assign(
            vwap=(g['pv'].cumsum() / g['volume'].cumsum()),
            vwap_sd=(g['pv'].rolling(PARAMS['vwap_lookback']).sum() / 
                     g['volume'].rolling(PARAMS['vwap_lookback']).sum())
        )
    ).reset_index(drop=True)
    
    df['vwap'] = vwap_data['vwap']
    df['vwap_sd'] = vwap_data['vwap_sd']
    
    # Volume average
    df['vol_avg'] = df['volume'].rolling(20).mean()
    
    # Candle properties
    df['body'] = (df['close'] - df['open']).abs()
    df['range'] = df['high'] - df['low']
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    df['wick_ratio'] = np.where(df['range'] > 0, 
                                 df[['upper_wick', 'lower_wick']].max(axis=1) / df['range'], 0)
    
    # Trend direction
    df['trend_up'] = (df['ema_fast'] > df['ema_slow']) & (df['ema_slow'] > df['ema_trend'])
    df['trend_down'] = (df['ema_fast'] < df['ema_slow']) & (df['ema_slow'] < df['ema_trend'])
    
    # Coil condition (EMAs within 1 ATR)
    df['coil'] = ((df['ema_fast'] - df['ema_slow']).abs() < df['atr']) & \
                 ((df['ema_slow'] - df['ema_trend']).abs() < df['atr'])
    
    return df


# ==============================================================
# STRATEGY LOGIC
# ==============================================================
def generate_signals(df, instrument_name):
    """Generate entry/exit signals based on strategy rules."""
    signals = []
    position = None
    entry_bar_idx = None
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        ts = row['timestamp']
        
        # Session time filter
        session_start = pd.Timestamp(f"{ts.date()} {PARAMS['session_start']}").tz_localize(None)
        session_end = pd.Timestamp(f"{ts.date()} {PARAMS['session_end']}").tz_localize(None)
        no_trade_until = session_start + pd.Timedelta(minutes=PARAMS['no_trade_first_min'])
        
        if ts < no_trade_until or ts > session_end:
            # Force close at session end
            if position and ts >= session_end:
                signals.append({
                    'timestamp': ts,
                    'type': 'EXIT',
                    'price': row['close'],
                    'reason': 'SESSION_END',
                    'position': position
                })
                position = None
            continue
        
        # Max hold time
        if position and entry_bar_idx is not None:
            hold_min = (ts - df.iloc[entry_bar_idx]['timestamp']).total_seconds() / 60
            if hold_min >= PARAMS['max_hold_minutes']:
                signals.append({
                    'timestamp': ts,
                    'type': 'EXIT',
                    'price': row['close'],
                    'reason': 'MAX_HOLD',
                    'position': position
                })
                position = None
                entry_bar_idx = None
                continue
        
        # --- ENTRY LOGIC ---
        if position is None:
            # Long setup
            trend_ok = row['trend_up'] or row['coil']
            adx_ok = row['adx'] >= PARAMS['adx_threshold']
            vol_ok = row['volume'] >= row['vol_avg'] * PARAMS['volume_mult']
            
            # Pullback to EMA9
            pullback_long = (prev_row['low'] <= prev_row['ema_fast']) and (row['close'] > row['ema_fast'])
            
            # Rejection wick at EMA9
            wick_long = (prev_row['lower_wick'] / prev_row['range'] >= PARAMS['wick_ratio']) if prev_row['range'] > 0 else False
            
            # VWAP confirmation
            vwap_ok_long = row['close'] > row['vwap']
            
            # RSI not overbought (approximate via price position)
            rsi_ok_long = row['close'] < row['ema_fast'] + 2 * row['atr']
            
            long_signal = trend_ok and adx_ok and vol_ok and pullback_long and wick_long and vwap_ok_long and rsi_ok_long
            
            # Short setup (mirror)
            trend_ok_s = row['trend_down'] or row['coil']
            pullback_short = (prev_row['high'] >= prev_row['ema_fast']) and (row['close'] < row['ema_fast'])
            wick_short = (prev_row['upper_wick'] / prev_row['range'] >= PARAMS['wick_ratio']) if prev_row['range'] > 0 else False
            vwap_ok_short = row['close'] < row['vwap']
            rsi_ok_short = row['close'] > row['ema_fast'] - 2 * row['atr']
            
            short_signal = trend_ok_s and adx_ok and vol_ok and pullback_short and wick_short and vwap_ok_short and rsi_ok_short
            
            if long_signal:
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                sl = min(row['low'] - 0.15 * atr_val, row['close'] - 0.5 * atr_val)
                sl = max(sl, row['close'] - 2 * atr_val)  # Cap at 2 ATR
                tp = row['close'] + PARAMS['atr_tp_mult'] * (row['close'] - sl)
                
                position = {
                    'side': 'LONG',
                    'entry_price': row['close'],
                    'sl': sl,
                    'tp': tp,
                    'entry_time': ts,
                    'atr_at_entry': atr_val
                }
                entry_bar_idx = i
                signals.append({
                    'timestamp': ts,
                    'type': 'ENTRY',
                    'price': row['close'],
                    'side': 'LONG',
                    'sl': sl,
                    'tp': tp,
                    'reason': 'PULLBACK_EMA9'
                })
            
            elif short_signal:
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                sl = max(row['high'] + 0.15 * atr_val, row['close'] + 0.5 * atr_val)
                sl = min(sl, row['close'] + 2 * atr_val)
                tp = row['close'] - PARAMS['atr_tp_mult'] * (sl - row['close'])
                
                position = {
                    'side': 'SHORT',
                    'entry_price': row['close'],
                    'sl': sl,
                    'tp': tp,
                    'entry_time': ts,
                    'atr_at_entry': atr_val
                }
                entry_bar_idx = i
                signals.append({
                    'timestamp': ts,
                    'type': 'ENTRY',
                    'price': row['close'],
                    'side': 'SHORT',
                    'sl': sl,
                    'tp': tp,
                    'reason': 'PULLBACK_EMA9'
                })
        
        # --- EXIT LOGIC ---
        else:
            if position['side'] == 'LONG':
                # Check SL
                if row['low'] <= position['sl']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['sl'],
                        'reason': 'STOP_LOSS',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
                # Check TP
                elif row['high'] >= position['tp']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['tp'],
                        'reason': 'TAKE_PROFIT',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
            
            elif position['side'] == 'SHORT':
                # Check SL
                if row['high'] >= position['sl']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['sl'],
                        'reason': 'STOP_LOSS',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
                # Check TP
                elif row['low'] <= position['tp']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['tp'],
                        'reason': 'TAKE_PROFIT',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
    
    return signals


# ==============================================================
# IMPROVED STRATEGY LOGIC (v2)
# ==============================================================
def generate_signals_v2(df, instrument_name):
    """Generate entry/exit signals with daily trade cap and improved risk management."""
    signals = []
    position = None
    entry_bar_idx = None
    daily_trades = {}
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        ts = row['timestamp']
        day_key = ts.date()
        
        # Session time filter
        session_start = pd.Timestamp(f"{ts.date()} {PARAMS['session_start']}").tz_localize(None)
        session_end = pd.Timestamp(f"{ts.date()} {PARAMS['session_end']}").tz_localize(None)
        no_trade_until = session_start + pd.Timedelta(minutes=PARAMS['no_trade_first_min'])
        
        if ts < no_trade_until or ts > session_end:
            # Force close at session end
            if position and ts >= session_end:
                signals.append({
                    'timestamp': ts,
                    'type': 'EXIT',
                    'price': row['close'],
                    'reason': 'SESSION_END',
                    'position': position
                })
                position = None
            continue
        
        # Max hold time
        if position and entry_bar_idx is not None:
            hold_min = (ts - df.iloc[entry_bar_idx]['timestamp']).total_seconds() / 60
            if hold_min >= PARAMS['max_hold_minutes']:
                signals.append({
                    'timestamp': ts,
                    'type': 'EXIT',
                    'price': row['close'],
                    'reason': 'MAX_HOLD',
                    'position': position
                })
                position = None
                entry_bar_idx = None
                continue
        
        # --- ENTRY LOGIC ---
        if position is None:
            # Daily trade cap check
            if daily_trades.get(day_key, 0) >= PARAMS['max_trades_per_day']:
                continue
            
            # Minimum ATR filter (avoid dead markets)
            atr_pct = row['atr'] / row['close'] if row['close'] > 0 else 0
            if atr_pct < PARAMS['min_atr_threshold']:
                continue
            
            # Long setup
            trend_ok = row['trend_up'] or row['coil']
            adx_ok = row['adx'] >= PARAMS['adx_threshold']
            vol_ok = row['volume'] >= row['vol_avg'] * PARAMS['volume_mult']
            
            # Pullback to EMA9
            pullback_long = (prev_row['low'] <= prev_row['ema_fast']) and (row['close'] > row['ema_fast'])
            
            # Rejection wick at EMA9
            wick_long = (prev_row['lower_wick'] / prev_row['range'] >= PARAMS['wick_ratio']) if prev_row['range'] > 0 else False
            
            # VWAP confirmation
            vwap_ok_long = row['close'] > row['vwap']
            
            # RSI not overbought (approximate via price position)
            rsi_ok_long = row['close'] < row['ema_fast'] + 2 * row['atr']
            
            long_signal = trend_ok and adx_ok and vol_ok and pullback_long and wick_long and vwap_ok_long and rsi_ok_long
            
            # Short setup (mirror)
            trend_ok_s = row['trend_down'] or row['coil']
            pullback_short = (prev_row['high'] >= prev_row['ema_fast']) and (row['close'] < row['ema_fast'])
            wick_short = (prev_row['upper_wick'] / prev_row['range'] >= PARAMS['wick_ratio']) if prev_row['range'] > 0 else False
            vwap_ok_short = row['close'] < row['vwap']
            rsi_ok_short = row['close'] > row['ema_fast'] - 2 * row['atr']
            
            short_signal = trend_ok_s and adx_ok and vol_ok and pullback_short and wick_short and vwap_ok_short and rsi_ok_short
            
            if long_signal:
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                # Wider SL: 2 ATR from entry, or below swing low
                sl = min(row['low'] - 0.1 * atr_val, row['close'] - PARAMS['atr_sl_mult'] * atr_val)
                tp = row['close'] + PARAMS['atr_tp_mult'] * (row['close'] - sl)
                
                position = {
                    'side': 'LONG',
                    'entry_price': row['close'],
                    'sl': sl,
                    'tp': tp,
                    'entry_time': ts,
                    'atr_at_entry': atr_val
                }
                entry_bar_idx = i
                daily_trades[day_key] = daily_trades.get(day_key, 0) + 1
                signals.append({
                    'timestamp': ts,
                    'type': 'ENTRY',
                    'price': row['close'],
                    'side': 'LONG',
                    'sl': sl,
                    'tp': tp,
                    'reason': 'PULLBACK_EMA9'
                })
            
            elif short_signal:
                atr_val = row['atr'] if not pd.isna(row['atr']) else 0
                sl = max(row['high'] + 0.1 * atr_val, row['close'] + PARAMS['atr_sl_mult'] * atr_val)
                tp = row['close'] - PARAMS['atr_tp_mult'] * (sl - row['close'])
                
                position = {
                    'side': 'SHORT',
                    'entry_price': row['close'],
                    'sl': sl,
                    'tp': tp,
                    'entry_time': ts,
                    'atr_at_entry': atr_val
                }
                entry_bar_idx = i
                daily_trades[day_key] = daily_trades.get(day_key, 0) + 1
                signals.append({
                    'timestamp': ts,
                    'type': 'ENTRY',
                    'price': row['close'],
                    'side': 'SHORT',
                    'sl': sl,
                    'tp': tp,
                    'reason': 'PULLBACK_EMA9'
                })
        
        # --- EXIT LOGIC ---
        else:
            if position['side'] == 'LONG':
                # Check SL
                if row['low'] <= position['sl']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['sl'],
                        'reason': 'STOP_LOSS',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
                # Check TP
                elif row['high'] >= position['tp']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['tp'],
                        'reason': 'TAKE_PROFIT',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
            
            elif position['side'] == 'SHORT':
                # Check SL
                if row['high'] >= position['sl']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['sl'],
                        'reason': 'STOP_LOSS',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
                # Check TP
                elif row['low'] <= position['tp']:
                    signals.append({
                        'timestamp': ts,
                        'type': 'EXIT',
                        'price': position['tp'],
                        'reason': 'TAKE_PROFIT',
                        'position': position
                    })
                    position = None
                    entry_bar_idx = None
    
    return signals


# ==============================================================
# BACKTEST ENGINE
# ==============================================================
def run_backtest(symbol, config, start_date, end_date=None):
    """Run complete backtest for a symbol."""
    print(f"\n{'='*60}")
    print(f"BACKTESTING: {symbol}")
    print(f"{'='*60}")
    
    # For NSE: fetch INDEX data for signals, FUTURES for P&L
    # For MCX: futures data serves both purposes
    if symbol in ["CRUDEOIL", "GOLD", "SILVER"]:
        # MCX - single data source
        sec_id = get_active_futures_contract(symbol, start_date)
        if not sec_id:
            print(f"  No active futures contract found for {symbol}")
            return None
        print(f"  Using futures contract ID: {sec_id}")
        
        print(f"  Fetching historical data from {start_date.date()}...")
        df = fetch_historical_data(
            sec_id, 
            config["futures_segment"], 
            config["instrument_type"],
            start_date, 
            end_date
        )
        price_df = df  # Same data for signals and P&L
        
    else:
        # NSE - Index for signals, Futures for P&L
        print(f"  Fetching INDEX data (signals) from {start_date.date()}...")
        index_df = fetch_index_data(config["index_id"], start_date, end_date)
        
        print(f"  Fetching FUTURES data (P&L) from {start_date.date()}...")
        fut_sec_id = get_active_futures_contract(symbol, start_date)
        if not fut_sec_id:
            print(f"  No active futures contract found for {symbol}")
            return None
        print(f"  Using futures contract ID: {fut_sec_id}")
        
        futures_df = fetch_historical_data(
            fut_sec_id,
            config["futures_segment"],
            config["instrument_type"],
            start_date,
            end_date
        )
        
        if index_df.empty or futures_df.empty:
            print(f"  No data retrieved for {symbol}")
            return None
        
        # Merge on timestamp (nearest)
        index_df = index_df.set_index('timestamp')
        futures_df = futures_df.set_index('timestamp')
        
        # Align futures to index timestamps (forward fill)
        price_df = index_df.join(futures_df, how='left', rsuffix='_fut').ffill()
        price_df = price_df.reset_index()
        
        print(f"  Index bars: {len(index_df)}, Futures bars: {len(futures_df)}, Aligned: {len(price_df)}")
    
    if price_df.empty:
        print(f"  No data retrieved for {symbol}")
        return None
    
    print(f"  Total bars for signals: {len(price_df)}")
    
    # Calculate indicators on index/price data
    print("  Calculating indicators...")
    df = calculate_indicators(price_df)
    
    # Generate signals with daily trade cap
    print("  Generating signals...")
    signals = generate_signals_v2(df, symbol)
    
    # Process trades using FUTURES prices for P&L
    trades = []
    current_trade = None
    daily_trade_count = {}
    
    for sig in signals:
        ts = sig['timestamp']
        day_key = ts.date()
        
        if sig['type'] == 'ENTRY':
            # Check daily trade cap
            if daily_trade_count.get(day_key, 0) >= PARAMS['max_trades_per_day']:
                continue
            
            current_trade = {
                'symbol': symbol,
                'side': sig['side'],
                'entry_time': ts,
                'entry_price': sig['price'],  # This is futures price (aligned)
                'sl': sig['sl'],
                'tp': sig['tp'],
                'reason': sig['reason']
            }
            daily_trade_count[day_key] = daily_trade_count.get(day_key, 0) + 1
            
        elif sig['type'] == 'EXIT' and current_trade:
            exit_price = sig['price']  # Futures price
            entry_price = current_trade['entry_price']
            
            if current_trade['side'] == 'LONG':
                gross_pnl = (exit_price - entry_price) * config['point_value']
            else:
                gross_pnl = (entry_price - exit_price) * config['point_value']
            
            # Costs: commission + slippage
            commission = entry_price * config['lot_size'] * PARAMS['commission_pct'] * 2
            slippage = config['slippage_per_fill'] * config['point_value'] * 2
            total_costs = commission + slippage
            
            net_pnl = gross_pnl - total_costs
            
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
    
    # Print results
    if trades:
        trades_df = pd.DataFrame(trades)
        print(f"\n  === RESULTS for {symbol} ===")
        print(f"  Total trades: {len(trades_df)}")
        print(f"  Win rate: {(trades_df['net_pnl'] > 0).mean() * 100:.1f}%")
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
        
        # By exit reason
        print(f"\n  By exit reason:")
        for reason, grp in trades_df.groupby('exit_reason'):
            wr = (grp['net_pnl'] > 0).mean() * 100
            print(f"    {reason}: {len(grp)} trades, WR={wr:.1f}%, Net={grp['net_pnl'].sum():.2f}")
        
        # Monthly breakdown
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
    # Test period: last 6 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    print(f"Backtest period: {start_date.date()} to {end_date.date()}")
    print(f"Strategy: VWAP + EMA Pullback with ATR Risk Management")
    print(f"Parameters: {PARAMS}")
    
    all_results = {}
    
    for symbol, config in INSTRUMENTS.items():
        try:
            result = run_backtest(symbol, config, start_date, end_date)
            if result is not None and not result.empty:
                all_results[symbol] = result
        except Exception as e:
            print(f"  ERROR backtesting {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Combined portfolio results
    if all_results:
        print(f"\n{'='*60}")
        print("PORTFOLIO SUMMARY")
        print(f"{'='*60}")
        
        all_trades = pd.concat(all_results.values(), ignore_index=True)
        all_trades = all_trades.sort_values('exit_time')
        
        print(f"\nTotal trades: {len(all_trades)}")
        print(f"Win rate: {(all_trades['net_pnl'] > 0).mean() * 100:.1f}%")
        print(f"Net P&L: {all_trades['net_pnl'].sum():,.2f} pts")
        print(f"Gross P&L: {all_trades['gross_pnl'].sum():,.2f} pts")
        print(f"Total costs: {all_trades['costs'].sum():,.2f} pts")
        
        wins = all_trades[all_trades['net_pnl'] > 0]
        losses = all_trades[all_trades['net_pnl'] <= 0]
        if len(wins) > 0 and len(losses) > 0:
            pf = wins['net_pnl'].sum() / abs(losses['net_pnl'].sum())
            print(f"Profit Factor: {pf:.2f}")
        
        # Per instrument
        print(f"\nPer Instrument:")
        for sym, grp in all_trades.groupby('symbol'):
            wr = (grp['net_pnl'] > 0).mean() * 100
            print(f"  {sym}: {len(grp)} trades, Net={grp['net_pnl'].sum():.2f}, WR={wr:.1f}%")
        
        # Save combined trades
        output_path = f"dhan_backtest_results_{datetime.now().strftime('%Y%m%d')}.csv"
        all_trades.to_csv(output_path, index=False)
        print(f"\nSaved combined results to: {output_path}")