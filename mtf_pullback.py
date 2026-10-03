"""Port of working_strategies/BankNifty/2_v1.1_MTF_pullback_3min.pine.txt (HTF bias + LTF pullback-reclaim,
PF 1.64 / Sharpe +1.21 on BankNifty 3m/15m) to crypto perps and gold.

  HTF bias: HTF EMA9 vs EMA21 cross, "fresh" within fresh_bars (12) HTF bars of the cross
  LTF entry: LTF EMA9 vs EMA21 aligned with bias; track a pullback to LTF EMA9 within pb_lookback (12) LTF
             bars of last being above/below both EMAs; stop order at the pullback extreme, armed for
             reclaim_win (10) bars
  Trend-strength gates (from completed bars, no lookahead): HTF ADX >= 25, a SLOWER (4x HTF)-timeframe
             ADX >= 20 -- same two-gate structure as the original's dAdxMin/htfAdxMin (daily + 15m)
  Risk: stop = pullback extreme +/- 0.15xATR, floored at 0.5xATR, capped at 2.0xATR; target = 2.5R
  Cooldown: 2 bars after an exit before a new pullback can arm
BankNifty-specific bits dropped for 24/7 markets: session window, 35pt ATR floor, RSI(3) chop filter (all
either off by default in the Pine or meaningless outside NSE hours).
"""
from __future__ import annotations
import numpy as np, pandas as pd

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def atr14(d):
    pc = d["close"].shift(1); tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean()

def adx14(d):
    h, l, c = d["high"], d["low"], d["close"]; up, dn = h.diff(), -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = c.shift(1); tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1); w = lambda s: s.ewm(alpha=1 / 14, adjust=False).mean()
    a = w(tr); p = 100 * w(pd.Series(pdm, index=d.index)) / a; m = 100 * w(pd.Series(mdm, index=d.index)) / a
    return 100 * w((p - m).abs() / (p + m).replace(0, np.nan))

def resample(d, rule):
    # origin="epoch": bin boundaries are epoch-aligned, matching .dt.floor()'s epoch-aligned grid used in
    # map_prev_completed below -- required for correctness when `rule` doesn't evenly divide a day (e.g. 16h),
    # where pandas' default day-anchored origin silently produces bins that never match the floor() lookup.
    return (d.set_index("time").resample(rule, label="left", closed="left", origin="epoch")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna().reset_index())

def map_prev_completed(ltf_time, htf, htf_minutes):
    """Build a per-LTF-bar lookup of the PREVIOUS COMPLETED htf bar's bull/bear/bars_since_flip/adx."""
    e9, e21 = ema(htf["close"], 9), ema(htf["close"], 21)
    bull = (e9 > e21).to_numpy(); sign = np.where(bull, 1, -1)
    flip = np.r_[True, sign[1:] != sign[:-1]]
    flip_bar = pd.Series(np.where(flip, np.arange(len(htf)), np.nan)).ffill().to_numpy()
    bars_since_flip = np.arange(len(htf)) - flip_bar
    a = adx14(htf).to_numpy()
    feat = pd.DataFrame({"bull": bull, "bars_since_flip": bars_since_flip, "adx": a}).shift(1)
    feat.index = htf["time"]
    idx = ltf_time.dt.floor(f"{htf_minutes}min")
    out = feat.reindex(idx).reset_index(drop=True)
    out.columns = ["bull", "bars_since_flip", "adx"]
    out["bull"] = out["bull"].fillna(0).astype(bool)
    out["bars_since_flip"] = out["bars_since_flip"].fillna(10 ** 9)
    out["adx"] = out["adx"].fillna(0.0)
    return out

def simulate(ltf, htf, slow, htf_minutes, slow_minutes, pb_lookback=12, reclaim_win=10, cool_bars=2,
            atr_buf=0.15, stop_floor=0.5, max_stop=2.0, rr=2.5, htf_adx_min=25.0, slow_adx_min=20.0,
            fresh_bars=12, cost_fn=None, fund=None):
    o, h, l, c = (ltf[x].to_numpy(float) for x in ("open", "high", "low", "close")); t = ltf["time"].to_numpy(); n = len(ltf)
    e9, e21 = ema(ltf["close"], 9).to_numpy(), ema(ltf["close"], 21).to_numpy()
    atr = atr14(ltf).to_numpy()
    hf = map_prev_completed(ltf["time"], htf, htf_minutes)
    sf = map_prev_completed(ltf["time"], slow, slow_minutes)
    bias_up = (hf["bull"].to_numpy()) & (hf["bars_since_flip"].to_numpy() <= fresh_bars)
    bias_dn = (~hf["bull"].to_numpy()) & (hf["bars_since_flip"].to_numpy() <= fresh_bars)
    adx_ok = (hf["adx"].to_numpy() >= htf_adx_min) & (sf["adx"].to_numpy() >= slow_adx_min)
    above_both = (c > e9) & (c > e21); below_both = (c < e9) & (c < e21)
    regime_up = bias_up & (e9 > e21); regime_dn = bias_dn & (e9 < e21)

    trades = []
    pb_act_l = pb_act_s = False; pb_low = pb_hi = np.nan; pb_bar_l = pb_bar_s = -1
    wait_l = wait_s = False; trig_l = trig_s = sl_l = sl_s = np.nan; wait_bar_l = wait_bar_s = -1
    pos = 0; entry = sl = tp = 0.0; entry_i = 0; last_exit = -10 ** 9; last_above = last_below = -10 ** 9

    for i in range(300, n):
        # ---- 1) act on orders/positions armed on a PRIOR bar, using this bar's range ----
        if pos != 0:
            hit_sl = (l[i] <= sl) if pos == 1 else (h[i] >= sl)
            hit_tp = (h[i] >= tp) if pos == 1 else (l[i] <= tp)
            if hit_sl or hit_tp:
                px = sl if hit_sl else tp
                trades.append((t[entry_i], t[i], pos, entry, px, abs(entry - sl))); last_exit = i; pos = 0
        elif wait_l and h[i] >= trig_l:
            fill = max(trig_l, o[i]) if o[i] > trig_l else trig_l
            pos, entry, sl, entry_i = 1, fill, sl_l, i; tp = entry + rr * (entry - sl); wait_l = False
        elif wait_s and l[i] <= trig_s:
            fill = min(trig_s, o[i]) if o[i] < trig_s else trig_s
            pos, entry, sl, entry_i = -1, fill, sl_s, i; tp = entry - rr * (sl - entry); wait_s = False
        if wait_l and ((i - wait_bar_l) > reclaim_win or not regime_up[i]): wait_l = False
        if wait_s and ((i - wait_bar_s) > reclaim_win or not regime_dn[i]): wait_s = False

        # ---- 2) update pullback tracking and arm NEW orders off this bar's close -- these can only
        #          fill starting the NEXT iteration (step 1 above, on a future bar) ----
        if above_both[i]: last_above = i
        if regime_up[i] and l[i] <= e9[i] and (i - last_above) <= pb_lookback:
            fresh = (not pb_act_l) or (last_above >= pb_bar_l)
            pb_low = l[i] if fresh else min(pb_low, l[i]); pb_act_l = True; pb_bar_l = i
        if not regime_up[i]: pb_act_l = False
        if below_both[i]: last_below = i
        if regime_dn[i] and h[i] >= e9[i] and (i - last_below) <= pb_lookback:
            fresh = (not pb_act_s) or (last_below >= pb_bar_s)
            pb_hi = h[i] if fresh else max(pb_hi, h[i]); pb_act_s = True; pb_bar_s = i
        if not regime_dn[i]: pb_act_s = False

        cool_ok = (i - last_exit) > cool_bars
        if pos == 0 and not wait_l and pb_act_l and regime_up[i] and adx_ok[i] and (i - pb_bar_l) <= reclaim_win and cool_ok:
            _sl = min(pb_low - atr_buf * atr[i], h[i] - stop_floor * atr[i])
            risk = h[i] - _sl
            if risk > 0 and risk <= max_stop * atr[i]:
                wait_l, wait_bar_l, trig_l, sl_l = True, i, h[i], _sl; pb_act_l = False
        if pos == 0 and not wait_s and pb_act_s and regime_dn[i] and adx_ok[i] and (i - pb_bar_s) <= reclaim_win and cool_ok:
            _sl = max(pb_hi + atr_buf * atr[i], l[i] + stop_floor * atr[i])
            risk = _sl - l[i]
            if risk > 0 and risk <= max_stop * atr[i]:
                wait_s, wait_bar_s, trig_s, sl_s = True, i, l[i], _sl; pb_act_s = False
    tr = pd.DataFrame(trades, columns=["entry_time", "exit_time", "side", "entry", "exit", "risk"])
    if len(tr):
        g = tr["side"] * (tr["exit"] - tr["entry"]) / tr["risk"]
        cs = cost_fn(tr["entry"].to_numpy()) if cost_fn else np.zeros(len(tr))
        fsum = np.zeros(len(tr))
        if fund is not None:
            ft, fc = fund; fsum = fc[np.searchsorted(ft, tr["exit_time"].to_numpy(), side="right")] - fc[np.searchsorted(ft, tr["entry_time"].to_numpy(), side="right")]
        tr["gross_r"] = g.clip(-5, 10)
        tr["net_r"] = (g - cs / tr["risk"] - tr["side"] * fsum * tr["entry"] / tr["risk"]).clip(-5, 10)
    return tr
