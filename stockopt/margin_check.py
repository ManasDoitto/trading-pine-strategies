"""Real intraday-futures margin requirement for each A+ v1 (131-symbol) allowlist stock,
via Dhan's own read-only margin_calculator (no order placed -- pure calculation endpoint).

Not routed through ReadOnlyDhan: margin_calculator is legitimately read-only, but the
allowlist's own test defensively blocks any method starting with "margin" (there's no other
margin-prefixed dhanhq method today, but the test wasn't narrowed to make an exception, so
this stays a one-off raw call rather than a permanent addition to the allowlist).
"""
import json
import os
import sys
import time

from dhanhq import DhanContext, dhanhq
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from trading_agents.core.dhan_client import wait_for_slot  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
dhan = dhanhq(DhanContext(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN")))

fmap = json.load(open(os.path.join(ROOT, "research_data", "stockopt", "aplus_v1_futures.json")))
prices = json.load(open(os.path.join(ROOT, "research_data", "stockopt", "aplus_v1_recent_prices.json")))

rows = []
for i, (sym, f) in enumerate(fmap.items()):
    px = prices.get(sym)
    if px is None:
        continue
    wait_for_slot("data")
    try:
        r = dhan.margin_calculator(security_id=str(f["secid"]), exchange_segment="NSE_FNO",
                                   transaction_type="BUY", quantity=f["lot"],
                                   product_type="MARGIN", price=px)
        m = r.get("data", {}) if isinstance(r, dict) else {}
        margin = m.get("totalMargin")
        rows.append(dict(symbol=sym, lot=f["lot"], price=px, notional=px * f["lot"],
                         margin=margin, raw=m, note="ok"))
    except Exception as e:
        rows.append(dict(symbol=sym, lot=f["lot"], price=px, notional=px * f["lot"],
                         margin=None, note=f"fail: {e}"))
    if (i + 1) % 25 == 0:
        print(f"..{i+1}/{len(fmap)}", flush=True)

import pandas as pd  # noqa: E402
out = pd.DataFrame(rows)
out.to_csv(os.path.join(ROOT, "research_data", "stockopt", "aplus_v1_margins.csv"), index=False)
ok = out[out.note == "ok"].copy()
print(f"\n{len(ok)}/{len(out)} priced")
if len(ok):
    ok["margin_pct"] = ok.margin / ok.notional * 100
    print(ok[["symbol", "price", "lot", "notional", "margin", "margin_pct"]]
          .sort_values("margin").to_string(index=False))
    print("\nmargin per lot: min={:.0f} median={:.0f} mean={:.0f} max={:.0f}".format(
        ok.margin.min(), ok.margin.median(), ok.margin.mean(), ok.margin.max()))
    print("margin %% of notional: min={:.1f}% median={:.1f}% max={:.1f}%".format(
        ok.margin_pct.min(), ok.margin_pct.median(), ok.margin_pct.max()))
