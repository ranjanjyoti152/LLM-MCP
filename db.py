"""
Database layer for the LLM Memory MCP Server.
Handles connection pooling, schema initialization, and all query operations.
"""

import asyncpg
import os
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import embeddings as emb


_pool: Optional[asyncpg.Pool] = None

SCHEMA_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Conversations table (episodic memory)
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(50) NOT NULL,
    title VARCHAR(500),
    summary TEXT,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    importance REAL DEFAULT 0.5,
    outcome VARCHAR(50) DEFAULT 'neutral',
    emotional_context VARCHAR(100) DEFAULT '',
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    embedding vector(512),
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

-- Knowledge entities (long-term semantic memory)
CREATE TABLE IF NOT EXISTS knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    memory_type VARCHAR(20) DEFAULT 'semantic',
    tags TEXT[] DEFAULT '{}',
    source_platform VARCHAR(50),
    source_conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    importance REAL DEFAULT 0.5,
    confidence REAL DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    embedding vector(512),
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Short-term / working memory (auto-expires)
CREATE TABLE IF NOT EXISTS short_term_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    context_key VARCHAR(200),
    source_platform VARCHAR(50),
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    importance REAL DEFAULT 0.3,
    expires_at TIMESTAMPTZ NOT NULL,
    consolidated BOOLEAN DEFAULT FALSE,
    consolidated_into UUID,
    embedding vector(512),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Code snippets table (procedural memory)
CREATE TABLE IF NOT EXISTS code_snippets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    language VARCHAR(50) NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    tags TEXT[] DEFAULT '{}',
    source_platform VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    importance REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    embedding vector(512),
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
CREATE INDEX IF NOT EXISTS idx_knowledge_memory_type
    ON knowledge(memory_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_importance
    ON knowledge(importance DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_expires
    ON knowledge(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_tags
    ON conversations USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_conversations_importance
    ON conversations(importance DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_short_term_search
    ON short_term_memory USING GIN (to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS idx_short_term_expires
    ON short_term_memory(expires_at);
CREATE INDEX IF NOT EXISTS idx_short_term_context_key
    ON short_term_memory(context_key);
CREATE INDEX IF NOT EXISTS idx_short_term_consolidated
    ON short_term_memory(consolidated) WHERE NOT consolidated;
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

-- Knowledge version history (change tracking)
CREATE TABLE IF NOT EXISTS knowledge_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_id UUID NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    tags TEXT[] DEFAULT '{}',
    source_platform VARCHAR(50),
    importance REAL DEFAULT 0.5,
    confidence REAL DEFAULT 1.0,
    changed_by VARCHAR(50),
    change_type VARCHAR(20) NOT NULL DEFAULT 'update',
    change_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Memory conflicts (cross-platform conflict tracking)
CREATE TABLE IF NOT EXISTS memory_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_id UUID REFERENCES knowledge(id) ON DELETE CASCADE,
    conflicting_content TEXT NOT NULL,
    conflicting_platform VARCHAR(50) NOT NULL,
    existing_platform VARCHAR(50),
    existing_content TEXT,
    conflict_type VARCHAR(30) NOT NULL DEFAULT 'content_mismatch',
    resolution_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    resolution_strategy VARCHAR(30),
    resolved_by VARCHAR(50),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_versions_kid
    ON knowledge_versions(knowledge_id, version DESC);
CREATE INDEX IF NOT EXISTS idx_memory_conflicts_status
    ON memory_conflicts(resolution_status) WHERE resolution_status = 'pending';
CREATE INDEX IF NOT EXISTS idx_memory_conflicts_kid
    ON memory_conflicts(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_version
    ON knowledge(version);

-- Vector similarity indexes (HNSW for fast approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_embedding
    ON conversations USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_short_term_embedding
    ON short_term_memory USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_code_snippets_embedding
    ON code_snippets USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
"""

# Migration SQL for existing databases — adds new columns safely
MIGRATION_SQL = """
-- Add new columns to conversations if not present
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS importance REAL DEFAULT 0.5;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS outcome VARCHAR(50) DEFAULT 'neutral';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS emotional_context VARCHAR(100) DEFAULT '';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ;

-- Add new columns to knowledge if not present
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS memory_type VARCHAR(20) DEFAULT 'semantic';
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS importance REAL DEFAULT 0.5;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS confidence REAL DEFAULT 1.0;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ;
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Add new columns to code_snippets if not present
ALTER TABLE code_snippets ADD COLUMN IF NOT EXISTS importance REAL DEFAULT 0.5;
ALTER TABLE code_snippets ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;

-- Add embedding columns (pgvector)
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS embedding vector(512);
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS embedding vector(512);
ALTER TABLE code_snippets ADD COLUMN IF NOT EXISTS embedding vector(512);

-- Create short_term_memory table if not present (handled by SCHEMA_SQL but adding safety)
CREATE TABLE IF NOT EXISTS short_term_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    context_key VARCHAR(200),
    source_platform VARCHAR(50),
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    importance REAL DEFAULT 0.3,
    expires_at TIMESTAMPTZ NOT NULL,
    consolidated BOOLEAN DEFAULT FALSE,
    consolidated_into UUID,
    embedding vector(512),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add version column to knowledge
ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;

-- Create knowledge_versions table if not present
CREATE TABLE IF NOT EXISTS knowledge_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_id UUID NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    tags TEXT[] DEFAULT '{}',
    source_platform VARCHAR(50),
    importance REAL DEFAULT 0.5,
    confidence REAL DEFAULT 1.0,
    changed_by VARCHAR(50),
    change_type VARCHAR(20) NOT NULL DEFAULT 'update',
    change_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create memory_conflicts table if not present
CREATE TABLE IF NOT EXISTS memory_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_id UUID REFERENCES knowledge(id) ON DELETE CASCADE,
    conflicting_content TEXT NOT NULL,
    conflicting_platform VARCHAR(50) NOT NULL,
    existing_platform VARCHAR(50),
    existing_content TEXT,
    conflict_type VARCHAR(30) NOT NULL DEFAULT 'content_mismatch',
    resolution_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    resolution_strategy VARCHAR(30),
    resolved_by VARCHAR(50),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        database_url = os.environ.get("DATABASE_URL", "postgresql://mcp_user:mcp_secure_pass_2026@localhost:4569/mcp_memory")
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    return _pool


def _split_sql(sql: str) -> list[str]:
    """Split SQL into individual statements, stripping comments."""
    # Remove full-line comments
    lines = [l for l in sql.split('\n') if not l.strip().startswith('--')]
    clean = '\n'.join(lines)
    # Split on semicolons and filter empty
    return [s.strip() for s in clean.split(';') if s.strip()]


async def init_db():
    """Initialize the database schema and run migrations for existing databases."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Enable pgvector extension first (needed before any vector columns)
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Run migrations FIRST to add new columns to existing tables
        # This must happen before indexes reference those columns
        for statement in _split_sql(MIGRATION_SQL):
            try:
                await conn.execute(statement)
            except Exception:
                pass  # Column/table already exists or other safe-to-skip error

        # Execute SCHEMA_SQL statement by statement
        # (batch execution fails if indexes reference columns added by migration)
        for statement in _split_sql(SCHEMA_SQL):
            try:
                await conn.execute(statement)
            except Exception:
                pass  # Table/index already exists


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
    importance: float = 0.5,
    outcome: str = "neutral",
    emotional_context: str = "",
) -> dict:
    """Save a conversation with its messages (episodic memory)."""
    pool = await get_pool()
    # Generate embedding from title + summary
    embed_text = f"{title or ''} {summary or ''}"
    vec = await emb.get_embedding(embed_text) if embed_text.strip() else None
    vec_str = str(vec) if vec else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (platform, title, summary, tags, metadata, importance, outcome, emotional_context, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, created_at
                """,
                platform,
                title,
                summary,
                tags or [],
                json.dumps(metadata or {}),
                max(0.0, min(1.0, importance)),
                outcome,
                emotional_context,
                vec_str,
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
                "importance": importance,
                "outcome": outcome,
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
    memory_type: str = "semantic",
    importance: float = 0.5,
    confidence: float = 1.0,
) -> dict:
    """Save a knowledge entity (long-term semantic memory)."""
    pool = await get_pool()
    vec = await emb.get_embedding(content)
    vec_str = str(vec) if vec else None

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
            INSERT INTO knowledge (category, content, tags, source_platform, source_conversation_id, metadata,
                                   memory_type, importance, confidence, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id, created_at
            """,
            category,
            content,
            tags or [],
            source_platform,
            conv_id,
            json.dumps(metadata or {}),
            memory_type,
            max(0.0, min(1.0, importance)),
            max(0.0, min(1.0, confidence)),
            vec_str,
        )
        return {
            "id": str(row["id"]),
            "category": category,
            "content": content[:100] + "..." if len(content) > 100 else content,
            "memory_type": memory_type,
            "importance": importance,
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
    changed_by: Optional[str] = None,
    change_reason: Optional[str] = None,
) -> dict:
    """Update an existing knowledge entry with version tracking.

    Before updating, saves a snapshot of the current state to knowledge_versions.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            kid = _uuid.UUID(knowledge_id)
        except ValueError:
            return {"error": "Invalid UUID"}
        existing = await conn.fetchrow("SELECT * FROM knowledge WHERE id = $1", kid)
        if not existing:
            return {"error": "Not found"}

        current_version = existing.get("version") or 1

        # Snapshot current state into version history
        await conn.execute(
            """
            INSERT INTO knowledge_versions
                (knowledge_id, version, content, category, tags, source_platform,
                 importance, confidence, changed_by, change_type, change_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'update', $10)
            """,
            kid, current_version, existing["content"], existing["category"],
            existing["tags"], existing["source_platform"],
            existing["importance"], existing["confidence"],
            changed_by or existing.get("source_platform"), change_reason,
        )

        new_content = content if content is not None else existing["content"]
        new_category = category if category is not None else existing["category"]
        new_tags = tags if tags is not None else existing["tags"]
        new_version = current_version + 1

        # Update the embedding if content changed
        vec_str = None
        if content is not None and content != existing["content"]:
            vec = await emb.get_embedding(new_content)
            vec_str = str(vec) if vec else None

        if vec_str:
            await conn.execute(
                "UPDATE knowledge SET content=$1, category=$2, tags=$3, version=$4, embedding=$5, updated_at=NOW() WHERE id=$6",
                new_content, new_category, new_tags, new_version, vec_str, kid,
            )
        else:
            await conn.execute(
                "UPDATE knowledge SET content=$1, category=$2, tags=$3, version=$4, updated_at=NOW() WHERE id=$5",
                new_content, new_category, new_tags, new_version, kid,
            )

        return {
            "id": str(kid),
            "status": "updated",
            "version": new_version,
            "previous_version": current_version,
            "content": new_content[:100],
            "category": new_category,
        }


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
            "short_term_memory": await conn.fetchval("SELECT COUNT(*) FROM short_term_memory WHERE expires_at > NOW() AND consolidated = FALSE"),
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
    embed_text = f"{title} {description or ''} {language}"
    vec = await emb.get_embedding(embed_text)
    vec_str = str(vec) if vec else None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO code_snippets (title, language, code, description, tags, source_platform, embedding) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id, created_at",
            title, language.lower(), code, description, tags or [], source_platform, vec_str,
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


# ─── Short-Term Memory Operations ───────────────────────────────────────────


async def save_short_term_memory(
    content: str,
    context_key: Optional[str] = None,
    source_platform: Optional[str] = None,
    tags: Optional[list[str]] = None,
    ttl_minutes: int = 60,
    importance: float = 0.3,
) -> dict:
    """Save a short-term / working memory entry with a TTL.

    Short-term memories auto-expire after ttl_minutes. They represent
    transient context like 'user is currently debugging auth', 'we are
    working on file X', etc.
    """
    pool = await get_pool()
    vec = await emb.get_embedding(content)
    vec_str = str(vec) if vec else None

    async with pool.acquire() as conn:
        expires = datetime.now(timezone.utc) + timedelta(minutes=max(1, ttl_minutes))
        row = await conn.fetchrow(
            """
            INSERT INTO short_term_memory (content, context_key, source_platform, tags, importance, expires_at, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, created_at, expires_at
            """,
            content,
            context_key,
            source_platform,
            tags or [],
            max(0.0, min(1.0, importance)),
            expires,
            vec_str,
        )
        return {
            "id": str(row["id"]),
            "content": content[:100] + "..." if len(content) > 100 else content,
            "context_key": context_key,
            "ttl_minutes": ttl_minutes,
            "expires_at": row["expires_at"].isoformat(),
            "created_at": row["created_at"].isoformat(),
        }


async def get_active_short_term_memories(
    context_key: Optional[str] = None,
    source_platform: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Get all non-expired, non-consolidated short-term memories."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        sql = """
            SELECT id, content, context_key, source_platform, tags, importance, expires_at, created_at
            FROM short_term_memory
            WHERE expires_at > NOW() AND consolidated = FALSE
        """
        params = []
        param_idx = 1

        if context_key:
            sql += f" AND context_key = ${param_idx}"
            params.append(context_key)
            param_idx += 1

        if source_platform:
            sql += f" AND source_platform = ${param_idx}"
            params.append(source_platform)
            param_idx += 1

        sql += f" ORDER BY importance DESC, created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        rows = await conn.fetch(sql, *params)
        return [
            {
                "id": str(r["id"]),
                "content": r["content"],
                "context_key": r["context_key"],
                "source_platform": r["source_platform"],
                "tags": r["tags"],
                "importance": float(r["importance"]),
                "expires_at": r["expires_at"].isoformat(),
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]


async def search_short_term_memory(
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Full-text search across active short-term memories."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, content, context_key, source_platform, tags, importance, expires_at, created_at,
                   ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS rank
            FROM short_term_memory
            WHERE expires_at > NOW() AND consolidated = FALSE
              AND to_tsvector('english', content) @@ plainto_tsquery('english', $1)
            ORDER BY rank DESC, importance DESC LIMIT $2
            """,
            query, limit,
        )
        return [
            {
                "id": str(r["id"]),
                "content": r["content"],
                "context_key": r["context_key"],
                "importance": float(r["importance"]),
                "relevance": float(r["rank"]),
                "expires_at": r["expires_at"].isoformat(),
            }
            for r in rows
        ]


# ─── Memory Consolidation ───────────────────────────────────────────────────


async def consolidate_memories(
    source_platform: Optional[str] = None,
) -> dict:
    """Promote important short-term memories into long-term knowledge.

    Finds non-expired, non-consolidated short-term memories with
    importance >= 0.5, saves each as a long-term knowledge entry,
    and marks the short-term entry as consolidated.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        sql = """
            SELECT id, content, context_key, source_platform, tags, importance
            FROM short_term_memory
            WHERE consolidated = FALSE AND expires_at > NOW() AND importance >= 0.5
        """
        params = []
        param_idx = 1
        if source_platform:
            sql += f" AND source_platform = ${param_idx}"
            params.append(source_platform)
            param_idx += 1
        sql += " ORDER BY importance DESC"

        rows = await conn.fetch(sql, *params)
        consolidated = []

        for r in rows:
            async with conn.transaction():
                # Insert into long-term knowledge
                k_row = await conn.fetchrow(
                    """
                    INSERT INTO knowledge (category, content, memory_type, tags, source_platform, importance, confidence)
                    VALUES ('consolidated', $1, 'semantic', $2, $3, $4, 0.8)
                    RETURNING id
                    """,
                    r["content"],
                    r["tags"] or [],
                    r["source_platform"],
                    float(r["importance"]),
                )
                # Mark short-term entry as consolidated
                await conn.execute(
                    "UPDATE short_term_memory SET consolidated = TRUE, consolidated_into = $1 WHERE id = $2",
                    k_row["id"], r["id"],
                )
                consolidated.append({
                    "short_term_id": str(r["id"]),
                    "knowledge_id": str(k_row["id"]),
                    "content": r["content"][:80],
                })

        return {
            "total_candidates": len(rows),
            "consolidated": len(consolidated),
            "entries": consolidated,
        }


async def cleanup_expired_memories() -> dict:
    """Delete expired short-term memories and expired knowledge entries."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        stm_result = await conn.execute(
            "DELETE FROM short_term_memory WHERE expires_at <= NOW()"
        )
        k_result = await conn.execute(
            "DELETE FROM knowledge WHERE expires_at IS NOT NULL AND expires_at <= NOW()"
        )
        stm_count = int(stm_result.split()[-1]) if stm_result else 0
        k_count = int(k_result.split()[-1]) if k_result else 0
        return {
            "deleted_short_term": stm_count,
            "deleted_expired_knowledge": k_count,
            "total_deleted": stm_count + k_count,
        }


# ─── Smart Recall (Unified Retrieval) ───────────────────────────────────────


async def recall(
    query: str,
    platform: Optional[str] = None,
    memory_types: Optional[list[str]] = None,
    limit: int = 15,
) -> dict:
    """Unified smart recall with HYBRID search (vector + full-text).

    Searches across ALL memory stores combining:
      - Vector cosine similarity (semantic understanding)
      - Full-text ts_rank (keyword matching)
      - Recency (time decay)
      - Importance scoring

    Final score = semantic * 0.3 + text_rank * 0.2 + recency * 0.25 + importance * 0.25
    """
    pool = await get_pool()
    results = []
    seen_ids = set()
    allowed_types = set(memory_types or ["short_term", "knowledge", "episodic", "procedural"])

    # Generate query embedding for vector search
    query_vec = await emb.get_embedding(query)
    query_vec_str = str(query_vec)

    def _score(text_rank: float, vec_sim: float, age_days: float, importance: float) -> float:
        recency = 1.0 / (1.0 + age_days)
        semantic = max(0.0, 1.0 - vec_sim) if vec_sim is not None else 0.0  # cosine distance → similarity
        return semantic * 0.3 + float(text_rank) * 0.2 + recency * 0.25 + float(importance) * 0.25

    def _age(created_at):
        return (datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400.0

    async with pool.acquire() as conn:

        # ── Short-term memory (hybrid) ──
        if "short_term" in allowed_types:
            stm_rows = await conn.fetch(
                """
                SELECT id, content, context_key AS title, importance, created_at,
                       ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS text_rank,
                       CASE WHEN embedding IS NOT NULL THEN embedding <=> $2::vector ELSE NULL END AS vec_dist
                FROM short_term_memory
                WHERE expires_at > NOW() AND consolidated = FALSE
                  AND (to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                       OR (embedding IS NOT NULL AND embedding <=> $2::vector < 1.2))
                ORDER BY COALESCE(embedding <=> $2::vector, 1.0) ASC LIMIT $3
                """,
                query, query_vec_str, limit,
            )
            for r in stm_rows:
                rid = str(r["id"])
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                results.append({
                    "memory_type": "short_term",
                    "id": rid,
                    "title": r["title"],
                    "content": r["content"],
                    "importance": float(r["importance"]),
                    "score": round(_score(r["text_rank"], r["vec_dist"], _age(r["created_at"]), r["importance"]), 4),
                    "created_at": r["created_at"].isoformat(),
                })

        # ── Long-term knowledge (hybrid) ──
        if "knowledge" in allowed_types:
            k_sql = """
                SELECT id, category AS title, content, importance, created_at, memory_type,
                       ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS text_rank,
                       CASE WHEN embedding IS NOT NULL THEN embedding <=> $2::vector ELSE NULL END AS vec_dist
                FROM knowledge
                WHERE (expires_at IS NULL OR expires_at > NOW())
                  AND (to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                       OR (embedding IS NOT NULL AND embedding <=> $2::vector < 1.2))
            """
            k_params = [query, query_vec_str]
            k_idx = 3
            if platform:
                k_sql += f" AND source_platform = ${k_idx}"
                k_params.append(platform)
                k_idx += 1
            k_sql += f" ORDER BY COALESCE(embedding <=> $2::vector, 1.0) ASC LIMIT ${k_idx}"
            k_params.append(limit)

            k_rows = await conn.fetch(k_sql, *k_params)
            for r in k_rows:
                rid = str(r["id"])
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                results.append({
                    "memory_type": f"knowledge/{r['memory_type']}",
                    "id": rid,
                    "title": r["title"],
                    "content": r["content"],
                    "importance": float(r["importance"]),
                    "score": round(_score(r["text_rank"], r["vec_dist"], _age(r["created_at"]), r["importance"]), 4),
                    "created_at": r["created_at"].isoformat(),
                })
                await conn.execute(
                    "UPDATE knowledge SET access_count = access_count + 1, last_accessed_at = NOW() WHERE id = $1",
                    r["id"],
                )

        # ── Episodic memory (hybrid) ──
        if "episodic" in allowed_types:
            e_sql = """
                SELECT c.id, c.title, c.summary AS content, c.importance, c.created_at,
                       ts_rank(to_tsvector('english', coalesce(c.title,'') || ' ' || coalesce(c.summary,'')),
                               plainto_tsquery('english', $1)) AS text_rank,
                       CASE WHEN c.embedding IS NOT NULL THEN c.embedding <=> $2::vector ELSE NULL END AS vec_dist
                FROM conversations c
                WHERE (to_tsvector('english', coalesce(c.title,'') || ' ' || coalesce(c.summary,''))
                       @@ plainto_tsquery('english', $1)
                       OR (c.embedding IS NOT NULL AND c.embedding <=> $2::vector < 1.2)
                       OR c.id IN (SELECT conversation_id FROM messages
                                   WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)))
            """
            e_params = [query, query_vec_str]
            e_idx = 3
            if platform:
                e_sql += f" AND c.platform = ${e_idx}"
                e_params.append(platform)
                e_idx += 1
            e_sql += f" ORDER BY COALESCE(c.embedding <=> $2::vector, 1.0) ASC LIMIT ${e_idx}"
            e_params.append(limit)

            e_rows = await conn.fetch(e_sql, *e_params)
            for r in e_rows:
                rid = str(r["id"])
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                results.append({
                    "memory_type": "episodic",
                    "id": rid,
                    "title": r["title"],
                    "content": r["content"],
                    "importance": float(r["importance"]),
                    "score": round(_score(r["text_rank"], r["vec_dist"], _age(r["created_at"]), r["importance"]), 4),
                    "created_at": r["created_at"].isoformat(),
                })
                await conn.execute(
                    "UPDATE conversations SET access_count = access_count + 1, last_accessed_at = NOW() WHERE id = $1",
                    r["id"],
                )

        # ── Procedural memory (hybrid) ──
        if "procedural" in allowed_types:
            cs_rows = await conn.fetch(
                """
                SELECT id, title, code AS content, importance, created_at,
                       ts_rank(to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || code),
                               plainto_tsquery('english', $1)) AS text_rank,
                       CASE WHEN embedding IS NOT NULL THEN embedding <=> $2::vector ELSE NULL END AS vec_dist
                FROM code_snippets
                WHERE (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,'') || ' ' || code)
                       @@ plainto_tsquery('english', $1)
                       OR (embedding IS NOT NULL AND embedding <=> $2::vector < 1.2))
                ORDER BY COALESCE(embedding <=> $2::vector, 1.0) ASC LIMIT $3
                """,
                query, query_vec_str, limit,
            )
            for r in cs_rows:
                rid = str(r["id"])
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                results.append({
                    "memory_type": "procedural",
                    "id": rid,
                    "title": r["title"],
                    "content": r["content"][:300],
                    "importance": float(r["importance"]),
                    "score": round(_score(r["text_rank"], r["vec_dist"], _age(r["created_at"]), r["importance"]), 4),
                    "created_at": r["created_at"].isoformat(),
                })

    # Sort all results by composite score
    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "query": query,
        "total_results": len(results),
        "results": results[:limit],
    }


# ─── Memory Importance Decay ────────────────────────────────────────────────


async def decay_memories(decay_factor: float = 0.95) -> dict:
    """Apply time-based decay to memory importance scores.

    Reduces importance of all knowledge and conversation entries that
    haven't been accessed recently. Memories that are accessed frequently
    decay more slowly (their access_count acts as a buffer).

    Formula: new_importance = importance * decay_factor ^ (days_since_last_access / 30)
    Minimum importance is clamped at 0.05 so memories never fully vanish.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Decay knowledge
        k_result = await conn.execute(
            """
            UPDATE knowledge SET
                importance = GREATEST(0.05,
                    importance * POWER($1, EXTRACT(EPOCH FROM (NOW() - COALESCE(last_accessed_at, created_at))) / 2592000.0)
                ),
                updated_at = NOW()
            WHERE importance > 0.05
              AND (expires_at IS NULL OR expires_at > NOW())
            """,
            decay_factor,
        )
        # Decay conversations
        c_result = await conn.execute(
            """
            UPDATE conversations SET
                importance = GREATEST(0.05,
                    importance * POWER($1, EXTRACT(EPOCH FROM (NOW() - COALESCE(last_accessed_at, created_at))) / 2592000.0)
                ),
                updated_at = NOW()
            WHERE importance > 0.05
            """,
            decay_factor,
        )
        k_count = int(k_result.split()[-1]) if k_result else 0
        c_count = int(c_result.split()[-1]) if c_result else 0
        return {
            "decay_factor": decay_factor,
            "knowledge_updated": k_count,
            "conversations_updated": c_count,
        }


# ─── Enhanced Stats ─────────────────────────────────────────────────────────


async def get_memory_health() -> dict:
    """Get a comprehensive health overview of all memory stores."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conv_count = await conn.fetchval("SELECT COUNT(*) FROM conversations")
        msg_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
        k_total = await conn.fetchval("SELECT COUNT(*) FROM knowledge")
        k_semantic = await conn.fetchval("SELECT COUNT(*) FROM knowledge WHERE memory_type = 'semantic'")
        k_consolidated = await conn.fetchval("SELECT COUNT(*) FROM knowledge WHERE memory_type = 'semantic' AND category = 'consolidated'")
        stm_active = await conn.fetchval("SELECT COUNT(*) FROM short_term_memory WHERE expires_at > NOW() AND consolidated = FALSE")
        stm_expired = await conn.fetchval("SELECT COUNT(*) FROM short_term_memory WHERE expires_at <= NOW()")
        stm_consolidated = await conn.fetchval("SELECT COUNT(*) FROM short_term_memory WHERE consolidated = TRUE")
        snippets = await conn.fetchval("SELECT COUNT(*) FROM code_snippets")
        projects = await conn.fetchval("SELECT COUNT(*) FROM projects")

        avg_k_importance = await conn.fetchval("SELECT COALESCE(AVG(importance), 0) FROM knowledge")
        avg_c_importance = await conn.fetchval("SELECT COALESCE(AVG(importance), 0) FROM conversations")

        expiring_soon = await conn.fetchval(
            "SELECT COUNT(*) FROM short_term_memory WHERE expires_at > NOW() AND expires_at <= NOW() + INTERVAL '30 minutes' AND consolidated = FALSE"
        )

        return {
            "episodic_memory": {
                "conversations": conv_count,
                "messages": msg_count,
                "avg_importance": round(float(avg_c_importance), 3),
            },
            "semantic_memory": {
                "total_knowledge": k_total,
                "semantic_entries": k_semantic,
                "consolidated_from_stm": k_consolidated,
                "avg_importance": round(float(avg_k_importance), 3),
            },
            "short_term_memory": {
                "active": stm_active,
                "expired_pending_cleanup": stm_expired,
                "consolidated": stm_consolidated,
                "expiring_soon_30min": expiring_soon,
            },
            "procedural_memory": {
                "code_snippets": snippets,
            },
            "projects": projects,
        }


# ─── Memory Reflection & Compression ────────────────────────────────────────


async def reflect_and_compress(
    older_than_days: int = 7,
    min_conversations: int = 3,
    platform: Optional[str] = None,
) -> dict:
    """Compress old conversations into dense knowledge summaries.

    Finds clusters of related old conversations (by shared tags and
    overlapping content), extracts the key takeaways, and saves them as
    high-importance knowledge entries. The original conversations are
    marked with a 'compressed' tag but NOT deleted.

    This keeps the memory store lean while preserving all important context.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Find old conversations that haven't been compressed yet
        sql = """
            SELECT id, title, summary, tags, importance, platform, created_at
            FROM conversations
            WHERE created_at < NOW() - ($1 || ' days')::INTERVAL
              AND NOT ('compressed' = ANY(tags))
              AND summary IS NOT NULL AND summary != ''
        """
        params = [str(older_than_days)]
        p_idx = 2
        if platform:
            sql += f" AND platform = ${p_idx}"
            params.append(platform)
            p_idx += 1
        sql += " ORDER BY created_at ASC"

        rows = await conn.fetch(sql, *params)

        if len(rows) < min_conversations:
            return {
                "status": "skipped",
                "reason": f"Only {len(rows)} old conversations found (minimum: {min_conversations})",
                "compressed": 0,
            }

        # Group by shared tags into clusters
        clusters = {}
        for r in rows:
            # Use the first tag as cluster key, or 'general' if no tags
            cluster_key = r["tags"][0] if r["tags"] else "general"
            if cluster_key not in clusters:
                clusters[cluster_key] = []
            clusters[cluster_key].append(r)

        compressed_entries = []

        for cluster_key, convos in clusters.items():
            if len(convos) < 2:
                # Single conversations don't need compression
                continue

            # Build a compressed summary from all conversations in cluster
            summaries = []
            max_importance = 0.0
            conv_ids = []
            all_tags = set()
            platforms_used = set()

            for c in convos:
                summaries.append(f"- {c['title'] or 'Untitled'}: {c['summary']}")
                max_importance = max(max_importance, float(c["importance"]))
                conv_ids.append(c["id"])
                all_tags.update(c["tags"] or [])
                platforms_used.add(c["platform"])

            compressed_content = (
                f"Compressed memory from {len(convos)} conversations "
                f"(platforms: {', '.join(platforms_used)}, "
                f"period: {convos[0]['created_at'].strftime('%Y-%m-%d')} to "
                f"{convos[-1]['created_at'].strftime('%Y-%m-%d')}):\n"
                + "\n".join(summaries[:20])  # Cap at 20 entries per cluster
            )

            # Generate embedding for compressed content
            vec = await emb.get_embedding(compressed_content)
            vec_str = str(vec) if vec else None

            # Save as high-importance knowledge
            k_row = await conn.fetchrow(
                """
                INSERT INTO knowledge (category, content, memory_type, tags, importance, confidence, embedding)
                VALUES ('reflection', $1, 'semantic', $2, $3, 0.9, $4)
                RETURNING id
                """,
                compressed_content,
                list(all_tags),
                min(1.0, max_importance + 0.1),  # Boost importance slightly
                vec_str,
            )

            # Mark original conversations as compressed
            for cid in conv_ids:
                await conn.execute(
                    "UPDATE conversations SET tags = array_append(tags, 'compressed') WHERE id = $1",
                    cid,
                )

            compressed_entries.append({
                "knowledge_id": str(k_row["id"]),
                "cluster": cluster_key,
                "conversations_compressed": len(convos),
                "content_preview": compressed_content[:150],
            })

        return {
            "status": "completed",
            "total_old_conversations": len(rows),
            "clusters_found": len(clusters),
            "compressed_entries": len(compressed_entries),
            "entries": compressed_entries,
        }


# ─── Memory Versioning & Change Tracking ────────────────────────────────────


async def get_knowledge_history(
    knowledge_id: str,
    limit: int = 20,
) -> dict:
    """Get the full version history of a knowledge entry.

    Returns the current version plus all previous snapshots,
    showing what changed, when, and by whom.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            kid = _uuid.UUID(knowledge_id)
        except ValueError:
            return {"error": "Invalid UUID"}

        # Current state
        current = await conn.fetchrow(
            "SELECT id, category, content, tags, source_platform, importance, confidence, version, created_at, updated_at FROM knowledge WHERE id = $1",
            kid,
        )
        if not current:
            return {"error": "Knowledge entry not found"}

        # Version history
        versions = await conn.fetch(
            """
            SELECT version, content, category, tags, source_platform,
                   importance, confidence, changed_by, change_type, change_reason, created_at
            FROM knowledge_versions
            WHERE knowledge_id = $1
            ORDER BY version DESC LIMIT $2
            """,
            kid, limit,
        )

        return {
            "knowledge_id": str(kid),
            "current": {
                "version": current["version"] or 1,
                "content": current["content"],
                "category": current["category"],
                "tags": current["tags"],
                "source_platform": current["source_platform"],
                "importance": float(current["importance"]),
                "confidence": float(current["confidence"]),
                "created_at": current["created_at"].isoformat(),
                "updated_at": current["updated_at"].isoformat(),
            },
            "total_versions": len(versions) + 1,
            "history": [
                {
                    "version": v["version"],
                    "content": v["content"],
                    "category": v["category"],
                    "tags": v["tags"],
                    "changed_by": v["changed_by"],
                    "change_type": v["change_type"],
                    "change_reason": v["change_reason"],
                    "importance": float(v["importance"]),
                    "timestamp": v["created_at"].isoformat(),
                }
                for v in versions
            ],
        }


async def rollback_knowledge(
    knowledge_id: str,
    target_version: int,
    rolled_back_by: Optional[str] = None,
) -> dict:
    """Rollback a knowledge entry to a previous version.

    Restores the content, category, tags, importance, and confidence
    from the specified version. Creates a new version entry recording
    the rollback.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            kid = _uuid.UUID(knowledge_id)
        except ValueError:
            return {"error": "Invalid UUID"}

        # Get current state
        current = await conn.fetchrow("SELECT * FROM knowledge WHERE id = $1", kid)
        if not current:
            return {"error": "Knowledge entry not found"}

        # Find the target version
        target = await conn.fetchrow(
            "SELECT * FROM knowledge_versions WHERE knowledge_id = $1 AND version = $2",
            kid, target_version,
        )
        if not target:
            return {"error": f"Version {target_version} not found"}

        current_version = current.get("version") or 1

        # Snapshot current state as a version (before rollback)
        await conn.execute(
            """
            INSERT INTO knowledge_versions
                (knowledge_id, version, content, category, tags, source_platform,
                 importance, confidence, changed_by, change_type, change_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'rollback', $10)
            """,
            kid, current_version, current["content"], current["category"],
            current["tags"], current["source_platform"],
            current["importance"], current["confidence"],
            rolled_back_by, f"Rolled back to version {target_version}",
        )

        new_version = current_version + 1

        # Restore from target version
        vec = await emb.get_embedding(target["content"])
        vec_str = str(vec) if vec else None

        await conn.execute(
            """
            UPDATE knowledge SET
                content = $1, category = $2, tags = $3,
                importance = $4, confidence = $5,
                version = $6, embedding = $7, updated_at = NOW()
            WHERE id = $8
            """,
            target["content"], target["category"], target["tags"],
            target["importance"], target["confidence"],
            new_version, vec_str, kid,
        )

        return {
            "id": str(kid),
            "status": "rolled_back",
            "from_version": current_version,
            "to_version": new_version,
            "restored_from": target_version,
            "content": target["content"][:100],
            "category": target["category"],
        }


# ─── Memory Conflict Resolution ─────────────────────────────────────────────

# Similarity threshold for conflict detection (0.0 = identical, 2.0 = completely different)
CONFLICT_SIMILARITY_THRESHOLD = 0.4


async def detect_and_save_or_conflict(
    category: str,
    content: str,
    tags: Optional[list[str]] = None,
    source_platform: Optional[str] = None,
    source_conversation_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    memory_type: str = "semantic",
    importance: float = 0.5,
    confidence: float = 1.0,
) -> dict:
    """Save knowledge with automatic cross-platform conflict detection.

    Before saving, checks if similar knowledge already exists from a
    DIFFERENT platform. If it does and the content meaningfully differs,
    a conflict is raised instead of silently overwriting.

    Conflict strategies:
    - If exact duplicate: skip (dedup)
    - If same topic but different content from different platform: create conflict
    - If no match: save normally
    """
    pool = await get_pool()
    vec = await emb.get_embedding(content)
    vec_str = str(vec) if vec else None

    async with pool.acquire() as conn:
        # Check for similar existing knowledge using vector similarity
        similar = None
        if vec_str:
            similar_rows = await conn.fetch(
                """
                SELECT id, content, category, source_platform, importance, confidence, version,
                       embedding <=> $1::vector AS distance
                FROM knowledge
                WHERE embedding IS NOT NULL
                  AND category = $2
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY embedding <=> $1::vector ASC
                LIMIT 3
                """,
                vec_str, category,
            )
            for row in similar_rows:
                dist = float(row["distance"])
                if dist < CONFLICT_SIMILARITY_THRESHOLD:
                    similar = row
                    break

        # Also check full-text for exact-ish matches
        if not similar:
            similar = await conn.fetchrow(
                """
                SELECT id, content, category, source_platform, importance, confidence, version,
                       ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) AS rank
                FROM knowledge
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                  AND category = $2
                ORDER BY rank DESC LIMIT 1
                """,
                content[:200], category,
            )
            if similar and float(similar.get("rank", 0)) < 0.3:
                similar = None  # Not similar enough

        if similar:
            existing_platform = similar["source_platform"] or "unknown"
            existing_content = similar["content"]

            # Exact duplicate — skip
            if existing_content.strip().lower() == content.strip().lower():
                return {
                    "status": "duplicate_skipped",
                    "existing_id": str(similar["id"]),
                    "message": "Identical knowledge already exists",
                }

            # Same platform — just update (no conflict)
            if existing_platform == source_platform:
                result = await update_knowledge(
                    str(similar["id"]),
                    content=content,
                    tags=tags,
                    changed_by=source_platform,
                    change_reason="Updated by same platform",
                )
                result["status"] = "updated_same_platform"
                return result

            # DIFFERENT platform with different content → CONFLICT
            conflict_row = await conn.fetchrow(
                """
                INSERT INTO memory_conflicts
                    (knowledge_id, conflicting_content, conflicting_platform,
                     existing_platform, existing_content, conflict_type)
                VALUES ($1, $2, $3, $4, $5, 'content_mismatch')
                RETURNING id, created_at
                """,
                similar["id"], content, source_platform or "unknown",
                existing_platform, existing_content,
            )

            return {
                "status": "conflict_detected",
                "conflict_id": str(conflict_row["id"]),
                "existing_id": str(similar["id"]),
                "existing_platform": existing_platform,
                "existing_content": existing_content[:100],
                "new_platform": source_platform,
                "new_content": content[:100],
                "message": "Conflicting knowledge from different platform. Use resolve_conflict to handle.",
            }

        # No conflict — save normally
        conv_id = None
        if source_conversation_id:
            try:
                conv_id = _uuid.UUID(source_conversation_id)
            except ValueError:
                pass

        row = await conn.fetchrow(
            """
            INSERT INTO knowledge (category, content, tags, source_platform, source_conversation_id,
                                   metadata, memory_type, importance, confidence, embedding, version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 1)
            RETURNING id, created_at
            """,
            category, content, tags or [], source_platform, conv_id,
            json.dumps(metadata or {}), memory_type,
            max(0.0, min(1.0, importance)),
            max(0.0, min(1.0, confidence)),
            vec_str,
        )

        return {
            "status": "saved",
            "id": str(row["id"]),
            "category": category,
            "content": content[:100] + "..." if len(content) > 100 else content,
            "version": 1,
            "created_at": row["created_at"].isoformat(),
        }


async def list_conflicts(
    status: str = "pending",
    limit: int = 20,
) -> dict:
    """List memory conflicts, optionally filtered by resolution status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mc.id, mc.knowledge_id, mc.conflicting_content, mc.conflicting_platform,
                   mc.existing_platform, mc.existing_content, mc.conflict_type,
                   mc.resolution_status, mc.resolution_strategy, mc.resolved_by,
                   mc.resolved_at, mc.created_at,
                   k.category, k.version AS current_version
            FROM memory_conflicts mc
            LEFT JOIN knowledge k ON k.id = mc.knowledge_id
            WHERE mc.resolution_status = $1
            ORDER BY mc.created_at DESC LIMIT $2
            """,
            status, limit,
        )

        return {
            "status_filter": status,
            "total": len(rows),
            "conflicts": [
                {
                    "conflict_id": str(r["id"]),
                    "knowledge_id": str(r["knowledge_id"]) if r["knowledge_id"] else None,
                    "category": r["category"],
                    "existing_platform": r["existing_platform"],
                    "existing_content": r["existing_content"][:150] if r["existing_content"] else None,
                    "conflicting_platform": r["conflicting_platform"],
                    "conflicting_content": r["conflicting_content"][:150],
                    "conflict_type": r["conflict_type"],
                    "resolution_status": r["resolution_status"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in rows
            ],
        }


async def resolve_conflict(
    conflict_id: str,
    strategy: str = "keep_existing",
    merged_content: Optional[str] = None,
    resolved_by: Optional[str] = None,
) -> dict:
    """Resolve a memory conflict using the specified strategy.

    Strategies:
    - 'keep_existing': Keep the existing knowledge, discard the conflict
    - 'use_new': Replace existing with the conflicting content (with version tracking)
    - 'merge': Use the provided merged_content as the new version
    - 'keep_both': Save conflicting content as a separate knowledge entry
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            cid = _uuid.UUID(conflict_id)
        except ValueError:
            return {"error": "Invalid conflict UUID"}

        conflict = await conn.fetchrow(
            "SELECT * FROM memory_conflicts WHERE id = $1", cid,
        )
        if not conflict:
            return {"error": "Conflict not found"}

        if conflict["resolution_status"] != "pending":
            return {"error": f"Conflict already resolved ({conflict['resolution_status']})"}

        kid = conflict["knowledge_id"]
        result = {"conflict_id": str(cid), "strategy": strategy}

        if strategy == "keep_existing":
            # Just mark as resolved, no changes
            result["action"] = "Kept existing knowledge unchanged"

        elif strategy == "use_new":
            # Replace existing with conflicting content
            update_result = await update_knowledge(
                str(kid),
                content=conflict["conflicting_content"],
                changed_by=conflict["conflicting_platform"],
                change_reason=f"Conflict resolution: accepted content from {conflict['conflicting_platform']}",
            )
            result["action"] = "Replaced with new content"
            result["new_version"] = update_result.get("version")

        elif strategy == "merge":
            if not merged_content:
                return {"error": "merged_content is required for 'merge' strategy"}
            update_result = await update_knowledge(
                str(kid),
                content=merged_content,
                changed_by=resolved_by or "conflict_resolution",
                change_reason=f"Merged content from {conflict['existing_platform']} and {conflict['conflicting_platform']}",
            )
            result["action"] = "Merged content saved"
            result["new_version"] = update_result.get("version")

        elif strategy == "keep_both":
            # Save conflicting content as a new entry
            existing = await conn.fetchrow("SELECT category, tags, memory_type FROM knowledge WHERE id = $1", kid)
            new_entry = await save_knowledge(
                category=existing["category"] if existing else "general",
                content=conflict["conflicting_content"],
                tags=existing["tags"] if existing else [],
                source_platform=conflict["conflicting_platform"],
                memory_type=existing["memory_type"] if existing else "semantic",
                importance=0.5,
            )
            result["action"] = "Saved conflicting content as separate entry"
            result["new_knowledge_id"] = new_entry["id"]

        else:
            return {"error": f"Unknown strategy: {strategy}. Use: keep_existing, use_new, merge, keep_both"}

        # Mark conflict as resolved
        await conn.execute(
            """
            UPDATE memory_conflicts SET
                resolution_status = 'resolved',
                resolution_strategy = $1,
                resolved_by = $2,
                resolved_at = NOW()
            WHERE id = $3
            """,
            strategy, resolved_by or "system", cid,
        )

        result["status"] = "resolved"
        return result
