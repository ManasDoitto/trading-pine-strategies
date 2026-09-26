# BankNifty v5.1 flip+breakout: tested, adjusted, and it does not work (run 2026-09-26)

Pre-registration: `pre_registration_bnf_breakout_2026_09_26.md`. Code: `bnf_breakout_test.py`. Raw: `research_data/bnf_breakout.csv`.
NSE:BANKNIFTY1! 5m, 2024-03-25 -> 2026-09-24 (30 months), 1 lot, points, six calendar windows. 20 pre-registered trials.

## Verdict: 0 of 20 pass, and NONE is profitable after 0.02%/side. The silver breakout recipe does not transfer.

## The incumbent, measured on the same harness (its own engine)
BankNifty v0.4: **74 trades (2.5/mo), gross PF 1.880, +3,001 pts (+40.6/trade); after 0.02%/side PF 1.326, +1,407 (+19.0/trade).**
That reproduces the README's PF 1.29 / +1,277 (different cost convention), so the harness is validated for BankNifty.

## The shipped file and its ablations (gross unless stated)
| trial | trades | /mo | PF | net pts | maxDD | win | pts/trade | best month | **after 0.02%/side** |
|---|---|---|---|---|---|---|---|---|---|
| **S0: v5.1 as shipped** | 212 | 7.1 | 1.242 | +3,909 | 1,809 | 45.3% | +18.4 | 37.5% | PF 0.965, **-657** |
| S0 - flat 15:00 | 216 | 7.2 | 1.236 | +4,062 | 1,913 | 41.7% | +18.8 | 48.5% | PF 0.971, -589 |
| S0 - RR 2.0 | 215 | 7.2 | 1.190 | +3,039 | 2,185 | 46.5% | +14.1 | 45.0% | PF 0.914, -1,587 |
| S0 - no EMA200 | 268 | 8.9 | 1.168 | +3,446 | 1,687 | 44.0% | +12.9 | 51.8% | PF 0.902, -2,330 |
| S0 - no pullback gate | 291 | 9.7 | 1.117 | +2,861 | 3,430 | 44.0% | +9.8 | 52.3% | PF 0.877, -3,444 |
| **S0 - no ADX gate** | 256 | 8.5 | **1.281** | **+5,464** | 1,931 | 45.7% | **+21.3** | 45.8% | PF 0.999, **-30** |
| S0 - no vol regime | 342 | 11.4 | 1.184 | +4,526 | 2,258 | 44.2% | +13.2 | 41.4% | PF 0.901, -2,849 |
| S0 - no ATR floor | 261 | 8.7 | 1.096 | +1,836 | 2,264 | 42.1% | +7.0 | 79.8% | PF 0.829, -3,833 |
The file's own header says "126 trades, PF 0.94"; on this harness it is 212 trades, PF 1.242 gross and PF 0.965 net - the same
story once costs are applied. The README already calls it "not recommended". **Only one adjustment helps: dropping the ADX gate
(+40% gross points, PF 1.281)**, consistent with the repo's 14 Sep and 26 Sep findings that the ADX gate does not port to
SHA-flip entries. Even so, it nets -30 after costs: breakeven at best.

## The silver recipe (breakout on a clean EMA9/22 base) collapses on BankNifty
| entry \ RR | 2.0 | 3.0 | 4.0 |
|---|---|---|---|
| flip only (ancestor) | PF 1.207, +4,882, 14/mo | PF 1.209, **+5,035**, 14/mo | PF 1.150, +3,625 |
| flip OR breakout(3) | PF 1.007, +545, 36/mo | PF 1.028, +2,088 | PF 1.009, +653 |
| flip OR breakout(5) | PF 0.974, **-1,818** | PF 1.008, +522 | PF 0.992, -528 |
| flip OR breakout(10) | PF 1.066, +3,608 | PF 1.083, +4,490, 26/mo | PF 1.037, +2,025 |
The breakout does what it did on silver - it multiplies trade count (14/mo -> 26-36/mo) - but on BankNifty it destroys
quality: PF falls from ~1.2 to ~1.0, drawdown triples (2,052 -> 5,700-7,400), and W3/W4/W6 turn negative. Every breakout
variant is worse than its own flip-only ancestor. After 0.02%/side they lose **-12,537 to -22,960 pts**.

## Why it worked on silver and not here: the edge has to clear the cost
| | gross pts per trade | 0.02%/side round trip | edge left |
|---|---|---|---|
| Silver bo(5) | ~+372 | ~59 pts | ~84% |
| BankNifty v5.1 (S0 - no ADX) | +21.3 | ~22 pts | **~0%** |
| BankNifty best breakout | +5.7 | ~22 pts | negative |
| **BankNifty v0.4** | **+40.6** | ~22 pts | **~46%** |
BankNifty trades earn ~20 points against a ~22-point cost, so any strategy that trades more without raising quality goes
negative. v0.4 wins because it is selective and its per-trade edge (+40.6) is twice the alternatives'.

## Walk-forward: tuning loses again
Picking the best of the 20 on past windows and trading the next: **-2,050 pts over W2-W6, versus +3,195 for simply holding
the shipped file and +1,138 for a median trial.** The picks were "no ADX" three times running, and it lost in W5 and W6.
That is now well over twenty independent past-to-next measurements saying parameter performance does not persist.

## Option-premium screen (IV ASSUMED at 12-18%, chain not fetched)
ATM BankNifty call at F=55,000: ~364-546 pts at 7 days, ~629-944 at 21 days. A +18-21 pt average trade is ~4-6% of a
weekly premium and v0.4's +41 is ~8-11%. By the repo's screening rule (points-per-trade must be of the order of decay
plus spread) none of the v5.1 variants is a viable option-buying strategy; v0.4 is marginal.

## Answer to "make necessary adjustments to get better results"
The adjustments were made, pre-registered and tested: 7 ablations of the shipped file and 12 silver-recipe combinations.
The one that helps is dropping the ADX gate (gross +3,909 -> +5,464). It does not produce a profitable strategy after
costs, the walk-forward says it will not persist, and the breakout idea itself makes BankNifty worse. **BankNifty v0.4 remains
the best BankNifty strategy on every basis measured: highest points per trade, positive after costs, PF 1.33 net.**
Do not deploy v5.1 on BankNifty.
Running gate total: 0 of 4,734.
