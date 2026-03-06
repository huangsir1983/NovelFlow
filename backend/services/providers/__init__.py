"""Provider adapter registry and factory."""

from services.providers.base import ProviderAdapter, AIResponse
from services.providers.anthropic_adapter import AnthropicAdapter
from services.providers.gemini_adapter import GeminiAdapter, ImageResponse
from services.providers.openai_compat_adapter import OpenAICompatAdapter

ADAPTER_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "openai_compat": OpenAICompatAdapter,
}


def create_adapter(
    provider_type: str,
    *,
    base_url: str,
    api_key: str,
    provider_name: str = "",
) -> ProviderAdapter:
    """Factory: create a provider adapter by type string."""
    cls = ADAPTER_REGISTRY.get(provider_type)
    if not cls:
        raise ValueError(f"Unknown provider type: {provider_type}. Available: {list(ADAPTER_REGISTRY.keys())}")
    return cls(base_url=base_url, api_key=api_key, provider_name=provider_name)


__all__ = [
    "ProviderAdapter",
    "AIResponse",
    "ImageResponse",
    "AnthropicAdapter",
    "GeminiAdapter",
    "OpenAICompatAdapter",
    "create_adapter",
    "ADAPTER_REGISTRY",
]
