import asyncio, json, sys, os

from mcp.client import stdio as stdio_client
from mcp.client import session as mcp_session

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TV_MCP_DIR = r"C:\Users\Manas\Downloads\tradingview-mcp-main\tradingview-mcp-main"
SERVER_PATH = os.path.join(TV_MCP_DIR, "src", "server.js")
PINE_V53 = r"D:\Trading code-Claude\working_strategies\Silver\7_v5.3_optimized_sweep_winner.pine.txt"


async def check():
    server_params = stdio_client.StdioServerParameters(
        command="node", args=[SERVER_PATH], env=None, cwd=TV_MCP_DIR,
    )
    async with stdio_client.stdio_client(server_params) as (read_stream, write_stream):
        async with mcp_session.ClientSession(read_stream, write_stream) as mcp:
            with open(PINE_V53, 'r') as f:
                code = f.read()

            result = await mcp.call_tool("pine_check", arguments={"source": code})
            text = result.content[0].text if result.content else ""
            data = json.loads(text)
            print(json.dumps(data, indent=2), flush=True)

            if data.get('compiled'):
                print("\n*** v5.3 COMPILES SUCCESSFULLY ***", flush=True)
            else:
                print(f"\n*** COMPILE ERRORS: {data.get('error_count', 0)} ***", flush=True)


if __name__ == "__main__":
    asyncio.run(check())
