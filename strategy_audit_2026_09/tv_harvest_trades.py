"""Dump the Strategy Tester trade list of the chart's v4.1 strategy to disk (one JSON per replay window).

Companion to tv_harvest_bars.py: drive symbol / inputs / replay with the TradingView MCP, then run this to save what the strategy
did in the window it currently covers. Read-only: it only reads reportData() over the debugging port.

    python strategy_audit_2026_09/tv_harvest_trades.py --tag LIVE_SILVER1_t03 [--study "forward test"]

Output: research_data/tv_trades/<tag>.json with the window (backtest range), the symbol, the inputs and every trade
(entry/exit ms-UTC, prices, side, net INR after commission, commission INR). Net points = net INR / point value.
"""
import argparse
import json
from pathlib import Path

from strategy_audit_2026_09.tv_harvest_bars import Chart

OUT = Path(__file__).resolve().parents[1] / "research_data" / "tv_trades"

JS = """(function(study) {
  var w = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model();
  var chart = window.TradingViewApi.activeChart();
  var pv = null; try { pv = w.mainSeries().symbolInfo().pointvalue; } catch (e) {}
  var out = [];
  chart.getAllStudies().forEach(function(s) {
    if (s.name.indexOf(study) < 0) return;
    var ds = w.dataSources().filter(function(d) { return d.id && d.id() === s.id; })[0];
    if (!ds) return;
    var rep = ds.reportData(); rep = rep.value ? rep.value() : rep;
    var inputs = {};
    chart.getStudyById(s.id).getInputValues().forEach(function(x) { if (/^in_([0-9]|2[34])$/.test(x.id)) inputs[x.id] = x.value; });
    out.push({entity: s.id, symbol: chart.symbol(), resolution: chart.resolution(), window: rep.settings.dateRange.backtest, point_value: pv, inputs: inputs,
      trades: (rep.trades || []).map(function(t) { return {side: t.e.tp === 'le' ? 'LONG' : 'SHORT', entry_ms: t.e.tm, exit_ms: t.x.tm,
        entry: t.e.p, exit: t.x.p, net_inr: t.tp.v, comm_inr: t.cm, exit_name: t.x.c}; })});
  });
  return out;
})"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--study", default="forward test")
    ap.add_argument("--chart-id")
    a = ap.parse_args()
    chart = Chart(a.chart_id)
    try:
        res = chart.evaluate(f"({JS})({json.dumps(a.study)})")
    finally:
        chart.close()
    if not res:
        raise SystemExit("no matching study on the chart")
    OUT.mkdir(parents=True, exist_ok=True)
    for r in res:
        label = f"rr{r['inputs'].get('in_6'):g}_sl{r['inputs'].get('in_4'):g}_dl{r['inputs'].get('in_7'):g}"
        (OUT / f"{a.tag}__{label}.json").write_text(json.dumps(r), encoding="utf-8")
        t = r["trades"]
        lo, hi = (min(x["entry_ms"] for x in t), max(x["exit_ms"] for x in t)) if t else (0, 0)
        print(f"{a.tag} {label}: {r['symbol']} {r['resolution']}  {len(t)} trades  window {r['window']}  span {lo} -> {hi}  pv {r['point_value']}")


if __name__ == "__main__":
    main()
