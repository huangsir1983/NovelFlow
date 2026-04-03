"""Asset image mapping API — persist asset_id + slot → storage_key."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.asset_image import AssetImage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["asset-images"])


# --- Schemas ---

class AssetImageCreate(BaseModel):
    asset_id: str
    asset_type: str = ""       # character | location | prop | variant
    slot_key: str
    storage_key: str


class AssetImageResponse(BaseModel):
    id: str
    project_id: str
    asset_id: str
    asset_type: str | None
    slot_key: str | None
    storage_key: str | None

    model_config = {"from_attributes": True}


# --- Routes ---

@router.post(
    "/projects/{project_id}/asset-images",
    response_model=AssetImageResponse,
    status_code=201,
)
def save_asset_image(
    project_id: str,
    data: AssetImageCreate,
    db: Session = Depends(get_db),
):
    """Upsert an asset image mapping (same asset_id + slot_key → update)."""
    existing = (
        db.query(AssetImage)
        .filter(
            AssetImage.asset_id == data.asset_id,
            AssetImage.slot_key == data.slot_key,
        )
        .first()
    )
    if existing:
        existing.storage_key = data.storage_key
        existing.asset_type = data.asset_type
        db.commit()
        db.refresh(existing)
        return existing

    row = AssetImage(
        id=str(uuid4()),
        project_id=project_id,
        asset_id=data.asset_id,
        asset_type=data.asset_type,
        slot_key=data.slot_key,
        storage_key=data.storage_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get(
    "/projects/{project_id}/asset-images",
    response_model=list[AssetImageResponse],
)
def list_asset_images(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Return all asset image mappings for a project."""
    return (
        db.query(AssetImage)
        .filter(AssetImage.project_id == project_id)
        .all()
    )


class UploadResponse(BaseModel):
    storage_key: str
    storage_uri: str | None = None


@router.post(
    "/projects/{project_id}/asset-images/upload",
    response_model=UploadResponse,
)
def upload_asset_image(
    project_id: str,
    file: UploadFile = File(...),
):
    """Upload an image file to storage (no AI generation). Used for panorama screenshots etc."""
    file_bytes = file.file.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    content_type = file.content_type or "image/jpeg"
    ext = content_type.split("/")[-1].split(";")[0]
    if ext not in ("png", "jpeg", "jpg", "webp"):
        ext = "png"

    from services.storage_adapter import get_storage

    storage = get_storage()
    object_key = f"assets/screenshots/{uuid4()}.{ext}"
    try:
        stored = storage.put_bytes(
            object_key=object_key,
            data=file_bytes,
            content_type=content_type,
        )
        return UploadResponse(
            storage_key=stored.object_key,
            storage_uri=stored.uri,
        )
    except Exception as e:
        logger.error("Failed to upload asset image: %s", e)
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")
