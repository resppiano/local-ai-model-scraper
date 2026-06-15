"""
brain.py — Agent One / Agent Two Phase 1: the persistent project "brain".
================================================================================
This is the InVideo "brain" / persistent project context: the thing that
remembers the treatment, the look, the brand rules, your reference material,
and (for serialized work) the series bible — so you never re-explain the same
thing twice.

DESIGN NOTE
-----------
This module is deliberately STANDALONE. It does NOT modify or depend on your
existing WorldState. A Brain persists to its own JSON file, one per project,
under a brain directory. Your Writer/Director can read from it via
`Brain.load(project).to_summary()`; nothing in your existing pipeline has to
change to adopt it.

Storage layout (default brain dir = $AGENT_ONE_BRAIN_DIR or ./agentone_brain):
    agentone_brain/
        _active.json              # remembers the active project name
        <project>.brain.json      # one brain per project

Stdlib only. No third-party imports.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sid(prefix: str) -> str:
    """Short, readable id, e.g. 'insp_9f3a1c20'."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _brain_dir(brain_dir: Optional[str] = None) -> Path:
    d = brain_dir or os.environ.get("AGENT_ONE_BRAIN_DIR", "agentone_brain")
    p = Path(d).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_name(project: str) -> str:
    keep = "-_. "
    cleaned = "".join(c for c in project.strip() if c.isalnum() or c in keep)
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "untitled"


# ──────────────────────────────────────────────────────────────────────────
# data structures
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class Treatment:
    title: str = ""
    logline: str = ""
    vision: str = ""            # the creative-vision paragraph(s)
    tone: str = ""
    genre: str = ""
    format: str = ""           # "30s social" | "episodic 3-5min" | "short film" ...
    target_length: str = ""
    audience: str = ""
    notes: str = ""


@dataclass
class VisualLanguage:
    look: str = ""             # overall look, e.g. "warm film grain, 90s broadcast"
    primary_reference: str = ""   # film-comp, e.g. "Blade Runner 2049 meets The Lighthouse"
    palette: list = field(default_factory=list)   # color names / hex
    lensing: str = ""          # default lenses / DOF behavior
    lighting: str = ""
    film_stock: str = ""       # e.g. "heavy 35mm grain, 2K, high contrast"
    grade: str = ""            # color grade
    framing: str = ""          # default framing conventions
    avoid: list = field(default_factory=list)     # negatives: "no neon", "no digital sheen"
    references: list = field(default_factory=list)  # free-text ref notes


@dataclass
class BrandGuidelines:
    name: str = ""
    voice: str = ""            # brand voice / tone of address
    typography: str = ""
    logo_usage: str = ""
    colors: list = field(default_factory=list)
    rules: list = field(default_factory=list)       # do/don't list


@dataclass
class InspirationRef:
    id: str
    ref: str                   # path or URL
    kind: str                  # "image" | "video" | "link"
    note: str = ""
    added: str = field(default_factory=_now)


@dataclass
class KnowledgeDoc:
    id: str
    source: str                # path / url / title
    kind: str                  # "script" | "brief" | "spec" | "episode" | "research"
    note: str = ""
    content: str = ""          # optional inlined text (e.g. an Episodo export)
    added: str = field(default_factory=_now)


@dataclass
class BibleCharacter:
    name: str
    role: str = ""
    description: str = ""
    arc: str = ""
    voice: str = ""            # how they speak
    look: str = ""             # visual continuity notes
    first_appears: str = ""    # episode number/label


@dataclass
class Episode:
    number: str                # "S1E01" | "1" | ...
    title: str = ""
    logline: str = ""
    script_ref: str = ""       # knowledge doc id or external path
    status: str = "planned"    # planned | scripted | in_production | done


@dataclass
class SeriesBible:
    series_title: str = ""
    premise: str = ""
    characters: dict = field(default_factory=dict)        # name -> BibleCharacter
    episodes: list = field(default_factory=list)          # list[Episode]
    arcs: list = field(default_factory=list)
    recurring_locations: list = field(default_factory=list)
    rules: list = field(default_factory=list)             # series continuity rules


# ──────────────────────────────────────────────────────────────────────────
# the Brain
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class Brain:
    project: str
    created: str = field(default_factory=_now)
    updated: str = field(default_factory=_now)
    treatment: Treatment = field(default_factory=Treatment)
    visual_language: VisualLanguage = field(default_factory=VisualLanguage)
    brand: BrandGuidelines = field(default_factory=BrandGuidelines)
    inspiration: list = field(default_factory=list)       # list[InspirationRef]
    knowledge: list = field(default_factory=list)         # list[KnowledgeDoc]
    bible: SeriesBible = field(default_factory=SeriesBible)

    # ── persistence ──────────────────────────────────────────────────────
    @staticmethod
    def path_for(project: str, brain_dir: Optional[str] = None) -> Path:
        return _brain_dir(brain_dir) / f"{_safe_name(project)}.brain.json"

    @classmethod
    def load(cls, project: str, brain_dir: Optional[str] = None) -> "Brain":
        """Load an existing brain, or return a fresh one for a new project."""
        p = cls.path_for(project, brain_dir)
        if not p.exists():
            return cls(project=project)
        raw = json.loads(p.read_text(encoding="utf-8"))
        return cls._from_dict(raw)

    def save(self, brain_dir: Optional[str] = None) -> Path:
        self.updated = _now()
        p = Brain.path_for(self.project, brain_dir)
        p.write_text(json.dumps(self._to_dict(), indent=2), encoding="utf-8")
        return p

    def _to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def _from_dict(cls, d: dict) -> "Brain":
        b = cls(project=d.get("project", "untitled"))
        b.created = d.get("created", _now())
        b.updated = d.get("updated", _now())
        b.treatment = Treatment(**d.get("treatment", {}))
        b.visual_language = VisualLanguage(**d.get("visual_language", {}))
        b.brand = BrandGuidelines(**d.get("brand", {}))
        b.inspiration = [InspirationRef(**i) for i in d.get("inspiration", [])]
        b.knowledge = [KnowledgeDoc(**k) for k in d.get("knowledge", [])]
        bib = d.get("bible", {}) or {}
        b.bible = SeriesBible(
            series_title=bib.get("series_title", ""),
            premise=bib.get("premise", ""),
            characters={n: BibleCharacter(**c) for n, c in bib.get("characters", {}).items()},
            episodes=[Episode(**e) for e in bib.get("episodes", [])],
            arcs=list(bib.get("arcs", [])),
            recurring_locations=list(bib.get("recurring_locations", [])),
            rules=list(bib.get("rules", [])),
        )
        return b

    # ── mutators (each returns self for chaining; call .save() to persist) ─
    def set_treatment(self, **fields) -> "Brain":
        for k, v in fields.items():
            if hasattr(self.treatment, k) and v is not None:
                setattr(self.treatment, k, v)
        return self

    def set_visual_language(self, **fields) -> "Brain":
        for k, v in fields.items():
            if hasattr(self.visual_language, k) and v is not None:
                setattr(self.visual_language, k, v)
        return self

    def set_brand(self, **fields) -> "Brain":
        for k, v in fields.items():
            if hasattr(self.brand, k) and v is not None:
                setattr(self.brand, k, v)
        return self

    def add_inspiration(self, ref: str, kind: str = "link", note: str = "") -> InspirationRef:
        item = InspirationRef(id=_sid("insp"), ref=ref, kind=kind, note=note)
        self.inspiration.append(item)
        return item

    def add_knowledge(self, source: str, kind: str = "brief",
                      content: str = "", note: str = "") -> KnowledgeDoc:
        doc = KnowledgeDoc(id=_sid("kn"), source=source, kind=kind,
                           content=content, note=note)
        self.knowledge.append(doc)
        return doc

    def set_series(self, **fields) -> "Brain":
        for k in ("series_title", "premise"):
            if k in fields and fields[k] is not None:
                setattr(self.bible, k, fields[k])
        return self

    def add_bible_character(self, name: str, **fields) -> BibleCharacter:
        existing = self.bible.characters.get(name)
        if existing:
            for k, v in fields.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
            return existing
        ch = BibleCharacter(name=name, **{k: v for k, v in fields.items() if v is not None})
        self.bible.characters[name] = ch
        return ch

    def add_episode(self, number: str, title: str = "", logline: str = "",
                    script_ref: str = "", status: str = "planned") -> Episode:
        for ep in self.bible.episodes:
            if ep.number == number:          # update in place
                ep.title = title or ep.title
                ep.logline = logline or ep.logline
                ep.script_ref = script_ref or ep.script_ref
                ep.status = status or ep.status
                return ep
        ep = Episode(number=number, title=title, logline=logline,
                     script_ref=script_ref, status=status)
        self.bible.episodes.append(ep)
        return ep

    def import_episode(self, number: str, title: str = "", content: str = "",
                       source: str = "", logline: str = "") -> dict:
        """
        Ingest an Episodo (or any) episode script. Handoff path: pass the script
        text as `content` (from a browser export) and/or a `source` path/url.
        Stores the script in the knowledge bank AND registers the episode in the
        series bible, linking the two.
        """
        doc = self.add_knowledge(
            source=source or f"episode {number}",
            kind="episode",
            content=content,
            note=f"Episode {number}: {title}".strip(),
        )
        ep = self.add_episode(number=number, title=title, logline=logline,
                              script_ref=doc.id, status="scripted")
        return {"episode": asdict(ep), "knowledge_id": doc.id}

    # ── readout for agents / get_brain tool ──────────────────────────────
    def to_summary(self) -> str:
        """Human-readable digest the Writer/Director can consume, or get_brain returns."""
        t, v, br, bib = self.treatment, self.visual_language, self.brand, self.bible
        L: list[str] = []
        L.append(f"# Brain — project: {self.project}")
        L.append(f"(updated {self.updated})\n")

        L.append("## Treatment")
        if any(asdict(t).values()):
            if t.title:         L.append(f"- Title: {t.title}")
            if t.logline:       L.append(f"- Logline: {t.logline}")
            if t.genre or t.tone or t.format:
                L.append(f"- Genre/Tone/Format: {t.genre} / {t.tone} / {t.format}")
            if t.target_length: L.append(f"- Target length: {t.target_length}")
            if t.audience:      L.append(f"- Audience: {t.audience}")
            if t.vision:        L.append(f"- Vision: {t.vision}")
            if t.notes:         L.append(f"- Notes: {t.notes}")
        else:
            L.append("- (not set)")

        L.append("\n## Visual language")
        if any(asdict(v).values()):
            if v.look:     L.append(f"- Look: {v.look}")
            if v.primary_reference: L.append(f"- Primary reference: {v.primary_reference}")
            if v.palette:  L.append(f"- Palette: {', '.join(map(str, v.palette))}")
            if v.lensing:  L.append(f"- Lensing: {v.lensing}")
            if v.lighting: L.append(f"- Lighting: {v.lighting}")
            if v.film_stock: L.append(f"- Film stock: {v.film_stock}")
            if v.grade:    L.append(f"- Grade: {v.grade}")
            if v.framing:  L.append(f"- Framing: {v.framing}")
            if v.avoid:    L.append(f"- Avoid: {', '.join(map(str, v.avoid))}")
            if v.references:L.append(f"- Refs: {'; '.join(map(str, v.references))}")
        else:
            L.append("- (not set)")

        L.append("\n## Brand")
        if any(asdict(br).values()):
            if br.name:       L.append(f"- Name: {br.name}")
            if br.voice:      L.append(f"- Voice: {br.voice}")
            if br.typography: L.append(f"- Typography: {br.typography}")
            if br.colors:     L.append(f"- Colors: {', '.join(map(str, br.colors))}")
            if br.rules:      L.append("- Rules: " + "; ".join(map(str, br.rules)))
        else:
            L.append("- (not set)")

        L.append(f"\n## Inspiration ({len(self.inspiration)})")
        for i in self.inspiration:
            note = f" — {i.note}" if i.note else ""
            L.append(f"- [{i.kind}] {i.ref}{note}  ({i.id})")
        if not self.inspiration:
            L.append("- (none)")

        L.append(f"\n## Knowledge bank ({len(self.knowledge)})")
        for k in self.knowledge:
            has = " [text]" if k.content else ""
            note = f" — {k.note}" if k.note else ""
            L.append(f"- [{k.kind}] {k.source}{has}{note}  ({k.id})")
        if not self.knowledge:
            L.append("- (none)")

        L.append("\n## Series bible")
        if bib.series_title or bib.premise or bib.characters or bib.episodes:
            if bib.series_title: L.append(f"- Series: {bib.series_title}")
            if bib.premise:      L.append(f"- Premise: {bib.premise}")
            if bib.characters:
                L.append(f"- Recurring characters ({len(bib.characters)}):")
                for n, c in bib.characters.items():
                    bits = ", ".join(x for x in [c.role, c.look, c.voice] if x)
                    L.append(f"    • {n}{(' — ' + bits) if bits else ''}")
            if bib.episodes:
                L.append(f"- Episodes ({len(bib.episodes)}):")
                for e in bib.episodes:
                    L.append(f"    • {e.number} {e.title} [{e.status}]"
                             f"{(' — ' + e.logline) if e.logline else ''}")
            if bib.rules:
                L.append("- Continuity rules: " + "; ".join(map(str, bib.rules)))
        else:
            L.append("- (not a series / not set)")

        return "\n".join(L)


# ──────────────────────────────────────────────────────────────────────────
# active-project pointer (so tools can default to the open project)
# ──────────────────────────────────────────────────────────────────────────
def set_active(project: str, brain_dir: Optional[str] = None) -> None:
    p = _brain_dir(brain_dir) / "_active.json"
    p.write_text(json.dumps({"active": project}), encoding="utf-8")


def get_active(brain_dir: Optional[str] = None) -> Optional[str]:
    p = _brain_dir(brain_dir) / "_active.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("active")
    except Exception:
        return None
