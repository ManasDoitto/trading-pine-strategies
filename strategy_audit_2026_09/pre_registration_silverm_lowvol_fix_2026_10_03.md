# Pre-registration: fixing the weak S1 + S2 periods of the SILVERM strategy (written 2026-10-03, BEFORE the run)

Why S1/S2 are weak (hypotheses, from the 3-sample result): silver's 5m bar range was 74-97 pts in S1/S2 vs 398 in S3, while costs (0.02%/side ~ 90 pts a round trip) and the absolute-point
rules (350-pt brake, point-sized stops) do not scale. In S1/S2 expectancy was 0.003 / 0.029 R, in S3 0.308 R.
Samples = the three equal-time thirds of SILVERM1 (cuts 2024-12-07 and 2025-11-04; same cut dates for SILVER1). DESIGN data = S1+S2 ("LOW"); CHECK = S3. Points / R, net of 0.02%/side.

## Candidates (exactly 13, each alone vs the deployed strategy)
M1a/b/c  skip entries whose stop distance is < 250 / 400 / 600 pts (cost is a large share of a small stop)
M4a/b/c  breakout lookback 5 / 8 / 12 bars instead of 3 (fewer noise breakouts)
M5a/b    breakout must clear the channel by >= 0.25 / 0.5 ATR
M7a/b    stop floor 3.0 / 3.5 ATR instead of 2.5
M9       entries only in the busy hours (IST 9, 10, 11, 18, 19, 20, 21)
M13a/b   daily brake as "first loss ends the day" (limit 1 pt) / 700-pt limit instead of 350 (the 350 brake means two losses in S1/S2 but one in S3)

## Eligibility (ALL must hold)
1. on SILVERM1, LOW expectancy (R) >= deployed + 0.03, and on SILVER1 LOW expectancy >= deployed + 0.02
2. on SILVERM1, PF (points) in S1 and in S2 each >= deployed - 0.02
3. >= 300 SILVERM1 trades in LOW
4. S3 guard on SILVERM1: PF >= deployed - 0.10 and net points >= 85% of deployed
5. luck check for entry filters (M1, M5, M9): SILVERM1 LOW expectancy gain > the 90th percentile of gains from deleting the same share of deployed LOW trades at random (2,000 draws)
Combination: greedy by SILVERM1 LOW gain, at most 3 changes, each addition keeps 1-4 and adds >= 0.01. Then the final S1/S2/S3 table on both contracts and a month-block bootstrap on LOW.
13 trials tuned on S1+S2: a pass is optimistic by construction; S3 and SILVER1 are the only independent evidence. Nothing changes live without the user's explicit OK.
