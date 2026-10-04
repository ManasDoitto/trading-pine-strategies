"""
Generate the winning Pine Script with optimized v5.x parameters for Silver.
Based on 25,000-iteration sweep results.
"""
import json

with open('sweep_25000_results.json', 'r') as f:
    results = json.load(f)

print("=== SWEEP SUMMARY ===")
print(f"Total combinations tested: 25,000")
print(f"Profitable candidates (>=93 trades, PF>1.0): {len(results)}")
print(f"Profitable candidates (PF>1.3): {len([r for r in results if r['pf']>1.3])}")
print(f"Profitable candidates (PF>1.5): {len([r for r in results if r['pf']>1.5])}")
print()

# Top by PF
results.sort(key=lambda x: (x['pf'], x['net']), reverse=True)
print("=== TOP 10 BY PF ===")
for i, r in enumerate(results[:10]):
    tpm = r['trades'] / 4.69  # months
    print(f"  #{i+1}: ADX>={r['adx']} RR={r['rr']} PB={r['pb']} SWB={r['swb']} SHA={r['sha']} "
          f"ATR={r['atr_min']} MinSL={r['min_sl']} BO={r['bo_lb']} -> "
          f"{r['trades']}T ({tpm:.1f}/mo) PF={r['pf']:.3f} net={r['net']:+.0f} L/W={r['lw']} WR={r['wr']}%")

# Top by net
print("\n=== TOP 10 BY NET PROFIT ===")
by_net = sorted(results, key=lambda x: x['net'], reverse=True)
for i, r in enumerate(by_net[:10]):
    tpm = r['trades'] / 4.69
    print(f"  #{i+1}: ADX>={r['adx']} RR={r['rr']} PB={r['pb']} SWB={r['swb']} SHA={r['sha']} "
          f"ATR={r['atr_min']} MinSL={r['min_sl']} BO={r['bo_lb']} -> "
          f"{r['trades']}T ({tpm:.1f}/mo) PF={r['pf']:.3f} net={r['net']:+.0f} L/W={r['lw']} WR={r['wr']}%")

# Top by L/W (lowest = best)
print("\n=== TOP 10 BY L/W (lowest = best reward/risk) ===")
by_lw = sorted(results, key=lambda x: x['lw'])
for i, r in enumerate(by_lw[:10]):
    tpm = r['trades'] / 4.69
    print(f"  #{i+1}: ADX>={r['adx']} RR={r['rr']} PB={r['pb']} SWB={r['swb']} SHA={r['sha']} "
          f"ATR={r['atr_min']} MinSL={r['min_sl']} BO={r['bo_lb']} -> "
          f"{r['trades']}T ({tpm:.1f}/mo) PF={r['pf']:.3f} net={r['net']:+.0f} L/W={r['lw']} WR={r['wr']}%")

# Best balance (PF > 1.5 AND net > 10000 AND L/W < 0.45)
print("\n=== BEST BALANCE (PF>1.3, L/W<0.45, net>10000) ===")
balanced = [r for r in results if r['pf'] > 1.3 and r['lw'] < 0.45 and r['net'] > 10000]
balanced.sort(key=lambda x: (x['pf'], x['net']), reverse=True)
for i, r in enumerate(balanced[:10]):
    tpm = r['trades'] / 4.69
    print(f"  #{i+1}: ADX>={r['adx']} RR={r['rr']} PB={r['pb']} SWB={r['swb']} SHA={r['sha']} "
          f"ATR={r['atr_min']} MinSL={r['min_sl']} BO={r['bo_lb']} -> "
          f"{r['trades']}T ({tpm:.1f}/mo) PF={r['pf']:.3f} net={r['net']:+.0f} L/W={r['lw']} WR={r['wr']}%")

print(f"\n=== WINNER (by PF) ===")
r = results[0]
print(f"Config: ADX>={r['adx']}, RR={r['rr']}, PB={r['pb']}, SWB={r['swb']}, "
      f"SHA={r['sha']}, ATR_min={r['atr_min']}, MinSL={r['min_sl']}, BO={r['bo_lb']}")
print(f"Results: {r['trades']} trades ({r['trades']/4.69:.1f}/month), PF={r['pf']:.3f}, "
      f"WR={r['wr']}%, net={r['net']:+.0f} pts, L/W={r['lw']}, DD={r['dd']:+.0f}")
