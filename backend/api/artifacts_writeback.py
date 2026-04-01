"""Artifacts writeback API skeleton with audit trail."""

from datetime import datetime, UTC
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/artifacts/writeback", tags=["artifacts/writeback"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class WritebackPreviewRequest(BaseModel):
    project_id: str
    artifact_id: str
    target: str
    content: str
    base_version: str | None = None


class WritebackPreviewResponse(BaseModel):
    preview_id: str
    project_id: str
    artifact_id: str
    target: str
    status: str
    diff_summary: str
    created_at: str


class WritebackDecisionRequest(BaseModel):
    preview_id: str
    operator: str
    note: str | None = None


class WritebackDecisionResponse(BaseModel):
    preview_id: str
    status: str
    version_id: str | None = None
    decided_at: str


class WritebackVersionItem(BaseModel):
    version_id: str
    project_id: str
    artifact_id: str
    target: str
    operator: str
    created_at: str


class WritebackVersionListResponse(BaseModel):
    project_id: str
    total: int
    items: list[WritebackVersionItem]


_preview_records: dict[str, dict[str, Any]] = {}
_version_records: dict[str, list[WritebackVersionItem]] = {}


def _reset_state_for_tests() -> None:
    _preview_records.clear()
    _version_records.clear()


@router.post("/preview", response_model=WritebackPreviewResponse, status_code=201)
def create_writeback_preview(data: WritebackPreviewRequest):
    preview_id = str(uuid4())
    created_at = _now_iso()
    preview = {
        "preview_id": preview_id,
        "project_id": data.project_id,
        "artifact_id": data.artifact_id,
        "target": data.target,
        "status": "pending",
        "content": data.content,
        "base_version": data.base_version,
        "created_at": created_at,
        "updated_at": created_at,
    }
    _preview_records[preview_id] = preview

    return WritebackPreviewResponse(
        preview_id=preview_id,
        project_id=data.project_id,
        artifact_id=data.artifact_id,
        target=data.target,
        status="pending",
        diff_summary=f"pending_writeback chars={len(data.content)}",
        created_at=created_at,
    )


def _get_preview_or_404(preview_id: str) -> dict[str, Any]:
    preview = _preview_records.get(preview_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Writeback preview not found")
    return preview


@router.post("/confirm", response_model=WritebackDecisionResponse)
def confirm_writeback(data: WritebackDecisionRequest):
    preview = _get_preview_or_404(data.preview_id)
    if preview["status"] == "rejected":
        raise HTTPException(status_code=409, detail="Writeback preview is already rejected")

    version_id = str(uuid4())
    decided_at = _now_iso()
    preview["status"] = "confirmed"
    preview["updated_at"] = decided_at

    entry = WritebackVersionItem(
        version_id=version_id,
        project_id=preview["project_id"],
        artifact_id=preview["artifact_id"],
        target=preview["target"],
        operator=data.operator,
        created_at=decided_at,
    )
    _version_records.setdefault(preview["project_id"], []).append(entry)

    return WritebackDecisionResponse(
        preview_id=data.preview_id,
        status="confirmed",
        version_id=version_id,
        decided_at=decided_at,
    )


@router.post("/reject", response_model=WritebackDecisionResponse)
def reject_writeback(data: WritebackDecisionRequest):
    preview = _get_preview_or_404(data.preview_id)
    decided_at = _now_iso()
    preview["status"] = "rejected"
    preview["updated_at"] = decided_at
    return WritebackDecisionResponse(
        preview_id=data.preview_id,
        status="rejected",
        decided_at=decided_at,
    )


@router.get("/projects/{project_id}/versions", response_model=WritebackVersionListResponse)
def list_writeback_versions(project_id: str):
    items = _version_records.get(project_id, [])
    return WritebackVersionListResponse(project_id=project_id, total=len(items), items=items)
