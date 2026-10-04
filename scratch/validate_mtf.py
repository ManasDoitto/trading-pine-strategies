import sys; sys.path.insert(0,'.')
import numpy as np, pandas as pd
from trading_agents.core.signals_v50 import v50_frame, simulate
from backtest_btc_sha_adx_hybrid import btc_params
from backtest_btc_mtf import *

b15 = load_15m(); b1h = resample(b15, 60)
p = btc_params("flip", False, 30.0, 4.0)
df = v50_frame(b1h, p)
hf = htf_features(b1h, 240)
df["adx15_prev"] = hf["adx"].values
df["adx_ok"] = df["adx15_prev"] >= 30.0
# production simulator
trades, _, _ = simulate(df, p, start=250)
prod = pd.DataFrame(trades)
# fast simulator with the same gating simulate() applies at arming time
atr = df["atr"].to_numpy()
gate_l = df["ok_l"].to_numpy() & df["adx_ok"].to_numpy() & df["near_ema9_l"].to_numpy() & (df["risk_l"].to_numpy() <= 3.0*atr) & (atr>0)
gate_s = df["ok_s"].to_numpy() & df["adx_ok"].to_numpy() & df["near_ema9_s"].to_numpy() & (df["risk_s"].to_numpy() <= 3.0*atr) & (atr>0)
ft, fc = load_funding()
fast = simulate_fast(df, gate_l, gate_s, 4.0, ft, fc)
print("production trades:", len(prod), " fast trades:", len(fast))
m = pd.merge(prod[["entry_time","side","result"]], fast[["entry_time","side"]].assign(f=1), on=["entry_time"], how="outer", indicator=True)
print(m["_merge"].value_counts())
print("TP share prod:", (prod.result=="TP").mean().round(3), " fast TP share:", (fast.exit.sub(fast.entry).mul(fast.side)>0).mean().round(3))
print("fast avg net R:", fast.net_r.mean().round(3), " mean hold d:", fast.hold_d.mean().round(2))
