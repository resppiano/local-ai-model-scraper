"""
🎬 Fable Agent — The Orchestrator
=================================
A Model Context Protocol (MCP) server that controls the entire
Project Fable film studio.  It is the single point of control for:

    • Creating / managing film projects
    • Writing scripts & planning shots
    • Queuing renders (ComfyUI local  +  Higgsfield cloud)
    • Tracking progress & assembling outputs
    • Integrating with Claude, Gemini, or any MCP client

Run:
    cd /home/gregjones/agent_two
    source venv/bin/activate
    python fable_agent.py

Or via npx (MCP client):
    npx -y @modelcontextprotocol/sdk python fable_agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

# Ensure we can import the FastAPI models
sys.path.insert(0, "/home/gregjones/agent_two")
sys.path.insert(0, "/home/gregjones/agent_two/fable_api")

import httpx

# ── Constants ─────────────────────────────────────────────────────────────
FABLE_API_URL = os.environ.get("FABLE_API_URL", "http://localhost:8001")
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://localhost:8188")
ASSETS_DIR = os.environ.get("FABLE_ASSETS_DIR", "/home/gregjones/FableAssets")

os.makedirs(ASSETS_DIR, exist_ok=True)


# ── HTTP Client ───────────────────────────────────────────────────────────
async def api_get(path: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{FABLE_API_URL}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()


async def api_post(path: str, data: dict):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{FABLE_API_URL}{path}", json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()


async def api_patch(path: str, data: dict):
    async with httpx.AsyncClient() as client:
        resp = await client.patch(f"{FABLE_API_URL}{path}", json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()


# ═══════════════════════════════════════════════════════════════════════
# MCP SERVER
# ═══════════════════════════════════════════════════════════════════════
try:
    from mcp.server import Server
    from mcp.types import TextContent, Tool
    from mcp.server.stdio import stdio_server

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("[FableAgent] MCP SDK not found — running in CLI mode only.")


# ── Tool definitions ────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "fable_create_project",
        "description": "Create a new film project in Fable Studio.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Film title"},
                "logline": {"type": "string", "description": "One-sentence pitch"},
                "vision": {"type": "string", "description": "Visual style and creative direction"},
                "tone": {"type": "string", "description": "e.g. brooding, tense, whimsical"},
                "genre": {"type": "string", "description": "e.g. sci-fi, neo-noir, comedy"},
                "format": {"type": "string", "description": "e.g. short film, episodic 3-5min"},
                "target_length": {"type": "string", "description": "e.g. 2 minutes, 90 seconds"},
                "audience": {"type": "string", "description": "Target audience description"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "fable_list_projects",
        "description": "List all film projects in Fable Studio.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: draft, active, complete, archived"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "fable_get_project",
        "description": "Get full details of a project including shots and assets.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "Project ID"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "fable_add_shot",
        "description": "Add a shot to a project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "scene_number": {"type": "integer", "default": 1},
                "shot_number": {"type": "integer", "default": 1},
                "description": {"type": "string", "description": "Shot description"},
                "prompt": {"type": "string", "description": "AI generation prompt"},
                "motion_prompt": {"type": "string", "description": "Motion description (for video)"},
                "shot_type": {"type": "string", "description": "wide, close-up, medium, etc."},
                "duration": {"type": "number", "description": "Duration in seconds"},
                "character_id": {"type": "integer", "description": "Character to use for consistency"},
                "notes": {"type": "string"},
            },
            "required": ["project_id", "description", "prompt"],
        },
    },
    {
        "name": "fable_list_shots",
        "description": "List shots for a project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "status": {"type": "string", "description": "Filter by status"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "fable_render_shot",
        "description": "Queue a shot for rendering. Will use ComfyUI (local/free) or Higgsfield (cloud/paid).",
        "parameters": {
            "type": "object",
            "properties": {
                "shot_id": {"type": "integer"},
                "provider": {"type": "string", "enum": ["comfyui", "higgsfield"], "description": "comfyui = free local GPU, higgsfield = paid cloud quality"},
                "model": {"type": "string", "description": "Model override (optional)"},
            },
            "required": ["shot_id", "provider"],
        },
    },
    {
        "name": "fable_get_render_status",
        "description": "Check the status of a render job.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "integer"},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "fable_list_assets",
        "description": "List generated assets for a project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "type": {"type": "string", "description": "Filter: image, video, audio, thumbnail"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "fable_create_character",
        "description": "Create a character reference for consistent generation across shots.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "reference_image_url": {"type": "string"},
            },
            "required": ["project_id", "name"],
        },
    },
    {
        "name": "fable_get_dashboard",
        "description": "Get studio dashboard stats (projects, shots, assets, recent activity).",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "fable_write_script",
        "description": "Use the Filmake Agent's Phase 2 writer to generate a full script for a project.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "outline": {"type": "string", "description": "Optional story outline"},
            },
            "required": ["project_id"],
        },
    },
]


# ── Handlers ──────────────────────────────────────────────────────────────
async def handle_tool(name: str, arguments: dict) -> str:
    """Dispatch tool calls."""

    if name == "fable_create_project":
        data = await api_post("/projects", arguments)
        return f"🎬 Created project '{data['title']}' (ID: {data['id']})\nStatus: {data['status']}"

    if name == "fable_list_projects":
        params = {k: v for k, v in arguments.items() if v is not None}
        limit = params.pop("limit", 20)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        path = f"/projects?limit={limit}"
        if qs:
            path += "&" + qs
        data = await api_get(path)
        lines = [f"📁 Projects ({len(data)} total):"]
        for p in data:
            lines.append(f"  [{p['id']}] {p['title']} — {p['status']} ({p['shot_count']} shots, {p['asset_count']} assets)")
        return "\n".join(lines)

    if name == "fable_get_project":
        pid = arguments["project_id"]
        proj = await api_get(f"/projects/{pid}")
        shots = await api_get(f"/projects/{pid}/shots")
        assets = await api_get(f"/projects/{pid}/assets")
        lines = [
            f"🎬 Project: {proj['title']} (ID: {proj['id']})",
            f"   Status: {proj['status']}",
            f"   Logline: {proj['logline'] or '—'}",
            f"   Vision: {proj['vision'] or '—'}",
            f"   Tone: {proj['tone'] or '—'}",
            f"",
            f"📸 Shots ({len(shots)}):",
        ]
        for s in shots:
            lines.append(f"  [{s['id']}] Scene {s['scene_number']}.{s['shot_number']} — {s['status']} — {s['description'][:60]}...")
        lines.append(f"")
        lines.append(f"🖼 Assets ({len(assets)}):")
        for a in assets[:10]:
            lines.append(f"  [{a['type']}] {a['url'][:80]}")
        return "\n".join(lines)

    if name == "fable_add_shot":
        pid = arguments.pop("project_id")
        data = await api_post(f"/projects/{pid}/shots", arguments)
        return f"📸 Added shot {data['scene_number']}.{data['shot_number']} (ID: {data['id']})\nPrompt: {data['prompt'][:100]}..."

    if name == "fable_list_shots":
        pid = arguments["project_id"]
        status = arguments.get("status")
        path = f"/projects/{pid}/shots"
        if status:
            path += f"?status={status}"
        data = await api_get(path)
        lines = [f"📸 Shots for project {pid} ({len(data)} total):"]
        for s in data:
            lines.append(f"  [{s['id']}] {s['scene_number']}.{s['shot_number']} [{s['status']}] {s['description'][:60]}...")
        return "\n".join(lines)

    if name == "fable_render_shot":
        data = await api_post("/render", {
            "shot_id": arguments["shot_id"],
            "provider": arguments["provider"],
            "model": arguments.get("model"),
        })
        provider = arguments["provider"]
        return f"🎨 Queued render (Job {data['job_id']})\nProvider: {provider.upper()}\nStatus: {data['status']}\n{'Use get_render_status to poll.'}"

    if name == "fable_get_render_status":
        data = await api_get(f"/render/{arguments['job_id']}")
        emoji = {"queued": "⏳", "running": "🔄", "completed": "✅", "failed": "❌"}.get(data["status"], "❓")
        lines = [f"{emoji} Render Job {data['job_id']} [{data['status']}]"]
        if data["started_at"]:
            lines.append(f"   Started: {data['started_at']}")
        if data["completed_at"]:
            lines.append(f"   Completed: {data['completed_at']}")
        if data["error_message"]:
            lines.append(f"   Error: {data['error_message']}")
        return "\n".join(lines)

    if name == "fable_list_assets":
        pid = arguments["project_id"]
        t = arguments.get("type")
        path = f"/projects/{pid}/assets"
        if t:
            path += f"?type={t}"
        data = await api_get(path)
        lines = [f"🖼 Assets for project {pid} ({len(data)} total):"]
        for a in data:
            lines.append(f"  [{a['type']}] {a['url'][:100]}")
        return "\n".join(lines)

    if name == "fable_create_character":
        pid = arguments["project_id"]
        data = await api_post(f"/projects/{pid}/characters", {
            "name": arguments["name"],
            "description": arguments.get("description"),
            "reference_image_url": arguments.get("reference_image_url"),
        })
        return f"👤 Character '{data['name']}' created (ID: {data['id']})"

    if name == "fable_get_dashboard":
        data = await api_get("/dashboard/stats")
        lines = [
            "📊 Fable Studio Dashboard",
            f"   Projects: {data['total_projects']} total ({data['active_projects']} active)",
            f"   Shots: {data['total_shots']} total ({data['shots_rendered']} rendered)",
            f"   Assets: {data['total_assets']}",
            f"",
            f"🆕 Recent Assets:",
        ]
        for a in data["recent_assets"][:5]:
            lines.append(f"   [{a['type']}] {a['url'][:80]}")
        return "\n".join(lines)

    if name == "fable_write_script":
        # Integrate with existing Filmake Phase 2 writer
        try:
            from phases import handle_phase_tool
            pid = arguments["project_id"]
            outline = arguments.get("outline", "")

            # Fetch project details first
            proj = await api_get(f"/projects/{pid}")
            project_name = proj["title"]

            # Use Phase 2 to generate script
            result = handle_phase_tool("write_script", {
                "project": project_name,
                "outline": outline,
                "title": project_name,
                "logline": proj.get("logline", ""),
                "vision": proj.get("vision", ""),
                "tone": proj.get("tone", ""),
                "genre": proj.get("genre", ""),
            })
            return f"📝 Script generated for '{project_name}':\n\n{result}"
        except Exception as e:
            return f"⚠️ Script generation failed: {e}\n\nFallback: Please write the script manually and add shots with fable_add_shot."

    return f"Unknown tool: {name}"


# ═══════════════════════════════════════════════════════════════════════
# MCP SERVER ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════
if HAS_MCP:
    server = Server("fable-agent")

    @server.list_tools()
    async def list_tools():
        return [Tool(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"],
        ) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = await handle_tool(name, arguments)
        return [TextContent(type="text", text=result)]

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)


# ═══════════════════════════════════════════════════════════════════════
# CLI MODE (when MCP SDK is missing)
# ═══════════════════════════════════════════════════════════════════════
async def cli_repl():
    """Interactive CLI when running without an MCP client."""
    print("🎬 Fable Agent — Interactive Mode")
    print("Commands: project, shots, add_shot, render, status, assets, dashboard, quit")
    print("")

    while True:
        try:
            cmd = input("fable> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd or cmd.lower() in ("quit", "exit", "q"):
            break

        try:
            if cmd == "dashboard":
                print(await handle_tool("fable_get_dashboard", {}))
            elif cmd == "project":
                print(await handle_tool("fable_list_projects", {}))
            elif cmd.startswith("project "):
                pid = int(cmd.split()[1])
                print(await handle_tool("fable_get_project", {"project_id": pid}))
            elif cmd.startswith("shots "):
                pid = int(cmd.split()[1])
                print(await handle_tool("fable_list_shots", {"project_id": pid}))
            elif cmd.startswith("assets "):
                pid = int(cmd.split()[1])
                print(await handle_tool("fable_list_assets", {"project_id": pid}))
            elif cmd.startswith("render "):
                parts = cmd.split()
                shot_id = int(parts[1])
                provider = parts[2] if len(parts) > 2 else "comfyui"
                print(await handle_tool("fable_render_shot", {"shot_id": shot_id, "provider": provider}))
            elif cmd.startswith("status "):
                job_id = int(cmd.split()[1])
                print(await handle_tool("fable_get_render_status", {"job_id": job_id}))
            else:
                print("Unknown command. Try: dashboard, project, shots <id>, render <shot_id> [comfyui|higgsfield], status <job_id>, assets <id>, quit")
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye.")


if __name__ == "__main__":
    asyncio.run(cli_repl())
