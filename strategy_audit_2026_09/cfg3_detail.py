"""Detail sheet: live v4.1 vs candidate #3 (RR 4, floor 3.0, cap 5.0, lookback 3, day limit 500) on SILVER1 and SILVERM1, full history."""
import tomllib
from pathlib import Path
import numpy as np
import pandas as pd
from strategy_audit_2026_09 import research_sim as rs

LIVE_P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
CFG = {"LIVE": dict(rr=3.0, min_sl=2.5, max_sl=5.0, bo_lookback=3, day_loss_limit_pts=350),
       "#3": dict(rr=4.0, min_sl=3.0, max_sl=5.0, bo_lookback=3, day_loss_limit_pts=500)}


def trades(name, c):
    p = dict(LIVE_P, **c)
    f = rs.v40.v40_frame(rs.load(name), p)
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    t["R"] = t.net / t.risk_pts
    t["hold_h"] = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    t = t.merge(f[["time", "atr"]].rename(columns={"time": "signal_time"}), on="signal_time", how="left")
    return t


pd.set_option("display.width", 250, "display.max_rows", 100)
for name in ("MCX_SILVER1", "MCX_SILVERM1"):
    out = {}
    span = (rs.load(name).time.iloc[-1] - rs.load(name).time.iloc[0]).days / 30.4
    for k, c in CFG.items():
        t = trades(name, c)
        wins, loss = t[t.net > 0], t[t.net < 0]
        sl_only = t[t.result == "SL"]
        night = (t.entry_time.dt.date != t.exit_time.dt.date)
        out[k] = {
            "trades per month": round(len(t) / span, 1), "trades per week": round(len(t) / span / 4.35, 1),
            "stop dist: avg / median pts": f"{t.risk_pts.mean():,.0f} / {t.risk_pts.median():,.0f}",
            "stop dist: avg x ATR": round((t.risk_pts / t.atr).mean(), 2), "target dist: avg pts": f"{(t.risk_pts * c['rr']).mean():,.0f}",
            "exits by TP / SL / DAY LIMIT": f"{(t.result == 'TP').sum()} / {(t.result == 'SL').sum()} / {(t.result == 'DAY LIMIT').sum()}",
            "TP hit rate %": round(100 * (t.result == "TP").mean(), 1), "avg win / avg loss (pts)": f"{wins.net.mean():,.0f} / {loss.net.mean():,.0f}",
            "payoff ratio (avg win / avg loss)": round(wins.net.mean() / -loss.net.mean(), 2),
            "expectancy pts / R": f"{t.net.mean():,.0f} / {t.R.mean():.3f}", "breakeven win % needed at this RR": round(100 / (1 + c["rr"]), 1),
            "actual win %": round(100 * (t.net > 0).mean(), 1),
            "held overnight %": round(100 * night.mean()), "held > 24h %": round(100 * (t.hold_h > 24).mean()),
            "held < 2h %": round(100 * (t.hold_h < 2).mean()), "median hold h": round(t.hold_h.median(), 1),
            "longest trade h": round(t.hold_h.max()), "long / short trades": f"{(t.side == 'LONG').sum()} / {(t.side == 'SHORT').sum()}",
            "long / short net pts": f"{t[t.side == 'LONG'].net.sum():,.0f} / {t[t.side == 'SHORT'].net.sum():,.0f}",
            "worst day (pts)": round(t.groupby(t.exit_time.dt.date).net.sum().min()),
            "trades with stop > 1500 pts": int((t.risk_pts > 1500).sum()),
        }
    print(f"\n===== {name} =====")
    print(pd.DataFrame(out).to_string())
