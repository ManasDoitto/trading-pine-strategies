"""Read-only Dhan client.

Wraps dhanhq and exposes ONLY allowlisted data/report methods. Order placement,
modification, cancellation, kill-switch, position conversion etc. are
unreachable through this object by construction.
"""
import os
import time

from .config import REPO_ROOT

READ_METHODS = frozenset({
    "get_trade_book", "get_trade_history", "get_positions", "get_holdings", "get_fund_limits",
    "intraday_minute_data", "historical_daily_data",
    "option_chain", "expiry_list",
    "ticker_data", "ohlc_data", "quote_data",
})

# Minimum seconds between consecutive calls of the same method (Dhan rate limits).
_MIN_GAP = {"option_chain": 3.1, "expiry_list": 3.1}
_DEFAULT_GAP = 0.25


class ReadOnlyDhan:
    def __init__(self, raw):
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_last_call", {})

    def __getattr__(self, name):
        if name not in READ_METHODS:
            raise AttributeError(f"'{name}' is not available: trading_agents is read-only")
        fn = getattr(self._raw, name)

        def throttled(*args, **kwargs):
            gap = _MIN_GAP.get(name, _DEFAULT_GAP)
            wait = self._last_call.get(name, 0) + gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                return fn(*args, **kwargs)
            finally:
                self._last_call[name] = time.monotonic()

        return throttled

    def __setattr__(self, name, value):
        raise AttributeError("ReadOnlyDhan is immutable")

    def __dir__(self):
        return sorted(READ_METHODS)


def get_dhan_client():
    from dotenv import load_dotenv
    from dhanhq import dhanhq, DhanContext

    load_dotenv(REPO_ROOT / ".env")
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    if not client_id or not access_token or client_id == "your_client_id_here":
        raise RuntimeError("DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set in .env")
    return ReadOnlyDhan(dhanhq(DhanContext(client_id, access_token)))
