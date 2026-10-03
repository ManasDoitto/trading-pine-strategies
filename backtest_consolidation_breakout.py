"""4h consolidation -> quick momentum breakout. Pre-specified:
Consolidation = the previous N candles (largest N in 4..10 that qualifies) form a box with height <= K x ATR14 (K in {1.5, 2.5, 3.5}).
Signal = a 4h candle CLOSES beyond the box (long above / short below); enter at the next open.
Stop = box far side ('far') or box midpoint ('mid'); target = RR x risk (RR in {1.5, 3}); time stop 12 bars (2 days); skip if risk > 4 ATR.
Markets: BTC ETH SOL BNB XRP perps (0.07%/side + real funding) and XAUUSD (Dukascopy 4h, $1 round trip). Train <2023, test >=2023.
Control: same exits from RANDOM entry times/directions (count-matched) to show the no-edge baseline."""
from __future__ import annotations
import json, os, itertools
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__)); CRY = os.path.join(ROOT, "research_data", "crypto")
SPLIT = pd.Timestamp("2023-01-01"); MAXB = 12

def crypto_4h(sym):
    raw = json.load(open(os.path.join(CRY, f"{sym}usdt_perp_1h.json"))); d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
    for c in ("open", "high", "low", "close"): d[c] = d[c].astype(float)
    d["time"] = pd.to_datetime(d["t"], unit="ms"); d = d.set_index("time")
    b = d.resample("4h", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index()
    fr = pd.DataFrame(json.load(open(os.path.join(CRY, f"{sym}usdt_funding.json")))); ft = pd.to_datetime(fr["fundingTime"], unit="ms").to_numpy(); o = np.argsort(ft)
    return b, (ft[o], np.concatenate([[0.0], np.cumsum(fr["fundingRate"].astype(float).to_numpy()[o])]))

def gold_4h():
    d = pd.read_pickle(os.path.join(ROOT, "research_data", "gold", "xauusd_1m.pkl")); d["time"] = pd.to_datetime(d["time"]); d = d.set_index("time")
    return d.resample("4h", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index(), None

def atr14(d):
    pc = d["close"].shift(1); tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean()

def signals(d, K):
    h, l, c = d["high"], d["low"], d["close"]; atr = atr14(d).shift(1)
    bh = np.full(len(d), np.nan); bl = np.full(len(d), np.nan); bn = np.zeros(len(d), int)
    for N in range(10, 3, -1):                                        # largest qualifying N wins
        hh = h.rolling(N).max().shift(1); ll = l.rolling(N).min().shift(1); ok = ((hh - ll) <= K * atr) & hh.notna() & np.isnan(bh)
        bh = np.where(ok, hh, bh); bl = np.where(ok, ll, bl); bn = np.where(ok, N, bn)
    long_ = (c.to_numpy() > bh); short_ = (c.to_numpy() < bl)
    return long_ & ~short_, short_ & ~long_, bh, bl, bn, atr.to_numpy()

def simulate(d, fund, cost_fn, K, stop_mode, rr, rng=None, control_n=None):
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close")); t = d["time"].to_numpy(); n = len(d)
    L, S, bh, bl, bn, atr = signals(d, K)
    if control_n is not None:                                         # random entries with box-like stop (2 ATR) for the baseline
        idx = np.sort(rng.choice(np.arange(60, n - MAXB - 2), control_n, replace=False)); sig = idx
        side_ctrl = rng.choice([-1, 1], control_n)
    else:
        sig = np.flatnonzero(L | S); side_ctrl = None
    out = []; i_min = 60; k = 0
    while k < len(sig):
        i = int(sig[k])
        if i < i_min or i >= n - MAXB - 2: k += 1; continue
        if control_n is not None: side = int(side_ctrl[k]); risk = 2.0 * atr[i]; stop = o[i + 1] - side * risk
        else:
            side = 1 if L[i] else -1; mid = (bh[i] + bl[i]) / 2
            stop = (bl[i] if side == 1 else bh[i]) if stop_mode == "far" else mid
        j = i + 1; entry = o[j]; risk = abs(entry - stop)
        if not (risk > 0) or ((side == 1 and stop >= entry) or (side == -1 and stop <= entry)) or risk > 4 * atr[i]: k += 1; continue
        target = entry + side * rr * risk; e = j + MAXB
        if side == 1: hs, ht = l[j:e] <= stop, h[j:e] >= target
        else: hs, ht = h[j:e] >= stop, l[j:e] <= target
        hit = hs | ht
        if hit.any():
            m = int(np.argmax(hit)); kx = j + m; px = stop if hs[m] else target
            if m == 0 and ((side == 1 and entry <= stop) or (side == -1 and entry >= stop)): px = entry
        else: kx = e - 1; px = c[kx]
        fsum = 0.0
        if fund is not None: ft, fc = fund; fsum = fc[np.searchsorted(ft, t[kx], side="right")] - fc[np.searchsorted(ft, t[j], side="right")]
        out.append((t[j], t[kx], side, entry, px, risk, fsum, int(bn[i]) if control_n is None else 0))
        k = int(np.searchsorted(sig, kx + 1))
    tr = pd.DataFrame(out, columns=["entry_time", "exit_time", "side", "entry", "exit", "risk", "fund", "N"])
    if len(tr):
        g = tr["side"] * (tr["exit"] - tr["entry"]) / tr["risk"]; cs = cost_fn(tr)
        tr["gross_r"] = g.clip(-5, 10); tr["net_r"] = (g - cs / tr["risk"] - tr["side"] * tr["fund"] * tr["entry"] / tr["risk"]).clip(-5, 10)
    return tr

def tstat(x): return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 3 and x.std() > 0 else np.nan

if __name__ == "__main__":
    pd.set_option("display.width", 220)
    data = {s.upper(): crypto_4h(s) for s in ("btc", "eth", "sol", "bnb", "xrp")}
    cost_c = lambda tr: 2 * 0.0007 * tr["entry"]; cost_g = lambda tr: pd.Series(1.0, index=tr.index)
    gd = gold_4h(); data["XAU"] = gd
    costs = {k: (cost_g if k == "XAU" else cost_c) for k in data}
    print({k: f"{d[0].time.iloc[0].date()}..{len(d[0])} bars" for k, d in data.items()})
    res = {}
    for K, sm, rr in itertools.product((1.5, 2.5, 3.5), ("far", "mid"), (1.5, 3.0)):
        res[(K, sm, rr)] = {k: simulate(d[0], d[1], costs[k], K, sm, rr) for k, d in data.items()}
    rows = []
    for cfg, per in res.items():
        allt = pd.concat([t.assign(m=k) for k, t in per.items() if len(t)])
        tr, te = allt[allt.entry_time < SPLIT], allt[allt.entry_time >= SPLIT]
        rows.append(dict(K=cfg[0], stop=cfg[1], rr=cfg[2], n=len(allt), win=(allt.net_r > 0).mean(), gross=allt.gross_r.mean(), net=allt.net_r.mean(), t=tstat(allt.net_r),
                         n_tr=len(tr), R_tr=tr.net_r.mean(), n_te=len(te), R_te=te.net_r.mean(), t_te=tstat(te.net_r),
                         pos_mk=sum((per[k].net_r.mean() > 0) for k in per if len(per[k]) > 5)))
    R = pd.DataFrame(rows); print("\nPOOLED over 6 markets (BTC ETH SOL BNB XRP XAU), all 12 pre-set configs:"); print(R.round(3).to_string(index=False))
    print(f"\nconfigs with positive TEST net R: {(R.R_te>0).sum()}/12 ; positive TRAIN: {(R.R_tr>0).sum()}/12 ; both: {((R.R_te>0)&(R.R_tr>0)).sum()}/12")
    b = R.sort_values("R_tr", ascending=False).iloc[0]; print(f"train-best config K={b.K} stop={b.stop} rr={b.rr}: train {b.R_tr:+.3f} -> TEST {b.R_te:+.3f} (t={b.t_te:.1f}, n={int(b.n_te)})")
    # per-market for main config
    main = res[(2.5, "far", 1.5)]; print("\nMain config (K=2.5, far stop, RR1.5) per market:")
    for k, t in main.items():
        te = t[t.entry_time >= SPLIT]
        print(f"  {k:4} n={len(t):4} win={(t.net_r>0).mean():.0%} gross={t.gross_r.mean():+.3f} net={t.net_r.mean():+.3f} (t={tstat(t.net_r):.1f}) | test n={len(te)} net={te.net_r.mean():+.3f} | long {t[t.side==1].net_r.mean():+.2f} short {t[t.side==-1].net_r.mean():+.2f} | avg N={t.N.mean():.1f} | /yr {len(t)/((t.entry_time.max()-t.entry_time.min()).days/365.25):.0f}")
    # control
    rng = np.random.default_rng(3); ctrl = []
    for k, d in data.items():
        n_sig = len(main[k]);
        if n_sig > 5: ctrl.append(simulate(d[0], d[1], costs[k], 2.5, "far", 1.5, rng=rng, control_n=n_sig))
    ca = pd.concat(ctrl); ma = pd.concat([t for t in main.values() if len(t)])
    print(f"\nCONTROL random entries (same count, 2xATR stop, RR1.5): net {ca.net_r.mean():+.3f} gross {ca.gross_r.mean():+.3f}  vs breakout main: net {ma.net_r.mean():+.3f} gross {ma.gross_r.mean():+.3f}")
    ma["N_bucket"] = pd.cut(ma.N, [3, 5, 7, 10]); print("net R by consolidation length N (main config):", ma.groupby("N_bucket", observed=True).net_r.agg(["count", "mean"]).round(3).to_dict("index"))
