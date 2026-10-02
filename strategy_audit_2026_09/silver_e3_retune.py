"""Coordinate-search retune of silver E3 under pre_registration_silver_e3_retune_2026_10_03.md.
Selection sees DEVELOPMENT data only (oldest 80% of exits). Holdout is printed once, at the end, for incumbent vs final."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

LIVE = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
BARS = {"SILVER1": rs.load("MCX_SILVER1"), "SILVERM1": rs.load("MCX_SILVERM1")}
INCUMBENT = dict(earliest=12, rr=3.0, min_sl=2.5, max_sl=5.0, bo_lookback=3, day_limit=350, excl=(15, 16))
OPTIONS = [("earliest", [11, 13]), ("rr", [2.5, 3.5, 4.0]), ("sl", [(2.0, 4.5), (2.5, 4.0), (3.0, 5.0)]),
           ("bo_lookback", [2, 4, 5]), ("day_limit", [250, 500, 0]), ("excl", [(15, 16, 22, 23), (15, 16, 18)])]
CACHE = {}


def run(cfg, name="SILVER1"):
    key = (tuple(sorted(cfg.items())), name)
    if key in CACHE:
        return CACHE[key]
    p = dict(LIVE, rr=cfg["rr"], min_sl=cfg["min_sl"], max_sl=cfg["max_sl"], bo_lookback=cfg["bo_lookback"],
             day_loss_limit_pts=cfg["day_limit"], exclude_hours=list(cfg["excl"]))
    f = rs.v40.v40_frame(BARS[name], p)
    early = (f.time.dt.hour * 60 + f.time.dt.minute) < cfg["earliest"] * 60
    f["ok_l"] &= ~early
    f["ok_s"] &= ~early
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    CACHE[key] = t
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return w / l if l > 0 else 9.9


def streak(s):
    best = cur = 0
    for v in s:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def metrics(t):
    if len(t) < 5:
        return dict(n=len(t))
    mo = t.groupby(t.exit_time.dt.to_period("M")).R.sum()
    eq = t.R.cumsum()
    dd = (eq.cummax() - eq).max()
    q = t.exit_time.quantile([.6, .8])
    return dict(n=len(t), exp_R=t.R.mean(), pf_R=pf(t.R), pf_pts=pf(t.net), net_pts=t.net.sum(), net_R=t.R.sum(), dd_R=dd,
                net_dd=t.R.sum() / dd if dd else 0, win=100 * (t.net > 0).mean(), pos_m=100 * (mo > 0).mean(),
                streak=streak(t.net), hold_h=t.hold_h.mean(), med_hold=t.hold_h.median(),
                pf_tr=pf(t[t.exit_time <= q[.6]].R), pf_va=pf(t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])].R))


def split(t):
    cut = t.exit_time.quantile(.8)
    return t[t.exit_time <= cut], t[t.exit_time > cut]


def dev_metrics(cfg):
    dev, _ = split(run(cfg))
    return metrics(dev)


def accepts(new, inc):
    return (new["exp_R"] >= inc["exp_R"] + .01 and new["dd_R"] <= inc["dd_R"] * 1.05 and new["pos_m"] >= inc["pos_m"] - 3
            and new["n"] >= 500 and min(new["pf_tr"], new["pf_va"]) >= min(inc["pf_tr"], inc["pf_va"]) - .02)


def setdim(cfg, dim, v):
    c = dict(cfg)
    if dim == "sl":
        c["min_sl"], c["max_sl"] = v
    else:
        c[dim] = v
    return c


pd.set_option("display.width", 250)
cols = ["n", "exp_R", "pf_R", "dd_R", "net_dd", "win", "pos_m", "streak", "hold_h", "pf_tr", "pf_va"]
inc, inc_m = dict(INCUMBENT), dev_metrics(INCUMBENT)
print("DEVELOPMENT metrics of the incumbent (E3):", {k: round(v, 3) for k, v in inc_m.items()}, flush=True)
log = []
for dim, vals in OPTIONS:
    rows = []
    for v in vals:
        m = dev_metrics(setdim(inc, dim, v))
        rows.append(dict(dim=dim, value=str(v), ok=accepts(m, inc_m), **{c: m.get(c) for c in cols}))
    df = pd.DataFrame(rows)
    print(f"\n-- {dim} (incumbent now: {inc[dim] if dim != 'sl' else (inc['min_sl'], inc['max_sl'])})")
    print(df.round(3).to_string(index=False), flush=True)
    log.append(df)
    good = df[df.ok]
    if len(good):
        best = good.sort_values("exp_R", ascending=False).iloc[0]
        v = next(x for x in vals if str(x) == best.value)
        inc = setdim(inc, dim, v)
        inc_m = dev_metrics(inc)
        print(f"   ACCEPTED {dim} = {v}")
    else:
        print("   no change accepted")
pd.concat(log).to_csv("research_data/silver_e3_retune_dev.csv", index=False)
final = inc
print("\nFINAL CONFIG:", final, "\nCHANGES VS E3:", {k: (INCUMBENT[k], final[k]) for k in INCUMBENT if INCUMBENT[k] != final[k]})

# ---- C. neighbour robustness
print("\nC. neighbours (dev PF-R must stay >= 1.0):")
for dim, vals in OPTIONS:
    if INCUMBENT[dim] != final[dim] if dim != "sl" else (INCUMBENT["min_sl"], INCUMBENT["max_sl"]) != (final["min_sl"], final["max_sl"]):
        for v in vals:
            m = dev_metrics(setdim(final, dim, v))
            print(f"   {dim}={v}: PF-R {m['pf_R']:.2f}  exp_R {m['exp_R']:.3f}  n {m['n']}")

# ---- A. holdout, once
print("\nA. HOLDOUT (newest 20% of exits), looked at once:")
hold = {}
for nm, cfg in (("E3 incumbent", INCUMBENT), ("final", final)):
    hold[nm] = metrics(split(run(cfg))[1])
print(pd.DataFrame(hold).round(3).to_string())

# ---- B. SILVERM1 cross-check (all data)
print("\nB. SILVERM1 bars, all data:")
b = {nm: metrics(run(cfg, "SILVERM1")) for nm, cfg in (("E3 incumbent", INCUMBENT), ("final", final))}
b["live v4.1 (no 12:00 rule)"] = metrics(run(dict(INCUMBENT, earliest=0), "SILVERM1"))
print(pd.DataFrame(b).round(3).to_string())

# ---- D. bootstrap on all data
rng = np.random.default_rng(5)
A, Bt = run(INCUMBENT), run(final)
months = sorted(set(A.exit_time.dt.to_period("M")) | set(Bt.exit_time.dt.to_period("M")))
ga = {m: g for m, g in A.groupby(A.exit_time.dt.to_period("M"))}
gb = {m: g for m, g in Bt.groupby(Bt.exit_time.dt.to_period("M"))}
d_exp, d_dd = [], []
for _ in range(3000):
    pick = [months[i] for i in rng.choice(len(months), len(months))]
    xa, xb = pd.concat([ga[m] for m in pick if m in ga]), pd.concat([gb[m] for m in pick if m in gb])
    d_exp.append(xb.R.mean() - xa.R.mean())
    ea, eb = xa.R.cumsum(), xb.R.cumsum()
    d_dd.append((eb.cummax() - eb).max() - (ea.cummax() - ea).max())
for nm, d, better in (("expectancy R/trade", d_exp, lambda d: d > 0), ("max drawdown R", d_dd, lambda d: d < 0)):
    d = np.array(d)
    print(f"D. final minus E3, {nm}: median {np.median(d):.3f}  90% range [{np.percentile(d, 5):.3f}, {np.percentile(d, 95):.3f}]  P(final better) {better(d).mean():.0%}")
print("\nFULL-HISTORY side by side (all 33 months, informational):")
print(pd.DataFrame({"E3 incumbent": metrics(A), "final": metrics(Bt), "live v4.1": metrics(run(dict(INCUMBENT, earliest=0)))}).round(3).to_string())
