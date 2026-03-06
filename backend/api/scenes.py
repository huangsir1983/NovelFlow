"""Scenes CRUD API."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.scene import Scene

router = APIRouter(tags=["scenes"])


# --- Schemas ---

class SceneCreate(BaseModel):
    beat_id: Optional[str] = None
    heading: str = ""
    location: str = ""
    time_of_day: str = ""
    description: str = ""
    action: str = ""
    dialogue: list = []
    order: int = 0
    tension_score: float = 0.0


class SceneUpdate(BaseModel):
    beat_id: Optional[str] = None
    heading: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    action: Optional[str] = None
    dialogue: Optional[list] = None
    order: Optional[int] = None
    tension_score: Optional[float] = None


class SceneResponse(BaseModel):
    id: str
    project_id: str
    beat_id: Optional[str]
    heading: str
    location: str
    time_of_day: str
    description: str
    action: str
    dialogue: list
    order: int
    tension_score: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Routes ---

@router.get("/projects/{project_id}/scenes", response_model=list[SceneResponse])
def list_scenes(project_id: str, db: Session = Depends(get_db)):
    """List all scenes for a project."""
    return db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.order).all()


@router.post("/projects/{project_id}/scenes", response_model=SceneResponse, status_code=201)
def create_scene(project_id: str, data: SceneCreate, db: Session = Depends(get_db)):
    """Create a new scene."""
    scene = Scene(
        id=str(uuid4()),
        project_id=project_id,
        beat_id=data.beat_id,
        heading=data.heading,
        location=data.location,
        time_of_day=data.time_of_day,
        description=data.description,
        action=data.action,
        dialogue=data.dialogue,
        order=data.order,
        tension_score=data.tension_score,
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


@router.get("/projects/{project_id}/scenes/{scene_id}", response_model=SceneResponse)
def get_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    """Get a single scene."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.put("/projects/{project_id}/scenes/{scene_id}", response_model=SceneResponse)
def update_scene(project_id: str, scene_id: str, data: SceneUpdate, db: Session = Depends(get_db)):
    """Update a scene."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    for field in ["beat_id", "heading", "location", "time_of_day", "description", "action", "dialogue", "order", "tension_score"]:
        value = getattr(data, field)
        if value is not None:
            setattr(scene, field, value)

    db.commit()
    db.refresh(scene)
    return scene


@router.delete("/projects/{project_id}/scenes/{scene_id}", status_code=204)
def delete_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    """Delete a scene."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    db.delete(scene)
    db.commit()
    return None
