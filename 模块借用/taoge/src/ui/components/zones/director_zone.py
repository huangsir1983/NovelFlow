"""
涛割 - 导演画布区
CanvasView 占满整个区域，侧边栏和精编面板为浮动层，带滑动动画。
- 左侧素材框默认隐藏，单击卡片时带动画滑出
- 卡片浮动工具栏跟随选中卡片
- 双击卡片进入独立的场景工作画布（无限画布），进行图片/视频生成
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPointF, QPropertyAnimation, QEasingCurve, QRect
)

from ui import theme
from ..canvas_mode import CanvasView
from ..canvas_sidebar import CanvasSidebar
from ..canvas_context_menu import show_canvas_context_menu


class DirectorCanvasPage(QWidget):
    """
    导演画布页面（page 0）—— 多卡片总览
    从原 DirectorZone 拆出的画布主视图部分
    """

    scene_selected = pyqtSignal(int)
    card_double_clicked = pyqtSignal(int)
    generate_image_requested = pyqtSignal(int)
    generate_video_requested = pyqtSignal(int)
    ai_analyze_requested = pyqtSignal(int)
    scene_deleted = pyqtSignal(int)
    scene_duplicated = pyqtSignal(int)
    batch_generate_requested = pyqtSignal(list)
    character_dropped = pyqtSignal(int, dict)
    prop_dropped = pyqtSignal(int, dict)
    property_changed = pyqtSignal(str, object)

    SIDEBAR_WIDTH = 220
    SIDEBAR_ANIM_DURATION = 250

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes_data: List[Dict[str, Any]] = []
        self._sidebar_visible = False
        self._sidebar_anim: Optional[QPropertyAnimation] = None

        self._init_ui()
        self._connect_floating_toolbar()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # CanvasView 直接占满
        self.canvas_view = CanvasView()
        self.canvas_view.scene_selected.connect(self._on_scene_selected)
        self.canvas_view.card_double_clicked.connect(self.card_double_clicked.emit)
        self.canvas_view.cards_multi_selected.connect(self._on_multi_selected)
        self.canvas_view.card_context_menu_requested.connect(self._on_context_menu_requested)
        self.canvas_view.zoom_changed.connect(self._on_zoom_changed)
        self.canvas_view.character_dropped_on_card.connect(self._on_character_dropped)
        self.canvas_view.prop_dropped_on_card.connect(self._on_prop_dropped)
        self.canvas_view.canvas_blank_clicked.connect(self._on_canvas_blank_clicked)
        layout.addWidget(self.canvas_view, 1)

        # === 侧边栏浮动（左侧）—— 默认隐藏 ===
        self.canvas_sidebar = CanvasSidebar()
        self.canvas_sidebar.setParent(self)
        self.canvas_sidebar.setFixedWidth(self.SIDEBAR_WIDTH)
        self.canvas_sidebar.setVisible(False)

        # === 浮动工具栏（左上角）===
        self._toolbar_float = self._create_toolbar()
        self._toolbar_float.setParent(self)
        self._toolbar_float.raise_()

        self._apply_theme()

    def _create_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("directorToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 6, 10, 6)
        toolbar_layout.setSpacing(8)

        self._grid_btn = QPushButton("网格")
        self._grid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grid_btn.clicked.connect(self._arrange_grid)
        toolbar_layout.addWidget(self._grid_btn)

        self._timeline_btn = QPushButton("时间线")
        self._timeline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timeline_btn.clicked.connect(self._arrange_horizontal)
        toolbar_layout.addWidget(self._timeline_btn)

        self._storyboard_btn = QPushButton("故事板")
        self._storyboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._storyboard_btn.clicked.connect(self._arrange_storyboard)
        toolbar_layout.addWidget(self._storyboard_btn)

        toolbar_layout.addWidget(self._create_sep())

        self.conn_btn = QPushButton("显示连线")
        self.conn_btn.setCheckable(True)
        self.conn_btn.setChecked(True)
        self.conn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.conn_btn.clicked.connect(self._toggle_connections)
        toolbar_layout.addWidget(self.conn_btn)

        self._fit_btn = QPushButton("适应视图")
        self._fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_btn.clicked.connect(self._fit_view)
        toolbar_layout.addWidget(self._fit_btn)

        toolbar_layout.addWidget(self._create_sep())

        self.batch_gen_btn = QPushButton("批量生成")
        self.batch_gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_gen_btn.clicked.connect(self._on_batch_generate)
        toolbar_layout.addWidget(self.batch_gen_btn)

        toolbar_layout.addWidget(self._create_sep())

        self.zoom_label = QLabel("100%")
        toolbar_layout.addWidget(self.zoom_label)

        toolbar_layout.addWidget(self._create_sep())

        self.stats_label = QLabel("0 场景")
        toolbar_layout.addWidget(self.stats_label)

        toolbar.adjustSize()
        return toolbar

    def _connect_floating_toolbar(self):
        toolbar = self.canvas_view.get_floating_toolbar()
        toolbar.generate_image_requested.connect(
            lambda idx: self.generate_image_requested.emit(idx)
        )
        toolbar.generate_video_requested.connect(
            lambda idx: self.generate_video_requested.emit(idx)
        )
        toolbar.ai_analyze_requested.connect(
            lambda idx: self.ai_analyze_requested.emit(idx)
        )
        toolbar.scene_duplicated.connect(
            lambda idx: self.scene_duplicated.emit(idx)
        )
        toolbar.scene_deleted.connect(
            lambda idx: self.scene_deleted.emit(idx)
        )

    # ==================== 侧边栏动画 ====================

    def _slide_in_sidebar(self):
        if self._sidebar_visible:
            return
        self._sidebar_visible = True
        self.canvas_sidebar.setVisible(True)

        start_rect = QRect(-self.SIDEBAR_WIDTH, 0, self.SIDEBAR_WIDTH, self.height())
        end_rect = QRect(0, 0, self.SIDEBAR_WIDTH, self.height())

        self._sidebar_anim = QPropertyAnimation(self.canvas_sidebar, b"geometry")
        self._sidebar_anim.setDuration(self.SIDEBAR_ANIM_DURATION)
        self._sidebar_anim.setStartValue(start_rect)
        self._sidebar_anim.setEndValue(end_rect)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sidebar_anim.start()
        self._position_toolbar()

    def _slide_out_sidebar(self):
        if not self._sidebar_visible:
            return
        self._sidebar_visible = False

        start_rect = QRect(0, 0, self.SIDEBAR_WIDTH, self.height())
        end_rect = QRect(-self.SIDEBAR_WIDTH, 0, self.SIDEBAR_WIDTH, self.height())

        self._sidebar_anim = QPropertyAnimation(self.canvas_sidebar, b"geometry")
        self._sidebar_anim.setDuration(self.SIDEBAR_ANIM_DURATION)
        self._sidebar_anim.setStartValue(start_rect)
        self._sidebar_anim.setEndValue(end_rect)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._sidebar_anim.finished.connect(
            lambda: self.canvas_sidebar.setVisible(False)
        )
        self._sidebar_anim.start()
        self._position_toolbar()

    # ==================== 主题 ====================

    def _apply_theme(self):
        self._toolbar_float.setStyleSheet(f"""
            QFrame#directorToolbar {{
                background-color: {theme.bg_elevated()};
                border-radius: 12px;
            }}
        """)

        tb = theme.tool_btn_style()
        self._grid_btn.setStyleSheet(tb)
        self._timeline_btn.setStyleSheet(tb)
        self._storyboard_btn.setStyleSheet(tb)
        self.conn_btn.setStyleSheet(tb)
        self._fit_btn.setStyleSheet(tb)

        self.batch_gen_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent_bg()};
                color: {theme.accent()};
                border: 1px solid rgba(10, 132, 255, 0.2);
                border-radius: 6px; padding: 5px 12px;
                font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: rgba(10, 132, 255, 0.25);
                color: white;
            }}
        """)

        self.zoom_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 11px; font-family: 'SF Mono', Consolas, monospace; background: transparent;")
        self.stats_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 11px; background: transparent;")

        self.canvas_view.viewport().update()

    def apply_theme(self, dark: bool):
        self._apply_theme()

    # ==================== 布局 ====================

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_all_floats()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_all_floats()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss_all()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _dismiss_all(self):
        self._slide_out_sidebar()
        self.canvas_view._hide_floating_toolbar()

    def _position_toolbar(self):
        self._toolbar_float.adjustSize()
        tw = self._toolbar_float.sizeHint().width()
        th = self._toolbar_float.sizeHint().height()
        self._toolbar_float.setGeometry(12, 12, tw, th)

    def _position_all_floats(self):
        self._position_toolbar()
        if self._sidebar_visible:
            self.canvas_sidebar.setGeometry(0, 0, self.SIDEBAR_WIDTH, self.height())

    # ==================== 交互处理 ====================

    def _on_scene_selected(self, index: int):
        self.scene_selected.emit(index)
        self._slide_in_sidebar()

    def _on_canvas_blank_clicked(self):
        self._dismiss_all()

    def _on_multi_selected(self, indices: list):
        pass

    def _on_context_menu_requested(self, scene_index: int, global_pos: QPointF):
        multi_selected = self.canvas_view.get_multi_selected_indices()
        if scene_index not in multi_selected:
            multi_selected = []
        show_canvas_context_menu(
            parent=self, scene_index=scene_index, global_pos=global_pos,
            multi_selected=multi_selected,
            on_generate_image=lambda idx: self.generate_image_requested.emit(idx),
            on_generate_video=lambda idx: self.generate_video_requested.emit(idx),
            on_open_property=lambda idx: self.card_double_clicked.emit(idx),
            on_batch_generate=lambda indices: self.batch_generate_requested.emit(indices),
            on_delete_scene=lambda idx: self.scene_deleted.emit(idx),
            on_duplicate_scene=lambda idx: self.scene_duplicated.emit(idx),
        )

    def _on_zoom_changed(self, percent: int):
        self.zoom_label.setText(f"{percent}%")

    def _on_character_dropped(self, scene_index: int, char_data: dict):
        self.character_dropped.emit(scene_index, char_data)
        if 0 <= scene_index < len(self.scenes_data):
            chars = self.scenes_data[scene_index].get('characters', [])
            if not any(c.get('id') == char_data.get('id') for c in chars):
                chars.append(char_data)
                self.scenes_data[scene_index]['characters'] = chars
                self.canvas_view.update_card_characters(scene_index, chars)

    def _on_prop_dropped(self, scene_index: int, prop_data: dict):
        self.prop_dropped.emit(scene_index, prop_data)

    def _on_batch_generate(self):
        multi = self.canvas_view.get_multi_selected_indices()
        if multi:
            self.batch_generate_requested.emit(multi)
        else:
            self.batch_generate_requested.emit(list(range(len(self.scenes_data))))

    # ==================== 公开 API ====================

    def load_scenes(self, scenes: list):
        self.scenes_data = scenes
        self.canvas_view.load_scenes(scenes)
        self.stats_label.setText(f"{len(scenes)} 场景")

    def update_card(self, index: int, scene_data: dict):
        self.canvas_view.update_card(index, scene_data)

    def update_card_progress(self, index: int, progress: int, is_generating: bool):
        self.canvas_view.update_card_progress(index, progress, is_generating)

    def select_card(self, index: int):
        self.canvas_view.select_card(index)

    def load_characters(self, characters: list):
        self.canvas_sidebar.load_characters(characters)

    def load_props(self, props: list):
        self.canvas_sidebar.load_props(props)

    # ==================== 辅助 ====================

    def _create_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background-color: {theme.separator()};")
        return sep

    def _arrange_grid(self):
        self.canvas_view.auto_arrange_grid()

    def _arrange_horizontal(self):
        self.canvas_view.auto_arrange_horizontal()

    def _arrange_storyboard(self):
        self.canvas_view.auto_arrange_storyboard()

    def _toggle_connections(self):
        self.canvas_view.set_show_connections(self.conn_btn.isChecked())

    def _fit_view(self):
        self.canvas_view.fit_all_in_view()


# ============================================================
#  DirectorZone —— 使用 QStackedWidget 切换导演画布 / 场景工作画布
# ============================================================

class DirectorZone(QWidget):
    """
    导演画布区 - 场景卡片的可视化编排
    page 0: DirectorCanvasPage（导演画布，多卡片总览）
    page 1: SceneWorkCanvas（单场景无限画布工作区，双击卡片进入）
    page 2: IntelligentCanvasPage（智能画布，多层编辑环境）
    """

    scene_selected = pyqtSignal(int)
    generate_image_requested = pyqtSignal(int)
    generate_video_requested = pyqtSignal(int)
    ai_analyze_requested = pyqtSignal(int)
    scene_deleted = pyqtSignal(int)
    scene_duplicated = pyqtSignal(int)
    batch_generate_requested = pyqtSignal(list)
    character_dropped = pyqtSignal(int, dict)
    prop_dropped = pyqtSignal(int, dict)
    property_changed = pyqtSignal(str, object)
    open_intelligent_canvas = pyqtSignal(int)  # scene_id

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self.scenes_data: List[Dict[str, Any]] = []
        self._scene_work_canvas = None  # 延迟创建
        self._intelligent_canvas_page = None  # 延迟创建

        self._init_ui()
        self._connect_data_hub()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # QStackedWidget 管理页面切换
        self._stack = QStackedWidget()

        # page 0: 导演画布页面
        self._director_page = DirectorCanvasPage()
        self._director_page.scene_selected.connect(self.scene_selected.emit)
        self._director_page.card_double_clicked.connect(self._enter_scene_work_canvas)
        self._director_page.generate_image_requested.connect(self.generate_image_requested.emit)
        self._director_page.generate_video_requested.connect(self.generate_video_requested.emit)
        self._director_page.ai_analyze_requested.connect(self.ai_analyze_requested.emit)
        self._director_page.scene_deleted.connect(self.scene_deleted.emit)
        self._director_page.scene_duplicated.connect(self.scene_duplicated.emit)
        self._director_page.batch_generate_requested.connect(self.batch_generate_requested.emit)
        self._director_page.character_dropped.connect(self.character_dropped.emit)
        self._director_page.prop_dropped.connect(self.prop_dropped.emit)
        self._director_page.property_changed.connect(self.property_changed.emit)
        self._stack.addWidget(self._director_page)  # index 0

        layout.addWidget(self._stack, 1)

    def _ensure_scene_work_canvas(self):
        """延迟创建场景工作画布"""
        if self._scene_work_canvas is None:
            from ..scene_work_canvas import SceneWorkCanvas
            self._scene_work_canvas = SceneWorkCanvas()
            self._scene_work_canvas.back_requested.connect(self._exit_scene_work_canvas)
            self._scene_work_canvas.generate_image_requested.connect(
                self.generate_image_requested.emit
            )
            self._scene_work_canvas.generate_video_requested.connect(
                self.generate_video_requested.emit
            )
            self._scene_work_canvas.ai_analyze_requested.connect(
                self.ai_analyze_requested.emit
            )
            self._scene_work_canvas.property_changed.connect(
                self._on_work_canvas_property_changed
            )
            self._stack.addWidget(self._scene_work_canvas)  # index 1

    def _enter_scene_work_canvas(self, scene_index: int):
        """双击卡片 → 进入场景工作画布"""
        if 0 <= scene_index < len(self.scenes_data):
            self._ensure_scene_work_canvas()
            self._scene_work_canvas.load_scene(scene_index, self.scenes_data[scene_index])
            self._stack.setCurrentWidget(self._scene_work_canvas)

    def _exit_scene_work_canvas(self):
        """从场景工作画布返回导演画布"""
        self._stack.setCurrentWidget(self._director_page)

    def _on_work_canvas_property_changed(self, prop: str, value):
        """场景工作画布中属性变更"""
        if self._scene_work_canvas and self._scene_work_canvas.current_scene_index >= 0:
            idx = self._scene_work_canvas.current_scene_index
            if self.data_hub:
                self.data_hub.update_scene_property(idx, prop, value)
            else:
                self.property_changed.emit(prop, value)

    # ==================== 智能画布 (page 2) ====================

    def _ensure_intelligent_canvas(self):
        """延迟创建智能画布页面"""
        if self._intelligent_canvas_page is None:
            from ..intelligent_canvas_page import IntelligentCanvasPage
            self._intelligent_canvas_page = IntelligentCanvasPage(
                data_hub=self.data_hub
            )
            self._intelligent_canvas_page.back_requested.connect(
                self._exit_intelligent_canvas
            )
            self._intelligent_canvas_page.scene_saved.connect(
                self._on_intelligent_canvas_saved
            )
            self._stack.addWidget(self._intelligent_canvas_page)  # index 2

    def enter_intelligent_canvas(self, scene_id: int):
        """进入智能画布编辑场景"""
        self._ensure_intelligent_canvas()
        self._intelligent_canvas_page.load_scene(scene_id)
        self._stack.setCurrentWidget(self._intelligent_canvas_page)

    def _exit_intelligent_canvas(self):
        """从智能画布返回导演画布"""
        self._stack.setCurrentWidget(self._director_page)

    def _on_intelligent_canvas_saved(self, scene_id: int):
        """智能画布保存后刷新场景数据"""
        if self.data_hub:
            self.data_hub.reload_scenes_only()

    # ==================== DataHub 信号连接 ====================

    def _connect_data_hub(self):
        if not self.data_hub:
            return
        self.data_hub.scenes_loaded.connect(self._on_scenes_loaded)
        self.data_hub.characters_loaded.connect(self._on_characters_loaded)
        self.data_hub.props_loaded.connect(self._on_props_loaded)
        self.data_hub.scene_updated.connect(self._on_scene_updated)
        self.data_hub.generation_progress.connect(self._on_generation_progress)
        self.data_hub.generation_completed.connect(self._on_generation_completed)
        self.data_hub.generation_started.connect(self._on_generation_started)
        self.data_hub.generation_failed.connect(self._on_generation_failed)

    # ==================== DataHub 信号处理 ====================

    def _on_scenes_loaded(self, scenes: list):
        self.scenes_data = scenes
        self._director_page.scenes_data = scenes
        self._director_page.load_scenes(scenes)

    def _on_characters_loaded(self, characters: list):
        self._director_page.load_characters(characters)

    def _on_props_loaded(self, props: list):
        self._director_page.load_props(props)

    def _on_scene_updated(self, index: int, scene_data: dict):
        if 0 <= index < len(self.scenes_data):
            self.scenes_data[index] = scene_data
            self._director_page.scenes_data = self.scenes_data
            self._director_page.update_card(index, scene_data)

            # 同步更新场景工作画布（如果正在查看此场景）
            if (self._scene_work_canvas and
                    self._stack.currentWidget() == self._scene_work_canvas and
                    self._scene_work_canvas.current_scene_index == index):
                self._scene_work_canvas.update_scene_data(scene_data)

    def _on_generation_started(self, scene_id: int, task_type: str):
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self._director_page.update_card_progress(index, 5, True)
            # 同步到场景工作画布
            if (self._scene_work_canvas and
                    self._stack.currentWidget() == self._scene_work_canvas and
                    self._scene_work_canvas.current_scene_index == index):
                self._scene_work_canvas.update_generation_progress(task_type, 5, True)

    def _on_generation_progress(self, scene_id: int, task_type: str, progress: int):
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self._director_page.update_card_progress(index, progress, True)
            if (self._scene_work_canvas and
                    self._stack.currentWidget() == self._scene_work_canvas and
                    self._scene_work_canvas.current_scene_index == index):
                self._scene_work_canvas.update_generation_progress(task_type, progress, True)

    def _on_generation_completed(self, scene_id: int, task_type: str, result_path: str):
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self._director_page.update_card_progress(index, 100, False)
            if (self._scene_work_canvas and
                    self._stack.currentWidget() == self._scene_work_canvas and
                    self._scene_work_canvas.current_scene_index == index):
                self._scene_work_canvas.update_generation_progress(task_type, 100, False)

    def _on_generation_failed(self, scene_id: int, task_type: str, error: str):
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self._director_page.update_card_progress(index, 0, False)
            if (self._scene_work_canvas and
                    self._stack.currentWidget() == self._scene_work_canvas and
                    self._scene_work_canvas.current_scene_index == index):
                self._scene_work_canvas.update_generation_progress(task_type, 0, False)

    # ==================== 主题 ====================

    def apply_theme(self, dark: bool):
        self._director_page.apply_theme(dark)
        if self._scene_work_canvas:
            self._scene_work_canvas.apply_theme(dark)
        if self._intelligent_canvas_page:
            self._intelligent_canvas_page.apply_theme()

    # ==================== 公开 API ====================

    def load_scenes(self, scenes: list):
        self.scenes_data = scenes
        self._director_page.scenes_data = scenes
        self._director_page.load_scenes(scenes)

    def select_scene(self, index: int):
        self._director_page.select_card(index)

    def refresh_sidebar(self):
        if self.data_hub:
            self._director_page.load_characters(self.data_hub.characters_data)
            self._director_page.load_props(self.data_hub.props_data)

    # Expose canvas_view for external access (backwards compat)
    @property
    def canvas_view(self):
        return self._director_page.canvas_view

    @property
    def canvas_sidebar(self):
        return self._director_page.canvas_sidebar

    # ==================== 辅助 ====================

    def _find_scene_index(self, scene_id: int) -> int:
        for i, s in enumerate(self.scenes_data):
            if s.get('id') == scene_id:
                return i
        return -1

    def keyPressEvent(self, event):
        """Esc 键：在场景工作画布或智能画布中返回导演画布"""
        if event.key() == Qt.Key.Key_Escape:
            if (self._intelligent_canvas_page and
                    self._stack.currentWidget() == self._intelligent_canvas_page):
                self._exit_intelligent_canvas()
                event.accept()
                return
            if (self._scene_work_canvas and
                    self._stack.currentWidget() == self._scene_work_canvas):
                self._exit_scene_work_canvas()
                event.accept()
                return
        super().keyPressEvent(event)
