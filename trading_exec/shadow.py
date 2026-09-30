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
import os
from datetime import date, datetime, timedelta

from trading_agents.core import instruments
from trading_agents.core import signals as v40
from trading_agents.core.config import load_config as agents_config
from trading_agents.core.market_data import intraday_bars

from .config import data_dir, load_config


def _atomic_write_json(path, obj):
    """write-temp-then-replace: an OOM kill or power loss mid-write can never truncate the real
    file. Without this, a crash mid-save leaves shadow.load() raising JSONDecodeError forever -
    tick_safely catches it, sends one [checker error], and the loop then goes quiet for the day."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


STORE = "shadow_trades.json"


def path():
    return data_dir() / STORE


def load():
    p = path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save(trades):
    _atomic_write_json(path(), trades)


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
    points: the front-month future through rollover, or a different contract entirely if the traded
    instrument's signal_from points elsewhere (no instrument currently does, as of 2026-09-18)."""
    start = datetime.fromisoformat(trade["bar_time"]).date()
    if trade.get("signal_security_id"):
        sid, seg, kind = trade["signal_security_id"], trade["signal_segment"], trade["signal_series_type"]
    elif trade.get("expiry"):               # records from before signal series were stored
        ref = instruments.reference_series(trade["instrument"], date.fromisoformat(trade["expiry"]))
        if ref is None:
            return None
        sid, seg, kind = ref["security_id"], ref["segment"], ref["instrument"]
    else:
        return None
    bars = intraday_bars(client, sid, seg, kind, start, now.date(), interval=5)
    return bars[bars["time"] > datetime.fromisoformat(trade["bar_time"])]


def _option_bars(client, trade, now):
    start = datetime.fromisoformat(trade["bar_time"]).date()
    bars = intraday_bars(client, trade["security_id"], trade["segment"], trade["instrument_type"],
                         start, now.date(), interval=5)
    return bars[bars["time"] >= datetime.fromisoformat(trade["bar_time"])]


def _exit_scan(trade, ubars):
    """First underlying touch of stop or target after entry. Stop wins a tie, as in simulate().
    A strategy with a same-day force-flat (BankNifty v0.4, flat_at 15:20) exits at that bar's open.

    trade["target"] is None for a reversal-exit strategy (Crude v4.2): there is no fixed target
    to scan for, so only the stop (and any force-flat) can close it here. The real reversal exit
    is a second, opposite-direction signal - not reproduced in this points-only scan, so a v4.2
    shadow trade that never hits its stop stays open longer than the live strategy actually would."""
    is_long = trade["side"] == "LONG"
    has_target = trade.get("target") is not None
    flat_at = None
    if trade.get("flat_at"):
        hh, mm = trade["flat_at"].split(":")
        flat_at = datetime.min.replace(hour=int(hh), minute=int(mm)).time()
    for r in ubars.to_dict("records"):
        if flat_at is not None and r["time"].time() >= flat_at:
            return r["time"], float(r["open"]), "EOD"
        hit_sl = r["low"] <= trade["sl"] if is_long else r["high"] >= trade["sl"]
        hit_tp = has_target and (r["high"] >= trade["target"] if is_long else r["low"] <= trade["target"])
        if hit_sl or hit_tp:
            return r["time"], (trade["sl"] if hit_sl else trade["target"]), ("SL" if hit_sl else "TARGET")
    return None, None, None


def _reversal_exit_scan(client, trade, now):
    """For a reversal_exit strategy (Crude v4.2): there is no fixed target to scan bars for, and the
    real exit - an opposite valid signal while in a position - can only be seen by rerunning the
    actual strategy, not by comparing the trade's own sl/target to price. This reruns production
    simulate() over a properly warmed-up window (WARMUP_BARS before entry, same as live) and reads
    this trade's own outcome off it: the only way to reproduce the reversal exit exactly."""
    strat = (agents_config().get("strategy", {}) or {}).get(trade.get("signal_instrument") or trade["instrument"])
    if not strat or not strat.get("reversal_exit"):
        return None
    sid, seg, kind = trade.get("signal_security_id"), trade.get("signal_segment"), trade.get("signal_series_type")
    if not sid:
        return None
    entry_date = datetime.fromisoformat(trade["bar_time"]).date()
    bars = intraday_bars(client, sid, seg, kind, entry_date - timedelta(days=30), now.date(), interval=5)
    if bars.empty:
        return None
    df = v40.v40_frame(bars, strat)
    sim_trades, _pos, _pending = v40.simulate(df, strat)
    bar_time = datetime.fromisoformat(trade["bar_time"])
    for t in sim_trades:
        if t["signal_time"] == bar_time and t["side"] == trade["side"]:
            return t["exit_time"], t["exit"], t["result"]
    return None


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
        rev = _reversal_exit_scan(client, trade, now) if trade.get("target") is None else None
        t, level, reason = rev if rev is not None else _exit_scan(trade, ubars)
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


# ---------------------------------------------------------------- blocked-signal watches
# A blocked signal buys nothing, so there is no premium to track - but the strategy still took the
# trade on the underlying, and the trader wants to know how it ended. A watch follows the same
# stop/target on the same series the signal was computed on, and is priced in POINTS only. Watches
# are kept apart from shadow trades so they can never reach the month-end verdict.
WATCH_STORE = "blocked_watch.json"
MAX_WATCH_DAYS = 10                      # a watch that never resolves is closed at the last price


def watch_path():
    return data_dir() / WATCH_STORE


def load_watches():
    p = watch_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_watches(watches):
    _atomic_write_json(watch_path(), watches)


def open_watches(watches=None):
    return [w for w in (watches if watches is not None else load_watches()) if w["status"] == "OPEN"]


def open_watch(signal, blocks, now=None):
    """Start following a blocked signal on the underlying."""
    now = now or datetime.now()
    return dict(
        id=f"{signal.instrument}-{signal.bar_time}-{signal.side}-watch",
        signal_key=signal.key, strategy=signal.strategy, instrument=signal.instrument,
        side=signal.side, bar_time=signal.bar_time,
        opened_at=now.replace(microsecond=0).isoformat(),
        blocked_by="; ".join(blocks),
        signal_entry=signal.entry_hint, entry_fill=None,
        sl=signal.sl, target=signal.target, risk_pts=signal.risk_pts, rr=signal.rr,
        signal_instrument=getattr(signal, "signal_instrument", "") or signal.instrument,
        signal_security_id=getattr(signal, "signal_security_id", ""),
        signal_segment=getattr(signal, "signal_segment", ""),
        signal_series_type=getattr(signal, "signal_series_type", ""),
        signal_label=getattr(signal, "signal_label", ""),
        flat_at=getattr(signal, "flat_at", ""),
        status="OPEN", exit_at=None, exit_level=None, exit_reason=None, pts=None, r_multiple=None,
    )


def record_watch(watch):
    watches = load_watches()
    if any(w["id"] == watch["id"] for w in watches):
        return watches
    watches.append(watch)
    save_watches(watches)
    return watches


def _close_watch(watch, when, level, reason):
    when = when.to_pydatetime() if hasattr(when, "to_pydatetime") else when
    watch["status"] = "CLOSED"
    watch["exit_at"] = when.replace(microsecond=0).isoformat()
    watch["exit_level"], watch["exit_reason"] = level, reason
    if watch.get("entry_fill") is not None and level is not None:
        sign = 1 if watch["side"] == "LONG" else -1
        watch["pts"] = round((level - watch["entry_fill"]) * sign, 2)
        watch["r_multiple"] = round(watch["pts"] / watch["risk_pts"], 2) if watch.get("risk_pts") else None
        watch["hold_min"] = round((datetime.fromisoformat(watch["exit_at"])
                                   - datetime.fromisoformat(watch["opened_at"])).total_seconds() / 60, 1)
    return watch


def mark_watch(client, watch, now=None):
    """Fill the watch at the bar after the signal, then close it on the first stop/target touch."""
    now = now or datetime.now()
    bars = _underlying_bars(client, watch, now)
    if bars is None or bars.empty:
        return watch
    if watch.get("entry_fill") is None:
        watch["entry_fill"] = float(bars["open"].iloc[0])     # the Pine fills at the next bar's open
    t, level, reason = _exit_scan(watch, bars)
    if t is not None:
        _close_watch(watch, t, level, reason)
    elif (now - datetime.fromisoformat(watch["opened_at"])).days >= MAX_WATCH_DAYS:
        last = bars.iloc[-1]
        _close_watch(watch, last["time"], float(last["close"]), "STALE")
    return watch


def mark_watches(client, now=None):
    """Mark every open watch. Returns (all_watches, newly_closed)."""
    watches = load_watches()
    closed = []
    for w in watches:
        if w["status"] != "OPEN":
            continue
        mark_watch(client, w, now)
        if w["status"] == "CLOSED":
            closed.append(w)
    save_watches(watches)
    return watches, closed
