"""Crypto-only trend filter: diversified ETF basket ALWAYS held + a BTC/ETH sleeve that is either always held or trend-filtered.
Sleeve size c in {10%, 20%, 30%} of the portfolio (fixed in advance), BTC and ETH split evenly. Same 5 long-only rules (TSMOM126/252,
MA50/200, MA20/100, Donchian100) averaged into an exposure in [0,1]; monthly rebalance (daily shown as sensitivity). Cash leg 5.5% (liquid fund).
ETF costs/crypto costs/funding as in backtest_india_trend.py. Window starts when BTC has 300 bars of history (mid-2020)."""
from __future__ import annotations
import numpy as np, pandas as pd
import backtest_india_trend as B

ETF = ["niftybees", "bankbees", "juniorbees", "goldbees", "silverbees", "mon100"]; CR = ["btc", "eth"]

def build(mk, fund, mode):
    idx = pd.DatetimeIndex(sorted(set().union(*[set(d["time"]) for d in mk.values()])))
    gaps = np.r_[0, np.diff(idx.values).astype("timedelta64[D]").astype(float)]
    R, S, L = {}, {}, {}
    for k, d in mk.items():
        t = pd.DatetimeIndex(d["time"]); r = pd.Series(d["close"].pct_change().fillna(0).to_numpy(), index=t)
        s = pd.Series(B.long_signal(d).to_numpy(), index=t)
        if mode == "M":
            last = pd.Series(t, index=t).groupby([t.year, t.month]).transform("max") == pd.Series(t, index=t)
            s = s.where(last).ffill()
        s = s.shift(1).fillna(0); live = pd.Series(np.arange(len(t)) >= 300, index=t)
        R[k] = r.reindex(idx).fillna(0); S[k] = s.reindex(idx).ffill().fillna(0); L[k] = live.reindex(idx).ffill().fillna(False)
    fundd = {k: pd.Series(v).reindex(idx).fillna(0) for k, v in fund.items()}
    return idx, gaps, pd.DataFrame(R), pd.DataFrame(S), pd.DataFrame(L), fundd

def compose(parts, c, crypto_mode, cash_rate=0.055):
    idx, gaps, Rm, Sm, Lm, fundd = parts
    cash = pd.Series(cash_rate / 365.25 * gaps, index=idx)
    n_etf = Lm[ETF].sum(axis=1).replace(0, np.nan)
    W = pd.DataFrame(0.0, index=idx, columns=Rm.columns)
    for k in ETF: W[k] = ((1 - c) * Lm[k].astype(float) / n_etf).fillna(0) if c is not None else 0
    for k in CR:
        sig = Sm[k] if crypto_mode == "trend" else pd.Series(1.0, index=idx)
        W[k] = (c / 2) * sig * Lm[k].astype(float) if c else 0.0
    Wp = W.shift(1).fillna(0)
    ret = (Wp * Rm).sum(axis=1) + (1 - Wp.sum(axis=1)) * cash
    dW = W.diff().abs().fillna(0)
    ret = ret - sum(dW[k] * B.COSTS[k] for k in W.columns) - dW.sum(axis=1) * B.CASH_COST
    for k in CR: ret = ret - Wp[k] * fundd[k]
    start = Lm["btc"].idxmax(); return ret[ret.index >= start]

def st(r):
    eq = (1 + r).cumprod(); yrs = (r.index[-1] - r.index[0]).days / 365.25
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, vol=r.std() * np.sqrt(252), sharpe=r.mean() / r.std() * np.sqrt(252), mdd=(eq / eq.cummax() - 1).min(), x=eq.iloc[-1])

if __name__ == "__main__":
    pd.set_option("display.width", 220)
    mk, fund = B.load_markets(True)
    out = {}
    for mode in ("M", "D"):
        parts = build(mk, fund, mode)
        for c in (0.0, 0.1, 0.2, 0.3):
            if c == 0.0:
                out[("ETF only", mode, 0)] = compose(parts, 0.0, "always")
            else:
                out[("crypto ALWAYS held", mode, c)] = compose(parts, c, "always")
                out[("crypto TREND-filtered", mode, c)] = compose(parts, c, "trend")
    rows = []
    for (name, mode, c), r in out.items():
        if mode == "D" and name != "crypto TREND-filtered": continue
        s = st(r); h = r[r.index < r.index[len(r) // 2]], r[r.index >= r.index[len(r) // 2]]
        rows.append(dict(scenario=name, rebal={"M": "monthly", "D": "daily"}[mode], sleeve=f"{c:.0%}", cagr=s["cagr"], vol=s["vol"], sharpe=s["sharpe"], mdd=s["mdd"],
                         **{"sharpe_h1": st(h[0])["sharpe"], "sharpe_h2": st(h[1])["sharpe"], "Rs1L_to": 100000 * s["x"]}))
    R = pd.DataFrame(rows); print(f"window: {out[('ETF only','M',0)].index[0].date()} .. {out[('ETF only','M',0)].index[-1].date()}")
    print(R.round(3).to_string(index=False))
    # crypto sleeve alone, always vs trend
    parts = build(mk, fund, "M"); idx, gaps, Rm, Sm, Lm, fundd = parts
    print("\nCrypto sleeve ALONE (100% BTC+ETH, equal split):")
    for nm, mode_ in (("always held", "always"), ("trend-filtered monthly", "trend")):
        W = pd.DataFrame({k: (0.5 * (Sm[k] if mode_ == "trend" else 1.0) * Lm[k].astype(float)) for k in CR}); Wp = W.shift(1).fillna(0)
        cash = pd.Series(0.055 / 365.25 * gaps, index=idx); r = (Wp * Rm[CR]).sum(axis=1) + (1 - Wp.sum(axis=1)) * cash
        r = r - sum(W.diff().abs().fillna(0)[k] * B.COSTS[k] for k in CR) - sum(Wp[k] * fundd[k] for k in CR); r = r[r.index >= Lm["btc"].idxmax()]
        s = st(r); print(f"  {nm:24} CAGR {s['cagr']:.1%}  vol {s['vol']:.1%}  Sharpe {s['sharpe']:.2f}  maxDD {s['mdd']:.0%}")
    ba = out[("crypto ALWAYS held", "M", 0.2)]; bt = out[("crypto TREND-filtered", "M", 0.2)]
    print("\nCalendar years, 20% sleeve (monthly):"); y = lambda r: (r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1) * 100).round(1)
    print(pd.DataFrame({"ETF only": y(out[("ETF only", "M", 0)]), "20% crypto always": y(ba), "20% crypto trend": y(bt)}).T.to_string())
