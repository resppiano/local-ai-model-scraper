"""
Cinema Agent
============
Specialized agent that analyzes panel data and returns a structured
[CINEMATOGRAPHY] block — lighting, lens, camera movement, composition,
and color — for the final LTX prompt.

Uses the cinematography knowledge RAG to ground its output.
"""
from typing import Optional, List, Dict, Any

from ..rag.knowledge_rag import get_rag
from .base_agent import call_llm

SYSTEM_PROMPT = """You are a cinema/cinematography expert. Given a panel description, shot type, camera direction, and scene context, you produce a structured [CINEMATOGRAPHY] block for an LTX video generation prompt.

Your output covers:
- CAMERA MOVEMENT: how the camera moves (or doesn't), with emotional intent
- LIGHTING: lighting setup, quality, source, color temperature, mood
- LENS & FOCUS: focal length feel, depth of field, focus technique
- COMPOSITION: framing, rule of thirds, leading lines, depth
- COLOR: palette, grading style, emotional color associations

Output format:
```
[CINEMATOGRAPHY]
Camera: [exact camera movement description, mood, and pacing]
Lighting: [lighting setup, quality, source, direction, mood]
Lens: [focal length feel, depth of field, focus technique]
Composition: [framing, arrangement, visual flow]
Color: [palette, grade, emotional effect]
```

Be specific and visual. Use the Reference Knowledge if provided, but always tailor it to the specific panel data. Keep it to 3-5 lines per section, concise and prompt-ready."""


def analyze_cinematography(
    description: str,
    camera_direction: str = "static",
    panel_type: str = "wide",
    scene_summary: Optional[str] = None,
    project_tone: Optional[str] = None,
    project_vision: Optional[str] = None,
) -> str:
    """
    Returns a structured [CINEMATOGRAPHY] block string.
    Falls back to a simple template if the LLM call fails.
    """
    # Build user prompt
    lines = [f"Panel description: {description}"]
    lines.append(f"Shot type: {panel_type}")
    lines.append(f"Camera direction: {camera_direction}")

    if scene_summary:
        lines.append(f"Scene summary: {scene_summary}")
    if project_tone:
        lines.append(f"Project tone: {project_tone}")
    if project_vision:
        lines.append(f"Project vision: {project_vision}")

    # RAG context
    rag = get_rag()
    query = f"{panel_type} shot, {camera_direction} camera, {description[:200]}"
    if project_tone:
        query += f", {project_tone} mood"
    results = rag.query(query, top_k=3, domain_filter=["cinematography"])

    if results and results[0]["score"] > 0.6:
        lines.append("")
        lines.append("Reference Knowledge:")
        for r in results:
            lines.append(f"- [{r['heading']}] {r['content'][:300]}")
        lines.append("")

    user_prompt = "\n".join(lines)

    # Try LLM
    result = call_llm(SYSTEM_PROMPT, user_prompt, temperature=0.4)
    if result:
        return result

    # Fallback template
    camera_map = {
        "pan_left": "camera slowly pans left, revealing the scene horizontally",
        "pan_right": "camera slowly pans right, following the action",
        "dolly_in": "camera smoothly pushes in toward the subject, intensifying the moment",
        "dolly_out": "camera smoothly pulls back, revealing the larger context",
        "static": "static shot, camera is perfectly still, locked off on tripod",
        "handheld": "handheld camera, slight natural shake, documentary feel",
        "steadicam": "smooth gimbal-mounted shot, following the subject fluidly",
        "dolly_zoom": "dolly zoom effect — camera pulls back while zooming in, background warps",
        "track_left": "camera tracks left alongside the subject",
        "track_right": "camera tracks right alongside the subject",
        "crane_up": "camera rises up, revealing the full scale of the environment",
        "crane_down": "camera lowers, bringing us into the scene from above",
        "tilt_up": "camera tilts up, revealing height and scale",
        "tilt_down": "camera tilts down, looking down on the subject",
        "whip_pan": "fast whip pan, quick disorienting camera movement",
        "aerial": "aerial drone shot, high above, sweeping view",
    }
    cam_text = camera_map.get(camera_direction, "static shot, camera is still")

    tone_lighting = {
        "noir": "Chiaroscuro lighting, deep shadows, venetian blind patterns, high contrast",
        "tense": "Low-key lighting, practical light sources, mixed color temperatures, shadows",
        "romantic": "Soft diffused lighting, golden warmth, gentle shadows, dreamy quality",
        "nostalgic": "Golden hour warmth, soft halation, gentle backlight, warm tones",
        "dark": "Minimal lighting, deep blacks, single strong key light, silhouettes",
        "bright": "High-key lighting, even illumination, minimal shadows, clean",
    }
    lighting = "Professional three-point lighting, balanced and natural"
    for t, lt in tone_lighting.items():
        if project_tone and t in project_tone.lower():
            lighting = lt
            break

    return f"""[CINEMATOGRAPHY]
Camera: {cam_text}. The movement {['creates tension', 'feels immersive', 'follows the action', 'keeps the viewer focused', 'reveals the environment slowly'][hash(description) % 5]}.
Lighting: {lighting}. The light {['sculpts the subject from the darkness', 'wraps the scene in natural warmth', 'creates dramatic contrast', 'feels motivated by practical sources', 'emphasizes the subject while the background falls into shadow'][hash(description) % 5]}.
Lens: {['Shallow depth of field, subject sharp against a soft bokeh background', 'Deep focus, everything sharp from foreground to infinity', 'Standard 50mm equivalent, natural perspective', 'Wide angle, emphasizing depth and scale', 'Telephoto compression, flattening the space for intimacy'][hash(panel_type) % 5]}.
Composition: {['Rule of thirds, subject placed on the left third', 'Centered symmetrical framing, formal and balanced', 'Leading lines draw the eye toward the subject', 'Deep space with action across three planes', 'Subject isolated in negative space'][hash(panel_type) % 5]}.
Color: {['Natural color palette, true to life', 'Desaturated with selective color for emphasis', 'Warm golden tones, soft and nostalgic', 'Cool teal shadows with warm skin tones', 'Monochromatic palette within a single hue range'][hash(project_tone or 'neutral') % 5]}."""