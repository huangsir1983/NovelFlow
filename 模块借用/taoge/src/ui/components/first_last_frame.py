"""
涛割 - 首尾帧控制组件
用于视频片段的首帧和尾帧设置，实现视频衔接优化
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QTextEdit, QGroupBox, QMessageBox,
    QDialog, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from ui.pixmap_cache import PixmapCache
from database import session_scope, Scene


class FramePreview(QFrame):
    """帧预览组件"""

    frame_changed = pyqtSignal(str)  # 帧路径变更信号
    clear_requested = pyqtSignal()  # 清除请求信号

    def __init__(self, title: str = "帧预览", parent=None):
        super().__init__(parent)
        self.title = title
        self.frame_path: Optional[str] = None

        self.setStyleSheet("""
            FramePreview {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: rgb(0, 180, 255); font-weight: bold; font-size: 13px;")
        layout.addWidget(title_label)

        # 预览图
        self.preview_label = QLabel("点击选择图片")
        self.preview_label.setFixedSize(200, 120)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.02);
                border: 2px dashed rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                color: rgba(255, 255, 255, 0.4);
                font-size: 12px;
            }
            QLabel:hover {
                border-color: rgba(0, 122, 204, 0.5);
                color: rgba(255, 255, 255, 0.6);
            }
        """)
        self.preview_label.mousePressEvent = self._on_preview_clicked
        layout.addWidget(self.preview_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.select_btn = QPushButton("选择")
        self.select_btn.setFixedWidth(70)
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(self._select_frame)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        btn_layout.addWidget(self.select_btn)

        self.clear_btn = QPushButton("清除")
        self.clear_btn.setFixedWidth(70)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_frame)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 4px;
                padding: 6px;
                color: rgb(239, 68, 68);
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.3);
            }
        """)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

    def _on_preview_clicked(self, event):
        """预览图点击事件"""
        self._select_frame()

    def _select_frame(self):
        """选择帧图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"选择{self.title}图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp);;所有文件 (*.*)"
        )
        if file_path:
            self.set_frame(file_path)
            self.frame_changed.emit(file_path)

    def _clear_frame(self):
        """清除帧"""
        self.frame_path = None
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("点击选择图片")
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.02);
                border: 2px dashed rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                color: rgba(255, 255, 255, 0.4);
                font-size: 12px;
            }
        """)
        self.clear_requested.emit()

    def set_frame(self, path: str):
        """设置帧图片"""
        if path and os.path.exists(path):
            self.frame_path = path
            scaled = PixmapCache.instance().get_scaled(path, 196, 116)
            if scaled:
                self.preview_label.setPixmap(scaled)
                self.preview_label.setText("")
                self.preview_label.setStyleSheet("""
                    QLabel {
                        background-color: rgba(255, 255, 255, 0.02);
                        border: 2px solid rgba(0, 122, 204, 0.5);
                        border-radius: 6px;
                    }
                """)

    def get_frame_path(self) -> Optional[str]:
        """获取帧路径"""
        return self.frame_path


class FrameDescriptionEditor(QFrame):
    """帧描述编辑器"""

    description_changed = pyqtSignal(str)

    def __init__(self, title: str = "帧描述", placeholder: str = "", parent=None):
        super().__init__(parent)
        self.title = title
        self.placeholder = placeholder

        self.setStyleSheet("""
            FrameDescriptionEditor {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("color: rgb(0, 180, 255); font-weight: bold; font-size: 13px;")
        layout.addWidget(title_label)

        # 描述输入
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText(self.placeholder)
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 8px;
                color: white;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: rgb(0, 122, 204);
            }
        """)
        self.desc_edit.textChanged.connect(
            lambda: self.description_changed.emit(self.desc_edit.toPlainText())
        )
        layout.addWidget(self.desc_edit)

    def set_description(self, text: str):
        """设置描述"""
        self.desc_edit.setPlainText(text)

    def get_description(self) -> str:
        """获取描述"""
        return self.desc_edit.toPlainText()


class FirstLastFramePanel(QWidget):
    """首尾帧控制面板"""

    frames_updated = pyqtSignal(dict)  # 帧数据更新信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_scene_id: Optional[int] = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        # 标题
        header = QHBoxLayout()
        title = QLabel("首尾帧控制")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # 帮助提示
        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setToolTip("首尾帧用于控制视频片段的起始和结束画面，实现更好的视频衔接")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                color: white;
            }
        """)
        help_btn.clicked.connect(self._show_help)
        header.addWidget(help_btn)

        layout.addLayout(header)

        # 首帧区域
        start_group = QGroupBox("首帧 (Start Frame)")
        start_group.setStyleSheet(self._group_style())
        start_layout = QHBoxLayout(start_group)
        start_layout.setSpacing(15)

        self.start_frame_preview = FramePreview("首帧图片")
        self.start_frame_preview.frame_changed.connect(self._on_start_frame_changed)
        self.start_frame_preview.clear_requested.connect(self._on_start_frame_cleared)
        start_layout.addWidget(self.start_frame_preview)

        self.start_frame_desc = FrameDescriptionEditor(
            "首帧描述",
            "描述首帧的画面内容，用于生成视频时的参考..."
        )
        self.start_frame_desc.description_changed.connect(self._on_start_desc_changed)
        start_layout.addWidget(self.start_frame_desc, 1)

        layout.addWidget(start_group)

        # 尾帧区域
        end_group = QGroupBox("尾帧 (End Frame)")
        end_group.setStyleSheet(self._group_style())
        end_layout = QHBoxLayout(end_group)
        end_layout.setSpacing(15)

        self.end_frame_preview = FramePreview("尾帧图片")
        self.end_frame_preview.frame_changed.connect(self._on_end_frame_changed)
        self.end_frame_preview.clear_requested.connect(self._on_end_frame_cleared)
        end_layout.addWidget(self.end_frame_preview)

        self.end_frame_desc = FrameDescriptionEditor(
            "尾帧描述",
            "描述尾帧的画面内容，用于与下一个片段衔接..."
        )
        self.end_frame_desc.description_changed.connect(self._on_end_desc_changed)
        end_layout.addWidget(self.end_frame_desc, 1)

        layout.addWidget(end_group)

        # 快捷操作
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        # 从上一场景复制尾帧
        copy_prev_btn = QPushButton("从上一场景复制尾帧")
        copy_prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_prev_btn.clicked.connect(self._copy_from_previous)
        copy_prev_btn.setStyleSheet(self._action_btn_style())
        actions_layout.addWidget(copy_prev_btn)

        # 复制首帧到尾帧
        copy_to_end_btn = QPushButton("复制首帧到尾帧")
        copy_to_end_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_to_end_btn.clicked.connect(self._copy_start_to_end)
        copy_to_end_btn.setStyleSheet(self._action_btn_style())
        actions_layout.addWidget(copy_to_end_btn)

        actions_layout.addStretch()

        layout.addLayout(actions_layout)

    def _group_style(self) -> str:
        return """
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """

    def _action_btn_style(self) -> str:
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 8px 15px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """

    def load_scene(self, scene_id: int):
        """加载场景的首尾帧数据"""
        self.current_scene_id = scene_id

        with session_scope() as session:
            scene = session.query(Scene).get(scene_id)
            if scene:
                # 加载首帧
                if scene.start_frame_path:
                    self.start_frame_preview.set_frame(scene.start_frame_path)
                else:
                    self.start_frame_preview._clear_frame()

                self.start_frame_desc.set_description(scene.start_frame_description or "")

                # 加载尾帧
                if scene.end_frame_path:
                    self.end_frame_preview.set_frame(scene.end_frame_path)
                else:
                    self.end_frame_preview._clear_frame()

                self.end_frame_desc.set_description(scene.end_frame_description or "")

    def _on_start_frame_changed(self, path: str):
        """首帧变更"""
        self._save_to_db()

    def _on_start_frame_cleared(self):
        """首帧清除"""
        self._save_to_db()

    def _on_end_frame_changed(self, path: str):
        """尾帧变更"""
        self._save_to_db()

    def _on_end_frame_cleared(self):
        """尾帧清除"""
        self._save_to_db()

    def _on_start_desc_changed(self, text: str):
        """首帧描述变更"""
        # 延迟保存，避免频繁写入
        pass

    def _on_end_desc_changed(self, text: str):
        """尾帧描述变更"""
        pass

    def _save_to_db(self):
        """保存到数据库"""
        if not self.current_scene_id:
            return

        with session_scope() as session:
            scene = session.query(Scene).get(self.current_scene_id)
            if scene:
                scene.start_frame_path = self.start_frame_preview.get_frame_path()
                scene.start_frame_description = self.start_frame_desc.get_description()
                scene.end_frame_path = self.end_frame_preview.get_frame_path()
                scene.end_frame_description = self.end_frame_desc.get_description()

        self.frames_updated.emit(self.get_frame_data())

    def save_descriptions(self):
        """保存描述（手动调用）"""
        self._save_to_db()

    def get_frame_data(self) -> dict:
        """获取帧数据"""
        return {
            "start_frame_path": self.start_frame_preview.get_frame_path(),
            "start_frame_description": self.start_frame_desc.get_description(),
            "end_frame_path": self.end_frame_preview.get_frame_path(),
            "end_frame_description": self.end_frame_desc.get_description(),
        }

    def _copy_from_previous(self):
        """从上一场景复制尾帧作为当前首帧"""
        if not self.current_scene_id:
            return

        with session_scope() as session:
            current_scene = session.query(Scene).get(self.current_scene_id)
            if not current_scene:
                return

            # 查找上一个场景
            prev_scene = session.query(Scene).filter(
                Scene.project_id == current_scene.project_id,
                Scene.scene_index == current_scene.scene_index - 1
            ).first()

            if prev_scene and prev_scene.end_frame_path:
                self.start_frame_preview.set_frame(prev_scene.end_frame_path)
                if prev_scene.end_frame_description:
                    self.start_frame_desc.set_description(prev_scene.end_frame_description)
                self._save_to_db()
                QMessageBox.information(self, "提示", "已从上一场景复制尾帧")
            else:
                QMessageBox.warning(self, "提示", "上一场景没有设置尾帧")

    def _copy_start_to_end(self):
        """复制首帧到尾帧"""
        start_path = self.start_frame_preview.get_frame_path()
        if start_path:
            self.end_frame_preview.set_frame(start_path)
            self.end_frame_desc.set_description(self.start_frame_desc.get_description())
            self._save_to_db()
        else:
            QMessageBox.warning(self, "提示", "请先设置首帧")

    def _show_help(self):
        """显示帮助信息"""
        QMessageBox.information(
            self,
            "首尾帧控制说明",
            "首尾帧控制用于优化视频片段之间的衔接：\n\n"
            "• 首帧：视频片段的起始画面\n"
            "• 尾帧：视频片段的结束画面\n\n"
            "使用技巧：\n"
            "1. 将上一场景的尾帧设为当前场景的首帧，可实现平滑过渡\n"
            "2. 添加帧描述可以帮助AI更好地理解画面内容\n"
            "3. 支持的模型（如Kling）会根据首尾帧生成过渡动画"
        )


class FirstLastFrameDialog(QDialog):
    """首尾帧控制对话框"""

    def __init__(self, scene_id: int, parent=None):
        super().__init__(parent)
        self.scene_id = scene_id

        self.setWindowTitle("首尾帧控制")
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(30, 30, 30);
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 首尾帧面板
        self.frame_panel = FirstLastFramePanel()
        self.frame_panel.load_scene(self.scene_id)
        layout.addWidget(self.frame_panel)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setFixedSize(100, 36)
        close_btn.clicked.connect(self._on_close)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgb(0, 140, 230);
            }
        """)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _on_close(self):
        """关闭对话框"""
        self.frame_panel.save_descriptions()
        self.accept()
