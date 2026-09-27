# Pre-registration: tune BankNifty's Supertrend flip scalp for higher PF (2026-09-27)
Base = Supertrend(10,3) flip scalp: RR 1.5, ~1.0xATR stop, 45-min time-stop, session 09:15-15:20, flat 15:20-15:30, no day-loss limit.
Reference (harness, NSE:BANKNIFTY1! futures 5m, 35.5mo, gross): 1,225 trades, PF 1.190, +11,136 net, win 48.4%, DD 2,906, TRAIN PF 1.219/HOLDOUT PF 1.147 (both halves positive).
40 configs, all evaluated on the same 35.5-month harness, TRAIN < 25 Jun 2025 <= HOLDOUT:
A (7) Supertrend (period, multiplier): (7,2), (7,3), (10,2), (10,4), (14,2), (14,3), (20,3).
B (5) trend/quality filters added to the base: +EMA200 agreement, +15m ADX>=15, +15m ADX>=20, +above-average-volume, +both ADX15>=15 and EMA200.
C (8) exit re-tune: RR in {1.0, 1.25, 1.75, 2.0, 2.5} (5) x time-stop in {30, 60, 75, 90} minutes (paired with the current best RR from A/B once seen; interim uses RR=1.5) -- concretely: RR alone (4: 1.0,1.25,2.0,2.5) + time-stop alone (4: 30,60,75,90).
D (5) stop model: min_sl in {0.5, 0.75, 1.5, 2.0} xATR, plus close-based (not low/high) swing stop.
E (5) entry-quality: skip Monday, skip Friday, avoid entries 12:00-13:30 (midday chop), only trade 09:15-12:00, only trade 12:30-15:15.
F (5) mechanism add-ons: break-even at 0.75R, break-even at 1.0R, cooldown 6 bars after a stop-loss, cooldown 12 bars, min-hold 2 bars before a reversal-style re-entry is allowed (skip -- not applicable, replaced with a second consolidation-before-flip filter: ATR contracting over the prior 10 bars).
G (5) hand-picked combinations of whichever single knobs look best once A-F are in, decided after seeing the single-knob results (kept to simple, explainable combinations, not a second free search).
Pick rule (fixed now): among configs with >=15 trades/month, highest PF wins, but it only counts as a genuine improvement if it ALSO beats the reference in TRAIN PF, HOLDOUT PF, and net points (not just one half) --
matching every other robustness check this project has used. A pass is a harness-only candidate, not a finding, pending TradingView confirmation. Report the full table regardless.
