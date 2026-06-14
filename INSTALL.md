# 🎬 Project Fable — Installation Guide

> Install the complete Fable Studio on any Ubuntu machine (Agent One, Agent Two, etc.)

---

## Quick Install (One-Liner)

```bash
curl -sL https://raw.githubusercontent.com/resppiano/local-ai-model-scraper/main/install-fable.sh | bash
```

**Or** download and run:

```bash
wget https://raw.githubusercontent.com/resppiano/local-ai-model-scraper/main/install-fable.sh
bash install-fable.sh
```

---

## What Gets Installed

| Component | Version | Location |
|-----------|---------|----------|
| Python 3.14+ | system | — |
| Node.js 20+ | LTS | `/usr/bin/node` |
| Docker + Compose | latest | system |
| Fable API (FastAPI) | 0.1.0 | `~/agent_two/fable_api/` |
| Fable Agent (MCP) | 0.1.0 | `~/agent_two/fable_mcp_server.py` |
| Web Dashboard (React) | 0.0.0 | `~/Desktop/app/` |
| Higgsfield MCP | 0.2.0 | npm global |
| SQLite DB | — | `~/agent_two/fable_api/fable.db` |

---

## Requirements

- **OS:** Ubuntu 24.04 LTS (or 22.04+)
- **RAM:** 8GB+ recommended (16GB+ for ComfyUI)
- **Disk:** 20GB+ free
- **GPU:** Optional (for ComfyUI local rendering)
- **Sudo:** Required for package installation
- **Internet:** Required for downloads

---

## Install Options

### Option A: Full Fresh Install

For a completely new machine:

```bash
bash install-fable.sh
```

This will:
1. Install system packages (git, node, docker, python, nginx)
2. Clone the GitHub repo
3. Create Python venv and install deps
4. Install Higgsfield MCP
5. Configure environment variables
6. Initialize SQLite database
7. Create startup scripts
8. Create systemd services
9. Configure Claude MCP
10. Build web dashboard Docker image

### Option B: Agent One Quick Setup

If the repo is **already cloned** (e.g., from a shared filesystem or prior git clone):

```bash
bash agent-one-setup.sh
```

This is faster — skips system package installation and assumes the code exists.

### Option C: Manual Step-by-Step

```bash
# 1. System deps
sudo apt-get update
sudo apt-get install -y git curl nodejs npm docker.io python3 python3-venv sqlite3

# 2. Clone repo
git clone https://github.com/resppiano/local-ai-model-scraper.git ~/agent_two
cd ~/agent_two

# 3. Python venv
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy aiosqlite python-multipart websockets httpx

# 4. Higgsfield MCP
sudo npm install -g higgsfield-mcp

# 5. Set credentials
export HF_API_KEY="your-key"
export HF_SECRET="your-secret"

# 6. Init DB
export FABLE_DB_PATH="~/agent_two/fable_api/fable.db"
python3 -c "from fable_api.database import init_db; init_db()"

# 7. Start API
cd ~/agent_two && ./start_fable_api.sh

# 8. Start Agent (new terminal)
cd ~/agent_two && ./start_fable_agent.sh

# 9. Build dashboard
cd ~/Desktop/app && docker compose up -d --build
```

---

## Post-Install

### Start Everything

```bash
cd ~/agent_two
./start_fable.sh
```

Or individually:
```bash
./start_fable_api.sh      # API on port 8001
./start_fable_agent.sh    # MCP Agent
```

### Enable Auto-Start (Systemd)

```bash
sudo systemctl enable --now fable-api
sudo systemctl enable --now fable-agent
sudo systemctl status fable-api
```

### Connect Claude MCP

```bash
claude mcp add fable -- bash ~/agent_two/start_fable_agent.sh
```

Or it was already configured during install (check `~/.claude.json`).

### Add Higgsfield Credits

1. Go to https://cloud.higgsfield.ai/api-keys
2. Copy API Key and Secret
3. Add to `~/.config/higgsfield/.env`
4. Or re-run install script with credentials

---

## Verify Installation

```bash
# Check API
curl http://localhost:8001/health

# Check Dashboard
curl http://localhost:3001

# Check Docker
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check DB
sqlite3 ~/agent_two/fable_api/fable.db "SELECT * FROM projects;"
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `tsc not found` during dashboard build | Rebuild inside Docker container (npm ci runs there) |
| `docker permission denied` | Logout and login again, or `sudo usermod -aG docker $USER` |
| `uvicorn not found` | Activate venv: `source ~/agent_two/venv/bin/activate` |
| API won't start | Check port 8001 isn't used: `lsof -i :8001` |
| Dashboard shows old title | Hard refresh browser (Ctrl+Shift+R) |

---

## Files Created

| File | Purpose |
|------|---------|
| `~/agent_two/` | Main project directory |
| `~/agent_two/venv/` | Python virtual environment |
| `~/agent_two/fable_api/fable.db` | SQLite database |
| `~/agent_two/start_fable.sh` | Start all services |
| `~/agent_two/start_fable_api.sh` | Start API only |
| `~/agent_two/start_fable_agent.sh` | Start Agent only |
| `~/.config/higgsfield/.env` | Higgsfield credentials |
| `~/.gemini/antigravity/mcp_config.json` | MCP config for Gemini |
| `~/.claude.json` | Claude MCP config |
| `/etc/systemd/system/fable-api.service` | Systemd API service |
| `/etc/systemd/system/fable-agent.service` | Systemd Agent service |
| `~/Desktop/app/` | Web dashboard (React) |
| `~/FableAssets/` | Generated outputs |

---

## Multi-Agent Setup

To replicate across multiple machines:

1. **On AI-2 (master):**
   ```bash
   cd ~/Desktop/app
   git add -A
   git commit -m "setup: add install scripts"
   git push origin main
   ```

2. **On Agent One:**
   ```bash
   curl -sL https://raw.githubusercontent.com/resppiano/local-ai-model-scraper/main/install-fable.sh | bash
   ```

3. **Sync projects** between agents via GitHub or shared volume:
   ```bash
   # Export project
   sqlite3 ~/agent_two/fable_api/fable.db ".dump" > project_backup.sql
   
   # Import on another agent
   sqlite3 ~/agent_two/fable_api/fable.db < project_backup.sql
   ```

---

*Project Fable — Install anywhere, create everywhere.*
