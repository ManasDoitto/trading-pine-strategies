"""Aggregate VARIANT LAB v2 window dumps (lab2_raw.txt) per script/TF/variant."""
import math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "lab2_raw_window_dumps.txt")
LABEL = {
 1: "SHA pullback RR2", 2: "SHA pullback RR2.4", 3: "SHA pullback RR3", 4: "SHA pullback RR2.4, 1st pullback/leg",
 5: "SHA pullback RR2.4 + EMA aligned", 6: "SHA pullback RR2.4 + 15m SHA same colour",
 7: "SHA pullback RR2.4 + 15m strong + 5m strong", 8: "SHA pullback RR2 + 15m strong + 5m strong",
 9: "SHA pullback RR3 + 15m strong + 5m strong", 10: "SHA pullback RR2.4 + aligned + 15m same",
 11: "SHA pullback RR2.4, SL buf 0.2ATR", 12: "SHA pullback RR2.4, trigger next bar only",
 13: "CPR pullback RR2", 14: "CPR pullback + SHA agree RR2", 15: "PDH/PDL break-retest RR2",
 16: "PDH/PDL retest + SHA agree RR2", 17: "PDH/PDL break-retest RR3", 18: "S1/R1 fade RR1.5",
 19: "CPR pullback RR3", 20: "SHA pullback RR2.4 (crude EOD flat)",
}

def parse():
    blocks, cur = [], None
    for line in open(RAW, encoding="utf-8"):
        line = line.strip()
        if line.startswith("LAB2|"):
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
        for v in range(1, 21):
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
