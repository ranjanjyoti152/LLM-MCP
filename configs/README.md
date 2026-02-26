# LLM Memory MCP Server — Platform Configuration Guide

Connect your AI platforms to the shared memory server at `http://localhost:4040/mcp`.

---

## 🟢 Antigravity (Google)

Add to your MCP configuration (Settings → MCP Servers, or edit `mcp_config.json`):

```json
{
  "mcpServers": {
    "llm-memory": {
      "serverUrl": "http://localhost:4040/mcp"
    }
  }
}
```

---

## 🟣 Cursor

Go to **Settings → MCP Servers → Add Server**, or edit `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "llm-memory": {
      "url": "http://localhost:4040/mcp"
    }
  }
}
```

For global configuration, edit `~/.cursor/mcp.json`.

---

## 🔵 VS Code + GitHub Copilot

Edit `.vscode/mcp.json` in your workspace (or user settings for global):

```json
{
  "servers": {
    "llm-memory": {
      "type": "http",
      "url": "http://localhost:4040/mcp"
    }
  }
}
```

Or add via **Command Palette** → `MCP: Add Server` → choose HTTP → enter URL `http://localhost:4040/mcp`.

---

## 🟡 Gemini CLI

Add to your Gemini CLI settings file (`~/.gemini/settings.json`):

```json
{
  "mcpServers": {
    "llm-memory": {
      "httpUrl": "http://localhost:4040/mcp"
    }
  }
}
```

---

## 🔴 Claude Desktop

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "llm-memory": {
      "url": "http://localhost:4040/mcp"
    }
  }
}
```

---

## 🌐 ChatGPT / Other Platforms

For platforms that support custom MCP servers via HTTP, use this endpoint:

```
http://localhost:4040/mcp
```

Transport: **Streamable HTTP** (POST/GET with optional SSE streaming)

---

## Available Tools (25)

Once connected, these tools will be available to your AI assistant:

| Tool | What it does |
|------|-------------|
| **Conversations** | |
| `save_conversation` | Save a conversation with messages, tags, and metadata |
| `search_memory` | Full-text search across all stored conversations |
| `get_recent_conversations` | Get latest conversations (optional platform filter) |
| `get_conversation_by_id` | Retrieve a specific conversation by UUID |
| `add_message_to_conversation` | Append messages to an existing conversation |
| `tag_conversation` | Add or remove tags from a conversation |
| `delete_memory` | Remove a specific conversation or knowledge entry |
| **Knowledge** | |
| `save_knowledge` | Store facts, preferences, instructions, project info |
| `search_knowledge` | Search stored knowledge by query, category, or tags |
| `list_all_knowledge` | List all knowledge with optional category filter |
| `get_knowledge_by_category` | Get entries in a specific category |
| `get_related_knowledge` | Find related entries by content similarity |
| `update_knowledge` | Update content, category, or tags on an entry |
| `auto_extract_preferences` | Auto-extract & save preferences from conversation text |
| `get_context_summary` | Get combined context summary for a topic |
| **Code Snippets** | |
| `save_code_snippet` | Save a reusable code snippet with language tag |
| `search_code_snippets` | Search snippets by keyword, language, or tags |
| **Projects** | |
| `save_project_context` | Save/update project-level context (tech stack, repos) |
| `get_project_context` | Retrieve stored context for a project by name |
| **Utility** | |
| `search_by_tags` | Search conversations, knowledge, and snippets by tags |
| `count_memories` | Get a quick count of all stored memory types |
| `summarize_platform_activity` | Get detailed activity summary for a platform |
| `export_memories` | Export all data as JSON for backup |
| `import_memories` | Import data from a JSON backup |
| `clear_platform_data` | Delete ALL data for a specific platform ⚠️ |

## Quick Test

After starting the server, ask your AI assistant:

> "Use the LLM Memory tools to save a knowledge entry: I prefer Python for backend development."

Then switch to a **different** AI platform and ask:

> "Search my memory for my programming language preferences."

The knowledge should appear across platforms! 🎉
