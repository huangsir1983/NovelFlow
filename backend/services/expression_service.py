"""
Gemini img2img 表情/动作变换服务 — 使用 Gemini 的图像生成能力
基于参考图 + 文本 prompt 生成角色的特定表情/动作变体。
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_expression(
    reference_image_base64: str,
    expression_prompt: str,
    *,
    negative_prompt: Optional[str] = None,
    character_name: Optional[str] = None,
    db=None,
) -> str:
    """
    Use Gemini img2img to transform a character reference image
    with a given expression/action prompt.

    Args:
        reference_image_base64: Base64-encoded reference image.
        expression_prompt: Text prompt describing the desired expression/action.
        negative_prompt: Things to avoid in the generated image.
        character_name: Optional character name for context.
        db: Optional database session for provider routing.

    Returns:
        Base64-encoded result image string.
    """
    from services.ai_engine import ai_engine

    # Build the prompt
    parts = []
    if character_name:
        parts.append(f"This is {character_name}.")
    parts.append(f"Transform this character image to show: {expression_prompt}")
    parts.append("Keep the character's identity, clothing, and features consistent.")
    parts.append("Only change the expression, pose, and action as described.")
    if negative_prompt:
        parts.append(f"Avoid: {negative_prompt}")

    full_prompt = " ".join(parts)

    # Decode base64 to bytes for ai_engine.generate_image()
    ref_bytes = base64.b64decode(reference_image_base64)

    # Detect MIME type from image header
    ref_mime = "image/png"
    if ref_bytes[:3] == b'\xff\xd8\xff':
        ref_mime = "image/jpeg"
    elif ref_bytes[:4] == b'RIFF' and ref_bytes[8:12] == b'WEBP':
        ref_mime = "image/webp"

    try:
        result = ai_engine.generate_image(
            prompt=full_prompt,
            reference_image=ref_bytes,
            reference_mime=ref_mime,
            aspect_ratio="3:4",
            db=db,
        )
        # Return base64-encoded result
        return base64.b64encode(result["image_data"]).decode("utf-8")
    except Exception as e:
        logger.error("Expression generation failed: %s", e)
        raise
