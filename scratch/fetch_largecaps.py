import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scratch.fetch_btc_perp import fetch_klines, fetch_funding, OUT_DIR
end_ms = int(time.time()*1000); s = int(time.mktime(time.strptime("2019-09-01","%Y-%m-%d")))*1000
for sym in ["BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","LTCUSDT","DOTUSDT","BCHUSDT","TRXUSDT"]:
    p = os.path.join(OUT_DIR, f"{sym.lower()}_perp_1h.json")
    if os.path.exists(p): print("skip", sym); continue
    kl = fetch_klines(sym, "1h", s, end_ms); fr = fetch_funding(sym, s, end_ms)
    json.dump(fr, open(os.path.join(OUT_DIR, f"{sym.lower()}_funding.json"),"w"))
    json.dump(kl, open(p,"w")); print("DONE", sym, len(kl), len(fr), flush=True)
