"""
Fable API — Pydantic Schemas
============================
Request / response models for the REST API.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Project ───────────────────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    logline: Optional[str] = None
    vision: Optional[str] = None
    tone: Optional[str] = None
    genre: Optional[str] = None
    format: Optional[str] = None
    target_length: Optional[str] = None
    audience: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    logline: Optional[str] = None
    vision: Optional[str] = None
    tone: Optional[str] = None
    genre: Optional[str] = None
    format: Optional[str] = None
    target_length: Optional[str] = None
    audience: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    title: str
    logline: Optional[str]
    vision: Optional[str]
    tone: Optional[str]
    genre: Optional[str]
    format: Optional[str]
    target_length: Optional[str]
    audience: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    shot_count: int = 0
    asset_count: int = 0

    class Config:
        from_attributes = True


# ── Shot ──────────────────────────────────────────────────────────────────
class ShotCreate(BaseModel):
    scene_number: int = 1
    shot_number: int = 1
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    motion_prompt: Optional[str] = None
    shot_type: Optional[str] = None
    duration: Optional[float] = None
    character_id: Optional[int] = None
    notes: Optional[str] = None


class ShotUpdate(BaseModel):
    scene_number: Optional[int] = None
    shot_number: Optional[int] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    motion_prompt: Optional[str] = None
    shot_type: Optional[str] = None
    duration: Optional[float] = None
    status: Optional[str] = None
    character_id: Optional[int] = None
    notes: Optional[str] = None


class ShotOut(BaseModel):
    id: int
    project_id: int
    scene_number: int
    shot_number: int
    description: Optional[str]
    prompt: Optional[str]
    negative_prompt: Optional[str]
    motion_prompt: Optional[str]
    shot_type: Optional[str]
    duration: Optional[float]
    status: str
    render_provider: Optional[str]
    render_model: Optional[str]
    character_id: Optional[int]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    assets: List["AssetOut"] = []

    class Config:
        from_attributes = True


# ── Character ─────────────────────────────────────────────────────────────
class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    reference_image_url: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    reference_image_url: Optional[str] = None
    higgsfield_character_id: Optional[str] = None
    comfyui_embedding_path: Optional[str] = None


class CharacterOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str]
    reference_image_url: Optional[str]
    higgsfield_character_id: Optional[str]
    comfyui_embedding_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Asset ─────────────────────────────────────────────────────────────────
class AssetCreate(BaseModel):
    type: str = Field(..., pattern="^(image|video|audio|thumbnail)$")
    url: str
    local_path: Optional[str] = None
    provider: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    meta: Optional[str] = None


class AssetOut(BaseModel):
    id: int
    project_id: int
    shot_id: Optional[int]
    type: str
    url: str
    local_path: Optional[str]
    provider: Optional[str]
    width: Optional[int]
    height: Optional[int]
    duration: Optional[float]
    file_size: Optional[int]
    meta: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Render ──────────────────────────────────────────────────────────────
class RenderRequest(BaseModel):
    shot_id: int
    provider: str = Field(..., pattern="^(comfyui|higgsfield)$")
    model: Optional[str] = None
    priority: int = 0


class RenderStatus(BaseModel):
    job_id: int
    shot_id: int
    provider: str
    status: str
    external_job_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if hasattr(obj, 'id') and not hasattr(obj, 'job_id'):
            data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            data['job_id'] = data.pop('id')
            return cls(**data)
        return super().model_validate(obj, **kwargs)

    class Config:
        from_attributes = True


# ── Dashboard Stats ─────────────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_projects: int
    active_projects: int
    total_shots: int
    shots_rendered: int
    total_assets: int
    recent_assets: List[AssetOut] = []


# Resolve forward refs
ShotOut.model_rebuild()
ProjectOut.model_rebuild()
