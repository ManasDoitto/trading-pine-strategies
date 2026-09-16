"""Telegram and email alerts.

Never raises: a failed alert must not take down the signal pipeline. Every attempt is
recorded in exec_data/notify.log so a silent failure is still visible afterwards.
"""
import smtplib
from datetime import datetime
from email.message import EmailMessage

from .config import data_dir, env, load_config


def _log(line):
    with open(data_dir() / "notify.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().replace(microsecond=0).isoformat()} {line}\n")


def _telegram(text):
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat or token.startswith("123456:"):
        return "skipped: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set in .env"
    import requests
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=15)
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
    body = "\n".join(str(l) for l in lines)
    text = f"{title}\n\n{body}" if body else title
    results = {}
    if cfg.get("telegram"):
        try:
            results["telegram"] = _telegram(text)
        except Exception as e:
            results["telegram"] = f"error: {e}"
    if cfg.get("email"):
        try:
            results["email"] = _email(title, text)
        except Exception as e:
            results["email"] = f"error: {e}"
    _log(f"[{severity}] {title} -> {results}")
    return results
