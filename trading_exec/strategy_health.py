"""Is the deployed SILVERM strategy still inside its historical normal range?

A ledger of the strategy's closed trades (exec_data/strategy_health_silverm.csv, net POINTS after the 0.02%/side cost) is seeded once from the
34-month research history and topped up each evening with trades from the latest Dhan bars. The post-market digest then shows rolling profit factor,
the drawdown from the peak, how long it has been below that peak and the current losing streak, against limits taken from the 2026-10-03 robustness
battery (strategy_audit_2026_09/silverm_robustness_battery.py):

    last-100-trade PF   5th percentile of history 0.86   -> REVIEW below 0.85, WATCH below 1.00 (25% of 60-trade windows are below 1.0: normal)
    drawdown            history max 68,416 pts           -> REVIEW above 100,000 pts, WATCH above 75,000
    below a peak        longest 193 trades (~9.5 months) -> REVIEW above 365 days, WATCH above 270
    losing streak       longest 20 trades                -> REVIEW above 20, WATCH from 15

These describe the STRATEGY (its own simulated trades), not your account. A breach means "look at the strategy again", never "stop trading".

    python -m trading_exec.strategy_health --seed      # build the ledger from research_data/bars (once)
    python -m trading_exec.strategy_health --status    # update from Dhan and print the health lines
"""
import argparse
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from trading_agents.core import signals as v40
from trading_agents.core.config import load_config as agents_config

from .config import data_dir, instrument_cfg

INSTRUMENT = "SILVERM"
COST = 0.0002                                   # per side, as in every backtest
LIMITS = dict(pf100_review=0.85, pf100_watch=1.00, dd_review=100_000.0, dd_watch=75_000.0,
              underwater_review=365, underwater_watch=270, streak_review=20, streak_watch=15)
COLUMNS = ["signal_time", "side", "entry_time", "exit_time", "net_pts", "source"]


def ledger_path():
    return data_dir() / "strategy_health_silverm.csv"


def _atomic_write_csv(df, path):
    tmp = Path(str(path) + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def load_ledger(path=None):
    p = Path(path) if path else ledger_path()
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["signal_time", "entry_time", "exit_time"])
    return df.sort_values("exit_time").reset_index(drop=True)


def _to_ledger(trades, source, cost=COST, net_col=None):
    """trades: list of simulate() dicts. `net` already includes the cost when it comes from research_sim."""
    rows = []
    for t in trades:
        net = t["net"] if net_col is None else t[net_col] - cost * (t["entry"] + t["exit"])
        rows.append(dict(signal_time=t["signal_time"], side=t["side"], entry_time=t["entry_time"], exit_time=t["exit_time"],
                         net_pts=round(float(net), 2), source=source))
    return pd.DataFrame(rows, columns=COLUMNS)


def seed(bars_csv=None, out=None):
    """Build the ledger from the harvested SILVERM1 history using the deployed settings. Needs research_data/ and the research simulator."""
    from strategy_audit_2026_09 import research_sim as rs            # research-only dependency, used for the one-off seed
    params = agents_config()["strategy"][INSTRUMENT]
    bars = rs.load("MCX_SILVERM1") if bars_csv is None else bars_csv
    trades = rs.simulate(v40.v40_frame(bars, params), params)
    df = _to_ledger(trades, "history")
    _atomic_write_csv(df, Path(out) if out else ledger_path())
    return df


def live_trades(client, now=None):
    """The strategy's closed trades over the last ~45 days of Dhan bars (production simulate; cost deducted here)."""
    from . import poller
    now = now or datetime.now()
    tcfg = instrument_cfg(INSTRUMENT)
    source = tcfg.get("signal_from", INSTRUMENT)
    params = agents_config()["strategy"][source]
    series = poller.signal_series(source, tcfg)
    bars = poller.closed_bars(client, series, now, 45, 5)
    if bars.empty or len(bars) < v40.WARMUP_BARS + 50:
        return pd.DataFrame(columns=COLUMNS)
    trades, _pos, _pending = v40.simulate(v40.v40_frame(bars, params), params)
    return _to_ledger(trades, "live", net_col="pnl_pts")


def update(client, now=None, fetch=None):
    """Append strategy trades whose SIGNAL is later than the newest one in the ledger. Returns (ledger, added)."""
    led = load_ledger()
    if led is None or led.empty:
        return led, 0
    new = (fetch or live_trades)(client, now)
    new = new[new["signal_time"] > led["signal_time"].max()] if len(new) else new
    if not len(new):
        return led, 0
    out = pd.concat([led, new], ignore_index=True).sort_values("exit_time").reset_index(drop=True)
    _atomic_write_csv(out, ledger_path())
    return out, len(new)


def _pf(s):
    w, l = s[s > 0].sum(), -s[s < 0].sum()
    return float(w / l) if l > 0 else float("inf")


def _runs(flags):
    best = cur = 0
    for v in flags:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best, cur


def compute(led):
    net = led["net_pts"].reset_index(drop=True)
    exit_t = led["exit_time"].reset_index(drop=True)
    eq = net.cumsum()
    peak = eq.cummax()
    dd = peak - eq
    below = (eq < peak).to_numpy()
    # time below a peak, in days, at every trade
    peak_time = exit_t.where(~below).ffill()
    underwater = (exit_t - peak_time).dt.days.fillna(0)
    roll100 = [_pf(net.iloc[i:i + 100]) for i in range(0, max(len(net) - 100 + 1, 0), 5)]
    longest_streak, streak_now = _runs((net < 0).to_numpy())
    last30 = led[led["exit_time"] > exit_t.iloc[-1] - pd.Timedelta(days=30)]["net_pts"]
    s = dict(n=len(net), first=exit_t.iloc[0], last=exit_t.iloc[-1], pf100=_pf(net.iloc[-100:]) if len(net) >= 20 else None, pf60=_pf(net.iloc[-60:]) if len(net) >= 20 else None,
             normal_lo=float(np.percentile(roll100, 5)) if roll100 else None, normal_hi=float(np.percentile(roll100, 75)) if roll100 else None,
             dd_now=float(dd.iloc[-1]), dd_max=float(dd.max()), underwater_now=int(underwater.iloc[-1]), underwater_max=int(underwater.max()),
             streak_now=streak_now, streak_max=longest_streak, last30_net=float(last30.sum()), last30_n=len(last30), live_n=int((led["source"] == "live").sum()))
    L = LIMITS
    review, watch = [], []
    if s["pf100"] is not None:
        if s["pf100"] < L["pf100_review"]:
            review.append(f"last-100 PF {s['pf100']:.2f} < {L['pf100_review']:.2f}")
        elif s["pf100"] < L["pf100_watch"]:
            watch.append(f"last-100 PF {s['pf100']:.2f} < {L['pf100_watch']:.2f}")
    for key, val, rev, wat, txt in (("dd", s["dd_now"], L["dd_review"], L["dd_watch"], "drawdown {v:,.0f} pts"),
                                    ("uw", s["underwater_now"], L["underwater_review"], L["underwater_watch"], "{v} days below its peak"),
                                    ("st", s["streak_now"], L["streak_review"], L["streak_watch"], "{v} losses in a row")):
        if val > rev:
            review.append(txt.format(v=val) + f" (review above {rev:,.0f})")
        elif val >= wat:
            watch.append(txt.format(v=val) + f" (watch from {wat:,.0f})")
    s["status"] = "REVIEW" if review else ("WATCH" if watch else "OK")
    s["reasons"] = review or watch
    return s


def lines(s):
    f = lambda x: f"{x:,.0f}"
    head = f"strategy health ({INSTRUMENT} v4.1, {s['n']} trades since {s['first']:%b %Y}, {s['live_n']} live): {s['status']}"
    out = [head]
    if s["reasons"]:
        out.append("  " + "; ".join(s["reasons"]))
    if s["pf100"] is not None:
        normal = f" (normal {s['normal_lo']:.2f}-{s['normal_hi']:.2f})" if s["normal_lo"] is not None else " (fewer than 100 trades in the ledger)"
        out.append(f"  last 100 trades PF {s['pf100']:.2f}{normal}, last 60 PF {s['pf60']:.2f}")
    out.append(f"  drawdown now {f(s['dd_now'])} pts (history max {f(s['dd_max'])}, review above {f(LIMITS['dd_review'])})")
    out.append(f"  below its peak for {s['underwater_now']} days (longest {s['underwater_max']}, review above {LIMITS['underwater_review']})")
    out.append(f"  losing streak now {s['streak_now']} (longest {s['streak_max']}), last 30 days {s['last30_n']} trades {f(s['last30_net'])} pts")
    return out


def digest_lines(client=None, now=None, fetch=None):
    """Lines for the post-market digest. Never raises: a problem here must not cost the trader the rest of the digest."""
    try:
        led = load_ledger()
        if led is None or led.empty:
            return ["strategy health: ledger not built yet - run python -m trading_exec.strategy_health --seed"]
        note = ""
        if client is not None or fetch is not None:
            try:
                led, added = update(client, now, fetch)
            except Exception as e:                                      # stale ledger is still worth showing
                note = f"  (not updated today: {type(e).__name__})"
        return lines(compute(led)) + ([note] if note else [])
    except Exception as e:
        return [f"strategy health: unavailable ({type(e).__name__}: {e})"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="store_true", help="build the ledger from research_data/bars (overwrites)")
    ap.add_argument("--status", action="store_true", help="update from Dhan and print the health lines")
    a = ap.parse_args(argv)
    if a.seed:
        df = seed()
        print(f"ledger written: {len(df)} trades, {df['exit_time'].min()} -> {df['exit_time'].max()}  ({ledger_path()})")
    if a.status or not a.seed:
        from . import health
        print("\n".join(digest_lines(health.fresh_client())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
