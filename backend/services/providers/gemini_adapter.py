"""Gemini generateContent API adapter (used for Comfly and Google AI).

Based on official Gemini API format:
- Endpoint: {base_url}/v1beta/models/{model}:generateContent
- Stream:   {base_url}/v1beta/models/{model}:streamGenerateContent?alt=sse
- Auth:     Authorization: Bearer {api_key}
- Body:     { contents: [{parts: [{text}]}], generationConfig: {...} }
- Image:    { contents: [...], generationConfig: { responseModalities: ["IMAGE"], imageConfig: {...} } }
"""

import base64
import json
import time
import logging
from dataclasses import dataclass
from typing import Generator

import httpx

from services.providers.base import ProviderAdapter, AIResponse

logger = logging.getLogger(__name__)


@dataclass
class ImageResponse:
    """Response from image generation."""
    image_data: bytes  # raw image bytes
    mime_type: str  # e.g. "image/png"
    model: str
    elapsed: float = 0.0
    provider_name: str = ""


class GeminiAdapter(ProviderAdapter):
    """Adapter for Gemini generateContent API (including Comfly proxy)."""

    def __init__(self, *, base_url: str, api_key: str, provider_name: str = "Gemini"):
        super().__init__(base_url=base_url, api_key=api_key, provider_name=provider_name)

    def _build_body(
        self,
        *,
        system: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Build Gemini request body from unified message format."""
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        body: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def call(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        url = f"{self.base_url}/v1beta/models/{model}:generateContent"
        body = self._build_body(
            system=system, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )

        start = time.time()
        with httpx.Client(timeout=300) as client:
            resp = client.post(url, json=body, headers=self._headers())
            resp.raise_for_status()

        elapsed = time.time() - start
        data = resp.json()

        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts if "text" in p)

        usage = data.get("usageMetadata", {})

        return AIResponse(
            content=content,
            model=data.get("modelVersion", model),
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            elapsed=round(elapsed, 2),
            provider_name=self.provider_name,
        )

    def stream(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        url = f"{self.base_url}/v1beta/models/{model}:streamGenerateContent?alt=sse"
        body = self._build_body(
            system=system, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )

        with httpx.Client(timeout=300) as client:
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
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                text = p.get("text", "")
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        continue

    def generate_image(
        self,
        *,
        model: str,
        prompt: str,
        reference_image: bytes | None = None,
        reference_mime: str = "image/png",
        aspect_ratio: str = "3:4",
        image_size: str = "2K",
    ) -> ImageResponse:
        """Generate an image using Gemini image model.

        Args:
            model: Image model ID (e.g. "gemini-3.1-flash-image-preview")
            prompt: Text prompt describing the desired image
            reference_image: Optional reference image bytes for img2img
            reference_mime: MIME type of reference image
            aspect_ratio: Output aspect ratio ("1:1", "3:4", "4:3", "16:9", "9:16")
            image_size: Output resolution ("1K", "2K", "4K" — 4K requires gemini-3.1-flash-image-preview-4k model)

        Returns:
            ImageResponse with raw image bytes
        """
        url = f"{self.base_url}/v1beta/models/{model}:generateContent"

        # Build parts
        parts = []
        if reference_image:
            image_b64 = base64.b64encode(reference_image).decode("utf-8")
            parts.append({
                "inlineData": {
                    "data": image_b64,
                    "mimeType": reference_mime,
                }
            })
        parts.append({"text": prompt})

        body = {
            "contents": [
                {
                    "parts": parts,
                    "role": "user",
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": image_size,
                },
            },
        }

        start = time.time()
        with httpx.Client(timeout=180) as client:
            resp = client.post(url, json=body, headers=self._headers())
            resp.raise_for_status()

        elapsed = time.time() - start
        data = resp.json()

        # Extract image from response
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("No candidates in image generation response")

        parts = candidates[0].get("content", {}).get("parts", [])

        for part in parts:
            inline_data = part.get("inlineData")
            if inline_data and inline_data.get("data"):
                image_bytes = base64.b64decode(inline_data["data"])
                mime = inline_data.get("mimeType", "image/png")
                logger.info(
                    f"Image generated: model={model}, size={len(image_bytes)} bytes, "
                    f"mime={mime}, elapsed={round(elapsed, 2)}s"
                )
                return ImageResponse(
                    image_data=image_bytes,
                    mime_type=mime,
                    model=data.get("modelVersion", model),
                    elapsed=round(elapsed, 2),
                    provider_name=self.provider_name,
                )

        raise RuntimeError("No image data found in response")

    def health_check(self) -> bool:
        """Verify API connectivity with a minimal generateContent call."""
        try:
            test_model = "gemini-3.1-flash-lite-preview"
            url = f"{self.base_url}/v1beta/models/{test_model}:generateContent"
            body = {
                "contents": [{"parts": [{"text": "hi"}]}],
                "generationConfig": {"maxOutputTokens": 5},
            }
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, json=body, headers=self._headers())
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False
