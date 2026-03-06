"""UnrealMake (虚幻造物) FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    init_db()


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


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
