"""
rules.py — Agent One / Agent Two Phase 4: the typed rules engine.
================================================================================
Formalizes the old free-text `add_rule` into structured, enforceable rules that
the Reviewer checks every shot against.

A rule has:
  scope    : global | character | shot_type
  target   : '' (global) | a character name | a shot subject (e.g. 'establishing')
  kind     : forbid | require
  terms    : keywords/phrases (forbid = must NOT appear; require = must appear)
  severity : block | warn
  description : human text

Examples:
  forbid  global      ['spaceship','laser']     block   "no sci-fi elements"
  require shot_type:establishing ['lower third'] warn    "lower-thirds present"
  forbid  character:Gladiator ['gun','rifle']    block   "traditional weapons only"

Persists per project as <brain_dir>/<project>.rules.json. Stdlib only.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    from .brain import _safe_name
    from .editor import dep_key
except ImportError:
    from brain import _safe_name
    from editor import dep_key


def _brain_dir() -> Path:
    d = os.environ.get("AGENT_ONE_BRAIN_DIR", "agentone_brain")
    p = Path(d).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class Rule:
    id: str
    scope: str = "global"          # global | character | shot_type
    target: str = ""               # character name or shot subject; '' for global
    kind: str = "forbid"           # forbid | require
    terms: list = field(default_factory=list)
    severity: str = "warn"         # block | warn
    description: str = ""

    def applies_to(self, rec) -> bool:
        if self.scope == "global":
            return True
        if self.scope == "character":
            return dep_key("character", self.target) in getattr(rec, "depends_on", [])
        if self.scope == "shot_type":
            return (getattr(rec, "spec", {}) or {}).get("subject", "").lower() == self.target.lower()
        return False

    def check(self, text: str) -> Optional[dict]:
        """Return a finding dict if violated, else None. `text` is the shot's
        combined lowercased text (prompt + dialogue + subject + bible looks)."""
        terms = [t.lower() for t in self.terms if t]
        if not terms:
            return None
        present = [t for t in terms if t in text]
        violated = False
        if self.kind == "forbid" and present:
            violated = True
            msg = f"forbidden term(s) present: {', '.join(present)}"
        elif self.kind == "require" and not present:
            violated = True
            msg = f"required term(s) missing: {', '.join(terms)}"
        if not violated:
            return None
        return {
            "rule_id": self.id, "severity": self.severity,
            "scope": self.scope, "target": self.target,
            "message": f"{self.description or self.kind}: {msg}".strip(),
        }


@dataclass
class RuleSet:
    project: str
    rules: list = field(default_factory=list)   # list[Rule]

    @staticmethod
    def path_for(project: str) -> Path:
        return _brain_dir() / f"{_safe_name(project)}.rules.json"

    @classmethod
    def load(cls, project: str) -> "RuleSet":
        p = cls.path_for(project)
        if not p.exists():
            return cls(project=project)
        d = json.loads(p.read_text(encoding="utf-8"))
        rs = cls(project=project)
        rs.rules = [Rule(**r) for r in d.get("rules", [])]
        return rs

    def save(self) -> Path:
        p = RuleSet.path_for(self.project)
        p.write_text(json.dumps(
            {"project": self.project, "rules": [asdict(r) for r in self.rules]},
            indent=2), encoding="utf-8")
        return p

    def add(self, scope: str = "global", target: str = "", kind: str = "forbid",
            terms: Optional[list] = None, severity: str = "warn",
            description: str = "") -> Rule:
        if scope not in ("global", "character", "shot_type"):
            raise ValueError("scope must be global | character | shot_type")
        if kind not in ("forbid", "require"):
            raise ValueError("kind must be forbid | require")
        if severity not in ("block", "warn"):
            raise ValueError("severity must be block | warn")
        r = Rule(id=f"rule_{uuid.uuid4().hex[:8]}", scope=scope, target=target,
                 kind=kind, terms=terms or [], severity=severity, description=description)
        self.rules.append(r)
        return r

    def remove(self, rule_id: str) -> bool:
        n = len(self.rules)
        self.rules = [r for r in self.rules if r.id != rule_id]
        return len(self.rules) < n

    def applicable(self, rec) -> list:
        return [r for r in self.rules if r.applies_to(rec)]

    def to_summary(self) -> str:
        if not self.rules:
            return f"No rules for '{self.project}'."
        L = [f"Rules for '{self.project}' ({len(self.rules)}):"]
        for r in self.rules:
            scope = r.scope + (f":{r.target}" if r.target else "")
            L.append(f"  {r.id}  [{r.severity}] {r.kind} {scope}  "
                     f"terms={r.terms}  — {r.description}")
        return "\n".join(L)
