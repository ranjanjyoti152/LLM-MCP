#!/usr/bin/env bash
#
# 🧠 LLM Memory MCP Server — One-Command Setup
#
# Usage:  ./setup.sh
#
# This script will:
#   1. Check prerequisites (Docker, Docker Compose)
#   2. Start the PostgreSQL + MCP Server stack
#   3. Wait for health checks to pass
#   4. Auto-detect installed AI platforms
#   5. Generate config files for each detected platform
#   6. Run a quick smoke test
#
set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

print_header()  { echo -e "\n${BOLD}${BLUE}═══════════════════════════════════════════════════${NC}"; echo -e "${BOLD}${BLUE}  $1${NC}"; echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════${NC}"; }
print_step()    { echo -e "  ${CYAN}▸${NC} $1"; }
print_ok()      { echo -e "  ${GREEN}✅${NC} $1"; }
print_warn()    { echo -e "  ${YELLOW}⚠️${NC}  $1"; }
print_fail()    { echo -e "  ${RED}❌${NC} $1"; }
print_info()    { echo -e "  ${BLUE}ℹ${NC}  $1"; }

MCP_URL="http://localhost:4040/mcp"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── 1. Prerequisites ───────────────────────────────────────────────────────
print_header "🧠 LLM Memory MCP Server Setup"

print_step "Checking prerequisites..."

if ! command -v docker &>/dev/null; then
    print_fail "Docker is not installed. Get it at: https://docs.docker.com/get-docker/"
    exit 1
fi
print_ok "Docker found"

if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
    print_fail "Docker Compose is not installed."
    exit 1
fi
print_ok "Docker Compose found"

# ─── 2. Create .env if not present ──────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    print_step "Creating default .env file..."
    cat > "$SCRIPT_DIR/.env" <<'EOF'
# LLM Memory MCP Server Configuration
POSTGRES_USER=mcp_user
POSTGRES_PASSWORD=mcp_secure_pass_2026
POSTGRES_DB=mcp_memory
POSTGRES_PORT=4569
MCP_PORT=4040
MCP_HOST=0.0.0.0

# Embedding provider: 'local' (zero-config), 'ollama' (local AI), 'openai' (cloud)
EMBEDDING_PROVIDER=local

# Uncomment for Ollama embeddings:
# EMBEDDING_PROVIDER=ollama
# OLLAMA_URL=http://host.docker.internal:11434
# OLLAMA_MODEL=nomic-embed-text

# Uncomment for OpenAI embeddings:
# EMBEDDING_PROVIDER=openai
# OPENAI_API_KEY=sk-...

# Background maintenance interval (minutes)
MAINTENANCE_INTERVAL_MINUTES=30
EOF
    print_ok ".env created with defaults"
else
    print_ok ".env already exists"
fi

# ─── 3. Start the stack ─────────────────────────────────────────────────────
print_header "🐳 Starting Docker Stack"

cd "$SCRIPT_DIR"
print_step "Building and starting containers..."
docker compose up -d --build 2>&1 | sed 's/^/    /'

# ─── 4. Wait for health ─────────────────────────────────────────────────────
print_step "Waiting for services to be healthy..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    PG_STATUS=$(docker inspect --format='{{.State.Health.Status}}' llm-mcp-postgres 2>/dev/null || echo "missing")
    MCP_STATUS=$(docker inspect --format='{{.State.Status}}' llm-mcp-server 2>/dev/null || echo "missing")

    if [ "$PG_STATUS" = "healthy" ] && [ "$MCP_STATUS" = "running" ]; then
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -ne "\r    Waiting... ${WAITED}s (postgres: ${PG_STATUS}, mcp: ${MCP_STATUS})   "
done
echo ""

if [ "$PG_STATUS" = "healthy" ] && [ "$MCP_STATUS" = "running" ]; then
    print_ok "PostgreSQL: healthy"
    print_ok "MCP Server: running"
else
    print_fail "Services did not start properly. Check: docker compose logs"
    exit 1
fi

# Give the MCP server a moment to fully initialize
sleep 3

# Quick HTTP check
if curl -sf "$MCP_URL" -o /dev/null 2>/dev/null || curl -sf "http://localhost:4040/" -o /dev/null 2>/dev/null; then
    print_ok "MCP endpoint responding at $MCP_URL"
else
    print_warn "MCP endpoint not responding yet — it may still be starting. Check: docker compose logs -f mcp-server"
fi

# ─── 5. Detect platforms & generate configs ──────────────────────────────────
print_header "🔍 Detecting AI Platforms"

CONFIGS_GENERATED=0

# --- Cursor ---
detect_cursor() {
    local cursor_dir=""
    if [ -d "$HOME/.cursor" ]; then
        cursor_dir="$HOME/.cursor"
    fi
    if [ -n "$cursor_dir" ]; then
        print_ok "Cursor detected at $cursor_dir"
        local config_file="$cursor_dir/mcp.json"
        if [ -f "$config_file" ]; then
            print_info "Config already exists: $config_file"
        else
            cat > "$config_file" <<EOF
{
  "mcpServers": {
    "llm-memory": {
      "url": "$MCP_URL"
    }
  }
}
EOF
            print_ok "Created $config_file"
            CONFIGS_GENERATED=$((CONFIGS_GENERATED + 1))
        fi
    fi
}

# --- VS Code ---
detect_vscode() {
    local vscode_dir=""
    if [ -d "$HOME/.vscode" ] || command -v code &>/dev/null; then
        vscode_dir="$HOME/.vscode"
        mkdir -p "$vscode_dir"
    fi
    if [ -n "$vscode_dir" ]; then
        print_ok "VS Code detected"
        local config_file="$vscode_dir/mcp.json"
        if [ -f "$config_file" ]; then
            print_info "Config already exists: $config_file"
        else
            cat > "$config_file" <<EOF
{
  "servers": {
    "llm-memory": {
      "type": "http",
      "url": "$MCP_URL"
    }
  }
}
EOF
            print_ok "Created $config_file"
            CONFIGS_GENERATED=$((CONFIGS_GENERATED + 1))
        fi
    fi
}

# --- Gemini CLI ---
detect_gemini() {
    if [ -d "$HOME/.gemini" ] || command -v gemini &>/dev/null; then
        print_ok "Gemini CLI detected"
        local config_file="$HOME/.gemini/settings.json"
        mkdir -p "$HOME/.gemini"
        if [ -f "$config_file" ]; then
            print_info "Config already exists: $config_file"
        else
            cat > "$config_file" <<EOF
{
  "mcpServers": {
    "llm-memory": {
      "httpUrl": "$MCP_URL"
    }
  }
}
EOF
            print_ok "Created $config_file"
            CONFIGS_GENERATED=$((CONFIGS_GENERATED + 1))
        fi
    fi
}

# --- Claude Desktop ---
detect_claude() {
    local claude_config=""
    if [ -f "$HOME/.config/claude/claude_desktop_config.json" ]; then
        claude_config="$HOME/.config/claude/claude_desktop_config.json"
    elif [ -f "$HOME/Library/Application Support/Claude/claude_desktop_config.json" ]; then
        claude_config="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    fi
    if [ -n "$claude_config" ]; then
        print_ok "Claude Desktop detected at $(dirname "$claude_config")"
        print_info "Config already exists: $claude_config"
        print_info "Add this to your mcpServers if not present:"
        echo -e "    ${CYAN}\"llm-memory\": { \"command\": \"docker\", \"args\": [\"exec\", \"-i\", \"llm-mcp-server\", \"python\", \"server.py\", \"stdio\"] }${NC}"
    else
        # Check if Docker Desktop is installed (macOS/Linux)
        if [ -d "$HOME/.config/claude" ] || [ -d "$HOME/Library/Application Support/Claude" ]; then
            print_ok "Claude Desktop directory found"
        fi
    fi
}

# --- Windsurf ---
detect_windsurf() {
    if [ -d "$HOME/.windsurf" ] || [ -d "$HOME/.codeium/windsurf" ]; then
        print_ok "Windsurf detected"
        local config_dir="$HOME/.windsurf"
        mkdir -p "$config_dir"
        local config_file="$config_dir/mcp_config.json"
        if [ -f "$config_file" ]; then
            print_info "Config already exists: $config_file"
        else
            cat > "$config_file" <<EOF
{
  "mcpServers": {
    "llm-memory": {
      "serverUrl": "$MCP_URL"
    }
  }
}
EOF
            print_ok "Created $config_file"
            CONFIGS_GENERATED=$((CONFIGS_GENERATED + 1))
        fi
    fi
}

detect_cursor
detect_vscode
detect_gemini
detect_claude
detect_windsurf

if [ $CONFIGS_GENERATED -eq 0 ]; then
    print_info "No new configs generated (existing configs preserved)"
fi

# ─── 6. Summary ──────────────────────────────────────────────────────────────
print_header "🎉 Setup Complete!"

echo -e ""
echo -e "  ${BOLD}MCP Server URL:${NC}  ${GREEN}$MCP_URL${NC}"
echo -e "  ${BOLD}PostgreSQL:${NC}      ${GREEN}localhost:4569${NC}"
echo -e ""
echo -e "  ${BOLD}Memory Architecture:${NC}"
echo -e "    ${CYAN}┌─ Short-Term Memory${NC}  (auto-expires, working context)"
echo -e "    ${CYAN}├─ Semantic Memory${NC}   (long-term facts & knowledge)"
echo -e "    ${CYAN}├─ Episodic Memory${NC}   (conversation history)"
echo -e "    ${CYAN}├─ Procedural Memory${NC} (code snippets & patterns)"
echo -e "    ${CYAN}└─ Vector Search${NC}     (semantic similarity via pgvector)"
echo -e ""
echo -e "  ${BOLD}Features:${NC}"
echo -e "    • Hybrid search (vector + full-text)"
echo -e "    • Auto memory consolidation & decay"
echo -e "    • Background maintenance scheduler"
echo -e "    • Memory reflection & compression"
echo -e ""
echo -e "  ${BOLD}Quick Test:${NC}"
echo -e "    Ask any connected AI: ${YELLOW}\"Save a knowledge entry: I prefer Python for backend\"${NC}"
echo -e "    Then on another platform: ${YELLOW}\"What are my programming preferences?\"${NC}"
echo -e ""
echo -e "  ${BOLD}Commands:${NC}"
echo -e "    docker compose logs -f mcp-server  ${CYAN}# View logs${NC}"
echo -e "    docker compose restart              ${CYAN}# Restart${NC}"
echo -e "    docker compose down                 ${CYAN}# Stop${NC}"
echo -e "    python test_client.py               ${CYAN}# Run tests${NC}"
echo -e ""
