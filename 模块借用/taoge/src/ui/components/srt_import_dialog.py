"""
涛割 - SRT导入对话框
"""

import os
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QProgressBar,
    QScrollArea, QFrame, QMessageBox, QFileDialog,
    QGroupBox, QFormLayout, QTextEdit, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from services.scene.processor import SceneProcessor, SceneGroup
from database import session_scope, Project, Scene


class SrtParseThread(QThread):
    """SRT解析线程"""
    finished = pyqtSignal(list)  # 解析完成信号
    error = pyqtSignal(str)  # 错误信号

    def __init__(self, file_path: str, strategy: str = "duration"):
        super().__init__()
        self.file_path = file_path
        self.strategy = strategy

    def run(self):
        try:
            processor = SceneProcessor()
            segments = processor.parse_srt_file(self.file_path)
            groups = processor.group_segments(segments, strategy=self.strategy)
            self.finished.emit(groups)
        except Exception as e:
            self.error.emit(str(e))


class ScenePreviewItem(QFrame):
    """场景预览项"""

    def __init__(self, index: int, group: SceneGroup, parent=None):
        super().__init__(parent)
        self.index = index
        self.group = group

        self.setStyleSheet("""
            ScenePreviewItem {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            ScenePreviewItem:hover {
                background-color: rgba(255, 255, 255, 0.06);
                border-color: rgba(0, 122, 204, 0.5);
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)

        # 顶部行：序号、时间、时长
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        # 序号
        index_label = QLabel(f"场景 {self.index + 1}")
        index_label.setStyleSheet("color: rgb(0, 180, 255); font-weight: bold; font-size: 14px;")
        top_layout.addWidget(index_label)

        # 时间
        time_text = f"{self.group.start_time} → {self.group.end_time}"
        time_label = QLabel(time_text)
        time_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        top_layout.addWidget(time_label)

        # 时长
        duration_label = QLabel(f"{self.group.duration:.1f}秒")
        duration_label.setStyleSheet("""
            color: white;
            background-color: rgba(0, 122, 204, 0.3);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
        """)
        top_layout.addWidget(duration_label)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 文本内容
        text = self.group.full_text
        if len(text) > 150:
            text = text[:150] + "..."
        text_label = QLabel(text)
        text_label.setStyleSheet("color: rgba(255, 255, 255, 0.85); font-size: 13px; line-height: 1.4;")
        text_label.setWordWrap(True)
        layout.addWidget(text_label)


class SrtImportDialog(QDialog):
    """SRT导入对话框"""

    project_created = pyqtSignal(object)  # 项目创建完成信号

    def __init__(self, file_path: str = None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.scene_groups: List[SceneGroup] = []
        self.parse_thread: Optional[SrtParseThread] = None

        self.setWindowTitle("导入SRT字幕")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(30, 30, 30);
            }
            QLabel {
                color: white;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px;
                color: white;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: rgb(0, 122, 204);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                color: rgb(0, 180, 255);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
        """)

        self._init_ui()

        if file_path:
            self.file_input.setText(file_path)
            self._parse_srt()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # 标题
        title = QLabel("导入SRT字幕文件")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        # 文件选择
        file_group = QGroupBox("文件选择")
        file_layout = QHBoxLayout(file_group)

        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("选择SRT字幕文件...")
        self.file_input.setReadOnly(True)
        file_layout.addWidget(self.file_input, 1)

        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # 项目设置
        settings_group = QGroupBox("项目设置")
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(12)

        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("输入项目名称")
        settings_layout.addRow("项目名称:", self.project_name)

        self.project_desc = QTextEdit()
        self.project_desc.setPlaceholderText("项目描述（可选）")
        self.project_desc.setMaximumHeight(60)
        settings_layout.addRow("项目描述:", self.project_desc)

        # 分组策略
        strategy_layout = QHBoxLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["按时长分组", "按内容分组", "每条字幕一个场景"])
        self.strategy_combo.setStyleSheet("""
            QComboBox {
                min-width: 150px;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(40, 40, 40);
                color: white;
                selection-background-color: rgb(0, 122, 204);
            }
        """)
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        strategy_layout.addWidget(self.strategy_combo)
        strategy_layout.addStretch()
        settings_layout.addRow("分组策略:", strategy_layout)

        # 画布尺寸
        size_layout = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(640, 4096)
        self.width_spin.setValue(1920)
        self.width_spin.setSingleStep(64)
        size_layout.addWidget(self.width_spin)
        size_layout.addWidget(QLabel("x"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(480, 4096)
        self.height_spin.setValue(1080)
        self.height_spin.setSingleStep(64)
        size_layout.addWidget(self.height_spin)
        size_layout.addStretch()
        settings_layout.addRow("画布尺寸:", size_layout)

        layout.addWidget(settings_group)

        # 场景预览
        preview_group = QGroupBox("场景预览")
        preview_layout = QVBoxLayout(preview_group)

        # 统计信息
        self.stats_label = QLabel("请选择SRT文件")
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        preview_layout.addWidget(self.stats_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: rgb(0, 122, 204);
                border-radius: 4px;
            }
        """)
        preview_layout.addWidget(self.progress_bar)

        # 场景列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.05);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 0.3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        scroll.setMinimumHeight(300)

        self.scenes_container = QWidget()
        self.scenes_container.setStyleSheet("background: transparent;")
        self.scenes_layout = QVBoxLayout(self.scenes_container)
        self.scenes_layout.setContentsMargins(5, 5, 5, 5)
        self.scenes_layout.setSpacing(10)
        self.scenes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.scenes_container)
        preview_layout.addWidget(scroll)

        layout.addWidget(preview_group, 1)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.create_btn = QPushButton("创建项目")
        self.create_btn.setEnabled(False)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                border: none;
                padding: 10px 25px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgb(0, 140, 230);
            }
            QPushButton:disabled {
                background-color: rgba(0, 122, 204, 0.3);
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.create_btn.clicked.connect(self._create_project)
        btn_layout.addWidget(self.create_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择SRT字幕文件",
            "",
            "SRT字幕文件 (*.srt);;所有文件 (*.*)"
        )
        if file_path:
            self.file_path = file_path
            self.file_input.setText(file_path)

            # 自动设置项目名称
            if not self.project_name.text():
                name = os.path.splitext(os.path.basename(file_path))[0]
                self.project_name.setText(name)

            self._parse_srt()

    def _get_strategy(self) -> str:
        """获取分组策略"""
        strategies = ["duration", "content", "fixed"]
        return strategies[self.strategy_combo.currentIndex()]

    def _on_strategy_changed(self):
        """策略变更"""
        if self.file_path:
            self._parse_srt()

    def _parse_srt(self):
        """解析SRT文件"""
        if not self.file_path:
            return

        # 显示进度
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.stats_label.setText("正在解析...")
        self.create_btn.setEnabled(False)

        # 清空预览
        while self.scenes_layout.count():
            item = self.scenes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 启动解析线程
        self.parse_thread = SrtParseThread(self.file_path, self._get_strategy())
        self.parse_thread.finished.connect(self._on_parse_finished)
        self.parse_thread.error.connect(self._on_parse_error)
        self.parse_thread.start()

    def _on_parse_finished(self, groups: List[SceneGroup]):
        """解析完成"""
        self.scene_groups = groups
        self.progress_bar.setVisible(False)

        # 计算统计信息
        total_duration = sum(g.duration for g in groups)
        total_segments = sum(len(g.segments) for g in groups)

        self.stats_label.setText(
            f"共 {len(groups)} 个场景 | {total_segments} 条字幕 | "
            f"总时长 {total_duration:.1f} 秒"
        )

        # 显示场景预览
        for i, group in enumerate(groups[:50]):  # 最多显示50个
            item = ScenePreviewItem(i, group)
            self.scenes_layout.addWidget(item)

        if len(groups) > 50:
            more_label = QLabel(f"... 还有 {len(groups) - 50} 个场景")
            more_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); padding: 10px;")
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scenes_layout.addWidget(more_label)

        self.create_btn.setEnabled(True)

    def _on_parse_error(self, error: str):
        """解析错误"""
        self.progress_bar.setVisible(False)
        self.stats_label.setText(f"解析失败: {error}")
        QMessageBox.warning(self, "解析错误", f"无法解析SRT文件:\n{error}")

    def _create_project(self):
        """创建项目"""
        name = self.project_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入项目名称")
            return

        if not self.scene_groups:
            QMessageBox.warning(self, "提示", "没有可用的场景数据")
            return

        try:
            with session_scope() as session:
                # 创建项目
                project = Project(
                    name=name,
                    description=self.project_desc.toPlainText().strip(),
                    source_type="srt",
                    source_path=self.file_path,
                    canvas_width=self.width_spin.value(),
                    canvas_height=self.height_spin.value(),
                    total_scenes=len(self.scene_groups),
                    total_duration=sum(g.duration for g in self.scene_groups),
                    status="draft"
                )
                session.add(project)
                session.flush()  # 获取project.id

                # 创建场景
                for i, group in enumerate(self.scene_groups):
                    scene = Scene(
                        project_id=project.id,
                        scene_index=i + 1,
                        name=f"场景 {i + 1}",
                        start_time=group.start_time,
                        end_time=group.end_time,
                        start_microseconds=group.start_microseconds,
                        end_microseconds=group.end_microseconds,
                        duration=group.duration,
                        subtitle_text=group.full_text,
                        subtitle_segments=[
                            {
                                "index": s.index,
                                "start": s.start,
                                "end": s.end,
                                "text": s.text
                            }
                            for s in group.segments
                        ],
                        ai_tags=group.ai_tags,
                        status="pending"
                    )
                    session.add(scene)

                # 提交后获取完整的project对象
                session.commit()
                project_id = project.id
                project_name = project.name

            # 发出信号，传递项目ID和名称的字典
            self.project_created.emit({'id': project_id, 'name': project_name})

            QMessageBox.information(
                self,
                "创建成功",
                f"项目 '{project_name}' 已创建\n共 {len(self.scene_groups)} 个场景"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "创建失败", f"创建项目时出错:\n{str(e)}")
