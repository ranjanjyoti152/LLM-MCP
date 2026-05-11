"""
Advanced Memory Dashboard — REST API + Static File Server
=========================================================
Serves the web dashboard UI and provides REST endpoints for
visualizing and managing all memory data.
"""

import asyncio
import json
import os
from datetime import datetime, timezone

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.routing import Route

import db

DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "4041"))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _json(data, status=200):
    return JSONResponse(data, status_code=status)


def _ser(row, keys=None):
    """Serialize an asyncpg Record to dict."""
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif hasattr(v, '__str__') and type(v).__name__ == 'UUID':
            d[k] = str(v)
    if keys:
        d = {k: d[k] for k in keys if k in d}
    return d


# ─── API Endpoints ──────────────────────────────────────────────────────────

async def api_health(request):
    result = await db.get_memory_health()
    return _json(result)


async def api_stats(request):
    result = await db.get_stats()
    return _json(result)


async def api_counts(request):
    result = await db.count_memories()
    return _json(result)


async def api_platforms(request):
    platforms = await db.get_platforms()
    return _json({"platforms": platforms})


async def api_knowledge(request):
    search = request.query_params.get("search", "")
    category = request.query_params.get("category", "")
    limit = int(request.query_params.get("limit", "50"))
    offset = int(request.query_params.get("offset", "0"))

    if search:
        results = await db.search_knowledge(
            query=search,
            category=category or None,
            limit=limit,
        )
        return _json({"items": results, "total": len(results)})
    else:
        result = await db.list_all_knowledge(
            category=category or None,
            limit=limit,
            offset=offset,
        )
        return _json(result)


async def api_knowledge_detail(request):
    kid = request.path_params["id"]
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, category, content, memory_type, tags, source_platform,
                      importance, confidence, access_count, version,
                      created_at, updated_at
               FROM knowledge WHERE id = $1::uuid""",
            kid,
        )
        if not row:
            return _json({"error": "Not found"}, 404)
        return _json(_ser(row))


async def api_knowledge_history(request):
    kid = request.path_params["id"]
    result = await db.get_knowledge_history(kid)
    return _json(result)


async def api_conversations(request):
    platform = request.query_params.get("platform", "")
    limit = int(request.query_params.get("limit", "30"))
    offset = int(request.query_params.get("offset", "0"))

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        sql = """SELECT id, platform, title, summary, tags, importance, outcome,
                        emotional_context, access_count, created_at, updated_at
                 FROM conversations"""
        params = []
        idx = 1
        if platform:
            sql += f" WHERE platform = ${idx}"
            params.append(platform)
            idx += 1
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM conversations" +
            (f" WHERE platform = $1" if platform else ""),
            *([platform] if platform else []),
        )
        sql += f" ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}"
        params.extend([limit, offset])
        rows = await conn.fetch(sql, *params)
        return _json({
            "items": [_ser(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        })


async def api_conversation_detail(request):
    cid = request.path_params["id"]
    result = await db.get_conversation_by_id(cid)
    if not result or "error" in result:
        return _json({"error": "Not found"}, 404)
    return _json(result)


async def api_short_term(request):
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, content, context_key, source_platform, tags,
                      importance, expires_at, consolidated, created_at
               FROM short_term_memory
               ORDER BY created_at DESC LIMIT 50"""
        )
        active = [_ser(r) for r in rows if not r["consolidated"]]
        consolidated = [_ser(r) for r in rows if r["consolidated"]]
        expired = [r for r in active
                   if datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc)]
        return _json({
            "active": [r for r in active if r not in expired],
            "expired": expired,
            "consolidated": consolidated,
            "total_active": len(active) - len(expired),
            "total_expired": len(expired),
            "total_consolidated": len(consolidated),
        })


async def api_code_snippets(request):
    search = request.query_params.get("search", "")
    language = request.query_params.get("language", "")
    limit = int(request.query_params.get("limit", "30"))

    if search:
        results = await db.search_code_snippets(
            query=search,
            language=language or None,
            limit=limit,
        )
        return _json({"items": results, "total": len(results)})
    else:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            sql = "SELECT id, title, language, code, description, tags, source_platform, importance, created_at FROM code_snippets"
            params = []
            idx = 1
            if language:
                sql += f" WHERE language = ${idx}"
                params.append(language)
                idx += 1
            sql += f" ORDER BY created_at DESC LIMIT ${idx}"
            params.append(limit)
            rows = await conn.fetch(sql, *params)
            return _json({"items": [_ser(r) for r in rows], "total": len(rows)})


async def api_conflicts(request):
    status = request.query_params.get("status", "pending")
    result = await db.list_conflicts(status=status, limit=50)
    return _json(result)


async def api_resolve_conflict(request):
    cid = request.path_params["id"]
    body = await request.json()
    result = await db.resolve_conflict(
        conflict_id=cid,
        strategy=body.get("strategy", "keep_existing"),
        merged_content=body.get("merged_content"),
        resolved_by=body.get("resolved_by", "dashboard"),
    )
    return _json(result)


async def api_maintenance_cleanup(request):
    result = await db.cleanup_expired_memories()
    return _json(result)


async def api_maintenance_consolidate(request):
    result = await db.consolidate_memories()
    return _json(result)


async def api_maintenance_decay(request):
    body = await request.json() if request.method == "POST" else {}
    factor = float(body.get("decay_factor", 0.95))
    result = await db.decay_memories(decay_factor=factor)
    return _json(result)


async def api_maintenance_compress(request):
    body = await request.json() if request.method == "POST" else {}
    days = int(body.get("older_than_days", 7))
    result = await db.reflect_and_compress(older_than_days=days)
    return _json(result)


async def api_timeline(request):
    """Recent activity across all memory types."""
    limit = int(request.query_params.get("limit", "20"))
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        events = []
        # Recent knowledge
        rows = await conn.fetch(
            "SELECT id, category AS title, content, source_platform, importance, created_at, 'knowledge' AS type FROM knowledge ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        for r in rows:
            events.append({**_ser(r), "memory_type": "semantic"})
        # Recent conversations
        rows = await conn.fetch(
            "SELECT id, title, summary AS content, platform AS source_platform, importance, created_at, 'conversation' AS type FROM conversations ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        for r in rows:
            events.append({**_ser(r), "memory_type": "episodic"})
        # Recent STM
        rows = await conn.fetch(
            "SELECT id, context_key AS title, content, source_platform, importance, created_at, 'short_term' AS type FROM short_term_memory ORDER BY created_at DESC LIMIT $1",
            limit,
        )
        for r in rows:
            events.append({**_ser(r), "memory_type": "short_term"})
        # Sort all by created_at desc
        events.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        return _json({"events": events[:limit]})


# ─── Dashboard HTML ─────────────────────────────────────────────────────────

async def serve_dashboard(request):
    return FileResponse("static/index.html", media_type="text/html")


# ─── App Setup ──────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await db.init_db()
    print(f"📊 Dashboard API ready on port {DASHBOARD_PORT}")
    yield


routes = [
    Route("/", serve_dashboard),
    Route("/api/health", api_health),
    Route("/api/stats", api_stats),
    Route("/api/counts", api_counts),
    Route("/api/platforms", api_platforms),
    Route("/api/knowledge", api_knowledge),
    Route("/api/knowledge/{id}", api_knowledge_detail),
    Route("/api/knowledge/{id}/history", api_knowledge_history),
    Route("/api/conversations", api_conversations),
    Route("/api/conversations/{id}", api_conversation_detail),
    Route("/api/short-term", api_short_term),
    Route("/api/code-snippets", api_code_snippets),
    Route("/api/conflicts", api_conflicts),
    Route("/api/conflicts/{id}/resolve", api_resolve_conflict, methods=["POST"]),
    Route("/api/maintenance/cleanup", api_maintenance_cleanup, methods=["POST"]),
    Route("/api/maintenance/consolidate", api_maintenance_consolidate, methods=["POST"]),
    Route("/api/maintenance/decay", api_maintenance_decay, methods=["POST"]),
    Route("/api/maintenance/compress", api_maintenance_compress, methods=["POST"]),
    Route("/api/timeline", api_timeline),
]

app = Starlette(routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=DASHBOARD_PORT)
