"""BankNifty, built from scratch for intraday day trading: 24 configs, none ported from crude/silver.
Rationale: the crude/silver SHA-flip/breakout family tops out at PF ~1.15 on BankNifty (bnf_port_test.py) because
BankNifty is choppier and more mean-reverting intraday than a trending commodity. This instead builds mean-reversion
(fade extremes back toward the mean) and quick-scalp continuation families natively, with small targets and short
holds -- explicitly what was asked for ("small moves fine, short-lived quick trade is fine").
Data: NSE_BANKNIFTY1_5m.csv (3yr, robust) and _3m.csv (3.9mo, thin -- spot-checked on the best 5m configs only).
Session 09:15-15:20, flat by 15:30. No day-loss limit (kept simple, matches other from-scratch screens this project).
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
import silver_sweep as SS
import bnf_port_test as B  # reuse base()/load_tf(), PV, SESSION, FLAT

SESSION = ("09:15", "15:20")
FLAT = ["15:20", "15:30"]


def extra(d):
    """Add the indicator set once per (tf) frame -- mean-reversion + scalp toolkit."""
    if "rsi" in d.columns:
        return d
    c, o, h, l, atr = d["close"], d["open"], d["high"], d["low"], d["atr"]
    date = d["time"].dt.date
    # RSI(14)
    dl = c.diff()
    g = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    ls = (-dl.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + g / ls.replace(0, np.nan))
    # Bollinger(20)
    sma20, std20 = c.rolling(20).mean(), c.rolling(20).std()
    d["bb_mid"], d["bb_up"], d["bb_lo"] = sma20, sma20 + 2 * std20, sma20 - 2 * std20
    # Keltner(20, ATR)
    d["ema20"] = c.ewm(span=20, adjust=False).mean()
    d["kelt_up"], d["kelt_lo"] = d["ema20"] + 1.5 * atr, d["ema20"] - 1.5 * atr
    # Stochastic(14,3)
    ll, hh = l.rolling(14).min(), h.rolling(14).max()
    k = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    d["stoch_k"] = k
    # CCI(20)
    tp = (h + l + c) / 3
    sma_tp = tp.rolling(20).mean()
    mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    d["cci"] = (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))
    # VWAP (session-reset)
    pv = (tp * d["volume"]).groupby(date).cumsum()
    vv = d["volume"].groupby(date).cumsum().replace(0, np.nan)
    d["vwap"] = pv / vv
    # MACD
    e12, e26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    d["macd_hist"] = macd - macd.ewm(span=9, adjust=False).mean()
    # Donchian(10/20)
    d["dc10_hi"], d["dc10_lo"] = h.rolling(10).max().shift(1), l.rolling(10).min().shift(1)
    d["dc20_hi"], d["dc20_lo"] = h.rolling(20).max().shift(1), l.rolling(20).min().shift(1)
    # Supertrend(10,3)
    atr10 = SS.wilder(SS.true_range(h, l, c), 10)
    hl2 = (h + l) / 2
    up_b, dn_b = hl2 + 3 * atr10, hl2 - 3 * atr10
    st_dir = np.ones(len(d))
    fub, flb = up_b.to_numpy().copy(), dn_b.to_numpy().copy()
    cc = c.to_numpy()
    for i in range(1, len(d)):
        if cc[i - 1] <= fub[i - 1]:
            fub[i] = min(up_b.iat[i], fub[i - 1])
        if cc[i - 1] >= flb[i - 1]:
            flb[i] = max(dn_b.iat[i], flb[i - 1])
        st_dir[i] = -1 if (st_dir[i - 1] == 1 and cc[i] < flb[i - 1]) else (1 if (st_dir[i - 1] == -1 and cc[i] > fub[i - 1]) else st_dir[i - 1])
    d["st_dir"] = st_dir
    # prior-day H/L, day open
    d["prevday_hi"] = date.map(h.groupby(date).max().shift(1)).astype(float)
    d["prevday_lo"] = date.map(l.groupby(date).min().shift(1)).astype(float)
    # opening-range (first 6 bars = 30min on 5m; first 10 on 3m -- use bar_idx_in_day generically)
    d["bar_idx_in_day"] = d.groupby(date).cumcount()
    or_n = 6 if d["time"].diff().dt.total_seconds().median() == 300 else 10
    d["or_hi"] = h.where(d["bar_idx_in_day"] < or_n).groupby(date).transform("max")
    d["or_lo"] = l.where(d["bar_idx_in_day"] < or_n).groupby(date).transform("min")
    d["or_n"] = or_n
    d["e200"] = c.ewm(span=200, adjust=False).mean()
    return d


def cross_up(a, b):
    return (a > b) & (a.shift(1) <= b.shift(1))


def cross_dn(a, b):
    return (a < b) & (a.shift(1) >= b.shift(1))


def build(d, name, min_sl_atr=1.0, max_sl_atr=None):
    """Returns ok_l, ok_s, risk_l, risk_s for a named family, small ATR-relative stop (scalp-sized)."""
    c, o, h, l, atr = d["close"], d["open"], d["high"], d["low"], d["atr"]
    zero = pd.Series(0.0, index=d.index)
    if name == "rsi_revert25":
        L, S = cross_up(d["rsi"], pd.Series(25.0, index=d.index)), cross_dn(d["rsi"], pd.Series(75.0, index=d.index))
    elif name == "rsi_revert20":
        L, S = cross_up(d["rsi"], pd.Series(20.0, index=d.index)), cross_dn(d["rsi"], pd.Series(80.0, index=d.index))
    elif name == "rsi_revert_trend":
        L = cross_up(d["rsi"], pd.Series(25.0, index=d.index)) & (c > d["e200"])
        S = cross_dn(d["rsi"], pd.Series(75.0, index=d.index)) & (c < d["e200"])
    elif name == "bb_fade":
        touch_lo = (l <= d["bb_lo"]) & (c > d["bb_lo"])
        touch_up = (h >= d["bb_up"]) & (c < d["bb_up"])
        L, S = touch_lo, touch_up
    elif name == "vwap_fade":
        L = c < d["vwap"] - 1.5 * atr
        S = c > d["vwap"] + 1.5 * atr
    elif name == "stoch_revert":
        L, S = cross_up(d["stoch_k"], pd.Series(20.0, index=d.index)), cross_dn(d["stoch_k"], pd.Series(80.0, index=d.index))
    elif name == "cci_revert":
        L, S = cross_up(d["cci"], pd.Series(-100.0, index=d.index)), cross_dn(d["cci"], pd.Series(100.0, index=d.index))
    elif name == "kelt_fade":
        touch_lo = (l <= d["kelt_lo"]) & (c > d["kelt_lo"])
        touch_up = (h >= d["kelt_up"]) & (c < d["kelt_up"])
        L, S = touch_lo, touch_up
    elif name == "rsi_bb_confluence":
        L = (d["rsi"] < 30) & (l <= d["bb_lo"]) & (c > d["bb_lo"])
        S = (d["rsi"] > 70) & (h >= d["bb_up"]) & (c < d["bb_up"])
    elif name == "or_fade":
        brk_up = c > d["or_hi"]; brk_dn = c < d["or_lo"]
        L = brk_dn.shift(1).fillna(False) & (c > d["or_lo"])
        S = brk_up.shift(1).fillna(False) & (c < d["or_hi"])
    elif name == "ema_cross":
        L, S = cross_up(d["e9"], d["e22"]), cross_dn(d["e9"], d["e22"])
    elif name == "donch10":
        L, S = c > d["dc10_hi"], c < d["dc10_lo"]
    elif name == "donch20":
        L, S = c > d["dc20_hi"], c < d["dc20_lo"]
    elif name == "momentum3":
        up3 = (c > c.shift(1)) & (c.shift(1) > c.shift(2)) & (c.shift(2) > c.shift(3))
        dn3 = (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3))
        L, S = up3 & ~up3.shift(1).fillna(False), dn3 & ~dn3.shift(1).fillna(False)
    elif name == "supertrend":
        st = pd.Series(d["st_dir"], index=d.index)
        L, S = (st == 1) & (st.shift(1) == -1), (st == -1) & (st.shift(1) == 1)
    elif name == "macd0":
        L, S = cross_up(d["macd_hist"], zero), cross_dn(d["macd_hist"], zero)
    elif name == "vwap_cont":
        L = cross_up(c, d["vwap"]) & (d["e9"] > d["e22"])
        S = cross_dn(c, d["vwap"]) & (d["e9"] < d["e22"])
    elif name == "orb_cont":
        L = c > d["or_hi"]
        S = c < d["or_lo"]
    elif name == "pivot_cont":
        L, S = c > d["prevday_hi"], c < d["prevday_lo"]
    else:
        raise ValueError(name)
    swlo, swhi = SS.swings(d, 10)
    risk_l = (c - (swlo - 0.1 * atr)).clip(lower=min_sl_atr * atr)
    risk_s = ((swhi + 0.1 * atr) - c).clip(lower=min_sl_atr * atr)
    if max_sl_atr:
        cap = max_sl_atr * atr
        L = L & (risk_l <= cap); S = S & (risk_s <= cap)
    return L.fillna(False), S.fillna(False), risk_l, risk_s


def sim(v, tf, comm=0.0):
    d = B.base(tf)
    d = extra(d)
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in SESSION]
    ff0, ff1 = [int(x[:2]) * 60 + int(x[3:]) for x in FLAT]
    in_sess = (d["tmin"] >= s0m) & (d["tmin"] < s1m) & ~((d["tmin"] >= ff0) & (d["tmin"] < ff1))
    if v.get("tod"):
        t0, t1 = [int(x[:2]) * 60 + int(x[3:]) for x in v["tod"]]
        in_sess = in_sess & (d["tmin"] >= t0) & (d["tmin"] < t1)
    L, S, risk_l, risk_s = build(d, v["name"], v.get("min_sl", 1.0), v.get("max_sl"))
    if v.get("vol_filter"):
        vf = d["volume"] > d["volume"].rolling(20).mean()
        L, S = L & vf, S & vf
    g = d.copy()
    g["ok_l"] = in_sess & L
    g["ok_s"] = in_sess & S & ~g["ok_l"]
    g["risk_l"], g["risk_s"] = risk_l, risk_s
    p = dict(rr=v.get("rr", 1.5), day_loss_limit_pts=0.0)
    return rs.simulate(g, p, start=rs.WARMUP, commission=comm, time_stop_min=v.get("time_stop"), flat_at=FLAT[0])


def summ(tag, v, tf):
    tr = sim(v, tf)
    d = B.base(tf)
    months = (d["time"].iloc[-1] - d["time"].iloc[rs.WARMUP]).days / 30.44
    if len(tr) < 15:
        return dict(id=tag, tf=tf, n=len(tr), months=round(months, 1))
    s = rs.stats(tr)
    return dict(id=tag, tf=tf, n=s["n"], per_mo=round(s["n"] / months, 1), pf=s["pf"], net=round(s["net"]),
                win=s["win_pct"], dd=round(s["max_dd"]), avg_hold_h=s["avg_hold_h"], best_mo=s["best_month_share"], months=round(months, 1))


CONFIGS = {
    # ---- mean-reversion family ----
    "M1 RSI revert 25/75": dict(name="rsi_revert25", min_sl=0.75, rr=1.5, time_stop=30),
    "M2 Bollinger band fade": dict(name="bb_fade", min_sl=1.0, rr=1.5, time_stop=45),
    "M3 VWAP extension fade": dict(name="vwap_fade", min_sl=1.0, rr=1.2, time_stop=30),
    "M4 Stochastic revert 20/80": dict(name="stoch_revert", min_sl=0.75, rr=1.5, time_stop=30),
    "M5 CCI revert +-100": dict(name="cci_revert", min_sl=1.0, rr=1.5, time_stop=30),
    "M6 Keltner band fade": dict(name="kelt_fade", min_sl=1.0, rr=1.2, time_stop=45),
    "M7 RSI+Bollinger confluence": dict(name="rsi_bb_confluence", min_sl=1.0, rr=2.0, time_stop=45),
    "M8 Opening-range fade": dict(name="or_fade", min_sl=0.75, rr=1.5, time_stop=30),
    # ---- quick-momentum scalp family ----
    "Q1 EMA9/22 cross scalp tight": dict(name="ema_cross", min_sl=0.75, rr=1.0, time_stop=30),
    "Q2 EMA9/22 cross scalp wide": dict(name="ema_cross", min_sl=1.0, rr=1.5, time_stop=45),
    "Q3 Donchian10 breakout scalp": dict(name="donch10", min_sl=0.75, rr=1.0, time_stop=20),
    "Q4 Donchian20 breakout scalp": dict(name="donch20", min_sl=1.0, rr=1.5, time_stop=30),
    "Q5 3-bar momentum burst": dict(name="momentum3", min_sl=0.75, rr=1.0, time_stop=20),
    "Q6 Supertrend flip scalp": dict(name="supertrend", min_sl=1.0, rr=1.5, time_stop=45),
    "Q7 MACD histogram cross scalp": dict(name="macd0", min_sl=1.0, rr=1.2, time_stop=30),
    "Q8 VWAP-cross continuation": dict(name="vwap_cont", min_sl=1.0, rr=1.5, time_stop=30),
    # ---- level / time-of-day family ----
    "T1 Opening-range breakout continuation": dict(name="orb_cont", min_sl=1.0, rr=2.0),
    "T2 Prior-day H/L breakout continuation": dict(name="pivot_cont", min_sl=1.0, rr=1.5, time_stop=45),
    "T3 RSI revert, morning only 0915-1100": dict(name="rsi_revert25", min_sl=0.75, rr=1.5, time_stop=30, tod=("09:15", "11:00")),
    "T4 RSI revert, afternoon only 1300-1500": dict(name="rsi_revert25", min_sl=0.75, rr=1.5, time_stop=30, tod=("13:00", "15:00")),
    # ---- hybrid / robustness checks ----
    "H1 RSI revert, trend-filtered (vs e200)": dict(name="rsi_revert_trend", min_sl=0.75, rr=1.5, time_stop=30),
    "H2 Bollinger fade + volume filter": dict(name="bb_fade", min_sl=1.0, rr=1.5, time_stop=45, vol_filter=True),
    "H3 Time-stop only, no RR (15min, wide stop)": dict(name="ema_cross", min_sl=2.0, rr=10.0, time_stop=15),
    "H4 RSI revert 20/80 (wider bands)": dict(name="rsi_revert20", min_sl=0.75, rr=1.5, time_stop=30),
}

if __name__ == "__main__":
    rows = []
    for i, (tag, v) in enumerate(CONFIGS.items()):
        rows.append(summ(tag, v, "5"))
        if (i + 1) % 8 == 0:
            print(f"{i + 1}/{len(CONFIGS)}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "bnf_scratch_scalp.csv", index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
