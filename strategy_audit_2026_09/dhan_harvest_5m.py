"""Harvest ~60 months of 5-minute BankNifty/Nifty INDEX history via Dhan's intraday_minute_data (90 days/request cap,
chunked backward from today until the API returns 0 bars). Confirmed floor: BankNifty ~2021-08-04, Nifty ~2021-06-01
or earlier (checked further back below). Saves research_data/bars/DHAN_BANKNIFTY_5m.csv / DHAN_NIFTY_5m.csv in the
same schema as the TradingView-harvested files (unix-seconds time, open/high/low/close/volume) so they plug directly
into research_sim.load()-compatible loaders.
"""
import sys, time as time_mod
from pathlib import Path
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trading_agents.core.dhan_client import get_dhan_client

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research_data" / "bars"
SECURITY = {"BANKNIFTY": "25", "NIFTY": "13"}


def pull(dhan, sec_id, frm, to):
    r = dhan.intraday_minute_data(security_id=sec_id, exchange_segment="IDX_I", instrument_type="INDEX",
                                   from_date=frm.isoformat(), to_date=to.isoformat(), interval=5)
    if isinstance(r, dict) and r.get("status") == "failure":
        return None, r.get("remarks")
    d = r.get("data", {}) if isinstance(r, dict) else {}
    n = len(d.get("open", []))
    if n == 0:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"]), None
    df = pd.DataFrame({"time": d["timestamp"], "open": d["open"], "high": d["high"],
                        "low": d["low"], "close": d["close"], "volume": d["volume"]})
    df["time"] = df["time"].astype("int64")
    return df, None


def harvest(name, floor_hint):
    dhan = get_dhan_client()
    sec_id = SECURITY[name]
    frames = []
    to = date.today()
    stalls = 0
    while True:
        frm = to - timedelta(days=89)
        df, err = pull(dhan, sec_id, frm, to)
        if err:
            print(f"  {frm}->{to}: FAIL {err}")
            break
        print(f"  {frm}->{to}: {len(df)} bars", flush=True)
        if len(df) == 0:
            stalls += 1
            if stalls >= 2 or frm < floor_hint:
                break
        else:
            stalls = 0
            frames.append(df)
        to = frm - timedelta(days=1)
        time_mod.sleep(0.4)
    if not frames:
        print(f"{name}: nothing fetched")
        return
    full = pd.concat(frames).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    path = OUT / f"DHAN_{name}_5m.csv"
    full.to_csv(path, index=False)
    t0 = pd.to_datetime(full.time.iat[0], unit="s") + pd.Timedelta(hours=5, minutes=30)
    t1 = pd.to_datetime(full.time.iat[-1], unit="s") + pd.Timedelta(hours=5, minutes=30)
    print(f"{name}: wrote {path.name}: {len(full):,} bars, {t0} -> {t1}")


if __name__ == "__main__":
    for name, floor_hint in [("BANKNIFTY", date(2021, 6, 1)), ("NIFTY", date(2021, 1, 1))]:
        print(f"=== {name} ===")
        harvest(name, floor_hint)
