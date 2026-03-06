"""Beats CRUD API."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.beat import Beat

router = APIRouter(tags=["beats"])


# --- Schemas ---

class BeatCreate(BaseModel):
    chapter_id: Optional[str] = None
    title: str
    description: str = ""
    beat_type: str = "event"
    emotional_value: float = 0.0
    order: int = 0


class BeatUpdate(BaseModel):
    chapter_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    beat_type: Optional[str] = None
    emotional_value: Optional[float] = None
    order: Optional[int] = None


class BeatResponse(BaseModel):
    id: str
    project_id: str
    chapter_id: Optional[str]
    title: str
    description: str
    beat_type: str
    emotional_value: float
    order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Routes ---

@router.get("/projects/{project_id}/beats", response_model=list[BeatResponse])
def list_beats(project_id: str, db: Session = Depends(get_db)):
    """List all beats for a project."""
    return db.query(Beat).filter(Beat.project_id == project_id).order_by(Beat.order).all()


@router.post("/projects/{project_id}/beats", response_model=BeatResponse, status_code=201)
def create_beat(project_id: str, data: BeatCreate, db: Session = Depends(get_db)):
    """Create a new beat."""
    beat = Beat(
        id=str(uuid4()),
        project_id=project_id,
        chapter_id=data.chapter_id,
        title=data.title,
        description=data.description,
        beat_type=data.beat_type,
        emotional_value=data.emotional_value,
        order=data.order,
    )
    db.add(beat)
    db.commit()
    db.refresh(beat)
    return beat


@router.get("/projects/{project_id}/beats/{beat_id}", response_model=BeatResponse)
def get_beat(project_id: str, beat_id: str, db: Session = Depends(get_db)):
    """Get a single beat."""
    beat = db.query(Beat).filter(Beat.id == beat_id, Beat.project_id == project_id).first()
    if not beat:
        raise HTTPException(status_code=404, detail="Beat not found")
    return beat


@router.put("/projects/{project_id}/beats/{beat_id}", response_model=BeatResponse)
def update_beat(project_id: str, beat_id: str, data: BeatUpdate, db: Session = Depends(get_db)):
    """Update a beat."""
    beat = db.query(Beat).filter(Beat.id == beat_id, Beat.project_id == project_id).first()
    if not beat:
        raise HTTPException(status_code=404, detail="Beat not found")

    for field in ["chapter_id", "title", "description", "beat_type", "emotional_value", "order"]:
        value = getattr(data, field)
        if value is not None:
            setattr(beat, field, value)

    db.commit()
    db.refresh(beat)
    return beat


@router.delete("/projects/{project_id}/beats/{beat_id}", status_code=204)
def delete_beat(project_id: str, beat_id: str, db: Session = Depends(get_db)):
    """Delete a beat."""
    beat = db.query(Beat).filter(Beat.id == beat_id, Beat.project_id == project_id).first()
    if not beat:
        raise HTTPException(status_code=404, detail="Beat not found")
    db.delete(beat)
    db.commit()
    return None
