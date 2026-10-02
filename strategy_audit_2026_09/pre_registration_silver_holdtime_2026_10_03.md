# Pre-registration: shorter holding time for live silver v4.1 (written 2026-10-03, BEFORE the run)

Why: the trader buys OPTIONS on this signal; theta is paid every hour held. Live v4.1 averages 14.1h per trade with 14% over 24h.
Entries are FROZEN (the live [strategy.SILVER] v4.1: SHA flip OR 3-bar Donchian, stop floor 2.5 / cap 5.0 x ATR, 350-pt day limit,
15-17h excluded). Data: SILVER1! 5m, ~30 months (research_data/bars). Points, net of 0.02%/side, gap fills, 400-bar warm-up.

## Grid (exactly 18 variants; nothing added after seeing results)
- RR (target = RR x stop distance): 1.5, 2.0, 3.0 (3.0 = current)
- time stop (exit at next bar's open this many minutes after the fill): none, 240, 120
- flat at the open of the 23:25 bar (no overnight): no, yes

## Pass criteria (all must hold)
1. Average hold <= 4.0 hours.   2. >= 600 trades.   3. PF >= 1.15 in each of TRAIN (oldest 60%), VALIDATION (next 20%), HOLDOUT (newest 20%).
4. >= 50% of calendar months positive.   5. PF over all trades >= 1.15 and net > 0.
(1.15 not 1.30 because the baseline itself is below 1.0 in TRAIN; a variant that fails any criterion is dropped, not re-tuned.)
18 trials on one dataset => treat any pass as a candidate for the shadow book, never as proof. Nothing is changed live from this test.
