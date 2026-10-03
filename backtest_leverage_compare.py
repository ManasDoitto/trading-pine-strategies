"""Leverage comparison for the slow config (1h/4h ADX>=40 RR4) on BTC+ETH, $1000 start.
Framing A  fixed-risk sizing (what we've reported): leverage is only a CAP on notional.
Framing B  fixed-leverage sizing: notional = L x equity on every trade (leverage IS the position size).
Liquidation is modelled with each trade's real intratrade adverse excursion from 1h bars:
  liquidated if adverse move >= 1/L - MMR (MMR=0.5% assumed maintenance margin), loss = equity*(1 - MMR*L).
Same costs as before: 0.07%/side + real funding, scaled by notional."""
import sys, os, pickle, json
sys.path.insert(0,'.')
import numpy as np, pandas as pd
from backtest_btc_perp_trend import load_klines, DATA_DIR
from backtest_btc_mtf import COST_SIDE, WINDOW_START
MMR = 0.005
T0 = WINDOW_START; T1 = pd.Timestamp("2026-10-02"); yrs=(T1-T0).days/365.25
btc = pickle.load(open("research_data/crypto/slow_family.pkl","rb"))[(40,4.0)]
eth = pickle.load(open("research_data/crypto/alts_slow.pkl","rb"))["ethusdt"][(40,4.0)]

def add_mae(tr, file):
    k = load_klines(os.path.join(DATA_DIR,file)); k["t"]=pd.to_datetime(k.dt).dt.tz_localize(None)
    t=k.t.to_numpy(); lo=k.low.to_numpy(); hi=k.high.to_numpy(); out=[]
    for r in tr.itertuples():
        a=np.searchsorted(t,np.datetime64(r.entry_time)); b=np.searchsorted(t,np.datetime64(r.exit_time),side="right")
        out.append((r.entry-lo[a:b].min())/r.entry if r.side==1 else (hi[a:b].max()-r.entry)/r.entry)
    tr=tr.copy(); tr["mae"]=np.maximum(out,0); return tr
def prep(tr,file):
    tr=tr[tr.entry_time>=T0]; tr=add_mae(tr,file)
    tr["ret"]=tr.side*(tr.exit/tr.entry-1)-2*COST_SIDE-tr.side*tr.fund
    tr["stop_pct"]=(tr.entry-tr.sl).abs()/tr.entry
    return tr
B=prep(btc,"btcusdt_perp_1h.json").assign(sym="BTC"); E=prep(eth,"ethusdt_perp_1h.json").assign(sym="ETH")
P=pd.concat([B,E]).sort_values("entry_time").reset_index(drop=True)
print("stop distance % of price (BTC+ETH):", P.stop_pct.describe()[["25%","50%","75%","max"]].round(4).to_dict())

def sim(tr, mode, x, start=1000.0):
    """mode 'risk': x = risk fraction, leverage cap 100. mode 'lev': x = leverage multiple."""
    ev=[]
    for i,r in enumerate(tr.itertuples()):
        ev.append((r.entry_time,1,i)); ev.append((r.exit_time,0 if r.exit_time>r.entry_time else 2,i))
    ev.sort(key=lambda e:(e[0],e[1])); rows=list(tr.itertuples())
    eq=start; peak=start; dd=0; notional={}; used=0.0; liqs=0; n=0; ruin=False; minlev=[]
    for t,kind,i in ev:
        r=rows[i]
        if kind==1:
            cap = (x if mode=="lev" else 100.0)*eq
            want = (x*eq) if mode=="lev" else (x*eq/max(r.stop_pct,1e-6))
            nt = max(0.0, min(want, cap-used)); notional[i]=nt; used+=nt
        else:
            nt=notional.pop(i); used-=nt
            if nt<=0: continue
            L_eff = nt/max(eq,1e-9)
            if r.mae >= 1.0/max(L_eff,1e-9) - MMR and L_eff>1:      # liquidated first
                eq -= eq*min(1.0,(1-MMR*L_eff)) if mode=="lev" else nt*(1/L_eff-MMR)*0+eq*min(1.0,(1-MMR*L_eff)); liqs+=1
            else:
                eq += nt*r.ret
            n+=1; peak=max(peak,eq); dd=min(dd,eq/peak-1)
            if eq<=5: ruin=True; eq=max(eq,0); break
    return eq,dd,liqs,n,ruin

print("\n=== A) FIXED-RISK sizing, BTC+ETH, $1000: leverage only caps notional (cap shown) ===")
for risk in (0.02,0.05,0.10):
    e,d,l,n,ru=sim(P,"risk",risk); print(f"risk {risk:.0%}/trade -> ${e:,.0f}  maxDD {d:.0%}  liquidations {l}  trades {n}{'  RUINED' if ru else ''}")
# leverage actually needed at 2% risk
need=0.02/P.stop_pct; print(f"leverage needed to risk 2% per trade: median {need.median():.1f}x  90th pct {need.quantile(.9):.1f}x  max {need.max():.1f}x  (trades needing >3x: {(need>3).sum()}/{len(P)})")

print("\n=== B) FIXED-LEVERAGE sizing (notional = L x equity every trade) ===")
print(f"{'L':>4} {'avg risk/trade':>14} | {'BTC+ETH $1000->':>16} {'maxDD':>6} {'liq':>4} | {'BTC only':>9} {'ETH only':>9}")
for L in (1,2,3,5,7,10,15,20):
    e,d,l,n,ru=sim(P,"lev",L); eb,_,_,_,rb=sim(B.reset_index(drop=True),"lev",L); ee,_,_,_,re=sim(E.reset_index(drop=True),"lev",L)
    print(f"{L:>3}x {L*P.stop_pct.mean():>13.0%} | ${e:>14,.0f} {d:>6.0%} {l:>4} | ${eb:>8,.0f} ${ee:>8,.0f}{'  <-RUIN' if ru else ''}")

print("\n=== C) Bootstrap (resample the 113 trades, 3000 runs, sequential, $1000) ===")
rng=np.random.default_rng(7); arr=P[["ret","mae","stop_pct"]].to_numpy()
for L in (1,2,3,5,10,20):
    fin=[]
    for _ in range(3000):
        eq=1000.0
        for ret,mae,sp in arr[rng.integers(0,len(arr),len(arr))]:
            if L>1 and mae>=1/L-MMR: eq*=max(0,1-(1-MMR*L))   # liquidated
            else: eq*=1+L*ret
            if eq<5: eq=0; break
        fin.append(eq)
    fin=np.array(fin); print(f"{L:>3}x: median ${np.median(fin):>7,.0f}  5th pct ${np.percentile(fin,5):>6,.0f}  95th pct ${np.percentile(fin,95):>7,.0f}  P(end<$1000) {np.mean(fin<1000):.0%}  P(lose >50%) {np.mean(fin<500):.0%}  P(wiped <$50) {np.mean(fin<50):.0%}")
