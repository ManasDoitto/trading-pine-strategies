"""Realistic compounding equity simulation for the A+ screened tier, OOS period only.

Not a new backtest -- this replays the EXACT trades already produced by final_eval.py
(research_data/stockopt/final/aplus/trades.parquet), filtered to the 131-symbol A+ screened
allowlist and the OOS window (2025-01 to 2026-09, the genuinely out-of-sample stretch quoted
throughout working_strategies/StockOptions/README.md). What's new here is capital: each trade
is sized at risk_frac of CURRENT equity (compounding, same rule as stockopt/shadow.py), and
trades that overlap in time compete for the same margin -- a signal is skipped if there isn't
enough free capital, exactly as shadow_runner.py would skip it live. This is what turns a
per-trade win-rate/PF table into an actual "start with X, end with Y" answer.

    python -m stockopt.compound_backtest --risk 0.01
    python -m stockopt.compound_backtest --risk 0.02
    python -m stockopt.compound_backtest --risk 0.01 0.02 --out research_data/stockopt/final/compounding

Writes <out>_<risk>.csv (the full event-by-event equity curve) and prints a summary.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import shadow  # noqa: E402

TRADES_FILE = os.path.join(ROOT, "research_data", "stockopt", "final", "aplus", "trades.parquet")
STARTING_CAPITAL = 100000.0


def load_oos_trades() -> pd.DataFrame:
    spec = json.load(open(os.path.join(ROOT, "stockopt", "strategy_v1.json")))
    allow = set(spec["aplus"]["symbol_allowlist"])
    tr = pd.read_parquet(TRADES_FILE)
    tr = tr[(tr.symbol.isin(allow)) & (tr.period == "OOS")].copy()
    return tr.sort_values("entry_dt").reset_index(drop=True)


def simulate(tr: pd.DataFrame, risk_frac: float, mpct_cache: dict) -> tuple[pd.DataFrame, dict]:
    """Event-driven: process entries and exits in time order (exits first on a tie, so
    capital freed by a same-minute close is available to a same-minute new signal -- the
    same ordering shadow_runner.py's pass-based loop effectively gets for free)."""
    equity = STARTING_CAPITAL
    peak = equity
    max_dd_rupees = 0.0
    max_dd_pct = 0.0
    open_margin = 0.0
    open_trades: dict[int, dict] = {}
    taken = skipped = 0
    curve = []

    events = []
    for idx, row in tr.iterrows():
        events.append((row.entry_dt, 0, idx))
        events.append((row.exit_dt, -1, idx))
    events.sort(key=lambda e: (e[0], e[1]))

    for t, kind, idx in events:
        row = tr.loc[idx]
        if kind == -1:
            if idx not in open_trades:
                continue
            ot = open_trades.pop(idx)
            open_margin -= ot["margin"]
            pnl = ot["risk_rupees"] * row.R
            equity += pnl
            peak = max(peak, equity)
            dd_rupees = peak - equity
            max_dd_rupees = max(max_dd_rupees, dd_rupees)
            max_dd_pct = max(max_dd_pct, dd_rupees / peak * 100)
            curve.append(dict(t=t, equity=equity, event="CLOSE", symbol=row.symbol,
                              pnl_inr=round(pnl, 2), open_margin=round(open_margin, 2)))
        else:
            risk_rupees = equity * risk_frac
            shares = max(1, round(risk_rupees / (row.entry * row.risk_pct / 100.0)))
            mpct = mpct_cache.get(row.symbol, shadow.DEFAULT_MARGIN_PCT)
            margin_needed = shares * row.entry * mpct
            free = equity - open_margin
            if margin_needed > free:
                skipped += 1
                curve.append(dict(t=t, equity=equity, event="SKIP_NO_CAPITAL", symbol=row.symbol,
                                  pnl_inr=0.0, open_margin=round(open_margin, 2)))
                continue
            open_trades[idx] = dict(margin=margin_needed, risk_rupees=risk_rupees)
            open_margin += margin_needed
            taken += 1
            curve.append(dict(t=t, equity=equity, event="OPEN", symbol=row.symbol,
                              pnl_inr=0.0, open_margin=round(open_margin, 2)))

    summary = dict(
        risk_frac=risk_frac, trades_available=len(tr), taken=taken, skipped_no_capital=skipped,
        final_equity=round(equity, 2), total_return_pct=round((equity / STARTING_CAPITAL - 1) * 100, 2),
        max_drawdown_inr=round(max_dd_rupees, 2), max_drawdown_pct=round(max_dd_pct, 2),
    )
    return pd.DataFrame(curve), summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risk", type=float, nargs="+", default=[0.01, 0.02])
    ap.add_argument("--out", default=os.path.join(ROOT, "research_data", "stockopt", "final", "compounding"))
    a = ap.parse_args()

    tr = load_oos_trades()
    mpct_cache = shadow._margin_pct_map()
    print(f"OOS trades in A+ screened universe: {len(tr)}  "
          f"({tr.entry_dt.min().date()} to {tr.exit_dt.max().date()})\n")

    summaries = []
    for r in a.risk:
        curve, summary = simulate(tr, r, mpct_cache)
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        curve.to_csv(f"{a.out}_{r:.0%}.csv".replace("%", "pct"), index=False)
        summaries.append(summary)
        print(f"--- risk {r:.0%} per trade ---")
        for k, v in summary.items():
            if k != "risk_frac":
                print(f"  {k}: {v}")
        print()

    pd.DataFrame(summaries).to_csv(f"{a.out}_summary.csv", index=False)
    print(f"summary written to {a.out}_summary.csv")


if __name__ == "__main__":
    main()
