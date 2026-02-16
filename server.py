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
    print("🧠 LLM Memory MCP Server starting...")
    print(f"   Initializing database...")

    await db.init_db()
    print("   ✅ Database initialized")

    print(f"   🚀 Starting MCP server on {HOST}:{PORT}")
    print(f"   📡 Streamable HTTP endpoint: http://{HOST}:{PORT}/mcp")
    print(f"   🔗 Connect your AI platforms to: http://localhost:{PORT}/mcp")
    print()

    await mcp.run_streamable_http_async()


if __name__ == "__main__":
    asyncio.run(main())
