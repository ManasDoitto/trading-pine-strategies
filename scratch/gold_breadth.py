import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd
import backtest_gold as G, backtest_btc_mtf as M
from backtest_btc_mtf_search import tstat
M.COST_SIDE=0.0005
SPLIT=pd.Timestamp("2013-01-01"); END=pd.Timestamp("2026-10-02"); yrs=(END-SPLIT).days/365.25
assets={"GOLD":"research_data/gold/gc_1d.pkl"}
for n in ["si","hg","cl","ng","pl","es","zn","zc"]: assets[n.upper()]=f"research_data/gold/fut_{n}_1d.pkl"
R={}
for name,p in assets.items():
    d=pd.read_pickle(p); d["time"]=pd.to_datetime(d["time"]); d=d[(d.close>0)&(d.open>0)&(d.high>0)&(d.low>0)].reset_index(drop=True)
    R[name]=G.run_grid(d,10080)
KEY=("breakout",25,4.0)
print(f"{'asset':6} | {'nTr':>3} {'Rtr':>7} | {'nTe':>3} {'win':>4} {'Rte':>7} {'t':>5} {'hold':>5}")
pool=[]
for n,res in R.items():
    tr=res[KEY]; a=tr[tr.entry_time<SPLIT]; b=tr[tr.entry_time>=SPLIT].assign(a=n); pool.append(b)
    print(f"{n:6} | {len(a):>3} {a.net_r.mean():>+7.3f} | {len(b):>3} {(b.net_r>0).mean():>4.0%} {b.net_r.mean():>+7.3f} {tstat(b.net_r):>5.1f} {b.hold_d.mean():>5.0f}")
P=pd.concat(pool); print(f"\nPOOLED 9 markets @{KEY}: {len(P)} trades, avg R {P.net_r.mean():+.3f}, t={tstat(P.net_r):.1f}, positive markets {sum(1 for n in R if P[P.a==n].net_r.mean()>0)}/9")
Q=P[P.a!="GOLD"]; print(f"EXCLUDING GOLD: {len(Q)} trades avg R {Q.net_r.mean():+.3f} t={tstat(Q.net_r):.1f}, positive {sum(1 for n in R if n!='GOLD' and P[P.a==n].net_r.mean()>0)}/8")
print("\nPooled (9 markets) test avg R by config, [markets positive]:")
for trig in ("flip","breakout"):
    for a in (20,25,30,35):
        row=f"{trig:8} ADX{a}: "
        for rr in (2.0,3.0,4.0):
            x=pd.concat([R[n][(trig,a,rr)].query("entry_time>=@SPLIT").assign(a=n) for n in R]); npos=sum(1 for n in R if x[x.a==n].net_r.mean()>0)
            row+=f"RR{rr:.0f} {x.net_r.mean():>+6.2f} [{npos}/9]   "
        print(row)
g=R["GOLD"][KEY]; g=g[g.entry_time>=SPLIT]; g["y"]=g.entry_time.dt.year
print("\nGOLD selected config trades by year (test):"); print(g.groupby("y").net_r.agg(["count","sum"]).round(2).T.to_string())
print("share of gold's total R earned in 2024-2026:", round(g[g.y>=2024].net_r.sum()/g.net_r.sum(),2))
print("\nGOLD trades:"); print(g[["entry_time","side","hold_d","net_r"]].round(2).to_string(index=False))
