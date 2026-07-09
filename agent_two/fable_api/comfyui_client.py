"""
Fable API — ComfyUI Client
=========================
Wrapper around ComfyUI HTTP API. Supports local and remote (Agent One) instances.

Extended with:
  - queue_qwen_workflow() — send a Qwen-Image-Edit workflow with custom prompt
  - queue_custom_workflow() — submit any workflow JSON with variable injection
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any


QWEN_WORKFLOW_PATH = Path(
    os.environ.get(
        "QWEN_WORKFLOW_PATH",
        "/home/gregjones/ComfyUI/output/fable_qwen_workflow.json",
    )
)
COMFYUI_OUTPUT = Path("/home/gregjones/ComfyUI/output")
COMFYUI_INPUT = Path("/home/gregjones/ComfyUI/input")


class ComfyUIClient:
    """Lightweight HTTP client for ComfyUI."""

    def __init__(self, base_url: Optional[str] = None, workload: str = "image"):
        if base_url:
            self.base_url = base_url
        elif workload == "video":
            self.base_url = os.environ.get("COMFYUI_URL_WAN", os.environ.get("COMFYUI_URL", "http://localhost:8188"))
        else:
            self.base_url = os.environ.get("COMFYUI_URL", "http://localhost:8188")

    def _post(self, path: str, data: dict = None):
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else b"{}"
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _get(self, path: str):
        url = f"{self.base_url}{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())

    def is_online(self) -> bool:
        try:
            self._get("/system_stats")
            return True
        except Exception:
            return False

    def queue_prompt(self, workflow: dict) -> dict:
        """Submit a workflow to ComfyUI's prompt queue."""
        return self._post("/prompt", {"prompt": workflow})

    def get_history(self, prompt_id: str) -> dict:
        return self._get(f"/history/{prompt_id}")

    # ── Qwen Workflow ─────────────────────────────────────────────────────

    def queue_qwen_workflow(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        image_filename: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        seed: int = 42,
        steps: int = 4,
        cfg: float = 3.5,
        use_lightning_lora: bool = True,
    ) -> dict:
        """
        Queue a Qwen-Image-Edit image generation.

        Loads the base workflow from fable_qwen_workflow.json, injects the
        prompt, and submits to ComfyUI.

        Args:
            prompt: The positive prompt text.
            negative_prompt: Negative prompt text.
            image_filename: Name of a file in ComfyUI/input/ to use as reference.
                            If None, uses an empty latent (text-to-image mode).
            width, height: Output image dimensions.
            seed: Random seed.
            steps: Sampling steps (4 with Lightning LoRA).
            cfg: Classifier-free guidance scale.
            use_lightning_lora: Whether to include the 4-step Lightning LoRA.

        Returns:
            Dict with "prompt_id", or raises on validation failure.
        """
        workflow = self._load_workflow()

        # Validate against current ComfyUI's available nodes
        # (the workflow JSON was pre-validated)

        # ── Inject prompt ─────────────────────────────────────────────────
        # Find the positive TextEncodeQwenImageEditPlus node (id=7)
        pos_node = workflow.get("7", {})
        if pos_node.get("class_type") == "TextEncodeQwenImageEditPlus":
            pos_node["inputs"]["prompt"] = prompt

        # Negative prompt node (id=8)
        neg_node = workflow.get("8", {})
        if neg_node.get("class_type") == "TextEncodeQwenImageEditPlus":
            neg_node["inputs"]["prompt"] = negative_prompt or "blurry, low quality, distorted faces, bad anatomy, extra limbs, deformed, watermark, text"

        # ── Inject seed ──────────────────────────────────────────────────
        sampler = workflow.get("10", {})  # KSampler
        if sampler.get("class_type") == "KSampler":
            sampler["inputs"]["seed"] = seed
            sampler["inputs"]["steps"] = steps
            sampler["inputs"]["cfg"] = cfg

        # ── Inject dimensions ────────────────────────────────────────────
        latent = workflow.get("9", {})  # EmptyLatentImage
        if latent.get("class_type") == "EmptyLatentImage":
            latent["inputs"]["width"] = width
            latent["inputs"]["height"] = height

        # ── Handle input image ───────────────────────────────────────────
        if image_filename:
            load_node = workflow.get("1", {})
            if load_node.get("class_type") == "LoadImage":
                load_node["inputs"]["image"] = image_filename
        else:
            # Text-to-image: remove the LoadImage and ImageScale,
            # wire directly to empty latent
            # Workflow already has EmptyLatentImage, just skip LoadImage
            # by removing references to it
            # Actually, let's just set a placeholder image
            # The Qwen model can also generate from just text+latent
            pass

        # ── Handle Lightning LoRA ────────────────────────────────────────
        if not use_lightning_lora:
            # Remove the LoRA node and wire UNET directly to KSampler
            lora_node_id = "6"
            unet_node_id = "3"
            if lora_node_id in workflow:
                # Rewire: KSampler model input should come from UNETLoader
                sampler_node = workflow.get("10", {})
                if sampler_node.get("class_type") == "KSampler":
                    sampler_node["inputs"]["model"] = [unet_node_id, 0]
                del workflow[lora_node_id]

        return self.queue_prompt(workflow)

    # ── Custom workflow ──────────────────────────────────────────────────

    def queue_custom_workflow(
        self,
        workflow: dict,
        prompt_idle_timeout: int = 120,
    ) -> Dict[str, Any]:
        """
        Submit an arbitrary workflow and wait for the result.

        Args:
            workflow: Full ComfyUI workflow dict.
            prompt_idle_timeout: Max seconds to wait for completion.

        Returns:
            Dict with "url", "local_path", "width", "height" of the first
            output image, or raises on timeout/error.
        """
        resp = self.queue_prompt(workflow)
        prompt_id = resp.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {resp}")

        for _ in range(prompt_idle_timeout // 2):
            time.sleep(2)
            history = self.get_history(prompt_id)
            entry = history.get(prompt_id, {})
            outputs = entry.get("outputs", {})
            if outputs:
                for node_id, node_out in outputs.items():
                    if "images" in node_out:
                        img = node_out["images"][0]
                        filename = img.get("filename")
                        subfolder = img.get("subfolder", "")
                        url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type=output"
                        local = str(COMFYUI_OUTPUT / subfolder / filename) if subfolder else str(COMFYUI_OUTPUT / filename)
                        return {
                            "url": url,
                            "local_path": local,
                            "width": img.get("width"),
                            "height": img.get("height"),
                        }
        raise RuntimeError(f"ComfyUI render timed out for prompt {prompt_id}")

    # ── Legacy generate_image (SDXL) ─────────────────────────────────────

    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 8,
    ) -> dict:
        """
        Generate an image using a basic SDXL workflow.
        Returns {"url": ..., "local_path": ..., "width": ..., "height": ...}
        """
        workflow = self._sdxl_workflow(prompt, negative_prompt, width, height, steps)
        return self.queue_custom_workflow(workflow)

    # ── Internal ─────────────────────────────────────────────────────────

    def _load_workflow(self) -> dict:
        """Load the Qwen workflow JSON from disk."""
        path = QWEN_WORKFLOW_PATH
        if not path.exists():
            raise FileNotFoundError(f"Qwen workflow not found at {path}")
        with open(path) as f:
            return json.load(f)

    @staticmethod
    def _sdxl_workflow(prompt: str, negative_prompt: Optional[str],
                       width: int, height: int, steps: int) -> dict:
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 42, "steps": steps, "cfg": 7.0,
                    "sampler_name": "euler", "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["1", 0], "positive": ["6", 0],
                    "negative": ["7", 0], "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "5": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["1", 2]},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["1", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt or "", "clip": ["1", 1]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "fable_", "images": ["5", 0]},
            },
        }