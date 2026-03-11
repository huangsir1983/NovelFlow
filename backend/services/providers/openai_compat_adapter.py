"""OpenAI-compatible Chat Completions adapter with connection pooling and retry."""

import json
import time
import logging
from typing import Generator

import httpx

from services.providers.base import ProviderAdapter, AIResponse

logger = logging.getLogger(__name__)

# Stall timeout: raise if no new chunk arrives within this many seconds
_STALL_TIMEOUT_S = 60


class OpenAICompatAdapter(ProviderAdapter):
    """Adapter for OpenAI-compatible Chat Completions API with persistent connection pool."""

    def __init__(self, *, base_url: str, api_key: str, provider_name: str = "OpenAI Compatible"):
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

    def _build_messages(self, *, system: str, messages: list[dict]) -> list[dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        result.extend(messages)
        return result

    def call(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": model,
            "messages": self._build_messages(system=system, messages=messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.time()
        resp = self._client.post(url, json=body, headers=self._headers())
        resp.raise_for_status()
        elapsed = time.time() - start

        data = resp.json()
        content = ""
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        usage = data.get("usage", {})

        return AIResponse(
            content=content,
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
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
        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": model,
            "messages": self._build_messages(system=system, messages=messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            with self._client.stream("POST", url, json=body, headers=self._headers()) as resp:
                resp.raise_for_status()
                last_chunk_time = time.time()

                for line in resp.iter_lines():
                    # Stall timeout check
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
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                last_chunk_time = time.time()
                                yield text
                    except json.JSONDecodeError:
                        continue
        except GeneratorExit:
            # Consumer disconnected — httpx stream context manager handles cleanup
            logger.debug(f"Stream consumer disconnected for {self.provider_name}")
        except httpx.TimeoutException as e:
            logger.warning(f"Stream timeout from {self.provider_name}: {e}")
            raise

    def health_check(self) -> bool:
        try:
            url = f"{self.base_url}/v1/models"
            resp = self._client.get(url, headers=self._headers(), timeout=15)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"OpenAI-compat health check failed: {e}")
            return False

    def close(self) -> None:
        """Close the persistent HTTP client."""
        try:
            self._client.close()
        except Exception:
            pass
