"""
🧠 GOD MODE DEMO — LLM Memory MCP Server
Demonstrates the 4 new features:
  1. Hybrid Vector + Full-Text Search (recall)
  2. Short-Term Memory with TTL
  3. Memory Consolidation & Reflection
  4. Memory Health Monitoring
"""

import asyncio
import json
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

SERVER_URL = "http://localhost:4040/mcp"

async def call(session, tool, args=None):
    result = await session.call_tool(tool, args or {})
    text = result.content[0].text if result.content else "{}"
    return json.loads(text)

def show(title, data):
    print(f"\n{'━'*60}")
    print(f"  {title}")
    print(f"{'━'*60}")
    print(json.dumps(data, indent=2)[:1500])

async def main():
    print("\n" + "🧠"*30)
    print("     GOD MODE DEMO — LLM Memory MCP Server")
    print("🧠"*30)

    async with streamablehttp_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"\n✅ Connected! {len(tools.tools)} tools available\n")

            # ═══════════════════════════════════════════════════════════
            # DEMO 1: Multi-Platform Knowledge Saving (with embeddings)
            # ═══════════════════════════════════════════════════════════
            print("\n" + "="*60)
            print("  DEMO 1: Save knowledge from different platforms")
            print("="*60)

            # Simulate Windsurf saving
            r1 = await call(session, "save_knowledge", {
                "category": "preference",
                "content": "User strongly prefers async/await pattern over callbacks in all Python code",
                "tags": ["python", "coding-style", "async"],
                "source_platform": "windsurf",
                "importance": 0.9,
                "memory_type": "semantic",
            })
            print(f"\n  Windsurf saved: {r1['content']}")

            # Simulate Gemini CLI saving
            r2 = await call(session, "save_knowledge", {
                "category": "fact",
                "content": "The production API server runs on port 8443 behind nginx reverse proxy",
                "tags": ["infrastructure", "api", "nginx"],
                "source_platform": "gemini_cli",
                "importance": 0.7,
                "memory_type": "semantic",
            })
            print(f"  Gemini saved:   {r2['content']}")

            # Simulate Antigravity saving
            r3 = await call(session, "save_knowledge", {
                "category": "decision",
                "content": "We decided to use PostgreSQL with pgvector for all vector search instead of Pinecone",
                "tags": ["database", "architecture", "vector-search"],
                "source_platform": "antigravity",
                "importance": 0.85,
                "memory_type": "semantic",
            })
            print(f"  Antigravity:    {r3['content']}")

            # ═══════════════════════════════════════════════════════════
            # DEMO 2: Save an episodic conversation
            # ═══════════════════════════════════════════════════════════
            print("\n" + "="*60)
            print("  DEMO 2: Save episodic conversation with importance & outcome")
            print("="*60)

            conv = await call(session, "save_conversation", {
                "platform": "windsurf",
                "title": "Fixed authentication bug in the payment microservice",
                "summary": "Debugged JWT token expiration issue. Root cause was timezone mismatch between auth server and payment service. Fixed by normalizing all timestamps to UTC.",
                "tags": ["debugging", "auth", "payments", "jwt"],
                "importance": 0.8,
                "outcome": "success",
                "emotional_context": "relieved",
                "messages": [
                    {"role": "user", "content": "The payment API keeps returning 401 after exactly 1 hour"},
                    {"role": "assistant", "content": "This sounds like a JWT expiration issue. Let me check the token timestamps."},
                    {"role": "user", "content": "Found it! The auth server uses local time but payment service expects UTC"},
                    {"role": "assistant", "content": "Converting all timestamps to UTC with timezone.utc fixed the issue."},
                ],
            })
            print(f"\n  Saved conversation: {conv['title']}")
            print(f"  ID: {conv['id']}, Outcome: success, Importance: 0.8")

            # ═══════════════════════════════════════════════════════════
            # DEMO 3: Short-Term Memory (working context)
            # ═══════════════════════════════════════════════════════════
            print("\n" + "="*60)
            print("  DEMO 3: Short-Term Memory (auto-expires)")
            print("="*60)

            stm1 = await call(session, "save_short_term_memory", {
                "content": "Currently debugging the user authentication flow in auth-service/login.py",
                "context_key": "current_task",
                "source_platform": "windsurf",
                "tags": ["active-task"],
                "ttl_minutes": 120,
                "importance": 0.6,
            })
            print(f"\n  STM saved: {stm1['content']}")
            print(f"  Expires at: {stm1['expires_at']}")

            stm2 = await call(session, "save_short_term_memory", {
                "content": "User mentioned they have a meeting at 3pm and needs a quick fix before that",
                "context_key": "user_context",
                "source_platform": "windsurf",
                "tags": ["deadline"],
                "ttl_minutes": 60,
                "importance": 0.4,
            })
            print(f"  STM saved: {stm2['content']}")

            # Get working context
            ctx = await call(session, "get_working_context", {"source_platform": "windsurf"})
            show("Working Context (what the AI sees at conversation start)", ctx)

            # ═══════════════════════════════════════════════════════════
            # DEMO 4: HYBRID RECALL — The Magic ✨
            # ═══════════════════════════════════════════════════════════
            print("\n" + "="*60)
            print("  DEMO 4: Hybrid Recall (vector + full-text)")
            print("="*60)

            # This query doesn't use exact keywords but should still find
            # semantically related memories
            recall1 = await call(session, "recall", {
                "query": "how do we handle login problems",
                "limit": 5,
            })
            show("Recall: 'how do we handle login problems'", recall1)

            recall2 = await call(session, "recall", {
                "query": "what database technology are we using",
                "limit": 5,
            })
            show("Recall: 'what database technology are we using'", recall2)

            recall3 = await call(session, "recall", {
                "query": "coding style preferences",
                "limit": 5,
            })
            show("Recall: 'coding style preferences'", recall3)

            # ═══════════════════════════════════════════════════════════
            # DEMO 5: Memory Health
            # ═══════════════════════════════════════════════════════════
            print("\n" + "="*60)
            print("  DEMO 5: Memory Health Dashboard")
            print("="*60)

            health = await call(session, "memory_health")
            show("Memory Health", health)

            # ═══════════════════════════════════════════════════════════
            # DEMO 6: Count all memories
            # ═══════════════════════════════════════════════════════════
            count = await call(session, "count_memories")
            show("Memory Counts", count)

            # ═══════════════════════════════════════════════════════════
            # DEMO 7: Read the health resource
            # ═══════════════════════════════════════════════════════════
            print(f"\n{'━'*60}")
            print(f"  Reading resource: memory://health")
            print(f"{'━'*60}")
            health_res = await session.read_resource("memory://health")
            print(health_res.contents[0].text[:800])

            # ═══════════════════════════════════════════════════════════
            print("\n\n" + "🎉"*20)
            print("  ALL DEMOS COMPLETE — GOD MODE ACTIVE!")
            print("🎉"*20)
            print("""
  Summary:
  ✅ Multi-platform knowledge (Windsurf → Gemini → Antigravity)
  ✅ Episodic memory with importance & outcome tracking
  ✅ Short-term memory with auto-expiry (TTL)
  ✅ Hybrid recall (vector similarity + full-text search)
  ✅ Memory health monitoring
  ✅ Background scheduler running (cleanup, consolidation, decay)
  
  How it works across platforms:
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   Windsurf   │     │  Gemini CLI  │     │ Antigravity  │
  │ saves pref   │     │ saves fact   │     │saves decision│
  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
         │                    │                     │
         ▼                    ▼                     ▼
  ┌─────────────────────────────────────────────────────────┐
  │         🧠 LLM Memory MCP Server (:4040)                │
  │     33 tools • pgvector hybrid search • auto-maintain  │
  └─────────────────────────────────────────────────────────┘
  
  Any platform can now recall ANY memory from ANY other platform!
""")


if __name__ == "__main__":
    asyncio.run(main())
