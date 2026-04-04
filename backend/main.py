"""UnrealMake (虚幻造物) FastAPI application."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Send

from config import settings
from database import init_db
from api.projects import router as projects_router
from api.import_novel import router as import_novel_router
from api.beats import router as beats_router
from api.scenes import router as scenes_router
from api.ai_operations import router as ai_operations_router
from api.knowledge import router as knowledge_router
from api.import_script import router as import_script_router
from api.ai_providers import router as ai_providers_router
from api.image_gen import router as image_gen_router
from api.video_gen import router as video_gen_router
from api.budget import router as budget_router
from api.shot_actions import router as shot_actions_router
from api.novel_analysis import router as novel_analysis_router
from api.export import router as export_router
from api.asset_generation import router as asset_gen_router
from api.asset_images import router as asset_images_router
from api.pipeline import router as pipeline_router
from api.artifacts_writeback import router as artifacts_writeback_router
from api.collaboration import router as collaboration_router
from api.preview_export import router as preview_export_router
from api.canvas import router as canvas_router
from api.chain_templates import router as chain_templates_router
from api.workflow_execution import router as workflow_execution_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # ── Startup ──
    init_db()

    # Seed pre-configured AI providers (idempotent)
    from database import SessionLocal
    from services.seed_providers import seed_providers
    from services.seed_chain_templates import seed_chain_templates
    db = SessionLocal()
    try:
        seed_providers(db)
        seed_chain_templates(db)
    finally:
        db.close()

    yield

    # ── Shutdown ──
    logger.info("Shutting down: cancelling active pipelines...")
    from services.import_pipeline import ImportPipeline
    ImportPipeline.cancel_all()

    logger.info("Shutting down: draining import executor...")
    from api.import_novel import shutdown_executor
    shutdown_executor(wait=True)

    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# CORS — in development allow all origins (for tunnel/remote testing);
# in production restrict to configured origins.
_cors_origins = ["*"] if settings.app_env == "development" else settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if settings.app_env != "development" else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Ensure /uploads/ responses always carry CORS headers, even when the browser
# sends no Origin header (e.g. direct navigation or <img> without crossOrigin).
# Without this, cached non-CORS responses break subsequent WebGL texture loads.
class _UploadsCORSMiddleware:
    def __init__(self, app_: "ASGIApp"):
        self.app = app_

    async def __call__(self, scope: dict, receive: "Receive", send: "Send"):
        if scope["type"] == "http" and scope.get("path", "").startswith("/uploads/"):
            async def _send(message: dict):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    if not any(k == b"access-control-allow-origin" for k, _ in headers):
                        headers.append((b"access-control-allow-origin", b"*"))
                    message = {**message, "headers": headers}
                await send(message)
            await self.app(scope, receive, _send)
        else:
            await self.app(scope, receive, send)


app.add_middleware(_UploadsCORSMiddleware)


@app.get("/api/health")
def health_check():
    """Enhanced health check: DB + Redis + Storage connectivity + active imports."""
    from database import engine
    from sqlalchemy import text

    health = {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }

    # Check DB
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["db"] = "connected"
    except Exception as e:
        health["db"] = f"error: {e}"
        health["status"] = "degraded"

    # Check Redis
    try:
        from services.event_bus import _get_redis
        r = _get_redis()
        if r is not None:
            r.ping()
            health["redis"] = "connected"
        else:
            health["redis"] = "unavailable (memory fallback)"
    except Exception as e:
        health["redis"] = f"error: {e}"

    # Check Storage
    try:
        from services.storage_adapter import get_storage, get_storage_metrics

        storage = get_storage()
        ok, detail = storage.health_check()
        health["storage"] = "connected" if ok else f"error: {detail}"
        health["storage_provider"] = settings.storage_provider
        health["storage_metrics"] = get_storage_metrics()
        if not ok:
            health["status"] = "degraded"
    except Exception as e:
        health["storage"] = f"error: {e}"
        health["status"] = "degraded"

    # Quota usage snapshot
    try:
        from services.task_quota import get_quota_usage_snapshot

        health["quota_usage"] = get_quota_usage_snapshot()
    except Exception as e:
        health["quota_usage"] = {"error": str(e)}

    # Active imports + SSE metrics
    from api.import_novel import get_active_import_count, get_sse_metrics
    health["active_imports"] = get_active_import_count()
    health["sse_metrics"] = get_sse_metrics()

    return health


# Routers
app.include_router(projects_router, prefix="/api")
app.include_router(import_novel_router, prefix="/api")
app.include_router(beats_router, prefix="/api")
app.include_router(scenes_router, prefix="/api")
app.include_router(ai_operations_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(import_script_router, prefix="/api")
app.include_router(ai_providers_router, prefix="/api")
app.include_router(image_gen_router, prefix="/api")
app.include_router(video_gen_router, prefix="/api")
app.include_router(budget_router, prefix="/api")
app.include_router(shot_actions_router, prefix="/api")
app.include_router(novel_analysis_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(asset_gen_router, prefix="/api")
app.include_router(asset_images_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(artifacts_writeback_router, prefix="/api")
app.include_router(collaboration_router, prefix="/api")
app.include_router(preview_export_router, prefix="/api")
app.include_router(canvas_router, prefix="/api")
app.include_router(chain_templates_router, prefix="/api")
app.include_router(workflow_execution_router, prefix="/api")


# ── Static frontend served at root ──

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def serve_index():
    """Serve the frontend SPA."""
    return FileResponse(STATIC_DIR / "index.html")


# Mount static assets (css, js, images) if any extra files exist
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount uploads directory so stored images are accessible via URL
UPLOADS_DIR = Path(__file__).parent / "uploads"
if UPLOADS_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
