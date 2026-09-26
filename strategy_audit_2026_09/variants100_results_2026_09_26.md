# 100 variants each of crude and BankNifty, plus the TradingView crude replay (2026-09-26)

Pre-registration: `pre_registration_100variants_2026_09_26.md`. Code: `variants100.py`, `variants100_analysis.py`.
Raw (gitignored): `research_data/variants100_{CRUDE,BANKNIFTY}.csv`, `research_data/tv_replay_crude_{A,B}.txt`.
Split: TRAIN 2024-03-25 -> 2025-06-25, HOLDOUT 2025-06-25 -> 2026-09-25. Selection on TRAIN only, holdout read once.

## Verdict: nothing found on either instrument. 0 of 200 variants passes, and the search itself shows why.

## Part 1 - TradingView tiled replay, crude, all available months (2024-01-18 -> 2026-09-25), 5m, no costs, 13 windows
| | trades | PF | net pts | pts/trade | worst-window dd | windows profitable |
|---|---|---|---|---|---|---|
| **A: crude #1 (flip only, RR 4.0)** | 910 | **1.229** | **+5,672** | +6.2 | 1,898 | 8 / 13 |
| B: crude #1 + breakout(5) | 1,859 | 1.076 | +4,074 | +2.2 | 1,924 | 6 / 13 |
B beats A in **3 of 13** windows (W2 tie, W3, W8/W11 gains are outweighed by W1, W4, W6, W9, W10, W12, W13). TradingView agrees with the harness
(785 / 1.263 / +5,614 vs 1,607 / 1.120 / +5,547): the breakout doubles trades and halves the edge per trade. The replay reused the loaded silver v4.1
study with inputs set to crude #1's (minSL 1.5, maxSL 3.0, RR 4.0, no daily limit), and the forward-test inputs were restored afterwards.

## Part 2 - the 100-variant searches (harness-screened; TradingView cannot replay 100 variants)
| | CRUDE | BANKNIFTY |
|---|---|---|
| variants run | 100 (+2 controls) | 100 (+2 controls) |
| **transfer: Spearman(TRAIN net, HOLDOUT net)** | **+0.042** | **-0.156** |
| median TRAIN net / median HOLDOUT net | +486 / +1,107 | +2,775 / **-1,160** |
| profitable after costs on TRAIN / on HOLDOUT | 16 / 38 | 19 / **0 of 100** |
| eligible (>=100 trades, positive after costs on TRAIN) | 16 | 19 |
| **PICK (top TRAIN net)** | V089: flip-only, RR 5, minSL 2.0, maxSL 5.0, EMA9/22, pullback 1.0, US session 17:00-23:30, flat 22:45 | V037: flip OR breakout(2), RR 2.5, EMA9/22+EMA200, pullback 2.0, ADX 15, late session, flat 14:30 |
| pick TRAIN -> HOLDOUT (gross) | +2,331 -> **+1,885** | **+11,188 -> -4,225** |
| pick TRAIN -> HOLDOUT after costs | +1,774 -> +1,230 | +2,078 -> **-15,217** |
| incumbent, same split | crude #1: +2,270 -> **+3,344** | v0.4: +1,300 -> **+1,701** (+866 after costs) |
| variants beating the incumbent on HOLDOUT | 13 of 100 | 9 of 100 |
| their TRAIN ranks | 6, 10, 24, 26, 36, 43, 46, 47, 68, 82, 83, 91 | 6, 43, 65, 75, 85, 91, 92, 98, 100 |

**Gates for the picks.** Crude V089: positive after costs PASS, PF>=1.15 PASS, >=100 trades PASS, but **fails "beats crude #1" (+1,885 vs +3,344)**
and "best month <= 40%" (47.6%). BankNifty V037: **fails all of positive after costs, beats v0.4, PF>=1.15 (0.879) and concentration.**

## What the numbers say
- **Tuning does not transfer, again.** Rank correlations of +0.042 and -0.156 across 100 variants each are zero. The variants that later beat the incumbent
  were spread across the whole train ranking (rank 6 to rank 100): knowing how a variant did in training told us nothing about the holdout.
- **BankNifty is the clearest case of selection bias.** The best of 100 on TRAIN made +11,188 and then LOST 4,225 in the holdout (-15,217 after costs);
  the median variant went from +2,775 to -1,160; **not one of the 100 was profitable after costs in the holdout.** v0.4 made +1,701 (+866 after costs) with 37 trades.
- **Crude #1 held up: its holdout (+3,344) beat 87 of 100 variants.** It was chosen earlier by the repo on data that included the holdout, so this is not
  clean out-of-sample evidence for it - but no variant did better in a way that the training half could have predicted.
- The crude pick dropped the breakout entirely (flip-only). The search, left free to use breakouts, ranked a flip-only strategy first on TRAIN.

## Observation, explicitly NOT a finding (chosen after seeing the holdout)
Crude V072 (breakout only, 3-bar, RR 5, day session) made +3,838 in the holdout, above crude #1's +3,344, at TRAIN rank 5 and only +23 after costs in training
(holdout after costs +2,163 vs crude #1's +2,191). It is what a post-hoc "discovery" looks like; it was not the pre-registered pick and is not claimed.

## Why silver's result does not repeat
Silver's edge was ~+370 points per trade against ~60 points of cost; crude's is ~+6 against ~2.6; BankNifty's is ~+20 against ~22 (v0.4: +41). More variants of the same
trigger cannot raise a per-trade edge that is already the size of the cost. What worked for BankNifty (v0.4) is selectivity - wick, volume and VWAP filters that
cut trades to ~2.5/month - the opposite of what a wider search rewards.

## TradingView confirmation
No variant passed the harness gates, so none qualified as a finalist; confirming a strategy already known to lose to its incumbent would only add noise. The crude pick's
pullback gate and force-flat cannot be expressed in the loaded study's inputs anyway. What WAS confirmed on TradingView across all available months is Part 1.

## Bottom line
Keep crude working_strategies #1 for crude and v0.4 for BankNifty. On both instruments 100 variants found nothing that a training window could pick
and a holdout would confirm. Running gate total: 0 of ~4,950.
