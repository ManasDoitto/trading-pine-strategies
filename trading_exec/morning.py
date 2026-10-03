"""The 08:27 pre-market job: build today's facts, then send a short digest to Telegram.

It exists so the morning does not depend on Claude being open. Two jobs:

1. Build `journal_data/facts/<date>_premarket.json` before the open, so /premarket is instant
   later and any data problem surfaces while there is still time to fix it.
2. Send a digest of what matters at 08:27: where each instrument closed, the ATR regime, what the
   strategy is holding or waiting for, and what the ATM option costs in theta.

The token check comes FIRST and is reported even when everything else fails, because an expired
token is the one failure that silently stops the whole day.

    python -m trading_exec.morning              # build + digest
    python -m trading_exec.morning --no-notify  # build only, print the digest

Unattended (Windows Task Scheduler):
    pythonw -m trading_exec.morning --log exec_data/morning.log
"""
import argparse
import json
import sys
import traceback
from datetime import date, datetime

from trading_agents.core.config import data_dir as agents_data_dir
from trading_agents.facts import premarket as premarket_facts

from . import guards, health, shadow
from .config import enabled_instruments, instrument_cfg
from .notify import notify

BUILD_FAILED = "facts build failed"


def _fmt(x, nd=2):
    return "n/a" if x is None else (f"{x:,.{nd}f}" if isinstance(x, (int, float)) else str(x))


def facts_path(day):
    return premarket_facts.out_path(day) if hasattr(premarket_facts, "out_path") else None


def build_facts(day, only=None):
    """Returns (facts_dict, error_text). Never raises: the digest must go out either way."""
    argv = ["--date", day.isoformat()] + (["--only", ",".join(only)] if only else [])
    try:
        premarket_facts.main(argv)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    path = agents_data_dir("facts") / f"{day.isoformat()}_premarket.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"facts written but unreadable: {e}"


def instrument_lines(name, facts, source=None):
    """Three lines an option buyer can act on: where price is, what the strategy holds, what the
    option costs to hold. `source` is the instrument the live signal is computed on when it differs
    (SILVERM options signalled off SILVER): the strategy line must describe THAT, or the digest
    shows a position the live checker does not have."""
    insts = facts.get("instruments") or {}
    inst = insts.get(name) or {}
    if not inst.get("available"):
        return [f"{name}: no data"]
    u = inst.get("underlying") or {}
    prev = u.get("prev_day") or {}
    out = [f"{name} {_fmt(prev.get('close'))} ({_fmt(u.get('prev_day_change_pct'), 2)}%)"
           f"  ATR {u.get('atr_regime') or 'n/a'} {_fmt(u.get('atr_ratio'), 2)}x"
           + (f"  (signal on {source})" if source and source != name else "")]

    s = ((insts.get(source) or {}) if source and source != name else inst).get("strategy") or {}
    if s.get("available"):
        pos, pend = s.get("position"), s.get("pending_entry")
        if pos:
            out.append(f"  holding {pos['side']} from {_fmt(pos.get('entry'))}"
                       f"  stop {_fmt(pos.get('sl'))} target {_fmt(pos.get('tp'))}"
                       f"  ({_fmt(pos.get('open_pts'), 1)} pts)")
        elif pend:
            out.append(f"  entry pending: {pend['side']} stop {_fmt(pend.get('sl'))} target {_fmt(pend.get('tp'))}")
        else:
            out.append(f"  flat, {s.get('alignment') or 'no alignment'}")
    elif s.get("modelled") is False:
        out.append("  strategy not modelled here")

    near = (inst.get("options") or {}).get("nearest") or {}
    atm = (near.get("atm") or {}).get("ce") or {}
    if atm:
        out.append(f"  ATM {_fmt(near.get('atm_strike'), 0)} CE {_fmt(atm.get('ltp'))}"
                   f"  DTE {near.get('dte')}  theta {_fmt(atm.get('theta_pct_of_premium'), 1)}%/day")
    return out


def open_shadow_lines(trades=None):
    """Simulated trades carried into today. A swing trade can stay open for days after its one
    [signal · simulated] alert; without this it later shows up only as a block reason, unexplained."""
    op = [t for t in shadow.open_trades(trades) if not t.get("observational")]
    if not op:
        return ["No simulated trades open."]
    out = ["Simulated trades still open (shadow book - NOT your account):"]
    for t in op:
        target = f" target {_fmt(t['target'])}" if t.get("target") is not None else " (reversal exit)"
        out.append(f"- {guards.describe_open(t)}: {t.get('signal_label') or 'underlying'}"
                   f" from {_fmt(t.get('signal_entry'))}  stop {_fmt(t['sl'])}{target}")
    return out + [""]


def digest(day, facts, token_status, expiry, error=None):
    lines = []
    if token_status == "expired":
        lines += [f"TOKEN EXPIRED ({expiry:%d-%b %H:%M}) - no signals until DHAN_ACCESS_TOKEN is renewed in .env", ""]
    elif token_status in ("expires_within_hour", "expires_before_close") and expiry:
        lines += [f"Token expires {expiry:%d-%b %H:%M} - renew it in .env before then", ""]
    if error:
        lines += [f"{BUILD_FAILED}: {error}", "", "Run /premarket by hand to see the full error."]
        return lines
    for name in enabled_instruments():
        lines += instrument_lines(name, facts, instrument_cfg(name).get("signal_from"))
        lines.append("")
    lines += open_shadow_lines()
    src = (facts.get("instruments") or {})
    watched = [n for n in src if n not in enabled_instruments()]
    if watched:
        lines.append("also in the facts (not watched live): " + ", ".join(watched))
    lines.append("Full brief: run /premarket - the facts are already built.")
    return lines


def run(day=None, notify_fn=None, only=None):
    day = day or date.today()
    notify_fn = notify_fn or notify
    token = health.token_from_env_file()
    expiry = health.token_expiry(token)
    status = health.token_status(expiry, datetime.now(), None)
    facts, error = build_facts(day, only)
    lines = digest(day, facts or {}, status, expiry, error)
    severity = "warning" if (error or status == "expired") else "info"
    notify_fn(f"[pre-market] {day:%a %d-%b}", lines, severity)
    return dict(day=day.isoformat(), error=error, token_status=status, lines=lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--only", help="comma-separated underlyings")
    ap.add_argument("--no-notify", action="store_true", help="build and print, send nothing")
    ap.add_argument("--log", help="append output to this file (for Task Scheduler)")
    args = ap.parse_args(argv)

    if args.log:
        sys.stdout = sys.stderr = open(args.log, "a", encoding="utf-8", buffering=1)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        res = run(args.date, notify_fn=(lambda *a, **k: {}) if args.no_notify else None,
                  only=set(args.only.split(",")) if args.only else None)
    except Exception:
        print(f"{stamp} morning job crashed:\n{traceback.format_exc()}")
        return 1
    print(f"{stamp} pre-market {res['day']}: token {res['token_status']}"
          f"{', ' + BUILD_FAILED if res['error'] else ', facts ok'}")
    print("\n".join(res["lines"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
