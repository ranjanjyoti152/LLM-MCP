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

## Available Tools

Once connected, these tools will be available to your AI assistant:

| Tool | What it does |
|------|-------------|
| `save_conversation` | Save a conversation with messages, tags, and metadata |
| `search_memory` | Full-text search across all stored conversations |
| `get_recent_conversations` | Get latest conversations (optional platform filter) |
| `save_knowledge` | Store facts, preferences, instructions, project info |
| `search_knowledge` | Search stored knowledge by query, category, or tags |
| `get_context_summary` | Get combined context summary for a topic |
| `delete_memory` | Remove a specific conversation or knowledge entry |

## Quick Test

After starting the server, ask your AI assistant:

> "Use the LLM Memory tools to save a knowledge entry: I prefer Python for backend development."

Then switch to a **different** AI platform and ask:

> "Search my memory for my programming language preferences."

The knowledge should appear across platforms! 🎉
