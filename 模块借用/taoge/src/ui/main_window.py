"""
涛割 - 主窗口
"""

import sys
import os
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFileDialog, QMessageBox,
    QSplitter, QFrame, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QAction

from .resources.dark_theme import DARK_THEME_QSS, get_theme_qss, is_dark_theme
from .components.settings_page import SettingsPage
from .components.materials_page import MaterialsPage
from .components.tasks_page import TasksPage
from .components.srt_import_dialog import SrtImportDialog
from .components.projects_page import ProjectsPage
from .components.infinite_canvas_page import InfiniteCanvasPage
from config import get_settings, get_settings_manager
from database import get_db_manager, Project, session_scope
from services.controllers import ProjectController, CanvasController
from ui import theme


class SidebarButton(QPushButton):
    """苹果风格侧边栏按钮"""

    def __init__(self, text: str, icon_path: str = None, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)

        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(18, 18))

        self._apply_theme()

    def _apply_theme(self):
        if theme.is_dark():
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #8e8e93;
                    border: none;
                    text-align: left;
                    padding-left: 16px;
                    font-size: 13px;
                    font-weight: 500;
                    border-radius: 8px;
                    margin: 1px 8px;
                    font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.06);
                    color: #f5f5f7;
                }
                QPushButton:checked {
                    background-color: rgba(10, 132, 255, 0.15);
                    color: #0a84ff;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #6e6e73;
                    border: none;
                    text-align: left;
                    padding-left: 16px;
                    font-size: 13px;
                    font-weight: 500;
                    border-radius: 8px;
                    margin: 1px 8px;
                    font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.04);
                    color: #1c1c1e;
                }
                QPushButton:checked {
                    background-color: rgba(0, 122, 255, 0.10);
                    color: #007aff;
                }
            """)


class MainWindow(QMainWindow):
    """
    涛割主窗口
    支持双模式：向导模式 (Wizard) 和 画布模式 (Canvas)
    """

    project_changed = pyqtSignal(object)  # 项目变更信号

    def __init__(self):
        super().__init__()

        # 初始化配置和数据库
        self.settings = get_settings()
        self.settings_manager = get_settings_manager()
        self.db_manager = get_db_manager()

        # 当前项目
        self.current_project: Optional[Project] = None

        # 初始化UI
        self._init_ui()
        self._init_menu()
        self._connect_signals()

        # 加载最近项目
        self._load_recent_projects()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"{self.settings.app_name} - AI视频生成平台")
        self.setMinimumSize(1400, 900)

        # 根据配置应用主题
        theme_name = self.settings.ui.theme if hasattr(self.settings, 'ui') else "dark"
        theme.set_dark(is_dark_theme(theme_name))
        self.setStyleSheet(get_theme_qss(theme_name))

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)

        # 主内容区
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        # 添加页面
        self._create_pages()

        # 默认显示首页
        self._switch_to_page(0)

    def _create_sidebar(self) -> QWidget:
        """创建苹果风格侧边栏"""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        self._apply_sidebar_theme(sidebar)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo区域
        logo_widget = QWidget()
        logo_widget.setFixedHeight(72)
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(16, 20, 16, 8)
        logo_label = QLabel(self.settings.app_name)
        logo_label.setObjectName("logoLabel")
        logo_label.setFont(QFont("SF Pro Display", 20, QFont.Weight.Bold))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        logo_label.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")
        logo_layout.addWidget(logo_label)
        layout.addWidget(logo_widget)

        layout.addSpacing(8)

        # 导航按钮
        self.nav_buttons = []

        nav_items = [
            ("首页", None),
            ("新建项目", None),
            ("我的项目", None),
            ("资产库", None),
            ("任务队列", None),
            ("设置", None),
        ]

        for text, icon in nav_items:
            btn = SidebarButton(text, icon)
            current_idx = len(self.nav_buttons)
            if current_idx == 1:
                # "新建项目"按钮 → 直接创建空白项目进入模式选择
                btn.clicked.connect(lambda checked: self._create_blank_project())
            else:
                btn.clicked.connect(lambda checked, idx=current_idx: self._switch_to_page(idx))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        layout.addStretch()

        # 积分显示
        credits_widget = QWidget()
        credits_widget.setFixedHeight(48)
        credits_layout = QVBoxLayout(credits_widget)
        credits_layout.setContentsMargins(16, 8, 16, 12)

        self.credits_label = QLabel(f"积分  {self.settings.credits.balance:.0f}")
        self.credits_label.setObjectName("creditsLabel")
        self.credits_label.setStyleSheet(f"""
            color: {theme.text_secondary()};
            font-size: 12px;
            background: transparent;
            font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif;
        """)
        credits_layout.addWidget(self.credits_label)

        layout.addWidget(credits_widget)

        return sidebar

    def _create_pages(self):
        """创建各个页面（素材库/任务/设置延迟加载）"""
        # 记录哪些页面已实际创建
        self._page_initialized = set()

        # 首页（立即创建）
        home_page = self._create_home_page()
        self.content_stack.addWidget(home_page)
        self._page_initialized.add(0)

        # 新建项目页（立即创建）
        new_project_page = self._create_new_project_page()
        self.content_stack.addWidget(new_project_page)
        self._page_initialized.add(1)

        # 我的项目页（立即创建）
        projects_page = self._create_projects_page()
        self.content_stack.addWidget(projects_page)
        self._page_initialized.add(2)

        # 素材库页（占位，延迟创建）
        self.content_stack.addWidget(QWidget())

        # 任务队列页（占位，延迟创建）
        self.content_stack.addWidget(QWidget())

        # 设置页（占位，延迟创建）
        self.content_stack.addWidget(QWidget())

        # 场景编辑器页（索引6） → 替换为全屏四区域入口页
        self.scene_editor = InfiniteCanvasPage()
        self.scene_editor.back_requested.connect(self._on_editor_back)
        self.content_stack.addWidget(self.scene_editor)
        self._page_initialized.add(6)

        # 资产编辑器占位（索引7），运行时按需替换
        self.content_stack.addWidget(QWidget())
        self._asset_editor = None

    def _create_home_page(self) -> QWidget:
        """创建苹果风格首页"""
        page = QWidget()
        page.setObjectName("homePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(24)

        # 欢迎标题
        title = QLabel(f"欢迎使用 {self.settings.app_name}")
        title.setObjectName("homeTitle")
        title.setFont(QFont("SF Pro Display", 32, QFont.Weight.Bold))
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("AI驱动的精品短剧视频生成平台")
        subtitle.setObjectName("homeSubtitle")
        subtitle.setFont(QFont("SF Pro Display", 15))
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # 快捷操作区
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(16)

        new_project_card = self._create_action_card(
            "新建项目",
            "创建新项目并选择创作模式（剧情/解说）",
            "立即创建",
            self._create_blank_project
        )
        actions_layout.addWidget(new_project_card)

        open_project_card = self._create_action_card(
            "打开项目",
            "继续编辑现有的视频项目",
            "浏览项目",
            lambda: self._switch_to_page(2)
        )
        actions_layout.addWidget(open_project_card)

        materials_card = self._create_action_card(
            "资产库",
            "管理角色、服装、场景和道具资产",
            "打开资产库",
            lambda: self._switch_to_page(3)
        )
        actions_layout.addWidget(materials_card)

        layout.addLayout(actions_layout)

        # 最近项目
        layout.addSpacing(24)
        recent_title = QLabel("最近项目")
        recent_title.setObjectName("recentTitle")
        recent_title.setFont(QFont("SF Pro Display", 17, QFont.Weight.DemiBold))
        layout.addWidget(recent_title)

        self.recent_projects_list = QListWidget()
        self.recent_projects_list.setObjectName("recentList")
        self.recent_projects_list.setMaximumHeight(200)
        layout.addWidget(self.recent_projects_list)

        layout.addStretch()

        return page

    def _create_action_card(self, title: str, desc: str, btn_text: str, on_click) -> QFrame:
        """创建苹果风格操作卡片"""
        card = QFrame()
        card.setObjectName("actionCard")
        card.setFixedSize(280, 180)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_label.setFont(QFont("SF Pro Display", 17, QFont.Weight.DemiBold))
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setObjectName("cardDesc")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addStretch()

        btn = QPushButton(btn_text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("primary", True)
        btn.clicked.connect(on_click)
        layout.addWidget(btn)

        return card

    def _create_new_project_page(self) -> QWidget:
        """创建苹果风格新建项目页"""
        page = QWidget()
        page.setObjectName("newProjectPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(24)

        title = QLabel("新建项目")
        title.setObjectName("npTitle")
        title.setFont(QFont("SF Pro Display", 28, QFont.Weight.Bold))
        layout.addWidget(title)

        # 导入选项
        import_layout = QHBoxLayout()
        import_layout.setSpacing(16)

        # SRT导入
        srt_btn = QPushButton("导入SRT字幕")
        srt_btn.setObjectName("importBtn")
        srt_btn.setFixedSize(200, 120)
        srt_btn.clicked.connect(self._import_srt)
        import_layout.addWidget(srt_btn)

        # 剧本导入
        script_btn = QPushButton("导入剧本")
        script_btn.setObjectName("importBtn")
        script_btn.setFixedSize(200, 120)
        script_btn.clicked.connect(self._import_script)
        import_layout.addWidget(script_btn)

        # 空白项目
        blank_btn = QPushButton("空白项目")
        blank_btn.setObjectName("importBtn")
        blank_btn.setFixedSize(200, 120)
        blank_btn.clicked.connect(self._create_blank_project)
        import_layout.addWidget(blank_btn)

        import_layout.addStretch()
        layout.addLayout(import_layout)

        layout.addStretch()

        return page

    def _create_projects_page(self) -> QWidget:
        """创建项目列表页"""
        self.projects_page = ProjectsPage()
        self.projects_page.project_selected.connect(self._on_project_selected)
        return self.projects_page

    def _create_materials_page(self) -> QWidget:
        """创建素材库页"""
        self.materials_page = MaterialsPage()
        self.materials_page.edit_asset_requested.connect(
            self._open_asset_editor
        )
        return self.materials_page

    def _create_tasks_page(self) -> QWidget:
        """创建任务队列页"""
        self.tasks_page = TasksPage()
        return self.tasks_page

    def _create_settings_page(self) -> QWidget:
        """创建设置页"""
        self.settings_page = SettingsPage()
        self.settings_page.settings_changed.connect(self._on_settings_changed)
        return self.settings_page

    def _init_menu(self):
        """初始化菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        new_action = QAction("新建项目", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._create_blank_project)
        file_menu.addAction(new_action)

        open_action = QAction("打开项目", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        import_srt = QAction("导入SRT", self)
        import_srt.triggered.connect(self._import_srt)
        file_menu.addAction(import_srt)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")

        # 视图菜单
        view_menu = menubar.addMenu("视图")

        canvas_action = QAction("智能画布", self)
        canvas_action.setShortcut("Ctrl+Shift+E")
        canvas_action.triggered.connect(self._open_intelligent_canvas)
        view_menu.addAction(canvas_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _connect_signals(self):
        """连接信号"""
        self.project_changed.connect(self._on_project_changed)

    def _switch_to_page(self, index: int):
        """切换页面（首次访问时延迟创建）"""
        # 延迟创建尚未初始化的页面
        if index not in self._page_initialized:
            self._lazy_create_page(index)

        self.content_stack.setCurrentIndex(index)

        # 更新侧边栏按钮状态
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

    def _lazy_create_page(self, index: int):
        """延迟创建指定索引的页面，替换占位Widget"""
        creators = {
            3: self._create_materials_page,
            4: self._create_tasks_page,
            5: self._create_settings_page,
        }
        creator = creators.get(index)
        if creator:
            old_widget = self.content_stack.widget(index)
            new_page = creator()
            self.content_stack.insertWidget(index, new_page)
            self.content_stack.removeWidget(old_widget)
            old_widget.deleteLater()
            self._page_initialized.add(index)

    def _load_recent_projects(self):
        """加载最近项目"""
        self.recent_projects_list.clear()

        with session_scope() as session:
            projects = session.query(Project).order_by(
                Project.updated_at.desc().nullsfirst(),
                Project.created_at.desc()
            ).limit(5).all()

            for project in projects:
                item = QListWidgetItem(f"{project.name}  ({project.total_scenes} 个场景)")
                item.setData(Qt.ItemDataRole.UserRole, project.id)
                self.recent_projects_list.addItem(item)

            if not projects:
                item = QListWidgetItem("暂无项目")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.recent_projects_list.addItem(item)

        # 连接双击事件
        try:
            self.recent_projects_list.itemDoubleClicked.disconnect()
        except:
            pass
        self.recent_projects_list.itemDoubleClicked.connect(self._on_recent_project_clicked)

    def _on_recent_project_clicked(self, item: QListWidgetItem):
        """最近项目点击事件"""
        project_id = item.data(Qt.ItemDataRole.UserRole)
        if project_id:
            with session_scope() as session:
                project = session.query(Project).get(project_id)
                if project:
                    # 在 session 内提取需要的数据
                    project_data = {'id': project.id, 'name': project.name}
                    self._on_project_selected(project_data)

    def _on_project_selected(self, project_data):
        """项目选中事件"""
        # 确保 project_data 是 dict
        if not isinstance(project_data, dict):
            if hasattr(project_data, 'to_dict'):
                project_data = project_data.to_dict()
            else:
                project_data = {'id': getattr(project_data, 'id', None), 'name': '未命名'}

        self.project_changed.emit(project_data)
        # 打开场景编辑器
        project_id = project_data.get('id')
        self.scene_editor.load_project(project_id)
        self.content_stack.setCurrentIndex(6)  # 切换到场景编辑器
        self.sidebar.setVisible(False)  # 隐藏侧边栏
        self.menuBar().setVisible(False)  # 隐藏菜单栏
        # 去掉原生标题栏，由 TopNavigationBar 红绿灯按钮替代
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.show()

    def _on_editor_back(self):
        """从编辑器返回 — 与 _on_project_selected 对称"""
        # 1) 先切页面（和进入项目时一样：先切页面，后改窗口标志）
        self.content_stack.setCurrentIndex(2)  # 返回我的项目页
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == 2)
        self.sidebar.setVisible(True)
        self.menuBar().setVisible(True)

        # 2) 恢复原生标题栏 — setWindowFlag 会销毁并重建原生窗口
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.show()

        # 3) 刷新项目列表
        self.projects_page.load_projects()

    def _open_asset_editor(self, asset_data: dict):
        """打开对应类型的全屏资产编辑器（索引7）"""
        # 使用 DataHub 中的同一个 controller 实例，确保信号链路完整
        controller = self.scene_editor.data_hub.asset_controller
        asset_type = asset_data.get('asset_type', '')

        if asset_type == 'character':
            from ui.components.asset_editors.character_editor import CharacterEditor
            editor = CharacterEditor(asset_data, controller)
        elif asset_type == 'scene_bg':
            from ui.components.asset_editors.scene_editor import SceneEditor
            editor = SceneEditor(asset_data, controller)
        elif asset_type == 'prop':
            from ui.components.asset_editors.prop_editor import PropEditor
            editor = PropEditor(asset_data, controller)
        else:
            from ui.components.asset_editors.scene_editor import SceneEditor
            editor = SceneEditor(asset_data, controller)

        editor.back_requested.connect(self._on_asset_editor_back)
        editor.asset_saved.connect(self._on_asset_editor_saved)

        # 替换索引7处的 widget
        old = self.content_stack.widget(7)
        self.content_stack.insertWidget(7, editor)
        self.content_stack.removeWidget(old)
        old.deleteLater()
        self._asset_editor = editor
        self._page_initialized.add(7)

        self.content_stack.setCurrentIndex(7)

    def _on_asset_editor_back(self):
        """从资产编辑器返回素材库"""
        self._switch_to_page(3)

    def _on_asset_editor_saved(self, asset_id: int):
        """资产编辑器保存成功 — 刷新素材库"""
        if hasattr(self, 'materials_page') and self.materials_page:
            self.materials_page._load_materials()

    def _import_srt(self):
        """导入SRT文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择SRT字幕文件",
            "",
            "SRT字幕文件 (*.srt);;所有文件 (*.*)"
        )

        if file_path:
            dialog = SrtImportDialog(file_path, self)
            dialog.project_created.connect(self._on_project_created)
            dialog.exec()

    def _import_script(self):
        """导入剧本 → 创建项目 → 进入编辑器 → 弹出分镜分析"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择剧本文件",
            "",
            "文本文件 (*.txt);;Word文档 (*.docx);;所有文件 (*.*)"
        )

        if not file_path:
            return

        # 读取文本
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法读取文件: {e}")
                return
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取文件: {e}")
            return

        if not content.strip():
            QMessageBox.warning(self, "错误", "文件内容为空")
            return

        # 创建项目
        import os
        project_name = os.path.splitext(os.path.basename(file_path))[0]

        project_controller = ProjectController()
        project_data = project_controller.create_project(
            name=project_name,
            description=f"从剧本导入: {os.path.basename(file_path)}",
            source_type="script"
        )

        if not project_data:
            QMessageBox.warning(self, "错误", "创建项目失败")
            return

        project_id = project_data['id']

        # 保存源文案
        canvas_controller = CanvasController()
        canvas_controller.save_source_content(project_id, content, "script")

        # 进入编辑器
        self.scene_editor.load_project(project_id)
        self.content_stack.setCurrentIndex(6)
        self.sidebar.setVisible(False)
        self.menuBar().setVisible(False)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.show()

        self._load_recent_projects()
        self.project_changed.emit(project_data)

        # 弹出分镜分析对话框
        from .components.storyboard_analysis_dialog import StoryboardAnalysisDialog
        dialog = StoryboardAnalysisDialog(project_id, content, self)
        dialog.analysis_completed.connect(self._on_script_analysis_completed)
        dialog.exec()

    def _on_script_analysis_completed(self, project_id, scenes, characters):
        """剧本导入后分镜分析完成"""
        success = self.scene_editor.data_hub.save_analysis_results(
            project_id, characters, scenes
        )
        if success:
            # 自动跳转到导演画布区
            self.scene_editor._navigate_to_zone(2)

    def _create_blank_project(self):
        """创建空白项目 → 直接进入编辑器 → 显示模式选择"""
        project_controller = ProjectController()
        project_data = project_controller.create_project(
            name="未命名项目",
            description="",
            source_type=""  # 空类型 → ScriptZone 会显示模式选择页
        )

        if not project_data:
            QMessageBox.warning(self, "错误", "创建项目失败")
            return

        self._on_project_selected(project_data)
        self._load_recent_projects()

    def _open_intelligent_canvas(self):
        """Ctrl+Shift+E → 打开当前选中分镜的智能画布"""
        if not hasattr(self, 'scene_editor'):
            return
        data_hub = self.scene_editor.data_hub
        if not data_hub or not data_hub.scenes_data:
            return
        # 找到当前选中的场景，默认第一个
        scene_id = data_hub.scenes_data[0].get('id')
        if scene_id:
            data_hub.open_intelligent_canvas.emit(scene_id)

    def _open_project(self):
        """打开项目"""
        self._switch_to_page(2)

    def _on_project_created(self, project_data):
        """项目创建完成"""
        self.project_changed.emit(project_data)
        self._load_recent_projects()
        # 切换到我的项目页面
        self._switch_to_page(2)

    def _on_project_changed(self, project_data):
        """项目变更处理"""
        self.current_project = project_data
        if project_data:
            if isinstance(project_data, dict):
                name = project_data.get('name', '未命名')
            else:
                # 安全处理：尝试转为dict
                try:
                    name = project_data.to_dict().get('name', '未命名') if hasattr(project_data, 'to_dict') else str(project_data)
                except Exception:
                    name = '未命名'
            self.setWindowTitle(f"{self.settings.app_name} - {name}")

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            f"关于 {self.settings.app_name}",
            f"{self.settings.app_name} v{self.settings.app_version}\n\n"
            "AI驱动的精品短剧视频生成平台\n\n"
            "功能特点:\n"
            "- 先图后视频(I2V)生成流程\n"
            "- 多模型智能路由\n"
            "- 角色一致性控制\n"
            "- 剪映项目导出\n"
            "- 积分制成本追踪"
        )

    def _on_settings_changed(self):
        """设置变更后的回调"""
        self.apply_theme()
        self.update_credits_display()

    def apply_theme(self):
        """根据当前设置动态切换主题"""
        theme_name = self.settings.ui.theme if hasattr(self.settings, 'ui') else "dark"
        dark = is_dark_theme(theme_name)

        # 设置全局主题状态
        theme.set_dark(dark)

        # 应用全局 QSS
        qss = get_theme_qss(theme_name)
        self.setStyleSheet(qss)

        # 侧边栏
        self._apply_sidebar_theme(self.sidebar)

        # 侧边栏按钮
        for btn in self.nav_buttons:
            if isinstance(btn, SidebarButton):
                btn._apply_theme()

        # Logo
        logo = self.sidebar.findChild(QLabel, "logoLabel")
        if logo:
            logo.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")

        # 积分
        self.credits_label.setStyleSheet(f"""
            color: {theme.text_secondary()};
            font-size: 12px;
            background: transparent;
            font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif;
        """)

        # 首页卡片/导入按钮等 — 通过主页面刷新
        self._apply_home_theme()
        self._apply_new_project_theme()

        # 通知 InfiniteCanvasPage
        if hasattr(self, 'scene_editor'):
            self.scene_editor.apply_theme(dark)

    def update_credits_display(self):
        """更新积分显示"""
        self.credits_label.setText(f"积分  {self.settings.credits.balance:.0f}")

    def _apply_sidebar_theme(self, sidebar: QWidget):
        """设置侧边栏主题样式"""
        if theme.is_dark():
            sidebar.setStyleSheet("""
                QWidget#sidebar {
                    background-color: rgba(28, 28, 30, 0.95);
                    border-right: 1px solid rgba(255, 255, 255, 0.04);
                }
            """)
        else:
            sidebar.setStyleSheet("""
                QWidget#sidebar {
                    background-color: rgba(242, 242, 247, 0.95);
                    border-right: 1px solid rgba(0, 0, 0, 0.06);
                }
            """)

    def _apply_home_theme(self):
        """刷新首页主题颜色"""
        home = self.content_stack.widget(0)
        if not home:
            return
        home.setStyleSheet(f"background-color: {theme.bg_primary()};")
        t = home.findChild(QLabel, "homeTitle")
        if t:
            t.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")
        s = home.findChild(QLabel, "homeSubtitle")
        if s:
            s.setStyleSheet(f"color: {theme.text_secondary()}; background: transparent;")
        rt = home.findChild(QLabel, "recentTitle")
        if rt:
            rt.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")

        # action cards
        for card in home.findChildren(QFrame, "actionCard"):
            card.setStyleSheet(f"""
                QFrame#actionCard {{
                    background-color: {theme.bg_secondary()};
                    border: 1px solid {theme.border()};
                    border-radius: 16px;
                }}
                QFrame#actionCard:hover {{
                    border-color: rgba(10, 132, 255, 0.35);
                }}
            """)
            for lbl in card.findChildren(QLabel, "cardTitle"):
                lbl.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")
            for lbl in card.findChildren(QLabel, "cardDesc"):
                lbl.setStyleSheet(f"color: {theme.text_secondary()}; background: transparent; font-size: 13px;")

    def _apply_new_project_theme(self):
        """刷新新建项目页主题颜色"""
        page = self.content_stack.widget(1)
        if not page:
            return
        page.setStyleSheet(f"background-color: {theme.bg_primary()};")
        t = page.findChild(QLabel, "npTitle")
        if t:
            t.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")
        for btn in page.findChildren(QPushButton, "importBtn"):
            if theme.is_dark():
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2c2c2e;
                        border: 2px dashed rgba(255, 255, 255, 0.12);
                        border-radius: 16px;
                        color: #8e8e93;
                        font-size: 14px; font-weight: 500;
                    }
                    QPushButton:hover {
                        border-color: #0a84ff; color: #0a84ff;
                        background-color: rgba(10, 132, 255, 0.06);
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        border: 2px dashed rgba(0, 0, 0, 0.12);
                        border-radius: 16px;
                        color: #6e6e73;
                        font-size: 14px; font-weight: 500;
                    }
                    QPushButton:hover {
                        border-color: #007aff; color: #007aff;
                        background-color: rgba(0, 122, 255, 0.04);
                    }
                """)

    def closeEvent(self, event):
        """关闭事件"""
        # 保存配置
        self.settings_manager.save_settings()
        event.accept()


def run_app():
    """运行应用"""
    app = QApplication(sys.argv)

    # 设置应用信息
    app.setApplicationName("涛割")
    app.setApplicationVersion("1.0.0")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
