"""Test that MCP prompts are discoverable and functional."""
import asyncio, json
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

SERVER_URL = "http://localhost:4040/mcp"

async def main():
    async with streamablehttp_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List all prompts
            prompts = await session.list_prompts()
            print(f"✅ {len(prompts.prompts)} MCP Prompts registered:\n")
            for p in prompts.prompts:
                print(f"  📋 {p.name}")
                if p.description:
                    print(f"     {p.description[:80]}")
                if p.arguments:
                    args = ", ".join(f"{a.name}{'?' if not a.required else ''}" for a in p.arguments)
                    print(f"     Args: ({args})")
                print()

            # Test a specific prompt
            print("━" * 60)
            print("Testing: start_conversation(platform='windsurf', topic='React migration')")
            print("━" * 60)
            result = await session.get_prompt("start_conversation", arguments={
                "platform": "windsurf",
                "topic": "React migration",
            })
            print(result.messages[0].content.text[:500])

            print("\n" + "━" * 60)
            print("Testing: recall_everything(topic='database optimization')")
            print("━" * 60)
            result = await session.get_prompt("recall_everything", arguments={
                "topic": "database optimization",
            })
            print(result.messages[0].content.text[:500])

            # Count tools too
            tools = await session.list_tools()
            print(f"\n✅ Total: {len(prompts.prompts)} prompts + {len(tools.tools)} tools = full power")

if __name__ == "__main__":
    asyncio.run(main())
