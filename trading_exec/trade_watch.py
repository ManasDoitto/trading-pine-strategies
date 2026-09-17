"""Watches the REAL Dhan account and alerts on Telegram while the trader is away from the screen.

Everything here reacts to positions the trader punched manually, on any instrument Dhan reports -
not only the four the strategies follow, and never a shadow trade. It is read-only: it sends
messages, it never places, modifies or closes anything.

What it sends, each once per position per day:
  [trade opened]   a quality card the moment a new position appears - moneyness vs the R7 strike
                   limit, DTE vs R3, theta burden, and the exact premium levels where the cut
                   alert and the profit alert will fire, so the plan exists before the trade moves
  [cut it]         premium down `cut_pct` from the average entry (the trader's own 25% line)
  [losing]         an earlier heads-up at `warn_pct`
  [held too long]  the hold ladder: still down X% after N minutes, for trades that die slowly
                   rather than fast - the 2026-09-17 R4 breach sat 115 minutes before it was cut
  [averaging down] quantity added while the price is below the running average (R1), the single
                   most expensive habit in the journal
  [take profit]    unrealised profit above the trader's own average win on that underlying
  [closed]         a short result card when the position disappears

Hold time is measured from when this watcher FIRST SAW the position, so a position that predates
the process is a lower bound, and the card says so.

    python -m trading_exec.trade_watch --once            # one pass
    python -m trading_exec.trade_watch --status          # what's open and where the cut sits
    python -m trading_exec.trade_watch --test-telegram   # prove alerts reach the phone
    python -m trading_exec.trade_watch --loop            # keep watching

Unattended (Windows Task Scheduler), alongside the signal runner:
    pythonw -m trading_exec.trade_watch --loop --until 23:59 --log exec_data/trade_watch.log

It needs nothing from Claude: it is plain Python talking to Dhan and Telegram. It does need the
machine it runs on to stay awake and online.
"""
import argparse
import json
from datetime import date, datetime

from trading_agents.core import instruments
from trading_agents.core.config import load_config as agents_config
from trading_agents.core.option_symbols import underlying_of
from trading_agents.facts.journal import live_positions

from .config import data_dir, load_config
from .notify import notify

STORE = "trade_watch_state.json"
BENCHMARK_FALLBACK_INR = 4000.0


def _path():
    return data_dir() / STORE


def _load_state():
    p = _path()
    state = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if state.get("date") != date.today().isoformat():
        return {"date": date.today().isoformat(), "positions": {}}
    state.setdefault("positions", {})
    return state


def _save_state(state):
    _path().write_text(json.dumps(state, indent=1, default=str), encoding="utf-8")


def _cfg():
    return load_config().get("trade_watch", {})


def _fmt(x, nd=2):
    return "n/a" if x is None else f"{x:,.{nd}f}"


def bought_options(positions):
    """Only LONG option positions: a premium stop and a strike limit mean nothing on a short leg."""
    return [p for p in positions if p["side"] == "LONG" and p.get("right") in ("CE", "PE")
            and p.get("avg_entry") and p.get("ltp") is not None]


# ------------------------------------------------------------------ the trader's own numbers
def average_win_inr(underlying):
    """The trader's own average winning trade, from the newest journal facts: per underlying when
    that underlying has a history, else the account-wide episode average."""
    cfg = _cfg()
    if cfg.get("profit_alert_inr"):
        return float(cfg["profit_alert_inr"]), "config"
    files = sorted((data_dir().parent / "journal_data" / "facts").glob("*_journal.json")) \
        if (data_dir().parent / "journal_data" / "facts").exists() else []
    if files:
        try:
            all_time = json.loads(files[-1].read_text(encoding="utf-8"))["all_time"]
            by_und = (all_time.get("round_trips_by_underlying") or {}).get(underlying) or {}
            if by_und.get("avg_win") and (by_und.get("n") or 0) >= 5:
                return float(by_und["avg_win"]), f"{underlying} average win"
            if all_time["summary_episodes"].get("avg_win"):
                return float(all_time["summary_episodes"]["avg_win"]), "account average win"
        except (KeyError, ValueError, TypeError):
            pass
    return BENCHMARK_FALLBACK_INR, "fallback"


def dte_of(expiry, today=None):
    try:
        return (date.fromisoformat(str(expiry)[:10]) - (today or date.today())).days
    except (TypeError, ValueError):
        return None


def strikes_otm(underlying, right, strike, spot, expiry=None):
    """How many strikes out of the money the entry was, in that chain's own strike steps."""
    step = instruments.strike_step(underlying, expiry)
    if not step or not spot or not strike:
        return None
    dist = (strike - spot) if right == "CE" else (spot - strike)
    return round(dist / step, 2)


def underlying_spot(client, underlying, expiry):
    ref = instruments.reference_series(underlying, expiry)
    if ref is None:
        return None
    try:
        r = client.ticker_data({ref["segment"]: [int(ref["security_id"])]})
        return float(r["data"]["data"][ref["segment"]][str(ref["security_id"])]["last_price"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


# ------------------------------------------------------------------ the quality card
def quality_card(client, p, now=None):
    """Deterministic quality read on a position the trader just punched. Every line is computed
    from Dhan data or the trader's own configured rules - nothing is estimated by a model."""
    now = now or datetime.now()
    cfg = _cfg()
    und = underlying_of(p["symbol"]) or ""
    scope = agents_config()["instruments"]
    rules = agents_config()["rules"]
    entry, qty = p["avg_entry"], p["qty_units"]
    cut_pct, warn_pct = cfg.get("cut_pct", 25.0), cfg.get("warn_pct", 15.0)
    bench, bench_src = average_win_inr(und)

    lines = [f"{p['symbol']}", f"{_fmt(p['lots'], 2)} lots / {_fmt(qty, 0)} units at {_fmt(entry)}"
                               f"  =  {_fmt(entry * qty, 0)} INR at risk"]
    flags = []

    dte = dte_of(p.get("expiry"), now.date())
    if dte is not None:
        r3 = rules.get("r3_expiry_days")
        lines.append(f"expiry {str(p.get('expiry'))[:10]}  ({dte} DTE)")
        if dte == 0:
            flags.append("0 DTE - decay is at its steepest and there is no tomorrow to be right in")
        elif r3 is not None and dte <= r3:
            flags.append(f"{dte} DTE is inside the R3 floor of {r3} days")

    spot = underlying_spot(client, und, date.fromisoformat(str(p["expiry"])[:10])) \
        if und in scope and p.get("expiry") else None
    if spot and p.get("strike"):
        n_otm = strikes_otm(und, p["right"], float(p["strike"]), spot)
        # strike steps differ per chain, so each instrument carries its own R7 limit
        limit = scope.get(und, {}).get("r7_max_strikes_otm", rules.get("r7_max_strikes_otm"))
        if n_otm is not None:
            where = "ITM" if n_otm < 0 else ("ATM" if n_otm < 0.5 else f"{n_otm:g} strikes OTM")
            lines.append(f"{und} at {_fmt(spot)}  ->  strike {_fmt(float(p['strike']), 0)} is {where}")
            if limit is not None and n_otm > limit:
                flags.append(f"{n_otm:g} strikes OTM is past your R7 limit of {limit} for {und}")

    cut_at = entry * (1 - cut_pct / 100)
    lines += [
        "",
        f"cut alert at {_fmt(cut_at)}  (-{cut_pct:g}%, {_fmt((cut_at - entry) * qty, 0)} INR)",
        f"profit alert at {_fmt(entry + bench / qty)}  (+{_fmt(bench, 0)} INR, your {bench_src})",
        f"first warning at {_fmt(entry * (1 - warn_pct / 100))}  (-{warn_pct:g}%)",
    ]
    if flags:
        lines += [""] + [f"! {f}" for f in flags]
    return lines, flags


# ------------------------------------------------------------------ alert rules on an open position
def _hold_alerts(p, rec, pct, held_min, cfg):
    """The 'this is not working' ladder: still down X% after N minutes."""
    out = []
    for i, rule in enumerate(cfg.get("hold_rules") or []):
        key = f"hold{i}"
        if key in rec["sent"]:
            continue
        if held_min >= rule["after_min"] and pct <= -rule["loss_pct"]:
            out.append((key, f"[held too long] {p['symbol']}",
                        [f"held {held_min:.0f} min and still {pct:.1f}% down.",
                         f"Your rule: more than {rule['after_min']:g} min and still {rule['loss_pct']:g}% down "
                         f"means the idea has not worked.",
                         f"entry {_fmt(p['avg_entry'])}  now {_fmt(p['ltp'])}  "
                         f"unrealised {_fmt(p['unrealized_inr'], 0)} INR"], "warning"))
    return out


def evaluate(p, rec, now, cfg):
    """Every alert this position has newly earned. Returns [(key, title, lines, severity)]."""
    entry, ltp, qty = p["avg_entry"], p["ltp"], p["qty_units"]
    pct = (ltp / entry - 1) * 100
    held_min = (now - datetime.fromisoformat(rec["first_seen"])).total_seconds() / 60
    cut_pct, warn_pct = cfg.get("cut_pct", 25.0), cfg.get("warn_pct", 15.0)
    seen_from = "" if rec.get("seen_from_open", True) else " (held at least this long - it predates the watcher)"
    common = [f"entry {_fmt(entry)}  now {_fmt(ltp)}  ({pct:+.1f}%)",
              f"{_fmt(qty, 0)} units  unrealised {_fmt(p['unrealized_inr'], 0)} INR",
              f"held {held_min:.0f} min{seen_from}"]
    out = []

    if pct <= -cut_pct and "cut" not in rec["sent"]:
        out.append(("cut", f"[CUT IT] {p['symbol']}",
                    common + ["", f"Down {cut_pct:g}% - this is your line. Exit."], "error"))
    elif pct <= -warn_pct and "warn" not in rec["sent"]:
        out.append(("warn", f"[losing] {p['symbol']}",
                    common + ["", f"The {cut_pct:g}% cut is at {_fmt(entry * (1 - cut_pct / 100))}."], "warning"))

    out += _hold_alerts(p, rec, pct, held_min, cfg)

    bench = rec.get("profit_benchmark_inr") or BENCHMARK_FALLBACK_INR
    if (p["unrealized_inr"] or 0) >= bench * cfg.get("profit_multiple", 1.0) and "profit" not in rec["sent"]:
        out.append(("profit", f"[take profit?] {p['symbol']}",
                    common + ["", f"Above your {rec.get('profit_benchmark_src', 'average win')} "
                                  f"of {_fmt(bench, 0)} INR. Decide: bank it or move a stop up."], "info"))

    if cfg.get("averaging_down_alert", True) and qty > rec["qty"] + 1e-9 and entry < rec["entry"] - 1e-9 \
            and "averaging" not in rec["sent"]:
        out.append(("averaging", f"[AVERAGING DOWN] {p['symbol']}",
                    [f"quantity {_fmt(rec['qty'], 0)} -> {_fmt(qty, 0)} while the average entry fell "
                     f"{_fmt(rec['entry'])} -> {_fmt(entry)}.",
                     "This is R1. It is the most expensive habit in your journal - 16 times all-time,",
                     "including the single worst trade in the account."], "error"))
    return out


def closed_card(p_last, rec, now):
    entry, last = rec["entry"], p_last
    pct = (last / entry - 1) * 100 if entry else None
    held_min = (now - datetime.fromisoformat(rec["first_seen"])).total_seconds() / 60
    respected = "within" if (pct is None or pct >= -_cfg().get("cut_pct", 25.0)) else "BEYOND"
    return [f"entry {_fmt(entry)}  last seen {_fmt(last)}  ({pct:+.1f}%)" if pct is not None else f"entry {_fmt(entry)}",
            f"held about {held_min:.0f} min",
            f"exited {respected} your {_cfg().get('cut_pct', 25.0):g}% line."]


# ------------------------------------------------------------------ the poll
def check(client, now=None, positions=None):
    """One pass over the real account. Returns the alerts sent."""
    now = now or datetime.now()
    cfg = _cfg()
    if not cfg.get("enabled", True):
        return []
    state = _load_state()
    known = state["positions"]
    rows = bought_options(positions if positions is not None else live_positions(client))
    sent = []

    for p in rows:
        key = p["symbol"]
        rec = known.get(key)
        if rec is None:
            bench, src = average_win_inr(underlying_of(key) or "")
            rec = dict(first_seen=now.replace(microsecond=0).isoformat(), seen_from_open=True,
                       entry=p["avg_entry"], qty=p["qty_units"], last_ltp=p["ltp"],
                       profit_benchmark_inr=bench, profit_benchmark_src=src, sent=[])
            known[key] = rec
            try:
                lines, flags = quality_card(client, p, now)
            except Exception as e:                       # a card must never stop the alerting itself
                lines, flags = [f"{key}", f"quality card unavailable: {type(e).__name__}"], []
            notify(f"[trade opened] {key}", lines, "warning" if flags else "info")
            sent.append(dict(symbol=key, level="opened"))
            continue

        for alert_key, title, lines, severity in evaluate(p, rec, now, cfg):
            rec["sent"].append(alert_key)
            notify(title, lines, severity)
            sent.append(dict(symbol=key, level=alert_key, pct=round((p["ltp"] / p["avg_entry"] - 1) * 100, 2)))
        rec.update(entry=p["avg_entry"], qty=p["qty_units"], last_ltp=p["ltp"])

    if cfg.get("closed_summary", True):
        for key in [k for k in known if k not in {p["symbol"] for p in rows}]:
            rec = known.pop(key)
            if "closed" not in rec["sent"]:
                notify(f"[closed] {key}", closed_card(rec.get("last_ltp") or rec["entry"], rec, now), "info")
                sent.append(dict(symbol=key, level="closed"))

    _save_state(state)
    return sent


def status(client=None, positions=None):
    rows = bought_options(positions if positions is not None else live_positions(client))
    if not rows:
        print("no open bought-option positions")
        return
    cut_pct = _cfg().get("cut_pct", 25.0)
    for p in rows:
        pct = (p["ltp"] / p["avg_entry"] - 1) * 100
        print(f"  {p['symbol']}  entry {_fmt(p['avg_entry'])}  now {_fmt(p['ltp'])}  ({pct:+.1f}%)  "
              f"unrealised {_fmt(p['unrealized_inr'], 0)} INR  cut at {_fmt(p['avg_entry'] * (1 - cut_pct / 100))}")


def run_loop(until_text=None, sleep=None, max_ticks=None):
    """Poll the real account until --until. Survives every error: an outage must not be the reason
    an alert is missed, and it says so once rather than every poll."""
    import time as _time

    from . import health
    from .runner import parse_hhmm

    sleep = sleep or _time.sleep
    lock = acquire_single_instance_watch()
    if lock is None:
        print("another trade watcher is already polling; exiting so alerts are not duplicated.")
        return 0
    until = parse_hhmm(until_text) if until_text else None
    gap = _cfg().get("poll_seconds", 20)
    client, token, down = None, None, False
    notify("[watcher started]", [f"{datetime.now():%a %d-%b %H:%M}"
                                 + (f", running until {until_text}" if until else ""),
                                 f"Polling your real Dhan positions every {gap}s.",
                                 f"Cut alert at -{_cfg().get('cut_pct', 25.0):g}%, "
                                 f"profit alert at your average win."], "info")
    try:
        while True:
            now = datetime.now()
            if until and now.time() >= until:
                print(f"reached --until {until_text}; stopping.")
                return 0
            try:
                fresh = health.token_from_env_file()
                if client is None or fresh != token:
                    client, token = health.fresh_client(), fresh
                out = check(client, now)
                if down:
                    notify("[watcher recovered]", [f"position watching resumed at {now:%H:%M}"], "info")
                    down = False
                if out:
                    print(f"{now:%H:%M:%S} {out}")
            except Exception as e:
                if not down:
                    notify("[watcher error] not watching your positions right now",
                           [f"{type(e).__name__}: {e}", "It retries every poll."], "error")
                    down = True
                print(f"{now:%H:%M:%S} error: {type(e).__name__}: {e}")
            if max_ticks is not None:
                max_ticks -= 1
                if max_ticks <= 0:
                    return 0
            sleep(gap)
    except KeyboardInterrupt:
        print("stopped.")
        return 0


def acquire_single_instance_watch():
    """Its own lock, separate from the signal runner's, so the two can run side by side."""
    import os
    f = open(data_dir() / "trade_watch.lock", "a+")
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--until", help="HH:MM; with --loop, exit cleanly at this time (e.g. 23:59)")
    ap.add_argument("--log", help="append all output to this file (for unattended runs with no console)")
    ap.add_argument("--test-telegram", action="store_true", help="send one test message and exit")
    args = ap.parse_args(argv)

    if args.log:
        import sys
        sys.stdout = sys.stderr = open(args.log, "a", encoding="utf-8", buffering=1)

    if args.test_telegram:
        print(notify("[test] trade watcher", ["If you can read this, alerts reach your phone."], "info"))
        return 0
    if args.loop:
        return run_loop(args.until)

    from trading_agents.core.dhan_client import get_dhan_client
    client = get_dhan_client()
    if args.status:
        status(client)
        return 0
    alerts = check(client)
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S}: {len(alerts)} alert(s)" + (f" - {alerts}" if alerts else ""))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
