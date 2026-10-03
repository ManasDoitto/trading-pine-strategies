"""Slow v5.0 SHA-ADX config (1h base, 4h ADX gate, flip) across 13 large-cap perps.
Pre-specified universe (market-cap list, ALL reported). Config ADX>=40/RR4 was chosen on BTC pre-2021-10
data. Window 2021-10-04..2026-10-02. Costs 0.07%/side + real funding. Frictionless lot sizing."""
import sys, pickle
sys.path.insert(0,'.')
import numpy as np, pandas as pd
from backtest_alts_slow import run_grid
from backtest_btc_mtf import WINDOW_START as T0
from backtest_btc_mtf_search import tstat
SYMS=["btcusdt","ethusdt","solusdt","bnbusdt","xrpusdt","dogeusdt","adausdt","avaxusdt","linkusdt","ltcusdt","dotusdt","bchusdt","trxusdt"]
T1=pd.Timestamp("2026-10-02"); yrs=(T1-T0).days/365.25
KEY=(40,4.0)
try: R=pickle.load(open("research_data/crypto/largecap_slow.pkl","rb"))
except Exception:
    R={s:run_grid(s) for s in SYMS}; pickle.dump(R,open("research_data/crypto/largecap_slow.pkl","wb"))

print(f"{'asset':8} | {'nTr':>3} {'Rtr':>7} | {'nTe':>3} {'win':>4} {'Rte':>7} {'t':>5} {'hold':>5} | $1000->(2% risk alone)")
pool=[]
for s in SYMS:
    tr=R[s][KEY]; trn=tr[tr.entry_time<T0]; te=tr[tr.entry_time>=T0].assign(sym=s); pool.append(te)
    eq=1000*np.prod(1+0.02*te.sort_values("exit_time").net_r)
    print(f"{s[:-4].upper():8} | {len(trn):>3} {trn.net_r.mean():>+7.3f} | {len(te):>3} {(te.net_r>0).mean():>4.0%} {te.net_r.mean():>+7.3f} {tstat(te.net_r):>5.1f} {te.hold_d.mean():>5.2f} | ${eq:,.0f}")
P=pd.concat(pool)
print(f"\nPOOLED all 13: {len(P)} trades (~{len(P)/yrs:.0f}/yr) win {(P.net_r>0).mean():.0%} avg net R {P.net_r.mean():+.3f} t={tstat(P.net_r):.1f}  mean hold {P.hold_d.mean():.2f}d")
pos=sum(1 for s in SYMS if P[P.sym==s].net_r.mean()>0); print(f"assets with positive avg R at this config: {pos}/13")
Q=P[~P.sym.isin(["btcusdt","ethusdt"])]
print(f"EXCLUDING BTC/ETH (the 11 new/other assets): {len(Q)} trades avg net R {Q.net_r.mean():+.3f} t={tstat(Q.net_r):.1f}, positive assets {sum(1 for s in SYMS[2:] if P[P.sym==s].net_r.mean()>0)}/11")

print("\nPOOLED avg net R by (ADX gate, RR) over all 13 assets, test window  [n assets positive]")
print(f"{'':6}"+"".join(f"{'RR'+str(r):>16}" for r in (2.0,3.0,4.0)))
for a in (20,25,30,35,40):
    row=f"ADX{a:<3} "
    for rr in (2.0,3.0,4.0):
        x=pd.concat([R[s][(a,rr)].query("entry_time>=@T0").assign(sym=s) for s in SYMS])
        npos=sum(1 for s in SYMS if x[x.sym==s].net_r.mean()>0)
        row+=f"{x.net_r.mean():>+9.3f} [{npos:>2}/13]"
    print(row)

def sim(tr,f,cap,start=1000.0):
    ev=[]; rows=list(tr.itertuples())
    for i,r in enumerate(rows):
        ev.append((r.entry_time,1,i)); ev.append((r.exit_time,0 if r.exit_time>r.entry_time else 2,i))
    ev.sort(key=lambda e:(e[0],e[1])); eq=start; peak=start; dd=0; size={}; openrisk=0.0; taken=0; skipped=0; mc=0
    for t,k,i in ev:
        if k==1:
            amt=f*eq
            if openrisk+amt>cap*eq: skipped+=1; continue
            size[i]=amt; openrisk+=amt; taken+=1; mc=max(mc,len(size))
        elif i in size:
            a=size.pop(i); openrisk-=a; eq+=a*rows[i].net_r; peak=max(peak,eq); dd=min(dd,eq/peak-1)
    return eq,dd,taken,skipped,mc
print("\nPORTFOLIO, one $1000 account, all 13 assets, total open-risk cap 6% (first-come):")
S=P.sort_values("entry_time")
for f in (0.01,0.02,0.03):
    e,d,tk,sk,mc=sim(S,f,0.06); print(f"  risk {f:.0%}/trade: $1000 -> ${e:,.0f}  CAGR {(e/1000)**(1/yrs)-1:+.1%}  maxDD {d:.0%}  trades taken {tk} skipped {sk} (max concurrent {mc})")
S2=S[S.sym.isin(["btcusdt","ethusdt"])]
e,d,tk,sk,mc=sim(S2,0.02,0.06); print(f"  for reference BTC+ETH only @2%: ${e:,.0f} maxDD {d:.0%}")
yr=S.assign(y=S.entry_time.dt.year).groupby("y").net_r.agg(["count","mean"]).round(3).T; print("\nby year (pooled):\n"+yr.to_string())
