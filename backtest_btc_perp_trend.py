"""BTC perpetual trend-following strategy research, built from real Binance BTCUSDT
perp history (research_data/crypto/, fetched via scratch/fetch_btc_perp.py) -- not a
chart-pattern port like the SHA/EMA/Donchian-intraday family already tried on BTC in
.kilo/worktrees/elderly-carver/archive/variant_lab_v1/ (32 variants, 0/32 net-profitable
on BTCUSD 5m over 30.7 months, per lab_agg_gold_btc.json). This session's own track
record (2 YouTube-sourced intraday strategies, both failed on NSE) points the same way:
mechanical chart-pattern scalps don't survive costs. So this tests something with a
different, more defensible return driver for CRYPTO SPECIFICALLY:

  1. Classic Donchian trend-following on DAILY bars with an ATR trailing stop (turtle-
     style) -- crypto is one of the few retail-accessible markets with genuine, large,
     multi-day trend persistence (momentum is one of the most replicated anomalies in
     crypto literature), and daily bars avoid the cost-per-trade death-by-a-thousand-cuts
     that killed every intraday variant tested so far.
  2. A funding-rate overlay: perpetuals have a cost/benefit mechanism cash/spot markets
     don't -- funding paid every 8h based on crowd positioning. Tests whether skipping
     trades that fight extreme funding (e.g. don't go long when funding is already very
     rich, i.e. the crowd is already paying up to be long) changes the result.

Funding is modeled using REAL historical Binance funding rate settlements (summed per
day, applied as a return drag/credit while a position is held) -- not an assumed
constant. Costs: 0.05% taker per side (0.10% round trip), realistic for Delta Exchange
BTC perpetual futures at retail tier.
"""
from __future__ import annotations

import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "research_data", "crypto")
TAKER_FEE = 0.0005  # 0.05% per side


def load_klines(path: str) -> pd.DataFrame:
    with open(path) as f:
        raw = json.load(f)
    cols = ["open_time", "open", "high", "low", "close", "volume", "close_time",
            "qvol", "trades", "taker_base", "taker_quote", "ignore"]
    df = pd.DataFrame(raw, columns=cols)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df["dt"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["day"] = df["dt"].dt.date
    return df[["dt", "day", "open", "high", "low", "close", "volume"]]


def load_funding_daily() -> pd.Series:
    with open(os.path.join(DATA_DIR, "btcusdt_funding.json")) as f:
        raw = json.load(f)
    fr = pd.DataFrame(raw)
    fr["fundingRate"] = fr["fundingRate"].astype(float)
    fr["dt"] = pd.to_datetime(fr["fundingTime"], unit="ms", utc=True)
    fr["day"] = fr["dt"].dt.date
    return fr.groupby("day")["fundingRate"].sum()


def atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()


def donchian_trend(df: pd.DataFrame, funding_daily: pd.Series, entry_n: int, atr_mult: float,
                    funding_filter_pct: float | None = None) -> pd.DataFrame:
    """funding_filter_pct, if set (e.g. 0.90): skip a long entry when today's funding sits
    above that percentile of trailing 180d funding (crowd already paying up to be long),
    skip a short entry when funding sits below the (1-pct) percentile (crowd already
    paying up to be short)."""
    d = df.reset_index(drop=True)
    h, l, c = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    n = len(d)
    a = atr(d, 14)
    upper = pd.Series(h).rolling(entry_n).max().shift(1).to_numpy()
    lower = pd.Series(l).rolling(entry_n).min().shift(1).to_numpy()

    fund = d["day"].map(funding_daily).fillna(0.0)
    fund_roll_hi = fund.rolling(180, min_periods=60).quantile(funding_filter_pct) if funding_filter_pct else None
    fund_roll_lo = fund.rolling(180, min_periods=60).quantile(1 - funding_filter_pct) if funding_filter_pct else None
    fund = fund.to_numpy()
    fund_hi = fund_roll_hi.to_numpy() if funding_filter_pct else None
    fund_lo = fund_roll_lo.to_numpy() if funding_filter_pct else None

    trades = []
    pos = 0
    entry_px = 0.0
    hh = ll = 0.0
    entry_i = 0
    daily_rets = np.zeros(n)

    warmup = max(entry_n, 180 if funding_filter_pct else 14) + 1
    for i in range(warmup, n):
        day_ret = 0.0
        if pos == 1:
            hh = max(hh, h[i])
            trail = hh - atr_mult * a[i]
            day_ret += (c[i] - c[i - 1]) / c[i - 1]
            day_ret -= fund[i]  # long pays positive funding
            if l[i] <= trail:
                exit_px = min(trail, c[i])
                gross_r = (exit_px - entry_px) / entry_px
                trades.append((1, d["day"][entry_i], d["day"][i], entry_px, exit_px, gross_r))
                day_ret -= TAKER_FEE
                pos = 0
        elif pos == -1:
            ll = min(ll, l[i])
            trail = ll + atr_mult * a[i]
            day_ret += (c[i - 1] - c[i]) / c[i - 1]
            day_ret += fund[i]  # short receives positive funding
            if h[i] >= trail:
                exit_px = max(trail, c[i])
                gross_r = (entry_px - exit_px) / entry_px
                trades.append((-1, d["day"][entry_i], d["day"][i], entry_px, exit_px, gross_r))
                day_ret -= TAKER_FEE
                pos = 0

        if pos == 0:
            go_long = c[i] > upper[i] and not np.isnan(upper[i])
            go_short = c[i] < lower[i] and not np.isnan(lower[i])
            if funding_filter_pct:
                if go_long and not np.isnan(fund_hi[i]) and fund[i] > fund_hi[i]:
                    go_long = False
                if go_short and not np.isnan(fund_lo[i]) and fund[i] < fund_lo[i]:
                    go_short = False
            if go_long:
                pos, entry_px, hh, entry_i = 1, c[i], h[i], i
                day_ret -= TAKER_FEE
            elif go_short:
                pos, entry_px, ll, entry_i = -1, c[i], l[i], i
                day_ret -= TAKER_FEE

        daily_rets[i] = day_ret

    trades_df = pd.DataFrame(trades, columns=["dir", "entry_day", "exit_day", "entry_px", "exit_px", "gross_r"])
    rets = pd.Series(daily_rets, index=d["day"])
    return trades_df, rets


def summarize(trades: pd.DataFrame, rets: pd.Series, label: str):
    print(f"\n=== {label} ===")
    if len(trades) == 0:
        print("no trades"); return
    win_rate = (trades["gross_r"] > 0).mean()
    pf = trades.loc[trades["gross_r"] > 0, "gross_r"].sum() / -trades.loc[trades["gross_r"] < 0, "gross_r"].sum() \
        if (trades["gross_r"] < 0).any() else float("inf")
    eq = (1 + rets).cumprod()
    total_return = eq.iloc[-1] - 1
    years = len(rets) / 365.25
    cagr = (eq.iloc[-1]) ** (1 / years) - 1 if years > 0 and eq.iloc[-1] > 0 else float("nan")
    dd = (eq / eq.cummax() - 1).min()
    sharpe = rets.mean() / rets.std() * np.sqrt(365) if rets.std() > 0 else 0
    print(f"trades: {len(trades)}  (long {(trades['dir']==1).sum()} / short {(trades['dir']==-1).sum()})")
    print(f"win rate: {win_rate:.1%}  profit factor: {pf:.2f}")
    print(f"total return: {total_return:+.1%}  CAGR: {cagr:+.1%}  max drawdown: {dd:.1%}  Sharpe(d): {sharpe:+.2f}")
    print(f"avg trade gross return: {trades['gross_r'].mean():+.2%}")


def main():
    df = load_klines(os.path.join(DATA_DIR, "btcusdt_perp_1d.json"))
    funding_daily = load_funding_daily()
    print(f"BTC daily bars: {len(df)}  ({df['day'].iloc[0]} .. {df['day'].iloc[-1]})")

    configs = [
        ("Donchian20 ATRx3, no funding filter", 20, 3.0, None),
        ("Donchian55 ATRx3, no funding filter", 55, 3.0, None),
        ("Donchian20 ATRx2.5, no funding filter", 20, 2.5, None),
        ("Donchian20 ATRx3, skip top/bottom-10% funding", 20, 3.0, 0.90),
        ("Donchian55 ATRx3, skip top/bottom-10% funding", 55, 3.0, 0.90),
    ]
    for label, n, mult, ff in configs:
        trades, rets = donchian_trend(df, funding_daily, n, mult, ff)
        summarize(trades, rets, label)


if __name__ == "__main__":
    main()
