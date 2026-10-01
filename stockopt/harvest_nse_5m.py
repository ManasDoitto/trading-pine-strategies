"""Harvest 5-minute NSE equity history for the whole stock-options universe from Dhan.

One parquet per symbol in research_data/nse5m/. Resumable: a symbol whose parquet
already covers the requested end date is skipped.

Usage:  python -m stockopt.harvest_nse_5m [--start 2018-01-01] [--workers 3]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "research_data", "nse5m")
UNIVERSE_JSON = os.path.join(ROOT, "stockopt", "universe.json")
SCRIP_MASTER = os.path.join(ROOT, "api-scrip-master.csv")
URL = "https://api.dhan.co/v2/charts/intraday"
IST = timezone(timedelta(hours=5, minutes=30))

sys.path.insert(0, ROOT)
from trading_agents.core.dhan_client import wait_for_slot  # noqa: E402

_lock_print = __import__("threading").Lock()


def log(*a):
    with _lock_print:
        print(*a, flush=True)


# This uses raw REST (not the dhanhq client), but shares the same Dhan account/token as
# trading_exec.runner and trade_watch.py, so it waits on their SAME cross-process clock
# (trading_agents.core.dhan_client.wait_for_slot) rather than a limiter scoped to this
# process alone -- a per-process-only limiter here previously coexisted with a same-bug
# limiter in ReadOnlyDhan and the two processes' in-memory clocks disagreed
# (2026-09-29, DH-904 "breaching rate limits").


def build_universe() -> dict:
    """Underlyings that currently have stock options, mapped to NSE_EQ security ids."""
    df = pd.read_csv(SCRIP_MASTER, low_memory=False)
    opt = df[(df.SEM_EXM_EXCH_ID == "NSE") & (df.SEM_INSTRUMENT_NAME == "OPTSTK")].copy()
    opt["exp"] = pd.to_datetime(opt.SEM_EXPIRY_DATE, errors="coerce")
    opt["und"] = opt.SEM_TRADING_SYMBOL.str.extract(r"^(.+?)-[A-Za-z]{3}\d{4}-")[0]
    live = opt[opt.exp > opt.exp.max() - timedelta(days=95)]
    lots = live.groupby("und").SEM_LOT_UNITS.first().to_dict()
    eq = df[(df.SEM_EXM_EXCH_ID == "NSE") & (df.SEM_INSTRUMENT_NAME == "EQUITY") & (df.SEM_SERIES == "EQ")]
    eqmap = dict(zip(eq.SEM_TRADING_SYMBOL, eq.SEM_SMST_SECURITY_ID))
    uni = {}
    for u in sorted(x for x in live.und.dropna().unique() if "NSETEST" not in x):
        if u in eqmap:
            uni[u] = {"secid": int(eqmap[u]), "lot": int(lots.get(u, 0) or 0)}
    os.makedirs(os.path.dirname(UNIVERSE_JSON), exist_ok=True)
    with open(UNIVERSE_JSON, "w") as f:
        json.dump(uni, f, indent=1)
    return uni


def fetch_batch(sess, headers, secid, fd, td, tries=5):
    payload = {
        "securityId": str(secid),
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "interval": "5",
        "fromDate": fd,
        "toDate": td,
    }
    for attempt in range(tries):
        try:
            wait_for_slot("data")  # shared clock with runner.py / trade_watch.py, not just this process
            r = sess.post(URL, headers=headers, json=payload, timeout=40)
            if r.status_code == 429:
                time.sleep(2 + 3 * attempt)
                continue
            if r.status_code != 200:
                time.sleep(1 + attempt)
                continue
            j = r.json()
            ts = j.get("timestamp") or []
            if not ts:
                return None
            return pd.DataFrame(
                {
                    "ts": ts,
                    "open": j["open"],
                    "high": j["high"],
                    "low": j["low"],
                    "close": j["close"],
                    "volume": j["volume"],
                }
            )
        except Exception:
            time.sleep(1.5 + attempt)
    return None


def harvest_symbol(sym, secid, start, end, headers, throttle):
    path = os.path.join(OUT_DIR, f"{re.sub(r'[^A-Za-z0-9_.-]', '_', sym)}.parquet")
    if os.path.exists(path):
        try:
            old = pd.read_parquet(path)
            if len(old) and old["dt"].max() >= pd.Timestamp(end).tz_localize(IST) - timedelta(days=7):
                return sym, len(old), "cached"
        except Exception:
            old = None
    sess = requests.Session()
    frames = []
    cur = pd.Timestamp(start)
    endts = pd.Timestamp(end)
    while cur <= endts:
        nxt = min(cur + timedelta(days=89), endts)
        df = fetch_batch(sess, headers, secid, cur.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d"))
        if df is not None:
            frames.append(df)
        cur = nxt + timedelta(days=1)
        time.sleep(throttle)
    if not frames:
        return sym, 0, "empty"
    out = pd.concat(frames, ignore_index=True).drop_duplicates("ts").sort_values("ts")
    out["dt"] = pd.to_datetime(out.ts, unit="s", utc=True).dt.tz_convert(IST)
    out = out[(out.dt.dt.time >= pd.Timestamp("09:15").time()) & (out.dt.dt.time <= pd.Timestamp("15:30").time())]
    out = out.reset_index(drop=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    out.to_parquet(path, index=False)
    return sym, len(out), "fetched"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--throttle", type=float, default=0.35)
    ap.add_argument("--only", default=None, help="comma list of symbols")
    args = ap.parse_args()

    load_dotenv(os.path.join(ROOT, ".env"))
    headers = {
        "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
        "client-id": os.getenv("DHAN_CLIENT_ID"),
        "Content-Type": "application/json",
    }
    uni = build_universe()
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        uni = {k: v for k, v in uni.items() if k in want}
    log(f"universe: {len(uni)} symbols  -> {OUT_DIR}")
    os.makedirs(OUT_DIR, exist_ok=True)

    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(harvest_symbol, s, v["secid"], args.start, args.end, headers, args.throttle): s
            for s, v in uni.items()
        }
        for f in as_completed(futs):
            sym, n, how = f.result()
            done += 1
            log(f"[{done}/{len(uni)}] {sym:14s} {n:7d} bars  {how}  ({time.time()-t0:.0f}s)")
    log("HARVEST DONE", time.time() - t0, "s")


if __name__ == "__main__":
    main()
