"""Dhan fills -> normalised legs -> FIFO round trips + position episodes + stats.

FIFO matching is a function-ised port of the repo-root dhan_trade_analysis.py
(same cost allocation), so results reconcile with that earlier analysis.
"""
from collections import defaultdict, deque
from datetime import datetime

from .option_symbols import from_fill, underlying_of  # noqa: F401  (underlying_of re-exported)

COST_FIELDS = ("sebiTax", "stt", "brokerageCharges", "serviceTax", "exchangeTransactionCharges", "stampDuty")


# ------------------------------------------------------------------ pulling
def _check(r, what):
    if isinstance(r, dict) and r.get("status") == "failure":
        raise RuntimeError(f"Dhan {what} failed: {r.get('remarks')} (token expired? regenerate DHAN_ACCESS_TOKEN in .env)")


def pull_history(client, from_date, to_date, max_pages=100):
    rows = []
    for page in range(max_pages + 1):
        r = client.get_trade_history(from_date=from_date, to_date=to_date, page_number=page)
        if page == 0:
            _check(r, "trade history")
        data = r.get("data") if isinstance(r, dict) else None
        if not data:
            break
        rows.extend(data)
    return rows


def pull_today(client):
    r = client.get_trade_book()
    _check(r, "trade book")
    data = r.get("data") if isinstance(r, dict) else None
    return data if isinstance(data, list) else []


def parse_time(s):
    if not s or s == "NA":
        return None
    try:
        return datetime.fromisoformat(str(s).replace(" ", "T"))
    except ValueError:
        return None


def leg_key(raw):
    t = parse_time(raw.get("exchangeTime"))
    return "_".join(str(x) for x in (raw.get("orderId"), raw.get("exchangeTradeId"),
                                     t.isoformat() if t else raw.get("exchangeTime"),
                                     raw.get("tradedPrice"), raw.get("tradedQuantity")))


def merge_raw(*sources):
    """De-duplicate raw fills across sources. Earlier sources win (pass trade
    history before the trade book: history rows carry the cost fields)."""
    out = {}
    for rows in sources:
        for r in rows or []:
            out.setdefault(leg_key(r), r)
    return list(out.values())


# ------------------------------------------------------------------ legs
def normalize_leg(raw):
    t = parse_time(raw.get("exchangeTime"))
    if t is None:
        return None
    symbol = raw.get("customSymbol") or raw.get("tradingSymbol") or ""
    c = from_fill(raw, t)
    return dict(
        leg_id=leg_key(raw),
        order_id=str(raw.get("orderId")),
        time=t,
        symbol=symbol,
        underlying=c.underlying if c else underlying_of(symbol),
        segment=raw.get("exchangeSegment"),
        instrument=raw.get("instrument"),
        product=raw.get("productType"),
        side=raw["transactionType"],
        qty=int(raw["tradedQuantity"]),
        price=float(raw["tradedPrice"]),
        costs=sum(float(raw.get(f) or 0) for f in COST_FIELDS),
        expiry=c.expiry if c else None,
        strike=c.strike if c else None,
        right=c.right if c else None,
        security_id=str(raw.get("securityId")),
    )


def normalize(raw_rows):
    legs = [l for l in (normalize_leg(r) for r in raw_rows) if l is not None]
    legs.sort(key=lambda l: l["time"])
    return legs


def _contract_fields(leg):
    return dict(symbol=leg["symbol"], underlying=leg["underlying"], right=leg["right"],
                strike=leg["strike"], expiry=leg["expiry"], security_id=leg["security_id"])


# ------------------------------------------------------------------ FIFO
def fifo_match(legs):
    """Returns (round_trips, open_lots). A round trip is one FIFO-matched slice."""
    by_symbol = defaultdict(list)
    for leg in legs:
        by_symbol[leg["symbol"]].append(leg)

    closed, open_lots = [], []
    for sym, sym_legs in by_symbol.items():
        buys, sells = deque(), deque()
        for leg in sym_legs:
            qty, px = leg["qty"], leg["price"]
            cpu = leg["costs"] / qty if qty else 0
            remaining = qty
            same, opposite = (buys, sells) if leg["side"] == "BUY" else (sells, buys)
            while remaining > 0 and opposite:
                o = opposite[0]
                m = min(remaining, o["qty"])
                if leg["side"] == "BUY":      # closing a short
                    side, gross = "SHORT", (o["px"] - px) * m
                else:                         # closing a long
                    side, gross = "LONG", (px - o["px"]) * m
                cost = m * (cpu + o["cpu"])
                hold = (leg["time"] - o["time"]).total_seconds() / 60
                closed.append(dict(
                    **_contract_fields(leg), side=side,
                    entry_time=o["time"], exit_time=leg["time"], qty=m,
                    entry_px=o["px"], exit_px=px, gross_pnl=gross, costs=cost, net_pnl=gross - cost,
                    hold_min=hold,
                    pnl_pts=gross / m if m else 0.0,
                    pct=(gross / m) / o["px"] * 100 if m and o["px"] else 0.0,
                ))
                o["qty"] -= m
                remaining -= m
                if o["qty"] <= 0:
                    opposite.popleft()
            if remaining > 0:
                same.append(dict(qty=remaining, px=px, time=leg["time"], cpu=cpu))
        for q, side in ((buys, "LONG"), (sells, "SHORT")):
            for o in q:
                open_lots.append(dict(**_contract_fields(sym_legs[-1]), side=side,
                                      qty=o["qty"], entry_px=o["px"], entry_time=o["time"]))
    closed.sort(key=lambda c: c["exit_time"])
    return closed, open_lots


# ------------------------------------------------------------------ episodes
def episodes(legs, min_add_gap_minutes=5):
    """Group each symbol's legs into position episodes (flat -> open -> flat).

    Tracks adds to an open position and whether each add was *against* the
    position (below running avg for a long = averaging down). Adds from an
    order within `min_add_gap_minutes` of the previous entry are treated as
    part of the same (sliced) entry.
    """
    by_symbol = defaultdict(list)
    for leg in legs:
        by_symbol[leg["symbol"]].append(leg)

    out = []
    for sym, sym_legs in by_symbol.items():
        pos, ep = 0, None
        for leg in sym_legs:
            signed = leg["qty"] if leg["side"] == "BUY" else -leg["qty"]
            cpu = leg["costs"] / leg["qty"] if leg["qty"] else 0
            while signed != 0:
                if pos == 0:
                    ep = dict(id=f"{sym}@{leg['time']:%Y%m%d%H%M%S}", **_contract_fields(leg),
                              direction="LONG" if signed > 0 else "SHORT",
                              open_time=leg["time"], close_time=None, entries=[], exits=[],
                              adds=[], max_qty=0, costs=0.0, products=set())
                    out.append(ep)
                sign = 1 if ep["direction"] == "LONG" else -1
                if signed * sign > 0:                      # opening / adding
                    q = abs(signed)
                    if ep["entries"]:
                        prev = ep["entries"][-1]
                        avg = _avg(ep["entries"])
                        gap = (leg["time"] - prev["time"]).total_seconds() / 60
                        if leg["order_id"] != prev["order_id"] and gap >= min_add_gap_minutes:
                            against = leg["price"] < avg if sign > 0 else leg["price"] > avg
                            ep["adds"].append(dict(time=leg["time"], qty=q, px=leg["price"],
                                                   avg_before=avg, against=against,
                                                   drop_pct=(leg["price"] / avg - 1) * 100 if avg else 0.0))
                    ep["entries"].append(dict(time=leg["time"], qty=q, px=leg["price"], order_id=leg["order_id"]))
                    ep["costs"] += cpu * q
                    ep["products"].add(leg["product"])
                    pos += signed
                    ep["max_qty"] = max(ep["max_qty"], abs(pos))
                    signed = 0
                else:                                      # reducing / closing
                    m = min(abs(signed), abs(pos))
                    ep["exits"].append(dict(time=leg["time"], qty=m, px=leg["price"]))
                    ep["costs"] += cpu * m
                    pos -= sign * m
                    signed += sign * m
                    if pos == 0:
                        ep["close_time"] = leg["time"]
                        _finalize(ep)
                        ep = None
        if ep is not None:
            _finalize(ep)
    out.sort(key=lambda e: e["open_time"])
    return out


def _avg(fills):
    q = sum(f["qty"] for f in fills)
    return sum(f["qty"] * f["px"] for f in fills) / q if q else 0.0


def _finalize(ep):
    ep["products"] = sorted(p for p in ep["products"] if p)
    ep["avg_entry"] = _avg(ep["entries"])
    ep["avg_exit"] = _avg(ep["exits"]) if ep["exits"] else None
    ep["status"] = "CLOSED" if ep["close_time"] else "OPEN"
    sign = 1 if ep["direction"] == "LONG" else -1
    if ep["status"] == "CLOSED":
        gross = sign * (sum(x["qty"] * x["px"] for x in ep["exits"]) - sum(x["qty"] * x["px"] for x in ep["entries"]))
        ep["gross_pnl"], ep["net_pnl"] = gross, gross - ep["costs"]
        ep["pct"] = sign * (ep["avg_exit"] / ep["avg_entry"] - 1) * 100 if ep["avg_entry"] else 0.0
        ep["hold_min"] = (ep["close_time"] - ep["open_time"]).total_seconds() / 60
        ep["overnight"] = ep["close_time"].date() > ep["open_time"].date()
    else:
        ep["gross_pnl"] = ep["net_pnl"] = ep["pct"] = ep["hold_min"] = None
        ep["overnight"] = None     # decided by the caller relative to "now"
    ep["open_qty"] = sum(x["qty"] for x in ep["entries"]) - sum(x["qty"] for x in ep["exits"])
    ep["dte_at_entry"] = (ep["expiry"] - ep["open_time"].date()).days if ep["expiry"] else None
    ep["adds_against"] = sum(1 for a in ep["adds"] if a["against"])


# ------------------------------------------------------------------ stats
def hold_bucket(minutes):
    if minutes is None:
        return "open"
    if minutes < 5:
        return "<5min"
    if minutes < 30:
        return "5-30min"
    if minutes < 120:
        return "30min-2hr"
    if minutes < 1440:
        return "2hr-1day"
    return ">1day"


def dte_bucket(dte):
    if dte is None:
        return "unknown"
    if dte <= 0:
        return "expiry day"
    if dte <= 2:
        return "1-2d"
    if dte <= 7:
        return "3-7d"
    return ">7d"


def moneyness_bucket(strikes_otm, deep_limit=3):
    """deep_limit = the instrument's R7 threshold, so buckets mean the same thing across instruments."""
    if strikes_otm is None:
        return "unknown"
    if strikes_otm <= -1:
        return "ITM"
    if strikes_otm < 1:
        return "ATM"
    if strikes_otm < deep_limit:
        return "OTM near"
    return "OTM deep"


def summarize(items, pnl_key="net_pnl"):
    vals = [i[pnl_key] for i in items if i.get(pnl_key) is not None]
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]
    loss_sum = abs(sum(losses))
    return dict(
        n=len(vals),
        net=round(sum(vals), 2),
        win_rate=round(100 * len(wins) / len(vals), 1) if vals else None,
        profit_factor=round(sum(wins) / loss_sum, 2) if loss_sum else None,
        avg_win=round(sum(wins) / len(wins), 2) if wins else None,
        avg_loss=round(sum(losses) / len(losses), 2) if losses else None,
    )


def breakdown(items, keyfunc, pnl_key="net_pnl"):
    groups = defaultdict(list)
    for i in items:
        groups[keyfunc(i)].append(i)
    return {str(k): summarize(v, pnl_key) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}
