"""
phase3_tools.py — MCP tool surface for Phase 3 multi-shot editing.
================================================================================
Tools for Hermes:
  • add_shot        — register/update a shot + its dependencies (usually the
                      Director does this in code, but exposed for Hermes/testing)
  • edit            — change a target (character/visual_language/brand/...) and
                      make every dependent shot stale  ← the headline tool
  • affected_shots  — dry run: what would an edit touch?
  • rerender        — re-render stale shots (or given ids) via Phase 2 dispatch
  • mark_rendered   — complete a handoff: record the file a human produced
  • list_shots      — show the shot registry + statuses

Wire into mcp_server.py like the other phases:
  list_tools(): return [...] + phase1_tools() + phase2_tools() + phase3_tools()
  call_tool():  if name in PHASE3_NAMES:
                    return [TextContent(type="text", text=handle_phase3(name, arguments))]
"""

from __future__ import annotations

import json
from typing import Optional

try:
    from . import editor as E
    from .brain import get_active
except ImportError:
    import editor as E
    from brain import get_active

try:
    from mcp.types import Tool          # type: ignore
    _HAVE_MCP = True
except Exception:
    Tool = None                         # type: ignore
    _HAVE_MCP = False


_SCHEMAS: list[dict] = [
    {
        "name": "add_shot",
        "description": ("Register or update a shot and its dependencies so edits can "
                        "propagate to it. spec = router fields; depends_on auto-derived "
                        "if omitted (visual_language, brand, any characters/location)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "id": {"type": "string", "description": "Stable shot id, e.g. 'S1E01_004'."},
                "order": {"type": "integer"},
                "spec": {"type": "object", "description": "Router fields (subject, fidelity, ...)."},
                "content": {"type": "object", "description": "Creative payload (prompt, dialogue)."},
                "characters": {"type": "array", "items": {"type": "string"}},
                "location": {"type": "string"},
                "depends_on": {"type": "array", "items": {"type": "string"},
                               "description": "Explicit dependency keys; overrides auto-derive."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "edit",
        "description": ("Change a target and make every dependent shot stale. Targets: "
                        "'character:<name>', 'visual_language', 'brand', 'treatment', "
                        "'location:<name>', 'rule:<id>'. change = field updates."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "target": {"type": "string"},
                "change": {"type": "object", "description": "Field updates to apply."},
            },
            "required": ["target"],
        },
    },
    {
        "name": "affected_shots",
        "description": "Dry run: list shots that depend on a target (and which are stale).",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}, "target": {"type": "string"}},
            "required": ["target"],
        },
    },
    {
        "name": "rerender",
        "description": ("Re-render stale shots (default) or specific ids, through the router. "
                        "API backends render; handoff backends return packets to render manually."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "shot_ids": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "mark_rendered",
        "description": "Complete a handoff: record the output file a human produced for a shot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "shot_id": {"type": "string"},
                "output": {"type": "string"},
                "backend": {"type": "string"},
            },
            "required": ["shot_id", "output"],
        },
    },
    {
        "name": "list_shots",
        "description": "Show the shot registry with statuses and dependencies.",
        "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}}},
    },
]

PHASE3_NAMES = {s["name"] for s in _SCHEMAS}


def phase3_tools() -> list:
    if not _HAVE_MCP:
        raise RuntimeError("mcp not importable here; call inside the running MCP server.")
    return [Tool(name=s["name"], description=s["description"],
                 inputSchema=s["inputSchema"]) for s in _SCHEMAS]


def handle_phase3(name: str, arguments: Optional[dict]) -> str:
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
    if name not in PHASE3_NAMES:
        return f"Unknown Phase 3 tool: {name}"
    project = _proj(args)

    if name == "add_shot":
        reg = E.ShotRegistry.load(project)
        spec = args.get("spec", {}) or {}
        # let characters/location ride along for auto-derive
        merged = dict(spec)
        if args.get("characters"):
            merged["characters"] = args["characters"]
        if args.get("location"):
            merged["location"] = args["location"]
        deps = args.get("depends_on") or E.derive_deps(merged)
        rec = reg.upsert_shot(args["id"], spec=spec, content=args.get("content"),
                              depends_on=deps, order=args.get("order"))
        reg.save()
        return f"Shot '{rec.id}' registered (order {rec.order}). deps: {', '.join(rec.depends_on)}"

    if name == "edit":
        res = E.edit(project, args["target"], args.get("change") or {})
        line = f"edit {res['target']} → v{res['new_version']}"
        if res["brain_change"]:
            line += f" ({res['brain_change']})"
        return f"{line}\n{res['note']}\naffected: {', '.join(res['affected']) or '(none)'}"

    if name == "affected_shots":
        r = E.affected_shots(project, args["target"])
        return (f"{r['count']} shot(s) depend on {r['target']}.\n"
                f"  affected: {', '.join(r['affected']) or '(none)'}\n"
                f"  stale now: {', '.join(r['stale']) or '(none)'}")

    if name == "rerender":
        r = E.rerender(project, shot_ids=args.get("shot_ids"))
        head = (f"Re-rendered {r['rerendered']} shot(s): "
                f"{r['rendered']} rendered, {r['handoff']} handoff, {r['blocked']} blocked.")
        body = "\n".join(f"  {x['id']}: {x['status']} ({x['backend']})" for x in r["results"])
        return head + ("\n" + body if body else "")

    if name == "mark_rendered":
        r = E.mark_rendered(project, args["shot_id"], args["output"], args.get("backend", ""))
        return r.get("error") or f"Shot '{r['shot_id']}' marked rendered → {r['output']}"

    if name == "list_shots":
        return E.ShotRegistry.load(project).to_summary()

    return f"Unhandled: {name}"
