import os, requests, json, datetime
from dotenv import load_dotenv
load_dotenv(r'd:\Trading code-Claude\.env')
CLIENT_ID = os.getenv('DHAN_CLIENT_ID')
TOKEN = os.getenv('DHAN_ACCESS_TOKEN')
headers = {'access-token': TOKEN, 'client-id': CLIENT_ID, 'Content-Type': 'application/json'}

tests = [
    ('5yr ago', '2021-08-01', '2021-08-31'),
    ('4yr ago', '2022-08-01', '2022-08-31'),
    ('3yr ago', '2023-08-01', '2023-08-31'),
    ('2yr ago', '2024-08-01', '2024-08-31'),
    ('1yr ago', '2025-08-01', '2025-08-31'),
    ('1mo ago', '2026-08-01', '2026-08-31'),
]

for label, fd, td in tests:
    payload = {
        'exchangeSegment': 'NSE_FNO',
        'securityId': 13,           # NIFTY 50 index security ID
        'instrument': 'OPTIDX',
        'expiryFlag': 'MONTH',
        'expiryCode': 1,
        'strike': 'ATM',
        'drvOptionType': 'CALL',
        'interval': 15,
        'fromDate': fd,
        'toDate': td,
        'requiredData': ['open', 'high', 'low', 'close', 'volume']
    }
    r = requests.post(
        'https://api.dhan.co/v2/charts/rollingoption',
        headers=headers,
        json=payload,
        timeout=15
    )
    resp = r.json()
    # Response is either {'open': [...], 'timestamp': [...]} or {'data': {'ce': {'open': [...], 'timestamp': [...]}}}
    if 'timestamp' in resp:
        ts = resp.get('timestamp', [])
        opens = resp.get('open', [])
    elif 'data' in resp and 'ce' in resp['data']:
        ce = resp['data']['ce']
        ts = ce.get('timestamp', [])
        opens = ce.get('open', [])
    else:
        ts = []
        opens = []

    if ts:
        first = datetime.datetime.fromtimestamp(ts[0]).strftime('%Y-%m-%d')
        last  = datetime.datetime.fromtimestamp(ts[-1]).strftime('%Y-%m-%d')
        print(f'{label}: OK  records={len(ts)}  range={first} to {last}  first_open={opens[0] if opens else "?"}')
    else:
        err = resp.get('errorMessage', 'empty response')
        print(f'{label}: FAIL/EMPTY  {err}')
