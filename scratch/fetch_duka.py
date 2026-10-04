import urllib.request, lzma, struct, datetime as dt, time, sys, os, pandas as pd
from concurrent.futures import ThreadPoolExecutor
def get(day):
    url=f"http://datafeed.dukascopy.com/datafeed/XAUUSD/{day.year}/{day.month-1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    for a in range(4):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=30).read()
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
days=[dt.date(2018,1,1)+dt.timedelta(n) for n in range((dt.date(2026,10,3)-dt.date(2018,1,1)).days) if (dt.date(2018,1,1)+dt.timedelta(n)).weekday()!=5]
rows=[]; failed=[]
with ThreadPoolExecutor(8) as ex:
    for k,(day,r) in enumerate(ex.map(get,days)):
        if r is None: failed.append(day)
        else: rows+=r
        if k%300==0: print(k,len(days),len(rows),flush=True)
df=pd.DataFrame(rows,columns=["time","open","high","low","close","volume"]).sort_values("time").drop_duplicates("time")
df.to_pickle("research_data/gold/xauusd_1m.pkl"); print("DONE",len(df),df.time.iloc[0],df.time.iloc[-1],"failed",len(failed),failed[:5])
