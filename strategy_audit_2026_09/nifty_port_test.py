"""Same 30-config crude+silver port as bnf_port_test.py, run on NSE:NIFTY spot instead of BankNifty.
Data: research_data/bars/NSE_NIFTY_5m.csv and NSE_NIFTY_3m.csv, both harvested 2026-09-27. Unlike BankNifty futures
(3 years of 5m), Nifty spot AND Nifty futures both hit the same TradingView data floor as BankNifty spot did:
5m only back to 2026-03-09 (6.7mo), 3m only back to 2026-06-01 (3.9mo) -- confirmed by paging to "no older data" on
both the spot and futures symbols. So there is no robust multi-year option for Nifty on this feed either way;
spot is used since it was the literal ask and costs nothing extra this time. NSE:NIFTY spot point value = 1 (see
tv-mcp-testing-gotchas memory). Session/flat/day-loss-limit conventions identical to bnf_port_test.py.
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bnf_port_test as B

INST = "NSE_NIFTY"
B.PV = 1  # NSE:NIFTY spot point value

if __name__ == "__main__":
    ROOT = B.ROOT
    rows = []
    for tf in ("5", "3"):
        for i, (tag, v) in enumerate(B.ALL.items()):
            rows.append(B.summ(tag, v, tf, inst=INST))
            if (i + 1) % 10 == 0:
                print(f"tf={tf}m {i + 1}/{len(B.ALL)}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "nifty_port_test.csv", index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
