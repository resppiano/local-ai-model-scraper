"""
Infer API Client
================
Unified Python client for tryinfer.com — video, image, and audio generation
through a single API. $49/mo flat rate.

API pattern:
  POST https://api.tryinfer.com/v1/inference/{model_id}/{task}
    → {"request_id": "..."}
  GET  https://api.tryinfer.com/v1/inference/requests/{request_id}
    → {"status": "COMPLETED|FAILED|CANCELLED", "output": {...}}

Usage:
    client = InferClient(api_key="sk-...")
    
    # Video generation
    req = client.submit("seedance-2.0-fast", "text-to-video", {
        "prompt": "a cinematic scene...",
        "duration_seconds": "5",
        "aspect_ratio": "16:9"
    })
    result = client.poll_until_done(req["request_id"])
    
    # Image generation
    req = client.submit("flux-2", "text-to-image", {
        "prompt": "a character portrait...",
        "n": 4
    })
    
    # Voice generation
    req = client.submit("eleven-v3", "text-to-speech", {
        "text": "Hello world",
    })
"""
import json
import os
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

BASE_URL = "https://api.tryinfer.com/v1/inference"
DEFAULT_TIMEOUT = 300  # 5 min max for long video renders
POLL_INTERVAL = 2.0    # seconds between polls
MAX_POLLS = 600        # 600 * 2s = 20 min ceiling


class InferError(Exception):
    """API-level error from Infer."""
    pass


class InferClient:
    """
    Client for the Infer API (video, image, audio generation).

    Args:
        api_key: Bearer token. Falls back to INFER_API_KEY env var.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("INFER_API_KEY")
        if not self.api_key:
            raise InferError(
                "No Infer API key. Pass api_key= or set INFER_API_KEY env var."
            )

    # ── Public API ──────────────────────────────────────────────────────

    def submit(self, model_id: str, task: str, input_data: Dict[str, Any],
               timeout: int = 30) -> Dict[str, Any]:
        """
        Submit an inference job to Infer.

        Args:
            model_id: e.g. "seedance-2.0-fast", "ltx-2.3", "flux-2", "eleven-v3"
            task: e.g. "text-to-video", "image-to-video", "text-to-image",
                  "text-to-speech"
            input_data: Dict of input parameters for the model.
            timeout: Request timeout in seconds.

        Returns:
            {"request_id": "..."}

        Raises:
            InferError: On API error (auth, validation, upstream).
        """
        url = f"{BASE_URL}/{model_id}/{task}"
        payload = json.dumps({"input": input_data}).encode()

        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            msg = f"Infer API error: HTTP {e.code}"
            try:
                err = json.loads(body)
                msg += f" — {err.get('error', {}).get('message', body)}"
            except json.JSONDecodeError:
                msg += f" — {body}"
            raise InferError(msg) from e
        except urllib.error.URLError as e:
            raise InferError(f"Infer API unreachable: {e.reason}") from e

    def get_status(self, request_id: str) -> Dict[str, Any]:
        """
        Poll the status of an inference request.

        Returns:
            Dict with keys: request_id, status, output (optional), error (optional)
        """
        url = f"{BASE_URL}/requests/{request_id}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise InferError(
                f"Poll failed: HTTP {e.code} — {e.read().decode()[:200]}"
            ) from e

    def poll_until_done(
        self, request_id: str,
        poll_interval: float = POLL_INTERVAL,
        max_polls: int = MAX_POLLS,
    ) -> Dict[str, Any]:
        """
        Poll until COMPLETED, FAILED, or CANCELLED.

        Args:
            request_id: From submit().
            poll_interval: Seconds between polls.
            max_polls: Max number of polls before timeout.

        Returns:
            Full status dict with output (on success) or error (on failure).
        """
        for _ in range(max_polls):
            status = self.get_status(request_id)
            state = status.get("status", "UNKNOWN")

            if state == "COMPLETED":
                return status
            elif state in ("FAILED", "CANCELLED"):
                err = status.get("error", {}).get("message", "Unknown error")
                raise InferError(
                    f"Infer job {request_id} {state}: {err}"
                )

            time.sleep(poll_interval)

        raise InferError(
            f"Infer job {request_id} timed out after "
            f"{poll_interval * max_polls:.0f}s"
        )

    # ── High-level convenience methods ───────────────────────────────────

    def text_to_video(
        self, prompt: str,
        model: str = "seedance-2.0-fast",
        duration_seconds: str = "5",
        aspect_ratio: str = "16:9",
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate video from text prompt. Returns the completed output."""
        input_data = {
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "aspect_ratio": aspect_ratio,
            **kwargs,
        }
        req = self.submit(model, "text-to-video", input_data)
        return self.poll_until_done(req["request_id"])

    def image_to_video(
        self, image_url: str, prompt: str,
        model: str = "ltx-2.3",
        duration_seconds: str = "5",
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate video from image + text prompt."""
        input_data = {
            "image_url": image_url,
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            **kwargs,
        }
        req = self.submit(model, "image-to-video", input_data)
        return self.poll_until_done(req["request_id"])

    def text_to_image(
        self, prompt: str,
        model: str = "flux-2",
        n: int = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate image(s) from text prompt."""
        input_data = {"prompt": prompt, "n": n, **kwargs}
        req = self.submit(model, "text-to-image", input_data)
        return self.poll_until_done(req["request_id"])

    def image_to_image(
        self, image_url: str, prompt: str,
        model: str = "flux-2",
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate image from image + text."""
        input_data = {"image_url": image_url, "prompt": prompt, **kwargs}
        req = self.submit(model, "image-to-image", input_data)
        return self.poll_until_done(req["request_id"])

    def text_to_speech(
        self, text: str,
        model: str = "eleven-v3",
        voice: str = "default",
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate audio speech from text."""
        input_data = {"text": text, "voice": voice, **kwargs}
        req = self.submit(model, "text-to-speech", input_data)
        return self.poll_until_done(req["request_id"])


# ── Model registry ──────────────────────────────────────────────────────

MODEL_REGISTRY = {
    # Video generation
    "seedance-2.0-fast": {"tasks": ["text-to-video", "image-to-video"], "provider": "ByteDance"},
    "seedance-2.0": {"tasks": ["text-to-video", "image-to-video"], "provider": "ByteDance"},
    "ltx-2.3": {"tasks": ["text-to-video", "image-to-video"], "provider": "Lightricks"},
    "kling-3-pro": {"tasks": ["text-to-video", "image-to-video"], "provider": "Kuaishou"},
    "kling-3": {"tasks": ["text-to-video", "image-to-video"], "provider": "Kuaishou"},
    "happyhorse-1.0": {"tasks": ["text-to-video", "image-to-video"], "provider": "Alibaba"},
    "sam3": {"tasks": ["text-to-video"], "provider": "Meta"},
    "uni-1": {"tasks": ["text-to-video"], "provider": "Luma Labs"},
    # Image generation
    "flux-2": {"tasks": ["text-to-image", "image-to-image"], "provider": "Black Forest Labs"},
    "gpt-image-2": {"tasks": ["text-to-image", "image-to-image"], "provider": "OpenAI"},
    "ideogram-4": {"tasks": ["text-to-image", "image-to-image"], "provider": "Ideogram"},
    "nano-banana-2.0": {"tasks": ["text-to-image"], "provider": "Unknown"},
    # Audio / voice
    "eleven-v3": {"tasks": ["text-to-speech"], "provider": "Eleven Labs"},
    # Chat / text
    "qwen3.6-flash": {"tasks": ["chat"], "provider": "Alibaba/DashScope"},
    "qwen3.7-max-preview": {"tasks": ["chat"], "provider": "Alibaba/DashScope"},
}


def list_models() -> Dict[str, Dict]:
    """Return the model registry grouped by capability."""
    by_capability = {"video": {}, "image": {}, "audio": {}, "chat": {}}
    for mid, info in MODEL_REGISTRY.items():
        tasks = info["tasks"]
        if any(t in tasks for t in ["text-to-video", "image-to-video"]):
            by_capability["video"][mid] = info
        if any(t in tasks for t in ["text-to-image", "image-to-image"]):
            by_capability["image"][mid] = info
        if any(t in tasks for t in ["text-to-speech"]):
            by_capability["audio"][mid] = info
        if "chat" in tasks:
            by_capability["chat"][mid] = info
    return by_capability