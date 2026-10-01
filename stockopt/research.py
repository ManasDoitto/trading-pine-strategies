"""Research protocol for the stock-options strategy.

Splits (fixed before any tuning, never changed afterwards):
  symbols  A = even positions in the sorted universe -> used for development
           B = odd positions                        -> untouched until the final check
  time     IS  2018-01-01 .. 2022-12-31  -> parameter search
           VAL 2023-01-01 .. 2024-12-31  -> choosing between finalists
           OOS 2025-01-01 .. today       -> reported once, at the end

Day-level filters (gap, opening volume, cross-sectional rank, liquidity) are applied
after simulation. Positions never cross a session, so dropping whole symbol-days after
the fact is exactly equivalent to never arming on them.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import engine, run as R  # noqa: E402

PERIODS = {
    "IS": ("2018-01-01", "2023-01-01"),
    "VAL": ("2023-01-01", "2025-01-01"),
    "OOS": ("2025-01-01", "2030-01-01"),
}
KEEP = ["symbol", "dir", "entry_dt", "exit_dt", "entry", "exit", "points", "R", "pct",
        "risk_pct", "setup", "reason", "mfe_R", "touch", "gap", "orvol", "atr_pct", "bars"]


HURDLE_PCT = 0.09  # underlying move an ATM option buyer needs just to cover spread+theta+charges


def split_symbols():
    """Fixed from the universe file (not from whatever has downloaded) so it can never drift."""
    import json
    import re
    uni = sorted(re.sub(r"[^A-Za-z0-9_.-]", "_", u)
                 for u in json.load(open(os.path.join(ROOT, "stockopt", "universe.json"))))
    have = set(R.symbols())
    return [s for s in uni[0::2] if s in have], [s for s in uni[1::2] if s in have]


def period_of(ts: pd.Series) -> np.ndarray:
    out = np.full(len(ts), "", dtype=object)
    for k, (a, b) in PERIODS.items():
        m = (ts >= pd.Timestamp(a)) & (ts < pd.Timestamp(b))
        out[m.to_numpy()] = k
    return out


# --------------------------------------------------------------------------- #
# universe day table: per (symbol, date) catalyst features + cross-sectional ranks
# --------------------------------------------------------------------------- #
def _day_rows(sym):
    p = R.load_prep(sym)
    day = p["day"]
    first = np.r_[0, np.flatnonzero(np.diff(day)) + 1]
    dt = pd.to_datetime(p["dt"][first]).normalize()
    # orvol is fixed from 09:45 onward; read it on the first bar at/after 30 minutes
    mod = p["mod"]
    ov = pd.Series(p["orvol"]).where(mod >= 30).groupby(day).first().to_numpy()
    # liquidity: trailing 20-session median turnover, known before the session
    c = p["c"]
    v = p["v"]
    turn = pd.Series(c * v).groupby(day).sum()
    liq = turn.shift(1).rolling(20, min_periods=5).median().to_numpy()
    return pd.DataFrame({
        "symbol": sym, "date": dt, "gap": p["gap"][first], "orvol": ov, "liq": liq,
    })


def day_table(syms, workers=6) -> pd.DataFrame:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        frames = list(ex.map(_day_rows, syms))
    t = pd.concat(frames, ignore_index=True)
    t["agap"] = t.gap.abs()
    t["heat"] = t.agap.clip(upper=8) * t.orvol.clip(upper=8)
    g = t.groupby("date")
    t["liq_rank"] = g.liq.rank(ascending=False, method="first")
    t["heat_rank"] = g.heat.rank(ascending=False, method="first")
    t["ov_rank"] = g.orvol.rank(ascending=False, method="first")
    t["n_syms"] = g.symbol.transform("size")
    return t


# --------------------------------------------------------------------------- #
# trade collection
# --------------------------------------------------------------------------- #
def _collect_one(args):
    sym, cfg = args
    p = R.load_prep(sym)
    tr = engine.run(p, **cfg)
    tr["symbol"] = sym
    return tr[KEEP]


def collect(cfg: dict, syms, workers=6) -> pd.DataFrame:
    if workers <= 1:
        frames = [_collect_one((s, cfg)) for s in syms]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            frames = list(ex.map(_collect_one, [(s, cfg) for s in syms], chunksize=4))
    tr = pd.concat(frames, ignore_index=True)
    tr["period"] = period_of(tr.entry_dt)
    tr["date"] = tr.entry_dt.dt.normalize()
    return tr


def attach_day(tr: pd.DataFrame, dt: pd.DataFrame) -> pd.DataFrame:
    cols = ["symbol", "date", "liq", "liq_rank", "heat", "heat_rank", "ov_rank", "n_syms"]
    return tr.merge(dt[cols], on=["symbol", "date"], how="left")


# --------------------------------------------------------------------------- #
# stage-1 sweep: kernel parameters, summaries only (per period x filter bucket)
# --------------------------------------------------------------------------- #
FILTERS = {
    "all": lambda t: np.ones(len(t), bool),
    "g1ov15": lambda t: (t.gap.abs() >= 1.0) & (t.orvol >= 1.5),
    "g05ov12": lambda t: (t.gap.abs() >= 0.5) & (t.orvol >= 1.2),
    "ov15": lambda t: t.orvol >= 1.5,
    "g075ov125": lambda t: (t.gap.abs() >= 0.75) & (t.orvol >= 1.25),
}


def _summ(R_, P_):
    n = len(R_)
    if n == 0:
        return (0, 0, 0.0, 0.0, 0.0, 0.0)
    w = R_ > 0
    return (n, int(w.sum()), float(R_[w].sum()), float(-R_[~w].sum()), float(R_.sum()), float(P_.sum()))


def _sweep_one(args):
    sym, cfgs = args
    p = R.load_prep(sym)
    out = []
    for ci, cfg in enumerate(cfgs):
        tr = engine.run(p, **cfg)
        if not len(tr):
            continue
        per = period_of(tr.entry_dt)
        Rv = tr.R.to_numpy()
        Pv = tr.pct.to_numpy()
        for fk, fn in FILTERS.items():
            fm = np.asarray(fn(tr))
            for pk in PERIODS:
                m = fm & (per == pk)
                if m.any():
                    out.append((ci, fk, pk, sym) + _summ(Rv[m], Pv[m]))
    return out


def sweep(cfgs, syms, workers=6) -> pd.DataFrame:
    rows = []
    if workers <= 1:  # in-process: no spawn cost, safest on a low-RAM box
        for s in syms:
            rows.extend(_sweep_one((s, cfgs)))
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for res in ex.map(_sweep_one, [(s, cfgs) for s in syms]):
                rows.extend(res)
    df = pd.DataFrame(rows, columns=["cfg", "filt", "period", "symbol", "n", "w", "gp", "gl", "R", "pct"])
    agg = df.groupby(["cfg", "filt", "period"]).agg(
        n=("n", "sum"), w=("w", "sum"), gp=("gp", "sum"), gl=("gl", "sum"),
        R=("R", "sum"), pct=("pct", "sum"),
        sym_pos=("R", lambda x: (x > 0).mean() * 100), nsym=("symbol", "nunique"),
    ).reset_index()
    agg["win"] = agg.w / agg.n * 100
    agg["pf"] = agg.gp / agg.gl.replace(0, np.nan)
    agg["expR"] = agg.R / agg.n
    agg["exp_pct"] = agg.pct / agg.n
    return agg


def summarize(tr: pd.DataFrame, by=None) -> pd.DataFrame:
    def f(t):
        m = R.metrics(t)
        return pd.Series({k: m[k] for k in ("trades", "win", "pf", "exp_R", "net_R", "exp_pct",
                                            "avg_win_pct", "avg_loss_pct", "maxdd_R", "net_points")})
    if by is None:
        return f(tr).to_frame().T
    return tr.groupby(by).apply(f, include_groups=False)
