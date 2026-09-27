# Pre-registration: round 3, different ideas (2026-09-27)
Rounds 1-2 (100 trials) tuned exits, EMA lengths and simple filters and found nothing. Round 3 tests 25 ENTRY-QUALITY filters not tried before, each at two entry starts (09:15 and 17:30) = 50 configs (cumulative 150 trials).
Filters (all on crude #1 base, applied to the signal bar): body >= 0.5 ATR / >= 0.3 ATR; close in the top/bottom 30% / 50% of the bar range in trade direction; close above/below EMA60 (about 15m EMA20); above/below EMA240 (about 1h EMA48);
close above/below previous-day close; above/below the day open; ATR above its 50th percentile of 500 bars; ATR below its 90th percentile; volume above SMA20 / SMA50; EMA22 sloping with the trade over 6 bars;
close within 2 / 3 ATR of EMA22; skip Mondays; RSI14 >50 / >55 in trade direction; above/below session VWAP; above/below the 20-bar Donchian midpoint; fixed 2.0 ATR / 2.5 ATR stop instead of the swing stop;
prior 10-bar range < 3 ATR (squeeze) / >= 3 ATR; signal bar range < 1.5 ATR.
Stricter pass rule (fixed now): a filter PASSES only if, at BOTH entry starts, it beats the same-start control in TRAIN gross, HOLDOUT gross, full PF and HOLDOUT after-cost, with >=100 trades and >=15 trades/month at 09:15.
Anything passing goes to a second check (paired sibling threshold must not contradict) and then TradingView replay. Also report Spearman(TRAIN, HOLDOUT). If nothing passes that is the result.
