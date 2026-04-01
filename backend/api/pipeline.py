"""Workflow pipeline API skeleton for staged rollout."""

from datetime import datetime, UTC
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/workflow/pipeline", tags=["workflow/pipeline"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class PipelineRunCreateRequest(BaseModel):
    project_id: str
    workflow_id: str = "default"
    input_payload: dict[str, Any] = Field(default_factory=dict)


class PipelineRunResponse(BaseModel):
    run_id: str
    project_id: str
    workflow_id: str
    status: str
    created_at: str
    updated_at: str
    node_count: int


class NodeRunRequest(BaseModel):
    input_payload: dict[str, Any] = Field(default_factory=dict)
    simulate_failure: bool = False


class NodeRunResponse(BaseModel):
    run_id: str
    node_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    error: str | None = None


class PipelineResumeRequest(BaseModel):
    reason: str | None = None


class PipelineLogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    node_id: str | None = None


class PipelineLogsResponse(BaseModel):
    run_id: str
    total: int
    logs: list[PipelineLogEntry]


class PipelineRecoverRequest(BaseModel):
    strategy: str = "resume_failed_nodes"


_pipeline_runs: dict[str, dict[str, Any]] = {}
_pipeline_logs: dict[str, list[PipelineLogEntry]] = {}


def _append_log(run_id: str, level: str, message: str, node_id: str | None = None) -> None:
    entry = PipelineLogEntry(
        timestamp=_now_iso(),
        level=level,
        message=message,
        node_id=node_id,
    )
    _pipeline_logs.setdefault(run_id, []).append(entry)


def _get_run_or_404(run_id: str) -> dict[str, Any]:
    run = _pipeline_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


def _to_run_response(run: dict[str, Any]) -> PipelineRunResponse:
    return PipelineRunResponse(
        run_id=run["run_id"],
        project_id=run["project_id"],
        workflow_id=run["workflow_id"],
        status=run["status"],
        created_at=run["created_at"],
        updated_at=run["updated_at"],
        node_count=len(run["nodes"]),
    )


def _reset_state_for_tests() -> None:
    _pipeline_runs.clear()
    _pipeline_logs.clear()


@router.post("/runs", response_model=PipelineRunResponse, status_code=201)
def create_pipeline_run(data: PipelineRunCreateRequest):
    run_id = str(uuid4())
    now = _now_iso()
    _pipeline_runs[run_id] = {
        "run_id": run_id,
        "project_id": data.project_id,
        "workflow_id": data.workflow_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "nodes": {},
        "input_payload": data.input_payload,
    }
    _append_log(run_id, "info", "Pipeline run created")
    return _to_run_response(_pipeline_runs[run_id])


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
def get_pipeline_run(run_id: str):
    run = _get_run_or_404(run_id)
    return _to_run_response(run)


@router.post("/runs/{run_id}/nodes/{node_id}", response_model=NodeRunResponse)
def run_single_node(run_id: str, node_id: str, data: NodeRunRequest):
    run = _get_run_or_404(run_id)
    started_at = _now_iso()
    run["status"] = "running"
    run["updated_at"] = started_at

    node = {
        "run_id": run_id,
        "node_id": node_id,
        "status": "running",
        "started_at": started_at,
        "finished_at": None,
        "error": None,
        "input_payload": data.input_payload,
    }
    run["nodes"][node_id] = node
    _append_log(run_id, "info", "Node execution started", node_id=node_id)

    node["finished_at"] = _now_iso()
    if data.simulate_failure:
        node["status"] = "failed"
        node["error"] = "Simulated node failure for recovery testing"
        run["status"] = "failed"
        _append_log(run_id, "error", "Node execution failed", node_id=node_id)
    else:
        node["status"] = "succeeded"
        _append_log(run_id, "info", "Node execution succeeded", node_id=node_id)
        if all(item["status"] == "succeeded" for item in run["nodes"].values()):
            run["status"] = "succeeded"

    run["updated_at"] = _now_iso()
    return NodeRunResponse(**node)


@router.post("/runs/{run_id}/resume", response_model=PipelineRunResponse)
def resume_pipeline_run(run_id: str, data: PipelineResumeRequest):
    run = _get_run_or_404(run_id)
    run["status"] = "running"
    run["updated_at"] = _now_iso()
    _append_log(run_id, "info", f"Run resumed: {data.reason or 'manual_resume'}")
    return _to_run_response(run)


@router.post("/runs/{run_id}/continue", response_model=PipelineRunResponse)
def continue_pipeline_run(run_id: str):
    run = _get_run_or_404(run_id)
    run["status"] = "running"
    run["updated_at"] = _now_iso()
    _append_log(run_id, "info", "Pipeline continue requested")
    return _to_run_response(run)


@router.post("/runs/{run_id}/recover", response_model=PipelineRunResponse)
def recover_pipeline_run(run_id: str, data: PipelineRecoverRequest):
    run = _get_run_or_404(run_id)
    failed_nodes = [
        node_id
        for node_id, node in run["nodes"].items()
        if node["status"] == "failed"
    ]
    for node_id in failed_nodes:
        run["nodes"][node_id]["status"] = "pending"
        run["nodes"][node_id]["error"] = None
    run["status"] = "running"
    run["updated_at"] = _now_iso()
    _append_log(run_id, "warning", f"Recovery requested with strategy={data.strategy}")
    return _to_run_response(run)


@router.get("/runs/{run_id}/logs", response_model=PipelineLogsResponse)
def get_pipeline_run_logs(run_id: str):
    _get_run_or_404(run_id)
    logs = _pipeline_logs.get(run_id, [])
    return PipelineLogsResponse(run_id=run_id, total=len(logs), logs=logs)
