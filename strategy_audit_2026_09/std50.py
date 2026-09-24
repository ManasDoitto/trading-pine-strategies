"""The 50 standard intraday strategies of pre_registration_std50_2026_09_25.md. Entry rules only; all share one exit template."""
import numpy as np
import pandas as pd
from trading_agents.core.signals import ema, wilder, true_range


def sma(s, n): return s.rolling(n).mean()
def up(a, b): return (a > b) & (a.shift() <= b.shift())
def dn(a, b): return (a < b) & (a.shift() >= b.shift())
def const(d, x): return pd.Series(float(x), index=d.index)
def rsi(c, n):
    d = c.diff()
    return 100 - 100 / (1 + wilder(d.clip(lower=0), n) / wilder((-d).clip(lower=0), n).replace(0, np.nan))


def prep(df):
    d = df.reset_index(drop=True).copy()
    d["date"] = d["time"].dt.date
    d["idx"] = d.groupby("date").cumcount()
    d["minute"] = d["time"].dt.hour * 60 + d["time"].dt.minute
    d["atr"] = wilder(true_range(d["high"], d["low"], d["close"]), 14)
    g = d.groupby("date")
    d["day_open"] = g["open"].transform("first")
    day = g.agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    prev = day.shift(1)
    for k in ("h", "l", "c"):
        d["p" + k] = d["date"].map(prev[k])
    tp = (d.high + d.low + d.close) / 3
    v = d.volume.where(d.volume > 0, 1.0)
    d["vwap"] = (tp * v).groupby(d["date"]).cumsum() / v.groupby(d["date"]).cumsum()
    d["gap"] = d["day_open"] / d["pc"] - 1
    return d


def orb(d, bars):
    m = d.idx < bars
    hi = d.high.where(m).groupby(d.date).transform("max")
    lo = d.low.where(m).groupby(d.date).transform("min")
    return hi, lo, d.idx >= bars


def supertrend(d, n, mult):
    hl2 = (d.high + d.low) / 2
    ub, lb = (hl2 + mult * d.atr).to_numpy(), (hl2 - mult * d.atr).to_numpy()
    c = d.close.to_numpy()
    fu, fl = ub.copy(), lb.copy()
    tr = np.ones(len(d), bool)
    for i in range(1, len(d)):
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        tr[i] = True if c[i] > fu[i - 1] else False if c[i] < fl[i - 1] else tr[i - 1]
    t = pd.Series(tr.astype(int), index=d.index)
    return up(t, const(d, .5)), dn(t, const(d, .5))


def psar(d, af0=.02, afm=.2):
    h, l = d.high.to_numpy(), d.low.to_numpy()
    n = len(d)
    sar = np.zeros(n)
    bull = np.ones(n, bool)
    ep, af = h[0], af0
    sar[0] = l[0]
    for i in range(1, n):
        s, b = sar[i - 1] + af * (ep - sar[i - 1]), bull[i - 1]
        if b:
            s = min(s, l[i - 1], l[max(i - 2, 0)])
            if l[i] < s:
                b, s, ep, af = False, ep, l[i], af0
            elif h[i] > ep:
                ep, af = h[i], min(af + af0, afm)
        else:
            s = max(s, h[i - 1], h[max(i - 2, 0)])
            if h[i] > s:
                b, s, ep, af = True, ep, h[i], af0
            elif l[i] < ep:
                ep, af = l[i], min(af + af0, afm)
        sar[i], bull[i] = s, b
    t = pd.Series(bull.astype(int), index=d.index)
    return up(t, const(d, .5)), dn(t, const(d, .5))


def adx(d, n=14):
    upm, dnm = d.high.diff(), -d.low.diff()
    pdm = pd.Series(np.where((upm > dnm) & (upm > 0), upm, 0.0), index=d.index)
    mdm = pd.Series(np.where((dnm > upm) & (dnm > 0), dnm, 0.0), index=d.index)
    pdi, mdi = 100 * wilder(pdm, n) / d.atr, 100 * wilder(mdm, n) / d.atr
    return wilder(100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan), n), pdi, mdi


def S(d):
    """{id: (name, long_series, short_series)}, signals evaluated on the closed bar."""
    c, o, h, l, v, a = d.close, d.open, d.high, d.low, d.volume, d.atr
    out = {}

    def add(i, name, L, Sh):
        out[i] = (name, L.fillna(False).astype(bool), Sh.fillna(False).astype(bool))

    e = {n: ema(c, n) for n in (5, 8, 9, 13, 20, 21, 50, 55, 200)}
    z = const(d, 0)
    add(1, "EMA 9/21 cross", up(e[9], e[21]), dn(e[9], e[21]))
    add(2, "EMA 20/50 cross", up(e[20], e[50]), dn(e[20], e[50]))
    add(3, "EMA 5/13 cross", up(e[5], e[13]), dn(e[5], e[13]))
    add(4, "close x EMA200", up(c, e[200]), dn(c, e[200]))
    add(5, "EMA8x21 with 21 vs 55", up(e[8], e[21]) & (e[21] > e[55]), dn(e[8], e[21]) & (e[21] < e[55]))
    s10, s30 = sma(c, 10), sma(c, 30)
    add(6, "SMA 10/30 cross", up(s10, s30), dn(s10, s30))
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    add(7, "MACD signal cross", up(macd, sig), dn(macd, sig))
    add(8, "MACD zero cross", up(macd, z), dn(macd, z))
    add(9, "Supertrend 10,3", *supertrend(d, 10, 3))
    add(10, "Supertrend 7,2", *supertrend(d, 7, 2))
    ad, pdi, mdi = adx(d)
    add(11, "ADX>25 DI cross", up(pdi, mdi) & (ad > 25), dn(pdi, mdi) & (ad > 25))
    add(12, "Parabolic SAR flip", *psar(d))
    ten = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kij = (h.rolling(26).max() + l.rolling(26).min()) / 2
    add(13, "Ichimoku TK cross", up(ten, kij), dn(ten, kij))
    hac = (o + h + l + c) / 4
    hao = ((o + c) / 2).shift().combine_first(o)
    hag = hac > hao
    flip_g = hag & ~hag.shift(fill_value=False)
    flip_r = ~hag & hag.shift(fill_value=True)
    add(14, "Heikin-Ashi flip + confirm", flip_g.shift(fill_value=False) & hag, flip_r.shift(fill_value=False) & ~hag)
    add(15, "Donchian 20", c > h.shift().rolling(20).max(), c < l.shift().rolling(20).min())
    add(16, "Donchian 55", c > h.shift().rolling(55).max(), c < l.shift().rolling(55).min())
    add(17, "Keltner 20,1.5", up(c, e[20] + 1.5 * a), dn(c, e[20] - 1.5 * a))
    bm, bs = sma(c, 20), c.rolling(20).std()
    bu, bl = bm + 2 * bs, bm - 2 * bs
    add(18, "Bollinger breakout", up(c, bu), dn(c, bl))
    bw = (bu - bl) / bm
    sq = (bw <= bw.rolling(100).quantile(.2)).shift(fill_value=False)
    add(19, "Bollinger squeeze break", up(c, bu) & sq, dn(c, bl) & sq)
    add(20, "10-bar break + EMA50", (c > h.shift().rolling(10).max()) & (c > e[50]), (c < l.shift().rolling(10).min()) & (c < e[50]))
    r14 = rsi(c, 14)
    add(21, "RSI14 30/70 revert", up(r14, const(d, 30)), dn(r14, const(d, 70)))
    r2 = rsi(c, 2)
    add(22, "RSI2 with EMA200", (r2 < 10) & (c > e[200]), (r2 > 90) & (c < e[200]))
    add(23, "Bollinger revert", up(c, bl), dn(c, bu))
    lo14, hi14 = l.rolling(14).min(), h.rolling(14).max()
    k = sma(100 * (c - lo14) / (hi14 - lo14).replace(0, np.nan), 3)
    dd = sma(k, 3)
    add(24, "Stochastic 20/80 cross", up(k, dd) & (k < 20), dn(k, dd) & (k > 80))
    tpp = (h + l + c) / 3
    cci = (tpp - sma(tpp, 20)) / (0.015 * tpp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True))
    add(25, "CCI20 +-100 revert", up(cci, const(d, -100)), dn(cci, const(d, 100)))
    dev = (c - d.vwap) / a
    add(26, "VWAP 2.5ATR revert", (dev.shift() < -2.5) & (c > c.shift()), (dev.shift() > 2.5) & (c < c.shift()))
    wr = -100 * (hi14 - c) / (hi14 - lo14).replace(0, np.nan)
    add(27, "Williams %R revert", up(wr, const(d, -80)), dn(wr, const(d, -20)))
    s50 = e[50] > e[50].shift(3)
    add(28, "RSI 50 cross with EMA50 slope", up(r14, const(d, 50)) & s50, dn(r14, const(d, 50)) & ~s50)
    for i, bars, nm in ((29, 3, "ORB 15"), (30, 6, "ORB 30"), (31, 12, "ORB 60")):
        oh, ol, after = orb(d, bars)
        add(i, nm, after & up(c, oh), after & dn(c, ol))
    oh, ol, after = orb(d, 6)
    add(32, "ORB30 failed break fade", after & (h.shift() > oh) & (c < oh) & (c.shift() >= oh),
        after & (l.shift() < ol) & (c > ol) & (c.shift() <= ol))
    add(33, "close x VWAP", up(c, d.vwap), dn(c, d.vwap))
    add(34, "VWAP+EMA20 pullback", (c > d.vwap) & (c > e[20]) & (l <= e[20]), (c < d.vwap) & (c < e[20]) & (h >= e[20]))
    add(35, "prev-day H/L break", up(c, d.ph), dn(c, d.pl))
    pv = (d.ph + d.pl + d.pc) / 3
    add(36, "pivot R1/S1 break", up(c, 2 * pv - d.pl), dn(c, 2 * pv - d.ph))
    bc = (d.ph + d.pl) / 2
    tc = 2 * pv - bc
    cw = (tc - bc).abs() / c
    top, bot = np.maximum(tc, bc), np.minimum(tc, bc)
    add(37, "narrow CPR break", (cw < .0025) & up(c, top), (cw < .0025) & dn(c, bot))
    first = d.idx == 0
    add(38, "gap and go", first & (d.gap > .003) & (c > o), first & (d.gap < -.003) & (c < o))
    add(39, "gap fade", first & (d.gap > .003) & (c < o), first & (d.gap < -.003) & (c > o))
    ib = ((h < h.shift()) & (l > l.shift())).shift(fill_value=False)
    add(40, "inside bar break", ib & (c > h.shift()), ib & (c < l.shift()))
    rng = h - l
    nr = rng.shift() <= rng.shift().rolling(7).min()
    add(41, "NR7 break", nr & (c > h.shift()), nr & (c < l.shift()))
    body = (c - o).abs()
    add(42, "engulfing with EMA50 slope", (c > o) & (o.shift() > c.shift()) & (c > o.shift()) & (o < c.shift()) & s50,
        (c < o) & (c.shift() > o.shift()) & (c < o.shift()) & (o > c.shift()) & ~s50)
    uw, lw = h - np.maximum(o, c), np.minimum(o, c) - l
    add(43, "pin bar at 20-bar extreme", (lw >= 2 * body) & (l <= l.rolling(20).min()) & s50,
        (uw >= 2 * body) & (h >= h.rolling(20).max()) & ~s50)
    rv = (v > v.shift()) & (v.shift() > v.shift(2))
    add(44, "3 closes + rising volume", (c > c.shift()) & (c.shift() > c.shift(2)) & (c.shift(2) > c.shift(3)) & rv,
        (c < c.shift()) & (c.shift() < c.shift(2)) & (c.shift(2) < c.shift(3)) & rv)
    vs = v > 2 * sma(v, 20)
    add(45, "volume spike break", vs & (c > h.shift().rolling(5).max()), vs & (c < l.shift().rolling(5).min()))
    fh = (h.shift(2) > h.shift(3)) & (h.shift(2) > h.shift(1)) & (h.shift(2) > h.shift(4)) & (h.shift(2) > h)
    fl = (l.shift(2) < l.shift(3)) & (l.shift(2) < l.shift(1)) & (l.shift(2) < l.shift(4)) & (l.shift(2) < l)
    add(46, "fractal swing break", up(c, h.shift(2).where(fh).ffill()), dn(c, l.shift(2).where(fl).ffill()))
    f_hi = h.where(first).groupby(d.date).transform("max")
    f_lo = l.where(first).groupby(d.date).transform("min")
    add(47, "first-bar break", (d.idx >= 1) & up(c, f_hi), (d.idx >= 1) & dn(c, f_lo))
    mv, hr = c - d.day_open, d.idx == 11
    add(48, "60-min trend follow", hr & (mv > a), hr & (mv < -a))
    add(49, "2xATR range bar", (rng > 2 * a) & (c >= l + .75 * rng), (rng > 2 * a) & (c <= l + .25 * rng))
    roc = c.pct_change(10)
    add(50, "ROC10 zero cross + ADX", up(roc, z) & (ad > 20), dn(roc, z) & (ad > 20))
    return out
