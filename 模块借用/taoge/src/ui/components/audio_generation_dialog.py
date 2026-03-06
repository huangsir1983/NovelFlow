"""
涛割 - 音频生成对话框
基于 RunningHub TTS API 的音频生成界面。
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QGridLayout, QComboBox,
    QCheckBox, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from services.tts.tts_service import TTSRequest, TTSWorker


class AudioGenerationDialog(QDialog):
    """音频生成对话框"""

    audio_generated = pyqtSignal(int, str)  # scene_index, audio_path

    def __init__(self, scene_index: int, scene_data: Dict[str, Any],
                 output_dir: str, parent=None):
        super().__init__(parent)
        self._scene_index = scene_index
        self._scene_data = scene_data
        self._output_dir = output_dir
        self._worker: Optional[TTSWorker] = None

        self.setWindowTitle(f"音频生成 - 场景 {scene_index + 1}")
        self.setMinimumSize(680, 700)
        self.resize(720, 760)
        self.setStyleSheet(self._get_dialog_style())

        self._init_ui()
        self._load_settings()
        self._prefill_from_scene()

    def _get_dialog_style(self) -> str:
        return """
            QDialog {
                background-color: #1e1e24;
                color: #e0e0e0;
            }
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: #a0a0b0;
                border: 1px solid #35354a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLabel {
                color: #b0b0c0;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #2a2a36;
                color: #e0e0e0;
                border: 1px solid #40405a;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #0a84ff;
            }
            QTextEdit {
                background-color: #2a2a36;
                color: #e0e0e0;
                border: 1px solid #40405a;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: #0a84ff;
            }
            QPushButton {
                background-color: #35354a;
                color: #d0d0e0;
                border: 1px solid #45455a;
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #40406a;
                border-color: #5555aa;
            }
            QPushButton:pressed {
                background-color: #2a2a40;
            }
            QPushButton:disabled {
                color: #606070;
                background-color: #28283a;
            }
            QCheckBox {
                color: #b0b0c0;
                font-size: 12px;
                spacing: 6px;
            }
        """

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # ── 配置区 ──
        config_group = QGroupBox("配置")
        config_grid = QGridLayout(config_group)
        config_grid.setContentsMargins(12, 16, 12, 10)
        config_grid.setSpacing(6)

        config_grid.addWidget(QLabel("基础地址:"), 0, 0)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://www.runninghub.cn/openapi/v2")
        config_grid.addWidget(self.base_url_edit, 0, 1, 1, 3)

        config_grid.addWidget(QLabel("工作流路径:"), 1, 0)
        self.workflow_path_edit = QLineEdit()
        self.workflow_path_edit.setPlaceholderText("run/workflow/...")
        config_grid.addWidget(self.workflow_path_edit, 1, 1, 1, 3)

        config_grid.addWidget(QLabel("API 密钥:"), 2, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        config_grid.addWidget(self.api_key_edit, 2, 1, 1, 2)

        self.show_key_check = QCheckBox("显示明文")
        self.show_key_check.toggled.connect(self._toggle_key_visibility)
        config_grid.addWidget(self.show_key_check, 2, 3)

        config_grid.addWidget(QLabel("实例规格:"), 3, 0)
        self.instance_type_combo = QComboBox()
        self.instance_type_combo.addItems(["default", "plus"])
        config_grid.addWidget(self.instance_type_combo, 3, 1)

        config_grid.setColumnStretch(1, 1)
        config_grid.setColumnStretch(2, 1)
        layout.addWidget(config_group)

        # ── 节点映射区 ──
        mapping_group = QGroupBox("节点映射")
        mapping_grid = QGridLayout(mapping_group)
        mapping_grid.setContentsMargins(12, 16, 12, 10)
        mapping_grid.setSpacing(6)

        mapping_grid.addWidget(QLabel("文本节点ID:"), 0, 0)
        self.text_node_id_edit = QLineEdit("48")
        self.text_node_id_edit.setFixedWidth(80)
        mapping_grid.addWidget(self.text_node_id_edit, 0, 1)

        mapping_grid.addWidget(QLabel("文本字段名:"), 0, 2)
        self.text_field_name_edit = QLineEdit("编辑文本")
        mapping_grid.addWidget(self.text_field_name_edit, 0, 3)

        mapping_grid.addWidget(QLabel("提示词节点ID:"), 1, 0)
        self.prompt_node_id_edit = QLineEdit("49")
        self.prompt_node_id_edit.setFixedWidth(80)
        mapping_grid.addWidget(self.prompt_node_id_edit, 1, 1)

        mapping_grid.addWidget(QLabel("提示词字段名:"), 1, 2)
        self.prompt_field_name_edit = QLineEdit("编辑文本")
        mapping_grid.addWidget(self.prompt_field_name_edit, 1, 3)

        mapping_grid.setColumnStretch(1, 0)
        mapping_grid.setColumnStretch(3, 1)
        layout.addWidget(mapping_group)

        # ── 输入内容区 ──
        input_group = QGroupBox("输入内容")
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(12, 16, 12, 10)
        input_layout.setSpacing(6)

        input_layout.addWidget(QLabel("文本:"))
        self.text_input = QTextEdit()
        self.text_input.setFixedHeight(60)
        self.text_input.setPlaceholderText("输入要合成的文本...")
        input_layout.addWidget(self.text_input)

        input_layout.addWidget(QLabel("声音提示词:"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setFixedHeight(60)
        self.prompt_input.setPlaceholderText("描述声音特征，如：年轻女性，温柔甜美...")
        input_layout.addWidget(self.prompt_input)

        layout.addWidget(input_group)

        # ── 操作按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.load_workflow_btn = QPushButton("加载工作流")
        self.load_workflow_btn.clicked.connect(self._load_workflow_file)
        btn_row.addWidget(self.load_workflow_btn)

        self.start_btn = QPushButton("开始生成")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 7px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #409cff; }
            QPushButton:pressed { background-color: #0071e3; }
            QPushButton:disabled { background-color: #28283a; color: #606070; }
        """)
        self.start_btn.clicked.connect(self._start_generation)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_generation)
        btn_row.addWidget(self.stop_btn)

        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(lambda: self.log_view.clear())
        btn_row.addWidget(self.clear_log_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── 日志区 ──
        log_group = QGroupBox("日志（请求 / 响应 / 状态）")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 16, 12, 10)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a22;
                color: #90b090;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #30304a;
            }
        """)
        log_layout.addWidget(self.log_view)

        layout.addWidget(log_group, 1)

    def _toggle_key_visibility(self, checked: bool):
        self.api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def _load_settings(self):
        """从 SettingsManager 加载 TTS 配置预填各字段"""
        try:
            from config.settings import SettingsManager
            api_cfg = SettingsManager().settings.api

            self.base_url_edit.setText(api_cfg.runninghub_base_url)
            self.workflow_path_edit.setText(api_cfg.runninghub_workflow_path)
            self.api_key_edit.setText(api_cfg.runninghub_api_key)

            idx = self.instance_type_combo.findText(api_cfg.runninghub_instance_type)
            if idx >= 0:
                self.instance_type_combo.setCurrentIndex(idx)

            self.text_node_id_edit.setText(api_cfg.tts_text_node_id)
            self.text_field_name_edit.setText(api_cfg.tts_text_field_name)
            self.prompt_node_id_edit.setText(api_cfg.tts_prompt_node_id)
            self.prompt_field_name_edit.setText(api_cfg.tts_prompt_field_name)

            if api_cfg.tts_default_voice_prompt:
                self.prompt_input.setPlainText(api_cfg.tts_default_voice_prompt)
        except Exception:
            pass

    def _prefill_from_scene(self):
        """从场景数据预填文本"""
        if not self._scene_data:
            return

        # 优先从 audio_config.dialogue 取文本
        audio_config = self._scene_data.get("audio_config")
        if isinstance(audio_config, dict):
            dialogue = audio_config.get("dialogue", "")
            if dialogue:
                self.text_input.setPlainText(dialogue)
                return

        # 回退到 subtitle_text
        subtitle = self._scene_data.get("subtitle_text", "")
        if subtitle:
            self.text_input.setPlainText(subtitle)

    def _load_workflow_file(self):
        """选择工作流 JSON 文件并自动填充节点映射"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择工作流 JSON", "", "JSON 文件 (*.json)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            self._log("已读取工作流文件: " + file_path)

            # 查找 Qwen3TTSVoiceDesign 节点
            voice_node_id = None
            voice_node = None
            for node_id, node in data.items():
                if isinstance(node, dict) and node.get("class_type") == "Qwen3TTSVoiceDesign":
                    voice_node_id = str(node_id)
                    voice_node = node
                    break

            if not voice_node:
                self._log("未找到 Qwen3TTSVoiceDesign 节点。")
                return

            self._log(f"检测到语音设计节点: {voice_node_id}")
            inputs = voice_node.get("inputs", {})

            # 解析文本引用
            text_ref = inputs.get("文本")
            if isinstance(text_ref, list) and text_ref:
                text_node_id = str(text_ref[0])
                self.text_node_id_edit.setText(text_node_id)
                node_data = data.get(text_node_id, {})
                node_inputs = node_data.get("inputs", {}) if isinstance(node_data, dict) else {}
                if "编辑文本" in node_inputs:
                    self.text_field_name_edit.setText("编辑文本")
                    val = node_inputs.get("编辑文本", "")
                    if val and not self.text_input.toPlainText().strip():
                        self.text_input.setPlainText(str(val))

            # 解析提示词引用
            prompt_ref = inputs.get("提示词")
            if isinstance(prompt_ref, list) and prompt_ref:
                prompt_node_id = str(prompt_ref[0])
                self.prompt_node_id_edit.setText(prompt_node_id)
                node_data = data.get(prompt_node_id, {})
                node_inputs = node_data.get("inputs", {}) if isinstance(node_data, dict) else {}
                if "编辑文本" in node_inputs:
                    self.prompt_field_name_edit.setText("编辑文本")
                    val = node_inputs.get("编辑文本", "")
                    if val and not self.prompt_input.toPlainText().strip():
                        self.prompt_input.setPlainText(str(val))

            self._log("节点映射已更新。")
        except Exception as e:
            self._log(f"加载工作流文件失败: {e}")

    def _save_settings_to_config(self):
        """保存当前对话框配置到 SettingsManager"""
        try:
            from config.settings import SettingsManager
            sm = SettingsManager()
            api_cfg = sm.settings.api

            api_cfg.runninghub_base_url = self.base_url_edit.text().strip()
            api_cfg.runninghub_workflow_path = self.workflow_path_edit.text().strip()
            api_cfg.runninghub_api_key = self.api_key_edit.text().strip()
            api_cfg.runninghub_instance_type = self.instance_type_combo.currentText()
            api_cfg.tts_text_node_id = self.text_node_id_edit.text().strip()
            api_cfg.tts_text_field_name = self.text_field_name_edit.text().strip()
            api_cfg.tts_prompt_node_id = self.prompt_node_id_edit.text().strip()
            api_cfg.tts_prompt_field_name = self.prompt_field_name_edit.text().strip()

            sm.save_settings()
        except Exception:
            pass

    def _start_generation(self):
        """开始 TTS 生成"""
        text = self.text_input.toPlainText().strip()
        voice_prompt = self.prompt_input.toPlainText().strip()

        if not text:
            self._log("错误：文本内容为空。")
            return
        if not voice_prompt:
            self._log("错误：声音提示词为空。")
            return
        if not self.api_key_edit.text().strip():
            self._log("错误：API 密钥为空。")
            return
        if not self.workflow_path_edit.text().strip():
            self._log("错误：工作流路径为空。")
            return

        # 保存配置
        self._save_settings_to_config()

        scene_id = self._scene_data.get("id", 0) if self._scene_data else 0

        request = TTSRequest(
            text=text,
            voice_prompt=voice_prompt,
            scene_id=scene_id,
            scene_index=self._scene_index,
            output_dir=self._output_dir,
        )

        # 覆盖 SettingsManager 中的配置（使用对话框中的值）
        from config.settings import SettingsManager
        sm = SettingsManager()
        api_cfg = sm.settings.api
        api_cfg.runninghub_base_url = self.base_url_edit.text().strip()
        api_cfg.runninghub_workflow_path = self.workflow_path_edit.text().strip()
        api_cfg.runninghub_api_key = self.api_key_edit.text().strip()
        api_cfg.runninghub_instance_type = self.instance_type_combo.currentText()
        api_cfg.tts_text_node_id = self.text_node_id_edit.text().strip()
        api_cfg.tts_text_field_name = self.text_field_name_edit.text().strip()
        api_cfg.tts_prompt_node_id = self.prompt_node_id_edit.text().strip()
        api_cfg.tts_prompt_field_name = self.prompt_field_name_edit.text().strip()

        self._worker = TTSWorker(request, parent=self)
        self._worker.log_message.connect(self._log)
        self._worker.tts_completed.connect(self._on_tts_completed)
        self._worker.tts_failed.connect(self._on_tts_failed)
        self._worker.finished.connect(self._on_worker_finished)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._log("========== 开始 TTS 生成 ==========")
        self._worker.start()

    def _stop_generation(self):
        """停止 TTS 生成"""
        if self._worker:
            self._worker.request_stop()
            self._log("已发送停止信号。")

    def _on_tts_completed(self, scene_index: int, audio_path: str):
        self._log(f"生成完成: {audio_path}")
        self._log("========== 任务结束 ==========")
        self.audio_generated.emit(scene_index, audio_path)

    def _on_tts_failed(self, scene_index: int, error_message: str):
        self._log(f"生成失败: {error_message}")
        self._log("========== 任务结束 ==========")

    def _on_worker_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._worker = None

    def _log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_view.append(f"[{timestamp}] {message}")
        # 滚动到底部
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """关闭前保存配置并停止 worker"""
        self._save_settings_to_config()
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(3000)
        super().closeEvent(event)
