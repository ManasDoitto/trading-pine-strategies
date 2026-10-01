"""Position size calculator: how many shares to buy for a given signal, your current real
capital, and your chosen risk % per trade.

This is deliberately separate from stockopt/shadow.py -- shadow.py tracks a FICTITIOUS paper
position with its own equity ledger (research_data/stockopt/shadow_equity.json); this module
has no position tracking of any kind. It only reads one number, your real capital, from
stockopt/position_config.json, and does the arithmetic. YOU update that number -- there is no
way for this code to know your real broker balance, so sizing will silently go stale (too
small after you've compounded gains, too large after a drawdown) until you update it.

    python -m stockopt.position_calc --entry 101.25 --stop 99.80 --symbol RELIANCE
    python -m stockopt.position_calc --set-capital 150000    # update your real capital
    python -m stockopt.position_calc --set-risk 0.02          # update risk % per trade

Formula (same fixed-fractional-risk rule used throughout this repo's research):
    risk_rupees = capital * risk_frac
    shares      = risk_rupees / abs(entry - stop)
    margin      = shares * entry * margin_pct_for(symbol)   # informational only
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import shadow  # noqa: E402

CONFIG_FILE = os.path.join(ROOT, "stockopt", "position_config.json")
DEFAULTS = dict(capital=100000.0, risk_frac=0.02)


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        return {**DEFAULTS, **json.load(open(CONFIG_FILE))}
    return dict(DEFAULTS)


def save_config(cfg: dict):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    os.replace(tmp, CONFIG_FILE)


def calc_position(entry: float, stop: float, symbol: str | None = None,
                  capital: float | None = None, risk_frac: float | None = None,
                  mpct_cache: dict | None = None) -> dict:
    cfg = load_config()
    capital = capital if capital is not None else cfg["capital"]
    risk_frac = risk_frac if risk_frac is not None else cfg["risk_frac"]
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return dict(shares=0, risk_rupees=0.0, notional_rupees=0.0, margin_rupees=0.0,
                   capital=capital, risk_frac=risk_frac)
    risk_rupees = capital * risk_frac
    shares = max(1, round(risk_rupees / risk_per_share))
    notional = shares * entry
    mpct = shadow.margin_pct_for(symbol, mpct_cache) if symbol else shadow.DEFAULT_MARGIN_PCT
    margin = notional * mpct
    return dict(shares=shares, risk_rupees=round(risk_rupees, 2), notional_rupees=round(notional, 2),
               margin_rupees=round(margin, 2), capital=capital, risk_frac=risk_frac)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", type=float)
    ap.add_argument("--stop", type=float)
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--capital", type=float, default=None, help="override, one-off (doesn't save)")
    ap.add_argument("--risk", type=float, default=None, help="override, one-off (doesn't save), e.g. 0.02")
    ap.add_argument("--set-capital", type=float, default=None, help="update your real capital in the config")
    ap.add_argument("--set-risk", type=float, default=None, help="update risk %% per trade in the config, e.g. 0.02")
    a = ap.parse_args()

    if a.set_capital is not None or a.set_risk is not None:
        cfg = load_config()
        if a.set_capital is not None:
            cfg["capital"] = a.set_capital
        if a.set_risk is not None:
            cfg["risk_frac"] = a.set_risk
        save_config(cfg)
        print(f"saved: capital=Rs{cfg['capital']:,.0f}  risk={cfg['risk_frac']:.1%}/trade")
        return

    cfg = load_config()
    print(f"current config: capital=Rs{cfg['capital']:,.0f}  risk={cfg['risk_frac']:.1%}/trade")
    if a.entry is None or a.stop is None:
        print("pass --entry and --stop to size a specific signal")
        return
    r = calc_position(a.entry, a.stop, a.symbol, a.capital, a.risk)
    print(f"\n{a.symbol or ''} entry {a.entry:.2f}  stop {a.stop:.2f}  "
          f"risk/share Rs{abs(a.entry - a.stop):.2f}")
    print(f"  shares: {r['shares']}")
    print(f"  risking: Rs{r['risk_rupees']:,.0f} ({r['risk_frac']:.1%} of Rs{r['capital']:,.0f})")
    print(f"  notional: Rs{r['notional_rupees']:,.0f}   est. margin: Rs{r['margin_rupees']:,.0f}")


if __name__ == "__main__":
    main()
