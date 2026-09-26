"""Hull Suite concept on CRUDEOIL 5m. Pre-registration: pre_registration_hull_2026_09_26.md

Only the ENTRY condition differs from the deployed crude v4.0; every other param and the whole
fill/exit loop come from research_sim, unchanged. Points, net of 0.02%/side.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import research_sim as rs
from trading_agents.core import signals as v40

P = dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1,
         min_sl=1.5, max_sl=3.0, rr=4.0, session=["09:15", "23:30"])


def wma(s, n):
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s, n, mode="hma"):
    """Hull: WMA(2*WMA(n/2) - WMA(n), sqrt(n)). Ehma is the same shape with EMA throughout."""
    half, sq = int(n / 2), int(round(np.sqrt(n)))
    if mode == "ehma":
        return v40.ema(2 * v40.ema(s, half) - v40.ema(s, n), sq)
    return wma(2 * wma(s, half) - wma(s, n), sq)


def hull_dir(s, n, mode="hma"):
    """InSilico's own rule: hull > hull[2] = up. Returns a bool Series (NaN warm-up -> False)."""
    h = hma(s, n, mode)
    return (h > h.shift(2)).fillna(False).astype(bool)


def htf_hull_dir(df, n, rule="1h"):
    """Hull on resampled HTF bars, mapped back to 5m WITHOUT lookahead: each 5m bar sees only the
    last CLOSED HTF bar (shift(1) on the HTF series before the forward-fill)."""
    h = df.set_index("time")["close"].resample(rule).last().dropna()
    d = hull_dir(h, n).shift(1, fill_value=False)
    return d.reindex(df["time"], method="ffill").fillna(False).to_numpy().astype(bool)


def frame(df, variant):
    """v4.0 frame with the pre-registered entry swap applied."""
    f = v40.v40_frame(df, P)
    c, cap = f["close"], P["max_sl"] * f["atr"]
    base = f["in_sess"] & (f["risk_l"] <= cap), f["in_sess"] & (f["risk_s"] <= cap)

    if variant in ("A1", "A2", "A3", "A4"):           # Hull as BIAS FILTER, SHA flip stays the trigger
        if variant == "A3":
            up = pd.Series(htf_hull_dir(f, 55), index=f.index)
        else:
            up = hull_dir(c, 55, "ehma" if variant == "A2" else "hma")
        bias_l, bias_s = up, ~up
        if variant == "A4":                            # both filters required
            bias_l, bias_s = up & (f["e9"] > f["e22"]), ~up & (f["e9"] < f["e22"])
        ok_l = base[0] & f["flip_up"] & bias_l
        ok_s = base[1] & f["flip_dn"] & bias_s
    else:                                              # Hull flip as TRIGGER, EMA alignment stays
        n, mode = (89, "hma") if variant == "B3" else (55, "ehma" if variant == "B2" else "hma")
        up = hull_dir(c, n, mode)
        prev = up.shift(1, fill_value=bool(up.iat[0]))
        fu, fd = up & ~prev, ~up & prev
        if variant == "B4":                            # direction must hold 2 bars; enter on the 2nd
            fu = up & up.shift(1, fill_value=False) & ~up.shift(2, fill_value=False)
            fd = ~up & ~up.shift(1, fill_value=True) & up.shift(2, fill_value=True)
        ok_l = base[0] & fu & (f["e9"] > f["e22"])
        ok_s = base[1] & fd & (f["e9"] < f["e22"])

    f["ok_l"], f["ok_s"] = ok_l, ok_s & ~ok_l
    return f


def split_stats(trades):
    """60/20/20 by exit time, as pre-registered."""
    if not trades:
        return None
    t = pd.DataFrame(trades).sort_values("exit_time").reset_index(drop=True)
    n = len(t); a, b = int(n * .6), int(n * .8)
    return {k: rs.stats(v.to_dict("records")) for k, v in
            (("FULL", t), ("TRAIN", t[:a]), ("VALID", t[a:b]), ("HOLDOUT", t[b:]))}


if __name__ == "__main__":
    df = rs.load("MCX_CRUDEOIL1")
    rows = []
    base = v40.v40_frame(df, P)
    for name, f in [("BASELINE", base)] + [(v, frame(df, v)) for v in
                                           ("A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4")]:
        s = split_stats(rs.simulate(f, P))
        if s is None:
            print(f"{name:9s} NO TRADES"); continue
        F = s["FULL"]
        rows.append(dict(variant=name, n=F["n"], pf=F["pf"], net=F["net"], dd=F["max_dd"],
                         win=F["win_pct"], posM=F["pos_months_pct"], best_m=F["best_month_share"],
                         pf_train=s["TRAIN"]["pf"], pf_valid=s["VALID"]["pf"], pf_hold=s["HOLDOUT"]["pf"],
                         net_hold=s["HOLDOUT"]["net"]))
        print(f"{name:9s} n={F['n']:4d} PF={F['pf']:.3f} net={F['net']:+9.1f} dd={F['max_dd']:7.1f} "
              f"win={F['win_pct']:4.1f}% posM={F['pos_months_pct']:4.1f}% bestM={F['best_month_share']} | "
              f"tr={s['TRAIN']['pf']:.3f} va={s['VALID']['pf']:.3f} ho={s['HOLDOUT']['pf']:.3f}")
    pd.DataFrame(rows).to_csv(Path(__file__).resolve().parents[1] / "research_data" / "hull_results.csv", index=False)
