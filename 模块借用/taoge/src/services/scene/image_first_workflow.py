"""
涛割 - 先图后视频工作流
实现精品短剧的标准化生成流程：
1. 剧本/SRT → 场景拆分
2. 场景 → 图像生成（支持多宫格控图、角色一致性）
3. 图像确认 → 视频生成（I2V）
4. 视频合成 → 导出
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from datetime import datetime

from .processor import SceneProcessor, SceneGroup
from .prompt_generator import PromptGenerator, PromptContext
from ..generation.model_router import (
    ModelRouter,
    RoutingContext,
    SceneType,
    QualityLevel,
    get_model_router,
)
from ..generation.base_provider import (
    ImageGenerationRequest,
    VideoGenerationRequest,
    GenerationResult,
)


class WorkflowStage(Enum):
    """工作流阶段"""
    INIT = "init"  # 初始化
    SCENE_SPLIT = "scene_split"  # 场景拆分
    IMAGE_GEN = "image_gen"  # 图像生成
    IMAGE_REVIEW = "image_review"  # 图像审核
    VIDEO_GEN = "video_gen"  # 视频生成
    VIDEO_REVIEW = "video_review"  # 视频审核
    EXPORT = "export"  # 导出
    COMPLETED = "completed"  # 完成


class SceneStatus(Enum):
    """场景状态"""
    PENDING = "pending"  # 待处理
    IMAGE_GENERATING = "image_generating"  # 图像生成中
    IMAGE_READY = "image_ready"  # 图像就绪
    IMAGE_APPROVED = "image_approved"  # 图像已确认
    VIDEO_GENERATING = "video_generating"  # 视频生成中
    VIDEO_READY = "video_ready"  # 视频就绪
    VIDEO_APPROVED = "video_approved"  # 视频已确认
    FAILED = "failed"  # 失败


@dataclass
class SceneWorkItem:
    """场景工作项"""
    id: int
    scene_group: SceneGroup
    status: SceneStatus = SceneStatus.PENDING

    # Prompt
    image_prompt: str = ""
    image_negative_prompt: str = ""
    video_prompt: str = ""

    # 生成参数
    scene_type: SceneType = SceneType.DIALOGUE
    style: str = "realistic"
    camera_motion: str = "static"
    motion_intensity: float = 0.5

    # 角色一致性
    character_refs: List[str] = field(default_factory=list)

    # 首尾帧控制
    start_frame_path: Optional[str] = None
    end_frame_path: Optional[str] = None

    # 生成结果
    image_paths: List[str] = field(default_factory=list)
    selected_image_index: int = 0
    video_path: Optional[str] = None

    # 成本
    image_cost: float = 0.0
    video_cost: float = 0.0

    # 错误信息
    error_message: Optional[str] = None

    @property
    def selected_image(self) -> Optional[str]:
        """获取选中的图像"""
        if self.image_paths and 0 <= self.selected_image_index < len(self.image_paths):
            return self.image_paths[self.selected_image_index]
        return None

    @property
    def total_cost(self) -> float:
        """获取总成本"""
        return self.image_cost + self.video_cost


@dataclass
class WorkflowState:
    """工作流状态"""
    project_id: int
    stage: WorkflowStage = WorkflowStage.INIT
    scenes: List[SceneWorkItem] = field(default_factory=list)

    # 全局设置
    quality_level: QualityLevel = QualityLevel.STANDARD
    default_style: str = "realistic"
    maintain_consistency: bool = True

    # 角色库
    character_library: Dict[str, str] = field(default_factory=dict)

    # 进度
    total_scenes: int = 0
    completed_scenes: int = 0

    # 成本
    total_estimated_cost: float = 0.0
    total_actual_cost: float = 0.0

    # 时间
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def progress(self) -> float:
        """获取总进度"""
        if self.total_scenes == 0:
            return 0.0
        return (self.completed_scenes / self.total_scenes) * 100


class ImageFirstWorkflow:
    """
    先图后视频工作流
    实现精品短剧的标准化生成流程
    """

    def __init__(
        self,
        router: ModelRouter = None,
        scene_processor: SceneProcessor = None,
        prompt_generator: PromptGenerator = None
    ):
        self.router = router or get_model_router()
        self.scene_processor = scene_processor or SceneProcessor()
        self.prompt_generator = prompt_generator or PromptGenerator()

        # 当前工作流状态
        self._state: Optional[WorkflowState] = None

        # 事件回调
        self._callbacks: Dict[str, List[Callable]] = {
            "stage_changed": [],
            "scene_updated": [],
            "progress_updated": [],
            "error": [],
        }

    def on(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def off(self, event: str, callback: Callable):
        """移除事件回调"""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def _emit(self, event: str, *args, **kwargs):
        """触发事件"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"事件回调失败 [{event}]: {e}")

    @property
    def state(self) -> Optional[WorkflowState]:
        """获取当前状态"""
        return self._state

    def initialize(
        self,
        project_id: int,
        scene_groups: List[SceneGroup],
        quality_level: QualityLevel = QualityLevel.STANDARD,
        default_style: str = "realistic",
        character_library: Dict[str, str] = None
    ) -> WorkflowState:
        """
        初始化工作流

        Args:
            project_id: 项目ID
            scene_groups: 场景分组列表
            quality_level: 质量等级
            default_style: 默认风格
            character_library: 角色库 {角色名: 参考图路径}

        Returns:
            WorkflowState: 工作流状态
        """
        # 创建场景工作项
        scenes = []
        for i, group in enumerate(scene_groups):
            # 分析场景类型
            scene_type = self._analyze_scene_type(group)

            # 生成Prompt
            context = PromptContext(
                scene_tags=group.ai_tags.get("场景", []),
                character_tags=group.ai_tags.get("角色", []),
                prop_tags=group.ai_tags.get("道具", []),
                effect_tags=group.ai_tags.get("特效", []),
                subtitle_text=group.full_text,
                style=default_style,
            )

            prompt_result = self.prompt_generator.generate_image_prompt(context)

            # 获取角色参考图
            char_refs = []
            if character_library:
                for char_name in group.ai_tags.get("角色", []):
                    if char_name in character_library:
                        char_refs.append(character_library[char_name])

            scene_item = SceneWorkItem(
                id=i,
                scene_group=group,
                scene_type=scene_type,
                style=default_style,
                image_prompt=prompt_result["prompt"],
                image_negative_prompt=prompt_result["negative_prompt"],
                character_refs=char_refs,
            )
            scenes.append(scene_item)

        # 创建工作流状态
        self._state = WorkflowState(
            project_id=project_id,
            stage=WorkflowStage.SCENE_SPLIT,
            scenes=scenes,
            quality_level=quality_level,
            default_style=default_style,
            maintain_consistency=bool(character_library),
            character_library=character_library or {},
            total_scenes=len(scenes),
            started_at=datetime.now(),
        )

        # 估算成本
        self._estimate_total_cost()

        self._emit("stage_changed", self._state.stage)
        return self._state

    def _analyze_scene_type(self, group: SceneGroup) -> SceneType:
        """分析场景类型"""
        text = group.full_text.lower()
        tags = group.ai_tags

        # 根据标签和文本内容判断场景类型
        action_keywords = ["打", "跑", "跳", "追", "战斗", "冲", "逃"]
        landscape_keywords = ["风景", "远景", "全景", "天空", "山", "海"]
        portrait_keywords = ["特写", "近景", "表情", "眼神"]
        crowd_keywords = ["人群", "众人", "大家", "所有人"]
        vfx_keywords = ["爆炸", "魔法", "特效", "光芒", "闪电"]

        # 检查特效标签
        if tags.get("特效"):
            return SceneType.VFX

        # 检查关键词
        for keyword in action_keywords:
            if keyword in text:
                return SceneType.ACTION

        for keyword in vfx_keywords:
            if keyword in text:
                return SceneType.VFX

        for keyword in landscape_keywords:
            if keyword in text:
                return SceneType.LANDSCAPE

        for keyword in portrait_keywords:
            if keyword in text:
                return SceneType.PORTRAIT

        for keyword in crowd_keywords:
            if keyword in text:
                return SceneType.CROWD

        # 默认为对话场景
        return SceneType.DIALOGUE

    def _estimate_total_cost(self):
        """估算总成本"""
        if not self._state:
            return

        total = 0.0
        for scene in self._state.scenes:
            # 估算图像成本
            routing_ctx = RoutingContext(
                scene_type=scene.scene_type,
                quality_level=self._state.quality_level,
                require_consistency=len(scene.character_refs) > 0,
            )
            result = self.router.route(routing_ctx, "image")
            image_cost = result.estimated_cost

            # 估算视频成本
            result = self.router.route(routing_ctx, "video")
            video_cost = result.estimated_cost

            total += image_cost + video_cost

        self._state.total_estimated_cost = total

    async def generate_images(
        self,
        scene_indices: List[int] = None,
        num_variants: int = 1
    ) -> List[SceneWorkItem]:
        """
        生成图像

        Args:
            scene_indices: 要生成的场景索引，None表示全部
            num_variants: 每个场景生成的变体数量

        Returns:
            List[SceneWorkItem]: 更新后的场景列表
        """
        if not self._state:
            raise ValueError("工作流未初始化")

        self._state.stage = WorkflowStage.IMAGE_GEN
        self._emit("stage_changed", self._state.stage)

        # 确定要处理的场景
        if scene_indices is None:
            scenes_to_process = self._state.scenes
        else:
            scenes_to_process = [
                self._state.scenes[i]
                for i in scene_indices
                if 0 <= i < len(self._state.scenes)
            ]

        # 并发生成图像
        tasks = []
        for scene in scenes_to_process:
            task = self._generate_scene_image(scene, num_variants)
            tasks.append(task)

        await asyncio.gather(*tasks)

        # 更新阶段
        all_ready = all(
            s.status in (SceneStatus.IMAGE_READY, SceneStatus.IMAGE_APPROVED)
            for s in self._state.scenes
        )
        if all_ready:
            self._state.stage = WorkflowStage.IMAGE_REVIEW

        self._emit("stage_changed", self._state.stage)
        return scenes_to_process

    async def _generate_scene_image(
        self,
        scene: SceneWorkItem,
        num_variants: int = 1
    ):
        """生成单个场景的图像"""
        scene.status = SceneStatus.IMAGE_GENERATING
        self._emit("scene_updated", scene)

        try:
            # 路由选择Provider
            routing_ctx = RoutingContext(
                scene_type=scene.scene_type,
                quality_level=self._state.quality_level,
                require_consistency=len(scene.character_refs) > 0,
            )
            routing_result = self.router.route(routing_ctx, "image")
            provider = routing_result.provider

            # 构建请求
            request = ImageGenerationRequest(
                prompt=scene.image_prompt,
                negative_prompt=scene.image_negative_prompt,
                style=scene.style,
                character_refs=scene.character_refs,
                num_images=num_variants,
                scene_id=scene.id,
            )

            # 生成图像
            result = await provider.generate_image(request)

            if result.success:
                # 保存结果
                if result.result_url:
                    scene.image_paths = [result.result_url]
                elif result.result_path:
                    scene.image_paths = [result.result_path]

                scene.image_cost = result.credits_used
                scene.status = SceneStatus.IMAGE_READY
                self._state.total_actual_cost += result.credits_used
            else:
                scene.status = SceneStatus.FAILED
                scene.error_message = result.error_message

        except Exception as e:
            scene.status = SceneStatus.FAILED
            scene.error_message = str(e)
            self._emit("error", scene, e)

        self._emit("scene_updated", scene)
        self._update_progress()

    def approve_image(self, scene_index: int, selected_variant: int = 0):
        """
        确认场景图像

        Args:
            scene_index: 场景索引
            selected_variant: 选中的变体索引
        """
        if not self._state or scene_index >= len(self._state.scenes):
            return

        scene = self._state.scenes[scene_index]
        scene.selected_image_index = selected_variant
        scene.status = SceneStatus.IMAGE_APPROVED
        self._emit("scene_updated", scene)

        # 检查是否所有图像都已确认
        all_approved = all(
            s.status == SceneStatus.IMAGE_APPROVED
            for s in self._state.scenes
        )
        if all_approved:
            self._state.stage = WorkflowStage.VIDEO_GEN
            self._emit("stage_changed", self._state.stage)

    async def generate_videos(
        self,
        scene_indices: List[int] = None
    ) -> List[SceneWorkItem]:
        """
        串行生成视频（I2V），按 scene_index 顺序。
        每个视频完成后自动提取尾帧供下一个场景继承。

        Args:
            scene_indices: 要生成的场景索引，None表示全部已确认的

        Returns:
            List[SceneWorkItem]: 更新后的场景列表
        """
        if not self._state:
            raise ValueError("工作流未初始化")

        self._state.stage = WorkflowStage.VIDEO_GEN
        self._emit("stage_changed", self._state.stage)

        # 确定要处理的场景（只处理图像已确认的）
        if scene_indices is None:
            scenes_to_process = [
                s for s in self._state.scenes
                if s.status == SceneStatus.IMAGE_APPROVED
            ]
        else:
            scenes_to_process = [
                self._state.scenes[i]
                for i in scene_indices
                if (0 <= i < len(self._state.scenes) and
                    self._state.scenes[i].status == SceneStatus.IMAGE_APPROVED)
            ]

        # 串行生成视频（按顺序，支持尾帧继承）
        for i, scene in enumerate(scenes_to_process):
            # 检查是否需要从上一个场景继承尾帧
            if i > 0 and scene.start_frame_path is None:
                prev = scenes_to_process[i - 1]
                if prev.video_path and prev.status == SceneStatus.VIDEO_READY:
                    try:
                        import os
                        from services.utils.frame_extractor import FrameExtractor
                        frames_dir = os.path.join(
                            'generated', str(self._state.project_id), 'frames'
                        )
                        os.makedirs(frames_dir, exist_ok=True)
                        output = os.path.join(
                            frames_dir, f"end_frame_{prev.id}.png"
                        )
                        extracted = FrameExtractor.extract_last_frame(
                            prev.video_path, output
                        )
                        if extracted:
                            scene.start_frame_path = extracted
                    except Exception as e:
                        print(f"尾帧继承失败: {e}")

            await self._generate_scene_video(scene)

        # 更新阶段
        all_ready = all(
            s.status in (SceneStatus.VIDEO_READY, SceneStatus.VIDEO_APPROVED)
            for s in self._state.scenes
            if s.status != SceneStatus.FAILED
        )
        if all_ready:
            self._state.stage = WorkflowStage.VIDEO_REVIEW

        self._emit("stage_changed", self._state.stage)
        return scenes_to_process

    async def _generate_scene_video(self, scene: SceneWorkItem):
        """生成单个场景的视频"""
        if not scene.selected_image:
            scene.status = SceneStatus.FAILED
            scene.error_message = "未选择图像"
            self._emit("scene_updated", scene)
            return

        scene.status = SceneStatus.VIDEO_GENERATING
        self._emit("scene_updated", scene)

        try:
            # 路由选择Provider
            routing_ctx = RoutingContext(
                scene_type=scene.scene_type,
                quality_level=self._state.quality_level,
                require_first_last_frame=bool(scene.end_frame_path),
            )
            routing_result = self.router.route(routing_ctx, "video")
            provider = routing_result.provider

            # 生成视频Prompt
            context = PromptContext(
                scene_tags=scene.scene_group.ai_tags.get("场景", []),
                character_tags=scene.scene_group.ai_tags.get("角色", []),
                subtitle_text=scene.scene_group.full_text,
            )
            video_prompt_result = self.prompt_generator.generate_video_prompt(
                context,
                camera_motion=scene.camera_motion,
                duration=scene.scene_group.duration,
            )
            scene.video_prompt = video_prompt_result["prompt"]

            # 构建请求
            request = VideoGenerationRequest(
                prompt=scene.video_prompt,
                source_image=scene.selected_image,
                duration=min(scene.scene_group.duration, 6.0),  # 限制最大时长
                camera_motion=scene.camera_motion,
                motion_intensity=scene.motion_intensity,
                start_frame=scene.start_frame_path,
                end_frame=scene.end_frame_path,
                scene_id=scene.id,
            )

            # 生成视频
            result = await provider.image_to_video(request)

            if result.success:
                # 如果是异步任务，需要轮询状态
                if result.status == "processing" and result.task_id:
                    result = await self._poll_task_status(provider, result.task_id)

                if result.success:
                    scene.video_path = result.result_path or result.result_url
                    scene.video_cost = result.credits_used
                    scene.status = SceneStatus.VIDEO_READY
                    self._state.total_actual_cost += result.credits_used
                else:
                    scene.status = SceneStatus.FAILED
                    scene.error_message = result.error_message
            else:
                scene.status = SceneStatus.FAILED
                scene.error_message = result.error_message

        except Exception as e:
            scene.status = SceneStatus.FAILED
            scene.error_message = str(e)
            self._emit("error", scene, e)

        self._emit("scene_updated", scene)
        self._update_progress()

    async def _poll_task_status(
        self,
        provider,
        task_id: str,
        max_attempts: int = 60,
        interval: float = 5.0
    ) -> GenerationResult:
        """轮询任务状态"""
        for _ in range(max_attempts):
            status = await provider.check_task_status(task_id)

            if status.get("status") == "completed":
                return GenerationResult(
                    success=True,
                    result_url=status.get("result_url"),
                    task_id=task_id,
                )
            elif status.get("status") == "failed":
                return GenerationResult(
                    success=False,
                    error_message=status.get("error", "任务失败"),
                    task_id=task_id,
                )

            await asyncio.sleep(interval)

        return GenerationResult(
            success=False,
            error_message="任务超时",
            task_id=task_id,
        )

    def approve_video(self, scene_index: int):
        """确认场景视频"""
        if not self._state or scene_index >= len(self._state.scenes):
            return

        scene = self._state.scenes[scene_index]
        scene.status = SceneStatus.VIDEO_APPROVED
        self._emit("scene_updated", scene)

        # 检查是否所有视频都已确认
        all_approved = all(
            s.status == SceneStatus.VIDEO_APPROVED
            for s in self._state.scenes
            if s.status != SceneStatus.FAILED
        )
        if all_approved:
            self._state.stage = WorkflowStage.EXPORT
            self._emit("stage_changed", self._state.stage)

    def _update_progress(self):
        """更新进度"""
        if not self._state:
            return

        completed = sum(
            1 for s in self._state.scenes
            if s.status in (
                SceneStatus.IMAGE_APPROVED,
                SceneStatus.VIDEO_READY,
                SceneStatus.VIDEO_APPROVED,
            )
        )
        self._state.completed_scenes = completed
        self._emit("progress_updated", self._state.progress)

    def update_scene_prompt(self, scene_index: int, prompt: str, negative_prompt: str = None):
        """更新场景Prompt"""
        if not self._state or scene_index >= len(self._state.scenes):
            return

        scene = self._state.scenes[scene_index]
        scene.image_prompt = prompt
        if negative_prompt is not None:
            scene.image_negative_prompt = negative_prompt
        self._emit("scene_updated", scene)

    def update_scene_settings(
        self,
        scene_index: int,
        style: str = None,
        camera_motion: str = None,
        motion_intensity: float = None,
        character_refs: List[str] = None
    ):
        """更新场景设置"""
        if not self._state or scene_index >= len(self._state.scenes):
            return

        scene = self._state.scenes[scene_index]
        if style is not None:
            scene.style = style
        if camera_motion is not None:
            scene.camera_motion = camera_motion
        if motion_intensity is not None:
            scene.motion_intensity = motion_intensity
        if character_refs is not None:
            scene.character_refs = character_refs
        self._emit("scene_updated", scene)

    def set_first_last_frame(
        self,
        scene_index: int,
        start_frame: str = None,
        end_frame: str = None
    ):
        """设置首尾帧"""
        if not self._state or scene_index >= len(self._state.scenes):
            return

        scene = self._state.scenes[scene_index]
        if start_frame is not None:
            scene.start_frame_path = start_frame
        if end_frame is not None:
            scene.end_frame_path = end_frame
        self._emit("scene_updated", scene)

    def get_export_data(self) -> Dict[str, Any]:
        """获取导出数据"""
        if not self._state:
            return {}

        return {
            "project_id": self._state.project_id,
            "scenes": [
                {
                    "id": s.id,
                    "start_time": s.scene_group.start_time,
                    "end_time": s.scene_group.end_time,
                    "duration": s.scene_group.duration,
                    "text": s.scene_group.full_text,
                    "image_path": s.selected_image,
                    "video_path": s.video_path,
                    "status": s.status.value,
                }
                for s in self._state.scenes
            ],
            "total_cost": self._state.total_actual_cost,
            "quality_level": self._state.quality_level.value,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于保存状态）"""
        if not self._state:
            return {}

        return {
            "project_id": self._state.project_id,
            "stage": self._state.stage.value,
            "quality_level": self._state.quality_level.value,
            "default_style": self._state.default_style,
            "character_library": self._state.character_library,
            "total_estimated_cost": self._state.total_estimated_cost,
            "total_actual_cost": self._state.total_actual_cost,
            "scenes": [
                {
                    "id": s.id,
                    "status": s.status.value,
                    "scene_type": s.scene_type.value,
                    "style": s.style,
                    "image_prompt": s.image_prompt,
                    "image_negative_prompt": s.image_negative_prompt,
                    "video_prompt": s.video_prompt,
                    "camera_motion": s.camera_motion,
                    "motion_intensity": s.motion_intensity,
                    "character_refs": s.character_refs,
                    "image_paths": s.image_paths,
                    "selected_image_index": s.selected_image_index,
                    "video_path": s.video_path,
                    "image_cost": s.image_cost,
                    "video_cost": s.video_cost,
                }
                for s in self._state.scenes
            ],
        }
