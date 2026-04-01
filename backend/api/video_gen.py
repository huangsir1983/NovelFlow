"""Video generation API — Grok-based AI video generation."""

import logging
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["video"])


def _acquire_video_quota(project_id: str = "global"):
    from fastapi import HTTPException
    from services.task_quota import acquire_quota

    ok, info, lease = acquire_quota("video", tenant_id="default", project_id=project_id)
    if not ok:
        raise HTTPException(status_code=429, detail={"code": "quota_exceeded", **info})
    return lease


def _archive_video_to_storage(video_url: str) -> tuple[str | None, str | None, str | None]:
    """Best-effort archive provider video URL to configured storage."""
    if not video_url:
        return None, None, None

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.get(video_url)
            resp.raise_for_status()
            data = resp.content
            content_type = resp.headers.get("content-type", "video/mp4")

        from services.storage_adapter import get_storage

        storage = get_storage()
        ext = (content_type.split("/")[-1] or "mp4").split(";")[0]
        object_key = f"assets/videos/{uuid4()}.{ext}"
        stored = storage.put_bytes(
            object_key=object_key,
            data=data,
            content_type=content_type,
        )
        return stored.provider, stored.object_key, stored.uri
    except Exception as e:
        logger.warning("Failed to archive video to storage: %s", e)
        return None, None, None


# --- Schemas ---

class TextToVideoRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"   # 16:9 | 9:16
    seconds: int = 6             # fixed at 6
    size: str = "720P"           # 720P


class VideoGenerateResponse(BaseModel):
    video_url: str
    model: str
    task_id: str
    elapsed: float
    provider: str
    storage_provider: str | None = None
    storage_key: str | None = None
    storage_uri: str | None = None


class VideoTaskStatusResponse(BaseModel):
    task_id: str
    status: str       # queued | processing | completed | failed
    progress: int     # 0-100
    video_url: str | None = None


# --- Routes ---

@router.post("/ai/generate-video", response_model=VideoGenerateResponse)
def generate_video_from_text(
    data: TextToVideoRequest,
    db: Session = Depends(get_db),
):
    """Generate a video from a text prompt (text-to-video).

    This is a synchronous endpoint that internally polls the async video
    generation task until completion. Expect long response times (1-5 min).
    """
    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if data.aspect_ratio not in ("16:9", "9:16"):
        raise HTTPException(status_code=400, detail="aspect_ratio must be '16:9' or '9:16'")

    from services.ai_engine import ai_engine
    from services.task_quota import release_quota

    lease = _acquire_video_quota()
    try:
        result = ai_engine.generate_video(
            prompt=data.prompt,
            aspect_ratio=data.aspect_ratio,
            seconds=data.seconds,
            size=data.size,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        release_quota(lease)

    storage_provider, storage_key, storage_uri = _archive_video_to_storage(result["video_url"])

    return VideoGenerateResponse(
        video_url=result["video_url"],
        model=result["model"],
        task_id=result["task_id"],
        elapsed=result["elapsed"],
        provider=result["provider"],
        storage_provider=storage_provider,
        storage_key=storage_key,
        storage_uri=storage_uri,
    )


@router.post("/ai/generate-video/upload", response_model=VideoGenerateResponse)
def generate_video_with_reference(
    prompt: str = Form(...),
    aspect_ratio: str = Form("16:9"),
    seconds: int = Form(6),
    size: str = Form("720P"),
    reference: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Generate a video from an image + text prompt (image-to-video).

    Accepts multipart form with:
    - prompt: text description of the video motion/style
    - reference: reference image file (the starting frame)
    - aspect_ratio: 16:9 or 9:16
    """
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if aspect_ratio not in ("16:9", "9:16"):
        raise HTTPException(status_code=400, detail="aspect_ratio must be '16:9' or '9:16'")

    ref_bytes = reference.file.read()
    if len(ref_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Reference image too large (max 10MB)")

    ref_mime = reference.content_type or "image/jpeg"

    from services.ai_engine import ai_engine
    from services.task_quota import release_quota

    lease = _acquire_video_quota()
    try:
        result = ai_engine.generate_video(
            prompt=prompt,
            reference_image=ref_bytes,
            reference_mime=ref_mime,
            aspect_ratio=aspect_ratio,
            seconds=seconds,
            size=size,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        release_quota(lease)

    storage_provider, storage_key, storage_uri = _archive_video_to_storage(result["video_url"])

    return VideoGenerateResponse(
        video_url=result["video_url"],
        model=result["model"],
        task_id=result["task_id"],
        elapsed=result["elapsed"],
        provider=result["provider"],
        storage_provider=storage_provider,
        storage_key=storage_key,
        storage_uri=storage_uri,
    )


@router.post("/ai/generate-video/async")
def generate_video_async(
    data: TextToVideoRequest,
    db: Session = Depends(get_db),
):
    """Create a video generation task (returns immediately with task_id).

    Use GET /ai/generate-video/status/{task_id} to poll for completion.
    """
    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if data.aspect_ratio not in ("16:9", "9:16"):
        raise HTTPException(status_code=400, detail="aspect_ratio must be '16:9' or '9:16'")

    from services.ai_engine import ai_engine
    from services.providers.grok_video_adapter import GrokVideoAdapter
    from services.task_quota import release_quota

    lease = _acquire_video_quota()

    # Resolve video routes
    routes = ai_engine._resolve_routes("standard", db=db, model_type="video")
    routes = [(a, m) for a, m in routes if isinstance(a, GrokVideoAdapter)]

    if not routes:
        release_quota(lease)
        raise HTTPException(
            status_code=503,
            detail="No video-capable AI provider configured.",
        )

    adapter, model_id = routes[0]

    try:
        task_id = adapter._create_task(
            model=model_id,
            prompt=data.prompt,
            reference_image=None,
            reference_mime="image/jpeg",
            aspect_ratio=data.aspect_ratio,
            seconds=data.seconds,
            size=data.size,
        )
    except Exception as e:
        release_quota(lease)
        raise HTTPException(status_code=503, detail=str(e))

    release_quota(lease)
    return {"task_id": task_id, "status": "queued", "provider": adapter.provider_name}


@router.get("/ai/generate-video/status/{task_id}", response_model=VideoTaskStatusResponse)
def get_video_task_status(
    task_id: str,
    db: Session = Depends(get_db),
):
    """Poll the status of a video generation task."""
    from services.ai_engine import ai_engine
    from services.providers.grok_video_adapter import GrokVideoAdapter

    routes = ai_engine._resolve_routes("standard", db=db, model_type="video")
    routes = [(a, m) for a, m in routes if isinstance(a, GrokVideoAdapter)]

    if not routes:
        raise HTTPException(status_code=503, detail="No video provider configured.")

    adapter = routes[0][0]

    try:
        import httpx
        url = f"{adapter.base_url}/v1/videos/{task_id}"
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=adapter._headers())
            resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

    video_url = (
        data.get("video_url")
        or data.get("url")
        or (data.get("output", {}) or {}).get("url")
    )

    return VideoTaskStatusResponse(
        task_id=task_id,
        status=data.get("status", "unknown"),
        progress=data.get("progress", 0),
        video_url=video_url,
    )
