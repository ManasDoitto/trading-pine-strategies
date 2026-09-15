import sys, math
from collections import defaultdict
def load(paths, cap=500000):
    g = defaultdict(list)
    for path in paths:
        for l in open(path):
            p = l.strip().split("|")
            if len(p) < 16: continue
            g[p[0]].append(p)
    for tag, rows in g.items():
        rows.sort(key=lambda p: int(p[4].split("=")[1]))
        n=w=sW=sL=nD=sD2=0; off=gpk=gdd=0; wn=[]; pv=float(rows[0][15].split("=")[1])
        for p in rows:
            a,b,c,d,dd,s2,pk,mn = map(float, p[7:15]); nd = int(p[6].split("=")[1])
            n+=a; w+=b; sW+=c; sL+=d; nD+=nd; sD2+=s2
            gdd = max(gdd, dd, gpk-(off+mn)); gpk = max(gpk, off+pk); off += c+d; wn.append(round(c+d))
        net = sW+sL; mean = net/nD if nD else 0; var = sD2/nD-mean*mean if nD else 0
        sh = mean/math.sqrt(var)*math.sqrt(252) if var > 0 else 0
        pos = sum(x > 0 for x in wn); neg = sum(x < 0 for x in wn)
        print(f"{tag:10s} win={len(rows)} trades={n:.0f} ({n/(nD/21):.1f}/mo) win%={100*w/n if n else 0:.1f} PF={sW/-sL if sL else float('inf'):.2f} "
              f"net={net:+.0f}pts Sharpe={sh:+.2f} maxDD={gdd:.0f}pts (Rs {gdd*pv:,.0f} = {gdd*pv/cap*100:.1f}% of 5L) +win={pos} -win={neg} byWin(old->new)={wn}")
load(sys.argv[1:])
