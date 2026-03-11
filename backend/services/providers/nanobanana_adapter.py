"""NanoBanana image generation adapter — OpenAI Chat Completions protocol for image gen.

Protocol (大香蕉2):
- Endpoint: POST {BASE_URL}/v1/chat/completions
- Auth:     Authorization: Bearer {API_KEY}
- Stream:   SSE with data: chunks, [DONE] terminator
- Text-to-image: messages[0].content = "prompt string"
- Image-to-image: messages[0].content = [{type:"image_url",...}, {type:"text",...}]
- Model name: <prefix>-<ratio_suffix><size_suffix>
- Response: accumulated text containing image URL / data URL / markdown image
"""

import base64
import json
import re
import time
import logging
from typing import Generator

import httpx

from services.providers.base import ProviderAdapter, AIResponse
from services.providers.gemini_adapter import ImageResponse

logger = logging.getLogger(__name__)

# Aspect ratio → model suffix mapping
RATIO_SUFFIX_MAP = {
    "16:9": "landscape",
    "9:16": "portrait",
    "1:1": "square",
    "4:3": "four-three",
    "3:4": "three-four",
}

# Image size → model suffix mapping
SIZE_SUFFIX_MAP = {
    "1K": "",
    "2K": "-2k",
    "4K": "-4k",
}


def build_image_model_name(
    prefix: str,
    aspect_ratio: str = "16:9",
    image_size: str = "1K",
) -> str:
    """Build the full model name: <prefix>-<ratio_suffix><size_suffix>.

    Example: gemini-3.1-flash-image + 16:9 + 2K -> gemini-3.1-flash-image-landscape-2k
    """
    ratio_suffix = RATIO_SUFFIX_MAP.get(aspect_ratio, "landscape")
    size_suffix = SIZE_SUFFIX_MAP.get(image_size, "")
    return f"{prefix}-{ratio_suffix}{size_suffix}"


def extract_image_from_text(text: str) -> tuple[bytes, str] | None:
    """Parse accumulated response text to extract image data.

    Supports formats:
    - Markdown image: ![...](url or data:...)
    - data URL: data:image/...;base64,...
    - Plain URL: https://....(png|jpg|jpeg|webp|gif)
    - JSON with url: {"url":"..."}

    Returns (image_bytes, mime_type) or None.
    """
    text = text.strip()

    # Format B/D: data URL (inline base64)
    data_url_match = re.search(r'data:(image/[a-zA-Z+]+);base64,([A-Za-z0-9+/=\s]+)', text)
    if data_url_match:
        mime = data_url_match.group(1)
        b64_data = data_url_match.group(2).replace("\n", "").replace(" ", "")
        try:
            return base64.b64decode(b64_data), mime
        except Exception:
            pass

    # Format A: Markdown image with URL
    md_match = re.search(r'!\[.*?\]\((https?://[^\s)]+)\)', text)
    if md_match:
        url = md_match.group(1)
        return _download_image(url)

    # Format E: JSON with url
    json_match = re.search(r'\{[^}]*"url"\s*:\s*"(https?://[^"]+)"[^}]*\}', text)
    if json_match:
        url = json_match.group(1)
        return _download_image(url)

    # Format C: Plain URL
    url_match = re.search(r'(https?://\S+\.(?:png|jpg|jpeg|webp|gif)(?:\?\S*)?)', text, re.IGNORECASE)
    if url_match:
        url = url_match.group(1)
        return _download_image(url)

    return None


def _download_image(url: str) -> tuple[bytes, str] | None:
    """Download image from URL, return (bytes, mime_type)."""
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            mime = resp.headers.get("content-type", "image/png").split(";")[0].strip()
            return resp.content, mime
    except Exception as e:
        logger.warning("Failed to download image from %s: %s", url, e)
        return None


class NanoBananaAdapter(ProviderAdapter):
    """Adapter for NanoBanana (大香蕉2) image generation via OpenAI Chat Completions.

    Uses /v1/chat/completions with SSE streaming to generate images.
    The response is accumulated text containing image URLs or base64 data.
    """

    def __init__(self, *, base_url: str, api_key: str, provider_name: str = "NanoBanana"):
        super().__init__(base_url=base_url, api_key=api_key, provider_name=provider_name)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        reference_image: bytes | None = None,
        reference_mime: str = "image/png",
        aspect_ratio: str = "3:4",
        image_size: str = "1K",
    ) -> ImageResponse:
        """Generate an image using NanoBanana API.

        Args:
            model: Model prefix (e.g. "gemini-3.1-flash-image"). Will be combined
                   with aspect_ratio and image_size to form the full model name.
            prompt: Text prompt describing the desired image.
            reference_image: Optional reference image bytes for img2img.
            reference_mime: MIME type of reference image.
            aspect_ratio: Output aspect ratio ("1:1", "3:4", "4:3", "16:9", "9:16").
            image_size: Output resolution ("1K", "2K", "4K").

        Returns:
            ImageResponse with raw image bytes.
        """
        full_model = build_image_model_name(model, aspect_ratio, image_size)
        url = f"{self.base_url}/v1/chat/completions"

        # Build message content
        if reference_image:
            # Image-to-image: content is array with image_url + text
            b64 = base64.b64encode(reference_image).decode("utf-8")
            data_url = f"data:{reference_mime};base64,{b64}"
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ]
        else:
            # Text-to-image: content is plain string
            content = prompt

        body = {
            "model": full_model,
            "messages": [{"role": "user", "content": content}],
            "stream": True,
        }

        start = time.time()
        accumulated_text = self._stream_and_accumulate(url, body)
        elapsed = time.time() - start

        if not accumulated_text.strip():
            raise RuntimeError("NanoBanana returned empty response")

        # Check for explicit failure
        if accumulated_text.strip().lower().startswith("generation failed"):
            raise RuntimeError(f"NanoBanana generation failed: {accumulated_text.strip()}")

        # Extract image from accumulated text
        result = extract_image_from_text(accumulated_text)
        if result is None:
            raise RuntimeError(
                f"Could not extract image from NanoBanana response. "
                f"Raw text (first 500 chars): {accumulated_text[:500]}"
            )

        image_bytes, mime_type = result
        logger.info(
            "NanoBanana image generated: model=%s, size=%d bytes, mime=%s, elapsed=%.2fs",
            full_model, len(image_bytes), mime_type, elapsed,
        )

        return ImageResponse(
            image_data=image_bytes,
            mime_type=mime_type,
            model=full_model,
            elapsed=round(elapsed, 2),
            provider_name=self.provider_name,
        )

    def _stream_and_accumulate(self, url: str, body: dict) -> str:
        """Send streaming request and accumulate all text chunks."""
        accumulated = []

        with httpx.Client(timeout=180) as client:
            with client.stream("POST", url, json=body, headers=self._headers()) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            # Support both content and reasoning_content
                            text = delta.get("content", "") or delta.get("reasoning_content", "")
                            if text:
                                accumulated.append(text)
                    except json.JSONDecodeError:
                        continue

        return "".join(accumulated)

    # ── Required ProviderAdapter text methods ──
    # NanoBanana is image-only, but we implement call/stream as pass-through
    # so it can technically be used for text if needed.

    def call(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        raise NotImplementedError(
            "NanoBananaAdapter is for image generation. Use generate_image() instead."
        )

    def stream(self, **kwargs) -> Generator[str, None, None]:
        raise NotImplementedError(
            "NanoBananaAdapter is for image generation. Use generate_image() instead."
        )

    def health_check(self) -> bool:
        """Check API connectivity."""
        try:
            url = f"{self.base_url}/v1/models"
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, headers=self._headers())
                return resp.status_code == 200
        except Exception as e:
            logger.warning("NanoBanana health check failed: %s", e)
            return False
