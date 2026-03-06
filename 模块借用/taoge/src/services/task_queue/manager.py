"""
涛割 - 任务队列管理器
异步任务队列 + 持久化 + 进度通知
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue
import threading


class TaskPriority(Enum):
    """任务优先级"""
    URGENT = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    BACKGROUND = 9


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class TaskInfo:
    """任务信息"""
    id: str
    name: str
    task_type: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0

    # 输入输出
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    result_path: Optional[str] = None

    # 关联
    project_id: Optional[int] = None
    scene_id: Optional[int] = None

    # 重试
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None

    # 成本
    estimated_cost: float = 0.0
    actual_cost: float = 0.0

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 回调
    on_progress: Optional[Callable] = None
    on_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None

    def __lt__(self, other):
        """用于优先队列比较"""
        return self.priority.value < other.priority.value


class TaskQueueManager:
    """
    任务队列管理器
    支持异步执行、优先级队列、持久化、进度通知
    """

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._task_queue: PriorityQueue = PriorityQueue()
        self._tasks: Dict[str, TaskInfo] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._handlers: Dict[str, Callable] = {}
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()

        # 事件监听器
        self._listeners: List[Callable] = []

    def register_handler(self, task_type: str, handler: Callable):
        """
        注册任务处理器

        Args:
            task_type: 任务类型
            handler: 异步处理函数，签名: async def handler(task: TaskInfo) -> Dict
        """
        self._handlers[task_type] = handler

    def add_listener(self, listener: Callable):
        """添加事件监听器"""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable):
        """移除事件监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event: str, task: TaskInfo):
        """通知所有监听器"""
        for listener in self._listeners:
            try:
                listener(event, task)
            except Exception as e:
                print(f"监听器通知失败: {e}")

    def create_task(
        self,
        name: str,
        task_type: str,
        input_data: Dict[str, Any] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        project_id: int = None,
        scene_id: int = None,
        on_progress: Callable = None,
        on_complete: Callable = None,
        on_error: Callable = None
    ) -> str:
        """
        创建新任务

        Args:
            name: 任务名称
            task_type: 任务类型
            input_data: 输入数据
            priority: 优先级
            project_id: 关联项目ID
            scene_id: 关联场景ID
            on_progress: 进度回调
            on_complete: 完成回调
            on_error: 错误回调

        Returns:
            str: 任务ID
        """
        task_id = str(uuid.uuid4())

        task = TaskInfo(
            id=task_id,
            name=name,
            task_type=task_type,
            priority=priority,
            input_data=input_data or {},
            project_id=project_id,
            scene_id=scene_id,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )

        with self._lock:
            self._tasks[task_id] = task
            self._task_queue.put((priority.value, task_id, task))

        task.status = TaskStatus.QUEUED
        self._notify_listeners("task_created", task)

        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]

            # 如果正在运行，尝试取消
            if task_id in self._running_tasks:
                self._running_tasks[task_id].cancel()
                del self._running_tasks[task_id]

            task.status = TaskStatus.CANCELLED
            self._notify_listeners("task_cancelled", task)
            return True

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskInfo]:
        """获取所有任务"""
        return list(self._tasks.values())

    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskInfo]:
        """按状态获取任务"""
        return [t for t in self._tasks.values() if t.status == status]

    def get_pending_count(self) -> int:
        """获取等待中的任务数量"""
        return len([t for t in self._tasks.values()
                   if t.status in (TaskStatus.PENDING, TaskStatus.QUEUED)])

    def get_running_count(self) -> int:
        """获取运行中的任务数量"""
        return len(self._running_tasks)

    async def start(self):
        """启动任务处理器"""
        if self._is_running:
            return

        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """停止任务处理器"""
        self._is_running = False

        # 取消所有运行中的任务
        for task_id, task in list(self._running_tasks.items()):
            task.cancel()

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _worker_loop(self):
        """工作循环"""
        while self._is_running:
            # 检查是否可以开始新任务
            while (len(self._running_tasks) < self.max_concurrent and
                   not self._task_queue.empty()):

                try:
                    _, task_id, task = self._task_queue.get_nowait()

                    # 跳过已取消的任务
                    if task.status == TaskStatus.CANCELLED:
                        continue

                    # 启动任务
                    asyncio_task = asyncio.create_task(self._execute_task(task))
                    self._running_tasks[task_id] = asyncio_task

                except Exception as e:
                    print(f"启动任务失败: {e}")
                    break

            # 等待一段时间再检查
            await asyncio.sleep(0.1)

    async def _execute_task(self, task: TaskInfo):
        """执行任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self._notify_listeners("task_started", task)

        try:
            # 获取处理器
            handler = self._handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"未知的任务类型: {task.task_type}")

            # 创建进度回调包装器
            async def progress_callback(progress: float, message: str = ""):
                task.progress = progress
                if task.on_progress:
                    task.on_progress(task, progress, message)
                self._notify_listeners("task_progress", task)

            # 执行任务
            result = await handler(task, progress_callback)

            # 更新任务状态
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            task.output_data = result or {}
            task.completed_at = datetime.now()

            if task.on_complete:
                task.on_complete(task)

            self._notify_listeners("task_completed", task)

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            self._notify_listeners("task_cancelled", task)

        except Exception as e:
            task.error_message = str(e)

            # 检查是否可以重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.QUEUED
                self._task_queue.put((task.priority.value, task.id, task))
                self._notify_listeners("task_retry", task)
            else:
                task.status = TaskStatus.FAILED
                if task.on_error:
                    task.on_error(task, e)
                self._notify_listeners("task_failed", task)

        finally:
            # 从运行中列表移除
            if task.id in self._running_tasks:
                del self._running_tasks[task.id]

    def update_progress(self, task_id: str, progress: float, message: str = ""):
        """更新任务进度（供处理器调用）"""
        task = self._tasks.get(task_id)
        if task:
            task.progress = progress
            if task.on_progress:
                task.on_progress(task, progress, message)
            self._notify_listeners("task_progress", task)

    def clear_completed(self):
        """清除已完成的任务"""
        with self._lock:
            completed_ids = [
                task_id for task_id, task in self._tasks.items()
                if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED)
            ]
            for task_id in completed_ids:
                del self._tasks[task_id]


# 全局任务队列实例
_queue_instance: Optional[TaskQueueManager] = None


def get_task_queue(max_concurrent: int = 3) -> TaskQueueManager:
    """获取全局任务队列实例"""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = TaskQueueManager(max_concurrent)
    return _queue_instance
