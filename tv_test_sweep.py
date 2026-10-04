"""Test top sweep configs in TradingView via MCP."""
import asyncio, json, os, sys, time
from datetime import datetime
from mcp.client import stdio as stdio_client
from mcp.client import session as mcp_session

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TV_MCP_DIR = r"C:\Users\Manas\Downloads\tradingview-mcp-main\tradingview-mcp-main"
SERVER_PATH = os.path.join(TV_MCP_DIR, "src", "server.js")

PINE_SCRIPT = r"D:\Trading code-Claude\working_strategies\Silver\7_v5.3_optimized_sweep_winner.pine.txt"

# Load sweep results
with open('sweep_25000_results.json', 'r') as f:
    sweep_results = json.load(f)

# Select top configs to test (unique parameter sets)
seen_configs = set()
top_configs = []
for r in sweep_results:
    config_key = (r['adx'], r['rr'], r['pb'], r['swb'], r['sha'], r['min_sl'], r['bo_lb'])
    if config_key not in seen_configs:
        seen_configs.add(config_key)
        top_configs.append(r)
    if len(top_configs) >= 15:
        break

print(f"Testing {len(top_configs)} unique configs in TradingView", flush=True)
for i, r in enumerate(top_configs):
    print(f"  #{i+1}: ADX>={r['adx']} RR={r['rr']} PB={r['pb']} SWB={r['swb']} "
          f"SHA={r['sha']} MinSL={r['min_sl']} BO={r['bo_lb']} -> PF={r['pf']:.3f} net={r['net']:+.0f}", flush=True)


async def run_tv_tests():
    server_params = stdio_client.StdioServerTransport if hasattr(stdio_client, 'StdioServerTransport') else None
    server_params = stdio_client.StdioServerParameters(
        command="node",
        args=[SERVER_PATH],
        env=None,
        cwd=TV_MCP_DIR,
    )

    async with stdio_client.stdio_client(server_params) as (read_stream, write_stream):
        async with mcp_session.ClientSession(read_stream, write_stream) as mcp:
            print("\n=== Connected to TradingView MCP ===", flush=True)

            # Health check
            try:
                result = await mcp.call_tool("tv_health_check", arguments={})
                text = result.content[0].text if result.content else ""
                data = json.loads(text)
                if data.get('cdp_connected'):
                    print("CDP: Connected", flush=True)
                else:
                    print("CDP: Not connected, launching TV...", flush=True)
                    result = await mcp.call_tool("tv_launch", arguments={})
                    print(result.content[0].text if result.content else "Launch done")
                    await asyncio.sleep(15)
            except Exception as e:
                print(f"Health check: {e}", flush=True)

            # Set symbol and timeframe
            await mcp.call_tool("chart_set_symbol", arguments={"symbol": "MCX:SILVER1!"})
            await asyncio.sleep(2)
            await mcp.call_tool("chart_set_timeframe", arguments={"timeframe": "5"})
            await asyncio.sleep(2)

            # Open Pine Editor
            await mcp.call_tool("ui_open_panel", arguments={"panel": "pine-editor", "action": "open"})
            await asyncio.sleep(3)

            # Load Pine script
            with open(PINE_SCRIPT, 'r') as f:
                pine_code = f.read()
            result = await mcp.call_tool("pine_set_source", arguments={"source": pine_code})
            print(f"Pine source set: {result.content[0].text if result.content else 'OK'}", flush=True)

            # Compile
            await asyncio.sleep(1)
            result = await mcp.call_tool("pine_smart_compile", arguments={})
            text = result.content[0].text if result.content else ""
            print(f"Compile: {text[:300]}", flush=True)
            await asyncio.sleep(5)

            # Function to set inputs and get results
            async def test_config(config):
                # Set all input values
                inputs = {}
                for param, value in [
                    ('htfAdxMin', config['adx']),
                    ('rr', config['rr']),
                    ('pbAtrMult', config['pb']),
                    ('swBuf', config['swb']),
                    ('shaMinHold', config['sha']),
                    ('minSL', config['min_sl']),
                    ('boLookback', config['bo_lb']),
                ]:
                    inputs[param] = value

                try:
                    await mcp.call_tool("indicator_set_inputs", arguments={"study_id": "v5.3", "inputs": inputs})
                    await asyncio.sleep(3)  # Wait for TV to recalculate

                    # Get strategy results
                    result = await mcp.call_tool("data_get_strategy_results", arguments={})
                    text = result.content[0].text if result.content else "{}"
                    data = json.loads(text)

                    metrics = data.get('metrics', {})
                    return {
                        'trades': metrics.get('total_trades', 0),
                        'pf': metrics.get('profit_factor', 0),
                        'net': metrics.get('net_profit', 0),
                        'wr': metrics.get('percent_profitable', 0) * 100,
                        'dd': metrics.get('max_drawdown', 0),
                        'avg_trade': metrics.get('avg_trade', 0),
                    }
                except Exception as e:
                    return {'error': str(e)}

            # Test each config
            tv_results = []
            for i, config in enumerate(top_configs):
                print(f"\n--- Testing config #{i+1}: ADX>={config['adx']} RR={config['rr']} PB={config['pb']} ---", flush=True)
                result = await test_config(config)
                result.update({
                    'config': config,
                    'python_pf': config['pf'],
                    'python_net': config['net'],
                })
                tv_results.append(result)

                if 'error' not in result:
                    print(f"  TV: {result['trades']} trades, PF={result['pf']:.3f}, "
                          f"net={result['net']:.0f}, WR={result['wr']:.1f}%", flush=True)
                else:
                    print(f"  Error: {result['error']}", flush=True)

            # Print comparison table
            print(f"\n{'='*140}", flush=True)
            print(f"{'Config':>30} | {'Python':>30} | {'TV':>30}", flush=True)
            print(f"{'':30} | {'Trd':>5} {'PF':>7} {'Net':>9} | {'Trd':>5} {'PF':>7} {'Net':>9} {'WR%':>5}", flush=True)
            print("-" * 140, flush=True)
            for r in tv_results:
                c = r['config']
                cfg_str = f"ADX>{c['adx']} RR={c['rr']} PB={c['pb']}"
                if 'error' in r:
                    print(f"  {cfg_str:<30} | {c['trades']:>5} {c['pf']:>7.3f} {c['net']:+>9.0f} | ERROR: {r['error'][:20]}", flush=True)
                else:
                    print(f"  {cfg_str:<30} | {c['trades']:>5} {c['pf']:>7.3f} {c['net']:+>9.0f} | "
                          f"{r['trades']:>5} {r['pf']:>7.3f} {r['net']:+>9.0f} {r['wr']:>5.1f}", flush=True)

            # Save results
            with open('tv_verification_results.json', 'w') as f:
                json.dump(tv_results, f, indent=2)
            print(f"\nSaved TV verification results to tv_verification_results.json", flush=True)

            # Screenshot
            timestamp = datetime.now().strftime("%H%M%S")
            result = await mcp.call_tool("capture_screenshot", arguments={
                "region": "strategy_tester",
                "filename": f"silver_v53_tv_test_{timestamp}.png"
            })
            print(f"Screenshot: {result.content[0].text if result.content else 'OK'}", flush=True)


if __name__ == "__main__":
    asyncio.run(run_tv_tests())
