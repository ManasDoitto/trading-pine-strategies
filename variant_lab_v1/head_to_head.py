"""Head-to-head: existing picks (re-run in the Strategy Tester on the lab's exact windows, 0.02%/side)
vs VARIANT LAB v1 variants. Writes head_to_head.md next to this file."""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"D:/Trading code-Claude/variant_lab_v1")
from lab_agg import parse, aggregate, LABEL
lab = aggregate(parse())

cmp = {}
for line in open(os.path.join(HERE, "head_to_head_raw.txt"), encoding="utf-8"):
    p = line.strip().split("|")
    if len(p) < 13:
        continue
    kv = {x.split("=")[0]: int(x.split("=")[1]) for x in p[4:7]}
    n, w, sW, sL, dd, sD2 = map(float, p[7:13])
    cmp.setdefault(p[0], []).append(dict(**kv, n=n, w=w, sW=sW, sL=sL, dd=dd, sD2=sD2))

def summ(ws):
    ws = sorted(ws, key=lambda r: r["from"])
    n = sum(r["n"] for r in ws); w = sum(r["w"] for r in ws)
    sW = sum(r["sW"] for r in ws); sL = sum(r["sL"] for r in ws)
    nD = sum(r["nD"] for r in ws); sD2 = sum(r["sD2"] for r in ws)
    net = sW + sL; mean = net / nD; var = sD2 / nD - mean * mean
    months = (ws[-1]["last"] - ws[0]["from"]) / (1000 * 86400 * 30.44)
    return dict(n=int(n), tpm=n / months, win=100 * w / n, pf=sW / -sL, net=net,
                sharpe=mean / math.sqrt(var) * math.sqrt(252) if var > 0 else 0,
                worstDD=max(r["dd"] for r in ws), posWin=sum(r["sW"] + r["sL"] > 0 for r in ws),
                nWin=len(ws), wnet=[round(r["sW"] + r["sL"]) for r in ws],
                avgW=sW / w, avgL=sL / (n - w))

def labrow(combo, v):
    r = lab[combo]["res"][v]
    return dict(n=r["n"], tpm=r["tpm"], win=r["win"], pf=r["pf"], net=r["net"], sharpe=r["sharpe"],
                worstDD=r["worstDD"], posWin=r["posWin"], nWin=r["nWin"], wnet=r["wnet"],
                avgW=r["avgW"], avgL=r["avgL"])

SCRIPTS = [
 ("CrudeOil (MCX:CRUDEOIL1!)", [
   ("v4.0 SHA flip RR3 (lab V21, tester-verified)", "5m", labrow("CRUDEOIL1! 5m", 21)),
   ("v2.1 EMA 9/22 pullback (previous pick)", "5m", summ(cmp["v2.1"])),
   ("v3.0 SHA+RSI3 pullback (lab V01)", "5m", labrow("CRUDEOIL1! 5m", 1)),
   ("best 3m: v3.0 trig RSI>50 (lab V07)", "3m", labrow("CRUDEOIL1! 3m", 7))]),
 ("BankNifty (NSE:BANKNIFTY1!)", [
   ("v13 sweep-fade 'bear', RR 1:6 (previous pick)", "5m", summ(cmp["v13"])),
   ("best lab variant: SHA flip +EMA200 RR2 (V22)", "5m", labrow("BANKNIFTY1! 5m", 22)),
   ("best 3m: Donchian20 +SHA RR3 (lab V24)", "3m", labrow("BANKNIFTY1! 3m", 24))]),
 ("Nifty 50 (NSE:NIFTY spot)", [
   ("v2 sweep-fade 5m retune, RR 1:6 (previous pick)", "5m", summ(cmp["niftyv2_5m"])),
   ("best lab variant: SHA flip +EMA200 RR2 (V22)", "5m", labrow("NIFTY 5m", 22)),
   ("best 3m: SHA flip RR3 (lab V21)", "3m", labrow("NIFTY 3m", 21))]),
]
L = ["| Script | Strategy | TF | Trades | /month | Win% | Avg win / loss (pts) | PF | Net pts | Daily Sharpe | Worst-window DD | +windows | Net by window, oldest -> newest |",
     "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for s, cands in SCRIPTS:
    for name, tf, r in cands:
        L.append(f"| {s} | {name} | {tf} | {r['n']:,} | {r['tpm']:.0f} | {r['win']:.1f} | {r['avgW']:.0f} / {r['avgL']:.0f} | "
                 f"{r['pf']:.2f} | {r['net']:+,.0f} | {r['sharpe']:+.2f} | {r['worstDD']:,.0f} | {r['posWin']}/{r['nWin']} | "
                 + " ".join(f"{x:+,}" for x in r["wnet"]) + " |")
md = "\n".join(L)
open(os.path.join(HERE, "head_to_head.md"), "w", encoding="utf-8").write(md)
print(md)
