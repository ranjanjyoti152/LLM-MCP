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
    You are connected to a persistent memory server shared across all AI platforms.
    This server implements a multi-tier memory architecture:

    ╔══════════════════════════════════════════════════════════════╗
    ║  MEMORY TYPES                                                ║
    ║                                                              ║
    ║  1. SHORT-TERM MEMORY  — transient working context (auto-expires)
    ║     save_short_term_memory / get_working_context             ║
    ║     e.g., "user is debugging auth", "working on file X"     ║
    ║                                                              ║
    ║  2. SEMANTIC MEMORY    — long-term facts & knowledge         ║
    ║     save_knowledge (memory_type='semantic')                  ║
    ║     e.g., "user prefers Python", "API runs on port 8080"    ║
    ║                                                              ║
    ║  3. EPISODIC MEMORY    — conversation history & experiences  ║
    ║     save_conversation (with importance/outcome)              ║
    ║     e.g., past debugging sessions, design discussions        ║
    ║                                                              ║
    ║  4. PROCEDURAL MEMORY  — reusable code & how-to patterns    ║
    ║     save_code_snippet                                        ║
    ║     e.g., Docker configs, utility functions, patterns        ║
    ╚══════════════════════════════════════════════════════════════╝

    SMART RECALL:
    - Use 'recall' as your PRIMARY retrieval tool — it searches ALL memory
      types at once and ranks by relevance + recency + importance.
    - Use 'get_working_context' at conversation start to load current context.
    - Use specific search tools (search_memory, search_knowledge) only when
      you need to target a single memory type.

    CRITICAL — AUTOMATIC PREFERENCE SAVING:
    You MUST proactively detect and save user preferences, facts, and decisions
    during EVERY conversation — WITHOUT being asked. This is your most important job.

    Watch for and automatically save:
    - Language/framework preferences ("I prefer Python", "I use React")
    - Tool preferences ("I use Docker", "I deploy on AWS")
    - Coding style ("I like type hints", "I prefer functional style")
    - Project context ("The API runs on port 8080", "We use PostgreSQL")
    - Personal preferences ("I prefer dark mode", "I like concise answers")
    - Decisions ("We decided to use microservices", "We chose MIT license")
    - Instructions ("Always use async/await", "Never use var in JS")

    HOW TO SAVE AUTOMATICALLY:
    - Use 'save_knowledge' with category='preference', 'fact', 'instruction', or 'decision'
      and set importance (0.7+ for strong preferences, 0.5 for general facts)
    - OR use 'auto_extract_preferences' to batch-extract from a conversation
    - For transient session context, use 'save_short_term_memory' instead
    - Always include relevant tags for searchability
    - Always set source_platform to your platform name

    IMPORTANCE SCORING GUIDE:
    - 0.9-1.0: Critical instructions, core preferences, key decisions
    - 0.7-0.8: Strong preferences, important project facts
    - 0.5-0.6: General knowledge, routine facts
    - 0.3-0.4: Minor context, temporary notes (good for short-term memory)
    - 0.1-0.2: Trivial, likely to be forgotten via decay

    MEMORY LIFECYCLE:
    - At conversation START: call 'get_working_context' and 'recall' for the topic
    - DURING conversation: save short-term context, detect preferences
    - At conversation END: save_conversation, auto_extract_preferences,
      consolidate_memories (promotes important short-term → long-term)
    - PERIODICALLY: cleanup_expired_memories, decay_memories

    OTHER GUIDELINES:
    - When the user asks "what do you remember about X", use 'recall' first.
    - Tag entries with the current platform name so cross-platform searches work.
    - Set outcome ('success'/'failure'/'partial') on conversations for episodic recall.
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
) -> str:
    """
    Update an existing knowledge entry.

    Args:
        knowledge_id: The UUID of the knowledge entry to update
        content: New content (leave empty to keep existing)
        category: New category (leave empty to keep existing)
        tags: New tags (leave empty to keep existing)

    Returns:
        JSON string with updated knowledge entry details.
    """
    result = await db.update_knowledge(
        knowledge_id=knowledge_id,
        content=content or None,
        category=category.lower().strip() or None,
        tags=tags or None,
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

