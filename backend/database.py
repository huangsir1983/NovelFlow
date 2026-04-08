"""Database engine, session, and initialization."""

import logging
import time
import uuid
from pathlib import Path
from sqlalchemy import create_engine, text, inspect, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from typing import Generator

from config import settings
from models.base import Base

logger = logging.getLogger(__name__)

_is_sqlite = "sqlite" in settings.database_url

if settings.app_env.lower() == "production" and _is_sqlite:
    raise RuntimeError("Production mode does not allow SQLite. Please set PostgreSQL DATABASE_URL.")

if _is_sqlite:
    # SQLite development mode — single-thread friendly
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False, "timeout": 60},
        echo=settings.debug,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
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

@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start = getattr(context, "_query_start_time", None)
    if not start:
        return
    elapsed_ms = (time.time() - start) * 1000
    if elapsed_ms > settings.db_slow_query_ms:
        sql_preview = " ".join((statement or "").split())[:240]
        logger.warning("Slow query %.1fms > %sms: %s", elapsed_ms, settings.db_slow_query_ms, sql_preview)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def commit_with_retry(db: Session, max_retries: int = 5, base_delay: float = 0.3) -> None:
    """Commit helper.

    SQLite keeps retry logic for local development lock contention.
    PostgreSQL path commits directly.
    """
    if not _is_sqlite:
        db.commit()
        return

    for attempt in range(max_retries + 1):
        try:
            db.commit()
            return
        except OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"DB locked on commit, retry {attempt + 1}/{max_retries} in {delay:.1f}s")
                db.rollback()
                time.sleep(delay)
            else:
                raise


def init_db() -> None:
    """Create all tables, apply missing column migrations, and seed data."""
    Base.metadata.create_all(bind=engine)
    _apply_column_migrations()
    _ensure_core_indexes()
    if settings.db_explain_on_startup:
        _log_index_startup_selfcheck()
    _seed_style_templates()


def _ensure_core_indexes() -> None:
    """Ensure critical composite indexes exist for P1-3."""
    ddl = [
        "CREATE INDEX IF NOT EXISTS idx_import_tasks_project_created ON import_tasks(project_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_scenes_project_order ON scenes(project_id, \"order\")",
        "CREATE INDEX IF NOT EXISTS idx_shot_groups_project_scene_order ON shot_groups(project_id, scene_id, \"order\")",
    ]
    for stmt in ddl:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception as e:
            logger.warning("Ensure index failed: %s (%s)", stmt, e)


def _log_index_startup_selfcheck() -> None:
    """Log index hit self-check on startup and persist EXPLAIN snapshots."""
    try:
        with engine.begin() as conn:
            queries = {
                "import_tasks": "EXPLAIN SELECT * FROM import_tasks WHERE project_id='demo' ORDER BY created_at DESC LIMIT 20",
                "scenes": "EXPLAIN SELECT * FROM scenes WHERE project_id='demo' ORDER BY \"order\" ASC LIMIT 50",
                "shot_groups": "EXPLAIN SELECT * FROM shot_groups WHERE project_id='demo' AND scene_id='demo' ORDER BY \"order\" ASC LIMIT 50",
            }

            snapshot_lines: list[str] = []
            for name, sql in queries.items():
                try:
                    rows = conn.execute(text(sql)).fetchall()
                    plan_lines = [str(r[0]) for r in rows]
                    plan_text = "\n".join(plan_lines)
                    hit = any(("Index" in ln) or ("index" in ln) for ln in plan_lines)
                    logger.info("Index self-check %s hit=%s", name, hit)
                    snapshot_lines.append(f"[{name}] hit={hit}\n{plan_text}\n")
                except Exception as e:
                    err = f"[{name}] hit=unknown\nERROR: {e}\n"
                    snapshot_lines.append(err)
                    logger.warning("EXPLAIN self-check failed for %s: %s", name, e)

            snapshot_dir = Path(settings.upload_dir) / "diagnostics"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            target = snapshot_dir / f"explain_snapshot_{ts}.txt"
            target.write_text("\n".join(snapshot_lines), encoding="utf-8")
            logger.info("EXPLAIN snapshot written: %s", target)
    except Exception as e:
        logger.warning("Index startup self-check skipped: %s", e)


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
            ("novel_analysis", "TEXT"),
            ("source_file_name", "VARCHAR(255)"),
            ("source_storage_provider", "VARCHAR(20)"),
            ("source_storage_key", "VARCHAR(512)"),
            ("source_storage_uri", "TEXT"),
            ("source_file_size", "INTEGER"),
            ("story_bible_overrides", "JSON"),
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
            ("generated_script", "TEXT"),
            ("edited_source_text", "TEXT"),
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
            ("viewpoints", "JSON"),
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
            ("adaptation_direction", "VARCHAR(20)"),
            ("screen_format", "VARCHAR(20)"),
            ("style_preset", "VARCHAR(30)"),
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

    # P1-3: critical composite indexes
    required_indexes = {
        "import_tasks": [
            ("idx_import_tasks_project_created", "project_id, created_at"),
        ],
        "scenes": [
            ("idx_scenes_project_order", "project_id, \"order\""),
        ],
        "shot_groups": [
            ("idx_shot_groups_project_scene_order", "project_id, scene_id, \"order\""),
        ],
    }

    for table, indexes in required_indexes.items():
        if table not in inspector.get_table_names():
            continue

        existing_indexes = {idx.get("name") for idx in inspector.get_indexes(table)}

        for idx_name, idx_expr in indexes:
            if idx_name in existing_indexes:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({idx_expr})"))
                logger.info(f"Migration: created index {idx_name} on {table}")
            except Exception as e:
                msg = f"index {table}.{idx_name}: {e}"
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
