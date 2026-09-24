"""Run the 50 standard strategies (+100 random-direction controls) under the pre-registered template and gates."""
import sys
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs, std50

INST = {"BANKNIFTY": ("NSE_BANKNIFTY1", 14 * 60 + 30, "15:20"),
        "CRUDE": ("MCX_CRUDEOIL1", 22 * 60 + 30, "23:25"),
        "SILVER": ("MCX_SILVER1", 22 * 60 + 30, "23:25"),
        "SILVERM": ("MCX_SILVERM1", 22 * 60 + 30, "23:25")}
P = dict(rr=4.0)


def frame(d, L, Sh, last_entry):
    f = d.copy()
    win = (f.minute <= last_entry) & f.atr.notna()
    f["ok_l"] = L & win
    f["ok_s"] = Sh & win & ~f["ok_l"]
    f["risk_l"] = f["risk_s"] = 3.0 * f.atr
    return f


def gates(trades):
    """Pre-registered criteria. Returns (dict of metrics, pass bool)."""
    if len(trades) < 30:
        return dict(n=len(trades)), False
    t = pd.DataFrame(trades)
    t["exit_time"] = pd.to_datetime(t.exit_time)
    q = t.exit_time.quantile([.6, .8]).tolist()
    segs = (t[t.exit_time <= q[0]], t[(t.exit_time > q[0]) & (t.exit_time <= q[1])], t[t.exit_time > q[1]])

    def pf(x):
        w, ls = x.net[x.net > 0].sum(), -x.net[x.net < 0].sum()
        return w / ls if ls > 0 else (9.9 if w > 0 else 0)
    m = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    net = t.net.sum()
    r = dict(n=len(t), pf=round(pf(t), 2), net=round(net, 1), pf_tr=round(pf(segs[0]), 2), pf_va=round(pf(segs[1]), 2),
             pf_ho=round(pf(segs[2]), 2), pos_m=round(100 * (m > 0).mean()), best_m=round(100 * m.max() / net) if net > 0 else None)
    ok = (min(r["pf_tr"], r["pf_va"], r["pf_ho"]) >= 1.30 and r["n"] >= 150 and r["pos_m"] >= 70
          and r["best_m"] is not None and r["best_m"] <= 25)
    return r, ok


def sim(f, flat):
    return rs.simulate(f, P, start=250, flat_at=flat, max_per_day=2)


rows, rand_rows = [], []
for inst, (name, last, flat) in INST.items():
    d = std50.prep(rs.load(name))
    for i, (nm, L, Sh) in std50.S(d).items():
        r, ok = gates(sim(frame(d, L, Sh, last), flat))
        rows.append(dict(inst=inst, id=i, name=nm, passed=ok, **r))
    rng = np.random.default_rng(7)
    for k in range(100):
        fire = pd.Series(rng.random(len(d)) < .01, index=d.index)
        side = pd.Series(rng.random(len(d)) < .5, index=d.index)
        r, ok = gates(sim(frame(d, fire & side, fire & ~side, last), flat))
        rand_rows.append(dict(inst=inst, passed=ok, **r))
    print(inst, "done", file=sys.stderr, flush=True)

R, C = pd.DataFrame(rows), pd.DataFrame(rand_rows)
R.to_csv("research_data/std50_wide_results.csv", index=False)
C.to_csv("research_data/std50_wide_random_control.csv", index=False)
pd.set_option("display.width", 250, "display.max_rows", 300)
print("REAL passes:", int(R.passed.sum()), "of", len(R), "| RANDOM passes:", int(C.passed.sum()), "of", len(C))
print(R[R.passed].to_string(index=False))
print("\nRandom control PF (median, 95th pct) by instrument:")
print(C.groupby("inst").pf.describe(percentiles=[.5, .95])[["50%", "95%", "max"]].round(2))
print("\nBest 15 by holdout PF among n>=150 (NOT passes; for reference):")
print(R[R.n >= 150].sort_values("pf_ho", ascending=False).head(15).to_string(index=False))
print("\nPF distribution across all 200 real trials: median", R.pf.median(), " share PF>1:", round((R.pf > 1).mean(), 2))
