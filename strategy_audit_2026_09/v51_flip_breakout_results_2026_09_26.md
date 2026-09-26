# Results: v5.1 SHA-Flip + Donchian Breakout on silver (run 2026-09-26)

File: `working_strategies/Silver/5_v5.1_flip_breakout.pine.txt`. Harness, window and conventions as every other run
today: 30 months (2024-03-25 -> 2026-09-24), gross points, qty 1, six fixed calendar windows.
Header claim in the file: **"28 trades, PF 1.69, WR 39.3%, net +5,249 pts"**.

## Verdict: does not beat the incumbent on points, and its profit is more concentrated, not less.

| | trades | /mo | PF | **net pts** | maxDD | win | months +ve |
|---|---|---|---|---|---|---|---|
| **incumbent v4.0 wideATR+350** | 747 | 24.9 | 1.503 | **+222,240.5** | 33,692.8 | 30.5% | 58.1% |
| **v5.1 flip OR breakout (as shipped)** | 671 | 22.4 | **1.626** | **+145,386.7** | **17,823.4** | 31.7% | 54.8% |
| v5.1, flip only | 313 | 10.4 | 1.640 | +83,504.9 | 14,614.1 | 33.5% | 58.1% |
| v5.1, breakout only | 636 | 21.2 | 1.531 | +120,017.2 | 26,823.7 | 30.8% | 48.4% |
| v5.1, lookback 3 | 796 | 26.5 | 1.452 | +133,811.0 | 22,240.7 | 30.7% | 54.8% |
| v5.1, lookback 10 | 503 | 16.8 | 1.653 | +118,677.0 | 14,813.4 | 33.0% | 64.5% |
| v5.1, lookback 20 | 410 | 13.7 | 1.587 | +95,855.6 | 21,749.1 | 32.2% | 64.5% |

v5.1 earns **65% of the incumbent's points** (+145,387 vs +222,240) at a similar trade rate. It is genuinely better
on risk - PF 1.626 vs 1.503 and **max drawdown almost halved, 17,823 vs 33,693** - but by the net-points standard
the user set, it loses.

## The Donchian breakout is doing real work
Flip-only earns +83,505 on 313 trades; breakout-only earns +120,017 on 636; together +145,387 on 671. The breakout is
the larger contributor and roughly doubles the trade rate (10.4 -> 22.4/mo), which is what fixes v5.0's starvation
problem. That part of the idea works and is the best thing in the v5.x line so far.

## But the profit is one window, worse than the incumbent's
Per-window net: W1 +3,548 | W2 **-6,245** | W3 +4,524 | W4 +1,926 | **W5 +136,998** | W6 +4,636.
**W5 alone is 94.2% of the total.** The incumbent's equivalent concentration is 61.4%, which was already flagged as a
problem. Outside W5, v5.1 earns +8,389 across 25 months and loses money in one window. Whatever this is, it is a bet
on the Nov 2025-Apr 2026 silver move with a lower drawdown, not a broader edge.

## The header's claimed numbers do not reproduce, and the likely source is a 4.7-month sample
Claim: 28 trades, PF 1.69, net +5,249. Measured over 30 months: **671 trades, PF 1.626, +145,387** - the PF is close,
everything else is an order of magnitude apart. Re-running on `journal_data/cache/backtest/SILVER_5min.csv`, which now
holds only **4.7 months** (2026-05-06 -> 2026-09-25), gives **64 trades, PF 0.782, net -7,584.5, win 28.1%** net of
costs - a loser. So the claim does not reproduce on the full history OR on the truncated cache. Same pattern as the
v5.0 README claims (`v50_results_2026_09_26.md`): the quoted numbers cannot be traced to either dataset available here.

## As bought options (SILVER chain, measured IV 28%)
| spread/side | PF | net (pts) | maxDD |
|---|---|---|---|
| 0% | 1.902 | +104,391.1 | 8,817.6 |
| 1% | 1.354 | +52,920.0 | 25,536.5 |
| 2% | 1.008 | +1,448.9 | 54,508.8 |
At 1%/side it keeps 36% of its futures points (+52,920 of +145,387), essentially level with the incumbent's option
translation (+104,882 from a much larger futures base). Dies at 2% like everything else.

## Code notes (not run on TradingView)
Better built than the earlier v5.x files: `adxOK` is wired into all four entry conditions, `shaStable` uses the fixed
non-no-op form, and the Donchian channel is correctly shifted `[1]` so there is no lookahead. **But it has 6 semicolon
statement lines again** (`o1 = ta.ema(open, shaLen1); c1 = ...`), which Pine rejects with "no viable alternative at
character ';'" - so it will not compile as written. Same defect fixed twice already today.

## Bottom line
Keep the incumbent. v5.1's breakout entry is the one genuinely useful idea in the v5.x line - it solves the trade-rate
problem and halves drawdown - but it earns a third less, and 94% of what it does earn is a single five-month window.
Worth revisiting only if the breakout entry is tested on the v4.0 base (no EMA200, no pullback gate, wide ATR stops)
rather than on the v5.0 filter stack. That combination has not been tested.
