"""Image generation API — Gemini-based AI image generation + RunningHub view-angle conversion."""

import base64
import logging
import tempfile
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["image"])


def _acquire_image_quota(project_id: str = "global"):
    from fastapi import HTTPException
    from services.task_quota import acquire_quota

    ok, info, lease = acquire_quota("image", tenant_id="default", project_id=project_id)
    if not ok:
        raise HTTPException(status_code=429, detail={"code": "quota_exceeded", **info})
    return lease


# --- Schemas ---

class ReferenceImageItem(BaseModel):
    data: str           # base64-encoded image
    mime_type: str = "image/jpeg"


class InterleavedPart(BaseModel):
    """A single part in an interleaved text+image sequence for Gemini."""
    type: str           # "text" or "image"
    content: str        # text content, or base64-encoded image data
    mime_type: str = "image/jpeg"  # only used when type="image"


class TextToImageRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "3:4"   # 1:1 | 3:4 | 4:3 | 16:9 | 9:16
    image_size: str = "2K"      # 1K | 2K | 4K (4K needs 4k model)
    reference_images: list[ReferenceImageItem] | None = None  # legacy: all-images-first
    interleaved_parts: list[InterleavedPart] | None = None    # preferred: text+image interleaved


class ImageGenerateResponse(BaseModel):
    image_base64: str
    mime_type: str
    model: str
    elapsed: float
    provider: str
    storage_provider: str | None = None
    storage_key: str | None = None
    storage_uri: str | None = None


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
    from services.task_quota import release_quota

    # Build interleaved parts or legacy reference_images
    interleaved = None
    ref_images = None

    if data.interleaved_parts:
        # Preferred: interleaved text+image parts → direct Gemini parts
        logger.info(f"[IMAGE-API] Received {len(data.interleaved_parts)} interleaved parts")
        interleaved = []
        for i, part in enumerate(data.interleaved_parts):
            if part.type == "text":
                logger.info(f"[IMAGE-API] Part[{i}]: TEXT, len={len(part.content)}")
                interleaved.append({"type": "text", "content": part.content})
            elif part.type == "image":
                raw_bytes = base64.b64decode(part.content)
                logger.info(f"[IMAGE-API] Part[{i}]: IMAGE, b64_len={len(part.content)}, decoded={len(raw_bytes)} bytes, mime={part.mime_type}")
                interleaved.append({
                    "type": "image",
                    "data": raw_bytes,
                    "mime_type": part.mime_type,
                })
    elif data.reference_images:
        ref_images = []
        for ref in data.reference_images:
            ref_images.append({
                "data": base64.b64decode(ref.data),
                "mime_type": ref.mime_type,
            })

    lease = _acquire_image_quota()
    try:
        result = ai_engine.generate_image(
            prompt=data.prompt,
            reference_images=ref_images,
            interleaved_parts=interleaved,
            aspect_ratio=data.aspect_ratio,
            image_size=data.image_size,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        release_quota(lease)

    image_b64 = base64.b64encode(result["image_data"]).decode("utf-8")

    storage_provider = None
    storage_key = None
    storage_uri = None
    try:
        from services.storage_adapter import get_storage

        storage = get_storage()
        object_key = f"assets/images/{uuid4()}.{(result['mime_type'].split('/')[-1] or 'png').split(';')[0]}"
        stored = storage.put_bytes(
            object_key=object_key,
            data=result["image_data"],
            content_type=result["mime_type"],
        )
        storage_provider = stored.provider
        storage_key = stored.object_key
        storage_uri = stored.uri
    except Exception as e:
        logger.warning("Failed to store generated image to storage: %s", e)

    return ImageGenerateResponse(
        image_base64=image_b64,
        mime_type=result["mime_type"],
        model=result["model"],
        elapsed=result["elapsed"],
        provider=result["provider"],
        storage_provider=storage_provider,
        storage_key=storage_key,
        storage_uri=storage_uri,
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
    from services.task_quota import release_quota

    lease = _acquire_image_quota()
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
    finally:
        release_quota(lease)

    image_b64 = base64.b64encode(result["image_data"]).decode("utf-8")

    storage_provider = None
    storage_key = None
    storage_uri = None
    try:
        from services.storage_adapter import get_storage

        storage = get_storage()
        object_key = f"assets/images/{uuid4()}.{(result['mime_type'].split('/')[-1] or 'png').split(';')[0]}"
        stored = storage.put_bytes(
            object_key=object_key,
            data=result["image_data"],
            content_type=result["mime_type"],
        )
        storage_provider = stored.provider
        storage_key = stored.object_key
        storage_uri = stored.uri
    except Exception as e:
        logger.warning("Failed to store generated image to storage: %s", e)

    return {
        "image_base64": image_b64,
        "mime_type": result["mime_type"],
        "model": result["model"],
        "elapsed": result["elapsed"],
        "provider": result["provider"],
        "storage_provider": storage_provider,
        "storage_key": storage_key,
        "storage_uri": storage_uri,
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
    from services.task_quota import release_quota

    lease = _acquire_image_quota()
    try:
        result = ai_engine.generate_image(
            prompt=data.prompt,
            aspect_ratio=data.aspect_ratio,
            image_size=data.image_size,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        release_quota(lease)

    return Response(
        content=result["image_data"],
        media_type=result["mime_type"],
        headers={
            "X-Model": result["model"],
            "X-Provider": result["provider"],
            "X-Elapsed": str(result["elapsed"]),
        },
    )


# --- Panorama Generation (Gemini img2img → equirectangular 360° VR) ---

class PanoramaGenerateRequest(BaseModel):
    reference_storage_key: str   # storage_key of the main location image
    prompt: str                  # location visual_reference description
    style_preset: str = ""       # optional style tag (realistic, 3d_chinese, etc.)


class PanoramaGenerateResponse(BaseModel):
    image_base64: str
    mime_type: str
    model: str
    elapsed: float
    storage_key: str | None = None
    storage_uri: str | None = None


PANORAMA_PROMPT_TEMPLATE = (
    "Generate a seamless 360-degree equirectangular panorama image at 4000x2000 pixels resolution. "
    "The image MUST use equirectangular projection format suitable for spherical VR mapping. "
    "The left edge must connect perfectly and seamlessly to the right edge with no visible seam.\n\n"
    "SPATIAL COMPOSITION & CAMERA:\n"
    "- Create a SPACIOUS, EXPANSIVE, GRAND environment with a strong sense of depth and openness.\n"
    "- CAMERA DISTANCE: Place the camera FAR BACK from the main subject/focal point, as if shooting with a WIDE-ANGLE LENS from a DISTANT vantage point.\n"
    "- The camera should be positioned to show the FULL EXTENT of the environment — walls, floor, ceiling/sky all visible with plenty of empty space.\n"
    "- Leave LARGE AMOUNTS OF EMPTY FLOOR/GROUND SPACE in the scene — this is essential so characters can be composited into the scene later.\n"
    "- For interiors: camera in the center of a VERY LARGE room, showing the entire room with generous empty floor area, tall ceilings, distant walls.\n"
    "- For exteriors: camera pulled far back showing vast landscapes, wide streets, open plazas with lots of empty ground.\n"
    "- Use layered depth: clear foreground floor/ground, spacious midground, detailed background.\n"
    "- Avoid close-up or tight framing — everything should feel distant and spacious.\n"
    "- The viewer should feel they are standing in the middle of a LARGE, OPEN space with room to move around.\n\n"
    "ENVIRONMENT ONLY — no people, no characters, no humans, no living creatures anywhere in the scene.\n\n"
    "Scene description: {description}\n"
    "{style_line}"
    "\nCRITICAL REQUIREMENTS:\n"
    "1. Output MUST be equirectangular projection panorama (2:1 aspect ratio), NOT a flat perspective image.\n"
    "2. Full 360° horizontal coverage, ~180° vertical coverage (floor to ceiling/sky).\n"
    "3. Consistent lighting, color palette, and style throughout the full 360° sweep.\n"
    "4. Reference the provided image for visual style, color palette, materials, and atmosphere.\n"
    "5. Make the space feel LARGE, OPEN, and IMMERSIVE."
)


@router.post("/ai/generate-panorama", response_model=PanoramaGenerateResponse)
def generate_panorama(
    data: PanoramaGenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a 4000x2000 equirectangular 360° VR panorama from a reference location image."""
    from services.ai_engine import ai_engine
    from services.storage_adapter import get_storage
    from services.task_quota import release_quota

    # 1. Read reference image from storage
    storage = get_storage()
    try:
        ref_bytes = storage.get_bytes(object_key=data.reference_storage_key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Reference image not found: {e}")

    ref_mime = "image/png"
    if data.reference_storage_key.endswith((".jpg", ".jpeg")):
        ref_mime = "image/jpeg"
    elif data.reference_storage_key.endswith(".webp"):
        ref_mime = "image/webp"

    # 2. Build panorama prompt
    style_line = f"Style: {data.style_preset}\n" if data.style_preset else ""
    panorama_prompt = PANORAMA_PROMPT_TEMPLATE.format(
        description=data.prompt,
        style_line=style_line,
    )

    # 3. Generate via Gemini img2img with 2:1 aspect ratio
    lease = _acquire_image_quota()
    try:
        result = ai_engine.generate_image(
            prompt=panorama_prompt,
            reference_image=ref_bytes,
            reference_mime=ref_mime,
            aspect_ratio="2:1",     # Gemini adapter omits unsupported ratio, prompt controls dimensions
            image_size="4K",
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        release_quota(lease)

    image_b64 = base64.b64encode(result["image_data"]).decode("utf-8")

    # 4. Store panorama
    storage_key = None
    storage_uri = None
    try:
        ext = (result["mime_type"].split("/")[-1] or "png").split(";")[0]
        object_key = f"assets/panoramas/{uuid4()}.{ext}"
        stored = storage.put_bytes(
            object_key=object_key,
            data=result["image_data"],
            content_type=result["mime_type"],
        )
        storage_key = stored.object_key
        storage_uri = stored.uri
    except Exception as e:
        logger.warning("Failed to store panorama image: %s", e)

    return PanoramaGenerateResponse(
        image_base64=image_b64,
        mime_type=result["mime_type"],
        model=result["model"],
        elapsed=result["elapsed"],
        storage_key=storage_key,
        storage_uri=storage_uri,
    )


# --- View Angle Conversion (RunningHub) ---

class ViewAngleRequest(BaseModel):
    source_storage_key: str   # storage_key of the front-view source image
    prompt: str               # e.g. "<sks> left side view eye-level shot medium shot"


class ViewAngleResponse(BaseModel):
    image_base64: str
    storage_key: str | None = None


@router.post("/ai/view-angle-convert", response_model=ViewAngleResponse)
def view_angle_convert(data: ViewAngleRequest):
    """Convert a character's front-view image to a different view angle using RunningHub."""
    from config import settings
    from services.runninghub_client import RunningHubClient, RunningHubError
    from services.storage_adapter import get_storage

    if not settings.runninghub_api_key:
        raise HTTPException(status_code=503, detail="RunningHub API key not configured")

    storage = get_storage()

    # 1. Read source image from storage
    try:
        source_data = storage.get_bytes(object_key=data.source_storage_key)
    except Exception as e:
        logger.error("Failed to read source image from storage: %s", e)
        raise HTTPException(status_code=404, detail=f"Source image not found: {data.source_storage_key}")

    # 2. Write to temp file for upload
    suffix = ".png"
    if data.source_storage_key.endswith(".jpg") or data.source_storage_key.endswith(".jpeg"):
        suffix = ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(source_data)
        tmp.flush()
        tmp.close()

        # 3. Upload to RunningHub
        client = RunningHubClient(
            api_key=settings.runninghub_api_key,
            base_url=settings.runninghub_base_url,
        )
        download_url = client.upload_image(tmp.name)

        # 4. Submit task (node 41 = image, node 137 = prompt)
        node_info_list = [
            {"nodeId": "41", "fieldName": "image", "fieldValue": download_url},
            {"nodeId": "137", "fieldName": "text", "fieldValue": data.prompt},
        ]
        task_id = client.submit_task(
            app_id=settings.runninghub_app_id,
            node_info_list=node_info_list,
            instance_type=settings.runninghub_instance_type,
        )

        # 5. Poll until done (up to 300s)
        result = client.poll_until_done(task_id, poll_interval=3.0, timeout=300.0)

        # 6. Download result image
        results = result.get("results", [])
        if not results:
            raise HTTPException(status_code=502, detail="RunningHub returned no results")

        result_url = results[0] if isinstance(results[0], str) else results[0].get("url", "")
        if not result_url:
            raise HTTPException(status_code=502, detail="RunningHub returned empty result URL")

        result_data = client._get_binary(result_url)

        # 7. Store result
        storage_key: str | None = None
        try:
            ext = "png"
            if result_url.lower().endswith(".jpg") or result_url.lower().endswith(".jpeg"):
                ext = "jpg"
            object_key = f"assets/images/{uuid4()}.{ext}"
            stored = storage.put_bytes(
                object_key=object_key,
                data=result_data,
                content_type=f"image/{ext}",
            )
            storage_key = stored.object_key
        except Exception as e:
            logger.warning("Failed to store RunningHub result: %s", e)

        image_b64 = base64.b64encode(result_data).decode("utf-8")
        return ViewAngleResponse(image_base64=image_b64, storage_key=storage_key)

    except RunningHubError as e:
        logger.error("RunningHub error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        import os
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
