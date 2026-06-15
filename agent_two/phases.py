"""
phases.py — single wiring point for all Agent One/Two phase tools.
================================================================================
Instead of wiring five phases into mcp_server.py one by one, import this once:

    from phases import all_phase_tools, ALL_PHASE_NAMES, handle_phase_tool

    @self.server.list_tools()
    async def list_tools():
        return [ ...your base tools... ] + all_phase_tools()

    @self.server.call_tool()
    async def call_tool(name, arguments):
        if name in ALL_PHASE_NAMES:
            return [TextContent(type="text", text=handle_phase_tool(name, arguments))]
        # ...your base tool handling...

That's the whole integration. (Remember the one migration: remove the OLD base
`add_rule` — Phase 4's typed add_rule supersedes it.)
"""

from __future__ import annotations

from typing import Optional


def _imp(mod, *names):
    try:
        m = __import__(mod, fromlist=list(names))
    except ImportError:
        m = __import__(mod.split(".")[-1], fromlist=list(names))
    return [getattr(m, n) for n in names]


# pull each phase's NAMES set + handler (no mcp needed for these)
phase1_NAMES, handle_phase1 = _imp("phase1_tools", "PHASE1_NAMES", "handle_phase1")
phase2_NAMES, handle_phase2 = _imp("phase2_tools", "PHASE2_NAMES", "handle_phase2")
phase3_NAMES, handle_phase3 = _imp("phase3_tools", "PHASE3_NAMES", "handle_phase3")
phase4_NAMES, handle_phase4 = _imp("phase4_tools", "PHASE4_NAMES", "handle_phase4")
phase5_NAMES, handle_phase5 = _imp("phase5_tools", "PHASE5_NAMES", "handle_phase5")

_HANDLERS = [
    (phase1_NAMES, handle_phase1),
    (phase2_NAMES, handle_phase2),
    (phase3_NAMES, handle_phase3),
    (phase4_NAMES, handle_phase4),
    (phase5_NAMES, handle_phase5),
]

ALL_PHASE_NAMES = set().union(*[names for names, _ in _HANDLERS])


def all_phase_tools() -> list:
    """Every phase's Tool objects in one list (needs mcp; call inside the server)."""
    tools = []
    for mod in ("phase1_tools", "phase2_tools", "phase3_tools",
                "phase4_tools", "phase5_tools"):
        fn = _imp(mod, f"{mod.replace('_tools','')}_tools")[0]
        tools += fn()
    return tools


def handle_phase_tool(name: str, arguments: Optional[dict]) -> str:
    """Route a tool call to the phase that owns it."""
    for names, handler in _HANDLERS:
        if name in names:
            return handler(name, arguments)
    return f"Unknown phase tool: {name}"
