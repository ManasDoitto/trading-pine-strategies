"""Deterministic house-rule scan for agent reports.

This encodes conclusions this repo already reached the hard way, so no agent quietly
re-proposes them, plus the project's reporting conventions.

A rejected idea only counts when it shows up as a *recommendation*. Describing what the
trader actually did ("you averaged down on the 8000 PUT") must never be flagged, so a
finding needs a recommendation cue and the topic in the same sentence.

Usage:
    python -m trading_agents.validate.house_rules REPORT.md [--json]
Exit code 0 = no errors, 1 = at least one error-severity finding.
"""
import argparse
import json
import re
import sys

CLAIMS_RE = re.compile(r"```claims\s*\n.*?\n```", re.S)
STAMP_RE = re.compile(r"\n## (Validation|Supervisor)\b.*?(?=\n## |\Z)", re.S)
SENTENCE_RE = re.compile(r"(?<=[.!?:;])\s+|\n+")

RECOMMEND_CUE = re.compile(
    r"\b(should|recommend|suggest|consider|try|worth (adding|testing|trying)|could (add|improve|help)|"
    r"would (help|improve)|propose|advis\w+|better to|ought to|next time)\b"
    # modal + an action verb ("could optimise", "might want to add"), but not descriptive past
    # forms like "averaging down could have cost more"
    r"|\b(could|might|may|would)\s+(?:\w+\s+){0,3}?"
    r"(add|improve|help|optimi[sz]e|tune|test|try|use|switch|consider|remove|skip|scale|trail|"
    r"average|book|loosen|relax|filter|gate)\b", re.I)

REJECTED = [
    ("HR1", "partial take-profit / scaling out of v4.0",
     r"\b(partial (take[- ]?profit|exit|tp)|scal(e|ing) out|book(ing)? half|take half off)\b"),
    ("HR2", "extra confirmation filter or ADX gate on the SHA-flip family",
     r"\b(adx (gate|filter|threshold)|extra (confirmation|filter)|additional filter|htf (ema )?alignment|"
     r"higher[- ]timeframe (gate|filter))\b"),
    ("HR3", "day-of-week or weekday exclusions",
     r"\b(skip (monday|friday|tuesday|wednesday|thursday)|avoid trading on (monday|friday)|day[- ]of[- ]week filter)\b"),
    ("HR4", "loosening BankNifty v0.4's filters for frequency",
     r"\b(loosen\w*|relax\w*|remov\w+|drop\w*)\b[^.]{0,60}\b(volume (filter|requirement)|v0\.4|adx)\b"),
    ("HR5", "bare pullback-reclaim entries on the SHA-flip family",
     r"\bpullback[- ]reclaim\b|\breclaim entry\b|\bre-?enter on (the )?pullback\b"),
    ("HR6", "volatility-scaled circuit breaker instead of a fixed cap",
     r"\b(atr[- ]scaled|volatility[- ]scaled|dynamic)\b[^.]{0,40}\b(daily loss|circuit breaker|loss limit)\b"),
    ("HR7", "averaging down / adding to a losing option",
     r"\b(averag\w+ down|add(ing)? to (a|the|your) (losing|loser)|lower\w* (your |the )?(cost basis|average))\b"),
    ("HR8", "re-tuning until a target profit factor is hit (overfitting)",
     r"\b(tune|optimi[sz]e|re-?tune|curve[- ]fit)\w*\b[^.]{0,60}\b(pf|profit factor|until)\b"),
    ("HR9", "trailing stop on v4.0 (it uses a fixed bracket)",
     r"\btrail(ing)? stop\b"),
]

CERTAINTY = ("HR10", "stated as a certainty about the future",
             r"\b(will (rise|fall|move|hit|reach|break|gap|close)|is going to|guaranteed|certain(ly)? to|"
             r"definitely will|bound to)\b")
CURRENCY_FOR_STRATEGY = ("HR11", "strategy P&L quoted in rupees; this project reports strategy results in points",
                         r"\b(v4\.0|v0\.4|strategy|backtest|signal)\b[^.]{0,80}(₹|\bINR\b|\bRs\.?\b)\s?[\d,]{3,}")


def sentences(text):
    body = STAMP_RE.sub("", CLAIMS_RE.sub("", text))
    return [s.strip() for s in SENTENCE_RE.split(body) if s.strip()]


def check(text):
    findings = []
    for s in sentences(text):
        excerpt = s if len(s) <= 160 else s[:157] + "..."
        recommending = bool(RECOMMEND_CUE.search(s))
        for rule_id, name, pattern in REJECTED:
            if re.search(pattern, s, re.I) and recommending:
                findings.append(dict(rule=rule_id, severity="error", name=name, excerpt=excerpt))
        for rule_id, name, pattern in (CERTAINTY, CURRENCY_FOR_STRATEGY):
            if re.search(pattern, s, re.I):
                findings.append(dict(rule=rule_id, severity="warning", name=name, excerpt=excerpt))
    return dict(passed=not any(f["severity"] == "error" for f in findings), findings=findings)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with open(args.report, encoding="utf-8") as f:
        result = check(f.read())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"house_rules: {'PASS' if result['passed'] else 'FAIL'} ({len(result['findings'])} finding(s))")
        for f in result["findings"]:
            print(f"  {f['severity'].upper():7} {f['rule']} {f['name']}\n          \"{f['excerpt']}\"")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
