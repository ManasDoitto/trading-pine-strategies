# CrudeOil v5.1 flip+breakout: tested, adjusted, does not beat crude #1 (run 2026-09-26)

Pre-registration: `pre_registration_crude_breakout_2026_09_26.md`. Code: `crude_breakout_test.py`. Raw: `research_data/crude_breakout.csv`.
MCX:CRUDEOIL1! 5m, 2024-03-25 -> 2026-09-24 (30 months), 1 lot, points, six calendar windows, 15 pre-registered trials.
Correction made before interpreting: the first run of the "crude #1 base" wrongly applied the SHA-stability filter to flip entries
(738 trades); it was fixed to match crude #1 exactly and the ancestor now reproduces the known result to the trade (785 trades, PF 1.263, +5,614).

## Verdict: 0 of 15 pass. Nothing beats crude working_strategies #1, and the header claim does not reproduce.

## The shipped file and its ablations
| trial | trades | /mo | PF | net pts | maxDD | pts/trade | after 0.02%/side |
|---|---|---|---|---|---|---|---|
| **S0: v5.1 as shipped** | 1,343 | 44.8 | 1.067 | +1,566 | 2,043 | +1.2 | PF 0.924, **-1,942** |
| S0 - hold overnight | 1,225 | 40.8 | 1.053 | +1,611 | 3,648 | +1.3 | -1,577 |
| S0 - RR 4.0 | 1,291 | 43.0 | 1.074 | +1,698 | 2,223 | +1.3 | -1,665 |
| **S0 - no EMA200** | 1,668 | 55.6 | **1.133** | **+3,820** | 2,450 | +2.3 | PF 0.983, **-542** |
| S0 - no pullback gate | 1,678 | 55.9 | 1.061 | +1,923 | 1,346 | +1.1 | -2,448 |
| S0 - no ADX gate | 1,508 | 50.3 | 1.076 | +1,985 | 2,332 | +1.3 | -1,946 |
| S0 - no daily limit | 1,343 | 44.8 | 1.067 | +1,566 | 2,043 | +1.2 | identical to S0 |
The shipped file trades 45 times a month for about +1.2 points a trade - less than the ~2.6-point round-trip cost, so it loses
after costs. The daily limit (300 pts) is inert on crude: removing it changes nothing. The only helpful ablation is dropping EMA200
(+1,566 -> +3,820), and it is still negative after costs.

## The breakout on crude #1's own base
| entry \ RR | RR 3.0 | RR 4.0 |
|---|---|---|
| **flip only = crude #1** | 856 tr, PF 1.205, **+4,481**, net of costs +2,258 | **785 tr, PF 1.263, +5,614**, dd 2,176, net of costs **+3,577** |
| flip OR breakout(3) | 2,091 tr, PF 1.091, +5,028, costs -464 | 1,747 tr, PF 1.101, +5,034, dd 3,162, costs +444 |
| flip OR breakout(5) | 1,879 tr, PF 1.063, +3,194, costs -1,725 | 1,607 tr, PF 1.120, +5,547, dd 3,334, costs +1,336 |
| flip OR breakout(10) | 1,629 tr, PF 1.047, +2,103, costs -2,143 | 1,414 tr, PF 1.126, +5,113, dd 3,336, costs +1,437 |
The breakout multiplies trades 1.8-2.7x (26 -> 47-70/mo) but cuts points per trade from +7.2 to +2.4-3.6 and lowers PF from
1.263 to 1.10-1.13. Best case, bo(5) at RR 4.0, earns +5,547 - level with crude #1's +5,614 on 2x the trades, with ~50%
more drawdown, and **+1,336 after costs against crude #1's +3,577**. The extra trades cost ~2.6 points each and earn less than that.
This is the opposite of silver, where a per-trade edge of ~+370 points swamped the cost.

## Header claim: not reproduced
Header: "71 trades, PF 1.58, net +2,721 (ADX 15, SHA=2, RR 3.0, BO5)". On the current 3.2-month Dhan cache the shipped config gives
**80 trades, PF 1.094, +154.8 gross** (PF 0.941 / -108.6 net); shaMinHold 2 and 3 are identical in that sample. On the full 30 months
it is 1,343 trades, PF 1.067, +1,566. The claim matches neither. (The cache was rewritten this morning, so what it held when the
header was written cannot be checked.) Same pattern as the v5.0 claims and the silver v5.1 header.

## Walk-forward: tuning loses again
Picking the best of the 15 on past windows and trading the next earned **+1,875 over W2-W6, versus +3,837 for simply holding
crude #1** (and +1,298 for the shipped file). A further past-to-next measurement of the same null.

## Cost-gap check (the silver bo(3) lesson)
Gross-to-net gap is a constant **2.6 pts/trade for every trial**, so the net figures here are like-for-like; nothing is path-flattered.

## Standing context
Crude option buying was already ruled out (premium ~31x the per-trade edge; `option_premium_results_2026_09_26.md`), so this is a
futures-points question only. The crude forward test recorded in memory is not running.

## Bottom line
Crude working_strategies #1 (SHA flip + EMA9/22, RR 4.0) remains the best crude strategy on every basis measured, and the shipped v5.1
is worse than it on points, PF, drawdown and after-cost profit. The breakout idea that worked on silver does not work on crude or
BankNifty: it needs a per-trade edge large relative to the cost, and only silver has one. Do not deploy crude v5.1. Running gate total: 0 of 4,749.
