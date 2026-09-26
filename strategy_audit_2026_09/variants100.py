"""100 variants each of the crude and BankNifty breakout strategies.
Pre-registration: pre_registration_100variants_2026_09_26.md.   Usage: python variants100.py CRUDE|BANKNIFTY"""
import random
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
SPLIT = pd.Timestamp("2025-06-25")
INST = {
    "CRUDE": dict(bars="MCX_CRUDEOIL1", end_flat="23:30",
                  sessions={"full": ("09:15", "23:30"), "us": ("17:00", "23:30"), "day": ("09:15", "17:00")},
                  flats=[None, "22:45"], days=[0.0, 150.0]),
    "BANKNIFTY": dict(bars="NSE_BANKNIFTY1", end_flat="15:30",
                      sessions={"full": ("09:30", "15:00"), "late": ("10:00", "15:00"), "early": ("09:30", "13:00")},
                      flats=["15:00", "14:30"], days=[0.0, 300.0]),
}
_D = {}


def data(inst):
    if inst not in _D:
        _D[inst] = SS.base(INST[inst]["bars"])
    return _D[inst]


def draw(inst, rng):
    m = INST[inst]
    while True:
        v = dict(entry=rng.choice(["flip", "flip+bo", "flip+bo", "bo"]), lb=rng.choice([2, 3, 5, 8, 12, 20]),
                 rr=rng.choice([1.5, 2.0, 2.5, 3.0, 4.0, 5.0]), min_sl=rng.choice([1.0, 1.5, 2.0]),
                 max_sl=rng.choice([3.0, 4.0, 5.0]), sw=rng.choice([5, 10, 15]), hold=rng.choice([0, 3]),
                 trend=rng.choice(["none", "e922", "e922", "e922+200"]), pb=rng.choice([99.0, 99.0, 1.0, 2.0]),
                 adx=rng.choice([0.0, 0.0, 15.0, 20.0]), sess=rng.choice(list(m["sessions"])),
                 flat=rng.choice(m["flats"]), day=rng.choice(m["days"]))
        if v["max_sl"] > v["min_sl"]:
            return v


def simulate(inst, v, comm=0.0):
    m, d = INST[inst], data(inst)
    s_start, s_end = m["sessions"][v["sess"]]
    if v["flat"]:
        s_end = min(s_end, v["flat"])
        ffw = [v["flat"], m["end_flat"]]
    else:
        ffw = ["23:59", "23:59"]
    p = dict(sha_len1=10, sha_len2=10, sha_min_hold=v["hold"], sw_len=v["sw"], sw_buf=0.1, min_sl=v["min_sl"],
             max_sl=v["max_sl"], rr=v["rr"], adx_min=v["adx"], pb_atr_mult=v["pb"], atr_min_pts=0,
             use_vol_filter=False, vol_sma_len=80, use200=False, day_loss_limit=v["day"],
             session=[s_start, s_end], force_flat_window=ffw)
    f = SS.frame(d, p)
    cap = p["max_sl"] * f["atr"]
    if v["trend"] == "none":
        tl = ts = pd.Series(True, index=f.index)
    else:
        tl, ts = f["e9"] > f["e22"], f["e9"] < f["e22"]
        if v["trend"] == "e922+200":
            tl, ts = tl & (f["close"] > f["e200"]), ts & (f["close"] < f["e200"])
    gate = f["in_sess"] & f["atr_ok"] & f["adx_ok"] & ~f["in_flat_window"]
    flipL, flipS = f["flip_up"] & f["sha_stable"], f["flip_dn"] & f["sha_stable"]
    lb = v["lb"]
    boL = f["close"] > f["high"].rolling(lb).max().shift(1)
    boS = f["close"] < f["low"].rolling(lb).min().shift(1)
    if v["entry"] == "flip":
        L, S = flipL, flipS
    elif v["entry"] == "bo":
        L, S = boL, boS
    else:
        L, S = flipL | boL, flipS | boS
    g = f.copy()
    g["ok_l"] = gate & L & tl & (f["risk_l"] <= cap) & f["near_ema9_l"]
    g["ok_s"] = gate & S & ts & (f["risk_s"] <= cap) & f["near_ema9_s"] & ~g["ok_l"]
    s0 = max(int((g["time"] >= T0).idxmax()), rs.WARMUP)
    return rs.simulate(g, dict(p, day_loss_limit_pts=v["day"]), start=s0, flat_at=v["flat"], commission=comm)


def stats_split(tr):
    t = pd.DataFrame(tr)
    t["exit_time"] = pd.to_datetime(t["exit_time"])
    out = {}
    for tag, sub in (("full", t), ("tr", t[t.exit_time < SPLIT]), ("ho", t[t.exit_time >= SPLIT])):
        if len(sub) == 0:
            out[tag] = dict(n=0, pf=0.0, net=0.0, dd=0.0, conc=None)
            continue
        s = rs.stats(sub.to_dict("records"))
        out[tag] = dict(n=s["n"], pf=s["pf"], net=s["net"], dd=s["max_dd"], conc=s["best_month_share"])
    return out


def evaluate(inst, v):
    tr = simulate(inst, v)
    if len(tr) < 20:
        return None
    g = stats_split(tr)
    n = stats_split(simulate(inst, v, 0.0002))
    row = dict(v)
    for tag in ("full", "tr", "ho"):
        row[f"{tag}_n"], row[f"{tag}_pf"], row[f"{tag}_net"] = g[tag]["n"], g[tag]["pf"], g[tag]["net"]
        row[f"{tag}_dd"], row[f"{tag}_conc"] = g[tag]["dd"], g[tag]["conc"]
        row[f"{tag}_cost_net"] = n[tag]["net"]
    return row


CONTROLS = {
    "CRUDE": {"CTRL crude#1": dict(entry="flip", lb=5, rr=4.0, min_sl=1.5, max_sl=3.0, sw=10, hold=0, trend="e922", pb=99.0,
                                   adx=0.0, sess="full", flat=None, day=0.0),
              "CTRL crude v5.1 shipped": dict(entry="flip+bo", lb=5, rr=3.0, min_sl=1.5, max_sl=3.0, sw=10, hold=3,
                                              trend="e922+200", pb=1.0, adx=15.0, sess="full", flat="22:45", day=150.0)},
    "BANKNIFTY": {"CTRL bnf flip RR3": dict(entry="flip", lb=5, rr=3.0, min_sl=1.5, max_sl=3.0, sw=10, hold=0, trend="e922",
                                            pb=99.0, adx=0.0, sess="full", flat="15:00", day=300.0),
                  "CTRL bnf v5.1 shipped": dict(entry="flip+bo", lb=5, rr=4.0, min_sl=1.5, max_sl=3.0, sw=10, hold=3,
                                                trend="e922+200", pb=1.0, adx=20.0, sess="full", flat="14:30", day=300.0)},
}

if __name__ == "__main__":
    inst = sys.argv[1]
    rng = random.Random(20260926 + (0 if inst == "CRUDE" else 1))
    rows = []
    for name, v in CONTROLS[inst].items():
        r = evaluate(inst, v)
        if r:
            r["id"] = name
            rows.append(r)
    for i in range(100):
        r = evaluate(inst, draw(inst, rng))
        if r:
            r["id"] = f"V{i + 1:03d}"
            rows.append(r)
        if (i + 1) % 20 == 0:
            print(f"[{inst}] {i + 1}/100", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / f"variants100_{inst}.csv", index=False)
    print(f"DONE {inst}: {len(R)} rows", flush=True)
