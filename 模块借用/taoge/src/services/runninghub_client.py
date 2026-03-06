"""
涛割 - RunningHub API 通用客户端（同步、线程安全）
封装上传→提交→轮询→下载全流程。使用 urllib 纯标准库，无额外依赖。
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Callable


class RunningHubError(Exception):
    """RunningHub API 调用异常"""
    pass


class RunningHubClient:
    """RunningHub API 通用客户端（同步、线程安全）"""

    def __init__(self, api_key: str,
                 base_url: str = "https://www.runninghub.cn/openapi/v2"):
        if not api_key:
            raise RunningHubError("RunningHub API Key 未配置")
        self._api_key = api_key
        self._base_url = base_url.rstrip('/')

    # ── HTTP 基础方法 ──

    def _post_json(self, url: str, payload: dict, timeout: int = 60) -> dict:
        """POST JSON 请求，返回解析后的 dict"""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url=url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self._api_key}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RunningHubError(
                f"HTTP {exc.code}: {body[:500]}"
            )
        except Exception as exc:
            raise RunningHubError(f"请求失败: {exc}")

    def _get_binary(self, url: str, timeout: int = 180) -> bytes:
        """GET 请求下载二进制内容（自动处理 URL 中的非 ASCII 字符）"""
        # 对 URL 中非 ASCII 字符做 percent-encode，保留已有的 %xx 和合法 URL 字符
        safe_url = urllib.parse.quote(url, safe=':/?#[]@!$&\'()*+,;=-._~%')
        req = urllib.request.Request(url=safe_url, method="GET")
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            raise RunningHubError(
                f"下载失败 HTTP {exc.code}: {safe_url[:120]}"
            )
        except Exception as exc:
            raise RunningHubError(f"下载失败({type(exc).__name__}): {exc}")

    # ── 业务方法 ──

    def upload_image(self, file_path: str) -> str:
        """
        上传本地图片到 /media/upload/binary，返回 download_url。
        使用 multipart/form-data 格式。
        """
        file_path = os.path.abspath(file_path)
        if not os.path.isfile(file_path):
            raise RunningHubError(f"文件不存在: {file_path}")

        url = f"{self._base_url}/media/upload/binary"
        filename = os.path.basename(file_path)

        # 构建 multipart/form-data
        boundary = f"----RunningHubBoundary{int(time.time() * 1000)}"
        with open(file_path, 'rb') as f:
            file_data = f.read()

        body_parts = []
        body_parts.append(f"--{boundary}".encode())
        body_parts.append(
            f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode()
        )
        body_parts.append(b'Content-Type: application/octet-stream')
        body_parts.append(b'')
        body_parts.append(file_data)
        body_parts.append(f"--{boundary}--".encode())

        body = b'\r\n'.join(body_parts)

        req = urllib.request.Request(url=url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {self._api_key}")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")
                result = json.loads(resp_body)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RunningHubError(f"上传失败 HTTP {exc.code}: {err_body[:500]}")
        except Exception as exc:
            raise RunningHubError(f"上传失败: {exc}")

        # 解析响应
        if result.get('code') != 0:
            raise RunningHubError(
                f"上传失败: {result.get('message', '未知错误')}"
            )
        download_url = result.get('data', {}).get('download_url', '')
        if not download_url:
            raise RunningHubError("上传成功但未返回 download_url")
        return download_url

    def submit_task(self, app_id: str, node_info_list: list,
                    instance_type: str = "default") -> str:
        """
        提交 AI 应用任务到 /run/ai-app/{app_id}，返回 taskId。
        """
        url = f"{self._base_url}/run/ai-app/{app_id}"
        payload = {
            "nodeInfoList": node_info_list,
            "instanceType": instance_type,
            "usePersonalQueue": False,
        }
        result = self._post_json(url, payload)
        task_id = result.get('taskId', '')
        if not task_id:
            raise RunningHubError(
                f"提交任务失败: {result.get('errorMessage', '未返回 taskId')}"
            )
        return task_id

    def query_task(self, task_id: str) -> dict:
        """查询任务状态 /query，返回完整响应"""
        url = f"{self._base_url}/query"
        return self._post_json(url, {"taskId": task_id})

    def poll_until_done(self, task_id: str,
                        poll_interval: float = 3.0,
                        timeout: float = 300.0,
                        stop_event=None,
                        on_progress: Optional[Callable] = None) -> dict:
        """
        轮询直到 SUCCESS/FAILED，返回含 results 的最终结果。
        stop_event: threading.Event，外部可设置以中断轮询。
        on_progress: 进度回调，接收状态字符串。
        """
        start_time = time.time()
        while True:
            if stop_event and stop_event.is_set():
                raise RunningHubError("任务被用户取消")

            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise RunningHubError(
                    f"轮询超时（{timeout}秒），任务 {task_id} 仍未完成"
                )

            result = self.query_task(task_id)
            status = result.get('status', '')

            if on_progress:
                on_progress(f"状态: {status} ({int(elapsed)}s)")

            if status == 'SUCCESS':
                return result
            elif status == 'FAILED':
                error_msg = result.get('errorMessage', '')
                failed_reason = result.get('failedReason', {})
                raise RunningHubError(
                    f"任务失败: {error_msg} {failed_reason}"
                )

            time.sleep(poll_interval)

    def download_file(self, url: str, save_path: str) -> str:
        """下载文件到本地路径，返回绝对路径"""
        save_path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        data = self._get_binary(url)
        with open(save_path, 'wb') as f:
            f.write(data)
        return save_path
