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
        # Pre-create httpx client to avoid event-loop issues in worker threads (Python 3.12+)
        # Use short keepalive to avoid stale SSL connections being reused
        self._http_client = httpx.Client(
            timeout=300,
            limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=30),
        )

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
        resp = self._http_client.post(url, json=body, headers=self._headers())
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

        with self._http_client.stream("POST", url, json=body, headers=self._headers()) as resp:
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
        reference_images: list[dict] | None = None,
        interleaved_parts: list[dict] | None = None,
        aspect_ratio: str = "3:4",
        image_size: str = "2K",
    ) -> ImageResponse:
        """Generate an image using Gemini image model.

        Args:
            reference_image: Single reference image bytes (legacy, used if reference_images is empty).
            reference_images: List of {"data": bytes, "mime_type": str} for multi-image input.
            interleaved_parts: List of {"type": "text"|"image", ...} for precise text+image ordering.
                When provided, maps directly to Gemini parts (overrides prompt + reference_images).
        """
        url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"

        logger.info(f"[IMAGE-GEN] URL: {self.base_url}/v1beta/models/{model}:generateContent")
        logger.info(f"[IMAGE-GEN] interleaved_parts count: {len(interleaved_parts) if interleaved_parts else 0}")
        logger.info(f"[IMAGE-GEN] reference_images count: {len(reference_images) if reference_images else 0}")
        logger.info(f"[IMAGE-GEN] has reference_image: {reference_image is not None}")

        # Build parts — prefer interleaved for precise control
        parts = []
        if interleaved_parts:
            # Direct mapping: each part becomes a Gemini part in exact order
            for part in interleaved_parts:
                if part["type"] == "text":
                    parts.append({"text": part["content"]})
                elif part["type"] == "image":
                    image_b64 = base64.b64encode(part["data"]).decode("utf-8")
                    parts.append({
                        "inlineData": {
                            "data": image_b64,
                            "mimeType": part.get("mime_type", "image/png"),
                        }
                    })
        elif reference_images:
            for ref in reference_images:
                image_b64 = base64.b64encode(ref["data"]).decode("utf-8")
                parts.append({
                    "inlineData": {
                        "data": image_b64,
                        "mimeType": ref.get("mime_type", "image/png"),
                    }
                })
            parts.append({"text": prompt})
        elif reference_image:
            image_b64 = base64.b64encode(reference_image).decode("utf-8")
            parts.append({
                "inlineData": {
                    "data": image_b64,
                    "mimeType": reference_mime,
                }
            })
            parts.append({"text": prompt})
        else:
            parts.append({"text": prompt})

        # Build image config — omit aspectRatio for unsupported ratios (e.g. "2:1")
        supported_ratios = {"1:1", "3:4", "4:3", "16:9", "9:16"}
        image_config: dict = {}
        if aspect_ratio in supported_ratios:
            image_config["aspectRatio"] = aspect_ratio

        body = {
            "contents": [
                {
                    "parts": parts,
                    "role": "user",
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
                "imageConfig": image_config,
            },
        }

        # Diagnostic logging: parts summary
        for i, p in enumerate(parts):
            if "text" in p:
                text_preview = p["text"][:200] + "..." if len(p["text"]) > 200 else p["text"]
                logger.info(f"[IMAGE-GEN] Part[{i}]: TEXT, len={len(p['text'])}, preview={text_preview}")
            elif "inlineData" in p:
                b64_len = len(p["inlineData"]["data"])
                mime = p["inlineData"]["mimeType"]
                logger.info(f"[IMAGE-GEN] Part[{i}]: IMAGE, mime={mime}, b64_len={b64_len} (~{b64_len * 3 // 4 // 1024}KB)")

        body_json = json.dumps(body)
        logger.info(f"[IMAGE-GEN] Total request body size: {len(body_json) // 1024}KB ({len(body_json)} bytes)")

        start = time.time()
        resp = self._http_client.post(url, json=body, headers=self._headers())

        logger.info(f"[IMAGE-GEN] Response status: {resp.status_code}")
        if resp.status_code != 200:
            logger.error(f"[IMAGE-GEN] Response body: {resp.text[:2000]}")
        resp.raise_for_status()

        elapsed = time.time() - start
        data = resp.json()

        # Log response structure
        candidates = data.get("candidates", [])
        logger.info(f"[IMAGE-GEN] Response candidates: {len(candidates)}")
        if candidates:
            resp_parts = candidates[0].get("content", {}).get("parts", [])
            for i, rp in enumerate(resp_parts):
                if "text" in rp:
                    logger.info(f"[IMAGE-GEN] Resp Part[{i}]: TEXT = {rp['text'][:200]}")
                elif "inlineData" in rp:
                    logger.info(f"[IMAGE-GEN] Resp Part[{i}]: IMAGE, mime={rp['inlineData'].get('mimeType')}, b64_len={len(rp['inlineData'].get('data', ''))}")

        # Extract image from response
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
            resp = self._http_client.post(url, json=body, headers=self._headers())
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False
