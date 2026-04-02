"""Workflow Execution API — start, monitor, cancel, retry, resume chain executions."""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.workflow_execution import WorkflowExecution, WorkflowStepRun
from models.canvas_workflow import CanvasWorkflow
from services.workflow_engine import workflow_engine
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflow-execution"])


# ══════════════════════════════════════════════════════════════
# Request Models
# ══════════════════════════════════════════════════════════════

class StartExecutionRequest(BaseModel):
    workflowId: str
    templateId: str
    nodeIds: list
    concurrencyLimit: int = 3


# ══════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════

@router.post("/projects/{project_id}/workflow-executions")
def start_execution(project_id: str, req: StartExecutionRequest, db: Session = Depends(get_db)):
    """Create and start a new workflow execution from a chain template."""
    # Validate workflow exists
    workflow = db.query(CanvasWorkflow).get(req.workflowId)
    if not workflow:
        raise HTTPException(status_code=404, detail="Canvas workflow not found")

    try:
        execution = workflow_engine.instantiate(
            db=db,
            template_id=req.templateId,
            target_node_ids=req.nodeIds,
            project_id=project_id,
            workflow_id=req.workflowId,
            concurrency_limit=req.concurrencyLimit,
        )
        execution = workflow_engine.start_execution(db, execution.id)
        return execution.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflow-executions/{execution_id}")
def get_execution(execution_id: str, db: Session = Depends(get_db)):
    """Get execution status including all step runs."""
    execution = db.query(WorkflowExecution).get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    step_runs = db.query(WorkflowStepRun).filter(
        WorkflowStepRun.execution_id == execution_id
    ).all()

    result = execution.to_dict()
    result["stepRuns"] = [sr.to_dict() for sr in step_runs]
    return result


@router.post("/workflow-executions/{execution_id}/cancel")
def cancel_execution(execution_id: str, db: Session = Depends(get_db)):
    """Cancel a running or paused execution."""
    try:
        execution = workflow_engine.cancel_execution(db, execution_id)
        return execution.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/workflow-executions/{execution_id}/retry")
def retry_execution(execution_id: str, db: Session = Depends(get_db)):
    """Retry a failed execution from its failed steps."""
    try:
        execution = workflow_engine.retry_from_failed(db, execution_id)
        return execution.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/workflow-executions/{execution_id}/resume")
def resume_execution(execution_id: str, db: Session = Depends(get_db)):
    """Resume a paused execution (e.g. after user-select-frame)."""
    try:
        execution = workflow_engine.resume_execution(db, execution_id)
        return execution.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflow-executions/{execution_id}/events")
def execution_events(execution_id: str, db: Session = Depends(get_db)):
    """SSE stream of execution progress events."""
    def stream():
        import time
        while True:
            exec_ = db.query(WorkflowExecution).get(execution_id)
            if not exec_:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Not found'})}\n\n"
                break
            step_runs = db.query(WorkflowStepRun).filter(
                WorkflowStepRun.execution_id == execution_id
            ).all()
            yield f"data: {json.dumps({'type': 'progress', 'execution': exec_.to_dict(), 'stepRuns': [sr.to_dict() for sr in step_runs]}, ensure_ascii=False)}\n\n"
            if exec_.status in ('success', 'error', 'cancelled'):
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            time.sleep(2)

    return StreamingResponse(stream(), media_type="text/event-stream")
