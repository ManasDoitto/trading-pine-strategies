"""Aggregate BankNifty Combined v1 tiled-window rows (tag ALL_any) per module + total."""
import math, os, sys
TAG = sys.argv[1] if len(sys.argv) > 1 else "ALL_any"
HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for line in open(os.path.join(HERE, "combined_bnf_raw.txt"), encoding="utf-8"):
    p = line.strip().split("|")
    if not p or p[0] != TAG:
        continue
    kv = dict(x.split("=") for x in p[4:8])
    mods = [[float(v) for v in m.split(",")] for m in p[8:12]]
    rows.append(dict(frm=int(kv["from"]), last=int(kv["last"]), nD=int(kv["nD"]), mods=mods))
rows.sort(key=lambda r: r["frm"])
assert all(a["last"] < b["frm"] for a, b in zip(rows, rows[1:])), "overlap"
months = (rows[-1]["last"] - rows[0]["frm"]) / (1000 * 86400 * 30.44)
nD = sum(r["nD"] for r in rows)
names = ["A v13 sweep-fade", "B v0.4 pullback", "C MTF v1.1", "TOTAL"]
print(f"{len(rows)} windows, {months:.1f} months, {nD} days\n")
print("| Module | Trades | /mo | Win% | PF | Net pts | pts/mo | Rs/mo (1 lot) | Sharpe | Max DD pts | +windows | by window old->new |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for m in range(4):
    n = w = sW = sL = d2 = 0.0
    off = gpk = gdd = 0.0
    wn = []
    for r in rows:
        x = r["mods"][m]
        n += x[0]; w += x[1]; sW += x[2]; sL += x[3]; d2 += x[5]
        gdd = max(gdd, x[4], gpk - (off + x[7])); gpk = max(gpk, off + x[6]); off += x[2] + x[3]
        wn.append(round(x[2] + x[3]))
    net = sW + sL
    mean = net / nD
    var = d2 / nD - mean * mean
    sh = mean / math.sqrt(var) * math.sqrt(252) if var > 0 else 0
    pf = sW / -sL if sL < 0 else float("inf")
    print(f"| {names[m]} | {int(n)} | {n/months:.1f} | {100*w/n if n else 0:.1f} | {pf:.2f} | {net:+,.0f} | {net/months:+.0f} | "
          f"{30*net/months:+,.0f} | {sh:+.2f} | {gdd:,.0f} | {sum(v>0 for v in wn)}/{len(wn)} | " + " ".join(f"{v:+}" for v in wn) + " |")
