"""Resolve option and reference-futures contracts from the Dhan scrip master.

Same source as the repo-root dhan_expired_options.py; cached once per day under
journal_data/cache/. Expiries are never hardcoded.
"""
from collections import Counter
from datetime import date

import pandas as pd

from .config import data_dir, load_config

SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

_cache = None


def load_scrip_master(refresh=False):
    global _cache
    if _cache is not None and not refresh:
        return _cache
    cache_dir = data_dir("cache")
    path = cache_dir / f"scrip_master_{date.today():%Y%m%d}.csv"
    if path.exists() and not refresh:
        df = pd.read_csv(path, low_memory=False)
    else:
        df = pd.read_csv(SCRIP_MASTER_URL, low_memory=False)
        df.to_csv(path, index=False)
        for old in cache_dir.glob("scrip_master_*.csv"):
            if old != path:
                old.unlink()
    df["_expiry"] = pd.to_datetime(df["SEM_EXPIRY_DATE"], errors="coerce").dt.date
    _cache = df
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
