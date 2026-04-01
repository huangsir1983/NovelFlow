"""Projects CRUD API."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, commit_with_retry
from models.project import Project

router = APIRouter(tags=["projects"])


# --- Schemas ---

class ProjectCreate(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    import_source: str = "novel"
    edition: str = "normal"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    import_source: str
    edition: str
    stage: str
    adaptation_direction: Optional[str] = None
    screen_format: Optional[str] = None
    style_preset: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectConfigUpdate(BaseModel):
    adaptation_direction: Optional[str] = None
    screen_format: Optional[str] = None
    style_preset: Optional[str] = None


# --- Routes ---

@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    project_id = data.id or str(uuid4())
    # If client-provided ID already exists, return existing project (idempotent)
    if data.id:
        existing = db.query(Project).filter(Project.id == data.id).first()
        if existing:
            return existing
    project = Project(
        id=project_id,
        name=data.name,
        description=data.description,
        import_source=data.import_source,
        edition=data.edition,
    )
    db.add(project)
    commit_with_retry(db)
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """List all projects."""
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Get a single project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    """Update an existing project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.stage is not None:
        project.stage = data.stage

    commit_with_retry(db)
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    commit_with_retry(db)
    return None


@router.patch("/projects/{project_id}/config", response_model=ProjectResponse)
def update_project_config(project_id: str, data: ProjectConfigUpdate, db: Session = Depends(get_db)):
    """Update project configuration (adaptation direction, screen format, style preset)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.adaptation_direction is not None:
        project.adaptation_direction = data.adaptation_direction
    if data.screen_format is not None:
        project.screen_format = data.screen_format
    if data.style_preset is not None:
        project.style_preset = data.style_preset

    commit_with_retry(db)
    db.refresh(project)
    return project
