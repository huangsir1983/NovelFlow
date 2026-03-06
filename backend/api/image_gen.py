"""Image generation API — Gemini-based AI image generation."""

import base64
import logging
import os
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["image"])


# --- Schemas ---

class TextToImageRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "3:4"   # 1:1 | 3:4 | 4:3 | 16:9 | 9:16
    image_size: str = "2K"      # 1K | 2K | 4K (4K needs 4k model)


class ImageGenerateResponse(BaseModel):
    image_base64: str
    mime_type: str
    model: str
    elapsed: float
    provider: str


# --- Routes ---

@router.post("/ai/generate-image", response_model=ImageGenerateResponse)
def generate_image_from_text(
    data: TextToImageRequest,
    db: Session = Depends(get_db),
):
    """Generate an image from a text prompt (text-to-image)."""
    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    from services.ai_engine import ai_engine

    try:
        result = ai_engine.generate_image(
            prompt=data.prompt,
            aspect_ratio=data.aspect_ratio,
            image_size=data.image_size,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    image_b64 = base64.b64encode(result["image_data"]).decode("utf-8")

    return ImageGenerateResponse(
        image_base64=image_b64,
        mime_type=result["mime_type"],
        model=result["model"],
        elapsed=result["elapsed"],
        provider=result["provider"],
    )


@router.post("/ai/generate-image/upload")
def generate_image_with_reference(
    prompt: str = Form(...),
    aspect_ratio: str = Form("3:4"),
    image_size: str = Form("2K"),
    reference: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    """Generate an image with an optional reference image (img2img).

    Accepts multipart form with:
    - prompt: text description
    - reference: optional reference image file
    - aspect_ratio: output aspect ratio
    - image_size: output resolution
    """
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    ref_bytes = None
    ref_mime = "image/png"
    if reference and reference.filename:
        ref_bytes = reference.file.read()
        if len(ref_bytes) > 10 * 1024 * 1024:  # 10MB limit for reference images
            raise HTTPException(status_code=400, detail="Reference image too large (max 10MB)")
        ref_mime = reference.content_type or "image/png"

    from services.ai_engine import ai_engine

    try:
        result = ai_engine.generate_image(
            prompt=prompt,
            reference_image=ref_bytes,
            reference_mime=ref_mime,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    image_b64 = base64.b64encode(result["image_data"]).decode("utf-8")

    return {
        "image_base64": image_b64,
        "mime_type": result["mime_type"],
        "model": result["model"],
        "elapsed": result["elapsed"],
        "provider": result["provider"],
    }


@router.post("/ai/generate-image/raw")
def generate_image_raw(
    data: TextToImageRequest,
    db: Session = Depends(get_db),
):
    """Generate an image and return raw binary (for direct <img> use)."""
    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    from services.ai_engine import ai_engine

    try:
        result = ai_engine.generate_image(
            prompt=data.prompt,
            aspect_ratio=data.aspect_ratio,
            image_size=data.image_size,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return Response(
        content=result["image_data"],
        media_type=result["mime_type"],
        headers={
            "X-Model": result["model"],
            "X-Provider": result["provider"],
            "X-Elapsed": str(result["elapsed"]),
        },
    )
