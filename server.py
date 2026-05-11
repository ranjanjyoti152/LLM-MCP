"""
LLM Memory MCP Server
=====================
A Model Context Protocol server that provides persistent memory across
all AI platforms (Antigravity, Cursor, VS Code Copilot, Gemini, ChatGPT, etc.).

Runs on Streamable HTTP transport for universal compatibility.
"""

import asyncio
import json
import os
import signal
import sys
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import db

load_dotenv()

# ─── Server Setup ────────────────────────────────────────────────────────────

HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "4040"))

mcp = FastMCP(
    "LLM Memory",
    host=HOST,
    port=PORT,
    stateless_http=True,
    instructions="""
    You have a PERSISTENT MEMORY that works across ALL AI platforms (Windsurf, Cursor, Claude, Gemini, ChatGPT, Codex, etc.).
    Everything you learn about the user is shared everywhere. You are not stateless — you REMEMBER.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    MANDATORY — DO THIS AT THE START OF EVERY CONVERSATION:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. Call get_working_context() — loads active session context
    2. Call recall("<user's topic or greeting>") — searches ALL memory types
    3. Use what you recall to personalize your response (name, preferences, ongoing work)
    4. Call save_short_term_memory(content="<what we're working on>", context_key="current_task", source_platform="<your platform name>")

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    MANDATORY — DO THIS DURING EVERY CONVERSATION:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Silently detect and save ANY of these WITHOUT being asked:
    - Preferences: "I prefer X" → save_knowledge_smart(category="preference", importance=0.8)
    - Facts: "Our API uses port 3000" → save_knowledge_smart(category="fact", importance=0.6)
    - Decisions: "We chose PostgreSQL" → save_knowledge_smart(category="decision", importance=0.9)
    - Instructions: "Always use async/await" → save_knowledge_smart(category="instruction", importance=0.9)
    - Code patterns: Any reusable code → save_code_snippet(importance=0.7)
    ALWAYS use save_knowledge_smart (NOT save_knowledge) — it detects duplicates and cross-platform conflicts automatically.
    ALWAYS set source_platform to your platform name. ALWAYS add relevant tags.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    MANDATORY — DO THIS AT THE END OF EVERY CONVERSATION:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. Call save_conversation(platform="<name>", title="<descriptive>", summary="<2-3 sentences>", messages=<history>, importance=<0.3-1.0>, outcome="success|failure|partial", tags=<topics>)
    2. Call auto_extract_preferences(conversation_text=<full text>, source_platform="<name>")
    3. Call consolidate_memories(source_platform="<name>")

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    MEMORY ARCHITECTURE — 4 TIERS:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    1. SHORT-TERM — save_short_term_memory / get_working_context
       Transient session context. Auto-expires. Use for "currently debugging X", "working on file Y".
    2. SEMANTIC — save_knowledge_smart / search_knowledge / update_knowledge
       Permanent facts, preferences, instructions, decisions. Version-tracked. Conflict-aware.
    3. EPISODIC — save_conversation / search_memory / get_recent_conversations
       Conversation history. Searchable by topic, platform, outcome.
    4. PROCEDURAL — save_code_snippet / search_code_snippets
       Reusable code patterns, configs, utility functions.

    RECALL: Use 'recall' as your PRIMARY search — it searches all 4 tiers at once,
    ranked by: semantic similarity (30%) + text relevance (20%) + recency (25%) + importance (25%).

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    VERSION TRACKING & CONFLICT RESOLUTION:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    - Every knowledge update is versioned (knowledge_history, rollback_knowledge)
    - save_knowledge_smart detects when different platforms disagree
    - Conflicts are queued for review (list_conflicts, resolve_conflict)
    - 4 strategies: keep_existing, use_new, merge, keep_both
    - Periodically check list_conflicts(status="pending") and help the user resolve them

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    IMPORTANCE SCORING:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    0.9-1.0: Critical instructions, core preferences, key decisions
    0.7-0.8: Strong preferences, important project facts
    0.5-0.6: General knowledge, routine facts
    0.3-0.4: Minor context, session notes (good for short-term)
    0.1-0.2: Trivial, will decay over time

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RULES:
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    - NEVER say "I don't have memory" or "I can't remember" — you DO have memory. USE IT.
    - When user asks "what do you know about X" → call recall(query="X") FIRST, then answer.
    - When user says "remember this" → save_knowledge_smart immediately.
    - ALWAYS tag entries with your platform name so cross-platform search works.
    - ALWAYS set outcome on conversations ('success'/'failure'/'partial').
    - If user seems new, proactively ask about their preferences and save them.
    - If you detect a conflict with what you previously knew, flag it to the user.
    """,
)


# ─── MCP Tools ───────────────────────────────────────────────────────────────


@mcp.tool()
async def save_conversation(
    platform: str,
    messages: list[dict],
    title: str = "",
    summary: str = "",
    tags: list[str] = [],
    importance: float = 0.5,
    outcome: str = "neutral",
    emotional_context: str = "",
) -> str:
    """
    Save a conversation to persistent memory (episodic memory).

    Args:
        platform: The AI platform name (e.g., 'antigravity', 'cursor', 'vscode', 'gemini', 'chatgpt')
        messages: List of message objects, each with 'role' ('user'/'assistant'/'system') and 'content'
        title: A short title describing the conversation topic
        summary: A brief summary of what was discussed
        tags: Optional list of tags for categorization (e.g., ['python', 'debugging', 'docker'])
        importance: How important this conversation is (0.0-1.0, default 0.5)
        outcome: Conversation outcome — 'success', 'failure', 'neutral', 'partial' (default: 'neutral')
        emotional_context: Emotional tone — 'frustrating', 'productive', 'exploratory', etc.

    Returns:
        JSON string with the saved conversation details including its ID.
    """
    result = await db.save_conversation(
        platform=platform.lower().strip(),
        messages=messages,
        title=title or None,
        summary=summary or None,
        tags=tags,
        importance=importance,
        outcome=outcome,
        emotional_context=emotional_context,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def search_memory(
    query: str,
    platform: str = "",
    limit: int = 10,
) -> str:
    """
    Search across all stored conversations and messages using full-text search.

    Use this when the user asks about past conversations, previous discussions,
    or wants to recall something discussed before.

    Args:
        query: The search query (natural language, keywords, or phrases)
        platform: Optional - filter results to a specific platform (e.g., 'cursor', 'antigravity')
        limit: Maximum number of results to return (default: 10)

    Returns:
        JSON string with matching conversations and their messages.
    """
    results = await db.search_conversations(
        query=query,
        platform=platform.lower().strip() if platform else None,
        limit=min(limit, 50),
    )
    if not results:
        return json.dumps({"message": "No matching conversations found.", "results": []})
    return json.dumps({"result_count": len(results), "results": results}, indent=2)


@mcp.tool()
async def get_recent_conversations(
    platform: str = "",
    limit: int = 10,
) -> str:
    """
    Get the most recent conversations, optionally filtered by platform.

    Use this to see what was recently discussed across platforms.

    Args:
        platform: Optional - filter to a specific platform
        limit: Maximum number of conversations to return (default: 10)

    Returns:
        JSON string with recent conversations and their messages.
    """
    results = await db.get_recent_conversations(
        platform=platform.lower().strip() if platform else None,
        limit=min(limit, 50),
    )
    return json.dumps({"result_count": len(results), "results": results}, indent=2)


@mcp.tool()
async def save_knowledge(
    category: str,
    content: str,
    tags: list[str] = [],
    source_platform: str = "",
    memory_type: str = "semantic",
    importance: float = 0.5,
    confidence: float = 1.0,
) -> str:
    """
    Save a knowledge entity — a fact, preference, instruction, or important information (long-term semantic memory).

    Use this to store things like:
    - User preferences ("I prefer dark mode", "I use Python 3.12")
    - Project facts ("The API runs on port 8080", "Database is PostgreSQL")
    - Instructions ("Always use type hints in Python code")
    - Important decisions or conclusions from conversations

    Args:
        category: Type of knowledge — 'fact', 'preference', 'instruction', 'project', 'decision', or custom
        content: The knowledge content to store
        tags: Optional tags for categorization
        source_platform: The platform where this knowledge was learned
        memory_type: Memory classification — 'semantic' (facts/concepts), 'episodic' (events), 'procedural' (how-to)
        importance: How important this knowledge is (0.0-1.0, default 0.5). Higher = retained longer.
        confidence: How confident we are in this knowledge (0.0-1.0, default 1.0)

    Returns:
        JSON string with the saved knowledge entry details.
    """
    result = await db.save_knowledge(
        category=category.lower().strip(),
        content=content,
        tags=tags,
        source_platform=source_platform.lower().strip() if source_platform else None,
        memory_type=memory_type,
        importance=importance,
        confidence=confidence,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def search_knowledge(
    query: str,
    category: str = "",
    tags: list[str] = [],
    limit: int = 10,
) -> str:
    """
    Search stored knowledge entities (facts, preferences, instructions, etc.).

    Use this when the user asks about their preferences, project details,
    or any previously stored knowledge.

    Args:
        query: Search query (natural language or keywords)
        category: Optional - filter by category ('fact', 'preference', 'instruction', etc.)
        tags: Optional - filter by tags
        limit: Maximum results to return

    Returns:
        JSON string with matching knowledge entries.
    """
    results = await db.search_knowledge(
        query=query,
        category=category.lower().strip() if category else None,
        tags=tags if tags else None,
        limit=min(limit, 50),
    )
    if not results:
        return json.dumps({"message": "No matching knowledge found.", "results": []})
    return json.dumps({"result_count": len(results), "results": results}, indent=2)


@mcp.tool()
async def get_context_summary(
    topic: str = "",
    platform: str = "",
    limit: int = 5,
) -> str:
    """
    Get a summary of recent context — combines knowledge and conversations for a topic.

    Use this at the start of a conversation to load relevant context,
    or when the user asks for an overview of what's been discussed about a topic.

    Args:
        topic: Optional topic to focus on
        platform: Optional platform filter
        limit: Number of items to include per category

    Returns:
        JSON string with relevant knowledge items and recent conversations.
    """
    result = await db.get_context_summary(
        topic=topic or None,
        platform=platform.lower().strip() if platform else None,
        limit=min(limit, 20),
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def delete_memory(
    memory_id: str,
    memory_type: str = "conversation",
) -> str:
    """
    Delete a specific conversation or knowledge entry.

    Args:
        memory_id: The UUID of the conversation or knowledge entry to delete
        memory_type: Either 'conversation' or 'knowledge'

    Returns:
        JSON string confirming deletion or error.
    """
    if memory_type == "conversation":
        success = await db.delete_conversation(memory_id)
    elif memory_type == "knowledge":
        success = await db.delete_knowledge_entry(memory_id)
    else:
        return json.dumps({"error": f"Unknown memory_type: {memory_type}. Use 'conversation' or 'knowledge'."})

    if success:
        return json.dumps({"status": "deleted", "id": memory_id, "type": memory_type})
    return json.dumps({"status": "not_found", "id": memory_id, "type": memory_type})


@mcp.tool()
async def auto_extract_preferences(
    conversation_text: str,
    source_platform: str = "",
) -> str:
    """
    Automatically extract and save user preferences, facts, and decisions from conversation text.

    Call this at the END of every meaningful conversation to ensure nothing is lost.
    The tool parses the text for preference-like statements and saves each one
    as a knowledge entry, with deduplication (no duplicates will be created).

    Args:
        conversation_text: The full conversation text or a summary of key points.
                          Can be raw transcript or a bullet-point list of facts/preferences.
        source_platform: The AI platform name (e.g., 'antigravity', 'cursor', 'vscode')

    Returns:
        JSON with the number of new entries saved and any that were skipped as duplicates.
    """
    results = await db.extract_and_save_preferences(
        text=conversation_text,
        source_platform=source_platform.lower().strip() if source_platform else None,
    )
    return json.dumps(results, indent=2)


@mcp.tool()
async def update_knowledge(
    knowledge_id: str,
    content: str = "",
    category: str = "",
    tags: list[str] = [],
    changed_by: str = "",
    change_reason: str = "",
) -> str:
    """
    Update an existing knowledge entry (with automatic version tracking).

    Every update creates a version snapshot so you can view history and rollback.

    Args:
        knowledge_id: The UUID of the knowledge entry to update
        content: New content (leave empty to keep existing)
        category: New category (leave empty to keep existing)
        tags: New tags (leave empty to keep existing)
        changed_by: Platform or user making the change (for audit trail)
        change_reason: Why this change was made

    Returns:
        JSON string with updated entry details including version number.
    """
    result = await db.update_knowledge(
        knowledge_id=knowledge_id,
        content=content or None,
        category=category.lower().strip() or None,
        tags=tags or None,
        changed_by=changed_by.strip() or None,
        change_reason=change_reason.strip() or None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_all_knowledge(
    category: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """
    List all stored knowledge entries, optionally filtered by category.

    Useful for browsing all facts, preferences, instructions, or decisions
    stored in memory. Supports pagination.

    Args:
        category: Optional - filter by category ('fact', 'preference', 'instruction', etc.)
        limit: Maximum number of entries to return (default: 50)
        offset: Number of entries to skip for pagination (default: 0)

    Returns:
        JSON string with total count, pagination info, and knowledge items.
    """
    result = await db.list_all_knowledge(
        category=category.lower().strip() if category else None,
        limit=min(limit, 100),
        offset=offset,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_conversation_by_id(
    conversation_id: str,
) -> str:
    """
    Retrieve a specific conversation by its UUID, including all messages.

    Args:
        conversation_id: The UUID of the conversation to retrieve

    Returns:
        JSON string with the full conversation including all messages.
    """
    result = await db.get_conversation_by_id(conversation_id)
    if not result:
        return json.dumps({"error": "Conversation not found", "id": conversation_id})
    return json.dumps(result, indent=2)


@mcp.tool()
async def add_message_to_conversation(
    conversation_id: str,
    messages: list[dict],
) -> str:
    """
    Append new messages to an existing conversation.

    Useful for continuing a conversation without creating a new one.

    Args:
        conversation_id: The UUID of the conversation to add messages to
        messages: List of message objects, each with 'role' and 'content'

    Returns:
        JSON string with the conversation ID, number of added messages, and new total.
    """
    result = await db.add_messages_to_conversation(conversation_id, messages)
    return json.dumps(result, indent=2)


@mcp.tool()
async def tag_conversation(
    conversation_id: str,
    add_tags: list[str] = [],
    remove_tags: list[str] = [],
) -> str:
    """
    Add or remove tags from a conversation.

    Args:
        conversation_id: The UUID of the conversation
        add_tags: Tags to add to the conversation
        remove_tags: Tags to remove from the conversation

    Returns:
        JSON string with the conversation ID and updated tags list.
    """
    result = await db.update_conversation_tags(
        conversation_id, add_tags=add_tags or None, remove_tags=remove_tags or None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_knowledge_by_category(
    category: str,
    limit: int = 50,
) -> str:
    """
    Get all knowledge entries in a specific category.

    Example categories: 'fact', 'preference', 'instruction', 'decision', 'project'.

    Args:
        category: The category to filter by
        limit: Maximum results (default: 50)

    Returns:
        JSON string with all knowledge entries in that category.
    """
    results = await db.get_knowledge_by_category(category.lower().strip(), min(limit, 100))
    return json.dumps({"category": category, "count": len(results), "items": results}, indent=2)


@mcp.tool()
async def summarize_platform_activity(
    platform: str,
) -> str:
    """
    Get a detailed activity summary for a specific AI platform.

    Shows conversation count, message count, knowledge items, recent conversations,
    and most used tags for the platform.

    Args:
        platform: Platform name (e.g., 'antigravity', 'cursor', 'vscode')

    Returns:
        JSON string with comprehensive platform activity statistics.
    """
    result = await db.summarize_platform_activity(platform.lower().strip())
    return json.dumps(result, indent=2)


@mcp.tool()
async def export_memories() -> str:
    """
    Export all stored data as JSON for backup purposes.

    Exports conversations, messages, knowledge entries, code snippets, and projects.
    The output can be saved and later imported using import_memories.

    Returns:
        JSON string with all data (conversations, messages, knowledge, snippets, projects).
    """
    result = await db.export_all_memories()
    return json.dumps(result, indent=2)


@mcp.tool()
async def import_memories(
    data: dict,
) -> str:
    """
    Import data from a JSON backup into the memory database.

    Expects the same format as produced by export_memories.
    Uses upsert logic — existing entries (by UUID) are skipped, not duplicated.

    Args:
        data: The full backup object with keys: conversations, messages, knowledge, code_snippets, projects

    Returns:
        JSON string with import counts per entity type.
    """
    result = await db.import_memories(data)
    return json.dumps(result, indent=2)


@mcp.tool()
async def count_memories() -> str:
    """
    Get a quick count of all stored memory types.

    Returns counts for conversations, messages, knowledge entries, code snippets, and projects.

    Returns:
        JSON string with counts for each memory type.
    """
    result = await db.count_memories()
    return json.dumps(result, indent=2)


@mcp.tool()
async def search_by_tags(
    tags: list[str],
    limit: int = 20,
) -> str:
    """
    Search conversations, knowledge, and code snippets by tags.

    Finds all items that have ANY of the specified tags.

    Args:
        tags: List of tags to search for
        limit: Maximum results per category (default: 20)

    Returns:
        JSON string with matching conversations, knowledge items, and code snippets.
    """
    result = await db.search_by_tags(tags, min(limit, 50))
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_related_knowledge(
    knowledge_id: str,
    limit: int = 10,
) -> str:
    """
    Find knowledge entries related to a given one.

    Uses content similarity and shared tags to find related entries.

    Args:
        knowledge_id: UUID of the knowledge entry to find related items for
        limit: Maximum number of related items (default: 10)

    Returns:
        JSON string with related knowledge entries and their relevance scores.
    """
    results = await db.get_related_knowledge(knowledge_id, min(limit, 50))
    if not results:
        return json.dumps({"message": "No related knowledge found.", "results": []})
    return json.dumps({"count": len(results), "results": results}, indent=2)


@mcp.tool()
async def clear_platform_data(
    platform: str,
) -> str:
    """
    Delete ALL data for a specific platform. ⚠️ This is destructive!

    Removes all conversations, knowledge entries, code snippets, and projects
    associated with the specified platform. Cannot be undone.

    Args:
        platform: The platform to clear all data for (e.g., 'antigravity', 'cursor')

    Returns:
        JSON string with deletion counts per entity type.
    """
    result = await db.clear_platform_data(platform.lower().strip())
    return json.dumps(result, indent=2)


@mcp.tool()
async def save_code_snippet(
    title: str,
    language: str,
    code: str,
    description: str = "",
    tags: list[str] = [],
    source_platform: str = "",
) -> str:
    """
    Save a reusable code snippet with language tag.

    Store useful code patterns, solutions, and templates for later retrieval.

    Args:
        title: Short descriptive title for the snippet
        language: Programming language (e.g., 'python', 'javascript', 'bash')
        code: The actual code content
        description: Optional longer description of what the code does
        tags: Optional tags for categorization
        source_platform: The platform where this snippet was created

    Returns:
        JSON string with the saved snippet ID and details.
    """
    result = await db.save_code_snippet(
        title=title,
        language=language.lower().strip(),
        code=code,
        description=description or None,
        tags=tags,
        source_platform=source_platform.lower().strip() if source_platform else None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def search_code_snippets(
    query: str,
    language: str = "",
    tags: list[str] = [],
    limit: int = 10,
) -> str:
    """
    Search stored code snippets by keyword, language, or tags.

    Args:
        query: Search query (keywords or description)
        language: Optional - filter by programming language
        tags: Optional - filter by tags
        limit: Maximum results (default: 10)

    Returns:
        JSON string with matching code snippets including full code.
    """
    results = await db.search_code_snippets(
        query=query,
        language=language.lower().strip() if language else None,
        tags=tags if tags else None,
        limit=min(limit, 50),
    )
    if not results:
        return json.dumps({"message": "No matching code snippets found.", "results": []})
    return json.dumps({"count": len(results), "results": results}, indent=2)


@mcp.tool()
async def save_project_context(
    name: str,
    description: str = "",
    tech_stack: list[str] = [],
    repo_url: str = "",
    context: dict = {},
    tags: list[str] = [],
    source_platform: str = "",
) -> str:
    """
    Save or update project-level context (tech stack, repos, architecture, etc.).

    If a project with the same name already exists, it will be updated (merged).
    Use this to store high-level project information that persists across conversations.

    Args:
        name: Project name (unique identifier)
        description: What the project does
        tech_stack: List of technologies used (e.g., ['python', 'postgresql', 'docker'])
        repo_url: Git repository URL
        context: Additional context as key-value pairs (e.g., {"api_port": 8080, "database": "postgresql"})
        tags: Tags for categorization
        source_platform: The platform where this was recorded

    Returns:
        JSON string with the saved/updated project details.
    """
    result = await db.save_project_context(
        name=name,
        description=description or None,
        tech_stack=tech_stack,
        repo_url=repo_url or None,
        context=context,
        tags=tags,
        source_platform=source_platform.lower().strip() if source_platform else None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_project_context(
    name: str,
) -> str:
    """
    Retrieve all stored context for a project by name.

    Returns the full project record including description, tech stack,
    repository URL, custom context, and tags.

    Args:
        name: The project name to look up

    Returns:
        JSON string with the full project context, or error if not found.
    """
    result = await db.get_project_context(name)
    if not result:
        return json.dumps({"error": "Project not found", "name": name})
    return json.dumps(result, indent=2)


# ─── Short-Term Memory Tools ─────────────────────────────────────────────────


@mcp.tool()
async def save_short_term_memory(
    content: str,
    context_key: str = "",
    source_platform: str = "",
    tags: list[str] = [],
    ttl_minutes: int = 60,
    importance: float = 0.3,
) -> str:
    """
    Save a short-term / working memory entry that auto-expires.

    Use this for transient context that is relevant NOW but won't matter later:
    - "User is currently debugging authentication"
    - "We are working on the payment module"
    - "User's current file is server.py"
    - "User wants responses in bullet points for this session"

    Short-term memories automatically expire after ttl_minutes. Important ones
    (importance >= 0.5) can be promoted to long-term via consolidate_memories.

    Args:
        content: The context/information to remember temporarily
        context_key: Optional grouping key (e.g., 'current_task', 'session_prefs', 'debug_context')
        source_platform: The platform this context came from
        tags: Optional tags for categorization
        ttl_minutes: How long to keep this memory (default: 60 minutes, max recommended: 1440 = 24h)
        importance: How important (0.0-1.0). Memories >= 0.5 are eligible for consolidation.

    Returns:
        JSON string with the saved short-term memory details and expiry time.
    """
    result = await db.save_short_term_memory(
        content=content,
        context_key=context_key or None,
        source_platform=source_platform.lower().strip() if source_platform else None,
        tags=tags,
        ttl_minutes=ttl_minutes,
        importance=importance,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_working_context(
    context_key: str = "",
    source_platform: str = "",
    limit: int = 20,
) -> str:
    """
    Get all active (non-expired) short-term memories — the current working context.

    Call this at the start of a conversation to load the user's current context:
    what they're working on, recent decisions, session preferences, etc.

    Args:
        context_key: Optional — filter by context key (e.g., 'current_task')
        source_platform: Optional — filter by platform
        limit: Maximum entries to return (default: 20)

    Returns:
        JSON string with active short-term memory entries.
    """
    results = await db.get_active_short_term_memories(
        context_key=context_key or None,
        source_platform=source_platform.lower().strip() if source_platform else None,
        limit=min(limit, 50),
    )
    return json.dumps({"active_count": len(results), "entries": results}, indent=2)


# ─── Smart Recall Tool ──────────────────────────────────────────────────────


@mcp.tool()
async def recall(
    query: str,
    platform: str = "",
    memory_types: list[str] = [],
    limit: int = 15,
) -> str:
    """
    🧠 Unified smart recall — searches ALL memory stores at once with intelligent ranking.

    This is the BEST tool for retrieving relevant memories. It searches across:
    - Short-term memory (current working context)
    - Knowledge (long-term semantic memory — facts, preferences, instructions)
    - Conversations (episodic memory — past interactions)
    - Code snippets (procedural memory — how to do things)

    Results are ranked by a composite score blending:
    - Text relevance (40%) — how well content matches the query
    - Recency (30%) — newer memories score higher
    - Importance (30%) — more important memories score higher

    Accessed memories automatically get their access_count incremented,
    which protects them from future importance decay.

    Args:
        query: What to search for (natural language or keywords)
        platform: Optional — filter to a specific platform
        memory_types: Optional — limit to specific types: 'short_term', 'knowledge', 'episodic', 'procedural'
        limit: Maximum total results across all types (default: 15)

    Returns:
        JSON string with ranked results from all memory stores.
    """
    result = await db.recall(
        query=query,
        platform=platform.lower().strip() if platform else None,
        memory_types=memory_types if memory_types else None,
        limit=min(limit, 50),
    )
    return json.dumps(result, indent=2)


# ─── Memory Maintenance Tools ───────────────────────────────────────────────


@mcp.tool()
async def consolidate_memories(
    source_platform: str = "",
) -> str:
    """
    Promote important short-term memories into long-term knowledge.

    Finds all non-expired short-term memories with importance >= 0.5 and
    saves each as a permanent knowledge entry. The short-term entry is
    then marked as consolidated.

    Call this periodically or at the end of a work session to preserve
    important transient context permanently.

    Args:
        source_platform: Optional — only consolidate memories from this platform

    Returns:
        JSON string with count of consolidated entries and their details.
    """
    result = await db.consolidate_memories(
        source_platform=source_platform.lower().strip() if source_platform else None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def cleanup_expired_memories() -> str:
    """
    Delete all expired short-term memories and expired knowledge entries.

    Frees up storage by removing memories that have passed their expiry time.
    Call this periodically for housekeeping.

    Returns:
        JSON string with counts of deleted entries.
    """
    result = await db.cleanup_expired_memories()
    return json.dumps(result, indent=2)


@mcp.tool()
async def decay_memories(
    decay_factor: float = 0.95,
) -> str:
    """
    Apply time-based importance decay to all memories.

    Gradually reduces importance scores of memories that haven't been
    accessed recently. This ensures that frequently-used memories stay
    prominent while rarely-used ones fade.

    Formula: new_importance = importance × decay_factor ^ (days_since_access / 30)
    Minimum importance is clamped at 0.05 so memories never vanish completely.

    Memories that are accessed (via recall or search) get their access_count
    incremented, which protects them from decay.

    Args:
        decay_factor: Rate of decay (0.0-1.0, default 0.95). Lower = faster decay.

    Returns:
        JSON string with count of affected entries.
    """
    result = await db.decay_memories(max(0.5, min(1.0, decay_factor)))
    return json.dumps(result, indent=2)


@mcp.tool()
async def memory_health() -> str:
    """
    Get a comprehensive health overview of the entire memory system.

    Shows statistics broken down by memory type:
    - Episodic memory: conversation/message counts, avg importance
    - Semantic memory: knowledge entries, consolidated count, avg importance
    - Short-term memory: active, expired, consolidated, expiring soon
    - Procedural memory: code snippet count

    Use this to understand the state of the memory system and decide
    whether maintenance (consolidation, cleanup, decay) is needed.

    Returns:
        JSON string with detailed memory health statistics.
    """
    result = await db.get_memory_health()
    return json.dumps(result, indent=2)


@mcp.tool()
async def reflect_and_compress(
    older_than_days: int = 7,
    min_conversations: int = 3,
    platform: str = "",
) -> str:
    """
    Compress old conversations into dense knowledge summaries (memory reflection).

    Finds clusters of old conversations, extracts key takeaways, and saves
    them as high-importance knowledge entries. Original conversations are
    marked as 'compressed' but NOT deleted.

    This is like your brain's memory consolidation during sleep — it turns
    many scattered experiences into compact, retrievable wisdom.

    Args:
        older_than_days: Only compress conversations older than this (default: 7)
        min_conversations: Minimum conversations needed to trigger compression (default: 3)
        platform: Optional — only compress conversations from this platform

    Returns:
        JSON string with compression results.
    """
    result = await db.reflect_and_compress(
        older_than_days=older_than_days,
        min_conversations=min_conversations,
        platform=platform.lower().strip() if platform else None,
    )
    return json.dumps(result, indent=2)


# ─── MCP Resources ───────────────────────────────────────────────────────────


@mcp.resource("memory://stats")
async def memory_stats() -> str:
    """Get database statistics: conversation count, knowledge count, platforms, and categories."""
    stats = await db.get_stats()
    return json.dumps(stats, indent=2)


@mcp.resource("memory://platforms")
async def memory_platforms() -> str:
    """Get list of all AI platforms that have stored conversations."""
    platforms = await db.get_platforms()
    return json.dumps({"platforms": platforms}, indent=2)


@mcp.resource("memory://health")
async def memory_health_resource() -> str:
    """Get comprehensive memory system health — episodic, semantic, short-term, and procedural stores."""
    result = await db.get_memory_health()
    return json.dumps(result, indent=2)


# ─── MCP Prompts (Discoverable Workflow Templates) ──────────────────────────


@mcp.prompt()
def start_conversation(platform: str = "unknown", topic: str = "") -> str:
    """
    Initialize a conversation with full memory context.
    Run this at the START of every conversation to load what you know.
    """
    return f"""You are starting a new conversation on platform '{platform}'.
Topic: {topic or 'general'}

STEP 1 — Load working context:
Call get_working_context(source_platform="{platform}")

STEP 2 — Recall relevant memories:
Call recall(query="{topic or 'recent context and user preferences'}", platform="{platform}", memory_types="short_term,semantic,episodic,procedural", limit=10)

STEP 3 — Greet with context:
Use the recalled memories to personalize your response. Reference past conversations, known preferences, and ongoing work. If you know the user's name, use it.

STEP 4 — Save current session context:
Call save_short_term_memory(content="Starting conversation about: {topic or 'general'}", context_key="current_task", source_platform="{platform}", importance=0.4, ttl_minutes=120)

You now have full memory context. Proceed naturally while watching for new preferences/facts to save."""


@mcp.prompt()
def end_conversation(
    platform: str = "unknown",
    title: str = "",
    outcome: str = "success",
) -> str:
    """
    Wrap up a conversation — save it to episodic memory, extract preferences,
    and consolidate short-term memories.
    """
    return f"""The conversation is ending. Perform these memory operations:

STEP 1 — Save the conversation to episodic memory:
Call save_conversation with:
- platform: "{platform}"
- title: "{title or 'Untitled conversation'}"
- summary: <write a 2-3 sentence summary of what was discussed/accomplished>
- messages: <the full message history>
- importance: <0.3-1.0 based on significance>
- outcome: "{outcome}"
- tags: <relevant topic tags>

STEP 2 — Extract and save any preferences/facts mentioned:
Call auto_extract_preferences with the conversation text and source_platform="{platform}".

STEP 3 — Consolidate important short-term memories to long-term:
Call consolidate_memories(source_platform="{platform}")

STEP 4 — Confirm to the user what was saved."""


@mcp.prompt()
def save_user_preference(
    preference: str = "",
    platform: str = "unknown",
) -> str:
    """
    Detect and save a user preference, fact, or decision.
    Use this whenever you notice the user expressing a preference.
    """
    return f"""Detected a user preference/fact. Save it properly:

Preference/Fact: "{preference}"
Platform: "{platform}"

CLASSIFICATION — Determine the category:
- 'preference' — User likes/dislikes something ("I prefer dark mode", "I use TypeScript")
- 'fact' — Objective information ("Our API runs on port 8080", "Team uses PostgreSQL")
- 'instruction' — Standing orders ("Always use type hints", "Never commit to main directly")
- 'decision' — Choices made ("We chose Next.js for the frontend", "Using MIT license")

IMPORTANCE — Score it:
- 0.9-1.0: Core identity ("I'm a backend developer", "Always use Python")
- 0.7-0.8: Strong preference ("I prefer functional programming")
- 0.5-0.6: General fact ("We deploy on Fridays")
- 0.3-0.4: Minor detail

ACTION — Use save_knowledge_smart (conflict-aware):
Call save_knowledge_smart(
    category=<detected category>,
    content="{preference or '<the preference/fact>'}",
    source_platform="{platform}",
    tags=<relevant tags like ["coding-style", "python"]>,
    importance=<scored importance>,
    confidence=1.0
)

This will automatically detect duplicates and cross-platform conflicts."""


@mcp.prompt()
def recall_everything(topic: str = "") -> str:
    """
    Deep recall — search ALL memory types for everything related to a topic.
    Use when the user asks "what do you know about X?"
    """
    return f"""The user wants to know everything you remember about: "{topic}"

STEP 1 — Hybrid recall across all memory types:
Call recall(query="{topic}", memory_types="short_term,semantic,episodic,procedural", limit=20)

STEP 2 — Search for related code snippets:
Call search_code_snippets(query="{topic}")

STEP 3 — Check related knowledge:
Call search_knowledge(query="{topic}")

STEP 4 — Synthesize and present:
Organize the results by type:
- 🧠 **What I know** (semantic memories — facts, preferences, decisions)
- 📝 **Past conversations** (episodic memories — what we discussed before)
- 💻 **Code & patterns** (procedural memories — saved code snippets)
- ⏱️ **Current context** (short-term memories — active session info)

Present in a clear, conversational format. Mention which platform each memory came from if relevant."""


@mcp.prompt()
def resolve_all_conflicts() -> str:
    """
    Review and resolve all pending cross-platform memory conflicts.
    Use when maintaining memory consistency.
    """
    return """Check for and resolve cross-platform memory conflicts:

STEP 1 — List pending conflicts:
Call list_conflicts(status="pending")

STEP 2 — For each conflict, analyze both sides:
- What does the existing knowledge say? (from which platform?)
- What does the conflicting content say? (from which platform?)
- Are they truly contradictory, or just different aspects?

STEP 3 — Choose a resolution strategy for each:
- 'keep_existing' — if the existing version is correct/newer
- 'use_new' — if the new content is more accurate/recent
- 'merge' — if both contain useful info (provide merged_content)
- 'keep_both' — if they're different aspects of the same topic

Call resolve_conflict(conflict_id=<id>, strategy=<chosen>, merged_content=<if merge>)

STEP 4 — Report what was resolved to the user."""


@mcp.prompt()
def memory_maintenance() -> str:
    """
    Run a full memory system health check and maintenance cycle.
    Cleanup, consolidate, compress, and report.
    """
    return """Run a complete memory maintenance cycle:

STEP 1 — Health check:
Call memory_health() to get system overview.

STEP 2 — Cleanup expired memories:
Call cleanup_expired_memories()

STEP 3 — Consolidate short-term → long-term:
Call consolidate_memories()

STEP 4 — Check for conflicts:
Call list_conflicts(status="pending")

STEP 5 — Report to user:
Summarize:
- Total memories across all types
- Memories cleaned up
- Memories consolidated
- Pending conflicts (if any)
- Memory system health status

If there are pending conflicts, ask if the user wants to resolve them."""


@mcp.prompt()
def onboard_new_user() -> str:
    """
    Onboard a new user — learn their preferences, tools, and working style
    through a friendly interview. Saves everything to memory.
    """
    return """You're meeting a new user for the first time. Learn about them and save everything.

ASK ABOUT (one topic at a time, conversationally):
1. **Name & role** — "What should I call you? What's your role?"
2. **Languages & frameworks** — "What programming languages do you work with most?"
3. **Tools & environment** — "What's your dev setup? (IDE, OS, terminal, etc.)"
4. **Coding style** — "Any coding conventions you follow? (tabs/spaces, naming style, etc.)"
5. **Current projects** — "What are you working on right now?"
6. **Communication style** — "Do you prefer detailed explanations or concise answers?"
7. **AI platforms** — "Which AI assistants do you use besides this one?"

FOR EACH ANSWER:
- Call save_knowledge_smart with the right category and importance
- Use tags like ["user-profile", "preference", "<topic>"]
- Set importance 0.8+ for core identity items, 0.6 for general prefs

ALSO:
- Call save_project_context if they mention specific projects
- Call save_short_term_memory for the onboarding session context

END WITH:
"Great! I've saved your preferences. They'll be available across ALL your AI platforms — Windsurf, Cursor, Gemini, Claude — wherever you connect this memory server."
"""


@mcp.prompt()
def debug_session(
    error_message: str = "",
    platform: str = "unknown",
) -> str:
    """
    Start a debugging session with full memory-assisted context.
    Recalls past similar bugs, relevant code, and project context.
    """
    return f"""Starting a debug session. Load all relevant context:

Error: "{error_message or '<to be described>'}"
Platform: "{platform}"

STEP 1 — Recall past similar issues:
Call recall(query="bug error {error_message[:100] if error_message else 'debugging'}", memory_types="episodic,semantic,procedural", limit=10)

STEP 2 — Load current working context:
Call get_working_context(source_platform="{platform}")

STEP 3 — Search for related code patterns:
Call search_code_snippets(query="{error_message[:50] if error_message else 'error handling'}")

STEP 4 — Assist with debugging:
- Reference any past conversations where similar bugs were fixed
- Use saved code patterns if applicable
- Note the user's preferred debugging approach from preferences

STEP 5 — Save context:
Call save_short_term_memory(content="Debugging: {error_message[:100] if error_message else 'active debug session'}", context_key="current_debug", source_platform="{platform}", ttl_minutes=180)

WHEN RESOLVED — Save the solution:
- save_conversation with outcome='success' and tags=['debugging', '<error-type>']
- save_code_snippet if a reusable fix was created
- save_knowledge if a new fact was learned (e.g., "Port 3000 conflicts with service X")
"""


# ─── Memory Versioning & Conflict Resolution Tools ──────────────────────────


@mcp.tool()
async def knowledge_history(
    knowledge_id: str,
    limit: int = 20,
) -> str:
    """
    Get the full version history of a knowledge entry.

    Shows the current version and all previous versions with diffs,
    who changed it, when, and why. Use this to audit changes and
    understand how knowledge evolved over time.

    Args:
        knowledge_id: UUID of the knowledge entry
        limit: Maximum number of history entries (default: 20)

    Returns:
        JSON with current state and version history.
    """
    result = await db.get_knowledge_history(knowledge_id, limit)
    return json.dumps(result, indent=2)


@mcp.tool()
async def rollback_knowledge(
    knowledge_id: str,
    target_version: int,
    rolled_back_by: str = "",
) -> str:
    """
    Rollback a knowledge entry to a previous version.

    Restores content, category, tags, importance from the target version.
    The current state is saved as a version before rollback, so nothing is lost.

    Use knowledge_history first to find the version number you want.

    Args:
        knowledge_id: UUID of the knowledge entry
        target_version: The version number to restore to
        rolled_back_by: Who initiated the rollback (platform name)

    Returns:
        JSON with rollback result.
    """
    result = await db.rollback_knowledge(
        knowledge_id, target_version,
        rolled_back_by=rolled_back_by.strip() or None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def save_knowledge_smart(
    category: str,
    content: str,
    tags: list[str] = [],
    source_platform: str = "",
    memory_type: str = "semantic",
    importance: float = 0.5,
    confidence: float = 1.0,
) -> str:
    """
    Save knowledge with automatic cross-platform conflict detection.

    This is the SMART version of save_knowledge. Before saving, it checks
    if similar knowledge already exists from a DIFFERENT platform.

    Behaviors:
    - Exact duplicate: silently skips (dedup)
    - Same platform, similar content: updates in place (with version tracking)
    - Different platform, conflicting content: creates a conflict for review
    - No match: saves normally

    Use this instead of save_knowledge when you want conflict awareness.

    Args:
        category: Category (fact, preference, instruction, decision)
        content: The knowledge content
        tags: Tags for searchability
        source_platform: Which platform is saving this
        memory_type: Type of memory (semantic, episodic, procedural)
        importance: 0.0-1.0 importance score
        confidence: 0.0-1.0 confidence in accuracy

    Returns:
        JSON with save result or conflict information.
    """
    result = await db.detect_and_save_or_conflict(
        category=category.lower().strip(),
        content=content,
        tags=tags or [],
        source_platform=source_platform.lower().strip() if source_platform else None,
        memory_type=memory_type,
        importance=importance,
        confidence=confidence,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_conflicts(
    status: str = "pending",
    limit: int = 20,
) -> str:
    """
    List memory conflicts between platforms.

    When different AI platforms save conflicting knowledge about the same
    topic, conflicts are created. Use this to review them and decide
    how to resolve (keep_existing, use_new, merge, or keep_both).

    Args:
        status: Filter by status — 'pending', 'resolved', or 'all' (default: pending)
        limit: Maximum conflicts to return (default: 20)

    Returns:
        JSON with list of conflicts showing both sides.
    """
    if status == "all":
        # Get both pending and resolved
        pending = await db.list_conflicts("pending", limit)
        resolved = await db.list_conflicts("resolved", limit)
        return json.dumps({
            "pending": pending["conflicts"],
            "resolved": resolved["conflicts"],
            "total_pending": pending["total"],
            "total_resolved": resolved["total"],
        }, indent=2)
    result = await db.list_conflicts(status, limit)
    return json.dumps(result, indent=2)


@mcp.tool()
async def resolve_conflict(
    conflict_id: str,
    strategy: str = "keep_existing",
    merged_content: str = "",
    resolved_by: str = "",
) -> str:
    """
    Resolve a memory conflict between platforms.

    Strategies:
    - 'keep_existing': Keep existing knowledge, discard the conflict
    - 'use_new': Replace existing with the new conflicting content
    - 'merge': Provide merged_content that combines both versions
    - 'keep_both': Save both as separate knowledge entries

    All changes are version-tracked — nothing is permanently lost.

    Args:
        conflict_id: UUID of the conflict to resolve
        strategy: Resolution strategy (keep_existing, use_new, merge, keep_both)
        merged_content: Required only for 'merge' strategy — the combined content
        resolved_by: Who resolved this conflict (platform name)

    Returns:
        JSON with resolution result.
    """
    result = await db.resolve_conflict(
        conflict_id=conflict_id,
        strategy=strategy,
        merged_content=merged_content.strip() or None,
        resolved_by=resolved_by.strip() or None,
    )
    return json.dumps(result, indent=2)


# ─── Background Memory Maintenance ──────────────────────────────────────────

MAINTENANCE_INTERVAL = int(os.environ.get("MAINTENANCE_INTERVAL_MINUTES", "30"))

async def _memory_maintenance_loop():
    """Background task that automatically maintains the memory system.

    Runs every MAINTENANCE_INTERVAL_MINUTES (default: 30) and performs:
    1. Cleanup expired short-term memories and knowledge
    2. Consolidate important short-term memories → long-term
    3. Apply importance decay to old, unaccessed memories
    4. Compress old conversations into dense knowledge (weekly)
    """
    cycle = 0
    while True:
        await asyncio.sleep(MAINTENANCE_INTERVAL * 60)
        cycle += 1
        try:
            # Every cycle: cleanup + consolidate
            cleanup = await db.cleanup_expired_memories()
            consolidate = await db.consolidate_memories()
            print(f"   🔄 Maintenance cycle {cycle}: "
                  f"cleaned {cleanup['total_deleted']}, "
                  f"consolidated {consolidate['consolidated']}")

            # Every 6 cycles (~3h): apply decay
            if cycle % 6 == 0:
                decay = await db.decay_memories()
                print(f"   📉 Decay applied: {decay['knowledge_updated']}K + {decay['conversations_updated']}C entries")

            # Every 48 cycles (~24h): compress old conversations
            if cycle % 48 == 0:
                compress = await db.reflect_and_compress()
                print(f"   🗜️  Compression: {compress.get('compressed_entries', 0)} clusters compressed")

        except Exception as e:
            print(f"   ⚠️  Maintenance error: {e}")


# ─── Server Entry Point ─────────────────────────────────────────────────────

async def main():
    """Initialize the database and start the MCP server."""
    import sys

    # Check for stdio mode
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        # Stdio mode (for local Docker exec)
        await db.init_db()
        await mcp.run_stdio_async()
    else:
        # HTTP mode (default)
        print("🧠 LLM Memory MCP Server starting...")
        print(f"   Initializing database...")

        await db.init_db()
        print("   ✅ Database initialized")

        # Start background maintenance
        asyncio.create_task(_memory_maintenance_loop())
        print(f"   🔄 Background maintenance every {MAINTENANCE_INTERVAL}min")

        print(f"   🚀 Starting MCP server on {HOST}:{PORT}")
        print(f"   📡 Streamable HTTP endpoint: http://{HOST}:{PORT}/mcp")
        print(f"   🔗 Connect your AI platforms to: http://localhost:{PORT}/mcp")
        print()

        # Add CORS middleware to allow connections from any origin (e.g., web clients)
        # FastMCP uses Starlette under the hood, so we can access .app
        if hasattr(mcp, "_app") and mcp._app:
             from starlette.middleware.cors import CORSMiddleware
             mcp._app.add_middleware(
                 CORSMiddleware,
                 allow_origins=["*"],
                 allow_credentials=True,
                 allow_methods=["*"],
                 allow_headers=["*"],
             )

        await mcp.run_streamable_http_async()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

