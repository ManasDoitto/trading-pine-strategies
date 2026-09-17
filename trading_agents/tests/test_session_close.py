import unittest
from unittest import mock
from datetime import date, datetime, timedelta

import pandas as pd

from trading_agents.core import signals_v04
from trading_agents.core.config import load_config
from trading_agents.facts.session_close import alignment, session_summary, strategy_session_v04
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


class StrategySessionV04Test(unittest.TestCase):
    """BankNifty's session block: armed setups and fills are reported separately."""

    P = load_config()["strategy"]["BANKNIFTY"]
    DAY = date(2026, 9, 15)

    def synthetic(self, days=6):
        import math
        rows = []
        for d in range(days):
            start = datetime(2026, 9, 10 + d, 9, 15)
            for k in range(75):
                c = 55000 + 300 * math.sin((d * 75 + k) / 17) + 2 * k
                rows.append(dict(time=start + timedelta(minutes=5 * k), open=c - 5, high=c + 20,
                                 low=c - 20, close=c, volume=1000 + 10 * k))
        return pd.DataFrame(rows)

    def test_short_history_says_so_instead_of_guessing(self):
        out = strategy_session_v04(self.synthetic(days=1), self.P, self.DAY)
        self.assertFalse(out["available"])
        self.assertIn("v0.4 needs", out["note"])

    def frame(self, n=300):
        t0 = datetime(2026, 9, 15, 9, 15)
        return pd.DataFrame(dict(time=[t0 + timedelta(minutes=5 * i) for i in range(n)],
                                 open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0))

    def canned(self, sim):
        """The synthetic sine series arms nothing, so the events are supplied directly: this test is
        about how strategy_session_v04 maps them, not about the strategy."""
        bars = self.frame()
        with mock.patch.object(signals_v04, "v04_frame", lambda b, p: bars),              mock.patch.object(signals_v04, "simulate", lambda d, p, start=0: sim):
            return strategy_session_v04(bars, self.P, self.DAY)

    def events(self):
        d = datetime(2026, 9, 15, 10, 0)
        trade = dict(side="LONG", arm_time=d, entry_time=d + timedelta(minutes=10), entry=56010.0,
                     sl=55900.0, tp=56285.0, risk_pts=110.0, exit_time=d + timedelta(minutes=40),
                     exit=56285.0, result="TARGET", pnl_pts=275.0, entry_bar=252, exit_bar=258)
        return dict(trades=[trade], position=None, live=dict(L=None, S=None), events=[
            dict(kind="armed", bar=250, time=d, side="LONG", arm_bar=250, arm_time=d, trig=56010.0,
                 sl=55900.0, tp=56285.0, risk_pts=110.0),
            dict(kind="filled", bar=252, time=d + timedelta(minutes=10), **trade),
            dict(kind="armed", bar=260, time=d + timedelta(minutes=50), side="SHORT", arm_bar=260,
                 arm_time=d + timedelta(minutes=50), trig=55800.0, sl=55900.0, tp=55550.0, risk_pts=100.0),
            dict(kind="expired", bar=269, time=d + timedelta(minutes=95), side="SHORT", arm_bar=260,
                 arm_time=d + timedelta(minutes=50), trig=55800.0, sl=55900.0, tp=55550.0, risk_pts=100.0),
        ])

    def test_armed_and_filled_are_reported_apart(self):
        out = self.canned(self.events())
        self.assertEqual(len(out["armed"]), 2)                      # two setups offered
        self.assertEqual(len(out["signals"]), 1)                    # one actually triggered
        self.assertEqual(out["armed_expired"], 1)                   # the other timed out
        self.assertEqual(out["flips"], 2)
        self.assertEqual(out["armed"][0]["trigger"], 56010.0)
        self.assertEqual((out["trades_net_pts"], out["wins"]), (275.0, 1))
        self.assertIsNone(out["open_at_close"])                     # v0.4 force-flats at 15:20
        self.assertEqual(out["signals"][0]["option_for_buyer"], "CE")

    def test_a_short_fill_maps_to_a_put(self):
        sim = self.events()
        for e in sim["events"]:
            e["side"] = "SHORT"
        sim["trades"][0]["side"] = "SHORT"
        out = self.canned(sim)
        self.assertEqual(out["signals"][0]["option_for_buyer"], "PE")

    def test_signals_are_shaped_for_the_alignment_check(self):
        out = self.canned(self.events())
        entry = dict(time=out["signals"][0]["time"], side="LONG", symbol="BANKNIFTY-56100-CE")
        self.assertEqual(alignment([entry], out["signals"], 15).get("matched_a_signal"), 1)
        against = dict(time=out["signals"][0]["time"], side="SHORT", symbol="BANKNIFTY-56100-PE")
        self.assertEqual(alignment([against], out["signals"], 15).get("matched_a_signal"), 0)


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
