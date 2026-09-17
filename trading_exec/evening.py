"""The post-market job: rebuild the day's facts, then send the session digest to Telegram.

The mirror of morning.py, after the close instead of before the open. It runs the same three
deterministic steps the /session-close skill runs first, so the numbers are identical to the ones a
full review would cite:

    journal facts -> session-close facts -> scorecard (merged into the session facts)

Then it sends what a trader wants on their phone without opening anything: what their own trades did
and which rules they broke, what each strategy did on the same session, how this morning's bias was
graded, and how the shadow book moved.

Nothing here is a recommendation and nothing is placed - it reads Dhan and writes files.

    python -m trading_exec.evening                   # today, all sessions
    python -m trading_exec.evening --session MCX     # crude and silver only
    python -m trading_exec.evening --no-notify       # rebuild and print, send nothing

Unattended (Windows Task Scheduler), after the MCX close:
    pythonw -m trading_exec.evening --log exec_data/evening.log
"""
import argparse
import json
import sys
import traceback
from datetime import date, datetime

from trading_agents.core.config import data_dir as agents_data_dir
from trading_agents.facts import journal as journal_facts
from trading_agents.facts import session_close as session_facts
from trading_agents.validate import scorecard

from . import health, shadow
from .morning import _fmt
from .notify import notify

BUILD_FAILED = "facts build failed"


def _facts(day, kind):
    path = agents_data_dir("facts") / f"{day}_{kind}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def build_facts(day, session="ALL", only=None):
    """Journal, session and scorecard, in the order /session-close uses. Returns (facts, error)."""
    argv = ["--date", day.isoformat()] + (["--session", session] if session != "ALL" else [])
    try:
        journal_facts.main(argv + (["--only", ",".join(only)] if only else []))
        session_facts.main(argv + (["--only", ",".join(only)] if only else []))
        scorecard.main(["--date", day.isoformat()])
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    facts = _facts(day, "session_close")
    return (facts, None) if facts else (None, "session facts were not written")


def your_day_lines(day):
    """Your real fills: what they made and which rules they broke."""
    j = _facts(day, "journal")
    if not j:
        return ["your trades: no journal facts"]
    today = j.get("today") or {}
    s = today.get("summary_round_trips") or {}
    if not s.get("n"):
        return ["you took no trades today"]
    lines = [f"you: {s['n']} round trips, net {_fmt(s.get('net'), 0)} INR"
             f"  win rate {_fmt(s.get('win_rate'), 0)}%  PF {_fmt(s.get('profit_factor'))}"]
    for v in today.get("violations") or []:
        lines.append(f"  {v['rule']} {v['title']}: {v['symbol']} ({_fmt(v.get('inr'), 0)} INR)")
    return lines


def instrument_lines(name, sf, grades):
    sess, st = sf.get("session") or {}, sf.get("strategy") or {}
    if not sf.get("available") or sess.get("close") is None:
        return [f"{name}: {sf.get('note') or sess.get('note') or 'no session data'}"]
    out = [f"{name} C {_fmt(sess.get('close'))} ({_fmt(sess.get('change_pct'), 2)}%)"
           f"  range {_fmt(sess.get('range_vs_atr'), 2)}x ATR"]
    if st.get("available"):
        tag = "v0.4" if st.get("engine") == "v04" else "v4.0"
        out.append(f"  {tag}: {len(st.get('signals') or [])} signals, {len(st.get('trades') or [])} trades,"
                   f" {_fmt(st.get('trades_net_pts'), 1)} pts")
    al = sf.get("alignment") or {}
    if al.get("entries"):
        out.append(f"  your {al['entries']} entries: {al.get('matched_a_signal', 0)} matched a signal")
    g = grades.get(name)
    if g:
        verdict = "right" if str(g.get("rule_correct")).lower() == "true" else (
            "wrong" if str(g.get("rule_correct")).lower() == "false" else "ungraded")
        out.append(f"  morning bias {g.get('rule_bias') or 'n/a'} -> {g.get('outcome')} ({verdict})")
    return out


def shadow_lines(day):
    trades = shadow.load()
    closed = [t for t in trades if t["status"] == "CLOSED" and not t.get("observational")
              and str(t.get("exit_at", ""))[:10] == day.isoformat()]
    watches = [w for w in shadow.load_watches()
               if w["status"] == "CLOSED" and str(w.get("exit_at", ""))[:10] == day.isoformat()]
    out = []
    if closed:
        out.append(f"shadow book (simulated, not your money): {len(closed)} closed, "
                   f"{_fmt(sum(t.get('net_inr') or 0 for t in closed), 0)} INR"
                   f"  ({len(shadow.open_trades(trades))} still simulated open)")
    elif shadow.open_trades(trades):
        out.append(f"shadow book (simulated, not your money): nothing closed today, "
                   f"{len(shadow.open_trades(trades))} still simulated open")
    for w in watches:
        out.append(f"blocked signal ended: {w['instrument']} {w['side']} {w['exit_reason']}"
                   f" {_fmt(w.get('pts'))} pts (not traded)")
    return out


def digest(day, facts, token_status, expiry, error=None):
    lines = []
    if token_status == "expired":
        lines += [f"TOKEN EXPIRED ({expiry:%d-%b %H:%M}) - renew DHAN_ACCESS_TOKEN in .env before tomorrow", ""]
    if error:
        return lines + [f"{BUILD_FAILED}: {error}", "", "Run /session-close by hand to see the full error."]
    lines += your_day_lines(day) + [""]
    grades = {r["underlying"]: r for r in ((facts.get("scorecard") or {}).get("rows") or [])}
    for name, sf in (facts.get("instruments") or {}).items():
        lines += instrument_lines(name, sf, grades) + [""]
    sl = shadow_lines(day)
    if sl:
        lines += sl + [""]
    lines.append("Full review: run /session-close - the facts are already built.")
    return lines


def run(day=None, session="ALL", notify_fn=None, only=None):
    day = day or date.today()
    notify_fn = notify_fn or notify
    expiry = health.token_expiry(health.token_from_env_file())
    status = health.token_status(expiry, datetime.now(), None)
    facts, error = build_facts(day, session, only)
    lines = digest(day, facts or {}, status, expiry, error)
    notify_fn(f"[post-market] {day:%a %d-%b}", lines, "warning" if error else "info")
    return dict(day=day.isoformat(), error=error, token_status=status, lines=lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--session", choices=["NSE", "MCX", "ALL"], default="ALL")
    ap.add_argument("--only", help="comma-separated underlyings")
    ap.add_argument("--no-notify", action="store_true", help="rebuild and print, send nothing")
    ap.add_argument("--log", help="append output to this file (for Task Scheduler)")
    args = ap.parse_args(argv)

    if args.log:
        sys.stdout = sys.stderr = open(args.log, "a", encoding="utf-8", buffering=1)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        res = run(args.date, args.session, notify_fn=(lambda *a, **k: {}) if args.no_notify else None,
                  only=set(args.only.split(",")) if args.only else None)
    except Exception:
        print(f"{stamp} evening job crashed:\n{traceback.format_exc()}")
        return 1
    print(f"{stamp} post-market {res['day']} ({args.session}): token {res['token_status']}"
          f"{', ' + BUILD_FAILED if res['error'] else ', facts ok'}")
    print("\n".join(res["lines"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
