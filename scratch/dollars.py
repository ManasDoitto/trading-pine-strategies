import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd, pickle
from backtest_btc_mtf import *
res = pickle.load(open("research_data/crypto/slow_family.pkl","rb"))
fast = pickle.load(open("research_data/crypto/mtf_results.pkl","rb"))
T0, T1 = pd.Timestamp("2021-10-04"), pd.Timestamp("2026-10-02")
yrs = (T1-T0).days/365.25

d1 = load_klines(os.path.join(DATA_DIR,"btcusdt_perp_1d.json")) if False else None
import json
from backtest_btc_perp_trend import load_klines
d = load_klines(os.path.join(DATA_DIR,"btcusdt_perp_1d.json"))
d["t"]=pd.to_datetime(d["dt"]).dt.tz_localize(None)
p0 = d[d.t>=T0].iloc[0].close; p1 = d.iloc[-1].close
print(f"BUY & HOLD BTC: $100 -> ${100*p1/p0:,.0f}  (BTC {p0:,.0f} -> {p1:,.0f}); max drawdown in window ~{(d[d.t>=T0].close/d[d.t>=T0].close.cummax()-1).min():.0%}")
print()
cands = {
 "SLOW  1h/4h flip ADX>=40 RR4 (best on TRAIN data)": res[(40,4.0)],
 "SLOW  1h/4h flip ADX>=40 RR3": res[(40,3.0)],
 "SLOW  1h/4h flip ADX>=30 RR4 (last round's pick, in-sample)": res[(30,4.0)],
 "FAST  15m/4h flip ADX>=35 RR3 +EMA gate (best TRAIN fast)": fast[(15,240,'flip',35,3.0,1)],
 "FAST  30m/4h flip ADX>=30 RR3 +EMA gate": fast[(30,240,'flip',30,3.0,1)],
}
for name, tr in cands.items():
    te = tr[(tr.entry_time>=T0)]
    print(f"{name}\n   trades in 5y: {len(te)} (~{len(te)/yrs:.0f}/yr)  win {(te.net_r>0).mean():.0%}  median hold {te.hold_d.median():.2f}d  mean {te.hold_d.mean():.2f}d  avg net R {te.net_r.mean():+.3f}")
    for f in (0.01,0.02,0.03,0.05):
        r = dollar_sim(te, 100.0, f, T0, T1)
        cagr = (r['final']/100)**(1/yrs)-1 if r['final']>0 else -1
        print(f"   risk {f:.0%}/trade: $100 -> ${r['final']:>9,.2f}   CAGR {cagr:+6.1%}   maxDD {r['max_dd']:.0%}   executed {r['taken']} skipped {r['skipped']}")
    # bootstrap of trade sequence (2% risk), ignores lot rounding
    rng = np.random.default_rng(1); x = te.net_r.to_numpy(); n=len(x)
    fin=[]
    for _ in range(5000):
        s = rng.choice(x, n, replace=True); fin.append(100*np.prod(1+0.02*s))
    fin=np.array(fin)
    print(f"   bootstrap @2% (same #trades, resampled): median ${np.median(fin):,.0f}  5th pct ${np.percentile(fin,5):,.0f}  95th pct ${np.percentile(fin,95):,.0f}  P(end < $100) {np.mean(fin<100):.0%}")
    print()
