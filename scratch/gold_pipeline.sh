#!/bin/bash
cd "D:/Trading code-Claude"
until grep -q "^2026" scratch/repair.log; do sleep 10; done
sleep 5
python - <<'PY'
import pandas as pd
parts=[pd.read_pickle(f"research_data/gold/duka_years/{y}.pkl") for y in range(2018,2027)]
al=pd.concat(parts).sort_values("time").drop_duplicates("time"); al.to_pickle("research_data/gold/xauusd_1m.pkl")
print("combined",len(al),al.time.iloc[0],al.time.iloc[-1])
PY
python -c "
import gold_run_repo_modules as R
R.main(workers=3)
"
python gold_tpo.py
echo PIPELINE_FINISHED
