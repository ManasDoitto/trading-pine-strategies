"""Portfolio driver + parameter sweep for the MSPC engine.

Metrics are reported three ways because a stock universe spans Rs.90 to Rs.9000:
  * R            -- risk multiples, the only cross-sectionally comparable unit
  * pct          -- signed % move of the underlying, which is what drives option premium
  * points       -- gross points, per the house convention, meaningful per symbol
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BARS = os.path.join(ROOT, "research_data", "nse5m")
sys.path.insert(0, ROOT)

from stockopt import engine  # noqa: E402

_PREP_CACHE: dict = {}
_INDEX = None


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = engine.load_index()
    return _INDEX


def symbols() -> list[str]:
    return sorted(f[:-8] for f in os.listdir(BARS) if f.endswith(".parquet"))


PREP_DIR = os.path.join(ROOT, "research_data", "nse5m_prep")


def load_prep(sym: str):
    """Prepared arrays for a symbol, cached on disk as .npz (prepare() is the slow part)."""
    if sym in _PREP_CACHE:
        return _PREP_CACHE[sym]
    src = os.path.join(BARS, f"{sym}.parquet")
    cache = os.path.join(PREP_DIR, f"{sym}.npz")
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(src)             and os.path.getmtime(cache) >= os.path.getmtime(engine.__file__):
        z = np.load(cache, allow_pickle=True)
        p = {k: z[k] for k in z.files}
        p["warm"] = int(p["warm"])
        p["turnover"] = float(p["turnover"])
        if p["dt"].dtype == object:
            p["dt"] = pd.to_datetime(pd.Series(p["dt"])).dt.tz_localize(None).to_numpy().astype("datetime64[ns]")
    else:
        p = engine.prepare(pd.read_parquet(src), index=_index())
        os.makedirs(PREP_DIR, exist_ok=True)
        np.savez(cache, **p)
    _PREP_CACHE.clear()
    _PREP_CACHE[sym] = p
    return p


def _slice(tr: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    if not len(tr):
        return tr
    if start:
        tr = tr[tr.entry_dt >= pd.Timestamp(start)]
    if end:
        tr = tr[tr.entry_dt < pd.Timestamp(end)]
    return tr


def metrics(tr: pd.DataFrame) -> dict:
    n = len(tr)
    if n == 0:
        return dict(trades=0, win=0.0, pf=0.0, exp_R=0.0, net_R=0.0, net_pct=0.0,
                    exp_pct=0.0, avg_win_pct=0.0, avg_loss_pct=0.0, maxdd_R=0.0,
                    net_points=0.0, exp_points=0.0, avg_bars=0.0)
    R = tr.R.to_numpy()
    P = tr.pct.to_numpy()
    wins = R > 0
    gp = R[wins].sum()
    gl = -R[~wins].sum()
    eq = np.cumsum(np.sort(np.zeros(0)))  # placeholder
    ordered = tr.sort_values("exit_dt")
    eq = ordered.R.cumsum().to_numpy()
    dd = float((np.maximum.accumulate(np.concatenate(([0.0], eq))) - np.concatenate(([0.0], eq))).max())
    return dict(
        trades=n,
        win=float(wins.mean() * 100),
        pf=float(gp / gl) if gl > 0 else float("inf"),
        exp_R=float(R.mean()),
        net_R=float(R.sum()),
        net_pct=float(P.sum()),
        exp_pct=float(P.mean()),
        avg_win_pct=float(P[wins].mean()) if wins.any() else 0.0,
        avg_loss_pct=float(P[~wins].mean()) if (~wins).any() else 0.0,
        maxdd_R=dd,
        net_points=float(tr.points.sum()),
        exp_points=float(tr.points.mean()),
        avg_bars=float(tr.bars.mean()),
    )


# --------------------------------------------------------------------------- #
# sweep worker: one symbol, many configs
# --------------------------------------------------------------------------- #
def _worker(sym: str, configs: list[dict], start: str | None, end: str | None):
    prep = load_prep(sym)
    rows = []
    for ci, cfg in enumerate(configs):
        tr = engine.run(prep, **cfg)
        tr = _slice(tr, start, end)
        if not len(tr):
            rows.append((ci, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
            continue
        R = tr.R.to_numpy()
        P = tr.pct.to_numpy()
        w = R > 0
        rows.append((
            ci, len(tr), int(w.sum()),
            float(R[w].sum()), float(-R[~w].sum()),
            float(R.sum()), float(P.sum()),
            float(P[w].sum()), float(-P[~w].sum()),
        ))
    return sym, rows


def sweep(configs: list[dict], syms: list[str], start=None, end=None, workers=7) -> pd.DataFrame:
    agg = {i: dict(n=0, w=0, gp=0.0, gl=0.0, R=0.0, pct=0.0, pgp=0.0, pgl=0.0, syms=0, sym_pos=0)
           for i in range(len(configs))}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_worker, s, configs, start, end) for s in syms]
        for k, f in enumerate(as_completed(futs)):
            sym, rows = f.result()
            for (ci, n, w, gp, gl, R, pct, pgp, pgl) in rows:
                a = agg[ci]
                a["n"] += n
                a["w"] += w
                a["gp"] += gp
                a["gl"] += gl
                a["R"] += R
                a["pct"] += pct
                a["pgp"] += pgp
                a["pgl"] += pgl
                if n:
                    a["syms"] += 1
                    if R > 0:
                        a["sym_pos"] += 1
            if (k + 1) % 20 == 0:
                print(f"  ..{k+1}/{len(syms)} symbols", flush=True)
    out = []
    for ci, cfg in enumerate(configs):
        a = agg[ci]
        n = a["n"]
        out.append(dict(
            cfg_id=ci,
            trades=n,
            win=100.0 * a["w"] / n if n else 0.0,
            pf=a["gp"] / a["gl"] if a["gl"] > 0 else (float("inf") if a["gp"] > 0 else 0.0),
            pf_pct=a["pgp"] / a["pgl"] if a["pgl"] > 0 else 0.0,
            exp_R=a["R"] / n if n else 0.0,
            net_R=a["R"],
            exp_pct=a["pct"] / n if n else 0.0,
            net_pct=a["pct"],
            symbols=a["syms"],
            pct_syms_pos=100.0 * a["sym_pos"] / a["syms"] if a["syms"] else 0.0,
            **{k: v for k, v in cfg.items()},
        ))
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- #
def full_trades(cfg: dict, syms: list[str], start=None, end=None, workers=7) -> pd.DataFrame:
    def one(s):
        prep = load_prep(s)
        tr = engine.run(prep, **cfg)
        tr = _slice(tr, start, end)
        tr = tr.copy()
        tr["symbol"] = s
        return tr
    frames = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_trades_one, s, cfg, start, end) for s in syms]
        for f in as_completed(futs):
            frames.append(f.result())
    return pd.concat(frames, ignore_index=True).sort_values("exit_dt").reset_index(drop=True)


def _trades_one(sym, cfg, start, end):
    prep = load_prep(sym)
    tr = engine.run(prep, **cfg)
    tr = _slice(tr, start, end).copy()
    tr["symbol"] = sym
    return tr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    syms = symbols()[: a.n]
    print("symbols:", syms)
    tr = full_trades(engine.DEFAULTS, syms, workers=min(7, len(syms)))
    m = metrics(tr)
    for k, v in m.items():
        print(f"  {k:14s} {v}")
