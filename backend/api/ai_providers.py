"""AI Providers CRUD API — manage multi-vendor AI provider configurations."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.ai_provider import AIProvider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settings"])


# --- Schemas ---

class ModelConfig(BaseModel):
    model_id: str
    display_name: str = ""
    model_type: str = "text"  # text | image | video
    capability_tier: str = "standard"  # fast | standard | advanced
    max_tokens: int = 4096
    supports_streaming: bool = True


class ProviderCreate(BaseModel):
    name: str
    provider_type: str  # anthropic | gemini | openai_compat
    base_url: str = ""
    api_key: str = ""
    models: list[ModelConfig] = []
    is_default: bool = False
    enabled: bool = True
    priority: int = 10


class ProviderUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: list[ModelConfig] | None = None
    is_default: bool | None = None
    enabled: bool | None = None
    priority: int | None = None


def _mask_key(key: str) -> str:
    """Mask API key for safe display."""
    if not key or len(key) < 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _serialize_provider(p: AIProvider) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "provider_type": p.provider_type,
        "base_url": p.base_url,
        "api_key_masked": _mask_key(p.api_key),
        "models": p.models or [],
        "is_default": p.is_default,
        "enabled": p.enabled,
        "priority": p.priority,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# --- Routes ---

@router.get("/settings/ai-providers")
def list_providers(db: Session = Depends(get_db)):
    """List all AI providers (keys masked)."""
    providers = db.query(AIProvider).order_by(AIProvider.priority).all()
    return {"providers": [_serialize_provider(p) for p in providers]}


@router.post("/settings/ai-providers")
def create_provider(data: ProviderCreate, db: Session = Depends(get_db)):
    """Add a new AI provider."""
    valid_types = {"anthropic", "gemini", "openai_compat", "responses_api", "grok_video", "nanobanana"}
    if data.provider_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid provider_type. Allowed: {', '.join(valid_types)}")

    # If setting as default, clear other defaults
    if data.is_default:
        db.query(AIProvider).filter(AIProvider.is_default == True).update({"is_default": False})

    provider = AIProvider(
        id=str(uuid4()),
        name=data.name,
        provider_type=data.provider_type,
        base_url=data.base_url,
        api_key=data.api_key,
        models=[m.model_dump() for m in data.models],
        is_default=data.is_default,
        enabled=data.enabled,
        priority=data.priority,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    # Invalidate AI engine cache
    _invalidate_engine_cache()

    return _serialize_provider(provider)


@router.put("/settings/ai-providers/{provider_id}")
def update_provider(provider_id: str, data: ProviderUpdate, db: Session = Depends(get_db)):
    """Update an AI provider."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if data.name is not None:
        provider.name = data.name
    if data.provider_type is not None:
        valid_types = {"anthropic", "gemini", "openai_compat", "responses_api", "grok_video", "nanobanana"}
        if data.provider_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid provider_type")
        provider.provider_type = data.provider_type
    if data.base_url is not None:
        provider.base_url = data.base_url
    if data.api_key is not None:
        provider.api_key = data.api_key
    if data.models is not None:
        provider.models = [m.model_dump() for m in data.models]
    if data.is_default is not None:
        if data.is_default:
            db.query(AIProvider).filter(AIProvider.id != provider_id, AIProvider.is_default == True).update({"is_default": False})
        provider.is_default = data.is_default
    if data.enabled is not None:
        provider.enabled = data.enabled
    if data.priority is not None:
        provider.priority = data.priority

    db.commit()
    db.refresh(provider)

    _invalidate_engine_cache()

    return _serialize_provider(provider)


@router.delete("/settings/ai-providers/{provider_id}")
def delete_provider(provider_id: str, db: Session = Depends(get_db)):
    """Delete an AI provider."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    db.delete(provider)
    db.commit()

    _invalidate_engine_cache()

    return {"deleted": True}


@router.post("/settings/ai-providers/{provider_id}/test")
def test_provider(provider_id: str, db: Session = Depends(get_db)):
    """Test connectivity to an AI provider."""
    provider = db.query(AIProvider).filter(AIProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        from services.providers import create_adapter
        adapter = create_adapter(
            provider.provider_type,
            base_url=provider.base_url,
            api_key=provider.api_key,
            provider_name=provider.name,
        )
        ok = adapter.health_check()
        return {
            "success": ok,
            "message": "Connection successful" if ok else "Health check failed",
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
        }


@router.get("/settings/ai-providers/available-models")
def available_models(db: Session = Depends(get_db)):
    """List all available models grouped by model_type and capability_tier.

    Returns:
        {
            "text":  {"fast": [...], "standard": [...], "advanced": [...]},
            "image": {"fast": [...], "standard": [...], "advanced": [...]},
            "video": {"fast": [...], "standard": [...], "advanced": [...]},
        }
    """
    from config import settings

    def _empty_tiers():
        return {"fast": [], "standard": [], "advanced": []}

    result: dict[str, dict[str, list]] = {
        "text": _empty_tiers(),
        "image": _empty_tiers(),
        "video": _empty_tiers(),
    }

    # DB providers
    providers = db.query(AIProvider).filter(AIProvider.enabled == True).order_by(AIProvider.priority).all()
    for provider in providers:
        for m in (provider.models or []):
            model_type = m.get("model_type", "text")
            tier = m.get("capability_tier", "standard")
            if model_type in result and tier in result[model_type]:
                result[model_type][tier].append({
                    "provider_id": provider.id,
                    "provider_name": provider.name,
                    "provider_type": provider.provider_type,
                    "model_id": m.get("model_id", ""),
                    "display_name": m.get("display_name", m.get("model_id", "")),
                    "model_type": model_type,
                    "max_tokens": m.get("max_tokens", 4096),
                    "supports_streaming": m.get("supports_streaming", True),
                })

    # Env Anthropic fallback (text only)
    if settings.anthropic_api_key:
        for tier, model_id, display in [
            ("fast", "claude-haiku-4-5-20251001", "Claude Haiku (env)"),
            ("standard", "claude-sonnet-4-6", "Claude Sonnet (env)"),
            ("advanced", "claude-opus-4-6", "Claude Opus (env)"),
        ]:
            result["text"][tier].append({
                "provider_id": "_env_anthropic",
                "provider_name": "Anthropic (env)",
                "provider_type": "anthropic",
                "model_id": model_id,
                "display_name": display,
                "model_type": "text",
                "max_tokens": 8192,
                "supports_streaming": True,
            })

    return {"models": result}


def _invalidate_engine_cache():
    """Invalidate AI engine adapter cache."""
    try:
        from services.ai_engine import ai_engine
        ai_engine.invalidate_cache()
    except Exception:
        pass
