"""
Fable API — Database Layer
==========================
SQLAlchemy models + async engine for the Project Fable backend.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


# ── Base ──────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    logline: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tone: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    genre: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # "short film", "episode", etc.
    target_length: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    audience: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft | active | complete | archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    shots: Mapped[list["Shot"]] = relationship("Shot", back_populates="project", cascade="all, delete-orphan")
    characters: Mapped[list["Character"]] = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="project", cascade="all, delete-orphan")


class Shot(Base):
    __tablename__ = "shots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    scene_number: Mapped[int] = mapped_column(Integer, default=1)
    shot_number: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI generation prompt
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    motion_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # For video
    shot_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # wide, close-up, etc.
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # seconds
    status: Mapped[str] = mapped_column(String(50), default="planned")  # planned | queued | rendering | done | failed
    render_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # comfyui | higgsfield
    render_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    render_job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # external job ID
    character_id: Mapped[Optional[int]] = mapped_column(ForeignKey("characters.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project: Mapped["Project"] = relationship("Project", back_populates="shots")
    character: Mapped[Optional["Character"]] = relationship("Character", back_populates="shots")
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="shot", cascade="all, delete-orphan")


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    higgsfield_character_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # cloud char ID
    comfyui_embedding_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # local embedding
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship("Project", back_populates="characters")
    shots: Mapped[list["Shot"]] = relationship("Shot", back_populates="character")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    shot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shots.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # image | video | audio | thumbnail
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # comfyui | higgsfield | upload
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # bytes
    meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship("Project", back_populates="assets")
    shot: Mapped[Optional["Shot"]] = relationship("Shot", back_populates="assets")


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shot_id: Mapped[int] = mapped_column(ForeignKey("shots.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # comfyui | higgsfield
    status: Mapped[str] = mapped_column(String(50), default="queued")  # queued | running | completed | failed | cancelled
    external_job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Engine & Session ────────────────────────────────────────────────────
DB_PATH = os.environ.get("FABLE_DB_PATH", "/home/gregjones/agent_two/fable_api/fable.db")

# Sync engine for migrations
sync_engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# Async engine for the API
async_engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
async_session = async_sessionmaker(async_engine, expire_on_commit=False)


def init_db():
    """Create all tables synchronously (call once at startup)."""
    Base.metadata.create_all(sync_engine)


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
