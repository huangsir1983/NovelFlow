"""
涛割 - 智能PS独立最大化窗口
ComfyUI 风格节点画布窗口，替代嵌入统一画布的 SmartPSAgentNode。
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

from ui import theme
from .smart_ps_node_canvas import SmartPSNodeCanvas


class SmartPSWindow(QDialog):
    """ComfyUI 风格智能PS节点画布窗口（独立最大化）"""

    image_saved = pyqtSignal(int, int, str)  # scene_index, scene_id, image_path
    closed = pyqtSignal(int)                 # scene_index

    def __init__(self, scene_index: int, scene_id: int, data_hub,
                 assets: list, first_open: bool = True, parent=None):
        super().__init__(parent)
        self._scene_index = scene_index
        self._scene_id = scene_id
        self._data_hub = data_hub
        self._assets = assets
        self._first_open = first_open

        self.setWindowTitle(f"智能PS — 场景 {scene_index + 1}")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(1200, 800)

        self._init_ui()
        self.showMaximized()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- 顶栏 ---
        topbar = QWidget()
        topbar.setFixedHeight(48)
        is_dark = theme.is_dark()
        topbar.setStyleSheet(
            f"background: {'#1e1e2e' if is_dark else '#f0f0f5'}; "
            f"border-bottom: 1px solid {'#3a3a4a' if is_dark else '#d0d0d8'};"
        )

        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(16, 0, 16, 0)

        # 返回按钮
        back_btn = QPushButton("← 返回")
        back_btn.setFixedSize(80, 32)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(self._btn_style(is_dark))
        back_btn.clicked.connect(self.close)
        top_layout.addWidget(back_btn)

        # 标题
        title = QLabel(f"智能PS — 场景 {self._scene_index + 1}")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {'#e0e0ef' if is_dark else '#2a2a3a'}; "
            "border: none; background: transparent;"
        )
        top_layout.addWidget(title)

        top_layout.addStretch()

        # 确认输出按钮
        confirm_btn = QPushButton("确认输出")
        confirm_btn.setFixedSize(100, 32)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet(self._accent_btn_style())
        confirm_btn.clicked.connect(self._do_confirm_output)
        top_layout.addWidget(confirm_btn)

        layout.addWidget(topbar)

        # --- 节点画布 ---
        self._node_canvas = SmartPSNodeCanvas(
            scene_id=self._scene_id,
            data_hub=self._data_hub,
            assets=self._assets,
            first_open=self._first_open,
            parent=self,
        )
        self._node_canvas.output_ready.connect(self._on_output_ready)
        layout.addWidget(self._node_canvas, 1)

    def _do_confirm_output(self):
        """顶栏确认输出按钮"""
        path = self._node_canvas.export_output()
        if path:
            self._on_output_ready(path)
        else:
            # 尝试直接从 PS 画布导出
            if self._node_canvas._ps_node:
                path = self._node_canvas._ps_node.export_composite_image()
                if path:
                    self._on_output_ready(path)

    def _on_output_ready(self, path: str):
        """输出图片路径就绪"""
        self.image_saved.emit(self._scene_index, self._scene_id, path)

    def closeEvent(self, event):
        """关闭时保存画布 + 管线状态 + 发射 closed 信号"""
        try:
            self._node_canvas.save_canvas()
            self._node_canvas.save_pipeline_state()
        except Exception as e:
            print(f"[涛割] 智能PS关闭保存失败: {e}")
        self.closed.emit(self._scene_index)
        super().closeEvent(event)

    # ----------------------------------------------------------
    #  样式
    # ----------------------------------------------------------

    @staticmethod
    def _btn_style(is_dark: bool) -> str:
        return (
            f"QPushButton {{ "
            f"  background: {'#2a2a3e' if is_dark else '#e4e4ec'}; "
            f"  color: {'#c0c0d0' if is_dark else '#3a3a4a'}; "
            f"  border: 1px solid {'#3a3a50' if is_dark else '#c0c0cc'}; "
            f"  border-radius: 6px; "
            f"  font-size: 12px; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background: {'#3a3a50' if is_dark else '#d0d0dc'}; "
            f"}}"
        )

    @staticmethod
    def _accent_btn_style() -> str:
        return (
            "QPushButton { "
            "  background: #5b7fff; color: white; "
            "  border: none; border-radius: 6px; "
            "  font-size: 12px; font-weight: bold; "
            "} "
            "QPushButton:hover { background: #7090ff; }"
        )
