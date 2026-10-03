"""India-accessible long-only trend-filtered allocation (follow-up to backtest_trend_portfolio.py).
Universe (fixed in advance): NIFTYBEES BANKBEES JUNIORBEES GOLDBEES SILVERBEES(from 2022) MON100(Nasdaq-100); variant B adds BTC+ETH (Delta).
Each market gets an equal 1/N_live slice; slice is invested only while the trend signal is on, otherwise sits in LIQUIDBEES-like cash.
Signal = average of 5 long-only rules (TSMOM126, TSMOM252, MA50/200, MA20/100, Donchian100) in [0,1] -> fractional exposure.
Main mode = MONTHLY rebalance (month-end signal, next-day execution) -- what a small investor can actually do; DAILY shown as sensitivity.
No leverage. Costs per side on every weight change; cash leg trades cost too. Taxes NOT modelled (STCG/slab tax would reduce results)."""
from __future__ import annotations
import os, sys
import numpy as np, pandas as pd
import backtest_trend_portfolio as T

ROOT = os.path.dirname(os.path.abspath(__file__)); TR = os.path.join(ROOT, "research_data", "trend")
IN = ["niftybees", "bankbees", "juniorbees", "goldbees", "silverbees", "mon100"]
COSTS = {"niftybees": 0.0015, "bankbees": 0.0015, "juniorbees": 0.0015, "mon100": 0.0015, "goldbees": 0.0005, "silverbees": 0.0005, "btc": 0.0007, "eth": 0.0007}
CASH_COST = 0.0003
RULE_NAMES = ["TSMOM126", "TSMOM252", "MA50/200", "MA20/100", "DON100"]
TRAIN_END = pd.Timestamp("2016-12-31"); TEST_START = pd.Timestamp("2017-01-01")

def clean_spikes(d, name=""):
    """Drop single-bar price glitches: a >8% one-day move that is >=75% reversed by the next close (real shocks persist)."""
    d = d.reset_index(drop=True); dropped = []
    med = d["close"].rolling(11, center=True, min_periods=5).median()
    far = (d["close"] / med - 1).abs() > 0.40                        # multi-bar plateaus at the wrong scale (e.g. a /10 or /100 print)
    if far.any(): dropped += list(d["time"][far].dt.date); d = d[~far].reset_index(drop=True)
    while True:
        c = d["close"].to_numpy(); r = c[1:-1] / c[:-2] - 1; back = c[2:] / c[:-2] - 1
        bad = np.flatnonzero((np.abs(r) > 0.08) & (np.abs(back) < 0.25 * np.abs(r))) + 1
        if len(bad) == 0: break
        dropped += list(d["time"].iloc[bad].dt.date); d = d.drop(index=bad).reset_index(drop=True)
    if dropped: print(f"  cleaned {name}: dropped {len(dropped)} glitch bars {dropped}")
    return d

def load_markets(with_crypto):
    mk = {k: clean_spikes(pd.read_pickle(os.path.join(TR, f"in_{k}.pkl")), k) for k in IN}
    fund = {}
    if with_crypto:
        cm, cf = T.load_all()
        for k in ("btc", "eth"): mk[k] = cm[k]
        fund = cf
    return mk, fund

def long_signal(d):
    sigs = [T.RULES[r](d).clip(lower=0) for r in RULE_NAMES]
    return pd.concat(sigs, axis=1).mean(axis=1)

def run(mk, fund, mode="M", cash_rate=0.055, always_long=False, rules_mean=True):
    idx = pd.DatetimeIndex(sorted(set().union(*[set(d["time"]) for d in mk.values()])))
    cash = pd.Series(cash_rate / 365.25, index=idx) * pd.Series(np.r_[0, np.diff(idx.values).astype("timedelta64[D]").astype(float)], index=idx)
    R, S, LIVE = {}, {}, {}
    for k, d in mk.items():
        d = d.copy(); t = pd.DatetimeIndex(d["time"]); r = pd.Series(d["close"].pct_change().fillna(0).to_numpy(), index=t)
        s = pd.Series(1.0, index=t) if always_long else pd.Series(long_signal(d).to_numpy(), index=t)
        if mode == "M":
            me = s.groupby([t.year, t.month]).transform("last")           # month-end signal known at the month's last bar
            is_last = pd.Series(t, index=t).groupby([t.year, t.month]).transform("max") == pd.Series(t, index=t)
            s = me.where(is_last).ffill()                                  # carry the latest month-end value forward
        s = s.shift(1).fillna(0)                                           # signal known at close t-1 -> position for day t
        live = pd.Series(np.arange(len(t)) >= 300, index=t)
        R[k] = r.reindex(idx).fillna(0); S[k] = s.reindex(idx).ffill().fillna(0); LIVE[k] = live.reindex(idx).ffill().fillna(False)
    Rm, Sm, Lm = pd.DataFrame(R), pd.DataFrame(S), pd.DataFrame(LIVE)
    nl = Lm.sum(axis=1).replace(0, np.nan)
    W = (Sm.where(Lm, 0.0)).div(nl, axis=0).fillna(0)                       # slice = signal / N_live
    risky = W.sum(axis=1)
    ret = (W.shift(1).fillna(0) * Rm).sum(axis=1) + (1 - W.shift(1).fillna(0).sum(axis=1)) * cash
    dW = W.diff().abs().fillna(0)
    cost = sum(dW[k] * COSTS[k] for k in W.columns) + dW.sum(axis=1) * CASH_COST
    ret = ret - cost
    if fund:
        for k in fund:
            if k in W.columns: ret = ret - W.shift(1).fillna(0)[k] * pd.Series(fund[k]).reindex(idx).fillna(0)
    start = Lm.any(axis=1).idxmax(); ret = ret[ret.index >= start]
    return ret, W, dW

def stats(r):
    r = r.dropna()
    if len(r) < 100: return dict(cagr=np.nan, vol=np.nan, sharpe=np.nan, mdd=np.nan)
    eq = (1 + r).cumprod(); yrs = (r.index[-1] - r.index[0]).days / 365.25
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, vol=r.std() * np.sqrt(252), sharpe=r.mean() / r.std() * np.sqrt(252), mdd=(eq / eq.cummax() - 1).min())

def line(name, r):
    a, b = stats(r[r.index <= TRAIN_END]), stats(r[r.index >= TEST_START])
    return dict(name=name, tr_cagr=a["cagr"], tr_mdd=a["mdd"], te_cagr=b["cagr"], te_vol=b["vol"], te_sharpe=b["sharpe"], te_mdd=b["mdd"])

if __name__ == "__main__":
    pd.set_option("display.width", 220)
    rows = []
    for label, wc in (("INDIA ETFs only", False), ("INDIA ETFs + BTC/ETH", True)):
        mk, fund = load_markets(wc)
        for cr in (0.0, 0.03, 0.055):
            r, W, dW = run(mk, fund, "M", cr); rows.append(line(f"{label} | trend monthly | cash {cr:.1%}", r))
        r, W, dW = run(mk, fund, "D", 0.055); rows.append(line(f"{label} | trend DAILY  | cash 5.5%", r))
        r, _, _ = run(mk, fund, "M", 0.055, always_long=True); rows.append(line(f"{label} | ALWAYS-LONG equal wt | cash 5.5%", r))
    nb = clean_spikes(pd.read_pickle(os.path.join(TR, "in_niftybees.pkl")), "niftybees"); rr = pd.Series(nb["close"].pct_change().fillna(0).to_numpy(), index=pd.DatetimeIndex(nb["time"]))
    rows.append(line("NIFTYBEES buy&hold", rr[rr.index >= pd.Timestamp("2010-01-01")]))
    print(pd.DataFrame(rows).set_index("name").round(3).to_string())
