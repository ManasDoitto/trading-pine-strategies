"""Session-close facts for option buying. Per instrument:
- what the session did (OHLC, gap, range vs ATR, where it closed against this morning's levels)
- which v4.0 signals fired, and how the simulated trades ended
- what the ATM options did through the day (premium path, IV at the close vs this morning)
- your own trades from the journal, and whether they lined up with the strategy's signals

Writes journal_data/facts/<date>_session_close.json.

Usage (repo root):
    python -m trading_agents.facts.session_close                  # today, all instruments
    python -m trading_agents.facts.session_close --session MCX    # crude + silver only
    python -m trading_agents.facts.session_close --date 2026-09-15
"""
import argparse
import json
import sys
import traceback
from datetime import date, datetime, time, timedelta

from ..core import instruments, levels, options, signals
from ..core.config import data_dir, load_config
from ..core.dhan_client import get_dhan_client
from ..core.market_data import intraday_bars
from .premarket import rounded

SIDE_FOR_RIGHT = {"CE": "LONG", "PE": "SHORT"}


def load_facts(date_, kind):
    path = data_dir("facts") / f"{date_}_{kind}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def session_summary(day_bars, prior):
    """prior = the pre-market `underlying` block (levels/pivots/ATR) or None."""
    if day_bars.empty:
        return dict(available=False, note="no bars for this session yet")
    o, h = float(day_bars["open"].iloc[0]), float(day_bars["high"].max())
    l, c = float(day_bars["low"].min()), float(day_bars["close"].iloc[-1])
    rng = h - l
    prev_close = (prior or {}).get("prev_day", {}).get("close")
    atr = (prior or {}).get("atr14")
    piv = (prior or {}).get("pivots") or {}
    tp = (day_bars["high"] + day_bars["low"] + day_bars["close"]) / 3
    vol = day_bars["volume"].sum()
    out = dict(
        available=True, bars=len(day_bars),
        first_bar=day_bars["time"].iloc[0], last_bar=day_bars["time"].iloc[-1],
        open=o, high=h, low=l, close=c, range=rng,
        close_position_pct=(c - l) / rng * 100 if rng else None,
        change_pts=c - o, change_pct=(c / o - 1) * 100 if o else None,
        vwap=float((tp * day_bars["volume"]).sum() / vol) if vol else None,
        volume=float(vol),
    )
    if prev_close:
        out.update(gap_pts=o - prev_close, gap_pct=(o / prev_close - 1) * 100,
                   change_vs_prev_close_pts=c - prev_close)
    if atr:
        out.update(range_vs_atr=rng / atr, move_vs_atr=(c - o) / atr)
    if piv:
        out.update(closed_above_pivot=c > piv["P"], touched_r1=h >= piv["R1"], touched_s1=l <= piv["S1"],
                   closed_above_prev_high=c > (prior or {}).get("prev_day", {}).get("high", float("inf")),
                   closed_below_prev_low=c < (prior or {}).get("prev_day", {}).get("low", float("-inf")))
    return out


def strategy_session(bars, scfg, day):
    """v4.0 signals and simulated trades belonging to `day`."""
    if not scfg:
        return dict(modelled=False, available=False,
                    note="BANKNIFTY v0.4 (EMA pullback + 15m ADX gate) is not modelled in Python yet")
    if len(bars) < signals.WARMUP_BARS + 50:
        return dict(modelled=True, available=False, note=f"only {len(bars)} 5m bars of history")
    df = signals.v40_frame(bars, scfg)
    trades, pos, pending = signals.simulate(df, scfg)
    today = df[df["time"].dt.date == day]
    fired = [dict(time=r["time"], side="LONG" if r["ok_l"] else "SHORT", close=r["close"],
                  risk_pts=r["risk_l"] if r["ok_l"] else r["risk_s"],
                  option_for_buyer="CE" if r["ok_l"] else "PE")
             for r in today.to_dict("records") if r["ok_l"] or r["ok_s"]]
    day_trades = [signals._trade_view(t) for t in trades if t["entry_time"].date() == day]
    flips = today[today["flip_up"] | today["flip_dn"]]
    return dict(
        modelled=True, available=True, approximate=True, name=scfg["name"], rr=scfg["rr"],
        signals=fired, flips=int(len(flips)),
        trades=day_trades, trades_net_pts=sum(t.get("pnl_pts", 0) for t in day_trades),
        wins=sum(1 for t in day_trades if t.get("pnl_pts", 0) > 0),
        open_at_close=signals._trade_view(pos, float(df["close"].iloc[-1])) if pos else None,
        pending_at_close=signals._trade_view(pending) if pending else None,
    )


def option_path(client, underlying, expiry, strike, right, day):
    """What one option's premium did during the session."""
    c = instruments.option_contract(underlying, expiry, strike, right)
    if not c:
        return dict(strike=strike, right=right, available=False, note="contract not in the scrip master")
    bars = intraday_bars(client, c["security_id"], c["segment"], c["instrument"], day, day, interval=5)
    bars = bars[bars["time"].dt.date == day]
    if bars.empty:
        return dict(strike=strike, right=right, available=False, note="no premium bars for this session")
    o, c_ = float(bars["open"].iloc[0]), float(bars["close"].iloc[-1])
    return dict(strike=strike, right=right, available=True, symbol=c["label"], bars=len(bars),
                open=o, high=float(bars["high"].max()), low=float(bars["low"].min()), close=c_,
                change_pts=c_ - o, change_pct=(c_ / o - 1) * 100 if o else None,
                max_gain_pts=float(bars["high"].max()) - o, max_drawdown_pts=float(bars["low"].min()) - o,
                volume=float(bars["volume"].sum()))


def user_session_trades(journal, day, underlying):
    """Your fills for this instrument today, from the journal facts."""
    if not journal:
        return dict(available=False, note="no journal facts for this date -- run /journal first")
    positions = [p for p in journal["today"]["positions"] if p["underlying"] == underlying]
    entries = [dict(time=e["time"], qty=e["qty"], px=e["px"], symbol=p["symbol"], right=p["right"],
                    strike=p["strike"], side=SIDE_FOR_RIGHT.get(p["right"]))
               for p in positions for e in p.get("entries", []) if str(e["time"])[:10] == str(day)]
    return dict(available=True, positions=positions, entries_today=entries,
                violations=[v for v in journal["today"]["violations"] if v.get("symbol") in {p["symbol"] for p in positions}
                            or v.get("symbol") is None])


def alignment(entries, fired, window_minutes):
    """Did your entries line up with a v4.0 signal (same direction, within the window)?"""
    if not entries:
        return dict(entries=0, note="no entries today")
    out, matched = [], 0
    for e in entries:
        t = datetime.fromisoformat(str(e["time"]))
        near = [s for s in fired
                if abs((datetime.fromisoformat(str(s["time"])) - t).total_seconds()) <= window_minutes * 60]
        same = [s for s in near if s["side"] == e["side"]]
        matched += bool(same)
        out.append(dict(entry_time=e["time"], symbol=e["symbol"], your_side=e["side"],
                        matching_signal=same[0]["time"] if same else None,
                        opposite_signal_nearby=bool(near) and not same))
    return dict(entries=len(entries), matched_a_signal=matched, window_minutes=window_minutes, detail=out)


def instrument_facts(client, u, day, cfg, premarket, journal):
    pcfg, scfg_all = cfg["session_close"], cfg.get("strategy", {})
    pm = ((premarket or {}).get("instruments") or {}).get(u, {})
    prior = pm.get("underlying") if pm.get("available") else None

    exps = instruments.option_expiries(u, day)
    expiry = date.fromisoformat(pm["options"]["nearest"]["expiry"]) if pm.get("options") else (exps[0] if exps else None)
    ref = instruments.reference_series(u, expiry)
    if ref is None:
        return dict(available=False, note="no underlying contract listed")
    bars = intraday_bars(client, ref["security_id"], ref["segment"], ref["instrument"],
                         day - timedelta(days=pcfg["history_days"]), day, interval=5)
    day_bars = bars[bars["time"].dt.date == day]
    sess = session_summary(day_bars, prior)
    if not prior and not day_bars.empty:                      # no pre-market file: derive levels here
        prior = levels.level_summary(bars, day)
        sess = session_summary(day_bars, prior if prior.get("available") else None)

    strat = strategy_session(bars[bars["time"].dt.date <= day], scfg_all.get(u), day)
    user = user_session_trades(journal, day, u)
    align = alignment(user.get("entries_today", []), strat.get("signals", []), pcfg["signal_match_minutes"])

    opts = dict(expiry=expiry)
    if expiry and sess.get("available"):
        step = instruments.strike_step(u, expiry) or instruments.strike_step(u)
        atm = pm["options"]["nearest"].get("atm_strike") if pm.get("options") else None
        if atm is None and step:
            atm = round(sess["open"] / step) * step
        opts["atm_strike"] = atm
        if atm:
            opts["ce"] = option_path(client, u, expiry, atm, "CE", day)
            opts["pe"] = option_path(client, u, expiry, atm, "PE", day)
        if day == date.today():
            chain = options.chain_snapshot(client, u, expiry, datetime.combine(day, time(23, 59)),
                                           cfg["premarket"], sess.get("close"))
            opts["chain_at_close"] = chain
            pm_iv = (pm.get("options") or {}).get("nearest", {}).get("atm_iv")
            if pm_iv and chain.get("atm_iv") and chain.get("usable"):
                opts["atm_iv_premarket"] = pm_iv
                opts["atm_iv_change"] = chain["atm_iv"] - pm_iv
        else:
            opts["chain_at_close"] = dict(usable=False,
                                          flags=["option chain is live data only; not available for a past date"])
    return dict(available=True, reference=dict(label=ref["label"], expiry=ref["expiry"]),
                session=sess, prior_levels=prior, strategy=strat, options=opts,
                user_trades=user, alignment=align)


def build(client, day, session="ALL", only=None):
    cfg = load_config()
    premarket, journal = load_facts(day, "premarket"), load_facts(day, "journal")
    per = {}
    for u, icfg in cfg["instruments"].items():
        is_nse = icfg["option_segment"].startswith("NSE")
        if session != "ALL" and (session == "NSE") != is_nse:
            continue
        if only and u not in only:
            continue
        try:
            per[u] = instrument_facts(client, u, day, cfg, premarket, journal)
        except Exception as e:
            traceback.print_exc()
            per[u] = dict(available=False, note=f"error building facts: {e}")
    return rounded(dict(
        kind="session_close", date=day, weekday=day.strftime("%A"), session=session,
        generated_at=datetime.now().replace(microsecond=0),
        instruments=per,
        context=dict(
            premarket_available=premarket is not None,
            journal_available=journal is not None,
            journal_summary=(journal or {}).get("today", {}).get("summary_round_trips"),
            journal_violations=(journal or {}).get("today", {}).get("violations"),
            rolling_no_rule_break=((journal or {}).get("rolling", {}).get("violation_cost") or {}).get("_clean_episodes"),
            rolling_with_rule_break=((journal or {}).get("rolling", {}).get("violation_cost") or {}).get("_flagged_episodes"),
        ),
        caveats=[
            "Session OHLC is built from 5m bars of the futures contract underlying the nearest option expiry "
            "(the index for BANKNIFTY); MCX's official settlement close can differ from the last traded price.",
            "v4.0 signals and trades are a Python port on Dhan bars -- approximate, and they ignore whether the "
            "real strategy was already in a position before this session. BANKNIFTY v0.4 is not modelled.",
            "Option premium paths are the ATM strike chosen this morning; they are not your own fills.",
            "Alignment only checks direction and timing against v4.0 signals; it is not a judgement of the trade.",
        ],
    ))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--session", choices=["NSE", "MCX", "ALL"], default="ALL")
    ap.add_argument("--only")
    args = ap.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None

    facts = build(get_dhan_client(), args.date, args.session, only)
    path = data_dir("facts") / f"{args.date}_session_close.json"
    path.write_text(json.dumps(facts, indent=2), encoding="utf-8")
    print(f"session-close facts -> {path}")
    for u, f in facts["instruments"].items():
        if not f.get("available") or not f["session"].get("available"):
            print(f"  {u}: {f.get('note') or f['session'].get('note')}")
            continue
        s, st = f["session"], f["strategy"]
        print(f"  {u}: O {s['open']} H {s['high']} L {s['low']} C {s['close']} ({s.get('change_pct')}%), "
              f"range {s.get('range_vs_atr')}x ATR | v4.0 signals {len(st.get('signals', []))} "
              f"trades {len(st.get('trades', []))} net {round(st.get('trades_net_pts', 0), 1)} pts | "
              f"your entries {f['alignment'].get('entries', 0)} (matched {f['alignment'].get('matched_a_signal', 0)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
