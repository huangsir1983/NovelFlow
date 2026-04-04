"""
Gemini img2img 表情/动作变换服务 — 使用 Gemini 的图像生成能力
基于参考图 + 文本 prompt 生成角色的特定表情/动作变体。
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def generate_expression(
    reference_image_base64: str,
    expression_prompt: str,
    *,
    negative_prompt: Optional[str] = None,
    character_name: Optional[str] = None,
) -> str:
    """
    Use Gemini img2img to transform a character reference image
    with a given expression/action prompt.

    Args:
        reference_image_base64: Base64-encoded reference image.
        expression_prompt: Text prompt describing the desired expression/action.
        negative_prompt: Things to avoid in the generated image.
        character_name: Optional character name for context.

    Returns:
        Base64-encoded result image string.
    """
    from services.ai_engine import get_ai_engine

    engine = get_ai_engine()

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

    # Use Gemini image generation with reference image
    try:
        result = await engine.generate_image_with_reference(
            prompt=full_prompt,
            reference_image_base64=reference_image_base64,
            aspect_ratio="1:1",
        )
        return result
    except Exception as e:
        logger.error("Expression generation failed: %s", e)
        raise
