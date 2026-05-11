<div align="center">

# 🧠 LLM Memory MCP Server

### Your AI assistants finally have a shared brain.

**One memory. Every platform. Zero context lost.**

Save a fact in **Cursor** → recall it in **Claude** → search it in **VS Code** → update it in **Gemini** → it's everywhere.

[![Get Started](https://img.shields.io/badge/Get_Started_in_60s-7c5cfc?style=for-the-badge&logo=rocket&logoColor=white)](#-quick-start)
[![Dashboard](https://img.shields.io/badge/Live_Dashboard-34d399?style=for-the-badge&logo=googleanalytics&logoColor=white)](#-web-dashboard)
[![GitHub Stars](https://img.shields.io/github/stars/ranjanjyoti152/LLM-MCP?style=for-the-badge&logo=github&color=yellow)](https://github.com/ranjanjyoti152/LLM-MCP/stargazers)

<br>

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL_16-pgvector-336791?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-Streamable_HTTP-34d399?style=flat-square)
![Tools](https://img.shields.io/badge/38_MCP_Tools-7c5cfc?style=flat-square)
![Prompts](https://img.shields.io/badge/8_Smart_Prompts-fb7185?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-fbbf24?style=flat-square)

</div>

---

<div align="center">

### 🔥 Why 2,000+ developers are switching to shared AI memory

</div>

| Without LLM Memory | With LLM Memory |
|:---:|:---:|
| 😤 "I already told Claude my tech stack..." | 🧠 Every AI knows your stack on first message |
| 😤 "Cursor doesn't know what I did in Copilot..." | 🧠 Full cross-platform context, always |
| 😤 "I keep repeating my preferences..." | 🧠 Preferences auto-detected and saved silently |
| 😤 "My AI forgot our entire debugging session..." | 🧠 Conversations preserved with searchable history |
| 😤 "I lost that useful code snippet..." | 🧠 Procedural memory stores every pattern |

---

## ⚡ What Makes This Different

<table>
<tr>
<td width="50%">

### 🏗️ 4-Tier Memory Architecture
Not just a key-value store. A **cognitive memory system** inspired by human memory:

- **Short-term** — Working context (auto-expires)
- **Semantic** — Facts, preferences, decisions (permanent)
- **Episodic** — Conversation history (searchable)
- **Procedural** — Code patterns & how-tos

</td>
<td width="50%">

### 🔍 Hybrid AI Search
Every `recall` query searches **all 4 tiers at once**, ranked by:

```
Score = semantic_similarity × 0.30
      + text_relevance     × 0.20
      + recency            × 0.25
      + importance          × 0.25
```

Powered by **pgvector HNSW** + **GIN full-text** indexes.

</td>
</tr>
<tr>
<td width="50%">

### 🤖 Auto-Injected Intelligence
When any AI connects, it **automatically**:

1. Loads your working context on start
2. Recalls relevant memories for your topic
3. Silently detects & saves preferences
4. Saves the conversation on end
5. Extracts knowledge & consolidates memory

**Zero manual prompting required.**

</td>
<td width="50%">

### ⚔️ Cross-Platform Conflict Resolution
When **Cursor** says "user prefers tabs" and **Claude** says "user prefers spaces":

- 🔍 **Auto-detection** via vector similarity
- 📋 **Conflict queue** with side-by-side comparison
- 🎯 **4 resolution strategies**: keep existing, use new, merge, keep both
- 📊 **Version history** for every knowledge change

</td>
</tr>
</table>

---

## 🚀 Quick Start

> **60 seconds from zero to shared AI memory.**

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Any MCP-compatible AI platform

### Option A: One-Command Setup (Recommended)

```bash
git clone https://github.com/ranjanjyoti152/LLM-MCP.git
cd LLM-MCP
./setup.sh
```

The setup script auto-detects **Cursor, VS Code, Gemini CLI, Claude Desktop, Windsurf** and generates config files.

### Option B: Manual

```bash
git clone https://github.com/ranjanjyoti152/LLM-MCP.git
cd LLM-MCP
docker compose up -d --build
```

### Verify

```bash
docker compose ps
# llm-mcp-postgres    Up (healthy)   0.0.0.0:4569->5432
# llm-mcp-server      Up             0.0.0.0:4040->4040
# llm-mcp-dashboard   Up             0.0.0.0:4041->4041
```

### Try It!

Ask your AI:

> *"Save a knowledge entry: I prefer Python for backend and TypeScript for frontend."*

Switch to **any other AI** and ask:

> *"What are my programming language preferences?"*

✨ **It remembers.** Across every platform. Forever.

---

## 📊 Web Dashboard

**Live at `http://localhost:4041`** — a full-featured memory management UI.

<table>
<tr>
<td align="center"><b>📈 Overview</b><br><sub>Bento grid metrics, health stats, platform charts</sub></td>
<td align="center"><b>🧠 Knowledge</b><br><sub>Search, filter, version history per entry</sub></td>
</tr>
<tr>
<td align="center"><b>📝 Conversations</b><br><sub>Full episodic memory with message threads</sub></td>
<td align="center"><b>⚔️ Conflicts</b><br><sub>Side-by-side comparison, 1-click resolve</sub></td>
</tr>
<tr>
<td align="center"><b>🕐 Timeline</b><br><sub>Unified activity feed across all memory types</sub></td>
<td align="center"><b>🔧 Maintenance</b><br><sub>Cleanup, consolidate, decay, compress</sub></td>
</tr>
</table>

**8 tabs** · Dark theme · Auto-refresh · Chart.js visualizations · Conflict resolution UI · Version history modals

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AI PLATFORMS                                   │
│                                                                         │
│  ┌──────────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌───────┐ ┌────────┐  │
│  │ Windsurf │ │ Cursor │ │ VS Code │ │ Claude │ │Gemini │ │ Codex  │  │
│  └─────┬────┘ └───┬────┘ └────┬────┘ └───┬────┘ └──┬────┘ └───┬────┘  │
│        └───────────┴──────────┴──────────┴─────────┴──────────┘        │
│                                │                                        │
└────────────────────────────────┼────────────────────────────────────────┘
                                 │ MCP (Streamable HTTP)
                                 ▼
        ┌────────────────────────────────────────────────┐
        │         🧠 LLM Memory MCP Server :4040         │
        │                                                │
        │  38 Tools · 8 Prompts · 3 Resources            │
        │  Auto-injected instructions for every LLM      │
        │  Background scheduler (cleanup/decay/compress)  │
        │  Version tracking · Conflict resolution         │
        │                                                │
        │  📊 Dashboard UI :4041                          │
        │  19 REST endpoints · 8-tab interface            │
        └────────────────────┬───────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────┐
        │       PostgreSQL 16 + pgvector :4569            │
        │                                                │
        │  ┌─────────┐ ┌──────────┐ ┌───────────┐       │
        │  │Episodic  │ │ Semantic │ │Short-term │       │
        │  │convos +  │ │knowledge │ │TTL-expire │       │
        │  │messages  │ │+ vectors │ │+ consolid │       │
        │  └─────────┘ └──────────┘ └───────────┘       │
        │  ┌─────────┐ ┌──────────┐ ┌───────────┐       │
        │  │Procedural│ │Versions  │ │Conflicts  │       │
        │  │code snips│ │changelog │ │cross-plat │       │
        │  └─────────┘ └──────────┘ └───────────┘       │
        │                                                │
        │  HNSW vector index + GIN full-text index       │
        │  Hybrid search: semantic + keyword ranking      │
        └────────────────────────────────────────────────┘
```

---

## 🎯 Supported Platforms

| Platform | Transport | Status |
|:---------|:----------|:------:|
| **Windsurf** | Streamable HTTP | ✅ Ready |
| **Cursor** | Streamable HTTP | ✅ Ready |
| **VS Code** + GitHub Copilot | Streamable HTTP | ✅ Ready |
| **Claude Desktop** | Streamable HTTP / stdio | ✅ Ready |
| **Gemini CLI** | Streamable HTTP | ✅ Ready |
| **Antigravity** (Google) | Streamable HTTP | ✅ Ready |
| **ChatGPT** (MCP-compatible) | Streamable HTTP | ✅ Ready |
| **Codex** (OpenAI) | Streamable HTTP | ✅ Ready |
| Any MCP-compatible client | Streamable HTTP | ✅ Ready |

---

## 🔧 Platform Configuration

### <img src="https://img.shields.io/badge/-Windsurf-7c5cfc?style=flat-square" alt="Windsurf"> Windsurf

**Option A** — Via UI: **Settings → MCP → Add Server** → paste the URL.

**Option B** — Config file (`.windsurf/mcp_config.json`):

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

**Option A — Local (Best Performance):** Connect directly via Docker — no extra tools needed.

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

---

### <img src="https://img.shields.io/badge/-ChatGPT-74AA9C?style=flat-square&logo=openai&logoColor=white" alt="ChatGPT"> ChatGPT / Codex / Other MCP Clients

For any platform that supports MCP via HTTP, use:

```
Endpoint:   http://localhost:4040/mcp
Transport:  Streamable HTTP (JSON-RPC over POST with optional SSE streaming)
```

---

## 🛠️ 38 MCP Tools

<details open>
<summary><b>💬 Conversations (Episodic Memory)</b></summary>

| Tool | What it does |
|:-----|:------------|
| `save_conversation` | Save full conversation with messages, metadata, importance, outcome |
| `search_memory` | Full-text + semantic search across all conversations |
| `get_recent_conversations` | Latest conversations by platform |
| `get_conversation_by_id` | Retrieve specific conversation with all messages |
| `add_message_to_conversation` | Append messages to existing conversation |
| `tag_conversation` | Add/remove tags |
| `delete_memory` | Delete conversation or knowledge by ID |

</details>

<details open>
<summary><b>🧠 Knowledge (Semantic Memory)</b></summary>

| Tool | What it does |
|:-----|:------------|
| `save_knowledge` | Store fact/preference/instruction/decision |
| `save_knowledge_smart` | **Conflict-aware save** — detects duplicates & cross-platform conflicts |
| `search_knowledge` | Search by query, category, tags |
| `list_all_knowledge` | Paginated listing with category filter |
| `get_knowledge_by_category` | All entries in a category |
| `get_related_knowledge` | Similar entries by vector proximity |
| `update_knowledge` | Update with **automatic version snapshot** |
| `auto_extract_preferences` | Batch-extract preferences from conversation text |
| `get_context_summary` | Combined knowledge + conversation context |

</details>

<details>
<summary><b>⏱️ Working Memory (Short-term)</b></summary>

| Tool | What it does |
|:-----|:------------|
| `save_short_term_memory` | Save transient context with TTL auto-expiry |
| `get_working_context` | Load all active session context |
| `consolidate_memories` | Promote important STM → long-term knowledge |

</details>

<details>
<summary><b>💻 Code & Projects (Procedural Memory)</b></summary>

| Tool | What it does |
|:-----|:------------|
| `save_code_snippet` | Save reusable code with language, tags, description |
| `search_code_snippets` | Search by keyword, language, tags |
| `save_project_context` | Save project-level tech stack & architecture |
| `get_project_context` | Retrieve project context by name |

</details>

<details>
<summary><b>🔍 Search & Retrieval</b></summary>

| Tool | What it does |
|:-----|:------------|
| `recall` | **PRIMARY** — searches all 4 memory tiers at once, ranked by composite score |
| `search_by_tags` | Cross-type tag search |

</details>

<details>
<summary><b>⚔️ Versioning & Conflicts</b></summary>

| Tool | What it does |
|:-----|:------------|
| `knowledge_history` | Full version timeline for any knowledge entry |
| `rollback_knowledge` | Restore to any previous version |
| `list_conflicts` | View pending/resolved cross-platform conflicts |
| `resolve_conflict` | Resolve with strategy: keep_existing, use_new, merge, keep_both |

</details>

<details>
<summary><b>🔧 Maintenance & Utility</b></summary>

| Tool | What it does |
|:-----|:------------|
| `count_memories` | Count all memory types |
| `summarize_platform_activity` | Per-platform stats |
| `cleanup_expired_memories` | Remove expired STM & knowledge |
| `decay_memories` | Reduce importance of old unaccessed memories |
| `export_memories` | Full JSON backup |
| `import_memories` | Restore from backup (with dedup) |
| `clear_platform_data` | Delete all data for a platform ⚠️ |

</details>

### 📡 3 MCP Resources

| URI | Description |
|:----|:-----------|
| `memory://stats` | Database statistics & counts |
| `memory://platforms` | All platforms with stored data |
| `memory://health` | System health across all memory tiers |

### 🎯 8 Smart Prompts

Auto-discoverable prompt templates for key workflows:

| Prompt | What it does |
|:-------|:-----------|
| `start_conversation` | Initialize with full memory context |
| `end_conversation` | Save everything + extract knowledge |
| `save_user_preference` | Structured preference storage |
| `recall_everything` | Deep search across all memory |
| `resolve_all_conflicts` | Guided conflict resolution |
| `memory_maintenance` | Run all maintenance tasks |
| `onboard_new_user` | First-time setup & preference capture |
| `debug_session` | Context-aware debugging workflow |

---

## 🧬 Auto-Injected Behaviors

When any AI connects to this MCP server, it **automatically receives behavioral instructions** — no user action needed:

```
┌─────────────────────────────────────────────────────────────┐
│  CONVERSATION START (automatic)                              │
│  1. get_working_context() — load session context             │
│  2. recall("<topic>") — search all memory for relevance      │
│  3. Personalize response using recalled memories             │
│  4. save_short_term_memory() — track current task            │
├─────────────────────────────────────────────────────────────┤
│  DURING CONVERSATION (automatic, silent)                     │
│  • Detect preferences → save_knowledge_smart()               │
│  • Detect facts → save_knowledge_smart()                     │
│  • Detect decisions → save_knowledge_smart()                 │
│  • Detect code patterns → save_code_snippet()                │
│  • All saves are conflict-aware (dedup + cross-platform)     │
├─────────────────────────────────────────────────────────────┤
│  CONVERSATION END (automatic)                                │
│  1. save_conversation() — with importance + outcome          │
│  2. auto_extract_preferences() — batch knowledge extraction  │
│  3. consolidate_memories() — promote STM → long-term         │
└─────────────────────────────────────────────────────────────┘
```

**Result:** Every AI assistant becomes memory-aware from the moment it connects. No setup. No prompting. It just works.

---

## 📁 Project Structure

```
LLM-MCP/
├── server.py               # MCP server — 38 tools, 8 prompts, 3 resources
├── db.py                   # Async DB layer (asyncpg + pgvector + FTS)
├── embeddings.py           # Embedding engine (local/ollama/openai)
├── dashboard.py            # REST API for web dashboard (Starlette)
├── static/
│   └── index.html          # Dashboard UI (Tailwind + Chart.js)
├── prompts/
│   ├── system_prompt.md    # Standalone system prompt for any LLM
│   └── quick_prompts.md    # 12 copy-paste prompt templates
├── docker-compose.yml      # PostgreSQL + MCP Server + Dashboard
├── Dockerfile              # Python 3.12 slim container
├── setup.sh                # One-command auto-setup script
├── .env                    # Environment configuration
├── requirements.txt        # Python dependencies
├── test_client.py          # End-to-end test suite
├── test_versioning.py      # Versioning & conflict resolution tests
└── test_prompts.py         # MCP prompt discovery tests
```

---

## ⚙️ Configuration

All settings via `.env`:

| Variable | Default | Description |
|:---------|:--------|:------------|
| `POSTGRES_PORT` | `4569` | PostgreSQL host port |
| `MCP_PORT` | `4040` | MCP server port |
| `DASHBOARD_PORT` | `4041` | Dashboard UI port |
| `POSTGRES_USER` | `mcp_user` | Database user |
| `POSTGRES_PASSWORD` | `mcp_secure_pass_2026` | Database password |
| `POSTGRES_DB` | `mcp_memory` | Database name |
| `EMBEDDING_PROVIDER` | `local` | `local` / `ollama` / `openai` |
| `MAINTENANCE_INTERVAL_MINUTES` | `30` | Background scheduler interval |

### LAN Access

Replace `localhost` with your machine's IP for remote AI platforms:

```
http://192.168.x.x:4040/mcp       # MCP Server
http://192.168.x.x:4041            # Dashboard
```

---

## 🗄️ Database Schema

**8 tables** with hybrid search indexes:

```
┌─────────────────┐     ┌──────────────────┐
│  conversations   │────▶│    messages       │  Episodic memory
│  (importance,    │     │  (role, content,  │
│   outcome,       │     │   embedding)      │
│   embedding)     │     └──────────────────┘
└─────────────────┘

┌─────────────────┐     ┌──────────────────┐
│   knowledge      │────▶│knowledge_versions│  Semantic memory
│  (category,      │     │  (version, diff,  │  + version history
│   version,       │     │   changed_by)     │
│   embedding)     │     └──────────────────┘
└─────────────────┘

┌─────────────────┐     ┌──────────────────┐
│short_term_memory │     │memory_conflicts  │  Working memory
│  (TTL, context,  │     │  (existing vs    │  + conflict tracking
│   consolidated)  │     │   conflicting)   │
└─────────────────┘     └──────────────────┘

┌─────────────────┐     ┌──────────────────┐
│  code_snippets   │     │    projects       │  Procedural memory
│  (language,      │     │  (tech_stack,     │  + project context
│   embedding)     │     │   architecture)   │
└─────────────────┘     └──────────────────┘
```

**Indexes:** HNSW (vector similarity) + GIN (full-text search) + B-tree (importance, expiry) for sub-millisecond hybrid queries.

---

## 🧪 Testing

```bash
# Full test suite
python test_client.py

# Versioning & conflict resolution
python test_versioning.py

# MCP prompt discovery
python test_prompts.py
```

<details>
<summary>Manual verification commands</summary>

```bash
# Check services
docker compose ps

# PostgreSQL direct query
docker exec llm-mcp-postgres psql -U mcp_user -d mcp_memory \
  -c "SELECT COUNT(*) as knowledge FROM knowledge;"

# MCP server logs
docker logs -f llm-mcp-server

# Dashboard logs
docker logs -f llm-mcp-dashboard

# Restart everything
docker compose restart
```

</details>

---

## 📋 Docker Commands

| Command | Description |
|:--------|:------------|
| `docker compose up -d --build` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose logs -f mcp-server` | Stream server logs |
| `docker compose logs -f dashboard` | Stream dashboard logs |
| `docker compose down -v` | Stop & **delete all data** ⚠️ |

---

## 🔒 Security

- Bind to `127.0.0.1` for local-only: `MCP_HOST=127.0.0.1`
- Change `POSTGRES_PASSWORD` in production
- Add reverse proxy (nginx/Caddy) with TLS for remote access
- No auth by default — designed for local/trusted network use

---

## 🗺️ Roadmap

- [x] Semantic search with pgvector embeddings
- [x] Automatic conversation summarization (compression)
- [x] Memory expiration & archival policies
- [x] Background maintenance scheduler
- [x] Multi-tier memory (short-term, semantic, episodic, procedural)
- [x] Importance scoring & time-based decay
- [x] One-command auto-setup script
- [x] **Memory versioning & change tracking**
- [x] **Cross-platform conflict resolution**
- [x] **Web dashboard with real-time visualization**
- [x] **Auto-injected behavioral instructions**
- [x] **MCP prompt workflows**
- [ ] Authentication / API keys for multi-user
- [ ] Webhook notifications on new memories
- [ ] Memory sharing between users
- [ ] Cloud-hosted option (no Docker needed)
- [ ] Mobile companion app

---

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

All contributions welcome — features, bug fixes, docs, translations.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

### ⭐ If this project saves you from repeating yourself to your AIs, give it a star!

**[Star this repo](https://github.com/ranjanjyoti152/LLM-MCP)** · **[Report Bug](https://github.com/ranjanjyoti152/LLM-MCP/issues)** · **[Request Feature](https://github.com/ranjanjyoti152/LLM-MCP/issues)**

<br>

Built with ❤️ by [ranjanjyoti152](https://github.com/ranjanjyoti152)

*Stop repeating yourself. Let your AIs share a brain.*

<br>

<sub>If you found this useful, consider sharing it with other developers who use multiple AI tools.</sub>

</div>
