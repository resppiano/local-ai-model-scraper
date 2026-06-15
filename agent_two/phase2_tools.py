"""
phase2_tools.py — MCP tool surface for the Phase 2 router.
================================================================================
Three tools for Hermes:
  • set_render_tier  — choose local | online | auto (+ optional budget) per project
  • route_preview    — "which model would you pick for this shot, and why?"
  • list_models      — show the enabled backends

Wire into mcp_server.py exactly like Phase 1 (see PHASE2_INTEGRATION.md):
    list_tools(): return [...] + phase1_tools() + phase2_tools()
    call_tool():  if name in PHASE2_NAMES:
                      return [TextContent(type="text", text=handle_phase2(name, arguments))]
"""

from __future__ import annotations

from typing import Optional

try:
    from .router import (set_render_config, get_render_config,
                         route_preview_text, list_models_text)
    from .brain import get_active
except ImportError:
    from router import (set_render_config, get_render_config,
                        route_preview_text, list_models_text)
    from brain import get_active

try:
    from mcp.types import Tool          # type: ignore
    _HAVE_MCP = True
except Exception:
    Tool = None                         # type: ignore
    _HAVE_MCP = False


_SHOT_PROPS = {
    "subject": {"type": "string",
                "description": "talking_head | action | establishing | broll | still"},
    "needs_lipsync": {"type": "boolean"},
    "motion": {"type": "string", "enum": ["low", "medium", "high"]},
    "style": {"type": "string", "enum": ["photoreal", "stylized", "animated"]},
    "camera_move": {"type": "string", "enum": ["static", "simple", "cinematic"]},
    "duration_seconds": {"type": "number"},
    "fidelity": {"type": "string", "enum": ["draft", "hero"]},
    "still": {"type": "boolean", "description": "true for a keyframe/still image"},
    "frame_control_required": {"type": "boolean",
                               "description": "true if it must match a previous frame"},
}

_SCHEMAS: list[dict] = [
    {
        "name": "set_render_tier",
        "description": ("Set how the router escalates for a project: 'local' (free only), "
                        "'online' (prefer cloud), or 'auto' (local-first, escalate when worth it). "
                        "Optional budget caps online spend (relative cost units)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "tier": {"type": "string", "enum": ["local", "online", "auto"]},
                "budget": {"type": "number"},
            },
            "required": ["tier"],
        },
    },
    {
        "name": "route_preview",
        "description": ("Show which backend the router would pick for a shot and why, "
                        "without rendering. Use to sanity-check before spending."),
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}, **_SHOT_PROPS},
        },
    },
    {
        "name": "list_models",
        "description": "List the enabled render backends and what each is good for.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

PHASE2_NAMES = {s["name"] for s in _SCHEMAS}


def phase2_tools() -> list:
    if not _HAVE_MCP:
        raise RuntimeError("mcp not importable here; call inside the running MCP server.")
    return [Tool(name=s["name"], description=s["description"],
                 inputSchema=s["inputSchema"]) for s in _SCHEMAS]


def handle_phase2(name: str, arguments: Optional[dict]) -> str:
    try:
        return _dispatch(name, arguments or {})
    except Exception as e:
        return f"Error in {name}: {e}"


def _resolve_project(args: dict) -> Optional[str]:
    return args.get("project") or get_active()


def _dispatch(name: str, args: dict) -> str:
    if name not in PHASE2_NAMES:
        return f"Unknown Phase 2 tool: {name}"

    if name == "list_models":
        return list_models_text()

    if name == "set_render_tier":
        proj = _resolve_project(args)
        if not proj:
            return "Error: no project given and no active project. Call start_project first."
        kwargs = {"tier": args.get("tier")}
        if "budget" in args:                 # only touch budget if explicitly given
            kwargs["budget"] = args["budget"]
        cur = set_render_config(proj, **kwargs)
        return (f"Render config for '{proj}': tier={cur['tier']}, "
                f"budget={cur['budget']}.")

    if name == "route_preview":
        proj = _resolve_project(args)
        shot = {k: args[k] for k in _SHOT_PROPS if k in args}
        return route_preview_text(shot, project=proj)

    return f"Unhandled: {name}"
