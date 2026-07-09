"""
LTX Prompt Agent
================
Loads the Super Prompt Master Agent .md as a system prompt,
takes panel/scene data from Fable, and returns a structured
LTX 2.3 prompt via OpenRouter.

Multi-Agent Pipeline:
  1. CinemaAgent — analyzes the panel for cinematography details
  2. StorytellingAgent — analyzes the narrative context
  3. AuthorStyleAgent — identifies author/director style cues
  4. MasterAgent — synthesizes all three into the final LTX prompt
"""
import json
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

# ── Paths ────────────────────────────────────────────────────────────────
_here = Path(__file__).parent.parent
ANTMATTER_DIR = Path(os.environ.get(
    "ANTMATTER_DIR",
    "/home/gregjones/Documents/AntMatter",
))
SYSTEM_PROMPT_PATH = ANTMATTER_DIR / "ltx_2_3_super_prompt_master_agent_v2.md"


def _load_system_prompt() -> str:
    """Read the .md file once and cache."""
    if not SYSTEM_PROMPT_PATH.exists():
        print(f"[LTXPromptAgent] WARNING: {SYSTEM_PROMPT_PATH} not found — using default")
        return _default_system_prompt()
    return SYSTEM_PROMPT_PATH.read_text()


def _default_system_prompt() -> str:
    """Minimal fallback if the .md file is missing."""
    return (
        "You are a professional LTX 2.3 cinematic prompt architect. "
        "Transform a simple description into a clean, structured, production-ready LTX 2.3 prompt. "
        "Output format: [VISUAL]... [CINEMATOGRAPHY]... [CHARACTER MOTION]... [SPEECH]... [SOUNDS]..."
    )


# ── Agent ────────────────────────────────────────────────────────────────
class LTXPromptAgent:
    """Generates structured LTX 2.3 prompts using a multi-agent pipeline."""

    def __init__(self):
        self.system_prompt = _load_system_prompt()
        # Lazy-import sub-agents
        self._cinema = None
        self._story = None
        self._author = None
        self._master = None

    @property
    def cinema_agent(self):
        if self._cinema is None:
            from .agents.cinema_agent import analyze_cinematography
            self._cinema = analyze_cinematography
        return self._cinema

    @property
    def storytelling_agent(self):
        if self._story is None:
            from .agents.storytelling_agent import analyze_storytelling
            self._story = analyze_storytelling
        return self._story

    @property
    def author_agent(self):
        if self._author is None:
            from .agents.author_style_agent import analyze_author_style
            self._author = analyze_author_style
        return self._author

    @property
    def master_agent(self):
        if self._master is None:
            from .agents.master_agent import synthesize
            self._master = synthesize
        return self._master

    # ── Public API ────────────────────────────────────────────────────────

    def generate_from_panel(
        self,
        panel_description: str,
        camera_direction: str = "static",
        panel_type: str = "wide",
        scene_heading: Optional[str] = None,
        location: Optional[str] = None,
        time_of_day: Optional[str] = None,
        scene_summary: Optional[str] = None,
        characters: Optional[List[Dict[str, Any]]] = None,
        project_vision: Optional[str] = None,
        project_tone: Optional[str] = None,
        mode: str = "image-to-video",
    ) -> str:
        """
        Multi-agent pipeline:
        1. Run all three sub-agents
        2. Master agent synthesizes into final LTX prompt
        3. Falls back to single-LLM call if sub-agents fail
        """
        # Shared kwargs for all agents
        kwargs = {
            "description": panel_description,
            "camera_direction": camera_direction,
            "panel_type": panel_type,
            "scene_heading": scene_heading,
            "location": location,
            "time_of_day": time_of_day,
            "scene_summary": scene_summary,
            "characters": characters,
            "project_vision": project_vision,
            "project_tone": project_tone,
            "mode": mode,
        }

        # Step 1: Run all three sub-agents
        try:
            cinema_block = self.cinema_agent(
                description=panel_description,
                camera_direction=camera_direction,
                panel_type=panel_type,
                scene_summary=scene_summary,
                project_tone=project_tone,
                project_vision=project_vision,
            )
        except Exception as e:
            print(f"[LTXPromptAgent] CinemaAgent failed: {e}")
            cinema_block = ""

        try:
            story_block = self.storytelling_agent(
                description=panel_description,
                scene_summary=scene_summary,
                scene_heading=scene_heading,
                project_tone=project_tone,
                project_vision=project_vision,
                characters=characters,
            )
        except Exception as e:
            print(f"[LTXPromptAgent] StorytellingAgent failed: {e}")
            story_block = ""

        try:
            author_block = self.author_agent(
                description=panel_description,
                project_vision=project_vision,
                project_tone=project_tone,
                scene_summary=scene_summary,
            )
        except Exception as e:
            print(f"[LTXPromptAgent] AuthorStyleAgent failed: {e}")
            author_block = ""

        # Step 2: Master synthesis
        try:
            result = self.master_agent(
                panel_description=panel_description,
                camera_direction=camera_direction,
                panel_type=panel_type,
                scene_heading=scene_heading,
                location=location,
                time_of_day=time_of_day,
                scene_summary=scene_summary,
                characters=characters,
                project_vision=project_vision,
                project_tone=project_tone,
                mode=mode,
                cinema_block=cinema_block,
                storytelling_block=story_block,
                author_block=author_block,
            )
            if result:
                return result
        except Exception as e:
            print(f"[LTXPromptAgent] MasterAgent failed: {e}")

        # Step 3: Ultimate fallback — build user prompt and call LLM directly
        print("[LTXPromptAgent] Falling back to direct LLM call")
        user_prompt = self._build_user_prompt(
            description=panel_description,
            camera_direction=camera_direction,
            panel_type=panel_type,
            scene_heading=scene_heading,
            location=location,
            time_of_day=time_of_day,
            scene_summary=scene_summary,
            characters=characters,
            project_vision=project_vision,
            project_tone=project_tone,
            mode=mode,
        )
        return self._call_llm(user_prompt)

    # ── Fallback: single-LLM call (original behavior) ────────────────────

    def _build_user_prompt(
        self,
        description: str,
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
    ) -> str:
        lines = ["Generate an LTX 2.3 prompt for the following panel:"]

        # RAG context injection
        from .rag.knowledge_rag import get_rag
        rag = get_rag()
        rag_queries = []
        if scene_summary:
            rag_queries.append(scene_summary)
        if description:
            rag_queries.append(description)
        if project_tone:
            rag_queries.append(project_tone)
        if project_vision:
            rag_queries.append(project_vision)

        rag_contexts = []
        for q in rag_queries:
            results = rag.query(q, top_k=2)
            for r in results:
                if r["score"] > 0.65:
                    snippet = f"[{r['domain']}] {r['heading']}: {r['content'][:400]}"
                    if snippet not in rag_contexts:
                        rag_contexts.append(snippet)

        if rag_contexts:
            lines.append("")
            lines.append("Relevant knowledge for reference:")
            for ctx in rag_contexts[:4]:
                lines.append(f"  - {ctx}")
            lines.append("")

        # Project context
        ctx = []
        if project_vision:
            ctx.append(f"Style: {project_vision}")
        if project_tone:
            ctx.append(f"Tone: {project_tone}")
        if ctx:
            lines.append("Project: " + " | ".join(ctx))

        # Scene context
        scene_parts = []
        if scene_heading:
            scene_parts.append(scene_heading)
        if location:
            scene_parts.append(f"Location: {location}")
        if time_of_day:
            scene_parts.append(f"Time: {time_of_day}")
        if scene_summary:
            scene_parts.append(f"Summary: {scene_summary}")
        if scene_parts:
            lines.append("Scene: " + " | ".join(scene_parts))

        # Characters
        if characters:
            char_lines = []
            for c in characters:
                name = c.get("name", "?")
                desc = c.get("description", "")
                has_ref = bool(c.get("reference_image_url"))
                ref = " (reference image provided)" if has_ref else ""
                if desc:
                    char_lines.append(f"  {name}: {desc}{ref}")
                else:
                    char_lines.append(f"  {name}{ref}")
            if char_lines:
                lines.append("Characters:")
                lines.extend(char_lines)

        # Panel details
        lines.append(f"Shot type: {panel_type}")
        lines.append(f"Camera: {self._camera_text(camera_direction)}")
        lines.append(f"Description: {description}")
        lines.append("No dialogue unless specified below.")
        lines.append("")
        lines.append("Mode: " + mode)

        return "\n".join(lines)

    @staticmethod
    def _camera_text(direction: str) -> str:
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

    # ── LLM call ──────────────────────────────────────────────────────────

    def _call_llm(self, user_prompt: str) -> str:
        """
        Call OpenRouter with the .md as system prompt.
        Falls back to a simple template if the API call fails.
        """
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            import subprocess
            try:
                result = subprocess.run(
                    ["bash", "-c", "source /home/gregjones/.hermes/.env 2>/dev/null && echo \"$OPENROUTER_API_KEY\""],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    api_key = result.stdout.strip()
            except Exception:
                pass

        if not api_key:
            print("[LTXPromptAgent] No OPENROUTER_API_KEY — using template fallback")
            return self._template_fallback(user_prompt)

        try:
            payload = json.dumps({
                "model": "openai/gpt-4o",
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            }).encode()

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://fable-studio.local",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                content = result["choices"][0]["message"]["content"]
                return content.strip()

        except Exception as e:
            print(f"[LTXPromptAgent] API call failed: {e}")
            return self._template_fallback(user_prompt)

    # ── Fallback template ─────────────────────────────────────────────────

    def _template_fallback(self, user_prompt: str) -> str:
        """Generate a reasonable structured prompt without an LLM call."""
        desc = ""
        camera = "static shot, camera is still"
        location = ""
        chars = ""

        for line in user_prompt.splitlines():
            if line.startswith("Description:"):
                desc = line[len("Description:"):].strip()
            elif line.startswith("Camera:"):
                camera = line[len("Camera:"):].strip()
            elif line.startswith("Location:"):
                location = line[len("Location:"):].strip()
            elif line.startswith("  "):
                chars = line.strip()

        parts = ["[VISUAL]"]
        if location:
            parts.append(f"Scene set in {location}.")
        if desc:
            parts.append(desc)
        if chars:
            parts.append(f"Characters: {chars}")
        parts.append("Preserve the environment, lighting, and composition.")

        parts.append("\n[CINEMATOGRAPHY]")
        parts.append(f"{camera}.")
        parts.append("Maintain original framing and lighting.")

        parts.append("\n[CHARACTER MOTION]")
        if chars:
            parts.append("Natural blinking, subtle body movement, consistent with the scene.")
        else:
            parts.append("Environmental motion only: ambient movement, natural atmosphere.")

        parts.append("\n[SPEECH]")
        parts.append("No dialogue.")

        parts.append("\n[SOUNDS]")
        parts.append("Ambient background sound.")
        parts.append("No music.")

        return "\n".join(parts)