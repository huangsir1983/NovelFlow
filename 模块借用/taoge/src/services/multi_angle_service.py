"""
涛割 - 多视角生成服务
使用 RunningHub 的「角色多视角应用」API 工作流，从单张图片生成多视角图片。
"""

import os
import time
import urllib.parse
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from services.runninghub_client import RunningHubClient, RunningHubError

# 多视角应用常量
MULTI_ANGLE_APP_ID = "2026521841367519234"
MULTI_ANGLE_NODE_ID = "78"
MULTI_ANGLE_FIELD_NAME = "image"

# 状态中文映射
_STATUS_LABEL = {
    'QUEUED':  '排队中',
    'RUNNING': '运行中',
    'SUCCESS': '已完成',
    'FAILED':  '失败',
}


class MultiAngleWorker(QThread):
    """多视角图片生成 Worker"""

    progress = pyqtSignal(str)                # 进度消息
    completed = pyqtSignal(bool, list, str)   # success, local_paths[], error_msg
    # 注意：不能用 finished 作为信号名，QThread 内置 finished 信号会冲突

    def __init__(self, source_image_path: str, save_dir: str,
                 api_key: str, base_url: str,
                 instance_type: str = "default",
                 req_id: int = 0, parent=None):
        super().__init__(parent)
        self._source_image_path = source_image_path
        self._save_dir = save_dir
        self._api_key = api_key
        self._base_url = base_url
        self._instance_type = instance_type
        self._req_id = req_id

    def run(self):
        try:
            client = RunningHubClient(self._api_key, self._base_url)

            # ── 1. 上传图片 ──
            filename = os.path.basename(self._source_image_path)
            file_size = os.path.getsize(self._source_image_path)
            size_mb = file_size / (1024 * 1024)
            self.progress.emit(f"[1/4] 上传图片 {filename} ({size_mb:.1f}MB)...")

            upload_url = client.upload_image(self._source_image_path)
            short_url = upload_url[:60] + '...' if len(upload_url) > 60 else upload_url
            self.progress.emit(f"[1/4] 上传完成 → {short_url}")

            # ── 2. 提交任务 ──
            self.progress.emit("[2/4] 提交多视角生成任务...")
            node_info = [{
                "nodeId": MULTI_ANGLE_NODE_ID,
                "fieldName": MULTI_ANGLE_FIELD_NAME,
                "fieldValue": upload_url,
            }]
            task_id = client.submit_task(
                MULTI_ANGLE_APP_ID, node_info, self._instance_type
            )
            self.progress.emit(f"[2/4] 任务已提交 (ID: {task_id[:20]}...)")

            # ── 3. 轮询结果 ──
            self.progress.emit("[3/4] 等待云端生成...")
            poll_count = 0
            poll_interval = 3.0
            timeout = 300.0
            start_time = time.time()

            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise RunningHubError(
                        f"轮询超时（{int(timeout)}秒），任务仍未完成"
                    )

                result = client.query_task(task_id)
                status = result.get('status', '')
                status_cn = _STATUS_LABEL.get(status, status)
                poll_count += 1

                self.progress.emit(
                    f"[3/4] 轮询#{poll_count}  {status_cn}  "
                    f"已等待 {int(elapsed)}s"
                )

                if status == 'SUCCESS':
                    break
                elif status == 'FAILED':
                    error_msg = result.get('errorMessage', '')
                    failed_reason = result.get('failedReason', {})
                    raise RunningHubError(
                        f"云端任务失败: {error_msg} {failed_reason}"
                    )

                time.sleep(poll_interval)

            # ── 4. 下载结果 ──
            results = result.get('results', [])
            if not results:
                self.completed.emit(False, [], "生成成功但无输出结果")
                return

            total = len(results)
            self.progress.emit(f"[4/4] 开始下载 {total} 张图片...")
            os.makedirs(self._save_dir, exist_ok=True)

            downloaded_paths = []
            for i, item in enumerate(results):
                url = item.get('url', '')
                if not url:
                    self.progress.emit(
                        f"[4/4] 跳过第 {i+1} 张（无 URL）"
                    )
                    continue

                output_type = item.get('outputType', 'png')
                filename = f"angle_{i + 1}.{output_type}"
                save_path = os.path.join(self._save_dir, filename)

                # 避免文件名冲突
                if os.path.exists(save_path):
                    stem = f"angle_{i + 1}_{int(time.time())}"
                    save_path = os.path.join(
                        self._save_dir, f"{stem}.{output_type}"
                    )

                self.progress.emit(
                    f"[4/4] 下载 {i+1}/{total}: {os.path.basename(save_path)}..."
                )
                saved = client.download_file(url, save_path)
                downloaded_paths.append(saved)
                self.progress.emit(
                    f"[4/4] 已下载 {i+1}/{total}"
                )

            self.progress.emit(
                f"完成！共 {len(downloaded_paths)} 张多视角图片"
            )
            self.completed.emit(True, downloaded_paths, "")

        except RunningHubError as e:
            self.completed.emit(False, [], str(e))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.completed.emit(False, [], f"未知错误: {e}\n{tb}")
