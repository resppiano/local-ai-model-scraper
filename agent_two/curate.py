"""
curate.py — Agent One Phase 5 (thin): variants + hero pick + scenes.
================================================================================
Deliberately THIN. The rich curation flow (eyeball 100 grids, crop, upscale)
lives in the separate manual workflow — that's an inherently human act. Here
autopilot only provides the hooks:

  • generate_variants(shot, n) — render N candidates for a shot (or, for handoff
                                 backends, emit one "make N variants" instruction)
  • list_candidates(shot)      — show the candidates awaiting a pick
  • mark_hero(shot, choice)    — a human's chosen frame becomes the shot's output
  • set_scene / list_scene     — light scene grouping (aligns with the manual
                                 workflow's scene-organized folders)

So the loop is: autopilot generates options → a human picks the hero → autopilot
continues. No auto-selection, no curation UI.

Decoupled: extends the Phase 3 ShotRegistry; renders via Phase 2 dispatch.
Stdlib only.
"""

from __future__ import annotations

from typing import Callable, Optional

try:
    from .editor import ShotRegistry
    from .dispatch import render_shot as _default_render
except ImportError:
    from editor import ShotRegistry
    from dispatch import render_shot as _default_render


def generate_variants(project: str, shot_id: str, n: int = 4,
                      render_fn: Optional[Callable] = None) -> dict:
    """Render N candidates for a shot. API backends render n times (different
    seeds in your renderer); a handoff backend returns ONE 'make N variants'
    instruction instead. Sets status='candidates' until a hero is picked."""
    reg = ShotRegistry.load(project)
    if shot_id not in reg.shots:
        return {"error": f"no such shot: {shot_id}"}
    rec = reg.shots[shot_id]
    fn = render_fn or _default_render
    n = max(1, min(int(n), 50))

    made = []
    for i in range(n):
        payload = dict(rec.spec)
        payload.update(rec.content or {})
        payload["shot_id"] = rec.id
        payload["variant"] = i + 1
        out = fn(payload, project=project)
        status = out.get("status")
        if status == "rendered":
            cid = f"{rec.id}_v{i+1}"
            rec.candidates.append({"id": cid, "output": out.get("result", ""),
                                   "backend": out["decision"]["backend"], "chosen": False})
            made.append(cid)
        elif status == "handoff":
            # handoff is manual anyway — one instruction for the whole batch
            packet = out
            packet["instructions"] = (
                f"Generate {n} variants of shot {rec.id} in {out.get('backend')}, "
                f"drop them in assets/candidates/{rec.id}/, then mark_hero with your pick.")
            reg.save()
            return {"shot_id": rec.id, "mode": "handoff", "n": n,
                    "handoff": packet, "candidates_made": 0}
        else:  # blocked
            reg.save()
            return {"shot_id": rec.id, "blocked": out.get("reason"), "candidates_made": len(made)}

    if rec.candidates:
        rec.status = "candidates"
    reg.save()
    return {"shot_id": rec.id, "mode": "api", "candidates_made": len(made),
            "candidates": made, "note": "pick one with mark_hero"}


def list_candidates(project: str, shot_id: str) -> dict:
    reg = ShotRegistry.load(project)
    if shot_id not in reg.shots:
        return {"error": f"no such shot: {shot_id}"}
    rec = reg.shots[shot_id]
    return {"shot_id": shot_id, "status": rec.status,
            "candidates": rec.candidates, "count": len(rec.candidates)}


def mark_hero(project: str, shot_id: str, choice: str, backend: str = "") -> dict:
    """A human's pick becomes the shot's output. `choice` = a candidate id, a
    1-based index, or a file path (e.g. a hero rendered in the manual workflow)."""
    reg = ShotRegistry.load(project)
    if shot_id not in reg.shots:
        return {"error": f"no such shot: {shot_id}"}
    rec = reg.shots[shot_id]

    picked = None
    # by candidate id
    for c in rec.candidates:
        if c["id"] == choice:
            picked = c
            break
    # by 1-based index
    if picked is None and str(choice).isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(rec.candidates):
            picked = rec.candidates[idx]
    # by path (or a brand-new hero from manual curation)
    if picked is None:
        picked = {"id": f"{shot_id}_hero", "output": choice,
                  "backend": backend or rec.backend, "chosen": False}
        rec.candidates.append(picked)

    for c in rec.candidates:
        c["chosen"] = (c is picked)
    reg.record_render(shot_id, backend=picked["backend"], output=picked["output"],
                      status="rendered")
    reg.save()
    return {"shot_id": shot_id, "hero": picked["output"], "backend": picked["backend"],
            "from_candidates": len(rec.candidates)}


def set_scene(project: str, shot_id: str, scene: str) -> dict:
    reg = ShotRegistry.load(project)
    if shot_id not in reg.shots:
        return {"error": f"no such shot: {shot_id}"}
    reg.shots[shot_id].scene = scene
    reg.save()
    return {"shot_id": shot_id, "scene": scene}


def list_scene(project: str, scene: str) -> dict:
    reg = ShotRegistry.load(project)
    shots = [r for r in reg._ordered() if r.scene == scene]
    return {"scene": scene, "count": len(shots),
            "shots": [{"id": r.id, "status": r.status, "order": r.order,
                       "candidates": len(r.candidates)} for r in shots]}
