"""
涛割 - 数据库会话管理
"""

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base


class DatabaseManager:
    """数据库管理器 - 单例模式"""

    _instance: Optional['DatabaseManager'] = None
    _engine = None
    _session_factory = None

    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        # 默认数据库路径
        if db_path is None:
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "taoge.db")

        self.db_path = db_path
        self._init_database()
        self._initialized = True

    def _init_database(self):
        """初始化数据库连接"""
        # SQLite配置
        self._engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False  # 设置为True可以看到SQL日志
        )

        # 创建所有表
        Base.metadata.create_all(self._engine)

        # 增量迁移：为旧数据库添加新列
        self._migrate_schema()

        # 创建会话工厂
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False
        )

    def _migrate_schema(self):
        """增量迁移 - 检测并添加缺失的列"""
        inspector = sa_inspect(self._engine)
        table_names = inspector.get_table_names()

        def _add_missing_columns(table_name, migrations):
            """为已有表添加缺失的列"""
            if table_name not in table_names:
                return
            existing_cols = {c['name'] for c in inspector.get_columns(table_name)}
            with self._engine.connect() as conn:
                for col_name, col_def in migrations.items():
                    if col_name not in existing_cols:
                        conn.execute(text(
                            f'ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}'
                        ))
                        conn.commit()

        # ── scenes 表迁移 ──
        _add_missing_columns('scenes', {
            'act_id': 'INTEGER REFERENCES acts(id)',
            'scene_type': "VARCHAR(50) DEFAULT 'normal'",
            'shot_label': 'VARCHAR(50)',
            'visual_prompt_struct': 'TEXT',
            'audio_config': 'TEXT',
            'eye_focus': 'TEXT',
            'motion_vectors': 'TEXT',
            'use_prev_end_frame': 'BOOLEAN DEFAULT 0',
            'end_frame_source': 'VARCHAR(512)',
            'continuity_notes': 'TEXT',
            # v1.2 增强分镜信息
            'scene_environment': 'VARCHAR(255)',
            'shot_size': 'VARCHAR(20)',
            'character_actions': 'TEXT',
            'atmosphere': 'VARCHAR(255)',
            'interaction_desc': 'TEXT',
            'is_empty_shot': 'BOOLEAN DEFAULT 0',
            'bound_assets': 'TEXT',
            'generated_audio_path': 'VARCHAR(512)',
        })

        # ── projects 表迁移 ──
        _add_missing_columns('projects', {
            'animatic_settings': 'TEXT',
            # v1.2 视觉圣经
            'lighting_bible': 'TEXT',
            'cinematography_guide': 'TEXT',
            'continuity_bible': 'TEXT',
        })

        # ── assets 表迁移 ──
        _add_missing_columns('assets', {
            # 角色专用扩展
            'visual_anchors': 'TEXT',
            'sora_id': 'VARCHAR(255)',
            'age_group': 'VARCHAR(20)',
            'gender': 'VARCHAR(10)',
            # 衍生形象扩展
            'owner_asset_id': 'INTEGER REFERENCES assets(id)',
            'variant_type': 'VARCHAR(50)',
            'variant_description': 'VARCHAR(255)',
            'state_variants': 'TEXT',
            # 通用扩展
            'multi_angle_images': 'TEXT',
            'establishing_shot': 'VARCHAR(512)',
        })

        # ── layers 表迁移 ──
        _add_missing_columns('layers', {
            'blend_mode': "VARCHAR(30) DEFAULT 'normal'",
            'opacity': 'REAL DEFAULT 1.0',
            'original_image_path': 'VARCHAR(512)',
        })

        # ── costume → character variant 数据迁移（幂等） ──
        if 'assets' in table_names:
            with self._engine.connect() as conn:
                conn.execute(text("""
                    UPDATE assets
                    SET asset_type = 'character',
                        variant_type = 'costume_variant'
                    WHERE asset_type = 'costume'
                """))
                conn.commit()

        if 'asset_requirements' in table_names:
            with self._engine.connect() as conn:
                conn.execute(text("""
                    UPDATE asset_requirements
                    SET requirement_type = 'character'
                    WHERE requirement_type = 'costume'
                """))
                conn.commit()

    @property
    def engine(self):
        """获取数据库引擎"""
        return self._engine

    def get_session(self) -> Session:
        """获取新的数据库会话"""
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """提供事务范围的会话上下文管理器"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def drop_all_tables(self):
        """删除所有表（谨慎使用）"""
        Base.metadata.drop_all(self._engine)

    def recreate_all_tables(self):
        """重建所有表（谨慎使用）"""
        self.drop_all_tables()
        Base.metadata.create_all(self._engine)

    @classmethod
    def reset_instance(cls):
        """重置单例实例（主要用于测试）"""
        if cls._instance is not None:
            if cls._instance._engine:
                cls._instance._engine.dispose()
            cls._instance = None


# 便捷函数
def get_db_manager(db_path: str = None) -> DatabaseManager:
    """获取数据库管理器实例"""
    return DatabaseManager(db_path)


def get_session() -> Session:
    """获取数据库会话"""
    return get_db_manager().get_session()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """会话上下文管理器"""
    with get_db_manager().session_scope() as session:
        yield session
