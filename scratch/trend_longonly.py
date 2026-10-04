import sys; sys.path.insert(0,".")
import numpy as np, pandas as pd
import backtest_trend_portfolio as T
mk,fund=T.load_all(); SPLIT=T.SPLIT
lo=lambda f: (lambda d: f(d).clip(lower=0))
RUL={"LO-TSMOM126":lo(T.RULES["TSMOM126"]),"LO-TSMOM252":lo(T.RULES["TSMOM252"]),"LO-MA50/200":lo(T.RULES["MA50/200"]),"LO-MA20/100":lo(T.RULES["MA20/100"]),
     "LO-DON50":lo(T.RULES["DON50"]),"LO-DON100":lo(T.RULES["DON100"]),"ALWAYS-LONG":lambda d: pd.Series(1.0,index=d.index)}
T.RULES.update(RUL); out={}; rows=[]
for k in RUL:
    p,P,Lv=T.run_rule(k,mk,fund); out[k]=p; a,b=T.stats(p[p.index<SPLIT]),T.stats(p[p.index>=SPLIT])
    rows.append(dict(rule=k,tr_sharpe=a["sharpe"],tr_cagr=a["cagr"],tr_mdd=a["mdd"],te_sharpe=b["sharpe"],te_cagr=b["cagr"],te_vol=b["vol"],te_mdd=b["mdd"]))
R=pd.DataFrame(rows).set_index("rule"); pd.set_option("display.width",200); print(R.round(3).to_string())
ens=pd.concat([out[k] for k in RUL if k!="ALWAYS-LONG"],axis=1).mean(axis=1).dropna(); a,b=T.stats(ens[ens.index<SPLIT]),T.stats(ens[ens.index>=SPLIT])
print(f"\nLONG-ONLY ENSEMBLE (6 rules): train Sharpe {a['sharpe']:.2f}  test Sharpe {b['sharpe']:.2f}  test CAGR {b['cagr']:.1%} vol {b['vol']:.1%} maxDD {b['mdd']:.0%}")
te=ens[ens.index>=SPLIT]; print("halves Sharpe:",round(T.stats(te[te.index<'2021-01-01'])['sharpe'],2),round(T.stats(te[te.index>='2021-01-01'])['sharpe'],2))
yr=ens.groupby(ens.index.year).apply(lambda x:(1+x).prod()-1)*100; al=out["ALWAYS-LONG"].groupby(out["ALWAYS-LONG"].index.year).apply(lambda x:(1+x).prod()-1)*100
print("\nyearly % (long-only ensemble vs always-long):"); print(pd.DataFrame({"LO-ensemble":yr,"always-long":al}).loc[2008:].round(1).T.to_string())
p,P,Lv=T.run_rule("LO-TSMOM252",mk,fund); n=Lv.notna().sum(axis=1).replace(0,np.nan); c=P.where(Lv.notna(),0.0).div(n,axis=0); c=c[c.index>=SPLIT]; yrs=(c.index[-1]-c.index[0]).days/365.25
cm=(c.sum()/yrs*100); print("\nLO-TSMOM252 test contribution %/yr by class:",cm.groupby(lambda k:T.CLASS[k]).sum().round(2).to_dict(),"| positive markets",(cm>0).sum(),"/15")
print("leave-class-out test Sharpe:",{cl:round(T.stats((lambda p:p[p.index>=SPLIT])(T.run_rule("LO-TSMOM252",mk,fund,skip=tuple(k for k,v in T.CLASS.items() if v==cl))[0]))["sharpe"],2) for cl in sorted(set(T.CLASS.values()))})
trv=ens[ens.index<SPLIT].std()*np.sqrt(252)
print("\nLONG-ONLY ENSEMBLE, $1000 from 2015-01-01 (leverage scaled by train vol; financing ignored):")
for tgt in (0.08,0.12,0.16):
    k=tgt/trv; r=te*k; eq=(1+r).cumprod(); s=T.stats(r); print(f"  target {tgt:.0%} vol: leverage x{k:.2f}  final ${1000*eq.iloc[-1]:,.0f}  CAGR {s['cagr']:+.1%}  vol {s['vol']:.1%}  maxDD {s['mdd']:.0%}  Sharpe {s['sharpe']:.2f}")
al_te=out["ALWAYS-LONG"][out["ALWAYS-LONG"].index>=SPLIT]; eq=(1+al_te).cumprod(); print(f"  (always-long vol-targeted: ${1000*eq.iloc[-1]:,.0f}, maxDD {T.stats(al_te)['mdd']:.0%})")
