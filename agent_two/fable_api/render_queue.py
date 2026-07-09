"""
Fable API — Background Render Queue Worker
==========================================
Polls the database for queued render jobs and dispatches them to:
  • ComfyUI (local, free)
  • Infer (cloud, $49/mo flat — video, image, audio)
  • Higgsfield (cloud, paid)

Run standalone:
    python -m fable_api.render_queue
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import async_session, Shot, RenderJob, Asset, Panel
from .comfyui_client import ComfyUIClient
from .higgsfield_client import HiggsfieldClient
from .services.infer_client import InferClient, InferError


ASSETS_DIR = os.environ.get("FABLE_ASSETS_DIR", "/home/gregjones/FableAssets")


class RenderQueue:
    """Background worker that processes render jobs from the DB queue."""

    def __init__(self, poll_interval: float = 5.0):
        self.poll_interval = poll_interval
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.comfyui = ComfyUIClient()
        self.higgsfield = HiggsfieldClient()
        self.infer = None  # lazy init
        os.makedirs(ASSETS_DIR, exist_ok=True)

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def submit(self, job_id: int):
        """Trigger immediate processing of a specific job (called by FastAPI)."""
        asyncio.create_task(self._process_job(job_id))

    async def _loop(self):
        """Continuously poll for queued jobs."""
        while self.running:
            try:
                await self._poll_queue()
            except Exception as e:
                print(f"[RenderQueue] poll error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def _poll_queue(self):
        async with async_session() as db:
            stmt = (
                select(RenderJob)
                .where(RenderJob.status.in_(["queued", "running"]))
                .order_by(RenderJob.created_at)
                .limit(5)
            )
            result = await db.execute(stmt)
            jobs = result.scalars().all()
            for job in jobs:
                await self._process_job(job.id)

    async def _process_job(self, job_id: int):
        async with async_session() as db:
            job = await db.scalar(select(RenderJob).where(RenderJob.id == job_id))
            if not job or job.status not in ("queued", "running"):
                return

            # Mark running
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Fetch shot details
            shot = await db.scalar(select(Shot).where(Shot.id == job.shot_id))
            if not shot:
                job.status = "failed"
                job.error_message = "Shot not found"
                await db.commit()
                return

            try:
                if job.provider == "comfyui":
                    asset = await self._render_comfyui(db, shot)
                elif job.provider == "higgsfield":
                    asset = await self._render_higgsfield(db, shot, job)
                else:
                    raise ValueError(f"Unknown provider: {job.provider}")

                # Success
                shot.status = "done"
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                print(f"[RenderQueue] Job {job_id} completed → asset {asset.id}")

            except Exception as e:
                shot.status = "failed"
                job.status = "failed"
                job.error_message = str(e)
                await db.commit()
                print(f"[RenderQueue] Job {job_id} failed: {e}")

    async def _render_comfyui(self, db: AsyncSession, shot: Shot) -> Asset:
        """Dispatch to local ComfyUI. Returns Asset on success."""
        prompt = shot.prompt or ""
        # Call ComfyUI
        result = await self.comfyui.generate_image(prompt, shot.negative_prompt)
        output_url = result.get("url")
        local_path = result.get("local_path")

        asset = Asset(
            project_id=shot.project_id,
            shot_id=shot.id,
            type="image",
            url=output_url or "",
            local_path=local_path,
            provider="comfyui",
            width=result.get("width"),
            height=result.get("height"),
            meta=json.dumps(result),
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return asset

    async def _render_higgsfield(self, db: AsyncSession, shot: Shot, job: RenderJob) -> Asset:
        """Dispatch to Higgsfield cloud. Returns Asset on success."""
        # Check credentials
        if not self.higgsfield.has_credentials():
            raise RuntimeError("Higgsfield credentials not configured")

        # Submit
        if shot.motion_prompt:
            # Video
            result = await self.higgsfield.generate_video(
                prompt=shot.prompt or "",
                motion_prompt=shot.motion_prompt,
                model=job.render_model or "dop-preview",
            )
            asset_type = "video"
        else:
            # Image
            result = await self.higgsfield.generate_image(
                prompt=shot.prompt or "",
                quality=job.render_model or "1080p",
            )
            asset_type = "image"

        # Poll until complete (synchronous block — run in thread)
        external_id = result.get("request_id") or result.get("job_set_id")
        final = await self._poll_higgsfield(external_id, asset_type)

        asset = Asset(
            project_id=shot.project_id,
            shot_id=shot.id,
            type=asset_type,
            url=final.get("url", ""),
            provider="higgsfield",
            width=final.get("width"),
            height=final.get("height"),
            duration=final.get("duration"),
            meta=json.dumps(final),
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        return asset

    async def _poll_higgsfield(self, external_id: str, asset_type: str) -> dict:
        """Poll Higgsfield for completion. Run in executor since it blocks."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.higgsfield.poll_until_done, external_id, asset_type
        )


# ── Panel render helper (called from panels.py background task) ──────────


async def render_panel_comfyui(
    panel_id: int,
    project_id: int,
    ltx_prompt: str,
    image_filename: Optional[str] = None,
    db_session=None,
):
    """
    Standalone background task: render a panel using the Qwen workflow.

    If the panel has a driving_video_asset_id, the control video is
    available for downstream use (e.g., LTX video conditioning).

    Called from the panels generate endpoint.
    Runs its own DB session and ComfyUI client.
    """
    from .database import async_session
    from .comfyui_client import ComfyUIClient
    from sqlalchemy import select
    from .database import Panel, Asset

    client = ComfyUIClient()

    async with async_session() as db:
        try:
            # ── Load panel + driving video ────────────────────────────────
            panel = await db.scalar(select(Panel).where(Panel.id == panel_id))
            driving_video_url = None
            if panel and panel.driving_video_asset_id:
                dv = await db.scalar(
                    select(Asset).where(Asset.id == panel.driving_video_asset_id)
                )
                if dv:
                    driving_video_url = dv.url
                    print(f"[render_panel] Panel {panel_id} has driving video: {dv.url}")

            # Submit to Qwen workflow
            result = client.queue_qwen_workflow(
                prompt=ltx_prompt,
                image_filename=image_filename,
            )

            # Wait for completion
            prompt_id = result.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"No prompt_id returned: {result}")

            import time
            output = None
            for _ in range(60):  # 2 min timeout
                time.sleep(2)
                history = client.get_history(prompt_id)
                entry = history.get(prompt_id, {})
                outputs = entry.get("outputs", {})
                if outputs:
                    for node_id, node_out in outputs.items():
                        if "images" in node_out:
                            img = node_out["images"][0]
                            filename = img.get("filename")
                            subfolder = img.get("subfolder", "")
                            url = f"{client.base_url}/view?filename={filename}&subfolder={subfolder}&type=output"
                            local = (
                                f"/home/gregjones/ComfyUI/output/{subfolder}/{filename}"
                                if subfolder
                                else f"/home/gregjones/ComfyUI/output/{filename}"
                            )
                            output = {
                                "url": url,
                                "local_path": local,
                                "width": img.get("width"),
                                "height": img.get("height"),
                            }
                            break
                    if output:
                        break

            if not output:
                raise RuntimeError("ComfyUI render timed out")

            # Create asset
            asset = Asset(
                project_id=project_id,
                type="image",
                url=output["url"],
                local_path=output["local_path"],
                provider="comfyui",
                width=output.get("width"),
                height=output.get("height"),
                meta=json.dumps(output),
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)

            # Update panel
            panel = await db.scalar(
                select(Panel).where(Panel.id == panel_id)
            )
            if panel:
                panel.status = "done"
                panel.thumbnail_url = output["url"]
                panel.output_path = output["local_path"]
                panel.updated_at = datetime.now(timezone.utc)
                await db.commit()

            print(f"[render_panel] Panel {panel_id} completed → asset {asset.id}")

        except Exception as e:
            print(f"[render_panel] Panel {panel_id} failed: {e}")
            try:
                panel = await db.scalar(
                    select(Panel).where(Panel.id == panel_id)
                )
                if panel:
                    panel.status = "failed"
                    panel.updated_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass


# ── Infer render backend ──────────────────────────────────────────────────


async def render_panel_infer(
    panel_id: int,
    project_id: int,
    ltx_prompt: str,
    image_url: Optional[str] = None,
    model: str = "seedance-2.0-fast",
    db_session=None,
):
    """
    Standalone background task: render a panel using the Infer API.

    Instead of local ComfyUI, this sends the prompt to Infer's cloud
    API for video generation. Supports text-to-video and image-to-video.

    Requires INFER_API_KEY in environment or .hermes/.env.
    """
    from .database import async_session
    from .services.infer_client import InferClient, InferError
    from sqlalchemy import select
    from .database import Panel, Asset

    try:
        client = InferClient()
    except InferError as e:
        print(f"[render_panel_infer] No Infer API key: {e}")
        async with async_session() as db:
            panel = await db.scalar(select(Panel).where(Panel.id == panel_id))
            if panel:
                panel.status = "failed"
                panel.updated_at = datetime.now(timezone.utc)
                await db.commit()
        return

    async with async_session() as db:
        try:
            # Submit to Infer
            def _render():
                if image_url:
                    return client.image_to_video(
                        image_url=image_url,
                        prompt=ltx_prompt,
                        model=model,
                    )
                else:
                    return client.text_to_video(
                        prompt=ltx_prompt,
                        model=model,
                    )

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _render)

            # Extract output URL
            output = result.get("output", {})
            video_url = (output.get("video_url") or output.get("url")
                         or output.get("output_url"))

            if not video_url:
                raise RuntimeError(f"Infer returned no video URL: {result}")

            # Create asset
            asset = Asset(
                project_id=project_id,
                type="video",
                url=video_url,
                local_path=None,
                provider=f"infer:{model}",
                meta=json.dumps(result),
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)

            # Update panel
            panel = await db.scalar(select(Panel).where(Panel.id == panel_id))
            if panel:
                panel.status = "done"
                panel.image_url = video_url
                panel.updated_at = datetime.now(timezone.utc)
                await db.commit()

            print(f"[render_panel_infer] Panel {panel_id} completed via {model} → asset {asset.id}")

        except Exception as e:
            print(f"[render_panel_infer] Panel {panel_id} failed: {e}")
            try:
                panel = await db.scalar(select(Panel).where(Panel.id == panel_id))
                if panel:
                    panel.status = "failed"
                    panel.updated_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass


# ── Voice generation via Infer ────────────────────────────────────────────


async def generate_voice_infer(
    project_id: int,
    text: str,
    voice: str = "default",
    model: str = "eleven-v3",
) -> Optional[str]:
    """
    Generate voice audio via Infer's text-to-speech.

    Returns the audio URL on success, None on failure.
    """
    from .services.infer_client import InferClient, InferError
    from .database import async_session
    from .database import Asset

    try:
        client = InferClient()
    except InferError:
        return None

    def _generate():
        return client.text_to_speech(text=text, model=model, voice=voice)

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _generate)
        output = result.get("output", {})
        audio_url = (output.get("audio_url") or output.get("url")
                     or output.get("output_url"))
        if not audio_url:
            return None

        # Store as asset
        async with async_session() as db:
            asset = Asset(
                project_id=project_id,
                type="audio",
                url=audio_url,
                local_path=None,
                provider=f"infer:{model}",
                meta=json.dumps(result),
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)
            print(f"[generate_voice_infer] Voice created → asset {asset.id}")
            return audio_url

    except Exception as e:
        print(f"[generate_voice_infer] Failed: {e}")
        return None


if __name__ == "__main__":
    q = RenderQueue()
    asyncio.run(q.start())
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.run(q.stop())
