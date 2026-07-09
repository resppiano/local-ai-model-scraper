"""
Prompt Builder Service
======================
Builds structured LTX 2.3 prompts for panels by combining:
  - Panel description
  - Camera direction + panel type
  - Scene context (heading, location, time_of_day)
  - Character descriptions + reference images
  - Project vision / tone

Two paths:
  1. generate_panel_ltx_prompt() — calls the LLM (Super Prompt Agent)
  2. build_panel_prompt_fallback() — template-based without LLM
"""

import json
from typing import List, Optional, Dict, Any

from .ltx_prompt_agent import LTXPromptAgent

# Singleton agent (lazy-loaded)
_agent: Optional[LTXPromptAgent] = None


def _get_agent() -> LTXPromptAgent:
    global _agent
    if _agent is None:
        _agent = LTXPromptAgent()
    return _agent


def _camera_to_natural_language(direction: str) -> str:
    mapping = {
        "pan_left": "camera slowly pans left, revealing the scene horizontally",
        "pan_right": "camera slowly pans right, following the action",
        "dolly_in": "camera smoothly pushes in toward the subject, intensifying the moment",
        "dolly_out": "camera smoothly pulls back, revealing the larger context",
        "track_left": "camera tracks left alongside the subject, following their movement",
        "track_right": "camera tracks right alongside the subject, maintaining distance",
        "crane_up": "camera rises up, revealing the full scale of the environment",
        "crane_down": "camera lowers, bringing us into the scene from above",
        "tilt_up": "camera tilts up, revealing height and scale",
        "tilt_down": "camera tilts down, looking down on the subject",
        "static": "static shot, camera is perfectly still, locked off on tripod",
        "handheld": "handheld camera, slight natural shake, documentary feel",
        "steadicam": "smooth gimbal-mounted shot, following the subject fluidly",
        "dolly_zoom": "dolly zoom effect — camera pulls back while zooming in, background warps",
        "whip_pan": "fast whip pan, quick disorienting camera movement",
        "aerial": "aerial drone shot, high above, sweeping view",
    }
    return mapping.get(direction, "static shot, camera is still")


# ── Main entry point (LLM-powered) ───────────────────────────────────────

def generate_panel_ltx_prompt(
    description: str,
    camera_direction: str = "static",
    panel_type: str = "wide",
    scene_heading: Optional[str] = None,
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    scene_summary: Optional[str] = None,
    character_descriptions: Optional[List[Dict[str, Any]]] = None,
    project_vision: Optional[str] = None,
    project_tone: Optional[str] = None,
    mode: str = "image-to-video",
    panel_number: Optional[int] = None,
    total_panels: Optional[int] = None,
    previous_panel_prompt: Optional[str] = None,
) -> str:
    """
    Generate a structured LTX 2.3 prompt using the Super Prompt Agent LLM.

    Args:
        description: The panel's description text.
        camera_direction: pan_left/pan_right/dolly_in/dolly_out/static.
        panel_type: wide/medium/closeup/insert.
        scene_heading: Scene heading text.
        location: Scene location.
        time_of_day: Time of day.
        scene_summary: Scene summary from script breakdown.
        character_descriptions: List of dicts with name/description/reference_image_url.
        project_vision: Project's visual style.
        project_tone: Project's tonal direction.
        mode: image-to-video / text-to-video / retake.

    Returns:
        Structured LTX 2.3 prompt string.
    """
    agent = _get_agent()
    return agent.generate_from_panel(
        panel_description=description,
        camera_direction=camera_direction,
        panel_type=panel_type,
        scene_heading=scene_heading,
        location=location,
        time_of_day=time_of_day,
        scene_summary=scene_summary,
        characters=character_descriptions,
        project_vision=project_vision,
        project_tone=project_tone,
        mode=mode,
        panel_number=panel_number,
        total_panels=total_panels,
        previous_panel_prompt=previous_panel_prompt,
    )


# ── Fallback (no LLM) ────────────────────────────────────────────────────

def build_panel_prompt_fallback(
    description: str,
    camera_direction: str = "static",
    panel_type: str = "wide",
    scene_heading: Optional[str] = None,
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    character_descriptions: Optional[List[str]] = None,
    project_vision: Optional[str] = None,
    project_tone: Optional[str] = None,
) -> str:
    """
    Build a structured LTX prompt without an LLM call (template-based).
    Used when the API key is unavailable or the LLM call fails.
    """
    parts: List[str] = []

    # Project context
    if project_vision:
        parts.append(f"Style: {project_vision}")
    if project_tone:
        parts.append(f"Tone: {project_tone}")

    # Scene context
    scene_parts: List[str] = []
    if scene_heading:
        scene_parts.append(scene_heading)
    if location:
        scene_parts.append(f"Location: {location}")
    if time_of_day:
        scene_parts.append(f"Time: {time_of_day}")
    if scene_parts:
        parts.append("Scene: " + " | ".join(scene_parts))

    # Characters
    if character_descriptions:
        chars = "; ".join(c for c in character_descriptions if c)
        if chars:
            parts.append(f"Characters: {chars}")

    # Camera
    camera_text = _camera_to_natural_language(camera_direction)
    parts.append(f"Camera: {camera_text}")

    # Panel description
    parts.append(f"Description: {description}")

    # Quality tags
    parts.append(
        "cinematic, high quality, detailed, professional lighting, "
        "photorealistic, 8K, film grain, anamorphic"
    )

    return "\n".join(parts)


# ── DB convenience ────────────────────────────────────────────────────────

async def generate_ltx_prompt_from_panel_db(
    panel_description: str,
    camera_direction: str,
    panel_type: str,
    scene_heading: Optional[str] = None,
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    scene_summary: Optional[str] = None,
    assigned_character_ids_str: Optional[str] = None,
    project_vision: Optional[str] = None,
    project_tone: Optional[str] = None,
    character_lookup_func=None,
    mode: str = "image-to-video",
    panel_number: Optional[int] = None,
    total_panels: Optional[int] = None,
    previous_panel_prompt: Optional[str] = None,
) -> str:
    """
    Convenience wrapper for DB-driven calls.
    Calls the LLM path by default; falls back to template on failure.

    Args:
        assigned_character_ids_str: JSON array of character IDs as string.
        character_lookup_func: Async callable that takes list of IDs and
                               returns list of dicts with name/description.
    """
    characters: Optional[List[Dict[str, Any]]] = None

    if assigned_character_ids_str and character_lookup_func:
        try:
            ids = json.loads(assigned_character_ids_str)
            if isinstance(ids, list) and ids:
                characters = await character_lookup_func(ids)
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        # Try LLM path
        return generate_panel_ltx_prompt(
            description=panel_description,
            camera_direction=camera_direction,
            panel_type=panel_type,
            scene_heading=scene_heading,
            location=location,
            time_of_day=time_of_day,
            scene_summary=scene_summary,
            character_descriptions=characters,
            project_vision=project_vision,
            project_tone=project_tone,
            mode=mode,
            panel_number=panel_number,
            total_panels=total_panels,
            previous_panel_prompt=previous_panel_prompt,
        )
    except Exception as e:
        print(f"[prompt_builder] LLM path failed: {e}, using fallback")
        # Fallback
        char_texts = [c.get("description", "") or c.get("name", "") for c in characters] if characters else None
        return build_panel_prompt_fallback(
            description=panel_description,
            camera_direction=camera_direction,
            panel_type=panel_type,
            scene_heading=scene_heading,
            location=location,
            time_of_day=time_of_day,
            character_descriptions=char_texts,
            project_vision=project_vision,
            project_tone=project_tone,
        )