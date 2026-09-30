"""BankNifty v0.4 port: the mechanics that decide when an order arms, fills and exits."""
import math
import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from trading_agents.core import signals_v04 as v04

# v0.4's own parameters, pinned here: BANKNIFTY's live config moved to the Supertrend engine on
# 2026-09-28, but the v0.4 engine is still in the code (premarket engine="v04") and still tested.
P = dict(
    engine="v04", name="BankNifty v0.4 EMA pullback + 15m ADX gate (working_strategies/BankNifty/1)",
    ema_fast=9, ema_med=21, ema_slow=200, entry_window=["09:30", "15:00"], skip_open_min=15,
    flat_window=["15:15", "15:30"], flat_exit_at="15:20", atr_min_pts=50.0, atr_buff=0.15,
    stop_floor_atr=0.5, max_stop_atr=2.0, rr=2.5, wick_frac=0.5, vol_mlt=1.0, rsi_len=3,
    rsi_max_long=80, rsi_min_short=20, pb_lookback=10, reclaim_win=8, cool_bars=3, allow_coil=True,
    cluster_mlt=1.0, cluster_buf=0.25, htf_adx_min=25.0,
)


def forced(bars, **cols):
    """A frame with every per-bar condition set explicitly, so a test controls the gate stack.
    bars: list of (time, open, high, low, close). Defaults: long regime, above both EMAs, all gates on."""
    df = pd.DataFrame(bars, columns=["time", "open", "high", "low", "close"])
    df["time"] = pd.to_datetime(df["time"])
    n = len(df)
    defaults = dict(ema9=1000.0, ema21=990.0, ema_lo3=990.0, ema_hi3=1000.0, atr14=20.0, rsi3=50.0,
                    regime_up=True, regime_dn=False, above_both=True, below_both=False, coil=False,
                    big_lower_wick=True, big_upper_wick=False, q_vol=True, q_vwap_l=True, q_vwap_s=False,
                    in_session=True, in_flat=False, atr_ok=True, adx_ok=True)
    for k, v in {**defaults, **cols}.items():
        df[k] = v if isinstance(v, list) else [v] * n
    return df


def t(hhmm, day="2026-09-10"):
    return f"{day} {hhmm}:00"


# bar 0 sets "above both"; bar 1 dips to EMA9 with a wick and reclaims -> arms long:
#   trigger 1010, stop min(995-0.15*20, 1010-0.5*20) = 992, risk 18, target 1010+2.5*18 = 1055
SETUP = [(t("10:00"), 1002, 1006, 1001, 1005), (t("10:05"), 1005, 1010, 995, 1008)]


def events(sim, kind):
    return [e for e in sim["events"] if e["kind"] == kind]


class ArmFillExitTest(unittest.TestCase):
    def test_arms_then_fills_next_bar_and_exits_are_not_live_on_the_fill_bar(self):
        bars = SETUP + [(t("10:10"), 1008, 1012, 980, 1000),        # fills at 1010; its low 980 is below the stop
                        (t("10:15"), 1000, 1002, 990, 995)]         # stop 992 hit here
        sim = v04.simulate(forced(bars, above_both=[True, True, False, False]), P)
        armed = events(sim, "armed")
        self.assertEqual([(e["bar"], e["trig"], round(e["sl"], 2), round(e["tp"], 2)) for e in armed],
                         [(1, 1010.0, 992.0, 1055.0)])
        self.assertEqual([(e["bar"], e["entry"]) for e in events(sim, "filled")], [(2, 1010.0)])
        self.assertEqual([(t_["exit_bar"], t_["result"], t_["exit"]) for t_ in sim["trades"]], [(3, "SL", 992.0)])

    def test_cannot_fill_on_the_arming_bar(self):
        sim = v04.simulate(forced(SETUP, above_both=[True, True]), P)
        self.assertEqual(events(sim, "filled"), [])
        self.assertIsNotNone(sim["live"]["L"])                      # live for the next bar

    def test_gap_through_the_trigger_fills_at_the_open(self):
        bars = SETUP + [(t("10:10"), 1020, 1025, 1015, 1022)]
        sim = v04.simulate(forced(bars, above_both=[True, True, False]), P)
        self.assertEqual(events(sim, "filled")[0]["entry"], 1020.0)

    def test_stop_assumed_first_when_a_bar_touches_both(self):
        bars = SETUP + [(t("10:10"), 1008, 1012, 1005, 1011), (t("10:15"), 1011, 1060, 985, 1030)]
        sim = v04.simulate(forced(bars, above_both=[True, True, False, False]), P)
        self.assertEqual(sim["trades"][0]["result"], "SL")


class OrderLifetimeTest(unittest.TestCase):
    def test_expires_after_the_reclaim_window(self):
        quiet = [(t(f"10:{10 + 5 * k:02d}"), 1004, 1008, 1001, 1005) for k in range(9)]   # bars 2..10, below trigger
        late = [(t("10:55"), 1005, 1030, 1004, 1025)]                                     # bar 11 would fill
        bars = SETUP + quiet + late
        sim = v04.simulate(forced(bars, above_both=[True, True] + [False] * 10), P)
        self.assertEqual([e["bar"] for e in events(sim, "expired")], [10])      # 10 - 1 > reclaim_win (8)
        self.assertEqual(events(sim, "filled"), [])

    def test_regime_flip_cancels_the_order(self):
        bars = SETUP + [(t("10:10"), 1004, 1008, 1001, 1005), (t("10:15"), 1005, 1030, 1004, 1025)]
        sim = v04.simulate(forced(bars, above_both=[True, True, False, False],
                                  regime_up=[True, True, False, False]), P)
        self.assertEqual([e["bar"] for e in events(sim, "expired")], [2])
        self.assertEqual(events(sim, "filled"), [])

    def test_no_fill_once_the_flat_window_starts(self):
        bars = [(t("14:50"), 1002, 1006, 1001, 1005), (t("14:55"), 1005, 1010, 995, 1008),
                (t("15:00"), 1004, 1008, 1001, 1005), (t("15:05"), 1004, 1008, 1001, 1005),
                (t("15:10"), 1004, 1008, 1001, 1005), (t("15:15"), 1004, 1008, 1001, 1005),
                (t("15:20"), 1005, 1030, 1004, 1025)]                           # would fill, but it's flat time
        sim = v04.simulate(forced(bars, above_both=[True, True] + [False] * 5,
                                  in_flat=[False] * 5 + [True, True]), P)
        self.assertEqual(events(sim, "filled"), [])

    def test_force_flat_exits_at_the_next_bar_open(self):
        bars = [(t("14:55"), 1002, 1006, 1001, 1005), (t("15:00"), 1005, 1010, 995, 1008),
                (t("15:05"), 1008, 1012, 1005, 1011),                           # fill 1010
                (t("15:10"), 1011, 1015, 1006, 1013),
                (t("15:15"), 1013, 1016, 1008, 1014),                           # in flat window -> close next open
                (t("15:20"), 1017, 1020, 1015, 1018)]
        sim = v04.simulate(forced(bars, above_both=[True, True, False, False, False, False],
                                  in_flat=[False] * 4 + [True, True]), P)
        tr = sim["trades"][0]
        self.assertEqual((tr["result"], tr["exit"], tr["exit_bar"]), ("EOD", 1017.0, 5))

    def test_cooldown_blocks_rearming_for_three_bars_after_an_exit(self):
        bars = SETUP + [(t("10:10"), 1008, 1012, 1005, 1011),                   # fill
                        (t("10:15"), 1011, 1012, 985, 990)]                     # stop -> exit at bar 3
        bars += [(t(f"10:{20 + 5 * k:02d}"), 1002, 1010, 995, 1008) for k in range(6)]   # bars 4..9 re-set up
        sim = v04.simulate(forced(bars, above_both=[True, True, False, False] + [True] * 6), P)
        rearm = [e["bar"] for e in events(sim, "armed") if e["bar"] > 3]
        self.assertTrue(rearm)
        self.assertGreaterEqual(rearm[0], 7)                                    # bar - 3 > cool_bars (3)


class IndicatorTest(unittest.TestCase):
    def bars(self, days=3):
        rows = []
        for d in range(days):
            start = datetime(2026, 9, 7 + d, 9, 15)
            for k in range(75):
                c = 55000 + 300 * math.sin((d * 75 + k) / 17) + 2 * k
                rows.append(dict(time=start + timedelta(minutes=5 * k), open=c - 5, high=c + 20, low=c - 20,
                                 close=c, volume=1000 + 10 * k))
        return pd.DataFrame(rows)

    def test_15m_adx_is_the_previous_completed_bar(self):
        b = self.bars()
        mapped = v04.htf_adx_prev(b)
        k = (b.set_index("time").resample("15min", label="left", closed="left")
             .agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna(subset=["close"]).reset_index())
        k["adx"] = v04.adx(k)
        idx = b.index[b["time"] == datetime(2026, 9, 9, 11, 20)][0]            # inside the 11:15 15m bar
        expected = float(k.loc[k["time"] == datetime(2026, 9, 9, 11, 0), "adx"].iloc[0])
        self.assertAlmostEqual(mapped.iloc[idx], expected)

    def test_vwap_resets_each_day_and_frame_builds(self):
        b = self.bars()
        df = v04.v04_frame(b, P)
        first_day2 = df.index[df["time"] == datetime(2026, 9, 8, 9, 15)][0]
        r = df.loc[first_day2]
        self.assertAlmostEqual(r["vwap"], (r["high"] + r["low"] + r["close"]) / 3)
        self.assertFalse(df.loc[df["time"] == datetime(2026, 9, 8, 9, 20), "in_session"].iloc[0])   # skip-open
        self.assertTrue(df.loc[df["time"] == datetime(2026, 9, 8, 10, 0), "in_session"].iloc[0])
        self.assertTrue(df.loc[df["time"] == datetime(2026, 9, 8, 15, 15), "in_flat"].iloc[0])
        out = v04.simulate(df, P)
        self.assertEqual(set(out), {"trades", "position", "live", "events"})


class V04StateTest(unittest.TestCase):
    """What the pre-market brief reads: regime, gates, and only warmed-up trades."""

    def bars(self, days=6):
        rows = []
        for d in range(days):
            start = datetime(2026, 9, 7 + d, 9, 15)
            for k in range(75):
                c = 55000 + 300 * math.sin((d * 75 + k) / 17) + 2 * k
                rows.append(dict(time=start + timedelta(minutes=5 * k), open=c - 5, high=c + 20,
                                 low=c - 20, close=c, volume=1000 + 10 * k))
        return pd.DataFrame(rows)

    def test_too_little_history_is_reported_not_guessed(self):
        s = v04.v04_state(self.bars(days=2), P)
        self.assertFalse(s["available"])
        self.assertIn("needs 250", s["note"])

    def test_state_reports_regime_gates_and_what_it_needs(self):
        s = v04.v04_state(self.bars(), P)
        self.assertTrue(s["available"])
        self.assertEqual(s["engine"], "v04")
        self.assertIn(s["alignment"], ("long-aligned", "short-aligned", "coiled", "mixed"))
        self.assertEqual(s["gates"]["atr_min_pts"], P["atr_min_pts"])
        self.assertEqual(s["gates"]["htf_adx_min"], P["htf_adx_min"])
        self.assertIsNone(s["pending_entry"])                  # v0.4 arms a stop, never fills at the open
        self.assertIn("pullback", s["needs"])

    def test_shut_gates_are_named_in_needs(self):
        s = v04.v04_state(self.bars(), dict(P, atr_min_pts=1e9, htf_adx_min=1e9))
        self.assertFalse(s["gates"]["atr_ok"])
        self.assertFalse(s["gates"]["adx_ok"])
        self.assertIn("ATR below the floor", s["needs"])
        self.assertIn("15m ADX below the gate", s["needs"])

    def test_trades_before_the_warmup_are_excluded(self):
        b = self.bars()
        full = v04.simulate(v04.v04_frame(b, P), P)
        warm = v04.simulate(v04.v04_frame(b, P), P, start=v04.WARMUP_BARS)
        early = [t for t in full["trades"] if t["entry_bar"] < v04.WARMUP_BARS]
        self.assertEqual(len(warm["trades"]), len(full["trades"]) - len(early))
        state = v04.v04_state(b, P)
        self.assertEqual(state["sim_window"]["trades"], len(warm["trades"]))


if __name__ == "__main__":
    unittest.main()
