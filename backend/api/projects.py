"""Projects CRUD API."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.project import Project

router = APIRouter(tags=["projects"])


# --- Schemas ---

class ProjectCreate(BaseModel):
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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Routes ---

@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    project = Project(
        id=str(uuid4()),
        name=data.name,
        description=data.description,
        import_source=data.import_source,
        edition=data.edition,
    )
    db.add(project)
    db.commit()
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

    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Delete a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return None
