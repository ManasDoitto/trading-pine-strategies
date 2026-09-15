import math
import unittest
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from trading_agents.core import levels, options, signals
from trading_agents.core.config import load_config
from trading_agents.facts.premarket import rounded, rule_bias

PCFG = load_config()["premarket"]


def bars_from(closes, start=datetime(2026, 9, 1, 9, 15), step=5, wick=1.0):
    t = [start + timedelta(minutes=step * i) for i in range(len(closes))]
    c = np.asarray(closes, dtype=float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame(dict(time=t, open=o, high=np.maximum(o, c) + wick, low=np.minimum(o, c) - wick,
                             close=c, volume=100))


class LevelsTest(unittest.TestCase):
    def test_prev_day_pivots_and_today_excluded(self):
        rows = []
        for d, (h, l, c) in enumerate([(110, 90, 100), (120, 95, 115), (130, 100, 125)]):
            day = datetime(2026, 9, 14 + d, 10, 0)
            rows += [dict(time=day, open=100, high=h, low=l, close=c - 1, volume=1),
                     dict(time=day + timedelta(minutes=5), open=c - 1, high=c, low=c - 2, close=c, volume=1)]
        s = levels.level_summary(pd.DataFrame(rows), date(2026, 9, 16))
        self.assertEqual((s["prev_day"]["high"], s["prev_day"]["low"], s["prev_day"]["close"]), (120, 95, 115))
        p = (120 + 95 + 115) / 3
        self.assertAlmostEqual(s["pivots"]["P"], p)
        self.assertAlmostEqual(s["pivots"]["R1"], 2 * p - 95)
        self.assertEqual(s["prev_day_change_pts"], 15)
        self.assertGreater(s["atr14"], 0)

    def test_not_enough_history(self):
        self.assertFalse(levels.level_summary(bars_from([1, 2, 3]), date(2026, 9, 2))["available"])


class SignalsTest(unittest.TestCase):
    P = dict(name="t", sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, min_sl=1.5, max_sl=3.0, rr=4.0,
             session=["00:00", "23:59"])

    def closes(self, n=1200):
        return [100 + 10 * math.sin(i / 40) + 0.02 * i for i in range(n)]

    def test_ha_open_recursion_matches_pine(self):
        df = signals.v40_frame(bars_from(self.closes(60)), self.P)
        o1 = signals.ema(df["open"], 10)
        c1 = signals.ema(df["close"], 10)
        h1, l1 = signals.ema(df["high"], 10), signals.ema(df["low"], 10)
        ha_c = (o1 + h1 + l1 + c1) / 4
        ha_o0 = (o1[0] + c1[0]) / 2
        ha_o1 = (ha_o0 + ha_c[0]) / 2
        up1 = signals.ema(pd.Series([ha_c[0], ha_c[1]]), 10).iat[1] > signals.ema(pd.Series([ha_o0, ha_o1]), 10).iat[1]
        self.assertEqual(bool(df["sha_up"].iat[1]), bool(up1))

    def forced(self, longs, shorts, p=None):
        # a smooth sine rarely lines SHA flips up with the EMA9/22 side, so force signals on known bars
        df = signals.v40_frame(bars_from(self.closes()), p or self.P)
        df["ok_l"] = df.index.isin(longs)
        df["ok_s"] = df.index.isin(shorts)
        return df

    def test_flips_exist_and_are_exclusive(self):
        df = signals.v40_frame(bars_from(self.closes()), self.P)
        self.assertGreater(int(df["flip_up"].sum()), 2)
        self.assertGreater(int(df["flip_dn"].sum()), 2)
        self.assertFalse((df["flip_up"] & df["flip_dn"]).any())

    def test_bracket_geometry_and_next_open_fill(self):
        df = self.forced([300, 700], [500, 900])
        trades, pos, pending = signals.simulate(df, self.P)
        self.assertGreaterEqual(len(trades), 2)
        opens = dict(zip(df["time"], df["open"]))
        for t in trades:
            sign = 1 if t["side"] == "LONG" else -1
            sig_close = t["sl"] + sign * t["risk_pts"]
            self.assertAlmostEqual((t["tp"] - sig_close) * sign, 4.0 * t["risk_pts"])
            self.assertEqual(t["entry"], opens[t["entry_time"]])
            self.assertGreater(t["entry_time"], t["signal_time"])
            self.assertIn(t["result"], ("SL", "TP"))
            self.assertAlmostEqual(t["exit"], t["sl"] if t["result"] == "SL" else t["tp"])
        self.assertLessEqual(sum(1 for x in (pos, pending) if x), 1)

    def test_state_keys(self):
        s = signals.v40_state(bars_from(self.closes()), self.P)
        self.assertTrue(s["available"])
        self.assertIn(s["alignment"], ("long-aligned", "short-aligned", "mixed"))
        self.assertEqual(set(s["if_flip_now"]), {"long", "short"})
        self.assertFalse(signals.v40_state(bars_from(self.closes(100)), self.P)["available"])

    def test_daily_loss_limit_locks_day(self):
        p = dict(self.P, day_loss_limit_pts=0.01)
        df = self.forced(list(range(260, 1150, 15)), [], p)
        trades, _, _ = signals.simulate(df, p)
        self.assertTrue(any(t["pnl_pts"] < 0 for t in trades))
        # as in the Pine, the limit is on the day's NET realised P&L by exit day; once it trips,
        # no further entry may happen that date
        by_exit_day = {}
        for t in sorted(trades, key=lambda t: t["exit_time"]):
            by_exit_day.setdefault(t["exit_time"].date(), []).append(t)
        for day, day_trades in by_exit_day.items():
            net, locked_at = 0.0, None
            for t in day_trades:
                net += t["pnl_pts"]
                if net <= -p["day_loss_limit_pts"]:
                    locked_at = t["exit_time"]
                    break
            if locked_at:
                after = [t for t in trades if t["entry_time"].date() == day and t["entry_time"] > locked_at]
                self.assertEqual(after, [], f"entry after the day was locked at {locked_at}")


def chain(strikes, F, oi=1000, vol=500, iv=18.0, ltp_fn=None, stale=False, spread=1.0, chain_price=None):
    oc = {}
    for k in strikes:
        ce_ltp = max(F - k, 0) + 50 if ltp_fn is None else ltp_fn(k, "CE")
        pe_ltp = max(k - F, 0) + 50 if ltp_fn is None else ltp_fn(k, "PE")
        leg = lambda ltp, o, delta: {"last_price": ltp, "implied_volatility": iv, "oi": o, "previous_oi": o / 2,
                                     "volume": 0 if stale else vol, "previous_volume": 0 if stale else vol,
                                     "previous_close_price": ltp if stale else ltp + 5,
                                     "top_bid_price": ltp - spread / 2, "top_ask_price": ltp + spread / 2,
                                     "greeks": {"delta": delta, "theta": -8.0}}
        oc[f"{k:.6f}"] = {"ce": leg(ce_ltp, oi * (1 + (k > F)), 0.5), "pe": leg(pe_ltp, oi * (1 + 2 * (k < F)), -0.5)}
    return {"last_price": chain_price or F, "oc": oc}


class OptionsTest(unittest.TestCase):
    AS_OF = datetime(2026, 9, 10, 8, 30)
    KEEP_DHAN = dict(PCFG, max_iv_model_gap=1e9)      # fixture premiums aren't IV-consistent

    def test_atm_pcr_walls_theta(self):
        strikes = [9500 + 50 * i for i in range(9)]
        s = options.summarize_chain(chain(strikes, 9712), "CRUDEOIL", date(2026, 10, 15), self.AS_OF,
                                    self.KEEP_DHAN, 9710)
        self.assertEqual(s["atm_strike"], 9700)
        self.assertEqual(s["dte"], 35)
        self.assertTrue(s["usable"], s["flags"])
        self.assertAlmostEqual(s["straddle"], 62 + 50)          # CE 12 intrinsic + 50, PE OTM 50
        self.assertEqual(s["max_pe_oi_strike"], 9500)
        self.assertEqual(s["max_ce_oi_strike"], 9750)
        self.assertGreater(s["pcr_oi"], 1)
        ce = s["atm"]["ce"]
        self.assertAlmostEqual(ce["move_to_cover_1d_theta_pts"], 16.0)
        self.assertAlmostEqual(ce["theta_pct_of_premium"], 8 / 62 * 100)
        self.assertIsNotNone(ce["b76_iv"])
        self.assertEqual(ce["iv_source"], "dhan")

    def test_stale_chain_underlying_recentres_and_uses_black76(self):
        # crude pre-open 2026-09-16: chain said 9,706, futures closed 10,215; premiums priced off 10,215
        from trading_agents.core import black76
        F, T = 10215.0, options.years_to_expiry(date(2026, 9, 17), "23:30", self.AS_OF)
        px = lambda k, right: round(black76.price(F, k, T, 0.78, 0.065, right), 1)
        strikes = [10000 + 50 * i for i in range(9)]
        s = options.summarize_chain(chain(strikes, F, iv=140.0, ltp_fn=px, chain_price=9706), "CRUDEOIL",
                                    date(2026, 9, 17), self.AS_OF, PCFG, F)
        self.assertEqual((s["atm_strike"], s["underlying_price"], s["underlying_price_source"]),
                         (10200, F, "futures close"))
        self.assertTrue(s["usable"], s["flags"])
        for leg in s["atm"].values():
            self.assertTrue(leg["iv_source"].startswith("black76"))
            self.assertAlmostEqual(leg["iv"], 78.0, delta=0.5)
            self.assertEqual(leg["dhan_iv"], 140.0)

    def test_wide_spread_is_a_hard_gate(self):
        strikes = [230000 + 1000 * i for i in range(5)]
        s = options.summarize_chain(chain(strikes, 232036, oi=8, vol=13, spread=5000), "SILVER",
                                    date(2026, 9, 24), self.AS_OF, self.KEEP_DHAN, 232036)
        self.assertFalse(s["usable"])
        self.assertIn("wide bid-ask spread", s["flags"])

    def test_silver_like_stale_chain_is_unusable(self):
        strikes = [226000 + 1000 * i for i in range(5)]
        s = options.summarize_chain(chain(strikes, 227295, oi=0, iv=833.0, stale=True), "SILVER",
                                    date(2026, 9, 24), self.AS_OF, PCFG, 232690)
        self.assertFalse(s["usable"])
        for flag in ("no open interest", "no traded volume", "stale last price"):
            self.assertIn(flag, s["flags"])
        self.assertTrue(any("chain underlying price stale" in f for f in s["flags"]))

    def test_empty_chain(self):
        s = options.summarize_chain({"last_price": 0, "oc": {}}, "CRUDEOIL", date(2026, 10, 15), self.AS_OF, PCFG)
        self.assertFalse(s["usable"])


class PremarketHelpersTest(unittest.TestCase):
    def test_rounded(self):
        out = rounded({"a": np.float64(1.23456), "b": np.bool_(True), "c": date(2026, 9, 16),
                       "d": [np.int64(3), float("nan")], 5: pd.Timestamp("2026-09-16 09:15")})
        self.assertEqual(out, {"a": 1.23, "b": True, "c": "2026-09-16", "d": [3, None], "5": "2026-09-16T09:15:00"})

    def test_rule_bias(self):
        und = dict(available=True, prev_day=dict(close=110, close_position_pct=80), pivots=dict(P=100))
        self.assertEqual(rule_bias(und, dict(available=True, alignment="long-aligned"))[0], "bullish")
        self.assertEqual(rule_bias(und, dict(available=True, alignment="short-aligned"))[0], "neutral")
        self.assertEqual(rule_bias(und, dict(available=False))[0], "bullish")
        und_low = dict(available=True, prev_day=dict(close=90, close_position_pct=20), pivots=dict(P=100))
        self.assertEqual(rule_bias(und_low, dict(available=False))[0], "bearish")
        self.assertEqual(rule_bias(dict(available=False), {})[0], "neutral")


if __name__ == "__main__":
    unittest.main()
