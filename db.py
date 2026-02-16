"""
Database layer for the LLM Memory MCP Server.
Handles connection pooling, schema initialization, and all query operations.
"""

import asyncpg
import os
import json
from datetime import datetime, timezone
from typing import Optional


_pool: Optional[asyncpg.Pool] = None

SCHEMA_SQL = """
-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(50) NOT NULL,
    title VARCHAR(500),
    summary TEXT,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages within conversations
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge entities
CREATE TABLE IF NOT EXISTS knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',
    source_platform VARCHAR(50),
    source_conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS idx_conversations_search
    ON conversations USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(summary,'')));
CREATE INDEX IF NOT EXISTS idx_messages_search
    ON messages USING GIN (to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS idx_knowledge_search
    ON knowledge USING GIN (to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS idx_conversations_platform
    ON conversations(platform);
CREATE INDEX IF NOT EXISTS idx_conversations_created
    ON conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_category
    ON knowledge(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_tags
    ON knowledge USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);
"""


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        database_url = os.environ.get("DATABASE_URL", "postgresql://mcp_user:mcp_secure_pass_2026@localhost:4569/mcp_memory")
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    return _pool


async def init_db():
    """Initialize the database schema."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)


async def close_db():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ─── Conversation Operations ────────────────────────────────────────────────

async def save_conversation(
    platform: str,
    messages: list[dict],
    title: Optional[str] = None,
    summary: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Save a conversation with its messages."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (platform, title, summary, tags, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, created_at
                """,
                platform,
                title,
                summary,
                tags or [],
                json.dumps(metadata or {}),
            )
            conv_id = row["id"]

            for msg in messages:
                await conn.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content, metadata)
                    VALUES ($1, $2, $3, $4)
                    """,
                    conv_id,
                    msg.get("role", "user"),
                    msg.get("content", ""),
                    json.dumps(msg.get("metadata", {})),
                )

            return {
                "id": str(conv_id),
                "platform": platform,
                "title": title,
                "message_count": len(messages),
                "created_at": row["created_at"].isoformat(),
            }


async def search_conversations(
    query: str,
    platform: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Full-text search across conversations and messages."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Search in conversations (title + summary) and messages
        sql = """
            WITH matched_convs AS (
                SELECT DISTINCT c.id, c.platform, c.title, c.summary, c.tags,
                       c.created_at, c.updated_at,
                       ts_rank(to_tsvector('english', coalesce(c.title,'') || ' ' || coalesce(c.summary,'')),
                               plainto_tsquery('english', $1)) AS conv_rank
                FROM conversations c
                WHERE to_tsvector('english', coalesce(c.title,'') || ' ' || coalesce(c.summary,''))
                      @@ plainto_tsquery('english', $1)

                UNION

                SELECT DISTINCT c.id, c.platform, c.title, c.summary, c.tags,
                       c.created_at, c.updated_at,
                       ts_rank(to_tsvector('english', m.content),
                               plainto_tsquery('english', $1)) AS conv_rank
                FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE to_tsvector('english', m.content) @@ plainto_tsquery('english', $1)
            )
            SELECT id, platform, title, summary, tags, created_at, updated_at,
                   MAX(conv_rank) as rank
            FROM matched_convs
        """
        params = [query]
        param_idx = 2

        if platform:
            sql += f" WHERE platform = ${param_idx}"
            params.append(platform)
            param_idx += 1

        sql += f" GROUP BY id, platform, title, summary, tags, created_at, updated_at"
        sql += f" ORDER BY rank DESC, created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(sql, *params)
        results = []
        for row in rows:
            # Fetch messages for each conversation
            msg_rows = await conn.fetch(
                "SELECT role, content, created_at FROM messages WHERE conversation_id = $1 ORDER BY created_at",
                row["id"],
            )
            results.append({
                "id": str(row["id"]),
                "platform": row["platform"],
                "title": row["title"],
                "summary": row["summary"],
                "tags": row["tags"],
                "created_at": row["created_at"].isoformat(),
                "messages": [
                    {"role": m["role"], "content": m["content"], "created_at": m["created_at"].isoformat()}
                    for m in msg_rows
                ],
            })
        return results


async def get_recent_conversations(
    platform: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Get most recent conversations."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sql = "SELECT id, platform, title, summary, tags, created_at FROM conversations"
        params = []
        param_idx = 1

        if platform:
            sql += f" WHERE platform = ${param_idx}"
            params.append(platform)
            param_idx += 1

        sql += f" ORDER BY created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(sql, *params)
        results = []
        for row in rows:
            msg_rows = await conn.fetch(
                "SELECT role, content, created_at FROM messages WHERE conversation_id = $1 ORDER BY created_at",
                row["id"],
            )
            results.append({
                "id": str(row["id"]),
                "platform": row["platform"],
                "title": row["title"],
                "summary": row["summary"],
                "tags": row["tags"],
                "created_at": row["created_at"].isoformat(),
                "messages": [
                    {"role": m["role"], "content": m["content"], "created_at": m["created_at"].isoformat()}
                    for m in msg_rows
                ],
            })
        return results


# ─── Knowledge Operations ───────────────────────────────────────────────────

async def save_knowledge(
    category: str,
    content: str,
    tags: Optional[list[str]] = None,
    source_platform: Optional[str] = None,
    source_conversation_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Save a knowledge entity."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv_id = None
        if source_conversation_id:
            try:
                import uuid
                conv_id = uuid.UUID(source_conversation_id)
            except ValueError:
                pass

        row = await conn.fetchrow(
            """
            INSERT INTO knowledge (category, content, tags, source_platform, source_conversation_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, created_at
            """,
            category,
            content,
            tags or [],
            source_platform,
            conv_id,
            json.dumps(metadata or {}),
        )
        return {
            "id": str(row["id"]),
            "category": category,
            "content": content[:100] + "..." if len(content) > 100 else content,
            "created_at": row["created_at"].isoformat(),
        }


async def search_knowledge(
    query: str,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 10,
) -> list[dict]:
    """Search knowledge entities."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sql = """
            SELECT id, category, content, tags, source_platform,
                   created_at, updated_at,
                   ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS rank
            FROM knowledge
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
        """
        params = [query]
        param_idx = 2

        if category:
            sql += f" AND category = ${param_idx}"
            params.append(category)
            param_idx += 1

        if tags:
            sql += f" AND tags && ${param_idx}"
            params.append(tags)
            param_idx += 1

        sql += f" ORDER BY rank DESC, created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(sql, *params)
        return [
            {
                "id": str(row["id"]),
                "category": row["category"],
                "content": row["content"],
                "tags": row["tags"],
                "source_platform": row["source_platform"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]


async def get_context_summary(
    topic: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """Get a summary of recent context for a topic."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get relevant knowledge
        knowledge_items = []
        if topic:
            k_rows = await conn.fetch(
                """
                SELECT category, content, tags, source_platform, created_at
                FROM knowledge
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                ORDER BY created_at DESC LIMIT $2
                """,
                topic, limit,
            )
            knowledge_items = [
                {"category": r["category"], "content": r["content"], "tags": r["tags"],
                 "source": r["source_platform"], "created_at": r["created_at"].isoformat()}
                for r in k_rows
            ]

        # Get recent conversations
        conv_sql = "SELECT id, platform, title, summary, tags, created_at FROM conversations"
        conv_params = []
        param_idx = 1

        conditions = []
        if topic:
            conditions.append(f"to_tsvector('english', coalesce(title,'') || ' ' || coalesce(summary,'')) @@ plainto_tsquery('english', ${param_idx})")
            conv_params.append(topic)
            param_idx += 1
        if platform:
            conditions.append(f"platform = ${param_idx}")
            conv_params.append(platform)
            param_idx += 1

        if conditions:
            conv_sql += " WHERE " + " AND ".join(conditions)

        conv_sql += f" ORDER BY created_at DESC LIMIT ${param_idx}"
        conv_params.append(limit)

        conv_rows = await conn.fetch(conv_sql, *conv_params)
        conversations = [
            {"id": str(r["id"]), "platform": r["platform"], "title": r["title"],
             "summary": r["summary"], "tags": r["tags"], "created_at": r["created_at"].isoformat()}
            for r in conv_rows
        ]

        return {
            "topic": topic,
            "platform_filter": platform,
            "knowledge_items": knowledge_items,
            "recent_conversations": conversations,
        }


# ─── Delete Operations ──────────────────────────────────────────────────────

async def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and its messages."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        import uuid
        try:
            cid = uuid.UUID(conversation_id)
        except ValueError:
            return False
        result = await conn.execute("DELETE FROM conversations WHERE id = $1", cid)
        return result == "DELETE 1"


async def delete_knowledge_entry(knowledge_id: str) -> bool:
    """Delete a knowledge entry."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        import uuid
        try:
            kid = uuid.UUID(knowledge_id)
        except ValueError:
            return False
        result = await conn.execute("DELETE FROM knowledge WHERE id = $1", kid)
        return result == "DELETE 1"


# ─── Stats ───────────────────────────────────────────────────────────────────

async def get_stats() -> dict:
    """Get database statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv_count = await conn.fetchval("SELECT COUNT(*) FROM conversations")
        msg_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
        knowledge_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge")
        platforms = await conn.fetch(
            "SELECT platform, COUNT(*) as count FROM conversations GROUP BY platform ORDER BY count DESC"
        )
        categories = await conn.fetch(
            "SELECT category, COUNT(*) as count FROM knowledge GROUP BY category ORDER BY count DESC"
        )
        return {
            "total_conversations": conv_count,
            "total_messages": msg_count,
            "total_knowledge_items": knowledge_count,
            "platforms": {r["platform"]: r["count"] for r in platforms},
            "knowledge_categories": {r["category"]: r["count"] for r in categories},
        }


async def get_platforms() -> list[str]:
    """Get list of all platforms that have stored conversations."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT platform FROM conversations ORDER BY platform")
        return [r["platform"] for r in rows]
