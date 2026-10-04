"""
VWAP Mean Reversion Strategy - Designed for Dhan Futures Data
Based on actual trade analysis: intraday only, <2hr hold, avoid Mondays
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
    "BANKNIFTY": {"index_id": "25", "futures_segment": "NSE_FNO", "instrument_type": "FUTIDX", "pv": 30, "lot": 15, "slip": 5},
    "CRUDEOIL":  {"futures_segment": "MCX_COMM", "instrument_type": "FUTCOM", "pv": 100, "lot": 100, "slip": 2},
    "GOLD":      {"futures_segment": "MCX_COMM", "instrument_type": "FUTCOM", "pv": 100, "lot": 100, "slip": 2},
    "SILVER":    {"futures_segment": "MCX_COMM", "instrument_type": "FUTCOM", "pv": 30, "lot": 30, "slip": 3},
}

COMM = 0.0002

# Strategy params - tuned for intraday mean reversion
PARAMS = {
    "vwap_lookback": 20,
    "band_mult": 2.0,        # 2 std dev bands
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "atr_period": 14,
    "atr_sl_mult": 1.5,
    "target_r": 2.0,
    "max_hold_min": 120,     # Max 2 hours (matches winning pattern)
    "session_start": "09:30",
    "session_end": "15:00",
    "close_by": "15:15",
    "skip_monday": True,     # Monday was -420K in actual trades
    "min_atr_pct": 0.0005,   # Min ATR as % of price
    "max_trades_day": 3,
}

def fetch_data(sec_id, seg, inst, start, end=None, batch=90):
    if end is None: end = datetime.now()
    all_d = []
    ce = end
    while ce > start:
        cs = max(start, ce - timedelta(days=batch-1))
        f, t = cs.strftime("%Y-%m-%d"), ce.strftime("%Y-%m-%d")
        try:
            r = dhan.intraday_minute_data(security_id=str(sec_id), exchange_segment=seg, instrument_type=inst, from_date=f, to_date=t)
            if r.get("status") == "success":
                d = r.get("data", {})
                if d and d.get("timestamp"):
                    all_d.append(pd.DataFrame({"ts": d["timestamp"], "o": d["open"], "h": d["high"], "l": d["low"], "c": d["close"], "v": d["volume"]}))
            time.sleep(0.5)
        except Exception as e:
            print(f"  Err: {e}")
        ce = cs - timedelta(days=1)
    if all_d:
        df = pd.concat(all_d).reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(df["ts"]):
            df['ts'] = pd.to_datetime(df['ts'], unit='s')
        else:
            df['ts'] = pd.to_datetime(df['ts'])
        if df['ts'].dt.tz is None:
            df['ts'] += pd.Timedelta(hours=5, minutes=30)
        return df.sort_values('ts').reset_index(drop=True)
    return pd.DataFrame()

def fetch_index(idx_id, start, end=None):
    return fetch_data(idx_id, "IDX_I", "INDEX", start, end)

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

def calc_indicators(df):
    df = df.copy()
    # VWAP
    df['date'] = df['ts'].dt.date
    df['tp'] = (df['h'] + df['l'] + df['c']) / 3
    df['pv'] = df['tp'] * df['v']
    df['vwap'] = df.groupby('date')['pv'].cumsum() / df.groupby('date')['v'].cumsum()
    # VWAP rolling std
    df['vwap_std'] = df.groupby('date')['tp'].transform(lambda x: (x * df.loc[x.index, 'v']).rolling(PARAMS['vwap_lookback']).sum() / df.loc[x.index, 'v'].rolling(PARAMS['vwap_lookback']).sum())
    # Actually compute rolling VWAP std properly
    df['tp_sq'] = df['tp'] ** 2
    df['pv_sq'] = df['tp_sq'] * df['v']
    df['vwap_sq'] = df.groupby('date')['pv_sq'].cumsum() / df.groupby('date')['v'].cumsum()
    df['var'] = df['vwap_sq'] - df['vwap'] ** 2
    df['vwap_sd'] = np.sqrt(df['var'].clip(lower=0))
    
    # Upper/Lower bands
    df['upper'] = df['vwap'] + PARAMS['band_mult'] * df['vwap_sd']
    df['lower'] = df['vwap'] - PARAMS['band_mult'] * df['vwap_sd']
    
    # RSI
    delta = df['c'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/PARAMS['rsi_period'], adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/PARAMS['rsi_period'], adjust=False).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR
    hl = df['h'] - df['l']
    hc = (df['h'] - df['c'].shift()).abs()
    lc = (df['l'] - df['c'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=PARAMS['atr_period'], adjust=False).mean()
    
    # ATR as % of price
    df['atr_pct'] = df['atr'] / df['c']
    
    # Volume
    df['vol_avg'] = df['v'].rolling(20).mean()
    
    return df

def gen_signals(df, sym):
    sigs = []
    pos = None
    daily_trades = 0
    curr_day = None
    
    # Session times
    if sym == "GOLD":
        s_start, s_end = "17:30", "00:30"
    else:
        s_start, s_end = PARAMS['session_start'], PARAMS['session_end']
    
    for i in range(len(df)):
        r = df.iloc[i]
        ts = r['ts']
        day = ts.date()
        
        if curr_day != day:
            daily_trades = 0
            curr_day = day
        
        # Skip Monday
        if PARAMS['skip_monday'] and ts.weekday() == 0:
            continue
        
        # Daily trade limit
        if daily_trades >= PARAMS['max_trades_day']:
            continue
        
        # Session
        if sym == "GOLD" and s_end == "00:30":
            ss = pd.Timestamp(f"{ts.date()} {s_start}").tz_localize(None)
            se = pd.Timestamp(f"{(ts + timedelta(days=1)).date()} {s_end}").tz_localize(None)
            in_sess = ss <= ts <= se
        else:
            ss = pd.Timestamp(f"{ts.date()} {s_start}").tz_localize(None)
            se = pd.Timestamp(f"{ts.date()} {s_end}").tz_localize(None)
            in_sess = ss <= ts <= se
        
        close_by = pd.Timestamp(f"{ts.date()} {PARAMS['close_by']}").tz_localize(None)
        
        if not in_sess or ts > close_by:
            if pos and ts >= close_by:
                sigs.append({'ts': ts, 'type': 'EXIT', 'px': r['c'], 'reason': 'SESSION_END'})
                pos = None
            continue
        
        # Exit
        if pos:
            hold = (ts - pos['entry_ts']).total_seconds() / 60
            if pos['side'] == 'LONG':
                if r['l'] <= pos['sl']:
                    sigs.append({'ts': ts, 'type': 'EXIT', 'px': pos['sl'], 'reason': 'SL'})
                    pos = None
                elif r['h'] >= pos['tp']:
                    sigs.append({'ts': ts, 'type': 'EXIT', 'px': pos['tp'], 'reason': 'TP'})
                    pos = None
                elif hold >= PARAMS['max_hold_min']:
                    sigs.append({'ts': ts, 'type': 'EXIT', 'px': r['c'], 'reason': 'MAX_HOLD'})
                    pos = None
            else:
                if r['h'] >= pos['sl']:
                    sigs.append({'ts': ts, 'type': 'EXIT', 'px': pos['sl'], 'reason': 'SL'})
                    pos = None
                elif r['l'] <= pos['tp']:
                    sigs.append({'ts': ts, 'type': 'EXIT', 'px': pos['tp'], 'reason': 'TP'})
                    pos = None
                elif hold >= PARAMS['max_hold_min']:
                    sigs.append({'ts': ts, 'type': 'EXIT', 'px': r['c'], 'reason': 'MAX_HOLD'})
                    pos = None
        
        # Entry - Mean reversion to VWAP
        if not pos:
            atr = r['atr'] if not pd.isna(r['atr']) else 0
            if atr == 0 or r['atr_pct'] < PARAMS['min_atr_pct']:
                continue
            
            vol_ok = r['v'] >= r['vol_avg']
            if not vol_ok:
                continue
            
            # LONG: Price at lower band, RSI oversold, volume
            if r['c'] <= r['lower'] and r['rsi'] <= PARAMS['rsi_oversold']:
                sl = r['c'] - PARAMS['atr_sl_mult'] * atr
                tp = r['c'] + PARAMS['target_r'] * (r['c'] - sl)
                pos = {'side': 'LONG', 'entry': r['c'], 'sl': sl, 'tp': tp, 'entry_ts': ts, 'atr': atr}
                sigs.append({'ts': ts, 'type': 'ENTRY', 'px': r['c'], 'side': 'LONG', 'sl': sl, 'tp': tp, 'reason': 'VWAP_MR'})
                daily_trades += 1
            
            # SHORT: Price at upper band, RSI overbought
            elif r['c'] >= r['upper'] and r['rsi'] >= PARAMS['rsi_overbought']:
                sl = r['c'] + PARAMS['atr_sl_mult'] * atr
                tp = r['c'] - PARAMS['target_r'] * (sl - r['c'])
                pos = {'side': 'SHORT', 'entry': r['c'], 'sl': sl, 'tp': tp, 'entry_ts': ts, 'atr': atr}
                sigs.append({'ts': ts, 'type': 'ENTRY', 'px': r['c'], 'side': 'SHORT', 'sl': sl, 'tp': tp, 'reason': 'VWAP_MR'})
                daily_trades += 1
    
    return sigs

def run_bt(sym, cfg, start, end=None):
    print(f"\n{'='*50}")
    print(f"{sym} VWAP Mean Reversion")
    print(f"{'='*50}")
    
    if sym == "BANKNIFTY":
        idx = fetch_index(cfg["index_id"], start, end)
        fid = get_fut_id(sym, start)
        if not fid: return None
        fut = fetch_data(fid, cfg["futures_segment"], cfg["instrument_type"], start, end)
        if idx.empty or fut.empty: return None
        idx = idx.set_index('ts')
        fut = fut.set_index('ts')
        df = idx.join(fut, how='left', rsuffix='_f').ffill().reset_index()
    else:
        fid = get_fut_id(sym, start)
        if not fid: return None
        df = fetch_data(fid, cfg["futures_segment"], cfg["instrument_type"], start, end)
        if df.empty: return None
    
    print(f"  Bars: {len(df)}")
    df = calc_indicators(df)
    sigs = gen_signals(df, sym)
    
    trades = []
    pos = None
    for s in sigs:
        if s['type'] == 'ENTRY':
            pos = {'sym': sym, 'side': s['side'], 'entry_ts': s['ts'], 'entry_px': s['px'], 'sl': s['sl'], 'tp': s['tp'], 'reason': s['reason']}
        elif s['type'] == 'EXIT' and pos:
            ep = s['px']
            if pos['side'] == 'LONG':
                gp = (ep - pos['entry_px']) * cfg['pv']
            else:
                gp = (pos['entry_px'] - ep) * cfg['pv']
            c = pos['entry_px'] * cfg['lot'] * COMM * 2
            sl = cfg['slip'] * cfg['pv'] * 2
            npnl = gp - c - sl
            trades.append({**pos, 'exit_ts': s['ts'], 'exit_px': ep, 'exit_reason': s['reason'], 'gross': gp, 'costs': c+sl, 'net': npnl, 'hold_m': (s['ts']-pos['entry_ts']).total_seconds()/60})
            pos = None
    
    return print_res(trades, sym, cfg)

def print_res(trades, sym, cfg):
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
    print(f"Params: {PARAMS}")
    
    all_r = {}
    for s, c in INSTRUMENTS.items():
        try:
            r = run_bt(s, c, start, end)
            if r is not None and not r.empty:
                all_r[s] = r
        except Exception as e:
            print(f"  ERROR {s}: {e}")
            import traceback; traceback.print_exc()
    
    if all_r:
        print(f"\n{'='*50}")
        print("PORTFOLIO")
        print(f"{'='*50}")
        at = pd.concat(all_r.values()).sort_values('exit_ts')
        wr = (at.net>0).mean()*100
        print(f"Total: {len(at)}, WR: {wr:.1f}%, Net: {at.net.sum():,.0f}")
        for s, g in at.groupby('sym'):
            w, l = g[g.net>0], g[g.net<=0]
            pf = w.net.sum()/abs(l.net.sum()) if len(l) else float('inf')
            print(f"  {s}: {len(g)}, Net={g.net.sum():.0f}, WR={(g.net>0).mean()*100:.1f}%, PF={pf:.2f}")