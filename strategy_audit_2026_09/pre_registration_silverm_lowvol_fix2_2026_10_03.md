# Pre-registration, round 2: minimum stop distance as a share of price (written 2026-10-03, BEFORE the run)

Follow-up to pre_registration_silverm_lowvol_fix_2026_10_03.md (round 1: 13 candidates, 0 eligible). Round-1 near-miss: "skip entries whose stop is < 600 pts" raised S1+S2 expectancy by
+0.284 R on SILVERM1 (+0.302 on the SILVER chart), beat the random-deletion check (0.209), kept S3 unchanged (PF 1.47 vs 1.48) and lifted S1 PF 1.09 -> 1.17 and S2 PF 1.18 -> 1.54,
but was ineligible ONLY because it left 215 S1+S2 trades (< the 300 floor). The 400-pt version failed S1 PF (0.91).
An absolute-points floor does not scale if silver's price or volatility changes, so round 2 expresses the same idea as a share of price.

## Candidates (exactly 4; cumulative trials on this question: 17)
Skip entries whose stop distance (signal-bar close to stop) is < 0.20% / 0.25% / 0.30% / 0.35% of the signal-bar close (about 460 / 570 / 685 / 800 pts at a price of 228,000).
## Rules: identical to round 1 EXCEPT the minimum-trades floor, which is lowered from 300 to 200 S1+S2 trades. This is stated openly: the idea works by deleting small-stop trades, so fewer trades is the
mechanism, not a defect; the floor is lowered because of what round 1 showed, and that makes this round weaker evidence than a rule fixed in advance.
Everything else (expectancy gain >= +0.03 on SILVERM1 and >= +0.02 on the SILVER chart, S1 and S2 PF each >= deployed - 0.02, S3 guard PF >= deployed - 0.10 and net >= 85%, random-deletion luck check)
is unchanged. Caveat to be reported: S3 (2025-11 on) has almost no trades with small stops, so it adds almost no independent information for this idea; the only independent evidence is the SILVER chart
and future trades.
