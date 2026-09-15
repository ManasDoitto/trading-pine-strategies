"""Pre-market facts for option buying. For each instrument it gathers:
- prior-session levels and volatility regime
- the v4.0 strategy state
- an option-chain snapshot (ATM premium/IV/theta, straddle, OI walls, PCR), behind data-quality gates

It also carries the trader's own risk context from the latest journal.

Writes journal_data/facts/<date>_premarket.json (+ journal_data/iv_history.csv).

Usage (repo root):
    python -m trading_agents.facts.premarket
    python -m trading_agents.facts.premarket --date 2026-09-16 --only CRUDEOIL,BANKNIFTY
"""
import argparse
import csv
import json
import math
import sys
import traceback
from datetime import date, datetime, time, timedelta

import numpy as np

from ..core import instruments, levels, options, signals
from ..core.config import data_dir, load_config
from ..core.dhan_client import get_dhan_client
from ..core.market_data import intraday_bars


def rounded(obj, nd=2):
    """JSON-safe copy: floats rounded, numpy scalars unwrapped, dates as ISO strings."""
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return None if math.isnan(obj) or math.isinf(obj) else round(float(obj), nd)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):                        # pandas Timestamp
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): rounded(v, nd) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [rounded(v, nd) for v in obj]
    return obj


def rule_bias(und, strat):
    """Deterministic reference bias the analyst starts from (and the scorecard can grade)."""
    if not und.get("available"):
        return "neutral", "levels unavailable"
    c, piv, pos = und["prev_day"]["close"], und["pivots"]["P"], und["prev_day"]["close_position_pct"] or 50
    side = "above" if c >= piv else "below"
    if strat.get("available"):
        a = strat["alignment"]
        if a == "long-aligned" and c >= piv:
            return "bullish", "v4.0 long-aligned (SHA green, EMA9>EMA22) and prior close above pivot"
        if a == "short-aligned" and c <= piv:
            return "bearish", "v4.0 short-aligned (SHA red, EMA9<EMA22) and prior close below pivot"
        return "neutral", f"v4.0 {a}; prior close {side} pivot"
    if c > piv and pos >= 60:
        return "bullish", "prior close above pivot and in the upper part of its range"
    if c < piv and pos <= 40:
        return "bearish", "prior close below pivot and in the lower part of its range"
    return "neutral", f"prior close {side} pivot, mid-range"


def events_for(underlying, as_of):
    out = []
    for e in load_config().get("events", []):
        if underlying not in e.get("underlyings", []):
            continue
        if e.get("date") == as_of.isoformat() or e.get("weekday") == as_of.strftime("%A"):
            out.append({k: e[k] for k in ("name", "time_ist", "date") if k in e})
    return out


def iv_history(as_of, underlying, chain):
    path = data_dir() / "iv_history.csv"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        rows = []
    iv = chain.get("atm_iv")
    if iv and chain.get("usable"):
        rows = [r for r in rows if not (r["date"] == as_of.isoformat() and r["underlying"] == underlying)]
        rows.append(dict(date=as_of.isoformat(), underlying=underlying, expiry=str(chain["expiry"]),
                         dte=chain["dte"], atm_iv=round(iv, 2)))
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["date", "underlying", "expiry", "dte", "atm_iv"])
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: (r["date"], r["underlying"])))
    hist = [float(r["atm_iv"]) for r in rows if r["underlying"] == underlying and r["date"] < as_of.isoformat()]
    pct = sum(h <= iv for h in hist) / len(hist) * 100 if iv and len(hist) >= 20 else None
    return dict(prior_days_stored=len(hist), atm_iv_percentile=pct,
                note=None if pct is not None else "IV percentile needs 20+ stored pre-market days")


def journal_context(as_of):
    files = [p for p in data_dir("facts").glob("*_journal.json") if p.name[:10] <= as_of.isoformat()]
    if not files:
        return dict(available=False, note="no journal facts yet -- run /journal")
    f = json.loads(max(files).read_text(encoding="utf-8"))

    def dte_now(e):
        return (date.fromisoformat(e["expiry"]) - as_of).days if e.get("expiry") else None

    return dict(
        available=True,
        journal_date=f["date"],
        open_positions=[dict(symbol=e["symbol"], open_qty=e["open_qty"], lots=e["lots"], avg_entry=e["avg_entry"],
                             dte_now=dte_now(e), strikes_otm_at_entry=e["strikes_otm"])
                        for e in f["open_positions"]],
        live_positions=f["today"].get("live_positions"),
        last_session_violations=[dict(rule=v["rule"], symbol=v["symbol"], detail=v["detail"])
                                 for v in f["today"]["violations"]],
        rolling_summary=f["rolling"]["summary"],
        rolling_violations_by_rule=f["rolling"]["violations_by_rule"],
        rolling_no_rule_break=f["rolling"]["violation_cost"]["_clean_episodes"],
        rolling_with_rule_break=f["rolling"]["violation_cost"]["_flagged_episodes"],
    )


def rules_reminder(cfg):
    r = cfg["rules"]
    return dict(r3_expiry_days=r["r3_expiry_days"], r4_premium_stop_pct=r["r4_premium_stop_pct"],
                r5_daily_loss_limit_inr=r["r5_daily_loss_limit_inr"],
                r6_max_positions_per_day=r["r6_max_positions_per_day"],
                r7_max_strikes_otm_by_instrument={u: c.get("r7_max_strikes_otm", r["r7_max_strikes_otm"])
                                                  for u, c in cfg["instruments"].items()})


def last_close(client, ref, as_of):
    """Last traded price before `as_of` for another contract (e.g. next month's future)."""
    if not ref:
        return None
    b = intraday_bars(client, ref["security_id"], ref["segment"], ref["instrument"],
                      as_of - timedelta(days=6), as_of, interval=5)
    b = b[b["time"].dt.date < as_of]
    return float(b["close"].iloc[-1]) if len(b) else None


def instrument_facts(client, u, as_of, as_of_dt, cfg):
    pcfg = cfg["premarket"]
    exps = instruments.option_expiries(u, as_of)
    if not exps:
        return dict(available=False, note="no listed option expiries")
    ref = instruments.reference_series(u, exps[0])
    bars = intraday_bars(client, ref["security_id"], ref["segment"], ref["instrument"],
                         as_of - timedelta(days=pcfg["history_days"]), as_of, interval=5)
    prior = bars[bars["time"].dt.date < as_of]
    und = levels.level_summary(bars, as_of)
    scfg = cfg.get("strategy", {}).get(u)
    strat = (signals.v40_state(prior, scfg) if scfg else
             dict(modelled=False, available=False,
                  note="BANKNIFTY v0.4 (EMA pullback + 15m ADX gate) is not modelled in Python yet"))

    ref_close = und["prev_day"]["close"] if und.get("available") else None
    chains = dict(nearest=options.chain_snapshot(client, u, exps[0], as_of_dt, pcfg, ref_close))
    chains["nearest"]["underlying_contract"] = ref["label"]
    if chains["nearest"].get("dte", 99) <= pcfg["include_next_expiry_if_dte_le"] and len(exps) > 1:
        nref = instruments.reference_series(u, exps[1])
        nclose = ref_close if nref and nref["security_id"] == ref["security_id"] else last_close(client, nref, as_of)
        chains["next"] = options.chain_snapshot(client, u, exps[1], as_of_dt, pcfg, nclose)
        chains["next"]["underlying_contract"] = nref["label"] if nref else None

    for ch in chains.values():
        rv = und.get("rv20_pct")
        if ch.get("atm_iv") and ch.get("usable") and rv:
            ch["iv_rv_ratio"] = ch["atm_iv"] / rv
            ch["iv_vs_rv"] = ("rich" if ch["iv_rv_ratio"] > pcfg["iv_rich_ratio"]
                              else "cheap" if ch["iv_rv_ratio"] < pcfg["iv_cheap_ratio"] else "fair")

    near = chains["nearest"]
    if strat.get("available") and near.get("usable"):
        for side, right in (("long", "ce"), ("short", "pe")):
            leg = near["atm"][right]
            d = abs(leg["delta"]) if leg and leg.get("delta") else None
            hyp = strat["if_flip_now"][side]
            hyp["option_for_buyer"] = right.upper()
            hyp["approx_premium_risk_pts"] = hyp["risk_pts"] * d if d else None
            hyp["approx_premium_reward_pts"] = hyp["reward_pts"] * d if d else None

    bias, why = rule_bias(und, strat)
    return dict(
        available=True,
        reference=dict(label=ref["label"], security_id=ref["security_id"], expiry=ref["expiry"]),
        lot_size=instruments.lot_size(u),
        underlying=und,
        strategy=strat,
        options=chains,
        iv_history=iv_history(as_of, u, near),
        events=events_for(u, as_of),
        rule_bias=bias,
        rule_bias_reason=why,
    )


def build(client, as_of, only=None):
    cfg = load_config()
    now = datetime.now()
    as_of_dt = now if as_of == now.date() else datetime.combine(as_of, time(8, 30))
    per = {}
    for u in cfg["instruments"]:
        if only and u not in only:
            continue
        try:
            per[u] = instrument_facts(client, u, as_of, as_of_dt, cfg)
        except Exception as e:                                  # one bad feed shouldn't sink the brief
            traceback.print_exc()
            per[u] = dict(available=False, note=f"error building facts: {e}")
    facts = dict(
        kind="premarket",
        date=as_of,
        weekday=as_of.strftime("%A"),
        generated_at=now.replace(microsecond=0),
        instruments=per,
        context=dict(journal=journal_context(as_of), forward_test=cfg.get("forward_test", {}),
                     rules=rules_reminder(cfg)),
        caveats=[
            "Levels, ATR and realised vol are built from 5m bars of the futures contract underlying the "
            "nearest option expiry (the BANKNIFTY index for BANKNIFTY); around rollover these differ from "
            "TradingView's continuous contract.",
            "Prev-day close is the last traded price of the session. MCX's official daily close is a "
            "settlement price and can differ (up to 66 pts on crude in Aug-Sep 2026); highs and lows match "
            "Dhan's daily bars exactly.",
            "v4.0 state is a Python port of the Pine strategy on Dhan bars -- approximate; the simulated "
            "position is indicative only. BANKNIFTY v0.4 is not modelled.",
            "Option-chain values before the open reflect the previous session. Theta is per calendar day "
            "(Dhan greeks); b76_* fields are a local Black-76 cross-check.",
            "Chains failing the quality gates are marked usable=false; their premiums/IVs must not be quoted.",
        ],
    )
    return rounded(facts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--only", help="comma-separated underlyings, e.g. CRUDEOIL,BANKNIFTY")
    args = ap.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None

    facts = build(get_dhan_client(), args.date, only)
    path = data_dir("facts") / f"{args.date}_premarket.json"
    path.write_text(json.dumps(facts, indent=2), encoding="utf-8")
    print(f"premarket facts -> {path}")
    for u, f in facts["instruments"].items():
        if not f.get("available"):
            print(f"  {u}: unavailable ({f.get('note')})")
            continue
        near = f["options"]["nearest"]
        s = f["strategy"]
        print(f"  {u}: close {f['underlying'].get('prev_day', {}).get('close')} | ATR {f['underlying'].get('atr_regime')} "
              f"| v4.0 {s.get('alignment', 'n/a')} | options {'usable' if near.get('usable') else 'UNUSABLE ' + str(near.get('flags'))} "
              f"| rule bias {f['rule_bias']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
