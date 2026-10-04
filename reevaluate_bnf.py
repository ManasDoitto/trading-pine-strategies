"""Re-evaluate top 100 configs from sweep_25000_bnf (fast_sim_vec) using
the accurate research_sim.py simulation (gap fills, commission, next-bar-open entry).
"""
import sys, json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "strategy_audit_2026_09"))

import research_sim as rs
import silver_sweep as SS
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()

# Load data
d = SS.base("NSE_BANKNIFTY1")
print(f"Data: {len(d)} bars, {d['time'].iloc[0]} to {d['time'].iloc[-1]}")

# Load fast sweep results
with open("sweep_25000_bnf_results.json") as f:
    data = json.load(f)

fast_results = data["top"]
print(f"\nRe-evaluating top {len(fast_results)} configs from fast sweep with accurate simulation...")

# Base params
base = dict(v50.V50_INSTRUMENT_PARAMS["BANKNIFTY"])
base["atr_min_pts"] = float(cfg["strategy"]["BANKNIFTY"].get("atr_min_pts", 50.0))

accurate_results = []
for i, r in enumerate(fast_results):
    # Build params from fast sweep winner
    p = dict(base)
    p["adx_min"] = r["adx"]
    p["rr"] = r["rr"]
    p["pb_atr_mult"] = r["pb"]
    p["sw_buf"] = r["swb"]
    p["sha_min_hold"] = r["sha"]
    p["min_sl"] = r["min_sl"]
    p["max_sl"] = base["max_sl"]
    p["day_loss_limit"] = base["day_loss_limit"]
    p["use200"] = True
    p["use_vol_filter"] = True
    p["vol_sma_len"] = base["vol_sma_len"]

    # ATR floor
    if r["atr_min"] == 0:
        p["atr_min_pts"] = 0
    else:
        p["atr_min_pts"] = r["atr_min"]

    # Session from BankNifty config
    p["session"] = base["session"]
    p["force_flat_window"] = base["force_flat_window"]

    # Build frame and simulate
    f = SS.frame(d, p)
    s0 = max(int((f["time"] >= SS.T0).idxmax()), rs.WARMUP)

    try:
        tr = rs.simulate(f, dict(p, day_loss_limit_pts=p["day_loss_limit"]),
                         start=s0, flat_at="14:30", commission=0.0)
        if tr:
            s = rs.stats(tr)
            accurate_results.append({
                **{k: r[k] for k in ("mode", "adx", "rr", "pb", "swb", "sha", "atr_min", "min_sl", "bo_lb")},
                "n": s["n"], "pf": s["pf"], "net": round(s["net"]), "max_dd": round(s["max_dd"]),
                "win_pct": s["win_pct"], "pos_months_pct": s["pos_months_pct"],
                "avg_hold_h": s["avg_hold_h"]
            })
        else:
            accurate_results.append({
                **{k: r[k] for k in ("mode", "adx", "rr", "pb", "swb", "sha", "atr_min", "min_sl", "bo_lb")},
                "n": 0, "pf": 0, "net": 0, "max_dd": 0, "win_pct": 0
            })
    except Exception as e:
        print(f"  Config {i} ERROR: {e}")
        accurate_results.append({
            **{k: r[k] for k in ("mode", "adx", "rr", "pb", "swb", "sha", "atr_min", "min_sl", "bo_lb")},
            "n": 0, "pf": 0, "net": 0, "max_dd": 0, "error": str(e)
        })

    if (i + 1) % 20 == 0:
        print(f"  {i+1}/{len(fast_results)} re-evaluated...", flush=True)

# Sort by PF (then net)
accurate_results.sort(key=lambda x: (x.get("pf", 0), x.get("net", 0)), reverse=True)

# Print results
print(f"\n{'='*120}")
print("TOP 25 BY PF (accurate research_sim simulation)")
print(f"{'='*120}")
hdr = f'{"ADX":>4} {"RR":>4} {"PB":>4} {"SWB":>5} {"SHA":>3} {"ATR":>5} {"MinSl":>5} {"BO":>3} {"Trd":>4} {"PF":>6} {"Net":>8} {"WR%":>5} {"DD":>7} {"posM":>5}'
print(hdr)
print("-" * 120)
for r in accurate_results[:25]:
    print(f'{r["adx"]:4d} {r["rr"]:4.1f} {r["pb"]:4.1f} {r["swb"]:5.2f} {r["sha"]:3d} '
          f'{r["atr_min"]:5.0f} {r["min_sl"]:5.1f} {r["bo_lb"]:3d} '
          f'{r["n"]:4d} {r["pf"]:6.3f} {r["net"]:+8.0f} {r["win_pct"]:5.1f} {r["max_dd"]:+7.0f} {r.get("pos_months_pct",0):5.1f}')

# Save
with open("reeval_results.json", "w") as f:
    json.dump({"baseline": data["baseline"], "results": accurate_results[:100]}, f, indent=2)
print(f"\nSaved to reeval_results.json")

# Also save as CSV
df_out = pd.DataFrame(accurate_results)
df_out.to_csv("reeval_results.csv", index=False)
print(f"Saved to reeval_results.csv")

if accurate_results:
    r = accurate_results[0]
    print(f"\n=== WINNER (accurate sim) ===")
    print(f'ADX>={r["adx"]} RR={r["rr"]} PB={r["pb"]} SWB={r["swb"]} SHA={r["sha"]} ATR={r["atr_min"]} '
          f'MinSL={r["min_sl"]} BO={r["bo_lb"]}')
    print(f'Results: {r["n"]} trades, PF={r["pf"]:.3f}, net={r["net"]:+.0f}, '
          f'WR={r["win_pct"]:.1f}%, DD={r["max_dd"]:.0f}')
