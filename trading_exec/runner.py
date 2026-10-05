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
import json
import os
import sys
import time
import traceback
from datetime import date, datetime, time as dtime, timedelta

from trading_agents.core import signals as v40
from trading_agents.core.config import load_config as agents_config
from trading_agents.core.dhan_client import get_dhan_client
from trading_agents.core.market_data import DhanApiError, intraday_bars

from . import atm as atm_mod
from . import guards, health, poller, shadow, signals, trade_watch
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


def _when(iso):
    """2026-09-17T20:50:00 -> 17-Sep 20:50, which is what a phone has room for."""
    try:
        return datetime.fromisoformat(str(iso)).strftime("%d-%b %H:%M")
    except ValueError:
        return str(iso)


EXIT_ALERTS_STORE = "exit_alerts_sent.json"


def _exit_alert_keys():
    p = data_dir() / EXIT_ALERTS_STORE
    if not p.exists():
        return set()
    return set(json.loads(p.read_text(encoding="utf-8")))


def _save_exit_alert_keys(keys):
    p = data_dir() / EXIT_ALERTS_STORE
    p.write_text(json.dumps(sorted(keys)[-500:]), encoding="utf-8")   # keep it small


def check_exit_now_alerts(client, now=None):
    """PROACTIVE 'get out now' alert for reversal_exit strategies (Crude v4.2): fires the moment the
    most recently closed bar carries a valid opposite-direction signal for an OPEN shadow position -
    BEFORE the strategy's own next-bar-open fill happens, not after.

    Why this exists and [shadow exit]/REV is not enough for someone trading by hand: that alert only
    fires once shadow.mark() can see the fill in the bar data, which needs the NEXT bar to have
    already closed - by definition after the price the strategy exited at. This check runs on the
    SAME bar the condition first appears, the same moment a fresh entry signal would fire if flat,
    giving roughly one bar's width (~5 min for 5m strategies) to place a manual exit by hand, same as
    the live strategy itself has before its own fill.

    Deduplicated by (trade id, bar time) so it fires once per real event, not once per poll."""
    now = now or datetime.now()
    open_trades = [t for t in shadow.open_trades() if not t.get("observational")]
    if not open_trades:
        return
    strategies = agents_config().get("strategy", {})
    seen = _exit_alert_keys()
    changed = False
    for t in open_trades:
        strat = strategies.get(t.get("signal_instrument") or t["instrument"])
        if not strat or not strat.get("reversal_exit"):
            continue
        sid, seg, kind = t.get("signal_security_id"), t.get("signal_segment"), t.get("signal_series_type")
        if not sid:
            continue
        bars = intraday_bars(client, sid, seg, kind, (now - timedelta(days=10)).date(), now.date(), interval=5)
        bars = bars[bars["time"] + timedelta(minutes=5) <= now]        # only fully-closed bars
        if len(bars) < v40.WARMUP_BARS + 50:
            continue
        df = v40.v40_frame(bars, strat)
        last = df.iloc[-1]
        opposite_fired = bool(last["ok_s"] if t["side"] == "LONG" else last["ok_l"])
        key = f"{t['id']}|{last['time'].isoformat()}"
        if opposite_fired and key not in seen:
            seen.add(key)
            changed = True
            notify(f"[exit now · simulated] {t['instrument']} {t['side']} — reversal forming, act before the next bar", [
                f"{last['time']:%d-%b %H:%M} bar just closed with a valid opposite-direction signal.",
                f"reference underlying close {last['close']:,.1f}",
                "",
                "The live strategy exits at the NEXT bar's open (~5 min from now) - if you're trading this "
                "by hand, place your own exit now rather than waiting for the [signal exit · simulated] confirmation, "
                "which only arrives after that fill has already happened.",
                "",
                f"{t['symbol']}  entry {t.get('entry_premium')}  last seen {t.get('last_premium', 'n/a')}",
            ], "warning")
    if changed:
        _save_exit_alert_keys(seen)


def handle_signal(client, sig, now, silent=False):
    """Resolve the option, run the guards as warnings, alert, and record a shadow trade (or, when no
    option can be priced, follow the signal on the underlying). Never blocks.

    silent=True: record the shadow trade normally but suppress all Telegram/email notifications.
    Used for instruments whose alerts_enabled=false in config (forward-test mode)."""
    strat = (agents_config().get("strategy", {}) or {}).get(sig.signal_instrument or sig.instrument) or {}
    ref_rr = strat.get("ref_rr") if sig.target is None else None
    a = atm_mod.resolve(client, sig.instrument, sig.option_right, now)
    prem = atm_mod.premium_targets(a, sig, ref_rr=ref_rr)
    all_trades = shadow.load()
    ctx = dict(now=now,
               signals_today=[s for s in signals.on_date(signals.load_all(), now.date()) if s.kind == "entry"],
               open_positions=shadow.open_trades(all_trades),
               realised_today_inr=shadow.realised_today_inr(now.date(), all_trades))
    head = f"{sig.instrument} {sig.side} signal ({sig.strategy})"
    if sig.target is not None:
        risk_line = f"stop {_fmt(sig.sl)}  target {_fmt(sig.target)}  risk {_fmt(sig.risk_pts)} pts  R:R {sig.rr:g}"
    elif ref_rr:
        sign = 1 if sig.side == "LONG" else -1
        ref_target = sig.entry_hint + sign * ref_rr * sig.risk_pts
        risk_line = (f"stop {_fmt(sig.sl)}  risk {_fmt(sig.risk_pts)} pts  (reversal exit, no fixed target - "
                     f"~{_fmt(ref_target)} at {ref_rr:g}R avg-win reference, NOT a real exit)")
    else:
        risk_line = f"stop {_fmt(sig.sl)}  risk {_fmt(sig.risk_pts)} pts  (reversal exit, no fixed target)"
    base = [f"{_when(sig.bar_time)} bar  {sig.signal_label or 'underlying'} {_fmt(sig.entry_hint)}", risk_line]
    missed = sig.note == poller.MISSED_NOTE
    if missed:
        head += " - MISSED"
        base = [f"Caught up after a restart or outage: this signal fired while the checker was not "
                f"polling ({sig.age_minutes(now):.0f} min ago).", ""] + base

    # Nothing blocks a signal (the trader's call, 2026-09-30): every one the strategy takes goes out
    # as an entry alert, and whatever the guards object to is printed on it as a warning. What the
    # guards still decide is only HOW it is tracked: as a simulated option trade when the option can
    # be priced now, otherwise followed in points on the underlying. A caught-up (stale) signal is
    # followed in points too - buying the option late would record a trade the strategy never took.
    warnings = guards.check(sig, a, ctx)
    stale = sig.age_minutes(now) > load_config()["source"]["stale_signal_minutes"]
    warn_lines = (["", "Warnings (not blocking):"] + [f"- {w}" for w in warnings]) if warnings else []

    if not a.get("usable") or stale:
        why = "signal is from before the last poll" if stale else "; ".join(a.get("reasons") or ["option not priceable"])
        watch = shadow.open_watch(sig, [why], now)
        shadow.record_watch(watch)
        sig.status = "SIGNAL"
        sig.note = ((poller.MISSED_NOTE + " | ") if missed else "") + "; ".join(warnings)
        signals.append(sig)
        if not silent:
            notify(f"[signal · simulated] {head}", ["SIMULATED - a strategy signal, not a trade in your Dhan account.", ""] + base + warn_lines + [
                "", f"No simulated option trade ({why}). Followed on {sig.signal_label or 'the underlying'}:"
                    " you get [signal exit · simulated] when the strategy exits."], "warning" if warnings else "info")
        else:
            print(f"{_stamp()} [silent signal] {head} — alerts_enabled=false, recorded but not sent")
        return dict(signal=sig.to_dict(), warnings=warnings, trade=None, watch=watch)

    trade = shadow.open_trade(sig, a, prem, now)
    shadow.record(trade)
    sig.status = "SHADOW"
    sig.note = trade["id"] + (" | " + "; ".join(warnings) if warnings else "")
    signals.append(sig)
    if not silent:
        if prem.get("approx_target_premium") is not None:
            premium_target_txt = f" / target {_fmt(prem['approx_target_premium'])}"
        elif prem.get("approx_ref_target_premium") is not None:
            premium_target_txt = f" / ~{_fmt(prem['approx_ref_target_premium'])} avg-win ref (not a real exit)"
        else:
            premium_target_txt = ""
        notify(f"[signal · simulated] {head}", ["SIMULATED - a strategy signal, not a trade in your Dhan account.", ""] + base + [
            "",
            f"option {a['symbol']}  ({a['lots']} lots = {a['qty_units']} units, DTE {a['dte']})",
            f"entry at ask {_fmt(a['entry_premium'])}  (bid {_fmt(a['bid'])}, spread {_fmt(a['spread_pct'],1)}%)",
            f"IV {_fmt(a['iv'],1)}  delta {_fmt(a['delta'],3)}  theta {_fmt(a['theta'],1)}/day"
            f"  ({_fmt(a.get('theta_pct_of_premium'),1)}% of premium)",
            f"cost {_fmt(prem.get('cost_inr'),0)} INR   approx premium stop {_fmt(prem.get('approx_sl_premium'))}"
            f"{premium_target_txt}",
        ] + warn_lines + [
            "",
            "SHADOW ONLY - no order was placed.",
        ], "warning" if warnings else "info")
    else:
        print(f"{_stamp()} [silent signal] {head} — alerts_enabled=false, shadow trade {trade['id']} recorded")
    return dict(signal=sig.to_dict(), warnings=warnings, trade=trade)


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
    lines += ["", "No trade yet. [signal · simulated] follows only if the trigger is hit."]
    sig.status = "ARMED"
    signals.append(sig)
    notify(f"[setup armed · simulated] {sig.instrument} {sig.side} ({sig.strategy})", lines, "info")
    return dict(signal=sig.to_dict(), warnings=[], trade=None)


def tick(client, now=None):
    """One full pass: new signals, then mark open shadow trades.

    Real positions are NOT watched here: trade_watch runs as its own faster loop, and two
    processes sharing its state file would race."""
    now = now or datetime.now()
    out = dict(at=now.replace(microsecond=0).isoformat(), signals=[], armed=0, followed=0, opened=0,
               closed=[], watch_closed=[])
    check_exit_now_alerts(client, now)                    # proactive - before the retrospective checks below

    # Load trades/watches once per tick for the per-instrument SL count check.
    _all_trades  = shadow.load()
    _all_watches = shadow.load_watches()

    for sig in poller.poll_once(client, now, since=poller.last_poll()):   # catches up after a restart/outage
        if sig.kind == "armed":
            out["signals"].append(handle_armed(client, sig, now)["signal"])
            out["armed"] += 1
            continue

        icfg = load_config()["instruments"].get(sig.instrument, {})

        # Hard block: max_losses_day per instrument. Append to signals.jsonl so it is never re-emitted.
        max_losses = icfg.get("max_losses_day")
        if max_losses:
            sl_today = shadow.sl_exits_today(sig.instrument, now.date(), _all_trades, _all_watches)
            if sl_today >= max_losses:
                sig.status = "BLOCKED"
                sig.note = f"max_losses_day={max_losses}: {sl_today} SL exits today for {sig.instrument}"
                signals.append(sig)
                print(f"{_stamp()} [blocked] {sig.instrument} {sig.side} — {sig.note}")
                out["signals"].append(sig.to_dict())
                continue

        # Soft mode: alerts_enabled=false means shadow-record but suppress Telegram/email.
        silent = not icfg.get("alerts_enabled", True)

        res = handle_signal(client, sig, now, silent=silent)
        out["signals"].append(res["signal"])
        out["followed"] += res["trade"] is None
        out["opened"] += bool(res["trade"])

    _all, closed = shadow.mark_all(client, now)
    for t in closed:
        out["closed"].append(t)
        notify(f"[signal exit · simulated] {t['instrument']} {t['side']} {t['exit_reason']}", [
            "SIMULATED - not a trade in your Dhan account.",
            f"{t['symbol']}",
            f"premium {_fmt(t['entry_premium'])} -> {_fmt(t['exit_premium'])}  ({_fmt(t.get('pct'),1)}%)",
            f"net {_fmt(t.get('net_inr'),0)} INR after {_fmt(t['costs_inr'],0)} costs",
            f"held {_fmt(t.get('hold_min'),0)} min   underlying exit {_fmt(t.get('underlying_exit'))}",
            f"a 30% premium stop would have given {_fmt(t.get('premium_stop_net_inr'),0)} INR"
            if t.get("premium_stop_net_inr") is not None else "the 30% premium stop was never hit",
        ], "info")

    _watches, watch_closed = shadow.mark_watches(client, now)
    for w in watch_closed:
        out["watch_closed"].append(w)
        pts = w.get("pts")
        notify(f"[signal exit · simulated] {w['instrument']} {w['side']} {w['exit_reason']}", [
            "SIMULATED - not a trade in your Dhan account.",
            w["strategy"].split(" (")[0],
            f"{w.get('signal_label') or 'underlying'} {_fmt(w.get('entry_fill'))} -> {_fmt(w.get('exit_level'))}",
            f"{'+' if (pts or 0) >= 0 else ''}{_fmt(pts)} pts   {_fmt(w.get('r_multiple'), 2)} R"
            f"   held {_fmt(w.get('hold_min'), 0)} min",
            "",
            f"Followed on the underlying, no simulated option trade: {w['blocked_by']}",
        ], "info")

    poller.save_last_poll(now)                            # only after a full pass: a failed tick is retried
    return out


def status_lines(now=None, client=None):
    """Same content status() prints, as a list of lines - reused by the bot's /status command."""
    now = now or datetime.now()
    trades = shadow.load()
    op = shadow.open_trades(trades)
    todays = signals.on_date(signals.load_all(), now.date())
    lines = [f"SHADOW BOOK (simulated, not your account): {len(op)} open"]
    for t in op:
        lines.append(f"  {t['symbol']} {t['side']} entry {_fmt(t['entry_premium'])} last {_fmt(t.get('last_premium'))}"
                     f" | underlying stop {_fmt(t['sl'])} target {_fmt(t['target'])}")
    lines.append(f"signals today: {len(todays)} ({sum(s.status == 'SIGNAL' for s in todays)} followed on the underlying only)")
    watching = shadow.open_watches()
    lines.append(f"signals followed on the underlying: {len(watching)}")
    for w in watching:
        lines.append(f"  {w['instrument']} {w['side']} from {_fmt(w.get('entry_fill') or w['signal_entry'])}"
                     f" | stop {_fmt(w['sl'])} target {_fmt(w['target'])} | {w['blocked_by']}")
    lines.append(f"realised today (shadow): {_fmt(shadow.realised_today_inr(now.date(), trades), 0)} INR")
    lines.append(f"closed all-time: {sum(t['status'] == 'CLOSED' for t in trades)}")
    if client is not None:
        lines.append("real open positions:")
        lines += trade_watch.status_lines(client)
    return lines


def status(now=None, client=None):
    for line in status_lines(now, client):
        print(line)


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
    if not health.assert_ist(notify_fn):
        return 2
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
                      f"{out['followed']} followed on the underlying, {len(out['closed'])} closed")
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
        status(client=get_dhan_client())
        return 0

    if args.loop:
        return run_loop(args.until)

    client = get_dhan_client()

    out = tick(client)
    print(f"{out['at']}: {len(out['signals'])} signal(s), {out['opened']} opened, "
          f"{out['followed']} followed on the underlying, {len(out['closed'])} closed")
    for s in out["signals"]:
        print(f"  {s['instrument']} {s['side']} {s['status']}: {s.get('note') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
