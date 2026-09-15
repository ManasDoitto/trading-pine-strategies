import math
import unittest
from datetime import date, datetime

from trading_agents.core import black76, rules, trades
from trading_agents.core.dhan_client import READ_METHODS, ReadOnlyDhan
from trading_agents.core.option_symbols import from_fill, parse_custom_symbol, underlying_of
from trading_agents.tests.fixtures import RULES, fill


class ReadOnlyClientTest(unittest.TestCase):
    class FakeRaw:
        def get_trade_book(self):
            return {"status": "success", "data": []}

        def place_order(self, *a, **k):
            raise AssertionError("must never be reachable")

        cancel_order = modify_order = kill_switch = convert_position = place_super_order = place_order

    def test_reads_pass_through(self):
        self.assertEqual(ReadOnlyDhan(self.FakeRaw()).get_trade_book()["status"], "success")

    def test_order_methods_unreachable(self):
        c = ReadOnlyDhan(self.FakeRaw())
        for name in ("place_order", "cancel_order", "modify_order", "kill_switch",
                     "convert_position", "place_super_order", "_raw_place"):
            with self.assertRaises(AttributeError):
                getattr(c, name)
        with self.assertRaises(AttributeError):
            c.place_order = lambda: None

    def test_allowlist_has_no_write_verbs(self):
        bad = ("place", "modify", "cancel", "convert", "kill", "generate", "edis", "margin")
        self.assertFalse([m for m in READ_METHODS if m.startswith(bad)])

    def test_allowlist_exists_on_dhanhq(self):
        from dhanhq import dhanhq
        self.assertFalse([m for m in READ_METHODS if not hasattr(dhanhq, m)])


class OptionSymbolTest(unittest.TestCase):
    def test_structured_fields(self):
        c = from_fill(fill("2026-08-05T10:00:00", "BUY", 100, 231))
        self.assertEqual((c.underlying, c.expiry, c.strike, c.right), ("CRUDEOIL", date(2026, 8, 17), 7000.0, "PE"))

    def test_custom_symbol_fallback_and_year_rollover(self):
        c = parse_custom_symbol("BANKNIFTY 27 JAN 55000 CALL", date(2026, 12, 20))
        self.assertEqual((c.expiry, c.right), (date(2027, 1, 27), "CE"))

    def test_underlying_of(self):
        self.assertEqual(underlying_of("SILVERM 24 SEP 285000 CALL"), "SILVERM")
        self.assertEqual(underlying_of("SILVER-24Sep2026-283000-CE"), "SILVER")


class FifoAndEpisodeTest(unittest.TestCase):
    def legs(self, rows):
        return trades.normalize(rows)

    def test_long_partial_exits_and_costs(self):
        legs = self.legs([
            fill("2026-08-05T10:00:00", "BUY", 200, 100, brokerage=20),
            fill("2026-08-05T10:30:00", "SELL", 100, 120, brokerage=10),
            fill("2026-08-05T11:00:00", "SELL", 100, 90, brokerage=10),
        ])
        rts, open_lots = trades.fifo_match(legs)
        self.assertEqual(len(rts), 2)
        self.assertEqual([rt["gross_pnl"] for rt in rts], [2000, -1000])
        self.assertAlmostEqual(sum(rt["costs"] for rt in rts), 40)
        self.assertEqual(open_lots, [])
        eps = trades.episodes(legs)
        self.assertEqual(len(eps), 1)
        self.assertAlmostEqual(eps[0]["net_pnl"], sum(rt["net_pnl"] for rt in rts))

    def test_short_side(self):
        rts, _ = trades.fifo_match(self.legs([
            fill("2026-08-05T10:00:00", "SELL", 100, 50),
            fill("2026-08-05T10:10:00", "BUY", 100, 30),
        ]))
        self.assertEqual((rts[0]["side"], rts[0]["gross_pnl"]), ("SHORT", 2000))

    def test_averaging_down_episode(self):
        # the CRUDEOIL 7000 PUT pattern: repeated buys into a decaying option, held to expiry
        prices = [231, 213, 131, 120, 111, 89, 37, 14]
        rows = [fill(f"2026-08-{5 + i:02d}T11:00:00", "BUY", 100 * (i + 1), p) for i, p in enumerate(prices)]
        rows.append(fill("2026-08-17T23:00:00", "SELL", sum(100 * (i + 1) for i in range(len(prices))), 0.2))
        eps = trades.episodes(self.legs(rows))
        self.assertEqual(len(eps), 1)
        ep = eps[0]
        self.assertEqual(ep["adds_against"], 7)
        self.assertLess(ep["pct"], -95)

    def test_sliced_order_is_not_an_add(self):
        rows = [fill("2026-08-05T10:00:00", "BUY", 100, 100, order_id="A"),
                fill("2026-08-05T10:00:05", "BUY", 100, 99.5, order_id="B"),
                fill("2026-08-05T10:20:00", "SELL", 200, 110)]
        ep = trades.episodes(self.legs(rows))[0]
        self.assertEqual((ep["adds"], ep["status"]), ([], "CLOSED"))

    def test_open_episode(self):
        ep = trades.episodes(self.legs([fill("2026-08-05T10:00:00", "BUY", 100, 50)]))[0]
        self.assertEqual((ep["status"], ep["open_qty"], ep["net_pnl"]), ("OPEN", 100, None))

    def test_merge_prefers_first_source(self):
        a = fill("2026-08-05T10:00:00", "BUY", 100, 50, order_id="X", brokerage=20)
        b = dict(a, brokerageCharges=0.0, exchangeTime="2026-08-05 10:00:00")
        merged = trades.merge_raw([a], [b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["brokerageCharges"], 20)


class RulesTest(unittest.TestCase):
    AS_OF = datetime(2026, 8, 20, 23, 45)

    def check(self, rows, **overrides):
        legs = trades.normalize(rows)
        eps = trades.episodes(legs, RULES["r1_min_gap_minutes"])
        for ep in eps:
            ep.update(overrides)
        rts, _ = trades.fifo_match(legs)
        return {v["rule"] for v in rules.check_all(eps, rts, RULES, self.AS_OF)}

    def test_avg_down_overnight_expiry_premium_stop(self):
        rows = [fill("2026-08-10T11:00:00", "BUY", 100, 200),
                fill("2026-08-12T11:00:00", "BUY", 100, 120),
                fill("2026-08-16T11:00:00", "BUY", 100, 40),
                fill("2026-08-17T22:00:00", "SELL", 300, 1)]
        got = self.check(rows)
        self.assertTrue({"R1", "R2", "R3", "R4", "R5"} <= got, got)

    def test_clean_intraday_scalp(self):
        got = self.check([fill("2026-08-05T10:00:00", "BUY", 100, 100),
                          fill("2026-08-05T10:40:00", "SELL", 100, 115)])
        self.assertEqual(got, set())

    def test_sell_to_open(self):
        self.assertIn("R8", self.check([fill("2026-08-05T10:00:00", "SELL", 100, 100),
                                        fill("2026-08-05T10:40:00", "BUY", 100, 80)]))

    def test_pre_history_sell_is_not_r8(self):
        self.assertEqual(self.check([fill("2026-08-05T10:00:00", "SELL", 100, 100)], pre_history=True), {"DATA"})

    def test_per_instrument_deep_otm_limit(self):
        rows = [fill("2026-08-05T10:00:00", "BUY", 100, 5), fill("2026-08-05T10:40:00", "SELL", 100, 6)]
        self.assertEqual(self.check(rows, strikes_otm=4.8, deep_otm_limit=6), set())
        self.assertEqual(self.check(rows, strikes_otm=6.0, deep_otm_limit=6), {"R7"})

    def test_moneyness_buckets(self):
        b = trades.moneyness_bucket
        self.assertEqual([b(-1.2, 6), b(0.3, 6), b(4.8, 6), b(6, 6), b(None, 6)],
                         ["ITM", "ATM", "OTM near", "OTM deep", "unknown"])

    def test_deep_otm(self):
        got = self.check([fill("2026-08-05T10:00:00", "BUY", 100, 5),
                          fill("2026-08-05T10:40:00", "SELL", 100, 6)], strikes_otm=4.0)
        self.assertEqual(got, {"R7"})

    def test_revenge_entry(self):
        rows = [fill("2026-08-05T10:00:00", "BUY", 100, 200, symbol="CRUDEOIL 17 AUG 7100 PUT", strike=7100),
                fill("2026-08-05T10:30:00", "SELL", 100, 120, symbol="CRUDEOIL 17 AUG 7100 PUT", strike=7100),
                fill("2026-08-05T10:35:00", "BUY", 100, 50),
                fill("2026-08-05T10:50:00", "SELL", 100, 55)]
        self.assertIn("R6", self.check(rows))


class LivePositionTest(unittest.TestCase):
    def test_mcx_lots_and_multiplier(self):
        # real shape seen 2026-09-16: Dhan unrealizedProfit (-597.8) omits the x100 multiplier
        from trading_agents.facts.journal import position_view
        p = {"tradingSymbol": "CRUDEOIL-17Sep2026-8000-PE", "netQty": 6, "multiplier": 100, "buyAvg": 106.83333,
             "sellAvg": 0.0, "unrealizedProfit": -597.8, "carryForwardBuyQty": 6, "productType": "MARGIN"}
        v = position_view(p, 7.2, lot_size=100)
        self.assertEqual((v["qty_units"], v["lots"], v["side"]), (600, 6, "LONG"))
        self.assertAlmostEqual(v["unrealized_inr"], -59780.0, places=0)
        self.assertEqual(v["carried_forward_units"], 600)

    def test_nse_units_no_ltp(self):
        from trading_agents.facts.journal import position_view
        v = position_view({"tradingSymbol": "BANKNIFTY-Sep2026-55800-CE", "netQty": 30, "multiplier": 1,
                           "buyAvg": 500.0}, None, lot_size=30)
        self.assertEqual((v["qty_units"], v["lots"], v["unrealized_inr"]), (30, 1, None))


class Black76Test(unittest.TestCase):
    # Hull, Options Futures & Other Derivatives: F=20, K=20, T=4m, r=9%, vol=25% -> c ~ 1.12
    F, K, T, r, s = 20.0, 20.0, 4 / 12, 0.09, 0.25

    def test_hull_example(self):
        self.assertAlmostEqual(black76.price(self.F, self.K, self.T, self.s, self.r, "CE"), 1.1168, places=3)

    def test_put_call_parity(self):
        c = black76.price(21, 20, self.T, self.s, self.r, "CE")
        p = black76.price(21, 20, self.T, self.s, self.r, "PE")
        self.assertAlmostEqual(c - p, math.exp(-self.r * self.T) * (21 - 20), places=9)

    def test_iv_roundtrip(self):
        for right in ("CE", "PE"):
            px = black76.price(9700, 9800, 5 / 365, 0.42, 0.065, right)
            self.assertAlmostEqual(black76.implied_vol(px, 9700, 9800, 5 / 365, 0.065, right), 0.42, places=4)

    def test_greeks_signs(self):
        g_c = black76.greeks(100, 100, 0.1, 0.3, 0.05, "CE")
        g_p = black76.greeks(100, 100, 0.1, 0.3, 0.05, "PE")
        self.assertAlmostEqual(g_c["delta"] - g_p["delta"], math.exp(-0.05 * 0.1), places=9)
        self.assertLess(g_c["theta"], 0)
        self.assertGreater(g_c["gamma"], 0)

    def test_iv_out_of_range(self):
        self.assertIsNone(black76.implied_vol(120, 100, 100, 0.1, 0.05, "CE"))   # call can't exceed F


if __name__ == "__main__":
    unittest.main()
