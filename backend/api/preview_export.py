"""Preview export API skeleton for Animatic bundle and CapCut draft mapping."""

from datetime import datetime, UTC
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/preview/export", tags=["preview/export"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class PreviewExportRequest(BaseModel):
    quality: str = "standard"
    include_subtitles: bool = True
    include_tts: bool = True


class PreviewExportResponse(BaseModel):
    export_id: str
    project_id: str
    version_id: str
    format: str
    storage_uri: str
    created_at: str


class PreviewVersionMappingResponse(BaseModel):
    project_id: str
    version_id: str
    timeline_track_count: int
    shot_card_count: int
    mapping_status: str


_exports: dict[str, PreviewExportResponse] = {}
_version_mapping: dict[str, PreviewVersionMappingResponse] = {}


def _mapping_key(project_id: str, version_id: str) -> str:
    return f"{project_id}:{version_id}"


def _reset_state_for_tests() -> None:
    _exports.clear()
    _version_mapping.clear()


@router.post("/projects/{project_id}/capcut-draft", response_model=PreviewExportResponse, status_code=201)
def export_capcut_draft(project_id: str, data: PreviewExportRequest):
    export_id = str(uuid4())
    version_id = str(uuid4())
    created_at = _now_iso()

    result = PreviewExportResponse(
        export_id=export_id,
        project_id=project_id,
        version_id=version_id,
        format="capcut_draft",
        storage_uri=f"mock://preview/{project_id}/{export_id}.zip",
        created_at=created_at,
    )
    _exports[export_id] = result
    _version_mapping[_mapping_key(project_id, version_id)] = PreviewVersionMappingResponse(
        project_id=project_id,
        version_id=version_id,
        timeline_track_count=3 if data.include_tts else 2,
        shot_card_count=24,
        mapping_status="ready",
    )
    return result


@router.get(
    "/projects/{project_id}/versions/{version_id}/mapping",
    response_model=PreviewVersionMappingResponse,
)
def get_version_mapping(project_id: str, version_id: str):
    mapping = _version_mapping.get(_mapping_key(project_id, version_id))
    if mapping is None:
        raise HTTPException(status_code=404, detail="Version mapping not found")
    return mapping
