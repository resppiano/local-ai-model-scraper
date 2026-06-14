#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# Project Fable — Installation Script
# =====================================
# Run this on a fresh machine (Agent One, Agent Two, etc.) to replicate
# the complete Fable Studio setup.
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/resppiano/local-ai-model-scraper/main/install-fable.sh | bash
#   # or download and run:
#   bash install-fable.sh
#
# Tested on: Ubuntu 24.04 LTS
# Requires: sudo access, internet connection
# ═════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
INSTALL_DIR="${FABLE_INSTALL_DIR:-$HOME/agent_two}"
ASSETS_DIR="${FABLE_ASSETS_DIR:-$HOME/FableAssets}"
DASHBOARD_DIR="${FABLE_DASHBOARD_DIR:-$HOME/Desktop/app}"
COMFYUI_DIR="${FABLE_COMFYUI_DIR:-$HOME/ComfyUI}"
DB_PATH="${FABLE_DB_PATH:-$INSTALL_DIR/fable_api/fable.db}"
API_PORT="${FABLE_API_PORT:-8001}"
DASHBOARD_PORT="${FABLE_DASHBOARD_PORT:-3001}"

REPO_URL="https://github.com/resppiano/local-ai-model-scraper.git"
BRANCH="main"

# Higgsfield credentials (prompt if not set)
HF_API_KEY="${HF_API_KEY:-}"
HF_SECRET="${HF_SECRET:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Helpers ──────────────────────────────────────────────────────────────
log() { echo -e "${BLUE}[Fable]${NC} $1"; }
ok()  { echo -e "${GREEN}[OK]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err() { echo -e "${RED}[ERR]${NC} $1"; }

cmd_exists() { command -v "$1" >/dev/null 2>&1; }

# ── System Check ───────────────────────────────────────────────────────────
log "Starting Project Fable installation..."
log "Install dir: $INSTALL_DIR"
log "Dashboard dir: $DASHBOARD_DIR"
log "Assets dir: $ASSETS_DIR"

if ! cmd_exists sudo; then
    err "sudo is required. Run as a user with sudo privileges."
    exit 1
fi

# ── 1. System Dependencies ────────────────────────────────────────────────
log "Installing system dependencies..."

sudo apt-get update -qq
sudo apt-get install -y -qq \
    git curl wget jq sqlite3 \
    build-essential python3 python3-venv python3-pip \
    nodejs npm \
    docker.io docker-compose-v2 \
    nginx \
    2>/dev/null || {
    warn "Some packages may have failed, continuing..."
}

# Ensure docker group
if ! groups | grep -q docker; then
    sudo usermod -aG docker "$USER"
    warn "Added user to docker group. You may need to re-login for docker to work without sudo."
fi

ok "System dependencies installed"

# ── 2. Node.js 20+ (if system node is old) ──────────────────────────────
NODE_VERSION="$(node --version 2>/dev/null | sed 's/v//' || echo "0.0.0")"
REQUIRED_NODE="20.0.0"

if [ "$(printf '%s\n' "$REQUIRED_NODE" "$NODE_VERSION" | sort -V | head -n1)" != "$REQUIRED_NODE" ]; then
    log "Upgrading Node.js to 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
    ok "Node.js upgraded to $(node --version)"
else
    ok "Node.js $(node --version) is sufficient"
fi

# ── 3. Clone / Update Repositories ───────────────────────────────────────
log "Setting up Fable repositories..."

mkdir -p "$HOME/Desktop"

# Dashboard repo
if [ -d "$DASHBOARD_DIR/.git" ]; then
    log "Dashboard repo exists, pulling updates..."
    cd "$DASHBOARD_DIR"
    git fetch origin
    git reset --hard "origin/$BRANCH"
else
    log "Cloning dashboard repository..."
    git clone --depth=1 --branch "$BRANCH" "$REPO_URL" "$DASHBOARD_DIR"
fi
ok "Dashboard repo ready at $DASHBOARD_DIR"

# Agent Two / Fable API
mkdir -p "$INSTALL_DIR"
if [ -d "$INSTALL_DIR/.git" ]; then
    log "Agent directory exists, pulling..."
    cd "$INSTALL_DIR"
    git pull origin "$BRANCH" 2>/dev/null || true
else
    log "Cloning Fable agent code..."
    git clone --depth=1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi
ok "Agent code ready at $INSTALL_DIR"

# ── 4. Python Virtual Environment ────────────────────────────────────────
log "Setting up Python virtual environment..."

cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "Created venv"
else
    ok "venv already exists"
fi

source venv/bin/activate

# Upgrade pip
pip install --upgrade pip -q

# Install FastAPI + dependencies
pip install -q \
    fastapi uvicorn \
    sqlalchemy aiosqlite \
    python-multipart websockets \
    httpx \
    2>/dev/null || pip install --break-system-packages -q \
        fastapi uvicorn sqlalchemy aiosqlite python-multipart websockets httpx

ok "Python dependencies installed"

# ── 5. Higgsfield MCP ────────────────────────────────────────────────────
log "Installing Higgsfield MCP..."

if ! cmd_exists higgsfield-mcp; then
    npm install -g higgsfield-mcp 2>/dev/null || sudo npm install -g higgsfield-mcp
fi

ok "Higgsfield MCP installed"

# ── 6. Environment Configuration ─────────────────────────────────────────
log "Configuring environment..."

mkdir -p "$HOME/.config/higgsfield"
mkdir -p "$ASSETS_DIR"

# Prompt for Higgsfield credentials if not set
if [ -z "$HF_API_KEY" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Higgsfield AI API Credentials"
    echo "  Get your keys at: https://cloud.higgsfield.ai/api-keys"
    echo "═══════════════════════════════════════════════════════════"
    read -rp "Enter HF_API_KEY (or press Enter to skip): " HF_API_KEY
    read -rp "Enter HF_SECRET (or press Enter to skip): " HF_SECRET
fi

# Write env file
cat > "$HOME/.config/higgsfield/.env" << EOF
HF_API_KEY=${HF_API_KEY:-your-api-key-here}
HF_SECRET=${HF_SECRET:-your-secret-here}
EOF
chmod 600 "$HOME/.config/higgsfield/.env"

# Append to bashrc if not present
if ! grep -q "HF_API_KEY" "$HOME/.bashrc" 2>/dev/null; then
    cat >> "$HOME/.bashrc" << EOF

# Project Fable — Higgsfield AI
export HF_API_KEY="${HF_API_KEY:-your-api-key-here}"
export HF_SECRET="${HF_SECRET:-your-secret-here}"
export FABLE_API_URL="http://localhost:${API_PORT}"
export FABLE_ASSETS_DIR="${ASSETS_DIR}"
export FABLE_DB_PATH="${DB_PATH}"
EOF
fi

ok "Environment configured"

# ── 7. Database Initialization ───────────────────────────────────────────
log "Initializing SQLite database..."

export FABLE_DB_PATH="$DB_PATH"
cd "$INSTALL_DIR"
python3 -c "
import sys
sys.path.insert(0, 'fable_api')
from database import init_db
init_db()
print('Database initialized at:', '$DB_PATH')
" 2>/dev/null || python3 -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
sys.path.insert(0, '$INSTALL_DIR/fable_api')
from database import init_db
init_db()
print('Database initialized')
"

ok "Database ready"

# ── 8. Startup Scripts ────────────────────────────────────────────────────
log "Creating startup scripts..."

# API startup script
cat > "$INSTALL_DIR/start_fable_api.sh" << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source venv/bin/activate
export FABLE_DB_PATH="${FABLE_DB_PATH:-$(pwd)/fable_api/fable.db}"
export FABLE_ASSETS_DIR="${FABLE_ASSETS_DIR:-$HOME/FableAssets}"
export HF_API_KEY="${HF_API_KEY:-}"
export HF_SECRET="${HF_SECRET:-}"
exec python -m uvicorn fable_api.main:app --host 0.0.0.0 --port 8001 --workers 1
EOF
chmod +x "$INSTALL_DIR/start_fable_api.sh"

# Agent startup script
cat > "$INSTALL_DIR/start_fable_agent.sh" << 'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source venv/bin/activate
export FABLE_API_URL="${FABLE_API_URL:-http://localhost:8001}"
export FABLE_ASSETS_DIR="${FABLE_ASSETS_DIR:-$HOME/FableAssets}"
export HF_API_KEY="${HF_API_KEY:-}"
export HF_SECRET="${HF_SECRET:-}"
exec python fable_mcp_server.py
EOF
chmod +x "$INSTALL_DIR/start_fable_agent.sh"

# Combined startup script
cat > "$INSTALL_DIR/start_fable.sh" << 'EOF'
#!/usr/bin/env bash
# Start all Fable services
cd "$(dirname "$0")"

echo "🎬 Starting Project Fable..."

# Start API
echo "  → Starting API (port 8001)..."
nohup ./start_fable_api.sh > /tmp/fable_api.log 2>&1 &
sleep 3

# Check API
if curl -s http://localhost:8001/health > /dev/null; then
    echo "  ✅ API running"
else
    echo "  ⚠️  API may not be ready yet (check /tmp/fable_api.log)"
fi

# Start Agent
echo "  → Starting Agent (MCP)..."
nohup ./start_fable_agent.sh > /tmp/fable_agent.log 2>&1 &
sleep 1
echo "  ✅ Agent started"

# Dashboard (if Docker is available)
if command -v docker > /dev/null; then
    echo "  → Starting Dashboard (port 3001)..."
    cd "${FABLE_DASHBOARD_DIR:-$HOME/Desktop/app}" 2>/dev/null || true
    if [ -f "docker-compose.yml" ]; then
        docker compose up -d --build 2>/dev/null || docker-compose up -d --build 2>/dev/null
        echo "  ✅ Dashboard running"
    elif [ -f "Dockerfile" ]; then
        docker build -t fable-dashboard:latest . 2>/dev/null
        docker stop fable-dashboard 2>/dev/null; docker rm fable-dashboard 2>/dev/null
        docker run -d --name fable-dashboard -p 3001:80 fable-dashboard:latest 2>/dev/null
        echo "  ✅ Dashboard running"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Project Fable is starting up!"
echo "═══════════════════════════════════════════════════"
echo "  Dashboard:  http://localhost:3001"
echo "  API:        http://localhost:8001"
echo "  API Health: http://localhost:8001/health"
echo "═══════════════════════════════════════════════════"
EOF
chmod +x "$INSTALL_DIR/start_fable.sh"

ok "Startup scripts created"

# ── 9. Systemd Services (optional) ───────────────────────────────────────
log "Creating systemd services..."

sudo mkdir -p /etc/systemd/system

# Fable API service
sudo tee /etc/systemd/system/fable-api.service > /dev/null << EOF
[Unit]
Description=Project Fable API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=FABLE_DB_PATH=$DB_PATH
Environment=FABLE_ASSETS_DIR=$ASSETS_DIR
Environment=HF_API_KEY=${HF_API_KEY:-}
Environment=HF_SECRET=${HF_SECRET:-}
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$INSTALL_DIR/venv/bin/python -m uvicorn fable_api.main:app --host 0.0.0.0 --port $API_PORT --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Fable Agent service
sudo tee /etc/systemd/system/fable-agent.service > /dev/null << EOF
[Unit]
Description=Project Fable Agent (MCP)
After=network.target fable-api.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=FABLE_API_URL=http://localhost:$API_PORT
Environment=FABLE_ASSETS_DIR=$ASSETS_DIR
Environment=HF_API_KEY=${HF_API_KEY:-}
Environment=HF_SECRET=${HF_SECRET:-}
Environment=PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/fable_mcp_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload 2>/dev/null || true

ok "Systemd services created (enable with: sudo systemctl enable --now fable-api fable-agent)"

# ── 10. Claude MCP Config ────────────────────────────────────────────────
log "Configuring Claude MCP..."

CLAUDE_CONFIG="$HOME/.claude.json"
if [ -f "$CLAUDE_CONFIG" ]; then
    # Backup
    cp "$CLAUDE_CONFIG" "$CLAUDE_CONFIG.backup.$(date +%s)"
    
    # Use jq to inject if available, otherwise warn
    if cmd_exists jq; then
        jq --arg cmd "$INSTALL_DIR/start_fable_agent.sh" '
            .projects."/home/$ENV.USER".mcpServers.fable = {
                "type": "stdio",
                "command": "bash",
                "args": [$cmd],
                "env": {}
            }
        ' "$CLAUDE_CONFIG" > "$CLAUDE_CONFIG.tmp" 2>/dev/null && mv "$CLAUDE_CONFIG.tmp" "$CLAUDE_CONFIG"
        ok "Claude MCP config updated"
    else
        warn "jq not installed. Add this to $CLAUDE_CONFIG manually:"
        echo '    "fable": { "type": "stdio", "command": "bash", "args": ["'$INSTALL_DIR/start_fable_agent.sh'"] }'
    fi
else
    warn "No ~/.claude.json found. When you install Claude Code, add:"
    echo "    claude mcp add fable -- bash $INSTALL_DIR/start_fable_agent.sh"
fi

# ── 11. MCP Config for Gemini/Antigravity ────────────────────────────────
mkdir -p "$HOME/.gemini/antigravity"
cat > "$HOME/.gemini/antigravity/mcp_config.json" << EOF
{
  "mcpServers": {
    "higgsfield": {
      "command": "npx",
      "args": ["-y", "higgsfield-mcp"],
      "env": {
        "HF_API_KEY": "${HF_API_KEY:-}",
        "HF_SECRET": "${HF_SECRET:-}"
      }
    },
    "fable": {
      "command": "bash",
      "args": ["$INSTALL_DIR/start_fable_agent.sh"],
      "env": {
        "FABLE_API_URL": "http://localhost:$API_PORT",
        "HF_API_KEY": "${HF_API_KEY:-}",
        "HF_SECRET": "${HF_SECRET:-}"
      }
    }
  }
}
EOF
chmod 600 "$HOME/.gemini/antigravity/mcp_config.json"
ok "MCP config for Gemini/Antigravity created"

# ── 12. Build Web Dashboard ───────────────────────────────────────────────
log "Building web dashboard..."

cd "$DASHBOARD_DIR"
if [ -f "docker-compose.yml" ]; then
    docker compose build 2>/dev/null || docker-compose build 2>/dev/null || {
        warn "Docker build failed. Check Dockerfile."
    }
elif [ -f "Dockerfile" ]; then
    docker build -t fable-dashboard:latest . 2>/dev/null || warn "Docker build failed"
fi

ok "Dashboard built"

# ── 13. Verification ─────────────────────────────────────────────────────
log "Running verification..."

FAIL=0

curl -s http://localhost:$API_PORT/health > /dev/null 2>&1 || {
    warn "API not responding on port $API_PORT (expected if not started)"
    FAIL=1
}

if [ ! -f "$DB_PATH" ]; then
    warn "Database not found at $DB_PATH"
    FAIL=1
fi

if [ -f "$INSTALL_DIR/fable_api/main.py" ]; then
    ok "API source found"
else
    err "API source missing"
    FAIL=1
fi

if [ -f "$INSTALL_DIR/fable_mcp_server.py" ]; then
    ok "MCP server found"
else
    err "MCP server missing"
    FAIL=1
fi

# ── 14. Done ─────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "                    🎬 PROJECT FABLE INSTALLED"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "  Install Directory:  $INSTALL_DIR"
echo "  Dashboard:          $DASHBOARD_DIR"
echo "  Assets:             $ASSETS_DIR"
echo "  Database:          $DB_PATH"
echo ""
echo "  API Port:          $API_PORT"
echo "  Dashboard Port:    $DASHBOARD_PORT"
echo ""
echo "  Quick Start:"
echo "    cd $INSTALL_DIR"
echo "    ./start_fable.sh           # Start everything"
echo "    ./start_fable_api.sh       # Start API only"
echo "    ./start_fable_agent.sh     # Start Agent only"
echo ""
echo "  Systemd (auto-start on boot):"
echo "    sudo systemctl enable --now fable-api fable-agent"
echo ""
echo "  Claude MCP:"
echo "    claude mcp add fable -- bash $INSTALL_DIR/start_fable_agent.sh"
echo ""
echo "  URLs:"
echo "    Dashboard:  http://localhost:$DASHBOARD_PORT"
echo "    API:        http://localhost:$API_PORT"
echo "    API Health: http://localhost:$API_PORT/health"
echo ""
echo "  Next Steps:"
echo "    1. Start API:     ./start_fable_api.sh"
echo "    2. Start Agent:   ./start_fable_agent.sh"
echo "    3. Start ComfyUI: cd $COMFYUI_DIR && python main.py"
echo "    4. Add credits:   https://cloud.higgsfield.ai/credits"
echo ""
echo "═══════════════════════════════════════════════════════════════════════"

if [ $FAIL -eq 0 ]; then
    ok "Installation complete!"
else
    warn "Installation completed with warnings. Check logs above."
fi
