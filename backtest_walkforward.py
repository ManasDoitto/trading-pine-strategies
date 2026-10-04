"""
Walk-forward parameter optimization on Dhan data
Test simple EMA crossover + ATR stop to find profitable params
"""
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from itertools import product

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

# Test on CrudeOil (most liquid MCX)
SYMBOL = "CRUDEOIL"
CONFIG = {"futures_segment": "MCX_COMM", "instrument_type": "FUTCOM", "pv": 100, "lot": 100, "slip": 2}
COMM = 0.0002

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

def get_fut_id(sym, dt):
    url = "https://images.dhan.co/api-data/api-scrip-master.csv"
    df = pd.read_csv(url, low_memory=False)
    df = df[(df.SEM_EXM_EXCH_ID=='MCX') & (df.SEM_INSTRUMENT_NAME=='FUTCOM') & (df.SEM_CUSTOM_SYMBOL.str.startswith(sym))]
    if df.empty: return None
    df['SEM_EXPIRY_DATE'] = pd.to_datetime(df['SEM_EXPIRY_DATE'])
    df = df[df.SEM_EXPIRY_DATE >= pd.Timestamp(dt)].sort_values('SEM_EXPIRY_DATE')
    return str(df.iloc[0].SEM_SMST_SECURITY_ID) if not df.empty else None

def test_params(df, fast, slow, atr_mult, target_r, max_hold, skip_mon):
    """Test single param set, return net P&L"""
    df = df.copy()
    
    # EMAs
    df[f'ema{fast}'] = df['c'].ewm(span=fast, adjust=False).mean()
    df[f'ema{slow}'] = df['c'].ewm(span=slow, adjust=False).mean()
    
    # ATR
    hl = df['h'] - df['l']
    hc = (df['h'] - df['c'].shift()).abs()
    lc = (df['l'] - df['c'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    # Signals: EMA crossover
    df['cross_up'] = (df[f'ema{fast}'] > df[f'ema{slow}']) & (df[f'ema{fast}'].shift(1) <= df[f'ema{slow}'].shift(1))
    df['cross_dn'] = (df[f'ema{fast}'] < df[f'ema{slow}']) & (df[f'ema{fast}'].shift(1) >= df[f'ema{slow}'].shift(1))
    
    # Session filter
    df['date'] = df['ts'].dt.date
    df['time'] = df['ts'].dt.time
    mkt_open = pd.Timestamp("09:15").time()
    mkt_close = pd.Timestamp("15:15").time()
    
    trades = []
    pos = None
    
    for i in range(len(df)):
        r = df.iloc[i]
        ts = r['ts']
        
        # Skip Monday
        if skip_mon and ts.weekday() == 0:
            if pos:
                trades.append({'entry_ts': pos['entry_ts'], 'exit_ts': ts, 'entry_px': pos['entry_px'], 'exit_px': r['c'], 'side': pos['side'], 'gross': (r['c'] - pos['entry_px']) * CONFIG['pv'] if pos['side']=='LONG' else (pos['entry_px'] - r['c']) * CONFIG['pv'], 'reason': 'SKIP_MON'})
                pos = None
            continue
        
        # Market hours
        if r['time'] < mkt_open or r['time'] > mkt_close:
            if pos and r['time'] > mkt_close:
                gp = (r['c'] - pos['entry_px']) * CONFIG['pv'] if pos['side']=='LONG' else (pos['entry_px'] - r['c']) * CONFIG['pv']
                trades.append({**pos, 'exit_ts': ts, 'exit_px': r['c'], 'gross': gp, 'reason': 'SESSION_END'})
                pos = None
            continue
        
        # Exit
        if pos:
            hold = (ts - pos['entry_ts']).total_seconds() / 60
            if pos['side'] == 'LONG':
                if r['l'] <= pos['sl']:
                    gp = (pos['sl'] - pos['entry_px']) * CONFIG['pv']
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['sl'], 'gross': gp, 'reason': 'SL'})
                    pos = None
                elif r['h'] >= pos['tp']:
                    gp = (pos['tp'] - pos['entry_px']) * CONFIG['pv']
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['tp'], 'gross': gp, 'reason': 'TP'})
                    pos = None
                elif hold >= max_hold:
                    gp = (r['c'] - pos['entry_px']) * CONFIG['pv']
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': r['c'], 'gross': gp, 'reason': 'MAX_HOLD'})
                    pos = None
            else:
                if r['h'] >= pos['sl']:
                    gp = (pos['entry_px'] - pos['sl']) * CONFIG['pv']
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['sl'], 'gross': gp, 'reason': 'SL'})
                    pos = None
                elif r['l'] <= pos['tp']:
                    gp = (pos['entry_px'] - pos['tp']) * CONFIG['pv']
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['tp'], 'gross': gp, 'reason': 'TP'})
                    pos = None
                elif hold >= max_hold:
                    gp = (pos['entry_px'] - r['c']) * CONFIG['pv']
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': r['c'], 'gross': gp, 'reason': 'MAX_HOLD'})
                    pos = None
        
        # Entry
        if not pos:
            atr = r['atr'] if not pd.isna(r['atr']) else 0
            if atr == 0:
                continue
            
            if r['cross_up']:
                sl = r['c'] - atr_mult * atr
                tp = r['c'] + target_r * (r['c'] - sl)
                pos = {'side': 'LONG', 'entry_ts': ts, 'entry_px': r['c'], 'sl': sl, 'tp': tp}
            elif r['cross_dn']:
                sl = r['c'] + atr_mult * atr
                tp = r['c'] - target_r * (sl - r['c'])
                pos = {'side': 'SHORT', 'entry_ts': ts, 'entry_px': r['c'], 'sl': sl, 'tp': tp}
    
    if not trades:
        return None
    
    td = pd.DataFrame(trades)
    td['costs'] = td['entry_px'] * CONFIG['lot'] * COMM * 2 + CONFIG['slip'] * CONFIG['pv'] * 2
    td['net'] = td['gross'] - td['costs']
    td['hold_m'] = (td['exit_ts'] - td['entry_ts']).dt.total_seconds() / 60
    
    net = td['net'].sum()
    wr = (td['net'] > 0).mean() * 100
    w, l = td[td.net>0], td[td.net<=0]
    pf = w.net.sum() / abs(l.net.sum()) if len(l) and l.net.sum() != 0 else 0
    
    return {'net': net, 'wr': wr, 'pf': pf, 'trades': len(td), 'avg_hold': td.hold_m.mean(), 'params': (fast, slow, atr_mult, target_r, max_hold, skip_mon)}


# Walk-forward: train on first 60 days, test on next 30, roll forward
end = datetime.now()
start = end - timedelta(days=180)

print(f"Fetching {SYMBOL} data...")
fid = get_fut_id(SYMBOL, start)
if not fid:
    print("No contract")
    exit()

df = fetch_data(fid, CONFIG["futures_segment"], CONFIG["instrument_type"], start, end)
print(f"Bars: {len(df)}")

# Add indicators once
df['date'] = df['ts'].dt.date
df['time'] = df['ts'].dt.time

# Param grid
fast_vals = [5, 8, 9, 12, 15]
slow_vals = [13, 21, 22, 26, 34]
atr_mult_vals = [1.0, 1.5, 2.0, 2.5]
target_r_vals = [1.5, 2.0, 2.5, 3.0]
max_hold_vals = [60, 120, 180, 240]
skip_mon_vals = [True, False]

# Split into 3 periods: train 60d, test 30d, roll
periods = []
curr = start
while curr < end:
    train_end = min(curr + timedelta(days=60), end)
    test_end = min(train_end + timedelta(days=30), end)
    if train_end >= test_end:
        break
    periods.append((curr, train_end, test_end))
    curr = train_end

print(f"Walk-forward periods: {len(periods)}")

all_results = []

for p_idx, (train_s, train_e, test_e) in enumerate(periods):
    print(f"\nPeriod {p_idx+1}: Train {train_s.date()} to {train_e.date()}, Test {train_e.date()} to {test_e.date()}")
    
    train_df = df[(df['ts'] >= train_s) & (df['ts'] < train_e)].copy()
    test_df = df[(df['ts'] >= train_e) & (df['ts'] < test_e)].copy()
    
    if len(train_df) < 1000 or len(test_df) < 500:
        continue
    
    best = None
    best_score = -1e9
    
    # Grid search on train
    for fast, slow, atr_m, tr, mh, sm in product(fast_vals, slow_vals, atr_mult_vals, target_r_vals, max_hold_vals, skip_mon_vals):
        if fast >= slow:
            continue
        res = test_params(train_df, fast, slow, atr_m, tr, mh, sm)
        if res:
            # Score: net P&L with penalty for low trade count
            score = res['net'] * (1 + min(res['trades'] / 100, 1))
            if score > best_score:
                best_score = score
                best = res
    
    if best:
        print(f"  Best train: fast={best['params'][0]}, slow={best['params'][1]}, atr={best['params'][2]}, target={best['params'][3]}, hold={best['params'][4]}, skipMon={best['params'][5]}")
        print(f"  Train: Net={best['net']:.0f}, WR={best['wr']:.1f}%, PF={best['pf']:.2f}, Trades={best['trades']}")
        
        # Test on out-of-sample
        oos = test_params(test_df, *best['params'])
        if oos:
            print(f"  OOS Test: Net={oos['net']:.0f}, WR={oos['wr']:.1f}%, PF={oos['pf']:.2f}, Trades={oos['trades']}")
            all_results.append({'period': p_idx, 'train': best, 'test': oos})

# Summary
if all_results:
    print(f"\n{'='*60}")
    print("WALK-FORWARD SUMMARY")
    print(f"{'='*60}")
    total_net = sum(r['test']['net'] for r in all_results)
    total_trades = sum(r['test']['trades'] for r in all_results)
    avg_wr = np.mean([r['test']['wr'] for r in all_results])
    avg_pf = np.mean([r['test']['pf'] for r in all_results])
    print(f"Periods: {len(all_results)}")
    print(f"Total OOS Net: {total_net:,.0f}")
    print(f"Total OOS Trades: {total_trades}")
    print(f"Avg OOS WR: {avg_wr:.1f}%")
    print(f"Avg OOS PF: {avg_pf:.2f}")
    
    for r in all_results:
        t = r['test']
        print(f"  P{r['period']+1}: Net={t['net']:.0f}, WR={t['wr']:.1f}%, PF={t['pf']:.2f}, Trades={t['trades']}, Params={t['params']}")