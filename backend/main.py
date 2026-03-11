"""UnrealMake (虚幻造物) FastAPI application."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # ── Startup ──
    init_db()

    # Seed pre-configured AI providers (idempotent)
    from database import SessionLocal
    from services.seed_providers import seed_providers
    db = SessionLocal()
    try:
        seed_providers(db)
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

# CORS — origins from config (overridable via CORS_ORIGINS env var)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    """Enhanced health check: DB + Redis connectivity + active imports."""
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

    # Active imports
    from api.import_novel import get_active_import_count
    health["active_imports"] = get_active_import_count()

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


# ── Static frontend served at root ──

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def serve_index():
    """Serve the frontend SPA."""
    return FileResponse(STATIC_DIR / "index.html")


# Mount static assets (css, js, images) if any extra files exist
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
