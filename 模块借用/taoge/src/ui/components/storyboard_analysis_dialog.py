"""
涛割 - 分镜分析对话框
三步骤向导：角色提取 → 场景分割 → 分镜调整
"""

import re
import json
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QTextEdit, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPainter, QColor, QPen

from .character_extraction_widget import CharacterExtractionWidget
from .scene_adjustment_widget import SceneAdjustmentWidget


class SceneSplitWorker(QThread):
    """场景分割工作线程"""

    split_completed = pyqtSignal(list)  # [{"scene_text": str, "description": str}]
    split_failed = pyqtSignal(str)

    MODE_PARAGRAPH = "paragraph"
    MODE_DEEPSEEK = "deepseek"

    def __init__(self, text: str, characters: List[str], mode: str = "paragraph"):
        super().__init__()
        self.text = text
        self.characters = characters
        self.mode = mode

    def run(self):
        try:
            if self.mode == self.MODE_DEEPSEEK:
                scenes = self._split_by_deepseek(self.text, self.characters)
                if scenes is not None:
                    self.split_completed.emit(scenes)
                    return
                self.split_failed.emit("DeepSeek未返回有效结果，请检查API密钥或尝试快速分割")
            else:
                scenes = self._split_by_paragraph(self.text, self.characters)
                self.split_completed.emit(scenes)
        except Exception as e:
            self.split_failed.emit(str(e))

    def _split_by_deepseek(self, text: str, characters: List[str]):
        """通过 DeepSeek API 分割场景"""
        from config.settings import SettingsManager
        from config.constants import SCENE_SPLIT_PROMPT

        settings = SettingsManager().settings
        api_key = settings.api.deepseek_api_key

        if not api_key:
            raise ValueError("未配置DeepSeek API密钥，请在设置中填写")

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=settings.api.deepseek_base_url,
        )

        truncated = text[:4000]
        prompt = SCENE_SPLIT_PROMPT.format(text=truncated)

        if characters:
            prompt += f"\n\n已知角色：{', '.join(characters)}\n请在每个场景中标注出现的角色。"

        response = client.chat.completions.create(
            model=settings.api.deepseek_model,
            messages=[
                {"role": "system", "content": "你是一个专业的分镜师，擅长将文本拆分为独立的视觉场景。请只返回JSON数组，不要包含其他内容。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )

        content = response.choices[0].message.content.strip()

        # 移除可能的 markdown 代码块标记
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        raw_scenes = json.loads(content)

        if isinstance(raw_scenes, list) and len(raw_scenes) > 0:
            scenes = []
            for i, s in enumerate(raw_scenes):
                if not isinstance(s, dict):
                    continue

                scene_text = s.get('scene_text', '') or s.get('text', '') or s.get('content', '')
                if not scene_text:
                    continue

                scene_chars = s.get('characters', [])
                if not scene_chars:
                    scene_chars = [c for c in characters if c in scene_text]

                scenes.append({
                    'subtitle_text': scene_text,
                    'scene_text': scene_text,
                    'characters': scene_chars,
                    'duration': max(2.0, min(6.0, len(scene_text) / 15)),
                    'name': f"场景 {i + 1}",
                    'description': s.get('description', ''),
                })

            return scenes if scenes else None

        return None

    def _split_by_paragraph(self, text: str, characters: List[str]) -> List[Dict[str, Any]]:
        """按段落/句子分割场景"""
        # 按换行分段
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        # 如果段落太少，按句号进一步分割
        if len(paragraphs) < 3:
            all_sentences = []
            for p in paragraphs:
                sentences = re.split(r'[。！？!?]+', p)
                sentences = [s.strip() for s in sentences if s.strip()]
                all_sentences.extend(sentences)
            paragraphs = all_sentences

        # 将短段落合并（少于10字的与下一个合并）
        merged = []
        buffer = ""
        for p in paragraphs:
            buffer += p
            if len(buffer) >= 10:
                merged.append(buffer)
                buffer = ""
        if buffer:
            if merged:
                merged[-1] += buffer
            else:
                merged.append(buffer)

        # 构建场景数据
        scenes = []
        for i, text_content in enumerate(merged):
            # 检测该场景中出现的角色
            scene_chars = []
            for char_name in characters:
                if char_name in text_content:
                    scene_chars.append(char_name)

            scenes.append({
                'subtitle_text': text_content,
                'scene_text': text_content,
                'characters': scene_chars,
                'duration': max(2.0, min(6.0, len(text_content) / 15)),
                'name': f"场景 {i + 1}",
            })

        return scenes


class StepIndicatorBar(QWidget):
    """步骤指示条"""

    def __init__(self, steps: List[str], parent=None):
        super().__init__(parent)
        self.steps = steps
        self.current_step = 0
        self.setFixedHeight(60)

    def set_step(self, step: int):
        self.current_step = step
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        n = len(self.steps)

        # 计算间距
        step_width = w / n
        y_center = h / 2

        for i in range(n):
            cx = step_width * i + step_width / 2

            # 连线（到下一个步骤）
            if i < n - 1:
                next_cx = step_width * (i + 1) + step_width / 2
                if i < self.current_step:
                    painter.setPen(QPen(QColor(0, 122, 204), 2))
                else:
                    painter.setPen(QPen(QColor(60, 60, 65), 2))
                painter.drawLine(int(cx + 14), int(y_center), int(next_cx - 14), int(y_center))

            # 圆点
            if i < self.current_step:
                # 已完成
                painter.setBrush(QColor(0, 122, 204))
                painter.setPen(Qt.PenStyle.NoPen)
            elif i == self.current_step:
                # 当前
                painter.setBrush(QColor(0, 122, 204))
                painter.setPen(QPen(QColor(0, 122, 204, 100), 3))
            else:
                # 未到达
                painter.setBrush(QColor(50, 50, 55))
                painter.setPen(QPen(QColor(80, 80, 85), 1))

            painter.drawEllipse(int(cx - 12), int(y_center - 12), 24, 24)

            # 步骤数字
            painter.setPen(QColor(255, 255, 255, 220 if i <= self.current_step else 100))
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.drawText(int(cx - 12), int(y_center - 12), 24, 24,
                           Qt.AlignmentFlag.AlignCenter, str(i + 1))

            # 步骤名称
            painter.setPen(QColor(255, 255, 255, 180 if i == self.current_step else 80))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(int(cx - 50), int(y_center + 16), 100, 20,
                           Qt.AlignmentFlag.AlignCenter, self.steps[i])


class SceneSplitWidget(QWidget):
    """场景分割组件 - 步骤2"""

    scenes_generated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_text = ""
        self._characters: List[str] = []
        self._worker: Optional[SceneSplitWorker] = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # 说明
        hint = QLabel("系统将自动分析文案并分割为独立场景")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        layout.addWidget(hint)

        # 文案预览
        preview_label = QLabel("文案预览")
        preview_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        layout.addWidget(preview_label)

        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setMaximumHeight(150)
        self.text_preview.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 8px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
            }
        """)
        layout.addWidget(self.text_preview)

        # 操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.deepseek_split_btn = QPushButton("DeepSeek AI分割")
        self.deepseek_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deepseek_split_btn.clicked.connect(self._start_deepseek_split)
        self.deepseek_split_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgb(0, 140, 220); }
            QPushButton:disabled { background-color: rgba(0, 122, 204, 0.4); }
        """)
        btn_row.addWidget(self.deepseek_split_btn)

        self.split_btn = QPushButton("快速分割")
        self.split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.split_btn.clicked.connect(self._start_paragraph_split)
        self.split_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.12); color: white; }
            QPushButton:disabled { background-color: rgba(255, 255, 255, 0.04); color: rgba(255, 255, 255, 0.3); }
        """)
        btn_row.addWidget(self.split_btn)

        btn_row.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        btn_row.addWidget(self.status_label)

        layout.addLayout(btn_row)

        # 结果提示
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("""
            color: rgba(76, 175, 80, 0.8);
            font-size: 12px;
            padding: 10px;
        """)
        layout.addWidget(self.result_label)

        layout.addStretch()

    def set_source_text(self, text: str):
        self._source_text = text
        self.text_preview.setPlainText(text[:500] + ("..." if len(text) > 500 else ""))

    def set_characters(self, characters: List[str]):
        self._characters = characters

    def _start_deepseek_split(self):
        """通过 DeepSeek AI 分割场景"""
        if not self._source_text:
            self.status_label.setText("没有可分割的文案")
            return

        self.deepseek_split_btn.setEnabled(False)
        self.split_btn.setEnabled(False)
        self.status_label.setText("DeepSeek AI 正在分析...")

        self._worker = SceneSplitWorker(self._source_text, self._characters, mode="deepseek")
        self._worker.split_completed.connect(self._on_split_completed)
        self._worker.split_failed.connect(self._on_split_failed)
        self._worker.start()

    def _start_paragraph_split(self):
        """按段落快速分割场景"""
        if not self._source_text:
            self.status_label.setText("没有可分割的文案")
            return

        self.deepseek_split_btn.setEnabled(False)
        self.split_btn.setEnabled(False)
        self.status_label.setText("正在快速分割...")

        self._worker = SceneSplitWorker(self._source_text, self._characters, mode="paragraph")
        self._worker.split_completed.connect(self._on_split_completed)
        self._worker.split_failed.connect(self._on_split_failed)
        self._worker.start()

    def _on_split_completed(self, scenes: List[Dict[str, Any]]):
        self.deepseek_split_btn.setEnabled(True)
        self.split_btn.setEnabled(True)
        self.status_label.setText("")
        self.result_label.setText(f"已分割为 {len(scenes)} 个场景，点击\"下一步\"进行调整")
        self.scenes_generated.emit(scenes)

    def _on_split_failed(self, error: str):
        self.deepseek_split_btn.setEnabled(True)
        self.split_btn.setEnabled(True)
        self.status_label.setText(f"分割失败: {error}")


class StoryboardAnalysisDialog(QDialog):
    """
    分镜分析对话框 - 三步骤向导
    步骤1: 角色提取
    步骤2: 场景分割
    步骤3: 分镜调整
    """

    analysis_completed = pyqtSignal(int, list, list)  # project_id, scenes, characters

    def __init__(self, project_id: int, source_text: str, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.source_text = source_text
        self._current_step = 0
        self._scenes: List[Dict[str, Any]] = []
        self._characters: List[Dict[str, Any]] = []

        self.setWindowTitle("分镜分析")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(25, 25, 28);
            }
            QLabel {
                color: white;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部标题栏
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet("""
            QFrame {
                background-color: rgb(30, 30, 35);
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("分镜分析")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        layout.addWidget(header)

        # 步骤指示条
        self.step_bar = StepIndicatorBar(["角色提取", "场景分割", "分镜调整"])
        layout.addWidget(self.step_bar)

        # 内容区域
        self.content_stack = QStackedWidget()

        # 步骤1: 角色提取
        self.char_widget = CharacterExtractionWidget()
        self.char_widget.set_source_text(self.source_text)
        self.char_widget.characters_changed.connect(self._on_characters_changed)
        self.content_stack.addWidget(self.char_widget)

        # 步骤2: 场景分割
        self.split_widget = SceneSplitWidget()
        self.split_widget.set_source_text(self.source_text)
        self.split_widget.scenes_generated.connect(self._on_scenes_generated)
        self.content_stack.addWidget(self.split_widget)

        # 步骤3: 分镜调整
        self.adjust_widget = SceneAdjustmentWidget()
        self.adjust_widget.scenes_changed.connect(self._on_scenes_adjusted)
        self.content_stack.addWidget(self.adjust_widget)

        layout.addWidget(self.content_stack, 1)

        # 底部按钮栏
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("""
            QFrame {
                background-color: rgb(30, 30, 35);
                border-top: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        footer_layout.setSpacing(12)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.05); }
        """)
        footer_layout.addWidget(cancel_btn)

        footer_layout.addStretch()

        # 上一步
        self.prev_btn = QPushButton("上一步")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(self._go_prev)
        self.prev_btn.setVisible(False)
        self.prev_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.12); }
        """)
        footer_layout.addWidget(self.prev_btn)

        # 下一步 / 确认
        self.next_btn = QPushButton("下一步")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self._go_next)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgb(0, 140, 220); }
        """)
        footer_layout.addWidget(self.next_btn)

        layout.addWidget(footer)

    def _go_prev(self):
        if self._current_step > 0:
            self._current_step -= 1
            self._update_step()

    def _go_next(self):
        if self._current_step == 0:
            # 步骤1 → 步骤2：传递角色名到分割组件
            self._characters = self.char_widget.get_characters()
            char_names = [c['name'] for c in self._characters]
            self.split_widget.set_characters(char_names)
            self._current_step = 1
            self._update_step()

        elif self._current_step == 1:
            # 步骤2 → 步骤3：传递场景到调整组件
            if not self._scenes:
                QMessageBox.warning(self, "提示", "请先点击\"DeepSeek AI分割\"或\"快速分割\"按钮")
                return
            self.adjust_widget.set_scenes(self._scenes)
            self._current_step = 2
            self._update_step()

        elif self._current_step == 2:
            # 步骤3：确认完成
            final_scenes = self.adjust_widget.get_scenes()
            final_characters = self.char_widget.get_characters()

            if not final_scenes:
                QMessageBox.warning(self, "提示", "没有可用的场景数据")
                return

            self.analysis_completed.emit(
                self.project_id,
                final_scenes,
                final_characters
            )
            self.accept()

    def _update_step(self):
        """更新步骤显示"""
        self.step_bar.set_step(self._current_step)
        self.content_stack.setCurrentIndex(self._current_step)

        self.prev_btn.setVisible(self._current_step > 0)
        self.next_btn.setText("确认" if self._current_step == 2 else "下一步")

    def _on_characters_changed(self, characters: List[Dict[str, Any]]):
        self._characters = characters

    def _on_scenes_generated(self, scenes: List[Dict[str, Any]]):
        self._scenes = scenes

    def _on_scenes_adjusted(self, scenes: List[Dict[str, Any]]):
        self._scenes = scenes
