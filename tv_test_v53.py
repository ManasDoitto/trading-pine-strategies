"""Test v5.3 sweep winner in TradingView via MCP — fixed workflow.

Root cause of previous failure: chart_manage_indicator used 'id' instead of 'entity_id',
and ui_evaluate used 'code' instead of 'expression'.
Fix: Use correct parameter names, then use ui_keyboard Ctrl+Enter after source set.
"""
import asyncio, json, os, sys
from datetime import datetime
from mcp.client import stdio as stdio_client
from mcp.client import session as mcp_session

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TV_MCP_DIR = r"C:\Users\Manas\Downloads\tradingview-mcp-main\tradingview-mcp-main"
SERVER_PATH = os.path.join(TV_MCP_DIR, "src", "server.js")
PINE_V53 = r"D:\Trading code-Claude\working_strategies\Silver\7_v5.3_optimized_sweep_winner.pine.txt"

# Entity ID for the v4.1 strategy on the chart
V41_ENTITY_ID = "l7BgGR"


async def run_tv_test_v53():
    server_params = stdio_client.StdioServerParameters(
        command="node", args=[SERVER_PATH], env=None, cwd=TV_MCP_DIR,
    )

    async with stdio_client.stdio_client(server_params) as (read_stream, write_stream):
        async with mcp_session.ClientSession(read_stream, write_stream) as mcp:
            print("=== TradingView MCP Test: Silver v5.3 ===\n", flush=True)

            # 0. Check health
            result = await mcp.call_tool("tv_health_check", arguments={})
            data = json.loads(result.content[0].text)
            print(f"Health: CDP connected = {data.get('cdp_connected', False)}", flush=True)
            if not data.get('cdp_connected'):
                print("ERROR: TV not connected", flush=True)
                return

            # 1. Set symbol/timeframe
            await mcp.call_tool("chart_set_symbol", arguments={"symbol": "MCX:SILVER1!"})
            await asyncio.sleep(5)
            await mcp.call_tool("chart_set_timeframe", arguments={"timeframe": "5"})
            await asyncio.sleep(5)

            # 2. Check current chart state
            print("\n--- Chart State (before removal) ---", flush=True)
            result = await mcp.call_tool("chart_get_state", arguments={})
            chart_data = json.loads(result.content[0].text)
            for s in chart_data.get('studies', []):
                print(f"  [{s['id']}] {s['name']}", flush=True)

            # 3. Remove old v4.1 strategy from the chart using entity_id
            print(f"\n--- Removing old v4.1 strategy (entity_id: {V41_ENTITY_ID}) ---", flush=True)
            try:
                result = await mcp.call_tool("chart_manage_indicator", arguments={
                    "action": "remove",
                    "entity_id": V41_ENTITY_ID
                })
                print(f"  Remove result: {result.content[0].text[:300]}", flush=True)
            except Exception as e:
                print(f"  Remove error: {e}", flush=True)
            await asyncio.sleep(5)

            # Verify removal
            result = await mcp.call_tool("chart_get_state", arguments={})
            chart_data = json.loads(result.content[0].text)
            print(f"\nStudies after removal: {[s['name'] for s in chart_data.get('studies', [])]}", flush=True)

            # 4. Open Pine Editor panel
            print("\n--- Opening Pine Editor panel ---", flush=True)
            try:
                result = await mcp.call_tool("ui_open_panel", arguments={
                    "panel": "pine-editor",
                    "action": "open"
                })
                print(f"  {result.content[0].text[:200]}", flush=True)
                await asyncio.sleep(8)
            except Exception as e:
                print(f"  ui_open_panel error: {e}", flush=True)
                await asyncio.sleep(3)

            # 5. Set v5.3 source code
            print("\n--- Setting v5.3 Pine Source ---", flush=True)
            with open(PINE_V53, 'r') as f:
                v53_code = f.read()

            set_ok = False
            for attempt in range(5):
                await asyncio.sleep(2)
                result = await mcp.call_tool("pine_set_source", arguments={"source": v53_code})
                text = result.content[0].text if result.content else ""
                print(f"  Attempt {attempt+1}: {text[:300]}", flush=True)
                if 'lines_set' in text:
                    set_ok = True
                    print("  Source set successfully!", flush=True)
                    break

            await asyncio.sleep(3)

            # 6. Compile and Add to chart
            # Now that v4.1 is removed, Pine Editor should show "Add to chart" for v5.3
            print("\n--- Compiling v5.3 via pine_compile ---", flush=True)
            result = await mcp.call_tool("pine_compile", arguments={})
            text = result.content[0].text if result.content else ""
            print(f"  pine_compile: {text[:500]}", flush=True)
            await asyncio.sleep(10)

            # 7. Check if v5.3 is on chart now
            result = await mcp.call_tool("chart_get_state", arguments={})
            chart_data2 = json.loads(result.content[0].text)
            v53_on_chart = any("v5.3" in s.get('name', '') for s in chart_data2.get('studies', []))
            print(f"\n  v5.3 on chart: {v53_on_chart}", flush=True)
            print(f"  Current studies: {[s['name'] for s in chart_data2.get('studies', [])]}", flush=True)

            if not v53_on_chart:
                # Try Ctrl+Enter (add to chart shortcut) via ui_keyboard
                print("\n--- v5.3 not on chart, trying Ctrl+Enter (add to chart shortcut) ---", flush=True)
                try:
                    result = await mcp.call_tool("ui_keyboard", arguments={
                        "key": "Enter",
                        "modifiers": ["ctrl"]
                    })
                    print(f"  ui_keyboard: {result.content[0].text[:200]}", flush=True)
                    await asyncio.sleep(10)
                except Exception as e:
                    print(f"  ui_keyboard error: {e}", flush=True)
                    await asyncio.sleep(3)

                # Check again
                result = await mcp.call_tool("chart_get_state", arguments={})
                chart_data3 = json.loads(result.content[0].text)
                v53_on_chart = any("v5.3" in s.get('name', '') for s in chart_data3.get('studies', []))
                print(f"\n  v5.3 on chart after Ctrl+Enter: {v53_on_chart}", flush=True)
                print(f"  Current studies: {[s['name'] for s in chart_data3.get('studies', [])]}", flush=True)

            # 8. Wait for strategy calculation
            print("\nWaiting 30s for strategy to calculate on full data...", flush=True)
            await asyncio.sleep(30)

            # 9. Get strategy results
            print("\n--- Strategy Results ---", flush=True)
            try:
                result = await mcp.call_tool("data_get_strategy_results", arguments={})
                text = result.content[0].text if result.content else ""
                data = json.loads(text)
                m = data.get('metrics', {})
                print(f"  Strategy: {data.get('strategy', 'unknown')}", flush=True)
                print(f"  Trades: {m.get('total_trades', 0)}", flush=True)
                print(f"  Net: {m.get('net_profit', 0):.2f}", flush=True)
                print(f"  PF: {m.get('profit_factor', 0):.4f}", flush=True)
                print(f"  WR: {m.get('percent_profitable', 0)*100:.1f}%", flush=True)
                print(f"  DD: {m.get('max_drawdown', 0):.0f}", flush=True)
                print(f"  Sharpe: {m.get('sharpe', 0):.2f}", flush=True)
                print(f"  Sortino: {m.get('sortino', 0):.2f}", flush=True)

                ts = datetime.now().strftime("%H%M%S")
                with open(f"silver_v53_tv_results_{ts}.json", "w") as f:
                    json.dump(data, f, indent=2)
                print(f"\n  Full results saved to silver_v53_tv_results_{ts}.json", flush=True)

                if data.get('strategy', '').startswith('SILVER v5.3'):
                    print("\n*** SUCCESS: v5.3 is active on chart! ***", flush=True)
                else:
                    print(f"\n  NOTE: Strategy is '{data.get('strategy', '')}' — not v5.3", flush=True)

            except Exception as e:
                print(f"  Error: {e}", flush=True)

            print("\n=== TEST COMPLETE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(run_tv_test_v53())
