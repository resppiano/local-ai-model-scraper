"""
Fable API — ComfyUI Client
=========================
Wrapper around the local ComfyUI HTTP API.
"""

import json
import urllib.request
import urllib.error
from typing import Optional


COMFYUI_URL = "http://localhost:8188"


class ComfyUIClient:
    """Lightweight HTTP client for ComfyUI."""

    def _post(self, path: str, data: dict = None):
        url = f"{COMFYUI_URL}{path}"
        body = json.dumps(data).encode() if data else b"{}"
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _get(self, path: str):
        url = f"{COMFYUI_URL}{path}"
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
        # Minimal workflow: Load Checkpoint → CLIP Text Encode → KSampler → Save Image
        # NOTE: You will need to customize node IDs to match your ComfyUI setup.
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 42,
                    "steps": steps,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
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
                "inputs": {
                    "text": negative_prompt or "",
                    "clip": ["1", 1],
                },
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "fable_", "images": ["5", 0]},
            },
        }

        resp = self.queue_prompt(workflow)
        prompt_id = resp.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {resp}")

        # Poll history until done
        import time
        for _ in range(120):
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
                        url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                        local = f"/home/gregjones/ComfyUI/output/{subfolder}/{filename}" if subfolder else f"/home/gregjones/ComfyUI/output/{filename}"
                        return {
                            "url": url,
                            "local_path": local,
                            "width": width,
                            "height": height,
                        }
        raise RuntimeError("ComfyUI render timed out")
