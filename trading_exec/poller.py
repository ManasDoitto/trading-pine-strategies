"""The signal source: poll Dhan 5m bars and emit a Signal from the most recently CLOSED bar.

No TradingView involved. This runs the same v4.0 port the session-close reviews use
(trading_agents/core/signals.py), so signals here and in the journal agree by construction.
"""
from datetime import datetime, timedelta

from trading_agents.core import instruments
from trading_agents.core import signals as v40
from trading_agents.core.config import load_config as agents_config
from trading_agents.core.market_data import intraday_bars

from .config import enabled_instruments, load_config
from .signals import Signal, known_keys


def closed_bars(client, instrument, now, history_days, interval):
    """Bars whose candle has fully closed by `now`; the forming bar is dropped."""
    expiries = instruments.option_expiries(instrument, now.date())
    ref = instruments.reference_series(instrument, expiries[0] if expiries else None)
    if ref is None:
        return None, None
    bars = intraday_bars(client, ref["security_id"], ref["segment"], ref["instrument"],
                         now.date() - timedelta(days=history_days), now.date(), interval=interval)
    if bars.empty:
        return ref, bars
    closed = bars[bars["time"] + timedelta(minutes=interval) <= now]
    return ref, closed.reset_index(drop=True)


def signal_from_bars(bars, instrument, strategy_cfg):
    """A Signal if the last closed bar fired an entry, else None."""
    if len(bars) < v40.WARMUP_BARS + 50:
        return None
    df = v40.v40_frame(bars, strategy_cfg)
    last = df.iloc[-1]
    if not (last["ok_l"] or last["ok_s"]):
        return None
    side = "LONG" if last["ok_l"] else "SHORT"
    sign = 1 if side == "LONG" else -1
    risk = float(last["risk_l"] if side == "LONG" else last["risk_s"])
    close = float(last["close"])
    return Signal(
        strategy=strategy_cfg["name"],
        instrument=instrument,
        side=side,
        bar_time=last["time"].to_pydatetime().isoformat(),
        entry_hint=round(close, 2),
        sl=round(close - sign * risk, 2),
        target=round(close + sign * strategy_cfg["rr"] * risk, 2),
        risk_pts=round(risk, 2),
        rr=strategy_cfg["rr"],
    )


def poll_once(client, now=None, seen=None):
    """New, non-duplicate signals across the enabled instruments."""
    cfg = load_config()["source"]
    now = now or datetime.now()
    seen = known_keys() if seen is None else seen
    strategies = agents_config().get("strategy", {})
    out = []
    for instrument in enabled_instruments():
        strategy_cfg = strategies.get(instrument)
        if not strategy_cfg:
            continue
        _ref, bars = closed_bars(client, instrument, now, cfg["history_days"], cfg["interval_minutes"])
        if bars is None or bars.empty:
            continue
        sig = signal_from_bars(bars, instrument, strategy_cfg)
        if sig and sig.key not in seen:
            seen.add(sig.key)
            out.append(sig)
    return out
