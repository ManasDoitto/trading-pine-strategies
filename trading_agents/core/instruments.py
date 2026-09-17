"""Resolve option and reference-futures contracts from the Dhan scrip master.

Same source as the repo-root dhan_expired_options.py; cached once per day under
journal_data/cache/. Expiries are never hardcoded.

The in-memory cache is date-stamped (not just "loaded once"): a long-lived process that crosses
midnight must not keep trading against yesterday's expiry list. Under the old process-forever cache,
a normal-looking [shadow entry] alert could quietly name an already-expired contract.

The download is defended against a hung connection and a truncated response: a stall used to block
the whole poll loop forever with no exception, and a short-but-valid partial CSV would get cached and
trusted all day - which shows up as "ATM option not usable" on a perfectly liquid chain, not as an
obvious data error.
"""
import time
from collections import Counter
from datetime import date

import pandas as pd
import requests

from .config import data_dir, load_config

SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
MIN_ROWS = 100_000                       # the real file is ~207k rows; anything far short is a truncation
REQUIRED_EXCHANGES = {"MCX", "NSE"}
DOWNLOAD_ATTEMPTS = 3

_cache = None
_cache_date = None


def _download(url, dest_tmp):
    """Fetch the scrip master to a temp file with a timeout and a few retries, and refuse to cache
    anything that looks truncated. Only os.replace()s the real cache file once this passes."""
    last_err = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            with requests.get(url, timeout=(10, 120), stream=True) as r:
                r.raise_for_status()
                with open(dest_tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            df = pd.read_csv(dest_tmp, low_memory=False)
            if len(df) < MIN_ROWS or not REQUIRED_EXCHANGES <= set(df["SEM_EXM_EXCH_ID"].unique()):
                raise ValueError(f"scrip master looks truncated: {len(df)} rows, "
                                 f"exchanges {sorted(df['SEM_EXM_EXCH_ID'].unique())}")
            return df
        except Exception as e:
            last_err = e
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"scrip master download failed after {DOWNLOAD_ATTEMPTS} attempts: {last_err}")


def load_scrip_master(refresh=False):
    global _cache, _cache_date
    today = date.today()
    if _cache is not None and _cache_date == today and not refresh:
        return _cache
    cache_dir = data_dir("cache")
    path = cache_dir / f"scrip_master_{today:%Y%m%d}.csv"
    if path.exists() and not refresh:
        df = pd.read_csv(path, low_memory=False)
    else:
        tmp = path.with_suffix(path.suffix + ".tmp")
        df = _download(SCRIP_MASTER_URL, tmp)
        tmp.replace(path)                # atomic: a reader never sees a half-written cache file
        for old in cache_dir.glob("scrip_master_*.csv"):
            if old != path:
                old.unlink()
    df["_expiry"] = pd.to_datetime(df["SEM_EXPIRY_DATE"], errors="coerce").dt.date
    _cache, _cache_date = df, today
    return df


def instrument_cfg(underlying):
    return load_config()["instruments"][underlying]


def _rows(underlying, instrument_name):
    cfg = instrument_cfg(underlying)
    exch = "NSE" if cfg["option_segment"].startswith("NSE") else "MCX"
    sm = load_scrip_master()
    ts = sm["SEM_TRADING_SYMBOL"].astype(str)
    return sm[(sm.SEM_EXM_EXCH_ID == exch) & (sm.SEM_INSTRUMENT_NAME == instrument_name)
              & ts.str.startswith(underlying + "-")]


def option_rows(underlying):
    return _rows(underlying, instrument_cfg(underlying)["option_instrument"])


def option_expiries(underlying, on_or_after=None):
    ref = on_or_after or date.today()
    return sorted(e for e in option_rows(underlying)["_expiry"].dropna().unique() if e >= ref)


def strike_step(underlying, expiry=None):
    rows = option_rows(underlying)
    if expiry is None:
        exps = option_expiries(underlying)
        expiry = exps[0] if exps else None
    if expiry is not None:
        rows = rows[rows["_expiry"] == expiry]
    strikes = sorted(set(rows["SEM_STRIKE_PRICE"].dropna().astype(float)))
    diffs = [round(b - a, 4) for a, b in zip(strikes, strikes[1:]) if b > a]
    return Counter(diffs).most_common(1)[0][0] if diffs else None


def lot_size(underlying):
    cfg = instrument_cfg(underlying)
    if "lot_size" in cfg:
        return cfg["lot_size"]
    rows = option_rows(underlying)
    return float(rows["SEM_LOT_UNITS"].iloc[0]) if len(rows) else None


def underlying_future(underlying, option_expiry=None):
    """First listed future expiring on/after the option expiry (MCX options are on futures).
    Returns None if the matching future is no longer listed (expired)."""
    fut = _rows(underlying, "FUTCOM").dropna(subset=["_expiry"]).sort_values("_expiry")
    ref = option_expiry or date.today()
    fut = fut[fut["_expiry"] >= ref]
    if fut.empty:
        return None
    r = fut.iloc[0]
    return dict(security_id=str(int(r.SEM_SMST_SECURITY_ID)), segment="MCX_COMM", instrument="FUTCOM",
                expiry=r["_expiry"], label=r.SEM_TRADING_SYMBOL)


def front_future(underlying, as_of=None):
    """The front-month future a continuous chart shows (CRUDEOIL1!, SILVER1!, BANKNIFTY1!).
    MCX futures are FUTCOM; NSE index futures are FUTIDX. It rolls on the day after expiry.
    `as_of` picks the contract that was front month on a past date (for a session-close review)."""
    nse = instrument_cfg(underlying)["option_segment"].startswith("NSE")
    kind, segment = ("FUTIDX", "NSE_FNO") if nse else ("FUTCOM", "MCX_COMM")
    fut = _rows(underlying, kind).dropna(subset=["_expiry"]).sort_values("_expiry")
    fut = fut[fut["_expiry"] >= (as_of or date.today())]
    if fut.empty:
        return None
    r = fut.iloc[0]
    return dict(security_id=str(int(r.SEM_SMST_SECURITY_ID)), segment=segment, instrument=kind,
                expiry=r["_expiry"], label=r.SEM_TRADING_SYMBOL)


def reference_series(underlying, option_expiry=None):
    """The underlying price series used for levels / moneyness of an option."""
    cfg = instrument_cfg(underlying)
    if "underlying_security_id" in cfg:
        return dict(security_id=str(cfg["underlying_security_id"]), segment=cfg["underlying_segment"],
                    instrument=cfg["underlying_instrument"], expiry=None, label=f"{underlying} index")
    return underlying_future(underlying, option_expiry)


def option_contract(underlying, expiry, strike, right):
    rows = option_rows(underlying)
    rows = rows[(rows["_expiry"] == expiry) & (rows["SEM_STRIKE_PRICE"].astype(float) == float(strike))
                & (rows["SEM_OPTION_TYPE"] == right)]
    if rows.empty:
        return None
    r = rows.iloc[0]
    cfg = instrument_cfg(underlying)
    return dict(security_id=str(int(r.SEM_SMST_SECURITY_ID)), segment=cfg["option_segment"],
                instrument=cfg["option_instrument"], label=r.SEM_TRADING_SYMBOL)
