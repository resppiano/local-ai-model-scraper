"""
phase1_tools.py — MCP tool surface for the Phase 1 brain.
================================================================================
Exposes the brain to Hermes as MCP tools. Wire this into your existing
mcp_server.py with two tiny edits (see PHASE1_INTEGRATION.md):

    1) in list_tools():   return [...your 9 tools...] + phase1_tools()
    2) in call_tool():    if name in PHASE1_NAMES:
                              return [TextContent(type="text",
                                      text=handle_phase1(name, arguments))]

All work is delegated to brain.py. Tools default to the active project (set by
start_project) when `project` is omitted, so the workflow reads naturally:
"start a project" then "add this", "set the look", etc.

Set the brain directory once via env: AGENT_ONE_BRAIN_DIR (optional).
"""

from __future__ import annotations

from typing import Optional

try:                                    # works as a package (…import agentone)
    from .brain import Brain, set_active, get_active
except ImportError:                     # works as flat scripts in the same dir
    from brain import Brain, set_active, get_active

# mcp is only present inside the running server; guard so this file imports
# (and smoke-tests) without it.
try:
    from mcp.types import Tool          # type: ignore
    _HAVE_MCP = True
except Exception:                       # pragma: no cover
    Tool = None                         # type: ignore
    _HAVE_MCP = False


# ──────────────────────────────────────────────────────────────────────────
# tool schemas (plain dicts → wrapped as mcp Tool objects by phase1_tools())
# ──────────────────────────────────────────────────────────────────────────
_SCHEMAS: list[dict] = [
    {
        "name": "start_project",
        "description": ("Open or create a film project from a treatment (richer than a "
                        "logline). Sets it active so later brain tools default to it."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name / id."},
                "title": {"type": "string"},
                "logline": {"type": "string"},
                "vision": {"type": "string", "description": "The creative-vision paragraph(s)."},
                "tone": {"type": "string"},
                "genre": {"type": "string"},
                "format": {"type": "string", "description": "e.g. '30s social', 'episodic 3-5min', 'short film'."},
                "target_length": {"type": "string"},
                "audience": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["project"],
        },
    },
    {
        "name": "set_visual_language",
        "description": "Lock the project's look once: palette, lensing, lighting, grade, framing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "look": {"type": "string"},
                "primary_reference": {"type": "string", "description": "film-comp, e.g. 'Blade Runner 2049 meets The Lighthouse'"},
                "palette": {"type": "array", "items": {"type": "string"}},
                "lensing": {"type": "string"},
                "lighting": {"type": "string"},
                "film_stock": {"type": "string", "description": "e.g. 'heavy 35mm grain, 2K, high contrast'"},
                "grade": {"type": "string"},
                "framing": {"type": "string"},
                "avoid": {"type": "array", "items": {"type": "string"}, "description": "negatives, e.g. 'no neon', 'no digital sheen'"},
                "references": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "set_brand_guidelines",
        "description": "Set brand voice, typography, colors, and do/don't rules the film must respect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "name": {"type": "string"},
                "voice": {"type": "string"},
                "typography": {"type": "string"},
                "logo_usage": {"type": "string"},
                "colors": {"type": "array", "items": {"type": "string"}},
                "rules": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "add_inspiration",
        "description": "Register a reference (image/video/link) as visual inspiration for the project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "ref": {"type": "string", "description": "Path or URL."},
                "kind": {"type": "string", "enum": ["image", "video", "link"]},
                "note": {"type": "string"},
            },
            "required": ["ref"],
        },
    },
    {
        "name": "add_knowledge",
        "description": "Drop a script/brief/spec/research doc into the project knowledge bank.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "source": {"type": "string", "description": "Path / URL / title."},
                "kind": {"type": "string",
                         "enum": ["script", "brief", "spec", "episode", "research"]},
                "content": {"type": "string", "description": "Optional inline text."},
                "note": {"type": "string"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "add_to_bible",
        "description": ("Add/update the series bible: set series info, or add a recurring "
                        "character for cross-episode continuity."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "series_title": {"type": "string"},
                "premise": {"type": "string"},
                "character": {"type": "string", "description": "Recurring character name to add/update."},
                "role": {"type": "string"},
                "description": {"type": "string"},
                "arc": {"type": "string"},
                "voice": {"type": "string", "description": "How they speak."},
                "look": {"type": "string", "description": "Visual continuity notes."},
                "first_appears": {"type": "string"},
            },
        },
    },
    {
        "name": "import_episode",
        "description": ("Ingest an episode script (e.g. an Episodo export). Stores the script in "
                        "the knowledge bank and registers the episode in the series bible."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "number": {"type": "string", "description": "e.g. 'S1E01' or '1'."},
                "title": {"type": "string"},
                "logline": {"type": "string"},
                "content": {"type": "string", "description": "The script text (handoff path)."},
                "source": {"type": "string", "description": "Path/URL if not inlining text."},
            },
            "required": ["number"],
        },
    },
    {
        "name": "get_brain",
        "description": "Return a readable digest of the project brain (treatment, look, brand, refs, bible).",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
        },
    },
]

PHASE1_NAMES = {s["name"] for s in _SCHEMAS}


def phase1_tools() -> list:
    """Return mcp Tool objects to splice into your list_tools() handler."""
    if not _HAVE_MCP:
        raise RuntimeError("mcp not importable here; call inside the running MCP server.")
    return [Tool(name=s["name"], description=s["description"],
                 inputSchema=s["inputSchema"]) for s in _SCHEMAS]


# ──────────────────────────────────────────────────────────────────────────
# dispatcher
# ──────────────────────────────────────────────────────────────────────────
def _resolve_project(args: dict) -> str:
    proj = (args or {}).get("project") or get_active()
    if not proj:
        raise ValueError("No project given and no active project. Call start_project first.")
    return proj


def handle_phase1(name: str, arguments: Optional[dict]) -> str:
    """Execute a Phase 1 tool. Returns a human-readable string for TextContent.
    Never raises — errors come back as readable text so Hermes gets a clean reply."""
    try:
        return _dispatch(name, arguments or {})
    except Exception as e:
        return f"Error in {name}: {e}"


def _dispatch(name: str, args: dict) -> str:
    if name not in PHASE1_NAMES:
        return f"Unknown Phase 1 tool: {name}"
    if name == "start_project":
        proj = args.get("project")
        if not proj:
            return "Error: 'project' is required."
        b = Brain.load(proj)
        b.set_treatment(
            title=args.get("title"), logline=args.get("logline"),
            vision=args.get("vision"), tone=args.get("tone"),
            genre=args.get("genre"), format=args.get("format"),
            target_length=args.get("target_length"),
            audience=args.get("audience"), notes=args.get("notes"),
        ).save()
        set_active(proj)
        return f"Project '{proj}' opened and set active.\n\n{b.to_summary()}"

    proj = _resolve_project(args)
    b = Brain.load(proj)

    if name == "set_visual_language":
        b.set_visual_language(
            look=args.get("look"), palette=args.get("palette"),
            lensing=args.get("lensing"), lighting=args.get("lighting"),
            grade=args.get("grade"), framing=args.get("framing"),
            references=args.get("references"),
        ).save()
        return f"Visual language updated for '{proj}'."

    if name == "set_brand_guidelines":
        b.set_brand(
            name=args.get("name"), voice=args.get("voice"),
            typography=args.get("typography"), logo_usage=args.get("logo_usage"),
            colors=args.get("colors"), rules=args.get("rules"),
        ).save()
        return f"Brand guidelines updated for '{proj}'."

    if name == "add_inspiration":
        item = b.add_inspiration(ref=args["ref"], kind=args.get("kind", "link"),
                                 note=args.get("note", ""))
        b.save()
        return f"Added inspiration [{item.kind}] {item.ref}  ({item.id})."

    if name == "add_knowledge":
        doc = b.add_knowledge(source=args["source"], kind=args.get("kind", "brief"),
                              content=args.get("content", ""), note=args.get("note", ""))
        b.save()
        return f"Added knowledge [{doc.kind}] {doc.source}  ({doc.id})."

    if name == "add_to_bible":
        msgs = []
        if args.get("series_title") or args.get("premise"):
            b.set_series(series_title=args.get("series_title"),
                         premise=args.get("premise"))
            msgs.append("series info set")
        if args.get("character"):
            ch = b.add_bible_character(
                name=args["character"], role=args.get("role"),
                description=args.get("description"), arc=args.get("arc"),
                voice=args.get("voice"), look=args.get("look"),
                first_appears=args.get("first_appears"),
            )
            msgs.append(f"character '{ch.name}' added/updated")
        b.save()
        return f"Bible updated for '{proj}': " + (", ".join(msgs) if msgs else "no changes.")

    if name == "import_episode":
        res = b.import_episode(
            number=args["number"], title=args.get("title", ""),
            logline=args.get("logline", ""), content=args.get("content", ""),
            source=args.get("source", ""),
        )
        b.save()
        return (f"Imported episode {res['episode']['number']} "
                f"'{res['episode']['title']}' → knowledge {res['knowledge_id']}, "
                f"status {res['episode']['status']}.")

    if name == "get_brain":
        return b.to_summary()

    return f"Unknown Phase 1 tool: {name}"
