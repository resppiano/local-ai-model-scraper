"""
Panel Routes
============
CRUD + generate for individual panels.
Mounted under /panels.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db, Panel, Scene, Script, Project, Character, Asset
from ..schemas import PanelUpdate, PanelOut
from ..services.prompt_builder import generate_panel_ltx_prompt, build_panel_prompt_fallback

router = APIRouter(prefix="/panels", tags=["panels"])


async def _get_panel(panel_id: int, db: AsyncSession) -> Panel:
    stmt = select(Panel).where(Panel.id == panel_id)
    result = await db.execute(stmt)
    panel = result.scalar_one_or_none()
    if not panel:
        raise HTTPException(404, "Panel not found")
    return panel


async def _lookup_characters(db: AsyncSession, character_ids: list[int]):
    """Fetch character name + description for given IDs."""
    stmt = select(Character).where(Character.id.in_(character_ids))
    result = await db.execute(stmt)
    chars = result.scalars().all()
    return [
        {"name": c.name, "description": c.description, "reference_image_url": c.reference_image_url}
        for c in chars
    ]


# ── GET /panels/{id} ─────────────────────────────────────────────────────
@router.get("/{panel_id}", response_model=PanelOut)
async def get_panel(panel_id: int, db: AsyncSession = Depends(get_db)):
    panel = await _get_panel(panel_id, db)
    return PanelOut.model_validate(panel)


# ── PATCH /panels/{id} ────────────────────────────────────────────────────
@router.patch("/{panel_id}", response_model=PanelOut)
async def update_panel(
    panel_id: int,
    data: PanelUpdate,
    db: AsyncSession = Depends(get_db),
):
    panel = await _get_panel(panel_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(panel, field, value)
    panel.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(panel)
    return PanelOut.model_validate(panel)


# ── DELETE /panels/{id} ───────────────────────────────────────────────────
@router.delete("/{panel_id}", status_code=204)
async def delete_panel(
    panel_id: int,
    db: AsyncSession = Depends(get_db),
):
    panel = await _get_panel(panel_id, db)
    await db.delete(panel)
    await db.commit()
    return


# ── POST /panels/{id}/generate ────────────────────────────────────────────
@router.post("/{panel_id}/generate", status_code=202)
async def generate_panel(
    panel_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Queue a render for a single panel using the LTX 2.3 pipeline.

    Steps:
      1. Load panel + scene + script + project + characters
      2. Generate structured LTX prompt (via LLM or template fallback)
      3. Store in panel.auto_prompt
      4. Dispatch to ComfyUI Qwen workflow via background task
    """
    panel = await _get_panel(panel_id, db)

    # ── Load context ────────────────────────────────────────────────────
    scene = await db.scalar(
        select(Scene).where(Scene.id == panel.scene_id)
    )
    if not scene:
        raise HTTPException(404, "Scene not found for panel")

    script = await db.scalar(
        select(Script).where(Script.id == scene.script_id)
    )
    if not script:
        raise HTTPException(404, "Script not found for scene")

    project = await db.scalar(
        select(Project).where(Project.id == script.project_id)
    )
    if not project:
        raise HTTPException(404, "Project not found")

    # ── Load characters ─────────────────────────────────────────────────
    characters = None
    if panel.assigned_character_ids:
        try:
            ids = json.loads(panel.assigned_character_ids)
            if isinstance(ids, list) and ids:
                characters = await _lookup_characters(db, ids)
        except (json.JSONDecodeError, TypeError):
            pass

    # ── Generate LTX prompt ──────────────────────────────────────────────
    try:
        ltx_prompt = generate_panel_ltx_prompt(
            description=panel.description,
            camera_direction=panel.camera_direction,
            panel_type=panel.panel_type,
            scene_heading=scene.heading,
            location=scene.location,
            time_of_day=scene.time_of_day,
            scene_summary=scene.summary,
            character_descriptions=characters,
            project_vision=project.vision,
            project_tone=project.tone,
            mode="image-to-video",
        )
    except Exception as e:
        # Fallback: use template-based prompt
        print(f"[panels] LLM prompt gen failed: {e}, using template")
        char_texts = [
            c.get("description", "") or c.get("name", "")
            for c in (characters or [])
        ]
        ltx_prompt = build_panel_prompt_fallback(
            description=panel.description,
            camera_direction=panel.camera_direction,
            panel_type=panel.panel_type,
            scene_heading=scene.heading,
            location=scene.location,
            time_of_day=scene.time_of_day,
            character_descriptions=char_texts if char_texts else None,
            project_vision=project.vision,
            project_tone=project.tone,
        )

    # ── Store prompt ────────────────────────────────────────────────────
    panel.auto_prompt = ltx_prompt
    panel.status = "queued"
    panel.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # ── Dispatch to ComfyUI in background ────────────────────────────────
    # The background task renders the panel using the Qwen workflow
    # and updates the panel status + asset on completion
    from ..render_queue import render_panel_comfyui
    background_tasks.add_task(
        render_panel_comfyui,
        panel_id=panel.id,
        project_id=project.id,
        ltx_prompt=ltx_prompt,
        image_filename=None,  # No reference image for first render
    )

    return {
        "message": "Panel render queued",
        "panel_id": panel_id,
        "status": "queued",
        "prompt_preview": ltx_prompt[:200] + "..." if len(ltx_prompt) > 200 else ltx_prompt,
    }


# ── POST /panels/{id}/generate-prompt ────────────────────────────────────
@router.post("/{panel_id}/generate-prompt")
async def generate_panel_prompt_only(
    panel_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate the LTX prompt for a panel WITHOUT rendering.
    Just stores it in auto_prompt for review/editing.
    """
    panel = await _get_panel(panel_id, db)

    scene = await db.scalar(
        select(Scene).where(Scene.id == panel.scene_id)
    )
    script = await db.scalar(
        select(Script).where(Script.id == scene.script_id)
    )
    project = await db.scalar(
        select(Project).where(Project.id == script.project_id)
    )

    characters = None
    if panel.assigned_character_ids:
        try:
            ids = json.loads(panel.assigned_character_ids)
            if isinstance(ids, list) and ids:
                characters = await _lookup_characters(db, ids)
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        ltx_prompt = generate_panel_ltx_prompt(
            description=panel.description,
            camera_direction=panel.camera_direction,
            panel_type=panel.panel_type,
            scene_heading=scene.heading,
            location=scene.location,
            time_of_day=scene.time_of_day,
            scene_summary=scene.summary,
            character_descriptions=characters,
            project_vision=project.vision if project else None,
            project_tone=project.tone if project else None,
            mode="image-to-video",
        )
    except Exception as e:
        print(f"[panels] LLM prompt gen failed: {e}, using template")
        char_texts = [
            c.get("description", "") or c.get("name", "")
            for c in (characters or [])
        ]
        ltx_prompt = build_panel_prompt_fallback(
            description=panel.description,
            camera_direction=panel.camera_direction,
            panel_type=panel.panel_type,
            scene_heading=scene.heading,
            location=scene.location,
            time_of_day=scene.time_of_day,
            character_descriptions=char_texts if char_texts else None,
            project_vision=project.vision if project else None,
            project_tone=project.tone if project else None,
        )

    panel.auto_prompt = ltx_prompt
    panel.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "panel_id": panel_id,
        "auto_prompt": ltx_prompt,
    }