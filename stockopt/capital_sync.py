"""Keeps stockopt/position_config.json's capital figure in sync with THIS strategy's own
real, realized P&L -- automatically, without entangling it with whatever else is live in the
same Dhan account (the Crude/Silver/BankNifty/Nifty forward tests share this account and
trade MCX_COMM/IDX_I; this only ever looks at NSE_EQ fills in the 131-symbol A+ screened
allowlist).

Why not just read the account's free balance? Checked 2026-10-01: this Dhan account already
has ~Rs59k utilized and a sodLimit well above Rs1L from those other live strategies. Sizing
stock-options trades off the whole account would make position size drift for reasons that
have nothing to do with this strategy. Instead: capital = baseline_capital (what you started
this strategy with) + realized P&L of ONLY the matched NSE_EQ fills since epoch_start, net of
real brokerage/STT/taxes (Dhan's trade history reports these per fill, so this is actually
MORE accurate than the backtest's gross numbers).

Position matching is FIFO per security, long and short both handled (BUY-then-SELL for a long
signal, SELL-then-BUY for a short/intraday-short signal) -- a position nets toward zero and
realizes P&L as opposing fills consume the open queue.

    python -m stockopt.capital_sync            # sync now, print what changed
    python -m stockopt.capital_sync --dry-run   # show what WOULD change, don't write

Called automatically from scan_live.py's report() before sizing each signal.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque, defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stockopt import position_calc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIVERSE_FILE = os.path.join(ROOT, "stockopt", "universe.json")
SPEC_FILE = os.path.join(ROOT, "stockopt", "strategy_v1.json")


def _allowlist_secids() -> dict[str, str]:
    """secid (str) -> symbol, for the 131 A+ screened symbols only."""
    uni = json.load(open(UNIVERSE_FILE))
    spec = json.load(open(SPEC_FILE))
    allow = set(spec["aplus"]["symbol_allowlist"])
    return {str(v["secid"]): sym for sym, v in uni.items() if sym in allow}


def fetch_real_equity_fills(from_date: date, to_date: date) -> list[dict]:
    from trading_agents.core.dhan_client import get_dhan_client
    c = get_dhan_client()
    secid_map = _allowlist_secids()
    fills = []
    page = 0
    while True:
        res = c.get_trade_history(str(from_date), str(to_date), page)
        rows = res.get("data") or []
        if not rows:
            break
        for r in rows:
            if r.get("exchangeSegment") != "NSE_EQ":
                continue
            sym = secid_map.get(str(r.get("securityId")))
            if sym is None:
                continue  # an NSE_EQ fill that isn't one of the 131 allowlist symbols -- not ours
            real_costs = (r.get("sebiTax", 0) + r.get("stt", 0) + r.get("brokerageCharges", 0) +
                         r.get("serviceTax", 0) + r.get("exchangeTransactionCharges", 0) +
                         r.get("stampDuty", 0))
            fills.append(dict(symbol=sym, side=r["transactionType"], qty=r["tradedQuantity"],
                             price=r["tradedPrice"], costs=real_costs, t=r["exchangeTime"]))
        if len(rows) < 1000:  # Dhan pages at up to 1000; fewer means this was the last page
            break
        page += 1
    return sorted(fills, key=lambda f: f["t"])


def compute_realized_pnl(fills: list[dict]) -> tuple[float, int]:
    """FIFO per symbol, long and short both handled. Returns (net_realized_rupees, n_fills_matched)."""
    queues: dict[str, deque] = defaultdict(deque)  # symbol -> deque of [signed_qty, price]
    realized = 0.0
    matched = 0
    for f in fills:
        signed = f["qty"] if f["side"] == "BUY" else -f["qty"]
        q = queues[f["symbol"]]
        while signed != 0 and q and (q[0][0] > 0) != (signed > 0):
            lot_qty, lot_price = q[0]
            close_qty = min(abs(lot_qty), abs(signed))
            direction = 1 if lot_qty > 0 else -1  # +1 realized when closing a long, -1 a short
            realized += direction * close_qty * (f["price"] - lot_price)
            matched += 1
            lot_qty -= direction * close_qty
            signed -= direction * close_qty if direction == 1 else -direction * close_qty
            # adjust remaining lot or pop it
            if lot_qty == 0:
                q.popleft()
            else:
                q[0][0] = lot_qty
        if signed != 0:
            q.append([signed, f["price"]])
        realized -= f["costs"]
    return round(realized, 2), matched


def sync_capital(dry_run: bool = False) -> dict:
    cfg = position_calc.load_config()
    if "baseline_capital" not in cfg or "epoch_start" not in cfg:
        cfg["baseline_capital"] = cfg.get("capital", position_calc.DEFAULTS["capital"])
        cfg["epoch_start"] = date.today().isoformat()
    epoch = datetime.strptime(cfg["epoch_start"], "%Y-%m-%d").date()
    today = date.today()
    fills = fetch_real_equity_fills(epoch, today)
    realized_pnl, matched = compute_realized_pnl(fills)
    new_capital = round(cfg["baseline_capital"] + realized_pnl, 2)
    changed = abs(new_capital - cfg.get("capital", 0)) > 0.01
    result = dict(cfg, capital=new_capital, realized_pnl=realized_pnl, fills_seen=len(fills),
                 fills_matched=matched, last_synced=datetime.now().replace(microsecond=0).isoformat())
    if not dry_run:
        cfg["capital"] = new_capital
        cfg["last_synced"] = result["last_synced"]
        position_calc.save_config(cfg)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    r = sync_capital(dry_run=a.dry_run)
    print(f"epoch {r['epoch_start']}  baseline Rs{r['baseline_capital']:,.0f}")
    print(f"real NSE_EQ fills in the 131-symbol allowlist since epoch: {r['fills_seen']} "
          f"({r['fills_matched']} matched closes)")
    print(f"realized P&L (net of real brokerage/STT/taxes): Rs{r['realized_pnl']:+,.2f}")
    print(f"{'would set' if a.dry_run else 'capital now'}: Rs{r['capital']:,.2f}")


if __name__ == "__main__":
    main()
