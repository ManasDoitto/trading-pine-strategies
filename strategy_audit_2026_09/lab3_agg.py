"""Aggregate VARIANT LAB v3 (volume profile) window dumps (lab3_raw.txt) per script/TF/variant."""
import math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "lab3_raw.txt")
LABEL = {
 1: "SHA flip RR3 (v4.0 rules)", 2: "SHA flip + pPOC side", 3: "SHA flip + dPOC side", 4: "SHA flip + outside prior value",
 5: "SHA flip + inside prior value", 6: "SHA flip + pPOC & dPOC side", 7: "80% rule -> opposite VA edge", 8: "80% rule -> pPOC",
 9: "VA-edge fade -> pPOC", 10: "VA-edge fade RR2", 11: "VA-edge fade -> dPOC", 12: "pPOC bounce RR2", 13: "pPOC bounce RR3",
 14: "VA breakout-retest RR2", 15: "VA breakout-retest RR3", 16: "dPOC-trend pullback RR2", 17: "dPOC-trend pullback RR1.5",
 18: "dPOC-trend pullback + pPOC side RR2", 19: "VP-level sweep fade RR2", 20: "VP-level sweep fade RR6",
 21: "VP-level sweep fade RR6 + v13 trend gate", 22: "VA-edge fade -> pPOC + v13 trend gate", 23: "SHA flip + pPOC & dPOC side RR2",
 24: "dPOC-trend pullback RR3",
}

def parse():
    blocks, cur = [], None
    for line in open(RAW, encoding="utf-8"):
        line = line.strip()
        if line.startswith("LAB3|"):
            p = line.split("|")
            kv = dict(x.split("=") for x in p[3:])
            cur = {"sym": p[1], "tf": p[2], **{k: float(v) for k, v in kv.items()}, "rows": {}}
            blocks.append(cur)
        elif line.startswith("V") and cur is not None:
            p = line.split("|")
            cur["rows"][int(p[0][1:])] = [float(x) for x in p[1:]]
    return blocks

def aggregate(blocks):
    g = defaultdict(list)
    for b in blocks:
        g[(b["sym"], b["tf"])].append(b)
    out = {}
    for key, bl in g.items():
        bl.sort(key=lambda b: b["from"])
        ov = [a["last"] >= c["from"] for a, c in zip(bl, bl[1:])]
        months = (bl[-1]["last"] - bl[0]["from"]) / (1000 * 86400 * 30.44)
        nD = sum(b["nD"] for b in bl)
        res = {}
        for v in range(1, 25):
            n = w = sW = sL = cost = sD2 = 0.0
            off = gpk = gdd = 0.0
            wn = []
            for b in bl:
                r = b["rows"][v]
                n += r[0]; w += r[1]; sW += r[2]; sL += r[3]; cost += r[4]; sD2 += r[6]
                gdd = max(gdd, r[5], gpk - (off + r[8])); gpk = max(gpk, off + r[7]); off += r[2] + r[3]
                wn.append(round(r[2] + r[3]))
            net = sW + sL
            mean = net / nD
            var = sD2 / nD - mean * mean
            res[v] = dict(n=int(n), tpm=n / months, ppm=net / months, win=100 * w / n if n else 0,
                          pf=sW / -sL if sL < 0 else float("inf"), net=net, gross=net + cost,
                          sharpe=mean / math.sqrt(var) * math.sqrt(252) if var > 0 else 0,
                          dd=gdd, pos=sum(x > 0 for x in wn), nwin=len(bl), wnet=wn)
        out[key] = dict(res=res, months=months, windows=len(bl), overlaps=any(ov),
                        start=bl[0]["from"], end=bl[-1]["last"], pv=bl[0]["pv"])
    return out

if __name__ == "__main__":
    out = aggregate(parse())
    for (sym, tf), g in out.items():
        print(f"\n## {sym} {tf}m  {g['months']:.1f} months, {g['windows']} windows, overlaps={g['overlaps']}, pv={g['pv']:.0f}")
        print("| # | Variant | Trades | /mo | Win% | PF | Net pts | pts/mo | Gross | Sharpe | Max DD | +win | by window old->new |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for v in sorted(g["res"], key=lambda v: -g["res"][v]["sharpe"]):
            r = g["res"][v]
            print(f"| V{v:02d} | {LABEL[v]} | {r['n']} | {r['tpm']:.0f} | {r['win']:.1f} | {r['pf']:.2f} | {r['net']:+,.0f} | "
                  f"{r['ppm']:+.0f} | {r['gross']:+,.0f} | {r['sharpe']:+.2f} | {r['dd']:,.0f} | {r['pos']}/{r['nwin']} | "
                  + " ".join(f"{x:+}" for x in r["wnet"]) + " |")
