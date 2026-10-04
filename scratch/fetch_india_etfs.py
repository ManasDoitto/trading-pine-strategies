import json, subprocess, pandas as pd, urllib.parse
SYMS = ["NIFTYBEES.NS","BANKBEES.NS","JUNIORBEES.NS","GOLDBEES.NS","SILVERBEES.NS","MON100.NS","LIQUIDBEES.NS"]
for s in SYMS:
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?interval=1d&period1=946684800&period2=1791100000&events=div%2Csplit"
    out = subprocess.run(["curl","-s","-m","60","-A","Mozilla/5.0",u],capture_output=True,text=True).stdout
    try:
        r = json.loads(out)["chart"]["result"][0]; q = r["indicators"]["quote"][0]
        adj = r["indicators"].get("adjclose",[{}])[0].get("adjclose")
        d = pd.DataFrame({"time":pd.to_datetime(r["timestamp"],unit="s").normalize(),"open":q["open"],"high":q["high"],"low":q["low"],"close":q["close"],"volume":q["volume"]})
        d["adj"] = adj if adj else d["close"]; d = d.dropna(subset=["close","open","high","low"]).drop_duplicates("time")
        f = d["adj"]/d["close"]
        for c in ("open","high","low","close"): d[c] = d[c]*f
        d[["time","open","high","low","close","volume"]].to_pickle(f"research_data/trend/in_{s.split('.')[0].lower()}.pkl")
        raw = d["close"]/f
        print(f"{s:16} {len(d):5} {d.time.iloc[0].date()}..{d.time.iloc[-1].date()}  adj CAGR {(d.close.iloc[-1]/d.close.iloc[0])**(365.25/(d.time.iloc[-1]-d.time.iloc[0]).days)-1:+.1%}  median daily volume {d.volume.median():,.0f}")
    except Exception as e: print(s,"FAILED",repr(e)[:80], out[:100])
