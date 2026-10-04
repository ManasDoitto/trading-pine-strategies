import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import backtest_india_trend as B
pd.set_option("display.width",220)
mk,_=B.load_markets(False); mkc,fund=B.load_markets(True)
ens,W,dW=B.run(mk,{}, "M",0.055); al,_,_=B.run(mk,{}, "M",0.055,always_long=True)
nb=B.clean_spikes(pd.read_pickle("research_data/trend/in_niftybees.pkl"),"nb"); nbr=pd.Series(nb.close.pct_change().fillna(0).to_numpy(),index=pd.DatetimeIndex(nb.time)); nbr=nbr[nbr.index>=ens.index[0]]
print("\n== per-rule (INDIA ETFs only, monthly, cash 5.5%) ==")
rows=[]
for rule in B.RULE_NAMES+["ENSEMBLE(5)"]:
    B.RULE_NAMES_BAK=B.RULE_NAMES; B.RULE_NAMES=[rule] if rule!="ENSEMBLE(5)" else ["TSMOM126","TSMOM252","MA50/200","MA20/100","DON100"]
    r,_,_=B.run(mk,{}, "M",0.055); B.RULE_NAMES=B.RULE_NAMES_BAK
    a,b=B.stats(r[r.index<=B.TRAIN_END]),B.stats(r[r.index>=B.TEST_START]); rows.append(dict(rule=rule,tr_cagr=a["cagr"],tr_sharpe=a["sharpe"],te_cagr=b["cagr"],te_sharpe=b["sharpe"],te_mdd=b["mdd"]))
B.RULE_NAMES=["TSMOM126","TSMOM252","MA50/200","MA20/100","DON100"]
print(pd.DataFrame(rows).set_index("rule").round(3).to_string())
yr=lambda r:(r.groupby(r.index.year).apply(lambda x:(1+x).prod()-1)*100).round(1)
print("\n== calendar-year % returns =="); print(pd.DataFrame({"trend(monthly)":yr(ens),"always-long EW":yr(al),"NIFTYBEES":yr(nbr)}).T.to_string())
# turnover / switching
chg=(dW.sum(axis=1)[dW.index>=ens.index[0]]); m=chg.groupby([chg.index.year,chg.index.month]).sum(); yrs=(ens.index[-1]-ens.index[0]).days/365.25
print(f"\nturnover: avg one-way {chg.sum()/yrs*100:.0f}% of portfolio per year; months with a >5% allocation change: {(m>0.05).sum()} of {len(m)} ({(m>0.05).mean():.0%})")
# cost sensitivity: double equity-ETF costs
orig=dict(B.COSTS); B.COSTS.update({k:v*2 for k,v in orig.items()}); r2,_,_=B.run(mk,{}, "M",0.055); B.COSTS.update(orig)
print(f"cost x2 (0.3%/side equity ETFs): test CAGR {B.stats(r2[r2.index>=B.TEST_START])['cagr']:.1%} vs base {B.stats(ens[ens.index>=B.TEST_START])['cagr']:.1%}")
te=ens[ens.index>=B.TEST_START]; tea=al[al.index>=B.TEST_START]; yrs_t=(te.index[-1]-te.index[0]).days/365.25
print(f"rough tax drag if every year's gain taxed at 20% (STCG-like upper bound): trend CAGR {B.stats(te)['cagr']:.1%} -> ~{B.stats(te)['cagr']*0.8:.1%};  buy&hold style (LTCG 12.5%, deferred) always-long {B.stats(tea)['cagr']:.1%} -> ~{B.stats(tea)['cagr']*0.875:.1%}")
print("\nRs 1,00,000 invested 2017-01-01 -> 2026-10 (before tax):")
for n,r in (("trend monthly",te),("always-long EW",tea),("NIFTYBEES",nbr[nbr.index>=B.TEST_START])): print(f"  {n:16} Rs {100000*(1+r).prod():,.0f}")
# current signals
print("\n== CURRENT trend exposure per ETF (as of last bar; monthly rule uses last month-end) ==")
last=W.iloc[-1]; n_live=int((last.index.isin(mk)).sum())
sig={}
for k,d in mk.items():
    s=B.long_signal(d); sig[k]=(float(s.iloc[-1]), d.time.iloc[-1].date())
for k,(v,dt) in sig.items(): print(f"  {k:11} today's signal {v:.2f}  (data to {dt})")
print("  current monthly-rule slices (weight of total):",{k:round(float(v),3) for k,v in last.items()}, " cash:", round(1-float(last.sum()),3))
