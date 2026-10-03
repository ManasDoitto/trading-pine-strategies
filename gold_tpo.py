"""TPO value-area strategies from this research session (mean-reversion fade, trend breakout, hybrid) ported to gold.
Profile = developing time-at-price profile per UTC day on 5m bars (volume not used). Same logic as
backtest_tpo_value_area_mr.py / backtest_tpo_breakout_trend.py / backtest_tpo_hybrid_confirm.py, but trades carry times so
they can be split train/test and judged with the same stats as every other strategy."""
import sys, os, pickle
import numpy as np, pandas as pd
import gold_all_strategies as G

BIN = 0.5            # $0.50 bins (~0.0125% of price, comparable to the index bins used before)
VA = 0.70; MIN_BARS = 12; EXC = 1.0; MINBO = 2.0; BAL = (0.2, 0.8)

def profile_stats(counts):
    poc = max(counts, key=counts.get); tot = sum(counts.values()); tgt = tot * VA; acc = counts[poc]; lo = hi = poc
    while acc < tgt:
        vl, vh = counts.get(lo - 1, 0), counts.get(hi + 1, 0)
        if vl == 0 and vh == 0: break
        if vl >= vh: lo -= 1; acc += vl
        else: hi += 1; acc += vh
    return poc, lo, hi

def day_trades(df, mode, trend_rr=2.0):
    """mode: 'mr' (fade excess toward POC, balance days), 'trend' (follow close beyond VA on one-sided days), 'hybrid'."""
    o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close")); t = df["time"].to_numpy(); n = len(df)
    if n < MIN_BARS + 5: return []
    counts = {}; dhi, dlo = -np.inf, np.inf; out = []
    pos = 0; ent = sl = tp = 0.0; setup = ""; ent_i = 0
    ufail = lfail = utaken = ltaken = False
    for i in range(n):
        if pos:
            hs = (l[i] <= sl) if pos == 1 else (h[i] >= sl); ht = (h[i] >= tp) if pos == 1 else (l[i] <= tp)
            if hs or ht:
                px = sl if hs else tp
                out.append((t[ent_i], t[i], pos, ent, px, abs(ent - sl_init), setup))
                if hs and setup == "mr":
                    if pos == 1: lfail = True
                    else: ufail = True
                pos = 0
        if counts:
            poc, lo_b, hi_b = profile_stats(counts)
            poc_px = (poc + .5) * BIN; vah = (hi_b + 1) * BIN; val = lo_b * BIN
            if val <= c[i] <= vah: ufail = lfail = utaken = ltaken = False
            if not pos and i >= MIN_BARS:
                rng = max(dhi - dlo, BIN); pp = (poc_px - dlo) / rng
                balanced = BAL[0] <= pp <= BAL[1]; trending = pp <= BAL[0] or pp >= BAL[1]
                if mode in ("mr", "hybrid") and (balanced or mode == "hybrid"):
                    if (not ufail or mode == "mr") and h[i] >= vah + EXC * BIN and c[i] < vah:
                        e = c[i]; s_ = h[i] + EXC * BIN
                        if s_ > e > poc_px: pos, ent, sl, tp, setup, ent_i, sl_init = -1, e, s_, poc_px, "mr", min(i + 1, n - 1), s_
                    elif (not lfail or mode == "mr") and l[i] <= val - EXC * BIN and c[i] > val:
                        e = c[i]; s_ = l[i] - EXC * BIN
                        if s_ < e < poc_px: pos, ent, sl, tp, setup, ent_i, sl_init = 1, e, s_, poc_px, "mr", min(i + 1, n - 1), s_
                if not pos and mode in ("trend", "hybrid"):
                    ok_hy = (mode == "hybrid")
                    if c[i] > vah + MINBO * BIN and not utaken and ((trending and mode == "trend") or (ok_hy and ufail)):
                        e = c[i]; s_ = vah; pos, ent, sl, tp, setup, ent_i, sl_init = 1, e, s_, e + trend_rr * (e - s_), "trend", min(i + 1, n - 1), s_; utaken = True
                    elif c[i] < val - MINBO * BIN and not ltaken and ((trending and mode == "trend") or (ok_hy and lfail)):
                        e = c[i]; s_ = val; pos, ent, sl, tp, setup, ent_i, sl_init = -1, e, s_, e - trend_rr * (s_ - e), "trend", min(i + 1, n - 1), s_; ltaken = True
        dhi = max(dhi, h[i]); dlo = min(dlo, l[i])
        for b in range(int(np.floor(l[i] / BIN)), int(np.floor(h[i] / BIN)) + 1): counts[b] = counts.get(b, 0) + 1
    if pos: out.append((t[ent_i], t[-1], pos, ent, c[-1], abs(ent - sl_init), setup))
    return out

def run(mode, trend_rr=2.0):
    d1 = G.load_1m(); d5 = G.resample(d1, 5)         # naive IST times; group by IST day
    rows = []
    for _, day in d5.groupby(d5["time"].dt.date):
        for (te, tx, side, e, x, risk, setup) in day_trades(day.reset_index(drop=True), mode, trend_rr):
            if risk > 0: rows.append((pd.Timestamp(te), pd.Timestamp(tx), side, e, x, risk, side * (x - e)))
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "side_n", "entry", "exit", "risk_pts", "gross"])

if __name__ == "__main__":
    res = {}
    for name, mode, rr in [("TPO mean-reversion fade", "mr", 2.0), ("TPO trend breakout RR2", "trend", 2.0), ("TPO hybrid (fade then follow)", "hybrid", 2.0)]:
        t = run(mode, rr); res[("tpo", name, "ALL24h")] = t; print(name, len(t), flush=True)
    pickle.dump(res, open(G.ROOT / "research_data" / "gold" / "tpo_trades.pkl", "wb"))
