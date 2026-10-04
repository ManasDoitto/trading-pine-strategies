"""Parameter sweep for v5.0 SHA-ADX Hybrid.

Tests different combinations of ADX gate, pullback proximity, and RR
for each instrument to find the best settings.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from itertools import product

sys.path.insert(0, str(Path(__file__).parent))
from run_exact_backtests import fetch_or_load, compute_stats, CACHE_DIR
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()

# Parameter grid to test
ADX_THRESH = [15, 20, 25, 30]
PB_MULT = [0.5, 1.0, 1.5, 2.0]
RR_VALUES = [2.5, 3.0, 3.5, 4.0]
MIN_SL = [1.5, 2.0, 2.5]

# Per-instrument overrides from config
INST_PARAMS = {
    "CRUDEOIL": {"base": cfg["strategy"]["CRUDEOIL"], "target_max_sl": 3.0},
    "BANKNIFTY": {"base": cfg["strategy"]["BANKNIFTY"], "target_max_sl": 3.0},
    "SILVER": {"base": cfg["strategy"]["SILVER"], "target_max_sl": 5.0},
}


def make_params(underlying, adx_min, pb_mult, rr, min_sl):
    base = INST_PARAMS[underlying]["base"]
    p = dict(base)
    if "session" not in p:
        p["session"] = p.get("entry_window", ["09:15", "23:30"])
    p["sha_len1"] = base.get("sha_len1", 10)
    p["sha_len2"] = base.get("sha_len2", 10)
    p["sw_len"] = base.get("sw_len", 10)
    p["sw_buf"] = base.get("sw_buf", 0.1)
    p["min_sl"] = min_sl
    p["max_sl"] = INST_PARAMS[underlying]["target_max_sl"]
    p["rr"] = rr
    p["adx_min"] = adx_min
    p["pb_atr_mult"] = pb_mult
    p["day_loss_limit"] = base.get("day_loss_limit_pts", 0) or (300 if underlying != "BANKNIFTY" else 600)
    p["name"] = f"v5.0 sweep: ADX={adx_min} PB={pb_mult} RR={rr} minSL={min_sl}"
    return p


def run_sweep(underlying):
    cache_file = CACHE_DIR / f"{underlying}_5min.csv"
    if not cache_file.exists():
        print(f"  {underlying}: fetching data...")
        fetch_or_load(underlying, interval=5, days=900)
        if not cache_file.exists():
            print(f"  {underlying}: no data, skipping")
            return None

    df = pd.read_csv(cache_file, parse_dates=["time"])
    bars = df.copy()
    bars["time"] = pd.to_datetime(bars["time"])

    results = []
    combos = list(product(ADX_THRESH, PB_MULT, RR_VALUES, MIN_SL))
    total = len(combos)
    print(f"\n  {underlying}: testing {total} parameter combinations...")

    best = None
    for idx, (adx, pb, rr, msl) in enumerate(combos):
        if idx % 20 == 0:
            print(f"    ... {idx}/{total}")
        p = make_params(underlying, adx, pb, rr, msl)
        try:
            frame = v50.v50_frame(bars, p)
            trades, _, _ = v50.simulate(frame, p, start=v50.WARMUP_BARS)
        except Exception as e:
            continue
        if not trades:
            continue
        s = compute_stats(trades)
        if s["pf"] <= 0:
            continue
        results.append(dict(adx_min=adx, pb_mult=pb, rr=rr, min_sl=msl,
                           **s))
        if best is None or s["pf"] > best["pf"]:
            best = results[-1]

    if not results:
        print(f"  {underlying}: no valid results")
        return None

    # Sort by PF
    results.sort(key=lambda x: x["pf"], reverse=True)
    print(f"\n  Top 5 parameter sets for {underlying}:")
    print(f"  {'ADX':>4} {'PB':>4} {'RR':>4} {'minSL':>5} {'Trades':>7} {'Win%':>6} {'PF':>6} {'Net':>10} {'MaxDD':>8}")
    for r in results[:5]:
        print(f"  {r['adx_min']:>4} {r['pb_mult']:>4} {r['rr']:>4} {r['min_sl']:>5} {r['trades']:>7} {r['winrate']:>6} {r['pf']:>6} {r['net']:>10.1f} {r['max_dd']:>8.1f}")

    return results[:5]


if __name__ == "__main__":
    print("=" * 70)
    print("  v5.0 PARAMETER SWEEP")
    print("=" * 70)

    for underlying in ["CRUDEOIL", "BANKNIFTY", "SILVER"]:
        run_sweep(underlying)
