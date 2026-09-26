"""CrudeOil v5.1 flip+breakout: shipped file, ablations, and the recipe on crude #1's base.
Pre-registration: pre_registration_crude_breakout_2026_09_26.md  (15 trials, nothing else is run)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
import silver_sweep as SS

T0 = pd.Timestamp("2024-03-25")
WINDOWS = SS.WINDOWS
_D = None

S0 = dict(entry="flip+bo", lookback=5, use200=True, pullback=1.0, adx=15.0, rr=3.0, flat="22:45", day=300.0,
          min_sl=1.5, max_sl=3.0, hold=3)
CLEAN = dict(use200=False, pullback=99.0, adx=0.0, flat=None, day=0.0, min_sl=1.5, max_sl=3.0, hold=0)  # hold=0: crude #1 has NO SHA-stability filter


def data():
    global _D
    if _D is None:
        _D = SS.base("MCX_CRUDEOIL1")
    return _D


def build(d, cfg):
    ff = [cfg["flat"], "23:30"] if cfg["flat"] else ["23:59", "23:59"]   # ["23:59","23:59"] = never
    p = dict(sha_len1=10, sha_len2=10, sha_min_hold=cfg.get("hold", 3), sw_len=10, sw_buf=0.1,
             min_sl=cfg["min_sl"], max_sl=cfg["max_sl"], rr=cfg["rr"], adx_min=cfg["adx"],
             pb_atr_mult=cfg["pullback"], atr_min_pts=0, use_vol_filter=False, vol_sma_len=50,
             use200=cfg["use200"], day_loss_limit=cfg["day"], session=["09:15", "23:30"], force_flat_window=ff)
    f = SS.frame(d, p)
    cap = p["max_sl"] * f["atr"]
    tl = (f["e9"] > f["e22"]) & ((f["close"] > f["e200"]) if cfg["use200"] else True)
    ts = (f["e9"] < f["e22"]) & ((f["close"] < f["e200"]) if cfg["use200"] else True)
    gate = f["in_sess"] & f["atr_ok"] & f["adx_ok"] & ~f["in_flat_window"]
    flipL = f["flip_up"] & f["sha_stable"]
    flipS = f["flip_dn"] & f["sha_stable"]
    if cfg["entry"] == "flip":
        L, S = flipL, flipS
    else:
        lb = cfg["lookback"]
        L = flipL | (f["close"] > f["high"].rolling(lb).max().shift(1))
        S = flipS | (f["close"] < f["low"].rolling(lb).min().shift(1))
    g = f.copy()
    g["ok_l"] = gate & L & tl & (f["risk_l"] <= cap) & f["near_ema9_l"]
    g["ok_s"] = gate & S & ts & (f["risk_s"] <= cap) & f["near_ema9_s"] & ~g["ok_l"]
    return g, p


def run(cfg, comm=0.0, d=None, t0=T0):
    d = d if d is not None else data()
    g, p = build(d, cfg)
    s0 = max(int((g["time"] >= t0).idxmax()), rs.WARMUP)
    return rs.simulate(g, dict(p, day_loss_limit_pts=cfg["day"]), start=s0, flat_at=cfg["flat"], commission=comm)


def summarise(tag, cfg):
    tr, trn = run(cfg), run(cfg, 0.0002)
    if not tr:
        return dict(id=tag, n=0)
    s, sn = rs.stats(tr), (rs.stats(trn) if trn else {"net": 0, "pf": 0})
    t = pd.DataFrame(tr); t["exit_time"] = pd.to_datetime(t["exit_time"])
    wn = [round(float(t[(t.exit_time >= a) & (t.exit_time < b)].net.sum())) for a, b in WINDOWS]
    ex = pd.Series([x["result"] for x in tr]).value_counts()
    return dict(id=tag, n=s["n"], per_mo=round(s["n"] / 30, 1), pf=s["pf"], net=round(s["net"]), dd=round(s["max_dd"]),
                win=s["win_pct"], avg=round(s["net"] / s["n"], 1), pos_m=s["pos_months_pct"], conc=s["best_month_share"],
                hold_h=s["avg_hold_h"], tp=int(ex.get("TP", 0)), sl=int(ex.get("SL", 0)), flat=int(ex.get("FLAT", 0)),
                pf_net=sn.get("pf"), net_cost=round(sn["net"]), gap_per_trade=round((s["net"] - sn["net"]) / s["n"], 1),
                **{f"w{i+1}": v for i, v in enumerate(wn)})


def trials():
    out = [("S0 shipped", dict(S0))]
    ab = {"a hold overnight": dict(flat=None), "b RR 4.0": dict(rr=4.0), "c no EMA200": dict(use200=False),
          "d no pullback": dict(pullback=99.0), "e no ADX": dict(adx=0.0), "f no daily limit": dict(day=0.0)}
    for k, v in ab.items():
        out.append((f"S0 - {k}", dict(S0, **v)))
    for entry, lb in (("flip", None), ("flip+bo", 3), ("flip+bo", 5), ("flip+bo", 10)):
        for rr in (3.0, 4.0):
            tag = f"crude#1 base {'flip only' if entry == 'flip' else f'flip+bo({lb})'} RR{rr:g}"
            out.append((tag, dict(CLEAN, entry=entry, lookback=lb, rr=rr)))
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 270)
    pd.set_option("display.max_columns", 40)
    R = pd.DataFrame([summarise(t, c) for t, c in trials()])
    R.to_csv(ROOT / "research_data" / "crude_breakout.csv", index=False)
    print(R[["id", "n", "per_mo", "pf", "net", "dd", "win", "avg", "hold_h", "pos_m", "conc", "pf_net", "net_cost", "gap_per_trade"]].to_string(index=False))
    print("\nper-window net (W1..W6):")
    print(R[["id"] + [f"w{i}" for i in range(1, 7)]].to_string(index=False))
