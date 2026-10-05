"""Live scanner for the Stocks-in-Play MA Base Breakout.

The scan itself is still read only -- it places no orders. Whether a "Taking it" button
tap results in a real order is entirely stockopt/auto_order.py's call, gated by
order_config.json's live_orders_enabled (ships False). While that's False, this is exactly
as read-only as the docstring used to claim outright.

Every run pulls the last ~45 sessions of 5m bars for the whole stock-options universe
from Dhan, applies exactly the backtested rules to the last COMPLETED bar, and prints
armed setups ranked by catalyst strength:

    python -m stockopt.scan_live            # one scan now
    python -m stockopt.scan_live --loop     # re-scan at every 5m close until 13:20 IST,
                                              # then keep checking (no new entries) until
                                              # any REAL order placed today is flattened

Signal lines read: LONG (buy) / SHORT (sell) -- this strategy trades the underlying stock
directly, never an option. Each line gives the trigger price (buy-stop above / sell-stop
below the base), the stop and the 3R target. A trigger is valid for the next 3 bars only,
and never after 13:15.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import auto_order, capital_sync, engine, position_calc, shadow, telegram_decisions  # noqa: E402
from trading_agents.core.dhan_client import wait_for_slot  # noqa: E402
from trading_exec.notify import notify  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
SPEC = os.path.join(ROOT, "stockopt", "strategy_v1.json")
UNIVERSE = os.path.join(ROOT, "stockopt", "universe.json")
URL = "https://api.dhan.co/v2/charts/intraday"

# (symbol, dir, YYYY-MM-DD) -> True: sent an alert for this symbol+direction today.
# Keyed by day so it auto-expires overnight without any explicit reset.
# This is a DAILY dedup, not a per-pass one: once WIPRO LONG fires today it never fires
# again today even if the setup disappears for a bar and reappears. The old per-pass
# _ARM_ACTIVE cleared on every "no signals" pass, so a re-arming symbol would alert again
# and again, flooding the user with duplicate signals.
_ALERTED_TODAY: dict = {}

# This scanner does not go through the dhanhq client (raw REST, so it can batch NSE_EQ
# requests its own way), but it shares the same Dhan account/token as trading_exec.runner
# and trade_watch.py -- so it must wait on the SAME cross-process clock they use
# (trading_agents.core.dhan_client.wait_for_slot), not a limiter scoped to this process
# alone. A per-process-only limiter here previously coexisted with a same-bug limiter in
# ReadOnlyDhan and the two processes' in-memory clocks disagreed (2026-09-29, DH-904).


def load_spec() -> dict:
    return json.load(open(SPEC))


def rel_strength(p: dict, i: int) -> float:
    """Stock's since-open % move minus NIFTY's, at bar i's close (long-positive)."""
    return (p["c"][i] / p["day_open"][i] - 1.0) * 100.0 - p["n_ret"][i]


def is_aplus(sym: str, d: int, p: dict, i: int, spec: dict) -> bool:
    """A+ = the rel-strength gate AND the symbol is on the backtested allowlist.
    Both conditions are required -- this must match exactly what final_eval.py measured,
    or the live A+ tag stops meaning what the dashboard says it means."""
    allow = spec["aplus"].get("symbol_allowlist")
    if allow is not None and sym not in allow:
        return False
    return d * rel_strength(p, i) >= spec["aplus"]["rs_min"]


def base_signal(p: dict, i: int, cfg: dict) -> tuple[int, float, float]:
    """Mirror of the kernel's base-breakout branch evaluated at bar i's close.

    Returns (direction, trigger, stop); direction 0 when there is no setup.
    Kept line-for-line with engine.simulate so live and backtest agree
    (checked by stockopt/check_scanner.py).
    """
    a = p["atr"][i]
    if a <= 0:
        return 0, 0.0, 0.0
    m = p["mod"][i]
    if m < cfg["entry_from"] or m > cfg["entry_to"]:
        return 0, 0.0, 0.0
    c, ema, sma = p["c"][i], p["ema_f"][i], p["sma_m"][i]
    slope = (sma - p["sma_m"][i - cfg["slope_lb"]]) / a
    L = ema > sma and cfg["slope_min"] <= slope <= cfg["slope_max"]
    S = ema < sma and -cfg["slope_max"] <= slope <= -cfg["slope_min"]
    if cfg["use_daily"]:
        L = L and p["d_close"][i] > p["d_sma20"][i]
        S = S and p["d_close"][i] < p["d_sma20"][i]
    if cfg.get("use_rvol", 0):
        L = L and p["rvol"][i] >= cfg["rvol_min"]
        S = S and p["rvol"][i] >= cfg["rvol_min"]
    if cfg.get("rs_min", -99.0) > -50.0:
        rsv = rel_strength(p, i)
        L = L and rsv >= cfg["rs_min"]
        S = S and -rsv >= cfg["rs_min"]
    ext = (c - sma) / a
    if ext > cfg["ext_max"]:
        L = False
    if -ext > cfg["ext_max"]:
        S = False
    if not (L or S):
        return 0, 0.0, 0.0
    n = cfg["bo_n"]
    bh = p["h"][i - n + 1: i + 1].max()
    bl = p["l"][i - n + 1: i + 1].min()
    if bh - bl > cfg["bo_tight"] * a:
        return 0, 0.0, 0.0
    if L and bl <= ema + cfg["bo_zone"] * a and bh >= sma:
        px = bh + engine.TICK
        stp = bl - cfg["stop_buf"] * a
        if px - stp < cfg["min_risk_atr"] * a:
            stp = px - cfg["min_risk_atr"] * a
        return 1, px, stp
    if S and bh >= ema - cfg["bo_zone"] * a and bl <= sma:
        px = bl - engine.TICK
        stp = bh + cfg["stop_buf"] * a
        if stp - px < cfg["min_risk_atr"] * a:
            stp = px + cfg["min_risk_atr"] * a
        return -1, px, stp
    return 0, 0.0, 0.0


def fetch(sess, headers, secid, days=70, segment="NSE_EQ", instrument="EQUITY", tries=3):
    to = datetime.now(IST).date()
    fr = to - timedelta(days=days)
    payload = {
        "securityId": str(secid), "exchangeSegment": segment, "instrument": instrument,
        "interval": "5", "fromDate": fr.strftime("%Y-%m-%d"), "toDate": to.strftime("%Y-%m-%d"),
    }
    for attempt in range(tries):
        wait_for_slot("data")  # shared clock with runner.py / trade_watch.py, not just this process
        r = sess.post(URL, headers=headers, timeout=30, json=payload)
        if r.status_code == 429:
            time.sleep(2.0 * (attempt + 1))  # back off hard and let the shared quota recover
            continue
        break
    j = r.json()
    if not j.get("timestamp"):
        return None
    df = pd.DataFrame({k: j[k] for k in ("open", "high", "low", "close", "volume")})
    df["dt"] = pd.to_datetime(j["timestamp"], unit="s", utc=True).tz_convert(IST)
    t = df.dt.dt.time
    return df[(t >= pd.Timestamp("09:15").time()) & (t <= pd.Timestamp("15:25").time())].reset_index(drop=True)


def fetch_index(headers) -> pd.DataFrame:
    """NIFTY 50 (Dhan IDX_I security 13) since-open returns, for the relative-strength gate."""
    nf = fetch(requests.Session(), headers, 13, days=10, segment="IDX_I", instrument="INDEX")
    nf["dt"] = nf["dt"].dt.tz_localize(None)
    return engine.index_returns(nf)


def scan_one(sym, secid, headers, spec, now, index):
    cfg = dict(engine.DEFAULTS)
    cfg.update(spec["kernel"])
    try:
        df = fetch(requests.Session(), headers, secid)
    except Exception as e:  # network hiccup: skip the symbol this round
        return {"symbol": sym, "error": str(e)}
    if df is None or len(df) < 260:
        return None
    # drop a still-forming bar: a 5m bar is complete once now >= its open + 5 minutes
    if df.dt.iloc[-1] + timedelta(minutes=5) > now:
        df = df.iloc[:-1]
    p = engine.prepare(df, index=index)
    i = len(df) - 1
    if p["dt"][i].astype("datetime64[D]") != np.datetime64(now.date()):
        return None
    gap = float(p["gap"][i])
    orvol = float(p["orvol"][i])
    f = spec["day_filter"]
    in_play = abs(gap) >= f["gap_min"] and orvol >= f["orvol_min"]
    d, px, stp = base_signal(p, i, cfg)
    out = {"symbol": sym, "gap": gap, "orvol": orvol, "in_play": in_play,
           "heat": min(abs(gap), 8) * min(orvol, 8), "close": float(p["c"][i]),
           "bar": str(pd.Timestamp(p["dt"][i]).time())[:5], "dir": d}
    if d != 0:
        out["aplus"] = is_aplus(sym, d, p, i, spec)
        risk = abs(px - stp)
        out.update(trigger=round(px, 2), stop=round(stp, 2),
                   target=round(px + d * cfg["rr"] * risk, 2),
                   risk_pct=round(risk / px * 100, 2))
    return out


def scan(spec, workers=2):
    load_dotenv(os.path.join(ROOT, ".env"))
    headers = {"access-token": os.getenv("DHAN_ACCESS_TOKEN"), "client-id": os.getenv("DHAN_CLIENT_ID"),
               "Content-Type": "application/json"}
    uni = json.load(open(UNIVERSE))
    now = datetime.now(IST)
    index = fetch_index(headers)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(lambda kv: scan_one(kv[0], kv[1]["secid"], headers, spec, now, index), uni.items()))
    rows = [r for r in res if r and "error" not in r]
    errs = [r for r in res if r and "error" in r]
    df = pd.DataFrame(rows)
    return df, errs, now


def _notify_safe(title, lines, severity):
    try:
        res = notify(title, lines, severity)
        print(f"    [alert] {res}")
    except Exception as e:
        print(f"    [alert] error: {e}")


def report(df, errs, now, spec, alert=False):
    """alert=True sends real Telegram messages for newly-armed setups -- only for a genuinely
    live pass. Replay must NEVER set this."""
    top_n = spec["day_filter"].get("top_n", 0)
    print(f"\n=== MA Base Breakout scan  {now:%Y-%m-%d %H:%M} IST  ({len(df)} symbols, {len(errs)} errors) ===")
    if alert:
        try:
            decided = telegram_decisions.poll_decisions()
            for d in decided:
                print(f"    [decision] {d['meta'].get('symbol', '?')}: {d['decision']}")
                if d["decision"] == "taken":
                    try:
                        rec = auto_order.handle_taken_signal(d)
                        print(f"    [order] {'LIVE' if rec['live'] else 'dry-run'} "
                              f"{rec.get('error', rec['payload'])}")
                    except Exception as e:
                        print(f"    [order] failed: {e}")
        except Exception as e:
            print(f"    [decision poll] failed: {e}")
        try:
            moved = auto_order.poll_live_orders(now)
            for r in moved:
                print(f"    [order poll] {r['symbol']}: {r['status']}")
        except Exception as e:
            print(f"    [order poll] failed: {e}")
    if df.empty:
        print("no data (market closed or holiday?)")
        return
    play = df[df.in_play].sort_values("heat", ascending=False)
    if top_n:
        play = play.head(top_n)
    print(f"stocks in play: {len(play)}   " +
          ", ".join(f"{r.symbol}({r.gap:+.1f}%/{r.orvol:.1f}x)" for r in play.head(15).itertuples()))
    sig = play[play.dir != 0]
    if sig.empty:
        print("no armed base breakouts on the last completed bar")
        return
    print("\nARMED (valid for the next 3 bars, cancel after 13:15, flat by 15:15):")
    sig = sig.sort_values(["aplus", "heat"], ascending=False)
    mpct_cache = shadow._margin_pct_map()
    if alert:
        try:
            sync = capital_sync.sync_capital()
            print(f"    [capital] Rs{sync['capital']:,.0f}  "
                  f"(baseline Rs{sync['baseline_capital']:,.0f} {sync['realized_pnl']:+,.0f} "
                  f"realized, {sync['fills_matched']} real closes matched)")
        except Exception as e:
            print(f"    [capital] sync failed, using last known value: {e}")
    pos_cfg = position_calc.load_config()
    today_str = now.strftime("%Y-%m-%d")
    for r in sig.itertuples():
        side = "LONG (buy)   " if r.dir == 1 else "SHORT (sell)"
        side = ("A+ " if r.aplus else "   ") + side
        word = "buy-stop above" if r.dir == 1 else "sell-stop below"
        pos = position_calc.calc_position(r.trigger, r.stop, r.symbol, mpct_cache=mpct_cache)
        print(f"  {r.symbol:12s} {side}  underlying {word} {r.trigger:>9.2f}  stop {r.stop:>9.2f}  "
              f"target {r.target:>9.2f}  risk {r.risk_pct:.2f}%   gap {r.gap:+.2f}%  vol {r.orvol:.1f}x  bar {r.bar}  "
              f"-- {pos['shares']} shares (Rs{pos['risk_rupees']:,.0f} risk)")
        daily_key = (r.symbol, r.dir, today_str)
        if not r.aplus:
            print(f"    [no alert: not A+, audit-only]")
            continue
        if alert and daily_key not in _ALERTED_TODAY:
            _ALERTED_TODAY[daily_key] = True
            sid = telegram_decisions.signal_id(r.symbol, r.dir, r.bar, now.strftime("%Y%m%d"))
            meta = dict(symbol=r.symbol, dir=r.dir, trigger=r.trigger, stop=r.stop, target=r.target,
                       shares=pos["shares"], risk_rupees=pos["risk_rupees"], bar=r.bar,
                       date=now.strftime("%Y-%m-%d"))
            res = telegram_decisions.send_signal_with_buttons(f"[signal] {r.symbol} {side.strip()}", [
                f"Place a real {word} order at {r.trigger:.2f}, stop {r.stop:.2f}, target {r.target:.2f}",
                f"Size: {pos['shares']} shares (risking Rs{pos['risk_rupees']:,.0f}, "
                f"{pos['risk_frac']:.1%} of Rs{pos['capital']:,.0f} capital) -- "
                f"notional Rs{pos['notional_rupees']:,.0f}, est. margin Rs{pos['margin_rupees']:,.0f}",
                f"gap {r.gap:+.2f}%  vol {r.orvol:.1f}x  bar {r.bar}",
                "Valid for the next 3 bars, cancel unfilled after 13:15, flatten by 15:15.",
                "This is a signal only -- no order has been placed for you. Sizing uses "
                "stockopt/position_config.json -- keep its capital figure updated yourself.",
            ], sid, meta)
            print(f"    [alert] {res}")
        else:
            print(f"    [alert already sent today, not re-alerting]")


def replay_one(sym, secid, headers, spec, day, index):
    """Every bar of a past session where the scanner would have printed a setup."""
    cfg = dict(engine.DEFAULTS)
    cfg.update(spec["kernel"])
    df = fetch(requests.Session(), headers, secid, days=(datetime.now(IST).date() - day).days + 70)
    if df is None:
        return []
    df = df[df.dt.dt.date <= day].reset_index(drop=True)
    if len(df) < 260:
        return []
    p = engine.prepare(df, index=index)
    f = spec["day_filter"]
    out = []
    for i in np.flatnonzero(p["dt"].astype("datetime64[D]") == np.datetime64(day)):
        if not (abs(p["gap"][i]) >= f["gap_min"] and p["orvol"][i] >= f["orvol_min"]):
            continue
        d, px, stp = base_signal(p, i, cfg)
        if d:
            out.append({"symbol": sym, "bar": str(pd.Timestamp(p["dt"][i]).time())[:5],
                        "side": "LONG" if d == 1 else "SHORT",
                        "aplus": is_aplus(sym, d, p, i, spec),
                        "trigger": round(px, 2), "stop": round(stp, 2),
                        "target": round(px + d * cfg["rr"] * abs(px - stp), 2),
                        "gap": round(float(p["gap"][i]), 2), "orvol": round(float(p["orvol"][i]), 2)})
    return out


def replay(spec, day, workers=2):
    load_dotenv(os.path.join(ROOT, ".env"))
    headers = {"access-token": os.getenv("DHAN_ACCESS_TOKEN"), "client-id": os.getenv("DHAN_CLIENT_ID"),
               "Content-Type": "application/json"}
    uni = json.load(open(UNIVERSE))
    index = fetch_index(headers)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(lambda kv: replay_one(kv[0], kv[1]["secid"], headers, spec, day, index), uni.items()))
    rows = [r for rs in res for r in rs]
    print(f"\n=== replay {day}: {len(rows)} signal bars ===")
    if rows:
        print(pd.DataFrame(rows).sort_values(["bar", "symbol"]).to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--replay", default=None, help="YYYY-MM-DD: list the signals of a past session")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--log", default=None,
                     help="append all output to this file instead of stdout (for pythonw/Task Scheduler runs)")
    ap.add_argument("--no-alert", action="store_true",
                     help="live run that still prints/logs normally but never sends Telegram "
                          "(for manual testing against the real market without alerting)")
    a = ap.parse_args()

    if a.log:
        os.makedirs(os.path.dirname(a.log), exist_ok=True)
        logf = open(a.log, "a", buffering=1, encoding="utf-8")
        sys.stdout = logf
        sys.stderr = logf

    spec = load_spec()
    print(f"\n########## scan_live start {datetime.now(IST):%Y-%m-%d %H:%M:%S} IST"
          f"  (loop={a.loop}) ##########")
    if a.replay:
        replay(spec, datetime.strptime(a.replay, "%Y-%m-%d").date(), a.workers)
        return
    misses = 0
    consecutive_errors = 0
    while True:
        now = datetime.now(IST)
        try:
            df, errs, now = scan(spec, a.workers)
            report(df, errs, now, spec, alert=not a.no_alert)
            consecutive_errors = 0
            if df.empty or (len(df) < 20):
                # market holiday, feed outage, or run outside trading hours -- don't spin for hours
                misses += 1
                if misses >= 2:
                    print("no data on two consecutive scans -- stopping (holiday or feed down?)")
                    break
            else:
                misses = 0
        except Exception as e:
            # a single bad pass (Dhan hiccup, transient bug) must never silently kill alerting
            # for the whole rest of the day -- found 2026-10-01 while reviewing concurrency risk
            # with the other live strategies sharing this Dhan account: log it, tell the user,
            # keep going; only give up after several in a row.
            consecutive_errors += 1
            print(f"    [pass error] {type(e).__name__}: {e}")
            if not a.no_alert:
                _notify_safe("[scanner error]", [
                    f"A scan pass failed: {type(e).__name__}: {e}",
                    f"consecutive failures: {consecutive_errors}/6 -- will keep retrying.",
                ], "warning")
            if consecutive_errors >= 6:
                if not a.no_alert:
                    _notify_safe("[scanner stopped]", [
                        "6 consecutive pass failures -- stopping for today instead of spinning.",
                        "Check research_data/stockopt/scan_live.log for the real error.",
                    ], "warning")
                print("6 consecutive pass failures -- stopping.")
                break
        if not a.loop or now.hour * 60 + now.minute > 13 * 60 + 20:
            break
        nxt = (now + timedelta(minutes=5)).replace(second=5, microsecond=0)
        nxt = nxt.replace(minute=(nxt.minute // 5) * 5)
        time.sleep(max(5.0, (nxt - datetime.now(IST)).total_seconds()))

    # Entry window (09:45-13:15) is over -- no new signals matter now. But if any REAL
    # order was placed today, it still needs explicit flattening by 15:15 IST (this
    # strategy's own rule, not left to the broker's generic EOD square-off timing), so
    # keep a lightweight watch going instead of just exiting. Skipped entirely on a replay
    # or a --no-alert test run, and does nothing if live orders were never enabled.
    if a.loop and not a.no_alert:
        while auto_order.has_open_live_orders_today():
            now = datetime.now(IST)
            if now.hour * 60 + now.minute > 15 * 60 + 25:
                print("    [eod watch] past 15:25 with orders still marked open -- "
                      "check your Dhan app directly, stopping the watch.")
                break
            try:
                changed = auto_order.poll_live_orders(now)
                for r in changed:
                    print(f"    [eod watch] {r['symbol']}: {r['status']}")
            except Exception as e:
                print(f"    [eod watch] error: {e}")
            nxt = (now + timedelta(minutes=5)).replace(second=5, microsecond=0)
            nxt = nxt.replace(minute=(nxt.minute // 5) * 5)
            time.sleep(max(5.0, (nxt - datetime.now(IST)).total_seconds()))

    print(f"########## scan_live end {datetime.now(IST):%Y-%m-%d %H:%M:%S} IST ##########")


if __name__ == "__main__":
    main()
