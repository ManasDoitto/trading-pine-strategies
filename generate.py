import os

strategies = {
    'strategy_4.pine': '''//@version=6
strategy("Strat 4: Volume Delta Exhaustion", overlay=false, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
length = input.int(20, "Volume MA Length")
vol_ma = ta.sma(volume, length)

is_exhaustion_bull = close > open and volume > vol_ma * 2 and close < high - (high-low)*0.5
is_exhaustion_bear = close < open and volume > vol_ma * 2 and close > low + (high-low)*0.5

if (is_exhaustion_bull)
    strategy.entry("Short", strategy.short)
    strategy.exit("Exit Short", "Short", stop=high, limit=close - (high-low)*2)

if (is_exhaustion_bear)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=low, limit=close + (high-low)*2)
''',
    'strategy_5.pine': '''//@version=6
strategy("Strat 5: VWAP Mean Reversion", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
vwap = ta.vwap(hlc3)
stdev = ta.stdev(close, 20)
upper_band = vwap + stdev * 2.0
lower_band = vwap - stdev * 2.0

atr = ta.atr(14)
if (low < lower_band and close > lower_band)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=low - atr, limit=vwap)

if (high > upper_band and close < upper_band)
    strategy.entry("Short", strategy.short)
    strategy.exit("Exit Short", "Short", stop=high + atr, limit=vwap)
''',
    'strategy_6.pine': '''//@version=6
strategy("Strat 6: VCP Breakout", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
vol_ma = ta.sma(volume, 20)
vcp = ta.highest(high, 50) - ta.lowest(low, 50)
vcp_narrow = (high - low) < (vcp * 0.2) and volume < vol_ma * 0.5
breakout = close > ta.highest(high[1], 20) and volume > vol_ma * 1.5

atr = ta.atr(14)
if (vcp_narrow[1] and breakout)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*2, limit=close + atr*4)
''',
    'strategy_7.pine': '''//@version=6
strategy("Strat 7: ADX Trend Continuation", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
[diplus, diminus, adx] = ta.dmi(14, 14)
ema = ta.ema(close, 50)

long_cond = adx > 25 and diplus > diminus and close > ema and close[1] < ema[1]
short_cond = adx > 25 and diminus > diplus and close < ema and close[1] > ema[1]

atr = ta.atr(14)
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*1.5, limit=close + atr*3)

if (short_cond)
    strategy.entry("Short", strategy.short)
    strategy.exit("Exit Short", "Short", stop=close + atr*1.5, limit=close - atr*3)
''',
    'strategy_8.pine': '''//@version=6
strategy("Strat 8: Intraday Seasonality Reversal", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
time_to_fade = not na(time(timeframe.period, "1400-1415"))
atr = ta.atr(14)

if (time_to_fade and close > ta.ema(close, 200))
    strategy.entry("Short", strategy.short)
    strategy.exit("Exit Short", "Short", stop=close + atr*1.5, limit=close - atr*3)

if (time_to_fade and close < ta.ema(close, 200))
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*1.5, limit=close + atr*3)
''',
    'strategy_9.pine': '''//@version=6
strategy("Strat 9: ATR Trailing Stop Momentum", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
atr = ta.atr(14)
mult = 3.0
var float trailing_stop = na

if (close > ta.ema(close, 50))
    trailing_stop := math.max(nz(trailing_stop, close - atr * mult), close - atr * mult)
    if (close > trailing_stop)
        strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=trailing_stop)

if (close < ta.ema(close, 50))
    trailing_stop := math.min(nz(trailing_stop, close + atr * mult), close + atr * mult)
    if (close < trailing_stop)
        strategy.entry("Short", strategy.short)
    strategy.exit("Exit Short", "Short", stop=trailing_stop)
''',
    'strategy_10.pine': '''//@version=6
strategy("Strat 10: Failed Auction IB Fade", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
ib_time = input("0915-1015", "Initial Balance Time")
in_ib = not na(time(timeframe.period, ib_time))

var float ib_high = na
var float ib_low = na

if (in_ib and not in_ib[1])
    ib_high := high
    ib_low := low
else if (in_ib)
    ib_high := math.max(ib_high, high)
    ib_low := math.min(ib_low, low)

atr = ta.atr(14)
failed_break_high = high > ib_high and close < ib_high
failed_break_low = low < ib_low and close > ib_low

if (failed_break_high and not in_ib)
    strategy.entry("Short", strategy.short)
    strategy.exit("Exit Short", "Short", stop=high + atr, limit=close - atr*3)

if (failed_break_low and not in_ib)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=low - atr, limit=close + atr*3)
''',
    'strategy_11.pine': '''//@version=6
strategy("Strat 11: Order Block Retest", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
atr = ta.atr(14)
bull_ob = close > open and close[1] < open[1] and volume > ta.sma(volume, 20)*1.5
var float ob_low = na
if (bull_ob)
    ob_low := low[1]

retest = low < ob_low and close > ob_low
if (retest)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=low - atr, limit=close + atr*3)
''',
    'strategy_12.pine': '''//@version=6
strategy("Strat 12: MACD Divergence", overlay=false, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
[macdLine, signalLine, histLine] = ta.macd(close, 12, 26, 9)
atr = ta.atr(14)

bull_div = low < ta.lowest(low[1], 20) and macdLine > ta.lowest(macdLine[1], 20)
if (bull_div)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=low - atr, limit=close + atr*3)
''',
    'strategy_13.pine': '''//@version=6
strategy("Strat 13: RSI + EMA Cross", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
rsi = ta.rsi(close, 14)
ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)
atr = ta.atr(14)

long_cond = ta.crossover(ema_fast, ema_slow) and rsi < 40
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*1.5, limit=close + atr*3)
''',
    'strategy_14.pine': '''//@version=6
strategy("Strat 14: Bollinger Band Squeeze", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
length = 20
mult = 2.0
basis = ta.sma(close, length)
dev = mult * ta.stdev(close, length)
upper = basis + dev
lower = basis - dev
bb_width = (upper - lower) / basis
squeeze = bb_width < ta.lowest(bb_width[1], 50)
atr = ta.atr(14)

long_cond = squeeze[1] and close > upper
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*2, limit=close + atr*4)
''',
    'strategy_15.pine': '''//@version=6
strategy("Strat 15: SMI Reversal", overlay=false, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
q = 13
r = 25
s = 2
signalLength = 5
hh = ta.highest(q)
ll = ta.lowest(q)
center = (hh + ll) / 2
diff = hh - ll
num = ta.ema(ta.ema(close - center, r), s)
den = ta.ema(ta.ema(diff, r), s) / 2
smi = (num / den) * 100
signal = ta.ema(smi, signalLength)
atr = ta.atr(14)

long_cond = ta.crossover(smi, signal) and smi < -40
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*1.5, limit=close + atr*3)
''',
    'strategy_16.pine': '''//@version=6
strategy("Strat 16: Ichimoku Cloud Breakout", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
conversionPeriods = 9
basePeriods = 26
laggingSpan2Periods = 52
displacement = 26
donchian(len) => math.avg(ta.lowest(len), ta.highest(len))
conversionLine = donchian(conversionPeriods)
baseLine = donchian(basePeriods)
leadLine1 = math.avg(conversionLine, baseLine)
leadLine2 = donchian(laggingSpan2Periods)
atr = ta.atr(14)

long_cond = close > leadLine1[displacement-1] and close > leadLine2[displacement-1] and close[1] <= math.max(leadLine1[displacement-1], leadLine2[displacement-1])
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*2, limit=close + atr*4)
''',
    'strategy_17.pine': '''//@version=6
strategy("Strat 17: Fib Retracement Pin Bar", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
high_swing = ta.highest(high, 50)
low_swing = ta.lowest(low, 50)
fib_618 = high_swing - (high_swing - low_swing) * 0.618
atr = ta.atr(14)

pin_bar_bull = (close - low) > (high - low) * 0.66 and (open - low) > (high - low) * 0.66
if (low < fib_618 and pin_bar_bull)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=low - atr, limit=close + atr*3)
''',
    'strategy_18.pine': '''//@version=6
strategy("Strat 18: Donchian Channel Trend", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
length = 20
upper = ta.highest(high, length)
lower = ta.lowest(low, length)
atr = ta.atr(14)

long_cond = close == upper
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*2, limit=close + atr*4)
''',
    'strategy_19.pine': '''//@version=6
strategy("Strat 19: Keltner Mean Reversion", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
length = 20
mult = 1.5
basis = ta.ema(close, length)
range_1 = ta.atr(10)
upper = basis + range_1 * mult
lower = basis - range_1 * mult
atr = ta.atr(14)

long_cond = low < lower and close > lower
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=low - atr, limit=basis)
''',
    'strategy_20.pine': '''//@version=6
strategy("Strat 20: Parabolic SAR Reversal", overlay=true, initial_capital=100000, default_qty_type=strategy.percent_of_equity, default_qty_value=10)
start = 0.02
inc = 0.02
max = 0.2
sar = ta.sar(start, inc, max)
atr = ta.atr(14)

long_cond = ta.crossover(close, sar)
if (long_cond)
    strategy.entry("Long", strategy.long)
    strategy.exit("Exit Long", "Long", stop=close - atr*1.5, limit=close + atr*3)
'''
}

out_dir = 'D:/Trading code-Claude/strategy_audit_2026_09/new_strategies'
os.makedirs(out_dir, exist_ok=True)
for name, code in strategies.items():
    with open(os.path.join(out_dir, name), 'w', encoding='utf-8') as f:
        f.write(code)
print('Generated 17 strategy files.')
