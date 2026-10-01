"""Interactive Telegram buttons on each real signal alert: tap "Taking it" or "Skipping" and
the choice is recorded. This is a log of what YOU actually decided to do -- not a simulated
P&L (that's what the removed paper tracker did) and not your real Dhan fills (that's
capital_sync.py). Three different, deliberately separate things:
  - this file:        did you SAY you'd take the signal (a button tap)
  - capital_sync.py:  what ACTUALLY got filled in your real Dhan account
  - the backtest:      what the strategy's rules say happened historically

Button presses are picked up on the next scheduled scan pass (every 5 min during market
hours), not instantly -- there is no separate always-on listener. Acknowledgment can lag up
to ~5 minutes behind the actual tap. If that's not snappy enough, a small standalone poller
can be added later; this piggybacks on the existing cadence to avoid new infrastructure.

Storage (both gitignored, both under research_data/stockopt/):
  signal_decisions.json  -- one row per signal sent: taken / skipped / still pending
  .telegram_offset.json  -- getUpdates offset, so a button press is never processed twice
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import requests

from trading_exec.notify import body as fmt_body
from trading_exec.notify import env, headline

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "research_data", "stockopt")
DECISIONS_FILE = os.path.join(DATA_DIR, "signal_decisions.json")
OFFSET_FILE = os.path.join(DATA_DIR, ".telegram_offset.json")


def _atomic_write(path, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=str)
    os.replace(tmp, path)


def load_decisions() -> list:
    if os.path.exists(DECISIONS_FILE):
        return json.load(open(DECISIONS_FILE))
    return []


def save_decisions(rows: list):
    _atomic_write(DECISIONS_FILE, rows)


def signal_id(symbol: str, dir_: int, bar: str, date_str: str) -> str:
    return f"{symbol}|{dir_}|{bar}|{date_str}"


def send_signal_with_buttons(title: str, lines: list[str], sid: str, meta: dict) -> dict:
    """Sends the alert with Taking it / Skipping inline buttons, records a 'pending' row.
    `meta` is whatever signal info is worth keeping alongside the decision (symbol, trigger,
    stop, target, shares, etc.) -- stored as-is, not interpreted here."""
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return {"telegram": "skipped: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set"}
    text = headline(title, "info") + "\n\n" + fmt_body(lines)
    keyboard = {"inline_keyboard": [[
        {"text": "✅ Taking it", "callback_data": f"take:{sid}"},
        {"text": "❌ Skipping", "callback_data": f"skip:{sid}"},
    ]]}
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                                "disable_notification": False, "disable_web_page_preview": True,
                                "reply_markup": keyboard}, timeout=15)
    except Exception as e:
        return {"telegram": f"error: {e}"}
    if not r.ok:
        return {"telegram": f"failed: HTTP {r.status_code} {r.text[:150]}"}
    msg_id = r.json()["result"]["message_id"]
    rows = load_decisions()
    rows.append(dict(signal_id=sid, message_id=msg_id, decision="pending", meta=meta,
                     sent_at=datetime.now().replace(microsecond=0).isoformat(), decided_at=None))
    save_decisions(rows)
    return {"telegram": "sent"}


def _ack_and_mark(token, chat, msg_id, text):
    try:
        requests.post(f"https://api.telegram.org/bot{token}/editMessageReplyMarkup",
                     json={"chat_id": chat, "message_id": msg_id, "reply_markup": {"inline_keyboard": []}},
                     timeout=15)
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                           "reply_to_message_id": msg_id, "disable_notification": True}, timeout=15)
    except Exception:
        pass  # the decision is already saved; a failed UI touch-up isn't worth crashing a scan pass


def poll_decisions() -> list[dict]:
    """Call once per live scan pass: picks up any button presses since the last check, records
    the decision, removes the Telegram loading spinner on the button, and replies confirming
    what was recorded. Returns the decisions newly processed this call (possibly empty)."""
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return []
    offset = 0
    if os.path.exists(OFFSET_FILE):
        offset = json.load(open(OFFSET_FILE)).get("offset", 0)
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                         params={"offset": offset, "timeout": 0}, timeout=15)
    except Exception:
        return []
    if not r.ok:
        return []
    updates = r.json().get("result", [])
    if not updates:
        return []
    rows = load_decisions()
    by_id = {row["signal_id"]: row for row in rows if row["decision"] == "pending"}
    processed = []
    max_update_id = offset - 1
    for u in updates:
        max_update_id = max(max_update_id, u["update_id"])
        cq = u.get("callback_query")
        if not cq:
            continue
        data = cq.get("data", "")
        action, sep, sid = data.partition(":")
        try:
            requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                         json={"callback_query_id": cq["id"],
                               "text": "Recorded: taking it" if action == "take" else "Recorded: skipping"},
                         timeout=15)
        except Exception:
            pass
        if not sep or sid not in by_id:
            continue  # not a decision button, or for a signal we don't have / already decided
        row = by_id[sid]
        row["decision"] = "taken" if action == "take" else "skipped"
        row["decided_at"] = datetime.now().replace(microsecond=0).isoformat()
        processed.append(row)
        msg_id = cq.get("message", {}).get("message_id")
        if msg_id:
            _ack_and_mark(token, chat, msg_id,
                         "✅ Marked: taking it" if action == "take" else "❌ Marked: skipping")
    if processed:
        save_decisions(rows)
    _atomic_write(OFFSET_FILE, {"offset": max_update_id + 1})
    return processed
