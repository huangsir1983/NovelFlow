"""
涛割 - 集成测试
端到端流程测试：SRT导入 → 场景拆分 → Prompt生成 → 模型路由 → 导出
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from services.scene.processor import SceneProcessor
from services.scene.prompt_generator import PromptGenerator, PromptContext
from services.generation.model_router import (
    ModelRouter, RoutingContext, RoutingResult,
    SceneType, QualityLevel,
)
from services.export.jianying_exporter import JianyingExporter, ExportConfig
from services.task_queue.manager import (
    TaskQueueManager, TaskInfo, TaskStatus, TaskPriority,
)


# ==================== 测试数据 ====================

SAMPLE_SRT = """\
1
00:00:00,000 --> 00:00:03,000
他站在窗前，望着远方的群山

2
00:00:03,000 --> 00:00:06,000
心中涌起一股莫名的感伤

3
00:00:06,000 --> 00:00:09,500
"我们还能回到从前吗？"他低声说道

4
00:00:09,500 --> 00:00:13,000
她转过身来，眼中闪烁着泪光

5
00:00:13,000 --> 00:00:16,500
窗外的雨越下越大，打在玻璃上发出清脆的声响

6
00:00:16,500 --> 00:00:20,000
两个人就这样默默地站着，谁也没有说话
"""


# ==================== SRT导入 → 场景拆分 ====================

class TestSrtToScenes:
    """SRT导入到场景拆分的完整流程"""

    def test_srt_parse_and_group_duration(self, tmp_path):
        """SRT解析 + 按时长分组"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(SAMPLE_SRT, encoding='utf-8')

        processor = SceneProcessor()
        segments = processor.parse_srt_file(str(srt_file))

        assert len(segments) == 6
        assert segments[0].text == "他站在窗前，望着远方的群山"

        # 按时长分组
        groups = processor.group_segments(segments, strategy="duration")

        assert len(groups) >= 2
        # 每组的总时长不应超过max_duration太多
        for group in groups:
            assert group.duration <= 10.0  # 允许一定容差

    def test_srt_parse_and_group_content(self, tmp_path):
        """SRT解析 + 按内容分组"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(SAMPLE_SRT, encoding='utf-8')

        processor = SceneProcessor()
        segments = processor.parse_srt_file(str(srt_file))
        groups = processor.group_segments(segments, strategy="content")

        assert len(groups) >= 1
        # 所有segment都应归入某个group
        total_segments = sum(len(g.segments) for g in groups)
        assert total_segments == 6

    def test_srt_to_scene_dicts(self, tmp_path):
        """SRT转为场景字典列表（模拟数据库前的中间状态）"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(SAMPLE_SRT, encoding='utf-8')

        processor = SceneProcessor()
        segments = processor.parse_srt_file(str(srt_file))
        groups = processor.group_segments(segments, strategy="duration")

        # 转为场景字典
        scenes = []
        for idx, group in enumerate(groups):
            scene_dict = group.to_dict()
            scene_dict['scene_index'] = idx + 1
            scene_dict['name'] = f"场景 {idx + 1}"
            scenes.append(scene_dict)

        assert len(scenes) >= 2
        assert scenes[0]['scene_index'] == 1
        assert 'segments' in scenes[0]
        assert 'duration' in scenes[0]


# ==================== 场景 → Prompt生成 → 模型路由 ====================

class TestSceneToGeneration:
    """场景到生成请求的流程"""

    def test_scene_to_image_prompt(self):
        """场景文本 → 图像Prompt"""
        generator = PromptGenerator()
        context = PromptContext(
            subtitle_text="她站在雨中，泪水和雨水混在一起",
            style="cinematic",
            mood="sad",
            lighting="dark",
        )

        result = generator.generate_image_prompt(context)

        assert 'prompt' in result
        assert 'negative_prompt' in result
        assert len(result['prompt']) > 0
        # prompt应包含场景相关描述元素
        prompt_lower = result['prompt'].lower()
        assert any(kw in prompt_lower for kw in ['melancholic', 'somber', 'sad', 'dark'])

    def test_scene_to_video_prompt(self):
        """场景文本 → 视频Prompt"""
        generator = PromptGenerator()
        context = PromptContext(
            subtitle_text="他快速跑过走廊",
        )

        result = generator.generate_video_prompt(context, camera_motion="tracking")

        assert 'prompt' in result
        assert 'motion_type' in result
        assert len(result['prompt']) > 0

    def test_prompt_then_route(self):
        """Prompt生成 → 模型路由"""
        # 生成Prompt
        generator = PromptGenerator()
        context = PromptContext(
            subtitle_text="两人在咖啡馆安静地交谈",
            style="cinematic",
        )
        prompt = generator.generate_image_prompt(context)

        # 路由选择
        router = ModelRouter()

        class FakeProvider:
            def __init__(self, n):
                self.name = n
                self.supported_features = {"character_consistency": False}
            def validate_credentials(self):
                return True

        router.register_provider("vidu", FakeProvider("vidu"))
        router.register_provider("jimeng", FakeProvider("jimeng"))

        route_ctx = RoutingContext(
            scene_type=SceneType.DIALOGUE,
            quality_level=QualityLevel.STANDARD,
        )
        result = router.route(route_ctx)

        assert isinstance(result, RoutingResult)
        assert result.provider_name in ["vidu", "jimeng"]
        assert result.estimated_cost > 0


# ==================== 模型路由 → 多模型切换 ====================

class TestMultiModelSwitch:
    """多模型切换测试"""

    @pytest.fixture
    def multi_router(self):
        router = ModelRouter()

        class FakeProvider:
            def __init__(self, n, consistency=False):
                self.name = n
                self.supported_features = {"character_consistency": consistency}
            def validate_credentials(self):
                return True

        router.register_provider("vidu", FakeProvider("vidu", True))
        router.register_provider("kling", FakeProvider("kling"))
        router.register_provider("jimeng", FakeProvider("jimeng"))
        router.register_provider("comfyui", FakeProvider("comfyui", True))
        return router

    def test_dialogue_scene_routing(self, multi_router):
        ctx = RoutingContext(scene_type=SceneType.DIALOGUE)
        result = multi_router.route(ctx)
        assert result.provider_name in ["vidu", "kling", "jimeng", "comfyui"]

    def test_action_scene_routing(self, multi_router):
        ctx = RoutingContext(scene_type=SceneType.ACTION, quality_level=QualityLevel.HIGH)
        result = multi_router.route(ctx)
        assert result.provider_name in ["vidu", "kling", "jimeng", "comfyui"]

    def test_preferred_provider_override(self, multi_router):
        ctx = RoutingContext(preferred_provider="jimeng")
        result = multi_router.route(ctx)
        assert result.provider_name == "jimeng"

    def test_batch_routing_consistency(self, multi_router):
        """批量路由时相同类型场景应分配同一provider"""
        contexts = [
            RoutingContext(scene_type=SceneType.DIALOGUE),
            RoutingContext(scene_type=SceneType.DIALOGUE),
            RoutingContext(scene_type=SceneType.DIALOGUE),
        ]
        results = multi_router.route_batch(contexts, optimize_cost=True)
        assert len(results) == 3
        # 优化模式下相同类型应使用同一provider
        assert results[0].provider_name == results[1].provider_name == results[2].provider_name


# ==================== 任务队列并发测试 ====================

class TestTaskQueueConcurrency:
    """任务队列并发测试"""

    def test_concurrent_limit(self):
        """并发限制测试"""
        queue = TaskQueueManager(max_concurrent=2)

        # 创建多个任务
        ids = []
        for i in range(5):
            tid = queue.create_task(name=f"任务{i}", task_type="image_gen")
            ids.append(tid)

        assert len(ids) == 5
        assert queue.get_pending_count() == 5

    def test_priority_ordering(self):
        """优先级排序测试"""
        queue = TaskQueueManager(max_concurrent=1)

        low = queue.create_task(name="低优先级", task_type="test", priority=TaskPriority.LOW)
        urgent = queue.create_task(name="紧急", task_type="test", priority=TaskPriority.URGENT)
        normal = queue.create_task(name="普通", task_type="test", priority=TaskPriority.NORMAL)

        urgent_task = queue.get_task(urgent)
        normal_task = queue.get_task(normal)
        low_task = queue.get_task(low)

        # URGENT < NORMAL < LOW (数值越小优先级越高)
        assert urgent_task < normal_task
        assert normal_task < low_task

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """并发执行测试"""
        import asyncio
        queue = TaskQueueManager(max_concurrent=2)
        results = []

        async def handler(task, progress_cb):
            await asyncio.sleep(0.1)
            results.append(task.name)
            return {"done": True}

        queue.register_handler("test", handler)

        for i in range(4):
            queue.create_task(name=f"并发任务{i}", task_type="test")

        await queue.start()
        await asyncio.sleep(1.0)  # 等待执行完成
        await queue.stop()

        assert len(results) == 4


# ==================== 错误恢复测试 ====================

class TestErrorRecovery:
    """错误恢复测试"""

    @pytest.mark.asyncio
    async def test_task_retry_on_failure(self):
        """任务失败后重试"""
        import asyncio
        queue = TaskQueueManager(max_concurrent=1)
        call_count = [0]

        async def flaky_handler(task, progress_cb):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("模拟失败")
            return {"result": "ok"}

        queue.register_handler("test", flaky_handler)
        task_id = queue.create_task(name="重试任务", task_type="test")

        await queue.start()
        await asyncio.sleep(1.5)
        await queue.stop()

        # 至少被调用了2次（第一次失败+重试）
        assert call_count[0] >= 2

    def test_cancel_running_task(self):
        """取消排队中的任务"""
        queue = TaskQueueManager(max_concurrent=1)
        task_id = queue.create_task(name="取消测试", task_type="test")

        success = queue.cancel_task(task_id)
        assert success

        task = queue.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED


# ==================== 场景 → 导出 ====================

class TestSceneToExport:
    """场景到剪映导出的流程"""

    def test_scenes_to_jianying_project(self, tmp_path):
        """场景数据 → 剪映项目目录"""
        config = ExportConfig(
            project_name="集成测试项目",
            export_path=str(tmp_path / "export"),
            canvas_width=1920,
            canvas_height=1080,
            fps=30,
            include_subtitles=True,
        )

        exporter = JianyingExporter(config)

        # 模拟场景数据（带字幕、无生成图片/视频）
        scenes = [
            {
                'scene_index': 1,
                'name': '场景1',
                'subtitle_text': '他站在窗前，望着远方的群山',
                'start_time': '00:00:00,000',
                'end_time': '00:00:03,000',
                'start_microseconds': 0,
                'end_microseconds': 3000000,
                'duration': 3.0,
                'generated_image_path': None,
                'generated_video_path': None,
            },
            {
                'scene_index': 2,
                'name': '场景2',
                'subtitle_text': '心中涌起一股莫名的感伤',
                'start_time': '00:00:03,000',
                'end_time': '00:00:06,000',
                'start_microseconds': 3000000,
                'end_microseconds': 6000000,
                'duration': 3.0,
                'generated_image_path': None,
                'generated_video_path': None,
            },
        ]

        project_dir = exporter.create_project(scenes)

        # 验证导出目录存在
        assert os.path.isdir(project_dir)

        # 验证draft_content.json存在
        draft_file = os.path.join(project_dir, "draft_content.json")
        assert os.path.isfile(draft_file)

        # 验证JSON可解析
        import json
        with open(draft_file, 'r', encoding='utf-8') as f:
            draft = json.load(f)

        assert isinstance(draft, dict)


# ==================== 端到端完整流程 ====================

class TestEndToEnd:
    """端到端完整流程测试（不调用真实API）"""

    def test_srt_to_prompts_to_routing(self, tmp_path):
        """SRT → 场景拆分 → Prompt生成 → 路由选择（全链路）"""
        # Step 1: SRT解析
        srt_file = tmp_path / "e2e.srt"
        srt_file.write_text(SAMPLE_SRT, encoding='utf-8')

        processor = SceneProcessor()
        segments = processor.parse_srt_file(str(srt_file))
        assert len(segments) == 6

        # Step 2: 场景分组
        groups = processor.group_segments(segments, strategy="duration")
        assert len(groups) >= 2

        # Step 3: 为每个场景生成Prompt
        generator = PromptGenerator()
        prompts = []
        for group in groups:
            context = PromptContext(
                subtitle_text=group.full_text,
                style="cinematic",
                mood="melancholic",
            )
            img_prompt = generator.generate_image_prompt(context)
            vid_prompt = generator.generate_video_prompt(context)
            prompts.append({
                'image': img_prompt,
                'video': vid_prompt,
            })

        assert len(prompts) == len(groups)
        for p in prompts:
            assert len(p['image']['prompt']) > 0
            assert len(p['video']['prompt']) > 0

        # Step 4: 路由选择
        router = ModelRouter()

        class FakeProvider:
            def __init__(self, n):
                self.name = n
                self.supported_features = {"character_consistency": False}
            def validate_credentials(self):
                return True

        router.register_provider("vidu", FakeProvider("vidu"))
        router.register_provider("jimeng", FakeProvider("jimeng"))

        contexts = [
            RoutingContext(scene_type=SceneType.DIALOGUE, quality_level=QualityLevel.STANDARD)
            for _ in groups
        ]
        results = router.route_batch(contexts, optimize_cost=True)

        assert len(results) == len(groups)
        for r in results:
            assert r.provider_name in ["vidu", "jimeng"]
            assert r.estimated_cost > 0

    def test_full_pipeline_with_export(self, tmp_path):
        """完整管线：SRT → 场景 → Prompt → 路由 → 导出"""
        # SRT解析
        srt_file = tmp_path / "full.srt"
        srt_file.write_text(SAMPLE_SRT, encoding='utf-8')

        processor = SceneProcessor()
        segments = processor.parse_srt_file(str(srt_file))
        groups = processor.group_segments(segments, strategy="duration")

        # 生成Prompt
        generator = PromptGenerator()
        scenes_data = []
        for idx, group in enumerate(groups):
            context = PromptContext(subtitle_text=group.full_text, style="cinematic")
            img_prompt = generator.generate_image_prompt(context)

            scenes_data.append({
                'scene_index': idx + 1,
                'name': f"场景 {idx + 1}",
                'subtitle_text': group.full_text,
                'start_time': group.start_time,
                'end_time': group.end_time,
                'start_microseconds': group.start_microseconds,
                'end_microseconds': group.end_microseconds,
                'duration': group.duration,
                'image_prompt': img_prompt['prompt'],
                'generated_image_path': None,
                'generated_video_path': None,
            })

        # 导出
        config = ExportConfig(
            project_name="端到端测试",
            export_path=str(tmp_path / "e2e_export"),
        )
        exporter = JianyingExporter(config)
        project_dir = exporter.create_project(scenes_data)

        assert os.path.isdir(project_dir)
        assert os.path.isfile(os.path.join(project_dir, "draft_content.json"))


# ==================== 数据库集成测试 ====================

class TestDatabaseIntegration:
    """数据库层集成测试"""

    def test_project_crud_flow(self, temp_db):
        """项目完整CRUD流程"""
        from database import Project, Scene
        from database.session import session_scope

        # Create
        with session_scope() as session:
            project = Project(
                name="集成测试项目",
                source_type="srt",
                total_scenes=3,
            )
            session.add(project)
            session.flush()
            pid = project.id

        assert pid is not None

        # Read
        with session_scope() as session:
            p = session.query(Project).get(pid)
            assert p.name == "集成测试项目"
            assert p.total_scenes == 3

        # Update
        with session_scope() as session:
            p = session.query(Project).get(pid)
            p.status = "processing"
            p.completed_scenes = 1

        with session_scope() as session:
            p = session.query(Project).get(pid)
            assert p.status == "processing"
            assert p.completed_scenes == 1

        # Delete
        with session_scope() as session:
            p = session.query(Project).get(pid)
            session.delete(p)

        with session_scope() as session:
            p = session.query(Project).get(pid)
            assert p is None

    def test_project_scene_cascade(self, temp_db):
        """项目-场景级联操作"""
        from database import Project, Scene
        from database.session import session_scope

        # 创建项目和场景
        with session_scope() as session:
            project = Project(name="级联测试", source_type="srt")
            session.add(project)
            session.flush()
            pid = project.id

            for i in range(3):
                scene = Scene(
                    project_id=pid,
                    scene_index=i + 1,
                    name=f"场景{i+1}",
                    duration=3.0,
                    status="pending",
                )
                session.add(scene)

        # 验证场景创建
        with session_scope() as session:
            scenes = session.query(Scene).filter(Scene.project_id == pid).all()
            assert len(scenes) == 3

    def test_character_with_project(self, temp_db):
        """角色与项目关联"""
        from database import Character, Project
        from database.session import session_scope

        with session_scope() as session:
            project = Project(name="角色测试项目", source_type="srt")
            session.add(project)
            session.flush()
            pid = project.id

            char = Character(
                name="测试角色A",
                character_type="human",
                project_id=pid,
                is_active=True,
            )
            session.add(char)
            session.flush()
            cid = char.id

        with session_scope() as session:
            c = session.query(Character).get(cid)
            assert c.project_id == pid
            assert c.name == "测试角色A"


# ==================== Controller层集成测试 ====================

class TestControllerIntegration:
    """Controller层集成测试"""

    def test_project_controller_flow(self, temp_db):
        """ProjectController 完整流程"""
        from services.controllers.project_controller import ProjectController

        ctrl = ProjectController()

        # 创建
        result = ctrl.create_project(name="控制器测试", description="测试用项目")
        assert result is not None
        assert result['name'] == "控制器测试"
        pid = result['id']

        # 查询
        proj = ctrl.get_project(pid)
        assert proj['name'] == "控制器测试"

        # 列表
        all_projects = ctrl.get_all_projects()
        assert len(all_projects) >= 1

        # 更新
        success = ctrl.update_project(pid, name="更新后名称", status="processing")
        assert success

        proj = ctrl.get_project(pid)
        assert proj['name'] == "更新后名称"

        # 删除
        success = ctrl.delete_project(pid)
        assert success

        proj = ctrl.get_project(pid)
        assert proj is None

    def test_material_controller_flow(self, temp_db):
        """MaterialController 完整流程"""
        from services.controllers.material_controller import MaterialController

        ctrl = MaterialController()

        # 创建
        result = ctrl.create_character(
            name="控制器角色",
            character_type="human",
            description="测试描述",
            appearance="黑发蓝眼",
        )
        assert result is not None
        assert result['name'] == "控制器角色"
        cid = result['id']

        # 查询
        char = ctrl.get_character(cid)
        assert char['appearance'] == "黑发蓝眼"

        # 列表
        all_chars = ctrl.get_all_characters()
        assert len(all_chars) >= 1

        # 更新
        success = ctrl.update_character(cid, name="更新角色名")
        assert success

        char = ctrl.get_character(cid)
        assert char['name'] == "更新角色名"

        # 搜索
        found = ctrl.search_characters("更新")
        assert len(found) >= 1

        # 统计
        stats = ctrl.get_statistics()
        assert stats['total'] >= 1

        # 软删除
        success = ctrl.delete_character(cid, soft=True)
        assert success

        # 软删除后不应出现在活跃列表
        all_chars = ctrl.get_all_characters(active_only=True)
        active_ids = [c['id'] for c in all_chars]
        assert cid not in active_ids
