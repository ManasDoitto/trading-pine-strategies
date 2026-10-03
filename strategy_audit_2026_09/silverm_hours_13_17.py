"""What if hour 17 is skipped as well: 13-17 against the live 13-16."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P_NEW = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
P_OLD = dict(P_NEW, exclude_hours=[13, 14, 15, 16])
P_NEW = dict(P_NEW, exclude_hours=[13, 14, 15, 16, 17])
bars = rs.load("MCX_SILVERM1")
months = pd.period_range("2024-01", "2026-10", freq="M")
t0, t1 = bars.time.iloc[400], bars.time.iloc[-1]
cuts = [t0 + (t1 - t0) * k / 3 for k in range(4)]
pd.set_option("display.width", 250, "display.max_rows", 100)


def run(p):
    t = pd.DataFrame(rs.simulate(rs.v40.v40_frame(bars, p), p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    t["hour"] = t.signal_time.dt.hour
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


def head(t):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0)
    eq = t.net.cumsum()
    dd = (eq.cummax() - eq).max()
    return {"trades (per month)": f"{len(t)} ({len(t)/len(months):.1f})", "win rate": f"{100*(t.net>0).mean():.1f}%", "profit factor": pf(t.net), "NET POINTS": f"{t.net.sum():,.0f}",
            "expectancy (R)": round(t.R.mean(), 3), "avg win / avg loss": f"{t.net[t.net>0].mean():,.0f} / {t.net[t.net<0].mean():,.0f}",
            "target hit / stop hit": f"{100*(t.result=='TP').mean():.1f}% / {100*(t.result=='SL').mean():.1f}%", "max drawdown": f"{dd:,.0f}", "net / drawdown": round(t.net.sum() / dd, 2),
            "months positive": f"{int((mo>0).sum())}/{len(mo)} ({100*(mo>0).mean():.0f}%)", "best / worst month": f"{mo.max():,.0f} / {mo.min():,.0f}",
            "longest losing-month run": streak((mo < 0).to_numpy()), "longest losing streak (trades)": streak((t.net < 0).to_numpy()), "worst day": f"{t.groupby(t.exit_time.dt.date).net.sum().min():,.0f}",
            "avg / median hold h": f"{t.hold.mean():.1f} / {t.hold.median():.1f}", "held > 24h": f"{100*(t.hold>24).mean():.0f}%",
            "top-10 trades % of net": f"{100*t.net.nlargest(10).sum()/t.net.sum():.0f}%", "net / PF without top-10": f"{t.net.sum()-t.net.nlargest(10).sum():,.0f} / {pf(t.net.drop(t.net.nlargest(10).index))}"}


new, old = run(P_NEW), run(P_OLD)
print(f"DEPLOYED CONFIG: excluded signal hours {P_NEW['exclude_hours']}, min_stop_pct {P_NEW['min_stop_pct']}, brake {P_NEW['day_loss_limit_pts']}, rr {P_NEW['rr']}, bo {P_NEW['bo_lookback']}, swing {P_NEW['sw_len']}, floor/cap {P_NEW['min_sl']}/{P_NEW['max_sl']}")
print(f"DATA: SILVERM1 5m {bars.time.iloc[0]:%Y-%m-%d} -> {bars.time.iloc[-1]:%Y-%m-%d} ({len(months)} months), cost 0.02%/side, points\n")
print(pd.DataFrame({"13-17 skipped (if hour 17 is removed too)": head(new), "CURRENT live (13-16 skipped)": head(old)}).to_string())

print("\nBY YEAR (new hours)")
print(new.groupby(new.exit_time.dt.year).agg(trades=("net", "size"), win=("net", lambda s: round(100 * (s > 0).mean(), 1)), PF=("net", pf), net=("net", "sum"), expR=("R", "mean"), dd=("net", lambda s: (s.cumsum().cummax() - s.cumsum()).max())).round(2).to_string())

print("\nTHREE EQUAL-TIME SAMPLES (new | previous)")
for i, lab in enumerate(("S1", "S2", "S3")):
    sel = lambda t: t[(t.entry_time >= cuts[i]) & ((t.entry_time < cuts[i + 1]) if i < 2 else (t.entry_time <= cuts[3]))]
    a, b = sel(new), sel(old)
    mo = a.groupby(a.exit_time.dt.to_period("M")).net.sum()
    print(f"  {lab} {cuts[i]:%Y-%m-%d} -> {cuts[i+1]:%Y-%m-%d}: trades {len(a)} | win {100*(a.net>0).mean():.1f}% | PF {pf(a.net)} | net {a.net.sum():,.0f} | expR {a.R.mean():.3f} | months+ {int((mo>0).sum())}/{len(mo)}"
          f"   ||  previous: trades {len(b)}, PF {pf(b.net)}, net {b.net.sum():,.0f}, expR {b.R.mean():.3f}")

end = bars.time.iloc[-1]
print("\nRECENT (new | previous)")
for lab, d in (("last 30 days", 30), ("last 90 days", 90), ("last 180 days", 180), ("last 365 days", 365)):
    a, b = new[new.exit_time > end - pd.Timedelta(days=d)], old[old.exit_time > end - pd.Timedelta(days=d)]
    print(f"  {lab}: {len(a)} trades, PF {pf(a.net)}, net {a.net.sum():,.0f}  ||  previous: {len(b)} trades, PF {pf(b.net)}, net {b.net.sum():,.0f}")

print("\nWHICH HOURS THE REMAINING TRADES START IN (new)")
print(new.groupby("hour").agg(trades=("net", "size"), PF=("net", pf), net=("net", "sum")).round(0).to_string())

mo = new.groupby(new.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0)
print("\nMONTHLY NET POINTS (new hours)")
print(pd.DataFrame({"net": mo.round(0), "cumulative": mo.cumsum().round(0)}).T.to_string())

rng = np.random.default_rng(4)
G = {m: g for m, g in new.groupby(new.exit_time.dt.to_period("M"))}
ml = list(G)
res = []
for _ in range(4000):
    x = pd.concat([G[ml[i]] for i in rng.choice(len(ml), len(ml))])
    res.append((pf(x.net), x.net.sum(), x.R.mean()))
a = np.array(res)
print(f"\nBOOTSTRAP (4,000 month-block resamples, optimistic: the hours were chosen on this data): PF 90% range [{np.percentile(a[:,0],5):.2f}, {np.percentile(a[:,0],95):.2f}], "
      f"net 90% range [{np.percentile(a[:,1],5):,.0f}, {np.percentile(a[:,1],95):,.0f}], P(PF<1) {100*np.mean(a[:,0]<1):.1f}%, P(expectancy<=0) {100*np.mean(a[:,2]<=0):.1f}%")
