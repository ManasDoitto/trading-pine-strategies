import sys; sys.path.insert(0,'.')
import pickle, numpy as np, pandas as pd
from backtest_btc_mtf_search import tstat
btc = pickle.load(open("research_data/crypto/slow_family.pkl","rb"))
alts = pickle.load(open("research_data/crypto/alts_slow.pkl","rb"))
T0, T1 = pd.Timestamp("2021-10-04"), pd.Timestamp("2026-10-02"); yrs=(T1-T0).days/365.25
KEY=(40,4.0)
sets = {"BTC": btc[KEY], "ETH": alts["ethusdt"][KEY], "SOL": alts["solusdt"][KEY]}
for k,v in sets.items(): sets[k]=v[v.entry_time>=T0].assign(sym=k)

def sim(trades, f, start=100.0):
    ev=[]
    for i,r in enumerate(trades.itertuples()):
        ev.append((r.entry_time,1,i)); ev.append((r.exit_time,0 if r.exit_time>r.entry_time else 2,i))
    ev.sort(key=lambda x:(x[0],x[1]))   # exits before entries at same time
    eq=start; peak=start; dd=0; size={}; maxconc=0; open_n=0; yearly={}
    rs=list(trades.itertuples())
    for t,kind,i in ev:
        if kind==1:
            size[i]=f*eq; open_n+=1; maxconc=max(maxconc,open_n)
        else:
            eq+=size[i]*rs[i].net_r; open_n-=1; peak=max(peak,eq); dd=min(dd,eq/peak-1)
            yearly[t.year]=eq
    return eq,dd,maxconc

def show(name, tr):
    tr=tr.sort_values("entry_time"); n=len(tr)
    print(f"{name}: {n} trades (~{n/yrs:.0f}/yr)  win {(tr.net_r>0).mean():.0%}  avg net R {tr.net_r.mean():+.3f}  t={tstat(tr.net_r):.1f}  mean hold {tr.hold_d.mean():.2f}d")
    for f in (0.01,0.02,0.03):
        e,d,c=sim(tr,f); print(f"   risk {f:.0%}/trade/trade: $100 -> ${e:,.0f}  CAGR {(e/100)**(1/yrs)-1:+.1%}  maxDD {d:.0%}  max concurrent positions {c}")
for k in sets: show(k, sets[k])
print()
show("BTC+ETH", pd.concat([sets["BTC"],sets["ETH"]]))
show("BTC+ETH+SOL", pd.concat(sets.values()))
# overlap of BTC & ETH signals
b,e=sets["BTC"],sets["ETH"]
ov=sum(((e.entry_time<=r.exit_time)&(e.exit_time>=r.entry_time)).any() for r in b.itertuples())
print(f"\nBTC trades overlapping an ETH trade in time: {ov}/{len(b)}")
# per-year R for BTC+ETH
x=pd.concat([sets["BTC"],sets["ETH"]]); x["y"]=x.entry_time.dt.year
print(x.groupby("y").net_r.agg(["count","mean"]).round(3).T)
# buy & hold ETH
import json,os
from backtest_btc_perp_trend import load_klines, DATA_DIR
k=load_klines(os.path.join(DATA_DIR,"ethusdt_perp_1h.json")); k["t"]=pd.to_datetime(k.dt).dt.tz_localize(None)
w=k[k.t>=T0]; print(f"\nETH buy&hold: $100 -> ${100*w.close.iloc[-1]/w.close.iloc[0]:,.0f}  maxDD {(w.close/w.close.cummax()-1).min():.0%}")
