"""Keeping the unattended checker honest about its own health.

- The Dhan access token lasts exactly 24 hours (verified 2026-09-17: issued 10:21, expires 10:21 the
  next day), so a token generated mid-morning dies mid-session the next day. Its expiry is read
  locally from the token itself (the JWT `exp` claim) - no API call, and the token is never printed.
- load_dotenv never overrides variables already in the process, so a token regenerated in .env during
  the day would be silently ignored by a running checker. fresh_client() reads the file each time.
- runner_state.json remembers whether the checker already started today, so a mid-day start is
  announced as a restart.
"""
import base64
import json
import os
from datetime import datetime, timedelta

from dotenv import dotenv_values

from .config import REPO_ROOT, data_dir

STATE = "runner_state.json"


def token_from_env_file():
    """DHAN_ACCESS_TOKEN as the .env file says right now (not as the process first loaded it)."""
    return (dotenv_values(REPO_ROOT / ".env").get("DHAN_ACCESS_TOKEN") or "").strip()


def token_expiry(token):
    """Local-time expiry from the token's own `exp` claim, or None if it isn't a readable JWT."""
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return datetime.fromtimestamp(int(json.loads(base64.urlsafe_b64decode(payload))["exp"]))
    except (ValueError, KeyError, TypeError):
        return None


def token_status(expiry, now, session_end=None):
    """expired | expires_within_hour | expires_before_close | ok | unknown."""
    if expiry is None:
        return "unknown"
    if expiry <= now:
        return "expired"
    if expiry - now <= timedelta(hours=1):
        return "expires_within_hour"
    if session_end is not None and expiry < datetime.combine(now.date(), session_end):
        return "expires_before_close"
    return "ok"


def fresh_client():
    """The read-only Dhan client built from what .env says NOW."""
    values = dotenv_values(REPO_ROOT / ".env")
    for key in ("DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN"):
        if values.get(key):
            os.environ[key] = values[key]
    from trading_agents.core.dhan_client import get_dhan_client
    return get_dhan_client()


def mark_started(day, state_dir=None):
    """Record a start; True if it is the first start of `day`, False if this is a restart."""
    path = (state_dir or data_dir()) / STATE
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    first = state.get("last_start_date") != day.isoformat()
    state.update(last_start_date=day.isoformat(), last_start_at=datetime.now().replace(microsecond=0).isoformat())
    path.write_text(json.dumps(state), encoding="utf-8")
    return first
