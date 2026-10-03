"""Multi-timeframe, higher-frequency version of the v5.0 SHA-ADX Hybrid on BTC perpetual.

Multi-timeframe idea: a SLOW timeframe decides whether the market is trending (HTF ADX
gate + HTF EMA21>EMA55 stack, using only the PREVIOUS COMPLETED HTF bar -> no lookahead),
and a FAST timeframe (15m/30m) times the entry with the production SHA-flip / Donchian
trigger from trading_agents/core/signals_v50.py. More bars -> more signals -> more trades.

Honesty rules baked in:
  * parameters are SELECTED on data before the 5-year deployment window and JUDGED on the
    window (and a yearly walk-forward re-selection is reported too);
  * costs are deliberately conservative for a higher-frequency system: taker fee + extra
    slippage on every side, plus REAL historical funding paid/received while in the trade;
  * dollar results model Delta's coarse contract size (0.001 BTC) and a margin cap, so the
    $100 numbers are not a frictionless fantasy.
"""
from __future__ import annotations

import json
import os
import numpy as np
import pandas as pd

from trading_agents.core.signals_v50 import v50_frame, _adx_raw
from backtest_btc_sha_adx_hybrid import btc_params
from backtest_btc_perp_trend import load_klines, DATA_DIR

FEE_SIDE = 0.0005      # Delta taker fee (verify your tier; India GST on fees would add ~18% of this)
SLIP_SIDE = 0.0002     # extra slippage assumption on market/stop fills
COST_SIDE = FEE_SIDE + SLIP_SIDE
LOT_BTC = 0.001        # assumed Delta BTC perp contract size
WINDOW_START = pd.Timestamp("2021-10-04")


# ----------------------------------------------------------------------------- data
def load_15m() -> pd.DataFrame:
    df = load_klines(os.path.join(DATA_DIR, "btcusdt_perp_15m.json"))
    out = df.rename(columns={"dt": "time"})[["time", "open", "high", "low", "close", "volume"]].copy()
    out["time"] = out["time"].dt.tz_localize(None)
    return out.reset_index(drop=True)


def resample(bars: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if minutes == 15:
        return bars.copy()
    r = (bars.set_index("time").resample(f"{minutes}min", label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
         .dropna(subset=["close"]).reset_index())
    return r


def load_funding() -> tuple[np.ndarray, np.ndarray]:
    with open(os.path.join(DATA_DIR, "btcusdt_funding.json")) as f:
        raw = json.load(f)
    fr = pd.DataFrame(raw)
    t = pd.to_datetime(fr["fundingTime"], unit="ms", utc=True).dt.tz_localize(None)
    rate = fr["fundingRate"].astype(float).to_numpy()
    order = np.argsort(t.to_numpy())
    return t.to_numpy()[order], np.concatenate([[0.0], np.cumsum(rate[order])])


def htf_features(base: pd.DataFrame, htf_min: int) -> pd.DataFrame:
    k = (base.set_index("time").resample(f"{htf_min}min", label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
         .dropna(subset=["close"]))
    k["adx"] = _adx_raw(k["high"], k["low"], k["close"], 14)
    e21 = k["close"].ewm(span=21, adjust=False).mean()
    e55 = k["close"].ewm(span=55, adjust=False).mean()
    k["tl"] = ((e21 > e55) & (k["close"] > e55)).astype(float)
    k["ts"] = ((e21 < e55) & (k["close"] < e55)).astype(float)
    prev = k[["adx", "tl", "ts"]].shift(1)  # previous COMPLETED htf bar only
    idx = base["time"].dt.floor(f"{htf_min}min")
    return prev.reindex(idx).reset_index(drop=True)


# ----------------------------------------------------------------------------- simulator
def simulate_fast(df: pd.DataFrame, ok_l: np.ndarray, ok_s: np.ndarray, rr: float,
                  fund_t: np.ndarray, fund_cum: np.ndarray) -> pd.DataFrame:
    """Same entry semantics as signals_v50.simulate (arm at signal close, fill next open,
    SL checked before TP inside a bar, re-arm allowed on the exit bar) but vectorised."""
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t = df["time"].to_numpy()
    risk_l, risk_s = df["risk_l"].to_numpy(float), df["risk_s"].to_numpy(float)
    n = len(df)
    sig = np.flatnonzero(ok_l | ok_s)
    rows = []
    i = 250
    while True:
        p = np.searchsorted(sig, i)
        if p >= len(sig):
            break
        i = int(sig[p])
        if i >= n - 2:
            break
        side = 1 if ok_l[i] else -1
        risk = risk_l[i] if side == 1 else risk_s[i]
        sl, tp = c[i] - side * risk, c[i] + side * rr * risk
        j = i + 1
        entry = o[j]
        # walk forward in growing chunks until SL or TP is touched
        k, hit = j, None
        chunk = 512
        while hit is None and k < n:
            e = min(k + chunk, n)
            if side == 1:
                hs, ht = l[k:e] <= sl, h[k:e] >= tp
            else:
                hs, ht = h[k:e] >= sl, l[k:e] <= tp
            any_hit = hs | ht
            if any_hit.any():
                m = int(np.argmax(any_hit))
                hit = ("SL" if hs[m] else "TP", k + m)
            k = e
            chunk *= 2
        if hit is None:
            break
        why, kx = hit
        px = sl if why == "SL" else tp
        if kx == j:  # gap through a level at the fill bar -> fill at the open, not the level
            if side == 1 and entry <= sl: px = entry
            if side == 1 and entry >= tp and why == "TP": px = entry
            if side == -1 and entry >= sl: px = entry
            if side == -1 and entry <= tp and why == "TP": px = entry
        risk_act = abs(entry - sl)
        if risk_act / entry >= 0.001:
            f0 = fund_cum[np.searchsorted(fund_t, t[j], side="right")]
            f1 = fund_cum[np.searchsorted(fund_t, t[kx], side="right")]
            rows.append((t[j], t[kx], side, entry, sl, px, f1 - f0))
        i = kx
    tr = pd.DataFrame(rows, columns=["entry_time", "exit_time", "side", "entry", "sl", "exit", "fund"])
    if len(tr):
        risk_act = (tr["entry"] - tr["sl"]).abs()
        gross = tr["side"] * (tr["exit"] - tr["entry"]) / risk_act
        cost = 2 * COST_SIDE * tr["entry"] / risk_act
        fund = tr["side"] * tr["fund"] * tr["entry"] / risk_act
        tr["net_r"] = gross - cost - fund
        tr["hold_d"] = (tr["exit_time"] - tr["entry_time"]).dt.total_seconds() / 86400
    return tr


# ----------------------------------------------------------------------------- dollars
def dollar_sim(tr: pd.DataFrame, start_eq=100.0, f=0.02, t0=None, t1=None, max_lev=10.0):
    eq, peak, max_dd = start_eq, start_eq, 0.0
    last_exit, taken, skipped = None, 0, 0
    path = []
    for r in tr.sort_values("entry_time").itertuples():
        if t0 is not None and r.entry_time < t0: continue
        if t1 is not None and r.entry_time > t1: continue
        if last_exit is not None and r.entry_time < last_exit: continue
        stop_per_btc = abs(r.entry - r.sl)
        risk_target = f * eq
        lots = int(risk_target // (stop_per_btc * LOT_BTC))
        if lots < 1:
            if stop_per_btc * LOT_BTC <= 2.5 * risk_target:
                lots = 1
            else:
                skipped += 1; continue
        lots = min(lots, int(eq * max_lev // (r.entry * LOT_BTC)))
        if lots < 1:
            skipped += 1; continue
        q = lots * LOT_BTC
        pnl = q * r.side * (r.exit - r.entry) - q * (r.entry + r.exit) * COST_SIDE - q * r.side * r.fund * r.entry
        eq += pnl
        taken += 1
        last_exit = r.exit_time
        peak = max(peak, eq)
        max_dd = min(max_dd, eq / peak - 1)
        path.append((r.exit_time, eq))
        if eq <= 1.0:
            break
    return dict(final=eq, max_dd=max_dd, taken=taken, skipped=skipped, path=path)
