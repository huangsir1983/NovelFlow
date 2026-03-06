"""
涛割 - TTS 服务
基于 RunningHub API 的文字转语音服务，移植自 run_tts_gui.py。
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QThread, pyqtSignal


@dataclass
class TTSRequest:
    """TTS 生成请求"""
    text: str
    voice_prompt: str
    scene_id: int
    scene_index: int
    output_dir: str


@dataclass
class TTSResult:
    """TTS 生成结果"""
    success: bool
    audio_path: str = ""
    error_message: str = ""


class TTSService:
    """
    TTS 服务（同步），供 QThread 内调用。
    从 run_tts_gui.py 移植核心 HTTP 逻辑。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        workflow_path: str,
        instance_type: str = "default",
        text_node_id: str = "48",
        text_field_name: str = "编辑文本",
        prompt_node_id: str = "49",
        prompt_field_name: str = "编辑文本",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.workflow_path = workflow_path
        self.instance_type = instance_type
        self.text_node_id = text_node_id
        self.text_field_name = text_field_name
        self.prompt_node_id = prompt_node_id
        self.prompt_field_name = prompt_field_name

    def generate(
        self,
        request: TTSRequest,
        poll_interval: float = 3.0,
        timeout: float = 180.0,
        on_log: Optional[Callable[[str], None]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> TTSResult:
        """
        执行 TTS 生成流程：提交 → 轮询 → 下载。
        """

        def log(msg: str):
            if on_log:
                on_log(msg)

        def is_stopped() -> bool:
            return stop_check() if stop_check else False

        # 构建提交 URL
        wp = self.workflow_path
        if wp.startswith("http://") or wp.startswith("https://"):
            submit_url = wp
        else:
            submit_url = f"{self.base_url}/{wp.lstrip('/')}"

        query_url = self._build_query_url(submit_url, self.base_url)

        # 构建请求体
        node_info_list = [
            {
                "nodeId": self.text_node_id,
                "fieldName": self.text_field_name,
                "fieldValue": request.text,
            },
            {
                "nodeId": self.prompt_node_id,
                "fieldName": self.prompt_field_name,
                "fieldValue": request.voice_prompt,
            },
        ]

        payload = {
            "addMetadata": True,
            "nodeInfoList": node_info_list,
            "instanceType": self.instance_type,
            "usePersonalQueue": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 步骤 1：提交任务
        log("提交 TTS 任务...")
        log(f"提交地址: {submit_url}")

        submit_status, _, submit_body = self._post_json(submit_url, headers, payload)
        log(f"提交 HTTP 状态: {submit_status}")

        submit_obj = self._safe_parse_json(submit_body)
        task_id = self._extract_task_id(submit_obj)
        if not task_id:
            log(f"提交响应中未找到 taskId: {submit_body}")
            return TTSResult(success=False, error_message="提交失败：未获取到 taskId")

        log(f"任务 ID: {task_id}")

        # 步骤 2：轮询状态
        start_ts = time.time()
        while True:
            if is_stopped():
                log("用户已停止任务。")
                return TTSResult(success=False, error_message="用户取消")

            if time.time() - start_ts > timeout:
                log(f"轮询超时（{timeout} 秒）。")
                return TTSResult(success=False, error_message=f"轮询超时（{timeout}秒）")

            query_payload = {"taskId": task_id}
            query_status, _, query_body = self._post_json(query_url, headers, query_payload)

            query_obj = self._safe_parse_json(query_body)
            task_status = self._extract_task_status(query_obj)
            log(f"任务状态: {task_status}")

            if task_status == "FAILED":
                log("任务失败。")
                return TTSResult(success=False, error_message="RunningHub 任务失败")

            if task_status == "SUCCESS":
                log("任务成功，开始下载结果。")
                results = self._extract_results(query_obj)
                entries = self._extract_download_entries(results)

                if not entries:
                    log("未找到可下载的音频 URL。")
                    return TTSResult(success=False, error_message="未找到下载链接")

                # 下载第一个音频文件
                output_dir = Path(request.output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                url = entries[0].get("url", "")
                output_type = entries[0].get("outputType")
                filename = self._infer_filename(url, output_type, request.scene_index)
                file_path = output_dir / filename

                log(f"下载: {url}")
                dl_status, _, dl_bytes = self._get_binary(url)

                if dl_status != 200 or dl_bytes is None:
                    log(f"下载失败，HTTP 状态: {dl_status}")
                    return TTSResult(success=False, error_message=f"下载失败（HTTP {dl_status}）")

                file_path.write_bytes(dl_bytes)
                log(f"已保存: {file_path} ({len(dl_bytes)} 字节)")
                return TTSResult(success=True, audio_path=str(file_path))

            log(f"任务未完成，{poll_interval} 秒后重试...")
            time.sleep(poll_interval)

    @staticmethod
    def _build_query_url(submit_url: str, base_url: str) -> str:
        marker = "/run/workflow/"
        if marker in submit_url:
            return submit_url.split(marker, 1)[0] + "/query"
        return f"{base_url}/query"

    @staticmethod
    def _safe_parse_json(text: str):
        try:
            return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def _post_json(url: str, headers: dict, payload: dict, timeout: int = 60):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url=url, data=data, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode()
                resp_headers = dict(resp.headers.items())
                body = resp.read().decode("utf-8", errors="replace")
                return status, resp_headers, body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            resp_headers = dict(exc.headers.items()) if exc.headers else {}
            return exc.code, resp_headers, body
        except Exception as exc:
            return -1, {}, json.dumps({"error": str(exc)}, ensure_ascii=False)

    @staticmethod
    def _get_binary(url: str, timeout: int = 180):
        req = urllib.request.Request(url=url, method="GET")
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode()
                resp_headers = dict(resp.headers.items())
                body = resp.read()
                return status, resp_headers, body
        except urllib.error.HTTPError as exc:
            resp_headers = dict(exc.headers.items()) if exc.headers else {}
            _ = exc.read()
            return exc.code, resp_headers, None
        except Exception as exc:
            return -1, {"error": str(exc)}, None

    @staticmethod
    def _extract_task_id(obj):
        if not isinstance(obj, dict):
            return None
        if obj.get("taskId"):
            return str(obj["taskId"])
        data = obj.get("data")
        if isinstance(data, dict) and data.get("taskId"):
            return str(data["taskId"])
        return None

    @staticmethod
    def _extract_task_status(obj):
        if not isinstance(obj, dict):
            return None
        status = obj.get("status") or obj.get("taskStatus")
        if status:
            return str(status)
        data = obj.get("data")
        if isinstance(data, dict):
            return data.get("status") or data.get("taskStatus")
        return None

    @staticmethod
    def _extract_results(obj):
        if not isinstance(obj, dict):
            return None
        if "results" in obj:
            return obj.get("results")
        data = obj.get("data")
        if isinstance(data, dict):
            return data.get("results")
        return None

    @staticmethod
    def _extract_download_entries(results):
        found = []

        def walk(obj):
            if isinstance(obj, dict):
                url = (
                    obj.get("url")
                    or obj.get("download_url")
                    or obj.get("downloadUrl")
                )
                if isinstance(url, str) and url.strip():
                    found.append({
                        "url": url.strip(),
                        "outputType": obj.get("outputType"),
                    })
                for value in obj.values():
                    walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(results)

        dedup = []
        seen = set()
        for item in found:
            key = item["url"]
            if key not in seen:
                seen.add(key)
                dedup.append(item)
        return dedup

    @staticmethod
    def _infer_filename(url: str, output_type, scene_index: int) -> str:
        try:
            parsed = urllib.parse.urlsplit(url)
            name = Path(urllib.parse.unquote(parsed.path)).name
        except Exception:
            name = ""

        if not name:
            ext = ""
            if output_type:
                ext = "." + str(output_type).strip().lstrip(".")
            if not ext:
                ext = ".mp3"
            name = f"scene_{scene_index:03d}_audio{ext}"

        name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name).strip(" .")
        if not name:
            name = f"scene_{scene_index:03d}_audio.mp3"
        return name


class TTSWorker(QThread):
    """TTS 生成工作线程"""

    tts_completed = pyqtSignal(int, str)    # scene_index, audio_path
    tts_failed = pyqtSignal(int, str)       # scene_index, error_message
    log_message = pyqtSignal(str)           # 日志消息

    def __init__(self, request: TTSRequest, parent=None):
        super().__init__(parent)
        self._request = request
        self._stop_requested = False

    def run(self):
        try:
            from config.settings import SettingsManager
            sm = SettingsManager()
            api_cfg = sm.settings.api

            service = TTSService(
                api_key=api_cfg.runninghub_api_key,
                base_url=api_cfg.runninghub_base_url,
                workflow_path=api_cfg.runninghub_workflow_path,
                instance_type=api_cfg.runninghub_instance_type,
                text_node_id=api_cfg.tts_text_node_id,
                text_field_name=api_cfg.tts_text_field_name,
                prompt_node_id=api_cfg.tts_prompt_node_id,
                prompt_field_name=api_cfg.tts_prompt_field_name,
            )

            result = service.generate(
                request=self._request,
                poll_interval=3.0,
                timeout=180.0,
                on_log=lambda msg: self.log_message.emit(msg),
                stop_check=lambda: self._stop_requested,
            )

            if result.success:
                self.tts_completed.emit(self._request.scene_index, result.audio_path)
            else:
                self.tts_failed.emit(self._request.scene_index, result.error_message)
        except Exception as e:
            self.tts_failed.emit(self._request.scene_index, str(e))

    def request_stop(self):
        self._stop_requested = True
