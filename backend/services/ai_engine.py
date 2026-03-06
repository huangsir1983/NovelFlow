"""AI Engine — multi-provider routing with capability tiers, fallback, and streaming."""

import time
import logging
from typing import Generator

import anthropic

from config import settings

logger = logging.getLogger(__name__)

# Capability tier → default Anthropic model mapping (env fallback)
TIER_MODEL_MAP = {
    "fast": "claude-haiku-4-5-20251001",
    "standard": "claude-sonnet-4-6",
    "advanced": "claude-opus-4-6",
}

# Anthropic fallback chain (most capable → fastest)
FALLBACK_CHAIN = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]


class AIEngine:
    """Unified AI calling interface with multi-provider routing, fallback, and streaming."""

    def __init__(self):
        self._anthropic_client: anthropic.Anthropic | None = None
        self._adapter_cache: dict[str, object] = {}
        self._init_anthropic()

    def _init_anthropic(self):
        if settings.anthropic_api_key:
            self._anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        else:
            logger.warning("ANTHROPIC_API_KEY not set — env Anthropic fallback disabled")

    def invalidate_cache(self):
        """Clear adapter cache (call after DB provider changes)."""
        self._adapter_cache.clear()

    def _resolve_routes(
        self,
        capability_tier: str,
        db=None,
        *,
        model_type: str = "text",
    ) -> list[tuple]:
        """Resolve ordered list of (adapter_or_client, model_id) for a capability tier.

        Args:
            capability_tier: The capability tier to resolve (fast/standard/advanced).
            db: Optional database session for querying DB providers.
            model_type: Filter by model type — "text", "image", or "video".

        Returns list of tuples: (adapter_instance, model_id)
        where adapter_instance is either a ProviderAdapter or None (meaning use _anthropic_client).
        """
        routes = []

        # 1. Try DB-configured providers
        if db is not None:
            try:
                from models.ai_provider import AIProvider
                providers = (
                    db.query(AIProvider)
                    .filter(AIProvider.enabled == True)
                    .order_by(AIProvider.priority)
                    .all()
                )
                for provider in providers:
                    models_config = provider.models or []
                    for m in models_config:
                        m_type = m.get("model_type", "text")
                        if m_type != model_type:
                            continue
                        if m.get("capability_tier") == capability_tier:
                            adapter = self._get_or_create_adapter(provider)
                            if adapter:
                                routes.append((adapter, m["model_id"]))
            except Exception as e:
                logger.warning(f"Failed to query DB providers: {e}")

        # 2. Env Anthropic fallback (text only)
        if model_type == "text" and self._anthropic_client:
            env_model = TIER_MODEL_MAP.get(capability_tier, settings.default_model)
            routes.append((None, env_model))  # None = use _anthropic_client

        return routes

    def _get_or_create_adapter(self, provider):
        """Get or create a cached adapter for a DB provider."""
        cache_key = provider.id
        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]

        try:
            from services.providers import create_adapter
            adapter = create_adapter(
                provider.provider_type,
                base_url=provider.base_url,
                api_key=provider.api_key,
                provider_name=provider.name,
            )
            self._adapter_cache[cache_key] = adapter
            return adapter
        except Exception as e:
            logger.error(f"Failed to create adapter for {provider.name}: {e}")
            return None

    def call(
        self,
        *,
        system: str = "",
        messages: list[dict],
        model: str | None = None,
        capability_tier: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        db=None,
    ) -> dict:
        """Synchronous call with multi-provider fallback.

        Use capability_tier (preferred) or model (backward compat).

        Returns:
            {
                "content": str,
                "model": str,
                "input_tokens": int,
                "output_tokens": int,
                "elapsed": float,
                "provider": str,
            }
        """
        if capability_tier:
            routes = self._resolve_routes(capability_tier, db=db, model_type="text")
            # Tier fallback: if no text model for this tier, try adjacent tiers
            if not routes and capability_tier == "standard":
                logger.info("No 'standard' text model found, falling back to 'fast' tier")
                routes = self._resolve_routes("fast", db=db, model_type="text")
            elif not routes and capability_tier == "advanced":
                logger.info("No 'advanced' text model found, falling back to 'standard'/'fast'")
                routes = self._resolve_routes("standard", db=db, model_type="text")
                if not routes:
                    routes = self._resolve_routes("fast", db=db, model_type="text")
        elif model:
            # Backward compat: specific model → try env Anthropic only
            routes = [(None, model)]
        else:
            routes = [(None, settings.default_model)]

        if not routes:
            raise RuntimeError(
                "No AI providers configured. Add a provider in Settings or set ANTHROPIC_API_KEY in .env"
            )

        last_error = None
        for adapter, model_id in routes:
            try:
                if adapter is not None:
                    # Use provider adapter
                    resp = adapter.call(
                        model=model_id,
                        system=system,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    result = {
                        "content": resp.content,
                        "model": resp.model,
                        "input_tokens": resp.input_tokens,
                        "output_tokens": resp.output_tokens,
                        "elapsed": resp.elapsed,
                        "provider": resp.provider_name,
                    }
                    logger.info(
                        f"AI call OK: provider={resp.provider_name}, model={model_id}, "
                        f"tokens={resp.input_tokens}+{resp.output_tokens}, elapsed={resp.elapsed}s"
                    )
                    return result
                else:
                    # Env Anthropic client
                    if not self._anthropic_client:
                        continue
                    result = self._call_anthropic(
                        model=model_id,
                        system=system,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    return result

            except Exception as e:
                logger.warning(f"Provider call failed ({adapter.provider_name if adapter else 'Anthropic'}/{model_id}): {e}")
                last_error = e
                continue

        raise RuntimeError(f"All AI providers failed. Last error: {last_error}")

    def stream(
        self,
        *,
        system: str = "",
        messages: list[dict],
        model: str | None = None,
        capability_tier: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        db=None,
    ) -> Generator[str, None, None]:
        """Streaming call. Yields text chunks. Uses first available provider."""
        if capability_tier:
            routes = self._resolve_routes(capability_tier, db=db, model_type="text")
            # Tier fallback for streaming too
            if not routes and capability_tier == "standard":
                routes = self._resolve_routes("fast", db=db, model_type="text")
            elif not routes and capability_tier == "advanced":
                routes = self._resolve_routes("standard", db=db, model_type="text")
                if not routes:
                    routes = self._resolve_routes("fast", db=db, model_type="text")
        elif model:
            routes = [(None, model)]
        else:
            routes = [(None, settings.default_model)]

        if not routes:
            raise RuntimeError("No AI providers configured.")

        last_error = None
        for adapter, model_id in routes:
            try:
                if adapter is not None:
                    yield from adapter.stream(
                        model=model_id,
                        system=system,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    return
                else:
                    if not self._anthropic_client:
                        continue
                    yield from self._stream_anthropic(
                        model=model_id,
                        system=system,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    return

            except Exception as e:
                logger.warning(f"Provider stream failed ({adapter.provider_name if adapter else 'Anthropic'}/{model_id}): {e}")
                last_error = e
                continue

        raise RuntimeError(f"All AI providers failed for streaming. Last error: {last_error}")

    # ── Anthropic direct methods (env fallback) ──

    def _call_anthropic(self, *, model, system, messages, temperature, max_tokens) -> dict:
        start = time.time()
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system

        response = self._anthropic_client.messages.create(**kwargs)
        elapsed = time.time() - start

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        result = {
            "content": content,
            "model": model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "elapsed": round(elapsed, 2),
            "provider": "Anthropic (env)",
        }
        logger.info(
            f"AI call OK: provider=Anthropic(env), model={model}, "
            f"tokens={result['input_tokens']}+{result['output_tokens']}, elapsed={result['elapsed']}s"
        )
        return result

    def _stream_anthropic(self, *, model, system, messages, temperature, max_tokens):
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system

        with self._anthropic_client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def generate_image(
        self,
        *,
        prompt: str,
        reference_image: bytes | None = None,
        reference_mime: str = "image/png",
        aspect_ratio: str = "3:4",
        image_size: str = "2K",
        capability_tier: str = "standard",
        db=None,
    ) -> dict:
        """Generate an image using an image-type model.

        Routes via model_type="image" to find image-capable providers.

        Returns:
            {
                "image_data": bytes,
                "mime_type": str,
                "model": str,
                "elapsed": float,
                "provider": str,
            }
        """
        from services.providers.gemini_adapter import GeminiAdapter

        # Find image models via model_type routing
        routes = self._resolve_routes(capability_tier, db=db, model_type="image")
        # Tier fallback for image
        if not routes and capability_tier == "advanced":
            routes = self._resolve_routes("standard", db=db, model_type="image")
        if not routes and capability_tier != "fast":
            routes = self._resolve_routes("fast", db=db, model_type="image")

        # Filter to only Gemini adapters (only Gemini supports image generation currently)
        routes = [(a, m) for a, m in routes if isinstance(a, GeminiAdapter)]

        if not routes:
            raise RuntimeError(
                "No image-capable AI provider configured. "
                "Add a provider with an image model (model_type='image') in Settings."
            )

        last_error = None
        for adapter, model_id in routes:
            try:
                resp = adapter.generate_image(
                    model=model_id,
                    prompt=prompt,
                    reference_image=reference_image,
                    reference_mime=reference_mime,
                    aspect_ratio=aspect_ratio,
                    image_size=image_size,
                )
                return {
                    "image_data": resp.image_data,
                    "mime_type": resp.mime_type,
                    "model": resp.model,
                    "elapsed": resp.elapsed,
                    "provider": resp.provider_name,
                }
            except Exception as e:
                logger.warning(f"Image generation failed ({adapter.provider_name}/{model_id}): {e}")
                last_error = e
                continue

        raise RuntimeError(f"All image providers failed. Last error: {last_error}")

    def generate_video(
        self,
        *,
        prompt: str,
        reference_image: bytes | None = None,
        capability_tier: str = "standard",
        db=None,
    ) -> dict:
        """Generate a video using a video-type model.

        Routes via model_type="video" to find video-capable providers.
        Currently a stub — no video providers are implemented yet.

        Returns:
            {
                "video_data": bytes,
                "mime_type": str,
                "model": str,
                "elapsed": float,
                "provider": str,
            }
        """
        routes = self._resolve_routes(capability_tier, db=db, model_type="video")
        if not routes:
            raise RuntimeError(
                "No video-capable AI provider configured. "
                "Add a provider with a video model (model_type='video') in Settings."
            )

        raise RuntimeError("Video generation is not yet implemented.")


# Module-level singleton
ai_engine = AIEngine()
