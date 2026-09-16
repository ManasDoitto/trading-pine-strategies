"""The Stage B verdict: did the strategies survive as option buys?

The pass rules were fixed in the plan before any shadow data existed, and are duplicated here so
they can't drift once results are in:

    GO requires ALL of
      - net premium P&L positive after modelled costs
      - profit factor >= 1.2
      - at least 15 closed shadow trades
      - no single trade contributing more than half the net profit
    NO-GO otherwise.

Separately, and not automatable: spot-check 5 signals per instrument against your TradingView
chart during the month. More than one disagreement out of five means the Python port isn't
trustworthy enough to trade, whatever the P&L says.

    python -m trading_exec.report                 # everything recorded so far
    python -m trading_exec.report --month 2026-10
"""
import argparse
import sys
from collections import defaultdict
from datetime import date, datetime

from . import shadow
from .config import data_dir, load_config

MIN_TRADES = 15
MIN_PF = 1.2
MAX_SINGLE_SHARE = 0.5


def _stats(trades, key="net_inr"):
    vals = [t[key] for t in trades if t.get(key) is not None]
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v <= 0]
    loss_sum = abs(sum(losses))
    return dict(n=len(vals), net=round(sum(vals), 2),
                win_rate=round(100 * len(wins) / len(vals), 1) if vals else None,
                profit_factor=round(sum(wins) / loss_sum, 2) if loss_sum else None,
                avg_win=round(sum(wins) / len(wins), 2) if wins else None,
                avg_loss=round(sum(losses) / len(losses), 2) if losses else None,
                best=max(vals) if vals else None, worst=min(vals) if vals else None)


def verdict(trades):
    """Apply the pre-registered rules to one instrument's closed trades."""
    s = _stats(trades)
    wins = [t["net_inr"] for t in trades if (t.get("net_inr") or 0) > 0]
    top_share = (max(wins) / s["net"]) if wins and s["net"] and s["net"] > 0 else None
    checks = {
        f"at least {MIN_TRADES} closed trades": s["n"] >= MIN_TRADES,
        "net positive after costs": (s["net"] or 0) > 0,
        f"profit factor at least {MIN_PF}": (s["profit_factor"] or 0) >= MIN_PF,
        "no single trade over half the net profit": top_share is None or top_share <= MAX_SINGLE_SHARE,
    }
    return dict(stats=s, checks=checks, top_trade_share=round(top_share, 3) if top_share else None,
                verdict="GO" if all(checks.values()) else "NO-GO",
                failed=[k for k, v in checks.items() if not v])


def compare_exits(trades):
    """The strategy's underlying-based exit against a 30% premium stop, on the same trades."""
    both = [t for t in trades if t.get("net_inr") is not None and t.get("premium_stop_net_inr") is not None]
    if not both:
        return dict(comparable=0, note="no trade hit the 30% premium stop")
    real = sum(t["net_inr"] for t in both)
    stopped = sum(t["premium_stop_net_inr"] for t in both)
    return dict(comparable=len(both), underlying_exit_net=round(real, 2), premium_stop_net=round(stopped, 2),
                premium_stop_better=stopped > real)


def build(month=None):
    closed = [t for t in shadow.load() if t["status"] == "CLOSED"]
    if month:
        closed = [t for t in closed if str(t.get("exit_at", ""))[:7] == month]
    trades = [t for t in closed if not t.get("observational")]
    observational = [t for t in closed if t.get("observational")]
    by_inst = defaultdict(list)
    for t in trades:
        by_inst[t["instrument"]].append(t)

    obs_by_inst = defaultdict(list)
    for t in observational:
        obs_by_inst[t["instrument"]].append(t)
    out = dict(generated_at=datetime.now().replace(microsecond=0).isoformat(), month=month or "all",
               closed_trades=len(trades), instruments={},
               observational={inst: dict(_stats(ts), note="below the DTE floor; never tradeable, "
                                         "recorded only to show what the floor cost or saved")
                              for inst, ts in sorted(obs_by_inst.items())})
    for inst, ts in sorted(by_inst.items()):
        v = verdict(ts)
        floor = (load_config()["instruments"].get(inst) or {}).get("min_dte")
        v["exit_comparison"] = compare_exits(ts)
        v["below_dte_floor"] = sum(1 for t in ts if (t.get("dte_at_entry") or 99) < (floor or 0))
        v["by_exit_reason"] = {r: len([t for t in ts if t["exit_reason"] == r])
                               for r in sorted({t["exit_reason"] for t in ts if t.get("exit_reason")})}
        out["instruments"][inst] = v
    return out


def to_markdown(rep):
    L = [f"# Shadow verdict: {rep['month']}", "",
         f"Generated {rep['generated_at']} from {rep['closed_trades']} closed shadow trades.", "",
         "Pass rules were fixed before any data existed: at least "
         f"{MIN_TRADES} trades, net positive after costs, profit factor at least {MIN_PF}, "
         "and no single trade worth more than half the net profit.", ""]
    if not rep["instruments"]:
        L += ["No closed shadow trades yet."]
        return "\n".join(L)
    for inst, v in rep["instruments"].items():
        s = v["stats"]
        L += [f"## {inst}: **{v['verdict']}**", "",
              f"| trades | net INR | win rate | PF | avg win | avg loss | best | worst |",
              f"|---|---|---|---|---|---|---|---|",
              f"| {s['n']} | {s['net']:,} | {s['win_rate']}% | {s['profit_factor']} | {s['avg_win']} | "
              f"{s['avg_loss']} | {s['best']} | {s['worst']} |", ""]
        for name, ok in v["checks"].items():
            L.append(f"- {'PASS' if ok else 'FAIL'} — {name}")
        c = v["exit_comparison"]
        if c.get("comparable"):
            L += ["", f"Exit style, on the {c['comparable']} trades where both apply: the strategy's "
                      f"underlying exit made {c['underlying_exit_net']:,} INR, a 30% premium stop would have made "
                      f"{c['premium_stop_net']:,} INR."]
        else:
            L += ["", c.get("note", "")]
        if v["below_dte_floor"]:
            L.append(f"{v['below_dte_floor']} trade(s) were entered below the DTE floor.")
        L += [f"Exits: {v['by_exit_reason']}", ""]
    if rep.get("observational"):
        L += ["## Signals the DTE floor refused", "",
              "Never tradeable, tracked only to price the rule itself.", ""]
        for inst, s in rep["observational"].items():
            L += [f"- {inst}: {s['n']} trades, net {s['net']:,} INR, win rate {s['win_rate']}%, PF {s['profit_factor']}"]
        L += [""]
    L += ["", "Not covered by these numbers: the manual spot-check of 5 signals per instrument "
              "against the TradingView chart. More than one mismatch in five is a NO-GO regardless."]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", help="YYYY-MM; defaults to every closed trade")
    ap.add_argument("--write", action="store_true", help="also write the markdown into exec_data/")
    args = ap.parse_args(argv)

    rep = build(args.month)
    md = to_markdown(rep)
    print(md)
    if args.write:
        p = data_dir("reports") / f"shadow_verdict_{rep['month']}.md"
        p.write_text(md, encoding="utf-8")
        print(f"\nwritten to {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
