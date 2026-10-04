"""Final parameter sweep for v5.0 with volatility regime filter."""
import sys
import pandas as pd
import numpy as np
from itertools import product

sys.path.insert(0, '.')
from run_exact_backtests import compute_stats, CACHE_DIR
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()

ADX_THRESH = [20, 25, 30, 35]
RR_VALUES = [2.5, 3.0, 3.5, 4.0]
VOL_SMA = [20, 30, 50, 80]

INST_CONFIG = {
    "CRUDEOIL": {"entry_mode": "flip", "sha_min_hold": 3, "pb": 1.0, "min_sl": 1.5, "max_sl": 3.0,
                 "day_loss": 300, "session": ["09:15", "23:30"], "force_flat": ["22:45", "23:30"]},
    "BANKNIFTY": {"entry_mode": "flip", "sha_min_hold": 3, "pb": 1.0, "min_sl": 1.5, "max_sl": 3.0,
                  "day_loss": 500, "session": ["09:30", "15:00"], "force_flat": ["14:30", "15:00"]},
    "SILVER": {"entry_mode": "flip", "sha_min_hold": 3, "pb": 0.5, "min_sl": 1.5, "max_sl": 5.0,
               "day_loss": 350, "session": ["09:15", "23:30"], "force_flat": ["22:45", "23:30"]},
}


def make_params(underlying, adx, rr, vol_sma):
    base = cfg["strategy"][underlying]
    inst = INST_CONFIG[underlying]
    p = dict(base)
    p["sha_len1"] = 10
    p["sha_len2"] = 10
    p["sw_len"] = 10
    p["sw_buf"] = 0.1
    p["min_sl"] = inst["min_sl"]
    p["max_sl"] = inst["max_sl"]
    p["rr"] = rr
    p["adx_min"] = adx
    p["pb_atr_mult"] = inst["pb"]
    p["sha_min_hold"] = inst["sha_min_hold"]
    p["day_loss_limit"] = inst["day_loss"]
    p["session"] = inst["session"]
    p["force_flat_window"] = inst["force_flat"]
    p["entry_mode"] = inst["entry_mode"]
    p["breakout_lookback"] = 5
    p["use_quality_filters"] = False
    p["use_vol_filter"] = True
    p["vol_sma_len"] = vol_sma
    p["atr_min_pts"] = base.get("atr_min_pts", 0)
    return p


def run_sweep(underlying):
    cache_file = CACHE_DIR / f"{underlying}_5min.csv"
    if not cache_file.exists():
        from run_exact_backtests import fetch_or_load
        fetch_or_load(underlying, interval=5, days=900)
    df = pd.read_csv(cache_file, parse_dates=["time"])
    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])

    results = []
    combos = list(product(ADX_THRESH, RR_VALUES, VOL_SMA))
    print(f"\n  {underlying}: testing {len(combos)} combos with vol_regime filter...")

    for idx, (adx, rr, vol_sma) in enumerate(combos):
        p = make_params(underlying, float(adx), rr, vol_sma)
        try:
            frame = v50.v50_frame(bars, p)
            trades, _, _ = v50.simulate(frame, p, start=v50.WARMUP_BARS)
        except Exception as e:
            continue
        if not trades:
            continue
        s = compute_stats(trades)
        results.append(dict(adx=adx, rr=rr, vol_sma=vol_sma, **s))

    results.sort(key=lambda x: x["pf"], reverse=True)
    print(f"\n  Top 5 for {underlying} (min 10 trades):")
    print(f"  {'ADX':>4} {'RR':>4} {'VolS':>4} {'Trades':>7} {'Win%':>6} {'PF':>6} {'Net':>10} {'MaxDD':>8}")
    for r in results:
        if r["trades"] >= 10:
            print(f"  {r['adx']:>4} {r['rr']:>4} {r['vol_sma']:>4} {r['trades']:>7} {r['winrate']:>6} {r['pf']:>6} {r['net']:>10.1f} {r['max_dd']:>8.1f}")

    print(f"\n  Top 3 by net (all trade counts):")
    by_net = sorted(results, key=lambda x: x["net"], reverse=True)
    for r in by_net[:3]:
        print(f"  ADX={r['adx']} RR={r['rr']} VolS={r['vol_sma']}: {r['trades']} trades, PF={r['pf']}, net={r['net']:.1f}")


if __name__ == "__main__":
    print("=" * 70)
    print("  v5.0 FINAL PARAMETER SWEEP (with vol_regime_filter)")
    print("=" * 70)

    for underlying in ["CRUDEOIL", "BANKNIFTY", "SILVER"]:
        run_sweep(underlying)
