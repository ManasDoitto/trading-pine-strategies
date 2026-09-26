# Option-premium testing: do the futures-points edges survive option buying? (run 2026-09-26)

Every strategy number in this repo is futures points, and the README caveat says so: *"None of these are
options-tested."* The trader buys options. This prices an ATM option at each signal's entry and re-prices it at the
same signal's exit on the same futures path (Black-76, `trading_agents/core/black76.py`), so theta, delta and spread
are applied to the real trade sequence. Code: `option_premium_sim.py`. Raw: `research_data/option_premium_sim.csv`.

## Anchors measured from the live Dhan chain (2026-09-26, MCX SILVER, expiry 2026-10-27, underlying 231,793)
ATM 232000 CE: **IV 29.6%, delta 0.553, premium 9,000 pts.** Median plausible near-ATM CE IV **28.1%**. Strike step 1,000.
The matching PE quote is stale (IV 347%, OI 0), so the call side anchors the estimate.
**Liquidity warning, measured not assumed:** of 12 strikes within 10,000 points of ATM, only 4 carry a real quote,
with open interest of 14, 162, 28 and 1. Everything else prints IV 455%+ on zero OI. The 1%/side spread column below
is optimistic for this book; 2% is the more realistic planning case, and on some days no fill exists at all.

## SILVER - the edge survives, at roughly half strength
Futures baseline: 747 trades, PF 1.503, **+222,240.5 pts**, maxDD 33,692.8, win 30.5%, avg hold 10.9h.

| IV \ spread | 0%/side | **1%/side** | 2%/side |
|---|---|---|---|
| 22% | PF 1.879, +189,624 | PF 1.583, +142,735 | PF 1.350, +95,845 |
| **28% (measured)** | PF 1.736, +163,750 | **PF 1.403, +104,882** | PF 1.155, +46,014 |
| 34% | PF 1.629, +143,642 | PF 1.265, +72,738 | PF 1.006, **+1,835** |

At the measured IV with a 1% spread, option buying keeps **+104,882 of the +222,240 futures points - 47%** - at PF
1.403 vs 1.503. At 2% spread it keeps 21%. At IV 34% with a 2% spread the edge is **gone** (PF 1.006).
So silver's edge is real enough to survive premium, but it is roughly halved, and it dies somewhere between a 1% and
2% round-trip spread. Average premium paid is 3,831 pts per trade - at 30 kg/lot that is about **Rs 115,000 of premium
outlay per trade**, which is a capital constraint, not a modelling detail. SILVERM (5 kg) would be ~Rs 19,000.

## CRUDE - the edge does not survive. It was never big enough.
Futures baseline: 785 trades, PF 1.263, +5,614.5 pts, **+7.2 pts per trade**, avg hold 9.7h.
Average ATM premium at IV 35% is **218.5 pts - 31x the entire per-trade edge.**

| IV \ spread | 0%/side | 1%/side | 2%/side |
|---|---|---|---|
| 30% | PF 1.413, +4,495 | PF 1.116, +1,509 | **PF 0.902, -1,477** |
| 35% | PF 1.345, +3,838 | PF 1.027, **+369** | **PF 0.807, -3,099** |
| 45% | PF 1.240, +2,770 | **PF 0.887, -1,666** | **PF 0.660, -6,101** |

At the plausible 35% IV, a 1% spread leaves +369 points over 30 months - indistinguishable from zero - and anything
worse is a loss. **Crude v4.0 should not be traded as bought options.** Its futures edge of 7.2 points per trade is
smaller than one tick of slippage on the option.

## Why silver survives and crude does not
Both use the same mechanic, so the difference is scale, not quality. Silver's stop is 2.5 ATR and target 3R, so a
winner is thousands of points while theta over a 10.9h hold is tens of points - the option's sign follows the
futures' sign on 100% of winners and 0% of losers, because R dwarfs decay. Crude's per-trade edge is 7.2 points
against a 218.5-point premium; there the fixed costs dominate entirely.
**General rule for this repo: an option-buying strategy needs points-per-trade of the same order as the premium's
decay plus spread over the holding period. Points-per-trade, not PF, is the screening number.**

## Limits of this model (stated, not hidden)
1. **Constant IV.** No vol expansion on breakouts, no crush. For a buyer this cuts both ways and is the largest
   unmodelled risk; a systematic crush after entry would hurt more than the spread.
2. **ATM always available.** The liquidity measurement above says it often is not.
3. Expiry approximated at the 25th monthly (observed: 27 Oct, 27 Nov, 28 Dec, 25 Jan, 26 Feb); minimum 7 DTE.
4. No brokerage/STT/exchange fees - these are additive and make every column above worse.
5. The underlying futures results are themselves in-sample (see `silver_beat_222k_results_2026_09_26.md`): silver
   earns 61.4% of its total in one five-month window. Option economics do not fix that.

## Bottom line
Silver: viable as bought options at ~47% of the futures points, if spreads stay near 1%/side and premium outlay is
affordable. Crude: not viable - the edge is 31x smaller than the premium. This is the first result in this session
that changes what should actually be traded, and it did not come from tuning.


---
# SILVERM (added 2026-09-26) - the contract config.toml actually trades

Measured from the live Dhan chain (2026-09-26, expiry 2026-10-27, underlying 231,793, strike step 1,000):
**CE IV 31.4% median, PE IV ~21.5% - a ~10-point skew.** Calls are expensive, puts are cheap.

**SILVERM option liquidity is far better than SILVER's**, which changes the practical picture more than the pricing does:
**16 of the nearest 24 strikes carry CE open interest** (SILVER: 4 of 12), with real volume - 10,133 contracts at
235000, 1,838 at 236000, 1,616 at 230000. On SILVER the near-ATM book was 14 / 162 / 28 / 1. If these are to be traded
as options at all, SILVERM is the tradeable book.

## Futures baseline (same v4.0 wide-ATR + 350 params, on SILVERM's own bars)
732 trades (24.4/mo), PF 1.278, **+126,575.1 pts**, maxDD 82,673.7, win 31.4%, hold 11.5h, 401 long / 331 short.
Lower than SILVER1's +222,240 on the same rules - already known and recorded in `[[trading-agents-build]]`.

## Option results, with the measured skew
| spread/side | PF | net (pts) | maxDD | avg premium |
|---|---|---|---|---|
| 0% | 1.486 | +108,890.5 | 23,870.6 | 3,808 |
| 0.5% | 1.332 | +80,470.7 | 27,929.9 | 3,808 |
| **1%** | **1.200** | **+52,050.9** | 32,797.3 | 3,808 |
| 2% | 0.984 | **-4,788.7** | 45,482.6 | 3,808 |

At 1%/side it keeps **41% of the futures points** (+52,051 of +126,575) at PF 1.200. At 2% it is a **loser**.
The break-even spread is just under 2%/side - a thinner margin than SILVER's, because SILVERM's futures edge is
smaller to begin with.

## The skew is the most useful finding here
Splitting the 1%-spread result by direction:

| side | trades | net (pts) | avg premium |
|---|---|---|---|
| CE (long signals) | 401 | **+7,218.6** | 4,517 |
| PE (short signals) | 331 | **+44,832.3** | 2,949 |

**86% of the option profit comes from the short side**, on fewer trades. The long side is close to breakeven. This is
not a signal-quality difference - it is the skew: calls cost 4,517 points against puts at 2,949 for the same ATM
distance, so every long trade starts ~1,570 points further behind. Pricing both sides at a flat 31.4% destroys the
result (PF 1.091 at 1% spread, and **-40,951 at 2%**), which is exactly how a flat-IV model would mislead here.

**Actionable: the put side of SILVERM is materially cheaper than the call side. A short-only option-buying variant,
or one that demands a bigger expected move before paying up for calls, is worth testing.** Not yet tested - stated as
the next step, not a result.

## SILVERM vs SILVER as an options vehicle
| | SILVER | SILVERM |
|---|---|---|
| futures net (pts) | +222,240.5 | +126,575.1 |
| option net @1% spread | +104,882.3 (47%) | +52,050.9 (41%) |
| break-even spread | between 1% and 2% | just under 2% |
| avg premium per trade | 3,831 pts = **Rs 114,930** | 3,808 pts = **Rs 19,041** |
| near-ATM strikes with OI | 4 of 12 | **16 of 24** |

SILVER earns twice the points; SILVERM costs a sixth of the capital per trade and has the liquidity to actually fill.
At Rs 19,041 of premium per trade and ~24 trades/month, SILVERM is a realistic book for an account that cannot put
Rs 115,000 of premium at risk per trade. Neither is compelling after a 2% spread.
