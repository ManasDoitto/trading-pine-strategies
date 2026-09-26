"""Hull Suite Strategy (public InSilico script, Pine v2) swept on CRUDEOIL 5m.
Pre-registration: pre_registration_hull_sweep_2026_09_26.md. Points per 1 unit, net of 0.02%/side."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs

COMM, WARMUP = 0.0002, 400
T_VALID, T_HOLD = pd.Timestamp("2025-09-12 09:00"), pd.Timestamp("2026-03-11 15:10")
MODES = ("Hma", "Ehma", "Thma")
LENGTHS = (9, 14, 21, 34, 55, 70, 89, 120, 144, 180, 200, 250, 300, 400)
DIRS = ("long", "short", "all")
EXITS = ("hold", "intraday")


def wma(x, n):
    """Pine wma on a float array; NaN until n valid values (NaN inputs propagate, as in Pine)."""
    n = int(n)
    w = np.arange(1, n + 1, dtype=float)
    out = np.full(len(x), np.nan)
    if n <= len(x):
        out[n - 1:] = np.convolve(x, w[::-1], "valid") / w.sum()
    return out


def ema(x, n):
    return pd.Series(x).ewm(span=int(n), adjust=False).mean().to_numpy()


def hull(x, mode, n):
    if mode == "Hma":
        return wma(2 * wma(x, n // 2) - wma(x, n), round(np.sqrt(n)))
    if mode == "Ehma":
        s = ema(x, n // 2) if n // 2 > 0 else x
        return ema(2 * s - ema(x, n), round(np.sqrt(n)))
    m = n // 2                                                        # Mode() calls THMA(src, len/2)
    return wma(wma(x, m // 3) * 3 - wma(x, m // 2) - wma(x, m), m)


def positions(h, direction, flat_mask):
    """pos[i] = position held through bar i (filled at bar i's open) from the state at bar i-1's close."""
    n = len(h)
    sig = np.zeros(n)                                                 # +1 long order, -1 short order, 0 none
    prev2 = np.roll(h, 2); prev2[:2] = np.nan
    sig[h > prev2] = 1
    sig[h < prev2] = -1
    pos = np.zeros(n)
    cur = 0.0
    for i in range(WARMUP, n):
        s = sig[i - 1]
        if s == 1:
            cur = 1.0 if direction in ("long", "all") else 0.0        # disallowed direction closes, doesn't reverse
        elif s == -1:
            cur = -1.0 if direction in ("short", "all") else 0.0
        if flat_mask[i]:
            cur = 0.0 if s == 0 else cur                              # forced flat; see below
            pos[i] = 0.0
            continue
        pos[i] = cur
    return pos


def trades_from(pos, o, c, t):
    out, i, n = [], WARMUP, len(pos)
    while i < n:
        if pos[i] == 0:
            i += 1; continue
        side, j = pos[i], i
        while j < n and pos[j] == side:
            j += 1
        entry = o[i]
        exit_px, exit_t = (o[j], t[j]) if j < n else (c[n - 1], t[n - 1])
        gross = (exit_px - entry) * side
        out.append(dict(entry_time=t[i], exit_time=exit_t, side=side, entry=entry, exit=exit_px,
                        net=gross - COMM * (entry + exit_px)))
        i = j
    return out


def gate(S, full):
    return (all(S[k].get("pf", 0) >= 1.30 for k in ("TRAIN", "VALID", "HOLDOUT")) and full["n"] >= 150
            and full["pos_months_pct"] >= 70 and full["best_month_share"] is not None
            and full["best_month_share"] <= 25 and S["HOLDOUT"].get("pf", 0) > 1.312 and full["max_dd"] <= 2280.0)


if __name__ == "__main__":
    df = rs.load("MCX_CRUDEOIL1")
    o, c, t = df.open.to_numpy(float), df.close.to_numpy(float), df.time.to_numpy()
    minutes = (df.time.dt.hour * 60 + df.time.dt.minute).to_numpy()
    masks = {"hold": np.zeros(len(df), bool), "intraday": minutes >= 23 * 60 + 25}
    rows = []
    for mode in MODES:
        for n in LENGTHS:
            h = hull(c, mode, n)
            for d in DIRS:
                for ex in EXITS:
                    tr = trades_from(positions(h, d, masks[ex]), o, c, t)
                    if not tr:
                        continue
                    T = pd.DataFrame(tr); et = pd.to_datetime(T.exit_time)
                    parts = {"TRAIN": T[et < T_VALID], "VALID": T[(et >= T_VALID) & (et < T_HOLD)], "HOLDOUT": T[et >= T_HOLD]}
                    S = {k: rs.stats(v.to_dict("records")) for k, v in parts.items()}
                    F = rs.stats(tr)
                    rows.append(dict(mode=mode, length=n, direction=d, exit=ex, n=F["n"], pf=F["pf"], net=F["net"],
                                     max_dd=F["max_dd"], win=F["win_pct"], pos_m=F["pos_months_pct"],
                                     best_m=F["best_month_share"], avg_hold_h=F["avg_hold_h"],
                                     n_train=S["TRAIN"].get("n", 0), pf_train=S["TRAIN"].get("pf"),
                                     pf_valid=S["VALID"].get("pf"), pf_hold=S["HOLDOUT"].get("pf"),
                                     net_train=S["TRAIN"].get("net"), net_valid=S["VALID"].get("net"),
                                     net_hold=S["HOLDOUT"].get("net"), passes=gate(S, F)))
        print("done", mode, flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(Path(__file__).resolve().parents[1] / "research_data" / "hull_sweep_results.csv", index=False)
    print("combos:", len(R), "| pass all gates:", int(R.passes.sum()))
