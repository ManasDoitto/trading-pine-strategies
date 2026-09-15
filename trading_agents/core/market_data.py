"""OHLC bars from Dhan, generalised from the repo-root fetch_mcx_historical_batches.py
(which was hardcoded to MCX FUTCOM). Timestamps are returned as naive IST."""
import bisect
from datetime import datetime, timedelta

import pandas as pd

IST_OFFSET = pd.Timedelta(hours=5, minutes=30)
COLS = ["open", "high", "low", "close", "volume"]


def _to_df(data):
    if not isinstance(data, dict) or not data.get("timestamp"):
        return pd.DataFrame(columns=["time"] + COLS)
    df = pd.DataFrame({"time": data["timestamp"], **{c: data.get(c, []) for c in COLS}})
    df["time"] = pd.to_datetime(df["time"], unit="s") + IST_OFFSET
    return df


def intraday_bars(client, security_id, segment, instrument, start, end, interval=5, batch_days=90):
    """start/end: date or datetime. Walks backwards in batch_days chunks."""
    start = start if isinstance(start, datetime) else datetime.combine(start, datetime.min.time())
    end = end if isinstance(end, datetime) else datetime.combine(end, datetime.min.time())
    frames, cur_end = [], end
    while cur_end >= start:
        cur_start = max(start, cur_end - timedelta(days=batch_days - 1))
        r = client.intraday_minute_data(security_id=str(security_id), exchange_segment=segment,
                                        instrument_type=instrument, from_date=f"{cur_start:%Y-%m-%d}",
                                        to_date=f"{cur_end + timedelta(days=1):%Y-%m-%d}", interval=interval)
        if isinstance(r, dict) and r.get("status") == "success":
            frames.append(_to_df(r.get("data")))
        cur_end = cur_start - timedelta(days=1)
    if not frames:
        return pd.DataFrame(columns=["time"] + COLS)
    df = pd.concat(frames, ignore_index=True).drop_duplicates("time")
    return df.sort_values("time").reset_index(drop=True)


def daily_bars(client, security_id, segment, instrument, start, end, expiry_code=0):
    r = client.historical_daily_data(security_id=str(security_id), exchange_segment=segment,
                                     instrument_type=instrument, from_date=f"{start:%Y-%m-%d}",
                                     to_date=f"{end + timedelta(days=1):%Y-%m-%d}", expiry_code=expiry_code)
    df = _to_df(r.get("data") if isinstance(r, dict) else None)
    df["date"] = df["time"].dt.date
    return df.reset_index(drop=True)


class PriceLookup:
    """Price of a bar series at a moment: the open of the bar containing t."""

    def __init__(self, bars, interval_minutes):
        self.times = list(bars["time"])
        self.opens = list(bars["open"])
        self.span = timedelta(minutes=interval_minutes)

    def at(self, t):
        i = bisect.bisect_right(self.times, t) - 1
        if i < 0 or t - self.times[i] >= self.span:
            return None
        return float(self.opens[i])
