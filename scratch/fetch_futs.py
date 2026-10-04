import json, subprocess, pandas as pd
for sym in ["SI=F","HG=F","CL=F","NG=F","PL=F","ES=F","ZN=F","ZC=F"]:
    out=subprocess.run(["curl","-s","-m","60","-A","Mozilla/5.0",f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&period1=946684800&period2=1791100000"],capture_output=True,text=True).stdout
    try:
        r=json.loads(out)["chart"]["result"][0]; t=pd.to_datetime(r["timestamp"],unit="s"); q=r["indicators"]["quote"][0]
        df=pd.DataFrame({"time":t,"open":q["open"],"high":q["high"],"low":q["low"],"close":q["close"],"volume":q["volume"]}).dropna(subset=["close","open","high","low"])
        df["volume"]=df["volume"].fillna(0); df.to_pickle(f"research_data/gold/fut_{sym[:-2].lower()}_1d.pkl"); print(sym,len(df),df.time.iloc[0].date())
    except Exception as e: print(sym,"FAILED",e)
