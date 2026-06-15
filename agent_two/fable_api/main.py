"""
Fable API — FastAPI Backend
===========================
The REST API for Project Fable.  Provides endpoints for projects, shots,
characters, assets, and the render queue.

Run:
    cd /home/gregjones/agent_two/fable_api
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload

Or from agent_two:
    source venv/bin/activate
    python -m fable_api.main
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .database import init_db, get_db, Project, Shot, Character, Asset, RenderJob
from .schemas import (
    ProjectCreate, ProjectUpdate, ProjectOut,
    ShotCreate, ShotUpdate, ShotOut,
    CharacterCreate, CharacterUpdate, CharacterOut,
    AssetCreate, AssetOut,
    RenderRequest, RenderStatus, DashboardStats,
)
from .render_queue import RenderQueue


# ── Lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.queue = RenderQueue()
    await app.state.queue.start()
    yield
    await app.state.queue.stop()


# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fable API",
    description="Project Fable — AI Film Studio Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════
@app.get("/health")
async def health():
    return {"status": "ok", "service": "fable-api", "version": "0.1.0"}


# ═══════════════════════════════════════════════════════════════════════
# PROJECTS
# ═══════════════════════════════════════════════════════════════════════
@app.post("/projects", response_model=ProjectOut, status_code=201)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(**data.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_with_counts(db, project.id)


@app.get("/projects", response_model=list[ProjectOut])
async def list_projects(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Project).order_by(desc(Project.created_at))
    if status:
        stmt = stmt.where(Project.status == status)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    projects = result.scalars().all()
    return [await _project_with_counts(db, p.id) for p in projects]


@app.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return await _project_with_counts(db, project.id)


@app.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(project_id: int, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(project)
    return await _project_with_counts(db, project.id)


@app.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    await db.delete(project)
    await db.commit()
    return


async def _project_with_counts(db: AsyncSession, project_id: int) -> ProjectOut:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    p = result.scalar_one()
    shot_count = await db.scalar(select(func.count()).where(Shot.project_id == project_id))
    asset_count = await db.scalar(select(func.count()).where(Asset.project_id == project_id))
    data = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    data["shot_count"] = shot_count
    data["asset_count"] = asset_count
    return ProjectOut(**data)


# ═══════════════════════════════════════════════════════════════════════
# SHOTS
# ═══════════════════════════════════════════════════════════════════════
@app.post("/projects/{project_id}/shots", response_model=ShotOut, status_code=201)
async def create_shot(project_id: int, data: ShotCreate, db: AsyncSession = Depends(get_db)):
    # Verify project exists
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")

    shot = Shot(project_id=project_id, **data.model_dump())
    db.add(shot)
    await db.commit()
    await db.refresh(shot)
    return await _shot_with_assets(db, shot.id)


@app.get("/projects/{project_id}/shots", response_model=list[ShotOut])
async def list_shots(
    project_id: int,
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")
    stmt = select(Shot).where(Shot.project_id == project_id).order_by(Shot.scene_number, Shot.shot_number)
    if status:
        stmt = stmt.where(Shot.status == status)
    result = await db.execute(stmt)
    shots = result.scalars().all()
    return [await _shot_with_assets(db, s.id) for s in shots]


@app.get("/shots/{shot_id}", response_model=ShotOut)
async def get_shot(shot_id: int, db: AsyncSession = Depends(get_db)):
    return await _shot_with_assets(db, shot_id)


@app.patch("/shots/{shot_id}", response_model=ShotOut)
async def update_shot(shot_id: int, data: ShotUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Shot).where(Shot.id == shot_id)
    result = await db.execute(stmt)
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(404, "Shot not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(shot, field, value)
    shot.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(shot)
    return await _shot_with_assets(db, shot_id)


@app.delete("/shots/{shot_id}", status_code=204)
async def delete_shot(shot_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Shot).where(Shot.id == shot_id)
    result = await db.execute(stmt)
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(404, "Shot not found")
    await db.delete(shot)
    await db.commit()
    return


async def _shot_with_assets(db: AsyncSession, shot_id: int) -> ShotOut:
    stmt = select(Shot).where(Shot.id == shot_id).options(selectinload(Shot.assets))
    result = await db.execute(stmt)
    shot = result.scalar_one()
    data = {c.name: getattr(shot, c.name) for c in shot.__table__.columns}
    data["assets"] = [AssetOut.model_validate(a) for a in shot.assets]
    return ShotOut(**data)


# ═══════════════════════════════════════════════════════════════════════
# CHARACTERS
# ═══════════════════════════════════════════════════════════════════════
@app.post("/projects/{project_id}/characters", response_model=CharacterOut, status_code=201)
async def create_character(project_id: int, data: CharacterCreate, db: AsyncSession = Depends(get_db)):
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")
    char = Character(project_id=project_id, **data.model_dump())
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return CharacterOut.model_validate(char)


@app.get("/projects/{project_id}/characters", response_model=list[CharacterOut])
async def list_characters(project_id: int, db: AsyncSession = Depends(get_db)):
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")
    stmt = select(Character).where(Character.project_id == project_id)
    result = await db.execute(stmt)
    return [CharacterOut.model_validate(c) for c in result.scalars().all()]


@app.patch("/characters/{char_id}", response_model=CharacterOut)
async def update_character(char_id: int, data: CharacterUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Character).where(Character.id == char_id)
    result = await db.execute(stmt)
    char = result.scalar_one_or_none()
    if not char:
        raise HTTPException(404, "Character not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(char, field, value)
    await db.commit()
    await db.refresh(char)
    return CharacterOut.model_validate(char)


@app.delete("/characters/{char_id}", status_code=204)
async def delete_character(char_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Character).where(Character.id == char_id)
    result = await db.execute(stmt)
    char = result.scalar_one_or_none()
    if not char:
        raise HTTPException(404, "Character not found")
    await db.delete(char)
    await db.commit()
    return


# ═══════════════════════════════════════════════════════════════════════
# ASSETS
# ═══════════════════════════════════════════════════════════════════════
@app.post("/projects/{project_id}/assets", response_model=AssetOut, status_code=201)
async def create_asset(project_id: int, data: AssetCreate, db: AsyncSession = Depends(get_db)):
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")
    asset = Asset(project_id=project_id, **data.model_dump())
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return AssetOut.model_validate(asset)


@app.get("/projects/{project_id}/assets", response_model=list[AssetOut])
async def list_assets(
    project_id: int,
    type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")
    stmt = select(Asset).where(Asset.project_id == project_id).order_by(desc(Asset.created_at))
    if type:
        stmt = stmt.where(Asset.type == type)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return [AssetOut.model_validate(a) for a in result.scalars().all()]


@app.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Asset).where(Asset.id == asset_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "Asset not found")
    await db.delete(asset)
    await db.commit()
    return


# ═══════════════════════════════════════════════════════════════════════
# RENDER QUEUE
# ═══════════════════════════════════════════════════════════════════════
@app.post("/render", response_model=RenderStatus, status_code=202)
async def queue_render(
    data: RenderRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Verify shot exists
    shot = await db.scalar(select(Shot).where(Shot.id == data.shot_id))
    if not shot:
        raise HTTPException(404, "Shot not found")

    # Update shot status
    shot.status = "queued"
    shot.render_provider = data.provider
    shot.render_model = data.model
    await db.commit()

    # Create render job
    job = RenderJob(
        shot_id=data.shot_id,
        provider=data.provider,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Queue in background worker
    background_tasks.add_task(app.state.queue.submit, job.id)

    return RenderStatus.model_validate(job)


@app.get("/render/{job_id}", response_model=RenderStatus)
async def get_render_status(job_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(RenderJob).where(RenderJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Render job not found")
    return RenderStatus.model_validate(job)


@app.get("/projects/{project_id}/renders", response_model=list[RenderStatus])
async def list_project_renders(project_id: int, db: AsyncSession = Depends(get_db)):
    # Join through shots
    stmt = (
        select(RenderJob)
        .join(Shot, RenderJob.shot_id == Shot.id)
        .where(Shot.project_id == project_id)
        .order_by(desc(RenderJob.created_at))
    )
    result = await db.execute(stmt)
    return [RenderStatus.model_validate(j) for j in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════
@app.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total_projects = await db.scalar(select(func.count()).select_from(Project))
    active_projects = await db.scalar(
        select(func.count()).select_from(Project).where(Project.status == "active")
    )
    total_shots = await db.scalar(select(func.count()).select_from(Shot))
    shots_rendered = await db.scalar(
        select(func.count()).select_from(Shot).where(Shot.status == "done")
    )
    total_assets = await db.scalar(select(func.count()).select_from(Asset))

    # Recent 10 assets
    stmt = select(Asset).order_by(desc(Asset.created_at)).limit(10)
    result = await db.execute(stmt)
    recent_assets = [AssetOut.model_validate(a) for a in result.scalars().all()]

    return DashboardStats(
        total_projects=total_projects or 0,
        active_projects=active_projects or 0,
        total_shots=total_shots or 0,
        shots_rendered=shots_rendered or 0,
        total_assets=total_assets or 0,
        recent_assets=recent_assets,
    )


# ── Run ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fable_api.main:app", host="0.0.0.0", port=8001, reload=True)
