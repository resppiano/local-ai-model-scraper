"""
LTX Prompt Agent
================
Loads the Super Prompt Master Agent .md as a system prompt,
takes panel/scene data from Fable, and returns a structured
LTX 2.3 prompt via OpenRouter.

Usage:
    agent = LTXPromptAgent()
    prompt = await agent.generate_from_panel(panel_data, scene_data, characters, project)
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
    """Generates structured LTX 2.3 prompts from Fable panel data."""

    def __init__(self):
        self.system_prompt = _load_system_prompt()

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
        Build a user prompt from panel data, call the LLM, return the
        structured LTX 2.3 prompt.

        Args:
            panel_description: The panel's description text.
            camera_direction: pan_left / pan_right / dolly_in / dolly_out / static.
            panel_type: wide / medium / closeup / insert.
            scene_heading: e.g. "INT. OFFICE - NIGHT"
            location: e.g. "Rooftop, Neon City"
            time_of_day: e.g. "Night"
            scene_summary: Summary of the scene from script breakdown.
            characters: List of dicts with "name", "description", "reference_image_url".
            project_vision: e.g. "Neo-noir heist thriller..."
            project_tone: e.g. "brooding, tense"
            mode: "image-to-video" or "text-to-video" or "retake".

        Returns:
            The structured LTX 2.3 prompt string.
        """
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

    # ── User prompt builder ───────────────────────────────────────────────

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
            "pan_left": "camera slowly pans left",
            "pan_right": "camera slowly pans right",
            "dolly_in": "camera slowly pushes in",
            "dolly_out": "camera slowly pulls back",
            "static": "static shot, camera is still",
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
                    # Try loading from .hermes/.env via shell (file is credential-store masked)
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
            import urllib.request

            payload = json.dumps({
                "model": "openai/gpt-4o",  # works well for structured output
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
        # Parse the user prompt for key info
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

        # Build a structured fallback
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