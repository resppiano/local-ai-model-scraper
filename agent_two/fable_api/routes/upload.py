"""
Upload Route
============
Multipart file upload endpoint for Fable Studio assets.

Accepts:
  - file: the uploaded file
  - type: reference|environment|prop|mood_board
  - tags: comma-separated list
  - project_id: project to associate with

Saves to: ~/FableAssets/uploads/{type}/{uuid}.{ext}
Returns: Asset record
"""

import json
import mimetypes
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, Project, Asset
from ..schemas import AssetOut, UploadResponse

router = APIRouter(prefix="/upload", tags=["upload"])

# Base upload directory
UPLOAD_BASE = os.environ.get(
    "FABLE_ASSETS_DIR",
    os.path.expanduser("~/FableAssets/uploads"),
)

ALLOWED_TYPES = {"reference", "environment", "prop", "mood_board", "control_video"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB — control videos can be large


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form(...),
    project_id: int = Form(...),
    tags: Optional[str] = Form(None),
    panel_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file as an asset for a project."""

    # Validate project
    proj = await db.scalar(select(Project).where(Project.id == project_id))
    if not proj:
        raise HTTPException(404, "Project not found")

    # Validate type
    if file_type not in ALLOWED_TYPES:
        raise HTTPException(
            400,
            f"Invalid file type '{file_type}'. Must be one of: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    # Validate file
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    # Determine content type
    content_type = file.content_type or "application/octet-stream"

    # Determine extension
    ext = os.path.splitext(file.filename)[1].lower()
    if not ext:
        # Guess from content type
        ext = mimetypes.guess_extension(content_type) or ".bin"
        if ext == ".jpe":
            ext = ".jpg"

    # Generate unique filename
    unique_name = f"{uuid.uuid4().hex}{ext}"
    subdir = _ensure_dir(os.path.join(UPLOAD_BASE, file_type))
    local_path = os.path.join(subdir, unique_name)

    # Read and save file
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB")

    with open(local_path, "wb") as f:
        f.write(contents)

    file_size = len(contents)

    # Determine asset type from content type
    if content_type.startswith("image/"):
        asset_type = "image"
    elif content_type.startswith("video/"):
        asset_type = "video"
    elif content_type.startswith("audio/"):
        asset_type = "audio"
    else:
        asset_type = "image"  # default

    # Parse tags
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Create asset record
    asset = Asset(
        project_id=project_id,
        type=asset_type,
        url=f"/uploads/{file_type}/{unique_name}",
        local_path=local_path,
        provider="upload",
        source="uploaded",
        tags=json.dumps(tag_list) if tag_list else None,
        file_size=file_size,
    )
    if panel_id is not None:
        asset.panel_id = panel_id
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return UploadResponse(
        asset=AssetOut.model_validate(asset),
        filename=file.filename,
        file_type=file_type,
        tags=tag_list,
    )