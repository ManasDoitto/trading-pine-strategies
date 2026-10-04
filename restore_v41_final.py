"""Validate fixed v4.1 (Pine v6 compatible) and restore it on chart."""
import asyncio, json, os, sys, time
from mcp.client import stdio as stdio_client
from mcp.client import session as mcp_session

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TV_MCP_DIR = r"C:\Users\Manas\Downloads/tradingview-mcp-main/tradingview-mcp-main"
SERVER_PATH = os.path.join(TV_MCP_DIR, "src", "server.js")
PINE_V41 = r"D:\Trading code-Claude\working_strategies\Silver\6_v4.1_flip_breakout_forwardtest.pine.txt"


async def restore_v41():
    server_params = stdio_client.StdioServerParameters(
        command="node", args=[SERVER_PATH], env=None, cwd=TV_MCP_DIR,
    )

    async with stdio_client.stdio_client(server_params) as (read_stream, write_stream):
        async with mcp_session.ClientSession(read_stream, write_stream) as mcp:
            print("=== Restoring v4.1 (Pine v6 fixed) ===\n", flush=True)

            # 0. Check health
            result = await mcp.call_tool("tv_health_check", arguments={})
            data = json.loads(result.content[0].text)
            print(f"Health: CDP connected = {data.get('cdp_connected', False)}", flush=True)

            # 1. Set symbol/timeframe
            await mcp.call_tool("chart_set_symbol", arguments={"symbol": "MCX:SILVER1!"})
            await asyncio.sleep(5)
            await mcp.call_tool("chart_set_timeframe", arguments={"timeframe": "5"})
            await asyncio.sleep(5)

            # 2. Check current chart state — find v5.3 entity_id to remove
            result = await mcp.call_tool("chart_get_state", arguments={})
            chart_data = json.loads(result.content[0].text)
            print("Current studies:", flush=True)
            for s in chart_data.get('studies', []):
                print(f"  [{s['id']}] {s['name']}", flush=True)

            # Remove v5.3 if present
            for s in chart_data.get('studies', []):
                if "v5.3" in s.get('name', ''):
                    print(f"\nRemoving v5.3 (entity_id: {s['id']})...", flush=True)
                    result = await mcp.call_tool("chart_manage_indicator", arguments={
                        "action": "remove",
                        "entity_id": s['id']
                    })
                    print(f"  {result.content[0].text[:200]}", flush=True)
                    await asyncio.sleep(5)

            # 3. Validate v4.1 with pine_check
            print("\n--- Validating v4.1 (pine_check) ---", flush=True)
            with open(PINE_V41, 'r') as f:
                v41_code = f.read()

            result = await mcp.call_tool("pine_check", arguments={"source": v41_code})
            text = result.content[0].text if result.content else ""
            data = json.loads(text)
            print(f"  compiled: {data.get('compiled')}, errors: {data.get('error_count', 0)}", flush=True)
            if data.get('errors'):
                for e in data['errors']:
                    print(f"    Line {e.get('line')}: {e.get('message')}", flush=True)
            if not data.get('compiled'):
                print("ERROR: v4.1 does not compile! Not loading.", flush=True)
                return

            print("\n  v4.1 compiles cleanly — proceeding to load on chart.", flush=True)

            # 4. Open Pine Editor
            print("\n--- Opening Pine Editor ---", flush=True)
            await mcp.call_tool("ui_open_panel", arguments={"panel": "pine-editor", "action": "open"})
            await asyncio.sleep(8)

            # 5. Set v4.1 source
            print("\n--- Setting v4.1 Pine Source ---", flush=True)
            for attempt in range(5):
                await asyncio.sleep(2)
                result = await mcp.call_tool("pine_set_source", arguments={"source": v41_code})
                text = result.content[0].text if result.content else ""
                print(f"  Attempt {attempt+1}: {text[:200]}", flush=True)
                if 'lines_set' in text:
                    print("  Source set successfully!", flush=True)
                    break
            await asyncio.sleep(3)

            # 6. pine_compile (clicks Pine Save)
            print("\n--- pine_compile ---", flush=True)
            result = await mcp.call_tool("pine_compile", arguments={})
            text = result.content[0].text if result.content else ""
            print(f"  {text[:500]}", flush=True)
            await asyncio.sleep(10)

            # 7. Check compile errors
            print("\n--- Compile errors check ---", flush=True)
            result = await mcp.call_tool("pine_get_errors", arguments={})
            text = result.content[0].text if result.content else ""
            print(f"  {text[:500]}", flush=True)
            err_data = json.loads(text)
            actual_errors = [e for e in err_data.get('errors', []) if e.get('severity', 1) <= 2]
            if len(actual_errors) > 0:
                print("  ACTUAL COMPILE ERRORS DETECTED! Not adding to chart.", flush=True)
                for e in actual_errors:
                    print(f"    Line {e.get('line')}: {e.get('message')}", flush=True)
            else:
                warnings = [e for e in err_data.get('errors', []) if e.get('severity', 1) > 2]
                if warnings:
                    print(f"  {len(warnings)} non-blocking warning(s), proceeding:", flush=True)
                    for w in warnings:
                        print(f"    Line {w.get('line')}: {w.get('message')[:120]}", flush=True)
                # Proceed with Ctrl+Enter
                print("\n--- Ctrl+Enter (add to chart) ---", flush=True)
                result = await mcp.call_tool("ui_keyboard", arguments={
                    "key": "Enter",
                    "modifiers": ["ctrl"]
                })
                print(f"  {result.content[0].text[:200]}", flush=True)
                await asyncio.sleep(12)

            # 9. Verify v4.1 is on chart
            result = await mcp.call_tool("chart_get_state", arguments={})
            chart_data = json.loads(result.content[0].text)
            v41_present = any("v4.1" in s.get('name', '') for s in chart_data.get('studies', []))
            print(f"\nv4.1 on chart: {v41_present}", flush=True)
            print(f"Studies: {[s['name'] for s in chart_data.get('studies', [])]}", flush=True)

            # 10. Get v4.1 results
            if v41_present:
                print("\nWaiting 30s for v4.1 to calculate on full data...", flush=True)
                await asyncio.sleep(30)
                try:
                    result = await mcp.call_tool("data_get_strategy_results", arguments={})
                    text = result.content[0].text if result.content else ""
                    data = json.loads(text)
                    m = data.get('metrics', {})
                    print(f"\nv4.1 Strategy Results:", flush=True)
                    print(f"  Strategy: {data.get('strategy', 'unknown')}", flush=True)
                    print(f"  Trades: {m.get('total_trades', 0)}", flush=True)
                    print(f"  Net: {m.get('net_profit', 0):.2f}", flush=True)
                    print(f"  PF: {m.get('profit_factor', 0):.4f}", flush=True)
                    print(f"  WR: {m.get('percent_profitable', 0)*100:.1f}%", flush=True)
                    print(f"  DD: {m.get('max_drawdown', 0):.0f}", flush=True)

                    ts = datetime.now().strftime("%H%M%S") if 'datetime' in dir() else time.strftime("%H%M%S")
                    with open(f"silver_v41_restored_{ts}.json", "w") as f:
                        json.dump(data, f, indent=2)
                    print(f"\n  Results saved to silver_v41_restored_{ts}.json", flush=True)
                except Exception as e:
                    print(f"  Error getting results: {e}", flush=True)
            else:
                print("v4.1 NOT on chart — restoration failed.", flush=True)

            print("\n=== RESTORE COMPLETE ===", flush=True)


if __name__ == "__main__":
    asyncio.run(restore_v41())
