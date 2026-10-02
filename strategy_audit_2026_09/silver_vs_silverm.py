"""Deployed v4.1 strategy on SILVER1 (big silver) vs SILVERM1 (mini), each on its OWN bars, all history through 2026-10-01.
Also: how independent the two samples are, bootstrap confidence on the difference, and confidence intervals on each result."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]   # identical v4.1 values to [strategy.SILVER]
NAMES = {"SILVER (big)": "MCX_SILVER1", "SILVERM (mini)": "MCX_SILVERM1"}
T, B = {}, {}
for k, n in NAMES.items():
    B[k] = rs.load(n)
    f = rs.v40.v40_frame(B[k], P)
    t = pd.DataFrame(rs.simulate(f, P))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    T[k] = t
months = pd.period_range("2024-01", "2026-10", freq="M")


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def streak(flags):
    best = cur = 0
    for v in flags:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def kpis(t):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0)
    eq = t.net.cumsum()
    dd = (eq.cummax() - eq).max()
    q = t.exit_time.quantile([.6, .8])
    return {"trades (per month)": f"{len(t)} ({len(t)/len(months):.1f})", "win rate": f"{100*(t.net>0).mean():.1f}%", "profit factor": pf(t.net), "NET POINTS": f"{t.net.sum():,.0f}",
            "avg win / avg loss": f"{t.net[t.net>0].mean():,.0f} / {t.net[t.net<0].mean():,.0f}", "avg stop (median)": f"{t.risk_pts.mean():,.0f} ({t.risk_pts.median():,.0f})",
            "expectancy (R)": round(t.R.mean(), 3), "max drawdown (points / R)": f"{dd:,.0f} / {(t.R.cumsum().cummax() - t.R.cumsum()).max():.1f}", "net / drawdown": round(t.net.sum() / dd, 2),
            "months positive": f"{int((mo>0).sum())}/{len(months)} ({100*(mo>0).mean():.0f}%)", "longest losing-month run": streak((mo < 0).to_numpy()),
            "best / worst month": f"{mo.max():,.0f} / {mo.min():,.0f}", "best month % of net": round(100 * mo.max() / t.net.sum()),
            "top-10 trades % of net": round(100 * t.net.nlargest(10).sum() / t.net.sum()), "net without top-10 trades": f"{t.net.sum() - t.net.nlargest(10).sum():,.0f}",
            "PF early / middle / recent": " / ".join(str(pf(s.net)) for s in (t[t.exit_time <= q[.6]], t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])], t[t.exit_time > q[.8]])),
            "avg hold h": round(t.hold_h.mean(), 1), "held > 24h": f"{100*(t.hold_h>24).mean():.0f}%"}


pd.set_option("display.width", 250, "display.max_rows", 100)
print("DEPLOYED v4.1 on each contract's own bars (identical settings), 2024-01-08 -> 2026-10-01")
print(pd.DataFrame({k: kpis(t) for k, t in T.items()}).to_string())
print("\nBY YEAR (net points / PF)")
for k, t in T.items():
    print(k, {int(y): f"{g.net.sum():,.0f} / {pf(g.net)}" for y, g in t.groupby(t.exit_time.dt.year)})
end = B["SILVERM (mini)"].time.iloc[-1]
for lab, d in (("last 180 days", 180), ("last 90 days", 90), ("last 30 days", 30)):
    print(lab, {k: f"{len(s)} tr, PF {pf(s.net)}, net {s.net.sum():,.0f}" for k, t in T.items() for s in [t[t.exit_time > end - pd.Timedelta(days=d)]]})

# ---- how independent are the two samples?
mo = pd.DataFrame({k: t.groupby(t.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0) for k, t in T.items()})
dy = pd.DataFrame({k: t.groupby(t.exit_time.dt.date).net.sum() for k, t in T.items()}).fillna(0)
a, b = T["SILVER (big)"], T["SILVERM (mini)"]
ka = set(zip(a.signal_time, a.side))
kb = set(zip(b.signal_time, b.side))
near = sum(any(((s + pd.Timedelta(minutes=m), sd) in ka) for m in (-10, -5, 0, 5, 10)) for s, sd in kb)
print(f"\nINDEPENDENCE: monthly net correlation {mo.corr().iloc[0, 1]:.2f} | daily net correlation {dy.corr().iloc[0, 1]:.2f}")
print(f"signals on the same bar and side: {len(ka & kb)} of {len(kb)} SILVERM trades ({100*len(ka & kb)/len(kb):.0f}%); within +/-10 minutes: {near} ({100*near/len(kb):.0f}%)")
pc = pd.DataFrame({k: pd.read_csv(f"research_data/bars/{n}_5m.csv").set_index("time").close for k, n in NAMES.items()}).dropna().pct_change().dropna()
print(f"5-minute return correlation of the two charts: {pc.corr().iloc[0, 1]:.3f}")

# ---- confidence: month-block bootstrap
rng = np.random.default_rng(7)
G = {k: {m: g for m, g in t.groupby(t.exit_time.dt.to_period("M"))} for k, t in T.items()}
dn, dp, de = [], [], []
cis = {k: [] for k in T}
for _ in range(4000):
    pick = [months[i] for i in rng.choice(len(months), len(months))]
    res = {}
    for k in T:
        x = pd.concat([G[k][m] for m in pick if m in G[k]])
        res[k] = (x.net.sum(), pf(x.net), x.R.mean())
        cis[k].append(res[k])
    dn.append(res["SILVER (big)"][0] - res["SILVERM (mini)"][0])
    dp.append(res["SILVER (big)"][1] - res["SILVERM (mini)"][1])
    de.append(res["SILVER (big)"][2] - res["SILVERM (mini)"][2])
print("\nCONFIDENCE (4000 month-block resamples; same months drawn for both contracts):")
for k in T:
    arr = np.array(cis[k])
    print(f"  {k}: net points 90% range [{np.percentile(arr[:, 0], 5):,.0f}, {np.percentile(arr[:, 0], 95):,.0f}] | PF 90% range [{np.percentile(arr[:, 1], 5):.2f}, {np.percentile(arr[:, 1], 95):.2f}] | "
          f"P(net<0) {100*np.mean(arr[:, 0] < 0):.0f}% | P(PF<1) {100*np.mean(arr[:, 1] < 1):.0f}%")
for nm, d in (("net points", dn), ("PF", dp), ("expectancy R", de)):
    d = np.array(d)
    print(f"  SILVER minus SILVERM, {nm}: median {np.median(d):,.2f}, 90% range [{np.percentile(d, 5):,.2f}, {np.percentile(d, 95):,.2f}], P(SILVER better) {100*np.mean(d > 0):.0f}%")
