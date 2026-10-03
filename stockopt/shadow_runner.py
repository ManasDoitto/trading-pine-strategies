"""Live shadow (paper) trading for the A+ screened (131-symbol) tier. NO ORDERS PLACED.

Runs the exact same tested engine.run_with_open() used throughout research -- not a
reimplementation -- against live Dhan data, so a shadow entry/exit is guaranteed
consistent with everything already verified in this repo (check_scanner.py's 100% match
carries over by construction, since this calls the identical kernel).

    python -m stockopt.shadow_runner            # one live pass, sends real Telegram alerts
    python -m stockopt.shadow_runner --loop      # rescan every 5 min until 15:20, force flat
                                                  # at 15:15 by WALL-CLOCK time (not Dhan's bar
                                                  # data, which lags on recent days -- see
                                                  # working_strategies/StockOptions/README.md)
    python -m stockopt.shadow_runner --replay 2026-09-28   # dry run against a past session --
                                                  # NEVER sends real Telegram alerts, however
                                                  # many historical events it replays
    python -m stockopt.shadow_runner --log path.log   # for pythonw/Task Scheduler runs

Alerts (Telegram, via trading_exec.notify -- same bot/chat already used for Crude/Silver/
BankNifty/Nifty): setup armed, shadow entry, shadow exit, end-of-day summary. Every message
says SIMULATED / no order placed, never "position" -- see memory dhan-is-source-of-truth.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import engine, shadow  # noqa: E402
from stockopt.scan_live import base_signal, fetch, fetch_index, is_aplus, load_spec  # noqa: E402
from trading_exec.notify import notify  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
EOD_WALLCLOCK = (15, 15)  # force flat at this IST wall-clock time, regardless of bar data


def build_cfg(spec):
    cfg = dict(engine.DEFAULTS)
    cfg.update(spec["kernel"])
    cfg.update(spec["aplus"])
    return cfg


_FETCH_CACHE: dict = {}  # symbol -> full dataframe, reused across replay timesteps (no re-fetching)
_INDEX_CACHE: dict = {}
_SKIP_REPORTED: set = set()  # (symbol, entry_dt, dir) ids already logged as capital-blocked once
_ARM_ACTIVE: set = set()  # (symbol, dir) currently in an armed streak, as of the last pass that
# saw them armed -- alerts on the RISING EDGE only (first bar of a streak), not every bar the
# setup keeps re-qualifying with a slightly different trigger/stop (found 2026-10-01: DRREDDY
# fired 4 near-identical Telegram alerts across 4 consecutive bars of the same streak)


def _fetch_index_cached(headers, replay_through):
    import requests
    if replay_through is None:
        return fetch_index(headers)
    if "raw" not in _INDEX_CACHE:
        nf = fetch(requests.Session(), headers, 13, days=10, segment="IDX_I", instrument="INDEX")
        nf["dt"] = nf["dt"].dt.tz_localize(None)
        _INDEX_CACHE["raw"] = nf
    nf = _INDEX_CACHE["raw"]
    return engine.index_returns(nf[nf.dt <= replay_through])


def _fetch_cached(sess, headers, sym, secid, use_cache):
    if use_cache and sym in _FETCH_CACHE:
        return _FETCH_CACHE[sym]
    df = fetch(sess, headers, secid, days=70)
    if df is not None:
        df["dt"] = df["dt"].dt.tz_localize(None)
        if use_cache:
            _FETCH_CACHE[sym] = df
    return df


def one_pass(spec, cfg, now, headers, workers=2, replay_through=None, only=None):
    """One scan+mark pass. replay_through, if given, truncates every symbol's (once-fetched,
    cached) data to that timestamp instead of using live 'now' -- for --replay testing, this
    avoids re-fetching from Dhan on every simulated timestep. `only` restricts to a symbol
    subset, for cheap testing."""
    allow = only if only is not None else spec["aplus"]["symbol_allowlist"]
    index = _fetch_index_cached(headers, replay_through)
    mpct_cache = shadow._margin_pct_map()
    trades_store = shadow.load()
    events = []

    # wall-clock EOD cutoff, computed once per pass (found 2026-10-01: without this, a signal
    # that only clears the capital check at e.g. 15:20 -- after the 15:15 flatten cutoff --
    # would open a brand-new trade just to have it force-closed 5 minutes later, producing a
    # meaningless near-zero-duration "trade" with fake win/loss noise)
    wc = now if replay_through is None else (
        replay_through.tz_localize(IST) if replay_through.tzinfo is None else replay_through)
    hh, mm = EOD_WALLCLOCK
    past_eod = (wc.hour, wc.minute) >= (hh, mm)

    import requests
    sess = requests.Session()
    for sym in allow:
        secid = _secid(sym)
        if secid is None:
            continue
        df = _fetch_cached(sess, headers, sym, secid, use_cache=replay_through is not None)
        if df is None or len(df) < 260:
            continue
        if replay_through is not None:
            df = df[df.dt <= replay_through]
            if len(df) < 260:
                continue
        as_of = df.dt.iloc[-1]
        p = engine.prepare(df, index=index, final_day_complete=False)
        trades, open_pos = engine.run_with_open(p, **cfg)

        # setup armed (not yet filled) -- the SAME base_signal()/is_aplus() mirror the scanner
        # uses, 100%-verified against this exact kernel by check_scanner.py. Alert on the RISING
        # EDGE of a streak only: a base can keep re-qualifying bar after bar with a slightly
        # drifting trigger/stop (found 2026-10-01: DRREDDY fired 4 near-identical alerts across
        # 4 consecutive bars) -- dedupe on (symbol, dir) being newly armed, not on the bar time.
        if open_pos is None:
            i = len(p["c"]) - 1
            d, trig, stop_lvl = base_signal(p, i, cfg)
        else:
            d = 0  # filled -- any armed streak is over regardless of what base_signal reads now
        for other in (1, -1):
            if other != d:
                _ARM_ACTIVE.discard((sym, other))
        if d != 0 and not past_eod:
            arm_key = (sym, d)
            if arm_key not in _ARM_ACTIVE:
                _ARM_ACTIVE.add(arm_key)
                aplus = is_aplus(sym, d, p, i, spec)
                events.append(("ARMED", dict(symbol=sym, dir=d, trigger=trig, stop=stop_lvl,
                                             aplus=aplus, bar=str(p["dt"][i]))))

        open_shadow = next((t for t in trades_store if t["symbol"] == sym and t["status"] == "OPEN"), None)
        # a trade this session already force-closed (e.g. wallclock EOD) must never re-open just
        # because the kernel's own re-simulation still shows it "open" (Dhan's bar data may not
        # have caught up to that close yet) -- check ANY prior trade with this id, not just OPEN ones
        already_seen = open_pos is not None and any(
            t["id"] == shadow.make_id(sym, open_pos["entry_dt"], open_pos["dir"]) for t in trades_store)

        if open_shadow is None and open_pos is not None and not already_seen and not past_eod:
            # a fresh fill since the last pass
            new = shadow.open_trade(sym, open_pos["dir"], open_pos["entry"], open_pos["stop"],
                                    open_pos["target"], open_pos["entry_dt"], open_pos["setup"],
                                    tier="A+ screened", mpct_cache=mpct_cache)
            if new is not None:
                trades_store = shadow.record(new, trades_store)
                events.append(("OPEN", new))
            else:
                # keep retrying every pass (capital may free up later, as it correctly did in
                # testing), but only REPORT it once -- otherwise a capital-blocked signal spams
                # an identical line on every single pass until it either opens or the day ends
                skip_key = shadow.make_id(sym, open_pos["entry_dt"], open_pos["dir"])
                if skip_key not in _SKIP_REPORTED:
                    _SKIP_REPORTED.add(skip_key)
                    events.append(("SKIPPED_NO_CAPITAL", dict(symbol=sym, entry_dt=str(open_pos["entry_dt"]))))

        elif open_shadow is not None and open_pos is None:
            # closed since the last pass -- find the matching just-closed kernel trade for the real
            # exit. Compare PARSED timestamps, not raw strings: engine.run()'s entry_dt is a numpy
            # datetime64 ('2026-09-15T11:10:00.000000000'), shadow's stored copy went through str()
            # at open time in that same raw format, but a naive re-comparison via
            # pd.to_datetime(...).astype(str) renders as '2026-09-15 11:10:00' -- never equal to the
            # original, so the match silently always failed and the trade stayed OPEN forever
            # (found 2026-09-30, LT stuck open across a whole 11-day replay). Parse both sides.
            shadow_entry_ts = pd.Timestamp(open_shadow["entry_dt"])
            match = trades[pd.to_datetime(trades.entry_dt) == shadow_entry_ts]
            if len(match):
                row = match.iloc[-1]
                shadow.close_trade(open_shadow, float(row.exit), row.exit_dt, f"kernel:{int(row.reason)}")
                events.append(("CLOSE", open_shadow))
            # if no match found, leave it open -- the wall-clock EOD check below is the backstop

        elif open_shadow is not None and open_pos is not None:
            # still open -- wall-clock EOD backstop, independent of Dhan's bar-data completeness
            if past_eod:
                last_px = float(p["c"][-1])
                shadow.close_trade(open_shadow, last_px, as_of, "wallclock_EOD")
                events.append(("CLOSE_EOD", open_shadow))

    save_events = [e for e in events if e[0] in ("OPEN", "CLOSE", "CLOSE_EOD")]
    if save_events:
        shadow.save(trades_store)
    return events


_UNIVERSE = None


def _secid(sym):
    global _UNIVERSE
    if _UNIVERSE is None:
        _UNIVERSE = json.load(open(os.path.join(ROOT, "stockopt", "universe.json")))
    return _UNIVERSE.get(sym, {}).get("secid")


def _notify_safe(title, lines, severity):
    try:
        res = notify(title, lines, severity)
        print(f"    [alert] {res}")
    except Exception as e:
        print(f"    [alert] error: {e}")


def report(events, now, alert=False):
    """alert=True sends real Telegram messages -- only ever True for a genuinely live pass.
    Replay/test runs must NEVER set this, however many historical events they replay."""
    print(f"\n=== shadow pass {now:%Y-%m-%d %H:%M} IST ===")
    if not events:
        print("no changes")
    for kind, t in events:
        if kind == "ARMED":
            side = "LONG (buy)" if t["dir"] == 1 else "SHORT (sell)"
            tag = "A+ " if t["aplus"] else ""
            print(f"  ARMED {t['symbol']:12s} {tag}{side}  trigger {t['trigger']:.2f}  stop {t['stop']:.2f}")
            if alert:
                _notify_safe(f"[setup armed] {t['symbol']} {side}", [
                    f"{tag}base breakout forming, bar {t['bar']}",
                    f"trigger {t['trigger']:.2f}  stop {t['stop']:.2f}",
                    "", "No trade yet -- SIMULATED [shadow entry] follows only if the trigger is hit.",
                ], "info")
        elif kind == "OPEN":
            side = "LONG" if t["dir"] == 1 else "SHORT"
            print(f"  OPEN  {t['symbol']:12s} {side:5s} "
                  f"entry {t['entry']:.2f} stop {t['stop']:.2f} target {t['target']:.2f} "
                  f"shares {t['shares']} margin Rs{t['margin_inr']:,.0f} equity Rs{t['equity_at_entry']:,.0f}")
            if alert:
                _notify_safe(f"[shadow entry] {t['symbol']} {side}", [
                    "SIMULATED -- no order was placed, this is a tracked paper trade.",
                    f"entry {t['entry']:.2f}  stop {t['stop']:.2f}  target {t['target']:.2f}",
                    f"{t['shares']} shares, margin Rs{t['margin_inr']:,.0f} (equity Rs{t['equity_at_entry']:,.0f})",
                ], "info")
        elif kind in ("CLOSE", "CLOSE_EOD"):
            print(f"  CLOSE {t['symbol']:12s} {t['exit_reason']:14s} exit {t['exit']:.2f}  "
                  f"P&L Rs{t['pnl_inr']:+,.0f} ({t['pct']:+.2f}%)")
            if alert:
                sev = "info" if t["pnl_inr"] >= 0 else "warning"
                _notify_safe(f"[shadow exit] {t['symbol']} {t['exit_reason']}", [
                    "SIMULATED -- this closes a tracked paper trade, no real order involved.",
                    f"exit {t['exit']:.2f}  P&L Rs{t['pnl_inr']:+,.0f} ({t['pct']:+.2f}%)",
                ], sev)
        elif kind == "SKIPPED_NO_CAPITAL":
            print(f"  SKIP  {t['symbol']:12s} signal fired but insufficient free capital")
            if alert:
                _notify_safe(f"[shadow skipped] {t['symbol']}", [
                    "Signal fired but the simulated account has no free capital for it right now.",
                    "No trade was tracked for this one.",
                ], "warning")
    s = shadow.summary()
    print(f"  equity: Rs{s['equity']:,.0f}  (start Rs{s['starting_capital']:,.0f}, "
          f"realised Rs{s['realised_pnl_inr']:+,.0f})  open={s['open_trades']} closed={s['closed_trades']} "
          f"win%={s['win_pct']}  margin_in_use=Rs{s['margin_in_use']:,.0f}")


_DAILY_SUMMARY_SENT: set = set()  # dates a summary has already gone out for, this process's lifetime


def maybe_daily_summary(now, alert):
    """Once everything's flat after the close, one summary message for the day -- not per pass."""
    if not alert:
        return
    day_key = now.date().isoformat()
    if day_key in _DAILY_SUMMARY_SENT:
        return
    if now.hour * 60 + now.minute < 15 * 60 + 26:
        return
    trades = shadow.load()
    if shadow.open_trades(trades):
        return  # still something open -- not really end of day yet
    today = [t for t in trades if t["status"] == "CLOSED" and str(t["exit_dt"]).startswith(day_key)]
    _DAILY_SUMMARY_SENT.add(day_key)
    if not today:
        return
    s = shadow.summary(trades)
    wins = [t for t in today if t["pnl_inr"] > 0]
    day_pnl = sum(t["pnl_inr"] for t in today)
    _notify_safe(f"[shadow day summary] {day_key}", [
        "SIMULATED trading day summary -- paper trades only, no real orders.",
        f"{len(today)} trade(s), {len(wins)} win(s), today's P&L Rs{day_pnl:+,.0f}",
        f"running equity Rs{s['equity']:,.0f}  (total realised Rs{s['realised_pnl_inr']:+,.0f})",
    ], "info" if day_pnl >= 0 else "warning")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--replay", default=None,
                    help="YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD (inclusive range): dry-run against "
                         "past session(s). A range fetches each symbol ONCE and replays all days "
                         "from that single cached fetch, not once per day.")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", default=None, help="comma list of symbols, for cheap testing")
    ap.add_argument("--log", default=None,
                    help="append all output to this file instead of stdout (for pythonw/Task Scheduler)")
    ap.add_argument("--no-alert", action="store_true",
                    help="live run that still prints/tracks normally but never sends Telegram "
                         "(for manual testing against the real market without alerting)")
    a = ap.parse_args()
    only = a.only.split(",") if a.only else None

    if a.log:
        os.makedirs(os.path.dirname(a.log), exist_ok=True)
        logf = open(a.log, "a", buffering=1, encoding="utf-8")
        sys.stdout = logf
        sys.stderr = logf
    print(f"\n########## shadow_runner start {datetime.now(IST):%Y-%m-%d %H:%M:%S} IST "
          f"(loop={a.loop}, alerts={'off' if a.no_alert else 'on'}) ##########")

    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    headers = {"access-token": os.getenv("DHAN_ACCESS_TOKEN"), "client-id": os.getenv("DHAN_CLIENT_ID"),
               "Content-Type": "application/json"}
    spec = load_spec()
    cfg = build_cfg(spec)

    if a.replay:
        if ":" in a.replay:
            start_s, end_s = a.replay.split(":")
        else:
            start_s = end_s = a.replay
        start = datetime.strptime(start_s, "%Y-%m-%d").date()
        end = datetime.strptime(end_s, "%Y-%m-%d").date()
        days = pd.bdate_range(start, end).date  # trading-day approximation (skips weekends only;
        # a real holiday just replays as an empty/no-data day and is silently skipped below)
        print(f"REPLAY {start} to {end} ({len(days)} weekdays) -- dry run, one fetch per symbol, "
              f"replayed across the whole range from that single cache")
        for day in days:
            found_any = False
            for mins in range(30, 375, 5):  # 09:45 .. 15:45 IST, every 5 min
                t = datetime.combine(day, datetime.min.time()) + timedelta(hours=9, minutes=15 + mins)
                events = one_pass(spec, cfg, None, headers, a.workers, replay_through=pd.Timestamp(t), only=only)
                if events:
                    found_any = True
                    report(events, pd.Timestamp(t, tz=IST))
            if not found_any:
                print(f"{day}: no data / no events (holiday or nothing happened)")
        return

    live_alert = not a.no_alert
    while True:
        now = datetime.now(IST)
        events = one_pass(spec, cfg, now, headers, a.workers, only=only)
        report(events, now, alert=live_alert)
        maybe_daily_summary(now, alert=live_alert)
        if not a.loop or now.hour * 60 + now.minute > 15 * 60 + 20:
            break
        nxt = (now + timedelta(minutes=5)).replace(second=5, microsecond=0)
        nxt = nxt.replace(minute=(nxt.minute // 5) * 5)
        time.sleep(max(5.0, (nxt - datetime.now(IST)).total_seconds()))
    print(f"########## shadow_runner end {datetime.now(IST):%Y-%m-%d %H:%M:%S} IST ##########")


if __name__ == "__main__":
    main()
