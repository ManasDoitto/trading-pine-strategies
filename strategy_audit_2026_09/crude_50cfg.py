"""50 untested crude #1 configs. Pre-registration: pre_registration_crude_50cfg_2026_09_27.md"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
import silver_sweep as SS
from trading_agents.core import signals_v50 as v50

T0 = pd.Timestamp("2024-03-25"); SPLIT = pd.Timestamp("2025-06-25")
_D = {}
def data(fast=9, slow=22):
    k = (fast, slow)
    if k not in _D:
        d = SS.base("MCX_CRUDEOIL1")
        d["e9"] = v50.ema(d["close"], fast); d["e22"] = v50.ema(d["close"], slow)
        _D[k] = d
    return _D[k]

BASE = dict(start="09:15", end="23:30", fast=9, slow=22, hold=0, sw=10, min_sl=1.5, max_sl=3.0, rr=4.0, adx=0.0, vol=False,
            skip_fri=False, skip_h=None, flat=None, be=None, trail=None, tstop=None, maxday=None)

def simulate(v, comm=0.0):
    d = data(v["fast"], v["slow"])
    ff = [v["flat"], "23:30"] if v["flat"] else ["23:59", "23:59"]
    p = dict(sha_len1=10, sha_len2=10, sha_min_hold=v["hold"], sw_len=v["sw"], sw_buf=0.1, min_sl=v["min_sl"], max_sl=v["max_sl"],
             rr=v["rr"], adx_min=v["adx"], pb_atr_mult=99.0, atr_min_pts=0, use_vol_filter=False, vol_sma_len=50, use200=False,
             day_loss_limit=0.0, session=[v["start"], v["end"]], force_flat_window=ff)
    f = SS.frame(d, p)
    cap = p["max_sl"] * f["atr"]
    gate = f["in_sess"] & f["adx_ok"] & ~f["in_flat_window"]
    if v["vol"]: gate = gate & (f["atr"] > f["atr"].rolling(50).mean())
    if v["skip_fri"]: gate = gate & (f["time"].dt.dayofweek != 4)
    if v["skip_h"] is not None: gate = gate & (f["time"].dt.hour != v["skip_h"])
    L = f["flip_up"] & f["sha_stable"] & (f["e9"] > f["e22"]); S = f["flip_dn"] & f["sha_stable"] & (f["e9"] < f["e22"])
    g = f.copy()
    g["ok_l"] = gate & L & (f["risk_l"] <= cap)
    g["ok_s"] = gate & S & (f["risk_s"] <= cap) & ~g["ok_l"]
    s0 = max(int((g["time"] >= T0).idxmax()), rs.WARMUP)
    kw = {}
    if v["be"]: kw["be_at_r"] = v["be"]
    if v["trail"]: kw["trail_start_r"], kw["trail_dist_r"] = v["trail"]
    return rs.simulate(g, dict(p, day_loss_limit_pts=0.0), start=s0, flat_at=v["flat"], commission=comm,
                       time_stop_min=v["tstop"], max_per_day=v["maxday"], **kw)

IDEAS = {
 "be 1.0R": dict(be=1.0), "be 2.0R": dict(be=2.0), "trail 2R/2R": dict(trail=(2.0, 2.0)), "trail 3R/1.5R": dict(trail=(3.0, 1.5)),
 "time 4h": dict(tstop=240), "time 8h": dict(tstop=480), "time 16h": dict(tstop=960),
 "no overnight": dict(end="22:30", flat="23:25"), "max 1/day": dict(maxday=1), "max 2/day": dict(maxday=2),
 "ema 8/21": dict(fast=8, slow=21), "ema 12/26": dict(fast=12, slow=26), "ema 9/34": dict(fast=9, slow=34),
 "hold 2": dict(hold=2), "hold 4": dict(hold=4), "atr>sma50": dict(vol=True), "adx15>=20": dict(adx=20.0),
 "skip Fri": dict(skip_fri=True), "skip 22h": dict(skip_h=22), "sw 7": dict(sw=7), "sw 14": dict(sw=14),
 "minSL 1.75": dict(min_sl=1.75), "rr 3.5": dict(rr=3.5), "rr 4.5": dict(rr=4.5), "trail 1.5R/1R": dict(trail=(1.5, 1.0)),
}
def configs():
    out = [("CTRL 09:15", dict(BASE)), ("CTRL 17:30", dict(BASE, start="17:30"))]
    for st in ("09:15", "17:30"):
        for k, o in IDEAS.items():
            out.append((f"{k} @{st}", dict(BASE, start=st, **o)))
    return out

def summ(tag, v):
    tr, trn = simulate(v), simulate(v, 0.0002)
    if len(tr) < 20: return dict(id=tag, n=len(tr))
    row = dict(id=tag, start=v["start"])
    for name, sub in (("full", None), ("tr", "<"), ("ho", ">=")):
        for suf, T in (("", tr), ("c", trn)):
            t = pd.DataFrame(T); t["x"] = pd.to_datetime(t["exit_time"])
            if sub == "<": t = t[t.x < SPLIT]
            elif sub == ">=": t = t[t.x >= SPLIT]
            s = rs.stats(t.to_dict("records")) if len(t) else dict(n=0, pf=0, net=0, max_dd=0, best_month_share=None)
            if suf == "": row.update({f"{name}_n": s["n"], f"{name}_pf": s["pf"], f"{name}_net": round(s["net"]), f"{name}_dd": round(s["max_dd"]) if s["n"] else 0, f"{name}_conc": s["best_month_share"]})
            else: row[f"{name}_cnet"] = round(s["net"])
    return row

if __name__ == "__main__":
    rows = [summ(t, v) for t, v in configs()]
    R = pd.DataFrame(rows); R.to_csv(ROOT / "research_data" / "crude_50cfg.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(R[["id", "full_n", "full_pf", "full_net", "full_cnet", "tr_net", "ho_net", "ho_cnet", "full_dd", "full_conc"]].to_string(index=False))
