"""Chain Templates CRUD API — manage reusable workflow chain definitions."""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.chain_template import ChainTemplate
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chain-templates"])


# ══════════════════════════════════════════════════════════════
# Request Models
# ══════════════════════════════════════════════════════════════

class CreateChainTemplateRequest(BaseModel):
    name: str
    description: str = ""
    icon: str = "◆"
    color: str = "#378ADD"
    tags: list = Field(default_factory=list)
    steps: list = Field(default_factory=list)
    videoProvider: str = "jimeng"
    estimatedMinutes: int = 5


class UpdateChainTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    tags: Optional[list] = None
    steps: Optional[list] = None
    videoProvider: Optional[str] = None
    estimatedMinutes: Optional[int] = None


# ══════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/chain-templates")
def list_chain_templates(project_id: str, db: Session = Depends(get_db)):
    """List chain templates: all builtin globals + project-specific custom templates."""
    builtin = db.query(ChainTemplate).filter(
        ChainTemplate.is_builtin == True
    ).all()

    project_templates = db.query(ChainTemplate).filter(
        ChainTemplate.project_id == project_id,
        ChainTemplate.is_builtin == False,
    ).all()

    # Deduplicate (builtin have no project_id, so no overlap expected)
    all_templates = builtin + project_templates
    return [t.to_dict() for t in all_templates]


@router.post("/projects/{project_id}/chain-templates")
def create_chain_template(project_id: str, req: CreateChainTemplateRequest, db: Session = Depends(get_db)):
    """Create a custom (non-builtin) chain template for a project."""
    template = ChainTemplate(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=req.name,
        description=req.description,
        icon=req.icon,
        color=req.color,
        tags=req.tags,
        is_builtin=False,
        steps=req.steps,
        video_provider=req.videoProvider,
        estimated_minutes=req.estimatedMinutes,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template.to_dict()


@router.put("/chain-templates/{template_id}")
def update_chain_template(template_id: str, req: UpdateChainTemplateRequest, db: Session = Depends(get_db)):
    """Update a custom chain template. Builtin templates cannot be modified."""
    template = db.query(ChainTemplate).get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")
    if template.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot modify builtin templates")

    if req.name is not None:
        template.name = req.name
    if req.description is not None:
        template.description = req.description
    if req.icon is not None:
        template.icon = req.icon
    if req.color is not None:
        template.color = req.color
    if req.tags is not None:
        template.tags = req.tags
    if req.steps is not None:
        template.steps = req.steps
    if req.videoProvider is not None:
        template.video_provider = req.videoProvider
    if req.estimatedMinutes is not None:
        template.estimated_minutes = req.estimatedMinutes

    template.version = (template.version or 1) + 1
    db.commit()
    db.refresh(template)
    return template.to_dict()


@router.delete("/chain-templates/{template_id}")
def delete_chain_template(template_id: str, db: Session = Depends(get_db)):
    """Delete a custom chain template. Builtin templates cannot be deleted."""
    template = db.query(ChainTemplate).get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Chain template not found")
    if template.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete builtin templates")

    db.delete(template)
    db.commit()
    return {"status": "deleted", "id": template_id}
