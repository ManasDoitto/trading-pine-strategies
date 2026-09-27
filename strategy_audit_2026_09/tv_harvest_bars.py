"""Bar harvester: load history into the TradingView chart's bar buffer and dump it to CSV.

Why this exists: the TradingView MCP's data_get_ohlcv returns at most 500 bars per call, and 32 months of
5m MCX bars is ~120k rows - far too many to pass through a conversation. This talks to the same local
Chrome-DevTools port the MCP uses (9222) and writes straight to disk.

What it does to the chart: it asks the main series for older history (requestMoreData, exactly as the MCP's own
chart_set_visible_range does) and reads the bars. It never changes the symbol, timeframe, layout, scripts, view
or replay state - drive those with the MCP first.

    python strategy_audit_2026_09/tv_harvest_bars.py --peek                    # report what is loaded, write nothing
    python strategy_audit_2026_09/tv_harvest_bars.py --back-to 2024-01-01     # page history back, then merge to disk

Files: research_data/bars/<SYMBOL>_5m.csv  (unix seconds UTC; open,high,low,close,volume), de-duplicated by
time and kept sorted, so several harvests of one symbol build one continuous history.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from websockets.sync.client import connect

PORT = 9222
OUT = Path(__file__).resolve().parents[1] / "research_data" / "bars"

CHART = "window.TradingViewApi._activeChartWidgetWV.value()"
SERIES = f"{CHART}._chartWidget.model().mainSeries()"

STATE_JS = f"""(function() {{
  var ms = {SERIES}, b = ms.bars(), fv = b.valueAt(b.firstIndex());
  var more = true; try {{ more = ms.requestMoreDataAvailable(); }} catch (e) {{}}
  return {{firstTime: fv && fv[0], size: b.size(), more: more,
          symbol: {CHART}.symbol(), resolution: {CHART}.resolution()}};
}})()"""
MORE_JS = f"(function() {{ try {{ {SERIES}.requestMoreData(1000); }} catch (e) {{}} }})()"
ROWS_JS = f"""(function() {{
  var b = {SERIES}.bars(), rows = [], first = b.firstIndex(), last = b.lastIndex();
  for (var i = first; i <= last; i++) {{
    var v = b.valueAt(i);
    if (v) rows.push([v[0], v[1], v[2], v[3], v[4], v[5] || 0]);
  }}
  return rows;
}})()"""


def chart_target(chart_id=None, target_id=None):
    """The chart page to read. With several chart tabs open it will not guess: pass --chart-id or --target-id."""
    targets = json.load(urllib.request.urlopen(f"http://localhost:{PORT}/json/list", timeout=10))
    pages = [t for t in targets if t.get("type") == "page" and "/chart/" in t.get("url", "")]
    if target_id:
        pages = [t for t in pages if t.get("id") == target_id]
    elif chart_id:
        pages = [t for t in pages if f"/chart/{chart_id}" in t["url"]]
    if not pages:
        raise SystemExit("no matching TradingView chart page found on the debugging port")
    if len(pages) > 1:
        listing = ", ".join(f"{t['id']} ({t['url']})" for t in pages)
        raise SystemExit(f"several chart tabs are open - pass --target-id to choose one: {listing}")
    return pages[0]["webSocketDebuggerUrl"]


class Chart:
    def __init__(self, chart_id=None, target_id=None):
        self.ws = connect(chart_target(chart_id, target_id), max_size=None, open_timeout=15)
        self.n = 0

    def evaluate(self, expression):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate",
                                 "params": {"expression": expression, "returnByValue": True}}))
        while True:
            msg = json.loads(self.ws.recv(timeout=180))
            if msg.get("id") == mid:
                break
        if msg.get("result", {}).get("exceptionDetails"):
            raise SystemExit(f"chart evaluate failed: {msg['result']['exceptionDetails'].get('text')}")
        return msg.get("result", {}).get("result", {}).get("value")

    def close(self):
        self.ws.close()


def ist(sec):
    return pd.to_datetime(sec, unit="s") + pd.Timedelta(hours=5, minutes=30)


def page_back(chart, target_sec, max_pages=600, patience=4, wait=1.8):
    """Ask for older history until the earliest bar reaches target_sec, the feed runs out, or it stalls."""
    stalled, last = 0, None
    for i in range(max_pages):
        st = chart.evaluate(STATE_JS)
        if not st or st["firstTime"] is None:
            raise SystemExit("no bars loaded on the chart yet (still loading?)")
        if i % 20 == 0:
            print(f"  page {i:>3}: {st['size']:>7,} bars, earliest {ist(st['firstTime'])} IST", flush=True)
        if st["firstTime"] <= target_sec:
            return st, "reached target"
        if not st["more"]:
            return st, "feed has no older data"
        stalled = stalled + 1 if last == st["size"] else 0
        if stalled >= patience:
            return st, "stalled (plan bar limit or data floor?)"
        last = st["size"]
        chart.evaluate(MORE_JS)
        time.sleep(wait)
    return chart.evaluate(STATE_JS), "page cap"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--peek", action="store_true", help="report only, write nothing, request nothing")
    ap.add_argument("--back-to", help="YYYY-MM-DD: page history back to this date before dumping")
    ap.add_argument("--chart-id", help="the id in the chart URL, when several chart tabs are open")
    ap.add_argument("--target-id", help="the raw devtools target id, when --chart-id still matches more than one")
    args = ap.parse_args()

    chart = Chart(args.chart_id, args.target_id)
    try:
        st = chart.evaluate(STATE_JS)
        print(f"chart: {st['symbol']} {st['resolution']}  {st['size']:,} bars loaded, "
              f"earliest {ist(st['firstTime'])} IST, older data available: {st['more']}")
        if args.peek:
            return 0
        if str(st["resolution"]) not in ("3", "5"):
            raise SystemExit(f"refusing: resolution {st['resolution']!r}; this store handles 3m/5m only")
        if args.back_to:
            target = int(datetime.strptime(args.back_to, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
            st, why = page_back(chart, target)
            print(f"paging done: {why}; {st['size']:,} bars, earliest {ist(st['firstTime'])} IST")
        rows = chart.evaluate(ROWS_JS)
        symbol = chart.evaluate(f"{CHART}.symbol()")
    finally:
        chart.close()

    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"].astype("int64")
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / (re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_") + f"_{st['resolution']}m.csv")
    before = 0
    if path.exists():
        old = pd.read_csv(path)
        before = len(old)
        df = pd.concat([old, df]).drop_duplicates("time", keep="last").sort_values("time").reset_index(drop=True)
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)
    print(f"wrote {path.name}: {before:,} -> {len(df):,} bars, {ist(df.time.iat[0])} -> {ist(df.time.iat[-1])} IST")
    return 0


if __name__ == "__main__":
    sys.exit(main())
