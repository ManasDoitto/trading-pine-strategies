"""Round 6: entry signals other than SHA flip, same risk framework as crude #1.
Pre-registration: pre_registration_crude_round6_newsignals_2026_09_27.md"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crude_50cfg as C
import research_sim as rs
import silver_sweep as SS

_D = None
def base():
    global _D
    if _D is not None:
        return _D
    d = C.data(9, 22)
    d = d.copy()
    d["e200"] = d["close"].ewm(span=200, adjust=False).mean()
    d["e5"] = d["close"].ewm(span=5, adjust=False).mean()
    d["e13"] = d["close"].ewm(span=13, adjust=False).mean()
    lo, hi = SS.swings(d, 10)
    d["sw_lo"], d["sw_hi"] = lo, hi
    d["risk_l"] = np.maximum(d["close"] - (lo - 0.1 * d["atr"]), 1.5 * d["atr"])
    d["risk_s"] = np.maximum((hi + 0.1 * d["atr"]) - d["close"], 1.5 * d["atr"])
    date = d["time"].dt.date
    d["_date"] = date
    d["day_open"] = date.map(d["open"].groupby(date).first()).astype(float)
    d["prevday_hi"] = date.map(d["high"].groupby(date).max().shift(1)).astype(float)
    d["prevday_lo"] = date.map(d["low"].groupby(date).min().shift(1)).astype(float)
    tp = (d["high"] + d["low"] + d["close"]) / 3
    pv = (tp * d["volume"]).groupby(date).cumsum()
    vv = d["volume"].groupby(date).cumsum().replace(0, np.nan)
    d["vwap"] = pv / vv
    d["bar_idx_in_day"] = d.groupby(date).cumcount()
    for n, mins in ((6, 30), (12, 60)):
        hi_or = d["high"].where(d["bar_idx_in_day"] < n).groupby(date).transform("max")
        lo_or = d["low"].where(d["bar_idx_in_day"] < n).groupby(date).transform("min")
        d[f"or_hi_{mins}"], d[f"or_lo_{mins}"] = hi_or, lo_or
    e12, e26 = d["close"].ewm(span=12, adjust=False).mean(), d["close"].ewm(span=26, adjust=False).mean()
    macd = e12 - e26
    sig = macd.ewm(span=9, adjust=False).mean()
    d["macd"], d["macd_sig"], d["macd_hist"] = macd, sig, macd - sig
    dl = d["close"].diff()
    g = dl.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    ls = (-dl.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    d["rsi"] = 100 - 100 / (1 + g / ls.replace(0, np.nan))
    sma20 = d["close"].rolling(20).mean(); std20 = d["close"].rolling(20).std()
    d["bb_mid"], d["bb_std"] = sma20, std20
    d["atr20"] = SS.wilder(SS.true_range(d["high"], d["low"], d["close"]), 20)
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    ll = d["low"].rolling(14).min(); hh = d["high"].rolling(14).max()
    k = 100 * (d["close"] - ll) / (hh - ll).replace(0, np.nan)
    d["stoch_k"], d["stoch_d"] = k, k.rolling(3).mean()
    tp20 = (d["high"] + d["low"] + d["close"]) / 3
    sma_tp = tp20.rolling(20).mean(); mad = tp20.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    d["cci"] = (tp20 - sma_tp) / (0.015 * mad.replace(0, np.nan))
    atr10 = SS.wilder(SS.true_range(d["high"], d["low"], d["close"]), 10)
    hl2 = (d["high"] + d["low"]) / 2
    up_band, dn_band = hl2 + 3 * atr10, hl2 - 3 * atr10
    st_dir = np.ones(len(d))
    fub, flb = up_band.to_numpy().copy(), dn_band.to_numpy().copy()
    c = d["close"].to_numpy()
    for i in range(1, len(d)):
        if c[i - 1] <= fub[i - 1]: fub[i] = min(up_band.iat[i], fub[i - 1])
        if c[i - 1] >= flb[i - 1]: flb[i] = max(dn_band.iat[i], flb[i - 1])
        if st_dir[i - 1] == 1 and c[i] < flb[i - 1]: st_dir[i] = -1
        elif st_dir[i - 1] == -1 and c[i] > fub[i - 1]: st_dir[i] = 1
        else: st_dir[i] = st_dir[i - 1]
    d["st_dir"] = st_dir
    up_move = d["high"].diff(); dn_move = -d["low"].diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    tr = SS.true_range(d["high"], d["low"], d["close"])
    atr14b = SS.wilder(tr, 14)
    plus_di = 100 * SS.wilder(pd.Series(plus_dm, index=d.index), 14) / atr14b.replace(0, np.nan)
    minus_di = 100 * SS.wilder(pd.Series(minus_dm, index=d.index), 14) / atr14b.replace(0, np.nan)
    d["plus_di"], d["minus_di"] = plus_di, minus_di
    d["psar"] = _psar(d["high"].to_numpy(), d["low"].to_numpy())
    _D = d
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

def cross_up(a, b): return (a > b) & (a.shift(1) <= b.shift(1))
def cross_dn(a, b): return (a < b) & (a.shift(1) >= b.shift(1))

def signal(d, name):
    c, o, h, l = d["close"], d["open"], d["high"], d["low"]
    zero = pd.Series(0, index=d.index)
    if name == "ema9x22": return cross_up(d["e9"], d["e22"]), cross_dn(d["e9"], d["e22"])
    if name == "ema9x22+200":
        L, S = cross_up(d["e9"], d["e22"]), cross_dn(d["e9"], d["e22"])
        return L & (c > d["e200"]), S & (c < d["e200"])
    if name == "macd_hist0": return cross_up(d["macd_hist"], zero), cross_dn(d["macd_hist"], zero)
    if name == "macd_sig": return cross_up(d["macd"], d["macd_sig"]), cross_dn(d["macd"], d["macd_sig"])
    if name == "supertrend":
        st = pd.Series(d["st_dir"], index=d.index)
        return (st == 1) & (st.shift(1) == -1), (st == -1) & (st.shift(1) == 1)
    if name.startswith("donch"):
        n = int(name[5:]); return c > h.rolling(n).max().shift(1), c < l.rolling(n).min().shift(1)
    if name.startswith("orb"):
        mins = name[3:]; n = {"30": 6, "60": 12}[mins]
        return (c > d[f"or_hi_{mins}"]) & (d["bar_idx_in_day"] == n), (c < d[f"or_lo_{mins}"]) & (d["bar_idx_in_day"] == n)
    if name == "rsi_cross50": return cross_up(d["rsi"], pd.Series(50, index=d.index)), cross_dn(d["rsi"], pd.Series(50, index=d.index))
    if name == "rsi_revert": return cross_up(d["rsi"], pd.Series(30, index=d.index)), cross_dn(d["rsi"], pd.Series(70, index=d.index))
    if name == "bb2":
        up, dn = d["bb_mid"] + 2 * d["bb_std"], d["bb_mid"] - 2 * d["bb_std"]; return c > up, c < dn
    if name == "bb1.5":
        up, dn = d["bb_mid"] + 1.5 * d["bb_std"], d["bb_mid"] - 1.5 * d["bb_std"]; return c > up, c < dn
    if name == "bb_squeeze":
        width = (4 * d["bb_std"]) / d["bb_mid"]; narrow = width < width.rolling(100).quantile(0.2)
        up, dn = d["bb_mid"] + 2 * d["bb_std"], d["bb_mid"] - 2 * d["bb_std"]
        return (c > up) & narrow.shift(1).fillna(False), (c < dn) & narrow.shift(1).fillna(False)
    if name == "stoch":
        return cross_up(d["stoch_k"], pd.Series(20, index=d.index)) & (d["stoch_d"] < 30), cross_dn(d["stoch_k"], pd.Series(80, index=d.index)) & (d["stoch_d"] > 70)
    if name == "cci0": return cross_up(d["cci"], zero), cross_dn(d["cci"], zero)
    if name == "vwapx": return cross_up(c, d["vwap"]), cross_dn(c, d["vwap"])
    if name == "momentum3":
        up3 = (c > c.shift(1)) & (c.shift(1) > c.shift(2)) & (c.shift(2) > c.shift(3))
        dn3 = (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (c.shift(2) < c.shift(3))
        return up3 & ~up3.shift(1).fillna(False), dn3 & ~dn3.shift(1).fillna(False)
    if name == "kelt2":
        up, dn = d["ema20"] + 2 * d["atr20"], d["ema20"] - 2 * d["atr20"]; return c > up, c < dn
    if name == "kelt1.5":
        up, dn = d["ema20"] + 1.5 * d["atr20"], d["ema20"] - 1.5 * d["atr20"]; return c > up, c < dn
    if name == "pivot": return c > d["prevday_hi"], c < d["prevday_lo"]
    if name == "di_cross": return cross_up(d["plus_di"], d["minus_di"]), cross_dn(d["plus_di"], d["minus_di"])
    if name == "psar_flip":
        ps = pd.Series(d["psar"], index=d.index)
        return cross_up(c, ps), cross_dn(c, ps)
    if name == "ema5x13": return cross_up(d["e5"], d["e13"]), cross_dn(d["e5"], d["e13"])
    raise ValueError(name)

NAMES = ["ema9x22", "ema9x22+200", "macd_hist0", "macd_sig", "supertrend", "donch10", "donch20", "donch55",
         "orb30", "orb60", "rsi_cross50", "rsi_revert", "bb2", "bb1.5", "bb_squeeze", "stoch", "cci0", "vwapx",
         "momentum3", "kelt2", "kelt1.5", "pivot", "di_cross", "psar_flip", "ema5x13"]

def sim(v, comm=0.0):
    d = base()
    L, S = signal(d, v["name"])
    L, S = pd.Series(L, index=d.index).fillna(False), pd.Series(S, index=d.index).fillna(False)
    tmin = d["tmin"]
    s0m, s1m = [int(x[:2]) * 60 + int(x[3:]) for x in (v["start"], "23:30")]
    in_sess = (tmin >= s0m) & (tmin < s1m)
    cap = 3.0 * d["atr"]
    g = d.copy()
    g["ok_l"] = in_sess & L & (d["risk_l"] <= cap)
    g["ok_s"] = in_sess & S & (d["risk_s"] <= cap) & ~g["ok_l"]
    p = dict(rr=4.0, day_loss_limit_pts=0.0)
    s0 = max(int((g["time"] >= C.T0).idxmax()), rs.WARMUP)
    return rs.simulate(g, p, start=s0, commission=comm)

def summ(tag, v):
    tr, trn = sim(v), sim(v, 0.0002)
    row = dict(id=tag, start=v["start"], name=v["name"])
    if len(tr) < 20:
        row["full_n"] = len(tr)
        return row
    for nm, sub in (("full", None), ("tr", "<"), ("ho", ">=")):
        for suf, T in (("", tr), ("c", trn)):
            t = pd.DataFrame(T); t["x"] = pd.to_datetime(t["exit_time"])
            if sub == "<": t = t[t.x < C.SPLIT]
            elif sub == ">=": t = t[t.x >= C.SPLIT]
            s = rs.stats(t.to_dict("records")) if len(t) else dict(n=0, pf=0, net=0, max_dd=0)
            if suf == "":
                row.update({f"{nm}_n": s["n"], f"{nm}_pf": s["pf"], f"{nm}_net": round(s["net"]), f"{nm}_dd": round(s["max_dd"])})
            else:
                row[f"{nm}_cnet"] = round(s["net"])
    return row

def cfgs():
    out = []
    for st in ("09:15", "17:30"):
        for n in NAMES:
            out.append((f"{n} @{st}", dict(start=st, name=n)))
    return out

if __name__ == "__main__":
    rows = []
    for i, (t, v) in enumerate(cfgs()):
        rows.append(summ(t, v))
        if (i + 1) % 10 == 0:
            print(f"{i + 1}/{len(cfgs())}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(C.ROOT / "research_data" / "crude_round6.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(R[["id", "full_n", "full_pf", "full_net", "full_cnet", "tr_net", "ho_net", "ho_cnet", "full_dd"]].to_string(index=False))
