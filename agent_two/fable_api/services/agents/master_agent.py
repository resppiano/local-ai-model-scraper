"""
Master Agent
============
Synthesizes the outputs from CinemaAgent, StorytellingAgent, and
AuthorStyleAgent into a single coherent LTX generation prompt.

This is the final step in the pipeline — it receives the three
structured blocks plus the original panel data and produces the
production-ready LTX prompt.
"""
from typing import Optional, List, Dict, Any

from ..rag.knowledge_rag import get_rag
from .base_agent import call_llm

SYSTEM_PROMPT = """You are a master LTX 2.3 prompt architect. You receive three expert analyses of a scene — cinematography, storytelling, and author style — and synthesize them into a single, coherent, production-ready LTX generation prompt.

Your output must follow this structure:
```
[VISUAL]
[Shot description, scene composition, character placement, environment details]
[CINEMATOGRAPHY]
[Camera movement, lighting, lens, composition, color]
[CHARACTER MOTION]
[Character movement, expression, performance notes]
[SPEECH]
[Dialogue, narration, silence]
[SOUNDS]
[Ambient, effects, music]
```

Rules:
- Every section must be present
- Be specific, visual, and prompt-ready
- Don't repeat the same information across sections
- Weave all three expert analyses together naturally
- Preserve the scene's emotional intent and narrative function
- Keep it under 300 words total
- Output ONLY the LTX prompt block, no commentary"""


def synthesize(
    panel_description: str,
    camera_direction: str,
    panel_type: str,
    scene_heading: Optional[str],
    location: Optional[str],
    time_of_day: Optional[str],
    scene_summary: Optional[str],
    characters: Optional[List[Dict[str, Any]]],
    project_vision: Optional[str],
    project_tone: Optional[str],
    mode: str,
    cinema_block: str,
    storytelling_block: str,
    author_block: str,
    master_model: str = "openai/gpt-4o",
    scene_position: str = "",
    continuity: Optional[str] = None,
) -> str:
    """
    Synthesize all three expert blocks plus panel data into the final LTX prompt.
    Falls back to the template fallback on LLM failure.
    """
    lines = [
        "Synthesize the following expert analyses into a single LTX 2.3 prompt.",
        "",
        "## Panel Data",
    ]
    if scene_heading:
        lines.append(f"Scene heading: {scene_heading}")
    if location:
        lines.append(f"Location: {location}")
    if time_of_day:
        lines.append(f"Time: {time_of_day}")
    if scene_summary:
        lines.append(f"Scene summary: {scene_summary}")
    lines.append(f"Shot type: {panel_type}")
    lines.append(f"Camera: {camera_direction}")
    lines.append(f"Description: {panel_description}")
    if project_vision:
        lines.append(f"Project vision: {project_vision}")
    if project_tone:
        lines.append(f"Project tone: {project_tone}")
    if scene_position:
        lines.append(f"Scene position: {scene_position}")
    if continuity:
        lines.append(f"Previous panel prompt for continuity: {continuity[:1000]}")
    lines.append(f"Mode: {mode}")

    if characters:
        lines.append("")
        lines.append("Characters:")
        for c in characters:
            name = c.get("name", "?")
            desc = c.get("description", "")
            has_ref = bool(c.get("reference_image_url"))
            ref = " (reference image provided)" if has_ref else ""
            lines.append(f"  {name}: {desc}{ref}")

    lines.append("")
    lines.append("## Cinema Expert Analysis")
    lines.append(cinema_block)

    lines.append("")
    lines.append("## Storytelling Expert Analysis")
    lines.append(storytelling_block)

    lines.append("")
    lines.append("## Author Style Expert Analysis")
    lines.append(author_block)

    user_prompt = "\n".join(lines)

    result = call_llm(SYSTEM_PROMPT, user_prompt, model=master_model, temperature=0.3, max_tokens=2048)
    if result:
        return result

    # Fallback: stitch blocks together directly
    parts = []
    parts.append("[VISUAL]")
    if scene_heading:
        parts.append(scene_heading)
    if location:
        parts.append(f"Location: {location}. {time_of_day or ''}")
    parts.append(panel_description)
    if characters:
        char_text = "; ".join(f"{c.get('name','?')}: {c.get('description','')}" for c in characters if c.get('description'))
        if char_text:
            parts.append(f"Characters: {char_text}")
    parts.append("")

    # Extract content from the expert blocks
    import re
    cin_lines = []
    st_lines = []
    au_lines = []
    for line in cinema_block.split("\n"):
        if line.startswith("[CINEMATOGRAPHY]"):
            continue
        if line.startswith("["):
            break
        cin_lines.append(line.strip())

    for line in storytelling_block.split("\n"):
        if line.startswith("[STORYTELLING]"):
            continue
        if line.startswith("["):
            break
        st_lines.append(line.strip())

    for line in author_block.split("\n"):
        if line.startswith("[AUTHOR STYLE]"):
            continue
        if line.startswith("["):
            break
        au_lines.append(line.strip())

    parts.append("[CINEMATOGRAPHY]")
    parts.extend(cin_lines)
    parts.append("")
    parts.append("[STORYTELLING]")
    parts.extend(st_lines)
    parts.append("")
    parts.append("[AUTHOR STYLE]")
    parts.extend(au_lines)
    parts.append("")
    parts.append("[CHARACTER MOTION]")
    if characters and any(c.get("description") for c in characters):
        parts.append("Natural blinking, subtle body movement, consistent with character description.")
    else:
        parts.append("Environmental motion only: ambient movement, natural atmosphere.")
    parts.append("")
    parts.append("[SPEECH]")
    parts.append("No dialogue.")
    parts.append("")
    parts.append("[SOUNDS]")
    parts.append("Ambient background sound matching the scene's atmosphere.")
    parts.append("No music.")

    return "\n".join(parts)