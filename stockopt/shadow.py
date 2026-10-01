"""Shadow (paper) trade tracking for the Stocks-in-Play MA Base Breakout, A+ screened tier.

No orders are ever placed -- this only ever reads prices. Position sizing follows the
1%-of-current-equity risk rule established in research (README + memory): the same rule
that produced the OOS/6-year sizing analysis this module now runs forward, live, for real.

Storage: two small JSON files under research_data/stockopt/ (gitignored):
  shadow_trades.json  -- every trade, OPEN or CLOSED
  shadow_equity.json  -- the running capital ledger (starting capital + realised P&L)

Everything here mirrors trading_exec/shadow.py's conventions (atomic writes, OPEN/CLOSED
status, mark-then-record loop) but tracks the UNDERLYING directly (equity intraday, MIS),
not an option premium -- per the 2026-09-29 finding that buying monthly ATM options on
these signals loses money in aggregate, while the underlying edge is real.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "research_data", "stockopt")
TRADES_STORE = os.path.join(DATA_DIR, "shadow_trades.json")
EQUITY_STORE = os.path.join(DATA_DIR, "shadow_equity.json")
MARGIN_FILE = os.path.join(DATA_DIR, "aplus_v1_equity_vs_futures_margin.csv")

RISK_FRAC = 0.01          # 1% of current equity risked per trade -- the recommended level
STARTING_CAPITAL = 100000.0
DEFAULT_MARGIN_PCT = 0.20  # fallback if a symbol is missing from the margin snapshot


def _atomic_write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _margin_pct_map() -> dict:
    if not os.path.exists(MARGIN_FILE):
        return {}
    import pandas as pd
    m = pd.read_csv(MARGIN_FILE)
    m = m[m.note == "ok"]
    return (m.eq_margin / m.notional).to_dict() | dict(zip(m.symbol, m.eq_margin / m.notional))


def margin_pct_for(symbol: str, cache: dict | None = None) -> float:
    cache = cache if cache is not None else _margin_pct_map()
    return float(cache.get(symbol, DEFAULT_MARGIN_PCT))


# --------------------------------------------------------------------------- #
# equity ledger
# --------------------------------------------------------------------------- #
def load_equity() -> dict:
    if os.path.exists(EQUITY_STORE):
        return json.load(open(EQUITY_STORE))
    return dict(starting_capital=STARTING_CAPITAL, realised_pnl_inr=0.0, updated=None)


def save_equity(eq: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    _atomic_write_json(EQUITY_STORE, eq)


def current_equity(eq: dict | None = None) -> float:
    eq = eq if eq is not None else load_equity()
    return eq["starting_capital"] + eq["realised_pnl_inr"]


# --------------------------------------------------------------------------- #
# trade store
# --------------------------------------------------------------------------- #
def load() -> list:
    if os.path.exists(TRADES_STORE):
        return json.load(open(TRADES_STORE))
    return []


def save(trades: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    _atomic_write_json(TRADES_STORE, trades)


def open_trades(trades: list | None = None) -> list:
    return [t for t in (trades if trades is not None else load()) if t["status"] == "OPEN"]


def margin_in_use(trades: list | None = None) -> float:
    return sum(t["margin_inr"] for t in open_trades(trades))


def make_id(symbol: str, entry_dt, dir_: int) -> str:
    return f"{symbol}-{entry_dt}-{'L' if dir_ == 1 else 'S'}"


def size_trade(symbol: str, entry: float, stop: float, mpct_cache: dict) -> dict:
    """The 1%-risk sizing rule: how many shares, and what margin, for this specific stop
    distance and the CURRENT tracked equity (not the original starting capital -- this is
    what makes it compounding, matching the 6-year simulation)."""
    eq = current_equity()
    risk_pct = abs(entry - stop) / entry * 100.0
    risk_rupees = eq * RISK_FRAC
    notional = risk_rupees / (risk_pct / 100.0) if risk_pct > 0 else 0.0
    shares = max(1, round(notional / entry))
    mpct = margin_pct_for(symbol, mpct_cache)
    margin_needed = shares * entry * mpct
    return dict(shares=shares, margin_inr=round(margin_needed, 2), equity_at_entry=eq,
               risk_pct=round(risk_pct, 4), margin_pct=round(mpct, 4))


def open_trade(symbol: str, dir_: int, entry: float, stop: float, target: float,
               entry_dt, setup: int, tier: str, mpct_cache: dict | None = None) -> dict | None:
    """Returns the new trade dict, or None if there isn't enough free capital right now
    (mirrors the capital-constrained 6-year simulation -- a real account behaves the same way)."""
    mpct_cache = mpct_cache if mpct_cache is not None else _margin_pct_map()
    sizing = size_trade(symbol, entry, stop, mpct_cache)
    eq = sizing["equity_at_entry"]
    free = eq - margin_in_use()
    if sizing["margin_inr"] > free:
        return None
    return dict(
        id=make_id(symbol, entry_dt, dir_), symbol=symbol, tier=tier, dir=dir_, setup=setup,
        status="OPEN",
        entry=entry, stop=stop, target=target, entry_dt=str(entry_dt),
        shares=sizing["shares"], margin_inr=sizing["margin_inr"], equity_at_entry=eq,
        risk_pct=sizing["risk_pct"], margin_pct=sizing["margin_pct"],
        opened_at=datetime.now().replace(microsecond=0).isoformat(),
        exit=None, exit_dt=None, exit_reason=None, pnl_inr=None, pct=None,
    )


def close_trade(trade: dict, exit_px: float, exit_dt, reason: str) -> dict:
    trade["status"] = "CLOSED"
    trade["exit"] = round(exit_px, 4)
    trade["exit_dt"] = str(exit_dt)
    trade["exit_reason"] = reason
    trade["closed_at"] = datetime.now().replace(microsecond=0).isoformat()
    sign = 1 if trade["dir"] == 1 else -1
    pnl = trade["shares"] * (exit_px - trade["entry"]) * sign
    trade["pnl_inr"] = round(pnl, 2)
    trade["pct"] = round((exit_px / trade["entry"] - 1) * 100.0 * sign, 4)
    eq = load_equity()
    eq["realised_pnl_inr"] += trade["pnl_inr"]
    eq["updated"] = datetime.now().replace(microsecond=0).isoformat()
    save_equity(eq)
    return trade


def record(trade: dict, trades: list | None = None) -> list:
    trades = trades if trades is not None else load()
    if any(t["id"] == trade["id"] for t in trades):
        return trades
    trades.append(trade)
    save(trades)
    return trades


def summary(trades: list | None = None) -> dict:
    trades = trades if trades is not None else load()
    closed = [t for t in trades if t["status"] == "CLOSED"]
    op = [t for t in trades if t["status"] == "OPEN"]
    n = len(closed)
    wins = [t for t in closed if t["pnl_inr"] > 0]
    eq = load_equity()
    return dict(
        equity=current_equity(eq), starting_capital=eq["starting_capital"],
        realised_pnl_inr=eq["realised_pnl_inr"],
        closed_trades=n, open_trades=len(op),
        win_pct=round(100 * len(wins) / n, 1) if n else None,
        margin_in_use=round(margin_in_use(trades), 2),
    )
