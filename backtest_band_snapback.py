"""Dhan 'Band Snapback' (Bollinger Bands Made Simple, youtube.com/shorts/tqe8ANVnr6c) tested in parallel on
5 big crypto perps + Nifty + BankNifty + CrudeOil + SilverM.

What the Short says (formalised; it gives NO numeric rules or statistics): Bollinger Bands = 20-SMA middle band +/- 2 std;
price that becomes 'overstretched' outside the band is expected to snap back toward the 20 SMA; use the bands to find
entry, exit and stop-loss. Everything below fixes those choices in advance (no tuning):
  bands BB(20,2) on closes | target = 20 SMA at signal bar | stop = beyond the overstretched bar's extreme (+0.1 ATR)
  entry = next bar's open | time stop 10 bars | one position at a time | long (lower band) and short (upper band)
  variant I 'immediate fade': first close outside the band -> enter next open
  variant C 'confirmed snapback': a close back INSIDE the band after an outside close -> enter next open
Timeframes: daily (as in the video) and 1h. Costs per side by instrument; crypto also pays/receives real funding."""
from __future__ import annotations
import json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(ROOT, "research_data", "bars"); CRY = os.path.join(ROOT, "research_data", "crypto")
MAX_BARS = 10
COST = {"BTC": 0.0007, "ETH": 0.0007, "SOL": 0.0007, "BNB": 0.0007, "XRP": 0.0007,
        "NIFTY": 0.0002, "BANKNIFTY": 0.0002, "CRUDE": 0.0003, "SILVERM": 0.0005}

def load_csv_ist(name):
    d = pd.read_csv(os.path.join(BARS, name))
    d["time"] = pd.to_datetime(d["time"], unit="s") + pd.Timedelta(hours=5, minutes=30)
    return d[["time", "open", "high", "low", "close"]].sort_values("time").reset_index(drop=True)

def load_crypto(sym):
    raw = json.load(open(os.path.join(CRY, f"{sym.lower()}usdt_perp_1h.json")))
    d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
    for c in ("open", "high", "low", "close"): d[c] = d[c].astype(float)
    d["time"] = pd.to_datetime(d["t"], unit="ms")
    fr = pd.DataFrame(json.load(open(os.path.join(CRY, f"{sym.lower()}usdt_funding.json"))))
    ft = pd.to_datetime(fr["fundingTime"], unit="ms").to_numpy(); o = np.argsort(ft)
    fc = np.concatenate([[0.0], np.cumsum(fr["fundingRate"].astype(float).to_numpy()[o])])
    return d[["time", "open", "high", "low", "close"]], ft[o], fc

def agg(d, rule, offset=None):
    r = (d.set_index("time").resample(rule, label="left", closed="left", offset=offset)
         .agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index())
    return r

def daily(d):
    day = d["time"].dt.date
    g = d.groupby(day)
    r = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last()})
    r.index = pd.to_datetime(r.index); return r.reset_index().rename(columns={"index": "time"})

def frames(name):
    """-> {tf: df}, funding arrays (or None)."""
    fund = None
    if name in ("BTC", "ETH", "SOL", "BNB", "XRP"):
        h, ft, fc = load_crypto(name); fund = (ft, fc)
        return {"1H": h.reset_index(drop=True), "1D": agg(h, "1D")}, fund
    if name == "NIFTY": b = load_csv_ist("DHAN_NIFTY_5m.csv"); off = "15min"
    elif name == "BANKNIFTY": b = load_csv_ist("DHAN_BANKNIFTY_5m.csv"); off = "15min"
    elif name == "CRUDE": b = load_csv_ist("MCX_CRUDEOIL1_5m.csv"); off = None
    else: b = load_csv_ist("MCX_SILVERM1_5m.csv"); off = None
    return {"1H": agg(b, "60min", off), "1D": daily(b)}, fund

def signals(d, variant):
    c, h, l = d["close"], d["high"], d["low"]
    sma = c.rolling(20).mean(); sd = c.rolling(20).std(ddof=0); up, lo = sma + 2 * sd, sma - 2 * sd
    pc = c.shift(1); tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1); atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    if variant == "I":
        L = (c < lo) & (pc >= lo.shift(1)); S = (c > up) & (pc <= up.shift(1))
        stop_l = l - 0.1 * atr; stop_s = h + 0.1 * atr
    else:
        L = (c > lo) & (pc < lo.shift(1)); S = (c < up) & (pc > up.shift(1))
        stop_l = pd.concat([l, l.shift(1)], axis=1).min(axis=1) - 0.1 * atr
        stop_s = pd.concat([h, h.shift(1)], axis=1).max(axis=1) + 0.1 * atr
    L = L & (sma > c) & (c - stop_l > 0.2 * atr); S = S & (sma < c) & (stop_s - c > 0.2 * atr)
    return L.fillna(False).to_numpy(), S.fillna(False).to_numpy(), stop_l.to_numpy(), stop_s.to_numpy(), sma.to_numpy()

def simulate(d, variant, fund):
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close")); t = d["time"].to_numpy(); n = len(d)
    L, S, stop_l, stop_s, tgt = signals(d, variant); sig = np.flatnonzero(L | S); out = []; i = 30
    while True:
        p = np.searchsorted(sig, i)
        if p >= len(sig): break
        i = int(sig[p])
        if i >= n - 2: break
        side = 1 if L[i] else -1; stop = stop_l[i] if side == 1 else stop_s[i]; target = tgt[i]; j = i + 1; entry = o[j]
        if (side == 1 and not (stop < entry < target)) or (side == -1 and not (target < entry < stop)):
            i += 1; continue
        e = min(j + MAX_BARS, n)
        if side == 1: hs, ht = l[j:e] <= stop, h[j:e] >= target
        else: hs, ht = h[j:e] >= stop, l[j:e] <= target
        hit = hs | ht
        if hit.any():
            m = int(np.argmax(hit)); kx = j + m
            if hs[m]: px = stop; why = "SL"
            else: px = target; why = "TP"
            if m == 0:                                   # gap at the fill bar -> fill at the open
                if side == 1 and entry <= stop: px = entry
                if side == -1 and entry >= stop: px = entry
        else:
            kx = e - 1; px = c[kx]; why = "TIME"
        risk = abs(entry - stop)
        fsum = 0.0
        if fund is not None:
            ft, fc = fund; fsum = fc[np.searchsorted(ft, t[kx], side="right")] - fc[np.searchsorted(ft, t[j], side="right")]
        out.append((t[j], t[kx], side, entry, px, risk, fsum, kx - j + 1, why))
        i = kx
    return pd.DataFrame(out, columns=["entry_time", "exit_time", "side", "entry", "exit", "risk", "fund", "bars", "why"])

def finish(tr, cost):
    if len(tr) == 0: return tr
    g = (tr["side"] * (tr["exit"] - tr["entry"]) / tr["risk"])
    c = 2 * cost * tr["entry"] / tr["risk"]; f = tr["side"] * tr["fund"] * tr["entry"] / tr["risk"]
    tr = tr.copy(); tr["gross_r"] = g.clip(-5, 10); tr["net_r"] = (g - c - f).clip(-5, 10); return tr

def task(name):
    fr, fund = frames(name); res = {}
    for tf, d in fr.items():
        for v in ("I", "C"):
            res[(name, tf, v)] = finish(simulate(d, v, fund), COST[name])
    return name, res

def tstat(x): return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 3 and x.std() > 0 else np.nan

def report(allres):
    rows = []
    for (name, tf, v), t in allres.items():
        if len(t) < 5: rows.append(dict(inst=name, tf=tf, var=v, n=len(t))); continue
        yrs = (t.entry_time.max() - t.entry_time.min()).days / 365.25
        mid = t.entry_time.min() + (t.entry_time.max() - t.entry_time.min()) / 2
        rows.append(dict(inst=name, tf=tf, var=v, n=len(t), per_yr=len(t) / max(yrs, .1), win=(t.net_r > 0).mean(), gross=t.gross_r.mean(), net=t.net_r.mean(),
                         t=tstat(t.net_r), h1=t[t.entry_time < mid].net_r.mean(), h2=t[t.entry_time >= mid].net_r.mean(),
                         long=t[t.side == 1].net_r.mean(), short=t[t.side == -1].net_r.mean(), hold=t.bars.mean(), yrs=yrs))
    R = pd.DataFrame(rows)
    pd.set_option("display.width", 220); pd.set_option("display.max_rows", 200)
    for tf in ("1D", "1H"):
        for v, label in (("I", "IMMEDIATE fade (first close outside band)"), ("C", "CONFIRMED snapback (close back inside band)")):
            s = R[(R.tf == tf) & (R["var"] == v)].set_index("inst").reindex(list(COST))
            print(f"\n=== {tf} | {label} | costs/side: crypto 0.07%, idx 0.02%, crude 0.03%, silverM 0.05% ===")
            print(s[["n", "per_yr", "win", "gross", "net", "t", "h1", "h2", "long", "short", "hold", "yrs"]].round(3).to_string())
            ok = s.dropna(subset=["net"]); tot = sum(len(allres[(i, tf, v)]) for i in ok.index)
            pooled = pd.concat([allres[(i, tf, v)] for i in ok.index]);
            print(f"   POOLED {len(ok)} instruments: {tot} trades, net R {pooled.net_r.mean():+.3f} (t={tstat(pooled.net_r):.1f}), gross R {pooled.gross_r.mean():+.3f}; instruments net-positive: {(ok.net > 0).sum()}/{len(ok)}; both halves positive: {((ok.h1 > 0) & (ok.h2 > 0)).sum()}/{len(ok)}")
    R.to_csv(os.path.join(ROOT, "research_data", "band_snapback_table.csv"), index=False)

if __name__ == "__main__":
    t0 = time.time(); names = list(COST)
    allres = {}
    with ProcessPoolExecutor(4) as ex:
        for name, res in ex.map(task, names):
            allres.update(res); print(name, "done", f"{time.time()-t0:.0f}s", flush=True)
    import pickle; pickle.dump(allres, open(os.path.join(ROOT, "research_data", "band_snapback_trades.pkl"), "wb"))
    report(allres)
