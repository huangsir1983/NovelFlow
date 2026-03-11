"""UnrealMake (虚幻造物) backend configuration."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "UnrealMake"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database — default PostgreSQL for production, SQLite still supported via env
    database_url: str = "postgresql+psycopg2://unrealmake:unrealmake@localhost:5432/unrealmake"
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_recycle: int = 1800

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS — read from env CORS_ORIGINS as comma-separated string
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # AI
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-6"

    # AI rate limiting
    ai_rpm_limit: int = 500
    ai_tpm_limit: int = 800000

    # Import concurrency
    max_concurrent_imports: int = 50

    # Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
