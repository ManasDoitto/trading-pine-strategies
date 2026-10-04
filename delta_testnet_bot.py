import ccxt
import pandas as pd
import numpy as np
import requests
import time
import os
import sqlite3
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
# 1. Delta Testnet API Keys
API_KEY = '4OprX3nM9lu5njD15Fpf4uCEF6t0Nd'
API_SECRET = '8lXx7EJTJzfoTKoUs6ub8C88f6wXlNHzVhVavPnfRDp11JPkq6KD5CNVkq6s'

from dotenv import load_dotenv
load_dotenv()

# 2. Telegram Bot (Get from @BotFather on Telegram)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 3. Strategy Parameters
RISK_PERCENT = 0.02  # 2% Risk per trade
SYMBOLS = ['BTC/USD:USD', 'ETH/USD:USD', 'XAUT/USD:USD']
TIMEFRAME = '1h'
EMA_PERIOD = 200
DONCHIAN_PERIOD = 200
ATR_PERIOD = 14
ATR_MULTIPLIER = 5

DB_NAME = 'testnet_trades.db'

# ==========================================
# INITIALIZATION
# ==========================================
exchange = ccxt.delta({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})
# Point to Delta Exchange India Testnet (Required for Indian accounts)
exchange.urls['api'] = {
    'public': 'https://cdn-ind.testnet.deltaex.org',
    'private': 'https://cdn-ind.testnet.deltaex.org',
}

def send_telegram(message):
    """Sends a notification to your phone."""
    print(f"[LOG] {message.encode('ascii', 'ignore').decode()}")
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

def init_db():
    """Create local SQLite journal."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (timestamp TEXT, symbol TEXT, action TEXT, price REAL, size REAL, pnl REAL)''')
    conn.commit()
    conn.close()

def log_trade(symbol, action, price, size, pnl=0):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO trades VALUES (?,?,?,?,?,?)", 
              (datetime.utcnow().isoformat(), symbol, action, price, size, pnl))
    conn.commit()
    conn.close()

# ==========================================
# STRATEGY LOGIC
# ==========================================
def get_data_and_indicators(symbol):
    """Fetches last 250 hours of data and computes indicators."""
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=250)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['ema200'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
        df['dc_upper'] = df['high'].rolling(DONCHIAN_PERIOD).max().shift(1)
        df['dc_lower'] = df['low'].rolling(DONCHIAN_PERIOD).min().shift(1)
        
        df['prev_close'] = df['close'].shift(1)
        df['tr'] = pd.concat([df['high']-df['low'], (df['high']-df['prev_close']).abs(), (df['low']-df['prev_close']).abs()], axis=1).max(axis=1)
        df['atr'] = df['tr'].ewm(span=ATR_PERIOD, adjust=False).mean()
        
        return df.iloc[-1] # Return the most recently closed candle
    except Exception as e:
        send_telegram(f"⚠️ Error fetching data for {symbol}: {str(e)}")
        return None

def run_bot():
    send_telegram("⚙️ <i>Fat Tail Catcher awakening for hourly check...</i>")
    
    try:
        balance = exchange.fetch_balance()
        equity = balance['USDT']['total'] if 'USDT' in balance else 0
        positions = exchange.fetch_positions()
    except Exception as e:
        send_telegram(f"❌ Critical API Error (fetch_balance): {str(e)}")
        return

    active_symbols = [p['symbol'] for p in positions if float(p['contracts']) > 0]

    for symbol in SYMBOLS:
        row = get_data_and_indicators(symbol)
        if row is None:
            continue
            
        current_price = row['close']
        atr = row['atr']
        stop_dist = atr * ATR_MULTIPLIER
        
        # 1. CHECK FOR OPEN POSITIONS
        if symbol in active_symbols:
            pos = next((p for p in positions if p['symbol'] == symbol), None)
            size = float(pos['contracts'])
            
            new_trailing_stop = current_price - stop_dist
            
            # Simplified Logic: If price broke the 200-Low, market close it.
            if current_price < row['dc_lower']:
                try:
                    exchange.create_market_sell_order(symbol, size)
                    log_trade(symbol, "EXIT", current_price, size)
                    send_telegram(f"🔴 <b>EXITED LONG:</b> {symbol}\nReason: 200-Low Broken\nExit Price: ${current_price:.2f}")
                except Exception as e:
                    send_telegram(f"❌ Error closing {symbol}: {str(e)}")
            
            # (Note: In production, we would query active stop-loss orders and modify them via exchange API if new_trailing_stop is higher)
            # send_telegram(f"🔒 {symbol}: Trailing stop mathematically raised to ${new_trailing_stop:.2f}")

        # 2. CHECK FOR ENTRY
        else:
            if current_price > row['ema200'] and current_price > row['dc_upper']:
                risk_amt = equity * RISK_PERCENT
                qty = risk_amt / stop_dist
                
                try:
                    # Place Market Buy
                    order = exchange.create_market_buy_order(symbol, qty)
                    # Place Stop Loss
                    stop_price = current_price - stop_dist
                    params = {'stopPrice': stop_price, 'reduceOnly': True}
                    exchange.create_order(symbol, 'limit', 'sell', qty, stop_price, params)
                    
                    log_trade(symbol, "ENTRY", current_price, qty)
                    send_telegram(f"🟢 <b>ENTERED LONG:</b> {symbol}\nPrice: ${current_price:.2f}\nStop Loss: ${stop_price:.2f}\nRisk: ${risk_amt:.2f}")
                except Exception as e:
                    send_telegram(f"❌ Error entering {symbol}: {str(e)}")

    print("[LOG] Bot successfully finished evaluating all markets. No new trade conditions met right now.")

if __name__ == "__main__":
    init_db()
    run_bot()
