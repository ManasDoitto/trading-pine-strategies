"""Journal facts: pull Dhan fills (read-only), rebuild round trips / position
episodes, flag option-buyer rule violations, and write

    journal_data/facts/<date>_journal.json   (what the journal agent reads)
    journal_data/trades.csv                  (all FIFO round trips)
    journal_data/episodes.csv                (all position episodes)
    journal_data/fills.json                  (de-duplicated raw fill store)
    journal_data/snapshots/<date>/*.svg      (charts drawn from Dhan 5m bars)

Usage (from repo root):
    python -m trading_agents.facts.journal                        # today, live pull
    python -m trading_agents.facts.journal --date 2026-09-09
    python -m trading_agents.facts.journal --session MCX          # chart MCX underlyings only
    python -m trading_agents.facts.journal --import-file X.json   # seed store from an earlier pull
    python -m trading_agents.facts.journal --no-pull              # stored fills only (bars still fetched)
    python -m trading_agents.facts.journal --offline              # no Dhan calls at all
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from ..core import charts, instruments, rules, trades
from ..core.config import data_dir, load_config
from ..core.dhan_client import get_dhan_client
from ..core.market_data import PriceLookup, intraday_bars

STORE_NAME = "fills.json"
VIOLATION_RULES = ("R1", "R2", "R3", "R4", "R7", "R8")


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"not serialisable: {type(o)}")


# ------------------------------------------------------------------ fill store
def load_store():
    p = data_dir() / STORE_NAME
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_store(rows):
    (data_dir() / STORE_NAME).write_text(json.dumps(rows, indent=1), encoding="utf-8")


def combine_sources(history_rows, book_rows):
    """Trade-history rows carry cost fields and win; trade-book rows (today, no costs)
    are kept only for orders that trade history doesn't have yet."""
    hist = trades.merge_raw(history_rows)
    hist_orders = {str(r.get("orderId")) for r in hist}
    book = [r for r in trades.merge_raw(book_rows) if str(r.get("orderId")) not in hist_orders]
    return hist + book


def refresh_store(client, as_of, import_file=None, pull=True):
    store = load_store()
    hist = [r for r in store if r.get("_src") != "tradebook"]
    book = [r for r in store if r.get("_src") == "tradebook"]
    if import_file:
        with open(import_file, encoding="utf-8") as f:
            hist += [dict(r, _src="history") for r in json.load(f)]
    if pull:
        times = [t for t in (trades.parse_time(r.get("exchangeTime")) for r in hist) if t]
        start = max(times).date() - timedelta(days=3) if times else as_of - timedelta(days=120)
        hist += [dict(r, _src="history") for r in trades.pull_history(client, f"{start}", f"{as_of}")]
        if as_of == date.today():
            book += [dict(r, _src="tradebook") for r in trades.pull_today(client)]
    rows = combine_sources(hist, book)
    save_store(rows)
    return rows


# ------------------------------------------------------------------ enrichment
def attach_moneyness(client, eps):
    """strikes_otm = distance from the underlying at entry, in strike steps (+ = OTM, - = ITM)."""
    inst_cfg = load_config()["instruments"]
    needs, refs = defaultdict(list), {}
    for ep in eps:
        ep.update(strikes_otm=None, otm_pct=None, underlying_at_entry=None, moneyness_source="unavailable",
                  deep_otm_limit=inst_cfg.get(ep["underlying"], {}).get("r7_max_strikes_otm"))
        if client is None or ep["underlying"] not in inst_cfg or not ep["right"] or ep["strike"] is None:
            continue
        ref = instruments.reference_series(ep["underlying"], ep["expiry"])
        if ref is None:
            continue
        gap = inst_cfg[ep["underlying"]].get("future_max_gap_days")
        if ref["expiry"] and gap is not None and ep["expiry"] and (ref["expiry"] - ep["expiry"]).days > gap:
            ep["moneyness_source"] = "underlying future no longer listed"
            continue
        step = instruments.strike_step(ep["underlying"], ep["expiry"]) or instruments.strike_step(ep["underlying"])
        key = (ref["security_id"], ref["segment"], ref["instrument"])
        refs[key] = ref
        needs[key].append((ep, step))

    for key, items in needs.items():
        start = min(ep["open_time"] for ep, _ in items).date()
        end = max(ep["open_time"] for ep, _ in items).date()
        look = PriceLookup(intraday_bars(client, *key, start, end, interval=5), 5)
        for ep, step in items:
            s = look.at(ep["open_time"])
            if s is None or not step:
                ep["moneyness_source"] = "no underlying bar at entry"
                continue
            dist = ep["strike"] - s if ep["right"] == "CE" else s - ep["strike"]
            ep.update(underlying_at_entry=s, strikes_otm=round(dist / step, 2), otm_pct=round(dist / s * 100, 2),
                      moneyness_source=f"{refs[key]['label']} 5m")


def position_view(p, ltp, lot_size=None):
    """Dhan's positions API reports MCX qty in lots and its unrealizedProfit WITHOUT the lot
    multiplier (verified 2026-09-16: netQty 6, multiplier 100, unrealizedProfit -597.8 on a
    -59,780 mark-to-market), so quantity and P&L are recomputed here from the live LTP."""
    mult = float(p.get("multiplier") or 1)
    units = float(p["netQty"]) * mult
    is_long = units > 0
    avg = float((p.get("buyAvg") if is_long else p.get("sellAvg")) or 0)
    pts = None if ltp is None else (ltp - avg) * (1 if is_long else -1)
    return dict(
        symbol=p.get("tradingSymbol"), side="LONG" if is_long else "SHORT",
        qty_units=abs(units), lots=round(abs(units) / lot_size, 2) if lot_size else None,
        avg_entry=round(avg, 2), ltp=ltp,
        pnl_pts=None if pts is None else round(pts, 2),
        unrealized_inr=None if pts is None else round(pts * abs(units), 2),
        product=p.get("productType"), expiry=p.get("drvExpiryDate"), right=p.get("drvOptionType"),
        strike=p.get("drvStrikePrice"),
        carried_forward_units=float(p.get("carryForwardBuyQty") or 0) * mult,
    )


def live_positions(client):
    r = client.get_positions()
    rows = r.get("data") if isinstance(r, dict) else None
    rows = [p for p in (rows if isinstance(rows, list) else []) if p.get("netQty")]
    by_seg = defaultdict(list)
    for p in rows:
        by_seg[p["exchangeSegment"]].append(int(p["securityId"]))
    ltps = {}
    if by_seg:
        q = client.ticker_data(dict(by_seg))
        quotes = ((q.get("data") or {}).get("data") or {}) if isinstance(q, dict) else {}
        for seg, ids in quotes.items():
            for sid, v in ids.items():
                ltps[(seg, str(sid))] = v.get("last_price")
    scope = load_config()["instruments"]
    out = []
    for p in rows:
        und = trades.underlying_of(p.get("tradingSymbol"))
        ls = instruments.lot_size(und) if und in scope else None
        out.append(position_view(p, ltps.get((p["exchangeSegment"], str(p["securityId"]))), ls))
    return out


# ------------------------------------------------------------------ views
def ep_view(ep, with_fills=False):
    v = {k: ep.get(k) for k in (
        "id", "symbol", "underlying", "right", "strike", "expiry", "direction", "status", "expired",
        "open_time", "close_time", "max_qty", "open_qty", "avg_entry", "avg_exit", "net_pnl", "pct",
        "hold_min", "dte_at_entry", "strikes_otm", "otm_pct", "moneyness", "underlying_at_entry", "moneyness_source",
        "adds_against", "products", "costs")}
    v["lots"] = _lots(ep)
    v["entries_count"] = len(ep["entries"])
    v["pnl_pts"] = round(ep["avg_exit"] - ep["avg_entry"], 2) if ep.get("avg_exit") is not None else None
    for k in ("avg_entry", "avg_exit", "net_pnl", "pct", "hold_min", "costs"):
        if isinstance(v[k], float):
            v[k] = round(v[k], 2)
    if with_fills:
        v["entries"] = ep["entries"]
        v["exits"] = ep["exits"]
        v["adds"] = ep["adds"]
    return v


def _lots(ep):
    try:
        ls = instruments.lot_size(ep["underlying"]) if ep["underlying"] in load_config()["instruments"] else None
    except Exception:
        ls = None
    return round(ep["max_qty"] / ls, 2) if ls else None


def violation_cost(violations, eps_by_id, window_ids=None):
    """Per rule: distinct flagged closed episodes and their combined net P&L (INR)."""
    out, flagged = {}, set()
    for rule in VIOLATION_RULES:
        ids = {v["episode_id"] for v in violations if v["rule"] == rule and v["episode_id"]}
        if window_ids is not None:
            ids &= window_ids
        closed = [eps_by_id[i] for i in ids if eps_by_id[i]["status"] == "CLOSED"]
        flagged |= {e["id"] for e in closed}
        out[rule] = dict(episodes=len(ids), net_inr=round(sum(e["net_pnl"] for e in closed), 2))
    pool = [e for e in eps_by_id.values() if e["status"] == "CLOSED" and (window_ids is None or e["id"] in window_ids)]
    out["_clean_episodes"] = trades.summarize([e for e in pool if e["id"] not in flagged])
    out["_flagged_episodes"] = trades.summarize([e for e in pool if e["id"] in flagged])
    return out


def chart_underlyings(session, traded):
    inst = load_config()["instruments"]
    wanted = [u for u in inst if session == "ALL" or (session == "NSE") == inst[u]["option_segment"].startswith("NSE")]
    return [u for u in wanted if u in traded] or [u for u in wanted if u != "SILVERM"]


def build_charts(client, as_of, legs, open_eps, session, traded):
    """SVG charts from Dhan 5m bars (instead of TradingView screenshots): each underlying with
    today's fill times marked, and each option traded or held today with fills at exact prices."""
    if client is None:
        return []
    out_dir = data_dir(f"snapshots/{as_of}")
    day_legs = [l for l in legs if l["time"].date() == as_of]
    last_leg = {l["symbol"]: l for l in legs}
    out = []

    def day_bars(sid, seg, inst):
        b = intraday_bars(client, sid, seg, inst, as_of, as_of, interval=5)
        return b[b["time"].dt.date == as_of]

    def save(name, svg, **info):
        path = out_dir / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', name)}.svg"
        path.write_text(svg, encoding="utf-8")
        out.append(dict(path=path.relative_to(data_dir()).as_posix(), **info))

    for u in chart_underlyings(session, traded):
        u_legs = [l for l in day_legs if l["underlying"] == u]
        symbols = list(dict.fromkeys([l["symbol"] for l in u_legs]
                                     + [e["symbol"] for e in open_eps if e["underlying"] == u]))
        ref = instruments.reference_series(u, last_leg[symbols[0]]["expiry"] if symbols else None)
        bars = day_bars(ref["security_id"], ref["segment"], ref["instrument"]) if ref else None
        if bars is None or bars.empty:
            out.append(dict(underlying=u, kind="underlying", path=None, note=f"no {u} bars for {as_of}"))
        else:
            vl = [dict(time=l["time"], side=l["side"],
                       label=f"{l['side'][0]} {l['strike']:g}{l['right']} @{l['price']:g}") for l in u_legs]
            save(f"{u}_underlying", charts.candles_svg(bars, f"{ref['label']}  5m  {as_of}", vlines=vl),
                 underlying=u, kind="underlying", fills_marked=len(vl))
        for sym in symbols:
            leg = last_leg[sym]
            ob = day_bars(leg["security_id"], leg["segment"], leg["instrument"])
            if ob.empty:
                out.append(dict(underlying=u, kind="option", symbol=sym, path=None,
                                note=f"no premium bars for {as_of} (illiquid or no trades)"))
                continue
            mk = [dict(time=l["time"], price=l["price"], side=l["side"], label=f"{l['side'][0]} {l['qty']}@{l['price']:g}")
                  for l in u_legs if l["symbol"] == sym]
            save(sym, charts.candles_svg(ob, f"{sym}  premium 5m  {as_of}", markers=mk),
                 underlying=u, kind="option", symbol=sym, fills_marked=len(mk))
    return out


# ------------------------------------------------------------------ build
def build(as_of, rows, client, session="ALL"):
    cfg = load_config()
    rcfg = cfg["rules"]
    n_sessions = cfg["journal"]["rolling_sessions"]
    scope = set(cfg["instruments"])

    legs = [l for l in trades.normalize(rows) if l["time"].date() <= as_of]
    rts, _ = trades.fifo_match(legs)
    eps = trades.episodes(legs, rcfg["r1_min_gap_minutes"])
    now = datetime.now()
    as_of_dt = now if as_of == now.date() else datetime.combine(as_of, time(23, 59))
    first_day = legs[0]["time"].date() if legs else None
    for ep in eps:
        ep["expired"] = ep["status"] == "OPEN" and ep["expiry"] is not None and ep["expiry"] < as_of
        # an unmatched sell in the first days of the data is usually the exit of a pre-history buy
        ep["pre_history"] = (ep["direction"] == "SHORT" and ep["status"] == "OPEN" and first_day is not None
                             and (ep["open_time"].date() - first_day).days <= 3)
    attach_moneyness(client, eps)
    for ep in eps:
        ep["moneyness"] = trades.moneyness_bucket(ep["strikes_otm"], ep["deep_otm_limit"] or rcfg["r7_max_strikes_otm"])
    violations = rules.check_all(eps, rts, rcfg, as_of_dt, scope)
    eps_by_id = {e["id"]: e for e in eps}
    closed_eps = [e for e in eps if e["status"] == "CLOSED"]

    def on(t):
        return t is not None and t.date() == as_of

    today_eps = [e for e in eps if on(e["open_time"]) or on(e["close_time"])
                 or (e["status"] == "OPEN" and not e["expired"])]
    today_ids = {e["id"] for e in today_eps}
    today_rts = [r for r in rts if on(r["exit_time"])]
    today_viol = [v for v in violations
                  if (v["episode_id"] in today_ids and v["rule"] != "SCOPE") or (v["time"] or "")[:10] == as_of.isoformat()]

    days = sorted({l["time"].date() for l in legs})     # a session = any day with a fill
    window_days = set([d for d in days if d <= as_of][-n_sessions:])
    window_eps = [e for e in closed_eps if e["close_time"].date() in window_days]
    window_ids = {e["id"] for e in window_eps}
    window_viol = [v for v in violations if v["episode_id"] in window_ids
                   or (v["episode_id"] is None and v["time"] and date.fromisoformat(v["time"][:10]) in window_days)]

    def buckets(items):
        return dict(
            by_hold=trades.breakdown(items, lambda e: trades.hold_bucket(e["hold_min"])),
            by_moneyness=trades.breakdown(items, lambda e: e["moneyness"]),
            by_dte=trades.breakdown(items, lambda e: trades.dte_bucket(e["dte_at_entry"])),
            by_right=trades.breakdown(items, lambda e: e["right"]),
            by_underlying=trades.breakdown(items, lambda e: e["underlying"]),
        )

    def count_by_rule(vs):
        c = defaultdict(int)
        for v in vs:
            c[v["rule"]] += 1
        return dict(sorted(c.items()))

    used_book = any(r.get("_src") == "tradebook" for r in rows)
    expired_open = [e for e in eps if e["expired"]]
    caveats = [
        "P&L is in INR (price x qty, net of Dhan-reported costs); pnl_pts/avg prices are option premium points.",
        "Moneyness uses the underlying 5m bar containing the entry time; MCX options whose underlying future has "
        "expired show 'unknown'.",
        "Dhan trade-history API only reaches back ~3-4 months; older trades are only present if previously stored.",
    ]
    if used_book:
        caveats.append("Some of today's fills come from the trade book, which has no cost fields -- costs are "
                       "filled in once trade history includes them.")
    if expired_open:
        caveats.append(f"{len(expired_open)} position(s) have no exit fill and are past expiry (expired/settled "
                       "outside the fill data); their P&L is NOT in any total.")

    facts = dict(
        kind="journal",
        date=as_of,
        weekday=as_of.strftime("%A"),
        generated_at=now.replace(microsecond=0),
        session=session,
        sources=dict(fills_total=len(rows), legs_used=len(legs), from_trade_book=used_book,
                     first_fill=legs[0]["time"] if legs else None, last_fill=legs[-1]["time"] if legs else None),
        rules_config=dict(rcfg, r7_max_strikes_otm_by_instrument={
            u: c.get("r7_max_strikes_otm", rcfg["r7_max_strikes_otm"]) for u, c in cfg["instruments"].items()}),
        today=dict(
            summary_round_trips=trades.summarize(today_rts),
            summary_episodes=trades.summarize([e for e in today_eps if e["status"] == "CLOSED" and on(e["close_time"])]),
            positions=[ep_view(e, with_fills=True) for e in today_eps],
            violations=today_viol,
            live_positions=live_positions(client) if client is not None and as_of == now.date() else None,
        ),
        rolling=dict(
            sessions=sorted(window_days),
            summary=trades.summarize(window_eps),
            **buckets(window_eps),
            violations_by_rule=count_by_rule(window_viol),
            violation_cost=violation_cost(violations, eps_by_id, window_ids),
        ),
        all_time=dict(
            summary_round_trips=trades.summarize(rts),
            summary_episodes=trades.summarize(closed_eps),
            round_trips_by_underlying=trades.breakdown(rts, lambda r: r["underlying"]),
            **buckets(closed_eps),
            violations_by_rule=count_by_rule(violations),
            violation_cost=violation_cost(violations, eps_by_id),
            worst_episodes=[ep_view(e) for e in sorted(closed_eps, key=lambda e: e["net_pnl"])[:5]],
            best_episodes=[ep_view(e) for e in sorted(closed_eps, key=lambda e: -e["net_pnl"])[:5]],
            expired_without_exit=[ep_view(e) for e in expired_open],
        ),
        open_positions=[ep_view(e) for e in eps if e["status"] == "OPEN" and not e["expired"]],
        charts=build_charts(client, as_of, legs, [e for e in eps if e["status"] == "OPEN" and not e["expired"]],
                            session, {e["underlying"] for e in today_eps}),
        caveats=caveats,
    )
    return facts, rts, eps


def write_outputs(facts, rts, eps):
    facts_path = data_dir("facts") / f"{facts['date']}_journal.json"
    facts_path.write_text(json.dumps(facts, indent=2, default=_json_default), encoding="utf-8")

    rt_cols = ["symbol", "underlying", "right", "strike", "expiry", "side", "entry_time", "exit_time", "qty",
               "entry_px", "exit_px", "pnl_pts", "pct", "gross_pnl", "costs", "net_pnl", "hold_min"]
    with open(data_dir() / "trades.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rt_cols, extrasaction="ignore")
        w.writeheader()
        for r in rts:
            w.writerow({k: round(v, 2) if isinstance(v, float) else v for k, v in r.items()})

    views = [ep_view(e) for e in eps]
    with open(data_dir() / "episodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(views[0].keys()) if views else ["id"])
        w.writeheader()
        w.writerows(views)
    return facts_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--session", choices=["NSE", "MCX", "ALL"], default="ALL")
    ap.add_argument("--import-file")
    ap.add_argument("--no-pull", action="store_true", help="use stored fills; still fetch bars for moneyness")
    ap.add_argument("--offline", action="store_true", help="no Dhan calls at all")
    args = ap.parse_args(argv)

    client = None if args.offline else get_dhan_client()
    rows = refresh_store(client, args.date, args.import_file, pull=not (args.offline or args.no_pull))
    facts, rts, eps = build(args.date, rows, client, args.session)
    path = write_outputs(facts, rts, eps)

    t, a = facts["today"], facts["all_time"]
    print(f"journal facts -> {path}")
    print(f"today {args.date}: {len(t['positions'])} position(s), realised net INR {t['summary_round_trips']['net']:,}, "
          f"{len(t['violations'])} violation(s)")
    print(f"all-time: {a['summary_round_trips']['n']} round trips, net INR {a['summary_round_trips']['net']:,}; "
          f"violations {a['violations_by_rule']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
