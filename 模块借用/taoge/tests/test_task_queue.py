"""
涛割 - TaskQueueManager 单元测试
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from services.task_queue.manager import (
    TaskQueueManager, TaskInfo, TaskStatus, TaskPriority
)


@pytest.fixture
def queue():
    """创建任务队列"""
    return TaskQueueManager(max_concurrent=2)


class TestTaskCreation:
    """任务创建测试"""

    def test_create_task(self, queue):
        task_id = queue.create_task(
            name="测试任务",
            task_type="image_gen",
            input_data={"prompt": "测试Prompt"}
        )

        assert task_id is not None
        assert len(task_id) > 0

    def test_task_has_correct_status(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")
        task = queue.get_task(task_id)

        assert task.status == TaskStatus.QUEUED

    def test_task_has_correct_type(self, queue):
        task_id = queue.create_task(name="任务", task_type="video_gen")
        task = queue.get_task(task_id)

        assert task.task_type == "video_gen"
        assert task.name == "任务"

    def test_task_priority(self, queue):
        task_id = queue.create_task(
            name="紧急任务",
            task_type="image_gen",
            priority=TaskPriority.URGENT
        )
        task = queue.get_task(task_id)

        assert task.priority == TaskPriority.URGENT

    def test_task_with_project_and_scene(self, queue):
        task_id = queue.create_task(
            name="任务",
            task_type="image_gen",
            project_id=1,
            scene_id=5
        )
        task = queue.get_task(task_id)

        assert task.project_id == 1
        assert task.scene_id == 5

    def test_multiple_tasks(self, queue):
        ids = [
            queue.create_task(name=f"任务{i}", task_type="image_gen")
            for i in range(5)
        ]

        assert len(set(ids)) == 5  # 所有ID应唯一


class TestTaskRetrieval:
    """任务查询测试"""

    def test_get_task(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")
        task = queue.get_task(task_id)

        assert task is not None
        assert task.id == task_id

    def test_get_nonexistent_task(self, queue):
        task = queue.get_task("nonexistent")
        assert task is None

    def test_get_all_tasks(self, queue):
        for i in range(3):
            queue.create_task(name=f"任务{i}", task_type="image_gen")

        tasks = queue.get_all_tasks()
        assert len(tasks) == 3

    def test_get_tasks_by_status(self, queue):
        queue.create_task(name="任务1", task_type="image_gen")
        queue.create_task(name="任务2", task_type="image_gen")

        queued_tasks = queue.get_tasks_by_status(TaskStatus.QUEUED)
        assert len(queued_tasks) == 2

        running_tasks = queue.get_tasks_by_status(TaskStatus.RUNNING)
        assert len(running_tasks) == 0


class TestTaskCancellation:
    """任务取消测试"""

    def test_cancel_task(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")
        success = queue.cancel_task(task_id)

        assert success
        task = queue.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED

    def test_cancel_nonexistent_task(self, queue):
        success = queue.cancel_task("nonexistent")
        assert not success


class TestTaskCounting:
    """任务计数测试"""

    def test_pending_count(self, queue):
        queue.create_task(name="任务1", task_type="image_gen")
        queue.create_task(name="任务2", task_type="image_gen")

        assert queue.get_pending_count() == 2

    def test_pending_count_after_cancel(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")
        queue.cancel_task(task_id)

        assert queue.get_pending_count() == 0

    def test_running_count_initial(self, queue):
        assert queue.get_running_count() == 0


class TestClearCompleted:
    """清除已完成任务测试"""

    def test_clear_completed(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")
        task = queue.get_task(task_id)
        task.status = TaskStatus.COMPLETED

        queue.clear_completed()

        assert queue.get_task(task_id) is None

    def test_clear_does_not_remove_pending(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")

        queue.clear_completed()

        assert queue.get_task(task_id) is not None

    def test_clear_removes_cancelled(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")
        queue.cancel_task(task_id)

        queue.clear_completed()

        assert queue.get_task(task_id) is None


class TestEventListeners:
    """事件监听器测试"""

    def test_add_listener(self, queue):
        events = []

        def listener(event, task):
            events.append(event)

        queue.add_listener(listener)
        queue.create_task(name="任务", task_type="image_gen")

        assert "task_created" in events

    def test_remove_listener(self, queue):
        events = []

        def listener(event, task):
            events.append(event)

        queue.add_listener(listener)
        queue.remove_listener(listener)
        queue.create_task(name="任务", task_type="image_gen")

        assert len(events) == 0

    def test_cancel_listener(self, queue):
        events = []

        def listener(event, task):
            events.append(event)

        queue.add_listener(listener)
        task_id = queue.create_task(name="任务", task_type="image_gen")
        queue.cancel_task(task_id)

        assert "task_cancelled" in events


class TestTaskHandlerRegistration:
    """任务处理器注册测试"""

    def test_register_handler(self, queue):
        async def handler(task, progress_cb):
            return {"result": "done"}

        queue.register_handler("image_gen", handler)
        assert "image_gen" in queue._handlers

    def test_register_multiple_handlers(self, queue):
        async def handler1(task, progress_cb):
            return {}

        async def handler2(task, progress_cb):
            return {}

        queue.register_handler("image_gen", handler1)
        queue.register_handler("video_gen", handler2)

        assert len(queue._handlers) == 2


class TestProgressUpdate:
    """进度更新测试"""

    def test_update_progress(self, queue):
        task_id = queue.create_task(name="任务", task_type="image_gen")
        queue.update_progress(task_id, 50.0, "进行中")

        task = queue.get_task(task_id)
        assert task.progress == 50.0

    def test_update_nonexistent_progress(self, queue):
        # 不应抛出异常
        queue.update_progress("nonexistent", 50.0)


class TestTaskInfoComparison:
    """TaskInfo比较测试"""

    def test_priority_comparison(self):
        task1 = TaskInfo(id="1", name="紧急", task_type="test", priority=TaskPriority.URGENT)
        task2 = TaskInfo(id="2", name="普通", task_type="test", priority=TaskPriority.NORMAL)

        assert task1 < task2  # URGENT (1) < NORMAL (5)

    def test_task_defaults(self):
        task = TaskInfo(id="1", name="测试", task_type="test")

        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
        assert task.retry_count == 0
        assert task.max_retries == 3


@pytest.mark.asyncio
class TestAsyncExecution:
    """异步执行测试"""

    async def test_start_and_stop(self):
        queue = TaskQueueManager(max_concurrent=1)
        await queue.start()
        assert queue._is_running

        await queue.stop()
        assert not queue._is_running

    async def test_execute_task(self):
        queue = TaskQueueManager(max_concurrent=1)

        results = []

        async def handler(task, progress_cb):
            await progress_cb(50.0, "处理中")
            results.append(task.name)
            return {"done": True}

        queue.register_handler("test", handler)
        queue.create_task(name="测试任务", task_type="test")

        await queue.start()
        await asyncio.sleep(0.5)  # 等待执行
        await queue.stop()

        assert "测试任务" in results
