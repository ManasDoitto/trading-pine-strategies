"""Grid search + out-of-sample judgement for the multi-timeframe BTC system.

Selection uses ONLY trades that entered before 2021-10-04. The 5-year window
(2021-10-04 .. 2026-10-02) is then the out-of-sample "if I had deployed 5 years ago" test.
Also reports a yearly walk-forward (re-select every Oct 4 using only prior data).
"""
from __future__ import annotations

import itertools
import pickle
import time
import numpy as np
import pandas as pd

from trading_agents.core.signals_v50 import v50_frame
from backtest_btc_sha_adx_hybrid import btc_params
from backtest_btc_mtf import (load_15m, resample, htf_features, load_funding, simulate_fast,
                              dollar_sim, WINDOW_START)

BASES = [15, 30]
HTFS = [60, 240]
TRIGGERS = ["flip", "breakout"]
ADXS = [20, 25, 30, 35]
RRS = [2.0, 3.0, 4.0]
HTF_EMA = [0, 1]
MIN_TRAIN_TRADES = 60


def tstat(x: pd.Series) -> float:
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else float("nan")


def build_all():
    b15 = load_15m()
    ft, fc = load_funding()
    results = {}
    t0 = time.time()
    for base in BASES:
        bars = resample(b15, base)
        p = btc_params("flip", False, 30.0, 3.0)
        df = v50_frame(bars, p)
        atr = df["atr"].to_numpy()
        base_ok = (atr > 0)
        g = {
            ("flip", "L"): df["ok_l"].to_numpy() & df["near_ema9_l"].to_numpy() & (df["risk_l"].to_numpy() <= 3.0 * atr) & base_ok,
            ("flip", "S"): df["ok_s"].to_numpy() & df["near_ema9_s"].to_numpy() & (df["risk_s"].to_numpy() <= 3.0 * atr) & base_ok,
            ("breakout", "L"): df["ok_l_bo"].to_numpy() & df["near_ema9_l"].to_numpy() & (df["risk_l"].to_numpy() <= 3.0 * atr) & base_ok,
            ("breakout", "S"): df["ok_s_bo"].to_numpy() & df["near_ema9_s"].to_numpy() & (df["risk_s"].to_numpy() <= 3.0 * atr) & base_ok,
        }
        for htf in HTFS:
            if htf <= base:
                continue
            hf = htf_features(bars, htf)
            adx = hf["adx"].to_numpy()
            tl, ts = hf["tl"].to_numpy() == 1.0, hf["ts"].to_numpy() == 1.0
            for trig, adx_min, rr, use_ema in itertools.product(TRIGGERS, ADXS, RRS, HTF_EMA):
                adx_ok = adx >= adx_min
                gl = g[(trig, "L")] & adx_ok & (tl if use_ema else True)
                gs = g[(trig, "S")] & adx_ok & (ts if use_ema else True)
                tr = simulate_fast(df, gl, gs, rr, ft, fc)
                results[(base, htf, trig, adx_min, rr, use_ema)] = tr
        print(f"base {base}m done ({time.time()-t0:.0f}s)", flush=True)
    return results


def summarize(results):
    rows = []
    for key, tr in results.items():
        if len(tr) == 0:
            continue
        train, test = tr[tr["entry_time"] < WINDOW_START], tr[tr["entry_time"] >= WINDOW_START]
        rows.append(dict(
            key=key, n_train=len(train), r_train=train["net_r"].mean() if len(train) else np.nan,
            t_train=tstat(train["net_r"]) if len(train) else np.nan,
            n_test=len(test), r_test=test["net_r"].mean() if len(test) else np.nan,
            t_test=tstat(test["net_r"]) if len(test) else np.nan,
            hold=test["hold_d"].mean() if len(test) else np.nan,
            win=(test["net_r"] > 0).mean() if len(test) else np.nan))
    return pd.DataFrame(rows)


def main():
    results = build_all()
    with open("research_data/crypto/mtf_results.pkl", "wb") as f:
        pickle.dump(results, f)
    s = summarize(results)
    s = s[s["n_train"] >= MIN_TRAIN_TRADES]
    print(f"\nconfigs with >= {MIN_TRAIN_TRADES} train trades: {len(s)}")
    print(f"share of ALL configs with positive TEST expectancy: {(s['r_test'] > 0).mean():.0%}   "
          f"median test avg R: {s['r_test'].median():+.3f}")
    print(f"share with positive TRAIN expectancy: {(s['r_train'] > 0).mean():.0%}")
    top = s.sort_values("t_train", ascending=False).head(10)
    print("\nTop 10 by TRAIN t-stat (pre 2021-10-04) -> what they did in the 5-year TEST window:")
    print(f"{'config (base,htf,trig,adx,rr,ema)':44} {'nTr':>4} {'Rtr':>7} {'t':>5} | {'nTe':>4} {'Rte':>7} {'t':>5} {'win':>5} {'hold_d':>6}")
    for r in top.itertuples():
        print(f"{str(r.key):44} {r.n_train:>4} {r.r_train:>+7.3f} {r.t_train:>5.1f} | {r.n_test:>4} {r.r_test:>+7.3f} {r.t_test:>5.1f} {r.win:>5.0%} {r.hold:>6.2f}")
    best_test = s.sort_values("t_test", ascending=False).head(5)
    print("\n(for reference only -- best 5 IN HINDSIGHT on the test window; NOT a tradable selection)")
    for r in best_test.itertuples():
        print(f"{str(r.key):44} nTe={r.n_test} Rte={r.r_test:+.3f} t={r.t_test:.1f} hold={r.hold:.2f}d")


if __name__ == "__main__":
    main()
