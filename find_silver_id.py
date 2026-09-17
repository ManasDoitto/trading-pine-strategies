import pandas as pd
try:
    df = pd.read_csv('api-scrip-master.csv', low_memory=False)
    # Find active SILVERM futures
    mcx = df[df['SEM_EXM_EXCH_ID'] == 'MCX']
    silver = mcx[mcx['SEM_CUSTOM_SYMBOL'].str.contains('SILVERM', na=False)]
    futures = silver[silver['SEM_INSTRUMENT_NAME'] == 'FUTCOM']
    # Sort by expiry date to find nearest
    futures = futures.sort_values(by='SEM_EXPIRY_DATE')
    print(futures[['SEM_SMST_SECURITY_ID', 'SEM_CUSTOM_SYMBOL', 'SEM_EXPIRY_DATE']].head())
except Exception as e:
    print(e)
