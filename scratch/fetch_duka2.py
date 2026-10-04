import urllib.request, urllib.error, lzma, struct, datetime as dt, time, os, sys, pandas as pd
from concurrent.futures import ThreadPoolExecutor
OUT="research_data/gold/duka_years"; os.makedirs(OUT,exist_ok=True)
def get(day):
    url=f"http://datafeed.dukascopy.com/datafeed/XAUUSD/{day.year}/{day.month-1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    for a in range(3):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=15).read()
            if not raw: return day,[]
            d=lzma.decompress(raw); base=dt.datetime(day.year,day.month,day.day); rows=[]
            for i in range(len(d)//24):
                t,o,c,l,h,v=struct.unpack(">IIIIIf",d[i*24:(i+1)*24]); rows.append((base+dt.timedelta(seconds=t),o/1000,h/1000,l/1000,c/1000,v))
            return day,rows
        except urllib.error.HTTPError as e:
            if e.code==404: return day,[]
            time.sleep(1+a)
        except Exception: time.sleep(1+a)
    return day,None
t0=time.time()
for year in range(2018,2027):
    p=f"{OUT}/{year}.pkl"
    if os.path.exists(p): print(year,"cached",flush=True); continue
    days=[dt.date(year,1,1)+dt.timedelta(n) for n in range(366) if (dt.date(year,1,1)+dt.timedelta(n)).year==year and (dt.date(year,1,1)+dt.timedelta(n))<=dt.date(2026,10,3) and (dt.date(year,1,1)+dt.timedelta(n)).weekday()!=5]
    rows=[]; failed=[]
    with ThreadPoolExecutor(6) as ex:
        for k,(day,r) in enumerate(ex.map(get,days)):
            if r is None: failed.append(day)
            else: rows+=r
    df=pd.DataFrame(rows,columns=["time","open","high","low","close","volume"]).drop_duplicates("time").sort_values("time")
    df.to_pickle(p); print(year,len(df),"bars; failed days:",len(failed),f"{time.time()-t0:.0f}s",flush=True)
parts=[pd.read_pickle(f"{OUT}/{y}.pkl") for y in range(2018,2027)]
al=pd.concat(parts).sort_values("time").drop_duplicates("time"); al.to_pickle("research_data/gold/xauusd_1m.pkl"); print("ALL DONE",len(al),al.time.iloc[0],al.time.iloc[-1],flush=True)
