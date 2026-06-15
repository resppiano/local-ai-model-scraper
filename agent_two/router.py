"""
router.py — Agent One / Agent Two Phase 2: automatic per-shot model selection.
================================================================================
The InVideo "you never see the model picker" behavior. Given a shot, the router
scores every enabled backend and picks the best one, honoring:
  • the project's render tier  (local | online | auto)
  • an optional budget         (skips online backends that would blow it)
  • hard constraints           (media type, clip length, frame control)

It returns a Decision dict (backend, mode, cost, reasoning, runner-up). The
Director calls `pick()` instead of hard-coding Kling; dispatch.py then either
calls the registered renderer (mode=api) or emits a handoff packet (mode=handoff).

Loads `model_registry.yaml` next to this file if present (and PyYAML is
installed); otherwise falls back to the embedded DEFAULT_REGISTRY below, so it
always runs. Stdlib + optional PyYAML.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

try:
    import yaml          # optional
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False


# ──────────────────────────────────────────────────────────────────────────
# embedded fallback (mirrors model_registry.yaml)
# ──────────────────────────────────────────────────────────────────────────
DEFAULT_REGISTRY: list[dict] = [
    {"name": "comfyui_wan", "enabled": True, "tier": "local", "mode": "api",
     "media": "video", "strengths": ["photoreal", "stylized", "action", "broll", "hero"],
     "max_clip_seconds": 5, "frame_control": True, "cost_per_second": 0.0, "priority": 50},
    {"name": "ltx_video", "enabled": True, "tier": "local", "mode": "api",
     "media": "video", "strengths": ["fast", "draft", "broll", "action"],
     "max_clip_seconds": 5, "frame_control": False, "cost_per_second": 0.0, "priority": 40},
    {"name": "comfyui_image", "enabled": True, "tier": "local", "mode": "api",
     "media": "image", "strengths": ["image", "keyframe", "still", "reference"],
     "max_clip_seconds": 0, "frame_control": False, "cost_per_second": 0.0, "priority": 60},
    {"name": "higgsfield", "enabled": True, "tier": "online", "mode": "handoff",
     "media": "video", "strengths": ["cinematic_camera", "camera_move", "hero"],
     "max_clip_seconds": 8, "frame_control": False, "cost_per_second": 0.5, "priority": 30},
    {"name": "martini", "enabled": True, "tier": "online", "mode": "handoff",
     "media": "video", "strengths": ["hero", "photoreal", "cinematic_camera", "dialogue", "multi_model"],
     "max_clip_seconds": 10, "frame_control": True, "cost_per_second": 1.0, "priority": 35},
    {"name": "kling", "enabled": False, "tier": "online", "mode": "api",
     "media": "video", "strengths": ["photoreal", "action", "hero", "cinematic_camera"],
     "max_clip_seconds": 10, "frame_control": True, "cost_per_second": 0.6, "priority": 45},
    {"name": "heygen", "enabled": False, "tier": "online", "mode": "api",
     "media": "video", "strengths": ["lipsync", "talking_head"],
     "max_clip_seconds": 30, "frame_control": False, "cost_per_second": 0.4, "priority": 46},
    {"name": "omnihuman", "enabled": False, "tier": "online", "mode": "api",
     "media": "video", "strengths": ["lipsync", "talking_head", "photoreal"],
     "max_clip_seconds": 15, "frame_control": False, "cost_per_second": 0.5, "priority": 44},
]


def load_registry(path: Optional[str] = None) -> list[dict]:
    """Enabled backends from YAML (if available) else the embedded defaults."""
    p = Path(path) if path else Path(__file__).with_name("model_registry.yaml")
    backends = DEFAULT_REGISTRY
    if _HAVE_YAML and p.exists():
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict) and data.get("backends"):
                backends = data["backends"]
        except Exception:
            backends = DEFAULT_REGISTRY
    return [b for b in backends if b.get("enabled", True)]


# ──────────────────────────────────────────────────────────────────────────
# render config (tier + budget) persisted per project, in the brain dir
# ──────────────────────────────────────────────────────────────────────────
def _brain_dir() -> Path:
    d = os.environ.get("AGENT_ONE_BRAIN_DIR", "agentone_brain")
    p = Path(d).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _render_cfg_path() -> Path:
    return _brain_dir() / "_render.json"


def get_render_config(project: str) -> dict:
    p = _render_cfg_path()
    allcfg = {}
    if p.exists():
        try:
            allcfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            allcfg = {}
    return allcfg.get(project, {"tier": "auto", "budget": None})


_UNSET = object()


def set_render_config(project: str, tier: Optional[str] = None,
                      budget=_UNSET) -> dict:
    p = _render_cfg_path()
    allcfg = {}
    if p.exists():
        try:
            allcfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            allcfg = {}
    cur = allcfg.get(project, {"tier": "auto", "budget": None})
    if tier is not None:
        if tier not in ("local", "online", "auto"):
            raise ValueError("tier must be local | online | auto")
        cur["tier"] = tier
    if budget is not _UNSET:            # None now means "clear the budget"
        cur["budget"] = budget
    allcfg[project] = cur
    p.write_text(json.dumps(allcfg, indent=2), encoding="utf-8")
    return cur


# ──────────────────────────────────────────────────────────────────────────
# shot normalization
# ──────────────────────────────────────────────────────────────────────────
def normalize_shot(shot: dict) -> dict:
    """Map a loose shot dict onto the fields the router scores against.
    Unknown fields are ignored; everything has a sane default."""
    s = shot or {}
    still = bool(s.get("still") or s.get("is_keyframe") or s.get("keyframe"))
    subject = (s.get("subject") or "").lower()
    return {
        "media": "image" if still else "video",
        "needs_lipsync": bool(s.get("needs_lipsync") or s.get("dialogue") or subject == "talking_head"),
        "subject": subject,
        "motion": (s.get("motion") or "medium").lower(),
        "style": (s.get("style") or "photoreal").lower(),
        "camera_move": (s.get("camera_move") or "simple").lower(),
        "duration_seconds": float(s.get("duration_seconds") or s.get("duration") or 5),
        "fidelity": (s.get("fidelity") or "hero").lower(),
        "frame_control_required": bool(s.get("frame_control_required") or s.get("continuity")),
    }


def desired_tags(spec: dict) -> set:
    tags: set = set()
    if spec["media"] == "image":
        tags |= {"image", "keyframe", "still"}
        return tags
    if spec["needs_lipsync"]:
        tags |= {"lipsync", "talking_head", "dialogue"}
    if spec["subject"]:
        tags.add(spec["subject"])
    if spec["motion"] == "high":
        tags |= {"fast", "action"}
    tags.add(spec["style"])                          # photoreal | stylized | animated
    if spec["camera_move"] in ("cinematic", "complex", "complex_cinematic"):
        tags |= {"cinematic_camera", "camera_move", "hero"}
    tags.add(spec["fidelity"])                       # hero | draft
    return tags


# ──────────────────────────────────────────────────────────────────────────
# scoring
# ──────────────────────────────────────────────────────────────────────────
def _score(spec: dict, backend: dict, tier_pref: str,
           budget: Optional[float]) -> dict:
    reasons: list[str] = []
    media = spec["media"]
    dur = spec["duration_seconds"]
    est_cost = float(backend.get("cost_per_second", 0.0)) * (0 if media == "image" else dur)

    # ── hard filters ──
    if backend.get("media") != media:
        return {"eligible": False, "why": f"media {backend.get('media')}≠{media}"}
    if spec["needs_lipsync"]:
        caps = set(backend.get("strengths", []))
        if not (caps & {"lipsync", "talking_head", "dialogue"}):
            return {"eligible": False, "why": "no lip-sync/dialogue capability"}
    if media == "video" and backend.get("max_clip_seconds", 0) < dur:
        return {"eligible": False,
                "why": f"max {backend.get('max_clip_seconds')}s < {dur}s"}
    if spec["frame_control_required"] and not backend.get("frame_control", False):
        return {"eligible": False, "why": "no frame control for continuity shot"}
    if tier_pref == "local" and backend.get("tier") != "local":
        return {"eligible": False, "why": "tier=local excludes non-local"}
    if budget is not None and est_cost > budget:
        return {"eligible": False, "why": f"est {est_cost:.2f} > budget {budget:.2f}"}

    # ── soft score ──
    want = desired_tags(spec)
    have = set(backend.get("strengths", []))
    overlap = want & have
    score = 3.0 * len(overlap)
    if overlap:
        reasons.append(f"matches {', '.join(sorted(overlap))}")

    if spec["needs_lipsync"] and (have & {"lipsync", "talking_head"}):
        score += 3.0
        reasons.append("dedicated lip-sync")

    is_local = backend.get("tier") == "local"
    if spec["fidelity"] == "draft":
        if is_local:
            score += 4.0; reasons.append("local favored for draft")
        score -= est_cost * 2.0
    else:  # hero
        if "hero" in have:
            score += 2.5; reasons.append("hero-grade")
        if tier_pref == "auto":
            score -= est_cost * 0.5
        elif tier_pref == "online" and not is_local:
            score += 2.0; reasons.append("tier=online favored")

    if tier_pref == "auto" and is_local:
        score += 1.0  # gentle local-first nudge under auto

    score += backend.get("priority", 0) / 100.0  # tiny tiebreaker
    return {"eligible": True, "score": round(score, 3),
            "est_cost": round(est_cost, 3), "reasons": reasons}


# ──────────────────────────────────────────────────────────────────────────
# the pick
# ──────────────────────────────────────────────────────────────────────────
def pick(shot: dict, project: Optional[str] = None,
         tier: Optional[str] = None, budget: Optional[float] = None,
         registry: Optional[list[dict]] = None) -> dict:
    """Choose a backend for one shot. Returns a Decision dict."""
    spec = normalize_shot(shot)
    reg = registry if registry is not None else load_registry()

    # resolve tier/budget: explicit arg > project config > defaults
    cfg = get_render_config(project) if project else {"tier": "auto", "budget": None}
    tier_pref = tier or cfg.get("tier", "auto")
    bud = budget if budget is not None else cfg.get("budget")

    scored = []
    rejected = []
    for b in reg:
        r = _score(spec, b, tier_pref, bud)
        if r.get("eligible"):
            scored.append((b, r))
        else:
            rejected.append((b["name"], r.get("why", "")))

    if not scored:
        return {
            "backend": None, "eligible": False, "tier_pref": tier_pref,
            "spec": spec, "reasoning": "No eligible backend.",
            "rejected": rejected,
            "suggestion": _suggest(spec, tier_pref),
        }

    scored.sort(key=lambda x: (x[1]["score"], x[0].get("priority", 0)), reverse=True)
    best_b, best_r = scored[0]
    runner = scored[1][0]["name"] if len(scored) > 1 else None

    return {
        "backend": best_b["name"],
        "tier": best_b.get("tier"),
        "mode": best_b.get("mode", "api"),
        "media": best_b.get("media"),
        "handoff": best_b.get("mode") == "handoff",
        "estimated_cost": best_r["est_cost"],
        "score": best_r["score"],
        "tier_pref": tier_pref,
        "reasoning": "; ".join(best_r["reasons"]) or "best available",
        "runner_up": runner,
        "spec": spec,
        "eligible": True,
    }


def _suggest(spec: dict, tier_pref: str) -> str:
    if spec["needs_lipsync"]:
        return "Talking-head shot: enable heygen/omnihuman, or set tier=online for martini dialogue."
    if tier_pref == "local":
        return "Nothing local fits. Set tier=auto/online, or raise max_clip_seconds."
    return "Loosen constraints (duration/frame control) or enable more backends."


# ──────────────────────────────────────────────────────────────────────────
# preview / listing (for the MCP tools)
# ──────────────────────────────────────────────────────────────────────────
def route_preview_text(shot: dict, project: Optional[str] = None) -> str:
    d = pick(shot, project=project)
    if not d.get("eligible"):
        lines = ["Route preview → NO BACKEND", f"  reason: {d['reasoning']}",
                 f"  suggestion: {d['suggestion']}"]
        if d.get("rejected"):
            lines.append("  rejected:")
            lines += [f"    - {n}: {w}" for n, w in d["rejected"]]
        return "\n".join(lines)
    return (
        f"Route preview → {d['backend']}  [{d['tier']}/{d['mode']}]\n"
        f"  tier pref : {d['tier_pref']}\n"
        f"  why       : {d['reasoning']}\n"
        f"  est cost  : {d['estimated_cost']}\n"
        f"  runner-up : {d['runner_up']}\n"
        + ("  NOTE: handoff — render in that tool and drop the file back.\n"
           if d["handoff"] else "")
    )


def list_models_text(registry: Optional[list[dict]] = None) -> str:
    reg = registry if registry is not None else load_registry()
    lines = [f"Enabled backends ({len(reg)}):"]
    for b in sorted(reg, key=lambda x: (x.get("tier", ""), -x.get("priority", 0))):
        lines.append(
            f"  • {b['name']:<14} {b.get('tier'):<7} {b.get('mode'):<7} "
            f"{b.get('media'):<6} ≤{b.get('max_clip_seconds')}s  "
            f"[{', '.join(b.get('strengths', []))}]"
        )
    return "\n".join(lines)
