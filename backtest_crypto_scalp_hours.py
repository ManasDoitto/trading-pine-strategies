"""Does ANY time of day give a profitable crypto scalp? Honest test.

1. Descriptive: per UTC hour, how big is the typical 5m range vs the round-trip cost, and
   does the hour's behaviour (momentum vs reversal) persist between TRAIN (2020-2022) and
   TEST (2023-2026)? A real intraday seasonality must persist; a lucky hour will not.
2. Two simple, pre-specified scalp rules run on all 24h with every trade tagged by entry UTC
   hour: Donchian breakout (N=12, N=36 bars) and RSI(14) extreme fade. ATR stop, fixed RR,
   2h time stop. Per-hour net R in train vs test, rank-correlation across hours, and what the
   train-best hours did in test.
Costs: scenario T = 0.07%/side (taker fee + slippage); scenario M = 0.03%/side (optimistic
maker-ish). Funding ignored (holds <= 2h).
"""
from __future__ import annotations
import os, sys
import numpy as np, pandas as pd
from backtest_btc_perp_trend import load_klines, DATA_DIR

TRAIN_END = pd.Timestamp("2023-01-01")
COSTS = {"T 0.07%/side": 0.0007, "M 0.03%/side": 0.0003}


def load5(sym):
    k = load_klines(os.path.join(DATA_DIR, f"{sym}_perp_5m.json"))
    df = k.rename(columns={"dt": "time"})[["time", "open", "high", "low", "close", "volume"]].copy()
    df["time"] = df["time"].dt.tz_localize(None)
    return df.reset_index(drop=True)


def atr14(df):
    pc = df["close"].shift(1)
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean()


def rsi14(c):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def sim(df, sig_l, sig_s, k_stop, rr, max_bars):
    o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
    atr = atr14(df).to_numpy(); t = df["time"].to_numpy(); n = len(df)
    idx = np.flatnonzero(sig_l | sig_s); out = []; i = 300
    while True:
        p = np.searchsorted(idx, i)
        if p >= len(idx): break
        i = int(idx[p])
        if i + max_bars + 2 >= n: break
        side = 1 if sig_l[i] else -1
        risk = k_stop * atr[i]; j = i + 1; ent = o[j]
        sl, tp = ent - side * risk, ent + side * rr * risk
        e = j + max_bars
        if side == 1: hs, ht = l[j:e] <= sl, h[j:e] >= tp
        else: hs, ht = h[j:e] >= sl, l[j:e] <= tp
        hit = hs | ht
        if hit.any():
            m = int(np.argmax(hit)); px = sl if hs[m] else tp; kx = j + m
        else:
            px = c[e - 1]; kx = e - 1
        out.append((t[j], side, ent, side * (px - ent) / risk, risk / ent))
        i = kx
    return pd.DataFrame(out, columns=["time", "side", "entry", "gross_r", "stop_pct"])


def prep(df):
    c = df["close"]; a = atr14(df); r = rsi14(c)
    s = {}
    for n in (12, 36):
        hi = df["high"].rolling(n).max().shift(1); lo = df["low"].rolling(n).min().shift(1)
        s[f"breakout N={n}"] = ((c > hi).to_numpy(), (c < lo).to_numpy(), 1.5, 1.5, 24)
    s["RSI fade 20/80"] = ((r < 20).to_numpy(), (r > 80).to_numpy(), 1.5, 1.0, 12)
    return s


def net(tr, cost):
    return tr["gross_r"] - 2 * cost / tr["stop_pct"]


def main(sym="btcusdt"):
    df = load5(sym)
    print(f"{sym}: {len(df)} 5m bars {df.time.iloc[0].date()}..{df.time.iloc[-1].date()}")
    # ---- 1. descriptive per hour
    df["hr"] = df.time.dt.hour; df["rng"] = (df.high - df.low) / df.open
    df["ret"] = df.close.pct_change()
    tr_m = df.time < TRAIN_END
    desc = pd.DataFrame({
        "rng5m%_train": df[tr_m].groupby("hr").rng.mean() * 100,
        "rng5m%_test": df[~tr_m].groupby("hr").rng.mean() * 100})
    print("\nMean 5m high-low range by UTC hour (%), vs round-trip cost 0.14% (taker):")
    print(desc.round(3).T.to_string())
    rc = desc.corr(method="spearman").iloc[0, 1]
    print(f"rank-corr of hourly volatility profile train vs test: {rc:+.2f}  (volatility seasonality IS persistent if high)")
    # lag-1 autocorr of 5m returns by hour
    def ac(x): return x.ret.autocorr(1) if len(x) > 50 else np.nan
    a_tr = df[tr_m].groupby("hr").apply(ac); a_te = df[~tr_m].groupby("hr").apply(ac)
    print(f"rank-corr of hourly return autocorr (momentum/reversal) train vs test: {pd.concat([a_tr,a_te],axis=1).corr(method='spearman').iloc[0,1]:+.2f}")
    # ---- 2. strategies
    for name, (sl_, ss_, k, rr, mb) in prep(df).items():
        tr = sim(df, sl_, ss_, k, rr, mb)
        tr["hr"] = pd.to_datetime(tr.time).dt.hour; tr["train"] = pd.to_datetime(tr.time) < TRAIN_END
        print(f"\n=== {name} (stop {k}xATR, RR {rr}, time stop {mb} bars): {len(tr)} trades, median stop {tr.stop_pct.median()*100:.2f}% of price ===")
        print(f"gross R/trade: train {tr[tr.train].gross_r.mean():+.3f}  test {tr[~tr.train].gross_r.mean():+.3f}")
        for cn, c in COSTS.items():
            tr["net"] = net(tr, c)
            g = tr.groupby(["hr", "train"]).net.mean().unstack()
            gg = tr.groupby(["hr", "train"]).gross_r.mean().unstack()
            rc = gg.corr(method="spearman").iloc[0, 1]
            top = g[True].sort_values(ascending=False).head(3).index.tolist()
            print(f"  [{cn}] net R/trade train {tr[tr.train].net.mean():+.3f} test {tr[~tr.train].net.mean():+.3f} | "
                  f"hours with positive TEST net R: {(g[False]>0).sum()}/24 | gross-R hourly rank-corr train vs test {rc:+.2f}")
            print(f"      top-3 TRAIN hours {top}: train {g.loc[top,True].round(3).tolist()} -> TEST {g.loc[top,False].round(3).tolist()}")
            if cn.startswith("T"):
                best_test = g[False].sort_values(ascending=False).head(3)
                print(f"      (hindsight) best TEST hours {best_test.index.tolist()}: {best_test.round(3).tolist()}  <- would be expected by chance among 24")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "btcusdt")
