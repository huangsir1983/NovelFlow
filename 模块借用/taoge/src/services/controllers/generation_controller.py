"""
涛割 - 生成控制器
负责图像/视频生成任务的调度和管理
"""

import asyncio
import os
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from database.session import session_scope
from database.models import Scene, Project, Task, SceneCharacter, Character
from services.generation.base_provider import (
    BaseProvider,
    ProviderFactory,
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)
from services.generation.model_router import ModelRouter, RoutingContext, SceneType, QualityLevel
from services.scene.prompt_generator import PromptGenerator, PromptContext
from config.settings import SettingsManager
from services.utils.frame_extractor import FrameExtractor


class GenerationTaskType(Enum):
    """生成任务类型"""
    IMAGE = "image"
    VIDEO = "video"
    IMAGE_TO_VIDEO = "i2v"


@dataclass
class GenerationTask:
    """生成任务"""
    task_id: str
    scene_id: int
    project_id: int
    task_type: GenerationTaskType
    provider_name: str
    request: Any  # ImageGenerationRequest 或 VideoGenerationRequest
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[GenerationResult] = None
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class GenerationWorker(QThread):
    """
    生成工作线程
    在后台执行异步生成任务
    """

    task_started = pyqtSignal(str)  # task_id
    task_progress = pyqtSignal(str, int)  # task_id, progress
    task_completed = pyqtSignal(str, object)  # task_id, GenerationResult
    task_failed = pyqtSignal(str, str)  # task_id, error_message

    def __init__(self, task: GenerationTask, provider: BaseProvider):
        super().__init__()
        self.task = task
        self.provider = provider
        self._is_cancelled = False

    def run(self):
        """执行生成任务"""
        self.task_started.emit(self.task.task_id)

        try:
            # 创建事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # 执行生成
                if self.task.task_type == GenerationTaskType.IMAGE:
                    result = loop.run_until_complete(
                        self.provider.generate_image(self.task.request)
                    )
                elif self.task.task_type == GenerationTaskType.VIDEO:
                    result = loop.run_until_complete(
                        self.provider.generate_video(self.task.request)
                    )
                elif self.task.task_type == GenerationTaskType.IMAGE_TO_VIDEO:
                    result = loop.run_until_complete(
                        self.provider.image_to_video(self.task.request)
                    )
                else:
                    raise ValueError(f"未知任务类型: {self.task.task_type}")

                # 如果是异步任务，等待完成
                if result.success and result.status == "processing" and result.task_id:
                    task_type = "video" if self.task.task_type != GenerationTaskType.IMAGE else "image"

                    # 轮询等待结果
                    if hasattr(self.provider, 'wait_for_result'):
                        result = loop.run_until_complete(
                            self.provider.wait_for_result(
                                result.task_id,
                                task_type=task_type,
                                timeout=300
                            )
                        )
                    else:
                        # 手动轮询
                        result = loop.run_until_complete(
                            self._poll_task_status(result.task_id, task_type)
                        )

                if result.success:
                    self.task_completed.emit(self.task.task_id, result)
                else:
                    self.task_failed.emit(self.task.task_id, result.error_message or "生成失败")

            finally:
                loop.close()

        except Exception as e:
            self.task_failed.emit(self.task.task_id, str(e))

    async def _poll_task_status(self, api_task_id: str, task_type: str,
                                 timeout: int = 300, interval: int = 5) -> GenerationResult:
        """轮询任务状态"""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._is_cancelled:
                return GenerationResult(
                    success=False,
                    error_message="任务已取消",
                    error_code="CANCELLED"
                )

            status = await self.provider.check_task_status(api_task_id, task_type)

            if status["status"] == "completed":
                return GenerationResult(
                    success=True,
                    result_url=status.get("result_url"),
                    task_id=api_task_id,
                    status="completed"
                )
            elif status["status"] == "failed":
                return GenerationResult(
                    success=False,
                    error_message=status.get("error", "任务失败"),
                    error_code="TASK_FAILED"
                )

            # 发送进度
            progress = status.get("progress", 50)
            self.task_progress.emit(self.task.task_id, progress)

            await asyncio.sleep(interval)

        return GenerationResult(
            success=False,
            error_message=f"任务超时 ({timeout}秒)",
            error_code="TIMEOUT"
        )

    def cancel(self):
        """取消任务"""
        self._is_cancelled = True


class GenerationController(QObject):
    """
    生成控制器
    管理图像/视频生成任务的调度、执行和状态跟踪
    """

    # 信号定义
    generation_started = pyqtSignal(int, str)  # scene_id, task_type
    generation_progress = pyqtSignal(int, str, int)  # scene_id, task_type, progress
    generation_completed = pyqtSignal(int, str, str)  # scene_id, task_type, result_path
    generation_failed = pyqtSignal(int, str, str)  # scene_id, task_type, error
    batch_progress = pyqtSignal(int, int, int)  # project_id, completed, total
    batch_video_scene_completed = pyqtSignal(int, int, int)  # scene_id, completed, total

    _instance: Optional['GenerationController'] = None

    def __init__(self):
        super().__init__()

        self._settings = SettingsManager()
        self._model_router = ModelRouter()
        self._prompt_generator = PromptGenerator()

        # 任务管理
        self._active_tasks: Dict[str, GenerationTask] = {}
        self._workers: Dict[str, GenerationWorker] = {}
        self._task_counter = 0

        # 并发控制
        self._max_concurrent = 3
        self._running_count = 0

    # ==================== Provider管理 ====================

    def _get_provider(self, provider_name: str) -> Optional[BaseProvider]:
        """获取Provider实例"""
        settings = self._settings.settings

        try:
            if provider_name == "vidu":
                return ProviderFactory.create(
                    "vidu",
                    api_key=settings.api.vidu_api_key
                )
            elif provider_name == "kling":
                return ProviderFactory.create(
                    "kling",
                    access_key=settings.api.kling_api_key,
                    secret_key=""  # 如果有secret_key配置
                )
            elif provider_name == "jimeng":
                return ProviderFactory.create(
                    "jimeng",
                    api_key=settings.api.jimeng_api_key,
                    secret_key=""
                )
            elif provider_name == "comfyui":
                from services.generation.open_source import ComfyUIProvider
                return ComfyUIProvider(
                    base_url=settings.api.comfyui_server_url
                )
            else:
                print(f"未知的Provider: {provider_name}")
                return None

        except Exception as e:
            print(f"创建Provider失败: {e}")
            return None

    def _select_provider(self, scene_data: Dict[str, Any],
                         task_type: GenerationTaskType) -> str:
        """
        智能选择Provider

        Args:
            scene_data: 场景数据
            task_type: 任务类型

        Returns:
            Provider名称
        """
        # 判断是否需要角色一致性
        gen_params = scene_data.get('generation_params') or {}
        consistency_mode = gen_params.get('consistency_mode', '关闭')
        require_consistency = consistency_mode != '关闭'

        # 构建路由上下文
        context = RoutingContext(
            scene_type=self._infer_scene_type(scene_data),
            quality_level=QualityLevel.STANDARD,
            require_first_last_frame=bool(
                scene_data.get('start_frame_path') or scene_data.get('end_frame_path')
            ),
            require_consistency=require_consistency
        )

        # 使用模型路由器选择
        provider_name = self._model_router.select_provider(context)

        # 检查Provider是否可用
        provider = self._get_provider(provider_name)
        if provider and provider.validate_credentials():
            return provider_name

        # 回退到默认Provider
        settings = self._settings.settings
        fallback_providers = ['vidu', 'kling', 'jimeng', 'comfyui']

        for name in fallback_providers:
            provider = self._get_provider(name)
            if provider and provider.validate_credentials():
                return name

        return 'vidu'  # 最终回退

    def _infer_scene_type(self, scene_data: Dict[str, Any]) -> SceneType:
        """从场景数据推断场景类型"""
        ai_tags = scene_data.get('ai_tags', {})
        subtitle = scene_data.get('subtitle_text', '')

        # 简单的场景类型推断
        if '特效' in str(ai_tags) or '爆炸' in subtitle or '魔法' in subtitle:
            return SceneType.VFX
        elif '打' in subtitle or '跑' in subtitle or '追' in subtitle:
            return SceneType.ACTION
        elif len(ai_tags.get('角色', [])) > 2:
            return SceneType.CROWD
        elif '说' in subtitle or '问' in subtitle or '答' in subtitle:
            return SceneType.DIALOGUE
        else:
            return SceneType.LANDSCAPE

    # ==================== 图像生成 ====================

    def generate_image(self, scene_id: int, provider_name: str = None,
                       prompt: str = None, asset_context: dict = None) -> str:
        """
        为场景生成图像

        Args:
            scene_id: 场景ID
            provider_name: 指定Provider（可选）
            prompt: 自定义Prompt（可选）
            asset_context: 资产上下文（可选，由 AssetController.assemble_generation_context 提供）

        Returns:
            任务ID
        """
        # 获取场景数据
        scene_data = self._get_scene_data(scene_id)
        if not scene_data:
            self.generation_failed.emit(scene_id, "image", "场景不存在")
            return ""

        # 选择Provider
        if not provider_name:
            provider_name = self._select_provider(scene_data, GenerationTaskType.IMAGE)

        provider = self._get_provider(provider_name)
        if not provider:
            self.generation_failed.emit(scene_id, "image", f"无法创建Provider: {provider_name}")
            return ""

        # 生成Prompt
        if not prompt:
            prompt = scene_data.get('image_prompt') or self._generate_image_prompt(scene_data)

        # 获取角色参考图
        character_refs = self._get_character_refs(scene_id)

        # 从 asset_context 补充参考图
        if asset_context:
            for c in asset_context.get('characters', []):
                character_refs.extend(c.get('ref_images', []))
                # 衍生角色的参考图也收集
                if c.get('ref_image'):
                    character_refs.append(c['ref_image'])

        gen_params = scene_data.get('generation_params') or {}
        consistency_mode = gen_params.get('consistency_mode', '关闭')
        consistency_strength = gen_params.get('consistency_strength', 0.8)
        maintain_consistency = consistency_mode != '关闭' and bool(character_refs)

        # 合并场景参考图与角色参考图
        all_refs = list(scene_data.get('reference_images', []))
        all_refs.extend(character_refs)
        if asset_context and asset_context.get('scene_bg', {}).get('ref_images'):
            all_refs.extend(asset_context['scene_bg']['ref_images'])

        # 创建请求
        settings = self._settings.settings
        request = ImageGenerationRequest(
            prompt=prompt,
            width=settings.export.video_width,
            height=settings.export.video_height,
            scene_id=scene_id,
            reference_images=all_refs,
            character_refs=character_refs,
            maintain_consistency=maintain_consistency,
        )

        # 创建任务
        task = self._create_task(
            scene_id=scene_id,
            project_id=scene_data.get('project_id', 0),
            task_type=GenerationTaskType.IMAGE,
            provider_name=provider_name,
            request=request
        )

        # 启动工作线程
        self._start_worker(task, provider)

        return task.task_id

    def _generate_image_prompt(self, scene_data: Dict[str, Any]) -> str:
        """生成图像Prompt"""
        context = PromptContext(
            scene_description=scene_data.get('subtitle_text', ''),
            scene_tags=scene_data.get('ai_tags', {}).get('场景', []),
            character_tags=scene_data.get('ai_tags', {}).get('角色', []),
            prop_tags=scene_data.get('ai_tags', {}).get('道具', []),
            effect_tags=scene_data.get('ai_tags', {}).get('特效', []),
        )
        return self._prompt_generator.generate_image_prompt(context)

    # ==================== 视频生成 ====================

    def generate_video(self, scene_id: int, provider_name: str = None,
                       prompt: str = None, use_i2v: bool = True,
                       asset_context: dict = None) -> str:
        """
        为场景生成视频

        Args:
            scene_id: 场景ID
            provider_name: 指定Provider（可选）
            prompt: 自定义Prompt（可选）
            use_i2v: 是否使用图生视频模式
            asset_context: 资产上下文（可选，包含角色/服装/场景参考图等）

        Returns:
            任务ID
        """
        scene_data = self._get_scene_data(scene_id)
        if not scene_data:
            self.generation_failed.emit(scene_id, "video", "场景不存在")
            return ""

        # 检查是否有图像（I2V模式需要）
        source_image = scene_data.get('generated_image_path')
        if use_i2v and not source_image:
            self.generation_failed.emit(scene_id, "video", "I2V模式需要先生成图像")
            return ""

        # 选择Provider
        task_type = GenerationTaskType.IMAGE_TO_VIDEO if use_i2v else GenerationTaskType.VIDEO
        if not provider_name:
            provider_name = self._select_provider(scene_data, task_type)

        provider = self._get_provider(provider_name)
        if not provider:
            self.generation_failed.emit(scene_id, "video", f"无法创建Provider: {provider_name}")
            return ""

        # 生成Prompt
        if not prompt:
            prompt = scene_data.get('video_prompt') or self._generate_video_prompt(scene_data)

        # 尾帧继承：如果启用了继承上一镜尾帧，自动解析起始帧
        resolved_start_frame = scene_data.get('start_frame_path')
        if scene_data.get('use_prev_end_frame') or (scene_data.get('generation_params') or {}).get('use_prev_end_frame'):
            inherited_frame = self._resolve_start_frame(scene_id, scene_data)
            if inherited_frame:
                resolved_start_frame = inherited_frame

        # 创建请求
        settings = self._settings.settings

        # 从 asset_context 收集角色参考图（供支持角色一致性的 Provider 使用）
        character_refs = []
        if asset_context:
            for c in asset_context.get('characters', []):
                character_refs.extend(c.get('ref_images', []))
                if c.get('ref_image'):
                    character_refs.append(c['ref_image'])

        request = VideoGenerationRequest(
            prompt=prompt,
            width=settings.export.video_width,
            height=settings.export.video_height,
            duration=min(scene_data.get('duration', 4.0), 10.0),
            fps=settings.export.video_fps,
            scene_id=scene_id,
            source_image=source_image if use_i2v else None,
            start_frame=resolved_start_frame,
            end_frame=scene_data.get('end_frame_path'),
            camera_motion=scene_data.get('camera_motion', 'static'),
            motion_intensity=scene_data.get('motion_intensity', 0.5),
            character_refs=character_refs,
        )

        # 创建任务
        task = self._create_task(
            scene_id=scene_id,
            project_id=scene_data.get('project_id', 0),
            task_type=task_type,
            provider_name=provider_name,
            request=request
        )

        # 启动工作线程
        self._start_worker(task, provider)

        return task.task_id

    def _generate_video_prompt(self, scene_data: Dict[str, Any]) -> str:
        """生成视频Prompt"""
        context = PromptContext(
            scene_description=scene_data.get('subtitle_text', ''),
            scene_tags=scene_data.get('ai_tags', {}).get('场景', []),
            character_tags=scene_data.get('ai_tags', {}).get('角色', []),
            camera_angle=scene_data.get('camera_motion', 'static'),
        )
        return self._prompt_generator.generate_video_prompt(context)

    # ==================== 批量生成 ====================

    def batch_generate_images(self, project_id: int,
                              scene_ids: List[int] = None) -> List[str]:
        """
        批量生成图像

        Args:
            project_id: 项目ID
            scene_ids: 指定场景ID列表（可选，默认所有pending场景）

        Returns:
            任务ID列表
        """
        if scene_ids is None:
            scenes = self._get_pending_scenes(project_id, "pending")
            scene_ids = [s['id'] for s in scenes]

        task_ids = []
        for scene_id in scene_ids:
            task_id = self.generate_image(scene_id)
            if task_id:
                task_ids.append(task_id)

        return task_ids

    def batch_generate_videos(self, project_id: int,
                              scene_ids: List[int] = None) -> List[str]:
        """
        批量串行生成视频（按 scene_index 顺序）

        每个视频生成完成后，自动提取最后一帧并保存到 Scene.end_frame_source，
        下一个场景自动继承。

        Args:
            project_id: 项目ID
            scene_ids: 指定场景ID列表（可选，默认所有image_generated场景）

        Returns:
            任务ID列表
        """
        if scene_ids is None:
            scenes = self._get_pending_scenes(project_id, "image_generated")
            scene_ids = [s['id'] for s in scenes]

        if not scene_ids:
            return []

        # 按 scene_index 排序
        ordered_ids = []
        with session_scope() as session:
            scenes_db = session.query(Scene).filter(
                Scene.id.in_(scene_ids)
            ).order_by(Scene.scene_index).all()
            ordered_ids = [s.id for s in scenes_db]

        if not ordered_ids:
            return []

        # 串行生成：将排序后的 ID 存储，由完成回调驱动下一个
        self._batch_queue = list(ordered_ids)
        self._batch_completed = 0
        self._batch_total = len(ordered_ids)
        self._batch_task_ids = []

        # 启动第一个
        self._start_next_batch_video()
        return self._batch_task_ids

    def _start_next_batch_video(self):
        """启动批量队列中的下一个视频生成"""
        if not hasattr(self, '_batch_queue') or not self._batch_queue:
            return

        scene_id = self._batch_queue.pop(0)
        task_id = self.generate_video(scene_id)
        if task_id:
            self._batch_task_ids.append(task_id)

    # ==================== 任务管理 ====================

    def _create_task(self, scene_id: int, project_id: int,
                     task_type: GenerationTaskType, provider_name: str,
                     request: Any) -> GenerationTask:
        """创建生成任务"""
        self._task_counter += 1
        task_id = f"gen_{self._task_counter}_{scene_id}_{task_type.value}"

        task = GenerationTask(
            task_id=task_id,
            scene_id=scene_id,
            project_id=project_id,
            task_type=task_type,
            provider_name=provider_name,
            request=request,
            status="pending"
        )

        self._active_tasks[task_id] = task
        return task

    def _start_worker(self, task: GenerationTask, provider: BaseProvider):
        """启动工作线程"""
        worker = GenerationWorker(task, provider)

        # 连接信号
        worker.task_started.connect(self._on_task_started)
        worker.task_progress.connect(self._on_task_progress)
        worker.task_completed.connect(self._on_task_completed)
        worker.task_failed.connect(self._on_task_failed)

        self._workers[task.task_id] = worker
        worker.start()

    def _on_task_started(self, task_id: str):
        """任务开始回调"""
        task = self._active_tasks.get(task_id)
        if task:
            task.status = "running"
            task.started_at = datetime.now()
            task_type = "image" if task.task_type == GenerationTaskType.IMAGE else "video"
            self.generation_started.emit(task.scene_id, task_type)

    def _on_task_progress(self, task_id: str, progress: int):
        """任务进度回调"""
        task = self._active_tasks.get(task_id)
        if task:
            task_type = "image" if task.task_type == GenerationTaskType.IMAGE else "video"
            self.generation_progress.emit(task.scene_id, task_type, progress)

    def _on_task_completed(self, task_id: str, result: GenerationResult):
        """任务完成回调"""
        task = self._active_tasks.get(task_id)
        if task:
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now()

            # 更新场景数据
            self._update_scene_result(task, result)

            task_type = "image" if task.task_type == GenerationTaskType.IMAGE else "video"
            result_path = result.result_path or result.result_url or ""
            self.generation_completed.emit(task.scene_id, task_type, result_path)

            # 串行批量视频：完成后提取尾帧并启动下一个
            if task.task_type in (GenerationTaskType.VIDEO, GenerationTaskType.IMAGE_TO_VIDEO) and result_path:
                self._auto_archive_last_frame(task.scene_id, task.project_id, result_path)
                if hasattr(self, '_batch_queue') and self._batch_queue:
                    self._batch_completed += 1
                    self.batch_video_scene_completed.emit(
                        task.scene_id, self._batch_completed, self._batch_total
                    )
                    self._start_next_batch_video()
                elif hasattr(self, '_batch_queue'):
                    # 批量全部完成
                    self._batch_completed += 1
                    self.batch_video_scene_completed.emit(
                        task.scene_id, self._batch_completed, self._batch_total
                    )

        # 清理
        self._cleanup_task(task_id)

    def _on_task_failed(self, task_id: str, error_message: str):
        """任务失败回调"""
        task = self._active_tasks.get(task_id)
        if task:
            task.status = "failed"
            task.completed_at = datetime.now()

            # 更新场景状态
            self._update_scene_error(task.scene_id, error_message)

            task_type = "image" if task.task_type == GenerationTaskType.IMAGE else "video"
            self.generation_failed.emit(task.scene_id, task_type, error_message)

        # 清理
        self._cleanup_task(task_id)

    def _cleanup_task(self, task_id: str):
        """清理任务资源"""
        if task_id in self._workers:
            worker = self._workers.pop(task_id)
            if worker.isRunning():
                worker.quit()
                worker.wait(1000)

        if task_id in self._active_tasks:
            del self._active_tasks[task_id]

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self._workers:
            self._workers[task_id].cancel()
            return True
        return False

    # ==================== 数据库操作 ====================

    def _get_scene_data(self, scene_id: int) -> Optional[Dict[str, Any]]:
        """获取场景数据"""
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if scene:
                    return scene.to_dict()
                return None
        except Exception as e:
            print(f"获取场景数据失败: {e}")
            return None

    def _get_character_refs(self, scene_id: int) -> List[str]:
        """获取场景关联角色的所有参考图路径"""
        refs = []
        try:
            with session_scope() as session:
                scene_chars = session.query(SceneCharacter).filter(
                    SceneCharacter.scene_id == scene_id
                ).all()
                for sc in scene_chars:
                    char = session.query(Character).get(sc.character_id)
                    if char and char.is_active:
                        # 优先使用主参考图
                        if char.main_reference_image:
                            refs.append(char.main_reference_image)
                        elif char.reference_images:
                            refs.append(char.reference_images[0])
        except Exception as e:
            print(f"获取角色参考图失败: {e}")
        return refs

    def _get_pending_scenes(self, project_id: int, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的场景列表"""
        try:
            with session_scope() as session:
                scenes = session.query(Scene).filter(
                    Scene.project_id == project_id,
                    Scene.status == status
                ).order_by(Scene.scene_index).all()
                return [s.to_dict() for s in scenes]
        except Exception as e:
            print(f"获取场景列表失败: {e}")
            return []

    def _update_scene_result(self, task: GenerationTask, result: GenerationResult):
        """更新场景生成结果"""
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == task.scene_id).first()
                if not scene:
                    return

                if task.task_type == GenerationTaskType.IMAGE:
                    scene.generated_image_path = result.result_path or result.result_url
                    scene.status = "image_generated"
                    scene.model_used = task.provider_name
                else:
                    scene.generated_video_path = result.result_path or result.result_url
                    scene.status = "video_generated"

                scene.error_message = None

        except Exception as e:
            print(f"更新场景结果失败: {e}")

    def _update_scene_error(self, scene_id: int, error_message: str):
        """更新场景错误信息"""
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if scene:
                    scene.status = "failed"
                    scene.error_message = error_message
        except Exception as e:
            print(f"更新场景错误失败: {e}")

    # ==================== 尾帧继承 ====================

    def _resolve_start_frame(self, scene_id: int, scene_data: Dict[str, Any]) -> Optional[str]:
        """
        解析起始帧（尾帧继承）

        检查上一个场景是否有可用的尾帧，按优先级：
        1. 上一场景的 end_frame_source（手动设置或提取的尾帧）
        2. 上一场景的 end_frame_path
        3. 从上一场景的 generated_video_path 提取最后一帧

        Args:
            scene_id: 当前场景 ID
            scene_data: 当前场景数据

        Returns:
            起始帧图片路径，无可用帧返回 None
        """
        prev_scene = self._get_previous_scene(scene_id)
        if not prev_scene:
            return None

        # 优先级 1: 手动设置的尾帧来源
        if prev_scene.get('end_frame_source') and os.path.exists(prev_scene['end_frame_source']):
            return prev_scene['end_frame_source']

        # 优先级 2: 尾帧路径
        if prev_scene.get('end_frame_path') and os.path.exists(prev_scene['end_frame_path']):
            return prev_scene['end_frame_path']

        # 优先级 3: 从视频中提取最后一帧
        video_path = prev_scene.get('generated_video_path')
        if video_path and os.path.exists(video_path):
            project_id = scene_data.get('project_id', 0)
            frames_dir = os.path.join('generated', str(project_id), 'frames')
            output_path = os.path.join(frames_dir, f"end_frame_scene_{prev_scene['id']}.png")

            extracted = FrameExtractor.extract_last_frame(video_path, output_path)
            if extracted:
                # 保存提取的尾帧路径到上一场景
                self._save_end_frame_source(prev_scene['id'], extracted)
                return extracted

        return None

    def _get_previous_scene(self, scene_id: int) -> Optional[Dict[str, Any]]:
        """获取同项目中上一个场景数据"""
        try:
            with session_scope() as session:
                current = session.query(Scene).filter(Scene.id == scene_id).first()
                if not current:
                    return None

                prev = session.query(Scene).filter(
                    Scene.project_id == current.project_id,
                    Scene.scene_index == current.scene_index - 1
                ).first()

                if prev:
                    return prev.to_dict()
                return None
        except Exception as e:
            print(f"获取上一场景失败: {e}")
            return None

    def _save_end_frame_source(self, scene_id: int, frame_path: str):
        """保存提取的尾帧路径到场景"""
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if scene:
                    scene.end_frame_source = frame_path
        except Exception as e:
            print(f"保存尾帧路径失败: {e}")

    def _auto_archive_last_frame(self, scene_id: int, project_id: int, video_path: str):
        """
        视频生成成功后自动提取最后一帧并存档。
        - 存储到 generated/last_frames/{project_id}/scene_{index}_last.png
        - 更新 Scene.end_frame_path
        - 如果下一镜 use_prev_end_frame == True，自动设置其 start_frame_path
        """
        if not video_path or not os.path.exists(video_path):
            return

        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if not scene:
                    return

                pid = project_id or scene.project_id or 0
                last_frames_dir = os.path.join('generated', 'last_frames', str(pid))
                os.makedirs(last_frames_dir, exist_ok=True)

                output_path = os.path.join(
                    last_frames_dir,
                    f"scene_{scene.scene_index}_last.png"
                )

                extracted = FrameExtractor.extract_last_frame(video_path, output_path)
                if not extracted:
                    return

                # 更新当前场景的 end_frame_path 和 end_frame_source
                scene.end_frame_path = extracted
                scene.end_frame_source = extracted
                print(f"[涛割] Last-Frame 存档: scene_id={scene_id}, path={extracted}")

                # 检查下一镜是否需要继承尾帧
                next_scene = session.query(Scene).filter(
                    Scene.project_id == scene.project_id,
                    Scene.scene_index == scene.scene_index + 1
                ).first()

                if next_scene:
                    gen_params = next_scene.generation_params or {}
                    if next_scene.use_prev_end_frame or gen_params.get('use_prev_end_frame'):
                        next_scene.start_frame_path = extracted
                        print(f"[涛割] 下一镜 scene_index={next_scene.scene_index} "
                              f"自动继承尾帧: {extracted}")

        except Exception as e:
            print(f"[涛割] Last-Frame 存档失败: {e}")


# 便捷函数
def get_generation_controller() -> GenerationController:
    """获取生成控制器单例"""
    return GenerationController()
