# BankNifty v0.5 (loosened v0.4): 5m and 3m results (13 Sep 2026)

## What changed from v0.4 (exactly as requested, nothing else)

1. `htfAdxMin` 25 -> 20 (15m ADX trend gate relaxed)
2. Core reclaim gate no longer requires above-average volume -- only rejection wick + VWAP-side + hold above EMA21
3. `rMultiple` 2.5 -> 2.0

Everything else (EMA9/21 regime, pullback tracker, stop construction, session, cooldown) is byte-identical to v0.4.
Script: `A90_bnf_v0.5.pine.txt`. Same cost model as v0.4: 0.02% commission/side + 5-point slippage baked into the
strategy() call. Same tiled non-overlapping-window method as every other audit in this project.

## Objective

Trade count >= 2x v0.4 (74 trades), Profit Factor strictly > 1.15, on 5m first and 3m as a fallback if 5m fails.

## Results

| Timeframe | Windows | Period | Trades | Win% | PF | Net pts | vs v0.4 (74 trades, PF 1.33, +1,403) |
|---|---|---|---|---|---|---|---|
| **5m** | 6 | 2023-09-26 -> 2026-09-13 (35.6mo) | 693 (9.4x) | 35.5% | **0.71** | **-12,330** | Trade count target crushed; PF collapsed |
| **3m** | 6 | 2024-11-29 -> 2026-09-13 (21.5mo) | 394 (7.3x) | 36.0% | **0.68** | **-7,350** | Same story, shorter history |

By window, oldest to newest:

| TF | Windows (net pts) |
|---|---|
| 5m | -2,393, -621, -1,817, -2,511, -1,226, -3,764 |
| 3m | -877, -1,670, +76, -552, -1,859, -2,469 |

**Every single window is negative except one** (3m, 2025-06-13 to 2025-10-03, +76 pts on 23 trades -- not
meaningfully different from zero).

## Reading

- **The trade-count objective was hit, by a lot** -- 9.4x on 5m, 7.3x on 3m, both comfortably past the "at least
  double" bar.
- **The profit-factor objective failed outright, on both timeframes.** PF 0.71 and 0.68 are not "a bit lower than
  1.33" -- they are decisively below breakeven. This is not a close call or a rounding question.
- **This is not "the edge doesn't scale with volume."** It's the opposite: the three filters that were loosened
  were load-bearing. Dropping the volume requirement in particular removes the one condition that screened out
  low-conviction reclaims (the exact midday-chop trades the filter existed to block, per v0.4's own header
  comment). Combined with a weaker trend gate (ADX 20 vs 25) and a tighter target (2.0R vs 2.5R, which needed a
  *higher* win rate to break even, not just more trades), the strategy took several times more trades of
  meaningfully lower quality.
- **v0.4's edge does not "scale with volume" by loosening its own filters.** The filters are most of the edge,
  not a bottleneck sitting on top of one.

## What this does not mean

This doesn't mean higher-frequency BankNifty trading is impossible -- it means these three specific loosenings,
applied together, destroy this specific strategy's edge. A different route to more trades (e.g. a genuinely
different setup type, not a loosened version of this one, the way `v10.3`/`v13` are uncorrelated with `v0.4` per
`best_2yr_analysis.md`'s correlation table) is a different question with a different answer -- not tested here.

## Recommendation

**Do not deploy v0.5. Keep v0.4 as-is.** If more trade frequency is genuinely needed, the better-supported option
already in this project's own data is combining v0.4 with an uncorrelated strategy (v13, r = -0.03) rather than
loosening v0.4's own filters -- that pairing is already documented as +2,317 net vs v0.4 alone's +1,403, without
touching the filters that make v0.4 work.
