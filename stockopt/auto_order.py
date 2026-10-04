"""Order placement for signals you tap "Taking it" on.

REBUILT 2026-10-01 after the first real attempt (IRFC) failed: the original design used
dhanhq.place_super_order to bundle entry+stop+target in one call, but Dhan's Super Order
product only accepts orderType LIMIT or MARKET for its entry leg (confirmed against
https://dhanhq.co/docs/v2/super-order/) -- it cannot express a stop-triggered entry at
all, which is what this strategy's "buy-stop above the base" signal actually is. That
failed locally (a Python TypeError, before any network call), so nothing was ever sent to
Dhan -- but the design itself was wrong, not just one argument.

The real flow now, matching what Dhan's /orders endpoint (place_order) actually supports:
  1. ENTRY:  place_order(order_type=SLM, trigger_price=signal's trigger, price=0) --
             an SL-M order, which DOES support a stop-triggered entry, unlike Super Order.
  2. WAIT for the entry to fill (status TRADED) -- polled, not assumed instant.
  3. Once filled: place TWO separate orders -- a stop-loss (SLM at meta.stop) and a
     target (LIMIT at meta.target). Dhan's plain /orders endpoint has no bracket/OCO
     concept outside Super Order, so this module does the OCO itself: whichever fills
     first, the other gets cancelled on the next poll.
  4. If the entry never fills within the signal's own validity window (3 bars / 15 min),
     the pending entry order is cancelled -- it must not sit live all day.
  5. If a position is still open past 15:15 IST (this strategy's own flatten rule, not
     the broker's generic EOD square-off), both pending exit legs are cancelled and the
     position is flattened with a market order.

Gated by stockopt/order_config.json's "live_orders_enabled" -- ships False, and nothing in
this codebase ever flips it. While False, a "taken" decision builds the entry payload and
sends a preview; nothing reaches Dhan. When live, two more safety rails apply
automatically:
  trial_mode_orders_left -- the first N live entries (config default 3) are forced to
    QUANTITY 1, so the whole mechanism gets proven with negligible money before your real
    position size is ever used.
  max_orders_per_day -- a hard ceiling (config default 5) on new entries placed per day.

poll_live_orders() must be called regularly (every pass of both decision_poller.py's
30-second loop and scan_live.py's 5-minute loop) -- it is what advances every state above,
not just handle_taken_signal(), which only ever places the initial entry order.

Storage (gitignored, research_data/stockopt/):
  orders_dryrun.json   -- every preview, whether or not live orders were ever enabled
  live_orders.json     -- every REAL entry this module has placed, and its full lifecycle
  .order_day_count.json -- today's placed-entry count, for the daily cap
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

from dhanhq import dhanhq

from trading_exec.notify import notify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "research_data", "stockopt")
DRYRUN_FILE = os.path.join(DATA_DIR, "orders_dryrun.json")
LIVE_ORDERS_FILE = os.path.join(DATA_DIR, "live_orders.json")
DAY_COUNT_FILE = os.path.join(DATA_DIR, ".order_day_count.json")
CONFIG_FILE = os.path.join(ROOT, "stockopt", "order_config.json")
UNIVERSE_FILE = os.path.join(ROOT, "stockopt", "universe.json")

EOD_FLATTEN_WALLCLOCK = (15, 15)       # same cutoff the strategy was backtested against
ENTRY_VALIDITY_MINUTES = 15            # "valid for the next 3 bars" = 3 x 5-min bars
FILLED_STATUSES = {"TRADED"}
DEAD_STATUSES = {"REJECTED", "CANCELLED", "EXPIRED"}


# --------------------------------------------------------------------------- #
# config / small state files
# --------------------------------------------------------------------------- #
def load_order_config() -> dict:
    cfg = dict(live_orders_enabled=False, trial_mode_orders_left=3, max_orders_per_day=5)
    if os.path.exists(CONFIG_FILE):
        cfg.update(json.load(open(CONFIG_FILE)))
    return cfg


def _save_order_config(cfg: dict):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    os.replace(tmp, CONFIG_FILE)


def _atomic_write(path, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=str)
    os.replace(tmp, path)


def _load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def _secid(symbol: str) -> str | None:
    uni = json.load(open(UNIVERSE_FILE))
    v = uni.get(symbol)
    return str(v["secid"]) if v else None


def _today_order_count() -> int:
    d = _load(DAY_COUNT_FILE, {})
    return d.get("count", 0) if d.get("date") == date.today().isoformat() else 0


def _increment_today_order_count():
    _atomic_write(DAY_COUNT_FILE, {"date": date.today().isoformat(), "count": _today_order_count() + 1})


def _save_dryrun(record: dict):
    rows = _load(DRYRUN_FILE, [])
    rows.append(record)
    _atomic_write(DRYRUN_FILE, rows)


def _save_live_rows(rows: list):
    _atomic_write(LIVE_ORDERS_FILE, rows)


def _extract_order_id(resp) -> tuple[str | None, str]:
    """Dhan's place_order can hand back shapes other than the nested-dict happy path this
    code originally assumed -- found 2026-10-01 when a real call crashed on `.get()` against
    a response that wasn't the expected dict (never confirmed exactly what it was, since the
    crash happened before anything got logged). Never raise here: an unparseable response
    must count as a failure to place, not an unhandled exception that hides whether a real
    order went through."""
    if resp is None:
        return None, "no response"
    if isinstance(resp, str):
        return None, resp
    if not isinstance(resp, dict):
        return None, f"unexpected response type: {type(resp).__name__}"
    data = resp.get("data")
    order_id = None
    if isinstance(data, dict):
        order_id = data.get("orderId")
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        order_id = data[0].get("orderId")
    if order_id is None:
        order_id = resp.get("orderId")
    status = str(resp.get("status", "")).lower()
    return order_id, status


# --------------------------------------------------------------------------- #
# preview (dry-run) path -- unchanged in spirit, now describes the ENTRY only
# --------------------------------------------------------------------------- #
def build_entry_payload(meta: dict, quantity: int | None = None) -> dict | None:
    secid = _secid(meta["symbol"])
    if secid is None:
        return None
    is_long = meta["dir"] == 1
    return dict(
        security_id=secid,
        exchange_segment="NSE_EQ",
        transaction_type=dhanhq.BUY if is_long else dhanhq.SELL,
        quantity=quantity if quantity is not None else meta["shares"],
        order_type=dhanhq.SLM,
        product_type=dhanhq.INTRA,
        price=0.0,
        trigger_price=meta["trigger"],
        tag=f"{meta['symbol']}{meta['bar'].replace(':', '')}{meta['date'].replace('-', '')[2:]}"[:20],
    )


def _preview_lines(payload: dict, meta: dict, note: str = "") -> list[str]:
    side = "BUY" if payload["transaction_type"] == dhanhq.BUY else "SELL"
    lines = [
        f"{side} {payload['quantity']} {meta['symbol']} -- SL-M entry trigger {meta['trigger']:.2f}",
        f"(stop {meta['stop']:.2f} and target {meta['target']:.2f} would follow as separate "
        f"orders once the entry fills)  product INTRADAY",
        f"risking Rs{meta['risk_rupees']:,.0f}",
    ]
    if note:
        lines.append(note)
    lines.append("DRY RUN -- nothing was sent to Dhan. This is exactly what WOULD be sent.")
    return lines


# --------------------------------------------------------------------------- #
# dispatcher called once per newly-"taken" decision -- places ONLY the entry
# --------------------------------------------------------------------------- #
def handle_taken_signal(decision_row: dict) -> dict:
    meta = decision_row["meta"]
    cfg = load_order_config()
    at = datetime.now().replace(microsecond=0).isoformat()

    if not cfg["live_orders_enabled"]:
        payload = build_entry_payload(meta)
        record = dict(signal_id=decision_row["signal_id"], meta=meta, payload=payload,
                     live=False, placed_order_id=None, at=at)
        if payload is None:
            record["error"] = f"no security id found for {meta['symbol']}"
            notify(f"[order error] {meta['symbol']}", [record["error"]], "warning")
        else:
            notify(f"[order preview] {meta['symbol']}", _preview_lines(payload, meta), "info")
        _save_dryrun(record)
        return record

    if _today_order_count() >= cfg["max_orders_per_day"]:
        payload = build_entry_payload(meta)
        record = dict(signal_id=decision_row["signal_id"], meta=meta, payload=payload,
                     live=False, placed_order_id=None, at=at,
                     note=f"daily cap ({cfg['max_orders_per_day']}) reached -- NOT placed")
        notify(f"[order capped] {meta['symbol']}", _preview_lines(
            payload, meta, f"Daily cap of {cfg['max_orders_per_day']} live entries already reached today."
        ), "warning")
        _save_dryrun(record)
        return record

    trial = cfg["trial_mode_orders_left"] > 0
    qty = 1 if trial else meta["shares"]
    payload = build_entry_payload(meta, quantity=qty)
    if payload is None:
        record = dict(signal_id=decision_row["signal_id"], meta=meta, payload=None,
                     live=True, placed_order_id=None, at=at,
                     error=f"no security id found for {meta['symbol']}")
        notify(f"[order error] {meta['symbol']}", [record["error"]], "warning")
        _save_dryrun(record)
        return record

    from stockopt import live_dhan
    try:
        resp = live_dhan.get_live_client().place_order(**payload)
    except Exception as e:
        record = dict(signal_id=decision_row["signal_id"], meta=meta, payload=payload,
                     live=True, placed_order_id=None, at=at, error=f"{type(e).__name__}: {e}")
        notify(f"[order FAILED] {meta['symbol']}", [
            f"Tried to place a REAL entry order and it failed: {type(e).__name__}: {e}",
            f"{payload['transaction_type']} {payload['quantity']} {meta['symbol']}, trigger {meta['trigger']:.2f}",
            "No order is believed to be open -- verify in your Dhan app before assuming otherwise.",
        ], "error")
        _save_dryrun(record)
        return record

    order_id, resp_status = _extract_order_id(resp)
    ok = bool(order_id) and resp_status != "failure"
    record = dict(signal_id=decision_row["signal_id"], meta=meta, payload=payload,
                 live=True, placed_order_id=order_id, trial=trial, raw_response=resp, at=at)
    if ok:
        if trial:
            cfg["trial_mode_orders_left"] -= 1
            _save_order_config(cfg)
        _increment_today_order_count()
        live_rows = _load(LIVE_ORDERS_FILE, [])
        live_rows.append(dict(
            signal_id=decision_row["signal_id"], symbol=meta["symbol"], security_id=payload["security_id"],
            dir=meta["dir"], qty=payload["quantity"], meta=meta, status="entry_pending",
            entry_order_id=order_id, entry_placed_at=at, stop_order_id=None, target_order_id=None,
            trial=trial, date=meta["date"],
        ))
        _save_live_rows(live_rows)
        notify(f"[LIVE entry placed] {meta['symbol']}" + (" (trial size)" if trial else ""), [
            f"{payload['transaction_type']} {payload['quantity']} {meta['symbol']} -- "
            f"SL-M trigger {meta['trigger']:.2f}, order id {order_id}",
            "Waiting for this to FILL before stop-loss and target orders are placed -- "
            "you'll get another message once that happens.",
            "This is a REAL order." + (f"  ({cfg['trial_mode_orders_left']} trial order(s) left after this)"
                                       if trial else ""),
        ], "info")
    else:
        notify(f"[entry rejected] {meta['symbol']}", [
            f"Dhan response: {resp}",
            "No order appears to be open -- verify in your Dhan app.",
        ], "warning")
    _save_dryrun(record)
    return record


# --------------------------------------------------------------------------- #
# the continuous poll: advances entry_pending -> open -> closed, and the EOD
# flatten -- must be called regularly, not just in reaction to new decisions
# --------------------------------------------------------------------------- #
def poll_live_orders(now_ist) -> list[dict]:
    rows = _load(LIVE_ORDERS_FILE, [])
    todays = [r for r in rows if r["date"] == date.today().isoformat()
             and r["status"] in ("entry_pending", "open")]
    if not todays:
        return []

    from stockopt import live_dhan
    from trading_agents.core.dhan_client import get_dhan_client
    c = get_dhan_client()
    changed = []

    for r in todays:
        if r["status"] == "entry_pending":
            _poll_entry(r, c, live_dhan, now_ist, changed)
        elif r["status"] == "open":
            _poll_open(r, c, live_dhan, now_ist, changed)

    if changed:
        _save_live_rows(rows)
    return changed


def _order_status(c, order_id) -> str:
    resp = c.get_order_by_id(order_id)
    if not isinstance(resp, dict):
        return ""
    data = resp.get("data")
    if isinstance(data, list) and data:
        data = data[0]
    return str((data or {}).get("orderStatus", "")).upper() if isinstance(data, dict) else ""


def _poll_entry(r, c, live_dhan, now_ist, changed):
    meta = r["meta"]
    try:
        status = _order_status(c, r["entry_order_id"])
    except Exception as e:
        print(f"    [order poll] {r['symbol']} entry status check failed: {e}")
        return

    if status in FILLED_STATUSES:
        is_long = r["dir"] == 1
        exit_side = dhanhq.SELL if is_long else dhanhq.BUY
        secid = r["security_id"]
        try:
            stop_resp = live_dhan.get_live_client().place_order(
                security_id=secid, exchange_segment="NSE_EQ", transaction_type=exit_side,
                quantity=r["qty"], order_type=dhanhq.SLM, product_type=dhanhq.INTRA,
                price=0.0, trigger_price=meta["stop"])
            target_resp = live_dhan.get_live_client().place_order(
                security_id=secid, exchange_segment="NSE_EQ", transaction_type=exit_side,
                quantity=r["qty"], order_type=dhanhq.LIMIT, product_type=dhanhq.INTRA,
                price=meta["target"])
            r["stop_order_id"], stop_status = _extract_order_id(stop_resp)
            r["target_order_id"], target_status = _extract_order_id(target_resp)
            if r["stop_order_id"] is None or r["target_order_id"] is None:
                notify(f"[EXIT ORDER PARTIAL] {r['symbol']}", [
                    f"stop order id: {r['stop_order_id']} ({stop_status})  "
                    f"target order id: {r['target_order_id']} ({target_status})",
                    "At least one exit leg may not have gone through -- check your Dhan app now.",
                ], "error")
            r["status"] = "open"
            r["filled_at"] = datetime.now().replace(microsecond=0).isoformat()
            notify(f"[LIVE entry filled] {r['symbol']}", [
                f"Entry filled. Stop-loss ({meta['stop']:.2f}) and target ({meta['target']:.2f}) "
                f"orders are now live, {r['qty']} shares each.",
                "Whichever fills first, the other will be cancelled automatically.",
            ], "info")
        except Exception as e:
            notify(f"[EXIT ORDER FAILED] {r['symbol']}", [
                f"Entry filled but placing stop/target failed: {type(e).__name__}: {e}",
                "You have a REAL open position with NO stop-loss or target live right now -- "
                "go set one manually in your Dhan app.",
            ], "error")
            r["status"] = "open_unprotected"
        changed.append(r)
    elif status in DEAD_STATUSES:
        r["status"] = "entry_failed"
        r["entry_final_status"] = status
        notify(f"[entry did not fill] {r['symbol']}", [f"Entry order ended as {status} -- no position opened."], "warning")
        changed.append(r)
    else:
        placed_at = datetime.fromisoformat(r["entry_placed_at"])
        if datetime.now() - placed_at > timedelta(minutes=ENTRY_VALIDITY_MINUTES):
            try:
                live_dhan.cancel_order(r["entry_order_id"])
                r["status"] = "entry_cancelled"
                notify(f"[entry expired] {r['symbol']}", [
                    f"Entry never filled within {ENTRY_VALIDITY_MINUTES} min (the signal's own "
                    "validity window) -- cancelled.",
                ], "warning")
                changed.append(r)
            except Exception as e:
                print(f"    [order poll] {r['symbol']} entry cancel failed: {e}")


def _poll_open(r, c, live_dhan, now_ist, changed):
    meta = r["meta"]
    try:
        stop_status = _order_status(c, r["stop_order_id"]) if r["stop_order_id"] else ""
        target_status = _order_status(c, r["target_order_id"]) if r["target_order_id"] else ""
    except Exception as e:
        print(f"    [order poll] {r['symbol']} exit status check failed: {e}")
        return

    hit, cancel_id, other_name = None, None, None
    if stop_status in FILLED_STATUSES:
        hit, cancel_id, other_name = "stop", r["target_order_id"], "target"
    elif target_status in FILLED_STATUSES:
        hit, cancel_id, other_name = "target", r["stop_order_id"], "stop"

    if hit:
        if cancel_id:
            try:
                live_dhan.cancel_order(cancel_id)
            except Exception as e:
                print(f"    [order poll] {r['symbol']} cancel {other_name} failed: {e}")
        r["status"] = "closed_by_bracket"
        r["closed_reason"] = hit
        r["closed_at"] = datetime.now().replace(microsecond=0).isoformat()
        notify(f"[LIVE exit] {r['symbol']} hit {hit}", [
            f"{hit.upper()} filled, the other exit order was cancelled.",
            "Real P&L will show up via the capital sync on the next pass.",
        ], "info")
        changed.append(r)
        return

    hh, mm = EOD_FLATTEN_WALLCLOCK
    if (now_ist.hour, now_ist.minute) < (hh, mm):
        return
    for oid in (r["stop_order_id"], r["target_order_id"]):
        if oid:
            try:
                live_dhan.cancel_order(oid)
            except Exception as e:
                print(f"    [order poll] {r['symbol']} EOD cancel failed: {e}")
    is_long = r["dir"] == 1
    try:
        resp = live_dhan.get_live_client().place_order(
            security_id=r["security_id"], exchange_segment="NSE_EQ",
            transaction_type=dhanhq.SELL if is_long else dhanhq.BUY,
            quantity=r["qty"], order_type=dhanhq.MARKET, product_type=dhanhq.INTRA, price=0.0)
        r["status"] = "flattened_eod"
        r["flatten_response"] = resp
        notify(f"[EOD flatten] {r['symbol']}", [
            f"Flattened {r['qty']} {r['symbol']} by market order at the 15:15 IST cutoff.",
        ], "info")
    except Exception as e:
        notify(f"[EOD FLATTEN FAILED] {r['symbol']}", [
            f"Tried to flatten a still-open REAL position and it failed: {type(e).__name__}: {e}",
            "ACT MANUALLY IN YOUR DHAN APP NOW -- this position may still be open.",
        ], "error")
        r["status"] = "flatten_failed"
    r["closed_at"] = datetime.now().replace(microsecond=0).isoformat()
    changed.append(r)


def has_open_live_orders_today() -> bool:
    rows = _load(LIVE_ORDERS_FILE, [])
    return any(r["status"] in ("entry_pending", "open", "open_unprotected")
              and r["date"] == date.today().isoformat() for r in rows)
