"""Aggregate walk-forward AUDIT rows (audit_raw.txt): tag|AUD|ticker|tf|from=|last=|nD=|pv=|n,w,sW,sL,dd,d2,pk,mn"""
import math, os
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
g = defaultdict(list)
for line in open(os.path.join(HERE, "audit_raw.txt"), encoding="utf-8"):
    p = line.strip().split("|")
    if len(p) < 9 or p[1] != "AUD":
        continue
    kv = dict(x.split("=") for x in p[4:8])
    v = [float(x) for x in p[8].split(",")]
    g[(p[0], p[2], p[3])].append(dict(frm=int(kv["from"]), last=int(kv["last"]), nD=int(kv["nD"]), v=v))
print("| Strategy | Sym | TF | Windows | Months | Trades | /mo | Win% | PF | Net pts | pts/mo | Sharpe | Max DD | +win | by window old->new |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for (tag, sym, tf), rows in sorted(g.items(), key=lambda kv: kv[0]):
    rows.sort(key=lambda r: r["frm"])
    ok = all(a["last"] < b["frm"] for a, b in zip(rows, rows[1:]))
    months = (rows[-1]["last"] - rows[0]["frm"]) / (1000 * 86400 * 30.44)
    nD = sum(r["nD"] for r in rows)
    n = w = sW = sL = d2 = 0.0
    off = gpk = gdd = 0.0
    wn = []
    for r in rows:
        x = r["v"]
        n += x[0]; w += x[1]; sW += x[2]; sL += x[3]; d2 += x[5]
        gdd = max(gdd, x[4], gpk - (off + x[7])); gpk = max(gpk, off + x[6]); off += x[2] + x[3]
        wn.append(round(x[2] + x[3]))
    net = sW + sL
    mean = net / nD if nD else 0
    var = d2 / nD - mean * mean if nD else 0
    sh = mean / math.sqrt(var) * math.sqrt(252) if var > 0 else 0
    pf = sW / -sL if sL < 0 else float("inf")
    print(f"| {tag} | {sym} | {tf} | {len(rows)}{'' if ok else ' OVERLAP'} | {months:.1f} | {int(n)} | {n/months:.1f} | {100*w/n if n else 0:.1f} | {pf:.2f} | {net:+,.0f} | {net/months:+.0f} | {sh:+.2f} | {gdd:,.0f} | {sum(x>0 for x in wn)}/{len(wn)} | " + " ".join(f"{x:+}" for x in wn) + " |")
