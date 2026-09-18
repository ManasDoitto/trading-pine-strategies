"""Telegram bot commands: read messages FROM the trader, not just alerts TO them, and run the
matching workflow. Checked once per position-watcher tick (~20s poll_seconds) - see the call to
poll_and_handle() in trade_watch.run_loop. No separate process, no separate schedule.

Only messages from TELEGRAM_CHAT_ID are ever acted on; everything else is silently ignored, so
finding the bot's username does not let a stranger trigger anything on this account. Nothing here
places an order - every command is read-only, same as the rest of trading_exec.

Commands:
  /analyze         live trade analysis for every currently open real position: strategy match,
                   its own stop/target for this direction, and your mistake history
  /status          shadow book, real positions, signals today, blocked signals being followed
  /premarket       rebuild today's pre-market facts and resend the digest (same as the 08:27 job)
  /session-close   rebuild today's session facts and resend the digest (same as the 23:40 job)
  /help            list commands

/premarket and /session-close send the deterministic digest, not the full Claude-written
narrative brief - a bot command can't invoke a Claude session. Ask Claude directly for that.

First run marks any already-pending messages as read without acting on them, so an old test
message sent before this existed can never be replayed as a command.
"""
import json

import requests

from .config import data_dir, env
from .notify import notify
from .shadow import _atomic_write_json

STATE = "telegram_bot_state.json"


def _load_state():
    p = data_dir() / STATE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state):
    _atomic_write_json(data_dir() / STATE, state)


def get_updates(offset=None):
    """Pending messages since `offset`. Never raises: a flaky Telegram call must not kill the
    position-watcher loop this is piggybacked on. timeout=0 - a short poll, not long-polling, so
    this fits inside one 20s tick rather than blocking it."""
    token = env("TELEGRAM_BOT_TOKEN")
    if not token or token.startswith("123456:"):
        return []
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                         params=dict(timeout=0, offset=offset), timeout=15)
        r.raise_for_status()
        return r.json().get("result") or []
    except Exception:
        return []


# ------------------------------------------------------------------ commands
def cmd_analyze(client):
    from . import trade_watch
    trade_watch.analyze_open_positions(client)


def cmd_status(client):
    from . import runner
    notify("[bot] /status", runner.status_lines(client=client), "info")


def cmd_premarket(client):
    from . import morning
    morning.run()


def cmd_session_close(client):
    from . import evening
    evening.run()


def cmd_help(client):
    notify("[bot] commands", [
        "/analyze - live trade analysis for your open positions",
        "/status - shadow book, real positions, signals today",
        "/premarket - rebuild + resend today's pre-market digest",
        "/session-close - rebuild + resend today's post-market digest",
    ], "info")


COMMANDS = {
    "/analyze": cmd_analyze,
    "/status": cmd_status,
    "/premarket": cmd_premarket,
    "/session-close": cmd_session_close,
    "/help": cmd_help,
    "/start": cmd_help,
}


def poll_and_handle(client):
    """One check for new commands. Call every tick from an existing loop. Returns the commands
    actually run, for the caller's own logging."""
    authorized = (env("TELEGRAM_CHAT_ID") or "").strip()
    state = _load_state()
    first_run = "offset" not in state
    updates = get_updates(state.get("offset"))
    handled = []
    for upd in updates:
        state["offset"] = upd["update_id"] + 1
        if first_run:
            continue                                      # backlog from before this existed - mark read only
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat_id = str((msg.get("chat") or {}).get("id") or "")
        text = (msg.get("text") or "").strip()
        if not text or chat_id != authorized:
            continue                                      # not from the owner's chat - ignore entirely
        cmd = text.split()[0].lower()
        fn = COMMANDS.get(cmd)
        if fn is None:
            if cmd.startswith("/"):
                notify(f"[bot] unknown command {cmd}", ["Try /help"], "info")
            continue
        try:
            fn(client)
        except Exception as e:
            notify(f"[bot] {cmd} failed", [f"{type(e).__name__}: {e}"], "warning")
        handled.append(cmd)
    if updates:
        _save_state(state)
    return handled
