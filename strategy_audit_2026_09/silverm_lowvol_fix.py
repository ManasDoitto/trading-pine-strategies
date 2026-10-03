"""Fix the weak S1+S2 periods (pre_registration_silverm_lowvol_fix_2026_10_03.md). Design on S1+S2, check on S3."""
import sys
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P0 = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
BARS = {"SILVERM1": rs.load("MCX_SILVERM1"), "SILVER1": rs.load("MCX_SILVER1")}
t0, t1 = BARS["SILVERM1"].time.iloc[400], BARS["SILVERM1"].time.iloc[-1]
C1, C2 = t0 + (t1 - t0) / 3, t0 + (t1 - t0) * 2 / 3
print("cuts:", C1, C2)
CACHE = {}


def frame(name, p):
    key = (name, p["bo_lookback"], p["min_sl"])
    if key not in CACHE:
        f = rs.v40.v40_frame(BARS[name], p)
        bo = p["bo_lookback"]
        f["dc_hi"] = f.high.rolling(bo).max().shift(1)
        f["dc_lo"] = f.low.rolling(bo).min().shift(1)
        f["hour"] = f.time.dt.hour
        CACHE[key] = f
    return CACHE[key]


SPEC = {"M1a minstop 250": dict(minstop=250), "M1b minstop 400": dict(minstop=400), "M1c minstop 600": dict(minstop=600),
        "M4a bo 5": dict(bo=5), "M4b bo 8": dict(bo=8), "M4c bo 12": dict(bo=12),
        "M5a margin .25": dict(margin=0.25), "M5b margin .5": dict(margin=0.5),
        "M7a floor 3.0": dict(floor=3.0), "M7b floor 3.5": dict(floor=3.5),
        "M9 busy hours": dict(hours=[9, 10, 11, 18, 19, 20, 21]),
        "M13a first loss ends day": dict(dl=1), "M13b limit 700": dict(dl=700)}
FILTERS = {"M1a minstop 250", "M1b minstop 400", "M1c minstop 600", "M5a margin .25", "M5b margin .5", "M9 busy hours"}


def run(name, keys):
    p = dict(P0)
    for k in keys:
        s = SPEC[k]
        if "bo" in s:
            p["bo_lookback"] = s["bo"]
        if "floor" in s:
            p["min_sl"] = s["floor"]
        if "dl" in s:
            p["day_loss_limit_pts"] = s["dl"]
    f = frame(name, p).copy()
    for k in keys:
        s = SPEC[k]
        if "minstop" in s:
            f["ok_l"] &= f.risk_l >= s["minstop"]
            f["ok_s"] &= f.risk_s >= s["minstop"]
        if "margin" in s:
            f["ok_l"] &= (f.close - f.dc_hi) >= s["margin"] * f.atr
            f["ok_s"] &= (f.dc_lo - f.close) >= s["margin"] * f.atr
        if "hours" in s:
            h = f.hour.isin(s["hours"])
            f["ok_l"] &= h
            f["ok_s"] &= h
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return t


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def seg(t, which):
    e = t.entry_time
    if which == "S1":
        return t[e < C1]
    if which == "S2":
        return t[(e >= C1) & (e < C2)]
    if which == "S3":
        return t[e >= C2]
    if which == "LOW":
        return t[e < C2]
    return t


def m(t):
    if len(t) < 5:
        return dict(n=len(t), pf=0, net=0, expR=0, dd=0, win=0, pos_m=0, hold=0)
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    ep = t.net.cumsum()
    return dict(n=len(t), pf=pf(t.net), net=round(t.net.sum()), expR=round(t.R.mean(), 3), dd=round((ep.cummax() - ep).max()), win=round(100 * (t.net > 0).mean(), 1),
                pos_m=round(100 * (mo > 0).mean()), hold=round(t.hold_h.mean(), 1))


SEGS = ("S1", "S2", "S3", "LOW", "ALL")
base = {n: run(n, []) for n in BARS}
B = {n: {s: m(seg(base[n], s)) for s in SEGS} for n in BARS}
pd.set_option("display.width", 250, "display.max_rows", 200)
for n in BARS:
    print(f"\nDEPLOYED {n}:\n", pd.DataFrame(B[n]).to_string())
rng = np.random.default_rng(5)


def null_p90(frac):
    d = seg(base["SILVERM1"], "LOW").R.to_numpy()
    k = int(round(len(d) * (1 - frac)))
    return float(np.percentile([d[rng.choice(len(d), k, replace=False)].mean() - d.mean() for _ in range(2000)], 90))


def blocked_frac(k):
    s = SPEC[k]
    f = frame("SILVERM1", P0)
    idx = f.set_index("time")
    low = seg(base["SILVERM1"], "LOW")
    bad = 0
    for st, sd in zip(low.signal_time, low.side):
        r = idx.loc[st]
        ok = True
        if "minstop" in s:
            ok &= (r.risk_l if sd == "LONG" else r.risk_s) >= s["minstop"]
        if "margin" in s:
            ok &= ((r.close - r.dc_hi) if sd == "LONG" else (r.dc_lo - r.close)) >= s["margin"] * r.atr
        if "hours" in s:
            ok &= r.hour in s["hours"]
        bad += (not ok)
    return bad / len(low)


def elig(res, null=None):
    a, b = res["SILVERM1"], B["SILVERM1"]
    c = res["SILVER1"]
    ok = (a["LOW"]["expR"] >= b["LOW"]["expR"] + 0.03 and c["LOW"]["expR"] >= B["SILVER1"]["LOW"]["expR"] + 0.02 and a["S1"]["pf"] >= b["S1"]["pf"] - 0.02
          and a["S2"]["pf"] >= b["S2"]["pf"] - 0.02 and a["LOW"]["n"] >= 300 and a["S3"]["pf"] >= b["S3"]["pf"] - 0.10 and a["S3"]["net"] >= 0.85 * b["S3"]["net"])
    if null is not None:
        ok = ok and (a["LOW"]["expR"] - b["LOW"]["expR"]) > null
    return ok


rows, ok_list = [], []
for k in SPEC:
    res = {n: {s: m(seg(run(n, [k]), s)) for s in SEGS} for n in BARS}
    nl = round(null_p90(blocked_frac(k)), 3) if k in FILTERS else None
    ok = elig(res, nl)
    if ok:
        ok_list.append(k)
    a = res["SILVERM1"]
    rows.append(dict(cand=k, ok=ok, n_low=a["LOW"]["n"], dExpR_M=round(a["LOW"]["expR"] - B["SILVERM1"]["LOW"]["expR"], 3), null_p90=nl,
                     dExpR_chartSILVER=round(res["SILVER1"]["LOW"]["expR"] - B["SILVER1"]["LOW"]["expR"], 3),
                     pf_S1=a["S1"]["pf"], pf_S2=a["S2"]["pf"], pf_S3=a["S3"]["pf"], net_S1=a["S1"]["net"], net_S2=a["S2"]["net"], net_S3=a["S3"]["net"]))
    print("done", k, flush=True)
R = pd.DataFrame(rows)
R.to_csv("research_data/silverm_lowvol_fix.csv", index=False)
b = B["SILVERM1"]
print("\nDEPLOYED SILVERM1: PF S1/S2/S3 =", b["S1"]["pf"], b["S2"]["pf"], b["S3"]["pf"], "| net", b["S1"]["net"], b["S2"]["net"], b["S3"]["net"],
      "| LOW expR", b["LOW"]["expR"], "| SILVER1 LOW expR", B["SILVER1"]["LOW"]["expR"])
print(R.to_string(index=False))
print("\nELIGIBLE:", ok_list)
if not ok_list:
    print("NOTHING ELIGIBLE.")
    sys.exit(0)
order = sorted(ok_list, key=lambda k: -float(R[R.cand == k].dExpR_M.iloc[0]))
combo, cur = [], None
for k in order:
    tr = combo + [k]
    res = {n: {s: m(seg(run(n, tr), s)) for s in SEGS} for n in BARS}
    if len(tr) <= 3 and elig(res) and (cur is None or res["SILVERM1"]["LOW"]["expR"] >= cur + 0.01):
        combo, cur = tr, res["SILVERM1"]["LOW"]["expR"]
print("COMBINATION:", combo)
if not combo:
    sys.exit(0)
fin = {n: run(n, combo) for n in BARS}
for n in BARS:
    print(f"\n{n}: deployed vs final")
    table = {f"{s} deployed": B[n][s] for s in ("S1", "S2", "S3", "ALL")}
    table.update({f"{s} final": m(seg(fin[n], s)) for s in ("S1", "S2", "S3", "ALL")})
    print(pd.DataFrame(table).to_string())
A, F = seg(base["SILVERM1"], "LOW"), seg(fin["SILVERM1"], "LOW")
ml = sorted(set(A.exit_time.dt.to_period("M")) | set(F.exit_time.dt.to_period("M")))
ga = {x: g for x, g in A.groupby(A.exit_time.dt.to_period("M"))}
gf = {x: g for x, g in F.groupby(F.exit_time.dt.to_period("M"))}
rg = np.random.default_rng(1)
d = []
for _ in range(3000):
    pk = [ml[i] for i in rg.choice(len(ml), len(ml))]
    d.append(pd.concat([gf[x] for x in pk if x in gf]).R.mean() - pd.concat([ga[x] for x in pk if x in ga]).R.mean())
print(f"\nLOW (S1+S2) expectancy difference final - deployed: median {np.median(d):.3f}, P(final better) {100*np.mean(np.array(d) > 0):.0f}%  (tuned on this data: optimistic)")
