"""Currently DEPLOYED silver strategy ([strategy.SILVERM], v4.1 on SILVERM1's own bars) over ALL bars up to the latest harvested bar."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
bars = rs.load("MCX_SILVERM1")
print(f"DEPLOYED: {P['name']}\n  rr {P['rr']}, stop floor/cap {P['min_sl']}/{P['max_sl']} ATR, swing {P['sw_len']} bars, breakout lookback {P['bo_lookback']}, "
      f"daily limit {P['day_loss_limit_pts']} pts, excluded hours {P['exclude_hours']}, session {P['session']}")
print(f"DATA: SILVERM1 5m, {bars.time.iloc[0]:%Y-%m-%d %H:%M} -> {bars.time.iloc[-1]:%Y-%m-%d %H:%M} IST ({len(bars):,} bars)")


def trades(limit):
    p = dict(P, day_loss_limit_pts=limit)
    f = rs.v40.v40_frame(bars, p)
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return t, f


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def streak(flags):
    best = cur = 0
    for v in flags:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def kpis(t, months):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0)
    eq = t.net.cumsum()
    dd = (eq.cummax() - eq).max()
    day = t.groupby(t.exit_time.dt.date).net.sum()
    return {"months covered": len(months), "trades (per month)": f"{len(t)} ({len(t)/len(months):.1f})", "win rate %": round(100 * (t.net > 0).mean(), 1),
            "profit factor": pf(t.net), "NET POINTS": f"{t.net.sum():,.0f}", "gross profit / loss": f"{t.net[t.net>0].sum():,.0f} / {t.net[t.net<0].sum():,.0f}",
            "avg win / avg loss": f"{t.net[t.net>0].mean():,.0f} / {t.net[t.net<0].mean():,.0f}", "avg stop distance": f"{t.risk_pts.mean():,.0f}",
            "expectancy R": round(t.R.mean(), 3), "max drawdown pts": f"{dd:,.0f}", "net / drawdown": round(t.net.sum() / dd, 2),
            "months positive / negative": f"{int((mo>0).sum())} / {int((mo<0).sum())}", "longest losing-month run": streak((mo < 0).to_numpy()),
            "best / worst month": f"{mo.max():,.0f} / {mo.min():,.0f}", "best month % of net": round(100 * mo.max() / t.net.sum()),
            "longest losing streak (trades)": streak((t.net < 0).to_numpy()), "worst day": f"{day.min():,.0f}",
            "avg / median hold h": f"{t.hold_h.mean():.1f} / {t.hold_h.median():.1f}", "trading days with a trade": t.exit_time.dt.date.nunique()}


months = pd.period_range("2024-01", f"{bars.time.iloc[-1]:%Y-%m}", freq="M")
t350, f350 = trades(350)
tnone, _ = trades(0)
pd.set_option("display.width", 250, "display.max_rows", 200)
print("\nHEADLINE (as deployed = 350 rule | same strategy with the 350 rule removed, for comparison)")
print(pd.DataFrame({"AS DEPLOYED (350)": kpis(t350, months), "no daily brake": kpis(tnone, months)}).to_string())

print("\nBY YEAR (as deployed)")
y = t350.groupby(t350.exit_time.dt.year).agg(trades=("net", "size"), win=("net", lambda s: round(100 * (s > 0).mean())), pf=("net", pf), net=("net", "sum"), expR=("R", "mean")).round(2)
print(y.to_string())
mo = t350.groupby(t350.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0)
print("\nMONTHLY NET POINTS (as deployed)")
print(pd.DataFrame({"net": mo.round(0), "cumulative": mo.cumsum().round(0), "trades": t350.groupby(t350.exit_time.dt.to_period("M")).size().reindex(months, fill_value=0)}).T.to_string())
end = bars.time.iloc[-1]
for label, days in (("last 30 days", 30), ("last 60 days", 60), ("last 90 days", 90), ("last 180 days", 180)):
    s = t350[t350.exit_time > end - pd.Timedelta(days=days)]
    print(f"{label}: {len(s)} trades, win {100*(s.net>0).mean():.0f}%, PF {pf(s.net)}, net {s.net.sum():,.0f}")
print("\nLAST 12 CLOSED TRADES (as deployed):")
print(t350.tail(12)[["signal_time", "side", "entry", "sl", "tp", "risk_pts", "exit_time", "result", "net"]].round(0).to_string(index=False))
from trading_agents.core import signals as prod
tr, pos, pend = prod.simulate(f350, P)
print("\nOPEN simulated position at the last bar (production simulate):", {k: (str(v) if k.endswith("time") else round(v, 1) if isinstance(v, float) else v) for k, v in (pos or {}).items()} or None)
print("pending entry:", pend)
