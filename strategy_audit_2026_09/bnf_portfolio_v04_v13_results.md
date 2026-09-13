# BankNifty Portfolio: v0.4 + v13 merged, same capital (13 Sep 2026)

## What was built

`A91_bnf_portfolio_v04_v13.pine.txt` -- a single Pine v5 `strategy()` merging v0.4's EMA-pullback logic and
v13's sweep-fade logic exactly as requested:

1. **Independent logic blocks.** v0.4's and v13's variables are entirely separate (`a*` prefix for v13,
   `b*` prefix for v0.4) -- neither module reads or writes the other's state.
2. **Distinct entry/exit IDs**, as specified: `v13_Long` / `v13_Short` / `v13_ExitL` / `v13_ExitS` for the
   sweep-fade module, `v04_Long` / `v04_Short` / `v04_ExitL` / `v04_ExitS` for the pullback module.
3. **`pyramiding = 2`** in the `strategy()` declaration, so both modules can hold a position at the same time.

Base for this file: an existing, previously-tested 3-module combined script already in this repo
(`bnf combined v1...pine.txt`, v13 + v0.4 + a third MTF module). Module C was removed; v13 and v0.4's logic is
byte-identical to that script's modules, which were themselves direct ports of the standalone `v13`/`v0.4`
files -- nothing in either module's entry, stop, target, or session rules was changed for this exercise.

## One technical point worth explaining before the numbers

TradingView's `strategy()` engine keeps **one net position per script**, not one position per module. If v0.4
is long and v13's fade signal wants to go short at the same moment, a naive "just enter both" would not create
two independent positions -- it would net them against each other and misattribute both modules' P&L. So,
matching the design of the pre-existing combined script: **same-direction concurrent positions are allowed**
(this is what `pyramiding=2` is for, and it's exercised whenever both modules are long, or both are short, at
once) but **opposite-direction signals are mutually exclusive** -- if v0.4 holds a long, v13's short signal
(and vice versa) is skipped that bar rather than silently closing/netting the other module's trade. This isn't
an extra restriction I added; it's the only way to keep the two modules' P&L honestly separable inside one
broker-emulated account, and it's exactly how the earlier 3-module version already in this repo handles it.

## Results: 5-minute BankNifty, 6 tiled windows, 2023-09-26 -> 2026-09-13 (35.6 months)

| | Trades | Win% | PF | Net pts | Read |
|---|---|---|---|---|---|
| **v13 module (inside portfolio)** | 273 | 30.4% | **0.97** | **-505** | Worse than its solo result |
| **v0.4 module (inside portfolio)** | 82 | 42.7% | **1.31** | **+1,469** | Close to its solo result |
| **TOTAL (combined capital)** | **355** | 33.2% | **1.04** | **+964** | Barely above breakeven |

By window, oldest to newest, TOTAL net pts: -1,177, +249, -522, +880, -719, +2,252

Max drawdown (largest single-window figure, same per-window convention used everywhere else in this project
-- it does not capture a drawdown that spans a window boundary): **1,764 pts**, in the live window.

## The honest finding: this fell well short of the +2,317 you expected, and here's why

**+2,317 was v0.4 alone (+1,403) plus v13 alone (+914) -- two separate backtests added together, assuming they
don't interact.** The actual combined script gets **+964, only 42% of that naive sum**, and the combined PF
(1.04) doesn't even clear the 1.15 bar this project has used as a minimum everywhere else, let alone v0.4's own
1.33.

The reason isn't that the strategies are secretly correlated after all (the -0.03 correlation, measured on
each strategy's own independent window returns, is real). It's that **combining them inside one account changes
which trades each one actually takes.** The mutual-exclusion rule above means v13's more frequent signals (273
trades vs its solo ~233) sometimes get blocked when v0.4 already holds the opposite-direction position, and
v13's performance is what absorbed nearly all the damage: **it went from a modest winner standalone (PF ~1.06,
+914 pts over 5 windows) to a net loser inside the portfolio (PF 0.97, -505 pts over 6 windows).** v0.4 held up
close to its solo number (+1,469 vs +1,403, over one extra window). This is a real interaction effect, not a
coding error -- it's the actual cost of sharing one execution account between two strategies that sometimes
want opposite things at the same time.

**What this does confirm:** trade frequency genuinely went up (355 trades vs v0.4's 74 alone -- 4.8x), and the
combined result is still net positive, just not by much. Unlike the v0.5 filter-loosening attempt (PF 0.71/0.68,
badly negative), this isn't a failed idea -- it's a real, modest, working portfolio. It's just a much smaller
edge than simple addition suggested, and PF 1.04 is thin enough that it's not clearly better than trading v0.4
alone and accepting its lower frequency.

## Recommendation

Don't deploy this in place of v0.4 alone without a closer look at *why* v13 degrades when combined -- the
mutual-exclusion collisions are identifiable trade-by-trade in this script's own data (every skipped v13 signal
happens when `bWaitL`/`bWaitS`/`anyLong`/`anyShort` is true) and would be worth examining before trusting this
portfolio with size. As it stands: v0.4 alone (PF 1.33, +1,403, 74 trades) has a cleaner risk/reward than this
combination (PF 1.04, +964, 355 trades) for a similar amount of total risk taken.
