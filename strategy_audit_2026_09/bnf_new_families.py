"""Round 3 of from-scratch strategies for BankNifty/Nifty: 16 signal families NOT tried in bnf_scratch_scalp.py's
24 (mean-reversion + EMA/Donchian/Supertrend/MACD/VWAP scalp families) or in the crude/silver port test.
Same quick-scalp exit style (small ATR-relative stop, RR target, time-stop) that worked for both live candidates.
Tested on both BankNifty futures 5m (3yr robust) and Nifty spot 5m (6.3mo, thin, same floor as before).
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
import silver_sweep as SS
import bnf_port_test as B
import bnf_scratch_scalp as X

SESSION = X.SESSION
FLAT = X.FLAT


def extra2(d):
    """Additional indicators for the 16 new families, layered on top of X.extra()'s set."""
    d = X.extra(d)
    if "psar" in d.columns:
        return d
    c, o, h, l, atr = d["close"], d["open"], d["high"], d["low"], d["atr"]
    date = d["time"].dt.date
    # Parabolic SAR
    d["psar"] = _psar(h.to_numpy(), l.to_numpy())
    # DI+/DI-
    up_move, dn_move = h.diff(), -l.diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr = SS.true_range(h, l, c)
    atr14b = SS.wilder(tr, 14)
    d["plus_di"] = 100 * SS.wilder(pd.Series(plus_dm, index=d.index), 14) / atr14b.replace(0, np.nan)
    d["minus_di"] = 100 * SS.wilder(pd.Series(minus_dm, index=d.index), 14) / atr14b.replace(0, np.nan)
    # NR7: today's range is the narrowest of the last 7 bars
    rng = h - l
    d["nr7"] = rng == rng.rolling(7).min()
    # gap (day open vs prior day close)
    lastc = c.groupby(date).last()
    d["prevday_close"] = date.map(lastc.shift(1)).astype(float)
    d["day_open"] = date.map(o.groupby(date).first()).astype(float)
    d["bar_idx"] = d.groupby(date).cumcount()
    # swing high/low for Fib retracement (use existing 10-bar swing)
    swlo, swhi = SS.swings(d, 10)
    d["fib50"] = (swlo + swhi) / 2
    # inside bar: today's range inside yesterday's bar range
    d["inside_bar"] = (h < h.shift(1)) & (l > l.shift(1))
    # triple EMA
    d["e5"] = c.ewm(span=5, adjust=False).mean()
    d["e13"] = c.ewm(span=13, adjust=False).mean()
    d["e34"] = c.ewm(span=34, adjust=False).mean()
    # RSI(2)
    dl2 = c.diff()
    g2 = dl2.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    ls2 = (-dl2.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    d["rsi2"] = 100 - 100 / (1 + g2 / ls2.replace(0, np.nan))
    # Ichimoku Tenkan(9)/Kijun(26)
    d["tenkan"] = (h.rolling(9).max() + l.rolling(9).min()) / 2
    d["kijun"] = (h.rolling(26).max() + l.rolling(26).min()) / 2
    # plain Heikin-Ashi (unsmoothed)
    ha_c = (o + h + l + c) / 4
    ha_o = np.empty(len(d)); ha_o[0] = (o.iat[0] + c.iat[0]) / 2
    ha_c_np = ha_c.to_numpy()
    for i in range(1, len(d)):
        ha_o[i] = (ha_o[i - 1] + ha_c_np[i - 1]) / 2
    ha_up = ha_c_np > ha_o
    d["ha_up"] = pd.Series(ha_up, index=d.index)
    # first-hour range (12 bars on 5m = 60min, or first_n)
    fh_n = 12 if abs(d["time"].diff().dt.total_seconds().median() - 300) < 1 else 20
    d["fh_hi"] = h.where(d["bar_idx"] < fh_n).groupby(date).transform("max")
    d["fh_lo"] = l.where(d["bar_idx"] < fh_n).groupby(date).transform("min")
    d["fh_n"] = fh_n
    # tight ATR channel around EMA20 (1.0x, vs Keltner's 1.5x already tried)
    d["atrch_up"], d["atrch_lo"] = d["ema20"] + 1.0 * atr, d["ema20"] - 1.0 * atr
    # Bollinger squeeze then breakout
    width = (d["bb_up"] - d["bb_lo"]) / d["bb_mid"]
    d["bb_narrow"] = width < width.rolling(100).quantile(0.2)
    return d


def _psar(high, low, af0=0.02, af_step=0.02, af_max=0.2):
    n = len(high)
    sar = np.zeros(n); trend = np.ones(n); ep = np.zeros(n); af = np.zeros(n)
    trend[0] = 1; sar[0] = low[0]; ep[0] = high[0]; af[0] = af0
    for i in range(1, n):
        prev_sar = sar[i - 1] + af[i - 1] * (ep[i - 1] - sar[i - 1])
        if trend[i - 1] == 1:
            prev_sar = min(prev_sar, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < prev_sar:
                trend[i] = -1; sar[i] = ep[i - 1]; ep[i] = low[i]; af[i] = af0
            else:
                trend[i] = 1; sar[i] = prev_sar
                if high[i] > ep[i - 1]: ep[i] = high[i]; af[i] = min(af[i - 1] + af_step, af_max)
                else: ep[i] = ep[i - 1]; af[i] = af[i - 1]
        else:
            prev_sar = max(prev_sar, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > prev_sar:
                trend[i] = 1; sar[i] = ep[i - 1]; ep[i] = high[i]; af[i] = af0
            else:
                trend[i] = -1; sar[i] = prev_sar
                if low[i] < ep[i - 1]: ep[i] = low[i]; af[i] = min(af[i - 1] + af_step, af_max)
                else: ep[i] = ep[i - 1]; af[i] = af[i - 1]
    return sar


def build2(d, name):
    c, o, h, l, atr = d["close"], d["open"], d["high"], d["low"], d["atr"]
    if name == "psar_flip":
        ps = pd.Series(d["psar"], index=d.index)
        L, S = X.cross_up(c, ps), X.cross_dn(c, ps)
    elif name == "di_cross":
        L, S = X.cross_up(d["plus_di"], d["minus_di"]), X.cross_dn(d["plus_di"], d["minus_di"])
    elif name == "nr7_breakout":
        L = d["nr7"].shift(1).fillna(False) & (c > h.shift(1))
        S = d["nr7"].shift(1).fillna(False) & (c < l.shift(1))
    elif name == "gap_fade":
        gap_up = (d["bar_idx"] == 0) & (d["day_open"] > d["prevday_close"])
        gap_dn = (d["bar_idx"] == 0) & (d["day_open"] < d["prevday_close"])
        L, S = gap_dn, gap_up  # fade: gap down -> long, gap up -> short
    elif name == "gap_go":
        gap_up = (d["bar_idx"] <= 2) & (c > d["day_open"]) & (d["day_open"] > d["prevday_close"])
        gap_dn = (d["bar_idx"] <= 2) & (c < d["day_open"]) & (d["day_open"] < d["prevday_close"])
        L, S = gap_up & ~gap_up.shift(1).fillna(False), gap_dn & ~gap_dn.shift(1).fillna(False)
    elif name == "fib_bounce":
        touch_up = (l <= d["fib50"]) & (c > d["fib50"]) & (c > d["e200"])
        touch_dn = (h >= d["fib50"]) & (c < d["fib50"]) & (c < d["e200"])
        L, S = touch_up, touch_dn
    elif name == "inside_bar_breakout":
        ib = d["inside_bar"].shift(1).fillna(False)
        L = ib & (c > h.shift(1))
        S = ib & (c < l.shift(1))
    elif name == "vwap_reclaim":
        L, S = X.cross_up(c, d["vwap"]), X.cross_dn(c, d["vwap"])
    elif name == "triple_ema":
        up = (d["e5"] > d["e13"]) & (d["e13"] > d["e34"])
        dn = (d["e5"] < d["e13"]) & (d["e13"] < d["e34"])
        L, S = up & ~up.shift(1).fillna(False), dn & ~dn.shift(1).fillna(False)
    elif name == "rsi2_pullback":
        L = X.cross_up(d["rsi2"], pd.Series(10.0, index=d.index)) & (c > d["e200"])
        S = X.cross_dn(d["rsi2"], pd.Series(90.0, index=d.index)) & (c < d["e200"])
    elif name == "tenkan_kijun":
        L, S = X.cross_up(d["tenkan"], d["kijun"]), X.cross_dn(d["tenkan"], d["kijun"])
    elif name == "ha_flip":
        up = d["ha_up"]
        L, S = up & ~up.shift(1).fillna(False), ~up & up.shift(1).fillna(False)
    elif name == "first_hour_retest":
        brk_up = c > d["fh_hi"]; brk_dn = c < d["fh_lo"]
        L = brk_up.shift(1).fillna(False) & (l <= d["fh_hi"]) & (c > d["fh_hi"])
        S = brk_dn.shift(1).fillna(False) & (h >= d["fh_lo"]) & (c < d["fh_lo"])
    elif name == "atr_channel":
        touch_lo = (l <= d["atrch_lo"]) & (c > d["atrch_lo"])
        touch_up = (h >= d["atrch_up"]) & (c < d["atrch_up"])
        L, S = touch_lo, touch_up
    elif name == "bb_squeeze_break":
        pre = d["bb_narrow"].shift(1).fillna(False)
        L = pre & (c > d["bb_up"])
        S = pre & (c < d["bb_lo"])
    else:
        raise ValueError(name)
    swlo, swhi = SS.swings(d, 10)
    risk_l = (c - (swlo - 0.1 * atr)).clip(lower=1.0 * atr)
    risk_s = ((swhi + 0.1 * atr) - c).clip(lower=1.0 * atr)
    return L.fillna(False), S.fillna(False), risk_l, risk_s


def sim(v, tf="5", comm=0.0, inst=None):
    d = B.base(tf, inst)
    d = extra2(d)
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in SESSION]
    ff0, ff1 = [int(x[:2]) * 60 + int(x[3:]) for x in FLAT]
    in_sess = (d["tmin"] >= s0m) & (d["tmin"] < s1m) & ~((d["tmin"] >= ff0) & (d["tmin"] < ff1))
    if v.get("tod"):
        t0, t1 = [int(x[:2]) * 60 + int(x[3:]) for x in v["tod"]]
        in_sess = in_sess & (d["tmin"] >= t0) & (d["tmin"] < t1)
    L, S, risk_l, risk_s = build2(d, v["name"])
    if v.get("adx_min"):
        gate = d["adx15_prev"] >= v["adx_min"]
        L, S = L & gate, S & gate
    g = d.copy()
    g["ok_l"] = in_sess & L
    g["ok_s"] = in_sess & S & ~g["ok_l"]
    g["risk_l"], g["risk_s"] = risk_l, risk_s
    p = dict(rr=v.get("rr", 1.5), day_loss_limit_pts=0.0)
    return rs.simulate(g, p, start=rs.WARMUP, commission=comm, time_stop_min=v.get("time_stop", 30), flat_at=FLAT[0])


def summ(tag, v, inst=None, months=None):
    tr = sim(v, inst=inst)
    if len(tr) < 15:
        return dict(id=tag, n=len(tr))
    d = B.base("5", inst)
    mo = months or (d["time"].iloc[-1] - d["time"].iloc[rs.WARMUP]).days / 30.44
    t = pd.DataFrame(tr); t["x"] = pd.to_datetime(t.exit_time)
    full = rs.stats(t.to_dict("records"))
    mid = t.x.min() + (t.x.max() - t.x.min()) / 2
    h1 = rs.stats(t[t.x < mid].to_dict("records"))
    h2 = rs.stats(t[t.x >= mid].to_dict("records"))
    return dict(id=tag, n=full["n"], per_mo=round(full["n"] / mo, 1), pf=full["pf"], net=round(full["net"]),
                win=full["win_pct"], dd=round(full["max_dd"]), best_mo=full["best_month_share"],
                h1_pf=h1.get("pf"), h2_pf=h2.get("pf"))


NAMES = ["psar_flip", "di_cross", "nr7_breakout", "gap_fade", "gap_go", "fib_bounce", "inside_bar_breakout",
         "vwap_reclaim", "triple_ema", "rsi2_pullback", "tenkan_kijun", "ha_flip", "first_hour_retest",
         "atr_channel", "bb_squeeze_break"]

if __name__ == "__main__":
    rows = []
    for inst, tag_pre in [("NSE_BANKNIFTY1", "BNF"), ("NSE_NIFTY", "NIFTY")]:
        B.PV = 30 if inst == "NSE_BANKNIFTY1" else 1
        for i, name in enumerate(NAMES):
            rows.append(summ(f"{tag_pre} {name}", dict(name=name, rr=1.5, time_stop=30), inst=inst))
            if (i + 1) % 8 == 0:
                print(f"{inst} {i + 1}/{len(NAMES)}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "bnf_nifty_new_families.csv", index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
