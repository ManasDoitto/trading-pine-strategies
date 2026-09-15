import json
import unittest

from trading_agents.validate.claims_check import check, stamp

FACTS = {
    "date": "2026-09-16",
    "instruments": {
        "CRUDEOIL": {"underlying": {"prev_day": {"high": 9845.4, "low": 9700.0}, "atr14": 212.37},
                     "strategy": {"sha_state": "green"},
                     "options": {"usable": True, "nearest": {"atm": {"ce": {"iv": 18.27}}}}},
    },
    "context": {"open_positions": 1, "unrealized_inr": -59780.0},
}


def report(body, claims=None, bias=None):
    payload = {"bias": bias if bias is not None else {"CRUDEOIL": "neutral"},
               "claims": claims if claims is not None else [
                   {"text": "PDH", "value": 9845, "source": "instruments.CRUDEOIL.underlying.prev_day.high"},
                   {"text": "PDL", "value": 9700, "source": "instruments.CRUDEOIL.underlying.prev_day.low"},
                   {"text": "IV", "value": 18.27, "source": "instruments.CRUDEOIL.options.nearest.atm.ce.iv"},
                   {"text": "SHA", "value": "green", "source": "instruments.CRUDEOIL.strategy.sha_state"},
               ]}
    return ("# Pre-market: 2026-09-16\n\n## Overview\nCrude flat.\n\n## CRUDEOIL\n" + body +
            "\n\n## Your risk reminders\nR1: no averaging down.\n\n## Data notes\nnone\n\n"
            "```claims\n" + json.dumps(payload) + "\n```\n")


GOOD = "PDH 9,845 and PDL 9,700.0 on the 5m chart at 17:34 on 2026-09-15; ATM CE IV 18.27% (R1, 3 lots)."


class ClaimsCheckTest(unittest.TestCase):
    def test_pass(self):
        r = check(report(GOOD), FACTS)
        self.assertEqual(r["verdict"], "PASS", r["errors"])
        self.assertEqual(r["warnings"], [])

    def test_claim_value_mismatch(self):
        bad = [{"text": "PDH", "value": 9900, "source": "instruments.CRUDEOIL.underlying.prev_day.high"}]
        r = check(report("PDH 9,900.", claims=bad), FACTS)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("does not match" in e for e in r["errors"]))

    def test_rounding_tolerance_follows_written_precision(self):
        wrong_precision = [{"text": "ATR", "value": 212.4, "source": "instruments.CRUDEOIL.underlying.atr14"},
                           {"text": "ATR", "value": 212.3, "source": "instruments.CRUDEOIL.underlying.atr14"}]
        r = check(report("ATR 212.4.", claims=wrong_precision), FACTS)
        self.assertEqual(sum("does not match" in e for e in r["errors"]), 1)   # 212.3 is wrong, 212.4 fine

    def test_untraceable_number_fails(self):
        r = check(report(GOOD + " Target 10,500."), FACTS)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("10,500" in e for e in r["errors"]))

    def test_unclaimed_fact_number_warns(self):
        r = check(report(GOOD + " Open MTM -59,780."), FACTS)
        self.assertEqual(r["verdict"], "PASS", r["errors"])
        self.assertTrue(any("59,780" in w for w in r["warnings"]))

    def test_number_quoted_from_a_string_fact_is_traceable(self):
        facts = dict(FACTS, caveats=["MCX close can differ by up to 66 pts on crude"])
        r = check(report(GOOD + " The caveat says up to 66 pts."), facts)
        self.assertEqual(r["verdict"], "PASS", r["errors"])

    def test_missing_block_bad_source_and_bias(self):
        self.assertEqual(check("## Overview\nno claims", FACTS)["verdict"], "FAIL")
        r = check(report(GOOD, claims=[{"text": "x", "value": 1, "source": "instruments.NOPE.x"}]), FACTS)
        self.assertTrue(any("not found" in e for e in r["errors"]))
        r = check(report(GOOD, bias={"CRUDEOIL": "moon"}), FACTS)
        self.assertTrue(any("bias for CRUDEOIL" in e for e in r["errors"]))

    def test_instruction_language(self):
        r = check(report(GOOD + " You should buy the 9800 CE at open."), FACTS)
        self.assertTrue(any("trade-instruction" in e for e in r["errors"]))

    def test_missing_instrument_section(self):
        r = check(report(GOOD).replace("## CRUDEOIL", "## Crude"), FACTS)
        self.assertTrue(any("## CRUDEOIL" in e for e in r["errors"]))

    def test_stamp_preserves_a_supervisor_section(self):
        rep = report(GOOD)
        once = stamp(rep, check(rep, FACTS))
        with_sup = once + "\n## Supervisor\n\n**Verdict: PASS** after checking 12,345 numbers\n"
        twice = stamp(with_sup, check(with_sup, FACTS))
        self.assertIn("## Supervisor", twice)
        self.assertEqual(twice.count("## Validation"), 1)
        self.assertEqual(check(twice, FACTS)["verdict"], "PASS", "supervisor prose must not be scanned")

    def test_stamp_replaces_previous(self):
        rep = report(GOOD)
        once = stamp(rep, check(rep, FACTS))
        twice = stamp(once, check(once, FACTS))
        self.assertEqual(twice.count("## Validation"), 1)
        self.assertEqual(check(twice, FACTS)["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
