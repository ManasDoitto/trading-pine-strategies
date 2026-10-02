"""Out-of-sample check of the joint-search top 5 (ranked on development data only) vs live, on SILVER1 and SILVERM1.
Declared before looking: config #1 is the primary; #2-#5 are reported in full too. Hold-time rule is relaxed (post-hoc, disclosed)."""
import re
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

LIVE_P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
BARS = {"SILVER1": rs.load("MCX_SILVER1"), "SILVERM1": rs.load("MCX_SILVERM1")}
LIVE_LABEL = "e0/rr3/sl2.5-5/bo3/dl350"
R = pd.read_csv("research_data/silver_joint_search_dev.csv").sort_values("worse_net_dd", ascending=False)
LABELS = [LIVE_LABEL] + [c for c in R.cfg if c != LIVE_LABEL][:5]


def parse(label):
    m = re.match(r"e(\d+)/rr([\d.]+)/sl([\d.]+)-([\d.]+)/bo(\d+)/dl(\d+)", label)
    e, rr, a, b, bo, dl = m.groups()
    return dict(earliest=int(e), rr=float(rr), min_sl=float(a), max_sl=float(b), bo=int(bo), dl=int(dl))


def run(label, name):
    c = parse(label)
    p = dict(LIVE_P, rr=c["rr"], min_sl=c["min_sl"], max_sl=c["max_sl"], bo_lookback=c["bo"], day_loss_limit_pts=c["dl"])
    f = rs.v40.v40_frame(BARS[name], p)
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
    return round(w / l, 2) if l > 0 else 9.99


def streak(s):
    best = cur = 0
    for v in s:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def dd(s):
    e = s.cumsum()
    return (e.cummax() - e).max()


def kpis(t):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    return {"months tested": len(mo), "trades": len(t), "win %": round(100 * (t.net > 0).mean(), 1), "net points": round(t.net.sum()),
            "net R": round(t.R.sum(), 1), "expectancy R": round(t.R.mean(), 3), "PF points": pf(t.net), "PF R": pf(t.R),
            "max DD points": round(dd(t.net)), "max DD R": round(dd(t.R), 1), "net/DD points": round(t.net.sum() / dd(t.net), 2),
            "net/DD R": round(t.R.sum() / dd(t.R), 2), "months positive": f"{int((mo > 0).sum())}/{len(mo)} ({100*(mo>0).mean():.0f}%)",
            "best/worst month pts": f"{mo.max():,.0f} / {mo.min():,.0f}", "longest losing streak": streak(t.net),
            "avg/median hold h": f"{t.hold_h.mean():.1f} / {t.hold_h.median():.1f}", "held >24h %": round(100 * (t.hold_h > 24).mean())}


TR = {(l, n): run(l, n) for l in LABELS for n in BARS}
pd.set_option("display.width", 250, "display.max_rows", 200, "display.max_columns", 20)
short = {l: ("LIVE" if l == LIVE_LABEL else f"#{i}") for i, l in enumerate(LABELS)}
print("Configs:", {short[l]: l for l in LABELS})

for n in BARS:
    cut = TR[(LIVE_LABEL, n)].exit_time.quantile(.8)
    print(f"\n===== {n}: HOLDOUT = exits after {cut:%Y-%m-%d} (newest 20% of LIVE's trades; same date cut for every config) =====")
    print(pd.DataFrame({short[l]: kpis(TR[(l, n)][TR[(l, n)].exit_time > cut]) for l in LABELS}).to_string())
    print(f"\n===== {n}: FULL HISTORY {BARS[n].time.iloc[0]:%Y-%m-%d} -> {BARS[n].time.iloc[-1]:%Y-%m-%d} =====")
    print(pd.DataFrame({short[l]: kpis(TR[(l, n)]) for l in LABELS}).to_string())

print("\n===== 6-MONTH BLOCKS (exit date), both contracts: net points / expectancy R =====")
for n in BARS:
    print(n)
    rows = {}
    for l in LABELS:
        t = TR[(l, n)]
        blk = t.groupby(pd.cut(t.exit_time, pd.date_range("2024-01-01", "2026-12-31", freq="6MS"))).agg(net=("net", "sum"), e=("R", "mean"), k=("net", "size"))
        rows[short[l]] = [f"{r.net:>9,.0f} / {r.e:+.2f} ({int(r.k)})" if r.k else "-" for r in blk.itertuples()]
    print(pd.DataFrame(rows, index=[f"{i.left:%Y-%m}" for i in blk.index]).to_string())

print("\n===== ROLLING 6-MONTH WINDOWS (step 1 month): in how many does each config beat LIVE? =====")
for n in BARS:
    t0 = TR[(LIVE_LABEL, n)]
    starts = pd.date_range(t0.exit_time.min().normalize().replace(day=1), t0.exit_time.max() - pd.DateOffset(months=6), freq="MS")
    for l in LABELS[1:]:
        t1, wins_e, wins_d, wins_n, tot = TR[(l, n)], 0, 0, 0, 0
        for s in starts:
            e = s + pd.DateOffset(months=6)
            a, b = t0[(t0.exit_time >= s) & (t0.exit_time < e)], t1[(t1.exit_time >= s) & (t1.exit_time < e)]
            if len(a) < 20 or len(b) < 20:
                continue
            tot += 1
            wins_e += b.R.mean() > a.R.mean()
            wins_d += dd(b.R) < dd(a.R)
            wins_n += b.net.sum() > a.net.sum()
        print(f"{n} {short[l]} ({l}): of {tot} windows - better expectancy {wins_e}, lower drawdown {wins_d}, more net points {wins_n}")

rng = np.random.default_rng(21)
print("\n===== BOOTSTRAP on full history (month blocks): #1 minus LIVE =====")
for n in BARS:
    A, B = TR[(LIVE_LABEL, n)], TR[(LABELS[1], n)]
    months = sorted(set(A.exit_time.dt.to_period("M")) | set(B.exit_time.dt.to_period("M")))
    ga = {m: g for m, g in A.groupby(A.exit_time.dt.to_period("M"))}
    gb = {m: g for m, g in B.groupby(B.exit_time.dt.to_period("M"))}
    de, dn, ddd = [], [], []
    for _ in range(3000):
        pk = [months[i] for i in rng.choice(len(months), len(months))]
        xa, xb = pd.concat([ga[m] for m in pk if m in ga]), pd.concat([gb[m] for m in pk if m in gb])
        de.append(xb.R.mean() - xa.R.mean()); dn.append(xb.net.sum() - xa.net.sum()); ddd.append(dd(xb.R) - dd(xa.R))
    print(f"{n}: expectancy P(better) {np.mean(np.array(de) > 0):.0%} | net points P(more) {np.mean(np.array(dn) > 0):.0%} (median {np.median(dn):,.0f}) | maxDD(R) P(lower) {np.mean(np.array(ddd) < 0):.0%}")
