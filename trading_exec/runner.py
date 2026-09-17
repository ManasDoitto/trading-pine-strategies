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
from datetime import date, datetime, time as dtime

from trading_agents.core.dhan_client import get_dhan_client
from trading_agents.core.market_data import DhanApiError

from . import atm as atm_mod
from . import guards, poller, shadow, signals
from .config import data_dir, load_config
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
               signals_today=signals.on_date(signals.load_all(), now.date()),
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


def tick(client, now=None):
    """One full pass: new signals, then mark open shadow trades."""
    now = now or datetime.now()
    out = dict(at=now.replace(microsecond=0).isoformat(), signals=[], blocked=0, opened=0, closed=[])
    for sig in poller.poll_once(client, now):
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

    client = get_dhan_client()
    if args.loop:
        global _LOCK
        _LOCK = acquire_single_instance()
        if _LOCK is None:
            print(f"{_stamp()} another runner is already polling; exiting so alerts are not duplicated.")
            return 0
        until = parse_hhmm(args.until) if args.until else None
        gap = load_config()["source"]["poll_seconds"]
        told = False
        print(f"{_stamp()} polling every {gap}s" + (f" until {args.until}" if until else "") + ". Ctrl-C to stop.")
        while True:
            if until and datetime.now().time() >= until:
                print(f"{_stamp()} reached --until {args.until}; stopping.")
                return 0
            try:
                out = tick(client)
                told = False
                if out["signals"] or out["closed"]:
                    print(f"{out['at']}: {len(out['signals'])} signal(s), {out['opened']} opened, "
                          f"{out['blocked']} blocked, {len(out['closed'])} closed")
            except DhanApiError as e:
                if not told:                       # tell once per outage, not every poll
                    notify("[feed down] Dhan API failure", [str(e), "", "Signals are NOT being checked."], "error")
                    told = True
                print(f"{_stamp()} feed error:", e)
            except KeyboardInterrupt:
                print("stopped.")
                return 0
            time.sleep(gap)

    out = tick(client)
    print(f"{out['at']}: {len(out['signals'])} signal(s), {out['opened']} opened, "
          f"{out['blocked']} blocked, {len(out['closed'])} closed")
    for s in out["signals"]:
        print(f"  {s['instrument']} {s['side']} {s['status']}: {s.get('note') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
