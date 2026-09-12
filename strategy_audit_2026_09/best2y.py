"""Deep analysis of every crude/BankNifty strategy with >= 24 months of tiled walk-forward data."""
import math, os
from datetime import datetime, timezone
S = os.path.dirname(os.path.abspath(__file__))
LAB3 = r"D:/Trading code-Claude/strategy_audit_2026_09/lab3_raw.txt"
def mon(ms): return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%b %y")

want = {"crude v2.0 base (aligned)": "CR v2.0 EMA pullback sep0.5",
        "crude v2.1": "CR v2.1 EMA pullback sep1.5",
        "crude v2.3": "CR v2.3 v2.1+daily trend",
        "bnf v0.4": "BN v0.4 pullback+15m ADX",
        "v10.3": "BN v10.3 PD sweep+dtrend",
        "v13": "BN v13 sweep fade bear"}
lab = {1: "CR v4.0 SHA flip RR3", 4: "CR v4.0 + outside prior VA", 2: "CR v4.0 + prior-POC side"}
st = {}
for line in open(os.path.join(S, "audit_raw.txt"), encoding="utf-8"):
    p = line.strip().split("|")
    if len(p) < 9 or p[1] != "AUD" or p[0] not in want or p[3] != "5":
        continue
    kv = dict(x.split("=") for x in p[4:8]); v = [float(x) for x in p[8].split(",")]
    s = st.setdefault(want[p[0]], dict(sym=p[2], pv=float(kv["pv"]), W=[]))
    s["W"].append(dict(frm=int(kv["from"]), last=int(kv["last"]), nD=int(kv["nD"]), n=v[0], w=v[1], sW=v[2], sL=v[3], dd=v[4], d2=v[5], pk=v[6], mn=v[7], cost=None))
cur = None
for line in open(LAB3, encoding="utf-8"):
    line = line.strip()
    if line.startswith("LAB3|"):
        p = line.split("|"); kv = dict(x.split("=") for x in p[3:]); cur = dict(sym=p[1], **{k: float(v) for k, v in kv.items()})
    elif line.startswith("V") and cur and cur["sym"] == "CRUDEOIL1!":
        p = line.split("|"); k = int(p[0][1:])
        if k in lab:
            r = [float(x) for x in p[1:]]
            s = st.setdefault(lab[k], dict(sym="CRUDEOIL1!", pv=cur["pv"], W=[]))
            s["W"].append(dict(frm=int(cur["from"]), last=int(cur["last"]), nD=int(cur["nD"]), n=r[0], w=r[1], sW=r[2], sL=r[3], cost=r[4], dd=r[5], d2=r[6], pk=r[7], mn=r[8]))

def M(s):
    W = sorted(s["W"], key=lambda x: x["frm"])
    months = (W[-1]["last"] - W[0]["frm"]) / (1000 * 86400 * 30.44)
    n = sum(x["n"] for x in W); w = sum(x["w"] for x in W); sW = sum(x["sW"] for x in W); sL = sum(x["sL"] for x in W)
    nD = sum(x["nD"] for x in W); d2 = sum(x["d2"] for x in W)
    off = gpk = gdd = 0.0
    for x in W:
        gdd = max(gdd, x["dd"], gpk - (off + x["mn"])); gpk = max(gpk, off + x["pk"]); off += x["sW"] + x["sL"]
    net = sW + sL; mean = net / nD; var = d2 / nD - mean * mean
    wn = [x["sW"] + x["sL"] for x in W]; srt = sorted(wn, reverse=True)
    cost = sum(x["cost"] for x in W) if all(x["cost"] is not None for x in W) else None
    return dict(W=W, months=months, n=n, w=w, sW=sW, sL=sL, net=net, sh=mean / math.sqrt(var) * math.sqrt(252) if var > 0 else 0,
                dd=gdd, wn=wn, pf=sW / -sL, avgW=sW / w, avgL=sL / (n - w), exp=net / n, pos=sum(x > 0 for x in wn),
                ex1=net - srt[0], ex2=net - srt[0] - srt[1], best=srt[0], worst=srt[-1], cost=cost, pv=s["pv"], sym=s["sym"])

R = {k: M(v) for k, v in st.items()}
print("== CORE METRICS (points per lot, 0.02%/side commission, no slippage)")
print(f"{'strategy':32s} {'mo':>5s} {'trd':>5s} {'/mo':>5s} {'win%':>5s} {'PF':>5s} {'net':>7s} {'pts/mo':>6s} {'Shrp':>5s} {'maxDD':>6s} {'net/DD':>6s} {'avgW':>6s} {'avgL':>6s} {'exp/tr':>6s} {'+win':>5s} {'best':>6s} {'worst':>6s} {'ex-best1':>8s} {'ex-best2':>8s}")
for k, r in sorted(R.items(), key=lambda kv: (kv[1]["sym"], -kv[1]["net"])):
    print(f"{k:32s} {r['months']:5.1f} {r['n']:5.0f} {r['n']/r['months']:5.1f} {100*r['w']/r['n']:5.1f} {r['pf']:5.2f} {r['net']:+7.0f} {r['net']/r['months']:+6.0f} {r['sh']:+5.2f} {r['dd']:6.0f} {r['net']/r['dd']:6.2f} {r['avgW']:6.1f} {r['avgL']:6.1f} {r['exp']:+6.2f} {r['pos']:2d}/{len(r['wn']):<2d} {r['best']:+6.0f} {r['worst']:+6.0f} {r['ex1']:+8.0f} {r['ex2']:+8.0f}")
print("\n== COSTS (lab rows only): commission paid vs gross")
for k, r in R.items():
    if r["cost"] is not None:
        print(f"{k:32s} gross {r['net']+r['cost']:+.0f}  commission {r['cost']:.0f} ({100*r['cost']/(r['net']+r['cost']):.0f}% of gross)  = {r['cost']/r['n']:.2f} pts/trade")
print("\n== SLIPPAGE STRESS (extra pts per round trip on top of commission)")
for k, r in sorted(R.items(), key=lambda kv: (kv[1]["sym"], -kv[1]["net"])):
    steps = (2, 4, 6) if r["sym"] == "CRUDEOIL1!" else (5, 10, 20)
    out = []
    for s in steps:
        net = r["net"] - s * r["n"]; pf = (r["sW"] - s * r["w"]) / -(r["sL"] - s * (r["n"] - r["w"]))
        out.append(f"{s:>2d}pt: {net:+6.0f} PF {pf:.2f}")
    print(f"{k:32s} " + " | ".join(out))
print("\n== BY PERIOD")
for k, r in sorted(R.items(), key=lambda kv: (kv[1]["sym"], -kv[1]["net"])):
    W, wn = r["W"], r["wn"]
    if len(W) == 11:
        groups = [(0, 4), (4, 8), (8, 11)]
    else:
        groups = [(i, i + 1) for i in range(len(W))]
    parts = [f"{mon(W[a]['frm'])}-{mon(W[b-1]['last'])}: {sum(wn[a:b]):+.0f}" for a, b in groups]
    print(f"{k:32s} " + " | ".join(parts))
print("\n== RUPEES PER LOT (net x point value)")
for k, r in sorted(R.items(), key=lambda kv: (kv[1]["sym"], -kv[1]["net"])):
    print(f"{k:32s} pv {r['pv']:.0f}: net Rs{r['net']*r['pv']:,.0f} over {r['months']:.1f} mo = Rs{r['net']*r['pv']/r['months']:,.0f}/mo ; max DD Rs{r['dd']*r['pv']:,.0f}")
def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
print("\n== WINDOW-NET CORRELATION")
pairs = [("CR v4.0 SHA flip RR3", "CR v2.0 EMA pullback sep0.5"), ("CR v4.0 SHA flip RR3", "CR v2.1 EMA pullback sep1.5"),
         ("CR v2.0 EMA pullback sep0.5", "CR v2.1 EMA pullback sep1.5"), ("BN v0.4 pullback+15m ADX", "BN v10.3 PD sweep+dtrend"),
         ("BN v0.4 pullback+15m ADX", "BN v13 sweep fade bear"), ("BN v10.3 PD sweep+dtrend", "BN v13 sweep fade bear")]
for a, b in pairs:
    print(f"{a:30s} vs {b:30s} r = {corr(R[a]['wn'], R[b]['wn']):+.2f}")
print("\n== TWO-STRATEGY PORTFOLIOS (1 lot each; window sums; DD at window granularity = lower bound)")
for a, b in pairs:
    s = [x + y for x, y in zip(R[a]["wn"], R[b]["wn"])]
    eq = pk = dd = 0.0
    for x in s:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
    print(f"{a} + {b}: net {sum(s):+.0f}, +windows {sum(x>0 for x in s)}/{len(s)}, window-level DD {dd:.0f} (standalone DDs {R[a]['dd']:.0f} + {R[b]['dd']:.0f}), by window " + " ".join(f"{x:+.0f}" for x in s))
