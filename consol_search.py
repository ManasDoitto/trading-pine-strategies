"""Honest large-scale tweak search for the 4h consolidation-breakout strategy (crypto: BTC ETH SOL BNB XRP).
Search space (random 100k draws from ~3e8 combos): box tightness K, stop mode, RR, hold limit, trend EMA span/strength, ADX gate,
breakout-candle body/range/close-position, volume expansion, aligned prior impulse, direction, min box length, hour-of-day mode.
Protocol: TRAIN entries < 2022-01-01 | VALIDATION 2022-01-01..2024-06-30 | HOLDOUT >= 2024-07-01 (never used for selection).
A NULL search (same 100k combos on outcome-shuffled data) shows what pure luck produces. Costs 0.07%/side + real funding."""
from __future__ import annotations
import json, os, sys, time
import numpy as np, pandas as pd
from numba import njit, prange

ROOT = os.path.dirname(os.path.abspath(__file__)); CRY = os.path.join(ROOT, "research_data", "crypto")
KS = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 3.5]); RRS = np.array([1.5, 2.0, 3.0, 4.0]); HOLDS = np.array([6, 12, 18]); SPANS = [60, 120, 240]
T1 = pd.Timestamp("2022-01-01").value; T2 = pd.Timestamp("2024-07-01").value
NO = 24                                                    # (stop 2) x (rr 4) x (hold 3)

def load4h(sym):
    raw = json.load(open(os.path.join(CRY, f"{sym}usdt_perp_1h.json"))); d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
    for c in ("open", "high", "low", "close", "v"): d[c] = d[c].astype(float)
    d["time"] = pd.to_datetime(d["t"], unit="ms"); d = d.set_index("time")
    b = d.resample("4h", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "v": "sum"}).dropna().reset_index()
    fr = pd.DataFrame(json.load(open(os.path.join(CRY, f"{sym}usdt_funding.json")))); ft = pd.to_datetime(fr["fundingTime"], unit="ms").to_numpy(); o = np.argsort(ft)
    return b, (ft[o], np.concatenate([[0.0], np.cumsum(fr["fundingRate"].astype(float).to_numpy()[o])]))

def gold4h():
    d = pd.read_pickle(os.path.join(ROOT, "research_data", "gold", "xauusd_1m.pkl")); d["time"] = pd.to_datetime(d["time"]); d = d.set_index("time")
    b = d.resample("4h", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna().reset_index().rename(columns={"volume": "v"})
    return b, None

def adx14(d):
    h, l, c = d["high"], d["low"], d["close"]; up, dn = h.diff(), -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = c.shift(1); tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1); w = lambda s: s.ewm(alpha=1 / 14, adjust=False).mean()
    atr = w(tr); p = 100 * w(pd.Series(pdm, index=d.index)) / atr; m = 100 * w(pd.Series(mdm, index=d.index)) / atr
    return 100 * w((p - m).abs() / (p + m).replace(0, np.nan))

@njit(cache=True)
def scan(o, h, l, c, idx, side, stop, rr, hold, atr):
    n = len(idx); exk = np.zeros(n, np.int64); g = np.full(n, np.nan); rk = np.zeros(n); en = np.zeros(n)
    for q in range(n):
        i = idx[q]; j = i + 1; e = o[j]; s = side[q]; st = stop[q]; risk = abs(e - st)
        en[q] = e; rk[q] = risk
        if not (risk > 0) or (s == 1 and st >= e) or (s == -1 and st <= e) or risk > 4.0 * atr[i]:
            exk[q] = j; continue
        tgt = e + s * rr * risk; kx = j + hold - 1; px = c[kx]
        for k in range(j, j + hold):
            hs = (l[k] <= st) if s == 1 else (h[k] >= st); ht = (h[k] >= tgt) if s == 1 else (l[k] <= tgt)
            if hs or ht:
                kx = k; px = st if hs else tgt
                if k == j and ((s == 1 and e <= st) or (s == -1 and e >= st)): px = e
                break
        exk[q] = kx; g[q] = s * (px - e) / risk
    return exk, g, rk, en

def build(markets, cost_fn):
    """-> dict of concatenated per-K signal feature arrays + outcome arrays (R, exit_time)."""
    per_k = {k: [] for k in range(len(KS))}
    for mi, (name, (d, fund)) in enumerate(markets.items()):
        o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close")); t = d["time"].to_numpy(); n = len(d); tv = t.astype("datetime64[ns]").astype(np.int64)
        pc = d["close"].shift(1); tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy(); atrp = np.r_[np.nan, atr[:-1]]
        ema = [d["close"].ewm(span=s, adjust=False).mean().to_numpy() for s in SPANS]
        adxp = np.r_[np.nan, adx14(d).to_numpy()[:-1]]; v = d["v"].to_numpy(float); vm = pd.Series(v).rolling(20).mean().shift(1).to_numpy(); volx = np.where(vm > 0, v / vm, 1.0)
        body = np.abs(c - o) / np.maximum(h - l, 1e-12); rng = (h - l) / atrp; hour = ((pd.DatetimeIndex(d["time"]).hour) // 4).to_numpy()
        for ki, K in enumerate(KS):
            hh = np.full(n, np.nan); ll = np.full(n, np.nan); bn = np.zeros(n, int)
            for N in range(10, 3, -1):
                H = pd.Series(h).rolling(N).max().shift(1).to_numpy(); Lo = pd.Series(l).rolling(N).min().shift(1).to_numpy()
                ok = ((H - Lo) <= K * atrp) & ~np.isnan(H) & np.isnan(hh); hh = np.where(ok, H, hh); ll = np.where(ok, Lo, ll); bn = np.where(ok, N, bn)
            lg = c > hh; sh = c < ll; idx = np.flatnonzero((lg ^ sh) & (np.arange(n) >= 60) & (np.arange(n) < n - 25) & ~np.isnan(hh)); side = np.where(c[idx] > hh[idx], 1, -1).astype(np.int64)
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
                        cs = cost_fn(en)                                               # cost in price units for the round trip
                        fs = np.zeros(len(idx))
                        if fund is not None:
                            ft, fc = fund; fs = fc[np.searchsorted(ft, t[exk], side="right")] - fc[np.searchsorted(ft, t[idx + 1], side="right")]
                        net = g - cs / rk - side * fs * en / rk; col = (st * 4 + ri) * 3 + hi
                        R[:, col] = np.clip(net, -5, 10); X[:, col] = tv[exk]
            good = ~np.isnan(adxp[idx]) & ~np.isnan(rng[idx]) & ~np.isnan(dist).any(axis=1)
            per_k[ki].append(dict(mid=np.full(len(idx), mi), side=side, et=tv[idx + 1], nbox=bn[idx], body=body[idx], rng=rng[idx], cpos=cpos, volx=volx[idx], dist=dist,
                                  adx=adxp[idx], imp=imp, hour=hour[idx], R=R, X=X, good=good))
    out = {}; offs = []; lens = []; cat = {k: [] for k in ("mid", "side", "et", "nbox", "body", "rng", "cpos", "volx", "dist", "adx", "imp", "hour", "R", "X")}; pos = 0
    for ki in range(len(KS)):
        parts = per_k[ki]; sel = [p["good"] for p in parts]; ln = 0
        for key in cat: cat[key].append(np.concatenate([p[key][g] for p, g in zip(parts, sel)]));
        ln = sum(int(g.sum()) for g in sel); offs.append(pos); lens.append(ln); pos += ln
    for key in cat: out[key] = np.concatenate(cat[key])
    out["offs"] = np.array(offs, np.int64); out["lens"] = np.array(lens, np.int64); return out

@njit(parallel=True, cache=True)
def search(P, offs, lens, mid, side, et, nbox, body, rng, cpos, volx, dist, adx, imp, hour, R, X, t1, t2):
    nc = P.shape[0]; out = np.zeros((nc, 3, 3))
    for c in prange(nc):
        p = P[c]; k = int(p[0]); st = int(p[1]); ri = int(p[2]); hi = int(p[3]); ema = int(p[4]); strength = p[5]; adxm = p[6]; bm = p[7]; rm = p[8]
        cm = p[9]; vm = p[10]; im = p[11]; dr = int(p[12]); nmin = int(p[13]); hm = int(p[14]); o24 = (st * 4 + ri) * 3 + hi
        off = offs[k]; ln = lens[k]; last = -9223372036854775807; cur = -1
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
            out[c, per, 0] += 1.0; out[c, per, 1] += r; out[c, per, 2] += r * r; last = X[i, o24]
    return out

SPACE = dict(k=range(6), stop=range(2), rr=range(4), hold=range(3), ema=range(4), strength=[0, .5, 1.0, 2.0], adx=[0, 20, 25, 30], body=[0, .5, .6, .7, .8], rngm=[0, .8, 1.0, 1.3, 1.6],
             cpos=[0, .7, .8], vol=[0, 1.2, 1.5, 2.0], imp=[-99, 0, 2, 4], dr=[0, 1, -1], nmin=[4, 6, 8], hour=[0, 1, 2])
def draw(n, rng):
    return np.stack([rng.choice(np.array(list(v), float), n) for v in SPACE.values()], axis=1)

ARGS = ("offs", "lens", "mid", "side", "et", "nbox", "body", "rng", "cpos", "volx", "dist", "adx", "imp", "hour")
def run(P, D, Rover=None):
    return search(P, *[D[a] for a in ARGS], D["R"] if Rover is None else Rover, D["X"], T1, T2)

def summarize(S):
    n = S[:, :, 0]; mean = np.divide(S[:, :, 1], n, out=np.full_like(n, np.nan), where=n > 0)
    var = np.divide(S[:, :, 2], n, out=np.zeros_like(n), where=n > 0) - mean ** 2; t = mean / np.sqrt(np.maximum(var, 1e-12) / np.maximum(n, 1))
    return n, mean, t

def null_R(D, rng):
    R = D["R"].copy()
    for k in range(len(KS)):
        sl = slice(int(D["offs"][k]), int(D["offs"][k] + D["lens"][k]))
        for o in range(NO):
            col = R[sl, o]; ok = ~np.isnan(col); vals = col[ok]; rng.shuffle(vals); col[ok] = vals; R[sl, o] = col
    return R
