"""
涛割 - 图像抠图服务
使用 RunningHub 的「图像抠图-通道输出」API 工作流，从原始图片生成带透明通道的抠图结果。
复用 RunningHubClient 的上传→提交→轮询→下载流程。
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from services.runninghub_client import RunningHubClient, RunningHubError

# 抠图应用常量
MATTING_APP_ID = "2026922313706377217"
IMAGE_NODE_ID = "1"
IMAGE_FIELD_NAME = "image"

# 状态中文映射
_STATUS_LABEL = {
    'QUEUED':  '排队中',
    'RUNNING': '运行中',
    'SUCCESS': '已完成',
    'FAILED':  '失败',
}


class MattingWorker(QThread):
    """抠图 Worker — 上传→提交→轮询→下载"""

    progress = pyqtSignal(str, int)               # 进度消息, 百分比(0-100)
    completed = pyqtSignal(bool, str, str)         # success, local_path, error_msg

    def __init__(self, source_image_path: str,
                 save_dir: str, api_key: str, base_url: str,
                 instance_type: str = "default", parent=None):
        super().__init__(parent)
        self._source_image_path = source_image_path
        self._save_dir = save_dir
        self._api_key = api_key
        self._base_url = base_url
        self._instance_type = instance_type

    def run(self):
        try:
            client = RunningHubClient(self._api_key, self._base_url)

            # 1. 上传图片
            filename = os.path.basename(self._source_image_path)
            self.progress.emit(f"[1/4] 上传图片 {filename}...", 10)
            upload_url = client.upload_image(self._source_image_path)
            self.progress.emit("[1/4] 上传完成", 20)

            # 2. 提交任务
            self.progress.emit("[2/4] 提交抠图任务...", 25)
            node_info = [
                {
                    "nodeId": IMAGE_NODE_ID,
                    "fieldName": IMAGE_FIELD_NAME,
                    "fieldValue": upload_url,
                },
            ]
            task_id = client.submit_task(
                MATTING_APP_ID, node_info, self._instance_type
            )
            self.progress.emit(f"[2/4] 任务已提交", 30)

            # 3. 轮询结果
            self.progress.emit("[3/4] 云端处理中...", 40)
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

                # 进度从 40 到 80 线性增长
                pct = min(80, 40 + int(elapsed / timeout * 40))
                self.progress.emit(
                    f"[3/4] 轮询#{poll_count}  {status_cn}  已等待 {int(elapsed)}s",
                    pct,
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

            # 4. 下载结果
            results = result.get('results', [])
            if not results:
                self.completed.emit(False, "", "抠图成功但无输出结果")
                return

            self.progress.emit("[4/4] 下载结果图片...", 90)
            os.makedirs(self._save_dir, exist_ok=True)

            url = results[0].get('url', '')
            if not url:
                self.completed.emit(False, "", "结果中无下载 URL")
                return

            output_type = results[0].get('outputType', 'png')
            save_path = os.path.join(
                self._save_dir,
                f"matting_{int(time.time())}.{output_type}"
            )

            saved = client.download_file(url, save_path)
            self.progress.emit("完成！抠图结果已下载", 100)
            self.completed.emit(True, saved, "")

        except RunningHubError as e:
            self.completed.emit(False, "", str(e))
        except Exception as e:
            import traceback
            self.completed.emit(False, "", f"未知错误: {e}\n{traceback.format_exc()}")
