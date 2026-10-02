"""Three equal-time samples of the SILVERM1 history; the deployed strategy and its leads evaluated in each.
Validated = net > 0 AND PF >= 1.10 in every one of the three samples. Trades are assigned to a sample by ENTRY time (indicators warm up on the full history)."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P0 = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
NAMES = {"SILVERM1": "MCX_SILVERM1", "SILVER1": "MCX_SILVER1"}
VARIANTS = {"A deployed": dict(), "B skip hours 13+17": dict(excl=[13, 15, 16, 17]), "C day limit 1500": dict(dl=1500),
            "D both B+C": dict(excl=[13, 15, 16, 17], dl=1500), "E long-only": dict(long_only=True)}


def run(bars, v):
    p = dict(P0)
    if "excl" in v: p["exclude_hours"] = v["excl"]
    if "dl" in v: p["day_loss_limit_pts"] = v["dl"]
    f = rs.v40.v40_frame(bars, p)
    if v.get("long_only"):
        f["ok_s"] = False
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def streak(flags):
    best = cur = 0
    for v in flags:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def stats(t, m0, m1):
    months = pd.period_range(m0, m1, freq="M")
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0)
    eq = t.net.cumsum()
    return {"trades": len(t), "win %": round(100 * (t.net > 0).mean(), 1), "PF": pf(t.net), "net pts": round(t.net.sum()), "exp R": round(t.R.mean(), 3),
            "max DD pts": round((eq.cummax() - eq).max()), "months +": f"{int((mo > 0).sum())}/{len(months)}", "worst month": round(mo.min()),
            "loss-month run": streak((mo < 0).to_numpy()), "best mo % net": round(100 * mo.max() / t.net.sum()) if t.net.sum() > 0 else None, "avg hold h": round(t.hold_h.mean(), 1)}


pd.set_option("display.width", 250, "display.max_rows", 200)
for dname, key in NAMES.items():
    bars = rs.load(key)
    t0, t1 = bars.time.iloc[400], bars.time.iloc[-1]
    cuts = [t0 + (t1 - t0) * k / 3 for k in (0, 1, 2, 3)]
    labels = [f"S{i+1}" for i in range(3)]
    print(f"\n================ {dname} ({t0:%Y-%m-%d} -> {t1:%Y-%m-%d}) ================")
    for i in range(3):
        seg = bars[(bars.time >= cuts[i]) & (bars.time < cuts[i + 1] if i < 2 else bars.time <= cuts[3])]
        pr = (seg.close.iloc[-1] / seg.close.iloc[0] - 1) * 100
        rngs = (seg.high - seg.low)
        print(f"  {labels[i]}: {cuts[i]:%Y-%m-%d} -> {cuts[i+1]:%Y-%m-%d} | silver price change {pr:+.0f}% | median 5m bar range {rngs.median():.0f} pts")
    results = {v: run(bars, spec) for v, spec in VARIANTS.items()}
    verdict = {}
    for v, t in results.items():
        rows = {}
        for i in range(3):
            s = t[(t.entry_time >= cuts[i]) & (t.entry_time < cuts[i + 1] if i < 2 else t.entry_time <= cuts[3])]
            rows[labels[i]] = stats(s, cuts[i].to_period("M"), cuts[i + 1].to_period("M") if i < 2 else cuts[3].to_period("M"))
        rows["ALL"] = stats(t, cuts[0].to_period("M"), cuts[3].to_period("M"))
        verdict[v] = all(rows[l]["net pts"] > 0 and rows[l]["PF"] >= 1.10 for l in labels)
        print(f"\n--- {v}: {'VALIDATED' if verdict[v] else 'NOT validated'} (net>0 and PF>=1.10 in all three samples)")
        print(pd.DataFrame(rows).to_string())
    print("\nSUMMARY (PF by sample S1 / S2 / S3 / all, net points by sample):")
    for v, t in results.items():
        pfs, nets = [], []
        for i in range(3):
            s = t[(t.entry_time >= cuts[i]) & (t.entry_time < cuts[i + 1] if i < 2 else t.entry_time <= cuts[3])]
            pfs.append(pf(s.net)); nets.append(round(s.net.sum()))
        print(f"  {v:22} PF {pfs[0]:>5} / {pfs[1]:>5} / {pfs[2]:>5} / {pf(t.net):>5}   net {nets[0]:>8,} / {nets[1]:>8,} / {nets[2]:>8,}   -> {'VALIDATED' if verdict[v] else 'not validated'}")
