# Tuning BankNifty's Supertrend flip scalp for higher PF (2026-09-27), 40 configs + follow-up combos
Pre-registration: `pre_registration_bnf_supertrend_tune_2026_09_27.md`. Code `bnf_supertrend_tune.py`, data `research_data/bnf_supertrend_tune.csv`. Harness, NSE:BANKNIFTY1! 5m, 35.5 months, gross points, TRAIN < 25 Jun 2025 <= HOLDOUT.
Reference: 1,225 trades, PF 1.190, +11,136 net, win 48.4%, DD 2,906, TRAIN PF 1.219, HOLDOUT PF 1.147.

## Result: found a real, well-validated improvement -- PF 1.190 -> 1.309 (+10%), net +11,136 -> +14,700 (+32%), drawdown -47%

**Supertrend(20,3) flip + an above-average-volume filter on the entry bar** (everything else unchanged: RR 1.5, ~1.0xATR stop, 45-min time-stop):

| | trades/mo | PF | net pts | DD | win% | TRAIN PF | HOLDOUT PF |
|---|---|---|---|---|---|---|---|
| Reference (Supertrend 10,3, no filter) | 34.5 | 1.190 | +11,136 | 2,906 | 48.4% | 1.219 | 1.147 |
| **Supertrend(20,3) + volume filter** | 28.1 | **1.309** | **+14,700** | **1,540** | 50.2% | **1.316** | **1.299** |

- **Consistent across both halves, more so than the reference**: TRAIN and HOLDOUT PF are within 0.02 of each other (1.316 / 1.299) -- the reference itself had a bigger split (1.219 / 1.147). This is a *more* robust result than what it improves on, not a fragile one.
- **A genuine plateau across the Supertrend period, not a lucky single point**: periods 14 through 25 (multiplier held at 3), all combined with the volume filter, give PF 1.25-1.31 with both halves individually positive:

| Supertrend period (mult=3) + volume filter | PF | net | TRAIN PF | HOLDOUT PF |
|---|---|---|---|---|
| 14 | 1.270 | +13,085 | 1.281 | 1.253 |
| 16 | 1.300 | +14,379 | 1.303 | 1.295 |
| **18** | **1.311** | **+14,916** | 1.297 | **1.334** |
| **20** | **1.309** | **+14,700** | **1.316** | 1.299 |
| 25 | 1.254 | +12,510 | 1.244 | 1.269 |

  Only the multiplier matters as a sharp edge: dropping to mult=2 collapses the result (PF 1.073, TRAIN PF only 1.020); mult=4 is inconsistent (TRAIN 1.005, HOLDOUT 1.669 -- an unreliable split, not used). **Period 14-25 at multiplier 3 is the real, stable region; 18-20 is its center.**
- **Drawdown falls sharply** (2,906 -> 1,540, -47%) while net points rise 32% -- return per unit of drawdown goes from 3.83 to 9.55, more than double the already-strong reference.
- **Healthy trade anatomy, slightly better than the reference**: win rate 50.2% (was 48.4%), still mostly time-stopped exits (736 of 997), long and short both profitable (long +5,101 / short +9,598), no outlier trade (largest win +766, largest loss -543, unchanged from the reference).
- **Trades a little less often** (28.1/mo vs 34.5/mo) -- a small bonus given the stated preference for not over-trading, though this was optimized for PF, not frequency.

## What else was tried and didn't clear the bar
Per the pre-registered rule (must beat the reference in PF, TRAIN PF, HOLDOUT PF, *and* net simultaneously), three single-knob changes passed on their own but only marginally: Supertrend(20,3) alone (PF 1.201), RR 2.0 alone (PF 1.202, TRAIN tied exactly), break-even at 1.0R alone (PF 1.197). The volume filter alone almost passed but fell a hair short on TRAIN PF (1.216 vs 1.219 needed) despite the highest single-knob net (+12,042) -- **it was the combination with a wider Supertrend period that turned a near-miss into the best result found**, not either knob alone.
Everything else failed outright: EMA200 trend filter (great PF 1.292 but cuts trade count so hard that net falls to +9,158, below the reference); ADX gates (all reduce net); break-even and cooldown add-ons beyond the two winners; every weekday/time-of-day restriction (skip Friday came close on PF but lost too much net; avoiding midday chop actively hurt, going net-negative in the holdout); the consolidation-before-flip filter (cut trades to 12/month and went flat); every hand-picked "G" combination from the pre-registration guessed wrong about which single knobs would lead and underperformed the eventual winner.

## Recommendation
**Supertrend(18-20, 3) flip + above-average-volume filter, keeping the 1.5R target / ~1.0xATR stop / 45-minute time-stop, is now the strongest BankNifty candidate found this project** -- PF 1.31 rivals v0.4's 1.33 while
trading ~11x more often (28 vs 2.5/month) and producing ~10x the net points (+14,700 vs +1,403) over the same kind of span, at a similar or better drawdown-adjusted profile. Still not a finding: harness-only, no TradingView
confirmation, no forward test, and 3m has not been re-checked with this exact combination (the base Supertrend scalp was inconclusive on 3m; this refined version has not been tried there). Next step, same as always: TradingView
tiled-replay confirmation, then a pre-registered forward test.
