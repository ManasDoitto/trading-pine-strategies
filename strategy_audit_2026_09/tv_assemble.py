"""Splice the TradingView replay windows (tv_harvest_trades.py) into one trade list per config and compare with the Python simulator.

Window ownership: each window owns trades that ENTER in [its start, the next newer window's start); the oldest window t11 (clamped by TradingView's
replay floor, so it overlaps t10) owns [t11 start, t10 start). Python is run on the same bars WITHOUT the 15-17h exclusion (the Pine script has none)
and only trades entering from the same first date are compared.
"""
import json
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from strategy_audit_2026_09 import research_sim as rs

TV = Path(__file__).resolve().parents[1] / "research_data" / "tv_trades"
LIVE_P = tomllib.loads(Path("trading_agents/config.toml").read_text(encoding="utf-8"))["strategy"]["SILVER"]
LIVE_P = {k: v for k, v in LIVE_P.items() if k != "exclude_hours"}
CONFIGS = {"LIVE": ("rr3_sl2.5_dl350", dict(rr=3.0, min_sl=2.5, day_loss_limit_pts=350)),
           "#3": ("rr4_sl3_dl500", dict(rr=4.0, min_sl=3.0, day_loss_limit_pts=500))}
IST = pd.Timedelta(hours=5, minutes=30)


def tv_trades(inst, label):
    tiles = {}
    for i in range(12):
        f = TV / f"{inst}_t{i:02d}__{label}.json"
        tiles[i] = json.loads(f.read_text(encoding="utf-8"))
    starts = {i: tiles[i]["window"]["from"] for i in tiles}
    rows = []
    for i, tile in tiles.items():
        lo = starts[i]
        hi = starts[i - 1] if i > 0 else 10 ** 14
        if i == 11:
            hi = starts[10]
        pv = tile["point_value"]
        for t in tile["trades"]:
            if lo <= t["entry_ms"] < hi:
                rows.append(dict(side=t["side"], entry_time=pd.to_datetime(t["entry_ms"], unit="ms") + IST,
                                 exit_time=pd.to_datetime(t["exit_ms"], unit="ms") + IST, net=t["net_inr"] / pv,
                                 risk_pts=abs(t["entry"] - t["exit"]), tile=i))
    d = pd.DataFrame(rows).drop_duplicates(["entry_time", "side"]).sort_values("entry_time").reset_index(drop=True)
    return d, pd.to_datetime(starts[11], unit="ms") + IST


def py_trades(inst, cfg, first):
    p = dict(LIVE_P, **cfg)
    f = rs.v40.v40_frame(rs.load(inst), p)
    t = pd.DataFrame(rs.simulate(f, p))
    t["entry_time"], t["exit_time"] = pd.to_datetime(t.entry_time), pd.to_datetime(t.exit_time)
    return t[t.entry_time >= first].reset_index(drop=True)


def pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return round(w / l, 2) if l > 0 else 9.99


def kp(t):
    mo = t.groupby(t.exit_time.dt.to_period("M")).net.sum()
    eq = t.net.cumsum()
    q = t.exit_time.quantile([.6, .8])
    hold = (t.exit_time - t.entry_time).dt.total_seconds() / 3600
    return {"trades": len(t), "win %": round(100 * (t.net > 0).mean(), 1), "PF points": pf(t.net), "net points": round(t.net.sum()),
            "avg win / loss pts": f"{t.net[t.net > 0].mean():,.0f} / {t.net[t.net < 0].mean():,.0f}", "max DD points": round((eq.cummax() - eq).max()),
            "net / DD": round(t.net.sum() / (eq.cummax() - eq).max(), 2), "months": len(mo), "months positive": f"{int((mo > 0).sum())}/{len(mo)} ({100*(mo>0).mean():.0f}%)",
            "best month % of net": round(100 * mo.max() / t.net.sum()), "PF early/mid/recent": " / ".join(str(pf(s.net)) for s in (
                t[t.exit_time <= q[.6]], t[(t.exit_time > q[.6]) & (t.exit_time <= q[.8])], t[t.exit_time > q[.8]])),
            "avg / median hold h": f"{hold.mean():.1f} / {hold.median():.1f}", "held >24h %": round(100 * (hold > 24).mean())}


pd.set_option("display.width", 250, "display.max_rows", 100)
for inst, name in (("SILVER1", "MCX_SILVER1"), ("SILVERM1", "MCX_SILVERM1")):
    res, match = {}, {}
    for cname, (label, cfg) in CONFIGS.items():
        tv, first = tv_trades(inst, label)
        py = py_trades(name, cfg, first)
        res[f"TV {cname}"], res[f"Python {cname}"] = kp(tv), kp(py)
        k = py.assign(k=py.entry_time.dt.floor("5min").astype(str) + py.side)
        tk = set(tv.entry_time.dt.floor("5min").astype(str) + tv.side)
        pk = set(k.k)
        match[cname] = (len(tk & pk), len(tv), len(py))
        tv.to_csv(TV.parent / f"tv_spliced_{inst}_{cname.strip('#')}.csv", index=False)
    print(f"\n===== {inst}: TradingView (spliced 12 replay windows) vs Python simulator, same coverage from {first:%Y-%m-%d} =====")
    print(pd.DataFrame(res).to_string())
    print("trades with identical entry bar+side (TV, Python):", {c: f"{m[0]} common of {m[1]} TV / {m[2]} Python" for c, m in match.items()})
