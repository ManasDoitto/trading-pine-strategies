"""Stage A runner: poll for signals, resolve the ATM option, run the guards, record a shadow
trade, and alert.

It holds only a ReadOnlyDhan client, so it cannot place an order even if something goes wrong.

    python -m trading_exec.runner --once     # one pass (safe to run any time)
    python -m trading_exec.runner --loop     # keep polling
    python -m trading_exec.runner --status   # what's open and what happened today

Unattended (Windows Task Scheduler):
    pythonw -m trading_exec.runner --loop --until 23:59 --log exec_data/runner.log

Only one --loop runner can poll at a time: a second one exits immediately, so overlapping starts
never double every alert. The lock is held by the OS and released if the process dies.
"""
import argparse
import os
import sys
import time
import traceback
from datetime import date, datetime, time as dtime

from trading_agents.core.dhan_client import get_dhan_client
from trading_agents.core.market_data import DhanApiError

from . import atm as atm_mod
from . import guards, health, poller, shadow, signals
from .config import data_dir, enabled_instruments, instrument_cfg, load_config
from .notify import notify

_LOCK = None                                   # held for the process lifetime once acquired


def parse_hhmm(text):
    hh, mm = text.strip().split(":")
    return dtime(int(hh), int(mm))


def acquire_single_instance(lock_dir=None):
    """An OS-level lock on exec_data/runner.lock. Returns the open file (keep a reference) or
    None if another runner holds it. The OS releases the lock when the process exits or crashes,
    so a crash never leaves a stale lock behind."""
    f = open((lock_dir or data_dir()) / "runner.lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def _stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fmt(x, nd=2):
    return "n/a" if x is None else (f"{x:,.{nd}f}" if isinstance(x, (int, float)) else str(x))


def handle_signal(client, sig, now):
    """Resolve the option, run guards, and either record a shadow trade or a blocked signal."""
    a = atm_mod.resolve(client, sig.instrument, sig.option_right, now)
    prem = atm_mod.premium_targets(a, sig)
    all_trades = shadow.load()
    ctx = dict(now=now,
               signals_today=[s for s in signals.on_date(signals.load_all(), now.date()) if s.kind == "entry"],
               open_positions=shadow.open_trades(all_trades),
               realised_today_inr=shadow.realised_today_inr(now.date(), all_trades))
    blocks = guards.check(sig, a, ctx)

    head = f"{sig.instrument} {sig.side} signal ({sig.strategy})"
    base = [f"bar {sig.bar_time}  {sig.signal_label or 'underlying'} {_fmt(sig.entry_hint)}",
            f"stop {_fmt(sig.sl)}  target {_fmt(sig.target)}  risk {_fmt(sig.risk_pts)} pts  R:R {sig.rr:g}"]

    if blocks:
        observed = None
        # The floor rarely blocks outright; near expiry it quietly selects a further, often illiquid
        # chain. Whenever the nearest expiry is below the floor, record it observationally so the
        # month can price the rule itself.
        if a.get("nearest_below_floor"):
            near = atm_mod.resolve(client, sig.instrument, sig.option_right, now, force_nearest=True)
            if near.get("usable"):
                observed = shadow.open_trade(sig, near, atm_mod.premium_targets(near, sig), now,
                                             observational=True)
                shadow.record(observed)
        sig.status = "BLOCKED"
        sig.note = "; ".join(blocks) + (" | recorded observationally" if observed else "")
        signals.append(sig)
        extra = ([f"", f"Recorded observationally: {observed['symbol']} at {_fmt(observed['entry_premium'])}"
                  f" (DTE {observed['dte_at_entry']}) - tracked to measure what the floor costs, never traded."]
                 if observed else [])
        notify(f"[blocked] {head}", base + ["", "Blocked by:"] + [f"- {b}" for b in blocks] + extra, "warning")
        return dict(signal=sig.to_dict(), blocked=blocks, trade=None, observational=observed)

    trade = shadow.open_trade(sig, a, prem, now)
    shadow.record(trade)
    sig.status = "SHADOW"
    sig.note = trade["id"]
    signals.append(sig)
    notify(f"[shadow entry] {head}", base + [
        "",
        f"option {a['symbol']}  ({a['lots']} lots = {a['qty_units']} units, DTE {a['dte']})",
        f"entry at ask {_fmt(a['entry_premium'])}  (bid {_fmt(a['bid'])}, spread {_fmt(a['spread_pct'],1)}%)",
        f"IV {_fmt(a['iv'],1)}  delta {_fmt(a['delta'],3)}  theta {_fmt(a['theta'],1)}/day"
        f"  ({_fmt(a.get('theta_pct_of_premium'),1)}% of premium)",
        f"cost {_fmt(prem.get('cost_inr'),0)} INR   approx premium stop {_fmt(prem.get('approx_sl_premium'))}"
        f" / target {_fmt(prem.get('approx_target_premium'))}",
        "",
        "SHADOW ONLY - no order was placed.",
    ], "info")
    return dict(signal=sig.to_dict(), blocked=[], trade=trade)


def handle_armed(client, sig, now):
    """A BankNifty v0.4 stop entry was armed: say where the trigger is before any trade happens."""
    a = atm_mod.resolve(client, sig.instrument, sig.option_right, now)
    above = sig.side == "LONG"
    lines = [f"trigger: {sig.signal_label} trades {'above' if above else 'below'} {_fmt(sig.entry_hint)}",
             f"if triggered: stop {_fmt(sig.sl)}  target {_fmt(sig.target)}  risk {_fmt(sig.risk_pts)} pts  R:R {sig.rr:g}",
             sig.note, ""]
    if a.get("usable"):
        lines += [f"option a buyer would use: {a['symbol']} ({a['lots']} lots = {a['qty_units']} units, DTE {a['dte']})",
                  f"ask now {_fmt(a['entry_premium'])}  spread {_fmt(a['spread_pct'], 1)}%  "
                  f"theta {_fmt(a.get('theta_pct_of_premium'), 1)}% of premium/day"]
    else:
        lines += ["option preview unavailable: " + "; ".join(a.get("reasons") or ["unknown"])]
    lines += ["", "No trade yet. [shadow entry] follows only if the trigger is hit."]
    sig.status = "ARMED"
    signals.append(sig)
    notify(f"[setup armed] {sig.instrument} {sig.side} ({sig.strategy})", lines, "info")
    return dict(signal=sig.to_dict(), blocked=[], trade=None)


def tick(client, now=None):
    """One full pass: new signals, then mark open shadow trades."""
    now = now or datetime.now()
    out = dict(at=now.replace(microsecond=0).isoformat(), signals=[], armed=0, blocked=0, opened=0, closed=[])
    for sig in poller.poll_once(client, now):
        if sig.kind == "armed":
            out["signals"].append(handle_armed(client, sig, now)["signal"])
            out["armed"] += 1
            continue
        res = handle_signal(client, sig, now)
        out["signals"].append(res["signal"])
        out["blocked"] += bool(res["blocked"])
        out["opened"] += bool(res["trade"])

    _all, closed = shadow.mark_all(client, now)
    for t in closed:
        out["closed"].append(t)
        notify(f"[shadow exit] {t['instrument']} {t['side']} {t['exit_reason']}", [
            f"{t['symbol']}",
            f"premium {_fmt(t['entry_premium'])} -> {_fmt(t['exit_premium'])}  ({_fmt(t.get('pct'),1)}%)",
            f"net {_fmt(t.get('net_inr'),0)} INR after {_fmt(t['costs_inr'],0)} costs",
            f"held {_fmt(t.get('hold_min'),0)} min   underlying exit {_fmt(t.get('underlying_exit'))}",
            f"a 30% premium stop would have given {_fmt(t.get('premium_stop_net_inr'),0)} INR"
            if t.get("premium_stop_net_inr") is not None else "the 30% premium stop was never hit",
        ], "info")
    return out


def status(now=None):
    now = now or datetime.now()
    trades = shadow.load()
    op = shadow.open_trades(trades)
    todays = signals.on_date(signals.load_all(), now.date())
    print(f"open shadow trades: {len(op)}")
    for t in op:
        print(f"  {t['symbol']} {t['side']} entry {_fmt(t['entry_premium'])} last {_fmt(t.get('last_premium'))}"
              f" | underlying stop {_fmt(t['sl'])} target {_fmt(t['target'])}")
    print(f"signals today: {len(todays)} ({sum(s.status == 'BLOCKED' for s in todays)} blocked)")
    print(f"realised today: {_fmt(shadow.realised_today_inr(now.date(), trades), 0)} INR")
    print(f"closed all-time: {sum(t['status'] == 'CLOSED' for t in trades)}")


class LoopState:
    """What the loop has already told you, so each problem is announced once, not every minute."""

    def __init__(self):
        self.feed_down = False
        self.error = False
        self.token = None
        self.warned = set()


def watching_lines():
    from trading_agents.core.config import load_config as agents_config
    strategies = agents_config().get("strategy", {})
    lines = []
    for traded in enabled_instruments():
        tcfg = instrument_cfg(traded)
        source = tcfg.get("signal_from", traded)
        series = f"{source} futures" if tcfg.get("signal_series") == "future" else source
        name = (strategies.get(source) or {}).get("name", "no strategy")
        lines.append(f"- {traded} options, signal on {series}: {name.split(' (')[0]}")
    return lines


def check_token(state, now, until, notify_fn):
    """Warn once per token per condition: expiring before the close, within the hour, or expired."""
    token = health.token_from_env_file()
    expiry = health.token_expiry(token)
    status = health.token_status(expiry, now, until)
    key = (token[-12:], status)
    messages = {
        "expires_before_close": ("[token warning] Dhan token expires before today's close",
                                 [f"expires {expiry:%d-%b %H:%M}; the checker runs until {until.strftime('%H:%M') if until else 'stopped'}.",
                                  "Regenerate DHAN_ACCESS_TOKEN in .env before then - it is picked up automatically."]),
        "expires_within_hour": ("[token expiring] Dhan token expires within the hour",
                                [f"expires {expiry:%d-%b %H:%M}.",
                                 "Regenerate DHAN_ACCESS_TOKEN in .env now - it is picked up automatically."]),
        "expired": ("[token expired] Dhan token has expired - no signals are being checked",
                    [f"expired {expiry:%d-%b %H:%M}.",
                     "Regenerate DHAN_ACCESS_TOKEN in .env; checking resumes within a minute."]),
    }
    if status in messages and key not in state.warned:
        state.warned.add(key)
        notify_fn(*messages[status], "warning")
    return expiry, status


def tick_safely(state, client_ref, notify_fn, now=None, tick_fn=None):
    """One poll that can never kill the loop. Rebuilds the client when .env has a new token, and
    announces each outage once and each recovery once."""
    tick_fn = tick_fn or tick
    try:
        token = health.token_from_env_file()
        if client_ref[0] is None or token != state.token:
            client_ref[0] = health.fresh_client()
            if state.token is not None and token != state.token:
                notify_fn("[token refreshed] picked up the new Dhan token", ["Signal checking continues."], "info")
            state.token = token
        out = tick_fn(client_ref[0], now)
        if state.feed_down or state.error:
            notify_fn("[recovered] signal checking resumed", [f"at {datetime.now():%H:%M}"], "info")
        state.feed_down = state.error = False
        return out
    except DhanApiError as e:
        if not state.feed_down:
            notify_fn("[feed down] Dhan API failure", [str(e), "", "Signals are NOT being checked until this clears."],
                      "error")
            state.feed_down = True
        print(f"{_stamp()} feed error: {e}")
    except Exception as e:                          # anything else: log it, say it once, keep going
        traceback.print_exc()
        if not state.error:
            notify_fn("[checker error] still running and retrying every minute",
                      [f"{type(e).__name__}: {e}", "", "Signals are NOT being checked until this clears."], "error")
            state.error = True
        print(f"{_stamp()} error: {type(e).__name__}: {e}")
    return None


def run_loop(until_text=None, notify_fn=None, sleep=time.sleep, max_ticks=None):
    """The unattended loop. Holds the single-instance lock, announces its start (or a restart), warns
    about the token, and never exits on an error - only at --until or Ctrl-C."""
    global _LOCK
    notify_fn = notify_fn or notify
    _LOCK = acquire_single_instance()
    if _LOCK is None:
        print(f"{_stamp()} another runner is already polling; exiting so alerts are not duplicated.")
        return 0
    until = parse_hhmm(until_text) if until_text else None
    gap = load_config()["source"]["poll_seconds"]
    state = LoopState()
    client_ref = [None]
    now = datetime.now()
    print(f"{_stamp()} polling every {gap}s" + (f" until {until_text}" if until else "") + ". Ctrl-C to stop.")

    first = health.mark_started(now.date())
    expiry = health.token_expiry(health.token_from_env_file())
    token_line = (f"Dhan token valid until {expiry:%d-%b %H:%M}" if expiry and expiry > now
                  else "Dhan token EXPIRED or unreadable - regenerate it in .env" if expiry
                  else "Dhan token expiry unreadable")
    notify_fn("[checker started]" if first else "[checker restarted]",
              [f"{now:%a %d-%b %H:%M}" + (f", running until {until_text}" if until else ""), "Watching:"]
              + watching_lines() + ["", token_line], "info")

    ticks = 0
    try:
        while True:
            now = datetime.now()
            if until and now.time() >= until:
                print(f"{_stamp()} reached --until {until_text}; stopping.")
                return 0
            check_token(state, now, until, notify_fn)
            out = tick_safely(state, client_ref, notify_fn, now)
            if out and (out["signals"] or out["closed"]):
                print(f"{out['at']}: {len(out['signals'])} signal(s), {out['opened']} opened, "
                      f"{out['blocked']} blocked, {len(out['closed'])} closed")
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                return 0
            sleep(gap)
    except KeyboardInterrupt:
        print(f"{_stamp()} stopped.")
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--until", help="HH:MM; with --loop, exit cleanly at this time (e.g. 23:59, after the MCX close)")
    ap.add_argument("--log", help="append all output to this file (for unattended runs with no console)")
    args = ap.parse_args(argv)

    if args.log:
        log = open(args.log, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log

    if args.status:
        status()
        return 0

    if args.loop:
        return run_loop(args.until)

    client = get_dhan_client()

    out = tick(client)
    print(f"{out['at']}: {len(out['signals'])} signal(s), {out['opened']} opened, "
          f"{out['blocked']} blocked, {len(out['closed'])} closed")
    for s in out["signals"]:
        print(f"  {s['instrument']} {s['side']} {s['status']}: {s.get('note') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
