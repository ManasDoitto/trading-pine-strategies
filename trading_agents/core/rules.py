"""Option-buyer rule detectors. Thresholds come from config.toml [rules].

Each detector reads position episodes (core.trades.episodes) and/or FIFO round
trips and returns plain-dict violations so they serialise straight into facts JSON.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta

RULE_TITLES = {
    "R1": "Averaging down into a losing option",
    "R2": "Bought option carried overnight",
    "R3": "Bought option held into expiry days",
    "R4": "Premium stop not respected",
    "R5": "Daily loss limit breached",
    "R6": "Overtrading / revenge entry",
    "R7": "Deep-OTM lottery buy",
    "R8": "Sell-to-open (not option buying)",
    "SCOPE": "Instrument outside the configured scope",
    "DATA": "Fill history incomplete",
}


def _v(rule, severity, ep_or_none, time, detail, inr=None):
    return dict(rule=rule, title=RULE_TITLES[rule], severity=severity,
                symbol=ep_or_none["symbol"] if ep_or_none else None,
                episode_id=ep_or_none.get("id") if ep_or_none else None,
                time=time.isoformat() if time else None, detail=detail,
                inr=round(inr, 2) if inr is not None else None)


def check_all(episodes, round_trips, rules_cfg, as_of, scope=None):
    """as_of: datetime of the check (open positions are judged relative to it)."""
    out = []
    for ep in episodes:
        out += check_episode(ep, rules_cfg, as_of, scope)
    out += check_daily_loss(round_trips, rules_cfg)
    out += check_overtrading(episodes, rules_cfg)
    out.sort(key=lambda v: v["time"] or "")
    return out


def check_episode(ep, cfg, as_of, scope=None):
    out = []
    is_long = ep["direction"] == "LONG"
    closed = ep["status"] == "CLOSED"
    end = ep["close_time"] if closed else as_of
    if not closed and ep["expiry"]:
        end = min(end, datetime.combine(ep["expiry"], time(23, 59)))   # an open option can't outlive expiry

    if scope is not None and ep["underlying"] not in scope:
        out.append(_v("SCOPE", "low", ep, ep["open_time"], f"{ep['underlying']} is not in the configured instruments"))

    if not is_long:
        if ep.get("pre_history"):
            out.append(_v("DATA", "low", ep, ep["open_time"],
                          "Sell with no matching buy near the start of the fill history -- most likely the exit "
                          "of a position bought before the data begins, not a sell-to-open"))
            return out
        out.append(_v("R8", "high", ep, ep["open_time"],
                      f"Opened by SELLING {ep['max_qty']} qty @ avg {ep['avg_entry']:.2f} -- option writing has unlimited risk",
                      ep["net_pnl"]))
        return out

    # R1 averaging down
    against = [a for a in ep["adds"] if a["against"] and a["drop_pct"] <= -cfg["r1_min_drop_pct"]]
    if against:
        prices = " -> ".join(f"{a['px']:g}" for a in against)
        out.append(_v("R1", "high", ep, against[0]["time"],
                      f"Re-bought {len(against)}x below running average (first entry "
                      f"{ep['entries'][0]['px']:g}, adds at {prices}); peak qty {ep['max_qty']}",
                      ep["net_pnl"]))

    # R2 overnight
    carried = end.date() > ep["open_time"].date()
    if cfg.get("r2_enabled", True) and carried:
        days = (end.date() - ep["open_time"].date()).days
        state = "held" if closed else "still open"
        out.append(_v("R2", "medium", ep, ep["open_time"],
                      f"Bought option {state} across {days} night(s)", ep["net_pnl"]))

    # R3 into expiry days
    if ep["expiry"] and carried:
        days_left_at_end = (ep["expiry"] - end.date()).days
        if days_left_at_end <= cfg["r3_expiry_days"]:
            out.append(_v("R3", "high", ep, end,
                          f"Held across sessions to within {max(days_left_at_end, 0)} day(s) of expiry "
                          f"({ep['expiry']:%d-%b-%Y}) -- theta is steepest here", ep["net_pnl"]))

    # R4 premium stop
    if closed and ep["pct"] is not None and ep["pct"] <= -cfg["r4_premium_stop_pct"]:
        sev = "high" if ep["pct"] <= -2 * cfg["r4_premium_stop_pct"] else "medium"
        out.append(_v("R4", sev, ep, ep["close_time"],
                      f"Exited {ep['pct']:.0f}% below average entry premium "
                      f"({ep['avg_entry']:.2f} -> {ep['avg_exit']:.2f}); stop is {cfg['r4_premium_stop_pct']:g}%",
                      ep["net_pnl"]))

    # R7 deep OTM
    otm = ep.get("strikes_otm")
    limit = ep.get("deep_otm_limit") or cfg["r7_max_strikes_otm"]
    if otm is not None and otm >= limit:
        out.append(_v("R7", "medium", ep, ep["open_time"],
                      f"Bought ~{otm:.1f} strikes OTM at entry (limit {limit:g})", ep["net_pnl"]))
    return out


def check_daily_loss(round_trips, cfg):
    by_day = defaultdict(float)
    for rt in round_trips:
        by_day[rt["exit_time"].date()] += rt["net_pnl"]
    out = []
    for day, net in sorted(by_day.items()):
        if net <= -cfg["r5_daily_loss_limit_inr"]:
            out.append(dict(rule="R5", title=RULE_TITLES["R5"], severity="high", symbol=None, episode_id=None,
                            time=f"{day.isoformat()}T23:59:00",
                            detail=f"Realised {net:,.0f} on {day:%d-%b-%Y}; limit is -{cfg['r5_daily_loss_limit_inr']:,}",
                            inr=round(net, 2)))
    return out


def check_overtrading(episodes, cfg):
    out = []
    by_day = defaultdict(list)
    for ep in episodes:
        by_day[ep["open_time"].date()].append(ep)
    for day, eps in sorted(by_day.items()):
        if len(eps) > cfg["r6_max_positions_per_day"]:
            out.append(dict(rule="R6", title=RULE_TITLES["R6"], severity="medium", symbol=None, episode_id=None,
                            time=f"{day.isoformat()}T23:59:00",
                            detail=f"{len(eps)} positions opened on {day:%d-%b-%Y} (max {cfg['r6_max_positions_per_day']})",
                            inr=None))

    closed = sorted((e for e in episodes if e["status"] == "CLOSED"), key=lambda e: e["close_time"])
    window = timedelta(minutes=cfg["r6_revenge_window_minutes"])
    for ep in episodes:
        trigger = next((c for c in reversed(closed)
                        if c is not ep and c["close_time"] <= ep["open_time"] <= c["close_time"] + window
                        and c["net_pnl"] <= -cfg["r6_revenge_loss_inr"]), None)
        if trigger:
            mins = (ep["open_time"] - trigger["close_time"]).total_seconds() / 60
            out.append(_v("R6", "medium", ep, ep["open_time"],
                          f"Opened {mins:.0f} min after closing {trigger['symbol']} for {trigger['net_pnl']:,.0f} (revenge window)",
                          ep["net_pnl"]))
    return out
