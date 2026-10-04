"""Is the VM itself okay - separate from strategy_health, which asks if the STRATEGIES are okay.

Answered by /vmhealth (telegram_bot.py), reachable any time of day via telegram_daemon.py, unlike
every other bot command which only runs inside trading-watcher's 08:51-23:59 weekday window.
Read-only: lists systemd units and disk space, never restarts or changes anything.
"""
import shutil
import subprocess
from datetime import datetime

from .config import REPO_ROOT
from . import health


def _run(cmd):
    """A shell-out that can never take the health check down with it."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (out.stdout or out.stderr or "").strip()
    except Exception as e:
        return f"[could not run: {type(e).__name__}: {e}]"


def failed_units():
    out = _run(["systemctl", "--failed", "--no-pager", "--plain"])
    if out.startswith("[could not run"):
        return [out]
    return [l for l in out.splitlines() if l.strip() and not l.startswith(("UNIT", "0 loaded"))]


def next_timers():
    out = _run(["systemctl", "list-timers", "trading-*", "--no-pager", "--all"])
    if out.startswith("[could not run"):
        return [out]
    return [l for l in out.splitlines() if l.strip().startswith("trading-")
            or ("NEXT" in l and "LEFT" in l)]


def disk_free_pct():
    total, _, free = shutil.disk_usage(REPO_ROOT)
    return free / total * 100


def lines():
    """The /vmhealth digest: everything that could make the VM silently stop doing its job."""
    now = datetime.now()
    out = [f"{now:%a %d-%b %H:%M} IST"]

    clock_ok = health.clock_offset_ok(now)
    out.append("clock: OK (matches UTC+5:30)" if clock_ok else "clock: WRONG - bars will look stale, no signals will fire")

    token = health.token_from_env_file()
    expiry = health.token_expiry(token)
    status = health.token_status(expiry, now)
    if expiry is None:
        out.append("Dhan token: unreadable (.env missing or token not a JWT)")
    else:
        out.append(f"Dhan token: {status}, expires {expiry:%d-%b %H:%M}")

    failed = failed_units()
    if failed and failed[0].startswith("[could not run"):
        out.append(f"systemd: {failed[0]}")
    else:
        out.append(f"systemd: {len(failed)} failed unit(s)" + (f" - {', '.join(failed)}" if failed else ", all clean"))

    free_pct = disk_free_pct()
    out.append(f"disk: {free_pct:.0f}% free" + ("" if free_pct > 10 else " - LOW"))

    timers = next_timers()
    if timers:
        out.append("next scheduled jobs:")
        out.extend(f"  {l}" for l in timers[:10])

    return out
