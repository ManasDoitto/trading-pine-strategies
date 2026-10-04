import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scratch.fetch_btc_perp import fetch_klines, fetch_funding, OUT_DIR
end_ms = int(time.time()*1000)
for sym, start in [("ETHUSDT","2019-11-01"),("SOLUSDT","2020-09-15")]:
    s = int(time.mktime(time.strptime(start,"%Y-%m-%d")))*1000
    kl = fetch_klines(sym, "1h", s, end_ms)
    json.dump(kl, open(os.path.join(OUT_DIR, f"{sym.lower()}_perp_1h.json"),"w"))
    fr = fetch_funding(sym, s, end_ms)
    json.dump(fr, open(os.path.join(OUT_DIR, f"{sym.lower()}_funding.json"),"w"))
    print(sym, len(kl), "bars", len(fr), "funding rows")
