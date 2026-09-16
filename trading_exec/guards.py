"""Pre-trade guards. Each returns a human-readable reason when it blocks.

In Stage A nothing can be ordered anyway, but the guards still run, so the shadow record shows
exactly which signals a live system would have refused, and Stage C inherits a tested stack.
"""
from datetime import datetime, time, timedelta

from trading_agents.core.config import load_config as agents_config

from .config import instrument_cfg, load_config


def session_window(instrument):
    start, end = agents_config()["instruments"][instrument]["session"]
    return _to_time(start), _to_time(end)


def _to_time(hhmm):
    hh, mm = hhmm.split(":")
    return time(int(hh), int(mm))


def check(signal, atm, ctx):
    """ctx: dict(now, signals_today, open_positions, realised_today_inr).

    Returns a list of blocking reasons; an empty list means clear.
    """
    cfg = load_config()
    g = cfg["guards"]
    icfg = instrument_cfg(signal.instrument)
    now = ctx.get("now") or datetime.now()
    blocks = []

    if not icfg.get("enabled"):
        blocks.append(f"{signal.instrument} is disabled in config")

    start, end = session_window(signal.instrument)
    cutoff = (datetime.combine(now.date(), end) - timedelta(minutes=g["session_buffer_minutes"])).time()
    if not start <= now.time() <= cutoff:
        blocks.append(f"outside the entry window {start.strftime('%H:%M')}-{cutoff.strftime('%H:%M')}")

    age = signal.age_minutes(now)
    if age > cfg["source"]["stale_signal_minutes"]:
        blocks.append(f"signal bar is {age:.0f} min old (stale)")

    if atm is not None and not atm.get("usable"):
        blocks += list(atm.get("reasons") or ["ATM option not usable"])

    todays = ctx.get("signals_today") or []
    if len(todays) >= g["max_signals_per_day"]:
        blocks.append(f"already {len(todays)} signals today (max {g['max_signals_per_day']})")

    openpos = ctx.get("open_positions") or []
    if len(openpos) >= g["max_open_positions"]:
        blocks.append(f"{len(openpos)} positions already open (max {g['max_open_positions']})")

    realised = ctx.get("realised_today_inr") or 0.0
    if realised <= -g["daily_loss_limit_inr"]:
        blocks.append(f"daily loss limit hit: {realised:,.0f} against a -{g['daily_loss_limit_inr']:,} cap")

    return blocks
