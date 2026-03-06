"""
涛割 - 5角度批量生成服务（并行模式）
使用 RunningHub 的「角色视角切换」API，从单张图片并行生成5个固定角度的图片。
所有API请求同时提交，统一轮询，按完成顺序下载，按索引顺序发射信号。
"""

import os
import time
from typing import List, Optional, Dict
from dataclasses import dataclass, field

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from services.runninghub_client import RunningHubClient, RunningHubError
from services.view_angle_service import (
    VIEW_ANGLE_APP_ID,
    IMAGE_NODE_ID, IMAGE_FIELD_NAME,
    PROMPT_NODE_ID, PROMPT_FIELD_NAME,
)

# ── 5个固定角度 ──
ANGLE_LABELS = ["正前", "正左", "正右", "正后", "上半身"]
ANGLE_PROMPTS = [
    "<sks> front view eye-level shot medium shot",
    "<sks> left side view eye-level shot medium shot",
    "<sks> right side view eye-level shot medium shot",
    "<sks> back view eye-level shot medium shot",
    "<sks> front view eye-level shot close-up",
]

# 状态中文映射
_STATUS_LABEL = {
    'QUEUED':  '排队中',
    'RUNNING': '运行中',
    'SUCCESS': '已完成',
    'FAILED':  '失败',
}


# ── 队列管理数据结构 ──

@dataclass
class AngleTaskStatus:
    """单个角度任务的状态"""
    index: int
    label: str
    prompt: str
    task_id: str = ''
    status: str = 'PENDING'       # PENDING / SUBMITTED / QUEUED / RUNNING / SUCCESS / FAILED / DOWNLOADING
    local_path: str = ''
    error: str = ''
    elapsed: float = 0.0


@dataclass
class BatchJobStatus:
    """整批任务的状态"""
    job_id: str = ''
    source_image: str = ''
    total: int = 5
    completed: int = 0
    failed: int = 0
    status: str = 'PENDING'       # PENDING / UPLOADING / SUBMITTED / POLLING / DONE / ERROR
    angle_tasks: List[AngleTaskStatus] = field(default_factory=list)
    error: str = ''
    start_time: float = 0.0

    def to_dict(self) -> dict:
        return {
            'job_id': self.job_id,
            'source_image': self.source_image,
            'total': self.total,
            'completed': self.completed,
            'failed': self.failed,
            'status': self.status,
            'error': self.error,
            'elapsed': time.time() - self.start_time if self.start_time else 0,
            'angles': [
                {
                    'index': t.index,
                    'label': t.label,
                    'status': t.status,
                    'local_path': t.local_path,
                    'error': t.error,
                    'elapsed': t.elapsed,
                }
                for t in self.angle_tasks
            ],
        }


class MultiAngleJobQueue(QObject):
    """多视角生成任务队列管理器（预留接口，供未来侧面板使用）

    信号:
        job_added(str)           — 新任务加入队列 (job_id)
        job_updated(str, dict)   — 任务状态更新 (job_id, status_dict)
        job_completed(str, bool) — 任务完成 (job_id, success)
        queue_changed()          — 队列变化（增删）
    """
    job_added = pyqtSignal(str)
    job_updated = pyqtSignal(str, dict)
    job_completed = pyqtSignal(str, bool)
    queue_changed = pyqtSignal()

    _instance = None

    @classmethod
    def instance(cls) -> 'MultiAngleJobQueue':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: Dict[str, BatchJobStatus] = {}

    def add_job(self, job: BatchJobStatus):
        self._jobs[job.job_id] = job
        self.job_added.emit(job.job_id)
        self.queue_changed.emit()

    def update_job(self, job_id: str, status: BatchJobStatus):
        self._jobs[job_id] = status
        self.job_updated.emit(job_id, status.to_dict())

    def complete_job(self, job_id: str, success: bool):
        if job_id in self._jobs:
            self._jobs[job_id].status = 'DONE' if success else 'ERROR'
        self.job_completed.emit(job_id, success)
        self.queue_changed.emit()

    def get_job(self, job_id: str) -> Optional[BatchJobStatus]:
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> List[dict]:
        return [j.to_dict() for j in self._jobs.values()]

    def get_active_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status not in ('DONE', 'ERROR'))

    def remove_completed(self):
        to_remove = [k for k, v in self._jobs.items() if v.status in ('DONE', 'ERROR')]
        for k in to_remove:
            del self._jobs[k]
        if to_remove:
            self.queue_changed.emit()


class MultiAngleBatchWorker(QThread):
    """5角度并行批量生成 Worker

    流程：上传1次 → 并行提交5个任务 → 统一轮询 → 按完成顺序下载 → 按索引顺序发射信号
    """

    angle_completed = pyqtSignal(int, str)         # (角度索引0-4, 本地路径)
    all_completed = pyqtSignal(bool, list, str)     # (成功, 5路径列表, 错误消息)
    progress = pyqtSignal(str)                      # 进度文本

    def __init__(self, source_image_path: str, save_dir: str,
                 api_key: str, base_url: str,
                 prompts: Optional[List[str]] = None,
                 labels: Optional[List[str]] = None,
                 instance_type: str = "default",
                 parent=None):
        super().__init__(parent)
        self._source_image_path = source_image_path
        self._save_dir = save_dir
        self._api_key = api_key
        self._base_url = base_url
        self._prompts = prompts or ANGLE_PROMPTS
        self._labels = labels or ANGLE_LABELS
        self._instance_type = instance_type
        self._stop_requested = False
        self._job_id = f"ma_{int(time.time() * 1000)}"

    @property
    def job_id(self) -> str:
        return self._job_id

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        total = len(self._prompts)
        job = BatchJobStatus(
            job_id=self._job_id,
            source_image=self._source_image_path,
            total=total,
            status='UPLOADING',
            start_time=time.time(),
            angle_tasks=[
                AngleTaskStatus(index=i, label=lbl, prompt=p)
                for i, (p, lbl) in enumerate(zip(self._prompts, self._labels))
            ],
        )
        queue = MultiAngleJobQueue.instance()
        queue.add_job(job)

        try:
            client = RunningHubClient(self._api_key, self._base_url)
            os.makedirs(self._save_dir, exist_ok=True)

            # 1. 上传源图片（只上传一次）
            filename = os.path.basename(self._source_image_path)
            self.progress.emit(f"上传图片 {filename}...")
            upload_url = client.upload_image(self._source_image_path)
            self.progress.emit("上传完成，正在提交 {0} 个视角任务...".format(total))

            # 2. 并行提交所有任务
            job.status = 'SUBMITTED'
            task_ids: List[str] = []
            for i, (prompt, label) in enumerate(zip(self._prompts, self._labels)):
                if self._stop_requested:
                    self._emit_cancel(job, queue, [])
                    return

                node_info = [
                    {
                        "nodeId": IMAGE_NODE_ID,
                        "fieldName": IMAGE_FIELD_NAME,
                        "fieldValue": upload_url,
                    },
                    {
                        "nodeId": PROMPT_NODE_ID,
                        "fieldName": PROMPT_FIELD_NAME,
                        "fieldValue": prompt,
                    },
                ]
                task_id = client.submit_task(
                    VIEW_ANGLE_APP_ID, node_info, self._instance_type
                )
                task_ids.append(task_id)
                job.angle_tasks[i].task_id = task_id
                job.angle_tasks[i].status = 'SUBMITTED'
                self.progress.emit(f"已提交「{label}」(任务 {i+1}/{total})")

            self.progress.emit(f"全部 {total} 个任务已提交，等待生成...")
            queue.update_job(self._job_id, job)

            # 3. 统一轮询所有任务
            job.status = 'POLLING'
            poll_interval = 3.0
            timeout = 300.0
            start_time = time.time()

            # 追踪每个任务的完成状态
            done_flags = [False] * total
            results_data: List[Optional[dict]] = [None] * total   # query_task 的结果
            saved_paths: List[str] = [''] * total
            # 按顺序发射信号的指针
            next_emit_index = 0

            while not all(done_flags):
                if self._stop_requested:
                    self._emit_cancel(job, queue, saved_paths)
                    return

                elapsed = time.time() - start_time
                if elapsed > timeout:
                    # 超时：已完成的照常返回，未完成的标记失败
                    for i in range(total):
                        if not done_flags[i]:
                            job.angle_tasks[i].status = 'FAILED'
                            job.angle_tasks[i].error = f'轮询超时（{int(timeout)}秒）'
                            job.failed += 1
                            done_flags[i] = True
                    break

                # 逐个检查未完成的任务
                for i in range(total):
                    if done_flags[i]:
                        continue

                    result = client.query_task(task_ids[i])
                    status = result.get('status', '')
                    label = self._labels[i]
                    status_cn = _STATUS_LABEL.get(status, status)

                    job.angle_tasks[i].status = status
                    job.angle_tasks[i].elapsed = time.time() - start_time

                    if status == 'SUCCESS':
                        done_flags[i] = True
                        results_data[i] = result
                        job.angle_tasks[i].status = 'DOWNLOADING'
                        queue.update_job(self._job_id, job)

                        # 立即下载
                        local_path = self._download_result(
                            client, result, label, i
                        )
                        saved_paths[i] = local_path
                        job.angle_tasks[i].local_path = local_path
                        job.angle_tasks[i].status = 'SUCCESS'
                        job.completed += 1

                        self.progress.emit(
                            f"「{label}」完成 ({job.completed}/{total})"
                        )

                        # 按顺序发射 angle_completed 信号
                        while next_emit_index < total and saved_paths[next_emit_index]:
                            self.angle_completed.emit(
                                next_emit_index, saved_paths[next_emit_index]
                            )
                            next_emit_index += 1

                    elif status == 'FAILED':
                        done_flags[i] = True
                        error_msg = result.get('errorMessage', '')
                        job.angle_tasks[i].status = 'FAILED'
                        job.angle_tasks[i].error = error_msg
                        job.failed += 1
                        self.progress.emit(f"「{label}」失败: {error_msg}")

                queue.update_job(self._job_id, job)

                # 如果还有未完成的，等待后再查
                if not all(done_flags):
                    time.sleep(poll_interval)

            # 4. 发射剩余按顺序的 angle_completed 信号
            while next_emit_index < total:
                if saved_paths[next_emit_index]:
                    self.angle_completed.emit(
                        next_emit_index, saved_paths[next_emit_index]
                    )
                next_emit_index += 1

            # 5. 最终结果
            success = job.failed == 0 and job.completed == total
            final_paths = [p for p in saved_paths if p]

            if success:
                self.progress.emit(f"全部完成！共 {len(final_paths)} 张")
                job.status = 'DONE'
            else:
                errors = [
                    f"「{t.label}」: {t.error}"
                    for t in job.angle_tasks if t.status == 'FAILED'
                ]
                error_summary = "; ".join(errors)
                self.progress.emit(f"部分完成：{job.completed} 成功，{job.failed} 失败")
                job.status = 'DONE' if job.completed > 0 else 'ERROR'
                job.error = error_summary

            queue.update_job(self._job_id, job)
            queue.complete_job(self._job_id, success)
            self.all_completed.emit(success, final_paths, job.error)

        except RunningHubError as e:
            job.status = 'ERROR'
            job.error = str(e)
            queue.update_job(self._job_id, job)
            queue.complete_job(self._job_id, False)
            self.all_completed.emit(False, [], str(e))
        except Exception as e:
            import traceback
            err = f"未知错误: {e}\n{traceback.format_exc()}"
            job.status = 'ERROR'
            job.error = err
            queue.update_job(self._job_id, job)
            queue.complete_job(self._job_id, False)
            self.all_completed.emit(False, [], err)

    def _download_result(self, client: RunningHubClient,
                         result: dict, label: str, index: int) -> str:
        """从完成的任务结果中下载图片"""
        results = result.get('results', [])
        if not results:
            raise RunningHubError(f"「{label}」生成成功但无输出")

        url = results[0].get('url', '')
        if not url:
            raise RunningHubError(f"「{label}」结果无下载 URL")

        output_type = results[0].get('outputType', 'png')
        save_path = os.path.join(
            self._save_dir,
            f"angle_{index}_{label}_{int(time.time())}.{output_type}"
        )
        return client.download_file(url, save_path)

    def _emit_cancel(self, job: BatchJobStatus,
                     queue: 'MultiAngleJobQueue',
                     saved_paths: List[str]):
        """处理用户取消"""
        job.status = 'ERROR'
        job.error = '用户取消'
        queue.update_job(self._job_id, job)
        queue.complete_job(self._job_id, False)
        self.all_completed.emit(False, [p for p in saved_paths if p], "用户取消")
