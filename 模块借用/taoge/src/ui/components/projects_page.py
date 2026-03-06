"""
涛割 - 项目列表页面组件
"""

from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QMessageBox, QMenu,
    QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from database import session_scope, Project


class ProjectCard(QFrame):
    """项目卡片组件"""

    clicked = pyqtSignal(object)  # 点击信号
    delete_requested = pyqtSignal(object)  # 删除请求信号

    STATUS_COLORS = {
        "draft": ("草稿", "#6b7280"),
        "processing": ("处理中", "#f59e0b"),
        "completed": ("已完成", "#10b981"),
    }

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        # 立即在session存活期间将ORM对象转为dict，避免DetachedInstanceError
        self.project = project.to_dict()

        self.setFixedSize(280, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            ProjectCard {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
            }
            ProjectCard:hover {
                background-color: rgba(255, 255, 255, 0.06);
                border-color: rgba(0, 122, 204, 0.5);
            }
        """)

        self._init_ui()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(8)

        # 标题行
        header = QHBoxLayout()
        name_label = QLabel(self.project.get('name', '未命名'))
        name_label.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        name_label.setWordWrap(True)
        header.addWidget(name_label, 1)

        # 状态标签
        status_text, status_color = self.STATUS_COLORS.get(
            self.project.get('status', 'draft'), ("未知", "#6b7280")
        )
        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"""
            background-color: {status_color};
            color: white;
            padding: 3px 8px;
            border-radius: 8px;
            font-size: 10px;
        """)
        header.addWidget(status_label)
        layout.addLayout(header)

        # 描述
        description = self.project.get('description', '')
        if description:
            desc = description[:50] + "..." if len(description) > 50 else description
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        layout.addStretch()

        # 底部信息
        footer = QHBoxLayout()

        # 场景数
        total_scenes = self.project.get('total_scenes', 0)
        scenes_label = QLabel(f"{total_scenes} 个场景")
        scenes_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        footer.addWidget(scenes_label)

        # 进度
        completed_scenes = self.project.get('completed_scenes', 0)
        if total_scenes > 0:
            progress = int(completed_scenes / total_scenes * 100)
            progress_label = QLabel(f"{progress}%")
            progress_label.setStyleSheet("color: rgb(0, 180, 255); font-size: 12px;")
            footer.addWidget(progress_label)

        footer.addStretch()

        # 时间
        time_text = self._format_time_str(self.project.get('created_at'))
        time_label = QLabel(time_text)
        time_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px;")
        footer.addWidget(time_label)

        layout.addLayout(footer)

    def _format_time(self, dt: datetime) -> str:
        """格式化时间"""
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
        elif seconds < 604800:
            return f"{int(seconds // 86400)}天前"
        else:
            return dt.strftime("%m-%d")

    def _format_time_str(self, time_str: str) -> str:
        """格式化ISO时间字符串"""
        if not time_str:
            return ""
        try:
            dt = datetime.fromisoformat(time_str)
            return self._format_time(dt)
        except (ValueError, TypeError):
            return ""

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
        """)

        open_action = menu.addAction("打开项目")
        open_action.triggered.connect(lambda: self.clicked.emit(self.project))

        menu.addSeparator()

        delete_action = menu.addAction("删除项目")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.project))

        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.project)
        super().mousePressEvent(event)


class ProjectsPage(QWidget):
    """项目列表页面"""

    project_selected = pyqtSignal(object)  # 项目选中信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.load_projects()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # 标题栏
        header = QHBoxLayout()

        title = QLabel("我的项目")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索项目...")
        self.search_input.setFixedWidth(250)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px 12px;
                color: white;
            }
            QLineEdit:focus {
                border-color: rgb(0, 122, 204);
            }
        """)
        self.search_input.textChanged.connect(self._filter_projects)
        header.addWidget(self.search_input)

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
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        refresh_btn.clicked.connect(self.load_projects)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # 统计信息
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        layout.addWidget(self.stats_label)

        # 项目网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.projects_container = QWidget()
        self.projects_container.setStyleSheet("background: transparent;")
        self.projects_grid = QGridLayout(self.projects_container)
        self.projects_grid.setContentsMargins(0, 0, 0, 0)
        self.projects_grid.setSpacing(20)
        self.projects_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.projects_container)
        layout.addWidget(scroll)

        self.project_cards = []

    def load_projects(self):
        """加载项目列表"""
        # 清空现有卡片
        while self.projects_grid.count():
            item = self.projects_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.project_cards.clear()

        with session_scope() as session:
            projects = session.query(Project).order_by(
                Project.updated_at.desc().nullsfirst(),
                Project.created_at.desc()
            ).all()

            self.stats_label.setText(f"共 {len(projects)} 个项目")

            cols = 4
            for i, project in enumerate(projects):
                card = ProjectCard(project)
                card.clicked.connect(self._on_project_clicked)
                card.delete_requested.connect(self._delete_project)

                self.projects_grid.addWidget(card, i // cols, i % cols)
                self.project_cards.append(card)

            # 空状态
            if not projects:
                empty_label = QLabel("暂无项目\n点击「新建项目」开始创建")
                empty_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 14px;")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_label.setMinimumHeight(200)
                self.projects_grid.addWidget(empty_label, 0, 0)

    def _filter_projects(self, text: str):
        """过滤项目"""
        text = text.lower()
        for card in self.project_cards:
            visible = text in card.project.get('name', '').lower()
            card.setVisible(visible)

    def _on_project_clicked(self, project_data: dict):
        """项目点击事件"""
        self.project_selected.emit(project_data)

    def _delete_project(self, project_data: dict):
        """删除项目"""
        project_name = project_data.get('name', '未命名')
        project_id = project_data.get('id')

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除项目 '{project_name}' 吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with session_scope() as session:
                p = session.query(Project).get(project_id)
                if p:
                    session.delete(p)

            self.load_projects()
            QMessageBox.information(self, "提示", f"项目 '{project_name}' 已删除")

    def get_recent_projects(self, limit: int = 5):
        """获取最近项目（返回dict列表）"""
        with session_scope() as session:
            projects = session.query(Project).order_by(
                Project.updated_at.desc().nullsfirst(),
                Project.created_at.desc()
            ).limit(limit).all()
            return [p.to_dict() for p in projects]
