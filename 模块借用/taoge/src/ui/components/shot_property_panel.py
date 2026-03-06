"""
涛割 - 镜头属性面板
右侧属性编辑区：角色、视觉设定、叙事内容等
"""

import os
from typing import Optional, List, Dict, Any, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QTextEdit, QComboBox,
    QSlider, QCheckBox, QSizePolicy, QGridLayout, QFileDialog,
    QDialog, QListWidget, QListWidgetItem, QDialogButtonBox,
    QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QAction

from ui.pixmap_cache import PixmapCache
from services.ai_analyzer import AIAnalysisWorker


class CollapsibleSection(QFrame):
    """可折叠的属性区块"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._is_expanded = True

        self.setObjectName("collapsibleSection")
        self.setStyleSheet("""
            QFrame#collapsibleSection {
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 6px;
                margin: 2px 0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        self.header = QPushButton(f"▼  {title}")
        self.header.setCheckable(True)
        self.header.setChecked(True)
        self.header.clicked.connect(self._toggle)
        self.header.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.9);
                border: none;
                text-align: left;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        layout.addWidget(self.header)

        # 内容区域
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 0, 12, 12)
        self.content_layout.setSpacing(8)
        layout.addWidget(self.content)

        self._title = title

    def _toggle(self):
        self._is_expanded = self.header.isChecked()
        self.content.setVisible(self._is_expanded)
        arrow = "▼" if self._is_expanded else "▶"
        self.header.setText(f"{arrow}  {self._title}")

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


class PropertyRow(QWidget):
    """属性行：标签 + 控件"""

    def __init__(self, label: str, widget: QWidget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        label_widget = QLabel(label)
        label_widget.setFixedWidth(70)
        label_widget.setStyleSheet("""
            color: rgba(255, 255, 255, 0.6);
            font-size: 11px;
        """)
        layout.addWidget(label_widget)

        layout.addWidget(widget, 1)


class ShotPropertyPanel(QFrame):
    """镜头属性面板 - 右侧"""

    property_changed = pyqtSignal(str, object)  # property_name, value
    generate_image_requested = pyqtSignal()
    generate_video_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_scene: Optional[Dict[str, Any]] = None
        self._updating = False  # 防止循环更新
        self._ai_worker: Optional[AIAnalysisWorker] = None

        self.setObjectName("shotPropertyPanel")
        self.setStyleSheet("""
            QFrame#shotPropertyPanel {
                background-color: rgb(28, 28, 30);
                border-left: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.setMinimumWidth(320)
        self.setMaximumWidth(400)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("""
            QFrame {
                background-color: rgb(35, 35, 38);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)

        title = QLabel("镜头属性")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.scene_index_label = QLabel("#01")
        self.scene_index_label.setStyleSheet("""
            color: rgb(0, 180, 255);
            font-family: Consolas;
            font-size: 14px;
            font-weight: bold;
        """)
        header_layout.addWidget(self.scene_index_label)

        layout.addWidget(header)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
            }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.02);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        # === 叙事内容区块 ===
        narrative_section = CollapsibleSection("叙事内容")

        # 字幕文本
        subtitle_label = QLabel("字幕文本")
        subtitle_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        narrative_section.add_widget(subtitle_label)

        self.subtitle_edit = QTextEdit()
        self.subtitle_edit.setFixedHeight(60)
        self.subtitle_edit.setPlaceholderText("场景字幕内容...")
        self.subtitle_edit.textChanged.connect(lambda: self._emit_change("subtitle_text", self.subtitle_edit.toPlainText()))
        self.subtitle_edit.setStyleSheet(self._get_textedit_style())
        narrative_section.add_widget(self.subtitle_edit)

        # 时间信息
        time_row = QHBoxLayout()
        time_row.setSpacing(10)

        self.start_time_edit = QLineEdit()
        self.start_time_edit.setPlaceholderText("开始时间")
        self.start_time_edit.setStyleSheet(self._get_input_style())
        time_row.addWidget(QLabel("开始"))
        time_row.addWidget(self.start_time_edit)

        self.end_time_edit = QLineEdit()
        self.end_time_edit.setPlaceholderText("结束时间")
        self.end_time_edit.setStyleSheet(self._get_input_style())
        time_row.addWidget(QLabel("结束"))
        time_row.addWidget(self.end_time_edit)

        for i in range(time_row.count()):
            item = time_row.itemAt(i)
            if item.widget() and isinstance(item.widget(), QLabel):
                item.widget().setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 10px;")

        narrative_section.add_layout(time_row)

        content_layout.addWidget(narrative_section)

        # === 视觉设定区块 ===
        visual_section = CollapsibleSection("视觉设定")

        # 图像提示词
        prompt_label = QLabel("图像提示词")
        prompt_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        visual_section.add_widget(prompt_label)

        self.image_prompt_edit = QTextEdit()
        self.image_prompt_edit.setFixedHeight(80)
        self.image_prompt_edit.setPlaceholderText("描述场景的视觉内容...")
        self.image_prompt_edit.textChanged.connect(lambda: self._emit_change("image_prompt", self.image_prompt_edit.toPlainText()))
        self.image_prompt_edit.setStyleSheet(self._get_textedit_style())
        visual_section.add_widget(self.image_prompt_edit)

        # 一键分析画面提示词按钮
        self.ai_image_prompt_btn = QPushButton("一键分析画面提示词")
        self.ai_image_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_image_prompt_btn.clicked.connect(self._ai_generate_image_prompt)
        self.ai_image_prompt_btn.setStyleSheet(self._get_ai_btn_style())
        visual_section.add_widget(self.ai_image_prompt_btn)

        # 首帧图片
        frame_row = QHBoxLayout()
        frame_row.setSpacing(8)

        self.start_frame_preview = QLabel()
        self.start_frame_preview.setFixedSize(64, 36)
        self.start_frame_preview.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        self.start_frame_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_frame_preview.setText("首帧")
        frame_row.addWidget(self.start_frame_preview)

        self.select_frame_btn = QPushButton("选择图片")
        self.select_frame_btn.clicked.connect(self._select_start_frame)
        self.select_frame_btn.setStyleSheet(self._get_btn_style())
        frame_row.addWidget(self.select_frame_btn)

        frame_row.addStretch()

        visual_section.add_layout(frame_row)

        content_layout.addWidget(visual_section)

        # === 视频提示词区块 ===
        video_section = CollapsibleSection("视频提示词")

        # 视频提示词文本
        video_prompt_label = QLabel("视频提示词")
        video_prompt_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        video_section.add_widget(video_prompt_label)

        self.video_prompt_edit = QTextEdit()
        self.video_prompt_edit.setFixedHeight(100)
        self.video_prompt_edit.setPlaceholderText("综合性的视频提示词...")
        self.video_prompt_edit.textChanged.connect(lambda: self._emit_change("video_prompt", self.video_prompt_edit.toPlainText()))
        self.video_prompt_edit.setStyleSheet(self._get_textedit_style())
        video_section.add_widget(self.video_prompt_edit)

        # 5个只读详情标签
        detail_style = """
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 10px;
                padding: 4px 8px;
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 3px;
            }
        """

        self.camera_motion_label = QLabel("运镜方式：-")
        self.camera_motion_label.setStyleSheet(detail_style)
        self.camera_motion_label.setWordWrap(True)
        video_section.add_widget(self.camera_motion_label)

        self.shot_size_label = QLabel("景别：-")
        self.shot_size_label.setStyleSheet(detail_style)
        self.shot_size_label.setWordWrap(True)
        video_section.add_widget(self.shot_size_label)

        self.character_actions_label = QLabel("角色动作：-")
        self.character_actions_label.setStyleSheet(detail_style)
        self.character_actions_label.setWordWrap(True)
        video_section.add_widget(self.character_actions_label)

        self.expression_changes_label = QLabel("表情变化：-")
        self.expression_changes_label.setStyleSheet(detail_style)
        self.expression_changes_label.setWordWrap(True)
        video_section.add_widget(self.expression_changes_label)

        self.vfx_analysis_label = QLabel("特效分析：-")
        self.vfx_analysis_label.setStyleSheet(detail_style)
        self.vfx_analysis_label.setWordWrap(True)
        video_section.add_widget(self.vfx_analysis_label)

        # 生成视频提示词按钮
        self.ai_video_prompt_btn = QPushButton("生成视频提示词")
        self.ai_video_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_video_prompt_btn.clicked.connect(self._ai_generate_video_prompt)
        self.ai_video_prompt_btn.setStyleSheet(self._get_ai_btn_style())
        video_section.add_widget(self.ai_video_prompt_btn)

        content_layout.addWidget(video_section)

        # === 角色区块 ===
        character_section = CollapsibleSection("场景角色")

        self.characters_container = QWidget()
        self.characters_layout = QVBoxLayout(self.characters_container)
        self.characters_layout.setContentsMargins(0, 0, 0, 0)
        self.characters_layout.setSpacing(4)

        # 占位提示
        self.no_character_label = QLabel("暂无角色")
        self.no_character_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.3);
            font-size: 11px;
            padding: 10px;
        """)
        self.no_character_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.characters_layout.addWidget(self.no_character_label)

        character_section.add_widget(self.characters_container)

        # 一致性模式选择
        consistency_row = QHBoxLayout()
        consistency_row.setSpacing(8)

        consistency_label = QLabel("一致性模式")
        consistency_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        consistency_label.setFixedWidth(70)
        consistency_row.addWidget(consistency_label)

        self.consistency_combo = QComboBox()
        self.consistency_combo.addItems(["关闭", "参考图模式", "角色ID模式", "LoRA模式"])
        self.consistency_combo.currentTextChanged.connect(
            lambda v: self._emit_change("consistency_mode", v)
        )
        self.consistency_combo.setStyleSheet(self._get_combo_style())
        consistency_row.addWidget(self.consistency_combo, 1)

        character_section.add_layout(consistency_row)

        # 一致性强度
        cs_container = QWidget()
        cs_layout = QHBoxLayout(cs_container)
        cs_layout.setContentsMargins(0, 0, 0, 0)
        cs_layout.setSpacing(10)

        cs_label = QLabel("一致性强度")
        cs_label.setFixedWidth(70)
        cs_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        cs_layout.addWidget(cs_label)

        self.consistency_slider = QSlider(Qt.Orientation.Horizontal)
        self.consistency_slider.setRange(0, 100)
        self.consistency_slider.setValue(80)
        self.consistency_slider.valueChanged.connect(
            lambda v: self._emit_change("consistency_strength", v / 100.0)
        )
        self.consistency_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.1);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: rgb(139, 92, 246);
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: rgb(139, 92, 246);
                border-radius: 2px;
            }
        """)
        cs_layout.addWidget(self.consistency_slider, 1)

        self.consistency_value_label = QLabel("80%")
        self.consistency_value_label.setFixedWidth(35)
        self.consistency_value_label.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 11px;")
        self.consistency_slider.valueChanged.connect(
            lambda v: self.consistency_value_label.setText(f"{v}%")
        )
        cs_layout.addWidget(self.consistency_value_label)

        character_section.add_widget(cs_container)

        # 添加角色按钮
        add_char_btn = QPushButton("+ 从资产库添加角色")
        add_char_btn.clicked.connect(self._show_character_picker)
        add_char_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgb(0, 150, 200);
                border: 1px dashed rgba(0, 150, 200, 0.5);
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(0, 150, 200, 0.1);
            }
        """)
        character_section.add_widget(add_char_btn)

        content_layout.addWidget(character_section)

        # === AI标签区块 ===
        tags_section = CollapsibleSection("AI标签")

        self.tags_container = QWidget()
        self.tags_flow_layout = QVBoxLayout(self.tags_container)
        self.tags_flow_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_flow_layout.setSpacing(6)

        tags_section.add_widget(self.tags_container)

        content_layout.addWidget(tags_section)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # 底部操作按钮
        action_bar = QFrame()
        action_bar.setFixedHeight(60)
        action_bar.setStyleSheet("""
            QFrame {
                background-color: rgb(35, 35, 38);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(15, 10, 15, 10)
        action_layout.setSpacing(10)

        self.ai_all_btn = QPushButton("一键生成")
        self.ai_all_btn.clicked.connect(self._ai_analyze_all)
        self.ai_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_all_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(139, 92, 246, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(139, 92, 246, 1.0); }
            QPushButton:disabled { background-color: rgba(139, 92, 246, 0.3); }
        """)
        action_layout.addWidget(self.ai_all_btn)

        self.gen_image_btn = QPushButton("生成图片")
        self.gen_image_btn.clicked.connect(self.generate_image_requested.emit)
        self.gen_image_btn.setStyleSheet(self._get_action_btn_style())
        action_layout.addWidget(self.gen_image_btn)

        self.gen_video_btn = QPushButton("生成视频")
        self.gen_video_btn.clicked.connect(self.generate_video_requested.emit)
        self.gen_video_btn.setStyleSheet(self._get_action_btn_style(primary=True))
        action_layout.addWidget(self.gen_video_btn)

        layout.addWidget(action_bar)

    def _get_input_style(self):
        return """
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px 10px;
                color: white;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: rgb(0, 122, 204);
            }
        """

    def _get_textedit_style(self):
        return """
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 11px;
            }
            QTextEdit:focus {
                border-color: rgb(0, 122, 204);
            }
        """

    def _get_combo_style(self):
        return """
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px 10px;
                color: white;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: rgba(255, 255, 255, 0.2);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(255, 255, 255, 0.5);
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(45, 45, 48);
                border: 1px solid rgba(255, 255, 255, 0.1);
                selection-background-color: rgb(0, 122, 204);
                color: white;
            }
        """

    def _get_btn_style(self):
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
        """

    def _get_ai_btn_style(self):
        return """
            QPushButton {
                background-color: rgba(139, 92, 246, 0.15);
                color: rgba(139, 92, 246, 0.9);
                border: 1px solid rgba(139, 92, 246, 0.3);
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(139, 92, 246, 0.25);
                color: rgb(139, 92, 246);
            }
            QPushButton:disabled {
                background-color: rgba(139, 92, 246, 0.05);
                color: rgba(139, 92, 246, 0.3);
                border-color: rgba(139, 92, 246, 0.1);
            }
        """

    def _get_action_btn_style(self, primary=False):
        if primary:
            return """
                QPushButton {
                    background-color: rgb(0, 122, 204);
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 10px 20px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgb(0, 140, 220);
                }
                QPushButton:disabled {
                    background-color: rgba(0, 122, 204, 0.4);
                }
            """
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """

    def set_scene(self, index: int, scene_data: Dict[str, Any]):
        """设置当前场景数据"""
        self._updating = True
        self.current_scene = scene_data

        # 更新场景序号
        self.scene_index_label.setText(f"#{index + 1:02d}")

        # 更新叙事内容
        self.subtitle_edit.setPlainText(scene_data.get("subtitle_text", ""))
        self.start_time_edit.setText(scene_data.get("start_time", ""))
        self.end_time_edit.setText(scene_data.get("end_time", ""))

        # 更新视觉设定
        self.image_prompt_edit.setPlainText(scene_data.get("image_prompt", ""))

        # 更新首帧预览
        start_frame = scene_data.get("start_frame_path")
        if start_frame:
            scaled = PixmapCache.instance().get_scaled(start_frame, 64, 36)
            if scaled:
                self.start_frame_preview.setPixmap(scaled)
            else:
                self.start_frame_preview.setText("首帧")
        else:
            self.start_frame_preview.setText("首帧")

        # 更新视频提示词
        self.video_prompt_edit.setPlainText(scene_data.get("video_prompt", ""))

        # 从generation_params恢复5个详情标签
        gen_params = scene_data.get("generation_params") or {}
        self.camera_motion_label.setText(f"运镜方式：{gen_params.get('camera_motion', '-')}")
        self.shot_size_label.setText(f"景别：{gen_params.get('shot_size', '-')}")
        self.character_actions_label.setText(f"角色动作：{gen_params.get('character_actions', '-')}")
        self.expression_changes_label.setText(f"表情变化：{gen_params.get('expression_changes', '-')}")
        self.vfx_analysis_label.setText(f"特效分析：{gen_params.get('vfx_analysis', '-')}")

        # 更新AI标签
        self._update_tags(scene_data.get("ai_tags", {}))

        # 更新一致性参数（从generation_params恢复）
        gen_params = scene_data.get("generation_params") or {}
        consistency_mode = gen_params.get("consistency_mode", "关闭")
        idx = self.consistency_combo.findText(consistency_mode)
        if idx >= 0:
            self.consistency_combo.setCurrentIndex(idx)

        consistency_strength = int(gen_params.get("consistency_strength", 0.8) * 100)
        self.consistency_slider.setValue(consistency_strength)

        self._updating = False

    def _update_tags(self, ai_tags: Dict[str, List[str]]):
        """更新AI标签显示"""
        # 清空现有标签
        while self.tags_flow_layout.count():
            item = self.tags_flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from config.constants import TAG_CATEGORY_COLORS, TAG_FONT_COLORS

        for category, tags in ai_tags.items():
            if not tags:
                continue

            # 类别标签
            cat_label = QLabel(category)
            cat_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.5);
                font-size: 10px;
                margin-top: 4px;
            """)
            self.tags_flow_layout.addWidget(cat_label)

            # 标签流
            tags_row = QHBoxLayout()
            tags_row.setSpacing(4)
            tags_row.setContentsMargins(0, 0, 0, 0)

            for tag in tags:
                bg_color = TAG_CATEGORY_COLORS.get(category, "rgba(100, 100, 100, {alpha})").format(alpha=0.3)
                font_color = TAG_FONT_COLORS.get(category, "#FFFFFF")
                tag_label = QLabel(tag)
                tag_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: {bg_color};
                        color: {font_color};
                        padding: 3px 8px;
                        border-radius: 10px;
                        font-size: 10px;
                    }}
                """)
                tags_row.addWidget(tag_label)

            tags_row.addStretch()

            tags_widget = QWidget()
            tags_widget.setLayout(tags_row)
            self.tags_flow_layout.addWidget(tags_widget)

    def _emit_change(self, prop: str, value):
        """发送属性变更信号"""
        if not self._updating:
            self.property_changed.emit(prop, value)

    def _select_start_frame(self):
        """选择首帧图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择首帧图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self._emit_change("start_frame_path", file_path)
            scaled = PixmapCache.instance().get_scaled(file_path, 64, 36)
            if scaled:
                self.start_frame_preview.setPixmap(scaled)

    # ==================== 角色一致性控制 ====================

    def _show_character_picker(self):
        """显示角色选择对话框"""
        try:
            from database.session import session_scope
            from database.models import Character

            dialog = QDialog(self)
            dialog.setWindowTitle("选择角色")
            dialog.setFixedSize(400, 500)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: rgb(30, 30, 30);
                }
                QLabel {
                    color: white;
                }
            """)

            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(15)

            # 搜索框
            search = QLineEdit()
            search.setPlaceholderText("搜索角色...")
            search.setStyleSheet(self._get_input_style())
            layout.addWidget(search)

            # 角色列表
            list_widget = QListWidget()
            list_widget.setStyleSheet("""
                QListWidget {
                    background-color: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    color: white;
                }
                QListWidget::item {
                    padding: 10px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                }
                QListWidget::item:selected {
                    background-color: rgba(0, 122, 204, 0.3);
                }
                QListWidget::item:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                }
            """)

            # 加载角色
            characters = []
            with session_scope() as session:
                chars = session.query(Character).filter(
                    Character.is_active == True
                ).order_by(Character.name).all()

                for char in chars:
                    char_dict = char.to_dict()
                    characters.append(char_dict)

                    type_names = {
                        "human": "人物", "animal": "动物",
                        "creature": "生物", "object": "物体",
                        "background": "背景"
                    }
                    type_name = type_names.get(char.character_type, char.character_type)
                    display = f"{char.name}  ({type_name})"
                    if char.appearance:
                        display += f"\n  {char.appearance[:30]}..."

                    item = QListWidgetItem(display)
                    item.setData(Qt.ItemDataRole.UserRole, char_dict)
                    list_widget.addItem(item)

            # 搜索过滤
            def filter_list(text):
                text = text.lower()
                for i in range(list_widget.count()):
                    item = list_widget.item(i)
                    visible = text in item.text().lower()
                    item.setHidden(not visible)

            search.textChanged.connect(filter_list)
            layout.addWidget(list_widget)

            # 按钮
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 4px;
                    padding: 8px 20px;
                    color: white;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.15);
                }
            """)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected = list_widget.currentItem()
                if selected:
                    char_data = selected.data(Qt.ItemDataRole.UserRole)
                    self._add_character_to_scene(char_data)

        except Exception as e:
            print(f"打开角色选择器失败: {e}")

    def _add_character_to_scene(self, char_data: Dict[str, Any]):
        """添加角色到当前场景"""
        # 隐藏空提示
        self.no_character_label.setVisible(False)

        # 创建角色卡片
        card = self._create_character_card(char_data)
        self.characters_layout.addWidget(card)

        # 通知变更
        self._emit_change("scene_characters_add", char_data)

    def _create_character_card(self, char_data: Dict[str, Any]) -> QFrame:
        """创建场景内的角色卡片（含参考图管理）"""
        card = QFrame()
        card.setObjectName("characterCard")
        card.setStyleSheet("""
            QFrame#characterCard {
                background-color: rgba(139, 92, 246, 0.1);
                border: 1px solid rgba(139, 92, 246, 0.3);
                border-radius: 6px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        # 第一行：缩略图 + 名称 + 操作按钮
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # 缩略图
        thumb = QLabel()
        thumb.setFixedSize(36, 36)
        thumb.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        """)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ref_img = char_data.get('main_reference_image', '')
        if ref_img and os.path.exists(ref_img):
            scaled = PixmapCache.instance().get_scaled(ref_img, 36, 36)
            if scaled:
                thumb.setPixmap(scaled)
            else:
                thumb.setText("?")
        else:
            thumb.setText("?")
            thumb.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                font-size: 18px;
                color: rgba(255, 255, 255, 0.3);
            """)

        top_row.addWidget(thumb)

        # 信息
        info = QVBoxLayout()
        info.setSpacing(2)

        name = QLabel(char_data.get('name', '未知'))
        name.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        info.addWidget(name)

        ref_count = len(char_data.get('reference_images') or [])
        type_names = {
            "human": "人物", "animal": "动物",
            "creature": "生物", "object": "物体",
            "background": "背景"
        }
        type_name = type_names.get(char_data.get('character_type', ''), '')
        desc = f"{type_name}  |  {ref_count}张参考图" if ref_count else type_name
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 10px;")
        info.addWidget(desc_label)

        top_row.addLayout(info, 1)

        # 管理参考图按钮
        char_id = char_data.get('id')
        manage_btn = QPushButton("...")
        manage_btn.setFixedSize(24, 24)
        manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        manage_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.5);
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: white;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        manage_btn.clicked.connect(lambda checked, cid=char_id, cd=char_data, c=card: self._show_character_menu(cid, cd, c, manage_btn))
        top_row.addWidget(manage_btn)

        # 移除按钮
        remove_btn = QPushButton("x")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.4);
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: rgb(239, 68, 68);
            }
        """)
        remove_btn.clicked.connect(lambda: self._remove_character_card(card, char_id))
        top_row.addWidget(remove_btn)

        card_layout.addLayout(top_row)

        # 参考图缩略图行（最多显示4张）
        ref_images = char_data.get('reference_images') or []
        main_ref = char_data.get('main_reference_image', '')
        if ref_images:
            refs_row = QHBoxLayout()
            refs_row.setSpacing(4)
            refs_row.setContentsMargins(0, 0, 0, 0)

            for i, img_path in enumerate(ref_images[:4]):
                ref_thumb = QLabel()
                ref_thumb.setFixedSize(40, 40)
                ref_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)

                is_main = (img_path == main_ref)
                border_color = "rgb(139, 92, 246)" if is_main else "rgba(255, 255, 255, 0.1)"
                border_width = "2px" if is_main else "1px"
                ref_thumb.setStyleSheet(f"""
                    QLabel {{
                        background-color: rgba(255, 255, 255, 0.05);
                        border: {border_width} solid {border_color};
                        border-radius: 3px;
                    }}
                """)

                if img_path and os.path.exists(img_path):
                    scaled = PixmapCache.instance().get_scaled(img_path, 40, 40)
                    if scaled:
                        ref_thumb.setPixmap(scaled)

                refs_row.addWidget(ref_thumb)

            if len(ref_images) > 4:
                more_label = QLabel(f"+{len(ref_images) - 4}")
                more_label.setStyleSheet("""
                    color: rgba(255, 255, 255, 0.4);
                    font-size: 10px;
                """)
                refs_row.addWidget(more_label)

            refs_row.addStretch()
            card_layout.addLayout(refs_row)

        return card

    def _show_character_menu(self, char_id: int, char_data: dict, card: QFrame, btn: QPushButton):
        """显示角色操作菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(45, 45, 48);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                color: white;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 122, 204, 0.5);
            }
        """)

        add_ref_action = menu.addAction("添加参考图")
        add_ref_action.triggered.connect(lambda: self._add_reference_image(char_id, char_data, card))

        ref_images = char_data.get('reference_images') or []
        if ref_images:
            view_refs_action = menu.addAction("管理参考图...")
            view_refs_action.triggered.connect(lambda: self._show_reference_manager(char_id, char_data, card))

        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _add_reference_image(self, char_id: int, char_data: dict, card: QFrame):
        """为角色添加参考图"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择参考图",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        if not file_path:
            return

        try:
            from services.controllers.material_controller import MaterialController
            ctrl = MaterialController()
            stored_path = ctrl.add_reference_image(char_id, file_path)
            if stored_path:
                # 更新本地 char_data
                refs = list(char_data.get('reference_images') or [])
                refs.append(stored_path)
                char_data['reference_images'] = refs
                if not char_data.get('main_reference_image'):
                    char_data['main_reference_image'] = stored_path

                # 刷新角色卡片
                self._refresh_character_card(card, char_data)
        except Exception as e:
            print(f"添加参考图失败: {e}")

    def _show_reference_manager(self, char_id: int, char_data: dict, card: QFrame):
        """显示参考图管理对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"管理参考图 - {char_data.get('name', '')}")
        dialog.setFixedSize(500, 400)
        dialog.setStyleSheet("""
            QDialog { background-color: rgb(30, 30, 30); }
            QLabel { color: white; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        hint_label = QLabel("点击图片设为主参考图，右键可删除")
        hint_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        layout.addWidget(hint_label)

        # 参考图网格
        grid_container = QWidget()
        grid = QGridLayout(grid_container)
        grid.setSpacing(8)

        ref_images = list(char_data.get('reference_images') or [])
        main_ref = char_data.get('main_reference_image', '')

        def make_set_main(path):
            def handler():
                try:
                    from services.controllers.material_controller import MaterialController
                    ctrl = MaterialController()
                    ctrl.set_main_reference(char_id, path)
                    char_data['main_reference_image'] = path
                    self._refresh_character_card(card, char_data)
                    dialog.accept()
                except Exception as e:
                    print(f"设置主参考图失败: {e}")
            return handler

        def make_remove(path):
            def handler():
                try:
                    from services.controllers.material_controller import MaterialController
                    ctrl = MaterialController()
                    ctrl.remove_reference_image(char_id, path)
                    if path in ref_images:
                        ref_images.remove(path)
                    char_data['reference_images'] = ref_images
                    if char_data.get('main_reference_image') == path:
                        char_data['main_reference_image'] = ref_images[0] if ref_images else None
                    self._refresh_character_card(card, char_data)
                    dialog.accept()
                except Exception as e:
                    print(f"删除参考图失败: {e}")
            return handler

        for i, img_path in enumerate(ref_images):
            row, col = divmod(i, 4)

            img_frame = QFrame()
            is_main = (img_path == main_ref)
            border_color = "rgb(139, 92, 246)" if is_main else "rgba(255, 255, 255, 0.1)"
            img_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(255, 255, 255, 0.03);
                    border: 2px solid {border_color};
                    border-radius: 6px;
                }}
            """)
            frame_layout = QVBoxLayout(img_frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(4)

            img_label = QLabel()
            img_label.setFixedSize(100, 100)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if os.path.exists(img_path):
                scaled = PixmapCache.instance().get_scaled(img_path, 100, 100)
                if scaled:
                    img_label.setPixmap(scaled)
            frame_layout.addWidget(img_label, alignment=Qt.AlignmentFlag.AlignCenter)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(4)

            set_main_btn = QPushButton("主图" if not is_main else "当前主图")
            set_main_btn.setEnabled(not is_main)
            set_main_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(139, 92, 246, 0.2);
                    color: rgba(255, 255, 255, 0.8);
                    border: none; border-radius: 3px;
                    padding: 3px 6px; font-size: 10px;
                }
                QPushButton:hover { background-color: rgba(139, 92, 246, 0.4); }
                QPushButton:disabled { color: rgba(255, 255, 255, 0.3); }
            """)
            set_main_btn.clicked.connect(make_set_main(img_path))
            btn_row.addWidget(set_main_btn)

            del_btn = QPushButton("删除")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.2);
                    color: rgba(255, 255, 255, 0.8);
                    border: none; border-radius: 3px;
                    padding: 3px 6px; font-size: 10px;
                }
                QPushButton:hover { background-color: rgba(239, 68, 68, 0.4); }
            """)
            del_btn.clicked.connect(make_remove(img_path))
            btn_row.addWidget(del_btn)

            frame_layout.addLayout(btn_row)
            grid.addWidget(img_frame, row, col)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(grid_container)
        scroll.setStyleSheet("background: transparent;")
        layout.addWidget(scroll)

        # 底部按钮
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px; padding: 8px 20px; color: white;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }
        """)
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        dialog.exec()

    def _refresh_character_card(self, old_card: QFrame, char_data: dict):
        """刷新角色卡片（替换旧卡片）"""
        parent_layout = self.characters_layout
        index = -1
        for i in range(parent_layout.count()):
            if parent_layout.itemAt(i).widget() is old_card:
                index = i
                break

        if index < 0:
            return

        new_card = self._create_character_card(char_data)
        parent_layout.insertWidget(index, new_card)
        old_card.deleteLater()

    def _remove_character_card(self, card: QFrame, char_id: int):
        """移除角色卡片"""
        card.deleteLater()

        # 检查是否还有角色
        remaining = 0
        for i in range(self.characters_layout.count()):
            item = self.characters_layout.itemAt(i)
            w = item.widget() if item else None
            if w and w != self.no_character_label and isinstance(w, QFrame):
                remaining += 1

        # remaining - 1 因为被删除的卡片此时可能还在
        if remaining <= 1:
            self.no_character_label.setVisible(True)

        self._emit_change("scene_characters_remove", char_id)

    def update_characters(self, characters: List[Dict[str, Any]]):
        """从外部更新角色列表"""
        # 清除现有角色卡片（保留 no_character_label）
        for i in reversed(range(self.characters_layout.count())):
            item = self.characters_layout.itemAt(i)
            w = item.widget() if item else None
            if w and w != self.no_character_label:
                w.deleteLater()

        if characters:
            self.no_character_label.setVisible(False)
            for char_data in characters:
                card = self._create_character_card(char_data)
                self.characters_layout.addWidget(card)
        else:
            self.no_character_label.setVisible(True)

    # ==================== AI 一键分析 ====================

    def _get_subtitle_text(self) -> str:
        """获取当前字幕文本"""
        return self.subtitle_edit.toPlainText().strip()

    def _get_scene_characters(self) -> List[str]:
        """获取当前场景角色名列表"""
        if not self.current_scene:
            return []
        chars = self.current_scene.get('characters', [])
        names = []
        for c in chars:
            if isinstance(c, dict):
                names.append(c.get('name', ''))
            elif isinstance(c, str):
                names.append(c)
        return [n for n in names if n]

    def _set_ai_buttons_enabled(self, enabled: bool):
        """设置所有AI按钮的启用状态"""
        self.ai_image_prompt_btn.setEnabled(enabled)
        self.ai_video_prompt_btn.setEnabled(enabled)
        self.ai_all_btn.setEnabled(enabled)

    def _ai_generate_image_prompt(self):
        """AI 生成画面提示词"""
        text = self._get_subtitle_text()
        if not text:
            return

        self._set_ai_buttons_enabled(False)
        self.ai_image_prompt_btn.setText("AI 分析中...")

        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_IMAGE_PROMPT,
            text,
            characters=self._get_scene_characters(),
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_analysis_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_analysis_failed)
        self._ai_worker.start()

    def _ai_generate_video_prompt(self):
        """生成视频提示词"""
        text = self._get_subtitle_text()
        if not text:
            return

        self._set_ai_buttons_enabled(False)
        self.ai_video_prompt_btn.setText("生成中...")

        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_VIDEO_PROMPT,
            text,
            characters=self._get_scene_characters(),
            image_prompt=self.image_prompt_edit.toPlainText().strip(),
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_analysis_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_analysis_failed)
        self._ai_worker.start()

    def _ai_analyze_all(self):
        """一键生成（画面提示词+视频提示词）"""
        text = self._get_subtitle_text()
        if not text:
            return

        self._set_ai_buttons_enabled(False)
        self.ai_all_btn.setText("生成中...")

        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_ALL,
            text,
            characters=self._get_scene_characters(),
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_analysis_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_analysis_failed)
        self._ai_worker.start()

    def _on_ai_analysis_completed(self, analysis_type: str, result: dict):
        """AI 分析完成回调"""
        self._set_ai_buttons_enabled(True)
        self._reset_ai_button_texts()

        self._updating = True

        if analysis_type == AIAnalysisWorker.TYPE_IMAGE_PROMPT:
            prompt = result.get('image_prompt', '')
            if prompt:
                self.image_prompt_edit.setPlainText(prompt)
                self._updating = False
                self._emit_change("image_prompt", prompt)
                self._updating = True

        elif analysis_type == AIAnalysisWorker.TYPE_VIDEO_PROMPT:
            self._fill_video_prompt_result(result)

        elif analysis_type == AIAnalysisWorker.TYPE_ALL:
            # 画面提示词
            prompt = result.get('image_prompt', '')
            if prompt:
                self.image_prompt_edit.setPlainText(prompt)
                self._updating = False
                self._emit_change("image_prompt", prompt)
                self._updating = True

            # 视频提示词
            self._fill_video_prompt_result(result)

        self._updating = False

    def _fill_video_prompt_result(self, result: dict):
        """填充视频提示词相关结果"""
        video_prompt = result.get('video_prompt', '')
        if video_prompt:
            self.video_prompt_edit.setPlainText(video_prompt)
            self._updating = False
            self._emit_change("video_prompt", video_prompt)
            self._updating = True

        # 填充5个详情标签
        camera_motion = result.get('camera_motion', '-')
        shot_size = result.get('shot_size', '-')
        character_actions = result.get('character_actions', '-')
        expression_changes = result.get('expression_changes', '-')
        vfx_analysis = result.get('vfx_analysis', '-')

        self.camera_motion_label.setText(f"运镜方式：{camera_motion}")
        self.shot_size_label.setText(f"景别：{shot_size}")
        self.character_actions_label.setText(f"角色动作：{character_actions}")
        self.expression_changes_label.setText(f"表情变化：{expression_changes}")
        self.vfx_analysis_label.setText(f"特效分析：{vfx_analysis}")

        # 回写camera_motion到Scene（后端视频API可能需要）
        if camera_motion and camera_motion != '-':
            self._updating = False
            self._emit_change("camera_motion", camera_motion)
            self._updating = True

        # 将5个子维度存入generation_params
        video_details = {
            'camera_motion': camera_motion,
            'shot_size': shot_size,
            'character_actions': character_actions,
            'expression_changes': expression_changes,
            'vfx_analysis': vfx_analysis,
        }
        self._updating = False
        self._emit_change("video_prompt_details", video_details)
        self._updating = True

    def _on_ai_analysis_failed(self, analysis_type: str, error: str):
        """AI 分析失败回调"""
        self._set_ai_buttons_enabled(True)
        self._reset_ai_button_texts()
        print(f"AI分析失败 [{analysis_type}]: {error}")

    def _reset_ai_button_texts(self):
        """重置所有AI按钮文本"""
        self.ai_image_prompt_btn.setText("一键分析画面提示词")
        self.ai_video_prompt_btn.setText("生成视频提示词")
        self.ai_all_btn.setText("一键生成")
