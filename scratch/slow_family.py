import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd, itertools, pickle
from trading_agents.core.signals_v50 import v50_frame
from backtest_btc_sha_adx_hybrid import btc_params
from backtest_btc_mtf import *
from backtest_btc_mtf_search import tstat

b15 = load_15m(); ft, fc = load_funding()
bars = resample(b15, 60)
df = v50_frame(bars, btc_params("flip", False, 30.0, 3.0))
atr = df["atr"].to_numpy()
gl0 = df["ok_l"].to_numpy() & df["near_ema9_l"].to_numpy() & (df["risk_l"].to_numpy()<=3*atr) & (atr>0)
gs0 = df["ok_s"].to_numpy() & df["near_ema9_s"].to_numpy() & (df["risk_s"].to_numpy()<=3*atr) & (atr>0)
adx = htf_features(bars, 240)["adx"].to_numpy()
res = {}
print("1h base / 4h ADX gate, flip  (cost: 0.07%/side + real funding)")
print(f"{'adx':>4} {'rr':>4} | {'nTr':>4} {'Rtr':>7} | {'nTe':>4} {'Rte':>7} {'t':>5} {'win':>5} {'hold':>5}")
for a, rr in itertools.product([20,25,30,35,40],[2.0,3.0,4.0]):
    ok = adx>=a
    tr = simulate_fast(df, gl0&ok, gs0&ok, rr, ft, fc)
    res[(a,rr)] = tr
    trn, te = tr[tr.entry_time<WINDOW_START], tr[tr.entry_time>=WINDOW_START]
    print(f"{a:>4} {rr:>4} | {len(trn):>4} {trn.net_r.mean():>+7.3f} | {len(te):>4} {te.net_r.mean():>+7.3f} {tstat(te.net_r):>5.1f} {(te.net_r>0).mean():>5.0%} {te.hold_d.mean():>5.2f}")
pickle.dump(res, open("research_data/crypto/slow_family.pkl","wb"))
