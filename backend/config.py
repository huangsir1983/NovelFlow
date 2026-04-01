"""UnrealMake (虚幻造物) backend configuration."""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "UnrealMake"
    app_version: str = "0.1.0"
    debug: bool = False
    app_env: str = "development"  # development | production

    # Database — default PostgreSQL for production, SQLite still supported in development
    database_url: str = "postgresql+psycopg2://unrealmake:unrealmake@localhost:5432/unrealmake"
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_recycle: int = 1800
    db_slow_query_ms: int = 300
    db_explain_on_startup: bool = True

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Queue mode
    use_celery_queue: bool = False

    # Queue tuning (P1-1)
    queue_import_name: str = "import_queue"
    queue_image_name: str = "image_queue"
    queue_video_name: str = "video_queue"
    queue_export_name: str = "export_queue"

    # Concurrent task quota (P1-2)
    limit_global_tasks: int = 120
    limit_tenant_tasks: int = 40
    limit_project_tasks: int = 20

    # Storage
    storage_provider: str = "local"  # local | oss
    storage_local_dir: str = "./uploads"
    oss_endpoint: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket_name: str = ""
    oss_prefix: str = "unrealmake"

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

    # RunningHub (view-angle conversion)
    runninghub_api_key: str = ""
    runninghub_base_url: str = "https://www.runninghub.cn/openapi/v2"
    runninghub_app_id: str = "2026919371204993025"
    runninghub_instance_type: str = "default"

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

    @model_validator(mode="after")
    def validate_production_database(self):
        """Enforce PostgreSQL in production and validate storage settings."""
        env = (self.app_env or "development").lower()
        if env == "production" and "postgresql" not in (self.database_url or ""):
            raise ValueError("Production requires PostgreSQL DATABASE_URL. SQLite is not allowed.")

        provider = (self.storage_provider or "local").lower()
        if provider == "oss":
            required = [
                self.oss_endpoint,
                self.oss_access_key_id,
                self.oss_access_key_secret,
                self.oss_bucket_name,
            ]
            if not all(required):
                raise ValueError("storage_provider=oss requires OSS endpoint/key/bucket configuration.")

        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
