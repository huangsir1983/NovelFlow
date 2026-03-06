"""
涛割 - 剧本结构面板
左侧场景列表，带序号和标签
"""

from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from config.constants import TAG_CATEGORY_COLORS, TAG_FONT_COLORS


class SceneListItem(QFrame):
    """场景列表项"""

    clicked = pyqtSignal(int)  # scene_index

    def __init__(self, scene_index: int, scene_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.scene_index = scene_index
        self.scene_data = scene_data
        self._is_selected = False

        self.setObjectName("sceneListItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(72)

        self._init_ui()
        self._update_style()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 序号标签
        self.index_label = QLabel(f"{self.scene_index + 1:02d}")
        self.index_label.setFixedWidth(28)
        self.index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.index_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.index_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.index_label)

        # 内容区域
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # 字幕预览（截取前30字符）
        subtitle = self.scene_data.get("subtitle_text", "")
        if len(subtitle) > 30:
            subtitle = subtitle[:30] + "..."
        self.subtitle_label = QLabel(subtitle or "无字幕")
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.9);
                font-size: 12px;
            }
        """)
        content_layout.addWidget(self.subtitle_label)

        # 标签行
        tags_layout = QHBoxLayout()
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(4)

        # 时长标签
        duration = self.scene_data.get("duration", 0)
        duration_label = QLabel(f"{duration:.1f}s")
        duration_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.4);
                font-size: 10px;
                background-color: rgba(255, 255, 255, 0.05);
                padding: 2px 6px;
                border-radius: 8px;
            }
        """)
        tags_layout.addWidget(duration_label)

        # AI标签（最多显示2个）
        ai_tags = self.scene_data.get("ai_tags", {})
        tag_count = 0
        for category, tags in ai_tags.items():
            if tag_count >= 2:
                break
            for tag in tags[:1]:
                if tag_count >= 2:
                    break
                bg_color = TAG_CATEGORY_COLORS.get(category, "rgba(100, 100, 100, {alpha})").format(alpha=0.3)
                font_color = TAG_FONT_COLORS.get(category, "#FFFFFF")
                tag_label = QLabel(tag)
                tag_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: {bg_color};
                        color: {font_color};
                        padding: 2px 6px;
                        border-radius: 8px;
                        font-size: 10px;
                    }}
                """)
                tags_layout.addWidget(tag_label)
                tag_count += 1

        tags_layout.addStretch()

        # 状态指示器
        status = self.scene_data.get("status", "pending")
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        status_colors = {
            "pending": "rgb(100, 100, 100)",
            "image_generating": "rgb(255, 193, 7)",
            "image_generated": "rgb(0, 150, 136)",
            "video_generating": "rgb(255, 152, 0)",
            "video_generated": "rgb(76, 175, 80)",
            "completed": "rgb(0, 200, 83)",
            "failed": "rgb(244, 67, 54)",
        }
        self.status_dot.setStyleSheet(f"""
            QLabel {{
                background-color: {status_colors.get(status, 'gray')};
                border-radius: 4px;
            }}
        """)
        tags_layout.addWidget(self.status_dot)

        content_layout.addLayout(tags_layout)
        layout.addLayout(content_layout, 1)

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet("""
                QFrame#sceneListItem {
                    background-color: rgba(0, 122, 204, 0.3);
                    border-left: 3px solid rgb(0, 122, 204);
                    border-radius: 0px;
                }
            """)
            self.index_label.setStyleSheet("""
                QLabel {
                    color: rgb(0, 180, 255);
                    background-color: rgba(0, 122, 204, 0.3);
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#sceneListItem {
                    background-color: transparent;
                    border-left: 3px solid transparent;
                    border-radius: 0px;
                }
                QFrame#sceneListItem:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                }
            """)
            self.index_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.5);
                    background-color: rgba(255, 255, 255, 0.05);
                    border-radius: 4px;
                    padding: 4px;
                }
            """)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_style()

    def update_data(self, scene_data: Dict[str, Any]):
        self.scene_data = scene_data

        # 更新字幕
        subtitle = scene_data.get("subtitle_text", "")
        if len(subtitle) > 30:
            subtitle = subtitle[:30] + "..."
        self.subtitle_label.setText(subtitle or "无字幕")

        # 更新状态点
        status = scene_data.get("status", "pending")
        status_colors = {
            "pending": "rgb(100, 100, 100)",
            "image_generating": "rgb(255, 193, 7)",
            "image_generated": "rgb(0, 150, 136)",
            "video_generating": "rgb(255, 152, 0)",
            "video_generated": "rgb(76, 175, 80)",
            "completed": "rgb(0, 200, 83)",
            "failed": "rgb(244, 67, 54)",
        }
        self.status_dot.setStyleSheet(f"""
            QLabel {{
                background-color: {status_colors.get(status, 'gray')};
                border-radius: 4px;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.scene_index)
        super().mousePressEvent(event)


class ScriptStructurePanel(QFrame):
    """剧本结构面板 - 左侧场景列表"""

    scene_selected = pyqtSignal(int)  # scene_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_items: List[SceneListItem] = []
        self.selected_index = -1

        self.setObjectName("scriptStructurePanel")
        self.setStyleSheet("""
            QFrame#scriptStructurePanel {
                background-color: rgb(28, 28, 30);
                border-right: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.setMinimumWidth(280)
        self.setMaximumWidth(350)

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

        title = QLabel("剧本结构")
        title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 场景数量
        self.count_label = QLabel("0 场景")
        self.count_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        header_layout.addWidget(self.count_label)

        layout.addWidget(header)

        # 搜索框
        search_container = QFrame()
        search_container.setFixedHeight(45)
        search_container.setStyleSheet("background-color: transparent;")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(10, 8, 10, 8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索场景...")
        self.search_input.textChanged.connect(self._on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 12px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: rgb(0, 122, 204);
            }
        """)
        search_layout.addWidget(self.search_input)

        layout.addWidget(search_container)

        # 场景列表滚动区域
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
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 0.25);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)

    def load_scenes(self, scenes: List[Dict[str, Any]]):
        """加载场景列表"""
        # 清空现有项
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.scene_items.clear()
        self.selected_index = -1

        # 更新计数
        self.count_label.setText(f"{len(scenes)} 场景")

        # 创建场景项
        for i, scene_data in enumerate(scenes):
            item = SceneListItem(i, scene_data)
            item.clicked.connect(self._on_item_clicked)
            self.list_layout.addWidget(item)
            self.scene_items.append(item)

        # 默认选中第一个
        if self.scene_items:
            self.select_scene(0)

    def select_scene(self, index: int, emit_signal: bool = True):
        """选中指定场景"""
        if index < 0 or index >= len(self.scene_items):
            return

        # 如果已经选中同一个场景，不重复处理
        if index == self.selected_index:
            return

        # 取消之前的选中
        if self.selected_index >= 0 and self.selected_index < len(self.scene_items):
            self.scene_items[self.selected_index].set_selected(False)

        # 选中新的
        self.selected_index = index
        self.scene_items[index].set_selected(True)

        if emit_signal:
            self.scene_selected.emit(index)

    def update_scene(self, index: int, scene_data: Dict[str, Any]):
        """更新指定场景数据"""
        if index >= 0 and index < len(self.scene_items):
            self.scene_items[index].update_data(scene_data)

    def _on_item_clicked(self, index: int):
        """场景项点击事件"""
        self.select_scene(index)

    def _on_search(self, text: str):
        """搜索过滤"""
        text = text.lower()
        for item in self.scene_items:
            subtitle = item.scene_data.get("subtitle_text", "").lower()
            if text in subtitle or not text:
                item.setVisible(True)
            else:
                item.setVisible(False)
