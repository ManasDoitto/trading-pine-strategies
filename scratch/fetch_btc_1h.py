import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scratch.fetch_btc_perp import fetch_klines, OUT_DIR
import json, time

symbol = "BTCUSDT"
start_ms = int(time.mktime(time.strptime("2019-09-08", "%Y-%m-%d"))) * 1000
end_ms = int(time.time() * 1000)
print("fetching 1h klines...")
kl = fetch_klines(symbol, "1h", start_ms, end_ms)
with open(os.path.join(OUT_DIR, "btcusdt_perp_1h.json"), "w") as f:
    json.dump(kl, f)
print(f"saved {len(kl)} 1h bars")
