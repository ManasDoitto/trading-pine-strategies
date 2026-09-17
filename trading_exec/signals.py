"""Normalised entry signals and their append-only store (exec_data/signals.jsonl).

A signal is identified by (strategy, instrument, side, bar_time), so the same bar can never
produce two records no matter how often the poller runs or how often the process restarts.

`instrument` is what gets traded (its options are bought); `signal_instrument` is the contract the
strategy ran on. They differ for silver: the signal is computed on SILVER, the option is SILVERM.
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from .config import data_dir

STORE = "signals.jsonl"


@dataclass
class Signal:
    strategy: str
    instrument: str           # traded underlying (whose options are bought)
    side: str                 # LONG or SHORT
    bar_time: str             # ISO time of the signal bar (the bar that closed)
    entry_hint: float         # the strategy's entry estimate (signal-bar close), in signal-series points
    sl: float                 # stop, in signal-series points
    target: float             # target, in signal-series points
    risk_pts: float
    rr: float
    source: str = "python"
    received_at: str = field(default_factory=lambda: datetime.now().replace(microsecond=0).isoformat())
    status: str = "NEW"
    note: str = ""
    signal_instrument: str = ""       # contract the strategy ran on; "" means the same as `instrument`
    signal_security_id: str = ""
    signal_segment: str = ""
    signal_series_type: str = ""      # FUTCOM or INDEX
    signal_label: str = ""            # e.g. SILVER-04Dec2026-FUT
    kind: str = "entry"               # "entry", or "armed" (a v0.4 stop entry armed, not yet triggered)
    flat_at: str = ""                 # HH:MM a same-day strategy force-closes (BankNifty v0.4: 15:20)

    @property
    def key(self):
        base = f"{self.strategy}|{self.instrument}|{self.side}|{self.bar_time}"
        return base if self.kind == "entry" else f"{base}|{self.kind}"

    @property
    def option_right(self):
        """What an option BUYER uses to express this direction."""
        return "CE" if self.side == "LONG" else "PE"

    def age_minutes(self, now=None):
        return ((now or datetime.now()) - datetime.fromisoformat(self.bar_time)).total_seconds() / 60

    def to_dict(self):
        d = asdict(self)
        d["key"] = self.key
        return d


def path():
    return data_dir() / STORE


def append(sig):
    with open(path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(sig.to_dict()) + "\n")
    return sig


def load_all():
    p = path()
    if not p.exists():
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                row.pop("key", None)
                out.append(Signal(**row))
    return out


def known_keys():
    return {s.key for s in load_all()}


def on_date(signals, day):
    day = day.isoformat() if isinstance(day, date) else str(day)
    return [s for s in signals if s.bar_time[:10] == day]
