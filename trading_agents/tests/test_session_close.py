import unittest
from datetime import date, datetime, timedelta

import pandas as pd

from trading_agents.facts.session_close import alignment, session_summary
from trading_agents.validate import scorecard


COLS = ["time", "open", "high", "low", "close", "volume"]


def day_bars(rows, day=date(2026, 9, 15)):
    t0 = datetime.combine(day, datetime.min.time()) + timedelta(hours=9, minutes=15)
    df = pd.DataFrame([dict(time=t0 + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=v)
                       for i, (o, h, l, c, v) in enumerate(rows)], columns=COLS)
    return df.astype({"time": "datetime64[ns]", **{c: "float64" for c in COLS[1:]}})


PRIOR = dict(prev_day=dict(close=100.0, high=104.0, low=96.0), atr14=10.0,
             pivots=dict(P=100.0, R1=106.0, S1=94.0))


class SessionSummaryTest(unittest.TestCase):
    def test_ohlc_gap_range_and_levels(self):
        s = session_summary(day_bars([(101, 108, 100, 107, 10), (107, 110, 93, 95, 30)]), PRIOR)
        self.assertEqual((s["open"], s["high"], s["low"], s["close"]), (101, 110, 93, 95))
        self.assertEqual((s["range"], s["change_pts"]), (17, -6))
        self.assertEqual(s["gap_pts"], 1.0)                       # open 101 vs prev close 100
        self.assertEqual(s["change_vs_prev_close_pts"], -5.0)
        self.assertAlmostEqual(s["range_vs_atr"], 1.7)
        self.assertAlmostEqual(s["move_vs_atr"], -0.6)
        self.assertEqual((s["closed_above_pivot"], s["touched_r1"], s["touched_s1"]), (False, True, True))
        self.assertEqual((s["closed_above_prev_high"], s["closed_below_prev_low"]), (False, True))
        typical = [(108 + 100 + 107) / 3, (110 + 93 + 95) / 3]      # VWAP uses (H+L+C)/3, not the close
        self.assertAlmostEqual(s["vwap"], (typical[0] * 10 + typical[1] * 30) / 40)

    def test_no_bars(self):
        s = session_summary(day_bars([]), PRIOR)
        self.assertFalse(s["available"])

    def test_without_prior_levels(self):
        s = session_summary(day_bars([(101, 108, 100, 107, 10)]), None)
        self.assertTrue(s["available"])
        self.assertNotIn("range_vs_atr", s)


class AlignmentTest(unittest.TestCase):
    ENTRIES = [dict(time="2026-09-15T10:00:00", symbol="X CE", right="CE", side="LONG"),
               dict(time="2026-09-15T14:00:00", symbol="Y PE", right="PE", side="SHORT")]
    FIRED = [dict(time="2026-09-15T10:10:00", side="LONG"), dict(time="2026-09-15T14:05:00", side="LONG")]

    def test_matches_direction_and_window(self):
        a = alignment(self.ENTRIES, self.FIRED, 15)
        self.assertEqual((a["entries"], a["matched_a_signal"]), (2, 1))
        self.assertEqual(a["detail"][0]["matching_signal"], "2026-09-15T10:10:00")
        self.assertTrue(a["detail"][1]["opposite_signal_nearby"])     # short entry, long signal nearby

    def test_window_excludes_far_signals(self):
        self.assertEqual(alignment(self.ENTRIES, self.FIRED, 5)["matched_a_signal"], 0)

    def test_no_entries(self):
        self.assertEqual(alignment([], self.FIRED, 15)["entries"], 0)


class ScorecardTest(unittest.TestCase):
    SESSION = dict(session="MCX", instruments=dict(
        CRUDEOIL=dict(available=True, session=dict(available=True, open=10000.0, high=10300.0, low=9950.0,
                                                   close=10250.0)),
        SILVER=dict(available=True, session=dict(available=True, open=232000.0, high=232500.0, low=231500.0,
                                                 close=232010.0))))
    PREMARKET = dict(instruments=dict(
        CRUDEOIL=dict(rule_bias="bullish", underlying=dict(atr14=300.0, pivots=dict(P=10100.0, R1=10280.0,
                                                                                    S1=9900.0))),
        SILVER=dict(rule_bias="bullish", underlying=dict(atr14=6000.0, pivots=dict(P=232000.0, R1=234000.0,
                                                                                   S1=230000.0)))))

    def test_outcome_and_grade(self):
        self.assertEqual(scorecard.outcome_of(250, 300, 0.25), "up")
        self.assertEqual(scorecard.outcome_of(-250, 300, 0.25), "down")
        self.assertEqual(scorecard.outcome_of(10, 300, 0.25), "flat")
        self.assertIs(scorecard.grade("bullish", "up"), True)
        self.assertIs(scorecard.grade("bullish", "down"), False)
        self.assertIs(scorecard.grade("neutral", "flat"), True)
        self.assertIs(scorecard.grade("neutral", "up"), False)
        self.assertIsNone(scorecard.grade(None, "up"))

    def test_build_rows(self):
        rows = scorecard.build_rows(date(2026, 9, 15), self.SESSION, self.PREMARKET,
                                    {"CRUDEOIL": "bullish", "SILVER": "bearish"})
        crude = next(r for r in rows if r["underlying"] == "CRUDEOIL")
        self.assertEqual((crude["outcome"], crude["move_pts"]), ("up", 250.0))
        self.assertIs(crude["analyst_correct"], True)
        self.assertIs(crude["rule_correct"], True)
        self.assertEqual((crude["touched_r1"], crude["touched_s1"], crude["closed_above_pivot"]),
                         (True, False, True))
        silver = next(r for r in rows if r["underlying"] == "SILVER")
        self.assertEqual(silver["outcome"], "flat")               # 10 pts on a 6000 ATR
        self.assertIs(silver["analyst_correct"], False)           # a bearish call on a flat session

    def test_falls_back_to_session_prior_levels_without_a_brief(self):
        session = dict(session="MCX", instruments=dict(CRUDEOIL=dict(
            available=True,
            session=dict(available=True, open=10000.0, high=10300.0, low=9950.0, close=10250.0),
            prior_levels=dict(atr14=300.0, pivots=dict(P=10100.0, R1=10280.0, S1=9900.0)))))
        row = scorecard.build_rows(date(2026, 9, 15), session, {}, {})[0]
        self.assertEqual((row["outcome"], row["move_vs_atr"]), ("up", 0.83))
        self.assertIs(row["touched_r1"], True)
        self.assertIsNone(row["analyst_correct"])              # no brief to grade
        self.assertIsNone(row["rule_bias"])

    def test_rerunning_a_date_replaces_its_rows(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(scorecard, "data_dir", lambda *a: Path(tmp)):
                first = scorecard.build_rows(date(2026, 9, 15), self.SESSION, self.PREMARKET,
                                             {"CRUDEOIL": "bullish", "SILVER": "bearish"})
                scorecard.append_rows(first)
                _, out = scorecard.append_rows(first)                 # same date again
        self.assertEqual(len(out), len(first))
        self.assertEqual(len({(r["date"], r["underlying"]) for r in out}), len(first))

    def test_hit_rates(self):
        rates = scorecard.hit_rates([
            dict(underlying="CRUDEOIL", analyst_correct=True, rule_correct=True),
            dict(underlying="CRUDEOIL", analyst_correct=False, rule_correct=True),
            dict(underlying="SILVER", analyst_correct=None, rule_correct=None),
        ])
        self.assertEqual(rates["by_underlying"]["CRUDEOIL"]["analyst"], dict(graded=2, correct=1, pct=50.0))
        self.assertEqual(rates["by_underlying"]["SILVER"]["analyst"]["graded"], 0)
        self.assertEqual(rates["overall"]["rule"]["pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
