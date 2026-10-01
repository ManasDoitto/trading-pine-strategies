"""Price all 259 A+ v1 (131-symbol) OOS trades against real Dhan option premium history.

Hourly resolution (found more stable than 5-min: `rollingoption`'s intraday series is
genuinely noisy at 5-min, confirmed by direct inspection on 2026-09-29 -- KEI's PE swung
15-20 points bar-to-bar on a smoothly-moving underlying). Flags trades whose entry lands
at/within 1 day of a monthly expiry rollover (ambiguous/atypical contract) separately
rather than silently mixing them in.

Read-only. All Dhan calls go through the shared cross-process rate limiter.
"""
import calendar
import json
import os
import re
import sys
import time
from datetime import timedelta

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from trading_agents.core.dhan_client import wait_for_slot  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
H = {"access-token": os.getenv("DHAN_ACCESS_TOKEN"), "client-id": os.getenv("DHAN_CLIENT_ID"),
     "Content-Type": "application/json"}
URL = "https://api.dhan.co/v2/charts/rollingoption"
IST = "Asia/Kolkata"
SYMFIX = {"GVT_D": "GVT&D"}


def last_thursday(year, month):
    c = calendar.Calendar()
    th = [d for d in c.itermonthdates(year, month) if d.month == month and d.weekday() == 3]
    return th[-1]


def expiry_flags(d):
    this_exp = last_thursday(d.year, d.month)
    py, pm = (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
    prev_exp = last_thursday(py, pm)
    days_since_prev = (d - prev_exp).days
    days_to_this = (this_exp - d).days
    return days_since_prev <= 1 or days_to_this <= 0, days_to_this


def nearest_bar(ts, opens, target_epoch, tol=2100):
    if not ts:
        return None
    idx = min(range(len(ts)), key=lambda i: abs(ts[i] - target_epoch))
    if abs(ts[idx] - target_epoch) > tol:
        return None
    return opens[idx]


def price_one(uni, r):
    sym = SYMFIX.get(r.symbol, r.symbol)
    sid = uni.get(sym, {}).get("secid")
    lot = uni.get(sym, {}).get("lot", 0)
    boundary, dte = expiry_flags(r.entry_dt.date())
    if sid is None:
        return dict(symbol_real=sym, opt_entry=None, opt_exit=None, opt_pct=None,
                    note="no secid", boundary=boundary, dte=dte)
    opt_type = "CALL" if r.dir == 1 else "PUT"
    entry_epoch = pd.Timestamp(r.entry_dt).tz_localize(IST).timestamp()
    exit_epoch = pd.Timestamp(r.exit_dt).tz_localize(IST).timestamp()
    fd = (r.entry_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    td = (r.exit_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    payload = dict(exchangeSegment="NSE_FNO", securityId=sid, instrument="OPTSTK",
                   expiryFlag="MONTH", expiryCode=1, strike="ATM", drvOptionType=opt_type,
                   interval=60, fromDate=fd, toDate=td, requiredData=["open", "timestamp"])
    resp = None
    for attempt in range(3):
        wait_for_slot("data")
        try:
            resp = requests.post(URL, headers=H, json=payload, timeout=30)
            if resp.status_code == 200:
                break
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    if resp is None or resp.status_code != 200:
        return dict(symbol_real=sym, opt_entry=None, opt_exit=None, opt_pct=None,
                    note="http fail", boundary=boundary, dte=dte)
    j = resp.json()
    leg = j.get("data", {}).get("ce" if opt_type == "CALL" else "pe") or {}
    ts_, opens = leg.get("timestamp", []), leg.get("open", [])
    e_px = nearest_bar(ts_, opens, entry_epoch)
    x_px = nearest_bar(ts_, opens, exit_epoch)
    if e_px is None or x_px is None or e_px == 0:
        return dict(symbol_real=sym, opt_entry=e_px, opt_exit=x_px, opt_pct=None,
                    note="missing bar", boundary=boundary, dte=dte)
    opt_pct = (x_px - e_px) / e_px * 100.0
    return dict(symbol_real=sym, opt_entry=e_px, opt_exit=x_px, opt_pct=opt_pct,
                opt_pnl_inr=(x_px - e_px) * lot, lot=lot, note="ok", boundary=boundary, dte=dte)


def main():
    uni = json.load(open(os.path.join(ROOT, "stockopt", "universe.json")))
    t = pd.read_csv(os.path.join(ROOT, "research_data", "stockopt", "oos259_signals.csv"),
                     parse_dates=["entry_dt", "exit_dt"])
    print(f"pricing {len(t)} trades, hourly resolution", flush=True)
    rows = []
    for i, r in t.iterrows():
        res = price_one(uni, r)
        row = dict(r)
        row.update(res)
        rows.append(row)
        if (i + 1) % 25 == 0:
            print(f"  ..{i+1}/{len(t)}", flush=True)
    out = pd.DataFrame(rows)
    out_path = os.path.join(ROOT, "research_data", "stockopt", "oos259_option_pnl.csv")
    out.to_csv(out_path, index=False)
    print(f"\nwrote {out_path}")

    for label, sub in [("ALL 259", out[out.note == "ok"]),
                        ("excl. expiry-boundary", out[(out.note == "ok") & (~out.boundary)])]:
        if not len(sub):
            print(f"{label}: 0 priced")
            continue
        w = sub.opt_pct > 0
        gl = -sub.opt_pct[~w].sum()
        pf = sub.opt_pct[w].sum() / gl if gl > 0 else float("inf")
        print(f"\n--- {label}: {len(sub)} trades ---")
        print(f"option win%={100*w.mean():.1f}  PF={pf:.2f}  avg%/trade={sub.opt_pct.mean():+.3f}  "
              f"total%={sub.opt_pct.sum():+.1f}  total_INR(1lot)={sub.opt_pnl_inr.sum():+,.0f}")
        print(f"underlying win% (same trades) = {100*(sub.R>0).mean():.1f}")
    n_fail = (out.note != "ok").sum()
    print(f"\nfailed to price: {n_fail}/{len(out)}", out.note.value_counts().to_dict())


if __name__ == "__main__":
    main()
