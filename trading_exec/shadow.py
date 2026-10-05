"""Shadow trades: what a signal would have bought, at real option prices, tracked to its exit.

This is the measurement that decides whether the strategies survive as option buys. Nothing here
places an order; it only ever holds a read-only client.

Rules, chosen to be pessimistic rather than flattering:
- entry at the ASK (a buyer crosses the spread), exit at the bar's close, plus a configured
  per-lot cost on both legs
- exits are the strategy's own: it is rerun on its signal series and this trade's exit read off it
  (stop, target, time stop, flatten, daily lock, reversal). Only a trade the strategy no longer
  has falls back to a plain stop/target scan, where a bar touching both assumes the stop
- a 30% premium stop (the journal's R4 rule) is tracked in parallel as a comparison, never as the
  real exit, so the month-end report can say which exit style would have served better
"""
import json
import os
from datetime import date, datetime, timedelta

from trading_agents.core import instruments
from trading_agents.core import signals as v40
from trading_agents.core import signals_scalp as scalp
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


def sl_exits_today(instrument, day=None, trades=None, watches=None):
    """Count closed SL exits today for instrument (shadow trades + underlying watches).
    Used by the max_losses_day guard in runner.py."""
    day = (day or date.today()).isoformat()
    trades  = trades  if trades  is not None else load()
    watches = watches if watches is not None else load_watches()
    t_count = sum(1 for t in trades
                  if t.get("instrument") == instrument and t["status"] == "CLOSED"
                  and not t.get("observational")
                  and str(t.get("exit_at", ""))[:10] == day
                  and t.get("exit_reason") == "SL")
    w_count = sum(1 for w in watches
                  if w.get("instrument") == instrument and w["status"] == "CLOSED"
                  and str(w.get("exit_at", ""))[:10] == day
                  and w.get("exit_reason") == "SL")
    return t_count + w_count


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


STILL_OPEN = "OPEN"
# simulate()'s result names -> the exit_reason the shadow book and reports use
_REASONS = {"TP": "TARGET"}
# exits the strategy fills at the bar's OPEN: the clock (TIME/FLAT) is known at the open, and a
# reversal decided on the previous close fills there too. SL/TARGET/DAY LIMIT use the bar's close.
OPEN_FILL_EXITS = {"EOD", "TIME", "FLAT", "REV"}


def _strategy_exit_scan(client, trade, now):
    """Reruns the strategy that produced this trade over its own signal series and reads this
    trade's exit off it. The strategies have more exits than a stop and a target - the scalps' 45-min
    time stop and 15:20 flatten, v4.0's daily loss lock, v4.2's reversal - and copying those rules
    here drifted from the real thing (2026-09-30: a Nifty short sat "open" 7h after the NSE close).
    Same window as live (30 days before the signal, closed bars only), so it is the same simulation.

    Returns (exit_time, exit_level, reason), STILL_OPEN, or None when the strategy has no such trade
    (e.g. a v0.4 record, or a series that has since changed) - the caller then falls back to the
    plain stop/target scan."""
    strat = (agents_config().get("strategy", {}) or {}).get(trade.get("signal_instrument") or trade["instrument"])
    engine = (strat or {}).get("engine", "v40")
    frames = {"v40": v40.v40_frame, "supertrend": scalp.supertrend_frame, "tenkan_kijun": scalp.tenkan_frame}
    sid, seg, kind = trade.get("signal_security_id"), trade.get("signal_segment"), trade.get("signal_series_type")
    if not strat or engine not in frames or not sid:
        return None
    bar_time = datetime.fromisoformat(trade["bar_time"])
    bars = intraday_bars(client, sid, seg, kind, bar_time.date() - timedelta(days=30), now.date(), interval=5)
    bars = bars[bars["time"] + timedelta(minutes=5) <= now] if not bars.empty else bars
    if bars.empty:
        return None
    df = frames[engine](bars, strat)
    sim_trades, pos, _pending = (v40.simulate(df, strat) if engine == "v40" else scalp.simulate_scalp(df, strat))
    for t in sim_trades:
        if t["signal_time"] == bar_time and t["side"] == trade["side"]:
            return t["exit_time"], float(t["exit"]), _REASONS.get(t["result"], t["result"])
    if pos and pos["signal_time"] == bar_time and pos["side"] == trade["side"]:
        return STILL_OPEN
    return None


def _exit(client, trade, ubars, now):
    """(time, level, reason) of this trade's exit, or (None, None, None) while it is still open."""
    res = _strategy_exit_scan(client, trade, now)
    if res == STILL_OPEN:
        return None, None, None
    return res if res is not None else _exit_scan(trade, ubars)


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
        t, level, reason = _exit(client, trade, ubars, now)
        if t is not None:
            at_exit = obars[obars["time"] <= t] if not obars.empty else obars
            exit_premium = float(at_exit["close"].iloc[-1]) if len(at_exit) else trade.get("last_premium")
            if reason in OPEN_FILL_EXITS and len(at_exit) and at_exit["time"].iloc[-1] == t:
                exit_premium = float(at_exit["open"].iloc[-1])          # these exits fill at the bar's open
            _close(trade, t, level, reason, exit_premium)
            return trade

    # The signal future expired under this trade (CRUDEOIL-21Sep2026-FUT signal on its own expiry
    # day): no more bars can ever reach its stop/target, so it would hold a position slot forever.
    # Seen when the option keeps trading on 2+ later days the signal series has no bars for.
    if ubars is not None and not obars.empty and str(trade.get("signal_series_type", "")).startswith("FUT"):
        last_u = ubars["time"].iloc[-1] if not ubars.empty else datetime.fromisoformat(trade["bar_time"])
        later_days = {d for d in obars["time"].dt.date if d > last_u.date()}
        if len(later_days) >= 2:
            at_exit = obars[obars["time"] <= last_u]
            exit_premium = float(at_exit["close"].iloc[-1]) if len(at_exit) else trade.get("last_premium")
            _close(trade, last_u, None, "SIGNAL_SERIES_EXPIRED", exit_premium)
            return trade

    if now >= expiry_close(trade):
        exit_premium = trade.get("last_premium") or 0.0
        _close(trade, min(now, expiry_close(trade)), trade.get("underlying_exit"), "EXPIRY", exit_premium)
    return trade


def expiry_close(trade):
    """The option stops trading at its market's close on expiry day, not at midnight before it: an
    expiry-day (DTE 0) observational trade must live through the session, not close as it opens."""
    session = agents_config()["instruments"].get(trade["instrument"], {}).get("session", ["09:00", "23:30"])
    hh, mm = (int(x) for x in session[1].split(":"))
    return datetime.combine(date.fromisoformat(trade["expiry"]), datetime.min.time()).replace(hour=hh, minute=mm)


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
    t, level, reason = _exit(client, watch, bars, now)
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
