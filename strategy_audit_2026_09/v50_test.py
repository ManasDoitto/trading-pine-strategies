"""v5.0 SHA-ADX Hybrid on crude / BankNifty / silver, 30 months. Pre-registration: pre_registration_v50_2026_09_26.md
Signals come from trading_agents/core/signals_v50.py UNCHANGED; only the fill/exit loop is research_sim (costs + gap fills)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_sim as rs
from trading_agents.core import signals as v40
from trading_agents.core import signals_v50 as v50

T0 = pd.Timestamp("2024-03-25")
COMM = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0002   # per side; user asked for gross points (0) on 2026-09-26
TAG = "" if COMM else "_gross"
COMMON = dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, sha_min_hold=3, breakout_lookback=5,
              use_quality_filters=False, vol_sma_len=80, entry_mode="flip", atr_min_pts=0)
CFG = {
    "CRUDE": dict(COMMON, bars="MCX_CRUDEOIL1", cache="CRUDEOIL", session=["09:15", "23:30"],
                  force_flat_window=["22:45", "23:30"], min_sl=1.5, max_sl=3.0, rr=3.0, adx_min=30.0,
                  pb_atr_mult=1.0, use_vol_filter=False, day_loss_limit=0.0, claim=dict(pf=3.82, net=4677)),
    "BANKNIFTY": dict(COMMON, bars="NSE_BANKNIFTY1", cache="BANKNIFTY", session=["09:30", "15:00"],
                      force_flat_window=["14:45", "15:00"], min_sl=1.5, max_sl=3.0, rr=3.5, adx_min=25.0,
                      pb_atr_mult=0.5, use_vol_filter=True, day_loss_limit=0.0, claim=dict(pf=1.494, net=1807)),
    "SILVER": dict(COMMON, bars="MCX_SILVER1", cache="SILVER", session=["09:15", "23:30"],
                   force_flat_window=["22:45", "23:30"], min_sl=2.5, max_sl=5.0, rr=4.0, adx_min=30.0,
                   pb_atr_mult=0.5, use_vol_filter=False, day_loss_limit=300.0, claim=dict(pf=2.04, net=3518)),
}
CFG["SILVERM"] = dict(CFG["SILVER"], bars="MCX_SILVERM1")


def gated(f, p, use200):
    """v5.0 entry = signals_v50 own components, with ADX / pullback folded in (signals_v50.simulate applies them at arm time)."""
    cap = p["max_sl"] * f["atr"]
    vol_ok = f["vol_regime_ok"] if p["use_vol_filter"] else True
    tl = (f["e9"] > f["e22"]) & ((f["close"] > f["e200"]) if use200 else True)
    ts = (f["e9"] < f["e22"]) & ((f["close"] < f["e200"]) if use200 else True)
    base = f["in_sess"] & f["sha_stable"] & f["atr_ok"] & vol_ok & f["adx_ok"] & ~f["in_flat_window"]
    g = f.copy()
    g["ok_l"] = base & f["flip_up"] & tl & (f["risk_l"] <= cap) & f["near_ema9_l"]
    g["ok_s"] = base & f["flip_dn"] & ts & (f["risk_s"] <= cap) & f["near_ema9_s"]
    return g


def baseline_frame(df, p):
    """Ancestor: plain v4.0 SHA flip + EMA9/22, same stops / RR / session as the v5.0 config."""
    q = dict(sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, min_sl=p["min_sl"], max_sl=p["max_sl"],
             rr=p["rr"], session=p["session"])
    return v40.v40_frame(df, q), q


def start_idx(df):
    return max(int((df["time"] >= T0).idxmax()), rs.WARMUP)


def split(trades):
    t = pd.DataFrame(trades).sort_values("exit_time").reset_index(drop=True)
    n = len(t)
    a, b = int(n * .6), int(n * .8)
    return {k: rs.stats(v.to_dict("records")) for k, v in
            (("FULL", t), ("TRAIN", t[:a]), ("VALID", t[a:b]), ("HOLDOUT", t[b:]))}


def verdict(S, B):
    F = S["FULL"]
    g = dict(pf_all3=all(S[k].get("pf", 0) >= 1.30 for k in ("TRAIN", "VALID", "HOLDOUT")),
             n100=F["n"] >= 100, months70=F["pos_months_pct"] >= 70,
             conc25=(F["best_month_share"] is not None and F["best_month_share"] <= 25),
             beats_base=(S["HOLDOUT"].get("pf", 0) > B["HOLDOUT"].get("pf", 0) and F["max_dd"] <= B["FULL"]["max_dd"]))
    return g, all(g.values())


def run_all():
    out = []
    for name, p in CFG.items():
        df = rs.load(p["bars"])
        f = v50.v50_frame(df, p)
        s0 = start_idx(f)
        unsat = int((f["atr"] >= f["risk_l"]).sum() + (f["atr"] >= f["risk_s"]).sum())  # the Pine atr >= risk gate
        bf, bq = baseline_frame(df, p)
        B = split(rs.simulate(bf, bq, start=s0, commission=COMM))
        flat_at = p["force_flat_window"][0]
        for use200 in (True, False):
            g = gated(f, p, use200)
            tr = rs.simulate(g, dict(p, day_loss_limit_pts=p["day_loss_limit"]), start=s0, flat_at=flat_at, commission=COMM)
            if not tr:
                print(name, "e200" if use200 else "noE200", "NO TRADES")
                continue
            S = split(tr)
            gates, ok = verdict(S, B)
            F = S["FULL"]
            out.append(dict(strategy=name, e200=use200, n=F["n"], pf=F["pf"], net=F["net"], dd=F["max_dd"],
                            win=F["win_pct"], posM=F["pos_months_pct"], bestM=F["best_month_share"],
                            tr=S["TRAIN"].get("pf"), va=S["VALID"].get("pf"), ho=S["HOLDOUT"].get("pf"),
                            net_tr=S["TRAIN"].get("net"), net_va=S["VALID"].get("net"), net_ho=S["HOLDOUT"].get("net"),
                            base_n=B["FULL"]["n"], base_pf=B["FULL"]["pf"], base_net=B["FULL"]["net"],
                            base_dd=B["FULL"]["max_dd"], base_ho=B["HOLDOUT"].get("pf"),
                            pine_atr_gate_true_bars=unsat, PASS=ok, **{"g_" + k: v for k, v in gates.items()}))
    return pd.DataFrame(out)


def pf_of(pnl):
    w, l = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    return w / l if l else np.inf


def reproduce():
    """Original engine, original Dhan cache, gross points: does the README full-history number reproduce?"""
    rows = []
    for name in ("CRUDE", "BANKNIFTY", "SILVER"):
        p = CFG[name]
        path = ROOT / "journal_data" / "cache" / "backtest" / f"{p['cache']}_5min.csv"
        b = pd.read_csv(path, parse_dates=["time"])
        f = v50.v50_frame(b, p)
        tr, _, _ = v50.simulate(f, dict(p), start=v50.WARMUP_BARS)
        if not tr:
            rows.append(dict(strategy=name, n=0))
            continue
        T = pd.DataFrame(tr)
        T["entry_time"] = pd.to_datetime(T["entry_time"])
        pnl = T["pnl_pts"]
        wpf, cur = [], T["entry_time"].min()
        while cur < T["entry_time"].max():
            m = T[(T["entry_time"] >= cur) & (T["entry_time"] < cur + pd.Timedelta(days=90))]["pnl_pts"]
            if len(m):
                wpf.append((pf_of(m), m.sum()))
            cur += pd.Timedelta(days=30)
        fin = [x[0] for x in wpf if np.isfinite(x[0])]
        rows.append(dict(strategy=name, cache_from=str(b["time"].iloc[0])[:10], cache_to=str(b["time"].iloc[-1])[:10],
                         n=len(T), pooled_pf=round(pf_of(pnl), 3), net=round(pnl.sum(), 1),
                         win=round(100 * (pnl > 0).mean(), 1), claim_pf=p["claim"]["pf"], claim_net=p["claim"]["net"],
                         windows=len(wpf), wf_mean_pf_finite=round(float(np.mean(fin)), 2),
                         wf_median_pf=round(float(np.median([x[0] for x in wpf])), 2),
                         wf_windows_inf=int(sum(not np.isfinite(x[0]) for x in wpf)),
                         wf_pos_windows=int(sum(x[1] > 0 for x in wpf))))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    R = run_all()
    R.to_csv(ROOT / "research_data" / f"v50_results{TAG}.csv", index=False)
    print(R[["strategy", "e200", "n", "pf", "net", "dd", "win", "posM", "bestM", "tr", "va", "ho", "PASS"]].to_string(index=False))
    print("\nbaseline (plain v4.0, same stops/RR/session), same window:")
    print(R.drop_duplicates("strategy")[["strategy", "base_n", "base_pf", "base_net", "base_dd", "base_ho"]].to_string(index=False))
    u = R.drop_duplicates("strategy")
    print("\nPine atr>=risk gate true on N bars (need >0 to trade at all):", dict(zip(u.strategy, u.pine_atr_gate_true_bars)))
    print("\ngate detail:")
    print(R[["strategy", "e200"] + [c for c in R.columns if c.startswith("g_")]].to_string(index=False))
    print("\n=== reproduction on original Dhan cache (gross, original engine) ===")
    print(reproduce().to_string(index=False))
