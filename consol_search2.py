"""1M-combination search across ALL available data, with luck calibration and marginal-effect analysis.

Markets: BTC ETH SOL BNB XRP (perps, 0.07%/side + real funding), XAUUSD (Dukascopy, $1 round trip),
NIFTY BANKNIFTY (0.02%/side), CRUDEOIL SILVERM (0.03%/0.05%/side). Timeframes 1h and 4h.
Protocol unchanged: TRAIN < 2022-01-01 | VALIDATION 2022-01-01..2024-06-30 | HOLDOUT >= 2024-07-01 (never used to select).

The point of a search this size is NOT to find the best combo (that is guaranteed to be a mirage -- see the null run).
It is to measure the MARGINAL effect of each parameter value, averaged over tens of thousands of combos, where luck cancels.
"""
from __future__ import annotations
import json, os
import numpy as np, pandas as pd
from numba import njit, prange
import consol_search as S1
from consol_search import KS, RRS, HOLDS, SPANS, NO, T1, T2, scan, adx14, SPACE, draw, summarize

ROOT = os.path.dirname(os.path.abspath(__file__)); BARS = os.path.join(ROOT, "research_data", "bars")
PCT = lambda p: (lambda en: 2 * p * en)
FLAT = lambda x: (lambda en: np.full_like(en, x))

def _resample(d, rule):
    r = (d.set_index("time").resample(rule, label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last", "v": "sum"}).dropna().reset_index())
    return r

def nse_mcx(fname):
    d = pd.read_csv(os.path.join(BARS, fname)); d["time"] = pd.to_datetime(d["time"], unit="s") + pd.Timedelta(hours=5, minutes=30)
    d = d.rename(columns={"volume": "v"})[["time", "open", "high", "low", "close", "v"]]
    return d.sort_values("time").reset_index(drop=True)

def all_markets(tf):
    """-> dict name -> (bars, funding, cost_fn). tf in {'1h','4h'}."""
    rule = {"1h": "60min", "4h": "4h"}[tf]; out = {}
    for s in ("btc", "eth", "sol", "bnb", "xrp"):
        raw = json.load(open(os.path.join(ROOT, "research_data", "crypto", f"{s}usdt_perp_1h.json")))
        d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
        for c in ("open", "high", "low", "close", "v"): d[c] = d[c].astype(float)
        d["time"] = pd.to_datetime(d["t"], unit="ms"); d = d[["time", "open", "high", "low", "close", "v"]]
        fr = pd.DataFrame(json.load(open(os.path.join(ROOT, "research_data", "crypto", f"{s}usdt_funding.json"))))
        ft = pd.to_datetime(fr["fundingTime"], unit="ms").to_numpy(); o = np.argsort(ft)
        fund = (ft[o], np.concatenate([[0.0], np.cumsum(fr["fundingRate"].astype(float).to_numpy()[o])]))
        out[s.upper()] = (_resample(d, rule) if tf == "4h" else d.reset_index(drop=True), fund, PCT(0.0007))
    g = pd.read_pickle(os.path.join(ROOT, "research_data", "gold", "xauusd_1m.pkl")); g["time"] = pd.to_datetime(g["time"]); g = g.rename(columns={"volume": "v"})
    out["XAU"] = (_resample(g[["time", "open", "high", "low", "close", "v"]], rule), None, FLAT(1.0))
    for nm, f, cost in (("NIFTY", "DHAN_NIFTY_5m.csv", 0.0002), ("BANKNIFTY", "DHAN_BANKNIFTY_5m.csv", 0.0002),
                        ("CRUDE", "MCX_CRUDEOIL1_5m.csv", 0.0003), ("SILVERM", "MCX_SILVERM1_5m.csv", 0.0005)):
        out[nm] = (_resample(nse_mcx(f), rule), None, PCT(cost))
    return out

def build_multi(markets):
    """Same feature/outcome layout as consol_search.build but per-market cost functions and a market index."""
    per_k = {k: [] for k in range(len(KS))}
    for mi, (name, (d, fund, cost_fn)) in enumerate(markets.items()):
        o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close")); t = d["time"].to_numpy(); n = len(d)
        if n < 400: continue
        tv = t.astype("datetime64[ns]").astype(np.int64)
        pc = d["close"].shift(1); tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy(); atrp = np.r_[np.nan, atr[:-1]]
        ema = [d["close"].ewm(span=s, adjust=False).mean().to_numpy() for s in SPANS]
        adxp = np.r_[np.nan, adx14(d).to_numpy()[:-1]]
        v = d["v"].to_numpy(float); vm = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
        volx = np.where((vm > 0) & np.isfinite(vm), v / np.maximum(vm, 1e-12), 1.0)
        body = np.abs(c - o) / np.maximum(h - l, 1e-12); rng = (h - l) / atrp
        hour = (pd.DatetimeIndex(d["time"]).hour // 4).to_numpy()
        for ki, K in enumerate(KS):
            hh = np.full(n, np.nan); ll = np.full(n, np.nan); bn = np.zeros(n, int)
            for N in range(10, 3, -1):
                H = pd.Series(h).rolling(N).max().shift(1).to_numpy(); Lo = pd.Series(l).rolling(N).min().shift(1).to_numpy()
                ok = ((H - Lo) <= K * atrp) & ~np.isnan(H) & np.isnan(hh)
                hh = np.where(ok, H, hh); ll = np.where(ok, Lo, ll); bn = np.where(ok, N, bn)
            lg = c > hh; sh = c < ll
            idx = np.flatnonzero((lg ^ sh) & (np.arange(n) >= 60) & (np.arange(n) < n - 25) & ~np.isnan(hh))
            if len(idx) == 0: continue
            side = np.where(c[idx] > hh[idx], 1, -1).astype(np.int64)
            cpos = np.where(side == 1, (c[idx] - l[idx]) / np.maximum(h[idx] - l[idx], 1e-12), (h[idx] - c[idx]) / np.maximum(h[idx] - l[idx], 1e-12))
            dist = np.stack([side * (c[idx] - e[idx]) / atrp[idx] for e in ema], axis=1)
            bs = idx - bn[idx]; imp = np.full(len(idx), -99.0); okimp = bs - 11 >= 0
            imp[okimp] = side[okimp] * (c[bs[okimp] - 1] - c[bs[okimp] - 11]) / atrp[idx][okimp]
            stops = [np.where(side == 1, ll[idx], hh[idx]), (hh[idx] + ll[idx]) / 2.0]
            R = np.full((len(idx), NO), np.nan); X = np.zeros((len(idx), NO), np.int64)
            for st in range(2):
                for ri, rr in enumerate(RRS):
                    for hi, hold in enumerate(HOLDS):
                        exk, g, rk, en = scan(o, h, l, c, idx, side, stops[st], float(rr), int(hold), atrp)
                        cs = cost_fn(en); fs = np.zeros(len(idx))
                        if fund is not None:
                            ft, fc = fund
                            fs = fc[np.searchsorted(ft, t[exk], side="right")] - fc[np.searchsorted(ft, t[idx + 1], side="right")]
                        net = g - cs / np.maximum(rk, 1e-12) - side * fs * en / np.maximum(rk, 1e-12)
                        col = (st * 4 + ri) * 3 + hi
                        R[:, col] = np.clip(net, -5, 10); X[:, col] = tv[exk]
            good = ~np.isnan(adxp[idx]) & ~np.isnan(rng[idx]) & ~np.isnan(dist).any(axis=1)
            per_k[ki].append(dict(mid=np.full(len(idx), mi, np.int64), side=side, et=tv[idx + 1], nbox=bn[idx], body=body[idx], rng=rng[idx],
                                  cpos=cpos, volx=volx[idx], dist=dist, adx=adxp[idx], imp=imp, hour=hour[idx], R=R, X=X, good=good))
    keys = ("mid", "side", "et", "nbox", "body", "rng", "cpos", "volx", "dist", "adx", "imp", "hour", "R", "X")
    out = {k: [] for k in keys}; offs = []; lens = []; pos = 0
    for ki in range(len(KS)):
        parts = per_k[ki]
        if not parts: offs.append(pos); lens.append(0); continue
        sel = [p["good"] for p in parts]
        for k in keys: out[k].append(np.concatenate([p[k][g] for p, g in zip(parts, sel)]))
        ln = sum(int(g.sum()) for g in sel); offs.append(pos); lens.append(ln); pos += ln
    D = {k: np.concatenate(v) for k, v in out.items() if v}
    D["offs"] = np.array(offs, np.int64); D["lens"] = np.array(lens, np.int64); D["nmkt"] = len(markets)
    return D

@njit(parallel=True, cache=True)
def search_mkt(P, offs, lens, mid, side, et, nbox, body, rng, cpos, volx, dist, adx, imp, hour, R, X, t1, t2, nmkt):
    """Per-combo accumulators split by market AND period: out[c, market, period, (n, sum, sumsq)]."""
    nc = P.shape[0]; out = np.zeros((nc, nmkt, 3, 3))
    for c in prange(nc):
        p = P[c]; k = int(p[0]); st = int(p[1]); ri = int(p[2]); hi = int(p[3]); ema = int(p[4]); strength = p[5]; adxm = p[6]
        bm = p[7]; rm = p[8]; cm = p[9]; vm = p[10]; im = p[11]; dr = int(p[12]); nmin = int(p[13]); hm = int(p[14])
        o24 = (st * 4 + ri) * 3 + hi; off = offs[k]; ln = lens[k]; last = -9223372036854775807; cur = -1
        for ii in range(ln):
            i = off + ii
            if mid[i] != cur: cur = mid[i]; last = -9223372036854775807
            s = side[i]
            if dr != 0 and s != dr: continue
            if nbox[i] < nmin: continue
            r = R[i, o24]
            if np.isnan(r): continue
            if body[i] < bm or rng[i] < rm or cpos[i] < cm or volx[i] < vm or adx[i] < adxm: continue
            if ema > 0 and dist[i, ema - 1] <= strength: continue
            if im > -50.0 and imp[i] < im: continue
            if hm == 1 and hour[i] == 0: continue
            if hm == 2 and not (hour[i] == 2 or hour[i] == 3 or hour[i] == 4): continue
            e = et[i]
            if e <= last: continue
            per = 0 if e < t1 else (1 if e < t2 else 2)
            m = mid[i]
            out[c, m, per, 0] += 1.0; out[c, m, per, 1] += r; out[c, m, per, 2] += r * r
            last = X[i, o24]
    return out

ARGS = ("offs", "lens", "mid", "side", "et", "nbox", "body", "rng", "cpos", "volx", "dist", "adx", "imp", "hour")
def run_mkt(P, D, Rover=None, chunk=250_000):
    outs = []
    for a in range(0, len(P), chunk):
        outs.append(search_mkt(P[a:a + chunk], *[D[x] for x in ARGS], D["R"] if Rover is None else Rover, D["X"], T1, T2, D["nmkt"]))
    return np.concatenate(outs, axis=0)

def pooled(St):
    """market-summed -> (n, mean, t) per period."""
    A = St.sum(axis=1); n = A[:, :, 0]
    mean = np.divide(A[:, :, 1], n, out=np.full_like(n, np.nan), where=n > 0)
    var = np.divide(A[:, :, 2], n, out=np.zeros_like(n), where=n > 0) - mean ** 2
    return n, mean, mean / np.sqrt(np.maximum(var, 1e-12) / np.maximum(n, 1))

def null_R(D, rng):
    R = D["R"].copy()
    for k in range(len(KS)):
        sl = slice(int(D["offs"][k]), int(D["offs"][k] + D["lens"][k]))
        if sl.stop <= sl.start: continue
        for o in range(NO):
            col = R[sl, o]; ok = ~np.isnan(col); vals = col[ok].copy(); rng.shuffle(vals); col[ok] = vals; R[sl, o] = col
    return R
