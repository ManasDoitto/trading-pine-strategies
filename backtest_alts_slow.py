"""Slow v5.0 SHA-ADX config (1h base, 4h ADX gate, flip entry) on ETH and SOL perps.
Config (ADX>=40, RR4) was chosen on BTC pre-2021-10 data, so ETH/SOL are out-of-sample for it.
Frictionless lot sizing (fractional contracts) to isolate the edge; Delta ETH/SOL contract
sizes are not assumed."""
import sys, os, pickle, itertools
sys.path.insert(0, ".")
import numpy as np, pandas as pd
from trading_agents.core.signals_v50 import v50_frame
from backtest_btc_sha_adx_hybrid import btc_params
from backtest_btc_perp_trend import load_klines, DATA_DIR
from backtest_btc_mtf import htf_features, simulate_fast, WINDOW_START, COST_SIDE
from backtest_btc_mtf_search import tstat
import json

def load_sym(sym):
    k = load_klines(os.path.join(DATA_DIR, f"{sym}_perp_1h.json"))
    bars = k.rename(columns={"dt":"time"})[["time","open","high","low","close","volume"]].copy()
    bars["time"] = bars["time"].dt.tz_localize(None); bars = bars.reset_index(drop=True)
    fr = pd.DataFrame(json.load(open(os.path.join(DATA_DIR, f"{sym}_funding.json"))))
    t = pd.to_datetime(fr["fundingTime"], unit="ms", utc=True).dt.tz_localize(None).to_numpy()
    o = np.argsort(t)
    return bars, t[o], np.concatenate([[0.0], np.cumsum(fr["fundingRate"].astype(float).to_numpy()[o])])

def run_grid(sym):
    bars, ft, fc = load_sym(sym)
    df = v50_frame(bars, btc_params("flip", False, 30.0, 3.0))
    atr = df["atr"].to_numpy()
    gl = df["ok_l"].to_numpy() & df["near_ema9_l"].to_numpy() & (df["risk_l"].to_numpy()<=3*atr) & (atr>0)
    gs = df["ok_s"].to_numpy() & df["near_ema9_s"].to_numpy() & (df["risk_s"].to_numpy()<=3*atr) & (atr>0)
    adx = htf_features(bars, 240)["adx"].to_numpy()
    out = {}
    for a, rr in itertools.product([20,25,30,35,40],[2.0,3.0,4.0]):
        ok = adx >= a
        out[(a,rr)] = simulate_fast(df, gl&ok, gs&ok, rr, ft, fc)
    return out

def eq_curve(tr, f, start=100.0):
    eq, peak, dd = start, start, 0.0
    for r in tr.sort_values("exit_time").itertuples():
        eq *= (1 + f*r.net_r); peak = max(peak, eq); dd = min(dd, eq/peak-1)
    return eq, dd

if __name__ == "__main__":
    T0 = WINDOW_START; yrs = (pd.Timestamp("2026-10-02")-T0).days/365.25
    allres = {}
    for sym in ["ethusdt","solusdt"]:
        res = run_grid(sym); allres[sym] = res
        print(f"\n===== {sym.upper()} : 1h/4h flip grid (cost 0.07%/side + real funding) =====")
        print(f"{'adx':>4} {'rr':>4} | {'nTr':>4} {'Rtr':>7} | {'nTe':>4} {'Rte':>7} {'t':>5} {'win':>5} {'hold':>5}")
        for (a,rr), tr in res.items():
            trn, te = tr[tr.entry_time<T0], tr[tr.entry_time>=T0]
            print(f"{a:>4} {rr:>4} | {len(trn):>4} {trn.net_r.mean():>+7.3f} | {len(te):>4} {te.net_r.mean():>+7.3f} {tstat(te.net_r):>5.1f} {(te.net_r>0).mean():>5.0%} {te.hold_d.mean():>5.2f}")
    pickle.dump(allres, open("research_data/crypto/alts_slow.pkl","wb"))
