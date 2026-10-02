"""Detailed historical result of the CURRENT live SILVERM strategy ([strategy.SILVERM], v4.1 on SILVERM1's own bars, hours 15-17 excluded).
Descriptive only (full history). Improvement testing is a separate, development-data-only script."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVERM"]
bars = rs.load("MCX_SILVERM1")
f = rs.v40.v40_frame(bars, P)
t = pd.DataFrame(rs.simulate(f, P))
t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
t["R"] = t.net / t.risk_pts
t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
sig = f.set_index("time")
t["atr"] = t.signal_time.map(sig.atr)
t["etype"] = np.where([bool(sig.at[s, "flip_up"] if sd == "LONG" else sig.at[s, "flip_dn"]) for s, sd in zip(t.signal_time, t.side)], "SHA flip", "3-bar breakout")
t["stop_atr"] = t.risk_pts / t.atr
t["hour"] = t.signal_time.dt.hour
t["dow"] = t.signal_time.dt.day_name()
t["regime"] = pd.qcut(t.atr, 3, labels=["low vol", "mid vol", "high vol"])
t["stopb"] = pd.cut(t.stop_atr, [0, 3, 4, 5.01], labels=["2.5-3 ATR", "3-4 ATR", "4-5 ATR"])
t["result2"] = np.where(t.net > 0, "win", "loss")
pd.set_option("display.width", 250, "display.max_rows", 200)


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def grp(col, order=None):
    g = t.groupby(col, observed=True).agg(trades=("net", "size"), win=("net", lambda s: round(100 * (s > 0).mean())), net=("net", "sum"),
                                          avg=("net", "mean"), pf=("net", pf), expR=("R", "mean"), hold=("hold_h", "mean")).round(2)
    g["net"] = g.net.round(0)
    g["avg"] = g.avg.round(0)
    g["share of net %"] = (100 * g.net / t.net.sum()).round(0)
    return g.loc[order] if order else g


months = pd.period_range("2024-01", "2026-09", freq="M")
mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum().reindex(months, fill_value=0)
eq = t.net.cumsum()
dd = (eq.cummax() - eq)
q = t.exit_time.quantile([.6, .8])
print(f"STRATEGY: {P['name']}")
print(f"SETTINGS: SHA {P['sha_len1']}/{P['sha_len2']}, EMA9/22 trend, breakout lookback {P['bo_lookback']}, swing {P['sw_len']} bars + {P['sw_buf']} ATR, "
      f"stop floor/cap {P['min_sl']}/{P['max_sl']} ATR, RR {P['rr']}, day limit {P['day_loss_limit_pts']} pts, session {P['session']}, excluded hours {P['exclude_hours']}")
print(f"DATA: SILVERM1 5m {bars.time.iloc[0]:%Y-%m-%d} -> {bars.time.iloc[-1]:%Y-%m-%d}  ({len(bars):,} bars, {len(months)} months); cost 0.02%/side; points\n")
H = {
    "trades / per month": f"{len(t)} / {len(t)/len(months):.1f}", "win rate": f"{100*(t.net>0).mean():.1f}%", "profit factor": pf(t.net),
    "net points": f"{t.net.sum():,.0f}", "gross profit / gross loss": f"{t.net[t.net>0].sum():,.0f} / {t.net[t.net<0].sum():,.0f}",
    "avg trade / median trade": f"{t.net.mean():,.0f} / {t.net.median():,.0f}", "avg win / avg loss": f"{t.net[t.net>0].mean():,.0f} / {t.net[t.net<0].mean():,.0f}",
    "payoff ratio": round(t.net[t.net > 0].mean() / -t.net[t.net < 0].mean(), 2), "expectancy (R per trade)": round(t.R.mean(), 3),
    "target hit % / stop hit %": f"{100*(t.result=='TP').mean():.1f} / {100*(t.result=='SL').mean():.1f}", "best / worst trade": f"{t.net.max():,.0f} / {t.net.min():,.0f}",
    "top-5 trades share of net": f"{100*t.net.nlargest(5).sum()/t.net.sum():.0f}%", "top-10 trades share of net": f"{100*t.net.nlargest(10).sum()/t.net.sum():.0f}%",
    "net without top-5 trades": f"{t.net.sum()-t.net.nlargest(5).sum():,.0f}", "max drawdown (points)": f"{dd.max():,.0f}", "net / max drawdown": round(t.net.sum()/dd.max(), 2),
    "avg / median hold": f"{t.hold_h.mean():.1f}h / {t.hold_h.median():.1f}h", "held overnight / >24h": f"{100*(t.entry_time.dt.date!=t.exit_time.dt.date).mean():.0f}% / {100*(t.hold_h>24).mean():.0f}%",
    "months positive / negative": f"{int((mo>0).sum())} / {int((mo<0).sum())}", "best / worst month": f"{mo.max():,.0f} / {mo.min():,.0f}",
    "best month share of net": f"{100*mo.max()/t.net.sum():.0f}%", "net without best month": f"{t.net.sum()-mo.max():,.0f}",
    "PF early / middle / recent": " / ".join(str(pf(s.net)) for s in (t[t.exit_time <= q[.6]], t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])], t[t.exit_time > q[.8]])),
    "net early / middle / recent": " / ".join(f"{s.net.sum():,.0f}" for s in (t[t.exit_time <= q[.6]], t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])], t[t.exit_time > q[.8]])),
}
print(pd.Series(H).to_string())
print("\nBY YEAR (exit)\n", grp(t.exit_time.dt.year).to_string())
print("\nBY SIDE\n", grp("side").to_string())
print("\nBY ENTRY TYPE\n", grp("etype").to_string())
print("\nBY STOP SIZE (x ATR)\n", grp("stopb").to_string())
print("\nBY VOLATILITY (ATR tercile)\n", grp("regime").to_string())
print("\nBY SIGNAL HOUR (IST)\n", grp("hour").to_string())
print("\nBY WEEKDAY\n", grp("dow", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]).to_string())
print("\nMONTHLY NET (points)\n", mo.round(0).to_frame("net").assign(cum=lambda d: d.net.cumsum().round(0)).T.to_string())
print("\nTOP 5 / BOTTOM 5 trades:\n", t.nlargest(5, "net")[["signal_time", "side", "etype", "risk_pts", "net", "hold_h"]].round(0).to_string(index=False),
      "\n", t.nsmallest(5, "net")[["signal_time", "side", "etype", "risk_pts", "net", "hold_h"]].round(0).to_string(index=False))
