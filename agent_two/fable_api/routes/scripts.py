"""
Script Routes
=============
CRUD + breakdown + auto-prompt generation for scripts.
All mounted under /projects/{project_id}/scripts.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db, Project, Script, Scene, Character, Panel
from ..schemas import (
    ScriptCreate,
    ScriptUpdate,
    ScriptOut,
    SceneOut,
    BreakdownResult,
)
from ..services.script_breakdown import parse_script
from ..services.prompt_builder import build_panel_prompt

router = APIRouter(prefix="/projects/{project_id}/scripts", tags=["scripts"])


async def _get_project(project_id: int, db: AsyncSession) -> Project:
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


async def _script_with_scenes(db: AsyncSession, script_id: int) -> ScriptOut:
    stmt = (
        select(Script)
        .where(Script.id == script_id)
        .options(selectinload(Script.scenes).selectinload(Scene.panels))
    )
    result = await db.execute(stmt)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(404, "Script not found")
    data = {c.name: getattr(script, c.name) for c in script.__table__.columns}
    data["scenes"] = [_scene_to_out(s) for s in script.scenes]
    return ScriptOut(**data)


def _scene_to_out(scene: Scene) -> SceneOut:
    data = {c.name: getattr(scene, c.name) for c in scene.__table__.columns}
    data["panels"] = []
    return SceneOut(**data)


# ── POST /projects/{project_id}/scripts ──────────────────────────────────
@router.post("", response_model=ScriptOut, status_code=201)
async def create_script(
    project_id: int,
    data: ScriptCreate,
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, db)
    script = Script(project_id=project_id, **data.model_dump())
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return await _script_with_scenes(db, script.id)


# ── GET /projects/{project_id}/scripts ───────────────────────────────────
@router.get("", response_model=list[ScriptOut])
async def list_scripts(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, db)
    stmt = (
        select(Script)
        .where(Script.project_id == project_id)
        .order_by(Script.created_at.desc())
    )
    result = await db.execute(stmt)
    scripts = result.scalars().all()

    output = []
    for script in scripts:
        data = {c.name: getattr(script, c.name) for c in script.__table__.columns}
        data["scenes"] = []
        output.append(ScriptOut(**data))
    return output


# ── GET /projects/{project_id}/scripts/{id} ──────────────────────────────
@router.get("/{script_id}", response_model=ScriptOut)
async def get_script(
    project_id: int,
    script_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await _script_with_scenes(db, script_id)


# ── PATCH /projects/{project_id}/scripts/{id} ─────────────────────────────
@router.patch("/{script_id}", response_model=ScriptOut)
async def update_script(
    project_id: int,
    script_id: int,
    data: ScriptUpdate,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Script).where(Script.id == script_id, Script.project_id == project_id)
    result = await db.execute(stmt)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(404, "Script not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(script, field, value)
    await db.commit()
    await db.refresh(script)
    return await _script_with_scenes(db, script.id)


# ── DELETE /projects/{project_id}/scripts/{id} ───────────────────────────
@router.delete("/{script_id}", status_code=204)
async def delete_script(
    project_id: int,
    script_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Script).where(Script.id == script_id, Script.project_id == project_id)
    result = await db.execute(stmt)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(404, "Script not found")
    await db.delete(script)
    await db.commit()
    return


# ── POST /projects/{project_id}/scripts/{id}/breakdown ───────────────────
@router.post("/{script_id}/breakdown", response_model=BreakdownResult)
async def breakdown_script(
    project_id: int,
    script_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Script).where(Script.id == script_id, Script.project_id == project_id)
    result = await db.execute(stmt)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(404, "Script not found")

    # Parse scenes from the script content
    parsed = parse_script(script.content)

    if not parsed:
        raise HTTPException(400, "No scene headings found in script content")

    # Delete existing scenes for this script
    old_scenes = await db.execute(
        select(Scene).where(Scene.script_id == script_id)
    )
    for s in old_scenes.scalars().all():
        await db.delete(s)

    # Create new scenes
    created_scenes = []
    for i, scene_data in enumerate(parsed):
        scene = Scene(
            script_id=script_id,
            scene_number=i + 1,
            heading=scene_data["heading"],
            location=scene_data["location"],
            time_of_day=scene_data["time_of_day"],
            summary=scene_data["summary"],
        )
        db.add(scene)
        await db.flush()
        await db.refresh(scene)
        created_scenes.append(scene)

    await db.commit()

    return BreakdownResult(
        scenes_parsed=len(created_scenes),
        scenes=[_scene_to_out(s) for s in created_scenes],
    )


# ── POST /projects/{project_id}/scripts/{id}/auto-prompts ────────────────
@router.post("/{script_id}/auto-prompts")
async def generate_auto_prompts(
    project_id: int,
    script_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Rebuild auto_prompt for all panels in all scenes of this script."""
    stmt = select(Script).where(Script.id == script_id, Script.project_id == project_id)
    result = await db.execute(stmt)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(404, "Script not found")

    # Get project for vision/tone
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")

    # Get all scenes + panels
    scenes_stmt = (
        select(Scene)
        .where(Scene.script_id == script_id)
        .options(selectinload(Scene.panels))
    )
    scenes_result = await db.execute(scenes_stmt)
    scenes = scenes_result.scalars().all()

    updated_count = 0
    for scene in scenes:
        for panel in scene.panels:
            # Look up characters if assigned
            char_descriptions = None
            if panel.assigned_character_ids:
                try:
                    import json
                    char_ids = json.loads(panel.assigned_character_ids)
                    if char_ids:
                        char_stmt = select(Character).where(
                            Character.id.in_(char_ids),
                            Character.project_id == project_id,
                        )
                        char_result = await db.execute(char_stmt)
                        chars = char_result.scalars().all()
                        char_descriptions = [
                            f"{c.name}: {c.description}" if c.description else c.name
                            for c in chars
                        ]
                except (json.JSONDecodeError, TypeError):
                    pass

            prompt = build_panel_prompt(
                description=panel.description,
                camera_direction=panel.camera_direction,
                scene_heading=scene.heading,
                location=scene.location,
                time_of_day=scene.time_of_day,
                character_descriptions=char_descriptions,
                project_vision=proj.vision,
                project_tone=proj.tone,
            )
            panel.auto_prompt = prompt
            updated_count += 1

    await db.commit()

    return {
        "message": f"Auto-prompts updated for {updated_count} panels",
        "panels_updated": updated_count,
    }