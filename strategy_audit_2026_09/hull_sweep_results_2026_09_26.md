# Results: Hull Suite Strategy length sweep on CRUDEOIL 5m (run 2026-09-26)

Pre-registration: `pre_registration_hull_sweep_2026_09_26.md`. Code: `hull_sweep.py`.
Raw (gitignored): `research_data/hull_sweep_results.csv`. 252 combos, points per 1 unit, net of 0.02%/side.
Formula verified against the live chart before reading any result: my Hma(21) = 9,367.9 / 9,768.4 and
Hma(55) = 9,544.9 / 9,507.9 on the last Daily bars vs TradingView's 9,368 / 9,768 and 9,545 / 9,508.

## Verdict: 0 of 252 pass. The pre-registered pick is essentially breakeven.

**Pre-registered pick (highest TRAIN PF, >= 100 TRAIN trades): Thma 400, short-only, hold overnight.**
PF 1.059, net +1,246.3 pts, 457 trades, max DD 2,061.7 | TRAIN 1.061 / VALID 1.000 / HOLDOUT 1.080.
The best in-sample Hull config is a 1.06 PF short-only swing system. It fails criteria 1, 3, 4 and 5.

**The deployed default (Hma 55, long) on 5m loses:** PF 0.932, −3,596.7 pts, DD 5,584.0 (hold);
PF 0.913, −4,327.0 pts, DD 6,102.0 (intraday). Whatever it did on Daily does not survive to 5m.

## What the sweep actually shows
1. **Length is the only lever that matters, and it points away from 5m.** Median PF by length rises almost
   monotonically: 9 -> 0.754, 21 -> 0.850, 55 -> 0.912, 89 -> 1.040, 144 -> 1.122, 400 -> 1.102. Short Hulls
   are eaten by noise plus the ~3.5 pts round-trip cost. The configs that make money hold 17-27 hours on
   average - they are multi-day swing systems that happen to be sampled on a 5m chart.
2. **The profitable region is a regime bet, not an edge.** Across the whole long-length plateau
   (89-400, every mode, long and all), TRAIN PF sits at 0.83-0.97 with only Thma 400 marginally above 1.
   Every full-sample leader loses Jan 2024 - Sep 2025 and earns it all back Sep 2025 - Sep 2026 (the crude
   rally/volatility period). Same concentration problem as v4.0, but worse in train.
3. **For day trading specifically: 0 of 126 intraday (flat by 23:25) combos are profitable in TRAIN.**
   Best intraday by the rule: Thma 400 long, PF 1.115, +2,838.6 pts, but TRAIN 0.995.
4. **Thma > Ehma > Hma** on 5m, consistent with the earlier run: the more the variant damps Hull's
   extrapolation overshoot, the less noise it trades. The deployed script defaults to the worst of the three.

## Reported for information only (chosen AFTER seeing results - not a selection)
Thma 400 long-only hold: PF 1.215, +4,349.3 pts, DD 1,883.6, 458 trades, TRAIN 1.012 / VALID 1.838 /
HOLDOUT 1.224. On full-sample numbers it beats v4.0 (PF 1.145, +3,504.9, DD 2,280.0). It is still not a
candidate: TRAIN is breakeven, best month = 72.3% of net, HOLDOUT PF 1.224 < v4.0's 1.312, it is long-only
through a period when crude rallied, and it is a 27-hour-hold overnight swing strategy, not a day trade.

## Bottom line
Hull on CRUDEOIL 5m has no day-trading edge at any length or variant tested. Running gate total: 0 of 460.
