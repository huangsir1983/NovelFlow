"""GPT Responses API adapter (/v1/responses) with connection pooling and retry."""

import json
import time
import logging
from typing import Generator

import httpx

from services.providers.base import ProviderAdapter, AIResponse

logger = logging.getLogger(__name__)

# Stall timeout: raise if no new chunk arrives within this many seconds
_STALL_TIMEOUT_S = 60


class ResponsesAPIAdapter(ProviderAdapter):
    """Adapter for GPT Responses API (POST /v1/responses) with persistent connection pool.

    This API uses a different request/response format from the standard
    OpenAI Chat Completions API:
    - Endpoint: /v1/responses (not /v1/chat/completions)
    - Input uses structured content objects (input_text / output_text)
    - Response parsed from output_text or output[].content[].text
    """

    def __init__(self, *, base_url: str, api_key: str, provider_name: str = "Responses API"):
        super().__init__(base_url=base_url, api_key=api_key, provider_name=provider_name)
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=10, read=300, write=30, pool=30),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_input(self, *, system: str, messages: list[dict]) -> list[dict]:
        """Convert standard messages to Responses API input format."""
        result = []

        if system:
            result.append({
                "role": "system",
                "content": [{"type": "input_text", "text": system}],
            })

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict):
                        parts.append(block.get("text", ""))
                text = "".join(parts)
            else:
                text = str(content)

            text_type = "output_text" if role == "assistant" else "input_text"
            result.append({
                "role": role,
                "content": [{"type": text_type, "text": text}],
            })

        return result

    @staticmethod
    def _extract_text(data: dict) -> str:
        """Extract text from Responses API response."""
        output_text = data.get("output_text")
        if output_text:
            return output_text

        parts = []
        for output_item in data.get("output", []):
            for content_block in output_item.get("content", []):
                text = content_block.get("text", "")
                if text:
                    parts.append(text)
        if parts:
            return "".join(parts)

        return ""

    def call(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        """Always use streaming internally and collect the full response."""
        url = f"{self.base_url}/v1/responses"
        body = {
            "model": model,
            "input": self._build_input(system=system, messages=messages),
            "max_output_tokens": max_tokens,
            "stream": True,
        }

        start = time.time()
        parts: list[str] = []
        usage = {}

        with self._client.stream("POST", url, json=body, headers=self._headers()) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    if chunk.get("type") == "response.output_text.delta":
                        delta_text = chunk.get("delta", "")
                        if delta_text:
                            parts.append(delta_text)
                        continue
                    if chunk.get("type") == "response.completed":
                        resp_obj = chunk.get("response", {})
                        usage = resp_obj.get("usage", {})
                    text = self._extract_text(chunk)
                    if text:
                        parts.append(text)
                except json.JSONDecodeError:
                    continue

        elapsed = time.time() - start
        content = "".join(parts)

        return AIResponse(
            content=content,
            model=model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
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
        """Stream response from Responses API with stall timeout and error handling."""
        url = f"{self.base_url}/v1/responses"
        body = {
            "model": model,
            "input": self._build_input(system=system, messages=messages),
            "max_output_tokens": max_tokens,
            "stream": True,
        }

        try:
            with self._client.stream("POST", url, json=body, headers=self._headers()) as resp:
                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "")

                # If server returns JSON instead of SSE, it doesn't support streaming
                if "text/event-stream" not in content_type and "application/json" in content_type:
                    raw = resp.read()
                    data = json.loads(raw)
                    text = self._extract_text(data)
                    if text:
                        yield text
                    return

                # SSE streaming with stall timeout
                last_chunk_time = time.time()

                for line in resp.iter_lines():
                    now = time.time()
                    if now - last_chunk_time > _STALL_TIMEOUT_S:
                        raise TimeoutError(
                            f"Stream stalled: no data for {_STALL_TIMEOUT_S}s"
                        )

                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        if chunk.get("type") == "response.output_text.delta":
                            delta_text = chunk.get("delta", "")
                            if delta_text:
                                last_chunk_time = time.time()
                                yield delta_text
                            continue
                        text = self._extract_text(chunk)
                        if text:
                            last_chunk_time = time.time()
                            yield text
                    except json.JSONDecodeError:
                        continue

        except GeneratorExit:
            logger.debug(f"Stream consumer disconnected for {self.provider_name}")
        except (httpx.HTTPStatusError, httpx.StreamError, httpx.TimeoutException) as e:
            logger.warning("Responses API streaming failed: %s", e)
            raise

    def health_check(self) -> bool:
        try:
            url = f"{self.base_url}/v1/models"
            resp = self._client.get(url, headers=self._headers(), timeout=15)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Responses API health check failed: {e}")
            return False

    def close(self) -> None:
        """Close the persistent HTTP client."""
        try:
            self._client.close()
        except Exception:
            pass
