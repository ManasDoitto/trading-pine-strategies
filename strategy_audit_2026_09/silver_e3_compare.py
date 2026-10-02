"""Full side-by-side: live silver v4.1 vs the same strategy with no entries before 12:00 (variant E3)."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

p = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
df = rs.load("MCX_SILVER1")
base = rs.v40.v40_frame(df, p)
e3 = base.copy()
early = (base.time.dt.hour * 60 + base.time.dt.minute) < 12 * 60
e3["ok_l"] &= ~early
e3["ok_s"] &= ~early


def trades(f):
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    t["R"] = t.net / t.risk_pts
    t["month"] = t.exit_time.dt.to_period("M")
    t["year"] = t.exit_time.dt.year
    return t


def pf(x, c="net"):
    v = x if isinstance(x, pd.Series) else x[c]
    w, l = v[v > 0].sum(), -v[v < 0].sum()
    return round(w / l, 2) if l > 0 else float("inf")


def streak(s):
    best = cur = 0
    for v in s:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def dd_pts(s):
    eq = s.cumsum()
    return (eq.cummax() - eq).max()


T = {"current": trades(base), "E3 (no entry < 12:00)": trades(e3)}
span_m = (df.time.iloc[-1] - df.time.iloc[0]).days / 30.4
pd.set_option("display.width", 250, "display.max_rows", 200)

# ---- headline
rows = {}
for k, t in T.items():
    mo = t.groupby("month").net.sum()
    top5 = t.net.nlargest(5).sum()
    rows[k] = {
        "trades": len(t), "per month": round(len(t) / span_m, 1), "win %": round(100 * (t.net > 0).mean(), 1),
        "PF (points)": pf(t), "PF (R)": pf(t, "R"), "net pts": round(t.net.sum()), "net R": round(t.R.sum(), 1),
        "avg trade pts": round(t.net.mean()), "avg win pts": round(t.net[t.net > 0].mean()), "avg loss pts": round(t.net[t.net < 0].mean()),
        "avg win R": round(t.R[t.R > 0].mean(), 2), "avg loss R": round(t.R[t.R < 0].mean(), 2),
        "expectancy R/trade": round(t.R.mean(), 3), "median trade pts": round(t.net.median()),
        "max drawdown pts": round(dd_pts(t.net)), "net / max DD": round(t.net.sum() / dd_pts(t.net), 2),
        "longest losing streak": streak(t.net), "worst trade pts": round(t.net.min()), "best trade pts": round(t.net.max()),
        "top-5 trades share of net %": round(100 * top5 / t.net.sum()),
        "avg stop pts": round(t.risk_pts.mean()), "median stop pts": round(t.risk_pts.median()), "stops > 1500": int((t.risk_pts > 1500).sum()),
        "avg hold h": round(t.hold_h.mean(), 1), "median hold h": round(t.hold_h.median(), 1),
        "held > 24h %": round(100 * (t.hold_h > 24).mean()), "held < 2h %": round(100 * (t.hold_h < 2).mean()),
        "months": len(mo), "months positive %": round(100 * (mo > 0).mean()), "best month pts": round(mo.max()),
        "worst month pts": round(mo.min()), "avg month pts": round(mo.mean()), "month std pts": round(mo.std()),
        "best month share of net %": round(100 * mo.max() / t.net.sum()),
        "avg-month / std (Sharpe-like)": round(mo.mean() / mo.std(), 2),
    }
print("HEADLINE\n", pd.DataFrame(rows).to_string())

# ---- segments and years
def seg(t):
    q = t.exit_time.quantile([.6, .8])
    return {"train": t[t.exit_time <= q[.6]], "validation": t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])], "holdout": t[t.exit_time > q[.8]]}


print("\nSEGMENTS (oldest 60% / next 20% / newest 20% by exit time)")
for k, t in T.items():
    for s, x in seg(t).items():
        print(f"{k:24} {s:10} {x.exit_time.min():%Y-%m} -> {x.exit_time.max():%Y-%m}  n {len(x):4}  PF {pf(x):5}  net {x.net.sum():9,.0f}  win% {100*(x.net>0).mean():4.1f}  maxDD {dd_pts(x.net):8,.0f}")
print("\nBY CALENDAR YEAR (exit)")
yr = pd.concat({k: t.groupby("year").agg(n=("net", "size"), net=("net", "sum"), pf=("net", pf)) for k, t in T.items()}, axis=1)
print(yr.round(1).to_string())

# ---- by side / signal hour / exit reason
print("\nBY SIDE")
for k, t in T.items():
    print(k, t.groupby("side").agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda s: round(100 * (s > 0).mean())), pf=("net", pf)).round(1).to_dict("index"))
print("\nBY SIGNAL HOUR (current | E3): n, net")
h = pd.concat({k: t.assign(hr=pd.to_datetime(t.signal_time).dt.hour).groupby("hr").agg(n=("net", "size"), net=("net", "sum")) for k, t in T.items()}, axis=1)
print(h.round(0).fillna(0).to_string())
print("\nBY EXIT REASON")
for k, t in T.items():
    print(k, t.groupby("result").agg(n=("net", "size"), net=("net", "sum")).round(0).to_dict("index"))

# ---- monthly paired table
m = pd.concat({k: t.groupby("month").net.sum() for k, t in T.items()}, axis=1).fillna(0)
m["E3 - current"] = m.iloc[:, 1] - m.iloc[:, 0]
print("\nMONTHLY NET (pts)\n", m.round(0).to_string())
print("months E3 better:", int((m["E3 - current"] > 0).sum()), "of", len(m), "| worse:", int((m["E3 - current"] < 0).sum()))

# ---- is the difference more than noise? paired block bootstrap by month
rng = np.random.default_rng(11)
months = m.index.tolist()
by = {k: {mo: g for mo, g in t.groupby("month")} for k, t in T.items()}
d_net, d_pf, d_dd = [], [], []
for _ in range(4000):
    pick = rng.choice(len(months), len(months))
    res = {}
    for k in T:
        parts = [by[k][months[i]] for i in pick if months[i] in by[k]]
        x = pd.concat(parts)
        res[k] = (x.net.sum(), pf(x), dd_pts(x.net))
    a, b = res["current"], res["E3 (no entry < 12:00)"]
    d_net.append(b[0] - a[0]); d_pf.append(b[1] - a[1]); d_dd.append(b[2] - a[2])
for nm, d in (("net pts", d_net), ("PF", d_pf), ("max drawdown pts", d_dd)):
    d = np.array(d)
    print(f"bootstrap E3 minus current, {nm}: median {np.median(d):,.2f}  90% range [{np.percentile(d, 5):,.2f}, {np.percentile(d, 95):,.2f}]  P(E3 better) "
          f"{(d < 0).mean() if nm.startswith('max') else (d > 0).mean():.0%}")

# ---- what changed: trades only in one of the two
a, b = T["current"], T["E3 (no entry < 12:00)"]
ka = set(zip(a.signal_time, a.side)); kb = set(zip(b.signal_time, b.side))
only_a = a[[(s, d) in ka - kb for s, d in zip(a.signal_time, a.side)]]
only_b = b[[(s, d) in kb - ka for s, d in zip(b.signal_time, b.side)]]
print(f"\nTRADES ONLY IN CURRENT (dropped by E3): n {len(only_a)}  net {only_a.net.sum():,.0f}  PF {pf(only_a)}")
print(f"TRADES ONLY IN E3 (new, taken later in the day instead): n {len(only_b)}  net {only_b.net.sum():,.0f}  PF {pf(only_b)}")
print("COMMON trades:", len(ka & kb))
