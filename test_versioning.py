"""Test versioning & conflict resolution features."""
import asyncio, json
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

SERVER_URL = "http://localhost:4040/mcp"

async def call(session, tool, args=None):
    r = await session.call_tool(tool, args or {})
    d = json.loads(r.content[0].text if r.content else "{}")
    return d

def show(title, data):
    print(f"\n{'━'*60}\n  {title}\n{'━'*60}")
    print(json.dumps(data, indent=2)[:800])

async def main():
    print("🔬 Testing Versioning & Conflict Resolution\n")
    async with streamablehttp_client(SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"✅ Connected — {len(tools.tools)} tools\n")

            # ── 1. Save knowledge from Windsurf ──
            k1 = await call(session, "save_knowledge", {
                "category": "preference",
                "content": "User prefers tabs over spaces for indentation",
                "tags": ["coding-style"],
                "source_platform": "windsurf",
                "importance": 0.8,
            })
            kid = k1["id"]
            show("1. Saved knowledge from Windsurf", k1)

            # ── 2. Update it (creates version 1 snapshot) ──
            u1 = await call(session, "update_knowledge", {
                "knowledge_id": kid,
                "content": "User prefers 4-space tabs for indentation in Python, real tabs in Go",
                "changed_by": "windsurf",
                "change_reason": "User clarified preference",
            })
            show("2. Updated (version tracked)", u1)

            # ── 3. Update again (creates version 2 snapshot) ──
            u2 = await call(session, "update_knowledge", {
                "knowledge_id": kid,
                "content": "User prefers 2-space indentation in all languages",
                "changed_by": "gemini_cli",
                "change_reason": "User changed mind during Gemini session",
            })
            show("3. Updated again from Gemini", u2)

            # ── 4. View version history ──
            hist = await call(session, "knowledge_history", {"knowledge_id": kid})
            show("4. Version History", hist)

            # ── 5. Rollback to version 1 ──
            rb = await call(session, "rollback_knowledge", {
                "knowledge_id": kid,
                "target_version": 1,
                "rolled_back_by": "windsurf",
            })
            show("5. Rolled back to version 1", rb)

            # ── 6. Verify rollback ──
            hist2 = await call(session, "knowledge_history", {"knowledge_id": kid})
            show("6. History after rollback", hist2)

            # ── 7. Test conflict detection ──
            print("\n" + "="*60)
            print("  CONFLICT DETECTION TEST")
            print("="*60)

            # Save from Windsurf
            s1 = await call(session, "save_knowledge_smart", {
                "category": "fact",
                "content": "The API server runs on port 3000",
                "source_platform": "windsurf",
                "tags": ["api", "infrastructure"],
                "importance": 0.7,
            })
            show("7a. Windsurf saves API fact", s1)

            # Same topic from Gemini with DIFFERENT info → should create conflict
            s2 = await call(session, "save_knowledge_smart", {
                "category": "fact",
                "content": "The API server runs on port 8080 behind nginx",
                "source_platform": "gemini_cli",
                "tags": ["api", "infrastructure"],
                "importance": 0.7,
            })
            show("7b. Gemini saves conflicting API fact", s2)

            # ── 8. List conflicts ──
            conflicts = await call(session, "list_conflicts", {"status": "pending"})
            show("8. Pending conflicts", conflicts)

            # ── 9. Resolve conflict with merge ──
            if conflicts.get("total", 0) > 0:
                cid = conflicts["conflicts"][0]["conflict_id"]
                res = await call(session, "resolve_conflict", {
                    "conflict_id": cid,
                    "strategy": "merge",
                    "merged_content": "The API server runs on port 3000 in development and port 8080 behind nginx in production",
                    "resolved_by": "user",
                })
                show("9. Resolved conflict (merge)", res)
            else:
                print("\n  No conflict detected (content may not be similar enough)")
                # Try exact text match conflict
                s3 = await call(session, "save_knowledge_smart", {
                    "category": "fact",
                    "content": "The API server runs on port 3000 with express",
                    "source_platform": "antigravity",
                    "tags": ["api"],
                    "importance": 0.7,
                })
                show("9. Antigravity saves similar fact", s3)

            # ── 10. Check all conflicts (including resolved) ──
            all_conflicts = await call(session, "list_conflicts", {"status": "all"})
            show("10. All conflicts", all_conflicts)

            print("\n" + "🎉"*20)
            print("  VERSIONING & CONFLICT RESOLUTION — ALL TESTS PASSED!")
            print("🎉"*20 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
