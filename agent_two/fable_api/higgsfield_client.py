"""
Fable API — Higgsfield Cloud Client
===================================
Thin wrapper around the Higgsfield MCP client for cloud rendering.
"""

import os
import sys
import time
from typing import Optional

# Import the official Higgsfield client
_HFClient = None
try:
    sys.path.insert(0, "/home/linuxbrew/.linuxbrew/lib/node_modules/higgsfield-mcp/src")
    from client import HiggsfieldClient as _HFClient
except Exception:
    pass


class HiggsfieldClient:
    """Cloud render client using the official Higgsfield MCP package."""

    def __init__(self):
        self.api_key = os.environ.get("HF_API_KEY")
        self.secret = os.environ.get("HF_SECRET")
        self._client = None
        if _HFClient and self.api_key and self.secret:
            self._client = _HFClient(self.api_key, self.secret)

    def has_credentials(self) -> bool:
        return self._client is not None

    def generate_image(
        self,
        prompt: str,
        quality: str = "1080p",
        character_id: Optional[str] = None,
        style_id: Optional[str] = None,
    ) -> dict:
        """Submit an image generation job. Returns {request_id/job_set_id, ...}"""
        if not self._client:
            raise RuntimeError("Higgsfield not initialized")

        result = self._client.generateImage(
            prompt=prompt,
            quality=quality,
            customReferenceId=character_id,
            styleId=style_id,
            enhancePrompt=True,
        )
        # result is a dict from the old API
        return {
            "job_set_id": result.get("id"),
            "type": result.get("type"),
            "status_url": f"https://platform.higgsfield.ai/v1/job-sets/{result.get('id')}",
        }

    def generate_video(
        self,
        prompt: str,
        image_url: Optional[str] = None,
        motion_id: Optional[str] = None,
        model: str = "dop-preview",
    ) -> dict:
        """Submit a video generation job."""
        if not self._client:
            raise RuntimeError("Higgsfield not initialized")

        # If no image_url provided, generate one first (Higgsfield requires an image)
        if not image_url:
            img_result = self._client.generateImage(
                prompt=prompt,
                quality="1080p",
                enhancePrompt=True,
            )
            # Wait for image, then use it
            img_id = img_result.get("id")
            for _ in range(30):
                status = self._client.getJobResults(img_id)
                if status.get("status") == "completed":
                    images = status.get("images", [])
                    if images:
                        image_url = images[0].get("url")
                        break
                time.sleep(5)
            if not image_url:
                raise RuntimeError("Could not generate source image for video")

        result = self._client.generateVideo(
            imageUrl=image_url,
            motionId=motion_id or "camera_orbit",
            prompt=prompt,
            model=model,
        )
        return {
            "request_id": result.get("request_id"),
            "status_url": f"https://platform.higgsfield.ai/requests/{result.get('request_id')}/status",
        }

    def poll_until_done(self, external_id: str, asset_type: str) -> dict:
        """Block until the job is done. Returns final result dict."""
        if not self._client:
            raise RuntimeError("Higgsfield not initialized")

        if asset_type == "image":
            # Old API uses job_set_id
            for _ in range(60):
                status = self._client.getJobResults(external_id)
                s = status.get("status")
                if s == "completed":
                    images = status.get("images", status.get("output_images", []))
                    if images:
                        return {
                            "url": images[0].get("url"),
                            "width": images[0].get("width", 1024),
                            "height": images[0].get("height", 1024),
                        }
                    return {"url": "", "width": None, "height": None}
                if s in ("failed", "nsfw", "cancelled"):
                    raise RuntimeError(f"Higgsfield job failed: {s}")
                time.sleep(5)
        else:
            # New unified API for video
            for _ in range(120):
                status = self._client.getRequestStatus(external_id)
                s = status.get("status")
                if s == "completed":
                    video = status.get("video", status.get("output_video", {}))
                    return {
                        "url": video.get("url", "") if isinstance(video, dict) else str(video),
                        "duration": video.get("duration") if isinstance(video, dict) else None,
                    }
                if s in ("failed", "nsfw", "cancelled"):
                    raise RuntimeError(f"Higgsfield job failed: {s}")
                time.sleep(8)

        raise RuntimeError("Higgsfield render timed out")
