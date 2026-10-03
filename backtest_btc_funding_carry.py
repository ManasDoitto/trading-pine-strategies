"""BTC perpetual funding carry (delta-neutral cash-and-carry), the one candidate from
this research that stands on a different, structural mechanism instead of predicting
price direction: short the perp + hold an equal notional of spot BTC. Price risk cancels
(you're short perp, long spot, same BTC exposure net-zero); what's left is the funding
rate, paid by longs to shorts every 8h whenever funding is positive.

Uses real Binance BTCUSDT perp funding settlements, 2019-09 to 2026-10 (7.1 years,
7,739 settlements, research_data/crypto/btcusdt_funding.json). This is NOT a claim that
Delta Exchange's own funding levels are identical to Binance's (different venues have
different funding formulas / open-interest composition) -- it's evidence that retail BTC
perp markets structurally run a persistent long bias (crowd pays to be long), which is
the economic premise the trade harvests, not a Binance-specific artifact.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "research_data", "crypto")
TAKER_FEE = 0.0005  # one-off entry/exit cost on the perp leg; spot leg assumed similar, ignored for simplicity


def main():
    with open(os.path.join(DATA_DIR, "btcusdt_funding.json")) as f:
        raw = json.load(f)
    fr = pd.DataFrame(raw)
    fr["fundingRate"] = fr["fundingRate"].astype(float)
    fr["dt"] = pd.to_datetime(fr["fundingTime"], unit="ms", utc=True)
    fr = fr.sort_values("dt").reset_index(drop=True)
    years = (fr["dt"].iloc[-1] - fr["dt"].iloc[0]).days / 365.25

    print(f"settlements: {len(fr)}  span: {years:.1f} years")
    print(f"pct of settlements where longs pay shorts (positive funding): {(fr['fundingRate']>0).mean():.1%}")
    print(f"mean funding per 8h settlement: {fr['fundingRate'].mean()*100:.4f}%  median: {fr['fundingRate'].median()*100:.4f}%")
    print(f"worst single settlement (you're short, so a NEGATIVE funding event costs you): {fr['fundingRate'].min()*100:.2f}%")

    # Strategy A: establish the hedge once, hold it the whole period, collect/pay funding every 8h.
    cum_a = fr["fundingRate"].sum()
    cagr_a = (1 + cum_a) ** (1 / years) - 1
    worst_month_a = fr.set_index("dt")["fundingRate"].resample("30D").sum().min()
    print(f"\n[A] hold the hedge continuously: cumulative funding {cum_a:+.1%}, "
          f"compounded CAGR {cagr_a:+.1%}, worst 30d stretch {worst_month_a:+.1%}, "
          f"entry/exit cost (one round trip over {years:.1f}y, negligible): -{2*TAKER_FEE:.2%}")

    # Strategy B: only hold the hedge while funding is currently positive (based on the
    # PRIOR settlement, no lookahead), flat otherwise -- avoids paying during negative stretches
    # but adds a taker-fee round trip on every regime flip.
    fr["prev_positive"] = (fr["fundingRate"].shift(1) > 0)
    held = fr["prev_positive"].fillna(False)
    flips = (held != held.shift(1)).fillna(False).sum()
    gross_b = fr.loc[held, "fundingRate"].sum()
    fee_drag_b = flips * TAKER_FEE  # one taker round trip per regime flip, rough
    cum_b = gross_b - fee_drag_b
    cagr_b = (1 + cum_b) ** (1 / years) - 1
    print(f"\n[B] only hold when last settlement was positive, flat otherwise: "
          f"gross funding {gross_b:+.1%}, ~{flips} regime flips -> fee drag ~{fee_drag_b:.1%}, "
          f"net {cum_b:+.1%}, compounded CAGR {cagr_b:+.1%}")

    print("\nCaveats this backtest does NOT capture (read before sizing this):")
    print(" - basis risk: spot and perp prices aren't identical tick-for-tick; the hedge isn't perfect")
    print(" - margin/liquidation risk on the SHORT PERP leg specifically: a sharp rally needs margin")
    print("   headroom even though the spot leg offsets it in NAV terms")
    print(" - funding can spike sharply negative in a squeeze -- worst 30d stretch shown above")
    print(" - assumes you can actually hold spot BTC as hedge collateral; check whether Delta")
    print("   Exchange offers spot BTC alongside the perp, or whether the spot leg has to sit on")
    print("   a different exchange/wallet (custody + transfer friction, not modeled here)")
    print(" - Delta's own funding levels may differ from Binance's used here")


if __name__ == "__main__":
    main()
