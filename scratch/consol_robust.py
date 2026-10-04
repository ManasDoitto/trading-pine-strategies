import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd, itertools
import backtest_consolidation_breakout as C
orig=C.signals
def sig_filtered(d,K):
    L,S,bh,bl,bn,atr=orig(d,K); c=d["close"]; o=d["open"]; h=d["high"]; l=d["low"]
    ema=c.ewm(span=120,adjust=False).mean().to_numpy(); rng=(h-l).to_numpy(); body=(c-o).abs().to_numpy(); strong=(body>=0.6*rng)&(rng>=1.0*atr)
    return L&(c.to_numpy()>ema)&strong, S&(c.to_numpy()<ema)&strong, bh,bl,bn,atr
C.signals=sig_filtered
data={s.upper():C.crypto_4h(s) for s in ("btc","eth","sol","bnb","xrp")}; data["XAU"]=C.gold_4h()
cc=lambda tr:2*0.0007*tr["entry"]; cg=lambda tr:pd.Series(1.0,index=tr.index); costs={k:(cg if k=="XAU" else cc) for k in data}
main={k:C.simulate(d[0],d[1],costs[k],2.5,"far",3.0) for k,d in data.items()}
allt=pd.concat([t.assign(m=k) for k,t in main.items()]).sort_values("entry_time").reset_index(drop=True)
print("PER MARKET (trend+strong-candle, K2.5, far stop, RR3):")
for k,t in main.items():
    te=t[t.entry_time>=C.SPLIT]; print(f"  {k:4} n={len(t):4} win={(t.net_r>0).mean():.0%} gross={t.gross_r.mean():+.3f} net={t.net_r.mean():+.3f} t={C.tstat(t.net_r):+.1f} | test n={len(te)} net={te.net_r.mean():+.3f} | long {t[t.side==1].net_r.mean():+.3f} short {t[t.side==-1].net_r.mean():+.3f}")
print("markets with positive net:", sum(t.net_r.mean()>0 for t in main.values()),"/6; positive in test:", sum(t[t.entry_time>=C.SPLIT].net_r.mean()>0 for t in main.values()),"/6")
y=allt.groupby(allt.entry_time.dt.year).net_r.agg(["count","mean"]).round(3); print("\nby year (all markets pooled):", y.T.to_dict())
print("\nSENSITIVITY pooled net R (test/all): ", end="")
for K,sm in itertools.product((1.5,2.5,3.5),("far","mid")):
    a=pd.concat([C.simulate(d[0],d[1],costs[k],K,sm,3.0) for k,d in data.items()]); print(f"K{K}/{sm}: {a.net_r.mean():+.3f}/{a[a.entry_time>=C.SPLIT].net_r.mean():+.3f}  ",end="")
c2={k:(lambda tr,f=f:2*(2*f)*tr["entry"] if False else f(tr)*2) for k,f in costs.items()}
a2=pd.concat([C.simulate(d[0],d[1],c2[k],2.5,"far",3.0) for k,d in data.items()]); print(f"\ncosts x2: net {a2.net_r.mean():+.3f} (t={C.tstat(a2.net_r):.1f})")
# block bootstrap by month for mean net R
allt["ym"]=allt.entry_time.dt.to_period("M"); g=[x.net_r.to_numpy() for _,x in allt.groupby("ym")]; rng=np.random.default_rng(5)
bs=[np.concatenate([g[i] for i in rng.integers(0,len(g),len(g))]).mean() for _ in range(3000)]
print(f"monthly-block bootstrap of mean net R: {np.mean(bs):+.3f}  95% CI [{np.percentile(bs,2.5):+.3f}, {np.percentile(bs,97.5):+.3f}]  P(<=0)={np.mean(np.array(bs)<=0):.1%}")
# dollar sim: one account, 1% risk/trade, cap 3% open risk
def sim(tr,f,cap,start=1000.0):
    ev=[]; rows=list(tr.itertuples())
    for i,r in enumerate(rows): ev+= [(r.entry_time,1,i),(r.exit_time,0 if r.exit_time>r.entry_time else 2,i)]
    ev.sort(key=lambda e:(e[0],e[1])); eq=start; peak=start; dd=0; size={}; openr=0; taken=0; path=[]
    for t,k,i in ev:
        if k==1:
            amt=f*eq
            if openr+amt>cap*eq: continue
            size[i]=amt; openr+=amt; taken+=1
        elif i in size:
            a=size.pop(i); openr-=a; eq+=a*rows[i].net_r; peak=max(peak,eq); dd=min(dd,eq/peak-1); path.append((t,eq))
    return eq,dd,taken,path
sub=allt[allt.m!="XAU"]
print("\nDOLLARS, crypto-only (5 perps), $1000, 1% risk/trade, max 3% open risk:")
for f in (0.005,0.01,0.02):
    for nm,t in (("all 2019-2026",sub),("test 2023-2026",sub[sub.entry_time>=C.SPLIT])):
        eq,dd,tk,path=sim(t,f,0.06 if f<=0.01 else 0.06); yrs=(t.exit_time.max()-t.entry_time.min()).days/365.25
        print(f"  risk {f:.1%}: {nm:15} $1000 -> ${eq:,.0f}  CAGR {(eq/1000)**(1/yrs)-1:+.0%}  maxDD {dd:.0%}  trades {tk}")
