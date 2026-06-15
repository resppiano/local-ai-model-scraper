"""
Fable API — Background Render Queue Worker
==========================================
Polls the database for queued render jobs and dispatches them to:
  • ComfyUI (local, free)
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

from .database import async_session, Shot, RenderJob, Asset
from .comfyui_client import ComfyUIClient
from .higgsfield_client import HiggsfieldClient


ASSETS_DIR = os.environ.get("FABLE_ASSETS_DIR", "/home/gregjones/FableAssets")


class RenderQueue:
    """Background worker that processes render jobs from the DB queue."""

    def __init__(self, poll_interval: float = 5.0):
        self.poll_interval = poll_interval
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.comfyui = ComfyUIClient()
        self.higgsfield = HiggsfieldClient()
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


if __name__ == "__main__":
    q = RenderQueue()
    asyncio.run(q.start())
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.run(q.stop())
