"""Test the user's ACTUAL production strategy (v5.0 SHA-ADX Hybrid -- the same code that
trades CrudeOil/Silver/BankNifty live, trading_agents/core/signals_v50.py, imported
directly here, not re-derived) on BTC perpetual.

Why this one and not another generic clone: it already has exactly the filters this
session's whole research pointed to as necessary and that the user explicitly asked for:
  - SHA-flip entry gated by a SHA-stability filter (previous trend run held >= N bars --
    rejects whipsaw/chop flips)
  - EMA9/22/200 trend alignment (only trade with a confirmed multi-EMA trend stack)
  - Higher-timeframe ADX>=30 gate (the literal "don't trade in a choppy market" filter --
    ADX below ~25 is the textbook definition of a non-trending/ranging market)
  - Optional volatility-regime filter (current ATR > SMA(ATR), i.e. an actively moving
    market, not a quiet range)
  - Fixed favorable reward:risk (RR=3, the OPPOSITE skew of the failed VWAP-pullback
    video -- risk 1R to make 3R, so win rate needed to break even is only 25%)
  - ATR-floored, swing-based stop with a max-SL cap (skips trades with oversized risk)

CrudeOil's exact parameters are reused as the BTC starting point (not reinvented) because
Crude is the best-validated, currently-live member of this family (PF 1.575, the top
performer in the archived cross-instrument lab). The only adaptations for BTC: 24/7
session (crypto has no close), and the "15m-off-5m" HTF ADX ratio is preserved
proportionally (4h-off-1h is the same ~3-4x multiple) since we're running off 1h/4h bars
instead of 5m.

Equity curve is simulated with REALISTIC fixed-fractional position sizing (risk a fixed
% of current equity per trade, matching how you'd actually size a $100 Delta account with
leverage) rather than all-in compounding, so the drawdown numbers reported are the ones
that would actually apply to an account run this way.
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from trading_agents.core.signals_v50 import v50_frame, simulate, V50_INSTRUMENT_PARAMS
from backtest_btc_perp_trend import load_klines, DATA_DIR

TAKER_FEE = 0.0005  # Delta Exchange BTC perp taker fee, per side


def load_bars(tf_file: str) -> pd.DataFrame:
    df = load_klines(os.path.join(DATA_DIR, tf_file))
    out = df.rename(columns={"dt": "time"})[["time", "open", "high", "low", "close", "volume"]].copy()
    out["time"] = out["time"].dt.tz_localize(None)
    return out


def btc_params(entry_mode: str, use_vol_filter: bool, adx_min: float, rr: float) -> dict:
    p = dict(V50_INSTRUMENT_PARAMS["CRUDEOIL"])  # start from the best-validated, live member
    p.update(dict(
        session=["00:00", "23:59"],          # BTC trades 24/7
        force_flat_window=["23:59", "23:59"],  # zero-width -> never triggers
        day_loss_limit=0,                     # points-based breaker doesn't translate to BTC's price scale; sized via position risk instead
        entry_mode=entry_mode,
        use_vol_filter=use_vol_filter,
        adx_min=adx_min,
        rr=rr,
    ))
    return p


def run(bars: pd.DataFrame, htf_minutes: int, p: dict) -> pd.DataFrame:
    df = v50_frame(bars, p)
    # adx_15m_prev is hardcoded to resample to a fixed window inside v50_frame (15min);
    # for non-5m base bars we need the HTF gate computed off the right multiple instead.
    from trading_agents.core.signals_v50 import adx_15m_prev
    df["adx15_prev"] = adx_15m_prev(bars.reset_index(drop=True), n=14, minutes=htf_minutes)
    df["adx_ok"] = df["adx15_prev"] >= p.get("adx_min", 20.0)
    trades, open_pos, pending = simulate(df, p, start=250)
    return pd.DataFrame(trades)


def summarize(trades: pd.DataFrame, label: str, risk_fracs=(0.01, 0.02, 0.05)):
    print(f"\n=== {label} ===")
    n = len(trades)
    if n == 0:
        print("no trades"); return
    r_mult = trades["pnl_pts"] / trades["risk_pts"]
    cost_r = (2 * TAKER_FEE) / (trades["risk_pts"] / trades["entry"])  # cost as fraction of risk, per trade
    net_r = r_mult - cost_r
    win_rate = (net_r > 0).mean()
    pf = net_r[net_r > 0].sum() / -net_r[net_r < 0].sum() if (net_r < 0).any() else float("inf")
    avg_hold = (trades["exit_time"] - trades["entry_time"]).dt.total_seconds().mean() / 86400
    print(f"trades: {n}  (long {(trades['side']=='LONG').sum()} / short {(trades['side']=='SHORT').sum()})")
    print(f"avg hold: {avg_hold:.2f} days")
    print(f"win rate (net): {win_rate:.1%}   profit factor (net R): {pf:.2f}   avg net R/trade: {net_r.mean():+.3f}")
    span_days = (trades["exit_time"].iloc[-1] - trades["entry_time"].iloc[0]).days
    years = span_days / 365.25
    for f in risk_fracs:
        eq = (1 + f * net_r).cumprod()
        total_return = eq.iloc[-1] - 1
        cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 and eq.iloc[-1] > 0 else float("nan")
        dd = (eq / eq.cummax() - 1).min()
        print(f"  risk {f:.0%}/trade: total return {total_return:+.1%}  CAGR {cagr:+.1%}  max DD {dd:.1%}")


def main():
    bars_4h = load_bars("btcusdt_perp_4h.json")
    bars_1h = load_bars("btcusdt_perp_1h.json")
    print(f"4h bars: {len(bars_4h)}  1h bars: {len(bars_1h)}")

    configs = [
        ("4h base / 1d HTF ADX, flip, ADX>=30, RR=3, vol_filter=OFF", bars_4h, 1440, "flip", False, 30.0, 3.0),
        ("4h base / 1d HTF ADX, flip, ADX>=20, RR=3, vol_filter=ON", bars_4h, 1440, "flip", True, 20.0, 3.0),
        ("4h base / 1d HTF ADX, breakout, ADX>=25, RR=3, vol_filter=ON", bars_4h, 1440, "breakout", True, 25.0, 3.0),
        ("1h base / 4h HTF ADX, flip, ADX>=30, RR=3, vol_filter=OFF", bars_1h, 240, "flip", False, 30.0, 3.0),
        ("1h base / 4h HTF ADX, flip, ADX>=20, RR=3, vol_filter=ON", bars_1h, 240, "flip", True, 20.0, 3.0),
        ("1h base / 4h HTF ADX, breakout, ADX>=25, RR=3, vol_filter=ON", bars_1h, 240, "breakout", True, 25.0, 3.0),
    ]
    for label, bars, htf_min, mode, volf, adxmin, rr in configs:
        p = btc_params(mode, volf, adxmin, rr)
        trades = run(bars, htf_min, p)
        summarize(trades, label)


if __name__ == "__main__":
    main()
