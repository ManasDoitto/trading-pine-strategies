# Crude #1: round 3, 25 entry-quality filters x 2 starts (2026-09-27)
Pre-registration: `pre_registration_crude_round3_2026_09_27.md`. Code `crude_round3.py`, data `research_data/crude_round3.csv`. Harness, gross points, TRAIN < 2025-06-25 <= HOLDOUT. Cumulative trials: 150.
Controls: 09:15 785 tr, PF 1.263, +5,614 (2,270 / 3,344); 17:30 429 tr, PF 1.476, +6,558 (2,447 / 4,111).

**Pass rule (must beat control in TRAIN, HOLDOUT, PF and HOLDOUT after-cost at BOTH starts): NO FILTER PASSES.**
- Most filters HURT: candle-body >= 0.5 ATR (-782 / -708), body >= 0.3, close-position 30%, RSI>55, squeeze, previous-day close, day open, skip Monday, volume > SMA20 all lose profit at both starts. Fixed 2.0/2.5 ATR stops turn the strategy into 1,659 / 1,272 trades with after-cost profit +1,383 / -550.
- Neutral: distance < 2/3 ATR (no-op), RSI>50, EMA22 slope, VWAP, Donchian midpoint (PF up a little, TRAIN lower).
- **Closest: ATR below its 90th percentile (skip the most volatile bars).** 09:15: 753 tr, PF 1.388, +7,264 (TRAIN 1,988 / HOLDOUT 5,276); 17:30: 375 tr, PF 1.695, +7,820 (2,087 / 5,733). Full-period and holdout gains at both starts, PF up, DD not worse, but TRAIN is LOWER than control at both starts (1,988 < 2,270; 2,087 < 2,447), so it fails the rule: the gain is entirely in the second half. Recorded as a hypothesis for forward testing, not a finding.
- Volume > SMA50 lifts PF (1.453 / 1.696) but TRAIN collapses (380 / 673).
