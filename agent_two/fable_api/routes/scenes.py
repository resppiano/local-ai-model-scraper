"""
Scene Routes
============
CRUD + panel creation + generate-all for scenes.
Mounted under /scenes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db, Scene, Panel, RenderJob
from ..schemas import SceneUpdate, SceneOut, PanelCreate, PanelOut

router = APIRouter(prefix="/scenes", tags=["scenes"])


async def _get_scene(scene_id: int, db: AsyncSession) -> Scene:
    stmt = (
        select(Scene)
        .where(Scene.id == scene_id)
        .options(selectinload(Scene.panels))
    )
    result = await db.execute(stmt)
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(404, "Scene not found")
    return scene


async def _scene_to_out(scene: Scene) -> SceneOut:
    data = {c.name: getattr(scene, c.name) for c in scene.__table__.columns}
    data["panels"] = [
        PanelOut.model_validate(p) for p in (scene.panels or [])
    ]
    return SceneOut(**data)


# ── PATCH /scenes/{id} ───────────────────────────────────────────────────
@router.patch("/{scene_id}", response_model=SceneOut)
async def update_scene(
    scene_id: int,
    data: SceneUpdate,
    db: AsyncSession = Depends(get_db),
):
    scene = await _get_scene(scene_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(scene, field, value)
    await db.commit()
    await db.refresh(scene)
    return await _scene_to_out(scene)


# ── DELETE /scenes/{id} ──────────────────────────────────────────────────
@router.delete("/{scene_id}", status_code=204)
async def delete_scene(
    scene_id: int,
    db: AsyncSession = Depends(get_db),
):
    scene = await _get_scene(scene_id, db)
    await db.delete(scene)
    await db.commit()
    return


# ── POST /scenes/{id}/panels ─────────────────────────────────────────────
@router.post("/{scene_id}/panels", response_model=PanelOut, status_code=201)
async def create_panel(
    scene_id: int,
    data: PanelCreate,
    db: AsyncSession = Depends(get_db),
):
    scene = await _get_scene(scene_id, db)
    panel = Panel(scene_id=scene_id, **data.model_dump())
    db.add(panel)
    await db.commit()
    await db.refresh(panel)
    return PanelOut.model_validate(panel)


# ── POST /scenes/{id}/generate-all ──────────────────────────────────────
@router.post("/{scene_id}/generate-all")
async def generate_all_panels(
    scene_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Queue renders for all panels in a scene."""
    scene = await _get_scene(scene_id, db)

    if not scene.panels:
        raise HTTPException(400, "Scene has no panels to generate")

    queued = 0
    for panel in scene.panels:
        if panel.status not in ("done", "rendering"):
            panel.status = "queued"
            queued += 1

    await db.commit()
    return {
        "message": f"Queued {queued} panels for rendering",
        "panels_queued": queued,
        "total_panels": len(scene.panels),
    }