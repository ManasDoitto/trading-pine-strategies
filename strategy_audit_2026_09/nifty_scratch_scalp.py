"""Same 24 from-scratch mean-reversion/quick-scalp families as bnf_scratch_scalp.py, run on Nifty 50 spot.
Data: NSE_NIFTY_5m.csv (6.3mo usable, 9 Mar-25 Sep 2026) and NSE_NIFTY_3m.csv (3.7mo, 1 Jun-25 Sep 2026) --
same TradingView data floor as BankNifty spot (confirmed on both spot and futures for Nifty, see
nifty_port_test_results_2026_09_27.md). No 3-year option exists for Nifty on this feed either way.
NSE:NIFTY spot pv=1. Same session/flat convention as bnf_scratch_scalp.py.
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bnf_scratch_scalp as X
import bnf_port_test as B

INST = "NSE_NIFTY"
B.PV = 1  # NSE:NIFTY spot point value

if __name__ == "__main__":
    ROOT = B.ROOT
    rows = []
    for tf in ("5", "3"):
        for i, (tag, v) in enumerate(X.CONFIGS.items()):
            rows.append(X.summ(tag, v, tf, inst=INST))
            if (i + 1) % 8 == 0:
                print(f"tf={tf}m {i + 1}/{len(X.CONFIGS)}", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(ROOT / "research_data" / "nifty_scratch_scalp.csv", index=False)
    pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
    print(R.to_string(index=False))
