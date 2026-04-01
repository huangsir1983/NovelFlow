"""Project export API — MVP artifact export to configured storage."""

import json
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.project import Project
from models.scene import Scene
from models.shot import Shot
from models.shot_group import ShotGroup
from services.storage_adapter import get_storage
from services.task_quota import acquire_quota, release_quota

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])

# In-memory latest export cache (minimal intrusive, can be replaced by DB table later)
_latest_exports: dict[str, dict] = {}


class ProjectExportResponse(BaseModel):
    project_id: str
    export_type: str
    storage_provider: str
    storage_key: str
    storage_uri: str
    generated_at: str


@router.get("/projects/{project_id}/export/latest", response_model=ProjectExportResponse)
def get_latest_export(project_id: str):
    latest = _latest_exports.get(project_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No export record found")
    return ProjectExportResponse(**latest)


@router.post("/projects/{project_id}/export/mvp", response_model=ProjectExportResponse)
def export_project_mvp(project_id: str, db: Session = Depends(get_db)):
    """Export project MVP timeline bundle JSON and upload to storage.

    This is a minimal export artifact for P0 closure. It does not render video,
    but exports timeline-ready structured data to object storage.
    """
    ok, info, lease = acquire_quota("export", tenant_id="default", project_id=project_id)
    if not ok:
        raise HTTPException(status_code=429, detail={"code": "quota_exceeded", **info})

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        release_quota(lease)
        raise HTTPException(status_code=404, detail="Project not found")

    scenes = (
        db.query(Scene)
        .filter(Scene.project_id == project_id)
        .order_by(Scene.order)
        .all()
    )
    shots = (
        db.query(Shot)
        .filter(Shot.project_id == project_id)
        .order_by(Shot.order)
        .all()
    )
    shot_groups = (
        db.query(ShotGroup)
        .filter(ShotGroup.project_id == project_id)
        .order_by(ShotGroup.order)
        .all()
    )

    image_assets: list[dict] = []
    video_assets: list[dict] = []

    for sh in shots:
        for ref in (sh.reference_assets or []):
            if isinstance(ref, dict):
                url = ref.get("url") or ref.get("storage_uri") or ref.get("uri")
                if url:
                    image_assets.append({
                        "shot_id": sh.id,
                        "source": "reference_assets",
                        "url": url,
                        "meta": ref,
                    })

        for cand in (sh.candidates or []):
            if isinstance(cand, dict):
                url = cand.get("url") or cand.get("image_url") or cand.get("storage_uri")
                video_url = cand.get("video_url")
                if url:
                    image_assets.append({
                        "shot_id": sh.id,
                        "source": "candidates",
                        "url": url,
                        "meta": cand,
                    })
                if video_url:
                    video_assets.append({
                        "shot_id": sh.id,
                        "source": "candidates",
                        "url": video_url,
                        "meta": cand,
                    })

    for g in shot_groups:
        meta = g.style_metadata or {}
        if isinstance(meta, dict):
            if meta.get("image_url"):
                image_assets.append({
                    "shot_group_id": g.id,
                    "source": "shot_group.style_metadata",
                    "url": meta.get("image_url"),
                    "meta": meta,
                })
            if meta.get("video_url"):
                video_assets.append({
                    "shot_group_id": g.id,
                    "source": "shot_group.style_metadata",
                    "url": meta.get("video_url"),
                    "meta": meta,
                })

    payload = {
        "export_type": "mvp_timeline_bundle",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "project": {
            "id": project.id,
            "name": project.name,
            "genre": project.genre,
            "logline": project.logline,
            "theme": project.theme,
        },
        "assets": {
            "images": image_assets,
            "videos": video_assets,
        },
        "scenes": [
            {
                "id": s.id,
                "order": s.order,
                "heading": s.heading,
                "location": s.location,
                "time_of_day": s.time_of_day,
                "core_event": s.core_event,
                "estimated_duration_s": s.estimated_duration_s,
            }
            for s in scenes
        ],
        "shots": [
            {
                "id": sh.id,
                "scene_id": sh.scene_id,
                "order": sh.order,
                "shot_number": sh.shot_number,
                "description": sh.description,
                "duration_estimate": sh.duration_estimate,
                "camera_angle": sh.camera_angle,
                "camera_movement": sh.camera_movement,
                "framing": sh.framing,
            }
            for sh in shots
        ],
        "shot_groups": [
            {
                "id": g.id,
                "scene_id": g.scene_id,
                "order": g.order,
                "segment_number": g.segment_number,
                "shot_ids": g.shot_ids or [],
                "duration": g.duration,
                "transition_type": g.transition_type,
                "visual_prompt_positive": g.visual_prompt_positive,
                "visual_prompt_negative": g.visual_prompt_negative,
            }
            for g in shot_groups
        ],
    }

    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    key = f"assets/exports/{project_id}/{uuid4()}.json"

    try:
        storage = get_storage()
        stored = storage.put_bytes(
            object_key=key,
            data=data,
            content_type="application/json",
        )
    except Exception as e:
        logger.error("Project export storage failed: %s", e)
        release_quota(lease)
        raise HTTPException(status_code=503, detail=f"Export storage failed: {e}")

    latest = {
        "project_id": project_id,
        "export_type": "mvp_timeline_bundle",
        "storage_provider": stored.provider,
        "storage_key": stored.object_key,
        "storage_uri": stored.uri,
        "generated_at": payload["generated_at"],
    }
    _latest_exports[project_id] = latest
    release_quota(lease)

    return ProjectExportResponse(**latest)
