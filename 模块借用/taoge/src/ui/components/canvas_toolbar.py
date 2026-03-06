"""
涛割 - 智能画布工具栏
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider,
    QToolButton, QButtonGroup, QWidget, QSpacerItem, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon

from ui import theme


class CanvasToolbar(QFrame):
    """智能画布顶部工具栏"""

    HEIGHT = 44

    # 信号
    tool_changed = pyqtSignal(str)        # select/move/rotate/scale/eyedrop/motion_vector
    ai_auto_layer = pyqtSignal()          # AI 自动分层
    flip_h_clicked = pyqtSignal()
    flip_v_clicked = pyqtSignal()
    onion_toggled = pyqtSignal(bool)
    onion_opacity_changed = pyqtSignal(int)  # 0-100
    continuity_toggled = pyqtSignal(bool)
    inherit_prev_clicked = pyqtSignal()
    save_clicked = pyqtSignal()
    back_clicked = pyqtSignal()
    add_material_clicked = pyqtSignal()  # 添加素材
    brush_color_changed = pyqtSignal(QColor)  # 画笔颜色
    brush_size_changed = pyqtSignal(int)      # 画笔大小
    merge_clicked = pyqtSignal()              # 合并选中图层

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self._current_tool = 'select'

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # 返回按钮
        self._back_btn = QPushButton("← 返回")
        self._back_btn.setFixedHeight(30)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self.back_clicked.emit)
        layout.addWidget(self._back_btn)

        # AI 分层按钮（accent）
        self._ai_btn = QPushButton("AI 分层")
        self._ai_btn.setFixedHeight(30)
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_btn.clicked.connect(self.ai_auto_layer.emit)
        layout.addWidget(self._ai_btn)

        # 添加素材按钮
        self._add_material_btn = QPushButton("+ 素材")
        self._add_material_btn.setFixedHeight(30)
        self._add_material_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_material_btn.setToolTip("从文件添加素材图层")
        self._add_material_btn.clicked.connect(self.add_material_clicked.emit)
        layout.addWidget(self._add_material_btn)

        self._add_separator(layout)

        # 工具按钮组
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)

        tools = [
            ('select', '选择 (V)'),
            ('move', '移动 (G)'),
            ('rotate', '旋转 (R)'),
            ('scale', '缩放 (S)'),
            ('magic_wand', '魔棒 (W)'),
            ('lasso', '套索 (L)'),
            ('brush', '画笔 (B)'),
        ]
        for tool_id, label in tools:
            btn = QToolButton()
            btn.setText(label)
            btn.setFixedHeight(28)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if tool_id == 'select':
                btn.setChecked(True)
            self._tool_group.addButton(btn)
            btn.clicked.connect(lambda checked, tid=tool_id: self._on_tool_clicked(tid))
            layout.addWidget(btn)

        self._add_separator(layout)

        # 画笔参数控件（默认隐藏，选中画笔工具时显示）
        self._brush_color = QColor(255, 0, 0)

        self._brush_color_btn = QPushButton()
        self._brush_color_btn.setFixedSize(28, 28)
        self._brush_color_btn.setToolTip("画笔颜色")
        self._brush_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._brush_color_btn.clicked.connect(self._on_brush_color_clicked)
        self._brush_color_btn.setVisible(False)
        self._update_brush_color_btn()
        layout.addWidget(self._brush_color_btn)

        self._brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._brush_size_slider.setFixedWidth(80)
        self._brush_size_slider.setRange(1, 50)
        self._brush_size_slider.setValue(5)
        self._brush_size_slider.setVisible(False)
        self._brush_size_slider.valueChanged.connect(self._on_brush_size_changed)
        layout.addWidget(self._brush_size_slider)

        self._brush_size_label = QLabel("5px")
        self._brush_size_label.setFixedWidth(30)
        self._brush_size_label.setVisible(False)
        layout.addWidget(self._brush_size_label)

        self._add_separator(layout)

        # 翻转按钮
        flip_h_btn = QPushButton("↔")
        flip_h_btn.setFixedSize(28, 28)
        flip_h_btn.setToolTip("水平翻转")
        flip_h_btn.clicked.connect(self.flip_h_clicked.emit)
        layout.addWidget(flip_h_btn)

        flip_v_btn = QPushButton("↕")
        flip_v_btn.setFixedSize(28, 28)
        flip_v_btn.setToolTip("垂直翻转")
        flip_v_btn.clicked.connect(self.flip_v_clicked.emit)
        layout.addWidget(flip_v_btn)

        # 合并选中图层按钮（默认隐藏，选中 >=2 图层时显示）
        self._merge_btn = QPushButton("合并选中图层")
        self._merge_btn.setFixedHeight(28)
        self._merge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._merge_btn.setToolTip("将选中的多个图层合并为一个")
        self._merge_btn.clicked.connect(self.merge_clicked.emit)
        self._merge_btn.setVisible(False)
        layout.addWidget(self._merge_btn)

        self._add_separator(layout)

        # 洋葱皮
        self._onion_btn = QPushButton("洋葱皮")
        self._onion_btn.setFixedHeight(28)
        self._onion_btn.setCheckable(True)
        self._onion_btn.clicked.connect(self._on_onion_toggled)
        layout.addWidget(self._onion_btn)

        self._onion_slider = QSlider(Qt.Orientation.Horizontal)
        self._onion_slider.setFixedWidth(80)
        self._onion_slider.setRange(0, 100)
        self._onion_slider.setValue(30)
        self._onion_slider.setVisible(False)
        self._onion_slider.valueChanged.connect(self.onion_opacity_changed.emit)
        layout.addWidget(self._onion_slider)

        self._add_separator(layout)

        # 连贯性辅助
        self._continuity_btn = QPushButton("连贯性")
        self._continuity_btn.setFixedHeight(28)
        self._continuity_btn.setCheckable(True)
        self._continuity_btn.clicked.connect(
            lambda checked: self.continuity_toggled.emit(self._continuity_btn.isChecked())
        )
        layout.addWidget(self._continuity_btn)

        # 继承上一镜
        self._inherit_btn = QPushButton("← 继承尾帧")
        self._inherit_btn.setFixedHeight(28)
        self._inherit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._inherit_btn.clicked.connect(self.inherit_prev_clicked.emit)
        layout.addWidget(self._inherit_btn)

        layout.addStretch()

        # 场景号
        self._scene_label = QLabel("#00")
        self._scene_label.setFont(QFont("Consolas", 10))
        layout.addWidget(self._scene_label)

        # 保存按钮
        self._save_btn = QPushButton("保存")
        self._save_btn.setFixedHeight(28)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self.save_clicked.emit)
        layout.addWidget(self._save_btn)

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(24)
        layout.addWidget(sep)

    def _on_tool_clicked(self, tool_id: str):
        self._current_tool = tool_id
        self.tool_changed.emit(tool_id)
        # 画笔参数控件可见性
        is_brush = (tool_id == 'brush')
        self._brush_color_btn.setVisible(is_brush)
        self._brush_size_slider.setVisible(is_brush)
        self._brush_size_label.setVisible(is_brush)

    def _on_onion_toggled(self):
        enabled = self._onion_btn.isChecked()
        self._onion_slider.setVisible(enabled)
        self.onion_toggled.emit(enabled)

    def _on_brush_color_clicked(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self._brush_color, self, "选择画笔颜色")
        if color.isValid():
            self._brush_color = color
            self._update_brush_color_btn()
            self.brush_color_changed.emit(color)

    def _update_brush_color_btn(self):
        self._brush_color_btn.setStyleSheet(
            f"QPushButton {{ background-color: {self._brush_color.name()}; "
            f"border: 2px solid #888; border-radius: 6px; }}"
            f"QPushButton:hover {{ border-color: #ccc; }}"
        )

    def _on_brush_size_changed(self, value: int):
        self._brush_size_label.setText(f"{value}px")
        self.brush_size_changed.emit(value)

    def set_scene_info(self, scene_index: int, scene_name: str = ""):
        text = f"#{scene_index + 1:02d}"
        if scene_name:
            text += f" {scene_name}"
        self._scene_label.setText(text)

    def set_onion_enabled(self, enabled: bool):
        self._onion_btn.setChecked(enabled)
        self._onion_slider.setVisible(enabled)

    def set_continuity_enabled(self, enabled: bool):
        self._continuity_btn.setChecked(enabled)

    def set_merge_visible(self, visible: bool):
        self._merge_btn.setVisible(visible)

    def apply_theme(self):
        self.setStyleSheet(f"""
            CanvasToolbar {{
                background: {theme.bg_primary()};
                border-bottom: 1px solid {theme.border()};
            }}
        """)

        accent_style = f"""
            QPushButton {{
                background-color: {theme.accent()}; color: white;
                border: none; border-radius: 6px;
                padding: 4px 12px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
        """
        self._ai_btn.setStyleSheet(accent_style)

        btn_style = f"""
            QPushButton, QToolButton {{
                background: {theme.bg_secondary()};
                color: {theme.text_primary()};
                border: 1px solid {theme.border()};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background: {theme.bg_hover()};
            }}
            QPushButton:checked, QToolButton:checked {{
                background: {theme.accent()}20;
                border-color: {theme.accent()};
                color: {theme.accent()};
            }}
        """
        for btn in [self._back_btn, self._onion_btn, self._continuity_btn,
                     self._inherit_btn, self._save_btn]:
            btn.setStyleSheet(btn_style)

        self._brush_size_label.setStyleSheet(
            f"QLabel {{ color: {theme.text_secondary()}; font-size: 11px; }}"
        )

        merge_style = f"""
            QPushButton {{
                background-color: #2ecc71; color: white;
                border: none; border-radius: 6px;
                padding: 4px 12px; font-size: 11px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #27ae60; }}
        """
        self._merge_btn.setStyleSheet(merge_style)
