"""
涛割 - 剧情模式面板
统一无限画布：三个 ZoneFrame（大场景序列 | 分镜节奏 | 剧本执行）
替代原有 QSplitter 三栏布局。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from ui import theme
from .unified_story_canvas import UnifiedStoryCanvasView


class StoryModePanel(QWidget):
    """
    剧情模式面板 — 统一无限画布
    三个区域各用 ZoneFrame 包裹，支持自由拖拽、缩放、跨区域连线。
    """

    analysis_completed = pyqtSignal(int, list, list)  # project_id, scenes, characters

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub

        self._init_ui()
        self._connect_data_hub()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 统一无限画布
        self._canvas = UnifiedStoryCanvasView(data_hub=self.data_hub)
        layout.addWidget(self._canvas)

        # 连接画布信号
        self._canvas.shots_changed.connect(self._on_shots_changed)

    def _connect_data_hub(self):
        if not self.data_hub:
            return
        self.data_hub.project_loaded.connect(self._canvas.on_project_loaded)
        self.data_hub.acts_loaded.connect(self._canvas.on_acts_loaded)

    def _on_shots_changed(self):
        """分镜列表变更后，通知导演画布区同步（不触发全量重载，避免大场景序列区布局被重置）"""
        if self.data_hub and self.data_hub.current_project_id:
            # 仅重新加载场景数据，不触发 project_loaded / acts_loaded 信号
            self.data_hub.reload_scenes_only()

    # ==================== 兼容旧接口 ====================

    @property
    def _act_panel(self):
        """兼容旧代码中对 _act_panel 的引用"""
        return self._canvas._act_delegate if self._canvas else None

    def apply_theme(self, dark: bool = None):
        self._apply_theme()

    def _apply_theme(self):
        if self._canvas:
            self._canvas.apply_theme()
