"""Research simulator for the v4.0 family on harvested TradingView bars (research_data/bars/*.csv).

Why a separate module: the production simulate() (trading_agents/core/signals.py) drives live alerts and shadow
exits and must not change. It also omits two things TradingView's Strategy Tester applies - commission and gap
fills - and has no time stop. This module reuses production's indicator frame (v40_frame) so the SIGNALS are
identical, and re-implements only the fill/exit loop with those additions, switchable so they can be measured.

Everything is in POINTS (price units per 1 unit, as the repo's audit dashboard reports).
"""
from pathlib import Path

import pandas as pd

from trading_agents.core import signals as v40

BARS = Path(__file__).resolve().parents[1] / "research_data" / "bars"
WARMUP = 400                                    # TradingView audit scripts start counting at bar 400


def load(name):
    """research_data/bars/<name>_5m.csv -> DataFrame with naive-IST `time`, as v40_frame expects."""
    df = pd.read_csv(BARS / f"{name}_5m.csv")
    df["time"] = pd.to_datetime(df["time"], unit="s") + pd.Timedelta(hours=5, minutes=30)
    return df[["time", "open", "high", "low", "close", "volume"]]


def simulate(df, p, start=WARMUP, gap_fills=True, commission=0.0002, time_stop_min=None, flat_at=None, max_per_day=None, be_at_r=None, trail_start_r=None, trail_dist_r=1.0,
             cooldown_bars=None, reversal_exit=False):
    """Bracket strategy with next-bar-open fills, as production simulate() does, plus:
    gap_fills   a bar that OPENS beyond the stop/target exits at that open (TradingView), not at the level
    commission  fraction of price charged per side (0.0002 = the Pine scripts' 0.02%)
    time_stop_min  exit at the OPEN of the first bar once this many minutes have passed since the fill
    be_at_r / trail_start_r / trail_dist_r  breakeven and trailing stop, in units of the original risk; a new stop
                applies from the NEXT bar (no same-bar lookahead)
    max_per_day  stop taking new signals after this many per calendar day
    flat_at     "HH:MM": exit at the OPEN of the first bar at/after this time; no entry is filled at/after it
    cooldown_bars   after an SL exit, no new entry is armed for this many bars (round 7)
    reversal_exit   if True, an opposite-direction ok_l/ok_s signal while a position is open forces an exit
                at that bar's OPEN before any new position is considered (round 7)
    Returns a list of trade dicts with `net` (points, after commission)."""
    rows = df.to_dict("records")
    limit = p.get("day_loss_limit_pts") or 0
    flat = None
    if flat_at:
        hh, mm = flat_at.split(":")
        flat = int(hh) * 60 + int(mm)
    trades, pos, pending = [], None, None
    day, day_real, locked, taken = None, 0.0, False, 0
    cooldown_until = -1
    pending_rev = False       # a reversal signal seen at bar i's CLOSE fires at bar i+1's OPEN (no lookahead)

    def close(px, t, why):
        nonlocal pos, day_real, locked, cooldown_until
        sign = 1 if pos["side"] == "LONG" else -1
        gross = (px - pos["entry"]) * sign
        net = gross - commission * (pos["entry"] + px)
        trades.append(dict(pos, exit_time=t, exit=px, result=why, gross=gross, net=net))
        day_real += net
        if limit and day_real <= -limit:
            locked = True
        if cooldown_bars and why == "SL":
            cooldown_until = i + cooldown_bars
        pos = None

    for i in range(start, len(rows)):
        r = rows[i]
        d, minute = r["time"].date(), r["time"].hour * 60 + r["time"].minute
        if d != day:
            day, day_real, locked, taken = d, 0.0, False, 0

        if pending is not None:
            if flat is not None and minute >= flat:
                pending = None                                     # would fill inside the flat window: skip
            else:
                pos = dict(pending, entry_time=r["time"], entry=r["open"])
                pending = None

        if pos is not None:
            long_ = pos["side"] == "LONG"
            forced = None
            if pending_rev and pos["entry_time"] != r["time"]:
                forced = "REV"
                pending_rev = False
            elif flat is not None and minute >= flat and pos["entry_time"] != r["time"]:
                forced = "FLAT"
            elif time_stop_min and (r["time"] - pos["entry_time"]).total_seconds() / 60 >= time_stop_min:
                forced = "TIME"
            if forced:
                close(r["open"], r["time"], forced)
            else:
                sl, tp = pos["sl"], pos["tp"]
                if gap_fills and (r["open"] <= sl if long_ else r["open"] >= sl):
                    close(r["open"], r["time"], "SL")
                elif gap_fills and (r["open"] >= tp if long_ else r["open"] <= tp):
                    close(r["open"], r["time"], "TP")
                else:
                    hit_sl = r["low"] <= sl if long_ else r["high"] >= sl
                    hit_tp = r["high"] >= tp if long_ else r["low"] <= tp
                    if hit_sl or hit_tp:                            # both in one bar: assume the stop
                        close(sl if hit_sl else tp, r["time"], "SL" if hit_sl else "TP")
                    elif locked:
                        close(r["close"], r["time"], "DAY LIMIT")
                    if pos is not None:
                        ext = r["high"] if long_ else r["low"]
                        pos["ext"] = max(pos.get("ext", ext), ext) if long_ else min(pos.get("ext", ext), ext)
                        gain = (pos["ext"] - pos["entry"]) * (1 if long_ else -1)
                        rk = pos["risk_pts"]
                        if be_at_r is not None and gain >= be_at_r * rk:
                            pos["sl"] = max(pos["sl"], pos["entry"]) if long_ else min(pos["sl"], pos["entry"])
                        if trail_start_r is not None and gain >= trail_start_r * rk:
                            t = pos["ext"] - trail_dist_r * rk if long_ else pos["ext"] + trail_dist_r * rk
                            pos["sl"] = max(pos["sl"], t) if long_ else min(pos["sl"], t)
                        if reversal_exit and (r["ok_s"] if long_ else r["ok_l"]):
                            pending_rev = True      # seen at bar i's close; fires at bar i+1's open (see top of loop)

        if (pos is None and pending is None and not locked and (r["ok_l"] or r["ok_s"])
                and (max_per_day is None or taken < max_per_day)
                and (cooldown_bars is None or i >= cooldown_until)):
            taken += 1
            side = "LONG" if r["ok_l"] else "SHORT"
            risk = r["risk_l"] if side == "LONG" else r["risk_s"]
            sign = 1 if side == "LONG" else -1
            pending = dict(side=side, signal_time=r["time"], risk_pts=risk,
                           sl=r["close"] - sign * risk, tp=r["close"] + sign * (p.get("rr_l", p["rr"]) if sign == 1 else p.get("rr_s", p["rr"])) * risk)
    return trades


def stats(trades):
    """PF, net, drawdown and consistency, all on net-of-commission points."""
    if not trades:
        return dict(n=0)
    t = pd.DataFrame(trades)
    win, loss = t.loc[t.net > 0, "net"].sum(), -t.loc[t.net < 0, "net"].sum()
    eq = t.net.cumsum()
    months = t.groupby(pd.to_datetime(t.exit_time).dt.to_period("M")).net.sum()
    return dict(n=len(t), win_pct=round(100 * (t.net > 0).mean(), 1), pf=round(win / loss, 3) if loss else float("inf"),
                net=round(t.net.sum(), 1), max_dd=round((eq.cummax() - eq).max(), 1),
                months=len(months), pos_months_pct=round(100 * (months > 0).mean(), 1),
                best_month_share=round(100 * months.max() / t.net.sum(), 1) if t.net.sum() > 0 else None,
                avg_hold_h=round((pd.to_datetime(t.exit_time) - pd.to_datetime(t.entry_time)).dt.total_seconds().mean() / 3600, 1))


def run(name, params, **kw):
    df = load(name)
    frame = v40.v40_frame(df, params)
    return simulate(frame, params, **kw)
