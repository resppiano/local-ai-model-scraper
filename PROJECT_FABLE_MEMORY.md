# 🎬 Project Fable — System Memory & State

> **Machine:** AI-2 (`AI-2` / `10.0.1.17` / `100.104.49.34`)  
> **Date:** June 14, 2026  
> **User:** gregjones / resppiano (GitHub)

---

## What Is Project Fable?

An **AI film studio** that runs entirely on AI-2. It combines a React web dashboard, FastAPI backend, Python film production pipeline (Filmake), local AI rendering (ComfyUI), and cloud AI generation (Higgsfield MCP) — all orchestrated by a single MCP agent.

---

## 🗺️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOU                                    │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │ Web Browser │   │ Claude/GPT  │   │ SSH / Terminal      │   │
│  │ localhost   │   │ MCP Client  │   │ python fable_agent  │   │
│  └──────┬──────┘   └──────┬──────┘   └──────────┬──────────┘   │
└─────────┼─────────────────┼────────────────────┼──────────────┘
          │                 │                    │
          ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  🎬 FABLE AGENT (MCP Server)                                   │
│  /home/gregjones/agent_two/fable_mcp_server.py                  │
│  /home/gregjones/agent_two/fable_agent.py  (CLI fallback)      │
│  Start: ./start_fable_agent.sh                                  │
│  Tools: create_project, add_shot, render_shot, dashboard, etc.   │
├─────────────────────────────────────────────────────────────────┤
│  🔧 FABLE API (FastAPI)                                        │
│  URL: http://localhost:8001                                     │
│  /home/gregjones/agent_two/fable_api/                           │
│  Start: ./start_fable_api.sh                                    │
│  DB: SQLite → /home/gregjones/agent_two/fable_api/fable.db     │
│                                                                 │
│  Endpoints:                                                     │
│    GET    /health                                               │
│    GET    /dashboard/stats                                      │
│    GET/POST /projects                                           │
│    GET/PATCH/DELETE /projects/{id}                              │
│    GET/POST /projects/{id}/shots                              │
│    GET/POST /projects/{id}/characters                           │
│    GET/POST /projects/{id}/assets                              │
│    POST   /render                                               │
│    GET    /render/{id}                                          │
├─────────────────────────────────────────────────────────────────┤
│  🎥 FILMAKE AGENT (Python)                                     │
│  /home/gregjones/agent_two/                                     │
│  Pipeline: Phase 1 (Start) → 2 (Write) → 3 (Plan) → 4 (Render) │
│            → 5 (Edit)                                          │
│  Key files: brain.py, phases.py, comfyui_renderer.py            │
│            director_templates.py, editor.py                     │
│  Demo: python filmake_real_render_test.py                       │
├─────────────────────────────────────────────────────────────────┤
│  🏭 COMFYUI (Local AI)                                           │
│  URL: http://localhost:8188                                     │
│  /home/gregjones/ComfyUI/                                       │
│  Start: python main.py                                          │
│  Models: SDXL Lightning, Wan 2.1 T2V, PhotoMaker, etc.          │
│  Outputs: /home/gregjones/ComfyUI/output/                        │
├─────────────────────────────────────────────────────────────────┤
│  🤖 HIGGSFIELD MCP (Cloud)                                     │
│  npm: higgsfield-mcp (installed globally)                        │
│  Models: Soul, Reve, Seedream, Kling, Seedance, DoP, Speak      │
│  Credentials:                                                   │
│    API Key: b9054caf-91a5-463f-b8eb-a566fe9e7eff               │
│    Secret:  85a9b31f1ef4ba8baad049c7443aa22f6c2958715508ec... │
│  Config: ~/.config/higgsfield/.env                              │
│          ~/.gemini/antigravity/mcp_config.json                  │
│  Status: ⚠️ Needs credits at https://cloud.higgsfield.ai/credits│
├─────────────────────────────────────────────────────────────────┤
│  🌐 WEB DASHBOARD (React + Vite)                                 │
│  URL: http://localhost:3001                                     │
│  /home/gregjones/Desktop/app/                                   │
│  Build: Dockerfile (nginx)                                      │
│  Repo: https://github.com/resppiano/local-ai-model-scraper     │
│                                                                 │
│  Pages:                                                         │
│    /         → Dashboard (stats, recent assets)                │
│    /projects → Project list + create                             │
│    /projects/:id → Shot board + render buttons                 │
│                                                                 │
│  API Client: src/api/fable.ts (talks to localhost:8001)      │
├─────────────────────────────────────────────────────────────────┤
│  🚀 COOLIFY (Deployment)                                        │
│  URL: http://localhost:8000                                     │
│  Apps: Fable Dashboard, Open WebUI, Kasm, Guacamole           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 File Locations

### Fable API (FastAPI Backend)
| File | Purpose |
|------|---------|
| `agent_two/fable_api/__init__.py` | Package marker |
| `agent_two/fable_api/database.py` | SQLAlchemy models + async engine |
| `agent_two/fable_api/schemas.py` | Pydantic request/response models |
| `agent_two/fable_api/main.py` | FastAPI app with all endpoints |
| `agent_two/fable_api/render_queue.py` | Background worker for renders |
| `agent_two/fable_api/comfyui_client.py` | ComfyUI HTTP wrapper |
| `agent_two/fable_api/higgsfield_client.py` | Higgsfield cloud wrapper |
| `agent_two/fable_api/fable.db` | SQLite database |

### Fable Agent (MCP + CLI)
| File | Purpose |
|------|---------|
| `agent_two/fable_mcp_server.py` | MCP server for Claude/GPT |
| `agent_two/fable_agent.py` | Interactive CLI fallback |
| `agent_two/start_fable_api.sh` | One-click API startup |
| `agent_two/start_fable_agent.sh` | One-click Agent startup |

### Web Dashboard
| File | Purpose |
|------|---------|
| `Desktop/app/src/api/fable.ts` | API client (localhost:8001) |
| `Desktop/app/src/components/Layout.tsx` | Navbar + routing layout |
| `Desktop/app/src/pages/Home.tsx` | Dashboard page |
| `Desktop/app/src/pages/Projects.tsx` | Project list + create |
| `Desktop/app/src/pages/ProjectDetail.tsx` | Shot board + render buttons |
| `Desktop/app/Dockerfile` | Multi-stage build (node → nginx) |
| `Desktop/app/nginx.conf` | SPA routing + gzip + cache headers |
| `Desktop/app/docker-compose.yml` | Compose with port 3001 |

### Legacy / Supporting
| File | Purpose |
|------|---------|
| `agent_two/brain.py` | Project memory (treatment, visual language) |
| `agent_two/phases.py` + `phase1-5_tools.py` | 5-phase film pipeline |
| `agent_two/comfyui_renderer.py` | Direct ComfyUI integration |
| `agent_two/filmake_real_render_test.py` | Demo script |
| `Desktop/PROJECT_FABLE_GUIDE.md` | Full user guide |
| `Desktop/higgsfield_demo.mjs` | Higgsfield test script |

---

## 🚀 How to Start Everything

```bash
# Terminal 1: FABLE API
cd /home/gregjones/agent_two
./start_fable_api.sh
# → http://localhost:8001

# Terminal 2: FABLE AGENT (for Claude MCP)
cd /home/gregjones/agent_two
./start_fable_agent.sh
# → MCP stdio server

# Terminal 3: WEB DASHBOARD (already running via Docker)
docker run -d --name fable-dashboard -p 3001:80 fable-dashboard:latest
# → http://localhost:3001

# Terminal 4: COMFYUI (optional, for local rendering)
cd /home/gregjones/ComfyUI
python main.py
# → http://localhost:8188
```

Or use docker-compose for the web app:
```bash
cd /home/gregjones/Desktop/app
docker compose up -d --build
```

---

## 🗄️ Database Schema (SQLite)

```sql
projects (id, title, logline, vision, tone, genre, format,
          target_length, audience, status, created_at, updated_at)

shots (id, project_id, scene_number, shot_number, description,
       prompt, negative_prompt, motion_prompt, shot_type, duration,
       status, render_provider, render_model, render_job_id,
       character_id, notes, created_at, updated_at)

characters (id, project_id, name, description, reference_image_url,
            higgsfield_character_id, comfyui_embedding_path, created_at)

assets (id, project_id, shot_id, type, url, local_path, provider,
        width, height, duration, file_size, meta, created_at)

render_jobs (id, shot_id, provider, status, external_job_id,
             started_at, completed_at, error_message, created_at)
```

**Current Data:**
- Project 1: "Test Project" (0 shots, 0 assets)
- Project 2: "Neon Requiem" (2 shots, 0 assets)
  - Shot 1.1: Wide establishing shot of rain-soaked neon street
  - Shot 1.2: Close-up of protagonist's face in neon light

---

## 🔑 Credentials & Secrets

| Service | Key/Value |
|---------|-----------|
| **Higgsfield API** | `HF_API_KEY=b9054caf-91a5-463f-b8eb-a566fe9e7eff` |
| **Higgsfield Secret** | `HF_SECRET=85a9b31f1ef4ba8baad049c7443aa22f6c2958715508ec000dc0738c574cf2aa` |
| **GitHub** | User: `resppiano` |
| **GitHub Repo** | `https://github.com/resppiano/local-ai-model-scraper` |
| **GitHub Branch** | `main` |

**Stored in:**
- `~/.config/higgsfield/.env` (chmod 600)
- `~/.bashrc` (exports)
- `~/.gemini/antigravity/mcp_config.json`
- `~/.claude.json` (MCP server config)

---

## 🐳 Docker Containers (Active)

| Container | Image | Port | Status |
|-----------|-------|------|--------|
| fable-dashboard | fable-dashboard:latest | 3001→80 | ✅ Running |
| coolify | ghcr.io/coollabsio/coolify:4.1.2 | 8000→8080 | ✅ Running |
| coolify-sentinel | ghcr.io/coollabsio/sentinel:0.0.21 | — | ✅ Running |
| coolify-realtime | ghcr.io/coollabsio/coolify-realtime:1.0.16 | 6001-6002 | ✅ Running |
| coolify-db | postgres:15-alpine | 5432 | ✅ Running |
| coolify-redis | redis:7-alpine | 6379 | ✅ Running |
| open-webui | ghcr.io/open-webui/open-webui:main | 3000→8080 | ✅ Running |
| kasm_proxy | kasmweb/proxy:1.18.0 | 443 | ✅ Running |
| kasm_manager | kasmweb/manager:1.18.0 | — | ✅ Running |
| kasm_api | kasmweb/api:1.18.0 | — | ✅ Running |
| guacamole | guacamole/guacamole:1.6.0 | 8080 | ✅ Running |

---

## ✅ What's Working

| Feature | Status | Notes |
|---------|--------|-------|
| Fable API (FastAPI) | ✅ | Full CRUD for projects, shots, characters, assets, renders |
| SQLite DB | ✅ | Auto-initialized on startup |
| Dashboard page | ✅ | Stats + recent assets |
| Projects page | ✅ | List + create projects |
| Project detail page | ✅ | Shot board + add shots |
| Render buttons | ✅ | ComfyUI + Higgsfield buttons per shot |
| Render queue | ✅ | Background worker (queued → running → done/failed) |
| MCP Server | ✅ | Claude Code configured in `~/.claude.json` |
| Interactive CLI | ✅ | `python fable_agent.py` → `dashboard`, `project`, `render` |
| GitHub push | ✅ | Repo updated, auto-deploy via Coolify |
| Higgsfield install | ✅ | `npm install -g higgsfield-mcp` |
| Docker build | ✅ | Multi-stage Dockerfile builds successfully |

---

## ⚠️ Known Issues & TODOs

| Issue | Severity | Next Step |
|-------|----------|-----------|
| ComfyUI render fails (HTTP 400) | 🔴 High | ComfyUI not running; start `python main.py` in ComfyUI/ |
| Higgsfield "no credits" | 🟡 Medium | Top up at https://cloud.higgsfield.ai/credits |
| Render queue only polls, no webhooks | 🟡 Medium | Add webhook endpoint for ComfyUI/Higgsfield callbacks |
| No asset thumbnails | 🟡 Medium | Auto-generate thumbnails from outputs |
| No character consistency | 🟡 Medium | Integrate PhotoMaker/InstantID into ComfyUI workflows |
| Web dashboard not using HashRouter | 🟡 Medium | Fixed — now using HashRouter for SPA paths |
| Dashboard SPA title cache | 🟢 Low | Refresh browser or hard-reload to see "Project Fable" title |
| Talking head pipeline | 🟢 Low | Requires WAV audio + character photo + Higgsfield credits |
| Backup/Export projects | 🟢 Low | Add ZIP export + GitHub backup |
| Rename repo to `project-fable` | 🟢 Low | Cosmetic — current name is `local-ai-model-scraper` |

---

## 🎯 Common Commands

```bash
# Check what's running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Start Fable API
cd ~/agent_two && ./start_fable_api.sh &

# Start Fable Agent (MCP)
cd ~/agent_two && ./start_fable_agent.sh &

# Start ComfyUI
cd ~/ComfyUI && python main.py &

# Rebuild web dashboard
cd ~/Desktop/app && docker compose up -d --build

# Access SQLite DB
sqlite3 ~/agent_two/fable_api/fable.db "SELECT * FROM projects;"

# Test API
curl http://localhost:8001/health
curl http://localhost:8001/dashboard/stats

# Test render via API
curl -X POST http://localhost:8001/render \
  -H "Content-Type: application/json" \
  -d '{"shot_id":1,"provider":"comfyui"}'

# Push changes to GitHub
cd ~/Desktop/app
git add -A && git commit -m "update" && git push origin main
```

---

## 📞 Quick Access URLs

| Service | URL |
|---------|-----|
| Fable Dashboard | http://localhost:3001 |
| Fable API | http://localhost:8001 |
| Fable API Health | http://localhost:8001/health |
| Coolify | http://localhost:8000 |
| ComfyUI | http://localhost:8188 |
| Open WebUI | http://localhost:3000 |

---

*Project Fable — Your AI studio, on your machine, under your control.*
*Built on AI-2, June 14, 2026.*
