"""
Author Style Agent
==================
Specialized agent that identifies and applies author/director style
guidance to the LTX prompt — visual hallmarks, narrative signatures,
and specific techniques associated with known directors and writers.

Uses the authors knowledge RAG to ground its output.
"""
from typing import Optional

from ..rag.knowledge_rag import get_rag
from .base_agent import call_llm

SYSTEM_PROMPT = """You are an expert in film and literary style. Given a project vision, tone, and scene context, you identify any relevant author or director style cues and produce a structured [AUTHOR STYLE] block for an LTX video generation prompt.

Your output covers:
- STYLE REFERENCE: which director/writer's style is being referenced (if any)
- VISUAL HALLMARKS: specific visual techniques from that style (symmetry, long takes, color, etc.)
- NARRATIVE SIGNATURE: how the style affects storytelling choices
- APPLICATION: how to apply these style cues to the specific scene

Output format:
```
[AUTHOR STYLE]
Style Reference: [director/writer name or "None" if no specific style cued]
Visual Hallmarks: [specific visual techniques from this style]
Narrative Signature: [how the style affects storytelling]
Application: [how to apply these cues to the specific panel data]
```

If no specific author/director style is referenced, note "None" and skip. Be specific about techniques — don't just say "Spielberg style", describe what that means visually."""


def analyze_author_style(
    description: str,
    project_vision: Optional[str] = None,
    project_tone: Optional[str] = None,
    scene_summary: Optional[str] = None,
) -> str:
    """Returns a structured [AUTHOR STYLE] block. Falls back on failure."""
    lines = [f"Panel description: {description}"]
    if project_vision:
        lines.append(f"Project vision: {project_vision}")
    if project_tone:
        lines.append(f"Project tone: {project_tone}")
    if scene_summary:
        lines.append(f"Scene summary: {scene_summary}")

    # Query authors RAG
    rag = get_rag()
    queries = []
    if project_vision:
        queries.append(project_vision)
    if project_tone:
        queries.append(project_tone)
    if scene_summary:
        queries.append(scene_summary)
    queries.append(description[:200])

    contexts = []
    for q in queries:
        results = rag.query(q, top_k=2, domain_filter=["authors"])
        for r in results:
            if r["score"] > 0.65:
                snippet = f"[{r['heading']}] {r['content'][:300]}"
                if snippet not in contexts:
                    contexts.append(snippet)

    if contexts:
        lines.append("")
        lines.append("Reference Author Styles:")
        for ctx in contexts[:3]:
            lines.append(f"- {ctx}")
        lines.append("")

    user_prompt = "\n".join(lines)
    result = call_llm(SYSTEM_PROMPT, user_prompt, temperature=0.4)
    if result:
        return result

    # Fallback — check for known names in project_vision
    vision = (project_vision or "").lower()
    if "spielberg" in vision:
        return """[AUTHOR STYLE]
Style Reference: Steven Spielberg
Visual Hallmarks: The Spielberg Face — close-up on character's reaction before the reveal. Golden hour lighting. Low-angle hero shots against the sky. Light beams cutting through darkness. One-shot continuous takes for wonder.
Narrative Signature: Ordinary people in extraordinary circumstances. Child's perspective. Awe balanced with danger. Hopeful endings.
Application: Frame the scene with a Spielberg one-shot — show the character's reaction before the subject. Use warm golden lighting. If appropriate, frame the character against a bright sky or light source."""
    elif "fincher" in vision:
        return """[AUTHOR STYLE]
Style Reference: David Fincher
Visual Hallmarks: Clinical precision, every camera move deliberate. Green/teal shadows. Dark underexposed frames. Slow, smooth dollies. Tight close-ups of process. Information revealed through visual detail.
Narrative Signature: Dark, psychological. Characters uncovering hidden truths. Procedural detail. Moral ambiguity.
Application: Use slow, precise camera movements. Keep the frame dark and underexposed. Push shadows toward green/teal. Use tight close-ups on hands, evidence, or details."""
    elif "kubrick" in vision:
        return """[AUTHOR STYLE]
Style Reference: Stanley Kubrick
Visual Hallmarks: Perfect symmetrical one-point perspective. The Kubrick stare — eyes raised, head tilted down. Slow zooms that creep forward. Wide angle deep focus. Cold, clinical color palette. Natural practical lighting.
Narrative Signature: Obsessive, ritualistic. Characters trapped by fate. Cold, detached observation.
Application: Use symmetrical framing with the vanishing point centered. Slow push-in zoom. Deep focus so everything is sharp. Hard practical lighting with no fill."""
    elif "villeneuve" in vision:
        return """[AUTHOR STYLE]
Style Reference: Denis Villeneuve
Visual Hallmarks: Massive scale — tiny figures against vast environments. Slow, patient pacing. Unconventional off-center framing with aggressive negative space. Harsh natural light. Thematic color palettes (desert golds, cold blues).
Narrative Signature: Existential themes. Communication across barriers. Moral complexity. Sudden shocking violence.
Application: Use extreme wide shots that dwarf the subject. Off-center composition with vast negative space. Patient pacing — let the camera hold. Dust, atmosphere, particles in the air."""
    elif "king" in vision:
        return """[AUTHOR STYLE]
Style Reference: Stephen King
Visual Hallmarks: Small-town normalcy contrasted with horror. The mundane turned sinister. Childhood perspective. Slow-burn escalation from normal to nightmare. Deep character focus.
Narrative Signature: Small-town Maine setting. The horror is metaphor for real trauma. Character depth makes the horror more effective. The Ka-Tet — a group of friends against evil.
Application: Establish normalcy first — warm golden hour, small-town familiarity. Then introduce subtle wrongness through Dutch angles, wrong shadows, Cold color intrusion. Use child-height camera for childhood POV."""
    else:
        return "[AUTHOR STYLE]\nStyle Reference: None (no specific author/director style referenced)."