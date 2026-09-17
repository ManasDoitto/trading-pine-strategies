"""The signal source: poll Dhan 5m bars and emit Signals only for what the strategy would actually do.

Two strategy engines:

- v4.0 SHA flip (crude, silver). Entries come from simulate(), so a signal fires only when the strategy
  is flat and not day-locked. A raw bar scan would have alerted far more often than the strategy trades
  (measured over 30 days on 2026-09-17: crude 45 vs 20, silver 96 vs 20, silver mini 91 vs 31).

- v0.4 EMA pullback (BankNifty). A quality reclaim ARMS a stop order; the trade happens only if price
  then breaks the trigger before the order expires. So there are two signals:
    kind "armed" - the order was armed on the bar that just closed (a heads-up with the trigger)
    kind "entry" - the trigger was hit: on the bar that just closed, or already INTRABAR, found by
                   checking the future's live price against the armed trigger each poll
  It runs on the front-month FUTURE (NSE:BANKNIFTY1!) because its core filter needs volume and VWAP.

Bars come from the front-month future of the signal instrument - what a continuous chart shows. The
signal instrument can differ from the traded one: silver signals run on SILVER and are bought as SILVERM
options (the two futures agreed on only 45% of signals over 30 days).
"""
from datetime import datetime, timedelta

from trading_agents.core import instruments
from trading_agents.core import signals as v40
from trading_agents.core import signals_v04 as v04
from trading_agents.core.config import load_config as agents_config
from trading_agents.core.market_data import intraday_bars

from .config import enabled_instruments, instrument_cfg, load_config
from .signals import Signal, known_keys

BAR = timedelta(minutes=5)


def _iso(ts):
    return (ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts).isoformat()


def signal_series(signal_instrument, traded_cfg=None):
    """The series a continuous chart would show: the front-month future (or the index for an index
    strategy that needs no volume)."""
    if (traded_cfg or {}).get("signal_series") == "future":
        return instruments.front_future(signal_instrument)
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


# ---------------------------------------------------------------- v4.0
def entry_on_last_bar(df, strategy_cfg):
    """(pending_entry, last_close) if the v4.0 strategy decided to enter on the most recent closed bar.

    simulate() leaves `pending` set only when that bar's signal arrived while flat and not day-locked;
    the Pine then fills it at the next bar's open. Anything else returns None."""
    if len(df) < v40.WARMUP_BARS + 50:
        return None
    _trades, _position, pending = v40.simulate(df, strategy_cfg)
    if not pending or pending["signal_time"] != df["time"].iat[-1]:
        return None
    return pending, float(df["close"].iat[-1])


def v40_signals(traded, source, params, series, bars):
    hit = entry_on_last_bar(v40.v40_frame(bars, params), params)
    if not hit:
        return []
    pending, close = hit
    return [Signal(strategy=params["name"], instrument=traded, side=pending["side"],
                   bar_time=_iso(pending["signal_time"]), entry_hint=round(close, 2),
                   sl=round(pending["sl"], 2), target=round(pending["tp"], 2),
                   risk_pts=round(pending["risk_pts"], 2), rr=params["rr"], **_series_fields(source, series))]


# ---------------------------------------------------------------- v0.4
def _series_fields(source, series):
    return dict(signal_instrument=source, signal_security_id=str(series["security_id"]),
                signal_segment=series["segment"], signal_series_type=series["instrument"],
                signal_label=series["label"])


def series_ltp(client, series):
    try:
        r = client.ticker_data({series["segment"]: [int(series["security_id"])]})
        return float(r["data"]["data"][series["segment"]][str(series["security_id"])]["last_price"])
    except Exception:
        return None


def v04_signals(client, traded, source, params, series, bars):
    """Armed and entry signals for BankNifty v0.4 as of the last closed bar, plus an intrabar trigger check."""
    df = v04.v04_frame(bars, params)
    if len(df) < v04.WARMUP_BARS:
        return []
    sim = v04.simulate(df, params)
    last = len(df) - 1
    common = dict(strategy=params["name"], instrument=traded, rr=params["rr"],
                  flat_at=params.get("flat_exit_at", ""), **_series_fields(source, series))
    out = []
    for e in sim["events"]:
        if e["bar"] != last:
            continue
        levels = dict(side=e["side"], sl=round(e["sl"], 2), target=round(e["tp"], 2), risk_pts=round(e["risk_pts"], 2))
        if e["kind"] == "armed":
            until = e["arm_time"] + BAR * (params["reclaim_win"] + 2)
            out.append(Signal(kind="armed", bar_time=_iso(e["arm_time"]), entry_hint=round(e["trig"], 2),
                              note=f"order live until {until:%H:%M} unless the trend flips or 15:15 arrives",
                              **levels, **common))
        elif e["kind"] == "filled":
            out.append(Signal(kind="entry", bar_time=_iso(e["time"]), entry_hint=round(e["entry"], 2),
                              note=f"stop entry armed {e['arm_time']:%H:%M}", **levels, **common))

    if sim["position"] is None and not any(s.kind == "entry" for s in out):
        orders = [o for o in sim["live"].values() if o]
        ltp = series_ltp(client, series) if orders else None
        for o in orders:
            if ltp is None:
                break
            if (ltp >= o["trig"]) if o["side"] == "LONG" else (ltp <= o["trig"]):
                out.append(Signal(kind="entry", side=o["side"], bar_time=_iso(df["time"].iat[-1] + BAR),
                                  entry_hint=round(o["trig"], 2), sl=round(o["sl"], 2), target=round(o["tp"], 2),
                                  risk_pts=round(o["risk_pts"], 2),
                                  note=f"stop entry armed {o['arm_time']:%H:%M}; trigger crossed intrabar (LTP {ltp:,.2f})",
                                  **common))
    return out


# ---------------------------------------------------------------- poll
def poll_once(client, now=None, seen=None):
    """New, non-duplicate signals across the enabled traded instruments."""
    cfg = load_config()["source"]
    now = now or datetime.now()
    seen = known_keys() if seen is None else seen
    strategies = agents_config().get("strategy", {})
    out = []
    for traded in enabled_instruments():
        tcfg = instrument_cfg(traded)
        source = tcfg.get("signal_from", traded)
        params = strategies.get(source)
        if not params:
            continue
        series = signal_series(source, tcfg)
        if series is None:
            continue
        bars = closed_bars(client, series, now, cfg["history_days"], cfg["interval_minutes"])
        if bars.empty:
            continue
        if params.get("engine", "v40") == "v04":
            found = v04_signals(client, traded, source, params, series, bars)
        else:
            found = v40_signals(traded, source, params, series, bars)
        for sig in found:
            if sig.key not in seen:
                seen.add(sig.key)
                out.append(sig)
    return out
