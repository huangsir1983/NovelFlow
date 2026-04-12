"""
Gemini img2img 表情/动作变换服务 — 使用 Gemini 的图像生成能力
基于参考图 + 文本 prompt 生成角色的特定表情/动作变体。
支持多图参照：图片1=角色, 图片2=姿势/表情参照 等。
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _detect_mime(data: bytes) -> str:
    """Detect image MIME type from header bytes."""
    if data[:3] == b'\xff\xd8\xff':
        return "image/jpeg"
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "image/webp"
    return "image/png"


def generate_expression(
    reference_image_base64: str,
    expression_prompt: str,
    *,
    extra_images: list[dict] | None = None,
    negative_prompt: Optional[str] = None,
    character_name: Optional[str] = None,
    aspect_ratio: str = "3:4",
    db=None,
) -> str:
    """
    Use Gemini img2img to transform a character reference image
    with a given expression/action prompt.

    Args:
        reference_image_base64: Base64-encoded primary reference image (character).
        expression_prompt: Text prompt describing the desired expression/action.
            May contain @N references to numbered images.
        extra_images: Additional reference images as [{"index": N, "base64": "..."}].
            These are the @N referenced images beyond the primary.
        negative_prompt: Things to avoid in the generated image.
        character_name: Optional character name for context.
        db: Optional database session for provider routing.

    Returns:
        Base64-encoded result image string.
    """
    from services.ai_engine import ai_engine

    # Collect all images: primary (index 1) + extras
    all_images: list[dict] = []

    # Primary image
    ref_bytes = base64.b64decode(reference_image_base64)
    all_images.append({
        "index": 1,
        "data": ref_bytes,
        "mime_type": _detect_mime(ref_bytes),
    })

    # Extra images (@2, @3, ...)
    if extra_images:
        for img in extra_images:
            img_bytes = base64.b64decode(img["base64"])
            all_images.append({
                "index": img["index"],
                "data": img_bytes,
                "mime_type": _detect_mime(img_bytes),
            })

    # Sort by index for consistent ordering
    all_images.sort(key=lambda x: x["index"])

    # Build prompt — label each image if multiple
    parts = []
    if len(all_images) > 1:
        # Multi-image mode: label each image
        for img in all_images:
            parts.append(f"Image @{img['index']} is provided above.")
        if character_name:
            parts.append(f"The character's name is {character_name}.")
        parts.append(f"Instruction: {expression_prompt}")
        parts.append("Keep the character's identity, clothing, and features consistent with the character reference image.")
        parts.append("Apply the pose, expression, or action as described, using the referenced images for guidance.")
    else:
        # Single-image mode (backward compatible)
        if character_name:
            parts.append(f"This is {character_name}.")
        parts.append(f"Transform this character image to show: {expression_prompt}")
        parts.append("Keep the character's identity, clothing, and features consistent.")
        parts.append("Only change the expression, pose, and action as described.")

    if negative_prompt:
        parts.append(f"Avoid: {negative_prompt}")

    full_prompt = " ".join(parts)

    # Build reference_images list for Gemini (multi-image)
    ref_images_for_api = [{"data": img["data"], "mime_type": img["mime_type"]} for img in all_images]

    try:
        result = ai_engine.generate_image(
            prompt=full_prompt,
            reference_images=ref_images_for_api,
            aspect_ratio=aspect_ratio,
            db=db,
        )
        return base64.b64encode(result["image_data"]).decode("utf-8")
    except Exception as e:
        logger.error("Expression generation failed: %s", e)
        raise
