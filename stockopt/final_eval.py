"""Final, one-shot evaluation of the locked spec (stockopt/strategy_v1.json).

Reports every period on both symbol sets, plus yearly, direction, per-symbol points,
drawdown and concurrency. Writes trades and tables to research_data/stockopt/final/.

    python -m stockopt.final_eval
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import engine, research as RS  # noqa: E402

OUT = os.path.join(ROOT, "research_data", "stockopt", "final")


def apply_day_filter(tr: pd.DataFrame, f: dict, dt: pd.DataFrame | None) -> pd.DataFrame:
    m = (tr.gap.abs() >= f["gap_min"]) & (tr.orvol >= f["orvol_min"])
    tr = tr[m]
    if f.get("top_n"):
        tr = RS.attach_day(tr, dt)
        tr = tr[tr.heat_rank_inplay <= f["top_n"]]
    return tr


def rank_in_play(dt: pd.DataFrame, f: dict) -> pd.DataFrame:
    """Rank only the stocks that pass the in-play thresholds, by catalyst heat, per day."""
    ip = (dt.agap >= f["gap_min"]) & (dt.orvol >= f["orvol_min"])
    dt = dt.copy()
    dt["heat_rank_inplay"] = np.nan
    dt.loc[ip, "heat_rank_inplay"] = dt[ip].groupby("date").heat.rank(ascending=False, method="first")
    return dt


def table(tr, by):
    return RS.summarize(tr, by).round(3)


def main():
    spec = json.load(open(os.path.join(ROOT, "stockopt", "strategy_v1.json")))
    base = dict(engine.DEFAULTS)
    base.update(spec["kernel"])
    tiers = [("core", base), ("aplus", dict(base, **spec["aplus"]))]
    for tier, cfg in tiers:
        evaluate(spec, cfg, tier)


def evaluate(spec, cfg, tier):
    global OUT
    OUT = os.path.join(ROOT, "research_data", "stockopt", "final", tier)
    f = spec["day_filter"]
    A, B = RS.split_symbols()
    os.makedirs(OUT, exist_ok=True)
    print()
    print("################ TIER " + tier.upper() + " ################")
    print(f"spec {spec['version']}  A={len(A)} B={len(B)}  filter={f}  rs_min={cfg['rs_min']}")

    dt = None
    if f.get("top_n"):
        dt = rank_in_play(RS.day_table(A + B, workers=1), f)

    tr = RS.collect(cfg, A + B, workers=1)
    tr["set"] = np.where(tr.symbol.isin(A), "A", "B")
    tr = apply_day_filter(tr, f, dt)
    if "heat_rank_inplay" not in tr.columns and dt is not None:
        tr = RS.attach_day(tr, dt)
    tr["year"] = tr.entry_dt.dt.year
    tr.to_parquet(os.path.join(OUT, "trades.parquet"))

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print("\n=== by set x period ===")
    t1 = table(tr, ["set", "period"])
    print(t1.to_string())
    print("\n=== all symbols, by period ===")
    t2 = table(tr, ["period"])
    print(t2.to_string())
    print("\n=== all symbols, whole history ===")
    t3 = RS.summarize(tr).round(3)
    print(t3.to_string())
    print("\n=== by year (all symbols) ===")
    t4 = table(tr, ["year"])
    print(t4.to_string())
    print("\n=== by direction x period ===")
    t5 = table(tr, ["dir", "period"])
    print(t5.to_string())

    # per-symbol gross points (house convention), whole history
    ps = tr.groupby("symbol").agg(trades=("R", "size"), win=("R", lambda x: 100 * (x > 0).mean()),
                                  net_points=("points", "sum"), net_pct=("pct", "sum"),
                                  pf=("R", lambda x: x[x > 0].sum() / max(-x[x <= 0].sum(), 1e-9)))
    ps = ps.sort_values("net_pct", ascending=False)
    ps.round(2).to_csv(os.path.join(OUT, "per_symbol.csv"))
    print(f"\nsymbols profitable (net %): {(ps.net_pct > 0).sum()}/{len(ps)}")
    print("top 10 by net % move:\n", ps.head(10).round(2).to_string())
    print("bottom 5:\n", ps.tail(5).round(2).to_string())

    # concurrency: open positions at any moment
    ev = pd.concat([pd.DataFrame({"t": tr.entry_dt, "d": 1}), pd.DataFrame({"t": tr.exit_dt, "d": -1})])
    ev = ev.sort_values(["t", "d"])
    conc = ev.d.cumsum()
    per_day = tr.groupby("date").size()
    print(f"\nmax concurrent positions {int(conc.max())}, 95th pct {int(np.percentile(conc, 95))}; "
          f"trading days with a signal {len(per_day)}, trades/day median {per_day.median():.0f} max {per_day.max()}")

    # daily R (portfolio) for drawdown in R
    daily = tr.groupby("date").R.sum()
    eq = daily.cumsum()
    dd = (eq.cummax() - eq).max()
    print(f"portfolio: net {daily.sum():.1f}R over {len(daily)} signal days, max DD {dd:.1f}R, "
          f"positive days {100 * (daily > 0).mean():.1f}%")
    daily.to_csv(os.path.join(OUT, "daily_R.csv"))
    for name, t in [("by_set_period", t1), ("by_period", t2), ("overall", t3), ("by_year", t4), ("by_dir_period", t5)]:
        t.to_csv(os.path.join(OUT, f"{name}.csv"))


if __name__ == "__main__":
    main()
