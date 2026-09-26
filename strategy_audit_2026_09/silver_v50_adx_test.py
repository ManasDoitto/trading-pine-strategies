import sys
sys.path.insert(0, r"D:\Trading code-Claude")
sys.path.insert(0, r"D:\Trading code-Claude\strategy_audit_2026_09")
import pandas as pd, research_sim as rs
from trading_agents.core import signals_v50 as v50
from trading_agents.core.config import load_config

cfg = load_config()
T0 = pd.Timestamp("2024-03-25")

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
    n = len(t); a, b = int(n*.6), int(n*.8)
    return {k: rs.stats(v.to_dict("records")) for k, v in
            (("FULL", t), ("TRAIN", t[:a]), ("VALID", t[a:b]), ("HOLDOUT", t[b:]))}

def gates(S):
    F = S["FULL"]
    ok = dict(pf3=all(S[k].get("pf",0) >= 1.30 for k in ("TRAIN","VALID","HOLDOUT")),
              n100=F["n"] >= 100, m70=F["pos_months_pct"] >= 70,
              c25=(F["best_month_share"] is not None and F["best_month_share"] <= 25))
    return ok, all(ok.values())

for sym, bars in (("SILVER1", "MCX_SILVER1"), ("SILVERM1", "MCX_SILVERM1")):
    p = dict(v50.V50_INSTRUMENT_PARAMS["SILVER"])
    p["atr_min_pts"] = cfg["strategy"].get("SILVER", {}).get("atr_min_pts", 0)
    f = v50.v50_frame(rs.load(bars), p)
    s0 = max(int((f["time"] >= T0).idxmax()), rs.WARMUP)
    print(f"\n===== MCX:{sym}  30 months, gross points (no costs) =====")
    for use_adx in (True, False):
        tr = rs.simulate(gated(f, p, use_adx), dict(p, day_loss_limit_pts=p["day_loss_limit"]),
                         start=s0, flat_at=p["force_flat_window"][0], commission=0.0)
        S = split(tr); F = S["FULL"]; g, passed = gates(S)
        tag = "ADX>=30 (as shipped)" if use_adx else "ADX gate OFF"
        print(f"{tag:22s} n={F['n']:4d} PF={F['pf']:6.3f} net={F['net']:+10.1f} maxDD={F['max_dd']:8.1f} "
              f"win={F['win_pct']:4.1f}% posM={F['pos_months_pct']:4.1f}% bestM={F['best_month_share']:6}"
              f" | TR {S['TRAIN']['pf']:.3f} VA {S['VALID']['pf']:.3f} HO {S['HOLDOUT']['pf']:.3f}"
              f" | PASS={passed} {[k for k,v in g.items() if not v]}")
