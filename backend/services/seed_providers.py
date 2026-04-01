"""Seed default AI providers into the database on startup."""

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from models.ai_provider import AIProvider

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Pre-configured providers to seed on first run.
# Each entry is checked by name — if a provider with that name already
# exists it will NOT be duplicated.
# ------------------------------------------------------------------
DEFAULT_PROVIDERS = [
    {
        "name": "OpenClaudeCode",
        "provider_type": "responses_api",
        "base_url": "https://www.openclaudecode.cn",
        "api_key": "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e",
        "models": [
            {
                "model_id": "gpt-5.4",
                "display_name": "GPT-5.4 (OpenClaudeCode)",
                "model_type": "text",
                "capability_tier": "advanced",
                "max_tokens": 4096,
                "supports_streaming": True,
            },
        ],
        "is_default": False,
        "enabled": True,
        "priority": 1,
    },
    {
        "name": "XuhuanAI-GPT",
        "provider_type": "responses_api",
        "base_url": "https://yhsub.xuhuanai.cn",
        "api_key": "sk-bb6179b38d7a845aa181c4933511999452259469ac89b8fce3c2d0731f945930",
        "models": [
            {
                "model_id": "gpt-5.4",
                "display_name": "GPT-5.4 (XuhuanAI)",
                "model_type": "text",
                "capability_tier": "advanced",
                "max_tokens": 4096,
                "supports_streaming": True,
            },
        ],
        "is_default": False,
        "enabled": True,
        "priority": 3,
    },
    {
        "name": "XuhuanAI-Video",
        "provider_type": "grok_video",
        "base_url": "https://yhgrok.xuhuanai.cn",
        "api_key": "V378STSBi6jAC9Gk",
        "models": [
            {
                "model_id": "grok-video-3",
                "display_name": "Grok Video 6s (XuhuanAI)",
                "model_type": "video",
                "capability_tier": "standard",
                "max_tokens": 0,
                "supports_streaming": False,
            },
        ],
        "is_default": False,
        "enabled": True,
        "priority": 1,
    },
    {
        "name": "GCLI-Text",
        "provider_type": "openai_compat",
        "base_url": "https://yhgcli.xuhuanai.cn",
        "api_key": "ghitavjlksjkvnklghrvjog",
        "models": [
            {
                "model_id": "gemini-3.1-pro-preview",
                "display_name": "Gemini 3.1 Pro (GCLI)",
                "model_type": "text",
                "capability_tier": "advanced",
                "max_tokens": 4096,
                "supports_streaming": True,
            },
        ],
        "is_default": False,
        "enabled": True,
        "priority": 2,
    },
    {
        "name": "Grok-Text",
        "provider_type": "openai_compat",
        "base_url": "https://yhgrok.xuhuanai.cn",
        "api_key": "V378STSBi6jAC9Gk",
        "models": [
            {
                "model_id": "grok-4.20-beta",
                "display_name": "Grok 4.20-beta (XuhuanAI)",
                "model_type": "text",
                "capability_tier": "advanced",
                "max_tokens": 4096,
                "supports_streaming": True,
            },
        ],
        "is_default": False,
        "enabled": True,
        "priority": 2,
    },
    {
        "name": "NanoBanana-Image",
        "provider_type": "gemini",
        "base_url": "https://yunwu.ai",
        "api_key": "sk-P3oE4OgQYSE6DXuV0BvnfnnCmscwFGE3PKrb31jAYwfhZnUU",
        "models": [
            {
                "model_id": "gemini-3.1-flash-image-preview",
                "display_name": "Gemini 3.1 Flash Image (YunwuAI)",
                "model_type": "image",
                "capability_tier": "standard",
                "max_tokens": 0,
                "supports_streaming": True,
            },
        ],
        "is_default": False,
        "enabled": True,
        "priority": 2,
    },
]


def seed_providers(db: Session) -> None:
    """Insert pre-configured providers that do not already exist.
    If a provider already exists, sync its fields to match the config."""
    for cfg in DEFAULT_PROVIDERS:
        exists = db.query(AIProvider).filter(AIProvider.name == cfg["name"]).first()
        if exists:
            # Sync fields in case config changed
            changed = False
            # Do NOT sync "enabled" and "priority" — respect user overrides
            for field in ("provider_type", "base_url", "api_key", "models", "is_default"):
                if getattr(exists, field) != cfg[field]:
                    setattr(exists, field, cfg[field])
                    changed = True
            if changed:
                logger.info("Updated AI provider: %s", cfg["name"])
            else:
                logger.debug("Provider '%s' already up-to-date, skipping.", cfg["name"])
            continue

        provider = AIProvider(
            id=str(uuid4()),
            name=cfg["name"],
            provider_type=cfg["provider_type"],
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            models=cfg["models"],
            is_default=cfg["is_default"],
            enabled=cfg["enabled"],
            priority=cfg["priority"],
        )
        db.add(provider)
        logger.info("Seeded AI provider: %s (%s)", cfg["name"], cfg["provider_type"])

    db.commit()
