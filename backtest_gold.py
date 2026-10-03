"""XAU/USD (COMEX GC=F proxy) test of the production v5.0 SHA-ADX family.
A) DAILY bars 2000-2026 with a WEEKLY ADX gate; select on 2000-08..2012-12, judge on 2013..2026.
B) HOURLY bars 2024-05..2026-10 (1h base / 4h ADX gate), the same shape as the crypto 'slow' config.
Compared to buy-and-hold. Costs: 0.05%/side (daily), 0.05%/side and a 0.02% sensitivity (hourly).
Note GC=F is a continuous futures series: roll gaps are not back-adjusted (small for gold)."""
import sys, itertools
sys.path.insert(0, ".")
import numpy as np, pandas as pd
import backtest_btc_mtf as M
from trading_agents.core.signals_v50 import v50_frame, _adx_raw
from backtest_btc_sha_adx_hybrid import btc_params
from backtest_btc_mtf_search import tstat

EMPTY_T = np.array([], dtype="datetime64[ns]"); EMPTY_C = np.array([0.0])

def htf_adx(base, minutes):
    k = (base.set_index("time").resample(f"{minutes}min", label="left", closed="left", origin="epoch")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(subset=["close"]))
    k["adx"] = _adx_raw(k["high"], k["low"], k["close"], 14)
    prev = k[["adx"]].shift(1)
    idx = base["time"].dt.floor(f"{minutes}min")
    return prev.reindex(idx)["adx"].to_numpy()

def gates(df):
    atr = df["atr"].to_numpy(); ok = atr > 0
    cap = lambda r: r <= 3.0 * atr
    return {("flip","L"): df["ok_l"].to_numpy() & df["near_ema9_l"].to_numpy() & cap(df["risk_l"].to_numpy()) & ok,
            ("flip","S"): df["ok_s"].to_numpy() & df["near_ema9_s"].to_numpy() & cap(df["risk_s"].to_numpy()) & ok,
            ("breakout","L"): df["ok_l_bo"].to_numpy() & df["near_ema9_l"].to_numpy() & cap(df["risk_l"].to_numpy()) & ok,
            ("breakout","S"): df["ok_s_bo"].to_numpy() & df["near_ema9_s"].to_numpy() & cap(df["risk_s"].to_numpy()) & ok}

def load(f):
    d = pd.read_pickle(f"research_data/gold/gc_{f}.pkl"); d["time"] = pd.to_datetime(d["time"]).dt.tz_localize(None) if d["time"].dt.tz else d["time"]
    return d.reset_index(drop=True)

def run_grid(bars, htf_min, adxs=(20,25,30,35), rrs=(2.0,3.0,4.0), trigs=("flip","breakout")):
    df = v50_frame(bars, btc_params("flip", False, 30.0, 3.0)); g = gates(df); adx = htf_adx(bars, htf_min)
    out = {}
    for trig, a, rr in itertools.product(trigs, adxs, rrs):
        ok = adx >= a
        out[(trig, a, rr)] = M.simulate_fast(df, g[(trig,"L")] & ok, g[(trig,"S")] & ok, rr, EMPTY_T, EMPTY_C)
    return out

def eq_stats(tr, f, years):
    if len(tr) == 0: return (np.nan, np.nan)
    eq = (1 + f * tr.sort_values("exit_time").net_r).cumprod(); dd = (eq / eq.cummax() - 1).min()
    return (eq.iloc[-1] ** (1 / years) - 1, dd)

if __name__ == "__main__":
    M.COST_SIDE = 0.0005
    # ---------------- A) daily
    d = load("1d"); print(f"DAILY gold {d.time.iloc[0].date()}..{d.time.iloc[-1].date()} {len(d)} bars")
    SPLIT = pd.Timestamp("2013-01-01"); END = d.time.iloc[-1]
    res = run_grid(d, 10080)
    rows = []
    for k, tr in res.items():
        a, b = tr[tr.entry_time < SPLIT], tr[tr.entry_time >= SPLIT]
        rows.append((k, len(a), a.net_r.mean(), tstat(a.net_r), len(b), b.net_r.mean(), tstat(b.net_r), (b.net_r>0).mean(), b.hold_d.mean()))
    S = pd.DataFrame(rows, columns=["cfg","nTr","Rtr","tTr","nTe","Rte","tTe","win","hold"])
    print(f"\nconfigs with positive TRAIN avg R: {(S.Rtr>0).sum()}/{len(S)};  positive TEST avg R: {(S.Rte>0).sum()}/{len(S)};  median test R {S.Rte.median():+.3f}")
    print("Top 6 by TRAIN t-stat -> TEST:")
    print(f"{'cfg':26} {'nTr':>4} {'Rtr':>7} {'t':>5} | {'nTe':>4} {'Rte':>7} {'t':>5} {'win':>5} {'hold_d':>6}")
    for r in S.sort_values("tTr", ascending=False).head(6).itertuples():
        print(f"{str(r.cfg):26} {r.nTr:>4} {r.Rtr:>+7.3f} {r.tTr:>5.1f} | {r.nTe:>4} {r.Rte:>+7.3f} {r.tTe:>5.1f} {r.win:>5.0%} {r.hold:>6.1f}")
    best = S.sort_values("tTr", ascending=False).iloc[0].cfg; te = res[best][res[best].entry_time >= SPLIT]
    yrs = (END - SPLIT).days / 365.25
    px = d[d.time >= SPLIT].close; bh_cagr = (px.iloc[-1]/px.iloc[0])**(1/yrs)-1; bh_dd = (px/px.cummax()-1).min()
    print(f"\nTRAIN-selected {best} in TEST 2013-2026: {len(te)} trades (~{len(te)/yrs:.0f}/yr), long {(te.side==1).sum()}/short {(te.side==-1).sum()}, "
          f"avg R long {te[te.side==1].net_r.mean():+.2f} short {te[te.side==-1].net_r.mean():+.2f}")
    for f in (0.01, 0.02, 0.05):
        c, dd = eq_stats(te, f, yrs); print(f"   risk {f:.0%}/trade: CAGR {c:+.1%}  maxDD {dd:.0%}   -> $1000 becomes ${1000*(1+c)**yrs:,.0f}")
    print(f"   BUY&HOLD gold 2013-2026: CAGR {bh_cagr:+.1%}  maxDD {bh_dd:.0%}  -> $1000 becomes ${1000*(px.iloc[-1]/px.iloc[0]):,.0f}")
    # ---------------- B) hourly
    h = load("1h"); print(f"\nHOURLY gold {h.time.iloc[0].date()}..{h.time.iloc[-1].date()} {len(h)} bars (1h base / 4h ADX gate)")
    for cost in (0.0005, 0.0002):
        M.COST_SIDE = cost; r2 = run_grid(h, 240, adxs=(20,30,40), rrs=(2.0,4.0), trigs=("flip",))
        print(f" cost {cost*100:.2f}%/side:")
        for k, tr in r2.items():
            print(f"   {str(k):22} n={len(tr):>3} win={(tr.net_r>0).mean():>4.0%} avgR={tr.net_r.mean():>+7.3f} t={tstat(tr.net_r):>5.1f} hold={tr.hold_d.mean():.2f}d")
