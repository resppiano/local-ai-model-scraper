"""
LTX Prompt Agent
================
Multi-Agent Pipeline with parallel execution, smart skipping,
scene position awareness, continuity, and tiered model costing.

Improvements over v1:
  1. PARALLEL — sub-agents run concurrently via ThreadPoolExecutor
  2. SKIP — AuthorStyleAgent skipped if no director/writer ref'd
  3. POSITION — panel_number + total_panels informs tension curve
  4. DEDUP — RAG deduplication at pipeline level
  5. COST — sub-agents use gpt-4o-mini, MasterAgent uses gpt-4o
  6. CONTINUITY — optional previous_panel_prompt for scene consistency
"""
import concurrent.futures
import json
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

# ── Paths ────────────────────────────────────────────────────────────────
_here = Path(__file__).parent.parent
ANTMATTER_DIR = Path(os.environ.get(
    "ANTMATTER_DIR",
    "/home/gregjones/Documents/AntMatter",
))
SYSTEM_PROMPT_PATH = ANTMATTER_DIR / "ltx_2_3_super_prompt_master_agent_v2.md"

# Default model strategy: cheap for sub-agents, quality for master
SUB_AGENT_MODEL = "openai/gpt-4o-mini"   # $0.15/M input, fast, good enough
MASTER_AGENT_MODEL = "openai/gpt-4o"      # $2.50/M input, quality synthesis

# Known director/writer names to detect in project_vision
KNOWN_AUTHORS = [
    "spielberg", "kubrick", "fincher", "villeneuve", "tarantino", "nolan",
    "scorsese", "coppola", "anderson", "king", "clancy", "del toro",
    "cameron", "scott", "besson", "kurosawa", "hitchcock", "lynch",
]


def _load_system_prompt() -> str:
    """Read the .md file once and cache."""
    if not SYSTEM_PROMPT_PATH.exists():
        print(f"[LTXPromptAgent] WARNING: {SYSTEM_PROMPT_PATH} not found — using default")
        return _default_system_prompt()
    return SYSTEM_PROMPT_PATH.read_text()


def _default_system_prompt() -> str:
    return (
        "You are a professional LTX 2.3 cinematic prompt architect. "
        "Transform a simple description into a clean, structured, production-ready LTX 2.3 prompt. "
        "Output format: [VISUAL]... [CINEMATOGRAPHY]... [CHARACTER MOTION]... [SPEECH]... [SOUNDS]..."
    )


def _detect_author_style_ref(project_vision: Optional[str]) -> bool:
    """Check if project_vision references a known director/writer."""
    if not project_vision:
        return False
    vision_lower = project_vision.lower()
    for name in KNOWN_AUTHORS:
        if name in vision_lower:
            return True
    return False


def _dedup_rag_results(results: List[Dict]) -> List[Dict]:
    """Deduplicate RAG results by heading to avoid redundant context."""
    seen_headings = set()
    deduped = []
    for r in results:
        key = r.get("heading", "") + "|" + r.get("source", "")
        if key not in seen_headings:
            seen_headings.add(key)
            deduped.append(r)
    return deduped


# ── Agent ────────────────────────────────────────────────────────────────
class LTXPromptAgent:
    """Generates structured LTX 2.3 prompts using a multi-agent pipeline."""

    def __init__(self):
        self.system_prompt = _load_system_prompt()
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
        # ── V2 improvements ──────────────────────────────────────────────
        panel_number: Optional[int] = None,
        total_panels: Optional[int] = None,
        previous_panel_prompt: Optional[str] = None,
        # Override models (defaults: sub=gpt-4o-mini, master=gpt-4o)
        sub_agent_model: Optional[str] = None,
        master_model: Optional[str] = None,
    ) -> str:
        """
        Multi-agent pipeline with parallel execution, smart skipping,
        scene position awareness, and tiered model costing.

        New args:
            panel_number: 1-based panel position in the scene.
            total_panels: Total panels in this scene.
            previous_panel_prompt: The LTX prompt from the previous panel
                for continuity (color palette, lighting consistency).
            sub_agent_model: Model for sub-agents (default: gpt-4o-mini).
            master_model: Model for MasterAgent (default: gpt-4o).
        """
        model_cfg = {
            "sub_agent": sub_agent_model or SUB_AGENT_MODEL,
            "master": master_model or MASTER_AGENT_MODEL,
        }

        # Determine scene position string for agents
        position_str = ""
        if panel_number is not None and total_panels is not None:
            ratio = panel_number / max(total_panels, 1)
            if ratio < 0.25:
                position_str = f"Panel {panel_number}/{total_panels} — early scene, setup/establishing phase"
            elif ratio < 0.45:
                position_str = f"Panel {panel_number}/{total_panels} — rising action, building tension"
            elif ratio < 0.55:
                position_str = f"Panel {panel_number}/{total_panels} — midpoint, potential turning point"
            elif ratio < 0.75:
                position_str = f"Panel {panel_number}/{total_panels} — late scene, approaching climax"
            else:
                position_str = f"Panel {panel_number}/{total_panels} — climax or resolution phase"

        # Determine if we should skip agents
        has_author_ref = _detect_author_style_ref(project_vision)
        has_story_context = bool(scene_summary or project_tone)

        # ── Step 1: Run sub-agents in parallel ──────────────────────────
        cinema_block = ""
        story_block = ""
        author_block = ""

        # Build task list for parallel execution
        tasks = []

        # CinemaAgent always runs (always relevant)
        tasks.append(("cinema", lambda: self.cinema_agent(
            description=panel_description,
            camera_direction=camera_direction,
            panel_type=panel_type,
            scene_summary=scene_summary,
            project_tone=project_tone,
            project_vision=project_vision,
            sub_agent_model=model_cfg["sub_agent"],
            scene_position=position_str,
            continuity=previous_panel_prompt,
        )))

        # StorytellingAgent — skip if no narrative context
        if has_story_context:
            tasks.append(("story", lambda: self.storytelling_agent(
                description=panel_description,
                scene_summary=scene_summary,
                scene_heading=scene_heading,
                project_tone=project_tone,
                project_vision=project_vision,
                characters=characters,
                sub_agent_model=model_cfg["sub_agent"],
                scene_position=position_str,
                continuity=previous_panel_prompt,
            )))
        else:
            story_block = ""

        # AuthorStyleAgent — skip if no author/director referenced
        if has_author_ref:
            tasks.append(("author", lambda: self.author_agent(
                description=panel_description,
                project_vision=project_vision,
                project_tone=project_tone,
                scene_summary=scene_summary,
                sub_agent_model=model_cfg["sub_agent"],
            )))
        else:
            author_block = ""

        # Execute in parallel
        if tasks:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_map = {executor.submit(fn): name for name, fn in tasks}
                for future in concurrent.futures.as_completed(future_map):
                    name = future_map[future]
                    try:
                        result = future.result()
                        if name == "cinema":
                            cinema_block = result
                        elif name == "story":
                            story_block = result
                        elif name == "author":
                            author_block = result
                    except Exception as e:
                        print(f"[LTXPromptAgent] {name} failed: {e}")

        # ── Step 2: Master synthesis ────────────────────────────────────
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
                master_model=model_cfg["master"],
                scene_position=position_str,
                continuity=previous_panel_prompt,
            )
            if result:
                return result
        except Exception as e:
            print(f"[LTXPromptAgent] MasterAgent failed: {e}")

        # ── Step 3: Ultimate fallback ───────────────────────────────────
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

    # ── Fallback: single-LLM call ────────────────────────────────────────

    def _build_user_prompt(
        self, description: str, camera_direction: str, panel_type: str,
        scene_heading: Optional[str], location: Optional[str],
        time_of_day: Optional[str], scene_summary: Optional[str],
        characters: Optional[List[Dict[str, Any]]], project_vision: Optional[str],
        project_tone: Optional[str], mode: str,
    ) -> str:
        lines = ["Generate an LTX 2.3 prompt for the following panel:"]

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

        ctx = []
        if project_vision:
            ctx.append(f"Style: {project_vision}")
        if project_tone:
            ctx.append(f"Tone: {project_tone}")
        if ctx:
            lines.append("Project: " + " | ".join(ctx))

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

        if characters:
            char_lines = []
            for c in characters:
                name = c.get("name", "?")
                desc = c.get("description", "")
                has_ref = bool(c.get("reference_image_url"))
                ref = " (reference image provided)" if has_ref else ""
                char_lines.append(f"  {name}: {desc}{ref}" if desc else f"  {name}{ref}")
            lines.append("Characters:")
            lines.extend(char_lines)

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
                return result["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"[LTXPromptAgent] API call failed: {e}")
            return self._template_fallback(user_prompt)

    # ── Fallback template ─────────────────────────────────────────────────

    def _template_fallback(self, user_prompt: str) -> str:
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


# ── Import urllib (needed by _call_llm) ───────────────────────────────────
import urllib.request