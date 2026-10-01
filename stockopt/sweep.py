"""Staged grid sweeps on symbol set A.

Each block varies a few related parameters around the current best config, ranks on
the in-sample period only, and prints validation numbers alongside purely so that a
plateau that collapses out of sample is visible early. Nothing is chosen on VAL/OOS here.

    python -m stockopt.sweep --block setup
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import engine, research as RS  # noqa: E402

OUT = os.path.join(ROOT, "research_data", "stockopt")
BEST_JSON = os.path.join(OUT, "best_cfg.json")

BASE = dict(engine.DEFAULTS, pb_on=0, gate_mode=0)

BLOCKS = {
    "setup": {
        "bo_n": [8, 10, 12, 15, 18, 24],
        "bo_tight": [1.5, 2.0, 2.5, 3.0, 4.0],
    },
    "trend": {
        "slope_min": [0.0, 0.15, 0.3, 0.5],
        "slope_max": [1.5, 2.5, 99.0],
        "ext_max": [1.0, 1.5, 2.5],
        "use_htf": [0, 1],
        "use_daily": [0, 1],
    },
    "exit": {
        "min_risk_atr": [0.5, 0.8, 1.2],
        "rr": [2.0, 3.0, 5.0],
        "trail_after": [0.0, 1.0, 1.5],
        "trail_mode": [0, 1],
        "trail_buf": [0.25, 0.5],
    },
    "session": {
        "entry_from": [15, 30, 45],
        "entry_to": [150, 240, 330],
        "max_trades_day": [1, 2, 3],
        "arm_bars": [1, 3],
    },
    "quality": {
        "rs_min": [-99.0, 0.0, 0.5, 1.0, 1.5, 2.0],
        "use_rvol": [0, 1],
        "rvol_min": [1.0, 1.5, 2.0],
    },
    "pullback": {
        "pb_on": [0, 1],
        "max_touch": [-1, 0],
        "sigq": [0.0, 0.5],
    },
}


def load_best():
    if os.path.exists(BEST_JSON):
        return json.load(open(BEST_JSON))
    return dict(BASE)


def score(df: pd.DataFrame) -> pd.Series:
    """Net underlying % captured after the option-buyer hurdle -- the quantity that pays."""
    return (df.exp_pct - RS.HURDLE_PCT) * df.n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", required=True, choices=list(BLOCKS))
    ap.add_argument("--filt", default="g1ov15", help="day filter bucket used for ranking")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--save", action="store_true", help="write the IS-best back to best_cfg.json")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    base = load_best()
    grid = BLOCKS[a.block]
    keys = list(grid)
    cfgs = []
    for vals in itertools.product(*[grid[k] for k in keys]):
        c = dict(base)
        c.update(dict(zip(keys, vals)))
        cfgs.append(c)
    A, _ = RS.split_symbols()
    print(f"block={a.block} configs={len(cfgs)} symbols(A)={len(A)}", flush=True)
    t0 = time.time()
    agg = RS.sweep(cfgs, A, workers=a.workers)
    print(f"swept in {time.time()-t0:.0f}s", flush=True)

    for k in keys:
        agg[k] = agg.cfg.map(lambda i, k=k: cfgs[i][k])
    agg["score"] = score(agg)
    agg.to_csv(os.path.join(OUT, f"stage_{a.block}.csv"), index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    cols = keys + ["n", "win", "pf", "expR", "exp_pct", "score", "sym_pos"]
    for filt in ["all", a.filt]:
        IS = agg[(agg.filt == filt) & (agg.period == "IS")].set_index("cfg")
        VAL = agg[(agg.filt == filt) & (agg.period == "VAL")].set_index("cfg")
        top = IS.sort_values("score", ascending=False).head(15)
        show = top[cols].copy()
        show["VAL_pf"] = VAL.reindex(top.index).pf
        show["VAL_exp%"] = VAL.reindex(top.index).exp_pct
        show["VAL_n"] = VAL.reindex(top.index).n
        print(f"\n=== top by IS score  [filter={filt}] ===")
        print(show.round(3).to_string())

    if a.save:
        IS = agg[(agg.filt == a.filt) & (agg.period == "IS")]
        best = int(IS.sort_values("score", ascending=False).iloc[0].cfg)
        json.dump(cfgs[best], open(BEST_JSON, "w"), indent=1)
        print("\nsaved best:", {k: cfgs[best][k] for k in keys})


if __name__ == "__main__":
    main()
