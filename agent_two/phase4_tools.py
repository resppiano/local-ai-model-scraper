"""
phase4_tools.py — MCP tool surface for Phase 4 review + rules.
================================================================================
Tools for Hermes:
  • add_rule        — add a typed rule (forbid/require, scoped)
  • list_rules      — show the rule set
  • remove_rule     — delete a rule by id
  • review_report   — grade every shot against rules + continuity + vision
  • review_shot     — grade a single shot
  • review_and_fix  — apply a registered fixer or escalate findings to you

IMPORTANT — migration: this `add_rule` supersedes the old free-text `add_rule`
from your base 9 tools. REMOVE the old one from your base list_tools() so the
name isn't registered twice (a duplicate tool name breaks the server).

Wire in like the other phases:
  list_tools(): return [...] + phase1_tools() + phase2_tools() + phase3_tools() + phase4_tools()
  call_tool():  if name in PHASE4_NAMES:
                    return [TextContent(type="text", text=handle_phase4(name, arguments))]
"""

from __future__ import annotations

from typing import Optional

try:
    from .rules import RuleSet
    from . import reviewer as RV
    from .brain import get_active
except ImportError:
    from rules import RuleSet
    import reviewer as RV
    from brain import get_active

try:
    from mcp.types import Tool          # type: ignore
    _HAVE_MCP = True
except Exception:
    Tool = None                         # type: ignore
    _HAVE_MCP = False


_SCHEMAS: list[dict] = [
    {
        "name": "add_rule",
        "description": ("Add a typed rule the Reviewer enforces on every shot. "
                        "kind forbid = terms must NOT appear; require = must appear. "
                        "scope global | character | shot_type (+ target)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "scope": {"type": "string", "enum": ["global", "character", "shot_type"]},
                "target": {"type": "string", "description": "character name or shot subject; blank for global"},
                "kind": {"type": "string", "enum": ["forbid", "require"]},
                "terms": {"type": "array", "items": {"type": "string"}},
                "severity": {"type": "string", "enum": ["block", "warn"]},
                "description": {"type": "string"},
            },
            "required": ["terms"],
        },
    },
    {
        "name": "list_rules",
        "description": "Show all rules for the project.",
        "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}}},
    },
    {
        "name": "remove_rule",
        "description": "Delete a rule by its id.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}, "rule_id": {"type": "string"}},
            "required": ["rule_id"],
        },
    },
    {
        "name": "review_report",
        "description": "Grade every shot against rules + continuity + vision; returns pass/warn/block.",
        "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}}},
    },
    {
        "name": "review_shot",
        "description": "Grade one shot by id.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}, "shot_id": {"type": "string"}},
            "required": ["shot_id"],
        },
    },
    {
        "name": "review_and_fix",
        "description": ("Run review; apply a registered fixer to flagged shots if present "
                        "(set apply=true to write), else escalate findings to you."),
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}, "apply": {"type": "boolean"}},
        },
    },
]

PHASE4_NAMES = {s["name"] for s in _SCHEMAS}


def phase4_tools() -> list:
    if not _HAVE_MCP:
        raise RuntimeError("mcp not importable here; call inside the running MCP server.")
    return [Tool(name=s["name"], description=s["description"],
                 inputSchema=s["inputSchema"]) for s in _SCHEMAS]


def handle_phase4(name: str, arguments: Optional[dict]) -> str:
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
    if name not in PHASE4_NAMES:
        return f"Unknown Phase 4 tool: {name}"
    project = _proj(args)

    if name == "add_rule":
        rs = RuleSet.load(project)
        r = rs.add(scope=args.get("scope", "global"), target=args.get("target", ""),
                   kind=args.get("kind", "forbid"), terms=args.get("terms", []),
                   severity=args.get("severity", "warn"), description=args.get("description", ""))
        rs.save()
        scope = r.scope + (f":{r.target}" if r.target else "")
        return f"Added {r.id}: [{r.severity}] {r.kind} {scope} terms={r.terms}"

    if name == "list_rules":
        return RuleSet.load(project).to_summary()

    if name == "remove_rule":
        rs = RuleSet.load(project)
        gone = rs.remove(args["rule_id"])
        rs.save()
        return f"Removed {args['rule_id']}." if gone else f"No such rule: {args['rule_id']}"

    if name == "review_report":
        return RV.review_report_text(project)

    if name == "review_shot":
        rep = RV.review_project(project)
        for rv in rep["reviews"]:
            if rv["shot_id"] == args["shot_id"]:
                lines = [f"{rv['shot_id']}: {rv['status'].upper()}"
                         f" (needs_rerender={rv['needs_rerender']})"]
                for f in rv["findings"]:
                    lines.append(f"  - [{f.get('severity')}] {f.get('message')}")
                return "\n".join(lines)
        return f"No such shot: {args['shot_id']}"

    if name == "review_and_fix":
        r = RV.review_and_fix(project, apply=bool(args.get("apply")))
        out = [f"fixed: {len(r['fixed'])}, escalated: {len(r['escalated'])}"]
        for e in r["escalated"]:
            out.append(f"  ! {e['shot_id']} ({e['status']}): "
                       + "; ".join(f.get("message", "") for f in e["findings"] if f.get("severity") != "info"))
        if r["rerender_after_fix"]:
            out.append(f"  → rerender after fix: {', '.join(r['rerender_after_fix'])}")
        return "\n".join(out)

    return f"Unhandled: {name}"
