"""Budget API — AI call cost tracking and aggregation."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.project import Project
from models.ai_call_log import AICallLog

router = APIRouter(tags=["budget"])


@router.get("/projects/{project_id}/budget")
def get_project_budget(project_id: str, db: Session = Depends(get_db)):
    """Get aggregated AI cost data for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logs = db.query(AICallLog).filter(AICallLog.project_id == project_id).all()

    total_cost = sum(log.estimated_cost for log in logs)
    total_input_tokens = sum(log.input_tokens for log in logs)
    total_output_tokens = sum(log.output_tokens for log in logs)

    # Group by operation_type
    by_operation = {}
    for log in logs:
        op = log.operation_type or "unknown"
        if op not in by_operation:
            by_operation[op] = {"count": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        by_operation[op]["count"] += 1
        by_operation[op]["cost"] += log.estimated_cost
        by_operation[op]["input_tokens"] += log.input_tokens
        by_operation[op]["output_tokens"] += log.output_tokens

    # Group by provider
    by_provider = {}
    for log in logs:
        prov = log.provider or "unknown"
        if prov not in by_provider:
            by_provider[prov] = {"count": 0, "cost": 0.0}
        by_provider[prov]["count"] += 1
        by_provider[prov]["cost"] += log.estimated_cost

    return {
        "project_id": project_id,
        "total_calls": len(logs),
        "total_cost_usd": round(total_cost, 4),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "by_operation": by_operation,
        "by_provider": by_provider,
    }
