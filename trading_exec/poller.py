"""The signal source: poll Dhan 5m bars and emit a Signal only when the strategy would actually ENTER.

Two things make these signals match the strategy on your chart rather than a raw pattern scan:

- Entries come from simulate(), so a signal fires only when the strategy is flat (the Pine's `flat`
  condition) and not locked out for the day (silver's 350-pt daily loss limit). Measured on
  2026-09-17 over 30 days of Dhan bars, a raw bar scan would have alerted far more often than the
  strategy trades: crude 45 vs 20, silver 96 vs 20, silver mini 91 vs 31.
- Bars come from the FRONT-MONTH future of the signal instrument - what a continuous chart
  (CRUDEOIL1!, SILVER1!) shows - not whichever future the nearest option expiry is written on,
  which diverges from the chart around rollover.

The signal instrument can differ from the traded one: silver signals are computed on SILVER, the
contract the strategy was tested on, and bought through SILVERM options, the liquid silver chain.
The two futures agreed on only 45% of signals over the same 30 days, so this matters.
"""
from datetime import datetime, timedelta

from trading_agents.core import instruments
from trading_agents.core import signals as v40
from trading_agents.core.config import load_config as agents_config
from trading_agents.core.market_data import intraday_bars

from .config import enabled_instruments, instrument_cfg, load_config
from .signals import Signal, known_keys


def signal_series(signal_instrument):
    """The series a continuous chart would show: the index, or the front-month future."""
    cfg = agents_config()["instruments"][signal_instrument]
    if "underlying_security_id" in cfg:
        return instruments.reference_series(signal_instrument)
    return instruments.underlying_future(signal_instrument)


def closed_bars(client, series, now, history_days, interval):
    """Bars whose candle has fully closed by `now`; the forming bar is dropped."""
    bars = intraday_bars(client, series["security_id"], series["segment"], series["instrument"],
                         now.date() - timedelta(days=history_days), now.date(), interval=interval)
    if bars.empty:
        return bars
    return bars[bars["time"] + timedelta(minutes=interval) <= now].reset_index(drop=True)


def entry_on_last_bar(df, strategy_cfg):
    """(pending_entry, last_close) if the strategy decided to enter on the most recent closed bar.

    simulate() leaves `pending` set only when that bar's signal arrived while flat and not
    day-locked; the Pine then fills it at the next bar's open. Anything else - no signal, a signal
    while already in a trade, or a signal after the daily lock - returns None."""
    if len(df) < v40.WARMUP_BARS + 50:
        return None
    _trades, _position, pending = v40.simulate(df, strategy_cfg)
    if not pending or pending["signal_time"] != df["time"].iat[-1]:
        return None
    return pending, float(df["close"].iat[-1])


def poll_once(client, now=None, seen=None):
    """New, non-duplicate entry signals across the enabled traded instruments."""
    cfg = load_config()["source"]
    now = now or datetime.now()
    seen = known_keys() if seen is None else seen
    strategies = agents_config().get("strategy", {})
    out = []
    for traded in enabled_instruments():
        source = instrument_cfg(traded).get("signal_from", traded)
        strategy_cfg = strategies.get(source)
        if not strategy_cfg:
            continue
        series = signal_series(source)
        if series is None:
            continue
        bars = closed_bars(client, series, now, cfg["history_days"], cfg["interval_minutes"])
        if bars.empty:
            continue
        hit = entry_on_last_bar(v40.v40_frame(bars, strategy_cfg), strategy_cfg)
        if not hit:
            continue
        pending, close = hit
        signal_time = pending["signal_time"]
        sig = Signal(
            strategy=strategy_cfg["name"], instrument=traded, side=pending["side"],
            bar_time=(signal_time.to_pydatetime() if hasattr(signal_time, "to_pydatetime") else signal_time).isoformat(),
            entry_hint=round(close, 2), sl=round(pending["sl"], 2), target=round(pending["tp"], 2),
            risk_pts=round(pending["risk_pts"], 2), rr=strategy_cfg["rr"],
            signal_instrument=source, signal_security_id=str(series["security_id"]),
            signal_segment=series["segment"], signal_series_type=series["instrument"],
            signal_label=series["label"],
        )
        if sig.key not in seen:
            seen.add(sig.key)
            out.append(sig)
    return out
