"""BankNifty v5.0 R:R + force-flat sweep. Pre-registration: pre_registration_bnf_exit_2026_09_26.md
Entries frozen; only rr, the flat time and the ADX gate vary. Gross points."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

T0 = pd.Timestamp("2024-03-25")
FLATS = ("14:30", "15:00", "15:15", "15:20")
RRS = (1.5, 2.0, 2.5, 3.0, 4.0)


def gated(f, p, use_adx):
    cap = p["max_sl"] * f["atr"]
    vol = f["vol_regime_ok"] if p.get("use_vol_filter") else True
    base = f["in_sess"] & f["sha_stable"] & f["atr_ok"] & vol & ~f["in_flat_window"]
    if use_adx:
        base = base & f["adx_ok"]
    tl = (f["e9"] > f["e22"]) & (f["close"] > f["e200"])
    ts = (f["e9"] < f["e22"]) & (f["close"] < f["e200"])
    g = f.copy()
    g["ok_l"] = base & f["flip_up"] & tl & (f["risk_l"] <= cap) & f["near_ema9_l"]
    g["ok_s"] = base & f["flip_dn"] & ts & (f["risk_s"] <= cap) & f["near_ema9_s"] & ~g["ok_l"]
    return g


def split(tr):
    t = pd.DataFrame(tr).sort_values("exit_time").reset_index(drop=True)
    n = len(t); a, b = int(n * .6), int(n * .8)
    return {k: rs.stats(v.to_dict("records")) for k, v in
            (("FULL", t), ("TRAIN", t[:a]), ("VALID", t[a:b]), ("HOLDOUT", t[b:]))}, t


def run(flat, rr, use_adx, cfg, commission=0.0):
    p = dict(v50.V50_INSTRUMENT_PARAMS["BANKNIFTY"])
    p["atr_min_pts"] = cfg["strategy"].get("BANKNIFTY", {}).get("atr_min_pts", 0)
    p["rr"] = rr
    entry_end = min(flat, "15:00")
    p["session"] = ["09:30", entry_end]
    p["force_flat_window"] = [flat, "15:30"]
    f = v50.v50_frame(rs.load("NSE_BANKNIFTY1"), p)
    s0 = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    tr = rs.simulate(gated(f, p, use_adx), dict(p, day_loss_limit_pts=p["day_loss_limit"]),
                     start=s0, flat_at=flat, commission=commission)
    return tr


def row(flat, rr, use_adx, tr):
    S, t = split(tr)
    F = S["FULL"]
    ex = pd.Series([x["result"] for x in tr]).value_counts()
    return dict(flat=flat, rr=rr, adx="on" if use_adx else "off", n=F["n"], pf=F["pf"], net=F["net"],
                max_dd=F["max_dd"], win=F["win_pct"], pos_m=F["pos_months_pct"], best_m=F["best_month_share"],
                tp=int(ex.get("TP", 0)), sl=int(ex.get("SL", 0)), flat_exit=int(ex.get("FLAT", 0)),
                tp_pct=round(100 * ex.get("TP", 0) / len(tr), 1), hold_h=F["avg_hold_h"],
                pf_train=S["TRAIN"].get("pf"), pf_valid=S["VALID"].get("pf"), pf_hold=S["HOLDOUT"].get("pf"))


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    cfg = load_config()
    rows = []
    for flat in FLATS:
        for rr in RRS:
            for use_adx in (True, False):
                tr = run(flat, rr, use_adx, cfg)
                if tr:
                    rows.append(row(flat, rr, use_adx, tr))
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "bnf_exit_sweep.csv", index=False)

    elig = R[R.n >= 40].sort_values("pf_train", ascending=False)
    print("=== PRE-REGISTERED PICK: highest TRAIN PF with >=40 trades (top 6) ===")
    cols = ["flat","rr","adx","n","pf","net","max_dd","win","pos_m","best_m","tp","sl","flat_exit","tp_pct","pf_train","pf_valid","pf_hold"]
    print(elig[cols].head(6).to_string(index=False))
    print("\n=== shipped config for reference ===")
    print(R[(R.flat=="14:30") & (R.rr==4.0) & (R.adx=="on")][cols].to_string(index=False))
    print("\n=== take-profit share by flat time and rr (ADX on) - the thing being fixed ===")
    print(R[R.adx=="on"].pivot(index="rr", columns="flat", values="tp_pct").to_string())
    print("\n=== full PF by flat time and rr (ADX on) ===")
    print(R[R.adx=="on"].pivot(index="rr", columns="flat", values="pf").round(3).to_string())
    print("\n=== full PF by flat time and rr (ADX off) ===")
    print(R[R.adx=="off"].pivot(index="rr", columns="flat", values="pf").round(3).to_string())
    print("\ncombos:", len(R), "| eligible (n>=40):", len(elig), "| n>=100:", int((R.n>=100).sum()))
