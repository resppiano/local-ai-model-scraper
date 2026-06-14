#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# Project Fable — Agent One Quick Setup
# =====================================
# For Agent One (or any replica machine) that already has the repo cloned.
# This is a faster, leaner version of install-fable.sh.
#
# Assumes: Ubuntu 24.04, git repo already cloned, Docker available
# ═════════════════════════════════════════════════════════════════════════════

set -euo pipefail

INSTALL_DIR="${FABLE_INSTALL_DIR:-$HOME/agent_two}"
DASHBOARD_DIR="${FABLE_DASHBOARD_DIR:-$HOME/Desktop/app}"
ASSETS_DIR="${FABLE_ASSETS_DIR:-$HOME/FableAssets}"
API_PORT="${FABLE_API_PORT:-8001}"

HF_API_KEY="${HF_API_KEY:-}"
HF_SECRET="${HF_SECRET:-}"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${BLUE}[Fable]${NC} $1"; }
ok()  { echo -e "${GREEN}[OK]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ── 1. System Check ────────────────────────────────────────────────────────
log "Agent One Quick Setup"
log "Install dir: $INSTALL_DIR"

if [ ! -d "$INSTALL_DIR" ]; then
    err "Install directory not found: $INSTALL_DIR"
    err "Clone the repo first: git clone https://github.com/resppiano/local-ai-model-scraper.git $INSTALL_DIR"
    exit 1
fi

if [ ! -d "$DASHBOARD_DIR" ]; then
    warn "Dashboard directory not found at $DASHBOARD_DIR"
    warn "Creating symlink..."
    mkdir -p "$HOME/Desktop"
    ln -sf "$INSTALL_DIR/dashboard" "$DASHBOARD_DIR" 2>/dev/null || true
fi

# ── 2. Python Dependencies ─────────────────────────────────────────────────
log "Setting up Python venv..."
cd "$INSTALL_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -q fastapi uvicorn sqlalchemy aiosqlite python-multipart websockets httpx
ok "Python deps installed"

# ── 3. Higgsfield MCP ──────────────────────────────────────────────────────
log "Installing Higgsfield MCP..."
if ! command -v higgsfield-mcp >/dev/null 2>&1; then
    npm install -g higgsfield-mcp 2>/dev/null || sudo npm install -g higgsfield-mcp
fi
ok "Higgsfield MCP ready"

# ── 4. Environment ─────────────────────────────────────────────────────────
log "Configuring environment..."

mkdir -p "$HOME/.config/higgsfield"
mkdir -p "$ASSETS_DIR"

if [ -z "$HF_API_KEY" ]; then
    echo ""
    read -rp "Higgsfield API Key (or Enter to skip): " HF_API_KEY
    read -rp "Higgsfield Secret (or Enter to skip): " HF_SECRET
fi

cat > "$HOME/.config/higgsfield/.env" << EOF
HF_API_KEY=${HF_API_KEY:-}
HF_SECRET=${HF_SECRET:-}
EOF
chmod 600 "$HOME/.config/higgsfield/.env"

if ! grep -q "HF_API_KEY" "$HOME/.bashrc" 2>/dev/null; then
    cat >> "$HOME/.bashrc" << EOF

# Project Fable
export HF_API_KEY="${HF_API_KEY:-}"
export HF_SECRET="${HF_SECRET:-}"
export FABLE_API_URL="http://localhost:$API_PORT"
export FABLE_ASSETS_DIR="$ASSETS_DIR"
EOF
fi

ok "Environment configured"

# ── 5. Database ────────────────────────────────────────────────────────────
log "Initializing database..."
cd "$INSTALL_DIR"
export FABLE_DB_PATH="$INSTALL_DIR/fable_api/fable.db"
python3 -c "
import sys
sys.path.insert(0, 'fable_api')
from database import init_db
init_db()
print('DB OK')
"
ok "Database initialized"

# ── 6. Startup Scripts ────────────────────────────────────────────────────
log "Creating startup scripts..."

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

cat > "$INSTALL_DIR/start_fable.sh" << EOF
#!/usr/bin/env bash
cd "\$(dirname "\$0")"

echo "🎬 Starting Project Fable..."

nohup ./start_fable_api.sh > /tmp/fable_api.log 2>&1 &
sleep 3

if curl -s http://localhost:$API_PORT/health >/dev/null; then
    echo "  ✅ API running on port $API_PORT"
else
    echo "  ⚠️  API starting (check /tmp/fable_api.log)"
fi

nohup ./start_fable_agent.sh > /tmp/fable_agent.log 2>&1 &
echo "  ✅ Agent started"

if command -v docker >/dev/null && [ -d "$DASHBOARD_DIR" ] && [ -f "$DASHBOARD_DIR/docker-compose.yml" ]; then
    echo "  → Starting Dashboard..."
    cd "$DASHBOARD_DIR"
    docker compose up -d --build 2>/dev/null || true
    echo "  ✅ Dashboard on port 3001"
fi

echo ""
echo "  Dashboard: http://localhost:3001"
echo "  API:       http://localhost:$API_PORT"
echo "  Health:    http://localhost:$API_PORT/health"
EOF
chmod +x "$INSTALL_DIR/start_fable.sh"

ok "Scripts ready"

# ── 7. Systemd (optional) ────────────────────────────────────────────────
if command -v systemctl >/dev/null; then
    log "Creating systemd services..."
    
    sudo tee /etc/systemd/system/fable-api.service > /dev/null << EOF
[Unit]
Description=Project Fable API
After=network.target
[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python -m uvicorn fable_api.main:app --host 0.0.0.0 --port $API_PORT --workers 1
Restart=always
[Install]
WantedBy=multi-user.target
EOF

    sudo tee /etc/systemd/system/fable-agent.service > /dev/null << EOF
[Unit]
Description=Project Fable Agent
After=network.target
[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/fable_mcp_server.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    ok "Systemd services created"
    echo "Enable with: sudo systemctl enable --now fable-api fable-agent"
fi

# ── 8. Done ───────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "        🎬 AGENT ONE SETUP COMPLETE"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Start everything:  cd $INSTALL_DIR && ./start_fable.sh"
echo "  Start API only:    ./start_fable_api.sh"
echo "  Start Agent:       ./start_fable_agent.sh"
echo ""
echo "  Dashboard:  http://localhost:3001"
echo "  API:        http://localhost:$API_PORT"
echo ""
echo "═══════════════════════════════════════════════════"
ok "Setup complete!"
