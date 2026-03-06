"""
涛割 - 剧本执行区（第三栏）
接收选中的 Scene，展示结构化视觉提示词表单 + 音频配置 + AI 生成按钮
"""

from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QPen, QBrush, QColor

from ui import theme


# 画面类型选项
SCENE_TYPES = [
    ('normal', '常规'),
    ('flashback', '闪回'),
    ('transition', '转场'),
    ('montage', '蒙太奇'),
]


# ============================================================
#  _ExpandBtn — 放大/缩小自绘图标按钮
# ============================================================

class _ExpandBtn(QPushButton):
    """放大/缩小切换按钮，自绘展开/收起图标"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._hovered = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("放大")

    def set_expanded(self, v: bool):
        self._expanded = v
        self.setToolTip("缩小" if v else "放大")
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        if self._hovered:
            p.setPen(QPen(QColor(theme.border()), 1))
            p.setBrush(QBrush(QColor(theme.btn_bg_hover())))
        else:
            p.setPen(QPen(QColor(theme.border()), 0.5))
            p.setBrush(QBrush(QColor(theme.bg_secondary())))
        p.drawRoundedRect(r, 6, 6)
        color = QColor(theme.text_primary()) if self._hovered else QColor(theme.text_secondary())
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        a = 5
        if not self._expanded:
            for x, y, dx, dy in [(6,6,1,1),(22,6,-1,1),(6,22,1,-1),(22,22,-1,-1)]:
                p.drawLine(x, y, x + dx * a, y)
                p.drawLine(x, y, x, y + dy * a)
        else:
            for x, y, dx, dy in [(11,11,-1,-1),(17,11,1,-1),(11,17,-1,1),(17,17,1,1)]:
                p.drawLine(x, y, x + dx * a, y)
                p.drawLine(x, y, x, y + dy * a)
        p.end()


class ShotExecutionPanel(QWidget):
    """
    剧本执行区 - 第三栏
    结构化视觉提示词 + 音频配置 + AI 生成
    """

    maximize_requested = pyqtSignal()
    restore_requested = pyqtSignal()

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self._current_scene_index = None
        self._current_scene_data = None
        self._ai_worker = None
        self._is_maximized = False

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 8, 8)
        layout.setSpacing(8)

        # 标题行
        title_row = QHBoxLayout()

        self._maximize_btn = _ExpandBtn()
        self._maximize_btn.clicked.connect(self._on_maximize_clicked)
        title_row.addWidget(self._maximize_btn)

        self._title_label = QLabel("剧本执行")
        self._title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_row.addWidget(self._title_label)
        title_row.addStretch()

        self._scene_info = QLabel("")
        self._scene_info.setFont(QFont("Arial", 10))
        title_row.addWidget(self._scene_info)

        layout.addLayout(title_row)

        # 滚动区域
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._form_widget = QWidget()
        self._form_layout = QVBoxLayout(self._form_widget)
        self._form_layout.setContentsMargins(0, 0, 4, 0)
        self._form_layout.setSpacing(10)

        # === 画面类型 ===
        type_row = QHBoxLayout()
        type_label = QLabel("画面类型")
        type_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        type_row.addWidget(type_label)
        self._type_label = type_label

        self._type_combo = QComboBox()
        for value, display in SCENE_TYPES:
            self._type_combo.addItem(display, value)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self._type_combo, 1)

        self._form_layout.addLayout(type_row)

        # === 结构化视觉提示词 ===
        visual_header = QLabel("结构化视觉提示词")
        visual_header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self._form_layout.addWidget(visual_header)
        self._visual_header = visual_header

        # 五个字段
        self._visual_fields = {}
        field_config = [
            ('subject', '主体', '描述画面中的主要人物/物体'),
            ('action', '动作', '描述主体的动作行为'),
            ('environment', '环境', '描述场景的环境、空间、氛围'),
            ('camera', '镜头', '描述摄影机角度、景别、运镜'),
            ('style', '风格', '描述画面风格、色调、光影'),
        ]

        for key, label_text, placeholder in field_config:
            row_widget = QWidget()
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            label = QLabel(label_text)
            label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            row_layout.addWidget(label)

            edit = QTextEdit()
            edit.setPlaceholderText(placeholder)
            edit.setMaximumHeight(50)
            edit.setFont(QFont("Arial", 11))
            edit.textChanged.connect(lambda k=key: self._on_visual_field_changed(k))
            row_layout.addWidget(edit)

            self._visual_fields[key] = {'label': label, 'edit': edit}
            self._form_layout.addWidget(row_widget)

        # === 音频配置 ===
        audio_header = QLabel("音频配置")
        audio_header.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self._form_layout.addWidget(audio_header)
        self._audio_header = audio_header

        self._audio_fields = {}
        audio_config = [
            ('dialogue', '对白', '角色的台词对白'),
            ('narration', '旁白', '旁白/画外音'),
            ('sfx', '音效', '环境音/特殊音效'),
        ]

        for key, label_text, placeholder in audio_config:
            row_widget = QWidget()
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            label = QLabel(label_text)
            label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            row_layout.addWidget(label)

            edit = QTextEdit()
            edit.setPlaceholderText(placeholder)
            edit.setMaximumHeight(40)
            edit.setFont(QFont("Arial", 11))
            edit.textChanged.connect(lambda k=key: self._on_audio_field_changed(k))
            row_layout.addWidget(edit)

            self._audio_fields[key] = {'label': label, 'edit': edit}
            self._form_layout.addWidget(row_widget)

        # === AI 生成按钮 ===
        self._form_layout.addSpacing(8)

        ai_row = QHBoxLayout()

        self._ai_gen_btn = QPushButton("AI 生成提示词")
        self._ai_gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_gen_btn.clicked.connect(self._ai_generate_prompt)
        ai_row.addWidget(self._ai_gen_btn)

        self._ai_all_btn = QPushButton("AI 全量分析")
        self._ai_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_all_btn.clicked.connect(self._ai_full_analysis)
        ai_row.addWidget(self._ai_all_btn)

        ai_row.addStretch()

        self._form_layout.addLayout(ai_row)

        self._ai_status = QLabel("")
        self._ai_status.setFont(QFont("Arial", 10))
        self._form_layout.addWidget(self._ai_status)

        self._form_layout.addStretch()

        self._scroll.setWidget(self._form_widget)
        layout.addWidget(self._scroll, 1)

        # 占位
        self._placeholder = QLabel("选择分镜查看详情")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setFont(QFont("Arial", 12))
        layout.addWidget(self._placeholder)

        # 初始隐藏表单
        self._scroll.setVisible(False)
        self._placeholder.setVisible(True)

    def load_scene(self, scene_index: int):
        """加载选中的分镜（scene_index 是全局索引）"""
        if not self.data_hub:
            return

        # 在 scenes_data 中查找
        scene_data = None
        for s in self.data_hub.scenes_data:
            if s.get('scene_index') == scene_index:
                scene_data = s
                break

        if not scene_data:
            # 可能是新创建的 scene，从数据库直接查
            from database import session_scope, Scene
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.scene_index == scene_index).first()
                if scene:
                    scene_data = scene.to_dict()

        if not scene_data:
            return

        self._current_scene_index = scene_index
        self._current_scene_data = scene_data

        self._placeholder.setVisible(False)
        self._scroll.setVisible(True)

        self._scene_info.setText(f"分镜 #{scene_index + 1}")

        # 填充画面类型
        scene_type = scene_data.get('scene_type', 'normal')
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i) == scene_type:
                self._type_combo.setCurrentIndex(i)
                break

        # 填充结构化提示词
        visual_struct = scene_data.get('visual_prompt_struct') or {}
        for key, field in self._visual_fields.items():
            edit = field['edit']
            edit.blockSignals(True)
            edit.setPlainText(visual_struct.get(key, ''))
            edit.blockSignals(False)

        # 填充音频配置
        audio_conf = scene_data.get('audio_config') or {}
        for key, field in self._audio_fields.items():
            edit = field['edit']
            edit.blockSignals(True)
            edit.setPlainText(audio_conf.get(key, ''))
            edit.blockSignals(False)

        self._ai_status.setText("")

    def clear(self):
        """清空面板"""
        self._current_scene_index = None
        self._current_scene_data = None
        self._placeholder.setVisible(True)
        self._scroll.setVisible(False)
        self._scene_info.setText("")
        self._ai_status.setText("")

    def _on_maximize_clicked(self):
        if self._is_maximized:
            self.restore_requested.emit()
        else:
            self.maximize_requested.emit()

    def set_maximized(self, maximized: bool):
        self._is_maximized = maximized
        self._maximize_btn.set_expanded(maximized)

    # ==================== 字段变更 ====================

    def _on_type_changed(self, index: int):
        if self._current_scene_index is None or not self.data_hub:
            return
        scene_type = self._type_combo.itemData(index)
        self._update_scene_prop('scene_type', scene_type)

    def _on_visual_field_changed(self, key: str):
        if self._current_scene_index is None or not self.data_hub:
            return

        # 收集所有 visual 字段
        struct = {}
        for k, field in self._visual_fields.items():
            struct[k] = field['edit'].toPlainText()

        self._update_scene_prop('visual_prompt_struct', struct)

    def _on_audio_field_changed(self, key: str):
        if self._current_scene_index is None or not self.data_hub:
            return

        config = {}
        for k, field in self._audio_fields.items():
            config[k] = field['edit'].toPlainText()

        self._update_scene_prop('audio_config', config)

    def _update_scene_prop(self, prop: str, value):
        """通过 DataHub 持久化"""
        if not self.data_hub or self._current_scene_index is None:
            return

        # 找到在 scenes_data 中的索引
        for i, s in enumerate(self.data_hub.scenes_data):
            if s.get('scene_index') == self._current_scene_index:
                self.data_hub.update_scene_property(i, prop, value)
                return

        # 如果不在 scenes_data 中，直接写数据库
        scene_data = self._current_scene_data
        if scene_data and scene_data.get('id'):
            from database import session_scope, Scene
            from sqlalchemy.orm.attributes import flag_modified
            with session_scope() as session:
                scene = session.query(Scene).get(scene_data['id'])
                if scene and hasattr(scene, prop):
                    setattr(scene, prop, value)
                    if prop in ('visual_prompt_struct', 'audio_config'):
                        flag_modified(scene, prop)

    # ==================== AI 生成 ====================

    def _ai_generate_prompt(self):
        """AI 生成结构化视觉提示词"""
        if not self._current_scene_data:
            return

        text = self._current_scene_data.get('subtitle_text', '')
        if not text:
            QMessageBox.warning(self, "提示", "该分镜没有文本内容")
            return

        self._ai_gen_btn.setEnabled(False)
        self._ai_status.setText("AI 生成中...")

        from services.ai_analyzer import AIAnalysisWorker
        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_IMAGE_PROMPT,
            text,
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_prompt_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def _ai_full_analysis(self):
        """AI 全量分析"""
        if not self._current_scene_data:
            return

        text = self._current_scene_data.get('subtitle_text', '')
        if not text:
            QMessageBox.warning(self, "提示", "该分镜没有文本内容")
            return

        self._ai_all_btn.setEnabled(False)
        self._ai_status.setText("AI 全量分析中...")

        from services.ai_analyzer import AIAnalysisWorker
        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_ALL,
            text,
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_full_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def _on_ai_prompt_completed(self, analysis_type: str, result: dict):
        self._ai_gen_btn.setEnabled(True)
        self._ai_status.setText("生成完成")

        image_prompt = result.get('image_prompt', '')
        if image_prompt:
            # 简单地填入 subject 字段
            self._visual_fields['subject']['edit'].setPlainText(image_prompt)
            # 也保存到 image_prompt
            if self.data_hub and self._current_scene_index is not None:
                self._update_scene_prop('image_prompt', image_prompt)

    def _on_ai_full_completed(self, analysis_type: str, result: dict):
        self._ai_all_btn.setEnabled(True)
        self._ai_status.setText("全量分析完成")

        # 填充视觉字段
        image_prompt = result.get('image_prompt', '')
        if image_prompt:
            self._visual_fields['subject']['edit'].setPlainText(image_prompt)

        camera = result.get('camera_motion', '')
        if camera:
            self._visual_fields['camera']['edit'].setPlainText(camera)

        actions = result.get('character_actions', '')
        if actions:
            self._visual_fields['action']['edit'].setPlainText(actions)

        # 保存
        if self.data_hub and self._current_scene_index is not None:
            if image_prompt:
                self._update_scene_prop('image_prompt', image_prompt)
            video_prompt = result.get('video_prompt', '')
            if video_prompt:
                self._update_scene_prop('video_prompt', video_prompt)

    def _on_ai_failed(self, analysis_type: str, error: str):
        self._ai_gen_btn.setEnabled(True)
        self._ai_all_btn.setEnabled(True)
        self._ai_status.setText(f"失败: {error}")

    # ==================== 主题 ====================

    def apply_theme(self):
        self._title_label.setStyleSheet(f"color: {theme.text_primary()};")
        self._scene_info.setStyleSheet(f"color: {theme.text_tertiary()}; background: transparent;")
        self._placeholder.setStyleSheet(f"color: {theme.text_tertiary()};")
        self._ai_status.setStyleSheet(f"color: {theme.text_tertiary()}; background: transparent;")
        self._visual_header.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")
        self._audio_header.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")
        self._type_label.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")

        self._maximize_btn.update()

        self._scroll.setStyleSheet(theme.scroll_area_style())

        edit_style = f"""
            QTextEdit {{
                background-color: {theme.bg_primary()};
                color: {theme.text_primary()};
                border: 1px solid {theme.border()};
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
            }}
            QTextEdit:focus {{
                border-color: {theme.accent()};
            }}
        """

        label_style = f"color: {theme.text_secondary()}; background: transparent;"

        for field in self._visual_fields.values():
            field['edit'].setStyleSheet(edit_style)
            field['label'].setStyleSheet(label_style)

        for field in self._audio_fields.values():
            field['edit'].setStyleSheet(edit_style)
            field['label'].setStyleSheet(label_style)

        self._type_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.bg_primary()};
                color: {theme.text_primary()};
                border: 1px solid {theme.border()};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)

        self._ai_gen_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()}; color: white;
                border: none; border-radius: 8px;
                padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
            QPushButton:disabled {{ background-color: {theme.bg_tertiary()}; color: {theme.text_tertiary()}; }}
        """)

        self._ai_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.success()}; color: white;
                border: none; border-radius: 8px;
                padding: 8px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #34c759; }}
            QPushButton:disabled {{ background-color: {theme.bg_tertiary()}; color: {theme.text_tertiary()}; }}
        """)
