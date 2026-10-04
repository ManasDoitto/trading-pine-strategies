"""
Test SIMPLE EMA Pullback strategies (Crude v2.1 style) on Dhan data
These worked better in repo: PF 1.14, Sharpe 0.68 for Crude
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

INSTRUMENTS = {
    "BANKNIFTY": {"index_id": "25", "futures_segment": "NSE_FNO", "instrument_type": "FUTIDX", "point_value": 30, "lot_size": 15, "slippage": 5},
    "CRUDEOIL":  {"futures_segment": "MCX_COMM", "instrument_type": "FUTCOM", "point_value": 100, "lot_size": 100, "slippage": 2},
    "GOLD":      {"futures_segment": "MCX_COMM", "instrument_type": "FUTCOM", "point_value": 100, "lot_size": 100, "slippage": 2},
    "SILVER":    {"futures_segment": "MCX_COMM", "instrument_type": "FUTCOM", "point_value": 30, "lot_size": 30, "slippage": 3},
}

COMMISSION_PCT = 0.0002

# ==============================================================
# CRUDE v2.1 STYLE: Simple EMA 9/22 Pullback
# Repo: PF 1.14, 37.4% WR, 17 trades/mo, Sharpe 0.68
# ==============================================================
def calculate_ema_pullback_indicators(df):
    df = df.copy()
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema22'] = df['close'].ewm(span=22, adjust=False).mean()
    
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    df['trend_up'] = df['ema9'] > df['ema22']
    df['trend_down'] = df['ema9'] < df['ema22']
    
    df['pullback_long'] = (df['low'].shift(1) <= df['ema9'].shift(1)) & (df['close'] > df['ema9'])
    df['pullback_short'] = (df['high'].shift(1) >= df['ema9'].shift(1)) & (df['close'] < df['ema9'])
    
    df['vol_avg'] = df['volume'].rolling(20).mean()
    
    df['date'] = df['timestamp'].dt.date
    df['typical'] = (df['high'] + df['low'] + df['close']) / 3
    df['pv'] = df['typical'] * df['volume']
    df['vwap'] = df.groupby('date')['pv'].cumsum() / df.groupby('date')['volume'].cumsum()
    
    # Precompute swing high/low
    df['swing_high_10'] = df['high'].rolling(10).max()
    df['swing_low_10'] = df['low'].rolling(10).min()
    
    return df


def generate_ema_pullback_signals(df, symbol):
    """
    Simple EMA 9/22 Pullback (Crude v2.1 style):
    - Trend: EMA9 > EMA22 (long) / < (short)
    - Pullback to EMA9
    - Entry: Market at close of pullback bar (or next bar open)
    - SL: Beyond swing + 0.1*ATR, min 1.5*ATR (Crude), 2.5*ATR (Silver), max 3*ATR (Crude), 5*ATR (Silver)
    - Target: 2R (Crude v2.1), 3R (Gold/Silver base)
    - Session: Crude/Silver 09:15-23:30, Gold 17:30-00:30
    - One position at a time
    - Silver: Daily loss limit 350 pts (gross P&L)
    """
    signals = []
    position = None
    daily_gross_pnl = 0
    current_day = None
    
    # Symbol params
    if symbol == "SILVER":
        sl_min, sl_max, target_r = 2.5, 5.0, 3.0
        daily_limit = 350
        sess_start, sess_end = "09:15", "23:30"
    elif symbol == "GOLD":
        sl_min, sl_max, target_r = 1.5, 3.0, 3.0
        daily_limit = None
        sess_start, sess_end = "17:30", "00:30"
    else:  # CRUDEOIL
        sl_min, sl_max, target_r = 1.5, 3.0, 2.0  # v2.1 uses 2R
        daily_limit = None
        sess_start, sess_end = "09:15", "23:30"
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        ts = row['timestamp']
        day_key = ts.date()
        
        if current_day != day_key:
            daily_gross_pnl = 0
            current_day = day_key
        
        if daily_limit and daily_gross_pnl <= -daily_limit:
            continue
        
        # Session
        if symbol == "GOLD" and sess_end == "00:30":
            s_start = pd.Timestamp(f"{ts.date()} {sess_start}").tz_localize(None)
            s_end = pd.Timestamp(f"{(ts + timedelta(days=1)).date()} {sess_end}").tz_localize(None)
            in_sess = s_start <= ts <= s_end
        else:
            s_start = pd.Timestamp(f"{ts.date()} {sess_start}").tz_localize(None)
            s_end = pd.Timestamp(f"{ts.date()} {sess_end}").tz_localize(None)
            in_sess = s_start <= ts <= s_end
        
        if not in_sess:
            if position:
                signals.append({'ts': ts, 'type': 'EXIT', 'px': row['close'], 'reason': 'SESSION_END'})
                position = None
            continue
        
        # Exit
        if position:
            atr = position['atr']
            if position['side'] == 'LONG':
                if row['low'] <= position['sl']:
                    pnl = position['sl'] - position['entry']
                    daily_gross_pnl += pnl
                    signals.append({'ts': ts, 'type': 'EXIT', 'px': position['sl'], 'reason': 'SL'})
                    position = None
                elif row['high'] >= position['tp']:
                    pnl = position['tp'] - position['entry']
                    daily_gross_pnl += pnl
                    signals.append({'ts': ts, 'type': 'EXIT', 'px': position['tp'], 'reason': 'TP'})
                    position = None
            else:
                if row['high'] >= position['sl']:
                    pnl = position['entry'] - position['sl']
                    daily_gross_pnl += pnl
                    signals.append({'ts': ts, 'type': 'EXIT', 'px': position['sl'], 'reason': 'SL'})
                    position = None
                elif row['low'] <= position['tp']:
                    pnl = position['entry'] - position['tp']
                    daily_gross_pnl += pnl
                    signals.append({'ts': ts, 'type': 'EXIT', 'px': position['tp'], 'reason': 'TP'})
                    position = None
        
        # Entry
        if not position:
            atr = row['atr'] if not pd.isna(row['atr']) else 0
            if atr == 0:
                continue
            
            vol_ok = row['volume'] >= row['vol_avg']
            vwap_long = row['close'] > row['vwap']
            vwap_short = row['close'] < row['vwap']
            
            # Long: trend up, pullback to EMA9, volume, vwap
            if row['trend_up'] and prev['pullback_long'] and vol_ok and vwap_long:
                swing_low = prev['swing_low_10']
                if pd.isna(swing_low):
                    swing_low = prev['low']
                
                sl_cand = swing_low - 0.1 * atr
                sl = max(sl_cand, row['close'] - sl_min * atr)
                if (row['close'] - sl) > sl_max * atr:
                    continue
                tp = row['close'] + target_r * (row['close'] - sl)
                
                position = {'side': 'LONG', 'entry': row['close'], 'sl': sl, 'tp': tp, 'atr': atr, 'entry_ts': ts}
                signals.append({'ts': ts, 'type': 'ENTRY', 'px': row['close'], 'side': 'LONG', 'sl': sl, 'tp': tp, 'reason': 'EMA_PULLBACK'})
            
            # Short
            elif row['trend_down'] and prev['pullback_short'] and vol_ok and vwap_short:
                swing_high = prev['swing_high_10']
                if pd.isna(swing_high):
                    swing_high = prev['high']
                
                sl_cand = swing_high + 0.1 * atr
                sl = min(sl_cand, row['close'] + sl_min * atr)
                if (sl - row['close']) > sl_max * atr:
                    continue
                tp = row['close'] - target_r * (sl - row['close'])
                
                position = {'side': 'SHORT', 'entry': row['close'], 'sl': sl, 'tp': tp, 'atr': atr, 'entry_ts': ts}
                signals.append({'ts': ts, 'type': 'ENTRY', 'px': row['close'], 'side': 'SHORT', 'sl': sl, 'tp': tp, 'reason': 'EMA_PULLBACK'})
    
    return signals


def fetch_historical_data(sec_id, seg, inst, start, end=None, batch=90):
    if end is None: end = datetime.now()
    all_data = []
    curr_end = end
    while curr_end > start:
        curr_start = max(start, curr_end - timedelta(days=batch-1))
        f, t = curr_start.strftime("%Y-%m-%d"), curr_end.strftime("%Y-%m-%d")
        try:
            req = dhan.intraday_minute_data(security_id=str(sec_id), exchange_segment=seg, instrument_type=inst, from_date=f, to_date=t)
            if req.get("status") == "success":
                d = req.get("data", {})
                if d and d.get("timestamp"):
                    all_data.append(pd.DataFrame({"timestamp": d["timestamp"], "open": d["open"], "high": d["high"], "low": d["low"], "close": d["close"], "volume": d["volume"]}))
            time.sleep(0.5)
        except Exception as e:
            print(f"  Err: {e}")
        curr_end = curr_start - timedelta(days=1)
    if all_data:
        df = pd.concat(all_data).reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(df["timestamp"]):
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        if df['timestamp'].dt.tz is None:
            df['timestamp'] += pd.Timedelta(hours=5, minutes=30)
        return df.sort_values('timestamp').reset_index(drop=True)
    return pd.DataFrame()


def fetch_index(idx_id, start, end=None):
    return fetch_historical_data(idx_id, "IDX_I", "INDEX", start, end)


def get_fut_id(sym, dt):
    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    df = pd.read_csv(url, low_memory=False)
    if sym in ["CRUDEOIL", "GOLD", "SILVER"]:
        df = df[(df.SEM_EXM_EXCH_ID=='MCX') & (df.SEM_INSTRUMENT_NAME=='FUTCOM') & (df.SEM_CUSTOM_SYMBOL.str.startswith(sym))]
    else:
        df = df[(df.SEM_EXM_EXCH_ID=='NSE') & (df.SEM_INSTRUMENT_NAME=='FUTIDX') & (df.SEM_CUSTOM_SYMBOL.str.startswith(sym))]
    if df.empty: return None
    df['SEM_EXPIRY_DATE'] = pd.to_datetime(df['SEM_EXPIRY_DATE'])
    df = df[df.SEM_EXPIRY_DATE >= pd.Timestamp(dt)].sort_values('SEM_EXPIRY_DATE')
    return str(df.iloc[0].SEM_SMST_SECURITY_ID) if not df.empty else None


def run_backtest(sym, cfg, start, end=None):
    print(f"\n{'='*50}")
    print(f"{sym} EMA 9/22 Pullback")
    print(f"{'='*50}")
    
    if sym == "BANKNIFTY":
        idx_df = fetch_index(cfg["index_id"], start, end)
        fut_id = get_fut_id(sym, start)
        if not fut_id: return None
        fut_df = fetch_historical_data(fut_id, cfg["futures_segment"], cfg["instrument_type"], start, end)
        if idx_df.empty or fut_df.empty: return None
        idx_df = idx_df.set_index('timestamp')
        fut_df = fut_df.set_index('timestamp')
        df = idx_df.join(fut_df, how='left', rsuffix='_f').ffill().reset_index()
    else:
        fut_id = get_fut_id(sym, start)
        if not fut_id: return None
        df = fetch_historical_data(fut_id, cfg["futures_segment"], cfg["instrument_type"], start, end)
        if df.empty: return None
    
    print(f"  Bars: {len(df)}")
    df = calculate_ema_pullback_indicators(df)
    sigs = generate_ema_pullback_signals(df, sym)
    
    # Process
    trades = []
    pos = None
    for s in sigs:
        if s['type'] == 'ENTRY':
            pos = {'sym': sym, 'side': s['side'], 'entry_ts': s['ts'], 'entry_px': s['px'], 'sl': s['sl'], 'tp': s['tp'], 'reason': s['reason']}
        elif s['type'] == 'EXIT' and pos:
            ep = s['px']
            if pos['side'] == 'LONG':
                gp = (ep - pos['entry_px']) * cfg['point_value']
            else:
                gp = (pos['entry_px'] - ep) * cfg['point_value']
            comm = pos['entry_px'] * cfg['lot_size'] * COMMISSION_PCT * 2
            slip = cfg['slippage'] * cfg['point_value'] * 2
            npnl = gp - comm - slip
            trades.append({**pos, 'exit_ts': s['ts'], 'exit_px': ep, 'exit_reason': s['reason'], 'gross': gp, 'costs': comm+slip, 'net': npnl, 'hold_m': (s['ts']-pos['entry_ts']).total_seconds()/60})
            pos = None
    
    return print_results(trades, sym, cfg)


def print_results(trades, sym, cfg):
    if not trades:
        print("  No trades")
        return pd.DataFrame()
    td = pd.DataFrame(trades)
    wr = (td.net > 0).mean() * 100
    print(f"  Trades: {len(td)}, WR: {wr:.1f}%, Net: {td.net.sum():,.0f}, Gross: {td.gross.sum():,.0f}, Costs: {td.costs.sum():,.0f}")
    w, l = td[td.net>0], td[td.net<=0]
    if len(w) and len(l):
        print(f"  PF: {w.net.sum()/abs(l.net.sum()):.2f}, AvgW: {w.net.mean():.0f}, AvgL: {l.net.mean():.0f}, Hold: {td.hold_m.mean():.0f}m, /mo: {len(td)/6:.1f}")
    for r, g in td.groupby('exit_reason'):
        print(f"    {r}: {len(g)}, WR={(g.net>0).mean()*100:.1f}%, Net={g.net.sum():.0f}")
    td['mo'] = td.exit_ts.dt.to_period('M')
    for m, g in td.groupby('mo'):
        print(f"    {m}: {len(g)}, Net={g.net.sum():.0f}, WR={(g.net>0).mean()*100:.1f}%")
    return td


if __name__ == "__main__":
    end = datetime.now()
    start = end - timedelta(days=180)
    print(f"Period: {start.date()} to {end.date()}")
    
    all_res = {}
    for sym, cfg in INSTRUMENTS.items():
        try:
            res = run_backtest(sym, cfg, start, end)
            if res is not None and not res.empty:
                all_res[sym] = res
        except Exception as e:
            print(f"  ERROR {sym}: {e}")
            import traceback; traceback.print_exc()
    
    if all_res:
        print(f"\n{'='*50}")
        print("PORTFOLIO")
        print(f"{'='*50}")
        all_t = pd.concat(all_res.values()).sort_values('exit_ts')
        wr = (all_t.net>0).mean()*100
        print(f"Total: {len(all_t)}, WR: {wr:.1f}%, Net: {all_t.net.sum():,.0f}")
        for s, g in all_t.groupby('sym'):
            w, l = g[g.net>0], g[g.net<=0]
            pf = w.net.sum()/abs(l.net.sum()) if len(l) else float('inf')
            print(f"  {s}: {len(g)}, Net={g.net.sum():.0f}, WR={(g.net>0).mean()*100:.1f}%, PF={pf:.2f}")