"""
reviewer.py — Agent One / Agent Two Phase 4: built-in QA / review agent.
================================================================================
Grades every shot against:
  1. the typed RULES (rules.py)                — deterministic, text-based
  2. CONTINUITY / staleness (Phase 3 registry) — is the shot out of date vs the
                                                  current brain? rendered at all?
  3. VISION drift (wardrobe/palette/likeness)  — PLUGGABLE: register a vision
                                                  checker; skipped if none wired.

For each shot it returns pass | warn | block with findings. Blocked or stale
shots can be re-rendered through the existing Phase 3 `rerender`.

AUTO-FIX: rewriting a prompt needs an LLM, so the Reviewer doesn't fake it. If a
`fixer` callable is registered it's used; otherwise the structured findings are
ESCALATED to Hermes, who can call `edit` / `rerender`.

Decoupled: reads brain.py, rules.py, editor.py; writes nothing to base files.
Stdlib only (+ whatever your registered vision checker needs).
"""

from __future__ import annotations

from typing import Callable, Optional

try:
    from .brain import Brain
    from .rules import RuleSet
    from .editor import ShotRegistry, dep_key
except ImportError:
    from brain import Brain
    from rules import RuleSet
    from editor import ShotRegistry, dep_key


# ── pluggable hooks (wire to your vision model / LLM) ──────────────────────
_VISION_CHECKER: Optional[Callable] = None
_FIXER: Optional[Callable] = None


def register_vision_checker(fn: Callable) -> None:
    """fn(rec, brain) -> list[finding dicts]. Inspect the rendered output for
    wardrobe/palette/likeness drift. Each finding: {check, severity, message}."""
    global _VISION_CHECKER
    _VISION_CHECKER = fn


def register_fixer(fn: Callable) -> None:
    """fn(rec, findings, brain) -> dict|None. Return updated content to apply,
    or None to escalate instead."""
    global _FIXER
    _FIXER = fn


# ── text assembly ──────────────────────────────────────────────────────────
def _shot_text(rec, brain: Brain) -> str:
    parts = []
    c = rec.content or {}
    parts.append(str(c.get("prompt", "")))
    parts.append(str(c.get("dialogue", "")))
    parts.append(str((rec.spec or {}).get("subject", "")))
    # include the bible look/description of any character this shot depends on,
    # so forbid/require rules can catch wardrobe conflicts in the canon too
    for dep in rec.depends_on:
        if dep.startswith("character:"):
            name = dep.split(":", 1)[1]
            ch = brain.bible.characters.get(name)
            if ch:
                parts.append(f"{ch.look} {ch.description}")
    return " ".join(parts).lower()


# ── core review ────────────────────────────────────────────────────────────
def review_shot(rec, brain: Brain, ruleset: RuleSet, reg: ShotRegistry) -> dict:
    findings: list[dict] = []

    # 1. rules
    text = _shot_text(rec, brain)
    for rule in ruleset.applicable(rec):
        f = rule.check(text)
        if f:
            findings.append(f)

    # 2. continuity / staleness
    if rec.status == "pending":
        findings.append({"check": "render", "severity": "warn",
                         "message": "shot has never been rendered"})
    elif reg.is_stale(rec):
        findings.append({"check": "continuity", "severity": "warn",
                         "message": "out of date vs current brain (rerender to update)"})

    # 3. vision (pluggable)
    if _VISION_CHECKER is not None and rec.status in ("rendered",):
        try:
            for f in (_VISION_CHECKER(rec, brain) or []):
                findings.append(f)
        except Exception as e:
            findings.append({"check": "vision", "severity": "warn",
                             "message": f"vision checker error: {e}"})
    elif _VISION_CHECKER is None:
        findings.append({"check": "vision", "severity": "info",
                         "message": "visual QA skipped (no vision checker registered)"})

    sev = {f.get("severity") for f in findings}
    status = "block" if "block" in sev else ("warn" if "warn" in sev else "pass")
    return {"shot_id": rec.id, "status": status,
            "needs_rerender": status == "block" or reg.is_stale(rec) or rec.status == "pending",
            "findings": findings}


def review_project(project: str) -> dict:
    brain = Brain.load(project)
    ruleset = RuleSet.load(project)
    reg = ShotRegistry.load(project)
    reviews = [review_shot(r, brain, ruleset, reg) for r in reg._ordered()]
    counts = {"pass": 0, "warn": 0, "block": 0}
    for rv in reviews:
        counts[rv["status"]] += 1
    return {
        "project": project,
        "total": len(reviews),
        "counts": counts,
        "needs_rerender": [rv["shot_id"] for rv in reviews if rv["needs_rerender"]],
        "reviews": reviews,
        "vision_enabled": _VISION_CHECKER is not None,
    }


def review_and_fix(project: str, apply: bool = False) -> dict:
    """For block/warn shots: if a fixer is registered, get updated content and
    (optionally) apply it; otherwise escalate the findings to Hermes."""
    rep = review_project(project)
    brain = Brain.load(project)
    reg = ShotRegistry.load(project)
    fixed, escalated = [], []
    for rv in rep["reviews"]:
        if rv["status"] == "pass":
            continue
        rec = reg.shots[rv["shot_id"]]
        if _FIXER is not None:
            new_content = _FIXER(rec, rv["findings"], brain)
            if new_content:
                if apply:
                    reg.upsert_shot(rec.id, spec=rec.spec, content=new_content,
                                    depends_on=rec.depends_on, order=rec.order)
                fixed.append({"shot_id": rec.id, "new_content": new_content})
                continue
        escalated.append({"shot_id": rec.id, "status": rv["status"],
                          "findings": rv["findings"]})
    if apply and fixed:
        reg.save()
    return {"fixed": fixed, "escalated": escalated,
            "rerender_after_fix": [f["shot_id"] for f in fixed]}


# ── formatting ─────────────────────────────────────────────────────────────
def review_report_text(project: str) -> str:
    rep = review_project(project)
    c = rep["counts"]
    L = [f"Review — {project}",
         f"  {rep['total']} shots: {c['pass']} pass, {c['warn']} warn, {c['block']} block"
         f"  (vision {'on' if rep['vision_enabled'] else 'OFF'})"]
    for rv in rep["reviews"]:
        if rv["status"] == "pass" and not rv["findings"]:
            L.append(f"  ✓ {rv['shot_id']}: pass")
            continue
        tag = {"pass": "✓", "warn": "!", "block": "✗"}[rv["status"]]
        L.append(f"  {tag} {rv['shot_id']}: {rv['status'].upper()}")
        for f in rv["findings"]:
            if f.get("severity") == "info":
                continue
            L.append(f"      - [{f.get('severity')}] {f.get('message')}")
    if rep["needs_rerender"]:
        L.append(f"  → rerender: {', '.join(rep['needs_rerender'])}")
    return "\n".join(L)
