"""Shadow trades: what a signal would have bought, at real option prices, tracked to its exit.

This is the measurement that decides whether the strategies survive as option buys. Nothing here
places an order; it only ever holds a read-only client.

Rules, chosen to be pessimistic rather than flattering:
- entry at the ASK (a buyer crosses the spread), exit at the bar's close, plus a configured
  per-lot cost on both legs
- exits follow the strategy's UNDERLYING stop/target, exactly as the Pine does. If both are
  touched in the same bar, the stop is assumed first
- a 30% premium stop (the journal's R4 rule) is tracked in parallel as a comparison, never as the
  real exit, so the month-end report can say which exit style would have served better
"""
import json
from datetime import date, datetime, timedelta

from trading_agents.core import instruments
from trading_agents.core.market_data import intraday_bars

from .config import data_dir, load_config

STORE = "shadow_trades.json"


def path():
    return data_dir() / STORE


def load():
    p = path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save(trades):
    path().write_text(json.dumps(trades, indent=1, default=str), encoding="utf-8")


def open_trades(trades=None):
    return [t for t in (trades if trades is not None else load()) if t["status"] == "OPEN"]


def realised_today_inr(day=None, trades=None):
    """Only real shadow trades count against the daily loss limit; observational ones never do."""
    day = (day or date.today()).isoformat()
    return sum(t.get("net_inr") or 0 for t in (trades if trades is not None else load())
               if t["status"] == "CLOSED" and not t.get("observational")
               and str(t.get("exit_at", ""))[:10] == day)


def open_trade(signal, atm, premium_targets, now=None, observational=False):
    """Record the entry a live system would have made.

    observational=True means the guards refused it (today: below the DTE floor) and it is tracked
    only to measure what the refusal cost or saved. It never counts towards the verdict."""
    now = now or datetime.now()
    cfg = load_config()["shadow"]
    qty = atm["qty_units"]
    entry = atm["entry_premium"]
    costs = cfg["cost_per_lot_inr"] * atm["lots"] * 2          # both legs, charged up front
    return dict(
        id=f"{signal.instrument}-{signal.bar_time}-{signal.side}" + ("-obs" if observational else ""),
        observational=observational,
        signal_key=signal.key, strategy=signal.strategy, instrument=signal.instrument,
        side=signal.side, right=signal.right if hasattr(signal, "right") else signal.option_right,
        symbol=atm["symbol"], security_id=atm["security_id"], segment=atm["segment"],
        instrument_type=atm["instrument_type"], strike=atm["strike"],
        expiry=str(atm["expiry"]), dte_at_entry=atm["dte"],
        opened_at=now.replace(microsecond=0).isoformat(), bar_time=signal.bar_time,
        underlying_entry=atm.get("underlying_price"), sl=signal.sl, target=signal.target,
        signal_instrument=getattr(signal, "signal_instrument", "") or signal.instrument,
        signal_security_id=getattr(signal, "signal_security_id", ""),
        signal_segment=getattr(signal, "signal_segment", ""),
        signal_series_type=getattr(signal, "signal_series_type", ""),
        signal_label=getattr(signal, "signal_label", ""),
        signal_entry=signal.entry_hint,
        flat_at=getattr(signal, "flat_at", ""),
        risk_pts=signal.risk_pts, rr=signal.rr,
        lots=atm["lots"], qty_units=qty,
        entry_premium=entry, entry_bid=atm.get("bid"), entry_ask=atm.get("ask"),
        entry_iv=atm.get("iv"), entry_delta=atm.get("delta"), entry_theta=atm.get("theta"),
        entry_spread_pct=atm.get("spread_pct"),
        approx_sl_premium=premium_targets.get("approx_sl_premium"),
        approx_target_premium=premium_targets.get("approx_target_premium"),
        cost_inr=round(entry * qty, 2), costs_inr=round(costs, 2),
        status="OPEN", exit_at=None, exit_reason=None, underlying_exit=None, exit_premium=None,
        premium_high=None, premium_low=None, net_inr=None, pct=None,
        premium_stop_hit_at=None, premium_stop_premium=None, premium_stop_net_inr=None,
    )


def _underlying_bars(client, trade, now):
    """Exits track the SAME series the signal was computed on, since the stop and target are in its
    points: the SILVER future for a SILVERM option, the front-month crude future through rollover."""
    start = datetime.fromisoformat(trade["bar_time"]).date()
    if trade.get("signal_security_id"):
        sid, seg, kind = trade["signal_security_id"], trade["signal_segment"], trade["signal_series_type"]
    else:                                   # records from before signal series were stored
        ref = instruments.reference_series(trade["instrument"], date.fromisoformat(trade["expiry"]))
        if ref is None:
            return None
        sid, seg, kind = ref["security_id"], ref["segment"], ref["instrument"]
    bars = intraday_bars(client, sid, seg, kind, start, now.date(), interval=5)
    return bars[bars["time"] > datetime.fromisoformat(trade["bar_time"])]


def _option_bars(client, trade, now):
    start = datetime.fromisoformat(trade["bar_time"]).date()
    bars = intraday_bars(client, trade["security_id"], trade["segment"], trade["instrument_type"],
                         start, now.date(), interval=5)
    return bars[bars["time"] >= datetime.fromisoformat(trade["bar_time"])]


def _exit_scan(trade, ubars):
    """First underlying touch of stop or target after entry. Stop wins a tie, as in simulate().
    A strategy with a same-day force-flat (BankNifty v0.4, flat_at 15:20) exits at that bar's open."""
    is_long = trade["side"] == "LONG"
    flat_at = None
    if trade.get("flat_at"):
        hh, mm = trade["flat_at"].split(":")
        flat_at = datetime.min.replace(hour=int(hh), minute=int(mm)).time()
    for r in ubars.to_dict("records"):
        if flat_at is not None and r["time"].time() >= flat_at:
            return r["time"], float(r["open"]), "EOD"
        hit_sl = r["low"] <= trade["sl"] if is_long else r["high"] >= trade["sl"]
        hit_tp = r["high"] >= trade["target"] if is_long else r["low"] <= trade["target"]
        if hit_sl or hit_tp:
            return r["time"], (trade["sl"] if hit_sl else trade["target"]), ("SL" if hit_sl else "TARGET")
    return None, None, None


def mark(client, trade, now=None):
    """Update one open trade's premium path and close it if the underlying hit stop or target."""
    now = now or datetime.now()
    obars = _option_bars(client, trade, now)
    if not obars.empty:
        trade["premium_high"] = float(obars["high"].max())
        trade["premium_low"] = float(obars["low"].min())
        trade["last_premium"] = float(obars["close"].iloc[-1])
        trade["max_favourable_pts"] = round(trade["premium_high"] - trade["entry_premium"], 2)
        trade["max_adverse_pts"] = round(trade["premium_low"] - trade["entry_premium"], 2)

        stop_level = trade["entry_premium"] * (1 - load_config()["shadow"]["premium_stop_pct"] / 100)
        if trade["premium_stop_hit_at"] is None:
            hit = obars[obars["low"] <= stop_level]
            if not hit.empty:
                row = hit.iloc[0]
                trade["premium_stop_hit_at"] = row["time"].to_pydatetime().isoformat()
                trade["premium_stop_premium"] = round(stop_level, 2)
                trade["premium_stop_net_inr"] = round((stop_level - trade["entry_premium"]) * trade["qty_units"]
                                                      - trade["costs_inr"], 2)

    ubars = _underlying_bars(client, trade, now)
    if ubars is not None and not ubars.empty:
        t, level, reason = _exit_scan(trade, ubars)
        if t is not None:
            at_exit = obars[obars["time"] <= t] if not obars.empty else obars
            exit_premium = float(at_exit["close"].iloc[-1]) if len(at_exit) else trade.get("last_premium")
            if reason == "EOD" and len(at_exit) and at_exit["time"].iloc[-1] == t:
                exit_premium = float(at_exit["open"].iloc[-1])          # the force-flat fills at the open
            _close(trade, t, level, reason, exit_premium)
            return trade

    if date.fromisoformat(trade["expiry"]) <= now.date():
        exit_premium = trade.get("last_premium") or 0.0
        _close(trade, now, trade.get("underlying_exit"), "EXPIRY", exit_premium)
    return trade


def _close(trade, when, underlying_level, reason, exit_premium):
    when = when.to_pydatetime() if hasattr(when, "to_pydatetime") else when
    trade["status"] = "CLOSED"
    trade["exit_at"] = when.replace(microsecond=0).isoformat()
    trade["exit_reason"] = reason
    trade["underlying_exit"] = underlying_level
    trade["exit_premium"] = round(exit_premium, 2) if exit_premium is not None else None
    if exit_premium is not None:
        gross = (exit_premium - trade["entry_premium"]) * trade["qty_units"]
        trade["gross_inr"] = round(gross, 2)
        trade["net_inr"] = round(gross - trade["costs_inr"], 2)
        trade["pct"] = round((exit_premium / trade["entry_premium"] - 1) * 100, 2) if trade["entry_premium"] else None
        trade["hold_min"] = round((datetime.fromisoformat(trade["exit_at"])
                                   - datetime.fromisoformat(trade["opened_at"])).total_seconds() / 60, 1)
    return trade


def mark_all(client, now=None):
    """Mark every open trade. Returns (all_trades, newly_closed)."""
    trades = load()
    closed = []
    for t in trades:
        if t["status"] != "OPEN":
            continue
        before = t["status"]
        mark(client, t, now)
        if t["status"] == "CLOSED" and before == "OPEN":
            closed.append(t)
    save(trades)
    return trades, closed


def record(trade):
    trades = load()
    if any(t["id"] == trade["id"] for t in trades):
        return trades
    trades.append(trade)
    save(trades)
    return trades
