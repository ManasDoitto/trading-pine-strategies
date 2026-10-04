"""Restore v4.1 forward test strategy on the chart after v5.3 test."""
import asyncio, json, os, sys
from mcp.client import stdio as stdio_client
from mcp.client import session as mcp_session

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TV_MCP_DIR = r"C:\Users\Manas\Downloads\tradingview-mcp-main\tradingview-mcp-main"
SERVER_PATH = os.path.join(TV_MCP_DIR, "src", "server.js")
PINE_V41 = r"D:\Trading code-Claude\working_strategies\Silver\6_v4.1_flip_breakout_forwardtest.pine.txt"


async def restore_v41():
    server_params = stdio_client.StdioServerParameters(
        command="node", args=[SERVER_PATH], env=None, cwd=TV_MCP_DIR,
    )

    async with stdio_client.stdio_client(server_params) as (read_stream, write_stream):
        async with mcp_session.ClientSession(read_stream, write_stream) as mcp:
            print("=== Restoring v4.1 Forward Test Strategy ===\n", flush=True)

            # 1. Set symbol/timeframe
            await mcp.call_tool("chart_set_symbol", arguments={"symbol": "MCX:SILVER1!"})
            await asyncio.sleep(5)
            await mcp.call_tool("chart_set_timeframe", arguments={"timeframe": "5"})
            await asyncio.sleep(5)

            # 2. Check current chart state — find v5.3 entity_id
            result = await mcp.call_tool("chart_get_state", arguments={})
            chart_data = json.loads(result.content[0].text)
            print("Current studies:", flush=True)
            v53_id = None
            for s in chart_data.get('studies', []):
                print(f"  [{s['id']}] {s['name']}", flush=True)
                if "v5.3" in s.get('name', ''):
                    v53_id = s['id']

            # 3. Remove v5.3 from chart
            if v53_id:
                print(f"\nRemoving v5.3 (entity_id: {v53_id})...", flush=True)
                result = await mcp.call_tool("chart_manage_indicator", arguments={
                    "action": "remove",
                    "entity_id": v53_id
                })
                print(f"  {result.content[0].text[:200]}", flush=True)
                await asyncio.sleep(5)

                # Verify removal
                result = await mcp.call_tool("chart_get_state", arguments={})
                chart_data = json.loads(result.content[0].text)
                print(f"Studies after removal: {[s['name'] for s in chart_data.get('studies', [])]}", flush=True)
            else:
                print("v5.3 not found on chart, skipping removal.", flush=True)

            # 4. Open Pine Editor
            print("\nOpening Pine Editor...", flush=True)
            await mcp.call_tool("ui_open_panel", arguments={"panel": "pine-editor", "action": "open"})
            await asyncio.sleep(8)

            # 5. Set v4.1 source
            print("\nSetting v4.1 Pine Source...", flush=True)
            with open(PINE_V41, 'r') as f:
                v41_code = f.read()

            result = await mcp.call_tool("pine_set_source", arguments={"source": v41_code})
            text = result.content[0].text if result.content else ""
            print(f"  {text[:200]}", flush=True)
            await asyncio.sleep(5)

            # 6. Compile + Add to chart (Ctrl+Enter)
            print("\nAdding v4.1 to chart (Ctrl+Enter)...", flush=True)
            try:
                result = await mcp.call_tool("ui_keyboard", arguments={
                    "key": "Enter",
                    "modifiers": ["ctrl"]
                })
                print(f"  ui_keyboard: {result.content[0].text[:200]}", flush=True)
                await asyncio.sleep(10)
            except Exception as e:
                print(f"  ui_keyboard error: {e}", flush=True)
                # Fallback: pine_compile
                result = await mcp.call_tool("pine_compile", arguments={})
                print(f"  pine_compile: {result.content[0].text[:200]}", flush=True)
                await asyncio.sleep(15)

            # 7. Verify v4.1 is on chart
            result = await mcp.call_tool("chart_get_state", arguments={})
            chart_data = json.loads(result.content[0].text)
            v41_present = any("v4.1" in s.get('name', '') for s in chart_data.get('studies', []))
            print(f"\nv4.1 on chart: {v41_present}", flush=True)
            print(f"Studies: {[s['name'] for s in chart_data.get('studies', [])]}", flush=True)

            # 8. Get v4.1 results
            print("\nWaiting 15s for v4.1 to calculate...", flush=True)
            await asyncio.sleep(15)

            try:
                result = await mcp.call_tool("data_get_strategy_results", arguments={})
                data = json.loads(result.content[0].text)
                m = data.get('metrics', {})
                print(f"\nv4.1 Results:", flush=True)
                print(f"  Strategy: {data.get('strategy', 'unknown')}", flush=True)
                print(f"  Trades: {m.get('total_trades', 0)}", flush=True)
                print(f"  Net: {m.get('net_profit', 0):.2f}", flush=True)
                print(f"  PF: {m.get('profit_factor', 0):.4f}", flush=True)
                print(f"  WR: {m.get('percent_profitable', 0)*100:.1f}%", flush=True)
                print(f"  DD: {m.get('max_drawdown', 0):.0f}", flush=True)
            except Exception as e:
                print(f"  Error getting results: {e}", flush=True)

            print("\n=== RESTORE COMPLETE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(restore_v41())
