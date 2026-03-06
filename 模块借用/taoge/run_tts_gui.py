import json
import os
import queue
import re
import threading
import time
import traceback
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


def 当前时间戳() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def 安全解析_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def 脱敏密钥(value: str) -> str:
    value = (value or "").strip()
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


class RunningHubTTS工具:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RunningHub TTS 调试工具")
        self.root.geometry("1180x880")

        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False

        self.base_dir = Path(__file__).resolve().parent
        self.api_file = self.base_dir / "API KEY.txt"
        self.workflow_file = self.base_dir / "Qwen3-tts创建声音_api.json"

        self.base_url_var = tk.StringVar(value="https://www.runninghub.cn/openapi/v2")
        self.workflow_path_var = tk.StringVar(value="")
        self.api_key_var = tk.StringVar(value="")
        self.instance_type_var = tk.StringVar(value="default")
        self.use_personal_queue_var = tk.BooleanVar(value=False)
        self.poll_interval_var = tk.StringVar(value="3")
        self.timeout_var = tk.StringVar(value="180")
        self.auto_download_var = tk.BooleanVar(value=True)
        self.download_dir_var = tk.StringVar(value="downloads")

        self.text_node_id_var = tk.StringVar(value="48")
        self.text_field_name_var = tk.StringVar(value="编辑文本")
        self.prompt_node_id_var = tk.StringVar(value="49")
        self.prompt_field_name_var = tk.StringVar(value="编辑文本")
        self.show_key_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._schedule_log_flush()
        self._自动加载本地文件()

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill="both", expand=True)

        config_frame = ttk.LabelFrame(container, text="配置", padding=10)
        config_frame.pack(fill="x")

        ttk.Label(config_frame, text="基础地址").grid(row=0, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.base_url_var, width=78).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=6
        )

        ttk.Label(config_frame, text="工作流路径").grid(row=1, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.workflow_path_var, width=78).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=6
        )

        ttk.Label(config_frame, text="API 密钥").grid(row=2, column=0, sticky="w")
        self.api_key_entry = ttk.Entry(
            config_frame, textvariable=self.api_key_var, width=78, show="*"
        )
        self.api_key_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=6)
        ttk.Checkbutton(
            config_frame,
            text="显示明文",
            variable=self.show_key_var,
            command=self._切换密钥显示,
        ).grid(row=2, column=3, sticky="w")

        ttk.Label(config_frame, text="实例规格").grid(row=3, column=0, sticky="w")
        ttk.Combobox(
            config_frame,
            textvariable=self.instance_type_var,
            values=("default", "plus"),
            width=16,
            state="readonly",
        ).grid(row=3, column=1, sticky="w", padx=6)
        ttk.Checkbutton(
            config_frame, text="使用个人队列", variable=self.use_personal_queue_var
        ).grid(row=3, column=2, sticky="w")

        ttk.Label(config_frame, text="轮询间隔(秒)").grid(row=4, column=0, sticky="w")
        ttk.Entry(config_frame, textvariable=self.poll_interval_var, width=12).grid(
            row=4, column=1, sticky="w", padx=6
        )
        ttk.Label(config_frame, text="超时(秒)").grid(row=4, column=2, sticky="w")
        ttk.Entry(config_frame, textvariable=self.timeout_var, width=12).grid(
            row=4, column=3, sticky="w", padx=6
        )

        ttk.Checkbutton(
            config_frame, text="成功后自动下载结果", variable=self.auto_download_var
        ).grid(row=5, column=0, sticky="w")
        ttk.Label(config_frame, text="下载目录").grid(row=5, column=1, sticky="e")
        ttk.Entry(config_frame, textvariable=self.download_dir_var, width=45).grid(
            row=5, column=2, sticky="ew", padx=6
        )
        ttk.Button(config_frame, text="打开目录", command=self._打开下载目录).grid(
            row=5, column=3, sticky="w"
        )

        config_frame.columnconfigure(1, weight=1)
        config_frame.columnconfigure(2, weight=1)

        mapping_frame = ttk.LabelFrame(container, text="节点映射", padding=10)
        mapping_frame.pack(fill="x", pady=(8, 0))

        ttk.Label(mapping_frame, text="文本节点ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(mapping_frame, textvariable=self.text_node_id_var, width=16).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Label(mapping_frame, text="文本字段名").grid(row=0, column=2, sticky="w")
        ttk.Entry(mapping_frame, textvariable=self.text_field_name_var, width=20).grid(
            row=0, column=3, sticky="w", padx=6
        )

        ttk.Label(mapping_frame, text="提示词节点ID").grid(row=1, column=0, sticky="w")
        ttk.Entry(mapping_frame, textvariable=self.prompt_node_id_var, width=16).grid(
            row=1, column=1, sticky="w", padx=6
        )
        ttk.Label(mapping_frame, text="提示词字段名").grid(row=1, column=2, sticky="w")
        ttk.Entry(mapping_frame, textvariable=self.prompt_field_name_var, width=20).grid(
            row=1, column=3, sticky="w", padx=6
        )

        input_frame = ttk.LabelFrame(container, text="输入内容", padding=10)
        input_frame.pack(fill="x", pady=(8, 0))

        ttk.Label(input_frame, text="文本").grid(row=0, column=0, sticky="nw")
        self.text_box = ScrolledText(input_frame, height=4, width=90, wrap="word")
        self.text_box.grid(row=0, column=1, sticky="ew", padx=6)

        ttk.Label(input_frame, text="提示词").grid(row=1, column=0, sticky="nw")
        self.prompt_box = ScrolledText(input_frame, height=4, width=90, wrap="word")
        self.prompt_box.grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))
        input_frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text="重新加载本地文件", command=self._自动加载本地文件).pack(
            side="left"
        )
        self.start_btn = ttk.Button(btn_frame, text="开始运行", command=self.start_run)
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = ttk.Button(btn_frame, text="停止轮询", command=self.stop_run, state="disabled")
        self.stop_btn.pack(side="left")
        ttk.Button(btn_frame, text="清空日志", command=self.clear_log).pack(side="left", padx=8)

        log_frame = ttk.LabelFrame(container, text="日志（请求 / 响应 / 状态）", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.log_box = ScrolledText(log_frame, wrap="word")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def _切换密钥显示(self):
        self.api_key_entry.configure(show="" if self.show_key_var.get() else "*")

    def _schedule_log_flush(self):
        self._flush_logs()
        self.root.after(120, self._schedule_log_flush)

    def _flush_logs(self):
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

    def log(self, message: str):
        self.log_queue.put(f"[{当前时间戳()}] {message}")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _自动加载本地文件(self):
        self.log("开始加载本地文件...")
        self._加载_api文件()
        self._加载_workflow文件()
        self.log("本地文件加载完成。")

    def _加载_api文件(self):
        if not self.api_file.exists():
            self.log(f"未找到 API 文件: {self.api_file}")
            return
        try:
            text = self.api_file.read_text(encoding="utf-8-sig", errors="replace")
            self.log(f"已读取 API 文件: {self.api_file}")

            endpoint_match = re.search(r"(?:端点接口|endpoint)\s*:\s*(.+)", text, flags=re.IGNORECASE)
            key_match = re.search(r"APIkey\s*:\s*([A-Za-z0-9]+)", text, flags=re.IGNORECASE)

            if endpoint_match:
                endpoint = endpoint_match.group(1).strip()
                self.workflow_path_var.set(endpoint)
                self.log(f"已加载工作流路径: {endpoint}")
            else:
                self.log("API KEY.txt 中未找到工作流路径。")

            if key_match:
                key = key_match.group(1).strip()
                self.api_key_var.set(key)
                self.log(f"已加载 API 密钥: {脱敏密钥(key)}")
            else:
                self.log("API KEY.txt 中未找到 API 密钥。")
        except Exception as exc:
            self.log(f"读取 API 文件失败: {exc}")

    def _加载_workflow文件(self):
        if not self.workflow_file.exists():
            self.log(f"未找到工作流文件: {self.workflow_file}")
            return
        try:
            raw = self.workflow_file.read_text(encoding="utf-8-sig", errors="strict")
            data = json.loads(raw)
            self.log(f"已读取工作流文件: {self.workflow_file}")

            voice_node_id, voice_node = self._查找首个节点(data, "Qwen3TTSVoiceDesign")
            if not voice_node:
                self.log("未找到 Qwen3TTSVoiceDesign 节点，保留手动映射。")
                return

            self.log(f"检测到语音设计节点: {voice_node_id}")
            inputs = voice_node.get("inputs", {})

            text_ref = inputs.get("文本")
            prompt_ref = inputs.get("提示词")
            text_node_id = self._提取引用节点ID(text_ref)
            prompt_node_id = self._提取引用节点ID(prompt_ref)

            if text_node_id:
                self.text_node_id_var.set(text_node_id)
                field_name, field_value = self._挑选文本字段(data.get(text_node_id, {}))
                if field_name:
                    self.text_field_name_var.set(field_name)
                if field_value:
                    self._设置文本框(self.text_box, field_value)
                self.log(
                    f"文本映射: nodeId={self.text_node_id_var.get()}, fieldName={self.text_field_name_var.get()}"
                )

            if prompt_node_id:
                self.prompt_node_id_var.set(prompt_node_id)
                field_name, field_value = self._挑选文本字段(data.get(prompt_node_id, {}))
                if field_name:
                    self.prompt_field_name_var.set(field_name)
                if field_value:
                    self._设置文本框(self.prompt_box, field_value)
                self.log(
                    f"提示词映射: nodeId={self.prompt_node_id_var.get()}, fieldName={self.prompt_field_name_var.get()}"
                )
        except Exception as exc:
            self.log(f"读取工作流文件失败: {exc}")

    @staticmethod
    def _查找首个节点(workflow_data, class_type: str):
        for node_id, node in workflow_data.items():
            if isinstance(node, dict) and node.get("class_type") == class_type:
                return str(node_id), node
        return None, None

    @staticmethod
    def _提取引用节点ID(value):
        if isinstance(value, list) and value:
            return str(value[0])
        return None

    @staticmethod
    def _挑选文本字段(node):
        inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
        if "编辑文本" in inputs:
            return "编辑文本", str(inputs.get("编辑文本", ""))
        for key, val in inputs.items():
            if isinstance(val, str):
                return str(key), val
        return None, None

    @staticmethod
    def _设置文本框(box: ScrolledText, value: str):
        box.delete("1.0", "end")
        box.insert("1.0", value)

    def _读取文本框(self, box: ScrolledText) -> str:
        return box.get("1.0", "end").strip()

    def _解析下载目录(self) -> Path:
        raw = self.download_dir_var.get().strip() or "downloads"
        path = Path(raw)
        if not path.is_absolute():
            path = self.base_dir / path
        return path

    def _打开下载目录(self):
        try:
            path = self._解析下载目录()
            path.mkdir(parents=True, exist_ok=True)

            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", str(path)])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", str(path)])
            self.log(f"已打开目录: {path}")
        except Exception as exc:
            self.log(f"打开目录失败: {exc}")

    def start_run(self):
        if self.running:
            self.log("当前已有任务在运行，请先停止。")
            return

        try:
            poll_interval = float(self.poll_interval_var.get().strip() or "3")
            timeout_sec = float(self.timeout_var.get().strip() or "180")
        except Exception:
            self.log("轮询间隔或超时时间格式错误。")
            return

        workflow_path = self.workflow_path_var.get().strip()
        if not workflow_path:
            self.log("工作流路径为空。")
            return

        api_key = self.api_key_var.get().strip()
        if not api_key:
            self.log("API 密钥为空。")
            return

        text_value = self._读取文本框(self.text_box)
        prompt_value = self._读取文本框(self.prompt_box)
        if not text_value:
            self.log("文本内容为空。")
            return
        if not prompt_value:
            self.log("提示词内容为空。")
            return

        base_url = self.base_url_var.get().strip().rstrip("/")
        submit_url = (
            workflow_path
            if workflow_path.startswith("http://") or workflow_path.startswith("https://")
            else f"{base_url}/{workflow_path.lstrip('/')}"
        )
        query_url = self._构建查询地址(submit_url, base_url)

        node_info_list = [
            {
                "nodeId": self.text_node_id_var.get().strip(),
                "fieldName": self.text_field_name_var.get().strip(),
                "fieldValue": text_value,
            },
            {
                "nodeId": self.prompt_node_id_var.get().strip(),
                "fieldName": self.prompt_field_name_var.get().strip(),
                "fieldValue": prompt_value,
            },
        ]

        for idx, item in enumerate(node_info_list, start=1):
            if not item["nodeId"] or not item["fieldName"]:
                self.log(f"第 {idx} 条节点映射不完整: {item}")
                return

        payload = {
            "addMetadata": True,
            "nodeInfoList": node_info_list,
            "instanceType": self.instance_type_var.get().strip() or "default",
            "usePersonalQueue": bool(self.use_personal_queue_var.get()),
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        download_root = self._解析下载目录()

        run_cfg = {
            "submit_url": submit_url,
            "query_url": query_url,
            "headers": headers,
            "payload": payload,
            "poll_interval": max(1.0, poll_interval),
            "timeout_sec": max(10.0, timeout_sec),
            "auto_download": bool(self.auto_download_var.get()),
            "download_root": download_root,
        }

        self.running = True
        self.stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        self.log("========== 开始任务 ==========")
        self.log(f"提交地址: {submit_url}")
        self.log(f"查询地址: {query_url}")
        self.log(f"Authorization: Bearer {脱敏密钥(api_key)}")
        self.log(f"自动下载: {run_cfg['auto_download']}")
        self.log(f"下载目录: {download_root}")
        self.log("提交请求体:")
        self.log(json.dumps(payload, ensure_ascii=False, indent=2))

        thread = threading.Thread(target=self._执行流程, args=(run_cfg,), daemon=True)
        thread.start()

    def stop_run(self):
        if not self.running:
            self.log("当前没有运行中的任务。")
            return
        self.stop_event.set()
        self.log("已发送停止信号。")

    @staticmethod
    def _构建查询地址(submit_url: str, base_url: str) -> str:
        marker = "/run/workflow/"
        if marker in submit_url:
            return submit_url.split(marker, 1)[0] + "/query"
        return f"{base_url}/query"

    def _执行流程(self, cfg: dict):
        try:
            submit_status, submit_headers, submit_body = self._post_json(
                cfg["submit_url"], cfg["headers"], cfg["payload"], timeout=60
            )
            self.log(f"提交 HTTP 状态: {submit_status}")
            self.log("提交响应头:")
            self.log(json.dumps(submit_headers, ensure_ascii=False, indent=2))
            self.log("提交响应体:")
            self.log(submit_body)

            submit_obj = 安全解析_json(submit_body)
            task_id = self._提取任务ID(submit_obj)
            if not task_id:
                self.log("提交响应中未找到 taskId，流程结束。")
                return

            self.log(f"任务ID: {task_id}")
            start_ts = time.time()

            while True:
                if self.stop_event.is_set():
                    self.log("轮询已由用户停止。")
                    return

                if time.time() - start_ts > cfg["timeout_sec"]:
                    self.log(f"轮询超时（{cfg['timeout_sec']} 秒）。")
                    return

                query_payload = {"taskId": task_id}
                self.log("轮询请求体:")
                self.log(json.dumps(query_payload, ensure_ascii=False, indent=2))

                query_status, query_headers, query_body = self._post_json(
                    cfg["query_url"], cfg["headers"], query_payload, timeout=60
                )
                self.log(f"查询 HTTP 状态: {query_status}")
                self.log("查询响应头:")
                self.log(json.dumps(query_headers, ensure_ascii=False, indent=2))
                self.log("查询响应体:")
                self.log(query_body)

                query_obj = 安全解析_json(query_body)
                task_status = self._提取任务状态(query_obj)
                results = self._提取结果(query_obj)
                self.log(f"解析任务状态: {task_status}")

                if task_status in {"SUCCESS", "FAILED"}:
                    self.log("任务已到达最终状态。")
                    if results is not None:
                        self.log("解析到 results:")
                        self.log(json.dumps(results, ensure_ascii=False, indent=2))
                    if task_status == "SUCCESS" and cfg["auto_download"]:
                        self._自动下载结果(task_id, results, cfg["download_root"])
                    self.log("========== 任务结束 ==========")
                    return

                wait_s = cfg["poll_interval"]
                self.log(f"任务未完成，{wait_s} 秒后继续轮询。")
                self.stop_event.wait(wait_s)
        except Exception as exc:
            self.log(f"执行失败: {exc}")
            self.log(traceback.format_exc())
        finally:
            self.running = False
            self.root.after(0, lambda: self.start_btn.configure(state="normal"))
            self.root.after(0, lambda: self.stop_btn.configure(state="disabled"))

    def _自动下载结果(self, task_id: str, results, download_root: Path):
        entries = self._提取下载条目(results)
        if not entries:
            self.log("未在 results 中发现可下载 URL。")
            return

        task_dir = download_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"开始自动下载，共 {len(entries)} 个文件。")
        self.log(f"任务下载目录: {task_dir}")

        for idx, entry in enumerate(entries, start=1):
            url = entry.get("url", "")
            output_type = entry.get("outputType")
            filename = self._推断文件名(url, output_type, idx)
            file_path = self._生成不冲突路径(task_dir / filename)

            self.log(f"[下载 {idx}/{len(entries)}] URL: {url}")
            dl_status, dl_headers, dl_bytes = self._get_binary(url, timeout=180)
            self.log(f"[下载 {idx}/{len(entries)}] HTTP 状态: {dl_status}")
            self.log(f"[下载 {idx}/{len(entries)}] 响应头:")
            self.log(json.dumps(dl_headers, ensure_ascii=False, indent=2))

            if dl_status != 200 or dl_bytes is None:
                self.log(f"[下载 {idx}/{len(entries)}] 下载失败。")
                continue

            file_path.write_bytes(dl_bytes)
            self.log(f"[下载 {idx}/{len(entries)}] 字节数: {len(dl_bytes)}")
            self.log(f"[下载 {idx}/{len(entries)}] 已保存: {file_path}")

    @staticmethod
    def _提取下载条目(results):
        found = []

        def walk(obj):
            if isinstance(obj, dict):
                url = (
                    obj.get("url")
                    or obj.get("download_url")
                    or obj.get("downloadUrl")
                )
                if isinstance(url, str) and url.strip():
                    found.append(
                        {
                            "url": url.strip(),
                            "outputType": obj.get("outputType"),
                        }
                    )
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
    def _推断文件名(url: str, output_type, index: int) -> str:
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
                ext = ".bin"
            name = f"result_{index:02d}{ext}"

        name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name).strip(" .")
        if not name:
            name = f"result_{index:02d}.bin"
        return name

    @staticmethod
    def _生成不冲突路径(path: Path) -> Path:
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        for i in range(1, 10000):
            candidate = parent / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                return candidate
        return parent / f"{stem}_{int(time.time())}{suffix}"

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
    def _提取任务ID(obj):
        if not isinstance(obj, dict):
            return None
        if obj.get("taskId"):
            return str(obj["taskId"])
        data = obj.get("data")
        if isinstance(data, dict) and data.get("taskId"):
            return str(data["taskId"])
        return None

    @staticmethod
    def _提取任务状态(obj):
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
    def _提取结果(obj):
        if not isinstance(obj, dict):
            return None
        if "results" in obj:
            return obj.get("results")
        data = obj.get("data")
        if isinstance(data, dict):
            return data.get("results")
        return None


def main():
    root = tk.Tk()
    app = RunningHubTTS工具(root)
    app.log("界面已就绪。")
    root.mainloop()


if __name__ == "__main__":
    main()
