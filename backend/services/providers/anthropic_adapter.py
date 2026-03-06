"""Anthropic Messages API adapter."""

import time
import logging
from typing import Generator

import anthropic

from services.providers.base import ProviderAdapter, AIResponse

logger = logging.getLogger(__name__)


class AnthropicAdapter(ProviderAdapter):
    """Adapter for the Anthropic Messages API."""

    def __init__(self, *, base_url: str = "", api_key: str, provider_name: str = "Anthropic"):
        super().__init__(base_url=base_url, api_key=api_key, provider_name=provider_name)
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**kwargs)

    def call(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        start = time.time()
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        elapsed = time.time() - start

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return AIResponse(
            content=content,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
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
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def health_check(self) -> bool:
        try:
            resp = self.call(
                model="claude-haiku-4-5-20251001",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            )
            return bool(resp.content)
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False
