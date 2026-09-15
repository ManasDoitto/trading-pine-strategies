"""Grade the morning's pre-market call against what the session actually did.

Reads the pre-market report's claims block (the analyst's stated bias), the pre-market facts
(the deterministic rule_bias), and the session-close facts (what happened), then appends one row
per instrument to journal_data/scorecard.csv and returns running hit rates.

A call is graded only when the session actually moved: if |close - open| is below
`flat_threshold_atr` x ATR14 the session counts as flat, which makes "neutral" correct and
directional calls wrong.

Usage:
    python -m trading_agents.validate.scorecard --date 2026-09-16 [--session MCX] [--json]
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date

from ..core.config import data_dir, load_config
from .claims_check import CLAIMS_RE

FIELDS = ["date", "underlying", "session", "analyst_bias", "rule_bias", "outcome", "open", "close",
          "move_pts", "move_vs_atr", "analyst_correct", "rule_correct", "touched_r1", "touched_s1",
          "closed_above_pivot"]


def report_bias(date_):
    path = data_dir("reports") / f"{date_}_premarket.md"
    if not path.exists():
        return {}, f"no pre-market report for {date_}"
    blocks = CLAIMS_RE.findall(path.read_text(encoding="utf-8"))
    if not blocks:
        return {}, "pre-market report has no claims block"
    try:
        return (json.loads(blocks[0]).get("bias") or {}), None
    except json.JSONDecodeError as e:
        return {}, f"pre-market claims block is not valid JSON: {e}"


def outcome_of(move_pts, atr, flat_threshold_atr):
    if atr and abs(move_pts) < flat_threshold_atr * atr:
        return "flat"
    return "up" if move_pts > 0 else "down"


def grade(bias, outcome):
    if bias not in ("bullish", "bearish", "neutral"):
        return None
    if outcome == "flat":
        return bias == "neutral"
    return (bias == "bullish") == (outcome == "up")


def build_rows(date_, session_facts, premarket_facts, biases):
    cfg = load_config()["session_close"]
    rows = []
    for u, sf in (session_facts.get("instruments") or {}).items():
        sess = sf.get("session") or {}
        if not sf.get("available") or sess.get("close") is None:
            continue
        pf = (premarket_facts.get("instruments") or {}).get(u, {})
        # without a morning brief, fall back to the levels the session facts computed themselves,
        # so the session is still graded for magnitude
        und = pf.get("underlying") or sf.get("prior_levels") or {}
        atr = und.get("atr14")
        move = sess["close"] - sess["open"]
        outcome = outcome_of(move, atr, cfg["flat_threshold_atr"])
        piv = (und.get("pivots") or {})
        rows.append(dict(
            date=date_, underlying=u, session=session_facts.get("session"),
            analyst_bias=biases.get(u), rule_bias=pf.get("rule_bias"), outcome=outcome,
            open=sess["open"], close=sess["close"], move_pts=round(move, 2),
            move_vs_atr=round(move / atr, 2) if atr else None,
            analyst_correct=grade(biases.get(u), outcome), rule_correct=grade(pf.get("rule_bias"), outcome),
            touched_r1=sess["high"] >= piv["R1"] if piv.get("R1") else None,
            touched_s1=sess["low"] <= piv["S1"] if piv.get("S1") else None,
            closed_above_pivot=sess["close"] > piv["P"] if piv.get("P") else None,
        ))
    return rows


def append_rows(rows):
    path = data_dir() / "scorecard.csv"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    else:
        existing = []
    # rows carry a date object, CSV rows a string: compare as strings so a re-run replaces its rows
    keys = {(str(r["date"]), str(r["underlying"])) for r in rows}
    existing = [r for r in existing if (str(r["date"]), str(r["underlying"])) not in keys]
    out = existing + [{k: ("" if v is None else v) for k, v in r.items()} for r in rows]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(out, key=lambda r: (str(r["date"]), str(r["underlying"]))))
    return path, out


def hit_rates(all_rows):
    """Running accuracy per instrument, and overall, for both the analyst and the rule bias."""
    def rate(rows, key):
        graded = [r for r in rows if str(r.get(key)) in ("True", "False", "true", "false")]
        hits = [r for r in graded if str(r[key]).lower() == "true"]
        return dict(graded=len(graded), correct=len(hits),
                    pct=round(100 * len(hits) / len(graded), 1) if graded else None)

    by_u = defaultdict(list)
    for r in all_rows:
        by_u[r["underlying"]].append(r)
    return dict(
        overall=dict(analyst=rate(all_rows, "analyst_correct"), rule=rate(all_rows, "rule_correct")),
        by_underlying={u: dict(analyst=rate(rs, "analyst_correct"), rule=rate(rs, "rule_correct"),
                               sessions=len(rs)) for u, rs in sorted(by_u.items())},
    )


def merge_into_facts(date_, result):
    """Put the scorecard inside the session facts so a report can cite it by dot path."""
    path = data_dir("facts") / f"{date_}_session_close.json"
    facts = json.loads(path.read_text(encoding="utf-8"))
    facts["scorecard"] = {k: result[k] for k in ("rows", "hit_rates", "notes")}
    path.write_text(json.dumps(facts, indent=2, default=str), encoding="utf-8")
    return path


def run(date_, session=None):
    facts_dir = data_dir("facts")
    sc_path = facts_dir / f"{date_}_session_close.json"
    pm_path = facts_dir / f"{date_}_premarket.json"
    if not sc_path.exists():
        raise FileNotFoundError(f"no session-close facts for {date_}: run facts.session_close first")
    session_facts = json.loads(sc_path.read_text(encoding="utf-8"))
    premarket_facts = json.loads(pm_path.read_text(encoding="utf-8")) if pm_path.exists() else {}
    biases, note = report_bias(date_)
    rows = build_rows(date_, session_facts, premarket_facts, biases)
    if session:
        rows = [r for r in rows if r["session"] == session]
    path, all_rows = append_rows(rows)
    return dict(date=str(date_), rows=rows, scorecard_csv=str(path), hit_rates=hit_rates(all_rows),
                notes=[n for n in (note, None if pm_path.exists() else f"no pre-market facts for {date_}") if n])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--session", choices=["NSE", "MCX", "ALL"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write-facts", action="store_true", help="don't merge the scorecard into the session facts")
    args = ap.parse_args(argv)
    result = run(args.date, args.session if args.session != "ALL" else None)
    if not args.no_write_facts:
        merge_into_facts(args.date, result)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for r in result["rows"]:
            print(f"{r['underlying']}: analyst {r['analyst_bias']} / rule {r['rule_bias']} vs {r['outcome']} "
                  f"({r['move_pts']:+} pts, {r['move_vs_atr']} x ATR) -> "
                  f"analyst {'correct' if r['analyst_correct'] else 'wrong' if r['analyst_correct'] is False else 'n/a'}")
        print("hit rates:", json.dumps(result["hit_rates"]["by_underlying"]))
        for n in result["notes"]:
            print("note:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
