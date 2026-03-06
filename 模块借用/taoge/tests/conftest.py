"""
涛割 - 测试配置
"""

import os
import sys
import tempfile

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest


@pytest.fixture
def temp_db(tmp_path):
    """创建临时数据库"""
    from database.session import DatabaseManager

    # 重置单例
    DatabaseManager._instance = None
    DatabaseManager._engine = None
    DatabaseManager._session_factory = None

    db_path = str(tmp_path / "test.db")
    db_manager = DatabaseManager(db_path)

    yield db_manager

    # 清理
    DatabaseManager._instance = None
    DatabaseManager._engine = None
    DatabaseManager._session_factory = None


@pytest.fixture
def sample_project(temp_db):
    """创建示例项目"""
    from database import Project

    with temp_db.session_scope() as session:
        project = Project(
            name="测试项目",
            description="这是一个测试项目",
            source_type="srt",
            canvas_width=1920,
            canvas_height=1080,
            total_scenes=5,
        )
        session.add(project)
        session.flush()
        project_id = project.id

    return project_id


@pytest.fixture
def sample_scene(temp_db, sample_project):
    """创建示例场景"""
    from database import Scene

    with temp_db.session_scope() as session:
        scene = Scene(
            project_id=sample_project,
            scene_index=1,
            name="场景1",
            start_time="00:00:00,000",
            end_time="00:00:05,000",
            duration=5.0,
            subtitle_text="这是测试字幕",
            status="pending"
        )
        session.add(scene)
        session.flush()
        scene_id = scene.id

    return scene_id


@pytest.fixture
def sample_character(temp_db):
    """创建示例角色"""
    from database import Character

    with temp_db.session_scope() as session:
        character = Character(
            name="测试角色",
            character_type="human",
            description="测试角色描述",
            appearance="黑发，蓝眼",
            is_global=True,
            is_active=True
        )
        session.add(character)
        session.flush()
        char_id = character.id

    return char_id
