"""Exhaustive v5.0 parameter sweep — searching for configs that beat baseline.
Focus: PF > 1.5, more trades, L/W < 0.40, higher net profit."""
import pandas as pd
import numpy as np
import tomllib
from trading_agents.core.signals_v50 import V50_INSTRUMENT_PARAMS, v50_frame, simulate, WARMUP_BARS

with open('trading_agents/config.toml', 'rb') as f:
    cfg = tomllib.load(f)


def compute_stats(trades):
    if not trades:
        return dict(trades=0, pf=0, net=0, wr=0, lw=0, dd=0, avg_w=0, avg_l=0)
    pnls = [t['pnl_pts'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gw = sum(wins) if wins else 0
    gl = abs(sum(losses)) if losses else 0.001
    pf = gw / gl
    net = sum(pnls)
    wr = len(wins) / len(trades) * 100
    avg_w = gw / len(wins) if wins else 0
    avg_l = gl / len(losses) if losses else 0
    lw = avg_l / avg_w if avg_w > 0 else 0
    equity = np.cumsum(pnls)
    running_max = np.maximum.accumulate(equity)
    dd = np.max(running_max - equity) if len(equity) > 0 else 0
    return dict(trades=len(trades), pf=round(pf, 3), net=round(net, 1),
                wr=round(wr, 1), avg_w=round(avg_w, 1), avg_l=round(avg_l, 1),
                dd=round(dd, 1), lw=round(lw, 2))


# Test on both instruments with data
instruments = {
    'SILVER': {
        'file': 'journal_data/cache/backtest/SILVER_5min.csv',
        'base': dict(V50_INSTRUMENT_PARAMS['SILVER']),
        'baseline_trade_count': 10,  # v5.0 default
        'baseline_pf': 2.04,
    },
    'BANKNIFTY': {
        'file': 'journal_data/cache/backtest/BANKNIFTY_5min.csv',
        'base': dict(V50_INSTRUMENT_PARAMS['BANKNIFTY']),
        'baseline_trade_count': 49,
        'baseline_pf': 1.494,
    },
}

# Parameter sweep
adx_values = [15, 18, 20, 25, 30]
sha_values = [1, 2, 3]
rr_values = [2.5, 3.0, 3.5, 4.0, 4.5]
pb_values = [0.5, 1.0, 1.5]
swbuf_values = [0.1, 0.2]
bo_values = [False, True]  # flip-only vs flip+breakout
bo_lookbacks = [3, 5, 8]

for instr_name, info in instruments.items():
    bars = pd.read_csv(info['file'], parse_dates=['time'])
    base = info['base']
    base['atr_min_pts'] = cfg['strategy'][instr_name].get('atr_min_pts', 0)
    
    baseline_pf = info['baseline_pf']
    baseline_trades = info['baseline_trade_count']
    
    print(f'\n{"="*80}')
    print(f'  {instr_name} — {len(bars)} bars ({bars["time"].iloc[0].date()} to {bars["time"].iloc[-1].date()})')
    print(f'  Baseline: {baseline_trades} trades, PF {baseline_pf}')
    print(f'  Sweep: {len(adx_values)*len(sha_values)*len(rr_values)*len(pb_values)*len(swbuf_values)*(len(bo_values)*len(bo_lookbacks) if any(bo_values) else 1)} configs')
    print(f'{"="*80}')
    
    best_configs = []
    
    for adx in adx_values:
        for sha in sha_values:
            for rr in rr_values:
                for pb in pb_values:
                    for swb in swbuf_values:
                        # Flip-only mode
                        p = dict(base)
                        p['adx_min'] = adx
                        p['sha_min_hold'] = sha
                        p['rr'] = rr
                        p['pb_atr_mult'] = pb
                        p['sw_buf'] = swb
                        p['entry_mode'] = 'flip'
                        
                        df = v50_frame(bars, p)
                        trades, _, _ = simulate(df, p, start=WARMUP_BARS)
                        s = compute_stats(trades)
                        
                        if s['trades'] > 0 and s['pf'] > 1.0:
                            best_configs.append({
                                'mode': 'flip',
                                'adx': adx, 'sha': sha, 'rr': rr, 'pb': pb, 'swb': swb,
                                'bo': None, 'trades': s['trades'], 'pf': s['pf'],
                                'wr': s['wr'], 'net': s['net'], 'lw': s['lw'], 'dd': s['dd'],
                                'avg_w': s['avg_w'], 'avg_l': s['avg_l']
                            })
                        
                        # Combined flip+breakout mode
                        for bo_lb in bo_lookbacks:
                            p2 = dict(p)
                            p2['breakout_lookback'] = bo_lb
                            df2 = v50_frame(bars, p2)
                            df2['ok_l'] = df2['ok_l'] | df2['ok_l_bo']
                            df2['ok_s'] = df2['ok_s'] | df2['ok_s_bo']
                            p2['entry_mode'] = 'flip'
                            
                            trades2, _, _ = simulate(df2, p2, start=WARMUP_BARS)
                            s2 = compute_stats(trades2)
                            
                            if s2['trades'] > 0 and s2['pf'] > 1.0:
                                best_configs.append({
                                    'mode': f'flip+bo{bo_lb}',
                                    'adx': adx, 'sha': sha, 'rr': rr, 'pb': pb, 'swb': swb,
                                    'bo': bo_lb, 'trades': s2['trades'], 'pf': s2['pf'],
                                    'wr': s2['wr'], 'net': s2['net'], 'lw': s2['lw'], 'dd': s2['dd'],
                                    'avg_w': s2['avg_w'], 'avg_l': s2['avg_l']
                                })
    
    # Sort by a composite score: prioritize PF, then net, then trade count (if PF > 1.3)
    # Filter for configs that beat baseline PF
    better_pf = [c for c in best_configs if c['pf'] > baseline_pf * 0.95 and c['trades'] > baseline_trades]
    
    print(f'\nFound {len(best_configs)} profitable configs, {len(better_pf)} beat/exceed baseline PF with more trades')
    print(f'\nTop 15 by PF (with more trades than baseline):\n')
    
    # Sort by PF descending, then net descending
    better_pf.sort(key=lambda x: (x['pf'], x['net']), reverse=True)
    
    print(f'{"Mode":<12} {"ADX":>3} {"SHA":>3} {"RR":>4} {"PB":>4} {"SWB":>4} {"BO":>4} {"Trd":>4} {"PF":>6} {"WR%":>5} {"Net":>8} {"L/W":>5} {"DD":>7}')
    print('-' * 85)
    for c in better_pf[:15]:
        bo_str = str(c['bo']) if c['bo'] else '-'
        print(f'{c["mode"]:<12} {c["adx"]:3d} {c["sha"]:3d} {c["rr"]:4.1f} {c["pb"]:4.1f} {c["swb"]:4.1f} {bo_str:>4s} {c["trades"]:4d} {c["pf"]:6.2f} {c["wr"]:5.1f} {c["net"]:+8.0f} {c["lw"]:5.2f} {c["dd"]:+7.0f}')
    
    # Also show top configs by net profit with L/W < 0.40
    print(f'\nTop 5 by NET profit with L/W < 0.40 and PF > 1.3:\n')
    lw_compliant = [c for c in best_configs if c['lw'] < 0.40 and c['pf'] > 1.3]
    lw_compliant.sort(key=lambda x: x['net'], reverse=True)
    print(f'{"Mode":<12} {"ADX":>3} {"SHA":>3} {"RR":>4} {"PB":>4} {"SWB":>4} {"BO":>4} {"Trd":>4} {"PF":>6} {"WR%":>5} {"Net":>8} {"L/W":>5}')
    print('-' * 75)
    for c in lw_compliant[:5]:
        bo_str = str(c['bo']) if c['bo'] else '-'
        print(f'{c["mode"]:<12} {c["adx"]:3d} {c["sha"]:3d} {c["rr"]:4.1f} {c["pb"]:4.1f} {c["swb"]:4.1f} {bo_str:>4s} {c["trades"]:4d} {c["pf"]:6.2f} {c["wr"]:5.1f} {c["net"]:+8.0f} {c["lw"]:5.2f}')
