"""NovelFlow FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from api.projects import router as projects_router


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
