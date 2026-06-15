"""
comfyui_renderer.py — Real ComfyUI API renderers for Agent One dispatch.
================================================================================
Registers three renderers with dispatch.py:

  • comfyui_image  → SDXL Lightning (DreamShaper XL) — ~3s per image
  • comfyui_wan    → Wan 2.1 T2V 1.3B — ~170s per clip, 832×480, 41 frames
  • ltx_video      → Wan 2.1 T2V 1.3B (draft: fewer steps, smaller)

Talks to ComfyUI at COMFYUI_URL (default http://localhost:8188).
Reads the project brain to enrich prompts with visual language + character details.

Usage:
    import comfyui_renderer
    comfyui_renderer.register_all()
    # now dispatch.render_shot() will hit ComfyUI instead of returning handoff
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Optional

try:
    from brain import Brain, get_active
    from dispatch import register_renderer
except ImportError:
    from .brain import Brain, get_active
    from .dispatch import register_renderer

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://localhost:8188")
OUTPUT_DIR = os.environ.get("FILMAKE_OUTPUT_DIR", os.path.expanduser("~/ComfyUI/output"))
POLL_INTERVAL = 2     # seconds
POLL_TIMEOUT = 3600    # 10 min max wait (video can be slow)

# ── Wan 2.1 defaults ─────────────────────────────────────────────────────
WAN_MODEL = "WanVideo/wan2.1_t2v_1.3B_fp16.safetensors"
WAN_VAE = "wanvideo/wan_2.1_vae.safetensors"
WAN_T5 = "umt5_xxl_fp16.safetensors"

# ── SDXL defaults ────────────────────────────────────────────────────────
SDXL_CHECKPOINT = "dreamshaperXL_lightningDPMSDE.safetensors"


# ══════════════════════════════════════════════════════════════════════════
# ComfyUI API helpers
# ══════════════════════════════════════════════════════════════════════════
def _api_post(endpoint: str, data: dict) -> dict:
    req = urllib.request.Request(
        f"{COMFYUI_URL}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _api_get(endpoint: str) -> dict:
    with urllib.request.urlopen(f"{COMFYUI_URL}{endpoint}", timeout=30) as resp:
        return json.loads(resp.read())


def _queue_prompt(workflow: dict) -> str:
    """Submit a workflow, return prompt_id."""
    result = _api_post("/prompt", {
        "prompt": workflow,
        "client_id": str(uuid.uuid4()),
    })
    return result["prompt_id"]


def _poll_completion(prompt_id: str, timeout: int = POLL_TIMEOUT) -> dict:
    """Block until prompt completes. Returns the history entry."""
    elapsed = 0
    while elapsed < timeout:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        try:
            hist = _api_get(f"/history/{prompt_id}")
        except Exception:
            continue
        if prompt_id in hist:
            entry = hist[prompt_id]
            status = entry.get("status", {})
            if status.get("completed"):
                return entry
            if status.get("status_str") == "error":
                # Extract error details
                for msg in status.get("messages", []):
                    if msg[0] == "execution_error":
                        ei = msg[1]
                        err_msg = str(ei.get("exception_message", "unknown"))[:500]
                        node = str(ei.get("node_type", "?"))
                        raise RuntimeError(f"ComfyUI error in {node}: {err_msg}")
                raise RuntimeError(f"ComfyUI error (no details)")
    raise TimeoutError(f"ComfyUI prompt {prompt_id} did not complete in {timeout}s")


def _extract_outputs(entry: dict) -> list[str]:
    """Pull output file paths from a completed history entry."""
    files = []
    for node_id, out in entry.get("outputs", {}).items():
        for img in out.get("images", []):
            fname = img.get("filename", "")
            subfolder = img.get("subfolder", "")
            if fname:
                full = os.path.join(OUTPUT_DIR, subfolder, fname) if subfolder else os.path.join(OUTPUT_DIR, fname)
                files.append(full)
        for vid in out.get("gifs", []):
            fname = vid.get("filename", "")
            subfolder = vid.get("subfolder", "")
            if fname:
                full = os.path.join(OUTPUT_DIR, subfolder, fname) if subfolder else os.path.join(OUTPUT_DIR, fname)
                files.append(full)
    return files


# ══════════════════════════════════════════════════════════════════════════
# Prompt enrichment from the brain
# ══════════════════════════════════════════════════════════════════════════
def _enrich_prompt(shot: dict, project: Optional[str] = None) -> tuple[str, str]:
    """Build positive + negative prompts from shot content + brain context."""
    content = shot.get("content") or shot
    positive_parts = []
    prompt_text = content.get("prompt", "")
    if prompt_text:
        positive_parts.append(prompt_text)

    negative_parts = [
        "text, watermark, logo, blurry, low quality, deformed, mutated"
    ]

    proj = project or get_active()
    if proj:
        try:
            brain = Brain.load(proj)
            vl = brain.visual_language

            look_parts = []
            if vl.look:
                look_parts.append(vl.look)
            if vl.lensing:
                look_parts.append(vl.lensing)
            if vl.lighting:
                look_parts.append(vl.lighting)
            if vl.film_stock:
                look_parts.append(vl.film_stock)
            if vl.grade:
                look_parts.append(vl.grade)
            if vl.framing:
                look_parts.append(vl.framing)
            if look_parts:
                positive_parts.append(", ".join(look_parts))

            characters = shot.get("characters", [])
            if isinstance(characters, str):
                characters = [characters]
            bible = brain.bible
            for char_name in characters:
                char = bible.characters.get(char_name)
                if char:
                    char_desc = f"{char_name}: {char.description}"
                    if char.look:
                        char_desc += f", {char.look}"
                    positive_parts.append(char_desc)

            if vl.avoid:
                negative_parts.extend(vl.avoid)

            brand = brain.brand
            for rule in brand.rules:
                if rule.lower().startswith("no ") or rule.lower().startswith("never "):
                    negative_parts.append(rule)

        except Exception:
            pass

    positive = ", ".join(p for p in positive_parts if p)
    negative = ", ".join(n for n in negative_parts if n)
    return positive, negative


# ══════════════════════════════════════════════════════════════════════════
# Image renderer (SDXL Lightning — DreamShaper XL)
# ══════════════════════════════════════════════════════════════════════════
def render_comfyui_image(shot: dict, decision: dict) -> str:
    """Generate a still image via SDXL Lightning. ~3s. Returns output file path."""
    positive, negative = _enrich_prompt(shot, project=shot.get("_project"))
    shot_id = shot.get("shot_id", "shot")
    prefix = f"filmake_{shot_id}"

    width = 1024
    height = 432  # 2.37:1 anamorphic

    workflow = {
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": SDXL_CHECKPOINT}
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["4", 1]}
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["4", 1]}
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": hash(shot_id) & 0xFFFFFFFF,
                "steps": 6, "cfg": 1.8,
                "sampler_name": "dpmpp_sde", "scheduler": "karras",
                "denoise": 1.0,
                "model": ["4", 0], "positive": ["6", 0],
                "negative": ["7", 0], "latent_image": ["5", 0],
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]}
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": prefix, "images": ["8", 0]}
        },
    }

    prompt_id = _queue_prompt(workflow)
    entry = _poll_completion(prompt_id)
    outputs = _extract_outputs(entry)
    return outputs[0] if outputs else f"queued:{prompt_id}"


# ══════════════════════════════════════════════════════════════════════════
# Video renderer (Wan 2.1 T2V 1.3B)
# ══════════════════════════════════════════════════════════════════════════
def _build_wan_workflow(positive: str, negative: str, shot_id: str,
                        width: int = 832, height: int = 480,
                        num_frames: int = 41, steps: int = 20,
                        cfg: float = 6.0, shift: float = 5.0,
                        fps: float = 16.0, quality: int = 85,
                        prefix: str = "filmake") -> dict:
    """Build a Wan 2.1 T2V workflow dict for the ComfyUI API."""
    return {
        # 1. Load Wan 2.1 T2V 1.3B model
        "1": {
            "class_type": "WanVideoModelLoader",
            "inputs": {
                "model": WAN_MODEL,
                "base_precision": "bf16",
                "quantization": "disabled",
                "load_device": "main_device",
            }
        },
        # 2. Load VAE
        "2": {
            "class_type": "WanVideoVAELoader",
            "inputs": {
                "model_name": WAN_VAE,
                "precision": "bf16",
            }
        },
        # 3. Load UMT5-XXL text encoder
        "3": {
            "class_type": "LoadWanVideoT5TextEncoder",
            "inputs": {
                "model_name": WAN_T5,
                "precision": "bf16",
            }
        },
        # 4. Encode text (on CPU to save VRAM)
        "4": {
            "class_type": "WanVideoTextEncode",
            "inputs": {
                "positive_prompt": positive,
                "negative_prompt": negative,
                "t5": ["3", 0],
                "force_offload": True,
                "device": "cpu",
            }
        },
        # 5. Empty image embeds (text-to-video)
        "5": {
            "class_type": "WanVideoEmptyEmbeds",
            "inputs": {
                "width": width,
                "height": height,
                "num_frames": num_frames,
            }
        },
        # 6. Sample
        "6": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "model": ["1", 0],
                "image_embeds": ["5", 0],
                "text_embeds": ["4", 0],
                "steps": steps,
                "cfg": cfg,
                "shift": shift,
                "seed": hash(shot_id) & 0xFFFFFFFF,
                "force_offload": True,
                "scheduler": "unipc",
                "riflex_freq_index": 0,
            }
        },
        # 7. Decode with VAE tiling
        "7": {
            "class_type": "WanVideoDecode",
            "inputs": {
                "vae": ["2", 0],
                "samples": ["6", 0],
                "enable_vae_tiling": True,
                "tile_x": 272,
                "tile_y": 272,
                "tile_stride_x": 144,
                "tile_stride_y": 128,
            }
        },
        # 8. Save as animated WEBP
        "8": {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "filename_prefix": prefix,
                "fps": fps,
                "lossless": False,
                "quality": quality,
                "method": "default",
                "images": ["7", 0],
            }
        },
    }


def render_comfyui_wan(shot: dict, decision: dict) -> str:
    """Generate a video clip via Wan 2.1 T2V 1.3B.
    832×480, 41 frames (~2.5s at 16fps), ~170s render time.
    Falls back to keyframe image if Wan nodes aren't available.
    Returns output file path."""
    positive, negative = _enrich_prompt(shot, project=shot.get("_project"))
    shot_id = shot.get("shot_id", "shot")
    prefix = f"filmake_{shot_id}"

    # Check Wan nodes are available
    try:
        info = _api_get("/object_info")
        if "WanVideoModelLoader" not in info:
            print(f"[comfyui_renderer] Wan nodes not available, falling back to image for {shot_id}")
            return render_comfyui_image(shot, decision)
    except Exception:
        return render_comfyui_image(shot, decision)

    # Determine frame count from duration
    duration = float(shot.get("duration_seconds",
                               shot.get("spec", {}).get("duration_seconds", 2.5)))
    fps = 16.0
    # Wan frame count must be 4n+1
    target_frames = int(duration * fps)
    n = max(1, round((target_frames - 1) / 4))
    num_frames = 4 * n + 1
    num_frames = min(num_frames, 81)   # cap at ~5s
    num_frames = max(num_frames, 17)   # minimum ~1s

    workflow = _build_wan_workflow(
        positive=positive,
        negative=negative,
        shot_id=shot_id,
        width=832,
        height=480,
        num_frames=num_frames,
        steps=20,
        cfg=6.0,
        shift=5.0,
        fps=fps,
        quality=85,
        prefix=prefix,
    )

    prompt_id = _queue_prompt(workflow)
    entry = _poll_completion(prompt_id, timeout=POLL_TIMEOUT)
    outputs = _extract_outputs(entry)
    return outputs[0] if outputs else f"queued:{prompt_id}"


def render_wan_draft(shot: dict, decision: dict) -> str:
    """Draft-quality video via Wan 2.1 — fewer steps, smaller resolution.
    480×288, 25 frames (~1.5s), 10 steps. ~60-80s render time.
    Returns output file path."""
    positive, negative = _enrich_prompt(shot, project=shot.get("_project"))
    shot_id = shot.get("shot_id", "shot")
    prefix = f"filmake_draft_{shot_id}"

    try:
        info = _api_get("/object_info")
        if "WanVideoModelLoader" not in info:
            print(f"[comfyui_renderer] Wan nodes not available, falling back to image for {shot_id}")
            return render_comfyui_image(shot, decision)
    except Exception:
        return render_comfyui_image(shot, decision)

    duration = float(shot.get("duration_seconds",
                               shot.get("spec", {}).get("duration_seconds", 2)))
    fps = 16.0
    target_frames = int(duration * fps)
    n = max(1, round((target_frames - 1) / 4))
    num_frames = 4 * n + 1
    num_frames = min(num_frames, 41)
    num_frames = max(num_frames, 9)

    workflow = _build_wan_workflow(
        positive=positive,
        negative=negative,
        shot_id=shot_id,
        width=480,
        height=288,
        num_frames=num_frames,
        steps=10,
        cfg=6.0,
        shift=5.0,
        fps=fps,
        quality=75,
        prefix=prefix,
    )

    prompt_id = _queue_prompt(workflow)
    entry = _poll_completion(prompt_id, timeout=POLL_TIMEOUT)
    outputs = _extract_outputs(entry)
    return outputs[0] if outputs else f"queued:{prompt_id}"


# ══════════════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════════════
def register_all():
    """Register all ComfyUI renderers with dispatch.py."""
    register_renderer("comfyui_image", render_comfyui_image)
    register_renderer("comfyui_wan", render_comfyui_wan)
    register_renderer("ltx_video", render_wan_draft)
    print("[comfyui_renderer] Registered: comfyui_image → SDXL, comfyui_wan → Wan 2.1, ltx_video → Wan draft")


# Auto-register on import
register_all()
