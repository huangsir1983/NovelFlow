"""Canvas API — CRUD + Agent + Node Execution endpoints for infinite canvas."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.canvas_workflow import CanvasWorkflow, CanvasNodeExecution

logger = logging.getLogger(__name__)

router = APIRouter(tags=["canvas"])


# ══════════════════════════════════════════════════════════════
# Request / Response Models
# ══════════════════════════════════════════════════════════════

class CanvasWorkflowResponse(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    workflow_json: dict
    node_count: int
    version: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SaveCanvasRequest(BaseModel):
    workflow_json: dict = Field(default_factory=dict)
    name: Optional[str] = None


class AnalyzeStoryboardRequest(BaseModel):
    node_id: str
    content: dict
    assets: list = Field(default_factory=list)


class AssignModulesRequest(BaseModel):
    nodes: list  # [{nodeId, text}]


class OptimizePromptRequest(BaseModel):
    type: str  # 'image' | 'video'
    current_prompt: str
    context: dict


class ReviewCompositionRequest(BaseModel):
    image_base64: str
    storyboard_text: str
    module_type: str


class ExecuteNodeRequest(BaseModel):
    node_type: str
    content: dict


class BatchExecuteRequest(BaseModel):
    node_ids: list


class SyncFromProjectRequest(BaseModel):
    project_id: str


class SyncToProjectRequest(BaseModel):
    project_id: str
    results: list


# ══════════════════════════════════════════════════════════════
# 1. Canvas CRUD
# ══════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/canvas")
async def get_canvas(project_id: str, db: AsyncSession = Depends(get_db)):  # noqa: E501
    """Get canvas workflow for a project."""
    result = await db.execute(
        select(CanvasWorkflow).where(CanvasWorkflow.project_id == project_id).order_by(CanvasWorkflow.created_at.desc())
    )
    workflow = result.scalars().first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Canvas not found for this project")

    return CanvasWorkflowResponse(
        id=workflow.id,
        project_id=workflow.project_id,
        name=workflow.name,
        status=workflow.status,
        workflow_json=workflow.workflow_json or {},
        node_count=workflow.node_count,
        version=workflow.version,
        created_at=str(workflow.created_at) if workflow.created_at else None,
        updated_at=str(workflow.updated_at) if workflow.updated_at else None,
    )


@router.post("/projects/{project_id}/canvas")
async def create_canvas(project_id: str, req: SaveCanvasRequest, db: AsyncSession = Depends(get_db)):
    """Create a new canvas workflow for a project."""
    workflow = CanvasWorkflow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=req.name or "默认画布",
        status="draft",
        workflow_json=req.workflow_json,
        node_count=len(req.workflow_json.get("nodes", [])),
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    return CanvasWorkflowResponse(
        id=workflow.id,
        project_id=workflow.project_id,
        name=workflow.name,
        status=workflow.status,
        workflow_json=workflow.workflow_json or {},
        node_count=workflow.node_count,
        version=workflow.version,
    )


@router.put("/projects/{project_id}/canvas")
async def save_canvas(project_id: str, req: SaveCanvasRequest, db: AsyncSession = Depends(get_db)):
    """Save / update canvas workflow."""
    result = await db.execute(
        select(CanvasWorkflow).where(CanvasWorkflow.project_id == project_id).order_by(CanvasWorkflow.created_at.desc())
    )
    workflow = result.scalars().first()

    if not workflow:
        # Auto-create if not exists
        workflow = CanvasWorkflow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            name=req.name or "默认画布",
            status="active",
            workflow_json=req.workflow_json,
            node_count=len(req.workflow_json.get("nodes", [])),
        )
        db.add(workflow)
    else:
        workflow.workflow_json = req.workflow_json
        workflow.node_count = len(req.workflow_json.get("nodes", []))
        workflow.version = (workflow.version or 1) + 1
        workflow.status = "active"
        if req.name:
            workflow.name = req.name

    await db.commit()
    await db.refresh(workflow)

    return CanvasWorkflowResponse(
        id=workflow.id,
        project_id=workflow.project_id,
        name=workflow.name,
        status=workflow.status,
        workflow_json=workflow.workflow_json or {},
        node_count=workflow.node_count,
        version=workflow.version,
    )


@router.delete("/projects/{project_id}/canvas")
async def delete_canvas(project_id: str, db: AsyncSession = Depends(get_db)):
    """Delete canvas workflow."""
    result = await db.execute(
        select(CanvasWorkflow).where(CanvasWorkflow.project_id == project_id)
    )
    workflow = result.scalars().first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Canvas not found")

    await db.delete(workflow)
    await db.commit()
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════
# 2. Agent Services (stubs — Phase 2 will implement AI logic)
# ══════════════════════════════════════════════════════════════

@router.post("/canvas/agent/analyze-storyboard")
async def analyze_storyboard(req: AnalyzeStoryboardRequest):
    """Analyze a storyboard node and generate image/video prompts."""
    # TODO Phase 2: integrate with AI provider system
    return {
        "node_id": req.node_id,
        "imagePrompt": f"cinematic shot of scene, {req.content.get('rawText', '')[:50]}",
        "videoPrompt": f"固定机位缓慢推进，{req.content.get('emotion', '中性')}氛围",
        "shotType": "medium",
        "emotion": req.content.get("emotion", ""),
        "duration": 5,
    }


@router.post("/canvas/agent/assign-modules")
async def assign_modules(req: AssignModulesRequest):
    """Assign workflow module types to storyboard nodes."""
    # TODO Phase 2: integrate with AI provider system
    results = []
    for node_info in req.nodes:
        results.append({
            "nodeId": node_info.get("nodeId", ""),
            "moduleType": "dialogue",
            "confidence": 0.5,
        })
    return results


@router.post("/canvas/agent/optimize-prompt")
async def optimize_prompt(req: OptimizePromptRequest):
    """Optimize an existing image or video prompt."""
    # TODO Phase 2
    return {"optimized_prompt": req.current_prompt}


@router.post("/canvas/agent/review-composition")
async def review_composition(req: ReviewCompositionRequest):
    """Review a generated image composition."""
    # TODO Phase 2
    return {"score": 7.5, "pass": True, "suggestions": []}


# ══════════════════════════════════════════════════════════════
# 3. Node Execution (stubs — Phase 3 will implement)
# ══════════════════════════════════════════════════════════════

@router.post("/canvas/nodes/{node_id}/execute")
async def execute_node(node_id: str, req: ExecuteNodeRequest, db: AsyncSession = Depends(get_db)):
    """Execute a single canvas node."""
    # TODO Phase 3
    execution = CanvasNodeExecution(
        id=str(uuid.uuid4()),
        workflow_id="pending",
        node_id=node_id,
        node_type=req.node_type,
        status="pending",
        input_snapshot=req.content,
    )
    return {"execution_id": execution.id, "status": "pending", "message": "Node execution queued"}


@router.post("/canvas/batch-execute")
async def batch_execute(req: BatchExecuteRequest):
    """Batch execute multiple canvas nodes."""
    # TODO Phase 3
    return {"status": "queued", "node_count": len(req.node_ids)}


@router.get("/canvas/nodes/{node_id}/status")
async def get_node_status(node_id: str):
    """Get execution status of a canvas node."""
    # TODO Phase 3
    return {"node_id": node_id, "status": "idle"}


# ══════════════════════════════════════════════════════════════
# 4. Data Sync
# ══════════════════════════════════════════════════════════════

@router.post("/canvas/sync/from-project")
async def sync_from_project(req: SyncFromProjectRequest):
    """Load project data (Scene/Shot/Assets) into canvas format."""
    # The actual conversion is done on the frontend via canvasIntegrationAdapter.
    # This endpoint can return raw project data for the frontend to process.
    return {"status": "ok", "message": "Use frontend adapter for conversion"}


@router.post("/canvas/sync/to-project")
async def sync_to_project(req: SyncToProjectRequest):
    """Write back canvas results to project (update Shot visual_prompt, etc.)."""
    # TODO Phase 4: implement write-back logic
    return {"status": "ok", "updated_count": len(req.results)}
