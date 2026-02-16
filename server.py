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
    Use these tools to save and retrieve conversations, knowledge, and context.

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
    - OR use 'auto_extract_preferences' to batch-extract from a conversation
    - Always include relevant tags for searchability
    - Always set source_platform to your platform name

    OTHER GUIDELINES:
    - When finishing a meaningful conversation, use 'save_conversation' to
      preserve the exchange for future context.
    - Before answering questions about past interactions, use 'search_memory'
      or 'get_context_summary' to check if relevant information exists.
    - When the user asks "what do you remember about X", use 'search_memory'
      and 'search_knowledge' to find relevant past interactions.
    - Tag entries with the current platform name so cross-platform searches work.
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
) -> str:
    """
    Save a conversation to persistent memory.

    Args:
        platform: The AI platform name (e.g., 'antigravity', 'cursor', 'vscode', 'gemini', 'chatgpt')
        messages: List of message objects, each with 'role' ('user'/'assistant'/'system') and 'content'
        title: A short title describing the conversation topic
        summary: A brief summary of what was discussed
        tags: Optional list of tags for categorization (e.g., ['python', 'debugging', 'docker'])

    Returns:
        JSON string with the saved conversation details including its ID.
    """
    result = await db.save_conversation(
        platform=platform.lower().strip(),
        messages=messages,
        title=title or None,
        summary=summary or None,
        tags=tags,
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
) -> str:
    """
    Save a knowledge entity — a fact, preference, instruction, or important information.

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

    Returns:
        JSON string with the saved knowledge entry details.
    """
    result = await db.save_knowledge(
        category=category.lower().strip(),
        content=content,
        tags=tags,
        source_platform=source_platform.lower().strip() if source_platform else None,
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

