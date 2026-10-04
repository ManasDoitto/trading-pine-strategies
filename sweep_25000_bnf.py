"""
BankNifty Strategy Optimization - 25,000 parameter sweep with VECTORIZED simulation (v5.0 SHA-ADX Hybrid).
Data: journal_data/cache/backtest/BANKNIFTY_5min.csv
"""
import itertools
import pandas as pd
import numpy as np
import tomllib
import json
import time
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from trading_agents.core.signals_v50 import V50_INSTRUMENT_PARAMS, v50_frame, WARMUP_BARS

with open('trading_agents/config.toml', 'rb') as f:
    cfg = tomllib.load(f)

BARS_CSV = 'journal_data/cache/backtest/BANKNIFTY_5min.csv'
OUT_JSON = 'sweep_25000_bnf_results.json'
SWEEP_CAP = 25000

bars = pd.read_csv(BARS_CSV, parse_dates=['time'])
n_months = (bars['time'].iloc[-1] - bars['time'].iloc[0]).days / 30.4
MIN_TRADES = int(12 * n_months)
print(f"BankNifty data: {len(bars)} bars, {bars['time'].iloc[0]} -> {bars['time'].iloc[-1]}", flush=True)
print(f"  ~{n_months:.1f} months, MIN_TRADES={MIN_TRADES}, close range {bars['close'].min():.1f}-{bars['close'].max():.1f}", flush=True)

base = dict(V50_INSTRUMENT_PARAMS['BANKNIFTY'])
base['atr_min_pts'] = float(cfg['strategy']['BANKNIFTY'].get('atr_min_pts', 50.0))


def fast_sim_vec(df_arr, params):
    """Fast trade simulation over numpy arrays (mirrors v5.0 bar-by-bar logic)."""
    n = len(df_arr['close'])
    start = WARMUP_BARS
    rr = params['rr']
    day_loss_limit = params['day_loss_limit']

    ok_l = df_arr['ok_l']
    ok_s = df_arr['ok_s']
    risk_l = df_arr['risk_l']
    risk_s = df_arr['risk_s']
    close = df_arr['close']
    low = df_arr['low']
    high = df_arr['high']
    in_flat = df_arr['in_flat']
    dates = df_arr['dates']
    adx_ok = df_arr['adx_ok']
    near_ema9_l = df_arr['near_ema9_l']
    near_ema9_s = df_arr['near_ema9_s']
    atr_arr = df_arr['atr']
    max_sl = params['max_sl']

    pnls = []
    pos_side = None
    entry_px = 0.0
    sl_px = 0.0
    tp_px = 0.0
    day_real = 0.0
    locked = False
    current_day = dates[start]

    for i in range(start, n):
        if dates[i] != current_day:
            current_day = dates[i]
            day_real = 0.0
            locked = False

        if pos_side is not None:
            if pos_side == 'LONG':
                if low[i] <= sl_px:
                    pnl = sl_px - entry_px
                    pnls.append(pnl)
                    day_real += pnl
                    pos_side = None
                    if day_loss_limit > 0 and day_real <= -day_loss_limit:
                        locked = True
                elif high[i] >= tp_px:
                    pnl = tp_px - entry_px
                    pnls.append(pnl)
                    day_real += pnl
                    pos_side = None
                    if day_loss_limit > 0 and day_real <= -day_loss_limit:
                        locked = True
                elif in_flat[i]:
                    pnl = close[i] - entry_px
                    pnls.append(pnl)
                    day_real += pnl
                    pos_side = None
            else:
                if high[i] >= sl_px:
                    pnl = entry_px - sl_px
                    pnls.append(pnl)
                    day_real += pnl
                    pos_side = None
                    if day_loss_limit > 0 and day_real <= -day_loss_limit:
                        locked = True
                elif low[i] <= tp_px:
                    pnl = entry_px - tp_px
                    pnls.append(pnl)
                    day_real += pnl
                    pos_side = None
                    if day_loss_limit > 0 and day_real <= -day_loss_limit:
                        locked = True
                elif in_flat[i]:
                    pnl = entry_px - close[i]
                    pnls.append(pnl)
                    day_real += pnl
                    pos_side = None

        if pos_side is None and not locked:
            if ok_l[i] and adx_ok[i] and near_ema9_l[i]:
                r = risk_l[i]
                if r > 0 and r <= max_sl * atr_arr[i]:
                    sl = close[i] - r
                    tp = close[i] + rr * r
                    pos_side = 'LONG'
                    entry_px = close[i]
                    sl_px = sl
                    tp_px = tp
            elif ok_s[i] and adx_ok[i] and near_ema9_s[i]:
                r = risk_s[i]
                if r > 0 and r <= max_sl * atr_arr[i]:
                    sl = close[i] + r
                    tp = close[i] - rr * r
                    pos_side = 'SHORT'
                    entry_px = close[i]
                    sl_px = sl
                    tp_px = tp

    return pnls


def compute_stats(pnls):
    if not pnls:
        return dict(trades=0, pf=0, net=0, wr=0, lw=0, dd=0, avg_w=0, avg_l=0)
    pnls = np.array(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    gw = wins.sum() if len(wins) > 0 else 0
    gl = abs(losses.sum()) if len(losses) > 0 else 1e-9
    pf = gw / gl
    net = pnls.sum()
    wr = len(wins) / len(pnls) * 100
    avg_w = gw / len(wins) if len(wins) > 0 else 0
    avg_l = gl / len(losses) if len(losses) > 0 else 0
    lw = avg_l / avg_w if avg_w > 0 else 999
    equity = np.cumsum(pnls)
    dd = np.max(np.maximum.accumulate(equity) - equity) if len(equity) > 0 else 0
    return dict(trades=len(pnls), pf=round(pf, 4), net=round(net, 1),
                wr=round(wr, 1), avg_w=round(avg_w, 1), avg_l=round(avg_l, 1),
                dd=round(dd, 1), lw=round(lw, 2))

# === PRECOMPUTE BASE FRAME ===
print("Precomputing base frame...", flush=True)
t0 = time.time()
df_base = v50_frame(bars, base)
print(f"Base frame computed in {time.time()-t0:.2f}s", flush=True)

n = len(df_base)
close_arr = df_base['close'].values
atr_arr = df_base['atr'].values
e9_arr = df_base['e9'].values
sw_lo_arr = df_base['sw_lo'].values
sw_hi_arr = df_base['sw_hi'].values
adx_prev_arr = df_base['adx15_prev'].values
sha_prev_group_arr = df_base['sha_prev_group_size'].values
flip_up_arr = df_base['flip_up'].values
flip_dn_arr = df_base['flip_dn'].values
trend_l_arr = df_base['trend_l'].values
trend_s_arr = df_base['trend_s'].values
in_sess_arr = df_base['in_sess'].values
in_flat_arr = df_base['in_flat_window'].values
dates_arr = df_base['time'].dt.date.values

df_arr_base = {
    'close': close_arr, 'low': df_base['low'].values, 'high': df_base['high'].values,
    'in_flat': in_flat_arr, 'dates': dates_arr, 'atr': atr_arr,
    'ok_l': None, 'ok_s': None, 'risk_l': None, 'risk_s': None,
    'adx_ok': None, 'near_ema9_l': None, 'near_ema9_s': None
}

bo_lookbacks = [3, 5, 8, 10, 15]
donchian_cache = {}
for lb in bo_lookbacks:
    dc_hi = df_base['high'].rolling(lb).max().shift(1).values
    dc_lo = df_base['low'].rolling(lb).min().shift(1).values
    donchian_cache[lb] = (close_arr > dc_hi, close_arr < dc_lo)
print(f"Donchian precomputed for {len(bo_lookbacks)} lookbacks", flush=True)


def build_arrays(adx_min, rr, pb_mult, sw_buf, sha_hold, atr_min, min_sl, bo_lb):
    sha_stable = sha_prev_group_arr >= sha_hold
    if atr_min == 0:
        atr_ok = np.ones(n, dtype=bool)
    else:
        atr_ok = atr_arr >= atr_min

    pb_thresh = pb_mult * atr_arr
    near_ema9_l = close_arr <= (e9_arr + pb_thresh)
    near_ema9_s = close_arr >= (e9_arr - pb_thresh)

    risk_l = np.maximum(close_arr - (sw_lo_arr - sw_buf * atr_arr), min_sl * atr_arr)
    risk_s = np.maximum((sw_hi_arr + sw_buf * atr_arr) - close_arr, min_sl * atr_arr)
    cap = base['max_sl'] * atr_arr

    adx_ok = adx_prev_arr >= adx_min

    ok_flip_l = (in_sess_arr & flip_up_arr & trend_l_arr & sha_stable & atr_ok
                 & (risk_l <= cap) & ~in_flat_arr)
    ok_flip_s = (in_sess_arr & flip_dn_arr & trend_s_arr & sha_stable & atr_ok
                 & (risk_s <= cap) & ~ok_flip_l & ~in_flat_arr)

    bo_l, bo_s = donchian_cache.get(bo_lb, donchian_cache[5])
    ok_bo_l = (in_sess_arr & bo_l & trend_l_arr & atr_ok & (risk_l <= cap) & ~in_flat_arr)
    ok_bo_s = (in_sess_arr & bo_s & trend_s_arr & atr_ok & (risk_s <= cap) & ~ok_bo_l & ~in_flat_arr)

    return (ok_flip_l | ok_bo_l, ok_flip_s | ok_bo_s, risk_l, risk_s,
            adx_ok, near_ema9_l, near_ema9_s)


# === BASELINE (v5.0 defaults) ===
_bl = build_arrays(base['adx_min'], base['rr'], base['pb_atr_mult'], base['sw_buf'],
                   base['sha_min_hold'], base['atr_min_pts'], base['min_sl'],
                   base['breakout_lookback'])
_bl_arr = dict(df_arr_base)
_bl_arr.update(dict(zip(['ok_l', 'ok_s', 'risk_l', 'risk_s', 'adx_ok',
                         'near_ema9_l', 'near_ema9_s'], _bl)))
baseline = compute_stats(fast_sim_vec(_bl_arr, base))
print(f"BASELINE v5.0 defaults: {baseline}", flush=True)

# === GENERATE PARAMETER COMBINATIONS ===
GRID = dict(
    adx_min=[5, 8, 10, 12, 15, 18, 20, 22, 25, 28, 30],
    rr=[2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0],
    pb_mult=[0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0],
    sw_buf=[0.05, 0.1, 0.15, 0.2, 0.3, 0.5],
    sha_hold=[1, 2, 3],
    atr_min=[0.0, 50.0, 100.0],
    min_sl=[1.0, 1.5, 2.0, 3.0],
    bo_lb=[3, 5, 8, 10, 15],
)
KEYS = list(GRID.keys())
full = list(itertools.product(*(GRID[k] for k in KEYS)))
print(f"Total possible combinations: {len(full)}", flush=True)

if len(full) > SWEEP_CAP:
    stride = len(full) / SWEEP_CAP
    param_combos = [full[int(i * stride)] for i in range(SWEEP_CAP)]
else:
    param_combos = full
print(f"Sweep combinations: {len(param_combos)} (evenly strided over full space)", flush=True)

# === RUN SWEEP ===
results = []
t0 = time.time()
sim_calls = 0

for idx, combo in enumerate(param_combos):
    adx_min, rr, pb_mult, sw_buf, sha_hold, atr_min, min_sl, bo_lb = combo

    ok_l, ok_s, risk_l, risk_s, adx_ok, near_ema9_l, near_ema9_s = build_arrays(
        adx_min, rr, pb_mult, sw_buf, sha_hold, atr_min, min_sl, bo_lb)

    signal_count = int(np.sum(ok_l[WARMUP_BARS:]) + np.sum(ok_s[WARMUP_BARS:]))
    if signal_count < 40:
        continue

    df_arr = dict(df_arr_base)
    df_arr['ok_l'] = ok_l
    df_arr['ok_s'] = ok_s
    df_arr['risk_l'] = risk_l
    df_arr['risk_s'] = risk_s
    df_arr['adx_ok'] = adx_ok
    df_arr['near_ema9_l'] = near_ema9_l
    df_arr['near_ema9_s'] = near_ema9_s

    p = dict(base)
    p['adx_min'] = adx_min
    p['rr'] = rr
    p['pb_atr_mult'] = pb_mult
    p['sw_buf'] = sw_buf
    p['sha_min_hold'] = sha_hold
    p['min_sl'] = min_sl
    p['max_sl'] = base['max_sl']
    p['day_loss_limit'] = base['day_loss_limit']
    p['entry_mode'] = 'flip'

    pnls = fast_sim_vec(df_arr, p)
    s = compute_stats(pnls)
    sim_calls += 1

    if s['trades'] >= MIN_TRADES and s['pf'] > 1.0:
        results.append({
            'mode': 'combined', 'adx': adx_min, 'rr': rr, 'pb': pb_mult,
            'swb': sw_buf, 'sha': sha_hold, 'atr_min': atr_min,
            'min_sl': min_sl, 'bo_lb': bo_lb, **s
        })

    if (idx + 1) % 2500 == 0:
        el = time.time() - t0
        rate = (idx + 1) / el
        eta = (len(param_combos) - idx - 1) / rate if rate > 0 else 0
        print(f"  {idx+1}/{len(param_combos)} ({el:.0f}s, {rate:.1f}/s, ETA {eta:.0f}s) | "
              f"sim_calls={sim_calls}, candidates={len(results)}", flush=True)

elapsed = time.time() - t0
print(f"\nSweep complete: {len(param_combos)} iterations in {elapsed:.1f}s", flush=True)
print(f"Simulation calls: {sim_calls}", flush=True)
print(f"Candidates (trades>={MIN_TRADES}, PF>1.0): {len(results)}", flush=True)

results.sort(key=lambda x: (x['pf'], x['net']), reverse=True)

print("\n" + "=" * 124)
print(f"TOP 25 BY PF (min {MIN_TRADES} trades = ~12/month)")
print("=" * 124)
hdr = (f'{"Mode":<9} {"ADX":>4} {"RR":>4} {"PB":>4} {"SWB":>5} {"SHA":>3} {"ATR":>5} {"MinSl":>5} {"BO":>3}'
       f' {"Trd":>5} {"T/mo":>5} {"PF":>7} {"WR%":>6} {"Net":>10} {"AvgW":>8} {"AvgL":>8} {"L/W":>5} {"DD":>9}')
print(hdr)
print("-" * 124)
for r in results[:25]:
    print(f'{r["mode"]:<9} {r["adx"]:4d} {r["rr"]:4.1f} {r["pb"]:4.1f} {r["swb"]:5.2f} {r["sha"]:3d} '
          f'{r["atr_min"]:5.0f} {r["min_sl"]:5.1f} {r["bo_lb"]:3d} {r["trades"]:5d} {r["trades"]/n_months:5.1f} '
          f'{r["pf"]:7.3f} {r["wr"]:5.1f} {r["net"]:+10.0f} {r["avg_w"]:8.1f} {r["avg_l"]:8.1f} '
          f'{r["lw"]:5.2f} {r["dd"]:+9.0f}')

print("\n" + "=" * 124)
print("CANDIDATES 26-50:")
for r in results[25:50]:
    print(f'  ADX>={r["adx"]} RR={r["rr"]} PB={r["pb"]} SWB={r["swb"]} SHA={r["sha"]} ATR={r["atr_min"]} '
          f'MinSL={r["min_sl"]} BO={r["bo_lb"]} -> {r["trades"]}T PF={r["pf"]:.3f} net={r["net"]:+.0f} L/W={r["lw"]}')

with open(OUT_JSON, 'w') as f:
    json.dump(dict(
        data=dict(bars=len(bars), start=str(bars['time'].iloc[0]), end=str(bars['time'].iloc[-1]),
                  months=round(n_months, 1), min_trades=MIN_TRADES),
        baseline=baseline,
        iterations=len(param_combos), sim_calls=sim_calls,
        elapsed_s=round(elapsed, 1), candidates=len(results),
        top=results[:100]), f, indent=2)
print(f"\nSaved top 100 configs to {OUT_JSON}", flush=True)

if results:
    r = results[0]
    tpm = r["trades"] / n_months
    print("\n=== WINNER ===", flush=True)
    print(f'Combined mode, ADX>={r["adx"]}, RR={r["rr"]}, PB={r["pb"]}, SWB={r["swb"]}, '
          f'SHA={r["sha"]}, ATR_min={r["atr_min"]}, MinSL={r["min_sl"]}, BO_lb={r["bo_lb"]}', flush=True)
    print(f'Results: {r["trades"]} trades ({tpm:.1f}/month), PF {r["pf"]}, WR {r["wr"]}%, '
          f'Net {r["net"]:+.0f} pts, L/W {r["lw"]}, DD {r["dd"]:+.0f}', flush=True)
    print(f'Baseline: {baseline["trades"]} trades, PF {baseline["pf"]}, net {baseline["net"]:+.0f}', flush=True)

print("\n=== SWEEP COMPLETE ===", flush=True)
