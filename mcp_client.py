import asyncio
import json
import sys
import os

# Minimal dependency check
try:
    import httpx
    from httpx_sse import connect_sse
except ImportError:
    print("This script requires 'httpx' and 'httpx-sse'.", file=sys.stderr)
    print("Please install them: pip install httpx httpx-sse", file=sys.stderr)
    sys.exit(1)

DEFAULT_URL = "https://mcp.smartnvr.shop/mcp"

async def forward_outgoing(client, url):
    """Read from stdin and send to remote server via HTTP POST."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            try:
                # Forward JSON-RPC request to the server
                await client.post(url, json=data)
            except Exception as e:
                print(f"Error forwarding request: {e}", file=sys.stderr)

        except Exception as e:
            print(f"Stdin read error: {e}", file=sys.stderr)
            break

async def forward_incoming(client, url):
    """Listen to remote SSE stream and write to stdout."""
    try:
        async with connect_sse(client, "GET", url) as event_source:
            async for sse in event_source.aiter_sse():
                if sse.event == "message":
                    sys.stdout.write(sse.data + "\n")
                    sys.stdout.flush()
    except Exception as e:
        print(f"SSE Connection error: {e}", file=sys.stderr)
        sys.exit(1)

async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    
    # Configure stdout for line buffering
    sys.stdout.reconfigure(line_buffering=True)
    
    print(f"Connecting to {url}...", file=sys.stderr)

    async with httpx.AsyncClient(timeout=None) as client:
        await asyncio.gather(
            forward_outgoing(client, url),
            forward_incoming(client, url)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
