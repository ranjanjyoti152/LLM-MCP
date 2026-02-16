"""
Database layer for the LLM Memory MCP Server.
Handles connection pooling, schema initialization, and all query operations.
"""

import asyncpg
import os
import json
import re
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

-- Code snippets table
CREATE TABLE IF NOT EXISTS code_snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    language VARCHAR(50) NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    tags TEXT[] DEFAULT '{}',
    source_platform VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    tech_stack TEXT[] DEFAULT '{}',
    repo_url VARCHAR(500),
    context JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    source_platform VARCHAR(50),
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
CREATE INDEX IF NOT EXISTS idx_conversations_tags
    ON conversations USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_code_snippets_search
    ON code_snippets USING GIN (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || code));
CREATE INDEX IF NOT EXISTS idx_code_snippets_language
    ON code_snippets(language);
CREATE INDEX IF NOT EXISTS idx_code_snippets_tags
    ON code_snippets USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_projects_search
    ON projects USING GIN (to_tsvector('english', coalesce(name,'') || ' ' || coalesce(description,'')));
CREATE INDEX IF NOT EXISTS idx_projects_name
    ON projects(name);
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


# ─── Auto-Extract Preferences ──────────────────────────────────────────────


# Keywords that indicate each category
_PREFERENCE_KEYWORDS = re.compile(
    r'\b(prefer|like|love|enjoy|favor|want|choose|rather|my favorite|i use|i always)\b',
    re.IGNORECASE,
)
_INSTRUCTION_KEYWORDS = re.compile(
    r'\b(always|never|must|should|don\'t|do not|make sure|ensure|avoid|remember to)\b',
    re.IGNORECASE,
)
_DECISION_KEYWORDS = re.compile(
    r'\b(decided|decision|chose|chosen|agreed|we will|going to|settled on|switched to|migrated to)\b',
    re.IGNORECASE,
)


def _classify_statement(text: str) -> str:
    """Classify a statement into a knowledge category."""
    if _PREFERENCE_KEYWORDS.search(text):
        return "preference"
    if _INSTRUCTION_KEYWORDS.search(text):
        return "instruction"
    if _DECISION_KEYWORDS.search(text):
        return "decision"
    return "fact"


def _extract_statements(text: str) -> list[str]:
    """Split text into individual meaningful statements."""
    # Handle bullet points, numbered lists, and newline-separated items
    lines = re.split(r'\n+', text.strip())
    statements = []
    for line in lines:
        # Strip bullet markers: -, *, •, numbered (1., 2.), etc.
        line = re.sub(r'^\s*[-*•]\s*', '', line)
        line = re.sub(r'^\s*\d+[.)]\s*', '', line)
        line = line.strip()
        if not line or len(line) < 10:
            continue
        # If a line has multiple sentences, split them
        sentences = re.split(r'(?<=[.!?])\s+', line)
        for s in sentences:
            s = s.strip()
            if len(s) >= 10:
                statements.append(s)
    return statements


def _extract_tags(text: str) -> list[str]:
    """Extract relevant tags from a statement."""
    tag_patterns = {
        "python": r'\bpython\b',
        "javascript": r'\bjavascript|js|node\.?js|typescript|ts\b',
        "docker": r'\bdocker\b',
        "postgresql": r'\bpostgre(?:sql|s)?\b',
        "react": r'\breact\b',
        "aws": r'\baws\b',
        "linux": r'\blinux\b',
        "git": r'\bgit(?:hub|lab)?\b',
        "api": r'\bapi|rest|graphql\b',
        "database": r'\bdatabase|db|sql|mysql|mongo\b',
        "testing": r'\btest(?:ing|s)?\b',
        "deployment": r'\bdeploy(?:ment|ing)?\b',
        "security": r'\bsecurity|auth(?:entication)?\b',
        "frontend": r'\bfrontend|front-end|css|html\b',
        "backend": r'\bbackend|back-end|server\b',
        "devops": r'\bdevops|ci/?cd|pipeline\b',
        "ai": r'\bai|ml|llm|machine.learning\b',
        "coding-style": r'\bstyle|convention|pattern|clean.code\b',
    }
    tags = []
    lower = text.lower()
    for tag, pattern in tag_patterns.items():
        if re.search(pattern, lower):
            tags.append(tag)
    return tags


async def save_knowledge_if_new(
    category: str,
    content: str,
    tags: Optional[list[str]] = None,
    source_platform: Optional[str] = None,
) -> dict:
    """Save a knowledge entry only if a near-duplicate doesn't already exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check for existing similar entries using full-text search
        existing = await conn.fetchval(
            """
            SELECT id FROM knowledge
            WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
            AND category = $2
            LIMIT 1
            """,
            content, category,
        )
        if existing:
            return {"status": "skipped", "reason": "duplicate", "existing_id": str(existing)}

        # No duplicate — save it
        row = await conn.fetchrow(
            """
            INSERT INTO knowledge (category, content, tags, source_platform, metadata)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, created_at
            """,
            category,
            content,
            tags or [],
            source_platform,
            json.dumps({}),
        )
        return {
            "status": "saved",
            "id": str(row["id"]),
            "category": category,
            "content": content[:100] + "..." if len(content) > 100 else content,
            "created_at": row["created_at"].isoformat(),
        }


async def extract_and_save_preferences(
    text: str,
    source_platform: Optional[str] = None,
) -> dict:
    """Extract preference-like statements from text and save each as deduplicated knowledge."""
    statements = _extract_statements(text)
    saved = []
    skipped = []

    for statement in statements:
        category = _classify_statement(statement)
        tags = _extract_tags(statement)
        if source_platform:
            tags.append(source_platform)

        result = await save_knowledge_if_new(
            category=category,
            content=statement,
            tags=list(set(tags)),
            source_platform=source_platform,
        )

        if result["status"] == "saved":
            saved.append(result)
        else:
            skipped.append({"content": statement[:80], "reason": result["reason"]})

    return {
        "total_extracted": len(statements),
        "newly_saved": len(saved),
        "duplicates_skipped": len(skipped),
        "saved_entries": saved,
        "skipped_entries": skipped,
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


# ─── New Tool Functions ──────────────────────────────────────────────────────

import uuid as _uuid


async def update_knowledge(
    knowledge_id: str,
    content: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Update an existing knowledge entry."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            kid = _uuid.UUID(knowledge_id)
        except ValueError:
            return {"error": "Invalid UUID"}
        existing = await conn.fetchrow("SELECT * FROM knowledge WHERE id = $1", kid)
        if not existing:
            return {"error": "Not found"}
        new_content = content if content is not None else existing["content"]
        new_category = category if category is not None else existing["category"]
        new_tags = tags if tags is not None else existing["tags"]
        await conn.execute(
            "UPDATE knowledge SET content=$1, category=$2, tags=$3, updated_at=NOW() WHERE id=$4",
            new_content, new_category, new_tags, kid,
        )
        return {"id": str(kid), "status": "updated", "content": new_content[:100], "category": new_category}


async def list_all_knowledge(
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List all knowledge entries, optionally filtered by category."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        count_sql = "SELECT COUNT(*) FROM knowledge"
        sql = "SELECT id, category, content, tags, source_platform, created_at FROM knowledge"
        params = []
        param_idx = 1
        if category:
            count_sql += f" WHERE category = ${param_idx}"
            sql += f" WHERE category = ${param_idx}"
            params.append(category)
            param_idx += 1
        total = await conn.fetchval(count_sql, *params)
        sql += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])
        rows = await conn.fetch(sql, *params)
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {"id": str(r["id"]), "category": r["category"], "content": r["content"],
                 "tags": r["tags"], "source_platform": r["source_platform"],
                 "created_at": r["created_at"].isoformat()}
                for r in rows
            ],
        }


async def get_conversation_by_id(conversation_id: str) -> Optional[dict]:
    """Get a specific conversation by its UUID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            cid = _uuid.UUID(conversation_id)
        except ValueError:
            return None
        row = await conn.fetchrow(
            "SELECT id, platform, title, summary, tags, metadata, created_at, updated_at FROM conversations WHERE id = $1", cid
        )
        if not row:
            return None
        msg_rows = await conn.fetch(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = $1 ORDER BY created_at", cid
        )
        return {
            "id": str(row["id"]),
            "platform": row["platform"],
            "title": row["title"],
            "summary": row["summary"],
            "tags": row["tags"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "messages": [
                {"id": str(m["id"]), "role": m["role"], "content": m["content"], "created_at": m["created_at"].isoformat()}
                for m in msg_rows
            ],
        }


async def add_messages_to_conversation(conversation_id: str, messages: list[dict]) -> dict:
    """Append messages to an existing conversation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            cid = _uuid.UUID(conversation_id)
        except ValueError:
            return {"error": "Invalid UUID"}
        existing = await conn.fetchval("SELECT id FROM conversations WHERE id = $1", cid)
        if not existing:
            return {"error": "Conversation not found"}
        async with conn.transaction():
            for msg in messages:
                await conn.execute(
                    "INSERT INTO messages (conversation_id, role, content, metadata) VALUES ($1, $2, $3, $4)",
                    cid, msg.get("role", "user"), msg.get("content", ""), json.dumps(msg.get("metadata", {})),
                )
            await conn.execute("UPDATE conversations SET updated_at = NOW() WHERE id = $1", cid)
        total = await conn.fetchval("SELECT COUNT(*) FROM messages WHERE conversation_id = $1", cid)
        return {"id": str(cid), "added": len(messages), "total_messages": total}


async def update_conversation_tags(conversation_id: str, add_tags: list[str] = None, remove_tags: list[str] = None) -> dict:
    """Add or remove tags from a conversation."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            cid = _uuid.UUID(conversation_id)
        except ValueError:
            return {"error": "Invalid UUID"}
        row = await conn.fetchrow("SELECT tags FROM conversations WHERE id = $1", cid)
        if not row:
            return {"error": "Conversation not found"}
        current_tags = set(row["tags"] or [])
        if add_tags:
            current_tags.update(add_tags)
        if remove_tags:
            current_tags -= set(remove_tags)
        new_tags = sorted(current_tags)
        await conn.execute("UPDATE conversations SET tags = $1, updated_at = NOW() WHERE id = $2", new_tags, cid)
        return {"id": str(cid), "tags": new_tags}


async def get_knowledge_by_category(category: str, limit: int = 50) -> list[dict]:
    """Get all knowledge entries in a specific category."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, category, content, tags, source_platform, created_at FROM knowledge WHERE category = $1 ORDER BY created_at DESC LIMIT $2",
            category, limit,
        )
        return [
            {"id": str(r["id"]), "category": r["category"], "content": r["content"],
             "tags": r["tags"], "source_platform": r["source_platform"],
             "created_at": r["created_at"].isoformat()}
            for r in rows
        ]


async def summarize_platform_activity(platform: str) -> dict:
    """Get activity summary for a specific platform."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv_count = await conn.fetchval("SELECT COUNT(*) FROM conversations WHERE platform = $1", platform)
        msg_count = await conn.fetchval(
            "SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE c.platform = $1", platform
        )
        knowledge_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge WHERE source_platform = $1", platform)
        snippet_count = await conn.fetchval("SELECT COUNT(*) FROM code_snippets WHERE source_platform = $1", platform)
        recent = await conn.fetch(
            "SELECT title, summary, created_at FROM conversations WHERE platform = $1 ORDER BY created_at DESC LIMIT 5", platform
        )
        top_tags = await conn.fetch(
            "SELECT unnest(tags) as tag, COUNT(*) as cnt FROM conversations WHERE platform = $1 GROUP BY tag ORDER BY cnt DESC LIMIT 10", platform
        )
        return {
            "platform": platform,
            "conversations": conv_count,
            "messages": msg_count,
            "knowledge_items": knowledge_count,
            "code_snippets": snippet_count,
            "recent_conversations": [
                {"title": r["title"], "summary": r["summary"], "created_at": r["created_at"].isoformat()}
                for r in recent
            ],
            "top_tags": {r["tag"]: r["cnt"] for r in top_tags},
        }


async def export_all_memories() -> dict:
    """Export all data as JSON for backup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        convs = await conn.fetch("SELECT * FROM conversations ORDER BY created_at")
        msgs = await conn.fetch("SELECT * FROM messages ORDER BY created_at")
        knowledge = await conn.fetch("SELECT * FROM knowledge ORDER BY created_at")
        snippets = await conn.fetch("SELECT * FROM code_snippets ORDER BY created_at")
        projects = await conn.fetch("SELECT * FROM projects ORDER BY created_at")

        def row_to_dict(r):
            d = dict(r)
            for k, v in d.items():
                if isinstance(v, _uuid.UUID):
                    d[k] = str(v)
                elif hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            return d

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "conversations": [row_to_dict(r) for r in convs],
            "messages": [row_to_dict(r) for r in msgs],
            "knowledge": [row_to_dict(r) for r in knowledge],
            "code_snippets": [row_to_dict(r) for r in snippets],
            "projects": [row_to_dict(r) for r in projects],
        }


async def import_memories(data: dict) -> dict:
    """Import data from a JSON backup."""
    pool = await get_pool()
    counts = {"conversations": 0, "messages": 0, "knowledge": 0, "code_snippets": 0, "projects": 0}
    async with pool.acquire() as conn:
        async with conn.transaction():
            for conv in data.get("conversations", []):
                try:
                    await conn.execute(
                        "INSERT INTO conversations (id, platform, title, summary, tags, metadata, created_at, updated_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING",
                        _uuid.UUID(conv["id"]), conv.get("platform",""), conv.get("title"), conv.get("summary"),
                        conv.get("tags",[]), conv.get("metadata","{}"), conv.get("created_at"), conv.get("updated_at"),
                    )
                    counts["conversations"] += 1
                except Exception:
                    pass
            for msg in data.get("messages", []):
                try:
                    await conn.execute(
                        "INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (id) DO NOTHING",
                        _uuid.UUID(msg["id"]), _uuid.UUID(msg["conversation_id"]), msg.get("role","user"),
                        msg.get("content",""), msg.get("metadata","{}"), msg.get("created_at"),
                    )
                    counts["messages"] += 1
                except Exception:
                    pass
            for k in data.get("knowledge", []):
                try:
                    conv_id = _uuid.UUID(k["source_conversation_id"]) if k.get("source_conversation_id") else None
                    await conn.execute(
                        "INSERT INTO knowledge (id, category, content, tags, source_platform, source_conversation_id, metadata, created_at, updated_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (id) DO NOTHING",
                        _uuid.UUID(k["id"]), k.get("category","fact"), k.get("content",""),
                        k.get("tags",[]), k.get("source_platform"), conv_id,
                        k.get("metadata","{}"), k.get("created_at"), k.get("updated_at"),
                    )
                    counts["knowledge"] += 1
                except Exception:
                    pass
            for s in data.get("code_snippets", []):
                try:
                    await conn.execute(
                        "INSERT INTO code_snippets (id, title, language, code, description, tags, source_platform, created_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING",
                        _uuid.UUID(s["id"]), s.get("title",""), s.get("language",""), s.get("code",""),
                        s.get("description"), s.get("tags",[]), s.get("source_platform"), s.get("created_at"),
                    )
                    counts["code_snippets"] += 1
                except Exception:
                    pass
            for p in data.get("projects", []):
                try:
                    await conn.execute(
                        "INSERT INTO projects (id, name, description, tech_stack, repo_url, context, tags, source_platform, created_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (id) DO NOTHING",
                        _uuid.UUID(p["id"]), p.get("name",""), p.get("description"), p.get("tech_stack",[]),
                        p.get("repo_url"), p.get("context","{}"), p.get("tags",[]), p.get("source_platform"), p.get("created_at"),
                    )
                    counts["projects"] += 1
                except Exception:
                    pass
    return {"status": "imported", "counts": counts}


async def count_memories() -> dict:
    """Quick count of all memory types."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {
            "conversations": await conn.fetchval("SELECT COUNT(*) FROM conversations"),
            "messages": await conn.fetchval("SELECT COUNT(*) FROM messages"),
            "knowledge": await conn.fetchval("SELECT COUNT(*) FROM knowledge"),
            "code_snippets": await conn.fetchval("SELECT COUNT(*) FROM code_snippets"),
            "projects": await conn.fetchval("SELECT COUNT(*) FROM projects"),
        }


async def search_by_tags(tags: list[str], limit: int = 20) -> dict:
    """Search conversations and knowledge by tags."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv_rows = await conn.fetch(
            "SELECT id, platform, title, summary, tags, created_at FROM conversations WHERE tags && $1 ORDER BY created_at DESC LIMIT $2",
            tags, limit,
        )
        k_rows = await conn.fetch(
            "SELECT id, category, content, tags, source_platform, created_at FROM knowledge WHERE tags && $1 ORDER BY created_at DESC LIMIT $2",
            tags, limit,
        )
        snippet_rows = await conn.fetch(
            "SELECT id, title, language, description, tags, created_at FROM code_snippets WHERE tags && $1 ORDER BY created_at DESC LIMIT $2",
            tags, limit,
        )
        return {
            "searched_tags": tags,
            "conversations": [
                {"id": str(r["id"]), "platform": r["platform"], "title": r["title"],
                 "summary": r["summary"], "tags": r["tags"], "created_at": r["created_at"].isoformat()}
                for r in conv_rows
            ],
            "knowledge": [
                {"id": str(r["id"]), "category": r["category"], "content": r["content"],
                 "tags": r["tags"], "created_at": r["created_at"].isoformat()}
                for r in k_rows
            ],
            "code_snippets": [
                {"id": str(r["id"]), "title": r["title"], "language": r["language"],
                 "description": r["description"], "tags": r["tags"], "created_at": r["created_at"].isoformat()}
                for r in snippet_rows
            ],
        }


async def get_related_knowledge(knowledge_id: str, limit: int = 10) -> list[dict]:
    """Find knowledge entries related to a given one (by shared tags and content similarity)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            kid = _uuid.UUID(knowledge_id)
        except ValueError:
            return []
        source = await conn.fetchrow("SELECT content, tags FROM knowledge WHERE id = $1", kid)
        if not source:
            return []
        rows = await conn.fetch(
            """
            SELECT id, category, content, tags, source_platform, created_at,
                   ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS rank
            FROM knowledge
            WHERE id != $2
              AND (to_tsvector('english', content) @@ plainto_tsquery('english', $1) OR tags && $3)
            ORDER BY rank DESC, created_at DESC LIMIT $4
            """,
            source["content"][:200], kid, source["tags"] or [], limit,
        )
        return [
            {"id": str(r["id"]), "category": r["category"], "content": r["content"],
             "tags": r["tags"], "source_platform": r["source_platform"],
             "relevance": float(r["rank"]), "created_at": r["created_at"].isoformat()}
            for r in rows
        ]


async def clear_platform_data(platform: str) -> dict:
    """Delete all data for a specific platform."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            conv_del = await conn.execute("DELETE FROM conversations WHERE platform = $1", platform)
            k_del = await conn.execute("DELETE FROM knowledge WHERE source_platform = $1", platform)
            s_del = await conn.execute("DELETE FROM code_snippets WHERE source_platform = $1", platform)
            p_del = await conn.execute("DELETE FROM projects WHERE source_platform = $1", platform)
            return {
                "platform": platform,
                "deleted_conversations": int(conv_del.split()[-1]) if conv_del else 0,
                "deleted_knowledge": int(k_del.split()[-1]) if k_del else 0,
                "deleted_snippets": int(s_del.split()[-1]) if s_del else 0,
                "deleted_projects": int(p_del.split()[-1]) if p_del else 0,
            }


async def save_code_snippet(
    title: str,
    language: str,
    code: str,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source_platform: Optional[str] = None,
) -> dict:
    """Save a reusable code snippet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO code_snippets (title, language, code, description, tags, source_platform) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id, created_at",
            title, language.lower(), code, description, tags or [], source_platform,
        )
        return {"id": str(row["id"]), "title": title, "language": language, "created_at": row["created_at"].isoformat()}


async def search_code_snippets(
    query: str,
    language: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 10,
) -> list[dict]:
    """Search code snippets by keyword, language, or tags."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sql = """
            SELECT id, title, language, code, description, tags, source_platform, created_at,
                   ts_rank(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || code),
                           plainto_tsquery('english', $1)) AS rank
            FROM code_snippets
            WHERE to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || code) @@ plainto_tsquery('english', $1)
        """
        params = [query]
        param_idx = 2
        if language:
            sql += f" AND language = ${param_idx}"
            params.append(language.lower())
            param_idx += 1
        if tags:
            sql += f" AND tags && ${param_idx}"
            params.append(tags)
            param_idx += 1
        sql += f" ORDER BY rank DESC, created_at DESC LIMIT ${param_idx}"
        params.append(limit)
        rows = await conn.fetch(sql, *params)
        return [
            {"id": str(r["id"]), "title": r["title"], "language": r["language"],
             "code": r["code"], "description": r["description"], "tags": r["tags"],
             "source_platform": r["source_platform"], "created_at": r["created_at"].isoformat()}
            for r in rows
        ]


async def save_project_context(
    name: str,
    description: Optional[str] = None,
    tech_stack: Optional[list[str]] = None,
    repo_url: Optional[str] = None,
    context: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    source_platform: Optional[str] = None,
) -> dict:
    """Save or update project context. Upserts by project name."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO projects (name, description, tech_stack, repo_url, context, tags, source_platform)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (name) DO UPDATE SET
                description = COALESCE(EXCLUDED.description, projects.description),
                tech_stack = CASE WHEN EXCLUDED.tech_stack = '{}' THEN projects.tech_stack ELSE EXCLUDED.tech_stack END,
                repo_url = COALESCE(EXCLUDED.repo_url, projects.repo_url),
                context = projects.context || EXCLUDED.context,
                tags = ARRAY(SELECT DISTINCT unnest(projects.tags || EXCLUDED.tags)),
                source_platform = COALESCE(EXCLUDED.source_platform, projects.source_platform),
                updated_at = NOW()
            RETURNING id, created_at, updated_at
            """,
            name, description, tech_stack or [], repo_url,
            json.dumps(context or {}), tags or [], source_platform,
        )
        return {"id": str(row["id"]), "name": name, "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat()}


async def get_project_context(name: str) -> Optional[dict]:
    """Get all context for a project by name."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM projects WHERE name = $1", name)
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "tech_stack": row["tech_stack"],
            "repo_url": row["repo_url"],
            "context": json.loads(row["context"]) if row["context"] else {},
            "tags": row["tags"],
            "source_platform": row["source_platform"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
