"""
涛割 - 视角转换服务
使用 RunningHub 的「角色视角切换」API 工作流，从单张图片生成指定视角的图片。
复用 RunningHubClient 的上传→提交→轮询→下载流程。
"""

import os
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from services.runninghub_client import RunningHubClient, RunningHubError

# 视角转换应用常量
VIEW_ANGLE_APP_ID = "2026919371204993025"
IMAGE_NODE_ID = "41"
IMAGE_FIELD_NAME = "image"
PROMPT_NODE_ID = "137"
PROMPT_FIELD_NAME = "text"

# 方位角预设（水平环绕）
AZIMUTH_PRESETS = {
    '正面': 'front view',
    '右前方': 'front-right quarter view',
    '右侧': 'right side view',
    '右后方': 'back-right quarter view',
    '背面': 'back view',
    '左后方': 'back-left quarter view',
    '左侧': 'left side view',
    '左前方': 'front-left quarter view',
}

# 俯仰角预设
ELEVATION_PRESETS = {
    '仰视': 'low-angle shot',
    '平视': 'eye-level shot',
    '俯视': 'elevated shot',
    '高角度': 'high-angle shot',
}

# 距离预设
DISTANCE_PRESETS = {
    '特写': 'close-up',
    '中景': 'medium shot',
    '远景': 'wide shot',
}

# 状态中文映射
_STATUS_LABEL = {
    'QUEUED':  '排队中',
    'RUNNING': '运行中',
    'SUCCESS': '已完成',
    'FAILED':  '失败',
}

# ── 数值 → 预设文本映射（用于从 3D 控件角度值生成提示词）──
# 水平角度约定: 0°=正面, +右, -左 (范围 -180° ~ +180°)

AZIMUTH_ANGLE_MAP = [
    (0,    'front view'),
    (45,   'front-right quarter view'),
    (90,   'right side view'),
    (135,  'back-right quarter view'),
    (180,  'back view'),
    (-180, 'back view'),
    (-135, 'back-left quarter view'),
    (-90,  'left side view'),
    (-45,  'front-left quarter view'),
]

ELEVATION_ANGLE_MAP = [
    (-30, 'low-angle shot'),
    (0,   'eye-level shot'),
    (30,  'elevated shot'),
    (60,  'high-angle shot'),
]

DISTANCE_RANGE_MAP = [
    (3.3,  'close-up'),
    (6.6,  'medium shot'),
    (10.0, 'wide shot'),
]


def build_angle_prompt(azimuth: str, elevation: str, distance: str) -> str:
    """构建视角转换提示词，格式：<sks> azimuth elevation distance"""
    return f"<sks> {azimuth} {elevation} {distance}"


def _nearest_azimuth_text(azimuth: float) -> str:
    """方位角：找最近的预设（支持 -180° ~ +180°）"""
    min_diff = float('inf')
    az_text = 'front view'
    for angle, text in AZIMUTH_ANGLE_MAP:
        # 考虑环绕距离
        diff = abs(azimuth - angle)
        if diff > 180:
            diff = 360 - diff
        if diff < min_diff:
            min_diff = diff
            az_text = text
    return az_text


def _nearest_elevation_text(elevation: float) -> str:
    """俯仰角：找最近的预设"""
    min_diff = float('inf')
    el_text = 'eye-level shot'
    for angle, text in ELEVATION_ANGLE_MAP:
        if abs(elevation - angle) < min_diff:
            min_diff = abs(elevation - angle)
            el_text = text
    return el_text


def _nearest_distance_text(distance: float) -> str:
    """距离：按区间划分"""
    for threshold, text in DISTANCE_RANGE_MAP:
        if distance <= threshold:
            return text
    return 'wide shot'


def angle_to_prompt(azimuth: float, elevation: float, distance: float) -> str:
    """从数值角度映射到最近预设文本并构建提示词

    Output format: <sks> {azimuth_text} {elevation_text} {distance_text}
    Example: <sks> front-right quarter view low-angle shot medium shot

    提示词只包含预设文本，不包含数值角度（Qwen 模型只识别预设文本）。
    """
    az_text = _nearest_azimuth_text(azimuth)
    el_text = _nearest_elevation_text(elevation)
    dist_text = _nearest_distance_text(distance)

    return f"<sks> {az_text} {el_text} {dist_text}"


def angle_to_display(azimuth: float, elevation: float, distance: float) -> str:
    """生成带有数值的显示文本（用于 UI 预览，非 API 提交）

    Example: <sks> front-right quarter view low-angle shot medium shot
             (水平: 38°, 垂直: -21°, 距离: 5.0)
    """
    prompt = angle_to_prompt(azimuth, elevation, distance)
    return f"{prompt}\n(水平: {azimuth:.0f}°, 垂直: {elevation:.0f}°, 距离: {distance:.1f})"


class ViewAngleConvertWorker(QThread):
    """视角转换 Worker — 上传→提交→轮询→下载"""

    progress = pyqtSignal(str)                    # 进度消息
    completed = pyqtSignal(bool, str, str)        # success, local_path, error_msg

    def __init__(self, source_image_path: str, prompt: str,
                 save_dir: str, api_key: str, base_url: str,
                 instance_type: str = "default", parent=None):
        super().__init__(parent)
        self._source_image_path = source_image_path
        self._prompt = prompt
        self._save_dir = save_dir
        self._api_key = api_key
        self._base_url = base_url
        self._instance_type = instance_type

    def run(self):
        try:
            client = RunningHubClient(self._api_key, self._base_url)

            # 1. 上传图片
            filename = os.path.basename(self._source_image_path)
            self.progress.emit(f"[1/4] 上传图片 {filename}...")
            upload_url = client.upload_image(self._source_image_path)
            self.progress.emit("[1/4] 上传完成")

            # 2. 提交任务（图片节点 + 提示词节点）
            self.progress.emit("[2/4] 提交视角转换任务...")
            node_info = [
                {
                    "nodeId": IMAGE_NODE_ID,
                    "fieldName": IMAGE_FIELD_NAME,
                    "fieldValue": upload_url,
                },
                {
                    "nodeId": PROMPT_NODE_ID,
                    "fieldName": PROMPT_FIELD_NAME,
                    "fieldValue": self._prompt,
                },
            ]
            task_id = client.submit_task(
                VIEW_ANGLE_APP_ID, node_info, self._instance_type
            )
            self.progress.emit(f"[2/4] 任务已提交 (ID: {task_id[:20]}...)")

            # 3. 轮询结果
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

            # 4. 下载结果
            results = result.get('results', [])
            if not results:
                self.completed.emit(False, "", "生成成功但无输出结果")
                return

            self.progress.emit("[4/4] 下载结果图片...")
            os.makedirs(self._save_dir, exist_ok=True)

            url = results[0].get('url', '')
            if not url:
                self.completed.emit(False, "", "结果中无下载 URL")
                return

            output_type = results[0].get('outputType', 'png')
            save_path = os.path.join(
                self._save_dir,
                f"view_angle_{int(time.time())}.{output_type}"
            )

            saved = client.download_file(url, save_path)
            self.progress.emit("完成！视角转换图片已下载")
            self.completed.emit(True, saved, "")

        except RunningHubError as e:
            self.completed.emit(False, "", str(e))
        except Exception as e:
            import traceback
            self.completed.emit(False, "", f"未知错误: {e}\n{traceback.format_exc()}")
