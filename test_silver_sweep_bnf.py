"""Quick test: run silver_sweep framework on BankNifty data."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "strategy_audit_2026_09"))

import research_sim as rs
import silver_sweep as SS
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()

# Load BankNifty data via silver_sweep.base
d = SS.base("NSE_BANKNIFTY1")
print(f"Data: {len(d)} bars")
print(f"Time: {d['time'].iloc[0]} to {d['time'].iloc[-1]}")
print(f"Close: {d['close'].min():.1f} - {d['close'].max():.1f}")

# Baseline params from V50_INSTRUMENT_PARAMS
p = dict(v50.V50_INSTRUMENT_PARAMS["BANKNIFTY"])
p["atr_min_pts"] = cfg["strategy"]["BANKNIFTY"].get("atr_min_pts", 0)
print(f"\nBaseline params: adx={p['adx_min']}, rr={p['rr']}, pb={p['pb_atr_mult']}, vol={p['use_vol_filter']}")

# Build frame and simulate
f = SS.frame(d, dict(p, use200=True))
s0 = max(int((f["time"] >= SS.T0).idxmax()), rs.WARMUP)
print(f"WARMUP start: bar {s0} ({f['time'].iloc[s0]})")

tr = rs.simulate(f, dict(p, day_loss_limit_pts=p["day_loss_limit"]),
                 start=s0, flat_at="14:30", commission=0.0)
if tr:
    s = rs.stats(tr)
    print(f"\nBaseline (gross, no commission): n={s['n']}, PF={s['pf']}, net={s['net']:.0f}, maxDD={s['max_dd']:.0f}, win={s['win_pct']:.1f}%")
else:
    print("NO TRADES")

# Also test with T0 from crude_bnf_v50_adx_test.py
s0b = max(int((f["time"] >= SS.T0).idxmax()), rs.WARMUP)
print(f"Using T0={SS.T0}, start bar={s0b}")
