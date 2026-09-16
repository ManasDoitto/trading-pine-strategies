---
name: dhan-historical-mcx-options
description: Fetch historical MCX options (OPTFUT) data using DhanHQ API in 90-day batches.
---

# Dhan Historical MCX Options Skill

This skill allows the agent to automatically fetch historical 1-minute OHLCV data for MCX options (`OPTFUT`) from the DhanHQ API. Because Dhan restricts historical data API endpoints to 90 days of data per request, this skill uses a Python script that implements batch processing to retrieve extended periods of data seamlessly.

## Use Case
Trigger this skill whenever the user asks to:
- Get historical data for MCX options over long periods (e.g., 6 months, 1 year).
- "Iterate in 90-day batches" for Dhan data.
- Fetch MCX options data.

## Script Location
The core implementation is located at `d:\Trading code-Claude\fetch_mcx_historical_batches.py`.

## Usage Instructions

When requested to fetch historical MCX options data:
1. Obtain the `security_id` for the desired MCX option. You may need to look this up from the Dhan scrip master (`api-scrip-master.csv`) where `SEM_EXM_EXCH_ID = 'MCX'` and `SEM_INSTRUMENT_NAME = 'OPTFUT'`.
2. Determine the `start_date` and `end_date` for the historical data.
3. Import or execute the `fetch_mcx_historical_in_batches` function from `d:\Trading code-Claude\fetch_mcx_historical_batches.py`.
4. This script connects using the `.env` credentials (`DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN`).
5. Ensure to handle API rate limits appropriately, as the batching script sleeps for a fraction of a second between requests.

### Example Python Integration
```python
import sys
sys.path.append(r"d:\Trading code-Claude")
from fetch_mcx_historical_batches import fetch_mcx_historical_in_batches, get_dhan_client
from datetime import datetime, timedelta

dhan = get_dhan_client()
security_id = "431269" # Example MCX OPTFUT Security ID
end_date = datetime.now()
start_date = end_date - timedelta(days=365) # up to 1 year of data requested

# instrument_type defaults to "OPTFUT" for options; pass instrument_type="FUTCOM" for futures
df = fetch_mcx_historical_in_batches(dhan, security_id, start_date, end_date, batch_days=90, instrument_type="OPTFUT")
print(df.head())
```

## Important Considerations
- **Date Range Limiting**: Do not request more than 90 days of data per individual API call. The script handles this batching logic automatically.
- **Instrument Types**: For MCX options, always use `exchange_segment="MCX_COMM"` and `instrument_type="OPTFUT"` (the default). Pass `instrument_type="FUTCOM"` explicitly if fetching a futures contract instead. The `NFO_OPT` or `OPTIDX` types are for NSE index options and will not work for MCX.
- **Active contracts only**: Dhan only returns intraday (1-min) data for contracts that are currently active/unexpired — see the Dhan findings memory. Requesting a date range that extends before the contract's own listing date, or fetching an already-expired contract, will return empty batches for those chunks (logged as warnings), not an error. This means "1 year of data" is only real for a contract that has actually been trading that long; MCX option contracts typically only exist for a few weeks/months before expiry.
- **Timezone**: Data returned by Dhan might be in epoch seconds or UTC. The provided script automatically converts the data to IST (+05:30).
