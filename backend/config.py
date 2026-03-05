"""NovelFlow backend configuration."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "NovelFlow"
    app_version: str = "0.1.0"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./novelflow.db"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # AI
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-6"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
