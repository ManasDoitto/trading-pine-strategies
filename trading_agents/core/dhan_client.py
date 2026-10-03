"""Read-only Dhan client.

Wraps dhanhq and exposes ONLY allowlisted data/report methods. Order placement,
modification, cancellation, kill-switch, position conversion etc. are
unreachable through this object by construction.
"""
import json
import os
import time

from .config import REPO_ROOT

READ_METHODS = frozenset({
    "get_trade_book", "get_trade_history", "get_positions", "get_holdings", "get_fund_limits",
    "get_order_list", "get_order_by_id", "get_super_order_list", "get_forever",
    "intraday_minute_data", "historical_daily_data",
    "option_chain", "expiry_list",
    "ticker_data", "ohlc_data", "quote_data",
})

# Minimum seconds between consecutive calls in the same category (Dhan rate limits).
# ticker_data is 1/sec: below that it returns a payload with no data, which every caller reads as
# "no price" rather than as an error (verified 2026-09-17 - back-to-back calls dropped the quote).
#
# intraday_minute_data/historical_daily_data share a "data" bucket, not one each: 2026-09-29,
# runner.py (poll_seconds=60) and trade_watch.py (poll_seconds=20) each ran their OWN
# ReadOnlyDhan instance with its OWN in-memory _last_call dict, so each process individually
# respected a 0.25s gap while the two processes interleaved to blow well past Dhan's actual
# combined per-account limit (DH-904 "breaching rate limits", ~40 times in one session, starting
# hours before anything else was touched). Fix: the gap-tracking state now lives in a small file
# under a cross-process lock, so every process sharing this Dhan token -- however many are
# running -- waits on the same clock. See trading_agents/tests/test_core.py for the regression test.
_CATEGORY = {
    "intraday_minute_data": "data", "historical_daily_data": "data",
    "ticker_data": "quote", "ohlc_data": "quote", "quote_data": "quote",
    "option_chain": "chain", "expiry_list": "chain",
}
_MIN_GAP = {"data": 0.4, "quote": 1.1, "chain": 3.1}
_DEFAULT_GAP = 0.4

_STATE_PATH = REPO_ROOT / "exec_data" / ".dhan_rate_state.json"


def _file_lock(timeout=20.0):
    from filelock import FileLock
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(_STATE_PATH) + ".lock", timeout=timeout)


def wait_for_slot(category: str, min_gap: float | None = None) -> float:
    """Cross-process throttle: reserves the next allowed call time for `category` in the
    shared state file, then sleeps until it. Safe to call from any process/script that
    talks to Dhan (trading_exec, trading_agents, stockopt/, ad-hoc scripts) -- they all
    share one account-level rate limit. Returns the seconds actually slept."""
    gap = _MIN_GAP.get(category, _DEFAULT_GAP) if min_gap is None else min_gap
    with _file_lock():
        state = {}
        if _STATE_PATH.exists():
            try:
                state = json.loads(_STATE_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                state = {}
        now = time.time()
        last = state.get(category, 0.0)
        target = max(now, last + gap)
        state[category] = target
        _STATE_PATH.write_text(json.dumps(state))
    delay = target - now
    if delay > 0:
        time.sleep(delay)
    return max(delay, 0.0)


class ReadOnlyDhan:
    def __init__(self, raw):
        object.__setattr__(self, "_raw", raw)

    def __getattr__(self, name):
        if name not in READ_METHODS:
            raise AttributeError(f"'{name}' is not available: trading_agents is read-only")
        fn = getattr(self._raw, name)
        category = _CATEGORY.get(name, name)

        def throttled(*args, **kwargs):
            wait_for_slot(category)
            return fn(*args, **kwargs)

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
