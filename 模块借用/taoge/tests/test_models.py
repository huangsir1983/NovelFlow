"""
涛割 - 数据库模型测试
"""

import pytest
from datetime import datetime


class TestProjectModel:
    """项目模型测试"""

    def test_create_project(self, temp_db):
        """测试创建项目"""
        from database import Project

        with temp_db.session_scope() as session:
            project = Project(
                name="新项目",
                description="项目描述",
                source_type="srt",
                canvas_width=1920,
                canvas_height=1080,
            )
            session.add(project)
            session.flush()

            assert project.id is not None
            assert project.name == "新项目"
            assert project.status == "draft"
            assert project.total_scenes == 0

    def test_project_to_dict(self, temp_db, sample_project):
        """测试项目转字典"""
        from database import Project

        with temp_db.session_scope() as session:
            project = session.query(Project).get(sample_project)
            data = project.to_dict()

            assert data['id'] == sample_project
            assert data['name'] == "测试项目"
            assert data['canvas_width'] == 1920
            assert 'created_at' in data

    def test_project_scenes_relationship(self, temp_db, sample_project, sample_scene):
        """测试项目与场景的关联"""
        from database import Project

        with temp_db.session_scope() as session:
            project = session.query(Project).get(sample_project)
            assert len(project.scenes) == 1
            assert project.scenes[0].name == "场景1"


class TestSceneModel:
    """场景模型测试"""

    def test_create_scene(self, temp_db, sample_project):
        """测试创建场景"""
        from database import Scene

        with temp_db.session_scope() as session:
            scene = Scene(
                project_id=sample_project,
                scene_index=1,
                name="测试场景",
                start_time="00:00:00,000",
                end_time="00:00:10,000",
                duration=10.0,
                subtitle_text="测试字幕内容",
            )
            session.add(scene)
            session.flush()

            assert scene.id is not None
            assert scene.status == "pending"
            assert scene.duration == 10.0

    def test_scene_to_dict(self, temp_db, sample_scene):
        """测试场景转字典"""
        from database import Scene

        with temp_db.session_scope() as session:
            scene = session.query(Scene).get(sample_scene)
            data = scene.to_dict()

            assert data['id'] == sample_scene
            assert data['scene_index'] == 1
            assert data['subtitle_text'] == "这是测试字幕"

    def test_scene_ai_tags(self, temp_db, sample_scene):
        """测试场景AI标签"""
        from database import Scene

        with temp_db.session_scope() as session:
            scene = session.query(Scene).get(sample_scene)
            scene.ai_tags = {
                "场景": ["室内", "办公室"],
                "角色": ["主角"],
                "道具": ["电脑"]
            }

        with temp_db.session_scope() as session:
            scene = session.query(Scene).get(sample_scene)
            assert "场景" in scene.ai_tags
            assert "室内" in scene.ai_tags["场景"]


class TestCharacterModel:
    """角色模型测试"""

    def test_create_character(self, temp_db):
        """测试创建角色"""
        from database import Character

        with temp_db.session_scope() as session:
            character = Character(
                name="新角色",
                character_type="human",
                appearance="金发碧眼",
                clothing="西装",
            )
            session.add(character)
            session.flush()

            assert character.id is not None
            assert character.is_active == True

    def test_character_full_description(self, temp_db, sample_character):
        """测试角色完整描述"""
        from database import Character

        with temp_db.session_scope() as session:
            character = session.query(Character).get(sample_character)
            desc = character.get_full_description()

            assert "测试角色" in desc
            assert "黑发" in desc

    def test_character_to_dict(self, temp_db, sample_character):
        """测试角色转字典"""
        from database import Character

        with temp_db.session_scope() as session:
            character = session.query(Character).get(sample_character)
            data = character.to_dict()

            assert data['name'] == "测试角色"
            assert data['character_type'] == "human"
            assert data['is_global'] == True


class TestTaskModel:
    """任务模型测试"""

    def test_create_task(self, temp_db, sample_project):
        """测试创建任务"""
        from database import Task

        with temp_db.session_scope() as session:
            task = Task(
                project_id=sample_project,
                task_type="image_gen",
                task_name="生成图片",
                priority=5,
            )
            session.add(task)
            session.flush()

            assert task.id is not None
            assert task.status == "pending"
            assert task.progress == 0.0

    def test_task_is_retryable(self, temp_db, sample_project):
        """测试任务可重试判断"""
        from database import Task

        with temp_db.session_scope() as session:
            task = Task(
                project_id=sample_project,
                task_type="video_gen",
                status="failed",
                retry_count=1,
                max_retries=3,
            )
            session.add(task)
            session.flush()

            assert task.is_retryable == True

            task.retry_count = 3
            assert task.is_retryable == False

    def test_task_duration(self, temp_db, sample_project):
        """测试任务时长计算"""
        from database import Task
        from datetime import datetime, timedelta

        with temp_db.session_scope() as session:
            now = datetime.now()
            task = Task(
                project_id=sample_project,
                task_type="image_gen",
                started_at=now,
                completed_at=now + timedelta(seconds=30),
            )
            session.add(task)
            session.flush()

            assert task.duration == 30.0
