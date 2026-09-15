import unittest

from trading_agents.validate.house_rules import check


def ids(text):
    return {f["rule"] for f in check(text)["findings"]}


class HouseRulesTest(unittest.TestCase):
    def test_describing_the_traders_own_mistake_is_not_flagged(self):
        text = ("You averaged down on the CRUDEOIL 8000 PUT, re-buying at 38.0 below a 120.6 average. "
                "R1 flagged it and the position is 99.63 premium points down.")
        self.assertEqual(check(text)["findings"], [])

    def test_recommending_averaging_down_is_an_error(self):
        r = check("You should consider averaging down to lower your cost basis.")
        self.assertEqual(ids("You should consider averaging down to lower your cost basis."), {"HR7"})
        self.assertFalse(r["passed"])

    def test_rejected_enhancements(self):
        self.assertIn("HR1", ids("It may be worth adding a partial take-profit at 2R on v4.0."))
        self.assertIn("HR2", ids("Consider an ADX gate on the crude signal to filter chop."))
        self.assertIn("HR3", ids("You should skip Monday trades given the weekday stats."))
        self.assertIn("HR5", ids("Worth testing a pullback-reclaim entry after the flip."))
        self.assertIn("HR6", ids("An ATR-scaled daily loss limit would help more than the fixed one."))
        self.assertIn("HR8", ids("We could optimise the parameters until PF is above 1.3."))
        self.assertIn("HR9", ids("A trailing stop would improve this strategy."))

    def test_topic_without_a_recommendation_cue_passes(self):
        self.assertEqual(ids("The ADX gate was tested on 14 Sep and made crude worse."), set())
        self.assertEqual(ids("A trailing stop is not part of v4.0; it uses a fixed 4R bracket."), set())

    def test_certainty_and_currency_conventions_are_warnings(self):
        r = check("Crude will rise tomorrow.")
        self.assertEqual(ids("Crude will rise tomorrow."), {"HR10"})
        self.assertTrue(r["passed"])                       # warnings don't fail the report
        self.assertIn("HR11", ids("The v4.0 strategy made ₹12,500 last session."))
        self.assertEqual(ids("Your account realised ₹12,500 last session."), set())

    def test_claims_block_and_stamps_are_ignored(self):
        text = ('Clean sentence.\n\n```claims\n{"claims": [{"text": "you should consider averaging down"}]}\n```\n'
                "\n## Validation\n\nclaims_check: PASS\n")
        self.assertEqual(check(text)["findings"], [])


if __name__ == "__main__":
    unittest.main()
