"""Asset image mapping API — persist asset_id + slot → storage_key."""

import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
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
