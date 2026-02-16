"""
Test client for the LLM Memory MCP Server.
Exercises all tools to verify the server is working correctly.
"""

import asyncio
import json
import sys
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


SERVER_URL = "http://localhost:4040/mcp"


async def call_tool(session: ClientSession, tool_name: str, args: dict) -> dict:
    """Call an MCP tool and return the parsed result."""
    print(f"\n{'─'*60}")
    print(f"📤 Calling: {tool_name}")
    print(f"   Args: {json.dumps(args, indent=2)}")

    result = await session.call_tool(tool_name, args)
    text = result.content[0].text if result.content else "{}"
    parsed = json.loads(text)

    print(f"📥 Result: {json.dumps(parsed, indent=2)}")
    return parsed


async def main():
    print("🧪 LLM Memory MCP Server — Test Client")
    print(f"   Connecting to: {SERVER_URL}")
    print("=" * 60)

    async with streamablehttp_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("\n✅ Connected and initialized!")

            # List available tools
            tools = await session.list_tools()
            print(f"\n📋 Available tools ({len(tools.tools)}):")
            for t in tools.tools:
                print(f"   • {t.name}: {t.description[:80]}...")

            # List available resources
            resources = await session.list_resources()
            print(f"\n📋 Available resources ({len(resources.resources)}):")
            for r in resources.resources:
                print(f"   • {r.uri}: {r.name}")

            # ── Test 1: Save a conversation ──
            conv_result = await call_tool(session, "save_conversation", {
                "platform": "test_client",
                "title": "Testing the Memory MCP Server",
                "summary": "A test conversation to verify the MCP memory server works correctly",
                "tags": ["test", "verification"],
                "messages": [
                    {"role": "user", "content": "Hello! Can you remember this conversation?"},
                    {"role": "assistant", "content": "Of course! I'll save this to persistent memory."},
                    {"role": "user", "content": "Great, I'm testing the LLM Memory MCP Server."},
                    {"role": "assistant", "content": "The test is working perfectly!"},
                ],
            })
            conv_id = conv_result.get("id")

            # ── Test 2: Save knowledge ──
            await call_tool(session, "save_knowledge", {
                "category": "fact",
                "content": "The LLM Memory MCP Server uses PostgreSQL for persistent storage and runs on port 4040.",
                "tags": ["mcp", "architecture", "postgresql"],
                "source_platform": "test_client",
            })

            await call_tool(session, "save_knowledge", {
                "category": "preference",
                "content": "The user prefers Python for backend development and uses Docker for containerization.",
                "tags": ["python", "docker", "development"],
                "source_platform": "test_client",
            })

            # ── Test 3: Search memory ──
            await call_tool(session, "search_memory", {
                "query": "memory MCP server",
                "limit": 5,
            })

            # ── Test 4: Search knowledge ──
            await call_tool(session, "search_knowledge", {
                "query": "PostgreSQL",
                "limit": 5,
            })

            # ── Test 5: Get recent conversations ──
            await call_tool(session, "get_recent_conversations", {
                "limit": 5,
            })

            # ── Test 6: Get context summary ──
            await call_tool(session, "get_context_summary", {
                "topic": "memory server",
                "limit": 5,
            })

            # ── Test 7: Read resources ──
            print(f"\n{'─'*60}")
            print(f"📤 Reading resource: memory://stats")
            stats = await session.read_resource("memory://stats")
            stats_text = stats.contents[0].text if stats.contents else "{}"
            print(f"📥 Stats: {stats_text}")

            print(f"\n{'─'*60}")
            print(f"📤 Reading resource: memory://platforms")
            platforms = await session.read_resource("memory://platforms")
            platforms_text = platforms.contents[0].text if platforms.contents else "{}"
            print(f"📥 Platforms: {platforms_text}")

            # ── Test 8: Delete the test conversation ──
            if conv_id:
                await call_tool(session, "delete_memory", {
                    "memory_id": conv_id,
                    "memory_type": "conversation",
                })

            print("\n" + "=" * 60)
            print("✅ All tests completed successfully!")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
