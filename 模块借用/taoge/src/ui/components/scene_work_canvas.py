"""
涛割 - 场景工作画布
双击导演画布中的卡片后，进入此独立无限画布区域。
在此区域内以节点方式展示场景信息、编辑提示词、生成图片/视频。
"""

import os
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsRectItem, QGraphicsProxyWidget,
    QGraphicsItem, QTextEdit, QSizePolicy, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QPixmap, QPainter, QColor, QPen, QBrush,
    QLinearGradient, QPainterPath, QPolygonF
)

from ui import theme
from ui.pixmap_cache import PixmapCache
from ui.components.base_canvas_view import BaseCanvasView


# ============================================================
#  画布上的节点基类
# ============================================================

class CanvasNodeItem(QGraphicsRectItem):
    """画布节点基类 —— 可拖拽、有标题栏、圆角的矩形框"""

    def __init__(self, title: str, width: int, height: int, parent=None):
        super().__init__(parent)
        self._title = title
        self._node_width = width
        self._node_height = height

        self.setRect(0, 0, width, height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()

        # 节点背景
        bg = QColor(38, 38, 45) if dark else QColor(255, 255, 255)
        painter.setBrush(QBrush(bg))

        # 选中边框
        if self.isSelected():
            painter.setPen(QPen(QColor(10, 132, 255), 2))
        else:
            painter.setPen(QPen(QColor(60, 60, 68) if dark else QColor(210, 210, 215), 1))

        painter.drawRoundedRect(rect, 10, 10)

        # 标题栏背景
        title_rect = QRectF(rect.x(), rect.y(), rect.width(), 32)
        title_bg = QColor(48, 48, 58) if dark else QColor(240, 240, 245)
        painter.setBrush(QBrush(title_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        # 只有上半部分圆角
        painter.drawRoundedRect(title_rect, 10, 10)
        # 补齐下半部分的直角
        painter.drawRect(QRectF(rect.x(), rect.y() + 20, rect.width(), 12))

        # 标题文字
        painter.setPen(QColor(255, 255, 255, 200) if dark else QColor(30, 30, 30, 200))
        painter.setFont(QFont("SF Pro Display", 11, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(rect.x() + 12, rect.y(), rect.width() - 24, 32),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._title
        )

    def mousePressEvent(self, event):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


# ============================================================
#  图片预览节点
# ============================================================

class ImagePreviewNode(CanvasNodeItem):
    """图片预览节点 —— 显示生成的图片 + 生成按钮"""

    NODE_W = 320
    NODE_H = 300

    def __init__(self, parent=None):
        super().__init__("图片预览", self.NODE_W, self.NODE_H, parent)
        self._pixmap: Optional[QPixmap] = None
        self._progress: int = 0
        self._is_generating: bool = False
        self._status: str = "pending"

    def set_image(self, path: str):
        if path and os.path.exists(path):
            cache = PixmapCache.instance()
            self._pixmap = cache.get_scaled(path, self.NODE_W - 20, self.NODE_H - 80)
        else:
            self._pixmap = None
        self.update()

    def set_progress(self, progress: int, is_generating: bool):
        self._progress = progress
        self._is_generating = is_generating
        self.update()

    def set_status(self, status: str):
        self._status = status
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.rect()
        dark = theme.is_dark()

        # 图片展示区
        img_rect = QRectF(10, 40, rect.width() - 20, rect.height() - 80)

        if self._pixmap:
            px_w = self._pixmap.width()
            px_h = self._pixmap.height()
            x_off = img_rect.x() + (img_rect.width() - px_w) / 2
            y_off = img_rect.y() + (img_rect.height() - px_h) / 2
            painter.drawPixmap(int(x_off), int(y_off), self._pixmap)
        else:
            painter.setBrush(QBrush(QColor(25, 25, 30) if dark else QColor(235, 235, 240)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(img_rect, 6, 6)
            painter.setPen(QColor(255, 255, 255, 50) if dark else QColor(0, 0, 0, 50))
            painter.setFont(QFont("SF Pro Display", 11))
            painter.drawText(img_rect, Qt.AlignmentFlag.AlignCenter, "点击下方按钮生成图片")

        # 生成中进度
        if self._is_generating and self._progress > 0:
            painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(img_rect, 6, 6)

            bar_w = img_rect.width() - 40
            bar_h = 6
            bar_x = img_rect.x() + 20
            bar_y = img_rect.center().y() + 12

            painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

            prog_w = bar_w * self._progress / 100
            painter.setBrush(QBrush(QColor(10, 132, 255)))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, prog_w, bar_h), 3, 3)

            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            painter.drawText(img_rect, Qt.AlignmentFlag.AlignCenter, f"{self._progress}%")

        # 底部状态条
        status_colors = {
            "pending": QColor(70, 70, 75),
            "image_generating": QColor(255, 152, 0),
            "image_generated": QColor(0, 150, 136),
            "completed": QColor(0, 200, 83),
            "failed": QColor(244, 67, 54),
        }
        status_color = status_colors.get(self._status, QColor(70, 70, 75))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(status_color))
        painter.drawRoundedRect(
            QRectF(10, rect.height() - 32, rect.width() - 20, 4), 2, 2
        )


# ============================================================
#  视频预览节点
# ============================================================

class VideoPreviewNode(CanvasNodeItem):
    """视频预览节点 —— 显示视频缩略图/状态 + 生成按钮"""

    NODE_W = 320
    NODE_H = 300

    def __init__(self, parent=None):
        super().__init__("视频预览", self.NODE_W, self.NODE_H, parent)
        self._pixmap: Optional[QPixmap] = None
        self._progress: int = 0
        self._is_generating: bool = False
        self._status: str = "pending"
        self._has_video: bool = False
        self._video_path: str = ""

    def set_video(self, path: str):
        self._video_path = path
        self._has_video = bool(path and os.path.exists(path))
        self.update()

    def set_thumbnail(self, path: str):
        if path and os.path.exists(path):
            cache = PixmapCache.instance()
            self._pixmap = cache.get_scaled(path, self.NODE_W - 20, self.NODE_H - 80)
        else:
            self._pixmap = None
        self.update()

    def set_progress(self, progress: int, is_generating: bool):
        self._progress = progress
        self._is_generating = is_generating
        self.update()

    def set_status(self, status: str):
        self._status = status
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.rect()
        dark = theme.is_dark()

        vid_rect = QRectF(10, 40, rect.width() - 20, rect.height() - 80)

        if self._pixmap:
            px_w = self._pixmap.width()
            px_h = self._pixmap.height()
            x_off = vid_rect.x() + (vid_rect.width() - px_w) / 2
            y_off = vid_rect.y() + (vid_rect.height() - px_h) / 2
            painter.drawPixmap(int(x_off), int(y_off), self._pixmap)

            # 播放按钮叠加
            if self._has_video and not self._is_generating:
                center = vid_rect.center()
                painter.setBrush(QBrush(QColor(0, 0, 0, 120)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(center, 24, 24)
                # 三角形播放图标
                painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
                from PyQt6.QtGui import QPolygonF
                triangle = QPolygonF([
                    QPointF(center.x() - 8, center.y() - 12),
                    QPointF(center.x() - 8, center.y() + 12),
                    QPointF(center.x() + 14, center.y()),
                ])
                painter.drawPolygon(triangle)
        else:
            painter.setBrush(QBrush(QColor(25, 25, 30) if dark else QColor(235, 235, 240)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(vid_rect, 6, 6)
            painter.setPen(QColor(255, 255, 255, 50) if dark else QColor(0, 0, 0, 50))
            painter.setFont(QFont("SF Pro Display", 11))
            hint = "需先生成图片" if not self._pixmap else "点击下方按钮生成视频"
            painter.drawText(vid_rect, Qt.AlignmentFlag.AlignCenter, hint)

        # 生成中进度
        if self._is_generating and self._progress > 0:
            painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(vid_rect, 6, 6)

            bar_w = vid_rect.width() - 40
            bar_h = 6
            bar_x = vid_rect.x() + 20
            bar_y = vid_rect.center().y() + 12

            painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

            prog_w = bar_w * self._progress / 100
            painter.setBrush(QBrush(QColor(76, 175, 80)))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, prog_w, bar_h), 3, 3)

            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            painter.drawText(vid_rect, Qt.AlignmentFlag.AlignCenter, f"{self._progress}%")

        # 底部状态条
        status_colors = {
            "pending": QColor(70, 70, 75),
            "video_generating": QColor(255, 152, 0),
            "video_generated": QColor(76, 175, 80),
            "completed": QColor(0, 200, 83),
            "failed": QColor(244, 67, 54),
        }
        status_color = status_colors.get(self._status, QColor(70, 70, 75))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(status_color))
        painter.drawRoundedRect(
            QRectF(10, rect.height() - 32, rect.width() - 20, 4), 2, 2
        )


# ============================================================
#  场景信息节点
# ============================================================

class SceneInfoNode(CanvasNodeItem):
    """场景信息节点 —— 显示场景基本信息和分析标签"""

    NODE_W = 280
    NODE_H = 200

    def __init__(self, parent=None):
        super().__init__("场景信息", self.NODE_W, self.NODE_H, parent)
        self._scene_data: Dict[str, Any] = {}

    def set_scene_data(self, data: Dict[str, Any]):
        self._scene_data = data
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        rect = self.rect()
        dark = theme.is_dark()

        y = 42
        left = 14
        max_w = rect.width() - 28

        # 场景序号
        index = self._scene_data.get('scene_index', 0)
        painter.setPen(QColor(10, 132, 255))
        painter.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        painter.drawText(int(left), int(y), f"#{index + 1:02d}")
        y += 22

        # 字幕
        subtitle = self._scene_data.get('subtitle_text', '')
        if subtitle:
            painter.setPen(QColor(255, 255, 255, 200) if dark else QColor(30, 30, 30, 200))
            painter.setFont(QFont("SF Pro Display", 10))
            # 截断处理
            metrics = painter.fontMetrics()
            lines = subtitle.split('\n')
            for line in lines[:3]:
                elided = metrics.elidedText(line, Qt.TextElideMode.ElideRight, int(max_w))
                painter.drawText(int(left), int(y), elided)
                y += 16

        y += 6

        # 时长
        duration = self._scene_data.get('duration', 0)
        if duration > 0:
            painter.setPen(QColor(255, 255, 255, 100) if dark else QColor(0, 0, 0, 100))
            painter.setFont(QFont("Consolas", 9))
            painter.drawText(int(left), int(y), f"时长: {duration:.1f}s")
            y += 18

        # 状态
        status = self._scene_data.get('status', 'pending')
        status_labels = {
            "pending": "待处理",
            "image_generating": "图片生成中",
            "image_generated": "图片已生成",
            "video_generating": "视频生成中",
            "video_generated": "视频已生成",
            "completed": "已完成",
            "failed": "失败",
        }
        status_text = status_labels.get(status, status)
        painter.setPen(QColor(255, 255, 255, 120) if dark else QColor(0, 0, 0, 120))
        painter.setFont(QFont("SF Pro Display", 9))
        painter.drawText(int(left), int(y), f"状态: {status_text}")

        # 角色标签
        chars = self._scene_data.get('characters', [])
        if chars:
            y += 20
            painter.setPen(QColor(139, 92, 246, 200))
            painter.setFont(QFont("SF Pro Display", 9, QFont.Weight.DemiBold))
            names = [c.get('name', '?') if isinstance(c, dict) else str(c) for c in chars[:4]]
            painter.drawText(int(left), int(y), "  ".join(f"[{n}]" for n in names))


# ============================================================
#  可嵌入画布的 QWidget 编辑面板
# ============================================================

class PromptEditWidget(QFrame):
    """提示词编辑面板 —— 通过 QGraphicsProxyWidget 嵌入画布"""

    text_changed = pyqtSignal(str, str)  # field_name, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(340, 380)
        self._is_updating = False

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题
        title = QLabel("提示词编辑")
        title.setObjectName("promptEditTitle")
        layout.addWidget(title)

        # 画面提示词
        img_label = QLabel("画面提示词")
        img_label.setObjectName("promptFieldLabel")
        layout.addWidget(img_label)

        self._image_prompt_edit = QTextEdit()
        self._image_prompt_edit.setPlaceholderText("描述画面内容...")
        self._image_prompt_edit.setMaximumHeight(90)
        self._image_prompt_edit.setObjectName("promptTextEdit")
        self._image_prompt_edit.textChanged.connect(
            lambda: self._on_text_changed('image_prompt', self._image_prompt_edit)
        )
        layout.addWidget(self._image_prompt_edit)

        # 视频提示词
        vid_label = QLabel("视频提示词")
        vid_label.setObjectName("promptFieldLabel")
        layout.addWidget(vid_label)

        self._video_prompt_edit = QTextEdit()
        self._video_prompt_edit.setPlaceholderText("描述运动和变化...")
        self._video_prompt_edit.setMaximumHeight(90)
        self._video_prompt_edit.setObjectName("promptTextEdit")
        self._video_prompt_edit.textChanged.connect(
            lambda: self._on_text_changed('video_prompt', self._video_prompt_edit)
        )
        layout.addWidget(self._video_prompt_edit)

        layout.addStretch()

    def _apply_theme(self):
        dark = theme.is_dark()
        self.setStyleSheet(f"""
            PromptEditWidget {{
                background-color: {theme.bg_secondary()};
                border: 1px solid {theme.border()};
                border-radius: 10px;
            }}
            QLabel#promptEditTitle {{
                color: {theme.text_primary()};
                font-size: 13px;
                font-weight: bold;
                padding-bottom: 4px;
            }}
            QLabel#promptFieldLabel {{
                color: {theme.text_secondary()};
                font-size: 11px;
                font-weight: 600;
            }}
            QTextEdit#promptTextEdit {{
                background-color: {"rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.02)"};
                border: 1px solid {theme.border()};
                border-radius: 6px;
                padding: 6px;
                color: {theme.text_primary()};
                font-size: 12px;
            }}
            QTextEdit#promptTextEdit:focus {{
                border-color: {theme.accent()};
            }}
        """)

    def set_data(self, scene_data: Dict[str, Any]):
        self._is_updating = True
        self._image_prompt_edit.setPlainText(scene_data.get('image_prompt', ''))
        self._video_prompt_edit.setPlainText(scene_data.get('video_prompt', ''))
        self._is_updating = False

    def _on_text_changed(self, field: str, edit: QTextEdit):
        if not self._is_updating:
            self.text_changed.emit(field, edit.toPlainText())


# ============================================================
#  操作按钮面板
# ============================================================

class ActionButtonsWidget(QFrame):
    """操作按钮面板 —— 生成图片/视频/AI分析"""

    generate_image_clicked = pyqtSignal()
    generate_video_clicked = pyqtSignal()
    ai_analyze_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("操作")
        title.setObjectName("actionTitle")
        layout.addWidget(title)

        self._gen_img_btn = QPushButton("生成图片")
        self._gen_img_btn.setFixedHeight(36)
        self._gen_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_img_btn.clicked.connect(self.generate_image_clicked.emit)
        self._gen_img_btn.setObjectName("genImgBtn")
        layout.addWidget(self._gen_img_btn)

        self._gen_vid_btn = QPushButton("生成视频")
        self._gen_vid_btn.setFixedHeight(36)
        self._gen_vid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_vid_btn.clicked.connect(self.generate_video_clicked.emit)
        self._gen_vid_btn.setObjectName("genVidBtn")
        layout.addWidget(self._gen_vid_btn)

        self._ai_btn = QPushButton("AI 分析")
        self._ai_btn.setFixedHeight(36)
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_btn.clicked.connect(self.ai_analyze_clicked.emit)
        self._ai_btn.setObjectName("aiAnalyzeBtn")
        layout.addWidget(self._ai_btn)

        layout.addStretch()

    def _apply_theme(self):
        self.setStyleSheet(f"""
            ActionButtonsWidget {{
                background-color: {theme.bg_secondary()};
                border: 1px solid {theme.border()};
                border-radius: 10px;
            }}
            QLabel#actionTitle {{
                color: {theme.text_primary()};
                font-size: 13px;
                font-weight: bold;
                padding-bottom: 4px;
            }}
            QPushButton#genImgBtn {{
                background-color: {theme.accent()};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#genImgBtn:hover {{
                background-color: {theme.accent_hover()};
            }}
            QPushButton#genVidBtn {{
                background-color: rgba(76, 175, 80, 0.85);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#genVidBtn:hover {{
                background-color: rgba(76, 175, 80, 1.0);
            }}
            QPushButton#aiAnalyzeBtn {{
                background-color: rgba(139, 92, 246, 0.8);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#aiAnalyzeBtn:hover {{
                background-color: rgba(139, 92, 246, 1.0);
            }}
        """)


# ============================================================
#  场景工作画布视图（核心无限画布）
# ============================================================

class SceneWorkCanvasView(BaseCanvasView):
    """单场景的无限画布视图，承载各种节点"""

    generate_image_requested = pyqtSignal(int)
    generate_video_requested = pyqtSignal(int)
    ai_analyze_requested = pyqtSignal(int)
    property_changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_index: int = -1
        self._scene_data: Dict[str, Any] = {}

        # 节点引用
        self._info_node: Optional[SceneInfoNode] = None
        self._image_node: Optional[ImagePreviewNode] = None
        self._video_node: Optional[VideoPreviewNode] = None
        self._prompt_proxy: Optional[QGraphicsProxyWidget] = None
        self._prompt_widget: Optional[PromptEditWidget] = None
        self._action_proxy: Optional[QGraphicsProxyWidget] = None
        self._action_widget: Optional[ActionButtonsWidget] = None

        # 连接线
        self._connection_lines = []

    def load_scene(self, scene_index: int, scene_data: Dict[str, Any]):
        """加载场景数据，创建节点布局"""
        self._scene_index = scene_index
        self._scene_data = scene_data

        # 清空现有
        self._clear_all()

        # 创建场景信息节点（左上）
        self._info_node = SceneInfoNode()
        scene_data_with_index = dict(scene_data)
        scene_data_with_index['scene_index'] = scene_index
        self._info_node.set_scene_data(scene_data_with_index)
        self._info_node.setPos(50, 60)
        self._canvas_scene.addItem(self._info_node)

        # 创建图片预览节点（中间）
        self._image_node = ImagePreviewNode()
        self._image_node.setPos(430, 30)
        img_path = scene_data.get('generated_image_path', '') or scene_data.get('start_frame_path', '')
        self._image_node.set_image(img_path)
        self._image_node.set_status(scene_data.get('status', 'pending'))
        self._canvas_scene.addItem(self._image_node)

        # 创建视频预览节点（右侧）
        self._video_node = VideoPreviewNode()
        self._video_node.setPos(850, 30)
        vid_path = scene_data.get('generated_video_path', '')
        self._video_node.set_video(vid_path)
        # 视频缩略图使用已生成的图片
        if img_path:
            self._video_node.set_thumbnail(img_path)
        video_status = scene_data.get('status', 'pending')
        self._video_node.set_status(video_status)
        self._canvas_scene.addItem(self._video_node)

        # 创建提示词编辑面板（下方左）
        self._prompt_widget = PromptEditWidget()
        self._prompt_widget.set_data(scene_data)
        self._prompt_widget.text_changed.connect(self._on_prompt_changed)
        self._prompt_proxy = self._canvas_scene.addWidget(self._prompt_widget)
        self._prompt_proxy.setPos(50, 340)
        self._prompt_proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        # 创建操作按钮面板（下方右）
        self._action_widget = ActionButtonsWidget()
        self._action_widget.generate_image_clicked.connect(
            lambda: self.generate_image_requested.emit(self._scene_index)
        )
        self._action_widget.generate_video_clicked.connect(
            lambda: self.generate_video_requested.emit(self._scene_index)
        )
        self._action_widget.ai_analyze_clicked.connect(
            lambda: self.ai_analyze_requested.emit(self._scene_index)
        )
        self._action_proxy = self._canvas_scene.addWidget(self._action_widget)
        self._action_proxy.setPos(480, 420)
        self._action_proxy.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        # 绘制连线
        self._draw_connections()

        self._expand_scene_rect()
        self.fit_all_in_view()

    def _clear_all(self):
        """清空画布"""
        for line in self._connection_lines:
            if line.scene():
                self._canvas_scene.removeItem(line)
        self._connection_lines.clear()
        self._canvas_scene.clear()
        self._info_node = None
        self._image_node = None
        self._video_node = None
        self._prompt_proxy = None
        self._prompt_widget = None
        self._action_proxy = None
        self._action_widget = None

    def _draw_connections(self):
        """在节点之间绘制贝塞尔曲线连线"""
        import math

        def _draw_curve(from_item, to_item, color: QColor):
            """绘制水平贝塞尔曲线：从 from_item 右侧中心 → to_item 左侧中心"""
            from_rect = from_item.sceneBoundingRect()
            to_rect = to_item.sceneBoundingRect()

            from_right = from_rect.right()
            from_cy = from_rect.center().y()
            to_left = to_rect.left()
            to_cy = to_rect.center().y()

            gap = to_left - from_right

            path = QPainterPath()
            path.moveTo(from_right, from_cy)
            cp1_x = from_right + gap * 0.4
            cp1_y = from_cy
            cp2_x = to_left - gap * 0.4
            cp2_y = to_cy
            path.cubicTo(cp1_x, cp1_y, cp2_x, cp2_y, to_left, to_cy)

            pen = QPen(color, 2, Qt.PenStyle.DashLine)
            path_item = self._canvas_scene.addPath(path, pen)
            path_item.setZValue(-1)
            self._connection_lines.append(path_item)

            # 在曲线中间位置添加小三角形箭头
            mid_point = path.pointAtPercent(0.5)
            # 获取前后点计算方向
            p_before = path.pointAtPercent(0.48)
            p_after = path.pointAtPercent(0.52)
            angle = math.atan2(p_after.y() - p_before.y(), p_after.x() - p_before.x())

            arrow_size = 6
            p1 = QPointF(
                mid_point.x() + arrow_size * math.cos(angle),
                mid_point.y() + arrow_size * math.sin(angle)
            )
            p2 = QPointF(
                mid_point.x() + arrow_size * math.cos(angle + 2.4),
                mid_point.y() + arrow_size * math.sin(angle + 2.4)
            )
            p3 = QPointF(
                mid_point.x() + arrow_size * math.cos(angle - 2.4),
                mid_point.y() + arrow_size * math.sin(angle - 2.4)
            )
            arrow_polygon = QPolygonF([p1, p2, p3])
            arrow_item = self._canvas_scene.addPolygon(
                arrow_polygon, QPen(Qt.PenStyle.NoPen), QBrush(color)
            )
            arrow_item.setZValue(-1)
            self._connection_lines.append(arrow_item)

        # 信息节点 → 图片节点（蓝色）
        if self._info_node and self._image_node:
            _draw_curve(self._info_node, self._image_node, QColor(10, 132, 255, 60))

        # 图片节点 → 视频节点（绿色）
        if self._image_node and self._video_node:
            _draw_curve(self._image_node, self._video_node, QColor(76, 175, 80, 60))

        # 提示词面板 → 信息节点（竖向虚线：从 prompt 顶部到 info 底部）
        if self._prompt_proxy and self._info_node:
            prompt_rect = self._prompt_proxy.sceneBoundingRect()
            info_rect = self._info_node.sceneBoundingRect()

            from_x = prompt_rect.center().x()
            from_y = prompt_rect.top()
            to_x = info_rect.center().x()
            to_y = info_rect.bottom()

            gap_v = from_y - to_y

            path = QPainterPath()
            path.moveTo(to_x, to_y)
            cp1_x = to_x
            cp1_y = to_y + gap_v * 0.4
            cp2_x = from_x
            cp2_y = from_y - gap_v * 0.4
            path.cubicTo(cp1_x, cp1_y, cp2_x, cp2_y, from_x, from_y)

            pen = QPen(QColor(10, 132, 255, 60), 2, Qt.PenStyle.DashLine)
            path_item = self._canvas_scene.addPath(path, pen)
            path_item.setZValue(-1)
            self._connection_lines.append(path_item)

    def update_scene_data(self, scene_data: Dict[str, Any]):
        """更新场景数据"""
        self._scene_data = scene_data

        if self._info_node:
            data_with_index = dict(scene_data)
            data_with_index['scene_index'] = self._scene_index
            self._info_node.set_scene_data(data_with_index)

        img_path = scene_data.get('generated_image_path', '') or scene_data.get('start_frame_path', '')
        if self._image_node:
            self._image_node.set_image(img_path)
            self._image_node.set_status(scene_data.get('status', 'pending'))

        if self._video_node:
            vid_path = scene_data.get('generated_video_path', '')
            self._video_node.set_video(vid_path)
            if img_path:
                self._video_node.set_thumbnail(img_path)
            self._video_node.set_status(scene_data.get('status', 'pending'))

    def update_image_progress(self, progress: int, is_generating: bool):
        if self._image_node:
            self._image_node.set_progress(progress, is_generating)

    def update_video_progress(self, progress: int, is_generating: bool):
        if self._video_node:
            self._video_node.set_progress(progress, is_generating)

    def _on_prompt_changed(self, field: str, value: str):
        self.property_changed.emit(field, value)

    def mousePressEvent(self, event):
        """左键点击空白不做特殊处理，右键平移由基类 BaseCanvasView 负责"""
        super().mousePressEvent(event)


# ============================================================
#  场景工作画布页面（包含顶部栏 + 无限画布）
# ============================================================

class SceneWorkCanvas(QWidget):
    """
    场景工作画布完整页面
    顶部: 返回按钮 + 场景标题 + 缩放信息
    主体: SceneWorkCanvasView 无限画布
    """

    back_requested = pyqtSignal()
    generate_image_requested = pyqtSignal(int)
    generate_video_requested = pyqtSignal(int)
    ai_analyze_requested = pyqtSignal(int)
    property_changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_index: int = -1

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部导航栏
        self._header = QFrame()
        self._header.setObjectName("sceneWorkHeader")
        self._header.setFixedHeight(44)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(10)

        self._back_btn = QPushButton("\u2190 返回导演画布")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._back_btn.setObjectName("sceneWorkBackBtn")
        header_layout.addWidget(self._back_btn)

        header_layout.addWidget(self._create_sep())

        self._title_label = QLabel("场景工作区")
        self._title_label.setObjectName("sceneWorkTitle")
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        self._fit_btn = QPushButton("适应视图")
        self._fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_btn.clicked.connect(self._fit_view)
        self._fit_btn.setObjectName("sceneWorkToolBtn")
        header_layout.addWidget(self._fit_btn)

        header_layout.addWidget(self._create_sep())

        self._zoom_label = QLabel("100%")
        self._zoom_label.setObjectName("sceneWorkZoom")
        header_layout.addWidget(self._zoom_label)

        layout.addWidget(self._header)

        # 无限画布
        self._canvas_view = SceneWorkCanvasView()
        self._canvas_view.zoom_changed.connect(
            lambda p: self._zoom_label.setText(f"{p}%")
        )
        self._canvas_view.generate_image_requested.connect(
            self.generate_image_requested.emit
        )
        self._canvas_view.generate_video_requested.connect(
            self.generate_video_requested.emit
        )
        self._canvas_view.ai_analyze_requested.connect(
            self.ai_analyze_requested.emit
        )
        self._canvas_view.property_changed.connect(
            self.property_changed.emit
        )
        layout.addWidget(self._canvas_view, 1)

    def _create_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet(f"background-color: {theme.separator()};")
        return sep

    def _apply_theme(self):
        dark = theme.is_dark()
        self._header.setStyleSheet(f"""
            QFrame#sceneWorkHeader {{
                background-color: {theme.bg_elevated()};
                border-bottom: 1px solid {theme.border()};
            }}
        """)
        self._back_btn.setStyleSheet(f"""
            QPushButton#sceneWorkBackBtn {{
                background-color: transparent;
                color: {theme.accent()};
                border: none;
                font-size: 13px;
                font-weight: 500;
                padding: 4px 10px;
            }}
            QPushButton#sceneWorkBackBtn:hover {{
                color: {theme.accent_hover()};
            }}
        """)
        self._title_label.setStyleSheet(f"""
            QLabel#sceneWorkTitle {{
                color: {theme.text_primary()};
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        self._fit_btn.setStyleSheet(theme.tool_btn_style())
        self._zoom_label.setStyleSheet(f"""
            QLabel#sceneWorkZoom {{
                color: {theme.text_tertiary()};
                font-size: 11px;
                font-family: 'SF Mono', Consolas, monospace;
            }}
        """)

    def _fit_view(self):
        self._canvas_view.fit_all_in_view()

    # ==================== 公开 API ====================

    def load_scene(self, scene_index: int, scene_data: Dict[str, Any]):
        """加载场景到工作画布"""
        self._scene_index = scene_index
        self._title_label.setText(f"场景 #{scene_index + 1} 工作区")
        self._canvas_view.load_scene(scene_index, scene_data)

    def update_scene_data(self, scene_data: Dict[str, Any]):
        """更新当前场景数据"""
        self._canvas_view.update_scene_data(scene_data)

    def update_generation_progress(self, task_type: str, progress: int, is_generating: bool):
        """更新生成进度"""
        if task_type in ('image', 'image_generating'):
            self._canvas_view.update_image_progress(progress, is_generating)
        elif task_type in ('video', 'video_generating'):
            self._canvas_view.update_video_progress(progress, is_generating)

    @property
    def current_scene_index(self) -> int:
        return self._scene_index

    def apply_theme(self, dark: bool):
        self._apply_theme()
        self._canvas_view.viewport().update()
