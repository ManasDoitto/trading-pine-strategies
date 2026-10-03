# TradingView Deployment Guide — v5.0 SHA-ADX Hybrid

## Where the Pine scripts are

```
working_strategies/
├── v5.0_SHA_ADX_hybrid.pine.txt                    (unified script, all params adjustable)
├── CrudeOil/4_v5.0_SHA_ADX_hybrid.pine.txt         ← CrudeOil v5.0 (flip entry, highest PF)
├── CrudeOil/5_v5.1_flip_breakout.pine.txt          ← CrudeOil v5.1 (flip + Donchian, high-freq)
├── BankNifty/4_v5.0_SHA_ADX_hybrid.pine.txt        ← BankNifty v5.0 (flip entry, highest PF)
├── BankNifty/5_v5.1_flip_breakout.pine.txt         ← BankNifty v5.1 (experimental — not recommended)
├── Silver/4_v5.0_SHA_ADX_hybrid.pine.txt           ← Silver v5.0 (flip entry, highest PF, best L/W)
└── Silver/5_v5.1_flip_breakout.pine.txt            ← Silver v5.1 (flip + Donchian, high-freq, L/W<0.40)
```

## How to test in TradingView

1. **Open the chart**: Navigate to the instrument
   - CrudeOil → `MCX:CRUDEOIL1!`
   - BankNifty → `NSE:BANKNIFTY1!`
   - Silver → `MCX:SILVER1!`

2. **Open Pine Editor**: Bottom panel of the TradingView window (or `Alt+E`)

3. **Paste the script**: Open the `4_v5.0_SHA_ADX_hybrid.pine.txt` file for your instrument, copy its entire contents, and paste into the Pine Editor

4. **Add to chart**: Click the "Add to chart" button (or `Ctrl+Enter`)

5. **Enable strategy**: TradingView will prompt you to "Enable" the strategy — click **Yes**

6. **Review results**: The strategy tester panel (bottom of chart) shows:
   - Performance summary (net profit, PF, Sharpe, max drawdown)
   - List of trades with entry/exit prices
   - Equity curve chart

7. **Adjust parameters**: Click the gear icon ⚙️ next to the strategy name in the chart legend → "Settings" → "Inputs" tab to tweak any parameter

## Recommended settings per instrument

| Parameter | CrudeOil | BankNifty | Silver |
|---|---|---|---|
| 15m ADX min | 30 | 25 | 30 |
| Volatility regime filter | Off | **On** | Off |
| EMA9 proximity (x ATR) | 1.0 | 0.5 | 0.5 |
| R:R target | 3.0 | 3.5 | 4.0 |
| SL min (x ATR) | 1.5 | 1.5 | **2.5** |
| SL max (x ATR) | 3.0 | 3.0 | **5.0** |
| Daily loss limit (pts) | 0 (off) | 0 (off) | **300** |
| Session | 09:15–23:30 | 09:30–15:00 | 09:15–23:30 |
| Force-flat | 22:45–23:30 | 14:45–15:00 | 22:45–23:30 |

## What's new vs the old strategies

The v5.0 scripts add **4 new filters** that the old scripts did not have:

1. **15m ADX Gate**: Only enter when the previous *completed* 15-minute ADX(14) exceeds a threshold. This filters out low-trend-strength entries. (CrudeOil: 30, BankNifty: 25, Silver: 30)

2. **Volatility Regime Filter** (BankNifty only): Only enter when current ATR exceeds its 80-bar SMA. BankNifty's post-Sep-2025 regime is choppy; this gate is essential there.

3. **SHA Stability Filter**: A SHA flip only counts if the previous SHA direction held for ≥3 bars. Prevents trading rapidly-flipping noise.

4. **EMA9 Pullback Proximity**: Only enter when price is within N×ATR of the EMA9. Catches the "first pull" rather than chasing after the move has run.

## Notes

- The scripts use **SHA flip entry** (not BankNifty's old pullback entry) — walk-forward testing showed SHA-flip + the new filters beat the old entry type on all instruments
- Set `initial_capital` to match your account size (defaults: CrudeOil 100k, BankNifty 500k, Silver 100k INR)
- Commission is set to 0.02%/side + 5pt slippage (BankNifty); adjust in the script header if your broker differs
- For Silver, the daily loss limit is in **points** (300 pts = ~Rs 9,000 at lot size 30) — this matches the Silver v4.0 breaker that cut max drawdown by 85% on backtests
