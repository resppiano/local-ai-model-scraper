#!/usr/bin/env bash
# ═════════════════════════════════════════════════════════════════════════════
# Project Fable — Agent One Quick Setup (FIXED v2)
# =================================================
# For Agent One (or any replica machine).
# This clones the repo, extracts agent_two to ~/agent_two,
# and copies the dashboard to ~/Desktop/app.
#
# Assumes: Ubuntu 24.04, Docker available, git available
# ═════════════════════════════════════════════════════════════════════════════

set -euo pipefail

INSTALL_DIR="${FABLE_INSTALL_DIR:-$HOME/agent_two}"
DASHBOARD_DIR="${FABLE_DASHBOARD_DIR:-$HOME/Desktop/app}"
ASSETS_DIR="${FABLE_ASSETS_DIR:-$HOME/FableAssets}"
API_PORT="${FABLE_API_PORT:-8001}"

REPO_URL="https://github.com/resppiano/local-ai-model-scraper.git"
BRANCH="main"
CLONE_DIR="${FABLE_CLONE_DIR:-$HOME/fable-temp-clone}"

HF_API_KEY="${HF_API_KEY:-}"
HF_SECRET="${HF_SECRET:-}"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${BLUE}[Fable]${NC} $1"; }
ok()  { echo -e "${GREEN}[OK]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ── 1. Clone repo and extract ──────────────────────────────────────────
log "Agent One Quick Setup (v2)"

if [ -d "$CLONE_DIR" ]; then
    rm -rf "$CLONE_DIR"
fi

log "Cloning repo..."
git clone --depth=1 --branch "$BRANCH" "$REPO_URL" "$CLONE_DIR"
ok "Repo cloned"

# Extract agent_two to INSTALL_DIR
if [ -d "$INSTALL_DIR" ]; then
    log "Removing old $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$INSTALL_DIR"
cp -r "$CLONE_DIR/agent_two/"* "$INSTALL_DIR/"
ok "Backend extracted to $INSTALL_DIR"

# Extract dashboard to DASHBOARD_DIR
if [ -d "$DASHBOARD_DIR" ]; then
    log "Removing old $DASHBOARD_DIR..."
    rm -rf "$DASHBOARD_DIR"
fi
mkdir -p "$HOME/Desktop"
cp -r "$CLONE_DIR" "$DASHBOARD_DIR"
rm -rf "$DASHBOARD_DIR/agent_two" 2>/dev/null || true
rm -rf "$DASHBOARD_DIR/.git"
ok "Dashboard extracted to $DASHBOARD_DIR"

# Clean up
rm -rf "$CLONE_DIR"

# ── 2. Python Dependencies ─────────────────────────────────────────────────
log "Setting up Python venv..."
cd "$INSTALL_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -q fastapi uvicorn sqlalchemy aiosqlite python-multipart websockets httpx mcp
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

# ── 7. Verify critical files ─────────────────────────────────────────────
log "Verifying installation..."

FAIL=0

for f in fable_mcp_server.py fable_agent.py fable_api/main.py brain.py phases.py comfyui_renderer.py; do
    if [ -f "$INSTALL_DIR/$f" ]; then
        ok "$f found"
    else
        err "$f MISSING"
        FAIL=1
    fi
done

# ── 8. Systemd (optional) ────────────────────────────────────────────────
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

# ── 9. Done ───────────────────────────────────────────────────────────────
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

if [ $FAIL -eq 0 ]; then
    ok "Setup complete!"
else
    warn "Setup completed with errors. Check logs above."
    exit 1
fi
