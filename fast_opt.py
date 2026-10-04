"""
Fast walk-forward optimization - CrudeOil EMA crossover
Focus: find ANY profitable parameter set on Dhan data
"""
import os, time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
from dhanhq import dhanhq, DhanContext
dhan = dhanhq(DhanContext(os.getenv('DHAN_CLIENT_ID'), os.getenv('DHAN_ACCESS_TOKEN')))

# Fetch CrudeOil data - split into train/test
print("Fetching CrudeOil 1m data (last 120 days)...")
start = datetime.now() - timedelta(days=120)
end = datetime.now()

all_d = []
ce = end
while ce > start:
    cs = max(start, ce - timedelta(days=90))
    f, t = cs.strftime("%Y-%m-%d"), ce.strftime("%Y-%m-%d")
    r = dhan.intraday_minute_data(security_id='569900', exchange_segment='MCX_COMM', instrument_type='FUTCOM', from_date=f, to_date=t)
    if r.get("status") == "success" and r.get("data", {}).get("timestamp"):
        d = r['data']
        all_d.append(pd.DataFrame({"ts": d["timestamp"], "c": d["close"], "h": d["high"], "l": d["low"], "o": d["open"], "v": d["volume"]}))
    time.sleep(0.3)
    ce = cs - timedelta(days=1)

df = pd.concat(all_d).reset_index(drop=True)
df['ts'] = pd.to_datetime(df['ts'], unit='s') + pd.Timedelta(hours=5, minutes=30)
df = df.sort_values('ts').reset_index(drop=True)
print(f"Total bars: {len(df)}")

# Walk-forward: 2 train periods (30 days each), 2 test periods (30 days each)
split_dates = [datetime.now() - timedelta(days=60), datetime.now() - timedelta(days=30)]
train_periods = [(df['ts'].min(), split_dates[0]), (split_dates[0], split_dates[1])]
test_periods = [(split_dates[0], split_dates[1]), (split_dates[1], df['ts'].max())]

PV = 100      # point value
LOT = 100
COMM = 0.0002
SLIP = 2

def backtest(d, fast, slow, atr_mult, target_r, max_hold_min, adx_thresh):
    """Single strategy test on DataFrame d"""
    d = d.copy()
    d['ema_f'] = d['c'].ewm(span=fast, adjust=False).mean()
    d['ema_s'] = d['c'].ewm(span=slow, adjust=False).mean()
    
    hl = d['h'] - d['l']
    hc = (d['h'] - d['c'].shift()).abs()
    lc = (d['l'] - d['c'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    d['atr'] = tr.ewm(span=14, adjust=False).mean()
    
    # ADX
    pdm = d['h'].diff()
    mdm = d['l'].shift().diff() * -1
    pdm[pdm < 0] = 0; mdm[mdm < 0] = 0
    tr_s = tr.ewm(span=14, adjust=False).mean()
    pdi = 100 * pdm.ewm(span=14, adjust=False).mean() / tr_s
    mdi = 100 * mdm.ewm(span=14, adjust=False).mean() / tr_s
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    d['adx'] = dx.ewm(span=14, adjust=False).mean()
    
    # Date/session
    d['date'] = d['ts'].dt.date
    d['time'] = d['ts'].dt.time
    
    # Cross signals
    d['long'] = (d['ema_f'] > d['ema_s']) & (d['ema_f'].shift(1) <= d['ema_s'].shift(1))
    d['short'] = (d['ema_f'] < d['ema_s']) & (d['ema_f'].shift(1) >= d['ema_s'].shift(1))
    
    # Market hours: 09:15-15:00, close by 15:15
    mkt_open = pd.Timestamp("09:15").time()
    mkt_close = pd.Timestamp("15:15").time()
    
    trades = []
    pos = None
    curr_day = None
    
    for i in range(len(d)):
        r = d.iloc[i]
        ts = r['ts']
        day = ts.date()
        
        # Skip Monday
        if ts.weekday() == 0:
            if pos:
                gp = (r['c'] - pos['entry']) * PV if pos['side']=='LONG' else (pos['entry'] - r['c']) * PV
                trades.append({**pos, 'exit_ts': ts, 'exit_px': r['c'], 'gross': gp, 'reason': 'MON_SKIP'})
                pos = None
            continue
        
        t = r['time']
        if t < mkt_open or t > mkt_close:
            if pos and t > mkt_close:
                gp = (r['c'] - pos['entry']) * PV if pos['side']=='LONG' else (pos['entry'] - r['c']) * PV
                trades.append({**pos, 'exit_ts': ts, 'exit_px': r['c'], 'gross': gp, 'reason': 'SESSION_END'})
                pos = None
            continue
        
        # Exit
        if pos:
            hold = (ts - pos['entry_ts']).total_seconds() / 60
            atr = pos['atr']
            if pos['side'] == 'LONG':
                if r['l'] <= pos['sl']:
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['sl'], 'gross': (pos['sl']-pos['entry'])*PV, 'reason': 'SL'})
                    pos = None
                elif r['h'] >= pos['tp']:
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['tp'], 'gross': (pos['tp']-pos['entry'])*PV, 'reason': 'TP'})
                    pos = None
                elif hold >= max_hold_min:
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': r['c'], 'gross': (r['c']-pos['entry'])*PV, 'reason': 'MAX_HOLD'})
                    pos = None
            else:
                if r['h'] >= pos['sl']:
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['sl'], 'gross': (pos['entry']-pos['sl'])*PV, 'reason': 'SL'})
                    pos = None
                elif r['l'] <= pos['tp']:
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': pos['tp'], 'gross': (pos['entry']-pos['tp'])*PV, 'reason': 'TP'})
                    pos = None
                elif hold >= max_hold_min:
                    trades.append({**pos, 'exit_ts': ts, 'exit_px': r['c'], 'gross': (pos['entry']-r['c'])*PV, 'reason': 'MAX_HOLD'})
                    pos = None
        
        # Entry (only if ADX >= threshold)
        if not pos:
            atr = r['atr']
            if pd.isna(atr) or atr == 0:
                continue
            if r['adx'] < adx_thresh if not pd.isna(r['adx']) else 0 < adx_thresh:
                continue
            if r['time'] <= pd.Timestamp("09:45").time():  # Wait 30 min after open
                continue
            
            if r['long']:
                sl = r['c'] - atr_mult * atr
                tp = r['c'] + target_r * (r['c'] - sl)
                pos = {'side': 'LONG', 'entry': r['c'], 'entry_ts': ts, 'sl': sl, 'tp': tp, 'atr': atr}
            elif r['short']:
                sl = r['c'] + atr_mult * atr
                tp = r['c'] - target_r * (sl - r['c'])
                pos = {'side': 'SHORT', 'entry': r['c'], 'entry_ts': ts, 'sl': sl, 'tp': tp, 'atr': atr}
    
    if not trades:
        return None
    td = pd.DataFrame(trades)
    td['costs'] = td['entry'] * LOT * COMM * 2 + SLIP * PV * 2
    td['net'] = td['gross'] - td['costs']
    td['hold_m'] = (td['exit_ts'] - td['entry_ts']).dt.total_seconds() / 60
    
    return {'net': td['net'].sum(), 'wr': (td.net>0).mean()*100, 'pf': (td[td.net>0].net.sum()/abs(td[td.net<=0].net.sum())) if len(td[td.net<=0]) else 0,
            'trades': len(td), 'avg_hold': td.hold_m.mean(), 'params': (fast, slow, atr_mult, target_r, max_hold_min, adx_thresh)}

# Limited grid search
param_grid = []
for fast, slow in [(5,21), (8,21), (9,22), (9,34), (12,26), (15,34)]:
    for atr_mult in [1.5, 2.0]:
        for target_r in [1.5, 2.0, 3.0]:
            for max_hold in [60, 120]:
                for adx in [0, 20, 30]:
                    param_grid.append((fast, slow, atr_mult, target_r, max_hold, adx))

print(f"\nTesting {len(param_grid)} parameter combos on {len(train_periods)} train + {len(test_periods)} test periods")
print(f"Total runs: {len(param_grid) * (len(train_periods) + len(test_periods))}")

best_overall = None
best_score = -1e9
results_log = []

for p_idx, (tr_s, tr_e) in enumerate(train_periods):
    print(f"\n--- TRAIN Period {p_idx+1}: {tr_s.date()} to {tr_e.date()} ---")
    train_df = df[(df['ts'] >= tr_s) & (df['ts'] < tr_e)]
    
    best_train = None
    best_train_score = -1e9
    
    for params in param_grid:
        res = backtest(train_df, *params)
        if res and res['trades'] > 5:
            # Score: Sharpe-like (net / sqrt(trades))
            score = res['net'] / (res['trades']**0.5) if res['trades'] > 0 else -1e9
            if score > best_train_score:
                best_train_score = score
                best_train = res
    
    if best_train:
        p = best_train['params']
        print(f"  Best: {best_train['params']}, Net={best_train['net']:.0f}, WR={best_train['wr']:.1f}%, PF={best_train['pf']:.2f}, Trades={best_train['trades']}")
        
        # Test OOS
        test_df = df[(df['ts'] >= tr_e) & (df['ts'] < min(tr_e + timedelta(days=30), df['ts'].max()))]
        oos = backtest(test_df, *p)
        if oos:
            print(f"  OOS: Net={oos['net']:.0f}, WR={oos['wr']:.1f}%, PF={oos['pf']:.2f}, Trades={oos['trades']}")
            results_log.append({'train_p': p_idx, 'train_res': best_train, 'oos_res': oos})
            if oos['net'] > best_score:
                best_score = oos['net']
                best_overall = {'train': best_train, 'oos': oos, 'period': p_idx}

print(f"\n{'='*60}")
print("FINAL RESULTS")
print(f"{'='*60}")
if best_overall:
    print(f"Best OOS config:")
    p = best_overall['train']['params']
    print(f"  EMA({p[0]}/{p[1]}), ATR_SL={p[2]}, R:R={p[3]}, Hold={p[4]}min, ADX>={p[5]}")
    print(f"  Train Net: {best_overall['train']['net']:.0f}, WR={best_overall['train']['wr']:.1f}%, PF={best_overall['train']['pf']:.2f}")
    print(f"  OOS Net: {best_overall['oos']['net']:.0f}, WR={best_overall['oos']['wr']:.1f}%, PF={best_overall['oos']['pf']:.2f}")

total_oos_net = sum(r['oos_res']['net'] for r in results_log)
total_oos_trades = sum(r['oos_res']['trades'] for r in results_log)
print(f"\nTotal OOS across all periods: Net={total_oos_net:.0f}, Trades={total_oos_trades}")
for r in results_log:
    p = r['train_res']['params']
    print(f"  P{r['train_p']+1}: Train={r['train_res']['net']:.0f}, OOS={r['oos_res']['net']:.0f}, OOS_WR={r['oos_res']['wr']:.1f}%, OOS_PF={r['oos_res']['pf']:.2f}, Params={p}")