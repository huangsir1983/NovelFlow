"""
涛割 - 图像生成服务
统一管理图像生成流程，支持多模型路由
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

from .base_provider import (
    BaseProvider,
    ProviderFactory,
    ImageGenerationRequest,
    GenerationResult,
)
from .model_router import ModelRouter, RoutingContext, SceneType, QualityLevel


@dataclass
class ImageGenTask:
    """图像生成任务"""
    id: str
    scene_id: Optional[int]
    prompt: str
    negative_prompt: str = ""
    style: str = "realistic"
    width: int = 1920
    height: int = 1080

    # 角色一致性
    character_refs: List[str] = field(default_factory=list)

    # 路由上下文
    scene_type: SceneType = SceneType.DIALOGUE
    quality_level: QualityLevel = QualityLevel.STANDARD

    # 状态
    status: str = "pending"  # pending, processing, completed, failed
    progress: float = 0.0
    result_path: Optional[str] = None
    result_url: Optional[str] = None
    error_message: Optional[str] = None

    # 成本
    estimated_cost: float = 0.0
    actual_cost: float = 0.0

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ImageGenService:
    """
    图像生成服务
    负责协调图像生成流程，支持：
    - 多模型智能路由
    - 批量生成
    - 角色一致性
    - 成本追踪
    """

    def __init__(
        self,
        router: ModelRouter = None,
        output_dir: str = "generated/images",
        max_concurrent: int = 3
    ):
        self.router = router or ModelRouter()
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent

        # 任务管理
        self._tasks: Dict[str, ImageGenTask] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # 回调
        self._progress_callbacks: List[Callable] = []

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

    def add_progress_callback(self, callback: Callable):
        """添加进度回调"""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable):
        """移除进度回调"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def _notify_progress(self, task: ImageGenTask):
        """通知进度更新"""
        for callback in self._progress_callbacks:
            try:
                callback(task)
            except Exception as e:
                print(f"进度回调失败: {e}")

    async def generate_single(
        self,
        prompt: str,
        scene_id: int = None,
        negative_prompt: str = "",
        style: str = "realistic",
        width: int = 1920,
        height: int = 1080,
        character_refs: List[str] = None,
        scene_type: SceneType = SceneType.DIALOGUE,
        quality_level: QualityLevel = QualityLevel.STANDARD,
        preferred_provider: str = None
    ) -> ImageGenTask:
        """
        生成单张图像

        Args:
            prompt: 图像描述
            scene_id: 关联场景ID
            negative_prompt: 负面提示词
            style: 风格
            width: 宽度
            height: 高度
            character_refs: 角色参考图
            scene_type: 场景类型
            quality_level: 质量等级
            preferred_provider: 偏好的Provider

        Returns:
            ImageGenTask: 生成任务
        """
        # 创建任务
        task = ImageGenTask(
            id=str(uuid.uuid4()),
            scene_id=scene_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            style=style,
            width=width,
            height=height,
            character_refs=character_refs or [],
            scene_type=scene_type,
            quality_level=quality_level,
        )

        self._tasks[task.id] = task

        # 执行生成
        await self._execute_generation(task, preferred_provider)

        return task

    async def generate_batch(
        self,
        tasks_data: List[Dict[str, Any]],
        quality_level: QualityLevel = QualityLevel.STANDARD,
        optimize_cost: bool = True
    ) -> List[ImageGenTask]:
        """
        批量生成图像

        Args:
            tasks_data: 任务数据列表，每项包含prompt等信息
            quality_level: 质量等级
            optimize_cost: 是否优化成本（按场景类型分组）

        Returns:
            List[ImageGenTask]: 生成任务列表
        """
        # 创建所有任务
        tasks = []
        for data in tasks_data:
            task = ImageGenTask(
                id=str(uuid.uuid4()),
                scene_id=data.get("scene_id"),
                prompt=data.get("prompt", ""),
                negative_prompt=data.get("negative_prompt", ""),
                style=data.get("style", "realistic"),
                width=data.get("width", 1920),
                height=data.get("height", 1080),
                character_refs=data.get("character_refs", []),
                scene_type=data.get("scene_type", SceneType.DIALOGUE),
                quality_level=quality_level,
            )
            tasks.append(task)
            self._tasks[task.id] = task

        # 并发执行
        await asyncio.gather(*[
            self._execute_generation(task)
            for task in tasks
        ])

        return tasks

    async def _execute_generation(
        self,
        task: ImageGenTask,
        preferred_provider: str = None
    ):
        """执行图像生成"""
        async with self._semaphore:
            task.status = "processing"
            task.progress = 10.0
            self._notify_progress(task)

            try:
                # 路由选择Provider
                routing_context = RoutingContext(
                    scene_type=task.scene_type,
                    quality_level=task.quality_level,
                    require_consistency=len(task.character_refs) > 0,
                    preferred_provider=preferred_provider,
                )

                routing_result = self.router.route(routing_context, "image")
                provider = routing_result.provider
                task.estimated_cost = routing_result.estimated_cost

                task.progress = 30.0
                self._notify_progress(task)

                # 构建请求
                request = ImageGenerationRequest(
                    prompt=task.prompt,
                    negative_prompt=task.negative_prompt,
                    width=task.width,
                    height=task.height,
                    style=task.style,
                    character_refs=task.character_refs,
                    scene_id=task.scene_id,
                )

                # 调用Provider生成
                result = await provider.generate_image(request)

                task.progress = 80.0
                self._notify_progress(task)

                if result.success:
                    # 下载/保存结果
                    if result.result_url:
                        local_path = await self._download_result(
                            result.result_url,
                            task.id
                        )
                        task.result_path = local_path
                        task.result_url = result.result_url
                    elif result.result_path:
                        task.result_path = result.result_path

                    task.status = "completed"
                    task.actual_cost = result.credits_used
                else:
                    task.status = "failed"
                    task.error_message = result.error_message

                task.progress = 100.0
                task.completed_at = datetime.now()

            except Exception as e:
                task.status = "failed"
                task.error_message = str(e)
                task.progress = 100.0

            self._notify_progress(task)

    async def _download_result(self, url: str, task_id: str) -> str:
        """下载生成结果到本地"""
        import aiohttp

        # 生成本地文件路径
        ext = ".png"
        if ".jpg" in url or ".jpeg" in url:
            ext = ".jpg"

        filename = f"{task_id}{ext}"
        local_path = os.path.join(self.output_dir, filename)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(local_path, "wb") as f:
                            f.write(content)
                        return local_path
        except Exception as e:
            print(f"下载图像失败: {e}")

        return url  # 下载失败时返回原URL

    def get_task(self, task_id: str) -> Optional[ImageGenTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[ImageGenTask]:
        """获取所有任务"""
        return list(self._tasks.values())

    def get_tasks_by_scene(self, scene_id: int) -> List[ImageGenTask]:
        """获取场景相关的任务"""
        return [t for t in self._tasks.values() if t.scene_id == scene_id]

    def get_completed_tasks(self) -> List[ImageGenTask]:
        """获取已完成的任务"""
        return [t for t in self._tasks.values() if t.status == "completed"]

    def get_total_cost(self) -> float:
        """获取总成本"""
        return sum(t.actual_cost for t in self._tasks.values())

    def clear_tasks(self):
        """清除所有任务"""
        self._tasks.clear()


# 全局实例
_image_gen_service: Optional[ImageGenService] = None


def get_image_gen_service() -> ImageGenService:
    """获取全局图像生成服务实例"""
    global _image_gen_service
    if _image_gen_service is None:
        from .model_router import get_model_router
        _image_gen_service = ImageGenService(router=get_model_router())
    return _image_gen_service
