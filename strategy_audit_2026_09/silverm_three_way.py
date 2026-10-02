"""Live v4.1 vs E3 vs 'final' on the FULL SILVERM1 history (the contract actually traded). Signals computed on SILVERM1 itself."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

LIVE = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
df = rs.load("MCX_SILVERM1")
CFG = {"live v4.1": dict(earliest=0, min_sl=2.5), "E3 (no entry <12:00)": dict(earliest=12, min_sl=2.5),
       "final (<13:00, floor 3.0)": dict(earliest=13, min_sl=3.0)}


def run(c):
    p = dict(LIVE, min_sl=c["min_sl"])
    f = rs.v40.v40_frame(df, p)
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


T = {k: run(c) for k, c in CFG.items()}
print(f"SILVERM1 history: {df.time.iloc[0]:%Y-%m-%d} -> {df.time.iloc[-1]:%Y-%m-%d}  ({len(df):,} bars, {(df.time.iloc[-1]-df.time.iloc[0]).days/30.4:.1f} months)")
span = (df.time.iloc[-1] - df.time.iloc[0]).days / 30.4
pd.set_option("display.width", 250, "display.max_rows", 100)
H = {}
for k, t in T.items():
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    q = t.exit_time.quantile([.6, .8])
    segs = (t[t.exit_time <= q[.6]], t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])], t[t.exit_time > q[.8]])
    H[k] = {"trades": len(t), "per month": round(len(t) / span, 1), "win %": round(100 * (t.net > 0).mean(), 1),
            "PF points": pf(t.net), "PF R": pf(t.R), "net points": round(t.net.sum()), "net R": round(t.R.sum(), 1),
            "expectancy R": round(t.R.mean(), 3), "avg win R / loss R": f"{t.R[t.R>0].mean():.2f} / {t.R[t.R<0].mean():.2f}",
            "max DD points": round(dd(t.net)), "max DD R": round(dd(t.R), 1), "net / DD (points)": round(t.net.sum() / dd(t.net), 2),
            "net / DD (R)": round(t.R.sum() / dd(t.R), 2), "longest losing streak": streak(t.net),
            "worst / best trade pts": f"{t.net.min():,.0f} / {t.net.max():,.0f}",
            "top-5 trades % of net": round(100 * t.net.nlargest(5).sum() / t.net.sum()),
            "avg / median hold h": f"{t.hold_h.mean():.1f} / {t.hold_h.median():.1f}", "held >24h %": round(100 * (t.hold_h > 24).mean()),
            "months": len(mo), "months positive %": round(100 * (mo > 0).mean()),
            "best / worst month pts": f"{mo.max():,.0f} / {mo.min():,.0f}", "best month % of net": round(100 * mo.max() / t.net.sum()),
            "avg month / std": f"{mo.mean():,.0f} / {mo.std():,.0f}", "PF train/val/hold (pts)": " / ".join(str(pf(s.net)) for s in segs),
            "PF-R train/val/hold": " / ".join(str(pf(s.R)) for s in segs),
            "win% train/val/hold": " / ".join(f"{100*(s.net>0).mean():.0f}" for s in segs),
            "net pts train/val/hold": " / ".join(f"{s.net.sum():,.0f}" for s in segs)}
print(pd.DataFrame(H).to_string())

print("\nBY CALENDAR YEAR (exit): n / net pts / PF")
for k, t in T.items():
    print(k, {int(y): f"{len(g)} / {g.net.sum():,.0f} / {pf(g.net)}" for y, g in t.groupby(t.exit_time.dt.year)})
print("\nBY SIDE: n / net pts / win% / PF")
for k, t in T.items():
    print(k, {s: f"{len(g)} / {g.net.sum():,.0f} / {100*(g.net>0).mean():.0f} / {pf(g.net)}" for s, g in t.groupby("side")})
print("\nQUARTERLY NET (pts)")
Q = pd.concat({k: t.groupby(t.exit_time.dt.to_period("Q")).net.sum() for k, t in T.items()}, axis=1).fillna(0).round(0)
print(Q.to_string())

rng = np.random.default_rng(9)
keys = list(T)
months = sorted(set().union(*[set(t.exit_time.dt.to_period("M")) for t in T.values()]))
grp = {k: {m: g for m, g in t.groupby(t.exit_time.dt.to_period("M"))} for k, t in T.items()}
for other in keys[1:]:
    dn, de, dd_ = [], [], []
    for _ in range(3000):
        pick = [months[i] for i in rng.choice(len(months), len(months))]
        a = pd.concat([grp[keys[0]][m] for m in pick if m in grp[keys[0]]])
        b = pd.concat([grp[other][m] for m in pick if m in grp[other]])
        dn.append(b.net.sum() - a.net.sum()); de.append(b.R.mean() - a.R.mean()); dd_.append(dd(b.R) - dd(a.R))
    print(f"\nbootstrap {other} minus live: net pts median {np.median(dn):,.0f} [90%: {np.percentile(dn,5):,.0f}, {np.percentile(dn,95):,.0f}] P(better) {np.mean(np.array(dn)>0):.0%} | "
          f"expectancy R median {np.median(de):.3f} P(better) {np.mean(np.array(de)>0):.0%} | maxDD R median {np.median(dd_):.1f} P(lower) {np.mean(np.array(dd_)<0):.0%}")
