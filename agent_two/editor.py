"""
editor.py — Agent One / Agent Two Phase 3: multi-shot editing.
================================================================================
The InVideo "change one thing, update every clip" feature.

Each shot records WHICH entities it depends on (characters, locations, rules,
the visual language, the brand). The registry tracks a VERSION per entity. When
a shot is rendered, it stamps the versions it rendered against. An edit bumps the
entity's version — which makes exactly the shots that depend on it "stale"
automatically, with no manual bookkeeping. `rerender` then re-runs only the stale
shots through the Phase 2 router/dispatch.

Decoupled like brain.py and router.py: standalone, persists its own JSON per
project in the brain dir, applies brain changes through brain.py's public
mutators, and never touches Greg's base WorldState/Director.

Storage: <brain_dir>/<project>.shots.json
Stdlib only (imports brain.py + dispatch.py from the same package).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

try:
    from .brain import Brain, _safe_name
    from .dispatch import render_shot as _default_render
except ImportError:
    from brain import Brain, _safe_name
    from dispatch import render_shot as _default_render


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _brain_dir() -> Path:
    d = os.environ.get("AGENT_ONE_BRAIN_DIR", "agentone_brain")
    p = Path(d).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


# ──────────────────────────────────────────────────────────────────────────
# dependency keys
# ──────────────────────────────────────────────────────────────────────────
GLOBAL_KEYS = {"visual_language", "brand", "treatment"}


def dep_key(kind: str, name: str = "") -> str:
    """Normalized dependency key, e.g. 'character:Dan Retriever' or 'visual_language'."""
    kind = kind.strip().lower()
    if kind in GLOBAL_KEYS or not name:
        return kind
    return f"{kind}:{name.strip()}"


def derive_deps(shot: dict, characters: Optional[list] = None) -> list[str]:
    """Build a sensible dependency list from a shot dict.
    - every visual shot depends on visual_language + brand
    - any character names in shot['characters'] (or passed in) → character: deps
    - shot['location'] → location: dep
    Pass characters explicitly if the shot doesn't carry them."""
    deps: list[str] = ["visual_language", "brand"]
    chars = shot.get("characters") or characters or []
    if isinstance(chars, str):
        chars = [chars]
    for c in chars:
        deps.append(dep_key("character", c))
    loc = shot.get("location")
    if loc:
        deps.append(dep_key("location", loc))
    for r in (shot.get("rules") or []):
        deps.append(dep_key("rule", str(r)))
    # de-dup, preserve order
    seen, out = set(), []
    for d in deps:
        if d not in seen:
            seen.add(d); out.append(d)
    return out


# ──────────────────────────────────────────────────────────────────────────
# data
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class ShotRecord:
    id: str
    order: int = 0
    scene: str = ""                                 # scene grouping (Phase 5)
    spec: dict = field(default_factory=dict)        # router-facing fields
    content: dict = field(default_factory=dict)     # creative payload (prompt, dialogue)
    depends_on: list = field(default_factory=list)  # dependency keys
    rendered_versions: dict = field(default_factory=dict)  # key -> version at last render
    candidates: list = field(default_factory=list)  # [{id, output, backend, chosen}] (Phase 5)
    status: str = "pending"   # pending | rendered | stale | handoff | blocked | candidates
    backend: str = ""
    output: str = ""
    updated: str = field(default_factory=_now)


@dataclass
class ShotRegistry:
    project: str
    versions: dict = field(default_factory=dict)    # entity key -> current version
    shots: dict = field(default_factory=dict)       # id -> ShotRecord
    updated: str = field(default_factory=_now)

    # ── persistence ──
    @staticmethod
    def path_for(project: str) -> Path:
        return _brain_dir() / f"{_safe_name(project)}.shots.json"

    @classmethod
    def load(cls, project: str) -> "ShotRegistry":
        p = cls.path_for(project)
        if not p.exists():
            return cls(project=project)
        d = json.loads(p.read_text(encoding="utf-8"))
        reg = cls(project=project,
                  versions=d.get("versions", {}),
                  updated=d.get("updated", _now()))
        reg.shots = {sid: ShotRecord(**rec) for sid, rec in d.get("shots", {}).items()}
        return reg

    def save(self) -> Path:
        self.updated = _now()
        p = ShotRegistry.path_for(self.project)
        p.write_text(json.dumps({
            "project": self.project,
            "versions": self.versions,
            "updated": self.updated,
            "shots": {sid: asdict(r) for sid, r in self.shots.items()},
        }, indent=2), encoding="utf-8")
        return p

    # ── versions ──
    def current_version(self, key: str) -> int:
        return self.versions.get(key, 1)

    def bump_version(self, key: str) -> int:
        self.versions[key] = self.current_version(key) + 1
        return self.versions[key]

    # ── shots ──
    def upsert_shot(self, id: str, spec: dict, content: Optional[dict] = None,
                    depends_on: Optional[list] = None, order: Optional[int] = None) -> ShotRecord:
        rec = self.shots.get(id)
        if rec is None:
            rec = ShotRecord(id=id, order=order if order is not None else len(self.shots))
            self.shots[id] = rec
        rec.spec = spec
        if content is not None:
            rec.content = content
        rec.depends_on = depends_on if depends_on is not None else derive_deps(spec)
        if order is not None:
            rec.order = order
        if rec.status == "rendered":
            # spec changed → may need re-render; recompute staleness lazily
            pass
        rec.updated = _now()
        return rec

    def is_stale(self, rec: ShotRecord) -> bool:
        if rec.status in ("pending", "stale", "blocked"):
            return True
        if rec.status == "handoff":
            return False   # awaiting manual render, not "stale" until a new edit
        for dep in rec.depends_on:
            if self.current_version(dep) > rec.rendered_versions.get(dep, 0):
                return True
        return False

    def stale_shots(self) -> list[ShotRecord]:
        return [r for r in self._ordered() if self.is_stale(r)]

    def affected_by(self, target: str) -> list[ShotRecord]:
        return [r for r in self._ordered() if target in r.depends_on]

    def _ordered(self) -> list[ShotRecord]:
        return sorted(self.shots.values(), key=lambda r: (r.order, r.id))

    def record_render(self, id: str, backend: str = "", output: str = "",
                      status: str = "rendered") -> None:
        rec = self.shots[id]
        rec.backend = backend
        rec.output = output
        rec.status = status
        # stamp current versions so it's not re-flagged until the next edit
        rec.rendered_versions = {d: self.current_version(d) for d in rec.depends_on}
        rec.updated = _now()

    def to_summary(self) -> str:
        L = [f"Shots for '{self.project}' ({len(self.shots)}):"]
        for r in self._ordered():
            flag = "STALE" if self.is_stale(r) else r.status.upper()
            L.append(f"  [{r.order:>2}] {r.id:<12} {flag:<8} "
                     f"{r.backend or '-':<12} deps={', '.join(r.depends_on)}")
        if self.versions:
            L.append("  versions: " + ", ".join(f"{k}={v}" for k, v in self.versions.items()))
        return "\n".join(L)


# ──────────────────────────────────────────────────────────────────────────
# operations (the Phase 3 verbs)
# ──────────────────────────────────────────────────────────────────────────
def _apply_to_brain(project: str, target: str, change: dict) -> Optional[str]:
    """Apply a structured change to the brain for known targets. Returns a note."""
    if not change:
        return None
    b = Brain.load(project)
    kind, _, name = target.partition(":")
    kind = kind.strip().lower()
    if kind == "character" and name:
        b.add_bible_character(name.strip(), **change); note = f"bible character '{name.strip()}' updated"
    elif kind == "visual_language":
        b.set_visual_language(**change); note = "visual language updated"
    elif kind == "brand":
        b.set_brand(**change); note = "brand updated"
    elif kind == "treatment":
        b.set_treatment(**change); note = "treatment updated"
    else:
        return None   # location/rule/etc: tag-only, nothing to write to the brain
    b.save()
    return note


def edit(project: str, target: str, change: Optional[dict] = None) -> dict:
    """
    Apply a change to `target` and make every dependent shot stale.
    target examples: 'character:Dan Retriever', 'visual_language', 'brand',
                     'location:Park', 'rule:no_scifi'.
    `change` is a dict of field updates (applied to the brain where applicable).
    Returns the affected shots (now stale).
    """
    reg = ShotRegistry.load(project)
    note = _apply_to_brain(project, target, change or {})
    reg.bump_version(target)                 # → dependents become stale via version check
    affected = reg.affected_by(target)
    reg.save()
    return {
        "target": target,
        "brain_change": note,
        "new_version": reg.current_version(target),
        "affected": [r.id for r in affected],
        "affected_count": len(affected),
        "note": f"{len(affected)} shot(s) now stale; run rerender to update them.",
    }


def affected_shots(project: str, target: str) -> dict:
    """Dry run: which shots depend on `target`, and which are currently stale."""
    reg = ShotRegistry.load(project)
    aff = reg.affected_by(target)
    return {
        "target": target,
        "affected": [r.id for r in aff],
        "stale": [r.id for r in aff if reg.is_stale(r)],
        "count": len(aff),
    }


def rerender(project: str, shot_ids: Optional[list] = None,
             render_fn: Optional[Callable] = None) -> dict:
    """
    Re-render stale shots (or the given ids) via the Phase 2 dispatch.
    render_fn(payload, project) -> dispatch result; defaults to dispatch.render_shot.
    """
    reg = ShotRegistry.load(project)
    fn = render_fn or _default_render

    if shot_ids:
        targets = [reg.shots[i] for i in shot_ids if i in reg.shots]
    else:
        targets = reg.stale_shots()

    results = []
    for rec in targets:
        payload = dict(rec.spec)
        payload.update(rec.content or {})
        payload["shot_id"] = rec.id
        out = fn(payload, project=project)
        status = out.get("status")
        if status == "rendered":
            reg.record_render(rec.id, backend=out["decision"]["backend"],
                              output=out.get("result", ""), status="rendered")
        elif status == "handoff":
            reg.record_render(rec.id, backend=out.get("backend", ""),
                              output="", status="handoff")
        else:  # blocked
            rec.status = "blocked"
        results.append({"id": rec.id, "status": status,
                        "backend": out.get("backend") or out.get("decision", {}).get("backend")})
    reg.save()
    rendered = sum(1 for r in results if r["status"] == "rendered")
    handoff = sum(1 for r in results if r["status"] == "handoff")
    blocked = sum(1 for r in results if r["status"] == "blocked")
    return {"rerendered": len(results), "rendered": rendered,
            "handoff": handoff, "blocked": blocked, "results": results}


def mark_rendered(project: str, shot_id: str, output: str,
                  backend: str = "") -> dict:
    """Complete a handoff: record the file a human produced for a shot."""
    reg = ShotRegistry.load(project)
    if shot_id not in reg.shots:
        return {"error": f"no such shot: {shot_id}"}
    reg.record_render(shot_id, backend=backend or reg.shots[shot_id].backend,
                      output=output, status="rendered")
    reg.save()
    return {"shot_id": shot_id, "status": "rendered", "output": output}
