"""Stand-alone fast poller for the "Taking it" / "Skipping" Telegram buttons.

Runs independently of the heavy 5-minute signal scanner (scan_live.py), checking every
30 seconds instead -- added 2026-10-01 once live order placement meant a tap-to-order
lag mattered (a signal's entry trigger is only valid for 3 bars / 15 minutes, so waiting
up to 5 minutes just to notice you'd already decided was real, avoidable slippage risk).

Safe to run at the same time as scan_live.py's own (redundant, slower) polling --
telegram_decisions.poll_decisions() is file-locked, so whichever process checks first
simply consumes the update; the other sees nothing new.

    python -m stockopt.decision_poller --loop            # every 30s until 15:30 IST
    python -m stockopt.decision_poller --loop --until 13:30
    python -m stockopt.decision_poller --log path.log
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stockopt import auto_order, telegram_decisions  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


def one_check() -> int:
    decided = telegram_decisions.poll_decisions()
    for d in decided:
        sym = d["meta"].get("symbol", "?")
        print(f"    [decision] {sym}: {d['decision']}")
        if d["decision"] == "taken":
            try:
                rec = auto_order.handle_taken_signal(d)
                print(f"    [order] {'LIVE' if rec['live'] else 'dry-run'} "
                      f"{rec.get('error', rec['payload'])}")
            except Exception as e:
                print(f"    [order] failed: {e}")
    now = datetime.now(IST)
    try:
        moved = auto_order.poll_live_orders(now)
        for r in moved:
            print(f"    [order poll] {r['symbol']}: {r['status']}")
    except Exception as e:
        print(f"    [order poll] failed: {e}")
    return len(decided)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--until", default="15:30", help="HH:MM IST wall-clock to stop at")
    ap.add_argument("--log", default=None)
    a = ap.parse_args()

    if a.log:
        os.makedirs(os.path.dirname(a.log), exist_ok=True)
        logf = open(a.log, "a", buffering=1, encoding="utf-8")
        sys.stdout = logf
        sys.stderr = logf

    until_h, until_m = (int(x) for x in a.until.split(":"))
    print(f"\n########## decision_poller start {datetime.now(IST):%Y-%m-%d %H:%M:%S} IST "
          f"(loop={a.loop}, interval={a.interval}s, until={a.until}) ##########")

    consecutive_errors = 0
    while True:
        now = datetime.now(IST)
        try:
            one_check()
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            print(f"    [poll error] {type(e).__name__}: {e}  ({consecutive_errors} in a row)")
            if consecutive_errors >= 10:
                print("10 consecutive poll failures -- stopping.")
                break
        if not a.loop or (now.hour, now.minute) >= (until_h, until_m):
            break
        time.sleep(a.interval)

    print(f"########## decision_poller end {datetime.now(IST):%Y-%m-%d %H:%M:%S} IST ##########")


if __name__ == "__main__":
    main()
