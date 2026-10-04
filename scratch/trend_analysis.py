import sys; sys.path.insert(0,".")
import pickle, numpy as np, pandas as pd
import backtest_trend_portfolio as T
mk, fund = T.load_all()
rets = pickle.load(open("research_data/trend/portfolio_returns.pkl","rb"))
SPLIT=T.SPLIT
ens = pd.concat(rets.values(),axis=1).mean(axis=1).dropna()                       # equal-weight ensemble of all 8 rules
tsm = rets["TSMOM252"]
# long-only benchmark: same vol targeting, signal always +1
T.RULES["LONG"] = lambda d: pd.Series(1.0, index=d.index); bh,_,_ = T.run_rule("LONG", mk, fund)
T.RULES["TSMOM252_LONGONLY"] = lambda d: np.sign(d["close"] / d["close"].shift(252) - 1).clip(lower=0).fillna(0); tlo,_,_ = T.run_rule("TSMOM252_LONGONLY", mk, fund)
spy = mk["spy"].set_index("time")["close"].pct_change()
def row(name, r):
    te=r[r.index>=SPLIT]; tr=r[r.index<SPLIT]; a,b=T.stats(tr),T.stats(te)
    return dict(name=name, tr_sharpe=a["sharpe"], te_sharpe=b["sharpe"], te_cagr=b["cagr"], te_vol=b["vol"], te_mdd=b["mdd"])
R=pd.DataFrame([row("TSMOM252 (train-chosen)",tsm),row("ENSEMBLE of all 8",ens),row("TSMOM252 LONG-ONLY (no shorts)",tlo),row("Always-long vol-targeted (same 15 mkts)",bh),row("SPY buy&hold",spy.dropna())]).set_index("name")
pd.set_option("display.width",200); print(R.round(3).to_string())
te_e=ens[ens.index>=SPLIT]
print("\nEnsemble, test halves:", {k:round(T.stats(v)["sharpe"],2) for k,v in {"2015-2020":te_e[te_e.index<'2021-01-01'],"2021-2026":te_e[te_e.index>='2021-01-01']}.items()})
print("\nCalendar-year returns (natural ~9% vol):")
y=pd.DataFrame({"TSMOM252":tsm.groupby(tsm.index.year).apply(lambda x:(1+x).prod()-1),"ENSEMBLE":ens.groupby(ens.index.year).apply(lambda x:(1+x).prod()-1),"LONGONLY":bh.groupby(bh.index.year).apply(lambda x:(1+x).prod()-1)})
print((y[y.index>=2008]*100).round(1).T.to_string())
# per-market and per-class contribution for the ensemble's main member rules (TSMOM252) in test
port,P,Lv = T.run_rule("TSMOM252", mk, fund)
n_live = Lv.notna().sum(axis=1).replace(0,np.nan); contrib = (P.where(Lv.notna(),0.0).div(n_live,axis=0))
ct = contrib[contrib.index>=SPLIT]
print("\nTSMOM252 test: annual return contribution by market (% of portfolio per year):")
yrs=(ct.index[-1]-ct.index[0]).days/365.25
cm=(ct.sum()/yrs*100).round(2); print(cm.sort_values(ascending=False).to_string())
cc=cm.groupby(lambda k:T.CLASS[k]).sum().round(2); print("\nby class:",cc.to_dict()); print("markets with positive contribution:",(cm>0).sum(),"/",len(cm))
# leave-one-class-out Sharpe (test)
print("\nLeave-one-class-out (TSMOM252 test Sharpe):")
for cl in sorted(set(T.CLASS.values())):
    skip=tuple(k for k,v in T.CLASS.items() if v==cl); p,_,_=T.run_rule("TSMOM252",mk,fund,skip=skip); print(f"  without {cl:8}: {T.stats(p[p.index>=SPLIT])['sharpe']:.2f}")
# scaling + dollars: scale ensemble to 10% / 15% vol using TRAIN vol only
trv=ens[ens.index<SPLIT].std()*np.sqrt(252)
print("\nENSEMBLE scaled with train-vol, $1000 invested 2015-01-01 -> 2026-10-01 (frictionless leverage/financing):")
for tgt in (0.10,0.15,0.20):
    k=tgt/trv; r=te_e*k; eq=(1+r).cumprod(); s=T.stats(r)
    print(f"  target {tgt:.0%}: leverage x{k:.2f}  final ${1000*eq.iloc[-1]:,.0f}  CAGR {s['cagr']:+.1%}  vol {s['vol']:.1%}  maxDD {s['mdd']:.0%}  Sharpe {s['sharpe']:.2f}")
