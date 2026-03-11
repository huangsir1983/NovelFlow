"""AIProvider model — stores multi-vendor AI provider configurations."""

from sqlalchemy import Column, String, Text, JSON, Boolean, Integer

from models.base import Base, TimestampMixin


class AIProvider(Base, TimestampMixin):
    """AI provider configuration (Anthropic, Gemini, OpenAI-compatible, etc.)."""

    __tablename__ = "ai_providers"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    provider_type = Column(String(30), nullable=False)  # anthropic | gemini | openai_compat
    base_url = Column(String(500), nullable=False, default="")
    api_key = Column(Text, nullable=False, default="")
    models = Column(JSON, nullable=False, default=lambda: [])
    is_default = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=10)
