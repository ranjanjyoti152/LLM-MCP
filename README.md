<p align="center">
  <h1 align="center">🧠 LLM Memory MCP Server</h1>
  <p align="center">
    <strong>A unified, persistent memory layer for all your AI coding assistants.</strong>
  </p>
  <p align="center">
    Save conversations, knowledge, and context from <em>any</em> platform — retrieve it from <em>every</em> platform.
  </p>
  <p align="center">
    <a href="#-quick-start"><img src="https://img.shields.io/badge/Get_Started-blue?style=for-the-badge" alt="Get Started"></a>
    <img src="https://img.shields.io/badge/python-3.12-blue?style=flat-square&logo=python&logoColor=white" alt="Python 3.12">
    <img src="https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL 16">
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/MCP-Streamable_HTTP-green?style=flat-square" alt="MCP">
    <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="MIT">
  </p>
</p>

---

## 💡 The Problem

You use **multiple AI assistants** daily — Antigravity, Cursor, VS Code Copilot, Gemini, ChatGPT — but **none of them remember** what you discussed in the other.  

Every time you switch platforms, you start from scratch. Your preferences, project context, past decisions — all lost.

## ✨ The Solution

**LLM Memory MCP Server** gives every AI platform a **shared brain**. It stores your conversations, knowledge, and preferences in a PostgreSQL database, accessible via the open [Model Context Protocol (MCP)](https://modelcontextprotocol.io) standard.

> **Save a fact in Cursor → recall it in Antigravity → search for it in VS Code.**

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        YOUR AI PLATFORMS                             │
│                                                                      │
│  ┌─────────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌───────────┐  │
│  │ Antigravity  │ │ Cursor │ │ VS Code  │ │ Gemini │ │  ChatGPT  │  │
│  │   (Google)   │ │        │ │ Copilot  │ │  CLI   │ │  / Claude │  │
│  └──────┬───────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └─────┬─────┘  │
│         │             │           │            │            │         │
└─────────┼─────────────┼───────────┼────────────┼────────────┼────────┘
          │             │           │            │            │
          ▼             ▼           ▼            ▼            ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Streamable HTTP  (:4040/mcp)                   │
    │  ┌───────────────────────────────────────────────────────┐  │
    │  │             🧠 LLM Memory MCP Server                  │  │
    │  │                                                       │  │
    │  │  ┌──────────────────┐  ┌────────────────────────┐     │  │
    │  │  │  33 MCP Tools    │  │    3 MCP Resources     │     │  │
    │  │  │  save, recall,   │  │  stats, platforms,     │     │  │
    │  │  │  consolidate,    │  │  health                │     │  │
    │  │  │  compress, decay │  │                        │     │  │
    │  │  └────────┬─────────┘  └───────────┬────────────┘     │  │
    │  │           │    Background Scheduler (auto-maintain)    │  │
    │  └───────────┼────────────────────────┼──────────────────┘  │
    └──────────────┼────────────────────────┼─────────────────────┘
                   │                        │
                   ▼                        ▼
    ┌─────────────────────────────────────────────────────────────┐
    │           PostgreSQL 16 + pgvector  (:4569)                 │
    │                                                             │
    │  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐       │
    │  │  Episodic     │ │  Semantic    │ │  Short-Term    │       │
    │  │  (convos +    │ │  (knowledge  │ │  (TTL, auto-   │       │
    │  │   messages)   │ │   + vectors) │ │   expire)      │       │
    │  └──────────────┘ └──────────────┘ └────────────────┘       │
    │  ┌──────────────┐                                           │
    │  │  Procedural   │  Full-Text (GIN) + Vector (HNSW) Indexes │
    │  │  (code snips) │  Hybrid Search: semantic + keyword       │
    │  └──────────────┘                                           │
    └─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Supported Platforms

| Platform | Transport | Status |
|:---------|:----------|:------:|
| **Antigravity** (Google) | Streamable HTTP | ✅ Ready |
| **Cursor** | Streamable HTTP | ✅ Ready |
| **VS Code** + GitHub Copilot | Streamable HTTP | ✅ Ready |
| **Gemini CLI** | Streamable HTTP | ✅ Ready |
| **Claude Desktop** | Streamable HTTP | ✅ Ready |
| **ChatGPT** (MCP-compatible) | Streamable HTTP | ✅ Ready |
| Any MCP-compatible client | Streamable HTTP | ✅ Ready |

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/) installed
- Git (optional, for cloning)

### 1. One-Command Setup (Recommended)

```bash
git clone https://github.com/YOUR_USERNAME/LLM-MCP.git
cd LLM-MCP
./setup.sh
```

The setup script will:
- Start PostgreSQL (with pgvector) + MCP Server
- Wait for health checks
- Auto-detect Cursor, VS Code, Gemini CLI, Claude, Windsurf
- Generate config files for each detected platform

### 2. Manual Start (Alternative)

```bash
docker compose up -d --build
```

### 3. Verify

```bash
docker compose ps
# llm-mcp-postgres   ... Up (healthy)   0.0.0.0:4569->5432/tcp
# llm-mcp-server     ... Up             0.0.0.0:4040->4040/tcp
```

### 4. Test It!

Ask your AI assistant:

> *"Save a knowledge entry: I prefer Python for backend and use Docker for everything."*

Switch to a **different** AI platform and ask:

> *"Search my memory for my tech preferences."*

✨ The knowledge persists across all your platforms!

---

## 🔧 Platform Configuration

### <img src="https://img.shields.io/badge/-Antigravity-4285F4?style=flat-square&logo=google&logoColor=white" alt="Antigravity"> Antigravity (Google)

**Option A** — Via UI: Go to **Settings → MCP Servers → Add** and paste the URL.

**Option B** — Via config file (`mcp_config.json`):

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

### <img src="https://img.shields.io/badge/-Cursor-000000?style=flat-square&logo=cursor&logoColor=white" alt="Cursor"> Cursor

**Option A** — Via UI: **Settings → MCP Servers → Add New MCP Server**

**Option B** — Project-level config (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "llm-memory": {
      "url": "http://localhost:4040/mcp"
    }
  }
}
```

**Option C** — Global config (`~/.cursor/mcp.json`) — applies to all projects.

---

### <img src="https://img.shields.io/badge/-VS_Code-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white" alt="VS Code"> VS Code + GitHub Copilot

**Option A** — Via Command Palette: `Ctrl+Shift+P` → `MCP: Add Server` → HTTP → enter `http://localhost:4040/mcp`

**Option B** — Workspace config (`.vscode/mcp.json`):

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

**Option C** — User settings (global): Add the same config to your VS Code user `settings.json` under `"mcp"`.

---

### <img src="https://img.shields.io/badge/-Gemini_CLI-8E75B2?style=flat-square&logo=googlegemini&logoColor=white" alt="Gemini"> Gemini CLI

Edit `~/.gemini/settings.json`:

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

### <img src="https://img.shields.io/badge/-Claude-D4A574?style=flat-square" alt="Claude"> Claude Desktop

**Option A - Local (Best Performance)**
If you are running the server on the same machine as Claude, connect directly via Docker.
**This requires no extra tools and is the fastest method.**

Go to **Settings → Developer → Edit Config** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "llm-memory": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "llm-mcp-server",
        "python",
        "server.py",
        "stdio"
      ]
    }
  }
}
```

### <img src="https://img.shields.io/badge/-Claude-D4A574?style=flat-square" alt="Claude"> Claude Desktop

**Option A - Local (Best Performance)**
If you are running the server on the same machine as Claude, connect directly via Docker.
**This requires no extra tools and is the fastest method.**

Go to **Settings → Developer → Edit Config** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "llm-memory": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "llm-mcp-server",
        "python",
        "server.py",
        "stdio"
      ]
    }
  }
}
```



### <img src="https://img.shields.io/badge/-ChatGPT-74AA9C?style=flat-square&logo=openai&logoColor=white" alt="ChatGPT"> ChatGPT / Other MCP Clients

For any platform that supports MCP via HTTP, use:

```
Endpoint:   http://localhost:4040/mcp
Transport:  Streamable HTTP (POST/GET with optional SSE streaming)
```

---

## 🛠️ Available MCP Tools (25)

### 💬 Conversations

| Tool | Description | Example Use |
|:-----|:------------|:------------|
| `save_conversation` | Save a full conversation with messages, platform tag, and metadata | *"Save this conversation about Docker debugging"* |
| `search_memory` | Full-text search across all stored conversations & messages | *"What did we discuss about authentication last week?"* |
| `get_recent_conversations` | Retrieve latest conversations, optionally filtered by platform | *"Show me my recent Cursor conversations"* |
| `get_conversation_by_id` | Retrieve a specific conversation by UUID, including all messages | *"Get conversation abc-123"* |
| `add_message_to_conversation` | Append new messages to an existing conversation | *"Add this follow-up to our previous chat"* |
| `tag_conversation` | Add or remove tags from a conversation | *"Tag this conversation as 'important'"* |
| `delete_memory` | Delete a specific conversation or knowledge entry by ID | *"Delete conversation abc-123"* |

### 🧠 Knowledge

| Tool | Description | Example Use |
|:-----|:------------|:------------|
| `save_knowledge` | Store a fact, preference, instruction, or decision | *"Remember: I use PostgreSQL 16 for all projects"* |
| `search_knowledge` | Search knowledge entries by query, category, or tags | *"What are my coding preferences?"* |
| `list_all_knowledge` | List all stored knowledge with optional category filter and pagination | *"Show me all my preferences"* |
| `get_knowledge_by_category` | Get all knowledge entries in a specific category | *"List all my instructions"* |
| `get_related_knowledge` | Find knowledge entries related to a given one by content similarity | *"What's related to this fact?"* |
| `update_knowledge` | Update an existing knowledge entry's content, category, or tags | *"Update my Python version preference"* |
| `auto_extract_preferences` | Automatically extract & save preferences from conversation text with deduplication | *"Extract preferences from this chat"* |
| `get_context_summary` | Get a combined overview of knowledge + conversations for a topic | *"Give me context on the payment system project"* |

### 💾 Code Snippets

| Tool | Description | Example Use |
|:-----|:------------|:------------|
| `save_code_snippet` | Save a reusable code snippet with language, tags, and description | *"Save this Docker compose template"* |
| `search_code_snippets` | Search stored snippets by keyword, language, or tags | *"Find my Python async patterns"* |

### 📂 Projects

| Tool | Description | Example Use |
|:-----|:------------|:------------|
| `save_project_context` | Save or update project-level context (tech stack, repos, architecture) | *"Save context for the e-commerce project"* |
| `get_project_context` | Retrieve all stored context for a project by name | *"What's the setup for project X?"* |

### 🔧 Utility

| Tool | Description | Example Use |
|:-----|:------------|:------------|
| `search_by_tags` | Search conversations, knowledge, and snippets by tags | *"Find everything tagged 'docker'"* |
| `count_memories` | Get a quick count of all stored memory types | *"How much data is stored?"* |
| `summarize_platform_activity` | Get detailed activity summary for a specific platform | *"Show my Antigravity stats"* |
| `export_memories` | Export all stored data as JSON for backup | *"Back up all my memories"* |
| `import_memories` | Import data from a JSON backup (with deduplication) | *"Restore from backup"* |
| `clear_platform_data` | Delete ALL data for a specific platform ⚠️ | *"Clear all test_client data"* |

### 📊 MCP Resources

| Resource URI | Description |
|:-------------|:------------|
| `memory://stats` | Database statistics — total conversations, messages, knowledge items, platform breakdown |
| `memory://platforms` | List of all AI platforms that have stored data |

---

## 📁 Project Structure

```
LLM-MCP/
├── docker-compose.yml       # Orchestrates PostgreSQL + MCP Server
├── Dockerfile               # Python 3.12 slim container for MCP server
├── .env                     # Environment variables (ports, credentials)
├── requirements.txt         # Python dependencies
├── server.py                # FastMCP server — 25 tools + 2 resources
├── db.py                    # Async database layer (asyncpg + full-text search)
├── test_client.py           # End-to-end verification script
├── configs/
│   └── README.md            # Per-platform configuration snippets
└── README.md                # This file
```

---

## ⚙️ Configuration

All settings are in `.env`:

| Variable | Default | Description |
|:---------|:--------|:------------|
| `POSTGRES_PORT` | `4569` | Host port for PostgreSQL |
| `MCP_PORT` | `4040` | Host port for MCP server |
| `POSTGRES_USER` | `mcp_user` | Database username |
| `POSTGRES_PASSWORD` | `mcp_secure_pass_2026` | Database password |
| `POSTGRES_DB` | `mcp_memory` | Database name |
| `MCP_HOST` | `0.0.0.0` | MCP server bind address |

### Accessing from Other Machines (LAN)

If your AI platform runs on a different machine on your local network, replace `localhost` with your server's IP:

```
http://192.168.100.69:4040/mcp
```

---


## 🧪 Testing

### Automated Test Client

```bash
# Install dependencies locally (if not using Docker)
pip install mcp[cli] asyncpg python-dotenv

# Run the full test suite
python test_client.py
```

The test client exercises all 7 tools and 2 resources, verifying:
- ✅ Conversation save & retrieval
- ✅ Knowledge storage & search
- ✅ Full-text search across messages
- ✅ Context summary generation
- ✅ Resource endpoints (stats, platforms)
- ✅ Delete operations

### Manual Verification

```bash
# Check PostgreSQL is accessible
docker exec llm-mcp-postgres psql -U mcp_user -d mcp_memory -c "SELECT COUNT(*) FROM conversations;"

# Check MCP server logs
docker logs -f llm-mcp-server

# Restart the stack
docker compose restart
```

---

## 📋 Docker Commands Reference

| Command | Description |
|:--------|:------------|
| `docker compose up -d` | Start all services in background |
| `docker compose down` | Stop all services |
| `docker compose restart` | Restart all services |
| `docker compose logs -f mcp-server` | Stream MCP server logs |
| `docker compose ps` | Check service status |
| `docker compose down -v` | Stop & **delete all data** ⚠️ |

---

## 🗄️ Database Schema

Five core tables with hybrid search indexes:

```sql
-- Episodic memory (importance, outcome, emotional_context, embedding)
conversations  →  one-to-many  →  messages (role, content)

-- Semantic memory (memory_type, importance, confidence, embedding, expires_at)
knowledge (category, content, tags, source_platform)

-- Short-term / working memory (auto-expires via TTL, consolidation support)
short_term_memory (content, context_key, importance, expires_at, consolidated)

-- Procedural memory (importance, embedding)
code_snippets (title, language, code, description)
```

**Indexes:** GIN full-text indexes + HNSW vector indexes (pgvector) for hybrid semantic + keyword search. Importance and expiry indexes for efficient maintenance.

---

## 🔒 Security Notes

- By default, the server binds to `0.0.0.0` (accessible from your network)
- For **local-only** use, set `MCP_HOST=127.0.0.1` in `.env`
- Change the default `POSTGRES_PASSWORD` in production
- Consider adding a reverse proxy (nginx/Caddy) with TLS for remote access

---

## 🗺️ Roadmap

- [x] ~~Semantic search with `pgvector` embeddings~~ ✅ Done!
- [x] ~~Automatic conversation summarization (memory compression)~~ ✅ Done!
- [x] ~~Memory expiration / archival policies~~ ✅ Done!
- [x] ~~Background memory maintenance scheduler~~ ✅ Done!
- [x] ~~Multi-tier memory (short-term, semantic, episodic, procedural)~~ ✅ Done!
- [x] ~~Importance scoring & time-based decay~~ ✅ Done!
- [x] ~~One-command auto-setup script~~ ✅ Done!
- [ ] Web dashboard for browsing stored memories
- [ ] Authentication / API keys for multi-user support
- [ ] Webhook notifications on new memories
- [ ] Memory conflict resolution across platforms
- [ ] Memory versioning & change tracking

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/semantic-search`)
3. Commit your changes (`git commit -m 'Add semantic search with pgvector'`)
4. Push to the branch (`git push origin feature/semantic-search`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Built with ❤️ for AI power users who use every tool available.</strong>
  <br>
  <em>Stop repeating yourself. Let your AIs share a brain.</em>
</p>
