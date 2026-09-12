# Swing-POC pullback v1.0 (13 Sep 2026)

Script: `swing-POC pullback v1.0 (fixed-range volume profile on the latest swing leg).pine.txt`.

## The user's process, and how it was made mechanical

| User's step | Rule in the script |
|---|---|
| Is the market trending up or down? | The last two confirmed 5-bar swing pivots make higher highs and higher lows (up), or lower highs and lower lows (down). |
| Take the latest swing low to swing high | The up-leg from the most recent swing low to the swing high after it; the down-leg is the mirror. |
| Fixed-range volume profile, point of control | 30-row volume profile over the bars of that leg. The POC is the row with the most volume. |
| Wait for the pullback to the POC, then a clear reaction | After price trades into the POC, enter on the first candle that closes back beyond it in the trend direction with a body in that direction, within 12 bars of the touch. Never on the touch alone. |
| Stop below the deepest wick | One tick beyond the most extreme wick of the pullback. |
| Target 1:3, breakeven at 1:1.5 | The target is 3R. The stop moves to breakeven once price reaches 1.5R. One trade per leg. |

The setup is cancelled if price closes beyond the leg's origin, or if it never reaches the POC within 48 bars. There is also an entry session filter (09:30-23:00) and a flat before the close (NSE 15:15, MCX 23:15).

## Results

Costs were 0.02% per side. Figures are points per lot, and the windows are the same non-overlapping ones used for every audit row.

| Instrument | Windows | Trades/mo | Win% | PF | Net pts | Max DD | Avg win / loss | + windows |
|---|---|---|---|---|---|---|---|---|
| Crude 5m (MCX:CRUDEOIL1!) | 11 (29.7 mo) | 48.7 | 24.2 | 0.79 | −5,000 | 5,334 | 55.2 / −22.2 | 1/11 |
| BankNifty 5m (NSE:BANKNIFTY1!) | 5 (30.2 mo) | 22.7 | 29.1 | 0.71 | −14,345 | 14,556 | 176.0 / −101.8 | 0/5 |
| Nifty 5m (NSE:NIFTY1!) | 5 (30.2 mo) | 22.3 | 26.6 | 0.53 | −9,603 | 9,866 | 59.9 / −41.1 | 0/5 |

Nifty was run on the futures contract because the spot index (NSE:NIFTY) has no volume, so a volume profile cannot be built on it.

Net points by window, oldest to newest:

| Instrument | Windows (oldest to newest) |
|---|---|
| Crude | −377 −52 −272 −772 −276 −760 −391 −840 −1121 +25 −165 |
| BankNifty | −6056 −198 −1153 −3568 −3369 |
| Nifty | −1314 −1757 −1412 −591 −4530 |

## Reading

- **The setup loses on all three instruments, in 20 of 21 windows.**
- At a 1:3 target, a win rate near 25% needs the average win to be about 3 times the average loss just to break even before costs.
- The actual ratio is about 2.5x on crude, 1.7x on BankNifty and 1.5x on Nifty. The breakeven move at 1.5R turns part of the would-be winners into scratch trades, and the POC is touched and broken far more often than it holds.
- The frequency target is met: BankNifty gives 23 trades a month. But it loses in every window.
- Two rules here are one reading of discretionary wording: "clear reaction" and "trend". Stricter versions, such as bigger swings or a stronger reaction candle, might behave differently.
- They were **not** tuned here. Tuning them on the same history would only fit the past.
