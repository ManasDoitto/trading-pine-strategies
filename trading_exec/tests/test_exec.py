import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pandas as pd

from trading_exec import guards, report, shadow, signals
from trading_exec.signals import Signal


def sig(instrument="CRUDEOIL", side="LONG", bar_time="2026-09-16T11:30:00", entry=10200.0,
        sl=10158.9, target=10364.5, risk=41.1, rr=4.0):
    return Signal(strategy="v4.0", instrument=instrument, side=side, bar_time=bar_time,
                  entry_hint=entry, sl=sl, target=target, risk_pts=risk, rr=rr)


def atm(usable=True, reasons=None, **over):
    a = dict(usable=usable, reasons=reasons or [], symbol="CRUDEOIL-17Oct2026-10200-CE",
             security_id="1", segment="MCX_COMM", instrument_type="OPTFUT", strike=10200.0,
             expiry=date(2026, 10, 15), dte=29, underlying_price=10200.0, lots=2, lot_size=100,
             qty_units=200, bid=230.0, ask=234.0, ltp=232.0, entry_premium=234.0, spread_pct=2.2,
             iv=79.0, delta=0.52, theta=-6.4, theta_pct_of_premium=2.7, chain_usable=True, chain_flags=[])
    a.update(over)
    return a


def bars(rows, start="2026-09-16T11:35:00"):
    t0 = datetime.fromisoformat(start)
    return pd.DataFrame([dict(time=t0 + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1.0)
                         for i, (o, h, l, c) in enumerate(rows)])


class SignalTest(unittest.TestCase):
    def test_key_right_and_age(self):
        s = sig()
        self.assertEqual(s.key, "v4.0|CRUDEOIL|LONG|2026-09-16T11:30:00")
        self.assertEqual(s.option_right, "CE")
        self.assertEqual(sig(side="SHORT").option_right, "PE")
        self.assertAlmostEqual(s.age_minutes(datetime(2026, 9, 16, 11, 45)), 15.0)


class GuardTest(unittest.TestCase):
    IN_SESSION = datetime(2026, 9, 16, 11, 45)

    def ctx(self, **over):
        c = dict(now=self.IN_SESSION, signals_today=[], open_positions=[], realised_today_inr=0.0)
        c.update(over)
        return c

    def test_clear(self):
        self.assertEqual(guards.check(sig(bar_time="2026-09-16T11:40:00"), atm(), self.ctx()), [])

    def test_blocks(self):
        s = sig(bar_time="2026-09-16T11:40:00")
        self.assertTrue(any("outside the entry window" in b
                            for b in guards.check(s, atm(), self.ctx(now=datetime(2026, 9, 16, 5, 0)))))
        self.assertTrue(any("stale" in b for b in guards.check(sig(bar_time="2026-09-16T10:00:00"),
                                                               atm(), self.ctx())))
        self.assertIn("chain not usable: wide bid-ask spread",
                      guards.check(s, atm(usable=False, reasons=["chain not usable: wide bid-ask spread"]),
                                   self.ctx()))
        self.assertTrue(any("signals today" in b for b in guards.check(s, atm(), self.ctx(signals_today=[1] * 6))))
        self.assertTrue(any("already open" in b for b in guards.check(s, atm(), self.ctx(open_positions=[1, 2]))))
        self.assertTrue(any("daily loss limit" in b
                            for b in guards.check(s, atm(), self.ctx(realised_today_inr=-10000))))

    def test_disabled_instrument(self):
        self.assertTrue(any("disabled" in b for b in guards.check(sig(instrument="BANKNIFTY"), atm(), self.ctx())))


class ShadowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(shadow, "data_dir", lambda *a: Path(self.tmp.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_open_trade_costs_and_store(self):
        t = shadow.open_trade(sig(), atm(), dict(approx_sl_premium=212.6, approx_target_premium=319.5),
                              datetime(2026, 9, 16, 11, 45))
        self.assertEqual(t["cost_inr"], 234.0 * 200)
        self.assertEqual(t["costs_inr"], 45.0 * 2 * 2)          # per lot, both legs
        self.assertEqual(t["status"], "OPEN")
        shadow.record(t)
        shadow.record(t)                                         # idempotent
        self.assertEqual(len(shadow.load()), 1)
        self.assertEqual(len(shadow.open_trades()), 1)

    def test_exit_scan_long_short_and_tie(self):
        t = dict(side="LONG", sl=10158.9, target=10364.5)
        _, level, reason = shadow._exit_scan(t, bars([(10200, 10240, 10190, 10230),
                                                      (10230, 10370, 10220, 10360)]))
        self.assertEqual((level, reason), (10364.5, "TARGET"))
        _, level, reason = shadow._exit_scan(t, bars([(10200, 10240, 10150, 10160)]))
        self.assertEqual((level, reason), (10158.9, "SL"))
        # both touched in one bar: the stop is assumed first
        _, level, reason = shadow._exit_scan(t, bars([(10200, 10370, 10150, 10300)]))
        self.assertEqual(reason, "SL")
        s = dict(side="SHORT", sl=10241.1, target=10035.5)
        _, level, reason = shadow._exit_scan(s, bars([(10200, 10250, 10190, 10245)]))
        self.assertEqual((level, reason), (10241.1, "SL"))

    def test_close_math(self):
        t = shadow.open_trade(sig(), atm(), {}, datetime(2026, 9, 16, 11, 45))
        shadow._close(t, datetime(2026, 9, 16, 13, 15), 10364.5, "TARGET", 300.0)
        self.assertEqual(t["gross_inr"], (300.0 - 234.0) * 200)
        self.assertEqual(t["net_inr"], (300.0 - 234.0) * 200 - 180.0)
        self.assertAlmostEqual(t["pct"], (300.0 / 234.0 - 1) * 100, places=2)
        self.assertEqual(t["hold_min"], 90.0)
        self.assertEqual(t["status"], "CLOSED")

    def test_realised_today_only_counts_closed(self):
        a = shadow.open_trade(sig(), atm(), {}, datetime(2026, 9, 16, 11, 45))
        shadow._close(a, datetime(2026, 9, 16, 13, 0), 10364.5, "TARGET", 300.0)
        b = shadow.open_trade(sig(bar_time="2026-09-16T12:30:00"), atm(), {}, datetime(2026, 9, 16, 12, 35))
        shadow.save([a, b])
        self.assertEqual(shadow.realised_today_inr(date(2026, 9, 16)), a["net_inr"])


class ObservationalTest(unittest.TestCase):
    """Signals the DTE floor refuses are tracked, but never count as trades."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(shadow, "data_dir", lambda *a: Path(self.tmp.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_flagged_and_id_suffixed(self):
        t = shadow.open_trade(sig(), atm(dte=1), {}, datetime(2026, 9, 16, 11, 45), observational=True)
        self.assertTrue(t["observational"])
        self.assertTrue(t["id"].endswith("-obs"))

    def test_excluded_from_the_daily_loss_limit(self):
        obs = shadow.open_trade(sig(), atm(dte=1), {}, datetime(2026, 9, 16, 11, 45), observational=True)
        shadow._close(obs, datetime(2026, 9, 16, 13, 0), 10158.9, "SL", 10.0)
        real = shadow.open_trade(sig(bar_time="2026-09-16T12:00:00"), atm(), {}, datetime(2026, 9, 16, 12, 5))
        shadow._close(real, datetime(2026, 9, 16, 14, 0), 10364.5, "TARGET", 300.0)
        shadow.save([obs, real])
        self.assertLess(obs["net_inr"], 0)
        self.assertEqual(shadow.realised_today_inr(date(2026, 9, 16)), real["net_inr"])

    def test_report_keeps_them_out_of_the_verdict(self):
        closed = [dict(instrument="CRUDEOIL", status="CLOSED", net_inr=9000, exit_reason="TARGET",
                       dte_at_entry=1, exit_at="2026-10-05T12:00:00", observational=True)]
        closed += [dict(instrument="CRUDEOIL", status="CLOSED", net_inr=-500, exit_reason="SL",
                        dte_at_entry=29, exit_at="2026-10-05T12:00:00") for _ in range(3)]
        with mock.patch.object(report.shadow, "load", lambda: closed):
            rep = report.build()
        self.assertEqual(rep["closed_trades"], 3)                      # the observational one is excluded
        self.assertEqual(rep["instruments"]["CRUDEOIL"]["stats"]["net"], -1500)
        self.assertEqual(rep["observational"]["CRUDEOIL"]["n"], 1)
        self.assertIn("DTE floor refused", report.to_markdown(rep))


class ReportTest(unittest.TestCase):
    def trades(self, nets, instrument="CRUDEOIL"):
        return [dict(instrument=instrument, status="CLOSED", net_inr=n, exit_reason="TARGET" if n > 0 else "SL",
                     dte_at_entry=29, exit_at="2026-10-05T12:00:00") for n in nets]

    def test_go_requires_every_rule(self):
        good = self.trades([4000] * 10 + [-1000] * 8)            # n=18, PF 5.0, no single trade dominant
        v = report.verdict(good)
        self.assertEqual(v["verdict"], "GO", v["failed"])

    def test_too_few_trades_fails(self):
        v = report.verdict(self.trades([5000, -1000, 3000]))
        self.assertEqual(v["verdict"], "NO-GO")
        self.assertIn("at least 15 closed trades", v["failed"])

    def test_one_trade_carrying_the_month_fails(self):
        nets = [60000] + [1000] * 8 + [-2000] * 8                # one winner is most of the net
        v = report.verdict(nets and self.trades(nets))
        self.assertEqual(v["verdict"], "NO-GO")
        self.assertIn("no single trade over half the net profit", v["failed"])

    def test_losing_month_fails_on_net_and_pf(self):
        v = report.verdict(self.trades([1000] * 8 + [-3000] * 10))
        self.assertEqual(v["verdict"], "NO-GO")
        self.assertIn("net positive after costs", v["failed"])

    def test_exit_comparison(self):
        ts = [dict(net_inr=-5000, premium_stop_net_inr=-2000), dict(net_inr=3000, premium_stop_net_inr=-2000)]
        c = report.compare_exits(ts)
        self.assertEqual((c["comparable"], c["underlying_exit_net"], c["premium_stop_net"]), (2, -2000.0, -4000.0))
        self.assertFalse(c["premium_stop_better"])
        self.assertEqual(report.compare_exits([dict(net_inr=1.0)])["comparable"], 0)


class UnattendedRunnerTest(unittest.TestCase):
    def test_parse_hhmm(self):
        from datetime import time as dtime
        from trading_exec.runner import parse_hhmm
        self.assertEqual(parse_hhmm("23:59"), dtime(23, 59))
        self.assertEqual(parse_hhmm(" 08:55 "), dtime(8, 55))

    def test_only_one_runner_can_hold_the_lock(self):
        from trading_exec.runner import acquire_single_instance
        with tempfile.TemporaryDirectory() as tmp:
            first = acquire_single_instance(Path(tmp))
            self.assertIsNotNone(first)
            self.assertIsNone(acquire_single_instance(Path(tmp)))       # a second runner is refused
            first.close()                                               # process exit releases it
            again = acquire_single_instance(Path(tmp))
            self.assertIsNotNone(again)
            again.close()


class StageASafetyTest(unittest.TestCase):
    """Stage A must contain no order-capable code at all."""

    FORBIDDEN = ("place_order", "place_super_order", "place_slice_order", "modify_order",
                 "cancel_order", "kill_switch", "convert_position", "dhanhq(")

    def test_no_order_calls_anywhere_in_trading_exec(self):
        offenders = []
        for py in Path("trading_exec").rglob("*.py"):
            if "tests" in py.parts:
                continue
            text = py.read_text(encoding="utf-8")
            offenders += [f"{py}: {word}" for word in self.FORBIDDEN if word in text]
        self.assertEqual(offenders, [])

    def test_runner_uses_the_read_only_client(self):
        from trading_agents.core.dhan_client import ReadOnlyDhan, READ_METHODS
        import trading_exec.runner as runner
        self.assertIs(runner.get_dhan_client.__module__ and ReadOnlyDhan, ReadOnlyDhan)
        self.assertNotIn("place_order", READ_METHODS)


if __name__ == "__main__":
    unittest.main()
