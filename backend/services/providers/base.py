"""Provider adapter base — ABC and shared response dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator


@dataclass
class AIResponse:
    """Unified response from any provider."""
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    elapsed: float = 0.0
    provider_name: str = ""


class ProviderAdapter(ABC):
    """Abstract base for all AI provider adapters."""

    def __init__(self, *, base_url: str, api_key: str, provider_name: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider_name = provider_name

    @abstractmethod
    def call(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AIResponse:
        ...

    @abstractmethod
    def stream(
        self,
        *,
        model: str,
        system: str = "",
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Generator[str, None, None]:
        ...

    @abstractmethod
    def health_check(self) -> bool:
        ...

    def close(self) -> None:
        """Close underlying connections. Override in subclasses with persistent clients."""
        pass
