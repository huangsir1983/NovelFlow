"""Novel import API — async pipeline with SSE progress streaming.

Endpoints:
  POST /projects/{id}/import/novel       — upload file, start async pipeline
  GET  /projects/{id}/import/events      — SSE stream for real-time progress
  GET  /projects/{id}/import/status      — polling fallback
  POST /projects/{id}/import/retry       — retry from failed phase
  GET  /projects/{id}/shots              — get all shots for a project
  GET  /projects/{id}/shot-groups        — get all shot groups for a project
  GET  /projects/{id}/props              — get all props for a project
  GET  /projects/{id}/variants           — get all character variants for a project
  GET  /style-templates                  — list available style templates
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db, SessionLocal
from models.project import Project
from models.chapter import Chapter
from models.import_task import ImportTask
from models.shot import Shot
from models.shot_group import ShotGroup
from models.prop import Prop
from models.character_variant import CharacterVariant
from models.style_template import StyleTemplate
from services.event_bus import get_events, event_count, subscribe

logger = logging.getLogger(__name__)

router = APIRouter(tags=["import"])

ALLOWED_EXTENSIONS = {"txt", "md", "docx", "epub", "pdf"}

# Module-level bounded thread pool for import pipelines
_import_executor = ThreadPoolExecutor(
    max_workers=settings.max_concurrent_imports,
    thread_name_prefix="import",
)

# Track active import count for concurrency limiting
import threading
_active_imports = 0
_active_lock = threading.Lock()


def get_active_import_count() -> int:
    """Return the current number of active imports (for health check)."""
    with _active_lock:
        return _active_imports


def shutdown_executor(wait: bool = True):
    """Graceful shutdown of the import executor (called from main.py)."""
    _import_executor.shutdown(wait=wait, cancel_futures=False)


# ─── Response Models ────────────────────────────────────────────


class ImportTaskResponse(BaseModel):
    task_id: str
    status: str
    current_phase: str


class ImportStatusResponse(BaseModel):
    task_id: str
    status: str
    current_phase: str
    progress: dict
    error: str | None = None


# Legacy response for backward compat
class ImportResult(BaseModel):
    chapter_count: int
    character_count: int
    beat_count: int
    scene_count: int
    location_count: int
    stage: str


# ─── POST: Start Import ────────────────────────────────────────


@router.post("/projects/{project_id}/import/novel", response_model=ImportTaskResponse)
def import_novel(
    project_id: str,
    file: UploadFile = File(...),
    style_template_id: str | None = Query(None, description="Optional style template ID"),
    db: Session = Depends(get_db),
):
    """Upload a novel file and start async import pipeline. Returns task_id for SSE tracking."""
    global _active_imports

    # Check concurrency limit
    with _active_lock:
        if _active_imports >= settings.max_concurrent_imports:
            raise HTTPException(
                status_code=429,
                detail=f"Too many concurrent imports ({settings.max_concurrent_imports}). Please try again later.",
            )

    # Validate project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate style template if provided
    if style_template_id:
        tpl = db.query(StyleTemplate).filter(StyleTemplate.id == style_template_id).first()
        if not tpl:
            raise HTTPException(status_code=404, detail="Style template not found")

    # Validate file extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Validate file size
    file_bytes = file.file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.max_upload_size_mb}MB")

    # Read file content
    from services.novel_parser import read_file

    try:
        full_text = read_file(file_bytes, file.filename or "upload.txt")
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    # Create ImportTask
    task_id = str(uuid4())
    task = ImportTask(
        id=task_id,
        project_id=project_id,
        status="pending",
        current_phase="streaming",
        progress={},
        full_text=full_text,
        style_template_id=style_template_id,
    )
    db.add(task)
    db.commit()

    # Submit to bounded thread pool
    _submit_pipeline(task_id, project_id, full_text)

    return ImportTaskResponse(
        task_id=task_id,
        status="pending",
        current_phase="streaming",
    )


def _submit_pipeline(task_id: str, project_id: str, full_text: str):
    """Submit a pipeline run to the bounded executor with active count tracking."""
    global _active_imports

    from services.import_pipeline import ImportPipeline

    pipeline = ImportPipeline(
        task_id=task_id,
        project_id=project_id,
        full_text=full_text,
        db_factory=SessionLocal,
    )

    def _run_and_track():
        global _active_imports
        with _active_lock:
            _active_imports += 1
        try:
            pipeline.run()
        finally:
            with _active_lock:
                _active_imports -= 1

    _import_executor.submit(_run_and_track)


# ─── GET: SSE Event Stream ─────────────────────────────────────


@router.get("/projects/{project_id}/import/events")
def import_events(
    project_id: str,
    task_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """SSE endpoint for real-time import progress via Redis event bus."""

    # Validate task exists and belongs to project
    task = db.query(ImportTask).filter(
        ImportTask.id == task_id,
        ImportTask.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Import task not found")

    def event_stream():
        """Generator that yields SSE events from the Redis event bus.

        Uses subscribe() to block-wait for notifications instead of polling.
        Sends heartbeat every 15s if no events arrive.
        """
        last_event_idx = 0
        max_idle_cycles = 480  # ~2 hours at 15s per cycle

        try:
            for _ in range(max_idle_cycles):
                # Get any new events
                new_events = get_events(task_id, since=last_event_idx)
                if new_events:
                    for event in new_events:
                        last_event_idx += 1
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                        # Check if pipeline is done
                        if event.get("type") in ("pipeline_complete", "error"):
                            return
                else:
                    # No new events — check DB for terminal state (cross-worker)
                    check_db = SessionLocal()
                    try:
                        check_task = check_db.query(ImportTask).filter(ImportTask.id == task_id).first()
                        if check_task and check_task.status in ("completed", "failed"):
                            # Get any remaining events
                            final_events = get_events(task_id, since=last_event_idx)
                            for event in final_events:
                                last_event_idx += 1
                                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                            if check_task.status == "completed":
                                yield f"data: {json.dumps({'type': 'pipeline_complete', 'summary': check_task.progress or {}}, ensure_ascii=False)}\n\n"
                            else:
                                yield f"data: {json.dumps({'type': 'error', 'message': check_task.error or 'Unknown error', 'retryable': True}, ensure_ascii=False)}\n\n"
                            return
                    finally:
                        check_db.close()

                # Block-wait for notification (Redis SUBSCRIBE or threading.Event)
                notified = subscribe(task_id, timeout=15.0)
                if not notified:
                    # Timeout — send heartbeat
                    yield ": heartbeat\n\n"

            # Max idle reached
            logger.warning(f"SSE stream for task {task_id} reached max idle cycles")
            yield f"data: {json.dumps({'type': 'error', 'message': 'SSE stream timeout', 'retryable': True}, ensure_ascii=False)}\n\n"

        except GeneratorExit:
            logger.info(f"SSE client disconnected for task {task_id}")
        except Exception as e:
            logger.warning(f"SSE stream error for task {task_id}: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── GET: Status (Polling Fallback) ────────────────────────────


@router.get("/projects/{project_id}/import/status", response_model=ImportStatusResponse)
def import_status(
    project_id: str,
    task_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Polling endpoint for import status. Use SSE /events when possible."""

    task = db.query(ImportTask).filter(
        ImportTask.id == task_id,
        ImportTask.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Import task not found")

    return ImportStatusResponse(
        task_id=task.id,
        status=task.status,
        current_phase=task.current_phase,
        progress=task.progress or {},
        error=task.error,
    )


# ─── POST: Retry from Failed Phase ─────────────────────────────


@router.post("/projects/{project_id}/import/retry", response_model=ImportTaskResponse)
def import_retry(
    project_id: str,
    task_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Retry import from the phase where it failed. Resumes using cached synopsis."""
    global _active_imports

    task = db.query(ImportTask).filter(
        ImportTask.id == task_id,
        ImportTask.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Import task not found")

    if task.status not in ("failed",):
        raise HTTPException(status_code=400, detail=f"Cannot retry task with status '{task.status}'")

    # Check concurrency limit
    with _active_lock:
        if _active_imports >= settings.max_concurrent_imports:
            raise HTTPException(
                status_code=429,
                detail=f"Too many concurrent imports ({settings.max_concurrent_imports}). Please try again later.",
            )

    # Reset status to running, keep current_phase for resume
    task.status = "pending"
    task.error = None
    db.commit()

    # We need the original full text — try task.full_text first, then reconstruct from chapters.
    full_text = task.full_text
    if not full_text:
        chapters = (
            db.query(Chapter)
            .filter(Chapter.project_id == project_id)
            .order_by(Chapter.order)
            .all()
        )
        if chapters and any(ch.content for ch in chapters):
            full_text = "\n\n".join(ch.content for ch in chapters if ch.content)
        else:
            raise HTTPException(
                status_code=400,
                detail="No original text found. Please re-upload the file.",
            )

    _submit_pipeline(task_id, project_id, full_text)

    return ImportTaskResponse(
        task_id=task_id,
        status="running",
        current_phase=task.current_phase,
    )


# ─── GET: Style Templates ──────────────────────────────────────


@router.get("/style-templates")
def list_style_templates(db: Session = Depends(get_db)):
    """Return all available style templates (built-in + user-defined)."""
    templates = (
        db.query(StyleTemplate)
        .order_by(StyleTemplate.sort_order)
        .all()
    )
    return [
        {
            "id": t.id,
            "name": t.name,
            "name_en": t.name_en or "",
            "description": t.description or "",
            "style_tags": t.style_tags or [],
            "style_negative": t.style_negative or "",
            "preview_image_url": t.preview_image_url or "",
            "category": t.category or "",
            "is_builtin": t.is_builtin,
            "sort_order": t.sort_order,
        }
        for t in templates
    ]


# ─── GET: Project Shots ──────────────────────────────────────────


@router.get("/projects/{project_id}/shots")
def get_project_shots(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Get all shots for a project, ordered by order field."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    shots = (
        db.query(Shot)
        .filter(Shot.project_id == project_id)
        .order_by(Shot.order)
        .all()
    )
    return [
        {
            "id": s.id,
            "project_id": s.project_id,
            "scene_id": s.scene_id,
            "shot_number": s.shot_number,
            "goal": s.goal,
            "composition": s.composition,
            "camera_angle": s.camera_angle,
            "camera_movement": s.camera_movement,
            "framing": s.framing,
            "duration_estimate": s.duration_estimate,
            "characters_in_frame": s.characters_in_frame or [],
            "emotion_target": s.emotion_target,
            "dramatic_intensity": s.dramatic_intensity,
            "transition_in": s.transition_in,
            "transition_out": s.transition_out,
            "description": s.description,
            "visual_prompt": s.visual_prompt,
            "order": s.order,
            "status": s.status or "draft",
            "candidates": s.candidates or [],
            "quality_score": s.quality_score or {},
            "next_action": s.next_action or "",
        }
        for s in shots
    ]


# ─── GET: Project Shot Groups ────────────────────────────────────


@router.get("/projects/{project_id}/shot-groups")
def get_project_shot_groups(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Get all shot groups for a project, ordered by order field."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    groups = (
        db.query(ShotGroup)
        .filter(ShotGroup.project_id == project_id)
        .order_by(ShotGroup.order)
        .all()
    )
    return [
        {
            "id": g.id,
            "project_id": g.project_id,
            "scene_id": g.scene_id,
            "shot_ids": g.shot_ids or [],
            "segment_number": g.segment_number,
            "duration": g.duration,
            "transition_type": g.transition_type,
            "emotional_beat": g.emotional_beat,
            "continuity": g.continuity,
            "vff_body": g.vff_body,
            "merge_rationale": g.merge_rationale,
            "style_metadata": g.style_metadata or {},
            "visual_prompt_positive": g.visual_prompt_positive,
            "visual_prompt_negative": g.visual_prompt_negative,
            "style_tags": g.style_tags or [],
            "order": g.order,
        }
        for g in groups
    ]


# ─── GET: Project Props ────────────────────────────────────────────


@router.get("/projects/{project_id}/props")
def get_project_props(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Get all props for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    props = (
        db.query(Prop)
        .filter(Prop.project_id == project_id)
        .order_by(Prop.is_major.desc(), Prop.appearance_count.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "project_id": p.project_id,
            "name": p.name,
            "category": p.category or "",
            "description": p.description or "",
            "visual_reference": p.visual_reference or "",
            "visual_prompt_negative": p.visual_prompt_negative or "",
            "narrative_function": p.narrative_function or "",
            "is_motif": p.is_motif or False,
            "is_major": p.is_major or False,
            "scenes_present": p.scenes_present or [],
            "appearance_count": p.appearance_count or 0,
            "emotional_association": p.emotional_association or "",
        }
        for p in props
    ]


# ─── GET: Project Character Variants ───────────────────────────────


@router.get("/projects/{project_id}/variants")
def get_project_variants(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Get all character variants for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    variants = (
        db.query(CharacterVariant)
        .filter(CharacterVariant.project_id == project_id)
        .all()
    )
    return [
        {
            "id": v.id,
            "project_id": v.project_id,
            "character_id": v.character_id,
            "variant_type": v.variant_type or "",
            "variant_name": v.variant_name or "",
            "tags": v.tags or [],
            "scene_ids": v.scene_ids or [],
            "trigger": v.trigger or "",
            "appearance_delta": v.appearance_delta or {},
            "costume_override": v.costume_override or {},
            "visual_reference": v.visual_reference or "",
            "visual_prompt_negative": v.visual_prompt_negative or "",
            "emotional_tone": v.emotional_tone or "",
        }
        for v in variants
    ]
