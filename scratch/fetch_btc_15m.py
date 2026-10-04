import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scratch.fetch_btc_perp import fetch_klines, OUT_DIR
start_ms = int(time.mktime(time.strptime("2019-09-08", "%Y-%m-%d"))) * 1000
end_ms = int(time.time() * 1000)
kl = fetch_klines("BTCUSDT", "15m", start_ms, end_ms)
with open(os.path.join(OUT_DIR, "btcusdt_perp_15m.json"), "w") as f:
    json.dump(kl, f)
print("saved", len(kl))
