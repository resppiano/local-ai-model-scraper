"""
Storytelling Agent
==================
Specialized agent that analyzes scene context and returns a structured
[STORYTELLING] block — narrative structure, tropes, character arcs,
pacing — for the final LTX prompt.

Uses the storytelling knowledge RAG to ground its output.
"""
from typing import Optional, List, Dict, Any

from ..rag.knowledge_rag import get_rag
from .base_agent import call_llm

SYSTEM_PROMPT = """You are a narrative/storytelling expert. Given a scene summary, project tone, character descriptions, and genre context, you produce a structured [STORYTELLING] block for an LTX video generation prompt.

Your output covers:
- NARRATIVE FUNCTION: what role this scene plays in the larger story (setup, confrontation, climax, resolution)
- TONE & MOOD: the emotional register the scene should convey
- NARRATIVE TECHNIQUE: relevant tropes, structure, or devices that inform the visual approach
- CHARACTER DYNAMIC: how the characters' relationships and arcs inform the visual framing
- PACING: scene rhythm, tension level, how the camera should feel

Output format:
```
[STORYTELLING]
Narrative Function: [scene's role in the story arc]
Tone: [emotional register, thematic weight]
Technique: [narrative devices, tropes, structure notes]
Character Dynamic: [how character arcs inform the visual approach]
Pacing: [rhythm, tension level, camera tempo]
```

Be specific and thematically aware. Use the Reference Knowledge if provided, but always tailor it to the specific scene. Keep it concise — 2-3 lines per section."""


def analyze_storytelling(
    description: str,
    scene_summary: Optional[str] = None,
    scene_heading: Optional[str] = None,
    project_tone: Optional[str] = None,
    project_vision: Optional[str] = None,
    characters: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Returns a structured [STORYTELLING] block string. Falls back on failure."""
    lines = [f"Panel description: {description}"]
    if scene_summary:
        lines.append(f"Scene summary: {scene_summary}")
    if scene_heading:
        lines.append(f"Scene heading: {scene_heading}")
    if project_tone:
        lines.append(f"Project tone: {project_tone}")
    if project_vision:
        lines.append(f"Project vision: {project_vision}")
    if characters:
        char_strs = [f"{c.get('name','?')}: {c.get('description','')}" for c in characters]
        lines.append("Characters:")
        for c in char_strs:
            lines.append(f"  - {c}")

    # RAG for storytelling and authors
    rag = get_rag()
    rag_queries = []
    if scene_summary:
        rag_queries.append(scene_summary)
    if project_tone:
        rag_queries.append(project_tone)
    if project_vision:
        rag_queries.append(project_vision)
    rag_queries.append(description[:200])

    contexts = []
    for q in rag_queries:
        results = rag.query(q, top_k=2, domain_filter=["storytelling", "authors"])
        for r in results:
            if r["score"] > 0.65:
                snippet = f"[{r['domain']}/{r['heading']}] {r['content'][:250]}"
                if snippet not in contexts:
                    contexts.append(snippet)

    if contexts:
        lines.append("")
        lines.append("Reference Knowledge:")
        for ctx in contexts[:4]:
            lines.append(f"- {ctx}")
        lines.append("")

    user_prompt = "\n".join(lines)
    result = call_llm(SYSTEM_PROMPT, user_prompt, temperature=0.4)
    if result:
        return result

    # Fallback
        fallback_lines = []
        nf = ['Scene builds tension and advances the plot', 'Scene provides emotional resolution', 'Scene establishes the world and character dynamics', 'Scene represents a turning point in the narrative', 'Scene deepens character relationships and reveals motivation']
        tones = ['grounded and real', 'heightened and dramatic', 'warm and intimate', 'tense and foreboding', 'bittersweet and reflective']
        techs = ['Classic three-act structure, rising action', 'Character-driven narrative, internal conflict', 'Genre conventions inform the visual language', 'Pacing builds toward a reveal', 'Atmospheric, mood-driven storytelling']
        chars = ['The protagonist is at the center of the frame', 'Character relationships shape the blocking and space between them', 'Internal conflict is reflected in the visual composition', 'Power dynamics are communicated through framing and height']
        pacings = ['Slow, deliberate -- the camera holds and breathes', 'Medium pace -- natural, scene-driven rhythm', 'Building tension -- each shot tightens toward the climax', 'Fast and urgent -- dynamic energy drives the scene', 'Calm and reflective -- the aftermath, space to breathe']

        fallback_lines.append(f"[STORYTELLING]")
        fallback_lines.append(f"Narrative Function: {nf[hash(description or '') % 5]}.")
        fallback_lines.append(f"Tone: {project_tone or 'Neutral, observational'} -- the scene should feel {tones[hash(project_tone or 'neutral') % 5]}.")
        fallback_lines.append(f"Technique: {techs[hash(description or '') % 5]}.")
        fallback_lines.append(f"Character Dynamic: {chars[hash(str(characters or '')) % 4]}.")
        fallback_lines.append(f"Pacing: {pacings[hash(project_tone or 'neutral') % 5]}.")
        return "\n".join(fallback_lines)