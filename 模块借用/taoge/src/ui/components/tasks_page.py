"""
涛割 - 任务队列页面组件
"""

from datetime import datetime
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QProgressBar, QMessageBox, QMenu,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QColor

from database import get_db_manager, Task, session_scope


class TaskStatusBadge(QLabel):
    """任务状态徽章"""

    STATUS_STYLES = {
        "pending": ("等待中", "#6b7280", "#374151"),
        "queued": ("排队中", "#f59e0b", "#78350f"),
        "running": ("运行中", "#3b82f6", "#1e3a8a"),
        "completed": ("已完成", "#10b981", "#064e3b"),
        "failed": ("失败", "#ef4444", "#7f1d1d"),
        "cancelled": ("已取消", "#6b7280", "#374151"),
    }

    def __init__(self, status: str, parent=None):
        super().__init__(parent)
        self.update_status(status)

    def update_status(self, status: str):
        text, bg_color, text_color = self.STATUS_STYLES.get(
            status, ("未知", "#6b7280", "#374151")
        )
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                padding: 4px 10px;
                border-radius: 10px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(70)


class TaskRow(QFrame):
    """任务行组件"""

    retry_requested = pyqtSignal(object)
    cancel_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task

        self.setStyleSheet("""
            TaskRow {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
            TaskRow:hover {
                background-color: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.15);
            }
        """)

        self._init_ui()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(15)

        # 任务类型图标
        type_icons = {
            "image_gen": "🖼️",
            "video_gen": "🎬",
            "tag_gen": "🏷️",
            "export": "📤",
        }
        type_label = QLabel(type_icons.get(self.task.task_type, "📋"))
        type_label.setFixedWidth(30)
        type_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(type_label)

        # 任务信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        name = self.task.task_name or f"任务 #{self.task.id}"
        name_label = QLabel(name)
        name_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        info_layout.addWidget(name_label)

        # 任务详情
        type_names = {
            "image_gen": "图片生成",
            "video_gen": "视频生成",
            "tag_gen": "标签生成",
            "export": "导出",
        }
        detail_text = type_names.get(self.task.task_type, self.task.task_type)
        if self.task.model_used:
            detail_text += f" · {self.task.model_used}"

        detail_label = QLabel(detail_text)
        detail_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        info_layout.addWidget(detail_label)

        layout.addLayout(info_layout, 1)

        # 进度条（仅运行中显示）
        if self.task.status == "running":
            self.progress_bar = QProgressBar()
            self.progress_bar.setFixedWidth(150)
            self.progress_bar.setFixedHeight(8)
            self.progress_bar.setValue(int(self.task.progress))
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: rgb(59, 130, 246);
                    border-radius: 4px;
                }
            """)
            layout.addWidget(self.progress_bar)

        # 成本
        cost_text = f"¥{self.task.actual_cost:.2f}" if self.task.actual_cost else f"预估 ¥{self.task.estimated_cost:.2f}"
        cost_label = QLabel(cost_text)
        cost_label.setFixedWidth(80)
        cost_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        cost_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(cost_label)

        # 时间
        time_text = self._format_time()
        time_label = QLabel(time_text)
        time_label.setFixedWidth(100)
        time_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(time_label)

        # 状态徽章
        self.status_badge = TaskStatusBadge(self.task.status)
        layout.addWidget(self.status_badge)

        # 操作按钮
        self.action_btn = QPushButton("⋮")
        self.action_btn.setFixedSize(32, 32)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.5);
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                color: white;
            }
        """)
        self.action_btn.clicked.connect(lambda: self._show_context_menu(self.action_btn.pos()))
        layout.addWidget(self.action_btn)

    def _format_time(self) -> str:
        """格式化时间显示"""
        if self.task.completed_at:
            return self._relative_time(self.task.completed_at)
        elif self.task.started_at:
            return self._relative_time(self.task.started_at)
        elif self.task.created_at:
            return self._relative_time(self.task.created_at)
        return ""

    def _relative_time(self, dt: datetime) -> str:
        """转换为相对时间"""
        if not dt:
            return ""
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        seconds = diff.total_seconds()

        if seconds < 60:
            return "刚刚"
        elif seconds < 3600:
            return f"{int(seconds // 60)}分钟前"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}小时前"
        else:
            return f"{int(seconds // 86400)}天前"

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(40, 40, 40);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 5px;
            }
            QMenu::item {
                color: white;
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: rgb(0, 122, 204);
            }
            QMenu::item:disabled {
                color: rgba(255, 255, 255, 0.3);
            }
        """)

        # 重试（仅失败任务）
        retry_action = menu.addAction("重试")
        retry_action.setEnabled(self.task.is_retryable)
        retry_action.triggered.connect(lambda: self.retry_requested.emit(self.task))

        # 取消（仅等待/运行中任务）
        cancel_action = menu.addAction("取消")
        cancel_action.setEnabled(self.task.status in ["pending", "queued", "running"])
        cancel_action.triggered.connect(lambda: self.cancel_requested.emit(self.task))

        menu.addSeparator()

        # 删除
        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.task))

        menu.exec(self.mapToGlobal(pos))

    def update_task(self, task: Task):
        """更新任务数据"""
        self.task = task
        self.status_badge.update_status(task.status)

        # 更新进度条
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(int(task.progress))

            # 根据状态调整进度条颜色
            if task.status == "completed":
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: rgba(255, 255, 255, 0.1);
                        border-radius: 4px;
                    }
                    QProgressBar::chunk {
                        background-color: rgb(16, 185, 129);
                        border-radius: 4px;
                    }
                """)
                self.progress_bar.setValue(100)
            elif task.status == "failed":
                self.progress_bar.setStyleSheet("""
                    QProgressBar {
                        background-color: rgba(255, 255, 255, 0.1);
                        border-radius: 4px;
                    }
                    QProgressBar::chunk {
                        background-color: rgb(239, 68, 68);
                        border-radius: 4px;
                    }
                """)


class TasksPage(QWidget):
    """任务队列页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = get_db_manager()
        self.task_rows = {}  # task_id -> TaskRow
        self._generation_controller = None

        self._init_ui()
        self._load_tasks()

        # 定时刷新运行中的任务
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_running_tasks)
        self.refresh_timer.start(3000)  # 每3秒刷新

        # 统计信息刷新
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(5000)  # 每5秒更新统计

    def connect_generation_controller(self, controller):
        """
        连接 GenerationController 以接收实时更新

        Args:
            controller: GenerationController 实例
        """
        self._generation_controller = controller

        controller.generation_started.connect(self._on_generation_started)
        controller.generation_progress.connect(self._on_generation_progress)
        controller.generation_completed.connect(self._on_generation_completed)
        controller.generation_failed.connect(self._on_generation_failed)

    @pyqtSlot(int, str)
    def _on_generation_started(self, scene_id: int, task_type: str):
        """生成任务开始 - 刷新列表"""
        self._load_tasks()

    @pyqtSlot(int, str, int)
    def _on_generation_progress(self, scene_id: int, task_type: str, progress: int):
        """生成任务进度更新"""
        # 查找对应的任务行并更新进度
        with session_scope() as session:
            task = session.query(Task).filter(
                Task.scene_id == scene_id,
                Task.status == "running"
            ).order_by(Task.created_at.desc()).first()

            if task and task.id in self.task_rows:
                task.progress = progress
                self.task_rows[task.id].update_task(task)

    @pyqtSlot(int, str, str)
    def _on_generation_completed(self, scene_id: int, task_type: str, result_path: str):
        """生成任务完成 - 刷新列表和统计"""
        self._load_tasks()

    @pyqtSlot(int, str, str)
    def _on_generation_failed(self, scene_id: int, task_type: str, error: str):
        """生成任务失败 - 刷新列表"""
        self._load_tasks()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # 标题栏
        header = QHBoxLayout()

        title = QLabel("任务队列")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # 筛选器
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部任务", "运行中", "等待中", "已完成", "失败"])
        self.filter_combo.setFixedWidth(120)
        self.filter_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px 12px;
                color: white;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(40, 40, 40);
                color: white;
                selection-background-color: rgb(0, 122, 204);
            }
        """)
        self.filter_combo.currentTextChanged.connect(self._filter_tasks)
        header.addWidget(self.filter_combo)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedSize(80, 36)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        refresh_btn.clicked.connect(self._load_tasks)
        header.addWidget(refresh_btn)

        # 清空已完成
        clear_btn = QPushButton("清空已完成")
        clear_btn.setFixedSize(100, 36)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 6px;
                color: rgb(239, 68, 68);
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.3);
            }
        """)
        clear_btn.clicked.connect(self._clear_completed)
        header.addWidget(clear_btn)

        layout.addLayout(header)

        # 统计信息
        self.stats_widget = self._create_stats_widget()
        layout.addWidget(self.stats_widget)

        # 任务列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.tasks_container = QWidget()
        self.tasks_container.setStyleSheet("background: transparent;")
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(10)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.tasks_container)
        layout.addWidget(scroll)

    def _create_stats_widget(self) -> QWidget:
        """创建统计信息组件"""
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
        """)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(40)

        # 统计项
        self.stat_labels = {}

        stats = [
            ("total", "总任务", "0"),
            ("running", "运行中", "0"),
            ("pending", "等待中", "0"),
            ("completed", "已完成", "0"),
            ("failed", "失败", "0"),
        ]

        for key, label, value in stats:
            stat_layout = QVBoxLayout()
            stat_layout.setSpacing(4)

            value_label = QLabel(value)
            value_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_layout.addWidget(value_label)

            name_label = QLabel(label)
            name_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_layout.addWidget(name_label)

            layout.addLayout(stat_layout)
            self.stat_labels[key] = value_label

        layout.addStretch()

        return widget

    def _load_tasks(self):
        """加载任务列表"""
        # 清空现有任务
        while self.tasks_layout.count():
            item = self.tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.task_rows.clear()

        with session_scope() as session:
            tasks = session.query(Task).order_by(
                Task.created_at.desc()
            ).limit(100).all()

            # 统计
            stats = {
                "total": len(tasks),
                "running": sum(1 for t in tasks if t.status == "running"),
                "pending": sum(1 for t in tasks if t.status in ["pending", "queued"]),
                "completed": sum(1 for t in tasks if t.status == "completed"),
                "failed": sum(1 for t in tasks if t.status == "failed"),
            }

            for key, value in stats.items():
                self.stat_labels[key].setText(str(value))

            # 添加任务行
            for task in tasks:
                row = TaskRow(task)
                row.retry_requested.connect(self._retry_task)
                row.cancel_requested.connect(self._cancel_task)
                row.delete_requested.connect(self._delete_task)

                self.tasks_layout.addWidget(row)
                self.task_rows[task.id] = row

            # 空状态
            if not tasks:
                empty_label = QLabel("暂无任务")
                empty_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 14px;")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_label.setMinimumHeight(200)
                self.tasks_layout.addWidget(empty_label)

    def _filter_tasks(self, filter_text: str):
        """筛选任务"""
        status_map = {
            "全部任务": None,
            "运行中": "running",
            "等待中": ["pending", "queued"],
            "已完成": "completed",
            "失败": "failed",
        }

        target_status = status_map.get(filter_text)

        for task_id, row in self.task_rows.items():
            if target_status is None:
                row.setVisible(True)
            elif isinstance(target_status, list):
                row.setVisible(row.task.status in target_status)
            else:
                row.setVisible(row.task.status == target_status)

    def _refresh_running_tasks(self):
        """刷新运行中的任务"""
        with session_scope() as session:
            running_tasks = session.query(Task).filter(
                Task.status.in_(["running", "queued"])
            ).all()

            for task in running_tasks:
                if task.id in self.task_rows:
                    self.task_rows[task.id].update_task(task)

            # 如果有任务状态变化（running→completed等），全量刷新
            completed_tasks = session.query(Task).filter(
                Task.status.in_(["completed", "failed"]),
                Task.completed_at.isnot(None)
            ).order_by(Task.completed_at.desc()).limit(1).first()

            if completed_tasks and completed_tasks.id not in self.task_rows:
                self._load_tasks()

    def _update_stats(self):
        """更新统计信息"""
        with session_scope() as session:
            tasks = session.query(Task).all()

            stats = {
                "total": len(tasks),
                "running": sum(1 for t in tasks if t.status == "running"),
                "pending": sum(1 for t in tasks if t.status in ["pending", "queued"]),
                "completed": sum(1 for t in tasks if t.status == "completed"),
                "failed": sum(1 for t in tasks if t.status == "failed"),
            }

            for key, value in stats.items():
                if key in self.stat_labels:
                    self.stat_labels[key].setText(str(value))

    def _retry_task(self, task: Task):
        """重试任务"""
        with session_scope() as session:
            t = session.query(Task).get(task.id)
            if t and t.is_retryable:
                t.status = "pending"
                t.retry_count += 1
                t.error_message = None

        self._load_tasks()
        QMessageBox.information(self, "提示", f"任务 #{task.id} 已重新加入队列")

    def _cancel_task(self, task: Task):
        """取消任务"""
        reply = QMessageBox.question(
            self,
            "确认取消",
            f"确定要取消任务 #{task.id} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                t = session.query(Task).get(task.id)
                if t:
                    t.status = "cancelled"

            self._load_tasks()

    def _delete_task(self, task: Task):
        """删除任务"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除任务 #{task.id} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                t = session.query(Task).get(task.id)
                if t:
                    session.delete(t)

            self._load_tasks()

    def _clear_completed(self):
        """清空已完成任务"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有已完成的任务吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                session.query(Task).filter(
                    Task.status == "completed"
                ).delete()

            self._load_tasks()
            QMessageBox.information(self, "提示", "已清空所有已完成任务")

    def closeEvent(self, event):
        """关闭事件"""
        self.refresh_timer.stop()
        self.stats_timer.stop()
        super().closeEvent(event)
