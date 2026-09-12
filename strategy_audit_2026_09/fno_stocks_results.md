# Top-10 F&O stocks: the best 5m strategies, tested on each stock (13 Sep 2026)

## Which 10 stocks

The 10 stocks with the highest average daily **cash-market turnover** (close x volume) over the 20 sessions to 11 Sep 2026. The ranking was taken from 40 liquid NSE F&O stocks with a TradingView indicator.

Cash turnover stands in for F&O activity; F&O turnover itself was not available here. A one-day ranking was checked and dropped: on a single day, MARUTI and KOTAKBANK wrongly made the top 10.

| Rank | Stock | Rs crore/day |
|---|---|---|
| 1 | HDFCBANK | 1,928 |
| 2 | BSE | 1,600 |
| 3 | RELIANCE | 1,390 |
| 4 | ICICIBANK | 1,266 |
| 5 | ETERNAL | 1,178 |
| 6 | BHARTIARTL | 1,071 |
| 7 | INFY | 903 |
| 8 | SBIN | 748 |
| 9 | ADANIENT | 631 |
| 10 | TCS | 562 |

The cut-off is tight: M&M (556) and AXISBANK (556) sit just below TCS.

## How it was tested

**Strategies:**

| Strategy | What it is | Setting changed for stocks |
|---|---|---|
| BankNifty v0.4 | EMA pullback with a 15m ADX 25 gate | 50-point minimum ATR switched off |
| Crude v2.0 / v1.0-tuned | EMA 9/22 pullback, separation 0.5 | 10-point minimum ATR switched off |

Those index-point floors mean nothing on a Rs 300-3,400 stock. Every other rule is unchanged. v0.4 flattens by 15:15. v2.0 has no end-of-day exit, so some of its trades are held overnight.

**Setup:**
- NSE cash symbols on the 5m chart, 1 share, 0.02% commission per side, no slippage.
- 5 non-overlapping replay windows per stock: 21 Jan 2024 to 11 Sep 2026, 31.7 months.
- Figures are points per share. "% of price" divides the net points by the stock's close on 11 Sep 2026 so that stocks can be compared. It is approximate, because the stocks traded at different prices earlier in the period.

**Not run:**
- **v13 sweep:** its 120-point stop cap and 30-point level spacing are sized for BankNifty and would need rebuilding for stocks.
- **Swing-POC:** it lost on all three index instruments.

## BankNifty v0.4 (15m ADX gate)

| Stock | Trades/mo | Win% | PF | Net pts/share | % of price | + windows |
|---|---|---|---|---|---|---|
| BSE | 6.3 | 42.2 | 1.32 | +333 | +9.8% | 5/5 |
| ETERNAL | 6.1 | 41.1 | 1.21 | +22 | +6.7% | 4/5 |
| TCS | 7.3 | 37.8 | 1.00 | −2 | −0.1% | 3/5 |
| SBIN | 6.9 | 32.3 | 0.87 | −45 | −4.5% | 1/5 |
| ADANIENT | 5.2 | 33.5 | 0.81 | −200 | −6.5% | 2/5 |
| BHARTIARTL | 7.5 | 31.0 | 0.70 | −206 | −11.3% | 1/5 |
| RELIANCE | 8.8 | 28.7 | 0.66 | −203 | −16.1% | 0/5 |
| ICICIBANK | 8.8 | 27.2 | 0.55 | −264 | −19.1% | 0/5 |
| HDFCBANK | 8.1 | 28.7 | 0.52 | −158 | −22.2% | 0/5 |
| INFY | 9.0 | 28.9 | 0.64 | −258 | −24.8% | 1/5 |
| **Average** | 7.4 | | | | **−8.8%** | |

## Crude v2.0 (EMA 9/22 pullback)

| Stock | Trades/mo | Win% | PF | Net pts/share | % of price | + windows |
|---|---|---|---|---|---|---|
| ADANIENT | 34.5 | 39.0 | 1.09 | +612 | +20.0% | 4/5 |
| BSE | 33.0 | 39.8 | 1.09 | +615 | +18.2% | 4/5 |
| ETERNAL | 34.7 | 36.3 | 0.85 | −120 | −37.1% | 0/5 |
| SBIN | 35.2 | 34.6 | 0.79 | −423 | −42.4% | 0/5 |
| INFY | 33.0 | 35.1 | 0.83 | −596 | −57.5% | 1/5 |
| BHARTIARTL | 35.3 | 33.3 | 0.73 | −1,058 | −57.8% | 0/5 |
| HDFCBANK | 35.1 | 33.5 | 0.74 | −466 | −65.8% | 0/5 |
| TCS | 34.0 | 34.2 | 0.79 | −1,448 | −65.8% | 0/5 |
| RELIANCE | 36.1 | 33.2 | 0.72 | −839 | −66.7% | 0/5 |
| ICICIBANK | 35.3 | 29.6 | 0.61 | −1,117 | −81.0% | 0/5 |
| **Average** | 34.7 | | | | **−43.6%** | |

## Reading

- **Neither strategy carries over to large-cap stocks.** v0.4 averages −8.8% of price and v2.0 averages −43.6%.
- **v2.0 trades about 35 times a month per stock.** On slow-moving large caps its stops are small relative to the 0.02%-per-side cost, and the costs swamp the edge. 8 of the 10 stocks are negative in almost every window. With its volatility floor switched off it has no filter against quiet markets.
- **v0.4 is much more selective,** at about 7 trades a month, so it loses far less. It is still negative on 7 of the 10 stocks.
- **The only consistent positives are BSE (both strategies) and ADANIENT (v2.0).** Both stocks trended strongly over the period, BSE especially, and that flatters any trend-following pullback. This looks like the stocks' trend, not an edge that would transfer. ETERNAL under v0.4 is positive (4/5 windows) but tiny.
- **Verdict:** none of the existing strategies should be traded on these stocks as they stand. A stock version would need its own volatility filter, sized as a fraction of price, and a much lower trade frequency. That has not been built or tested here.
