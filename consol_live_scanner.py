"""Live scanner for the winning consolidation-breakout config (see consol_dollar_sim.py for the backtest).
Checks the LAST CLOSED 4h candle on each market for: a qualifying consolidation box beforehand, and a breakout
that clears the trend/body/volume filters. Run this once every 4h after a candle closes (00:00/04:00/08:00/
12:00/16:00/20:00 UTC = 05:30/09:30/13:30/17:30/21:30/01:30 IST).

Scope: gold + crypto only (BTC ETH SOL BNB XRP, XAU) -- MCX/NSE instruments dropped per 2026-10-03 instruction
(user has existing setups for those). Recommended trading set is ETH SOL BNB XRP XAU; BTC is included in the
scan for visibility but its own backtest showed ~no edge (avg net R -0.01) -- see consol_dollar_sim.py.

Data sources:
  crypto (BTC ETH SOL BNB XRP)  -> Binance public REST, truly live, no auth
  XAU                           -> Dukascopy (same source as the backtest); NOTE this can lag by up to ~1 day
                                    and is occasionally flaky (rate-limits), so treat gold's scan as indicative,
                                    not a live trigger -- confirm on a real gold feed before acting on it.
"""
from __future__ import annotations
import sys, os, json, time, urllib.request
from datetime import datetime, timedelta, timezone
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from consol_dollar_sim import K, RR, HOLD, EMA_SPAN, BODY_MIN, VOL_MIN, atr14

LOOKBACK_4H = 320            # ~53 days of 4h bars; enough for the 240-span EMA to settle

def fetch_binance_4h(sym):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=4h&limit={LOOKBACK_4H}"
    raw = json.loads(urllib.request.urlopen(url, timeout=20).read())
    d = pd.DataFrame(raw).iloc[:, :6]; d.columns = ["t", "open", "high", "low", "close", "v"]
    for c in d.columns[1:]: d[c] = d[c].astype(float)
    d["time"] = pd.to_datetime(d["t"], unit="ms"); return d[["time", "open", "high", "low", "close", "v"]]

def fetch_gold_4h():
    import lzma, struct
    from concurrent.futures import ThreadPoolExecutor

    def get(day):
        url = f"http://datafeed.dukascopy.com/datafeed/XAUUSD/{day.year}/{day.month-1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8).read()
            if not raw: return []
            data = lzma.decompress(raw); base = datetime(day.year, day.month, day.day); rows = []
            for i in range(len(data) // 24):
                t, o, c, l, h, v = struct.unpack(">IIIIIf", data[i * 24:(i + 1) * 24])
                rows.append((base + timedelta(seconds=t), o / 1000, h / 1000, l / 1000, c / 1000, v))
            return rows
        except Exception:
            return []

    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=b) for b in range(70) if (today - timedelta(days=b)).weekday() != 5]
    rows = []
    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(get, days):
            rows += r
    d = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "v"])
    d["time"] = pd.to_datetime(d["time"]); d = d.sort_values("time").drop_duplicates("time")
    if len(d) < 1000: raise RuntimeError(f"too few 1m gold bars fetched ({len(d)}) -- Dukascopy may be rate-limiting, retry")
    r = (d.set_index("time").resample("4h", label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last", "v": "sum"}).dropna().reset_index())
    return r

def evaluate(d, name, label=""):
    """-> dict describing the current consolidation state and whether the LAST CLOSED candle triggered."""
    if len(d) < EMA_SPAN + 10:
        return dict(market=name, ok=False, note=f"only {len(d)} 4h bars, need >={EMA_SPAN+10}")
    o, h, l, c, v = (d[x].to_numpy(float) for x in ("open", "high", "low", "close", "v"))
    atr = atr14(d).to_numpy(); atrp = np.r_[np.nan, atr[:-1]]
    ema = d["close"].ewm(span=EMA_SPAN, adjust=False).mean().to_numpy()
    vm = pd.Series(v).rolling(20).mean().shift(1).to_numpy(); volx = np.where((vm > 0) & np.isfinite(vm), v / np.maximum(vm, 1e-12), 0.0)
    body = np.abs(c - o) / np.maximum(h - l, 1e-12)
    n = len(d); i = n - 1                                          # the LAST CLOSED candle
    hi_box = lo_box = np.nan; box_n = 0
    for N in range(10, 3, -1):
        if i - N < 0: continue
        hi = h[i - N:i].max(); lo = l[i - N:i].min()
        if (hi - lo) <= K * atrp[i]: hi_box, lo_box, box_n = hi, lo, N; break
    long_sig = (not np.isnan(hi_box)) and c[i] > hi_box and c[i] > ema[i] and body[i] >= BODY_MIN and volx[i] >= VOL_MIN
    short_sig = (not np.isnan(lo_box)) and c[i] < lo_box and c[i] < ema[i] and body[i] >= BODY_MIN and volx[i] >= VOL_MIN
    out = dict(market=name, label=label, ok=True, last_close_time=d["time"].iloc[i], last_close=float(c[i]),
              atr=float(atrp[i]) if not np.isnan(atrp[i]) else None, box_n=box_n,
              box_hi=float(hi_box) if not np.isnan(hi_box) else None, box_lo=float(lo_box) if not np.isnan(lo_box) else None,
              trend=("up" if c[i] > ema[i] else "down"), body_pct=round(float(body[i]), 2), vol_x=round(float(volx[i]), 2),
              signal=None)
    if long_sig or short_sig:
        side = 1 if long_sig else -1; stop = lo_box if side == 1 else hi_box; risk = abs(c[i] - stop)
        out["signal"] = dict(side="LONG" if side == 1 else "SHORT", suggested_entry_near=float(c[i]),
                             stop=float(stop), target=float(c[i] + side * RR * risk), risk_pts=float(risk),
                             hold_candles=int(HOLD), valid_until=str(d["time"].iloc[i] + pd.Timedelta(hours=4 * int(HOLD))))
    return out


def main():
    results = []
    print(f"=== Consolidation-breakout live scan, run at {datetime.now():%Y-%m-%d %H:%M IST} ===")
    print(f"rule: box<={K}xATR14 (N=4..10), close beyond box, trend-EMA{EMA_SPAN}, body>={BODY_MIN:.0%} range, "
          f"vol>={VOL_MIN}x avg | stop=box edge, target={RR}R, time-stop={HOLD} candles (2 days)\n")
    for sym in ("BTC", "ETH", "SOL", "BNB", "XRP"):
        try:
            d = fetch_binance_4h(sym); results.append(evaluate(d, sym))
        except Exception as e: results.append(dict(market=sym, ok=False, note=f"fetch failed: {e}"))
    try:
        d = fetch_gold_4h(); r = evaluate(d, "XAU"); r["note"] = "Dukascopy feed can lag by up to ~1 day -- confirm on a live gold feed before acting"; results.append(r)
    except Exception as e: results.append(dict(market="XAU", ok=False, note=f"gold fetch failed: {e}"))

    any_signal = False
    for r in results:
        if not r.get("ok"):
            print(f"  {r['market']:10} SKIPPED - {r.get('note','')}"); continue
        tag = f"[{r.get('label','')}]" if r.get("label") else ""
        print(f"  {r['market']:10} {tag:14} last close {r['last_close_time']} = {r['last_close']:.4g}  "
              f"trend={r['trend']}  box={r['box_n']}bars[{r['box_lo']},{r['box_hi']}]  "
              f"body={r['body_pct']:.0%} vol={r['vol_x']:.2f}x" + (f"  NOTE: {r['note']}" if r.get("note") and r.get("ok") else ""))
        if r.get("signal"):
            any_signal = True; s = r["signal"]
            print(f"      >>> SIGNAL: {s['side']} near {s['suggested_entry_near']:.4g}  stop {s['stop']:.4g}  "
                  f"target {s['target']:.4g}  (risk {s['risk_pts']:.4g}/unit)  valid until {s['valid_until']}")
    if not any_signal:
        print("\nNo fresh breakout on the last closed 4h candle, any market.")
    return results

if __name__ == "__main__":
    main()
