"""Telegram and email alerts.

Never raises: a failed alert must not take down the signal pipeline. Every attempt is
recorded in exec_data/notify.log so a silent failure is still visible afterwards.
"""
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

from .config import data_dir, env, load_config


def _log(line):
    with open(data_dir() / "notify.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().replace(microsecond=0).isoformat()} {line}\n")


# Telegram HTML: the numbers and the trading words carry the message, so they are the parts that are
# bold. A number is only emphasised when it stands on its own - never inside a contract symbol like
# SILVERM-24Sep2026-240000-CE, which would come out shredded.
# Not after ':' or before ':' either, so a clock time stays one readable piece rather than 20:<b>50</b>.
NUMBER = re.compile(r"(?<![\w.,:-])[-+]?\d[\d,]*(?:\.\d+)?(?:%|x)?(?![\w:-])(?!,\d)")
JARGON = re.compile(r"(?<![\w-])(LONG|SHORT|CE|PE|SL|TARGET|EOD|EXPIRY|STALE|ATM|DTE|IV|PF|R:R|INR|pts)"
                    r"(?![\w-])")
ADJACENT = re.compile(r"</b> <b>")          # one space only: wider gaps are deliberate columns
# "CRUDEOIL 17 SEP 2026 9600 PUT" is a name. Bolding its digits turns it into confetti, so it is
# held aside while the rest of the line is marked up. Hyphenated symbols are already safe.
SYMBOL = re.compile(r"[A-Z][A-Z]+ \d{1,2} [A-Z]{3} \d{4} [\d.]+ (?:PUT|CALL|CE|PE)")
NUM_X = re.compile(r"(?<=\d)x(?![\w-])")    # 0.89x ATR


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markup(text):
    """Escape for Telegram HTML, then bold the numbers and the trading terms."""
    safe = escape(text)
    held = []                                # a Dhan option name is one thing, not five numbers

    def hold(m):
        held.append(m.group(0))
        return f"\x00{'Q' * (len(held))}\x00"

    safe = SYMBOL.sub(hold, safe)
    safe = NUMBER.sub(lambda m: f"<b>{m.group(0)}</b>", safe)
    safe = JARGON.sub(lambda m: f"<b>{m.group(0)}</b>", safe)
    safe = ADJACENT.sub(" ", safe)          # "DTE 6" reads better than "DTE" "6" side by side
    return re.sub(r"\x00(Q+)\x00", lambda m: held[len(m.group(1)) - 1], safe)


# These alerts are read on a phone, usually mid-session and in a hurry, so every one is a card: an
# icon and a shouted tag you can recognise from the lock screen, then short lines. Column alignment
# built from runs of spaces is a terminal habit - it wraps into mush on a narrow screen - so those
# runs become middle dots and indented lines become bullets.
ICONS = {"shadow entry": "🟢", "setup armed": "⏳", "shadow exit": "🎯", "signal exit": "📊",
         "blocked": "⛔", "pre-market": "🌅", "post-market": "🌙", "trade opened": "📈", "closed": "🏁",
         "cut it": "🚨", "losing": "⚠️", "held too long": "⏱", "averaging down": "🚨",
         "take profit": "💰", "test": "🧪"}
SEVERITY_ICONS = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}
TAG = re.compile(r"^\[(?P<tag>[^\]]+)\]\s*(?P<rest>.*)$")
TRAILING_PARENS = re.compile(r"\s*\((?P<inner>[^()]+)\)\s*$")


def _icon(tag, rest, severity):
    if tag == "shadow exit":
        return "🎯" if "TARGET" in rest else "🛑" if " SL" in rest else "🏁"
    if tag == "shadow entry":
        return "🟢" if "LONG" in rest else "🔴"
    if tag.startswith("token"):
        return "🔑"
    return ICONS.get(tag) or SEVERITY_ICONS.get(severity, "•")


def headline(title, severity="info"):
    """`[shadow entry] CRUDEOIL LONG signal (CRUDE v4.0 ...)` -> an icon, a shouted tag, the subject,
    and the strategy moved onto its own quieter line."""
    m = TAG.match(title.strip())
    tag, rest = (m["tag"], m["rest"]) if m else ("", title.strip())
    sub = TRAILING_PARENS.search(rest)
    strategy = ""
    if sub:
        strategy, rest = sub["inner"], rest[:sub.start()]
    rest = re.sub(r"\s+signal$", "", rest.strip())      # only the trailing word, never mid-sentence
    # The subject is bold as one piece: it is often a contract symbol, and bolding its digits
    # separately ("CRUDEOIL 18 SEP 2026 9600 PUT") turns a name into confetti.
    head = f"{_icon(tag, rest, severity)} <b>{escape(tag.upper())}</b>" if tag else ""
    if rest:
        head = f"{head} · <b>{escape(rest)}</b>" if head else f"<b>{escape(rest)}</b>"
    return head + (f"\n<i>{escape(strategy)}</i>" if strategy else "")


def body(lines):
    out = []
    for raw in lines:
        s = str(raw).rstrip()
        if not s.strip():
            out.append("")
            continue
        indented = s[:1].isspace()
        s = re.sub(r"^[-•]\s+", "", s.strip())
        bullet = indented or s != str(raw).strip()
        s = re.sub(r"\s{2,}", " · ", s)
        out.append(("• " if bullet else "") + markup(s))
    return "\n".join(out).strip()


def _telegram(head, card):
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat or token.startswith("123456:"):
        return "skipped: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in .env"
    text = head + (f"\n\n{card}" if card else "")
    import requests
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=15)
    return "sent" if r.ok else f"failed: HTTP {r.status_code} {r.text[:120]}"


def _email(subject, text):
    host, port = env("SMTP_HOST"), env("SMTP_PORT")
    user, pwd, to = env("SMTP_USER"), env("SMTP_PASS"), env("SMTP_TO")
    if not all([host, port, user, pwd, to]) or "your-app-password" in str(pwd):
        return "skipped: SMTP_* not set in .env"
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(text)
    with smtplib.SMTP_SSL(host, int(port), timeout=20) as s:
        s.login(user, pwd)
        s.send_message(msg)
    return "sent"


def notify(title, lines, severity="info"):
    """Returns {channel: status}. Safe to call from anywhere."""
    cfg = load_config()["notify"]
    plain = "\n".join(str(l) for l in lines)
    text = f"{title}\n\n{plain}" if plain else title
    results = {}
    if cfg.get("telegram"):
        try:
            results["telegram"] = _telegram(headline(title, severity), body(lines))
        except Exception as e:
            results["telegram"] = f"error: {e}"
    if cfg.get("email"):
        try:
            results["email"] = _email(title, text)
        except Exception as e:
            results["email"] = f"error: {e}"
    _log(f"[{severity}] {title} -> {results}")
    return results
