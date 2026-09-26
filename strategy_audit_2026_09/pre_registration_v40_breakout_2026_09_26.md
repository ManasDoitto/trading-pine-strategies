# Pre-registration: Donchian breakout entry on the v4.0 base, silver (written 2026-09-26, BEFORE the run)

Motivation, from `v51_flip_breakout_results_2026_09_26.md`: v5.1's Donchian breakout entry doubles the trade rate
(10.4 -> 22.4/mo) and halves drawdown (33,693 -> 17,823), but it was bolted onto the v5.0 filter stack, which today's
testing showed is what destroys this family's points (EMA200 always on, EMA9 pullback gate, ADX gate). v5.1 therefore
earned only 65% of the incumbent's points. **This tests the breakout on the base that actually earns points.**

## Base (frozen) = silver working_strategies #1, exactly as it is
SHA 10/10 flip + EMA9>EMA22 alignment ONLY. No EMA200, no pullback proximity, no ADX gate, no vol regime, no SHA
stability filter, no force-flat. Swing 10 / buffer 0.1, **minSL 2.5, maxSL 5.0, R:R 3.0**, fixed 350-pt daily loss
limit, session 09:15-23:30. This base scores 747 trades, PF 1.503, **+222,240.5 pts**, maxDD 33,692.8 on the harness.

## The one change
Entry becomes `SHA flip OR Donchian breakout` (close above the prior `N`-bar high for longs, below the prior N-bar
low for shorts; the channel is shifted one bar, so no lookahead). The EMA9/22 alignment and all risk rules still apply
to breakout entries exactly as they do to flip entries.

## Variants (exactly six, nothing added afterwards)
B1 lookback 3 | B2 lookback 5 (v5.1's value) | B3 lookback 10 | B4 lookback 20 | B5 breakout-only, lookback 5
(no flip entries) | B6 lookback 5 with the 15m ADX>=25 gate added back, to check whether the gate helps once the
other filters are gone.

## Pass criteria (primary criterion is NET POINTS, per the user's standing instruction)
1. **Beat +222,240.5 net points** over the same 30 months, gross.  2. >= 600 trades (20/mo).
3. **Best single window <= 61.4% of net** - i.e. no more concentrated than the incumbent already is. A variant that
   earns more only by loading further into window 5 is reported as failing.
4. Max drawdown <= the incumbent's 33,692.8.
5. Walk-forward check: selecting the best variant on windows 1..i-1 by net points and trading it in window i must
   beat holding the incumbent over W2-W6.
Failing 1 or 3 means it is not an improvement, whatever the headline.

## Prior
The breakout demonstrably adds trades and cuts drawdown; whether it adds POINTS on a base that is not already
starved is the open question. v5.1's profit was 94.2% one window, so criterion 3 is the one most likely to fail.
0 of 4,714 tested strategies have passed this repo's gates.
