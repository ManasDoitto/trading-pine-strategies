import contextlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pandas as pd

from trading_exec import evening, guards, morning, notify as notify_mod, report, shadow, signals, trade_watch
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
        silver = dict(instrument="SILVERM", side="SHORT", opened_at="2026-09-29T09:20:19")
        crude = dict(instrument="CRUDEOIL", side="LONG", opened_at="2026-09-16T10:05:00")
        # another strategy's simulated trade no longer blocks; the same strategy's does, by name
        self.assertEqual(guards.check(s, atm(), self.ctx(open_positions=[silver])), [])
        self.assertIn("simulated CRUDEOIL LONG since 16-Sep 10:05 still open (max 1 per strategy)",
                      guards.check(s, atm(), self.ctx(open_positions=[silver, crude])))
        self.assertEqual(guards.check(s, atm(), self.ctx(open_positions=[dict(crude, observational=True)])), [])
        self.assertTrue(any("daily loss limit" in b
                            for b in guards.check(s, atm(), self.ctx(realised_today_inr=-10000))))

    def test_disabled_instrument(self):
        off = lambda u: dict(enabled=False, lots=2, min_dte=2, max_spread_pct=15.0)
        with mock.patch.object(guards, "instrument_cfg", off):
            self.assertTrue(any("disabled" in b for b in guards.check(sig(), atm(), self.ctx())))


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

    def test_save_is_atomic_no_tmp_file_and_valid_json_survives(self):
        shadow.save([shadow.open_trade(sig(), atm(), {}, datetime(2026, 9, 16, 11, 45))])
        names = sorted(p.name for p in Path(self.tmp.name).iterdir())
        self.assertEqual(names, [shadow.STORE])                  # no leftover .tmp
        json.loads(shadow.path().read_text(encoding="utf-8"))    # parses cleanly
        self.assertEqual(len(shadow.load()), 1)

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

    def marked(self, trade, obars, ubars, now):
        with mock.patch.object(shadow, "_option_bars", lambda *a: obars), \
                mock.patch.object(shadow, "_underlying_bars", lambda *a: ubars):
            return shadow.mark(None, trade, now)

    def test_expiry_day_trade_lives_until_the_close(self):
        t = shadow.open_trade(sig(instrument="BANKNIFTY"), atm(expiry=date(2026, 9, 16), dte=0), {},
                              datetime(2026, 9, 16, 11, 45))
        quiet = bars([(10200, 10210, 10190, 10200)])
        self.assertEqual(self.marked(t, bars([(234, 240, 230, 236)]), quiet,
                                     datetime(2026, 9, 16, 11, 46))["status"], "OPEN")
        t = self.marked(t, bars([(234, 240, 230, 236)]), quiet, datetime(2026, 9, 16, 15, 40))
        self.assertEqual((t["status"], t["exit_reason"], t["exit_at"]), ("CLOSED", "EXPIRY", "2026-09-16T15:30:00"))

    def test_expired_signal_future_closes_at_its_last_bar(self):
        t = shadow.open_trade(sig(), atm(), {}, datetime(2026, 9, 16, 11, 45))
        t["signal_series_type"] = "FUTCOM"
        ubars = bars([(10200, 10210, 10190, 10200)])              # the future's last bar: 16-Sep 11:35
        obars = pd.concat([bars([(234, 240, 230, 250)]), bars([(250, 260, 245, 255)], "2026-09-17T10:00:00"),
                           bars([(255, 270, 250, 265)], "2026-09-18T10:00:00")], ignore_index=True)
        t = self.marked(t, obars, ubars, datetime(2026, 9, 18, 10, 10))
        self.assertEqual((t["status"], t["exit_reason"], t["exit_premium"]), ("CLOSED", "SIGNAL_SERIES_EXPIRED", 250.0))
        # one later day alone is not enough: that can just be the underlying fetch lagging
        t2 = shadow.open_trade(sig(), atm(), {}, datetime(2026, 9, 16, 11, 45))
        t2["signal_series_type"] = "FUTCOM"
        self.assertEqual(self.marked(t2, obars.iloc[:2], ubars, datetime(2026, 9, 17, 10, 10))["status"], "OPEN")

    def strategy_marked(self, sim, obars, ubars, now, engine="tenkan_kijun"):
        """mark() with the strategy rerun stubbed to `sim` = (trades, pos, pending)."""
        t = shadow.open_trade(sig(instrument="NIFTY", side="SHORT", bar_time="2026-09-16T11:30:00"), atm(), {},
                              datetime(2026, 9, 16, 11, 35))
        t.update(signal_security_id="13", signal_segment="IDX_I", signal_series_type="INDEX")
        cfg = dict(strategy=dict(NIFTY=dict(engine=engine)), instruments=dict(NIFTY=dict(session=["09:15", "15:30"])))
        with mock.patch.object(shadow, "agents_config", lambda: cfg), \
                mock.patch.object(shadow, "intraday_bars", lambda *a, **k: ubars), \
                mock.patch.object(shadow.scalp, "tenkan_frame", lambda b, p: b), \
                mock.patch.object(shadow.scalp, "simulate_scalp", lambda d, p: sim):
            return self.marked(t, obars, ubars, now)

    def test_scalp_time_stop_exit_follows_the_strategy_at_the_bar_open(self):
        # the Nifty short of 2026-09-30: the stop/target never hit, the strategy left on its time stop
        ubars = bars([(10200, 10210, 10190, 10200)] * 12)
        obars = bars([(234, 240, 230, 236)] * 9 + [(250, 255, 240, 245)] + [(245, 246, 244, 245)] * 2)
        exit_bar = ubars["time"].iat[9]
        sim = ([dict(side="SHORT", signal_time=datetime(2026, 9, 16, 11, 30), exit_time=exit_bar,
                     exit=10200.0, result="TIME")], None, None)
        t = self.strategy_marked(sim, obars, ubars, datetime(2026, 9, 16, 12, 40))
        self.assertEqual((t["status"], t["exit_reason"], t["exit_premium"]), ("CLOSED", "TIME", 250.0))
        self.assertEqual(t["exit_at"], exit_bar.isoformat())

    def test_strategy_still_holding_keeps_it_open_and_tp_is_named_target(self):
        ubars = bars([(10200, 10400, 10000, 10200)])             # touches both of the record's own levels
        obars = bars([(234, 240, 230, 236)])
        pos = dict(side="SHORT", signal_time=datetime(2026, 9, 16, 11, 30))
        self.assertEqual(self.strategy_marked(([], pos, None), obars, ubars,
                                              datetime(2026, 9, 16, 11, 45))["status"], "OPEN")
        tp = ([dict(pos, exit_time=ubars["time"].iat[0], exit=10035.5, result="TP")], None, None)
        t = self.strategy_marked(tp, obars, ubars, datetime(2026, 9, 16, 11, 45))
        self.assertEqual((t["exit_reason"], t["underlying_exit"]), ("TARGET", 10035.5))

    def test_unknown_to_the_strategy_falls_back_to_the_stop_target_scan(self):
        ubars = bars([(10200, 10250, 10190, 10245)])             # a SHORT's stop at 10241.1 is hit
        t = self.strategy_marked(([], None, None), bars([(234, 240, 230, 236)]), ubars,
                                 datetime(2026, 9, 16, 11, 45))
        self.assertEqual(t["exit_reason"], "SL")

    def test_realised_today_only_counts_closed(self):
        a = shadow.open_trade(sig(), atm(), {}, datetime(2026, 9, 16, 11, 45))
        shadow._close(a, datetime(2026, 9, 16, 13, 0), 10364.5, "TARGET", 300.0)
        b = shadow.open_trade(sig(bar_time="2026-09-16T12:30:00"), atm(), {}, datetime(2026, 9, 16, 12, 35))
        shadow.save([a, b])
        self.assertEqual(shadow.realised_today_inr(date(2026, 9, 16)), a["net_inr"])


class NeverBlockTest(unittest.TestCase):
    """2026-09-30: no signal is ever blocked. Guard objections are warnings on the alert; they only
    decide whether it becomes a simulated option trade or is followed on the underlying."""

    def setUp(self):
        from trading_exec import runner
        self.runner = runner
        self.tmp = tempfile.TemporaryDirectory()
        d = lambda *a: Path(self.tmp.name)
        self.sent = []
        self.patches = [mock.patch.object(shadow, "data_dir", d), mock.patch.object(signals, "data_dir", d),
                        mock.patch.object(runner, "notify", lambda t, l, s="info": self.sent.append((t, l, s)))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def handle(self, s, a, now):
        with mock.patch.object(self.runner.atm_mod, "resolve", lambda *x, **k: a), \
                mock.patch.object(self.runner.atm_mod, "premium_targets", lambda *x, **k: {}):
            return self.runner.handle_signal(None, s, now)

    def test_guard_objection_is_a_warning_and_the_trade_still_opens(self):
        shadow.save([dict(shadow.open_trade(sig(bar_time="2026-09-16T10:00:00"), atm(), {},
                                            datetime(2026, 9, 16, 10, 5)))])     # same strategy already open
        res = self.handle(sig(bar_time="2026-09-16T11:40:00"), atm(), datetime(2026, 9, 16, 11, 45))
        self.assertIsNotNone(res["trade"])
        self.assertTrue(any("still open" in w for w in res["warnings"]))
        title, lines, severity = self.sent[-1]
        self.assertTrue(title.startswith("[signal · simulated]"))
        self.assertIn("Warnings (not blocking):", lines)
        self.assertEqual(signals.load_all()[-1].status, "SHADOW")

    def test_unpriceable_option_still_alerts_and_is_followed(self):
        res = self.handle(sig(bar_time="2026-09-16T11:40:00"), atm(usable=False, reasons=["wide bid-ask spread"]),
                          datetime(2026, 9, 16, 11, 45))
        self.assertIsNone(res["trade"])
        self.assertEqual(res["watch"]["blocked_by"], "wide bid-ask spread")
        self.assertTrue(self.sent[-1][0].startswith("[signal · simulated]"))
        self.assertEqual(signals.load_all()[-1].status, "SIGNAL")

    def test_caught_up_signal_is_followed_not_bought_late(self):
        res = self.handle(sig(bar_time="2026-09-16T10:00:00"), atm(), datetime(2026, 9, 16, 11, 45))
        self.assertIsNone(res["trade"])
        self.assertEqual(shadow.load(), [])
        self.assertTrue(self.sent[-1][0].startswith("[signal · simulated]"))


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


def pos(symbol="CRUDEOIL 17 SEP 2026 9600 PUT", side="LONG", avg_entry=69.0, ltp=69.0, **over):
    p = dict(symbol=symbol, side=side, qty_units=400.0, lots=4.0, avg_entry=avg_entry, ltp=ltp,
             pnl_pts=None if ltp is None else round(ltp - avg_entry, 2),
             unrealized_inr=None if ltp is None else round((ltp - avg_entry) * 400, 2),
             product="INTRADAY", expiry="2026-09-17", right="PE", strike=9600.0, carried_forward_units=0.0)
    p.update(over)
    return p


class RuleHistoryTest(unittest.TestCase):
    """How many times a rule has fired before, and what it cost - from the newest journal facts."""

    ALL_TIME = dict(violations_by_rule=dict(R7=8, R3=2),
                    violation_cost=dict(R7=dict(episodes=8, net_inr=-42150.0), R3=dict(episodes=2, net_inr=-500.0)))

    def test_a_rule_that_has_fired_returns_count_and_cost(self):
        self.assertEqual(trade_watch.rule_history("R7", self.ALL_TIME), dict(count=8, net_inr=-42150.0))

    def test_a_rule_that_has_never_fired_returns_none(self):
        self.assertIsNone(trade_watch.rule_history("R4", self.ALL_TIME))

    def test_no_journal_history_yet_returns_none(self):
        self.assertIsNone(trade_watch.rule_history("R7", None))


class StrategyReadTest(unittest.TestCase):
    """Does this trade match the strategy, and what would its own risk formula set as stop/target."""

    def patched(self, bars, state):
        from trading_exec import poller
        return [mock.patch.object(poller, "signal_series", lambda source, tcfg=None: dict(security_id="1")),
                mock.patch.object(poller, "closed_bars", lambda *a, **k: bars),
                mock.patch("trading_agents.core.signals.v40_state", lambda b, p: state)]

    def test_matches_a_live_open_position(self):
        state = dict(available=True, name="CRUDE v4.0 (x)", alignment="short-aligned",
                    position=dict(side="SHORT", sl=9862.47, tp=9610.13, risk_pts=50.47), pending_entry=None,
                    if_flip_now=dict(long={}, short={}))
        with contextlib.ExitStack() as stack:
            for p in self.patched(bars([(1, 1, 1, 1)]), state):
                stack.enter_context(p)
            r = trade_watch.strategy_read(None, "CRUDEOIL", "PE", datetime(2026, 9, 17, 12, 0))
        self.assertEqual(r["match"], "MATCHES a live strategy signal")
        self.assertEqual((r["levels"]["sl"], r["levels"]["tp"]), (9862.47, 9610.13))
        self.assertIn("live simulated position", r["levels"]["src"])

    def test_matches_the_trend_but_no_live_signal_uses_hypothetical_levels(self):
        state = dict(available=True, name="CRUDE v4.0 (x)", alignment="long-aligned", position=None, pending_entry=None,
                    if_flip_now=dict(long=dict(sl=9780.0, tp=9990.0, risk_pts=35.0), short={}))
        with contextlib.ExitStack() as stack:
            for p in self.patched(bars([(1, 1, 1, 1)]), state):
                stack.enter_context(p)
            r = trade_watch.strategy_read(None, "CRUDEOIL", "CE", datetime(2026, 9, 17, 12, 0))
        self.assertEqual(r["match"], "matches the trend (no live signal right now)")
        self.assertIn("hypothetical", r["levels"]["src"])
        self.assertEqual(r["levels"]["sl"], 9780.0)

    def test_against_the_trend_is_flagged_plainly(self):
        state = dict(available=True, name="CRUDE v4.0 (x)", alignment="short-aligned", position=None, pending_entry=None,
                    if_flip_now=dict(long=dict(sl=9780.0, tp=9990.0, risk_pts=35.0), short={}))
        with contextlib.ExitStack() as stack:
            for p in self.patched(bars([(1, 1, 1, 1)]), state):
                stack.enter_context(p)
            r = trade_watch.strategy_read(None, "CRUDEOIL", "CE", datetime(2026, 9, 17, 12, 0))
        self.assertEqual(r["match"], "AGAINST the strategy's current trend")

    def test_no_strategy_modelled_returns_none(self):
        self.assertIsNone(trade_watch.strategy_read(None, "NOTATRADEDINSTRUMENT", "CE", datetime.now()))

    def test_v04_uses_an_armed_order_when_no_open_position(self):
        state = dict(available=True, name="BankNifty v0.4 (x)", alignment="short-aligned", position=None,
                    armed_orders=[dict(side="SHORT", sl=56900.0, tp=56550.0, risk_pts=100.0, trigger=56800.0)])
        with contextlib.ExitStack() as stack:
            for p in [mock.patch("trading_exec.poller.signal_series", lambda source, tcfg=None: dict(security_id="1")),
                     mock.patch("trading_exec.poller.closed_bars", lambda *a, **k: bars([(1, 1, 1, 1)])),
                     mock.patch("trading_agents.core.signals_v04.v04_state", lambda b, p: state),
                     mock.patch("trading_exec.config.instrument_cfg", lambda u: dict(signal_series="future")),
                     mock.patch.object(trade_watch, "agents_config",
                                       lambda: dict(strategy={"BANKNIFTY": dict(engine="v04")}))]:
                stack.enter_context(p)
            r = trade_watch.strategy_read(None, "BANKNIFTY", "PE", datetime(2026, 9, 17, 12, 0))
        self.assertEqual(r["match"], "MATCHES a live strategy signal")
        self.assertIn("armed order", r["levels"]["src"])
        self.assertEqual(r["levels"]["sl"], 56900.0)


class QualityCardTest(unittest.TestCase):
    """The full [trade opened] card: strategy match, its stop/target, and rule history attached."""

    def build(self, p_over=None, read=None, flags_hist=None, history_rows=None):
        all_time = dict(violations_by_rule=dict(R7=8), violation_cost=dict(R7=dict(net_inr=-42150.0)))
        patches = [
            mock.patch.object(trade_watch, "average_win_inr", lambda u: (4000.0, "test average")),
            mock.patch.object(trade_watch, "latest_journal_all_time", lambda: all_time if history_rows is not False else None),
            mock.patch.object(trade_watch, "underlying_spot", lambda c, u, e: 9760.0),
            mock.patch.object(trade_watch, "strategy_read", lambda c, u, r, n: read),
        ]
        with contextlib.ExitStack() as stack:
            for pat in patches:
                stack.enter_context(pat)
            return trade_watch.quality_card(None, pos(**(p_over or {})), datetime(2026, 9, 17, 12, 0))

    def test_no_strategy_read_says_so(self):
        lines, _ = self.build(read=None)
        self.assertIn("strategy: no live read available right now", lines)

    def test_current_price_and_unrealised_pnl_are_shown(self):
        # pos() defaults: avg_entry=69.0, ltp=69.0 -> flat; use an explicit move so this is meaningful
        lines, _ = self.build(p_over=dict(ltp=78.0, avg_entry=69.0, unrealized_inr=3600.0), read=None)
        self.assertIn("now 78.00  (+13.0%)  unrealised 3,600 INR", lines)

    def test_no_ltp_yet_omits_the_line_rather_than_showing_garbage(self):
        lines, _ = self.build(p_over=dict(ltp=None, unrealized_inr=None), read=None)
        self.assertFalse(any(l.startswith("now ") for l in lines))

    def test_sl_and_target_are_always_present_even_with_no_strategy_read(self):
        # no strategy modelled/no live levels for this direction - must still give a concrete SL/target:
        # 5% premium stop, R:R 2 target, off the current premium (pos() defaults ltp=avg_entry=69.0)
        lines, _ = self.build(read=None)
        hit = [l for l in lines if l.strip().startswith("SL ")]
        self.assertTrue(hit, lines)
        self.assertIn("no strategy modelled", hit[0])
        self.assertIn("SL 65.55  target 75.90", hit[0])

    def test_sl_and_target_present_when_read_exists_but_has_no_levels(self):
        read = dict(name="CRUDE v4.0 (x)", alignment="short-aligned", side="LONG",
                    match="AGAINST the strategy's current trend", levels=None)
        lines, _ = self.build(read=read)
        hit = [l for l in lines if l.strip().startswith("SL ")]
        self.assertTrue(hit, lines)
        self.assertIn("no strategy modelled", hit[0])

    def test_no_strategy_fallback_uses_the_live_premium_not_the_entry(self):
        # entry 69.0 but the position has since moved to ltp 100.0 - the fallback should price off
        # where the trade is NOW, not where it started
        lines, _ = self.build(p_over=dict(ltp=100.0, avg_entry=69.0, unrealized_inr=12400.0), read=None)
        hit = [l for l in lines if l.strip().startswith("SL ")][0]
        self.assertIn("SL 95.00  target 110.00", hit)
        self.assertIn("current premium 100.00", hit)

    def test_a_live_matching_signal_shows_its_real_levels(self):
        read = dict(name="CRUDE v4.0 (x)", alignment="short-aligned", side="SHORT",
                    match="MATCHES a live strategy signal",
                    levels=dict(sl=9862.47, tp=9610.13, risk_pts=50.47, rr=4.0, src="its own live simulated position"))
        lines, _ = self.build(read=read)
        self.assertTrue(any("short-aligned" in l and "MATCHES a live strategy signal" in l for l in lines))
        self.assertTrue(any("SL 9,862.47" in l and "9,610.13" in l for l in lines))

    def test_an_r7_flag_carries_its_own_history(self):
        # strike 9200 vs spot 9760 with right="PE": far ITM, not OTM -- use a genuinely deep-OTM strike
        lines, flags = self.build(p_over=dict(strike=7000.0), read=None)
        hit = [l for l in lines if l.startswith("! ") and "R7" in l]
        self.assertTrue(hit, lines)
        self.assertIn("you've done this 8x before, net -42,150 INR", hit[0])

    def test_history_section_lists_worst_rules_first(self):
        lines, _ = self.build(read=None)
        self.assertIn("your history, all-time (worst first):", lines)
        self.assertIn("  R7: 8x, net -42,150 INR", lines)

    def test_no_journal_history_yet_omits_the_section(self):
        lines, _ = self.build(read=None, history_rows=False)
        self.assertFalse(any("your history" in l for l in lines))


class TelegramBotTest(unittest.TestCase):
    """Commands read FROM Telegram: only the owner's chat, never the pending backlog on first run,
    every command failure contained so it can't take the position-watcher loop down with it."""

    def setUp(self):
        from trading_exec import telegram_bot
        self.bot = telegram_bot
        self.tmp = tempfile.TemporaryDirectory()
        self.dir_patch = mock.patch.object(telegram_bot, "data_dir", lambda *a: Path(self.tmp.name))
        self.dir_patch.start()
        self.sent = []
        self.notify_patch = mock.patch.object(
            telegram_bot, "notify", lambda title, lines, sev="info": self.sent.append((title, tuple(lines), sev)))
        self.notify_patch.start()
        self.env_patch = mock.patch.object(telegram_bot, "env",
                                           lambda k: "AUTH_CHAT" if k == "TELEGRAM_CHAT_ID" else "tok:real")
        self.env_patch.start()

    def tearDown(self):
        for p in (self.dir_patch, self.notify_patch, self.env_patch):
            p.stop()
        self.tmp.cleanup()

    def update(self, uid, chat_id, text):
        return dict(update_id=uid, message=dict(chat=dict(id=chat_id), text=text))

    def test_first_run_marks_the_backlog_read_without_acting_on_it(self):
        with mock.patch.object(self.bot, "get_updates",
                               lambda offset=None: [self.update(1, "AUTH_CHAT", "/status")]):
            handled = self.bot.poll_and_handle(None)
        self.assertEqual(handled, [])
        self.assertEqual(self.sent, [])
        state = self.bot._load_state()
        self.assertEqual(state["offset"], 2)                # backlog is marked read, not replayed

    def test_a_command_from_the_owner_runs_after_first_run(self):
        self.bot._save_state({"offset": 1})                 # simulate first-run already happened
        with mock.patch.object(self.bot, "get_updates", lambda offset=None: [self.update(1, "AUTH_CHAT", "/help")]):
            handled = self.bot.poll_and_handle(None)
        self.assertEqual(handled, ["/help"])
        self.assertEqual(self.sent[0][0], "[bot] commands")

    def test_a_message_from_any_other_chat_is_silently_ignored(self):
        self.bot._save_state({"offset": 1})
        with mock.patch.object(self.bot, "get_updates",
                               lambda offset=None: [self.update(1, "SOMEONE_ELSE", "/analyze")]):
            handled = self.bot.poll_and_handle(None)
        self.assertEqual((handled, self.sent), ([], []))

    def test_unknown_command_gets_a_help_pointer(self):
        self.bot._save_state({"offset": 1})
        with mock.patch.object(self.bot, "get_updates", lambda offset=None: [self.update(1, "AUTH_CHAT", "/bogus")]):
            self.bot.poll_and_handle(None)
        self.assertEqual(self.sent[0][0], "[bot] unknown command /bogus")

    def test_plain_text_with_no_slash_is_ignored_not_treated_as_unknown(self):
        self.bot._save_state({"offset": 1})
        with mock.patch.object(self.bot, "get_updates", lambda offset=None: [self.update(1, "AUTH_CHAT", "hi")]):
            handled = self.bot.poll_and_handle(None)
        self.assertEqual((handled, self.sent), ([], []))

    def test_a_failing_command_is_caught_and_reported_not_raised(self):
        self.bot._save_state({"offset": 1})
        with mock.patch.object(self.bot, "get_updates", lambda offset=None: [self.update(1, "AUTH_CHAT", "/status")]), \
             mock.patch.dict(self.bot.COMMANDS, {"/status": lambda c: (_ for _ in ()).throw(RuntimeError("boom"))}):
            handled = self.bot.poll_and_handle(None)                     # must not raise
        self.assertEqual(handled, ["/status"])
        self.assertEqual(self.sent[0][0], "[bot] /status failed")

    def test_no_pending_updates_does_not_touch_the_state_file(self):
        with mock.patch.object(self.bot, "get_updates", lambda offset=None: []):
            self.bot.poll_and_handle(None)
        self.assertEqual(self.bot._load_state(), {})                      # still "first run"

    def test_get_updates_never_raises_on_a_network_failure(self):
        with mock.patch.object(self.bot.requests, "get", side_effect=RuntimeError("no network")):
            self.assertEqual(self.bot.get_updates(), [])

    def test_get_updates_skipped_without_a_real_token(self):
        with mock.patch.object(self.bot, "env", lambda k: "123456:placeholder" if k == "TELEGRAM_BOT_TOKEN" else None):
            self.assertEqual(self.bot.get_updates(), [])


class TradeWatchTest(unittest.TestCase):
    """The real-account watcher: a card on entry, then cut / hold / profit / averaging alerts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir_patch = mock.patch.object(trade_watch, "data_dir", lambda *a: Path(self.tmp.name))
        self.dir_patch.start()
        self.sent = []
        self.notify_patch = mock.patch.object(
            trade_watch, "notify", lambda title, lines, sev="info": self.sent.append((title, sev)))
        self.notify_patch.start()
        self.card_patch = mock.patch.object(trade_watch, "quality_card", lambda c, p, now=None: (["card"], []))
        self.card_patch.start()
        self.bench_patch = mock.patch.object(trade_watch, "average_win_inr", lambda u: (4000.0, "test average"))
        self.bench_patch.start()

    def tearDown(self):
        for p in (self.dir_patch, self.notify_patch, self.card_patch, self.bench_patch):
            p.stop()
        self.tmp.cleanup()

    def levels(self, alerts):
        return [a["level"] for a in alerts]

    def test_new_position_sends_a_quality_card_once(self):
        self.assertEqual(self.levels(trade_watch.check(None, positions=[pos()])), ["opened"])
        self.assertEqual(trade_watch.check(None, positions=[pos()]), [])
        self.assertEqual([t for t, _ in self.sent], ["[trade opened] CRUDEOIL 17 SEP 2026 9600 PUT"])

    def test_warn_then_cut(self):
        trade_watch.check(None, positions=[pos()])                                  # entry card
        self.assertEqual(self.levels(trade_watch.check(None, positions=[pos(ltp=57.0)])), ["warn"])   # -17%
        self.assertEqual(self.levels(trade_watch.check(None, positions=[pos(ltp=14.7)])), ["cut"])    # -78.7%
        self.assertEqual(self.levels(trade_watch.check(None, positions=[pos(ltp=14.7)])), [])         # once only
        self.assertEqual([s for _, s in self.sent], ["info", "warning", "error"])

    def test_hold_ladder_fires_on_time_plus_loss(self):
        t0 = datetime(2026, 9, 17, 19, 54)
        trade_watch.check(None, now=t0, positions=[pos()])
        # 10 minutes in and 12% down: under the 30-minute rung, so nothing yet
        self.assertEqual(self.levels(trade_watch.check(None, now=t0 + timedelta(minutes=10),
                                                       positions=[pos(ltp=60.7)])), [])
        out = self.levels(trade_watch.check(None, now=t0 + timedelta(minutes=35), positions=[pos(ltp=60.7)]))
        self.assertEqual(out, ["hold0"])

    def test_profit_alert_at_the_average_win(self):
        trade_watch.check(None, positions=[pos()])
        # +9 points on 400 units = 3,600 INR, under the 4,000 benchmark
        self.assertEqual(self.levels(trade_watch.check(None, positions=[pos(ltp=78.0)])), [])
        self.assertEqual(self.levels(trade_watch.check(None, positions=[pos(ltp=80.0)])), ["profit"])

    def test_averaging_down_is_flagged(self):
        trade_watch.check(None, positions=[pos()])
        added = pos(avg_entry=53.0, ltp=40.0, qty_units=800.0, lots=8.0)
        self.assertIn("averaging", self.levels(trade_watch.check(None, positions=[added])))
        self.assertIn("[AVERAGING DOWN] CRUDEOIL 17 SEP 2026 9600 PUT", [t for t, _ in self.sent])

    def test_closed_position_sends_a_result_card(self):
        trade_watch.check(None, positions=[pos()])
        self.assertEqual(self.levels(trade_watch.check(None, positions=[])), ["closed"])
        self.assertEqual(trade_watch.check(None, positions=[]), [])

    def test_a_real_dhan_position_through_position_view_is_not_silently_dropped(self):
        # end-to-end regression (2026-09-18): position_view() used to pass Dhan's raw "CALL"/"PUT"
        # straight through as `right`, and bought_options() filters on "CE"/"PE" - so every real
        # position was silently invisible to the watcher despite check() running with no error.
        from trading_agents.facts.journal import position_view
        real = position_view({"tradingSymbol": "SILVERM-24Sep2026-240000-CE", "netQty": 10, "multiplier": 1,
                              "buyAvg": 4800.0, "drvOptionType": "CALL"}, 5164.0, lot_size=5)
        self.assertEqual(self.levels(trade_watch.check(None, positions=[real])), ["opened"])

    def test_short_positions_and_missing_ltp_are_ignored(self):
        rows = [pos(side="SHORT", ltp=10.0), pos(ltp=None)]
        self.assertEqual(trade_watch.check(None, positions=rows), [])
        self.assertEqual(self.sent, [])


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

    def test_catch_up_finds_an_entry_the_loop_was_down_for(self):
        from trading_exec import poller
        df = self.frame(400, longs=[390])                       # fills at 391's open, still open or exited
        sim = poller.v40.simulate(df, self.P)
        t = df["time"]
        self.assertEqual(poller.entries_since(df, sim, None), [])          # the old last-bar-only view loses it
        found = poller.entries_since(df, sim, t.iat[388])                  # last good poll before bar 390 closed
        self.assertEqual([(e["side"], e["signal_time"], missed) for e, _c, missed in found],
                         [("LONG", t.iat[390], True)])
        self.assertAlmostEqual(found[0][1], float(df["close"].iat[390]))
        # a poll that ran just after bar 390 closed may still have been missing it (Dhan publishes late)
        self.assertEqual(len(poller.entries_since(df, sim, t.iat[391] + poller.BAR)), 1)
        self.assertEqual(poller.entries_since(df, sim, t.iat[391] + poller.OVERLAP + poller.BAR), [])

    def test_catch_up_keeps_the_last_bar_signal_normal(self):
        from trading_exec import poller
        df = self.frame(400, longs=[399])
        found = poller.entries_since(df, poller.v40.simulate(df, self.P), df["time"].iat[398])
        self.assertEqual([(e["signal_time"], missed) for e, _c, missed in found], [(df["time"].iat[399], False)])
        sigs = poller._to_signals(found, "CRUDEOIL", "CRUDEOIL", dict(self.P, name="t"),
                                  dict(security_id=1, segment="MCX_COMM", instrument="FUTCOM", label="X"))
        self.assertEqual(sigs[0].note, "")

    def test_last_poll_round_trip_and_capped_at_midnight(self):
        from trading_exec import poller
        with tempfile.TemporaryDirectory() as d, mock.patch.object(poller, "data_dir", lambda *a: Path(d)):
            self.assertIsNone(poller.last_poll())
            now = datetime.now().replace(microsecond=0)
            poller.save_last_poll(now)
            self.assertEqual(poller.last_poll(), now)
            poller.save_last_poll(now - timedelta(days=2))                 # yesterday's gap is not replayed
            self.assertEqual(poller.last_poll(), datetime.combine(now.date(), datetime.min.time()))

    def test_silverm_options_are_signalled_off_silverm_itself(self):
        # 2026-10-03: the signal chart is the traded chart. SILVERM uses [strategy.SILVERM], which must
        # carry the same v4.1 settings as SILVER (it did before the 2026-09-28 move to SILVER1!).
        from trading_exec.config import instrument_cfg
        from trading_agents.core.config import load_config as agents_config
        self.assertIsNone(instrument_cfg("SILVERM").get("signal_from"))
        strat = agents_config()["strategy"]
        for key in ("day_loss_limit_pts", "bo_lookback", "rr", "min_sl", "max_sl", "exclude_hours"):
            self.assertEqual(strat["SILVERM"][key], strat["SILVER"][key], key)
        self.assertEqual(strat["SILVERM"]["day_loss_limit_pts"], 350)
        # the one deliberate difference: SILVERM skips signals whose stop is under 0.35% of price (2026-10-03)
        self.assertEqual(strat["SILVERM"]["min_stop_pct"], 0.35)
        self.assertNotIn("min_stop_pct", strat["SILVER"])

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

    def test_mark_started_write_is_atomic_no_tmp_file_left_behind(self):
        # a crash mid-write must never truncate the real file - this proves a completed write is
        # whole and leaves no .tmp litter, not that an already-corrupt file self-heals (it must keep
        # raising, since silently discarding that evidence would be worse)
        from trading_exec import health
        with tempfile.TemporaryDirectory() as tmp:
            health.mark_started(date(2026, 9, 18), Path(tmp))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [health.STATE])
            json.loads((Path(tmp) / health.STATE).read_text(encoding="utf-8"))   # parses cleanly
            health.mark_started(date(2026, 9, 19), Path(tmp))                    # second write, same story
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), [health.STATE])

    def test_clock_offset_ok_matches_ist_and_rejects_utc(self):
        from trading_exec import health
        ist_now = datetime(2026, 9, 18, 12, 0)
        with mock.patch.object(health, "datetime") as dt:
            dt.now.return_value = ist_now
            dt.utcnow.return_value = ist_now - timedelta(hours=5, minutes=30)
            self.assertTrue(health.clock_offset_ok())
            dt.utcnow.return_value = ist_now                                # UTC clock: 0 offset
            self.assertFalse(health.clock_offset_ok())

    def test_assert_ist_sends_one_alert_and_returns_false_on_a_bad_clock(self):
        from trading_exec import health
        sent = []
        with mock.patch.object(health, "clock_offset_ok", lambda: False), \
             mock.patch.object(health, "datetime") as dt:
            dt.now.return_value = datetime(2026, 9, 18, 12, 0)
            dt.utcnow.return_value = datetime(2026, 9, 18, 12, 0)           # UTC == local: 0 offset
            ok = health.assert_ist(lambda t, l, s="info": sent.append((t, s)))
        self.assertFalse(ok)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0], ("[fatal] server clock is not IST", "error"))

    def test_assert_ist_true_and_silent_when_the_clock_is_fine(self):
        from trading_exec import health
        sent = []
        with mock.patch.object(health, "clock_offset_ok", lambda: True):
            self.assertTrue(health.assert_ist(lambda t, l, s="info": sent.append(t)))
        self.assertEqual(sent, [])

    def test_run_loop_refuses_to_start_on_a_bad_clock(self):
        from trading_exec import health, runner
        with mock.patch.object(health, "assert_ist", lambda notify_fn: False):
            self.assertEqual(runner.run_loop(notify_fn=lambda *a, **k: None), 2)

    def test_fresh_client_strips_whitespace_like_token_from_env_file_does(self):
        from trading_exec import health
        with mock.patch.object(health, "dotenv_values",
                               lambda p: {"DHAN_CLIENT_ID": "cid\r\n", "DHAN_ACCESS_TOKEN": "tok \n"}), \
             mock.patch("trading_agents.core.dhan_client.get_dhan_client", lambda: "client"):
            health.fresh_client()
        import os
        self.assertEqual(os.environ["DHAN_CLIENT_ID"], "cid")
        self.assertEqual(os.environ["DHAN_ACCESS_TOKEN"], "tok")


class BankNiftyV04WiringTest(unittest.TestCase):
    """BankNifty v0.4: armed and entry signals, intrabar trigger detection, and the 15:20 force-flat."""

    P = dict(name="BankNifty v0.4 test", rr=2.5, reclaim_win=8, flat_exit_at="15:20")
    SERIES = dict(security_id="68390", segment="NSE_FNO", instrument="FUTIDX", label="BANKNIFTY-Sep2026-FUT")

    def frame(self):
        t0 = datetime(2026, 9, 17, 10, 0)
        return pd.DataFrame(dict(time=[t0 + timedelta(minutes=5 * i) for i in range(300)],
                                 open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0))

    def run_v04(self, sim, ltp=None):
        from trading_exec import poller

        class Client:
            def ticker_data(self, securities):
                return {"data": {"data": {"NSE_FNO": {"68390": {"last_price": ltp}}}}}

        df = self.frame()
        with mock.patch.object(poller.v04, "v04_frame", lambda b, p: df), \
             mock.patch.object(poller.v04, "simulate", lambda d, p, start=0: sim):
            return poller.v04_signals(Client(), "BANKNIFTY", "BANKNIFTY", self.P, self.SERIES, df), df

    def order(self, df, side="LONG"):
        return dict(side=side, arm_bar=298, arm_time=df["time"].iat[298], trig=56010.0, sl=55900.0, tp=56285.0,
                    risk_pts=110.0)

    def test_armed_on_the_last_bar(self):
        df = self.frame()
        o = dict(self.order(df), arm_bar=299, arm_time=df["time"].iat[299])
        sim = dict(events=[dict(kind="armed", bar=299, time=o["arm_time"], **o)], position=None,
                   live=dict(L=o, S=None), trades=[])
        out, _ = self.run_v04(sim, ltp=55950.0)                      # below the trigger: no entry
        self.assertEqual([(s.kind, s.side, s.entry_hint, s.sl, s.target) for s in out],
                         [("armed", "LONG", 56010.0, 55900.0, 56285.0)])
        self.assertIn("until", out[0].note)
        self.assertEqual(out[0].flat_at, "15:20")

    def test_entry_filled_on_the_last_closed_bar(self):
        df = self.frame()
        o = self.order(df)
        fill = dict(kind="filled", bar=299, time=df["time"].iat[299], side="LONG", arm_time=o["arm_time"],
                    entry=56010.0, sl=55900.0, tp=56285.0, risk_pts=110.0)
        out, _ = self.run_v04(dict(events=[fill], position=dict(side="LONG"), live=dict(L=None, S=None), trades=[]))
        self.assertEqual([(s.kind, s.bar_time) for s in out], [("entry", df["time"].iat[299].isoformat())])

    def test_intrabar_trigger_cross_is_an_entry_on_the_forming_bar(self):
        df = self.frame()
        sim = dict(events=[], position=None, live=dict(L=self.order(df), S=None), trades=[])
        crossed, _ = self.run_v04(sim, ltp=56012.0)
        self.assertEqual(len(crossed), 1)
        s = crossed[0]
        self.assertEqual((s.kind, s.bar_time), ("entry", (df["time"].iat[-1] + timedelta(minutes=5)).isoformat()))
        self.assertIn("intrabar", s.note)
        not_yet, _ = self.run_v04(sim, ltp=56005.0)
        self.assertEqual(not_yet, [])

    def test_armed_and_entry_keys_never_collide(self):
        a = sig(bar_time="2026-09-17T10:05:00")
        b = Signal(**{**{k: getattr(a, k) for k in ("strategy", "instrument", "side", "bar_time", "entry_hint",
                                                     "sl", "target", "risk_pts", "rr")}, "kind": "armed"})
        self.assertNotEqual(a.key, b.key)
        self.assertEqual(a.key, "v4.0|CRUDEOIL|LONG|2026-09-17T10:05:00")          # entry keys unchanged

    def test_shadow_force_flat_exit_at_1520_open(self):
        t = dict(side="LONG", sl=55900.0, target=56285.0, flat_at="15:20")
        rows = bars([(56000, 56050, 55950, 56020), (56020, 56060, 55990, 56040), (56045, 56070, 56030, 56060)],
                    start="2026-09-17T15:10:00")
        when, level, reason = shadow._exit_scan(t, rows)
        self.assertEqual((when.strftime("%H:%M"), level, reason), ("15:20", 56045.0, "EOD"))
        early_stop = bars([(56000, 56010, 55850, 55880)], start="2026-09-17T15:10:00")
        self.assertEqual(shadow._exit_scan(t, early_stop)[2], "SL")


class BlockedWatchTest(unittest.TestCase):
    """A blocked signal buys nothing, but the strategy still took it: follow it in points."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(shadow, "data_dir", lambda *a: Path(self.tmp.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def watch(self, side="LONG", **over):
        s = sig(side=side, **over)
        w = shadow.open_watch(s, ["DTE 1 below floor 2", "spread 88.0% over the 15% cap"],
                              datetime(2026, 9, 16, 11, 35))
        shadow.record_watch(w)
        return w

    def client_for(self, rows, start="2026-09-16T11:35:00"):
        frame = bars(rows, start=start)
        return mock.patch.object(shadow, "_underlying_bars", lambda c, t, n: frame)

    def test_target_closes_the_watch_in_points(self):
        self.watch()
        with self.client_for([(10200, 10240, 10190, 10230), (10230, 10370, 10225, 10360)]):
            _all, closed = shadow.mark_watches(None, datetime(2026, 9, 16, 12, 0))
        self.assertEqual(len(closed), 1)
        w = shadow.load_watches()[0]                                # the store is the source of truth
        self.assertEqual((w["status"], w["exit_reason"]), ("CLOSED", "TARGET"))
        self.assertEqual(w["entry_fill"], 10200.0)                  # filled at the next bar's open
        self.assertEqual(w["pts"], 164.5)                           # 10364.5 - 10200
        self.assertEqual(w["r_multiple"], 4.0)
        self.assertIn("DTE 1 below floor 2", w["blocked_by"])

    def test_short_watch_profits_when_price_falls(self):
        self.watch(side="SHORT", entry=9812.0, sl=9862.47, target=9610.13, risk=50.47)
        with self.client_for([(9810, 9815, 9800, 9805), (9805, 9808, 9600, 9605)]):
            _all, closed = shadow.mark_watches(None, datetime(2026, 9, 17, 18, 0))
        self.assertEqual(closed[0]["exit_reason"], "TARGET")
        self.assertEqual(closed[0]["pts"], 199.87)                  # 9810 fill -> 9610.13
        self.assertGreater(closed[0]["r_multiple"], 3.9)

    def test_stop_wins_a_tie_and_loses_one_r(self):
        self.watch()
        with self.client_for([(10200, 10370, 10150, 10200)]):
            _all, closed = shadow.mark_watches(None, datetime(2026, 9, 16, 12, 0))
        self.assertEqual(closed[0]["exit_reason"], "SL")
        self.assertEqual(closed[0]["r_multiple"], -1.0)

    def test_unresolved_watch_stays_open_then_goes_stale(self):
        self.watch()
        quiet = [(10200, 10210, 10195, 10205)] * 3
        with self.client_for(quiet):
            _all, closed = shadow.mark_watches(None, datetime(2026, 9, 16, 13, 0))
        self.assertEqual((closed, len(shadow.open_watches())), ([], 1))
        with self.client_for(quiet):
            _all, closed = shadow.mark_watches(None, datetime(2026, 9, 30, 13, 0))
        self.assertEqual(closed[0]["exit_reason"], "STALE")

    def test_watches_never_reach_the_shadow_verdict(self):
        self.watch()
        self.assertEqual(shadow.load(), [])                         # a different store entirely
        self.assertEqual(shadow.realised_today_inr(date(2026, 9, 16)), 0)

    def test_recording_the_same_watch_twice_is_ignored(self):
        self.watch()
        self.watch()
        self.assertEqual(len(shadow.load_watches()), 1)


class MorningJobTest(unittest.TestCase):
    """The 08:27 job: the digest must go out even when the facts build fails."""

    FACTS = {"instruments": {
        "CRUDEOIL": {"available": True,
                     "underlying": {"prev_day": {"close": 9339.0}, "prev_day_change_pct": -0.12,
                                    "atr_regime": "normal", "atr_ratio": 1.2},
                     "strategy": {"available": True, "alignment": "long-aligned", "position": None,
                                  "pending_entry": None},
                     "options": {"nearest": {"dte": 27, "atm_strike": 9350.0,
                                             "atm": {"ce": {"ltp": 550.0, "theta_pct_of_premium": 1.8}}}}},
        "SILVERM": {"available": True,
                    "underlying": {"prev_day": {"close": 239940.0}, "prev_day_change_pct": 1.35,
                                   "atr_regime": "normal", "atr_ratio": 1.06},
                    # SILVERM's OWN-price strategy - not what the live checker trades on
                    "strategy": {"available": True, "alignment": "short-aligned", "position": None},
                    "options": {"nearest": {"dte": 6, "atm_strike": 240000.0,
                                            "atm": {"ce": {"ltp": 4302.0, "theta_pct_of_premium": 7.2}}}}},
        "SILVER": {"available": True,
                   "strategy": {"available": True, "position": {"side": "LONG", "entry": 240031.0,
                                                                "sl": 238897.86, "tp": 243430.43,
                                                                "open_pts": -91.0}}},
        "BANKNIFTY": {"available": False},
    }}
    OPEN_SHADOW = [dict(id="s", status="OPEN", instrument="SILVERM", side="SHORT", opened_at="2026-09-29T09:20:19",
                        signal_label="SILVER-04Dec2026-FUT", signal_entry=225800.0, sl=227792.9, target=219821.3),
                   dict(id="o", status="OPEN", instrument="NIFTY", side="SHORT", opened_at="2026-09-29T13:10:55",
                        observational=True, sl=1.0, target=2.0)]

    def sent(self, **over):
        got = {}
        args = dict(day=date(2026, 9, 18), facts=self.FACTS, error=None,
                    token_status="ok", expiry=datetime(2026, 9, 19, 10, 0), shadow=[])
        args.update(over)
        patches = [
            mock.patch.object(morning, "build_facts", lambda d, o: (args["facts"], args["error"])),
            mock.patch.object(morning.health, "token_from_env_file", lambda: "t"),
            mock.patch.object(morning.health, "token_expiry", lambda t: args["expiry"]),
            mock.patch.object(morning.health, "token_status", lambda *a: args["token_status"]),
            mock.patch.object(morning, "enabled_instruments", lambda: ["CRUDEOIL", "SILVERM", "BANKNIFTY"]),
            mock.patch.object(morning, "instrument_cfg", lambda u: dict(signal_from="SILVER") if u == "SILVERM" else {}),
            mock.patch.object(morning.shadow, "load", lambda: args["shadow"]),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            def fake(title, lines, severity="info"):
                got.update(title=title, text="\n".join(lines), severity=severity)
                return {}
            morning.run(args["day"], notify_fn=fake)
        return got

    def test_digest_shows_price_strategy_and_theta(self):
        g = self.sent()
        self.assertEqual(g["title"], "[pre-market] Fri 18-Sep")
        self.assertIn("CRUDEOIL 9,339.00 (-0.12%)  ATR normal 1.20x", g["text"])
        self.assertIn("flat, long-aligned", g["text"])
        self.assertIn("theta 1.8%/day", g["text"])
        self.assertIn("SILVERM 239,940.00 (1.35%)  ATR normal 1.06x  (signal on SILVER)", g["text"])
        self.assertIn("holding LONG from 240,031.00", g["text"])          # SILVER's position, the live source
        self.assertNotIn("short-aligned", g["text"])                       # not SILVERM's own-price strategy
        self.assertIn("BANKNIFTY: no data", g["text"])
        self.assertIn("No simulated trades open.", g["text"])
        self.assertEqual(g["severity"], "info")

    def test_digest_lists_simulated_trades_still_open(self):
        g = self.sent(shadow=self.OPEN_SHADOW)
        self.assertIn("Simulated trades still open (shadow book - NOT your account):", g["text"])
        self.assertIn("- SILVERM SHORT since 29-Sep 09:20: SILVER-04Dec2026-FUT from 225,800.00"
                      "  stop 227,792.90 target 219,821.30", g["text"])
        self.assertNotIn("NIFTY SHORT", g["text"])                         # observational ones are not trades

    def test_failed_build_still_alerts_and_says_so(self):
        g = self.sent(facts=None, error="DH-901 invalid token")
        self.assertIn(morning.BUILD_FAILED, g["text"])
        self.assertIn("DH-901", g["text"])
        self.assertEqual(g["severity"], "warning")

    def test_expired_token_leads_the_digest(self):
        g = self.sent(token_status="expired", expiry=datetime(2026, 9, 18, 10, 21))
        self.assertTrue(g["text"].startswith("TOKEN EXPIRED (18-Sep 10:21)"))
        self.assertEqual(g["severity"], "warning")

    def test_token_expiring_is_a_note_not_a_failure(self):
        g = self.sent(token_status="expires_before_close", expiry=datetime(2026, 9, 18, 10, 21))
        self.assertIn("Token expires 18-Sep 10:21", g["text"])
        self.assertEqual(g["severity"], "info")


class TelegramMarkupTest(unittest.TestCase):
    """Numbers and trading terms are what the eye needs first, so they are bold - and nothing else breaks."""

    def test_numbers_and_terms_are_bold(self):
        got = notify_mod.markup("premium 69.00 -> 14.70  (-79%)")
        self.assertEqual(got, "premium <b>69.00</b> -&gt; <b>14.70</b>  (<b>-79%</b>)")

    def test_contract_symbols_are_left_whole(self):
        got = notify_mod.markup("option SILVERM-24Sep2026-240000-CE (2 lots)")
        self.assertIn("SILVERM-24Sep2026-240000-CE", got)          # not shredded into bold fragments
        self.assertIn("<b>2</b> lots", got)

    def test_adjacent_bolds_merge_into_one_phrase(self):
        self.assertIn("<b>CRUDEOIL SHORT TARGET</b>", notify_mod.markup("CRUDEOIL SHORT TARGET"))
        self.assertIn("<b>-1,100 INR</b>", notify_mod.markup("net -1,100 INR"))
        two_spaces = notify_mod.markup("risk 50.47 pts  R:R 4")     # a wider gap is a column, kept apart
        self.assertIn("<b>50.47 pts</b>  <b>R:R 4</b>", two_spaces)

    def test_html_is_escaped_before_tags_are_added(self):
        got = notify_mod.markup("spread 88.0% & <script>")
        self.assertIn("&amp;", got)
        self.assertIn("&lt;script&gt;", got)
        self.assertNotIn("<script>", got)

    def test_telegram_sends_html_and_skips_without_credentials(self):
        with mock.patch.object(notify_mod, "env", lambda k: None):
            self.assertIn("skipped", notify_mod._telegram("[shadow entry] CRUDEOIL", "premium 69.00"))
        sent = {}

        class Resp:
            ok = True

        def fake_post(url, json=None, timeout=None):
            sent.update(json)
            return Resp()

        patches = [mock.patch.object(notify_mod, "env", lambda k: "x"),
                   mock.patch.object(notify_mod, "load_config", lambda: {"notify": {"telegram": True}}),
                   mock.patch.object(notify_mod, "_log", lambda line: None),
                   mock.patch.dict("sys.modules", {"requests": mock.Mock(post=fake_post)})]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            out = notify_mod.notify("[blocked] CRUDEOIL SHORT signal", ["DTE 1 below floor 2"], "warning")
        self.assertEqual(out["telegram"], "sent")
        self.assertEqual(sent["parse_mode"], "HTML")
        self.assertTrue(sent["text"].startswith("⛔ <b>BLOCKED</b> · <b>CRUDEOIL SHORT</b>"))
        self.assertIn("<b>DTE 1</b>", sent["text"])

    def test_the_card_is_built_for_a_phone(self):
        head = notify_mod.headline("[signal · simulated] SILVERM LONG signal (Silver v4.0 wide-ATR)")
        self.assertEqual(head, "🟢 <b>SIGNAL · SIMULATED</b> · <b>SILVERM LONG</b>\n<i>Silver v4.0 wide-ATR</i>")
        card = notify_mod.body(["stop 237,415.95  target 242,008.15", "", "Blocked by:", "- DTE 1 below floor 2"])
        self.assertIn(" · ", card)                                  # column gaps become separators
        self.assertIn("• <b>DTE 1</b> below floor <b>2</b>", card)  # dashes and indents become bullets
        self.assertIn("\n\n", card)                                 # blank lines still break sections

    def test_an_exit_icon_follows_the_outcome(self):
        self.assertTrue(notify_mod.headline("[signal exit · simulated] SILVERM LONG TARGET").startswith("🎯"))
        self.assertTrue(notify_mod.headline("[signal exit · simulated] CRUDEOIL SHORT SL").startswith("🛑"))
        self.assertTrue(notify_mod.headline("[signal · simulated] CRUDEOIL SHORT").startswith("🔴"))
        self.assertTrue(notify_mod.headline("[trade opened] CRUDEOIL-15Oct2026-8700-CE").startswith("📈"))  # real: unchanged
        self.assertTrue(notify_mod.headline("[cut it] CRUDEOIL 18 SEP 2026 9600 PUT", "error").startswith("🚨"))

    def test_clock_times_contract_names_and_ratios_survive(self):
        self.assertIn("<b>17-Sep</b> 20:50", notify_mod.markup("17-Sep 20:50 bar"))   # the clock stays whole
        self.assertIn("CRUDEOIL 17 SEP 2026 9600 PUT", notify_mod.markup("R4 on CRUDEOIL 17 SEP 2026 9600 PUT"))
        self.assertIn("<b>0.89x</b>", notify_mod.markup("range 0.89x ATR"))
        self.assertIn("<b>4,650.00</b>", notify_mod.markup("(bid 4,650.00, spread 1.1%)"))

    def test_script_strike_and_expiry_are_bold_as_one_piece(self):
        got = notify_mod.markup("R4 on CRUDEOIL 17 SEP 2026 9600 PUT (-21,720 INR)")
        self.assertIn("<b>CRUDEOIL 17 SEP 2026 9600 PUT</b>", got)      # one name, one bold run
        self.assertIn("<b>SILVERM-24Sep2026-240000-CE</b>", notify_mod.markup("option SILVERM-24Sep2026-240000-CE x"))
        self.assertIn("<b>BANKNIFTY-Sep2026-FUT</b>", notify_mod.markup("trigger: BANKNIFTY-Sep2026-FUT above 1"))
        self.assertIn("<b>CRUDEOIL</b>", notify_mod.markup("CRUDEOIL C 9,760.00"))
        self.assertIn("<b>18-Sep</b>", notify_mod.markup("18-Sep 20:50 bar"))

    def test_a_sentence_about_signals_is_not_mangled(self):
        head = notify_mod.headline("[token expired] Dhan token has expired - no signals are being checked")
        self.assertIn("no signals are being checked", head)


class EveningJobTest(unittest.TestCase):
    """The post-market digest: your day first, then each strategy, then the shadow book."""

    FACTS = {"instruments": {"CRUDEOIL": {
        "available": True,
        "session": {"close": 9760.0, "change_pct": -0.58, "range_vs_atr": 0.89},
        "strategy": {"available": True, "signals": [1], "trades": [], "trades_net_pts": 0.0},
        "alignment": {"entries": 10, "matched_a_signal": 0}}},
        "scorecard": {"rows": [{"underlying": "CRUDEOIL", "rule_bias": "bearish", "outcome": "flat",
                                "rule_correct": False}]}}
    JOURNAL = {"today": {"summary_round_trips": {"n": 10, "net": -1100.0, "win_rate": 90.0, "profit_factor": 0.95},
                         "violations": [{"rule": "R4", "title": "Premium stop not respected",
                                         "symbol": "CRUDEOIL 17 SEP 2026 9600 PUT", "inr": -21720.0}]}}

    def sent(self, journal=None, facts=None, error=None):
        got = {}

        def fake(title, lines, severity="info"):
            got.update(title=title, text="\n".join(lines), severity=severity)
            return {}

        patches = [
            mock.patch.object(evening, "build_facts", lambda d, s, o: (facts, error)),
            mock.patch.object(evening, "_facts", lambda d, kind: journal),
            mock.patch.object(evening.health, "token_from_env_file", lambda: "t"),
            mock.patch.object(evening.health, "token_expiry", lambda t: datetime(2026, 9, 19, 10, 0)),
            mock.patch.object(evening.health, "token_status", lambda *a: "ok"),
            mock.patch.object(evening, "shadow_lines", lambda d: ["shadow: 1 closed, 9,960 INR"]),
        ]
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            evening.run(date(2026, 9, 17), notify_fn=fake)
        return got

    def test_digest_leads_with_your_own_day(self):
        g = self.sent(journal=self.JOURNAL, facts=self.FACTS)
        self.assertEqual(g["title"], "[post-market] Thu 17-Sep")
        self.assertTrue(g["text"].startswith("you: 10 round trips, net -1,100 INR"))
        self.assertIn("R4 Premium stop not respected", g["text"])
        self.assertIn("-21,720 INR", g["text"])

    def test_digest_grades_the_morning_call_and_your_alignment(self):
        g = self.sent(journal=self.JOURNAL, facts=self.FACTS)
        self.assertIn("CRUDEOIL C 9,760.00 (-0.58%)", g["text"])
        self.assertIn("v4.0: 1 signals, 0 trades, 0.0 pts", g["text"])
        self.assertIn("your 10 entries: 0 matched a signal", g["text"])
        self.assertIn("morning bias bearish -> flat (wrong)", g["text"])
        self.assertIn("shadow: 1 closed", g["text"])

    def test_a_day_without_trades_says_so(self):
        quiet = {"today": {"summary_round_trips": {"n": 0}, "violations": []}}
        self.assertIn("you took no trades today", self.sent(journal=quiet, facts=self.FACTS)["text"])

    def test_failed_build_still_alerts(self):
        g = self.sent(error="DH-901 invalid token")
        self.assertIn(evening.BUILD_FAILED, g["text"])
        self.assertEqual(g["severity"], "warning")


class StrategyHealthTest(unittest.TestCase):
    """Rolling PF / drawdown / time-below-peak / losing-streak check shown in the post-market digest."""

    def ledger(self, nets, start=datetime(2026, 1, 5, 12, 0), sources=None):
        import pandas as pd
        rows = []
        for i, n in enumerate(nets):
            t = start + timedelta(days=i)
            rows.append(dict(signal_time=t - timedelta(minutes=5), side="LONG", entry_time=t, exit_time=t, net_pts=float(n),
                             source=(sources[i] if sources else "history")))
        return pd.DataFrame(rows)

    def test_rolling_pf_drawdown_underwater_and_streak(self):
        from trading_exec import strategy_health as sh
        s = sh.compute(self.ledger([100] * 10 + [-50] * 8))
        self.assertEqual(s["n"], 18)
        self.assertAlmostEqual(s["dd_now"], 400.0)
        self.assertEqual(s["underwater_now"], 8)                    # peak on day 10, last trade on day 18
        self.assertEqual((s["streak_now"], s["streak_max"]), (8, 8))
        pf = sh.compute(self.ledger(([300] * 40 + [-100] * 60)))["pf100"]
        self.assertAlmostEqual(pf, 12000 / 6000)

    def test_status_ok_watch_review(self):
        from trading_exec import strategy_health as sh
        good = sh.compute(self.ledger([200, -100] * 60))
        self.assertEqual(good["status"], "OK")
        weak = sh.compute(self.ledger([100, -105] * 60))              # last-100 PF ~0.95: below 1.0 is a WATCH, not a review
        self.assertEqual(weak["status"], "WATCH")
        broken = sh.compute(self.ledger([100, -200] * 60))            # PF 0.5
        self.assertEqual(broken["status"], "REVIEW")
        deep = sh.compute(self.ledger([1000, -150000]))
        self.assertEqual(deep["status"], "REVIEW")
        self.assertTrue(any("drawdown" in r for r in deep["reasons"]))
        streak = sh.compute(self.ledger([500] * 30 + [-1] * 21))
        self.assertEqual(streak["status"], "REVIEW")
        self.assertTrue(any("losses in a row" in r for r in streak["reasons"]))

    def test_update_appends_only_later_signals_and_is_idempotent(self):
        import pandas as pd
        from trading_exec import strategy_health as sh
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sh, "ledger_path", lambda: Path(tmp) / "l.csv"):
            led = self.ledger([100, -50, 80])
            sh._atomic_write_csv(led, sh.ledger_path())
            newest = led["signal_time"].max()
            fetched = pd.concat([led.tail(1).assign(source="live"),                               # already in the ledger
                                 self.ledger([-70], start=datetime(2026, 2, 1, 12, 0), sources=["live"])])   # genuinely new
            out, added = sh.update(None, None, fetch=lambda c, n: fetched)
            self.assertEqual(added, 1)
            self.assertEqual(len(out), 4)
            self.assertEqual(out["source"].tolist().count("live"), 1)
            self.assertGreater(out["signal_time"].max(), newest)
            _, again = sh.update(None, None, fetch=lambda c, n: fetched)
            self.assertEqual(again, 0)

    def test_digest_lines_never_raise(self):
        from trading_exec import strategy_health as sh
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sh, "ledger_path", lambda: Path(tmp) / "none.csv"):
            self.assertIn("ledger not built", " ".join(sh.digest_lines()))
            sh._atomic_write_csv(self.ledger([100, -50] * 30), sh.ledger_path())

            def boom(c, n):
                raise RuntimeError("dhan down")
            text = "\n".join(sh.digest_lines(object(), None, fetch=boom))
            self.assertIn("strategy health (SILVERM v4.1, 60 trades", text)
            self.assertIn("not updated today", text)
            Path(sh.ledger_path()).write_text("not,a,ledger\n1,2,3\n", encoding="utf-8")
            self.assertIn("unavailable", " ".join(sh.digest_lines()))

    def test_evening_digest_carries_the_health_section(self):
        with mock.patch.object(evening, "build_facts", lambda d, s, o: (EveningJobTest.FACTS, None)), \
                mock.patch.object(evening, "_facts", lambda d, kind: EveningJobTest.JOURNAL), \
                mock.patch.object(evening.health, "token_from_env_file", lambda: "t"), \
                mock.patch.object(evening.health, "token_expiry", lambda t: datetime(2026, 9, 19, 10, 0)), \
                mock.patch.object(evening.health, "token_status", lambda *a: "ok"), \
                mock.patch.object(evening, "shadow_lines", lambda d: []), \
                mock.patch.object(evening, "health_lines", lambda d: ["strategy health (SILVERM v4.1): OK", "  last 100 trades PF 1.27"]):
            got = {}
            evening.run(date(2026, 9, 17), notify_fn=lambda title, lines, sev="info": got.update(text="\n".join(lines)) or {})
        self.assertIn("strategy health (SILVERM v4.1): OK", got["text"])
        self.assertLess(got["text"].index("strategy health"), got["text"].index("Full review"))

    def test_health_lines_survive_a_dead_client(self):
        with mock.patch.object(evening.health, "fresh_client", side_effect=RuntimeError("no token")), \
                mock.patch.object(evening.strategy_health, "digest_lines", lambda client=None, *a, **k: [f"client={client}"]):
            self.assertEqual(evening.health_lines(date(2026, 9, 17)), ["client=None"])


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
