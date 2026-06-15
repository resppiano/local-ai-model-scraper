"""
phase5_tools.py — MCP tool surface for Phase 5 (variants + hero + scenes).
================================================================================
Thin by design — autopilot generates options and accepts a human's pick; the
rich curation lives in the separate manual workflow.

Tools:
  • generate_variants — render N candidates for a shot
  • list_candidates   — show candidates awaiting a pick
  • mark_hero         — record a human's chosen frame as the shot's output
  • set_scene         — group a shot into a scene
  • list_scene        — list a scene's shots

Wire in like the other phases:
  list_tools(): + phase5_tools()
  call_tool():  if name in PHASE5_NAMES: ... handle_phase5(...)
"""

from __future__ import annotations

from typing import Optional

try:
    from . import curate as C
    from .brain import get_active
except ImportError:
    import curate as C
    from brain import get_active

try:
    from mcp.types import Tool          # type: ignore
    _HAVE_MCP = True
except Exception:
    Tool = None                         # type: ignore
    _HAVE_MCP = False


_SCHEMAS: list[dict] = [
    {
        "name": "generate_variants",
        "description": ("Render N candidate versions of a shot to choose from. API "
                        "backends render N; handoff backends return one 'make N' instruction."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "shot_id": {"type": "string"},
                "n": {"type": "integer", "description": "how many candidates (default 4)"},
            },
            "required": ["shot_id"],
        },
    },
    {
        "name": "list_candidates",
        "description": "Show a shot's candidate renders awaiting a hero pick.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}, "shot_id": {"type": "string"}},
            "required": ["shot_id"],
        },
    },
    {
        "name": "mark_hero",
        "description": ("Record the chosen frame as the shot's output. choice = a candidate "
                        "id, a 1-based index, or a file path (e.g. a hero from manual curation)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "shot_id": {"type": "string"},
                "choice": {"type": "string"},
                "backend": {"type": "string"},
            },
            "required": ["shot_id", "choice"],
        },
    },
    {
        "name": "set_scene",
        "description": "Group a shot into a named scene.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "shot_id": {"type": "string"},
                "scene": {"type": "string"},
            },
            "required": ["shot_id", "scene"],
        },
    },
    {
        "name": "list_scene",
        "description": "List the shots in a scene with their status.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}, "scene": {"type": "string"}},
            "required": ["scene"],
        },
    },
]

PHASE5_NAMES = {s["name"] for s in _SCHEMAS}


def phase5_tools() -> list:
    if not _HAVE_MCP:
        raise RuntimeError("mcp not importable here; call inside the running MCP server.")
    return [Tool(name=s["name"], description=s["description"],
                 inputSchema=s["inputSchema"]) for s in _SCHEMAS]


def handle_phase5(name: str, arguments: Optional[dict]) -> str:
    try:
        return _dispatch(name, arguments or {})
    except Exception as e:
        return f"Error in {name}: {e}"


def _proj(args: dict) -> str:
    p = args.get("project") or get_active()
    if not p:
        raise ValueError("No project given and no active project. Call start_project first.")
    return p


def _dispatch(name: str, args: dict) -> str:
    if name not in PHASE5_NAMES:
        return f"Unknown Phase 5 tool: {name}"
    project = _proj(args)

    if name == "generate_variants":
        r = C.generate_variants(project, args["shot_id"], n=args.get("n", 4))
        if r.get("error"):
            return r["error"]
        if r.get("mode") == "handoff":
            return (f"{r['shot_id']}: handoff — "
                    f"{r['handoff'].get('instructions')}")
        if r.get("blocked"):
            return f"{r['shot_id']}: blocked — {r['blocked']}"
        return (f"{r['shot_id']}: {r['candidates_made']} candidates "
                f"({', '.join(r.get('candidates', []))}). Pick one with mark_hero.")

    if name == "list_candidates":
        r = C.list_candidates(project, args["shot_id"])
        if r.get("error"):
            return r["error"]
        if not r["candidates"]:
            return f"{args['shot_id']}: no candidates yet (status {r['status']})."
        lines = [f"{args['shot_id']} candidates ({r['count']}):"]
        for c in r["candidates"]:
            star = " ★ hero" if c.get("chosen") else ""
            lines.append(f"  {c['id']}: {c['output']} [{c['backend']}]{star}")
        return "\n".join(lines)

    if name == "mark_hero":
        r = C.mark_hero(project, args["shot_id"], args["choice"], args.get("backend", ""))
        return r.get("error") or f"{r['shot_id']} hero set → {r['hero']} [{r['backend']}]"

    if name == "set_scene":
        r = C.set_scene(project, args["shot_id"], args["scene"])
        return r.get("error") or f"{r['shot_id']} → scene '{r['scene']}'"

    if name == "list_scene":
        r = C.list_scene(project, args["scene"])
        if not r["shots"]:
            return f"No shots in scene '{r['scene']}'."
        lines = [f"Scene '{r['scene']}' ({r['count']} shots):"]
        for s in r["shots"]:
            lines.append(f"  [{s['order']:>2}] {s['id']}: {s['status']} "
                         f"({s['candidates']} candidates)")
        return "\n".join(lines)

    return f"Unhandled: {name}"
