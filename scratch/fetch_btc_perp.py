"""Fetch BTCUSDT perpetual futures history (klines + funding rate) from Binance's public
API, as the data source for a BTC perpetual strategy research backtest.

Why Binance and not Delta Exchange directly: Binance's BTCUSDT perp is the deepest/most
liquid BTC perp market in the world and has the longest clean public history (since
2019-09); price action across all major BTC perps (Delta, Binance, Bybit, OKX, etc.)
tracks within basis points of each other because of cross-exchange arbitrage, so it's a
sound proxy for price/trend behavior. Funding RATE LEVELS can differ exchange to
exchange (different funding formulas / open interest composition), so funding-based
results here are directional evidence about "is crowd positioning informative", not a
claim that Delta's funding numbers are identical to Binance's -- flagged in the writeup.
"""
import json
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "research_data", "crypto")
os.makedirs(OUT_DIR, exist_ok=True)

BASE = "https://fapi.binance.com"


def get(path, params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}{path}?{qs}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f"  retry {attempt} after error: {e}")
            time.sleep(2)
    raise RuntimeError(f"failed: {url}")


def fetch_klines(symbol, interval, start_ms, end_ms):
    out = []
    cur = start_ms
    while cur < end_ms:
        batch = get("/fapi/v1/klines", {
            "symbol": symbol, "interval": interval, "startTime": cur, "endTime": end_ms, "limit": 1500,
        })
        if not batch:
            break
        out.extend(batch)
        last_open = batch[-1][0]
        if last_open <= cur:
            break
        cur = last_open + 1
        print(f"  klines: {len(out)} bars, up to {time.strftime('%Y-%m-%d', time.gmtime(last_open/1000))}")
        time.sleep(0.25)
    return out


def fetch_funding(symbol, start_ms, end_ms):
    out = []
    cur = start_ms
    while cur < end_ms:
        batch = get("/fapi/v1/fundingRate", {
            "symbol": symbol, "startTime": cur, "endTime": end_ms, "limit": 1000,
        })
        if not batch:
            break
        out.extend(batch)
        last_t = batch[-1]["fundingTime"]
        if last_t <= cur:
            break
        cur = last_t + 1
        print(f"  funding: {len(out)} rows, up to {time.strftime('%Y-%m-%d', time.gmtime(last_t/1000))}")
        time.sleep(0.25)
    return out


def main():
    symbol = "BTCUSDT"
    start_ms = int(time.mktime(time.strptime("2019-09-08", "%Y-%m-%d"))) * 1000
    end_ms = int(time.time() * 1000)

    print("fetching 4h klines...")
    kl = fetch_klines(symbol, "4h", start_ms, end_ms)
    with open(os.path.join(OUT_DIR, "btcusdt_perp_4h.json"), "w") as f:
        json.dump(kl, f)
    print(f"saved {len(kl)} 4h bars")

    print("fetching 1d klines...")
    kld = fetch_klines(symbol, "1d", start_ms, end_ms)
    with open(os.path.join(OUT_DIR, "btcusdt_perp_1d.json"), "w") as f:
        json.dump(kld, f)
    print(f"saved {len(kld)} 1d bars")

    print("fetching funding rate history...")
    fr = fetch_funding(symbol, start_ms, end_ms)
    with open(os.path.join(OUT_DIR, "btcusdt_funding.json"), "w") as f:
        json.dump(fr, f)
    print(f"saved {len(fr)} funding rows")


if __name__ == "__main__":
    main()
