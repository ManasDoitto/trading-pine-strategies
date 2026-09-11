"""Cross-instrument comparison of the VARIANT LAB v1 results (reads lab_raw.txt via lab_agg)."""
import csv, os, sys
from lab_agg import LABEL, FAMILY, parse, aggregate

HERE = os.path.dirname(os.path.abspath(__file__))
COMBOS = ["CRUDEOIL1! 5m", "CRUDEOIL1! 3m", "BANKNIFTY1! 5m", "BANKNIFTY1! 3m", "NIFTY 5m", "NIFTY 3m"]
SHORT = {"CRUDEOIL1! 5m": "Crude 5m", "CRUDEOIL1! 3m": "Crude 3m", "BANKNIFTY1! 5m": "BN 5m",
         "BANKNIFTY1! 3m": "BN 3m", "NIFTY 5m": "Nifty 5m", "NIFTY 3m": "Nifty 3m"}

out = aggregate(parse())
L = []

L.append("## A. Best variant per instrument / timeframe (ranked by daily Sharpe, NET of 0.02%/side cost)\n")
L.append("| Script / TF | History | Best | Trades | /month | Win% | PF | Net pts | Gross pts | bps/trade | Sharpe | +windows | 2nd | 3rd | v3.0 (V01) net |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for c in COMBOS:
    g = out[c]; R = g["res"]
    order = sorted(R, key=lambda v: -R[v]["sharpe"])
    b = R[order[0]]
    L.append(f"| {SHORT[c]} | {g['start']}..{g['end']} ({g['months']:.0f} mo, {g['windows']} win) | V{order[0]:02d} {LABEL[order[0]]} | "
             f"{b['n']} | {b['tpm']:.0f} | {b['win']:.1f} | {b['pf']:.2f} | {b['net']:+,.0f} | {b['gross']:+,.0f} | {b['bps']:+.1f} | "
             f"{b['sharpe']:+.2f} | {b['posWin']}/{b['nWin']} | V{order[1]:02d} ({R[order[1]]['sharpe']:+.2f}) | "
             f"V{order[2]:02d} ({R[order[2]]['sharpe']:+.2f}) | {R[1]['net']:+,.0f} |")

L.append("\n## B. Every variant x every script/TF -- net points (daily Sharpe)\n")
L.append("| # | Variant | " + " | ".join(SHORT[c] for c in COMBOS) + " | Net+ | Gross+ | Avg Sharpe |")
L.append("|---|---|" + "---|" * len(COMBOS) + "---|---|---|")
rows = []
for v in range(1, 33):
    cells, npos, gpos, sh = [], 0, 0, 0.0
    for c in COMBOS:
        r = out[c]["res"][v]
        cells.append(f"{r['net']:+,.0f} ({r['sharpe']:+.2f})")
        npos += r["net"] > 0; gpos += r["gross"] > 0; sh += r["sharpe"]
    rows.append((sh / len(COMBOS), v, cells, npos, gpos))
for sh, v, cells, npos, gpos in sorted(rows, reverse=True):
    L.append(f"| V{v:02d} | {LABEL[v]} | " + " | ".join(cells) + f" | {npos}/6 | {gpos}/6 | {sh:+.2f} |")

L.append("\n## C. Strategy families -- best member per script/TF (daily Sharpe)\n")
fams = sorted(set(FAMILY.values()))
L.append("| Family | " + " | ".join(SHORT[c] for c in COMBOS) + " |")
L.append("|---|" + "---|" * len(COMBOS))
for f in fams:
    mem = [v for v in FAMILY if FAMILY[v] == f]
    cells = []
    for c in COMBOS:
        R = out[c]["res"]
        best = max(mem, key=lambda v: R[v]["sharpe"])
        cells.append(f"V{best:02d} {R[best]['sharpe']:+.2f}")
    L.append(f"| {f} | " + " | ".join(cells) + " |")

L.append("\n## D. Cost drag -- how many of the 32 variants are profitable BEFORE vs AFTER costs\n")
L.append("| Script / TF | Avg cost per trade (pts) | Gross-profitable variants | Net-profitable variants |")
L.append("|---|---|---|---|")
for c in COMBOS:
    R = out[c]["res"]
    cpt = sum(R[v]["cost"] for v in R) / sum(R[v]["n"] for v in R)
    L.append(f"| {SHORT[c]} | {cpt:.1f} | {sum(R[v]['gross'] > 0 for v in R)}/32 | {sum(R[v]['net'] > 0 for v in R)}/32 |")

L.append("\n## E. CrudeOil -- how many of the user's 36 marked trades each variant catches (same side, +-30 min)\n")
L.append("| # | Variant | Crude 5m caught | Crude 3m caught |")
L.append("|---|---|---|---|")
for v in sorted(range(1, 33), key=lambda v: -(out['CRUDEOIL1! 5m']['res'][v]['caught'] + out['CRUDEOIL1! 3m']['res'][v]['caught']))[:10]:
    L.append(f"| V{v:02d} | {LABEL[v]} | {out['CRUDEOIL1! 5m']['res'][v]['caught']}/36 | {out['CRUDEOIL1! 3m']['res'][v]['caught']}/36 |")

md = "\n".join(L)
open(os.path.join(HERE, "lab_summary.md"), "w", encoding="utf-8").write(md)

with open(os.path.join(HERE, "lab_results.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["script_tf", "from", "to", "windows", "variant", "label", "family", "trades", "trades_per_month",
                "win_pct", "profit_factor", "net_pts", "gross_pts", "cost_pts", "avg_win", "avg_loss",
                "bps_per_trade", "daily_sharpe", "worst_window_dd", "positive_windows", "user_trades_caught",
                "net_by_window_oldest_first"])
    for c in COMBOS:
        g = out[c]
        for v in range(1, 33):
            r = g["res"][v]
            w.writerow([SHORT[c], g["start"], g["end"], g["windows"], f"V{v:02d}", LABEL[v], FAMILY[v], r["n"],
                        round(r["tpm"], 1), round(r["win"], 1), round(r["pf"], 3), round(r["net"]), round(r["gross"]),
                        round(r["cost"]), round(r["avgW"], 1), round(r["avgL"], 1), round(r["bps"], 2),
                        round(r["sharpe"], 3), round(r["worstDD"]), f"{r['posWin']}/{r['nWin']}",
                        r["caught"] if c.startswith("CRUDE") else "", " ".join(str(x) for x in r["wnet"])])
print(md)
