import math
import unittest
from datetime import date, datetime
from unittest import mock

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


class MarketDataFailureTest(unittest.TestCase):
    """An API failure must raise, not look like an empty market (DH-901 token expiry, 2026-09-16)."""

    class Failing:
        def intraday_minute_data(self, **k):
            return {"status": "failure", "data": "",
                    "remarks": {"error_code": "DH-901", "error_type": "Invalid_Authentication",
                                "error_message": "Client ID or user generated access token is invalid or expired."}}

        def historical_daily_data(self, **k):
            return self.intraday_minute_data()

    class Empty:
        def intraday_minute_data(self, **k):
            return {"status": "success", "data": {"open": [], "high": [], "low": [], "close": [],
                                                  "volume": [], "timestamp": []}}

    def test_failure_raises_with_token_hint(self):
        from trading_agents.core.market_data import DhanApiError, daily_bars, intraday_bars
        for call in (lambda: intraday_bars(self.Failing(), "1", "MCX_COMM", "FUTCOM",
                                           date(2026, 9, 15), date(2026, 9, 16)),
                     lambda: daily_bars(self.Failing(), "1", "MCX_COMM", "FUTCOM",
                                        date(2026, 9, 15), date(2026, 9, 16))):
            with self.assertRaises(DhanApiError) as cm:
                call()
            self.assertIn("DH-901", str(cm.exception))
            self.assertIn("DHAN_ACCESS_TOKEN", str(cm.exception))

    def test_genuinely_empty_success_is_not_an_error(self):
        from trading_agents.core.market_data import intraday_bars
        df = intraday_bars(self.Empty(), "1", "MCX_COMM", "FUTCOM", date(2026, 9, 15), date(2026, 9, 16))
        self.assertTrue(df.empty)
        self.assertEqual(list(df.columns), ["time", "open", "high", "low", "close", "volume"])


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


class TradeBookFormatTest(unittest.TestCase):
    """Today's fills come from the trade book: different symbol format, drvOptionType "NA", and
    MCX quantity in LOTS. Verified against a real session on 2026-09-16."""

    def tb(self, side, lots, px, time="2026-09-16T19:52:37", sym="CRUDEOIL-17Sep2026-8000-PE",
           expiry="2026-09-17", strike=8000.0):
        return {"_src": "tradebook", "orderId": f"TB{side}{lots}{px}", "exchangeTradeId": f"{side}{lots}{px}",
                "transactionType": side, "exchangeSegment": "MCX_COMM", "instrument": None,
                "productType": "MARGIN", "customSymbol": None, "tradingSymbol": sym,
                "drvExpiryDate": expiry, "drvStrikePrice": strike, "drvOptionType": "NA",
                "tradedQuantity": lots, "tradedPrice": px, "exchangeTime": time.replace("T", " "),
                "securityId": "576521"}

    def test_trading_symbol_parse(self):
        from trading_agents.core.option_symbols import parse_trading_symbol
        c = parse_trading_symbol("CRUDEOIL-17Sep2026-9900-PE")
        self.assertEqual((c.underlying, c.expiry, c.strike, c.right), ("CRUDEOIL", date(2026, 9, 17), 9900.0, "PE"))
        b = parse_trading_symbol("BANKNIFTY-Sep2026-55800-CE")
        self.assertEqual((b.underlying, b.expiry, b.strike, b.right), ("BANKNIFTY", None, 55800.0, "CE"))
        self.assertIsNone(parse_trading_symbol("CRUDEOIL 17 SEP 8000 PUT"))

    def test_tradebook_row_gets_contract_and_units(self):
        leg = trades.normalize_leg(self.tb("SELL", 3, 141.2, sym="CRUDEOIL-17Sep2026-9900-PE", strike=9900.0))
        self.assertEqual((leg["strike"], leg["right"], leg["expiry"]), (9900.0, "PE", date(2026, 9, 17)))
        self.assertEqual(leg["qty"], 300)                                  # 3 lots x 100

    def test_instrument_inferred_for_tradebook_rows(self):
        leg = trades.normalize_leg(self.tb("BUY", 1, 114.1, sym="CRUDEOIL-17Sep2026-9900-PE", strike=9900.0))
        self.assertEqual(leg["instrument"], "OPTFUT")                     # bars API rejects None (DH-905)
        nse = dict(self.tb("BUY", 30, 500.0, sym="BANKNIFTY-Sep2026-55800-CE", expiry="2026-09-29",
                           strike=55800.0), exchangeSegment="NSE_FNO")
        self.assertEqual(trades.normalize_leg(nse)["instrument"], "OPTIDX")

    def test_history_and_tradebook_close_as_one_position(self):
        # the real 16-Sep sequence: 600 units held from history, +11 lots today, -17 lots today
        rows = [fill("2026-09-04T19:51:36", "BUY", 500, 120.6, symbol="CRUDEOIL 17 SEP 8000 PUT",
                     expiry="2026-09-17", strike=8000.0),
                fill("2026-09-09T17:34:48", "BUY", 100, 38.0, symbol="CRUDEOIL 17 SEP 8000 PUT",
                     expiry="2026-09-17", strike=8000.0),
                self.tb("BUY", 11, 5.4, time="2026-09-16T18:40:29"),
                self.tb("SELL", 17, 4.6, time="2026-09-16T19:52:37")]
        legs = trades.normalize(rows)
        self.assertEqual(len({l["symbol"] for l in legs}), 1)             # one canonical contract
        rts, open_lots = trades.fifo_match(legs)
        self.assertEqual(open_lots, [])
        self.assertEqual(sum(r["qty"] for r in rts), 1700)
        self.assertTrue(all(r["side"] == "LONG" for r in rts))            # no phantom sell-to-open
        eps = trades.episodes(legs)
        self.assertEqual(len(eps), 1)
        self.assertEqual((eps[0]["direction"], eps[0]["status"], eps[0]["adds_against"]), ("LONG", "CLOSED", 2))
        expected = (4.6 * 1700) - (500 * 120.6 + 100 * 38.0 + 1100 * 5.4)
        self.assertAlmostEqual(eps[0]["gross_pnl"], expected, places=2)


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


class ChartTest(unittest.TestCase):
    def test_svg_candles_markers_and_escaping(self):
        from datetime import timedelta
        from trading_agents.core.charts import candles_svg
        t0 = datetime(2026, 9, 9, 9, 0)
        bars = [dict(time=t0 + timedelta(minutes=5 * i), open=100 + i, high=102 + i, low=99 + i, close=101 + i)
                for i in range(30)]
        svg = candles_svg(bars, "T <&>", markers=[dict(time=t0 + timedelta(minutes=7), price=100.5, side="BUY",
                                                       label="B 100@100.5")],
                          vlines=[dict(time=t0 + timedelta(minutes=50), side="SELL", label="S 8000PE @38")])
        self.assertTrue(svg.startswith("<svg") and svg.endswith("</svg>"))
        self.assertEqual(svg.count('class="candle"'), 30)
        self.assertEqual((svg.count('class="marker"'), svg.count('class="fill-line"')), (1, 1))
        self.assertIn("T &lt;&amp;&gt;", svg)

    def test_empty(self):
        from trading_agents.core.charts import candles_svg
        self.assertIsNone(candles_svg([], "x"))


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


class ScripMasterLoaderTest(unittest.TestCase):
    """The scrip-master download must not hang forever, and a truncated/short response must never
    be cached and trusted for the rest of the day."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        from trading_agents.core import instruments
        self.instruments = instruments
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmp.name)
        self.patch = mock.patch.object(instruments, "data_dir", lambda *a: self.cache_dir)
        self.patch.start()
        instruments._cache, instruments._cache_date = None, None

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()
        self.instruments._cache, self.instruments._cache_date = None, None

    def good_df(self, n=150_000):
        import pandas as pd
        exch = (["MCX"] * (n // 2)) + (["NSE"] * (n - n // 2))
        return pd.DataFrame({"SEM_EXM_EXCH_ID": exch, "SEM_TRADING_SYMBOL": [f"X{i}" for i in range(n)],
                             "SEM_EXPIRY_DATE": ["2026-12-31"] * n})

    def test_a_truncated_download_is_rejected_and_retried(self):
        calls = []

        def fake_get(url, timeout=None, stream=None):
            calls.append(1)
            df = self.good_df(n=100) if len(calls) < 3 else self.good_df()   # short twice, then good

            class Resp:
                def raise_for_status(self):
                    pass

                def iter_content(self, chunk_size=None):
                    import io
                    buf = io.BytesIO()
                    df.to_csv(buf, index=False)
                    yield buf.getvalue()

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False
            return Resp()

        with mock.patch.object(self.instruments, "requests") as req, \
             mock.patch.object(self.instruments.time, "sleep", lambda s: None):
            req.get.side_effect = fake_get
            df = self.instruments.load_scrip_master()
        self.assertEqual(len(calls), 3)                                 # retried past the two short ones
        self.assertEqual(len(df), 150_000)
        self.assertEqual(list(self.cache_dir.glob("*.tmp")), [])         # no leftover temp file

    def test_a_permanently_truncated_download_raises_rather_than_caching(self):
        def fake_get(url, timeout=None, stream=None):
            class Resp:
                def raise_for_status(self):
                    pass

                def iter_content(self, chunk_size=None):
                    yield b"SEM_EXM_EXCH_ID,SEM_TRADING_SYMBOL,SEM_EXPIRY_DATE\nMCX,X,2026-12-31\n"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False
            return Resp()

        with mock.patch.object(self.instruments, "requests") as req, \
             mock.patch.object(self.instruments.time, "sleep", lambda s: None):
            req.get.side_effect = fake_get
            with self.assertRaises(RuntimeError):
                self.instruments.load_scrip_master()
        self.assertEqual(list(self.cache_dir.glob("scrip_master_*.csv")), [])   # never cached

    def test_in_memory_cache_expires_at_midnight(self):
        from datetime import timedelta
        today, tomorrow = date.today(), date.today() + timedelta(days=1)
        with mock.patch.object(self.instruments.pd, "read_csv",
                               lambda p, low_memory=None: self.good_df(n=100_001)):
            (self.cache_dir / f"scrip_master_{today:%Y%m%d}.csv").write_text("x", encoding="utf-8")
            first = self.instruments.load_scrip_master()
            self.assertIs(self.instruments.load_scrip_master(), first)      # same process, same day: cached

            with mock.patch.object(self.instruments, "date") as fake_date:
                fake_date.today.return_value = tomorrow
                (self.cache_dir / f"scrip_master_{tomorrow:%Y%m%d}.csv").write_text("x", encoding="utf-8")
                second = self.instruments.load_scrip_master()
        self.assertIsNot(second, first)                                     # date changed: reloaded, not stale


if __name__ == "__main__":
    unittest.main()
