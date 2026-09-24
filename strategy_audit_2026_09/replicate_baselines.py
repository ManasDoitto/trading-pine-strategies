"""Replication gate: research_sim on harvested bars vs documented TradingView baselines."""
import tomllib
from pathlib import Path
from strategy_audit_2026_09 import research_sim as rs

cfg = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]
CASES = [("MCX_SILVER1", "SILVER", 1.35, 160845, True), ("MCX_CRUDEOIL1", "CRUDEOIL", 1.12, 2811, True),
         ("MCX_SILVERM1", "SILVERM", 1.148, 73565, False)]
for name, key, pf, net, gate in CASES:
    p = cfg[key]
    for label, kw in [("TV-like (gap fills, comm)", {}), ("no gap fills", dict(gap_fills=False))]:
        s = rs.stats(rs.run(name, p, **kw))
        ok = abs(s["pf"] - pf) <= .05 and abs(s["net"] - net) <= .15 * abs(net)
        print(f"{name:14} {label:26} {s}  | TV PF {pf} net {net}  {'PASS' if ok else 'FAIL'}{'' if gate else ' (reference)'}")
