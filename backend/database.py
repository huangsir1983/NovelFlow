"""Database engine, session, and initialization."""

import logging
import uuid
from sqlalchemy import create_engine, text, inspect, event
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from config import settings
from models.base import Base

logger = logging.getLogger(__name__)

_is_sqlite = "sqlite" in settings.database_url

if _is_sqlite:
    # SQLite development mode — single-thread friendly
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        echo=settings.debug,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
else:
    # PostgreSQL production mode — connection pool
    engine = create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=30,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
        echo=settings.debug,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables, apply missing column migrations, and seed data."""
    Base.metadata.create_all(bind=engine)
    _apply_column_migrations()
    _seed_style_templates()


def _apply_column_migrations() -> None:
    """Add missing columns to existing tables.

    Each ALTER TABLE runs in its own transaction (B1.2 fix) so a single
    failure does not roll back other successful migrations.  Failures are
    accumulated and reported at the end.
    """
    inspector = inspect(engine)

    migrations = {
        "import_tasks": [
            ("full_text", "TEXT"),
            ("stream_checkpoint", "JSON"),
            ("style_template_id", "VARCHAR(36)"),
        ],
        "scenes": [
            ("characters_present", "JSON"),
            ("key_props", "JSON"),
            ("dramatic_purpose", "TEXT"),
            ("window_index", "INTEGER"),
            ("core_event", "TEXT"),
            ("key_dialogue", "TEXT"),
            ("emotional_peak", "TEXT"),
            ("estimated_duration_s", "INTEGER"),
        ],
        "locations": [
            ("chapter_id", "VARCHAR(36)"),
            ("sensory", "TEXT"),
            ("narrative_function", "TEXT"),
            ("type", "VARCHAR(50)"),
            ("era_style", "TEXT"),
            ("visual_reference", "TEXT"),
            ("atmosphere", "TEXT"),
            ("color_palette", "JSON"),
            ("lighting", "TEXT"),
            ("key_features", "JSON"),
            ("narrative_scene_ids", "JSON"),
            ("scene_count", "INTEGER"),
            ("time_variations", "JSON"),
            ("emotional_range", "TEXT"),
            ("visual_prompt_negative", "TEXT DEFAULT ''"),
        ],
        "characters": [
            ("age_range", "VARCHAR(50)"),
            ("appearance", "JSON"),
            ("costume", "JSON"),
            ("casting_tags", "JSON"),
            ("visual_reference", "TEXT"),
            ("desire", "TEXT"),
            ("flaw", "TEXT"),
            ("visual_prompt_negative", "TEXT DEFAULT ''"),
        ],
        "projects": [
            ("current_phase", "VARCHAR(20) DEFAULT 'workbench'"),
        ],
        "shots": [
            ("beat_id", "VARCHAR(36)"),
            ("reference_assets", "JSON"),
            ("candidates", "JSON"),
            ("quality_score", "JSON"),
            ("next_action", "VARCHAR(100)"),
            ("status", "VARCHAR(20) DEFAULT 'draft'"),
        ],
        "props": [
            ("visual_prompt_negative", "TEXT DEFAULT ''"),
        ],
        "character_variants": [
            ("visual_prompt_negative", "TEXT DEFAULT ''"),
        ],
    }

    _migration_failures: list[str] = []

    for table, columns in migrations.items():
        if table not in inspector.get_table_names():
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for col_name, col_type in columns:
            if col_name not in existing:
                try:
                    with engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"Migration: added {col_name} to {table}")
                except Exception as e:
                    msg = f"{table}.{col_name}: {e}"
                    _migration_failures.append(msg)
                    logger.warning(f"Migration FAILED {msg}")

    if _migration_failures:
        logger.error(
            f"Column migration completed with {len(_migration_failures)} failure(s): "
            + "; ".join(_migration_failures)
        )
    else:
        logger.info("Column migrations: all up to date")


# ---------------------------------------------------------------------------
# Seed data: built-in style templates (A-Step 8)
# ---------------------------------------------------------------------------

_BUILTIN_STYLE_TEMPLATES = [
    {
        "id": "tpl-chinese-3d-animation",
        "name": "中国3D国漫",
        "name_en": "Chinese 3D Animation",
        "description": "适合国产3D动画风格的角色和场景，类似《斗罗大陆》《完美世界》等作品的视觉风格",
        "style_tags": ["3d_render", "chinese_animation", "white_background", "character_sheet"],
        "style_negative": "low quality, blurry, deformed, watermark, text, signature, jpeg artifacts",
        "preview_image_url": "",
        "category": "animation",
        "is_builtin": True,
        "sort_order": 1,
    },
    {
        "id": "tpl-japanese-anime",
        "name": "日式二次元",
        "name_en": "Japanese Anime",
        "description": "经典日式动画风格，赛璐璐上色，鲜艳配色，适合轻小说、漫改等二次元题材",
        "style_tags": ["anime", "cel_shading", "vibrant_colors", "manga_style"],
        "style_negative": "realistic, 3d, photographic, blurry, low quality, watermark, text",
        "preview_image_url": "",
        "category": "animation",
        "is_builtin": True,
        "sort_order": 2,
    },
    {
        "id": "tpl-cinematic-realistic",
        "name": "写实电影风",
        "name_en": "Cinematic Realistic",
        "description": "电影级写实风格，适合现实题材、历史剧、悬疑推理等需要真实感的作品",
        "style_tags": ["cinematic", "photorealistic", "film_grain", "dramatic_lighting"],
        "style_negative": "cartoon, anime, drawing, low quality, blurry, watermark, text",
        "preview_image_url": "",
        "category": "realistic",
        "is_builtin": True,
        "sort_order": 3,
    },
    {
        "id": "tpl-chinese-ink",
        "name": "水墨国风",
        "name_en": "Chinese Ink Painting",
        "description": "传统水墨画风格，适合武侠、仙侠、古风题材，笔触写意，宣纸质感",
        "style_tags": ["chinese_ink_painting", "traditional", "brush_strokes", "rice_paper"],
        "style_negative": "modern, 3d, photographic, neon, digital, cartoon, low quality",
        "preview_image_url": "",
        "category": "illustration",
        "is_builtin": True,
        "sort_order": 4,
    },
]


def _seed_style_templates() -> None:
    """Insert built-in style templates if they don't already exist."""
    from models.style_template import StyleTemplate

    db = SessionLocal()
    try:
        for tpl in _BUILTIN_STYLE_TEMPLATES:
            existing = db.query(StyleTemplate).filter(StyleTemplate.id == tpl["id"]).first()
            if existing is None:
                db.add(StyleTemplate(**tpl))
                logger.info(f"Seed: inserted style template '{tpl['name']}'")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Style template seeding error: {e}")
    finally:
        db.close()
