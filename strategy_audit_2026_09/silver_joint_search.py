"""Joint SILVER1 + SILVERM1 search (pre_registration_silver_joint_search_2026_10_03.md). Holdout printed once, for the selected config only."""
import itertools
import sys
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

LIVE_P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
BARS = {"SILVER1": rs.load("MCX_SILVER1"), "SILVERM1": rs.load("MCX_SILVERM1")}
LIVE = dict(earliest=0, rr=3.0, min_sl=2.5, max_sl=5.0, bo=3, dl=350)
FRAMES = {}


def frame(name, c):
    key = (name, c["min_sl"], c["max_sl"], c["bo"])
    if key not in FRAMES:
        p = dict(LIVE_P, min_sl=c["min_sl"], max_sl=c["max_sl"], bo_lookback=c["bo"])
        FRAMES[key] = rs.v40.v40_frame(BARS[name], p)
    return FRAMES[key]


def run(c, name):
    p = dict(LIVE_P, rr=c["rr"], min_sl=c["min_sl"], max_sl=c["max_sl"], bo_lookback=c["bo"], day_loss_limit_pts=c["dl"])
    f = frame(name, c).copy()
    early = (f.time.dt.hour * 60 + f.time.dt.minute) < c["earliest"] * 60
    f["ok_l"] &= ~early
    f["ok_s"] &= ~early
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
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
    mo = t.groupby(t.exit_time.dt.to_period("M")).R.sum()
    eq = t.R.cumsum()
    dd = (eq.cummax() - eq).max()
    q = t.exit_time.quantile([.6, .8])
    return dict(n=len(t), exp_R=t.R.mean(), pf_R=pf(t.R), pf_pts=pf(t.net), net_pts=t.net.sum(), net_R=t.R.sum(), dd_R=dd,
                net_dd=t.R.sum() / dd if dd else 0, win=100 * (t.net > 0).mean(), pos_m=100 * (mo > 0).mean(), streak=streak(t.net),
                hold_h=t.hold_h.mean(), pf_tr=pf(t[t.exit_time <= q[.6]].R), pf_va=pf(t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])].R))


def split(t):
    cut = t.exit_time.quantile(.8)
    return t[t.exit_time <= cut], t[t.exit_time > cut]


GRID = [dict(earliest=e, rr=r, min_sl=m, max_sl=x, bo=b, dl=d) for e, r, m, x, b, d in
        itertools.product([0, 12], [3.0, 4.0], [2.5, 3.0], [4.0, 5.0], [3, 4], [350, 500])]
assert len(GRID) == 64 and LIVE in GRID
lab = lambda c: f"e{c['earliest']}/rr{c['rr']:g}/sl{c['min_sl']:g}-{c['max_sl']:g}/bo{c['bo']}/dl{c['dl']}"

DEV, ALL = {}, {}
for i, c in enumerate(GRID):
    for n in BARS:
        t = run(c, n)
        ALL[(lab(c), n)] = t
        DEV[(lab(c), n)] = metrics(split(t)[0])
    print(f"{i + 1}/64 {lab(c)}", flush=True)

L = lab(LIVE)


def eligible(c):
    for n in BARS:
        m, b = DEV[(lab(c), n)], DEV[(L, n)]
        if not (m["exp_R"] >= b["exp_R"] and m["dd_R"] <= b["dd_R"] and m["pos_m"] >= b["pos_m"] - 3 and m["n"] >= 450
                and min(m["pf_tr"], m["pf_va"]) >= min(b["pf_tr"], b["pf_va"]) - .02 and m["hold_h"] <= b["hold_h"] * 1.10):
            return False
    return True


rows = []
for c in GRID:
    r = dict(cfg=lab(c), eligible=eligible(c) and lab(c) != L)
    for n in BARS:
        m = DEV[(lab(c), n)]
        r.update({f"{n}_{k}": round(m[k], 3) for k in ("n", "exp_R", "pf_R", "dd_R", "net_dd", "pos_m", "hold_h")})
    r["worse_net_dd"] = round(min(DEV[(lab(c), n)]["net_dd"] for n in BARS), 3)
    rows.append(r)
R = pd.DataFrame(rows)
R.to_csv("research_data/silver_joint_search_dev.csv", index=False)
pd.set_option("display.width", 250, "display.max_rows", 100)
print("\nDEV metrics, LIVE:", {n: {k: round(v, 3) for k, v in DEV[(L, n)].items()} for n in BARS})
print(f"\nELIGIBLE: {int(R.eligible.sum())} of 63 non-live configs")
print(R[R.eligible].sort_values("worse_net_dd", ascending=False).to_string(index=False))
print("\nTop 8 by worse-contract net/DD regardless of eligibility (information only):")
print(R.sort_values("worse_net_dd", ascending=False).head(8)[["cfg", "eligible", "worse_net_dd", "SILVER1_exp_R", "SILVERM1_exp_R", "SILVER1_dd_R", "SILVERM1_dd_R"]].to_string(index=False))

if not R.eligible.any():
    print("\nNOTHING ELIGIBLE: the live strategy stays. Search ends.")
    sys.exit(0)
pick = R[R.eligible].sort_values("worse_net_dd", ascending=False).iloc[0].cfg
pc = next(c for c in GRID if lab(c) == pick)
print("\nSELECTED:", pick)
print("\nHOLDOUT (newest 20%), looked at once:")
H = {}
ok = True
for n in BARS:
    for nm, cfg in (("live", LIVE), ("selected", pc)):
        H[(n, nm)] = metrics(split(ALL[(lab(cfg), n)])[1])
    a, b = H[(n, "live")], H[(n, "selected")]
    ok &= b["exp_R"] >= a["exp_R"] and b["dd_R"] <= a["dd_R"] and b["pos_m"] >= a["pos_m"] and b["hold_h"] <= a["hold_h"] * 1.10
print(pd.DataFrame({f"{n} {nm}": v for (n, nm), v in H.items()}).round(3).to_string())
print("\nHOLDOUT VERDICT:", "PASS" if ok else "FAIL")

print("\nFULL HISTORY, live vs selected:")
print(pd.DataFrame({f"{n} {nm}": metrics(ALL[(lab(cfg), n)]) for n in BARS for nm, cfg in (("live", LIVE), ("selected", pc))}).round(3).to_string())
rng = np.random.default_rng(3)
for n in BARS:
    A, B = ALL[(L, n)], ALL[(pick, n)]
    months = sorted(set(A.exit_time.dt.to_period("M")) | set(B.exit_time.dt.to_period("M")))
    ga = {m: g for m, g in A.groupby(A.exit_time.dt.to_period("M"))}
    gb = {m: g for m, g in B.groupby(B.exit_time.dt.to_period("M"))}
    de, dd_ = [], []
    for _ in range(3000):
        pk = [months[i] for i in rng.choice(len(months), len(months))]
        xa, xb = pd.concat([ga[m] for m in pk if m in ga]), pd.concat([gb[m] for m in pk if m in gb])
        de.append(xb.R.mean() - xa.R.mean())
        ea, eb = xa.R.cumsum(), xb.R.cumsum()
        dd_.append((eb.cummax() - eb).max() - (ea.cummax() - ea).max())
    print(f"bootstrap {n}, selected minus live: expectancy median {np.median(de):.3f} P(better) {np.mean(np.array(de) > 0):.0%} | "
          f"maxDD R median {np.median(dd_):.1f} P(lower) {np.mean(np.array(dd_) < 0):.0%}")
