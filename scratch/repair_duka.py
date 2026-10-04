import urllib.request, urllib.error, lzma, struct, datetime as dt, time, os, pandas as pd, sys
from concurrent.futures import ThreadPoolExecutor
OUT="research_data/gold/duka_years"
def get(day):
    url=f"http://datafeed.dukascopy.com/datafeed/XAUUSD/{day.year}/{day.month-1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    for a in range(8):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=40).read()
            if not raw: return day,[]
            d=lzma.decompress(raw); base=dt.datetime(day.year,day.month,day.day); rows=[]
            for i in range(len(d)//24):
                t,o,c,l,h,v=struct.unpack(">IIIIIf",d[i*24:(i+1)*24]); rows.append((base+dt.timedelta(seconds=t),o/1000,h/1000,l/1000,c/1000,v))
            return day,rows
        except urllib.error.HTTPError as e:
            if e.code==404: return day,[]
            time.sleep(2+a)
        except Exception: time.sleep(2+a)
    return day,None
tot_fixed=0
for year in range(2018,2027):
    p=f"{OUT}/{year}.pkl"
    if not os.path.exists(p): continue
    df=pd.read_pickle(p); have=set(pd.to_datetime(df.time).dt.date)
    end=min(dt.date(year,12,31),dt.date(2026,10,2))
    miss=[dt.date(year,1,1)+dt.timedelta(n) for n in range((end-dt.date(year,1,1)).days+1)]
    miss=[d for d in miss if d.weekday()!=5 and d not in have]
    if not miss: print(year,"complete",flush=True); continue
    rows=[]; still=[]; empty=[]
    with ThreadPoolExecutor(4) as ex:
        for day,r in ex.map(get,miss):
            if r is None: still.append(day)
            elif r==[]: empty.append(day)
            else: rows+=r
    if rows:
        new=pd.concat([df,pd.DataFrame(rows,columns=df.columns)]).drop_duplicates("time").sort_values("time"); new.to_pickle(p)
    print(year,"missing",len(miss),"-> recovered",len(miss)-len(still)-len(empty),"empty(holiday)",len(empty),"still failed",len(still),flush=True)
