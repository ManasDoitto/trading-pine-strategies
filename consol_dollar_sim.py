"""Dollar simulation for the winning consolidation-breakout config found in the 1M-combination search:
  box = largest qualifying N in 4..10 prior 4h candles, height <= 4x ATR14
  trend filter: price beyond its 240-candle EMA in the breakout direction
  trigger: candle closes beyond the box, body >= 50% of its range, volume >= 1.2x its 20-candle average
  entry: next open | stop: box far side | target: 3x risk | time stop: 12 candles (2 days on 4h)
Markets: BTC ETH SOL BNB XRP (perps) + XAU CRUDE SILVERM (BTC shown separately -- holdout was negative there).
Real trade-level extraction (not the aggregated search table), so this is a proper path-dependent, compounding,
multi-market portfolio simulation: 1% risk per trade, capped at 6% total open risk, first-come when the cap binds.
"""
from __future__ import annotations
import json, os
import numpy as np, pandas as pd
import consol_search2 as S2
from consol_search import KS, RRS, HOLDS, SPANS

ROOT = os.path.dirname(os.path.abspath(__file__))
K, STOP, RR, HOLD, EMA_SPAN, BODY_MIN, VOL_MIN = 4.0, "far", 3.0, HOLDS[1], 240, 0.5, 1.2

def atr14(d):
    pc = d["close"].shift(1); tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean()

def extract_trades(d, fund, cost_fn):
    o, h, l, c, v = (d[x].to_numpy(float) for x in ("open", "high", "low", "close", "v")); t = d["time"].to_numpy(); n = len(d)
    atr = atr14(d).to_numpy(); atrp = np.r_[np.nan, atr[:-1]]
    ema = d["close"].ewm(span=EMA_SPAN, adjust=False).mean().to_numpy()
    vm = pd.Series(v).rolling(20).mean().shift(1).to_numpy(); volx = np.where((vm > 0) & np.isfinite(vm), v / np.maximum(vm, 1e-12), 0.0)
    body = np.abs(c - o) / np.maximum(h - l, 1e-12)
    hh = np.full(n, np.nan); ll = np.full(n, np.nan)
    for N in range(10, 3, -1):
        H = pd.Series(h).rolling(N).max().shift(1).to_numpy(); Lo = pd.Series(l).rolling(N).min().shift(1).to_numpy()
        ok = ((H - Lo) <= K * atrp) & ~np.isnan(H) & np.isnan(hh); hh = np.where(ok, H, hh); ll = np.where(ok, Lo, ll)
    long_ = (c > hh) & (c > ema) & (body >= BODY_MIN) & (volx >= VOL_MIN)
    short_ = (c < ll) & (c < ema) & (body >= BODY_MIN) & (volx >= VOL_MIN)
    sig = np.flatnonzero((long_ | short_) & (np.arange(n) >= 300) & (np.arange(n) < n - int(HOLD) - 2))
    out = []
    for i in sig:
        side = 1 if long_[i] else -1; stop = ll[i] if side == 1 else hh[i]; j = i + 1; entry = o[j]; risk = abs(entry - stop)
        if not (risk > 0) or (side == 1 and stop >= entry) or (side == -1 and stop <= entry) or risk > 4 * atrp[i]: continue
        target = entry + side * RR * risk; e = j + int(HOLD)
        if side == 1: hs, ht = l[j:e] <= stop, h[j:e] >= target
        else: hs, ht = h[j:e] >= stop, l[j:e] <= target
        hit = hs | ht
        if hit.any():
            m = int(np.argmax(hit)); kx = j + m; px = stop if hs[m] else target
            if m == 0 and ((side == 1 and entry <= stop) or (side == -1 and entry >= stop)): px = entry
        else: kx = e - 1; px = c[kx]
        fsum = 0.0
        if fund is not None:
            ft, fc = fund; fsum = fc[np.searchsorted(ft, t[kx], side="right")] - fc[np.searchsorted(ft, t[j], side="right")]
        out.append((t[j], t[kx], side, entry, px, risk, fsum))
    tr = pd.DataFrame(out, columns=["entry_time", "exit_time", "side", "entry", "exit", "risk", "fund"])
    if len(tr):
        g = tr["side"] * (tr["exit"] - tr["entry"]) / tr["risk"]; cs = cost_fn(tr["entry"].to_numpy())
        tr["gross_r"] = g.clip(-5, 10); tr["net_r"] = (g - cs / tr["risk"] - tr["side"] * tr["fund"] * tr["entry"] / tr["risk"]).clip(-5, 10)
    return tr

def dollar_sim(trades, f, cap, start=1000.0):
    """trades: DataFrame with entry_time/exit_time/net_r, already sorted won't be assumed. Shared capital, 1%/trade,
    capped concurrent open risk; first-come first-served when the cap binds (no lookahead -- we don't know future trades)."""
    ev = []
    for i, r in enumerate(trades.itertuples()):
        ev.append((r.entry_time, 1, i)); ev.append((r.exit_time, 0 if r.exit_time > r.entry_time else 2, i))
    ev.sort(key=lambda e: (e[0], e[1]))
    eq, peak, dd, size, openrisk, taken, skipped, path = start, start, 0.0, {}, 0.0, 0, 0, []
    rows = list(trades.itertuples())
    for t, k, i in ev:
        if k == 1:
            amt = f * eq
            if openrisk + amt > cap * eq: skipped += 1; continue
            size[i] = amt; openrisk += amt; taken += 1
        elif i in size:
            a = size.pop(i); openrisk -= a; eq += a * rows[i].net_r; peak = max(peak, eq); dd = min(dd, eq / peak - 1); path.append((t, eq))
    return dict(final=eq, max_dd=dd, taken=taken, skipped=skipped, path=path)

def stats(r, start=1000.0):
    if len(r) < 10: return dict(cagr=np.nan, mdd=np.nan)
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    return dict(cagr=(r.iloc[-1] / start) ** (1 / max(yrs, 0.01)) - 1, mdd=0.0, yrs=yrs)

if __name__ == "__main__":
    pd.set_option("display.width", 220)
    mks = S2.all_markets("4h")
    costs = {k: v[2] for k, v in mks.items()}
    all_trades = {}
    for name, (d, fund, cost_fn) in mks.items():
        tr = extract_trades(d, fund, cost_fn); all_trades[name] = tr
        print(f"{name:10} {len(tr):4} trades  {d['time'].iloc[0].date()}..{d['time'].iloc[-1].date()}  "
              f"win {( tr.net_r>0).mean():.0%} avg net R {tr.net_r.mean():+.3f}" if len(tr) else f"{name:10} 0 trades")

    pool_noBTC = pd.concat([t.assign(m=k) for k, t in all_trades.items() if k != "BTC" and len(t)]).sort_values("entry_time").reset_index(drop=True)
    pool_all = pd.concat([t.assign(m=k) for k, t in all_trades.items() if len(t)]).sort_values("entry_time").reset_index(drop=True)
    print(f"\nPOOLED excl. BTC: {len(pool_noBTC)} trades, win {(pool_noBTC.net_r>0).mean():.0%}, avg net R {pool_noBTC.net_r.mean():+.3f}")
    print(f"POOLED incl. BTC: {len(pool_all)} trades, win {(pool_all.net_r>0).mean():.0%}, avg net R {pool_all.net_r.mean():+.3f}")

    SPLIT = pd.Timestamp("2024-07-01")
    for label, pool in (("ALL HISTORY, excl BTC", pool_noBTC), ("ALL HISTORY, incl BTC", pool_all),
                       ("HOLDOUT ONLY (2024-07+), excl BTC", pool_noBTC[pool_noBTC.entry_time >= SPLIT]),
                       ("HOLDOUT ONLY (2024-07+), incl BTC", pool_all[pool_all.entry_time >= SPLIT])):
        print(f"\n=== {label}: {len(pool)} trades ===")
        if len(pool) < 10: continue
        for f in (0.005, 0.01, 0.02):
            r = dollar_sim(pool, f, 0.06); path = pd.Series(dict(r["path"])) if r["path"] else pd.Series([1000.0])
            yrs = (pool.entry_time.max() - pool.entry_time.min()).days / 365.25
            cagr = (r["final"] / 1000) ** (1 / max(yrs, 0.01)) - 1
            print(f"  risk {f:.1%}/trade: $1000 -> ${r['final']:,.0f}  CAGR {cagr:+.0%}  maxDD {r['max_dd']:.0%}  "
                  f"trades taken {r['taken']} (skipped {r['skipped']})")
    # bootstrap of the excl-BTC holdout-only pool for an honest range of outcomes
    ho = pool_noBTC[pool_noBTC.entry_time >= SPLIT]
    rng = np.random.default_rng(11); x = ho.net_r.to_numpy(); n = len(x)
    fin = [1000 * np.prod(1 + 0.01 * rng.choice(x, n, replace=True)) for _ in range(5000)]
    print(f"\nBootstrap (holdout, excl BTC, 1% risk, resampled {n} trades, 5000 runs):")
    print(f"  median ${np.median(fin):,.0f}  5th pct ${np.percentile(fin,5):,.0f}  95th pct ${np.percentile(fin,95):,.0f}  P(end<$1000) {np.mean(np.array(fin)<1000):.0%}")
    import pickle; pickle.dump(all_trades, open(os.path.join(ROOT, "research_data", "consol_final_trades.pkl"), "wb"))
