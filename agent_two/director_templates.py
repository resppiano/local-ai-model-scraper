"""
director_templates.py — structured prompt builders (harvested + adapted).
================================================================================
Encodes the three Theoretically Media prompt formats as reusable functions the
Director can call, alongside the existing Kling two-prompt method:

  • character_ref_grid(...)  → Nano-Banana-style character reference grid
  • scene_grid_2x2(...)      → 2x2 cinematic still grid for a scene
  • seedance_video(...)      → Seedance 2.0 structured video prompt

Each fills the proven template and runs the result through filtersafe.safe_text,
so prompts ship filter-safe by default. Missing fields render as a clear
[FIELD] marker so nothing silently drops.

Design principle baked in (from the source): let reference images carry
appearance; keep text on action + camera. The Seedance builder enforces 2-3
shots per clip and the @-tag convention.

Stdlib only (imports filtersafe from the same package).
"""

from __future__ import annotations

from typing import Optional

try:
    from .filtersafe import safe_text
    from .brain import Brain
except ImportError:
    from filtersafe import safe_text
    try:
        from brain import Brain
    except ImportError:
        Brain = None


_IMG_FOOTER = "Do not write text on the image. No subtitles. No captions."
_GROUNDING = ("The imagery must feel grounded, tactile, and physically real — like "
              "35mm film stock with practical lighting. No animation style, no "
              "painterly rendering, no digital glow. Real weight, real presence.")


def _grounding(avoid=None) -> str:
    """Base grounding line + any project-specific negatives from the brain."""
    if avoid:
        terms = ", ".join(str(a) for a in avoid)
        return f"{_GROUNDING} Avoid: {terms}."
    return _GROUNDING


def style_from_brain(project: str) -> dict:
    """Pull style fields from a project's brain so a builder can be **splatted:
    DT.character_ref_grid(**style_from_brain(p), character_names=..., ...)."""
    if Brain is None:
        return {}
    b = Brain.load(project)
    v, t = b.visual_language, b.treatment
    tone_bits = [x for x in (v.film_stock, v.grade,
                             (", ".join(v.palette) if v.palette else ""),
                             v.primary_reference) if x]
    return {
        "genre": t.genre or "",
        "lighting": v.lighting or "",
        "tone": "; ".join(tone_bits),
        "avoid": list(v.avoid),
    }


def _f(v, name: str) -> str:
    return str(v) if v not in (None, "") else f"[{name}]"


def character_ref_grid(avoid=None, genre: str = "", character_names: str = "",
                       location_brief: str = "", ref_tags: str = "",
                       scene_environment: str = "", character_details: str = "",
                       camera_notes: str = "", lighting: str = "", tone: str = "",
                       footage_type: str = "documentary footage",
                       environment_type: str = "a real location",
                       consistent_backdrop: str = "consistent backdrop, not the focus",
                       swaps: Optional[dict] = None) -> str:
    """Character Reference Grid prompt (Template 1). Generate ~30 for 120 picks."""
    body = f"""Generate a photorealistic cinematic 2x2 grid of character reference still frames from a {_f(genre,'GENRE')} film, featuring {_f(character_names,'CHARACTER_NAMES')} inside {_f(location_brief,'LOCATION_BRIEF')}.

{_grounding(avoid)} Everything should feel like real {footage_type} captured inside {environment_type}.

This is a CHARACTER REFERENCE GRID designed for consistent character creation. The environment must remain a {consistent_backdrop}.

Remember to use {_f(ref_tags,'REF_TAGS')} as references.

Each frame represents a different angle or distance, capturing the characters in various poses and expressions within the environment.

{_IMG_FOOTER}

---
SCENE & ENVIRONMENT
{_f(scene_environment,'SCENE_ENVIRONMENT')}
---
CHARACTERS
{_f(character_details,'CHARACTER_DETAILS')}
---
CAMERA & COMPOSITION
{_f(camera_notes,'CAMERA_NOTES')}
---
LIGHTING & ATMOSPHERE
{_f(lighting,'LIGHTING')}
---
TONE & FINISH
{_f(tone,'TONE')}"""
    return safe_text(body, swaps)["text"]


def scene_grid_2x2(avoid=None, genre: str = "", scene_summary: str = "", ref_tags: str = "",
                   action_summary: str = "", scene_environment: str = "",
                   character_details: str = "", action_continuity: str = "",
                   camera_composition: str = "", lighting_atmosphere: str = "",
                   tone_finish: str = "", swaps: Optional[dict] = None) -> str:
    """2x2 Scene Grid prompt (Template 2). Generate ~100 (=400 imgs) per scene."""
    body = f"""Generate a photorealistic cinematic 2x2 grid of still frames from a {_f(genre,'GENRE')} film, depicting {_f(scene_summary,'SCENE_SUMMARY')}.

{_grounding(avoid)}

Remember to use {_f(ref_tags,'REF_TAGS')} as references.

Each frame represents a different angle or distance from the same continuous moment, capturing {_f(action_summary,'ACTION_SUMMARY')}.

{_IMG_FOOTER}

---
SCENE & ENVIRONMENT
{_f(scene_environment,'SCENE_ENVIRONMENT')}
---
CHARACTERS
{_f(character_details,'CHARACTER_DETAILS — include @ tags')}
---
ACTION & CONTINUITY
{_f(action_continuity,'ACTION_CONTINUITY')}
(All four frames are fragments of ONE continuous moment.)
---
CAMERA & COMPOSITION
{_f(camera_composition,'CAMERA_COMPOSITION')}
---
LIGHTING & ATMOSPHERE
{_f(lighting_atmosphere,'LIGHTING_ATMOSPHERE')}
---
TONE & FINISH
{_f(tone_finish,'TONE_FINISH')}"""
    return safe_text(body, swaps)["text"]


def seedance_video(style: str = "", duration: int = 10,
                   camera_behavior: str = "", characters: Optional[list] = None,
                   shots: Optional[list] = None, swaps: Optional[dict] = None) -> str:
    """
    Seedance 2.0 structured video prompt (Template 3).
    characters: [{"name","tag","desc"}]   (desc kept brief — refs carry appearance)
    shots:      [{"name","camera","action","dialogue"(opt)}]   (2-3 per clip)
    """
    duration = 10 if duration not in (5, 10) else duration
    chars = characters or []
    shots = (shots or [])[:3]   # enforce 2-3 shots per clip

    char_lines = "\n".join(
        f"{_f(c.get('name'),'NAME')} ({c.get('tag','@')}): {_f(c.get('desc'),'BRIEF_DESC')}"
        for c in chars) or "[CHARACTERS]"

    shot_lines = []
    for i, s in enumerate(shots, 1):
        line = (f"Shot {i} ({_f(s.get('name'),'SHOT_NAME')}): "
                f"{_f(s.get('camera'),'CAMERA_TYPE')}. {_f(s.get('action'),'ACTION')}")
        if s.get("dialogue"):
            line += f' "{s["dialogue"]}"'
        shot_lines.append(line)
    shot_block = "\n\n".join(shot_lines) or "[SHOTS]"

    body = (f"【Style】 {_f(style,'VISUAL_STYLE')}. {_f(camera_behavior,'CAMERA_BEHAVIOR')} "
            f"【Duration】 {duration} seconds\n\n"
            f"Characters:\n{char_lines}\n\n"
            f"Shot Actions:\n\n{shot_block}")
    return safe_text(body, swaps)["text"]
