---
name: day_trading_system
description: Provides the systematic day trading rules, entry models, and Valid Range definitions extracted from the user's trading video notes. Use this when analyzing price action, reviewing trade journals, or writing algorithmic trading scripts (e.g., PineScript).
---

# Day Trading System Rules

When the user asks you to analyze trades, review backtesting logs, or build trading scripts based on their "day trading system", adhere to these explicit, systematic rules. Do NOT inject generic trading knowledge (like standard trendlines or moving averages) unless requested.

## 1. Market Structure & Valid Ranges
Structure is defined purely by **Valid Ranges**. Never guess if a swing is valid.
A structural leg (swing high/low) is only valid if it contains:
1. **Opposite Candle (OC):** A candle whose body closes in the opposite direction of the trend (e.g., a bearish body in an uptrend). Wicks do not matter. Dojis do not count.
2. **Pullback Candle (PBC):** A candle whose wick does not break the extreme (highest high/lowest low) of the current push. 
*A single candle can be both the OC and the PBC.*

### Key Terminology:
- **Market Structure Shift (MSS):** First failure to continue trend.
- **Trend Change (TC):** A confirmed break (candle body closure) of the last *Valid Range* protective swing point.
- **Structure Break (SB) / BOS:** Continuation of the trend following a TC.
- **Strong Structure:** A swing point that caused an SB. Trade *away* from this.
- **Weak Structure:** A swing point that failed to break structure. Target this.

## 2. Liquidity & PD Ranges
- **Premium/Discount (PD):** Drawn on the current Valid Range (Fib 0 to 1). Look for buys in Discount (<0.5) and sells in Premium (>0.5).
- **Liquidity Targets:** Singular Highs/Lows and Equal Highs/Lows (EQH/EQL).
- **Liquidity Grab (Sweep):** A break of a key level by a wick, followed by a failure to close beyond it.

## 3. Top-Down Analysis
1. **HTF (Higher Time Frame):** Determine directional bias using Valid Ranges and draw the HTF PD array. Identify HTF Supply/Demand zones.
2. **MTF (Middle Time Frame):** Refine HTF zones and track MTF structure alignment.
3. **LTF (Lower Time Frame):** Execution timeframe (1m, 3m, 5m).

## 4. Precision Entry Model (The Core Setup)
When evaluating a potential trade or coding an entry condition, ensure these 4 steps occur in order:
1. **Zone Mitigation:** Price must tap into an HTF/MTF Supply (Premium) or Demand (Discount) zone.
2. **Liquidity Grab:** Inside or near the zone, price must sweep a local high/low (wick break, no body close).
3. **LTF Trend Change (TC):** Following the sweep, the LTF structure must shift by breaking its last Valid Range.
4. **Entry:** Place limit order in the Discount/Premium of the *new* LTF leg formed by the TC. Stop loss goes behind the Liquidity Grab extreme.

## 5. Backtesting Evaluation
When reviewing the user's journal or backtesting results, evaluate based on:
- Was the entry model strictly followed? (No hindsight bias).
- Were the 10 data points tracked? (Date, Time, Asset, Direction, Entry Model, Setup Type, R:R, Result, Screenshots, Notes).
- Does the data support a positive expectancy (>40% win rate with >2R avg)?
- Identify patterns (e.g., "You lose 80% of trades on Fridays. Rule: Stop trading Fridays.")
