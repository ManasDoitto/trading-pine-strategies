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


class SignalFidelityTest(unittest.TestCase):
    """Signals must be what the strategy would actually trade (measured 2026-09-17: a raw bar scan
    alerted 56-79% more often than the strategy enters)."""

    P = dict(name="t", sha_len1=10, sha_len2=10, sw_len=10, sw_buf=0.1, min_sl=1.5, max_sl=3.0, rr=4.0,
             session=["00:00", "23:59"])

    def frame(self, n, longs, params=None):
        import math
        from trading_agents.core import signals as v40
        from trading_agents.tests.test_premarket import bars_from
        closes = [100 + 10 * math.sin(i / 40) + 0.02 * i for i in range(n)]
        df = v40.v40_frame(bars_from(closes), params or self.P)
        df["ok_l"] = df.index.isin(longs)
        df["ok_s"] = False
        return df

    def test_entry_when_flat(self):
        from trading_exec.poller import entry_on_last_bar
        hit = entry_on_last_bar(self.frame(400, longs=[399]), self.P)
        self.assertIsNotNone(hit)
        pending, close = hit
        self.assertEqual(pending["side"], "LONG")
        self.assertAlmostEqual(pending["tp"] - close, 4.0 * pending["risk_pts"])

    def test_no_signal_while_already_in_a_trade(self):
        from trading_exec.poller import entry_on_last_bar
        # bar 398 enters (fills at 399's open); bar 399 qualifies too, but the strategy is not flat
        self.assertIsNone(entry_on_last_bar(self.frame(400, longs=[398, 399]), self.P))

    def test_no_signal_without_an_entry_on_the_last_bar(self):
        from trading_exec.poller import entry_on_last_bar
        self.assertIsNone(entry_on_last_bar(self.frame(400, longs=[]), self.P))

    def test_follows_simulate_including_the_daily_lock(self):
        from trading_exec import poller
        df = self.frame(400, longs=[399])
        last = df["time"].iat[-1]
        with mock.patch.object(poller.v40, "simulate", lambda d, p: ([], None, None)):       # e.g. day-locked
            self.assertIsNone(poller.entry_on_last_bar(df, self.P))
        stale = dict(side="LONG", signal_time=df["time"].iat[-3], risk_pts=1.0, sl=1.0, tp=5.0)
        with mock.patch.object(poller.v40, "simulate", lambda d, p: ([], None, stale)):
            self.assertIsNone(poller.entry_on_last_bar(df, self.P))
        fresh = dict(stale, signal_time=last)
        with mock.patch.object(poller.v40, "simulate", lambda d, p: ([], None, fresh)):
            self.assertIs(poller.entry_on_last_bar(df, self.P)[0], fresh)

    def test_silver_signals_come_from_silver(self):
        from trading_exec.config import instrument_cfg
        from trading_agents.core.config import load_config as agents_config
        self.assertEqual(instrument_cfg("SILVERM").get("signal_from"), "SILVER")
        self.assertEqual(agents_config()["strategy"]["SILVER"]["day_loss_limit_pts"], 350)

    def test_option_priced_off_its_own_future_not_the_signal(self):
        from trading_exec import atm as atm_mod

        class Client:
            def ticker_data(self, securities):
                (seg, ids), = securities.items()
                return {"data": {"data": {seg: {str(ids[0]): {"last_price": 233750.0}}}}}

        ref = dict(security_id="483080", segment="MCX_COMM", instrument="FUTCOM", expiry=date(2026, 11, 30),
                   label="SILVERM-30Nov2026-FUT")
        with mock.patch.object(atm_mod.instruments, "reference_series", lambda u, e: ref):
            self.assertEqual(atm_mod.underlying_ltp(Client(), "SILVERM", date(2026, 9, 24)), 233750.0)

    def test_shadow_exits_track_the_signal_series(self):
        calls = []

        def fake_bars(client, sid, seg, kind, start, end, interval=5):
            calls.append((sid, seg, kind))
            return bars([(1, 1, 1, 1)], start="2026-09-16T11:40:00")

        trade = dict(bar_time="2026-09-16T11:35:00", instrument="SILVERM", expiry="2026-09-24",
                     signal_security_id="495214", signal_segment="MCX_COMM", signal_series_type="FUTCOM")
        with mock.patch.object(shadow, "intraday_bars", fake_bars):
            shadow._underlying_bars(None, trade, datetime(2026, 9, 16, 12, 0))
        self.assertEqual(calls, [("495214", "MCX_COMM", "FUTCOM")])                  # the SILVER future


class ResilienceTest(unittest.TestCase):
    """The unattended checker must survive errors, say each problem once, and warn about the token."""

    def jwt(self, exp):
        import base64
        enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
        return f"{enc({'alg': 'HS512'})}.{enc({'exp': int(exp.timestamp()), 'iat': int(exp.timestamp()) - 86400})}.sig"

    def test_token_expiry_read_locally(self):
        from trading_exec import health
        exp = datetime(2026, 9, 18, 10, 21)
        self.assertEqual(health.token_expiry(self.jwt(exp)), exp)
        self.assertIsNone(health.token_expiry("not-a-jwt"))

    def test_token_status(self):
        from datetime import time as dtime
        from trading_exec import health
        now, close = datetime(2026, 9, 18, 9, 0), dtime(23, 59)
        self.assertEqual(health.token_status(datetime(2026, 9, 18, 8, 0), now, close), "expired")
        self.assertEqual(health.token_status(datetime(2026, 9, 18, 9, 40), now, close), "expires_within_hour")
        self.assertEqual(health.token_status(datetime(2026, 9, 18, 10, 21), now, close), "expires_before_close")
        self.assertEqual(health.token_status(datetime(2026, 9, 19, 8, 30), now, close), "ok")
        self.assertEqual(health.token_status(None, now, close), "unknown")

    def run_ticks(self, outcomes):
        from trading_exec import health, runner
        from trading_agents.core.market_data import DhanApiError
        sent, state, ref = [], runner.LoopState(), [None]
        results = iter(outcomes)

        def fake_tick(client, now):
            r = next(results)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(health, "token_from_env_file", lambda: "TOKEN-A"), \
             mock.patch.object(health, "fresh_client", lambda: object()):
            for _ in outcomes:
                runner.tick_safely(state, ref, lambda t, l, s="info": sent.append(t), tick_fn=fake_tick)
        return sent

    def test_any_error_is_survived_and_announced_once(self):
        ok = dict(signals=[], closed=[])
        sent = self.run_ticks([ValueError("boom"), KeyError("x"), ok, ok])
        self.assertEqual(sent, ["[checker error] still running and retrying every minute",
                                "[recovered] signal checking resumed"])

    def test_feed_down_announced_once_then_recovery(self):
        from trading_agents.core.market_data import DhanApiError
        ok = dict(signals=[], closed=[])
        sent = self.run_ticks([DhanApiError("DH-901"), DhanApiError("DH-901"), ok])
        self.assertEqual(sent, ["[feed down] Dhan API failure", "[recovered] signal checking resumed"])

    def test_new_token_in_env_rebuilds_the_client(self):
        from trading_exec import health, runner
        tokens = iter(["TOKEN-A", "TOKEN-A", "TOKEN-B"])
        built, sent, state, ref = [], [], runner.LoopState(), [None]
        with mock.patch.object(health, "token_from_env_file", lambda: next(tokens)), \
             mock.patch.object(health, "fresh_client", lambda: built.append(1) or object()):
            for _ in range(3):
                runner.tick_safely(state, ref, lambda t, l, s="info": sent.append(t),
                                   tick_fn=lambda c, n: dict(signals=[], closed=[]))
        self.assertEqual(len(built), 2)                                 # first start + the new token
        self.assertEqual(sent, ["[token refreshed] picked up the new Dhan token"])

    def test_token_warning_sent_once_per_condition(self):
        from datetime import time as dtime
        from trading_exec import health, runner
        exp = datetime(2026, 9, 18, 10, 21)
        sent, state = [], runner.LoopState()
        with mock.patch.object(health, "token_from_env_file", lambda: self.jwt(exp)):
            for minute in (0, 1, 2):
                runner.check_token(state, datetime(2026, 9, 18, 9, minute), dtime(23, 59),
                                   lambda t, l, s="info": sent.append(t))
            runner.check_token(state, datetime(2026, 9, 18, 9, 30), dtime(23, 59),
                               lambda t, l, s="info": sent.append(t))
        self.assertEqual(sent, ["[token warning] Dhan token expires before today's close",
                                "[token expiring] Dhan token expires within the hour"])

    def test_first_start_vs_restart(self):
        from trading_exec import health
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(health.mark_started(date(2026, 9, 18), Path(tmp)))
            self.assertFalse(health.mark_started(date(2026, 9, 18), Path(tmp)))
            self.assertTrue(health.mark_started(date(2026, 9, 19), Path(tmp)))


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
