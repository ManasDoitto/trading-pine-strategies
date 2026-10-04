import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scratch.fetch_btc_perp import fetch_klines, OUT_DIR
end_ms = int(time.time()*1000); s = int(time.mktime(time.strptime("2020-01-01","%Y-%m-%d")))*1000
for sym in ["BTCUSDT","ETHUSDT"]:
    kl = fetch_klines(sym, "5m", s, end_ms)
    json.dump(kl, open(os.path.join(OUT_DIR, f"{sym.lower()}_perp_5m.json"),"w")); print("DONE", sym, len(kl), flush=True)
