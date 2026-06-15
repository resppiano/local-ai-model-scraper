#!/usr/bin/env python3
"""
Fable Agent MCP Server (Standalone)
====================================
A proper MCP server for Project Fable using the Python SDK.

Run:
    cd /home/gregjones/agent_two
    source venv/bin/activate
    python fable_mcp_server.py

Or connect from Claude:
    claude mcp add fable -- python /home/gregjones/agent_two/fable_mcp_server.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, "/home/gregjones/agent_two")
sys.path.insert(0, "/home/gregjones/agent_two/fable_api")

import httpx

FABLE_API_URL = os.environ.get("FABLE_API_URL", "http://localhost:8001")


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


# ── Tool Handlers ─────────────────────────────────────────────────────────
async def handle_create_project(args: dict) -> str:
    data = await api_post("/projects", args)
    return f"🎬 Created project '{data['title']}' (ID: {data['id']})\nStatus: {data['status']}"


async def handle_list_projects(args: dict) -> str:
    limit = args.get("limit", 20)
    status = args.get("status")
    qs = f"?limit={limit}"
    if status:
        qs += f"&status={status}"
    data = await api_get(f"/projects{qs}")
    lines = [f"📁 Projects ({len(data)} total):"]
    for p in data:
        lines.append(f"  [{p['id']}] {p['title']} — {p['status']} ({p['shot_count']} shots, {p['asset_count']} assets)")
    return "\n".join(lines)


async def handle_get_project(args: dict) -> str:
    pid = args["project_id"]
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


async def handle_add_shot(args: dict) -> str:
    pid = args.pop("project_id")
    data = await api_post(f"/projects/{pid}/shots", args)
    return f"📸 Added shot {data['scene_number']}.{data['shot_number']} (ID: {data['id']})\nPrompt: {data['prompt'][:100]}..."


async def handle_list_shots(args: dict) -> str:
    pid = args["project_id"]
    status = args.get("status")
    path = f"/projects/{pid}/shots"
    if status:
        path += f"?status={status}"
    data = await api_get(path)
    lines = [f"📸 Shots for project {pid} ({len(data)} total):"]
    for s in data:
        lines.append(f"  [{s['id']}] {s['scene_number']}.{s['shot_number']} [{s['status']}] {s['description'][:60]}...")
    return "\n".join(lines)


async def handle_render_shot(args: dict) -> str:
    data = await api_post("/render", {
        "shot_id": args["shot_id"],
        "provider": args["provider"],
        "model": args.get("model"),
    })
    provider = args["provider"]
    return f"🎨 Queued render (Job {data['job_id']})\nProvider: {provider.upper()}\nStatus: {data['status']}"


async def handle_get_render_status(args: dict) -> str:
    data = await api_get(f"/render/{args['job_id']}")
    emoji = {"queued": "⏳", "running": "🔄", "completed": "✅", "failed": "❌"}.get(data["status"], "❓")
    lines = [f"{emoji} Render Job {data['job_id']} [{data['status']}]"]
    if data.get("started_at"):
        lines.append(f"   Started: {data['started_at']}")
    if data.get("completed_at"):
        lines.append(f"   Completed: {data['completed_at']}")
    if data.get("error_message"):
        lines.append(f"   Error: {data['error_message']}")
    return "\n".join(lines)


async def handle_list_assets(args: dict) -> str:
    pid = args["project_id"]
    t = args.get("type")
    path = f"/projects/{pid}/assets"
    if t:
        path += f"?type={t}"
    data = await api_get(path)
    lines = [f"🖼 Assets for project {pid} ({len(data)} total):"]
    for a in data:
        lines.append(f"  [{a['type']}] {a['url'][:100]}")
    return "\n".join(lines)


async def handle_create_character(args: dict) -> str:
    pid = args["project_id"]
    data = await api_post(f"/projects/{pid}/characters", {
        "name": args["name"],
        "description": args.get("description"),
        "reference_image_url": args.get("reference_image_url"),
    })
    return f"👤 Character '{data['name']}' created (ID: {data['id']})"


async def handle_get_dashboard(args: dict) -> str:
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


TOOLS = {
    "fable_create_project": handle_create_project,
    "fable_list_projects": handle_list_projects,
    "fable_get_project": handle_get_project,
    "fable_add_shot": handle_add_shot,
    "fable_list_shots": handle_list_shots,
    "fable_render_shot": handle_render_shot,
    "fable_get_render_status": handle_get_render_status,
    "fable_list_assets": handle_list_assets,
    "fable_create_character": handle_create_character,
    "fable_get_dashboard": handle_get_dashboard,
}


# ── MCP Server using stdio ────────────────────────────────────────────────
async def main():
    """Simple JSON-RPC over stdio MCP server."""
    print("🎬 Fable Agent MCP Server started", file=sys.stderr)
    print("Connecting to Fable API at", FABLE_API_URL, file=sys.stderr)

    # Send initialize response
    init_req = json.loads(input())
    init_resp = {
        "jsonrpc": "2.0",
        "id": init_req.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fable-agent", "version": "0.1.0"},
        },
    }
    print(json.dumps(init_resp), flush=True)

    # Send tools list
    tools_list = {
        "jsonrpc": "2.0",
        "id": None,
        "method": "notifications/tools/list",
        "params": {
            "tools": [
                {
                    "name": name,
                    "description": name.replace("fable_", "").replace("_", " "),
                    "inputSchema": {"type": "object", "properties": {}},
                }
                for name in TOOLS
            ]
        },
    }
    print(json.dumps(tools_list), flush=True)

    # Handle requests
    while True:
        try:
            line = input()
            req = json.loads(line)
            method = req.get("method", "")
            req_id = req.get("id")

            if method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": name,
                                "description": name.replace("fable_", "").replace("_", " "),
                                "inputSchema": {"type": "object", "properties": {}},
                            }
                            for name in TOOLS
                        ]
                    },
                }
                print(json.dumps(resp), flush=True)

            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name", "")
                args = json.loads(params.get("arguments", "{}"))

                if tool_name in TOOLS:
                    try:
                        result = await TOOLS[tool_name](args)
                        resp = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": [{"type": "text", "text": result}]
                            },
                        }
                    except Exception as e:
                        resp = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": [{"type": "text", "text": f"❌ Error: {e}"}],
                                "isError": True,
                            },
                        }
                else:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                    }
                print(json.dumps(resp), flush=True)

        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
