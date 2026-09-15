"""Deterministic validator: every number an agent writes must trace to its facts JSON.

A report ends with one fenced ```claims block:

    {"bias": {"CRUDEOIL": "bullish", ...},
     "claims": [{"text": "PDH 9,845", "value": 9845.4,
                 "source": "instruments.CRUDEOIL.underlying.prev_day.high"}, ...]}

Checks:
  1. the claims block exists and is valid JSON
  2. every claim's `source` path exists in the facts and its value matches
     (numbers within half a unit of the precision the claim was written with)
  3. every number in the report body is covered by a claim. A number that only
     appears somewhere in the facts is a warning; a number found nowhere is an error
  4. required sections, and a bias for every instrument, are present
  5. no trade-instruction language

Usage:
    python -m trading_agents.validate.claims_check REPORT.md FACTS.json [--kind premarket] [--stamp] [--json]
Exit code 0 = PASS, 1 = FAIL.
"""
import argparse
import json
import re
import sys
from decimal import Decimal

REQUIRED_SECTIONS = {
    "premarket": ["## Overview", "## Your risk reminders", "## Data notes"],
    "session_close": ["## Overview", "## How this morning's call did", "## Your trades vs the strategy",
                      "## Data notes"],
}
BIAS_KINDS = {"premarket"}                 # only the pre-market brief states a bias
BIAS_VALUES = {"bullish", "bearish", "neutral"}
INSTRUCTION_RE = re.compile(
    r"\b(you should (buy|sell|take|enter)|i (would )?recommend (buying|selling)|go (long|short)|"
    r"enter (a )?(long|short)|place an? (buy|sell)? ?order|(buy|sell) (the )?\d[\d,]*\s*(ce|pe|call|put)s?\b)",
    re.I)
CLAIMS_RE = re.compile(r"```claims\s*\n(.*?)\n```", re.S)
# replace only our own section, so a later ## Supervisor stamp survives a re-check
STAMP_RE = re.compile(r"\n## Validation\b.*?(?=\n## |\Z)", re.S)
# both stamps are tool output, not analyst prose: never scan them for claims
STRIP_STAMPS_RE = re.compile(r"\n## (?:Validation|Supervisor)\b.*?(?=\n## |\Z)", re.S)
# a number not glued to letters, dates, times or paths; 5m / R1 / 2026-09-16 / 17:34 are skipped
NUM_RE = re.compile(r"(?<![\w.:/\-])[-+\u2212]?\d[\d,]*(?:\.\d+)?(?![\w:/\-]|\.\d)")
SMALL_INT_IGNORE = 10


def _decimals(v):
    if isinstance(v, Decimal):
        return max(-v.as_tuple().exponent, 0)
    return 0


def _close(shown, shown_decimals, fact):
    return abs(float(shown) - float(fact)) <= 0.5 * 10 ** -shown_decimals + 1e-9


def resolve(facts, path):
    cur = facts
    for part in path.split("."):
        if isinstance(cur, list):
            if not part.lstrip("-").isdigit() or int(part) >= len(cur):
                raise KeyError(path)
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def _numeric_leaves(obj, out):
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        # numbers inside string facts (e.g. a caveat quoted verbatim) count as traceable
        for _, num, _ in body_numbers(obj):
            out.append(num)
    elif isinstance(obj, dict):
        for v in obj.values():
            _numeric_leaves(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numeric_leaves(v, out)
    return out


def body_numbers(body):
    body = re.sub(r"(\d)x\b", r"\1 x", body)          # "1.2x" -> ratio 1.2
    for m in NUM_RE.finditer(body):
        tok = m.group(0).replace(",", "").replace("\u2212", "-")
        dec = len(tok.split(".")[1]) if "." in tok else 0
        yield m.group(0), float(tok), dec


def check(report, facts, kind="premarket"):
    errors, warnings = [], []
    text = STRIP_STAMPS_RE.sub("", report)
    blocks = CLAIMS_RE.findall(text)
    if len(blocks) != 1:
        errors.append(f"expected exactly one ```claims block, found {len(blocks)}")
        return _result(errors, warnings, 0, 0, 0)
    try:
        payload = json.loads(blocks[0], parse_float=Decimal)
    except json.JSONDecodeError as e:
        errors.append(f"claims block is not valid JSON: {e}")
        return _result(errors, warnings, 0, 0, 0)
    claims = payload.get("claims") or []
    body = CLAIMS_RE.sub("", text)

    # 2. claims vs facts
    claimed = []
    for c in claims:
        src, val = c.get("source"), c.get("value")
        label = c.get("text") or src
        try:
            fact = resolve(facts, src or "")
        except KeyError:
            errors.append(f"claim '{label}': source '{src}' not found in facts")
            continue
        if isinstance(val, (int, Decimal)) and not isinstance(val, bool):
            if isinstance(fact, bool) or not isinstance(fact, (int, float)):
                errors.append(f"claim '{label}': value {val} but facts {src} = {fact!r}")
            elif not _close(val, _decimals(val), fact):
                errors.append(f"claim '{label}': value {val} does not match facts {src} = {fact}")
            else:
                claimed.append(float(val))
        elif isinstance(val, str):
            if not isinstance(fact, str) or fact.strip().lower() != val.strip().lower():
                errors.append(f"claim '{label}': value '{val}' does not match facts {src} = {fact!r}")
        elif isinstance(val, bool):
            if fact is not val:
                errors.append(f"claim '{label}': value {val} does not match facts {src} = {fact!r}")
        else:
            errors.append(f"claim '{label}': unsupported value {val!r}")

    # 3. body numbers must be claimed
    fact_numbers = _numeric_leaves(facts, [])
    unclaimed = untraceable = 0
    for raw, num, dec in body_numbers(body):
        if dec == 0 and abs(num) < SMALL_INT_IGNORE:
            continue
        if dec == 0 and 2000 <= num <= 2100 and not any(_close(num, 0, c) for c in claimed):
            continue                                            # a year
        if any(_close(num, dec, c) or _close(-num, dec, c) for c in claimed):
            continue
        if any(_close(num, dec, f) or _close(-num, dec, f) for f in fact_numbers):
            unclaimed += 1
            warnings.append(f"number '{raw}' appears in the facts but has no claim")
        else:
            untraceable += 1
            errors.append(f"number '{raw}' in the report does not trace to any fact")

    # 4. structure
    for sec in REQUIRED_SECTIONS.get(kind, []):
        if not re.search(rf"^{re.escape(sec)}\b", body, re.M):
            errors.append(f"missing section '{sec}'")
    instruments = list((facts.get("instruments") or {}).keys())
    bias = payload.get("bias") or {}
    for inst in instruments:
        if not re.search(rf"^## {re.escape(inst)}\b", body, re.M):
            errors.append(f"missing section '## {inst}'")
        if kind in BIAS_KINDS and str(bias.get(inst, "")).lower() not in BIAS_VALUES:
            errors.append(f"bias for {inst} missing or not one of {sorted(BIAS_VALUES)}")

    # 5. instructions
    for m in INSTRUCTION_RE.finditer(body):
        errors.append(f"trade-instruction language: '{m.group(0)}'")

    return _result(errors, warnings, len(claims), unclaimed, untraceable)


def _result(errors, warnings, n_claims, unclaimed, untraceable):
    return dict(verdict="PASS" if not errors else "FAIL", passed=not errors, errors=errors, warnings=warnings,
                stats=dict(claims=n_claims, unclaimed_numbers=unclaimed, untraceable_numbers=untraceable))


def stamp(report, result):
    lines = [f"\n## Validation\n", f"**claims_check: {result['verdict']}**, "
             f"{result['stats']['claims']} claims, {len(result['errors'])} error(s), "
             f"{len(result['warnings'])} warning(s).\n"]
    lines += [f"- ❌ {e}" for e in result["errors"]]
    lines += [f"- ⚠ {w}" for w in result["warnings"]]
    return STAMP_RE.sub("", report).rstrip() + "\n" + "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("facts")
    ap.add_argument("--kind", default="premarket")
    ap.add_argument("--stamp", action="store_true", help="append/replace a '## Validation' section in the report")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with open(args.report, encoding="utf-8") as f:
        report = f.read()
    with open(args.facts, encoding="utf-8") as f:
        facts = json.load(f)
    result = check(report, facts, args.kind)
    if args.stamp:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(stamp(report, result))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"claims_check: {result['verdict']} ({result['stats']})")
        for e in result["errors"]:
            print("  ERROR", e)
        for w in result["warnings"]:
            print("  warn ", w)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
