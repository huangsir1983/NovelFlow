"""
涛割 - 场景卡片组件
单个场景的可视化卡片，支持预览、编辑和状态显示
"""

from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QSizePolicy, QMenu, QTextEdit, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QCursor

from ui.pixmap_cache import PixmapCache
from config.constants import TAG_CATEGORY_COLORS, TAG_FONT_COLORS


class TagLabel(QLabel):
    """标签组件"""

    clicked = pyqtSignal(str, str)  # category, tag_text

    def __init__(self, text: str, category: str, parent=None):
        super().__init__(text, parent)
        self.tag_text = text
        self.category = category
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        bg_color = TAG_CATEGORY_COLORS.get(self.category, "rgba(100, 100, 100, {alpha})").format(alpha=0.3)
        font_color = TAG_FONT_COLORS.get(self.category, "#FFFFFF")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {font_color};
                padding: 3px 8px;
                border-radius: 10px;
                font-size: 11px;
            }}
            QLabel:hover {{
                background-color: {TAG_CATEGORY_COLORS.get(self.category, "rgba(100, 100, 100, {alpha})").format(alpha=0.5)};
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.category, self.tag_text)
        super().mousePressEvent(event)


class SceneCard(QFrame):
    """
    场景卡片组件
    显示单个场景的预览图、字幕、标签和状态
    """

    # 信号
    selected = pyqtSignal(int)  # scene_index
    edit_requested = pyqtSignal(int)  # scene_index
    generate_image_requested = pyqtSignal(int)
    generate_video_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    merge_requested = pyqtSignal(int, str)  # scene_index, direction ('prev' or 'next')
    split_requested = pyqtSignal(int)
    tag_clicked = pyqtSignal(int, str, str)  # scene_index, category, tag

    # 状态颜色映射
    STATUS_COLORS = {
        "pending": "rgb(100, 100, 100)",
        "image_generating": "rgb(255, 193, 7)",
        "image_generated": "rgb(0, 150, 136)",
        "video_generating": "rgb(255, 152, 0)",
        "video_generated": "rgb(76, 175, 80)",
        "completed": "rgb(0, 200, 83)",
        "failed": "rgb(244, 67, 54)",
    }

    STATUS_TEXT = {
        "pending": "待处理",
        "image_generating": "图片生成中",
        "image_generated": "图片已生成",
        "video_generating": "视频生成中",
        "video_generated": "视频已生成",
        "completed": "已完成",
        "failed": "失败",
    }

    def __init__(
        self,
        scene_index: int,
        scene_data: Dict[str, Any],
        is_selected: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.scene_index = scene_index
        self.scene_data = scene_data
        self._is_selected = is_selected

        self.setObjectName("sceneCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._init_ui()
        self._update_style()

    def _init_ui(self):
        """初始化UI"""
        self.setFixedWidth(280)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 头部：序号和状态
        header = self._create_header()
        layout.addWidget(header)

        # 预览图区域
        self.preview_container = self._create_preview()
        layout.addWidget(self.preview_container)

        # 时间信息
        time_label = self._create_time_info()
        layout.addWidget(time_label)

        # 字幕文本
        self.subtitle_label = self._create_subtitle()
        layout.addWidget(self.subtitle_label)

        # 标签区域
        self.tags_container = self._create_tags()
        layout.addWidget(self.tags_container)

        # 操作按钮
        actions = self._create_actions()
        layout.addWidget(actions)

    def _create_header(self) -> QWidget:
        """创建头部"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        # 场景序号
        self.index_label = QLabel(f"场景 {self.scene_index + 1}")
        self.index_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(self.index_label)

        layout.addStretch()

        # 状态标签
        status = self.scene_data.get("status", "pending")
        self.status_label = QLabel(self.STATUS_TEXT.get(status, "未知"))
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.STATUS_COLORS.get(status, 'gray')};
                color: white;
                padding: 2px 8px;
                border-radius: 8px;
                font-size: 10px;
            }}
        """)
        layout.addWidget(self.status_label)

        return header

    def _create_preview(self) -> QWidget:
        """创建预览图区域"""
        container = QFrame()
        container.setObjectName("previewContainer")
        container.setFixedHeight(140)
        container.setStyleSheet("""
            QFrame#previewContainer {
                background-color: rgb(30, 30, 30);
                border: 1px solid rgb(50, 50, 50);
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 加载预览图
        image_path = self.scene_data.get("generated_image_path")
        if image_path:
            self._load_preview_image(image_path)
        else:
            self.preview_label.setText("暂无预览")
            self.preview_label.setStyleSheet("color: rgba(255, 255, 255, 0.3);")

        layout.addWidget(self.preview_label)

        return container

    def _load_preview_image(self, image_path: str):
        """加载预览图"""
        try:
            scaled = PixmapCache.instance().get_scaled(image_path, 256, 130)
            if scaled:
                self.preview_label.setPixmap(scaled)
            else:
                self.preview_label.setText("图片加载失败")
        except Exception as e:
            self.preview_label.setText("图片加载失败")

    def _create_time_info(self) -> QLabel:
        """创建时间信息"""
        start = self.scene_data.get("start_time", "00:00:00,000")
        end = self.scene_data.get("end_time", "00:00:00,000")
        duration = self.scene_data.get("duration", 0)

        # 简化时间格式显示
        start_short = start[:8] if len(start) > 8 else start
        end_short = end[:8] if len(end) > 8 else end

        time_label = QLabel(f"{start_short} - {end_short} ({duration:.1f}s)")
        time_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        return time_label

    def _create_subtitle(self) -> QLabel:
        """创建字幕显示"""
        subtitle = self.scene_data.get("subtitle_text", "")
        if len(subtitle) > 80:
            subtitle = subtitle[:80] + "..."

        label = QLabel(subtitle)
        label.setWordWrap(True)
        label.setMaximumHeight(50)
        label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px;")
        return label

    def _create_tags(self) -> QWidget:
        """创建标签区域"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 获取AI标签
        ai_tags = self.scene_data.get("ai_tags", {})
        tag_count = 0
        max_tags = 4

        for category, tags in ai_tags.items():
            if tag_count >= max_tags:
                break
            for tag in tags[:2]:  # 每类最多显示2个
                if tag_count >= max_tags:
                    break
                tag_label = TagLabel(tag, category)
                tag_label.clicked.connect(
                    lambda cat, txt: self.tag_clicked.emit(self.scene_index, cat, txt)
                )
                layout.addWidget(tag_label)
                tag_count += 1

        # 如果还有更多标签
        total_tags = sum(len(tags) for tags in ai_tags.values())
        if total_tags > max_tags:
            more_label = QLabel(f"+{total_tags - max_tags}")
            more_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.5);
                font-size: 10px;
            """)
            layout.addWidget(more_label)

        layout.addStretch()

        return container

    def _create_actions(self) -> QWidget:
        """创建操作按钮"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 生成图片按钮
        self.gen_image_btn = QPushButton("生成图片")
        self.gen_image_btn.setFixedHeight(28)
        self.gen_image_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gen_image_btn.clicked.connect(lambda: self.generate_image_requested.emit(self.scene_index))
        self.gen_image_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                border: none;
                border-radius: 4px;
                font-size: 11px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: rgb(0, 140, 220);
            }
        """)
        layout.addWidget(self.gen_image_btn)

        # 生成视频按钮
        self.gen_video_btn = QPushButton("生成视频")
        self.gen_video_btn.setFixedHeight(28)
        self.gen_video_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gen_video_btn.clicked.connect(lambda: self.generate_video_requested.emit(self.scene_index))

        # 根据状态设置按钮样式
        status = self.scene_data.get("status", "pending")
        if status in ["pending", "image_generating"]:
            self.gen_video_btn.setEnabled(False)
            self.gen_video_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgb(60, 60, 60);
                    color: rgb(100, 100, 100);
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 0 10px;
                }
            """)
        else:
            self.gen_video_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgb(76, 175, 80);
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 0 10px;
                }
                QPushButton:hover {
                    background-color: rgb(100, 200, 100);
                }
            """)
        layout.addWidget(self.gen_video_btn)

        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setFixedSize(50, 28)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.scene_index))
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid rgb(80, 80, 80);
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                border-color: rgb(0, 122, 204);
                color: rgb(0, 180, 255);
            }
        """)
        layout.addWidget(edit_btn)

        return container

    def _update_style(self):
        """更新卡片样式"""
        if self._is_selected:
            self.setStyleSheet("""
                QFrame#sceneCard {
                    background-color: rgb(40, 50, 65);
                    border: 2px solid rgb(0, 122, 204);
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#sceneCard {
                    background-color: rgb(35, 42, 51);
                    border: 1px solid rgb(50, 50, 50);
                    border-radius: 10px;
                }
                QFrame#sceneCard:hover {
                    border-color: rgb(80, 80, 80);
                }
            """)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(45, 45, 45);
                border: 1px solid rgb(60, 60, 60);
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: white;
            }
            QMenu::item:selected {
                background-color: rgb(60, 70, 80);
            }
        """)

        # 编辑
        edit_action = menu.addAction("编辑场景")
        edit_action.triggered.connect(lambda: self.edit_requested.emit(self.scene_index))

        menu.addSeparator()

        # 生成
        gen_image_action = menu.addAction("生成图片")
        gen_image_action.triggered.connect(lambda: self.generate_image_requested.emit(self.scene_index))

        gen_video_action = menu.addAction("生成视频")
        gen_video_action.triggered.connect(lambda: self.generate_video_requested.emit(self.scene_index))
        status = self.scene_data.get("status", "pending")
        if status in ["pending", "image_generating"]:
            gen_video_action.setEnabled(False)

        menu.addSeparator()

        # 合并/拆分
        merge_prev = menu.addAction("与上一场景合并")
        merge_prev.triggered.connect(lambda: self.merge_requested.emit(self.scene_index, "prev"))
        if self.scene_index == 0:
            merge_prev.setEnabled(False)

        merge_next = menu.addAction("与下一场景合并")
        merge_next.triggered.connect(lambda: self.merge_requested.emit(self.scene_index, "next"))

        split_action = menu.addAction("拆分场景")
        split_action.triggered.connect(lambda: self.split_requested.emit(self.scene_index))

        menu.addSeparator()

        # 删除
        delete_action = menu.addAction("删除场景")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.scene_index))
        delete_action.setStyleSheet("color: rgb(244, 67, 54);")

        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        """点击选中"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.scene_index)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        self._update_style()

    def update_data(self, scene_data: Dict[str, Any]):
        """更新场景数据"""
        self.scene_data = scene_data

        # 更新状态
        status = scene_data.get("status", "pending")
        self.status_label.setText(self.STATUS_TEXT.get(status, "未知"))
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.STATUS_COLORS.get(status, 'gray')};
                color: white;
                padding: 2px 8px;
                border-radius: 8px;
                font-size: 10px;
            }}
        """)

        # 更新预览图
        image_path = scene_data.get("generated_image_path")
        if image_path:
            self._load_preview_image(image_path)

        # 更新字幕
        subtitle = scene_data.get("subtitle_text", "")
        if len(subtitle) > 80:
            subtitle = subtitle[:80] + "..."
        self.subtitle_label.setText(subtitle)

        # 更新视频按钮状态
        if status in ["pending", "image_generating"]:
            self.gen_video_btn.setEnabled(False)
        else:
            self.gen_video_btn.setEnabled(True)

    def set_generating(self, is_generating: bool, task_type: str = "image"):
        """
        设置生成中状态

        Args:
            is_generating: 是否正在生成
            task_type: 任务类型 ("image" 或 "video")
        """
        if is_generating:
            # 更新状态显示
            if task_type == "image":
                status = "image_generating"
                self.gen_image_btn.setEnabled(False)
                self.gen_image_btn.setText("生成中...")
            else:
                status = "video_generating"
                self.gen_video_btn.setEnabled(False)
                self.gen_video_btn.setText("生成中...")

            self.status_label.setText(self.STATUS_TEXT.get(status, "生成中"))
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {self.STATUS_COLORS.get(status, 'orange')};
                    color: white;
                    padding: 2px 8px;
                    border-radius: 8px;
                    font-size: 10px;
                }}
            """)
        else:
            # 恢复按钮状态
            self.gen_image_btn.setEnabled(True)
            self.gen_image_btn.setText("生成图片")
            self.gen_video_btn.setText("生成视频")

            # 根据当前数据状态决定视频按钮是否可用
            status = self.scene_data.get("status", "pending")
            if status not in ["pending", "image_generating"]:
                self.gen_video_btn.setEnabled(True)

    def set_progress(self, progress: int):
        """
        设置生成进度

        Args:
            progress: 进度值 (0-100)
        """
        # 更新状态标签显示进度
        current_text = self.status_label.text()
        if "生成中" in current_text or "%" in current_text:
            self.status_label.setText(f"生成中 {progress}%")

    def set_error(self, error_message: str):
        """
        设置错误状态

        Args:
            error_message: 错误信息
        """
        self.status_label.setText("失败")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.STATUS_COLORS.get('failed', 'red')};
                color: white;
                padding: 2px 8px;
                border-radius: 8px;
                font-size: 10px;
            }}
        """)
        self.status_label.setToolTip(error_message)

        # 恢复按钮状态
        self.gen_image_btn.setEnabled(True)
        self.gen_image_btn.setText("生成图片")
        self.gen_video_btn.setText("生成视频")

