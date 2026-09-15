import os, json
from dotenv import load_dotenv
load_dotenv()
from dhanhq import dhanhq, DhanContext
ctx = DhanContext(os.getenv('DHAN_CLIENT_ID'), os.getenv('DHAN_ACCESS_TOKEN'))
dhan = dhanhq(ctx)

from datetime import datetime, timedelta
today = datetime.now().strftime('%Y-%m-%d')
two_yr_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

all_trades = []
page = 0
while True:
    r = dhan.get_trade_history(from_date=two_yr_ago, to_date=today, page_number=page)
    data = r.get('data') if isinstance(r, dict) else None
    if not data:
        break
    all_trades.extend(data)
    print(f"page {page}: {len(data)} trades (running total {len(all_trades)})")
    page += 1
    if page > 100:
        print("safety stop at 100 pages")
        break

dedup = {}
for t in all_trades:
    dedup[t['orderId'] + '_' + str(t.get('tradedPrice')) + '_' + str(t.get('exchangeTime'))] = t
uniq = list(dedup.values())

out_path = r"C:\Users\Manas\AppData\Local\Temp\claude\D--Trading-code-Claude\6c946a7d-c9ea-4c87-8de8-e707d932880d\scratchpad\dhan\trade_history_full.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(uniq, f, indent=2)
print("RAW FETCHED:", len(all_trades), "UNIQUE:", len(uniq))
print("saved to", out_path)
if uniq:
    times = [t.get('exchangeTime') for t in uniq if t.get('exchangeTime') and t.get('exchangeTime') != 'NA']
    times = sorted(times)
    print("earliest:", times[0] if times else None)
    print("latest:", times[-1] if times else None)
