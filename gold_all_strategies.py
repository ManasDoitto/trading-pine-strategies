"""Run EVERY strategy family in the repo on real XAUUSD (Dukascopy 1m, 2018-2026) with identical
costs and a strict train/test split. Reuses the repo's own research modules (strategy_audit_2026_09/)
unchanged: gold frames are injected through bnf_port_test.base()'s cache, and research_sim.simulate is
wrapped to run in yearly tiles (memory) -- signals and exit mechanics are exactly the repo's.

Times are naive IST (UTC+5:30) like every other frame in the repo. Costs are applied AFTER simulation
from the gross points (commission=0 inside the sim): net = gross - c*(entry+exit), c per side.
Train = entries before 2022-01-01, test = 2022-01-01 onward.
"""
from __future__ import annotations
import sys, os, time, json, pickle
from pathlib import Path
ROOT = Path(__file__).resolve().parent
AUD = ROOT / "strategy_audit_2026_09"
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(AUD))
import numpy as np, pandas as pd
import research_sim as rs
import bnf_port_test as B
import bnf_scratch_scalp as X
import bnf_new_families as N
from trading_agents.core import signals_v50 as v50
from trading_agents.core.levels import true_range, wilder

SPLIT = pd.Timestamp("2022-01-01")
INST = "XAU"
COSTS = {"$0.50 round-trip (tight ECN/CFD)": ("usd", 0.50), "$1.00 round-trip (CFD + commission)": ("usd", 1.00),
         "0.03%/side": ("pct", 0.0003), "0.06%/side (perp taker)": ("pct", 0.0006)}
ANY_TIME = ("00:00", "23:59")            # whole IST day
NO_FLAT = ["25:00", "26:00"]            # never flat / never excluded
ACTIVE = ("12:30", "23:59")             # London+NY active window: 07:00-18:29 UTC


def load_1m() -> pd.DataFrame:
    d = pd.read_pickle(os.environ.get("GOLD_1M_PATH") or (ROOT / "research_data" / "gold" / "xauusd_1m.pkl"))
    d["time"] = pd.to_datetime(d["time"])
    return d.sort_values("time").reset_index(drop=True)


def resample(d1m: pd.DataFrame, minutes: int) -> pd.DataFrame:
    r = (d1m.set_index("time").resample(f"{minutes}min", label="left", closed="left")
         .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
         .dropna(subset=["close"]).reset_index())
    r["time"] = r["time"] + pd.Timedelta(hours=5, minutes=30)         # UTC -> naive IST, repo convention
    return r


def make_base(df: pd.DataFrame) -> pd.DataFrame:
    d = df.reset_index(drop=True).copy()
    d["e9"] = v50.ema(d["close"], 9); d["e22"] = v50.ema(d["close"], 22); d["e200"] = v50.ema(d["close"], 200)
    d["atr"] = wilder(true_range(d["high"], d["low"], d["close"]), 14)
    d["adx15_prev"] = v50.adx_15m_prev(df.reset_index(drop=True))
    d["atr_p90"] = d["atr"].rolling(500).quantile(0.9)
    d["tmin"] = d["time"].dt.hour * 60 + d["time"].dt.minute
    return d


# ---- yearly-tiled wrapper around the repo's simulator --------------------------------------------------
_orig_sim = rs.simulate
def tiled_simulate(df, p, start=rs.WARMUP, **kw):
    yrs = df["time"].dt.year.to_numpy()
    out = []
    for y in np.unique(yrs):
        idx = np.flatnonzero(yrs == y)
        lo = max(0, idx[0] - rs.WARMUP)
        sub = df.iloc[lo: idx[-1] + 1]
        st = rs.WARMUP if lo > 0 else start
        out += _orig_sim(sub, p, start=st, **kw)
    return out
rs.simulate = tiled_simulate


def set_session(sess, flat=None):
    for mod in (B, X, N):
        mod.SESSION = sess
        mod.FLAT = flat or NO_FLAT


def trades_to_frame(tr) -> pd.DataFrame:
    if not tr:
        return pd.DataFrame()
    t = pd.DataFrame(tr)
    t["entry_time"] = pd.to_datetime(t["entry_time"]); t["exit_time"] = pd.to_datetime(t["exit_time"])
    t["side_n"] = np.where(t["side"] == "LONG", 1, -1)
    return t[["entry_time", "exit_time", "side_n", "entry", "exit", "risk_pts", "gross"]]


MIN_STOP = 0.0003      # trades with a stop < 0.03% of price are untradable noise (flat Dukascopy bars -> ATR~0)
R_CLIP = (-5.0, 10.0)

def clean(t: pd.DataFrame) -> pd.DataFrame:
    if len(t) == 0: return t
    return t[(t["risk_pts"] / t["entry"]) >= MIN_STOP].reset_index(drop=True)


def summarize(t: pd.DataFrame, cost: float):
    """Per-trade R net of cost. gross is in price points (commission=0 in sim)."""
    if len(t) == 0:
        return None
    kind, x = cost if isinstance(cost, tuple) else ("pct", cost)
    net = t["gross"] - (x if kind == "usd" else x * (t["entry"] + t["exit"]))
    r = (net / t["risk_pts"]).clip(*R_CLIP)
    return r


def stat_row(t: pd.DataFrame, cost: float) -> dict:
    t = clean(t)
    r = summarize(t, cost)
    if r is None or len(r) < 5:
        return dict(n=0)
    tr, te = r[t["entry_time"] < SPLIT], r[t["entry_time"] >= SPLIT]
    weeks = (t["entry_time"].max() - t["entry_time"].min()).days / 7.0
    def t_(x): return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 3 and x.std() > 0 else np.nan
    gross_r = (t["gross"] / t["risk_pts"]).clip(*R_CLIP)
    return dict(n=len(r), per_wk=len(r) / max(weeks, 1), win=(r > 0).mean(), gross_R=gross_r.mean(),
                net_R=r.mean(), t_all=t_(r), n_tr=len(tr), R_tr=tr.mean() if len(tr) else np.nan,
                n_te=len(te), R_te=te.mean() if len(te) else np.nan, t_te=t_(te),
                hold_h=((t["exit_time"] - t["entry_time"]).dt.total_seconds().mean() / 3600))
