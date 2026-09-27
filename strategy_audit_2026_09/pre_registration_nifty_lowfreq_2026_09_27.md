# Pre-registration: tighten Nifty to a lower, more selective trade rate, maximize PF (2026-09-27)
Context: BankNifty's live forward-test strategy (Supertrend20-3+volume scalp) trades ~28.9/month on its own. The user wants combined BankNifty+Nifty around 60 trades/month total, so Nifty is targeted at roughly
20-35 trades/month here (leaving BankNifty untouched -- it is already live/forward-testing and already a reasonable frequency on its own). Within that band, the goal is the highest PF and net points, not raw frequency.
Bases (both already found consistent on a split-half check, `nifty_scratch_scalp_results_2026_09_27.md`): H (EMA9/22 cross, ~2xATR stop that rarely binds, pure time-based exit) and Q4 (Donchian(20) breakout, 1.5R, 30-min time-stop).
NSE:NIFTY spot 5m, 6.3 months usable (TradingView's own floor for Nifty, unchanged).
34 configs:
A (4) H base, time-stop in {8, 10, 12, 15} minutes, no added filter (re-establishing the frequency/PF gradient already found).
B (5) H base (time-stop 10min) + one filter each: 15m ADX>=15, 15m ADX>=20, EMA200 agreement, above-average volume, ADX>=15 AND EMA200.
C (4) Q4 base, Donchian lookback in {20, 30, 40, 55}, RR 1.5, 30-min time-stop, no added filter.
D (5) Q4 base (lookback 30) + one filter each: 15m ADX>=15, 15m ADX>=20, EMA200 agreement, above-average volume, ADX>=15 AND EMA200.
E (8) time-of-day restriction on the best-looking H/Q4 variant from A-D (decided after seeing them): avoid midday 12:00-13:30, only 09:15-12:00, only 12:30-15:15, skip Monday, skip Friday -- x2 bases.
F (8) hand-picked combinations of the strongest single filters from B/D, on both bases.
Pick rule (fixed now): among configs landing in trades/month 15-35, highest PF; must also beat its own base's PF on BOTH halves of the data (split at the window midpoint) to count as a real improvement, not a lucky filter.
A pass is a harness-only candidate pending TradingView confirmation and a forward test, same as every other finding this project. Report the full table regardless.
