"""
涛割 - Canvas画布模式
拖拽式场景编排，支持场景卡片的自由排列、重新排序和视觉化预览
增强功能：角色头像、生成进度、多选、框选打组、右键菜单、属性面板
"""

import os
from typing import Optional, List, Dict, Any, Set

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsProxyWidget, QSizePolicy, QMenu, QToolBar,
    QGraphicsItem, QSplitter, QApplication, QGraphicsOpacityEffect,
    QGraphicsPixmapItem, QGraphicsTextItem, QSlider, QGraphicsPathItem,
    QToolTip
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QRectF, QPointF, QSizeF, QMimeData, QTimer,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QPixmap, QPainter, QColor, QPen, QBrush,
    QDrag, QLinearGradient, QPainterPath
)

from ui.pixmap_cache import PixmapCache
from ui import theme
from ui.components.base_canvas_view import BaseCanvasView
from ui.components.canvas_connections import CurvedConnectionLine


class SceneCanvasCard(QGraphicsRectItem):
    """
    画布上的场景卡片
    支持拖拽移动、状态颜色、缩略图显示、角色头像、生成进度
    """

    CARD_WIDTH = 200
    CARD_HEIGHT = 200
    THUMB_HEIGHT = 90
    CORNER_RADIUS = 8
    MAX_AVATARS = 3
    AVATAR_SIZE = 20

    # 状态颜色映射
    STATUS_COLORS = {
        "pending": QColor(70, 70, 75),
        "image_generating": QColor(255, 152, 0),
        "video_generating": QColor(255, 152, 0),
        "image_generated": QColor(0, 150, 136),
        "video_generated": QColor(76, 175, 80),
        "completed": QColor(0, 200, 83),
        "failed": QColor(244, 67, 54),
    }

    def __init__(self, index: int, scene_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.scene_index = index
        self.scene_data = scene_data
        self._is_selected = False
        self._is_multi_selected = False
        self._thumbnail: Optional[QPixmap] = None

        # 新增属性
        self._characters: List[Dict[str, Any]] = scene_data.get('characters', [])
        self._generation_progress: int = 0
        self._is_generating: bool = False
        self._group_id: Optional[int] = None

        self.setRect(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self._load_thumbnail()

    def _load_thumbnail(self):
        """加载场景缩略图"""
        cache = PixmapCache.instance()
        for key in ('generated_image_path', 'start_frame_path'):
            path = self.scene_data.get(key, '')
            if path and os.path.exists(path):
                self._thumbnail = cache.get_scaled(
                    path, self.CARD_WIDTH - 8, self.THUMB_HEIGHT - 4
                )
                if self._thumbnail:
                    break

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        status = self.scene_data.get('status', 'pending')
        status_color = self.STATUS_COLORS.get(status, QColor(70, 70, 75))

        dark = theme.is_dark()

        # 卡片背景
        is_any_selected = self._is_selected or self._is_multi_selected
        if dark:
            bg_color = QColor(45, 45, 55) if is_any_selected else QColor(38, 38, 42)
        else:
            bg_color = QColor(230, 230, 235) if is_any_selected else QColor(255, 255, 255)
        painter.setBrush(QBrush(bg_color))

        # 边框
        if self._is_selected:
            painter.setPen(QPen(QColor(0, 122, 204), 2))
        elif self._is_multi_selected:
            painter.setPen(QPen(QColor(0, 122, 204, 150), 1.5, Qt.PenStyle.DashLine))
        else:
            if dark:
                painter.setPen(QPen(QColor(60, 60, 65), 1))
            else:
                painter.setPen(QPen(QColor(210, 210, 215), 1))

        painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # 缩略图区域
        thumb_rect = QRectF(4, 4, rect.width() - 8, self.THUMB_HEIGHT)
        if self._thumbnail:
            px_w = self._thumbnail.width()
            px_h = self._thumbnail.height()
            x_offset = thumb_rect.x() + (thumb_rect.width() - px_w) / 2
            y_offset = thumb_rect.y() + (thumb_rect.height() - px_h) / 2
            painter.drawPixmap(int(x_offset), int(y_offset), self._thumbnail)
        else:
            if dark:
                painter.setBrush(QBrush(QColor(30, 30, 35)))
            else:
                painter.setBrush(QBrush(QColor(235, 235, 240)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(thumb_rect, 4, 4)

            painter.setPen(QColor(128, 128, 128, 100) if not dark else QColor(255, 255, 255, 60))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "无预览")

        # 生成进度覆盖层
        if self._is_generating and self._generation_progress > 0:
            # 半透明覆盖
            painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(thumb_rect, 4, 4)

            # 进度条
            bar_width = thumb_rect.width() - 20
            bar_height = 6
            bar_x = thumb_rect.x() + 10
            bar_y = thumb_rect.center().y() + 10

            # 背景
            painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_width, bar_height), 3, 3)

            # 进度
            progress_width = bar_width * self._generation_progress / 100
            painter.setBrush(QBrush(QColor(0, 122, 204)))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, progress_width, bar_height), 3, 3)

            # 进度文字
            painter.setPen(QColor(255, 255, 255, 220))
            painter.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, f"{self._generation_progress}%")

        # 底部信息区
        info_y = self.THUMB_HEIGHT + 6
        info_rect = QRectF(8, info_y, rect.width() - 16, rect.height() - info_y - 8)

        # 场景序号标签 + 时长（同一行）
        index_text = f"#{self.scene_index + 1:02d}"
        painter.setPen(QColor(0, 180, 255))
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(int(info_rect.x()), int(info_rect.y() + 14), index_text)

        duration = self.scene_data.get('duration', 0)
        if duration > 0:
            dur_text = f"{duration:.1f}s"
            painter.setPen(QColor(28, 28, 30, 100) if not dark else QColor(255, 255, 255, 100))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(
                int(info_rect.x() + info_rect.width() - 30),
                int(info_rect.y() + 14),
                dur_text
            )

        # 字幕文本（多行排列）
        subtitle = self.scene_data.get('subtitle_text', '')
        if subtitle:
            text_y = info_rect.y() + 24
            painter.setPen(QColor(28, 28, 30, 180) if not dark else QColor(255, 255, 255, 180))
            painter.setFont(QFont("Arial", 9))
            metrics = painter.fontMetrics()
            max_text_w = int(info_rect.width())
            max_lines = 3
            line_count = 0

            remaining = subtitle.replace('\n', ' ')
            while remaining and line_count < max_lines:
                # 用 fontMetrics 计算本行能放多少字符
                elided = metrics.elidedText(
                    remaining,
                    Qt.TextElideMode.ElideRight,
                    max_text_w
                )
                # 如果还有剩余文本且不是最后一行，按实际宽度截断（不加省略号）
                if line_count < max_lines - 1 and len(elided) < len(remaining):
                    # 找到不超过宽度的最长前缀
                    fit_len = len(elided) - 1 if elided.endswith('…') else len(elided)
                    for i in range(len(remaining), 0, -1):
                        if metrics.horizontalAdvance(remaining[:i]) <= max_text_w:
                            fit_len = i
                            break
                    draw_text = remaining[:fit_len]
                    remaining = remaining[fit_len:].lstrip()
                else:
                    draw_text = elided
                    remaining = ''

                painter.drawText(int(info_rect.x()), int(text_y), draw_text)
                text_y += metrics.height() + 1
                line_count += 1

        # 状态指示条
        bar_y = int(rect.height() - 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(status_color))
        painter.drawRoundedRect(
            QRectF(4, bar_y, rect.width() - 8, 3),
            1.5, 1.5
        )

        # 角色头像行（状态条上方，最多3个圆形）
        if self._characters:
            avatar_y = rect.height() - 12 - self.AVATAR_SIZE
            avatar_x_start = info_rect.x()

            for i, char in enumerate(self._characters[:self.MAX_AVATARS]):
                ax = avatar_x_start + i * (self.AVATAR_SIZE + 4)

                # 圆形背景
                painter.setPen(QPen(QColor(139, 92, 246, 180), 1))
                painter.setBrush(QBrush(QColor(139, 92, 246, 60)))
                painter.drawEllipse(QRectF(ax, avatar_y, self.AVATAR_SIZE, self.AVATAR_SIZE))

                # 首字母
                name = char.get('name', '?')
                painter.setPen(QColor(255, 255, 255, 200) if dark else QColor(80, 40, 180, 220))
                painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(ax, avatar_y, self.AVATAR_SIZE, self.AVATAR_SIZE),
                    Qt.AlignmentFlag.AlignCenter,
                    name[0] if name else "?"
                )

            # 超出数量提示
            if len(self._characters) > self.MAX_AVATARS:
                extra = len(self._characters) - self.MAX_AVATARS
                ex_x = avatar_x_start + self.MAX_AVATARS * (self.AVATAR_SIZE + 4)
                painter.setPen(QColor(28, 28, 30, 100) if not dark else QColor(255, 255, 255, 100))
                painter.setFont(QFont("Arial", 8))
                painter.drawText(int(ex_x), int(avatar_y + 14), f"+{extra}")

    def hoverEnterEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def set_multi_selected(self, selected: bool):
        self._is_multi_selected = selected
        self.update()

    # ==================== 新增方法 ====================

    def set_characters(self, characters: List[Dict[str, Any]]):
        """设置角色数据"""
        self._characters = characters
        self.update()

    def set_generation_progress(self, progress: int, is_generating: bool = True):
        """设置生成进度"""
        self._generation_progress = progress
        self._is_generating = is_generating
        self.update()

    def refresh_thumbnail(self):
        """刷新缩略图"""
        cache = PixmapCache.instance()
        for key in ('generated_image_path', 'start_frame_path'):
            path = self.scene_data.get(key, '')
            if path and os.path.exists(path):
                cache.invalidate(path)
                self._thumbnail = cache.get_scaled(
                    path, self.CARD_WIDTH - 8, self.THUMB_HEIGHT - 4
                )
                if self._thumbnail:
                    break
        self.update()

    def update_scene_data(self, new_data: Dict[str, Any]):
        """更新场景数据"""
        self.scene_data.update(new_data)
        self._characters = new_data.get('characters', self._characters)
        self._load_thumbnail()
        self.update()


class CardFloatingToolbar(QWidget):
    """
    卡片浮动工具栏 —— 单击卡片时在上方弹出一排操作按钮
    通过 QGraphicsProxyWidget 嵌入到 QGraphicsScene 中
    """

    generate_image_requested = pyqtSignal(int)
    generate_video_requested = pyqtSignal(int)
    ai_analyze_requested = pyqtSignal(int)
    scene_duplicated = pyqtSignal(int)
    scene_deleted = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_index: int = -1

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        btn_defs = [
            ("🖼 生成图片", self._on_gen_image),
            ("🎬 生成视频", self._on_gen_video),
            ("✨ AI分析", self._on_ai_analyze),
            ("📋 复制", self._on_duplicate),
            ("🗑 删除", self._on_delete),
        ]
        for text, slot in btn_defs:
            btn = QPushButton(text)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        self.adjustSize()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            CardFloatingToolbar {{
                background-color: {theme.bg_elevated()};
                border: 1px solid {theme.border()};
                border-radius: 8px;
            }}
            QPushButton {{
                background-color: {theme.btn_bg()};
                color: {theme.text_secondary()};
                border: 1px solid {theme.btn_border()};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {theme.btn_bg_hover()};
                color: {theme.text_primary()};
            }}
        """)

    def set_scene_index(self, index: int):
        self._scene_index = index

    def _on_gen_image(self):
        if self._scene_index >= 0:
            self.generate_image_requested.emit(self._scene_index)

    def _on_gen_video(self):
        if self._scene_index >= 0:
            self.generate_video_requested.emit(self._scene_index)

    def _on_ai_analyze(self):
        if self._scene_index >= 0:
            self.ai_analyze_requested.emit(self._scene_index)

    def _on_duplicate(self):
        if self._scene_index >= 0:
            self.scene_duplicated.emit(self._scene_index)

    def _on_delete(self):
        if self._scene_index >= 0:
            self.scene_deleted.emit(self._scene_index)


# ============================================================
#  分组数据
# ============================================================

class CardGroup:
    """一组卡片的数据模型"""

    _next_id = 0

    def __init__(self, card_indices: List[int], color: QColor = None):
        CardGroup._next_id += 1
        self.group_id = CardGroup._next_id
        self.card_indices: List[int] = list(card_indices)
        self.color = color or QColor(0, 122, 204, 30)
        self.rect_item: Optional['GroupBackgroundItem'] = None
        self.label_item = None


class GroupBackgroundItem(QGraphicsPathItem):
    """
    可拖拽的分组背景 —— 圆角矩形。
    拖动此背景时，会带动组内所有卡片一起移动。
    """

    CORNER_RADIUS = 16
    PADDING = 20

    def __init__(self, group: CardGroup, cards_ref: List[SceneCanvasCard],
                 canvas_view: 'CanvasView', parent=None):
        super().__init__(parent)
        self._group = group
        self._cards_ref = cards_ref  # CanvasView.cards 的引用
        self._canvas_view = canvas_view
        self._drag_start: Optional[QPointF] = None
        self._card_start_positions: Dict[int, QPointF] = {}

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setZValue(-1)

    def update_shape(self, rect: QRectF, color: QColor):
        """根据包围盒更新圆角路径和颜色"""
        expanded = rect.adjusted(-self.PADDING, -self.PADDING,
                                 self.PADDING, self.PADDING)
        path = QPainterPath()
        path.addRoundedRect(expanded, self.CORNER_RADIUS, self.CORNER_RADIUS)
        self.setPath(path)

        border_alpha = min(255, color.alpha() + 80)
        self.setPen(QPen(QColor(color.red(), color.green(), color.blue(),
                                border_alpha), 2.0, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(),
                                    color.alpha())))

    # ---- 拖拽组 ----

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._drag_start = event.scenePos()
            self._card_start_positions = {}
            for idx in self._group.card_indices:
                if 0 <= idx < len(self._cards_ref):
                    self._card_start_positions[idx] = QPointF(
                        self._cards_ref[idx].scenePos()
                    )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            delta = event.scenePos() - self._drag_start
            for idx, start_pos in self._card_start_positions.items():
                if 0 <= idx < len(self._cards_ref):
                    self._cards_ref[idx].setPos(start_pos + delta)
            # 实时更新背景位置
            self._canvas_view._draw_group_rect(self._group)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._drag_start = None
            self._card_start_positions.clear()
            # 拖拽结束后更新连线和场景大小
            self._canvas_view._update_connections()
            self._canvas_view._expand_scene_rect()
            self._canvas_view._update_all_group_rects()
            # 刷新组工具栏位置
            if self._canvas_view._active_group == self._group:
                self._canvas_view._show_group_toolbar(self._group)
            event.accept()
            return
        super().mouseReleaseEvent(event)


# 8 种预设分组颜色（半透明填充用）
GROUP_PRESET_COLORS = [
    ("白", QColor(255, 255, 255, 50)),
    ("红", QColor(244, 67, 54, 50)),
    ("橙", QColor(255, 152, 0, 50)),
    ("土黄", QColor(180, 150, 60, 50)),
    ("绿", QColor(76, 175, 80, 50)),
    ("青", QColor(0, 188, 212, 50)),
    ("粉", QColor(233, 30, 99, 50)),
    ("紫", QColor(139, 92, 246, 50)),
]


# ============================================================
#  分组浮动工具栏
# ============================================================

class GroupFloatingToolbar(QWidget):
    """
    分组浮动工具栏 —— 框选卡片并打组后，点击组背景时在上方显示
    按钮：颜色 | 布局（宫格/水平） | 整组执行 | 工作流模板(预留) | 解组
    """

    color_change_requested = pyqtSignal(int, QColor)    # group_id, color
    layout_grid_requested = pyqtSignal(int)              # group_id
    layout_horizontal_requested = pyqtSignal(int)        # group_id
    execute_group_requested = pyqtSignal(int, list)      # group_id, [scene_indices]
    workflow_template_requested = pyqtSignal(int, list)   # group_id, [scene_indices]
    ungroup_requested = pyqtSignal(int)                  # group_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group_id: int = -1

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # 颜色圆块按钮
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(26, 26)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.clicked.connect(self._on_color_pick)
        self._color_btn.setToolTip("更改组背景颜色")
        layout.addWidget(self._color_btn)

        # 布局按钮
        self._layout_btn = QPushButton("布局")
        self._layout_btn.setFixedHeight(26)
        self._layout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._layout_btn.clicked.connect(self._on_layout_menu)
        layout.addWidget(self._layout_btn)

        # 整组执行
        exec_btn = QPushButton("整组执行")
        exec_btn.setFixedHeight(26)
        exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exec_btn.clicked.connect(self._on_execute)
        layout.addWidget(exec_btn)

        # 工作流模板（预留）
        wf_btn = QPushButton("工作流模板")
        wf_btn.setFixedHeight(26)
        wf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wf_btn.clicked.connect(self._on_workflow_template)
        wf_btn.setEnabled(False)
        wf_btn.setToolTip("功能预留")
        layout.addWidget(wf_btn)

        # 解组
        ungroup_btn = QPushButton("解组")
        ungroup_btn.setFixedHeight(26)
        ungroup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ungroup_btn.clicked.connect(self._on_ungroup)
        layout.addWidget(ungroup_btn)

        self.adjustSize()
        self._current_color = QColor(0, 122, 204, 50)
        self._card_indices: List[int] = []
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            GroupFloatingToolbar {{
                background-color: {theme.bg_elevated()};
                border: 1px solid {theme.border()};
                border-radius: 8px;
            }}
            QPushButton {{
                background-color: {theme.btn_bg()};
                color: {theme.text_secondary()};
                border: 1px solid {theme.btn_border()};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {theme.btn_bg_hover()};
                color: {theme.text_primary()};
            }}
            QPushButton:disabled {{
                color: {theme.text_tertiary()};
                background-color: transparent;
            }}
        """)
        self._update_color_btn_style()

    def _update_color_btn_style(self):
        c = self._current_color
        self._color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({c.red()},{c.green()},{c.blue()},200);
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 13px;
            }}
            QPushButton:hover {{
                border-color: rgba(255,255,255,0.6);
            }}
        """)

    def set_group(self, group_id: int, card_indices: List[int], color: QColor):
        self._group_id = group_id
        self._card_indices = card_indices
        self._current_color = color
        self._update_color_btn_style()

    def _on_color_pick(self):
        """弹出 8 色选择面板（轻量弹窗，不使用模态 QColorDialog）"""
        popup = QFrame(self, Qt.WindowType.Popup)
        popup.setFixedSize(180, 36)
        popup.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.bg_elevated()};
                border: 1px solid {theme.border()};
                border-radius: 8px;
            }}
        """)

        h_layout = QHBoxLayout(popup)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(4)

        for name, color in GROUP_PRESET_COLORS:
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(name)
            # 用更高不透明度显示色块本身（便于辨认）
            r, g, b = color.red(), color.green(), color.blue()
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba({r},{g},{b},200);
                    border: 2px solid rgba(255,255,255,0.2);
                    border-radius: 9px;
                }}
                QPushButton:hover {{
                    border-color: rgba(255,255,255,0.7);
                }}
            """)
            # 闭包捕获 color
            btn.clicked.connect(lambda checked, c=color: self._apply_preset_color(c, popup))
            h_layout.addWidget(btn)

        # 显示在颜色按钮下方
        global_pos = self._color_btn.mapToGlobal(
            QPointF(0, self._color_btn.height() + 4).toPoint()
        )
        popup.move(global_pos)
        popup.show()

    def _apply_preset_color(self, color: QColor, popup: QFrame):
        """应用预设颜色并关闭弹窗"""
        popup.close()
        self._current_color = color
        self._update_color_btn_style()
        self.color_change_requested.emit(self._group_id, color)

    def _on_layout_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.bg_elevated()};
                border: 1px solid {theme.border()};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                color: {theme.text_primary()};
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.accent()};
                color: white;
            }}
        """)
        grid_action = menu.addAction("宫格布局")
        horiz_action = menu.addAction("水平布局")

        action = menu.exec(self._layout_btn.mapToGlobal(
            QPointF(0, self._layout_btn.height()).toPoint()
        ))
        if action == grid_action:
            self.layout_grid_requested.emit(self._group_id)
        elif action == horiz_action:
            self.layout_horizontal_requested.emit(self._group_id)

    def _on_execute(self):
        if self._group_id >= 0:
            self.execute_group_requested.emit(self._group_id, self._card_indices)

    def _on_workflow_template(self):
        if self._group_id >= 0:
            self.workflow_template_requested.emit(self._group_id, self._card_indices)

    def _on_ungroup(self):
        if self._group_id >= 0:
            self.ungroup_requested.emit(self._group_id)


class CanvasMiniMap(QWidget):
    """
    画布导航小地图 —— 可通过控制栏按钮切换显示/隐藏
    实时显示所有卡片的缩略布局和当前视口范围，支持点击/拖拽快速导航。
    """

    MINIMAP_W = 200
    MINIMAP_H = 140

    def __init__(self, canvas_view: 'CanvasView', parent=None):
        super().__init__(parent)
        self._canvas_view = canvas_view
        self._dragging = False

        self.setFixedSize(self.MINIMAP_W, self.MINIMAP_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        # 定时刷新
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(100)
        self._refresh_timer.timeout.connect(self.update)
        self._refresh_timer.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        painter.setBrush(QBrush(QColor(20, 20, 25, 210)))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)

        scene = self._canvas_view._canvas_scene
        cards = self._canvas_view.cards
        if not cards:
            painter.setPen(QColor(255, 255, 255, 50))
            painter.setFont(QFont("Arial", 9))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无场景")
            painter.end()
            return

        items_rect = scene.itemsBoundingRect()
        if items_rect.isEmpty():
            painter.end()
            return

        pad = 12
        draw_w = self.width() - pad * 2
        draw_h = self.height() - pad * 2

        sx = draw_w / items_rect.width() if items_rect.width() > 0 else 1
        sy = draw_h / items_rect.height() if items_rect.height() > 0 else 1
        scale = min(sx, sy)

        scaled_w = items_rect.width() * scale
        scaled_h = items_rect.height() * scale
        off_x = pad + (draw_w - scaled_w) / 2
        off_y = pad + (draw_h - scaled_h) / 2

        def to_mini(scene_x, scene_y):
            return (
                off_x + (scene_x - items_rect.left()) * scale,
                off_y + (scene_y - items_rect.top()) * scale,
            )

        self._map_items_rect = items_rect
        self._map_scale = scale
        self._map_off_x = off_x
        self._map_off_y = off_y

        selected_card = self._canvas_view._selected_card
        for card in cards:
            pos = card.scenePos()
            mx, my = to_mini(pos.x(), pos.y())
            mw = SceneCanvasCard.CARD_WIDTH * scale
            mh = SceneCanvasCard.CARD_HEIGHT * scale

            if card is selected_card:
                painter.setBrush(QBrush(QColor(0, 122, 204, 180)))
                painter.setPen(QPen(QColor(0, 180, 255), 1))
            else:
                status = card.scene_data.get('status', 'pending')
                if status in ('completed', 'video_generated'):
                    fill = QColor(0, 200, 83, 120)
                elif status in ('image_generated',):
                    fill = QColor(0, 150, 136, 120)
                elif status in ('image_generating', 'video_generating'):
                    fill = QColor(255, 152, 0, 120)
                else:
                    fill = QColor(80, 80, 90, 140)
                painter.setBrush(QBrush(fill))
                painter.setPen(QPen(QColor(255, 255, 255, 40), 0.5))

            painter.drawRoundedRect(QRectF(mx, my, mw, mh), 2, 2)

        vp_rect = self._canvas_view.mapToScene(
            self._canvas_view.viewport().rect()
        ).boundingRect()
        vx, vy = to_mini(vp_rect.left(), vp_rect.top())
        vw = vp_rect.width() * scale
        vh = vp_rect.height() * scale

        painter.setBrush(QBrush(QColor(255, 255, 255, 15)))
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1.5))
        painter.drawRoundedRect(QRectF(vx, vy, vw, vh), 2, 2)

        painter.end()

    def _mini_to_scene(self, mx, my):
        if not hasattr(self, '_map_items_rect'):
            return QPointF(0, 0)
        scene_x = self._map_items_rect.left() + (mx - self._map_off_x) / self._map_scale
        scene_y = self._map_items_rect.top() + (my - self._map_off_y) / self._map_scale
        return QPointF(scene_x, scene_y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._navigate_to(event.pos())

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._navigate_to(event.pos())

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def _navigate_to(self, pos):
        scene_pt = self._mini_to_scene(pos.x(), pos.y())
        self._canvas_view.centerOn(scene_pt)


# ============================================================
#  底部左下角控制栏
# ============================================================

class CanvasControlBar(QWidget):
    """
    画布左下角控制栏：
    - 小地图开关
    - 网格吸附开关
    - 适应视图按钮
    - 缩放滑块
    """

    MARGIN = 10

    def __init__(self, canvas_view: 'CanvasView', parent=None):
        super().__init__(parent)
        self._canvas_view = canvas_view
        self._mini_map: Optional[CanvasMiniMap] = None
        self._mini_map_visible = False

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._init_ui()
        self._apply_style()

        # 监听画布缩放变化
        self._canvas_view.zoom_changed.connect(self._on_zoom_changed)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 小地图开关
        self._minimap_btn = QPushButton("小地图")
        self._minimap_btn.setCheckable(True)
        self._minimap_btn.setFixedHeight(24)
        self._minimap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._minimap_btn.clicked.connect(self._toggle_minimap)
        layout.addWidget(self._minimap_btn)

        # 网格吸附开关
        self._snap_btn = QPushButton("吸附")
        self._snap_btn.setCheckable(True)
        self._snap_btn.setFixedHeight(24)
        self._snap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._snap_btn.clicked.connect(self._toggle_snap)
        layout.addWidget(self._snap_btn)

        # 适应视图
        self._fit_btn = QPushButton("适应")
        self._fit_btn.setFixedHeight(24)
        self._fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_btn.clicked.connect(self._fit_view)
        layout.addWidget(self._fit_btn)

        # 分隔线
        sep = QFrame()
        sep.setFixedSize(1, 18)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.15);")
        layout.addWidget(sep)

        # 缩放滑块
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setFixedWidth(100)
        self._zoom_slider.setFixedHeight(20)
        self._zoom_slider.setMinimum(5)    # 5%
        self._zoom_slider.setMaximum(500)  # 500%
        self._zoom_slider.setValue(100)
        self._zoom_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self._zoom_slider)

        # 缩放百分比标签
        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(40)
        layout.addWidget(self._zoom_label)

        self.adjustSize()

    def _apply_style(self):
        self.setStyleSheet(f"""
            CanvasControlBar {{
                background-color: rgba(20, 20, 25, 210);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }}
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
                color: white;
            }}
            QPushButton:checked {{
                background-color: rgba(0, 122, 204, 0.4);
                border-color: rgba(0, 122, 204, 0.6);
                color: white;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: rgba(0, 122, 204, 0.9);
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::sub-page:horizontal {{
                background: rgba(0, 122, 204, 0.4);
                border-radius: 2px;
            }}
            QLabel {{
                color: rgba(255, 255, 255, 0.5);
                font-size: 10px;
                font-family: Consolas;
            }}
        """)

    def reposition(self):
        """定位到父控件左下角"""
        if self.parent():
            ph = self.parent().height()
            self.move(self.MARGIN, ph - self.height() - self.MARGIN)
            # 小地图定位在控制栏上方
            if self._mini_map and self._mini_map.isVisible():
                self._mini_map.move(
                    self.MARGIN,
                    ph - self.height() - self.MARGIN - CanvasMiniMap.MINIMAP_H - 6
                )

    def _toggle_minimap(self):
        if self._mini_map is None:
            self._mini_map = CanvasMiniMap(self._canvas_view, parent=self.parent())
        self._mini_map_visible = not self._mini_map_visible
        self._mini_map.setVisible(self._mini_map_visible)
        self._minimap_btn.setChecked(self._mini_map_visible)
        self.reposition()

    def _toggle_snap(self):
        enabled = self._snap_btn.isChecked()
        self._canvas_view.set_grid_snap(enabled)

    def _fit_view(self):
        self._canvas_view.fit_all_in_view()

    def _on_slider_changed(self, value):
        self._canvas_view.set_zoom(value)

    def _on_zoom_changed(self, percent: int):
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(min(500, max(5, percent)))
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{percent}%")


class CanvasView(BaseCanvasView):
    """
    画布视图 - 右键平移、左键框选、打组、Ctrl多选、双击、拖放接收
    """

    scene_selected = pyqtSignal(int)  # scene_index
    scene_order_changed = pyqtSignal(list)  # 新的场景顺序 [scene_id, ...]
    card_double_clicked = pyqtSignal(int)  # scene_index
    cards_multi_selected = pyqtSignal(list)  # [scene_index, ...]
    card_context_menu_requested = pyqtSignal(int, QPointF)  # scene_index, global_pos
    character_dropped_on_card = pyqtSignal(int, dict)  # scene_index, char_data
    prop_dropped_on_card = pyqtSignal(int, dict)  # scene_index, prop_data
    canvas_blank_clicked = pyqtSignal()  # 点击空白区域
    batch_generate_from_group = pyqtSignal(list)  # [scene_index, ...]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.cards: List[SceneCanvasCard] = []
        self.connections: List[CurvedConnectionLine] = []
        self._selected_card: Optional[SceneCanvasCard] = None
        self._multi_selected: Set[int] = set()  # 多选的卡片索引
        self._show_connections = True
        self._group_rects: List[Any] = []  # 分组矩形图形项（遗留兼容）
        self._frame_preview_items: List = []  # 帧预览图形项

        # 浮动工具栏（单卡片）
        self._floating_toolbar = CardFloatingToolbar()
        self._toolbar_proxy: Optional[QGraphicsProxyWidget] = None
        self._toolbar_opacity_effect = QGraphicsOpacityEffect()
        self._floating_toolbar.setGraphicsEffect(self._toolbar_opacity_effect)

        # 分组浮动工具栏
        self._group_toolbar = GroupFloatingToolbar()
        self._group_toolbar_proxy: Optional[QGraphicsProxyWidget] = None
        self._group_toolbar_opacity = QGraphicsOpacityEffect()
        self._group_toolbar.setGraphicsEffect(self._group_toolbar_opacity)
        self._connect_group_toolbar_signals()

        # 分组数据
        self._groups: List[CardGroup] = []
        self._active_group: Optional[CardGroup] = None  # 当前选中的组

        # 框选状态
        self._is_rubber_banding = False
        self._rubber_band_start: Optional[QPointF] = None
        self._rubber_band_rect_item: Optional[QGraphicsRectItem] = None

        # 框选后的"打组"按钮
        self._group_btn_proxy: Optional[QGraphicsProxyWidget] = None
        self._group_btn: Optional[QPushButton] = None

        self.setAcceptDrops(True)

        # 底部控制栏（替代小地图）
        self._control_bar = CanvasControlBar(self, parent=self)
        self._control_bar.show()

    def _connect_group_toolbar_signals(self):
        self._group_toolbar.color_change_requested.connect(self._on_group_color_change)
        self._group_toolbar.layout_grid_requested.connect(self._on_group_layout_grid)
        self._group_toolbar.layout_horizontal_requested.connect(self._on_group_layout_horizontal)
        self._group_toolbar.execute_group_requested.connect(self._on_group_execute)
        self._group_toolbar.ungroup_requested.connect(self._on_group_ungroup)

    def resizeEvent(self, event):
        """窗口大小变化时重新定位控制栏"""
        super().resizeEvent(event)
        self._control_bar.reposition()

    def load_scenes(self, scenes: List[Dict[str, Any]]):
        """加载场景到画布"""
        self._clear()

        # 自动网格布局
        cols = max(1, int((self.width() - 60) / (SceneCanvasCard.CARD_WIDTH + 50)))
        if cols < 1:
            cols = 4

        for i, scene_data in enumerate(scenes):
            card = SceneCanvasCard(i, scene_data)
            row = i // cols
            col = i % cols
            x = 30 + col * (SceneCanvasCard.CARD_WIDTH + 50)
            y = 30 + row * (SceneCanvasCard.CARD_HEIGHT + 60)
            card.setPos(x, y)
            self._canvas_scene.addItem(card)
            self.cards.append(card)

        # 绘制连接线
        self._update_connections()

        # 使用 SmartViewportUpdate 当场景数量大时
        if len(scenes) > 100:
            self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)

        # 调整场景大小
        self._expand_scene_rect()

    def _clear(self):
        """清空画布"""
        for conn in self.connections:
            conn.remove(self._canvas_scene)
        self.connections.clear()
        self._clear_frame_previews()
        self._clear_group_rects()
        self._remove_group_btn()
        self.cards.clear()

        # 在 scene.clear() 之前，把浮动工具栏的 proxy 从场景中移除保护起来，
        # 防止 clear() 销毁 QGraphicsProxyWidget 连带销毁 widget。
        # 注意：必须保留引用，否则 GC 回收 proxy 仍会销毁 widget。
        if self._toolbar_proxy and self._toolbar_proxy.scene():
            self._canvas_scene.removeItem(self._toolbar_proxy)
        if self._group_toolbar_proxy and self._group_toolbar_proxy.scene():
            self._canvas_scene.removeItem(self._group_toolbar_proxy)

        # 清除分组的场景图形项
        for group in self._groups:
            if group.rect_item and group.rect_item.scene():
                self._canvas_scene.removeItem(group.rect_item)
            if group.label_item and hasattr(group.label_item, 'scene') and group.label_item.scene():
                self._canvas_scene.removeItem(group.label_item)
        self._groups.clear()
        self._active_group = None

        self._canvas_scene.clear()
        self._selected_card = None
        self._multi_selected.clear()

    def _clear_group_rects(self):
        """清除分组矩形"""
        for rect_item in self._group_rects:
            if rect_item.scene():
                self._canvas_scene.removeItem(rect_item)
        self._group_rects.clear()

    def _update_connections(self):
        """更新场景间连线"""
        for conn in self.connections:
            conn.remove(self._canvas_scene)
        self.connections.clear()

        if not self._show_connections:
            return

        for i in range(len(self.cards) - 1):
            linked = self._check_frame_link(self.cards[i], self.cards[i + 1])
            conn = CurvedConnectionLine(
                self._canvas_scene, self.cards[i], self.cards[i + 1],
                is_linked=linked
            )
            self.connections.append(conn)

    def set_show_connections(self, show: bool):
        self._show_connections = show
        self._update_connections()

    # ==================== 浮动工具栏管理 ====================

    def _show_floating_toolbar(self, card: SceneCanvasCard):
        """在选中卡片上方显示浮动工具栏"""
        self._floating_toolbar.set_scene_index(card.scene_index)
        self._floating_toolbar._apply_style()
        self._floating_toolbar.adjustSize()

        if self._toolbar_proxy is None:
            self._toolbar_proxy = self._canvas_scene.addWidget(self._floating_toolbar)
            self._toolbar_proxy.setZValue(1000)
        elif not self._toolbar_proxy.scene():
            self._canvas_scene.addItem(self._toolbar_proxy)

        # 定位在卡片上方居中
        card_rect = card.sceneBoundingRect()
        toolbar_w = self._floating_toolbar.sizeHint().width()
        toolbar_h = self._floating_toolbar.sizeHint().height()
        tx = card_rect.center().x() - toolbar_w / 2
        ty = card_rect.top() - toolbar_h - 8
        self._toolbar_proxy.setPos(tx, ty)
        self._toolbar_proxy.setVisible(True)

        # 淡入动画
        self._toolbar_opacity_effect.setOpacity(0)
        self._toolbar_fade_anim = QPropertyAnimation(self._toolbar_opacity_effect, b"opacity")
        self._toolbar_fade_anim.setDuration(150)
        self._toolbar_fade_anim.setStartValue(0.0)
        self._toolbar_fade_anim.setEndValue(1.0)
        self._toolbar_fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._toolbar_fade_anim.start()

    def _hide_floating_toolbar(self):
        """隐藏浮动工具栏"""
        if self._toolbar_proxy and self._toolbar_proxy.isVisible():
            self._toolbar_proxy.setVisible(False)

    def get_floating_toolbar(self) -> CardFloatingToolbar:
        """获取浮动工具栏实例，供外部连接信号"""
        return self._floating_toolbar

    def select_card(self, index: int):
        """选中指定卡片"""
        self._clear_multi_selection()
        if self._selected_card:
            self._selected_card.set_selected(False)

        if 0 <= index < len(self.cards):
            self._selected_card = self.cards[index]
            self._selected_card.set_selected(True)
            self.centerOn(self._selected_card)

    def _clear_multi_selection(self):
        """清除多选"""
        for idx in self._multi_selected:
            if 0 <= idx < len(self.cards):
                self.cards[idx].set_multi_selected(False)
        self._multi_selected.clear()

    def get_multi_selected_indices(self) -> List[int]:
        """获取多选的索引列表"""
        return sorted(self._multi_selected)

    # ==================== 帧关联检测与预览 ====================

    def _check_frame_link(self, card_a: SceneCanvasCard, card_b: SceneCanvasCard) -> bool:
        """检测 card_a 的尾帧是否被 card_b 借用"""
        end_frame = card_a.scene_data.get('end_frame_path', '')
        if not end_frame:
            return False
        start_frame = card_b.scene_data.get('start_frame_path', '')
        if end_frame and start_frame == end_frame:
            return True
        gen_params = card_b.scene_data.get('generation_params') or {}
        return gen_params.get('use_prev_end_frame', False)

    def _show_related_frames(self, card: SceneCanvasCard):
        """在选中卡片上方显示关联帧预览"""
        self._clear_frame_previews()

        try:
            idx = self.cards.index(card)
        except ValueError:
            return

        card_pos = card.scenePos()
        card_x = card_pos.x()
        card_y = card_pos.y()

        # 与前一个卡片的帧关联：显示前一个卡片的尾帧
        if idx > 0 and self._check_frame_link(self.cards[idx - 1], card):
            prev_end_frame = self.cards[idx - 1].scene_data.get('end_frame_path', '')
            if prev_end_frame and os.path.exists(prev_end_frame):
                self._add_frame_preview(
                    prev_end_frame, card_x, card_y - 80,
                    "\u4e0a\u4e00\u5e27\u5c3e\u5e27"  # 上一帧尾帧
                )

        # 与后一个卡片的帧关联：显示当前卡片的尾帧
        if idx < len(self.cards) - 1 and self._check_frame_link(card, self.cards[idx + 1]):
            cur_end_frame = card.scene_data.get('end_frame_path', '')
            if cur_end_frame and os.path.exists(cur_end_frame):
                self._add_frame_preview(
                    cur_end_frame,
                    card_x + SceneCanvasCard.CARD_WIDTH - 80,
                    card_y - 80,
                    "\u501f\u7528\u4e3a\u4e0b\u4e00\u5e27\u9996\u5e27"  # 借用为下一帧首帧
                )

    def _add_frame_preview(self, image_path: str, x: float, y: float, label_text: str):
        """添加一个帧预览到场景中"""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return
        pixmap = pixmap.scaled(80, 56, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)

        # 半透明背景框
        bg_rect = self._canvas_scene.addRect(
            QRectF(x - 2, y - 2, 84, 74),
            QPen(QColor(0, 122, 204, 120), 1),
            QBrush(QColor(0, 0, 0, 160))
        )
        bg_rect.setZValue(900)
        self._frame_preview_items.append(bg_rect)

        # 帧图片
        pix_item = QGraphicsPixmapItem(pixmap)
        pix_item.setPos(x, y)
        pix_item.setZValue(901)
        self._canvas_scene.addItem(pix_item)
        self._frame_preview_items.append(pix_item)

        # 文字标签
        text_item = QGraphicsTextItem(label_text)
        text_item.setDefaultTextColor(QColor(180, 220, 255))
        text_item.setFont(QFont("Arial", 8))
        text_item.setPos(x, y + 58)
        text_item.setZValue(902)
        self._canvas_scene.addItem(text_item)
        self._frame_preview_items.append(text_item)

        # 淡入效果
        for item in [bg_rect, pix_item, text_item]:
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(0)
            item.setGraphicsEffect(opacity_effect)
            anim = QPropertyAnimation(opacity_effect, b"opacity")
            anim.setDuration(150)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            # 保持动画引用防止被垃圾回收
            self._frame_preview_items.append(anim)

    def _clear_frame_previews(self):
        """清除所有帧预览项"""
        for item in self._frame_preview_items:
            if isinstance(item, QPropertyAnimation):
                item.stop()
            elif hasattr(item, 'scene') and item.scene():
                self._canvas_scene.removeItem(item)
        self._frame_preview_items.clear()

    # ==================== 排列方式 ====================

    def auto_arrange_grid(self):
        """自动网格排列"""
        cols = max(1, int((self.width() - 60) / (SceneCanvasCard.CARD_WIDTH + 50)))
        for i, card in enumerate(self.cards):
            row = i // cols
            col = i % cols
            x = 30 + col * (SceneCanvasCard.CARD_WIDTH + 50)
            y = 30 + row * (SceneCanvasCard.CARD_HEIGHT + 60)
            card.setPos(x, y)
        self._update_connections()
        self._expand_scene_rect()

    def auto_arrange_horizontal(self):
        """水平时间线排列"""
        for i, card in enumerate(self.cards):
            x = 30 + i * (SceneCanvasCard.CARD_WIDTH + 50)
            y = 100
            card.setPos(x, y)
        self._update_connections()
        self._expand_scene_rect()

    def auto_arrange_storyboard(self):
        """故事板排列（2行交错）"""
        for i, card in enumerate(self.cards):
            row = i % 2
            col = i // 2
            x = 30 + col * (SceneCanvasCard.CARD_WIDTH + 50)
            y = 30 + row * (SceneCanvasCard.CARD_HEIGHT + 60)
            card.setPos(x, y)
        self._update_connections()
        self._expand_scene_rect()

    # ==================== 分组矩形 ====================

    def add_group_rect(self, card_indices: List[int], color: QColor = None, label: str = ""):
        """为一组卡片绘制半透明包围框"""
        if not card_indices:
            return

        if color is None:
            from config.constants import CANVAS_GROUP_COLORS
            color = CANVAS_GROUP_COLORS[len(self._group_rects) % len(CANVAS_GROUP_COLORS)]

        # 计算包围矩形
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        for idx in card_indices:
            if 0 <= idx < len(self.cards):
                card = self.cards[idx]
                pos = card.scenePos()
                min_x = min(min_x, pos.x())
                min_y = min(min_y, pos.y())
                max_x = max(max_x, pos.x() + SceneCanvasCard.CARD_WIDTH)
                max_y = max(max_y, pos.y() + SceneCanvasCard.CARD_HEIGHT)

        if min_x == float('inf'):
            return

        padding = 15
        rect = QRectF(min_x - padding, min_y - padding,
                      max_x - min_x + 2 * padding,
                      max_y - min_y + 2 * padding)

        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        path_item = self._canvas_scene.addPath(
            path,
            QPen(QColor(color.red(), color.green(), color.blue(), 80), 1, Qt.PenStyle.DashLine),
            QBrush(color)
        )
        path_item.setZValue(-1)  # 在卡片下方
        self._group_rects.append(path_item)

        # 标签
        if label:
            text_item = self._canvas_scene.addText(label, QFont("Arial", 10, QFont.Weight.Bold))
            text_item.setDefaultTextColor(QColor(color.red(), color.green(), color.blue(), 150))
            text_item.setPos(min_x - padding + 5, min_y - padding - 20)
            text_item.setZValue(-1)
            self._group_rects.append(text_item)

    # ==================== 卡片数据更新 API ====================

    def update_card(self, index: int, new_data: Dict[str, Any]):
        """更新指定卡片的数据"""
        if 0 <= index < len(self.cards):
            self.cards[index].update_scene_data(new_data)

    def update_card_progress(self, index: int, progress: int, is_generating: bool = True):
        """更新卡片生成进度"""
        if 0 <= index < len(self.cards):
            self.cards[index].set_generation_progress(progress, is_generating)

    def update_card_characters(self, index: int, characters: List[Dict[str, Any]]):
        """更新卡片角色数据"""
        if 0 <= index < len(self.cards):
            self.cards[index].set_characters(characters)

    # ==================== 事件处理 ====================

    def _is_interactive_proxy(self, item) -> bool:
        """检查 item 是否是交互性 proxy widget（打组按钮、工具栏等），
        这些 item 应该由 QGraphicsScene 正常分发事件，不应被框选逻辑拦截。"""
        if item is None:
            return False
        # QGraphicsProxyWidget 本身
        if isinstance(item, QGraphicsProxyWidget):
            return True
        # proxy 的子 item（文字、图标等）
        parent = item.parentItem()
        while parent is not None:
            if isinstance(parent, QGraphicsProxyWidget):
                return True
            parent = parent.parentItem()
        return False

    def mousePressEvent(self, event):
        """
        左键点击：
          - 点击 proxy widget（按钮/工具栏）→ 交给 QGraphicsView 正常分发
          - 点击卡片 → 选中（Ctrl多选）
          - 点击组背景（GroupBackgroundItem） → 显示组工具栏，交给背景项处理拖拽
          - 点击空白 → 开始框选
        右键：由基类 BaseCanvasView 处理平移
        """
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            ctrl_pressed = event.modifiers() & Qt.KeyboardModifier.ControlModifier

            # 点击的是 proxy widget（打组按钮、浮动工具栏、组工具栏等）→ 交给默认处理
            if self._is_interactive_proxy(item):
                super().mousePressEvent(event)
                return

            if isinstance(item, SceneCanvasCard):
                # 点击卡片
                self._hide_group_toolbar()
                self._remove_group_btn()

                if ctrl_pressed:
                    idx = item.scene_index
                    if idx in self._multi_selected:
                        self._multi_selected.discard(idx)
                        item.set_multi_selected(False)
                    else:
                        self._multi_selected.add(idx)
                        item.set_multi_selected(True)
                    self.cards_multi_selected.emit(sorted(self._multi_selected))
                    self._hide_floating_toolbar()
                    self._clear_frame_previews()
                    # Ctrl 多选 ≥2 张卡片时显示"打组"按钮
                    if len(self._multi_selected) >= 2:
                        self._show_group_btn()
                    else:
                        self._remove_group_btn()
                else:
                    self._clear_multi_selection()
                    if self._selected_card:
                        self._selected_card.set_selected(False)
                    self._selected_card = item
                    item.set_selected(True)
                    self.scene_selected.emit(item.scene_index)
                    self._show_floating_toolbar(item)
                    self._show_related_frames(item)

                # 允许卡片拖拽移动
                super().mousePressEvent(event)
                return

            # 点击组背景 → 显示组工具栏 + 由 GroupBackgroundItem 处理拖拽
            if isinstance(item, GroupBackgroundItem) and not ctrl_pressed:
                clicked_group = item._group
                self._active_group = clicked_group
                self._hide_floating_toolbar()
                self._clear_frame_previews()
                self._remove_group_btn()
                if self._selected_card:
                    self._selected_card.set_selected(False)
                    self._selected_card = None
                self._show_group_toolbar(clicked_group)
                # 交给 QGraphicsView 分发，让 GroupBackgroundItem 收到 press 事件
                super().mousePressEvent(event)
                return

            # 空白区域 → 框选
            if not ctrl_pressed:
                self._clear_multi_selection()
                if self._selected_card:
                    self._selected_card.set_selected(False)
                    self._selected_card = None
                self._hide_floating_toolbar()
                self._hide_group_toolbar()
                self._clear_frame_previews()
                self._remove_group_btn()
                self.canvas_blank_clicked.emit()

            # 开始框选
            self._is_rubber_banding = True
            self._rubber_band_start = self.mapToScene(event.pos())
            # 开启鼠标追踪，确保拖动过程中 mouseMoveEvent 持续被调用
            self.setMouseTracking(True)
            event.accept()
            return

        # 右键由基类处理
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """左键拖动 → 绘制框选矩形"""
        if self._is_rubber_banding and self._rubber_band_start is not None:
            current = self.mapToScene(event.pos())
            rect = QRectF(self._rubber_band_start, current).normalized()

            if self._rubber_band_rect_item is None:
                self._rubber_band_rect_item = self._canvas_scene.addRect(
                    rect,
                    QPen(QColor(0, 122, 204, 180), 1.5, Qt.PenStyle.DashLine),
                    QBrush(QColor(0, 122, 204, 25))
                )
                self._rubber_band_rect_item.setZValue(2000)
            else:
                self._rubber_band_rect_item.setRect(rect)

            # 实时高亮框内卡片
            self._update_rubber_band_selection(rect)

            event.accept()
            return

        super().mouseMoveEvent(event)

    def _update_rubber_band_selection(self, rect: QRectF):
        """根据框选矩形实时更新卡片的多选高亮"""
        # 先取消所有多选高亮
        for idx in self._multi_selected:
            if 0 <= idx < len(self.cards):
                self.cards[idx].set_multi_selected(False)
        self._multi_selected.clear()

        # 检测框内卡片
        for card in self.cards:
            if rect.intersects(card.sceneBoundingRect()):
                self._multi_selected.add(card.scene_index)
                card.set_multi_selected(True)

    def mouseReleaseEvent(self, event):
        """左键释放 → 完成框选，显示"打组"按钮"""
        if event.button() == Qt.MouseButton.LeftButton and self._is_rubber_banding:
            self._is_rubber_banding = False
            self.setMouseTracking(False)

            # 移除框选矩形
            if self._rubber_band_rect_item:
                if self._rubber_band_rect_item.scene():
                    self._canvas_scene.removeItem(self._rubber_band_rect_item)
                self._rubber_band_rect_item = None

            # 如果框选了多张卡片，显示"打组"按钮
            if len(self._multi_selected) >= 2:
                self.cards_multi_selected.emit(sorted(self._multi_selected))
                self._show_group_btn()
            else:
                self._clear_multi_selection()

            self._rubber_band_start = None
            event.accept()
            return

        super().mouseReleaseEvent(event)
        self._update_connections()
        self._expand_scene_rect()
        # 更新已有分组的包围框
        self._update_all_group_rects()

    def mouseDoubleClickEvent(self, event):
        """双击事件"""
        item = self.itemAt(event.pos())
        if isinstance(item, SceneCanvasCard):
            self.card_double_clicked.emit(item.scene_index)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单事件 — 仅在右键没有拖动（未平移）时触发"""
        if self._pan_moved:
            # 右键拖动过，不弹菜单
            event.accept()
            return
        item = self.itemAt(event.pos())
        if isinstance(item, SceneCanvasCard):
            global_pos = event.globalPos()
            self.card_context_menu_requested.emit(
                item.scene_index, QPointF(global_pos.x(), global_pos.y())
            )
        else:
            super().contextMenuEvent(event)

    # ==================== 拖放支持 ====================

    def dragEnterEvent(self, event):
        """拖放进入事件"""
        mime = event.mimeData()
        if (mime.hasFormat("application/x-taoge-character") or
                mime.hasFormat("application/x-taoge-prop")):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """拖放移动事件 - 高亮鼠标下方的卡片"""
        mime = event.mimeData()
        if (mime.hasFormat("application/x-taoge-character") or
                mime.hasFormat("application/x-taoge-prop")):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """拖放释放事件"""
        import json

        mime = event.mimeData()
        pos = event.position() if hasattr(event, 'position') else event.posF()
        scene_pos = self.mapToScene(int(pos.x()), int(pos.y()))

        # 找到落点卡片
        target_card = None
        for card in self.cards:
            if card.sceneBoundingRect().contains(scene_pos):
                target_card = card
                break

        if target_card is None:
            event.ignore()
            return

        if mime.hasFormat("application/x-taoge-character"):
            data = bytes(mime.data("application/x-taoge-character")).decode('utf-8')
            char_data = json.loads(data)
            self.character_dropped_on_card.emit(target_card.scene_index, char_data)
            event.acceptProposedAction()

        elif mime.hasFormat("application/x-taoge-prop"):
            data = bytes(mime.data("application/x-taoge-prop")).decode('utf-8')
            prop_data = json.loads(data)
            self.prop_dropped_on_card.emit(target_card.scene_index, prop_data)
            event.acceptProposedAction()

        else:
            event.ignore()

    # ==================== 框选 → 打组 ====================

    def _show_group_btn(self):
        """在框选卡片的中心上方显示"打组"按钮"""
        self._remove_group_btn()

        # 计算框选卡片的包围盒
        rect = self._get_multi_selected_bounds()
        if rect is None:
            return

        self._group_btn = QPushButton("打组")
        self._group_btn.setFixedSize(60, 28)
        self._group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._group_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.accent_hover()};
            }}
        """)
        self._group_btn.clicked.connect(self._on_create_group)

        self._group_btn_proxy = self._canvas_scene.addWidget(self._group_btn)
        self._group_btn_proxy.setZValue(2000)
        self._group_btn_proxy.setPos(
            rect.center().x() - 30,
            rect.top() - 40
        )

    def _remove_group_btn(self):
        """移除打组按钮"""
        if self._group_btn_proxy:
            if self._group_btn_proxy.scene():
                self._canvas_scene.removeItem(self._group_btn_proxy)
            self._group_btn_proxy = None
            self._group_btn = None

    def _on_create_group(self):
        """创建分组"""
        if len(self._multi_selected) < 2:
            return

        indices = sorted(self._multi_selected)

        # 检测是否为连续序号
        is_consecutive = all(
            indices[i] + 1 == indices[i + 1] for i in range(len(indices) - 1)
        )
        if not is_consecutive:
            # 不连续，弹出提示，保留框选状态
            bounds = self._get_multi_selected_bounds()
            if bounds:
                view_pt = self.mapFromScene(bounds.center())
                cursor_pos = self.mapToGlobal(view_pt)
            else:
                cursor_pos = self.cursor().pos()
            QToolTip.showText(cursor_pos, "只能对连续的场景打组", self, msecShowTime=2000)
            return
        group = CardGroup(indices, QColor(0, 122, 204, 50))
        self._groups.append(group)

        # 绘制组背景矩形
        self._draw_group_rect(group)

        # 清除框选状态
        self._clear_multi_selection()

        # 先隐藏打组按钮，延迟到下一事件循环再移除 ——
        # 当前处于按钮 clicked 信号处理中，直接移除/销毁按钮
        # 会导致 C++ 对象在信号发射链完成前被销毁，引发崩溃
        if self._group_btn_proxy:
            self._group_btn_proxy.setVisible(False)
        QTimer.singleShot(0, self._remove_group_btn)

        # 立即显示组工具栏
        self._active_group = group
        self._show_group_toolbar(group)

    def _draw_group_rect(self, group: CardGroup):
        """为组绘制/更新圆角背景（GroupBackgroundItem）"""
        rect = self._get_group_bounds(group)
        if rect is None:
            return

        if group.rect_item and group.rect_item.scene():
            # 已有背景，只更新形状和颜色
            group.rect_item.update_shape(rect, group.color)
        else:
            # 新建
            bg = GroupBackgroundItem(group, self.cards, self)
            bg.update_shape(rect, group.color)
            self._canvas_scene.addItem(bg)
            group.rect_item = bg

    def _get_group_bounds(self, group: CardGroup) -> Optional[QRectF]:
        """计算组内卡片的包围盒"""
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        for idx in group.card_indices:
            if 0 <= idx < len(self.cards):
                card = self.cards[idx]
                pos = card.scenePos()
                min_x = min(min_x, pos.x())
                min_y = min(min_y, pos.y())
                max_x = max(max_x, pos.x() + SceneCanvasCard.CARD_WIDTH)
                max_y = max(max_y, pos.y() + SceneCanvasCard.CARD_HEIGHT)

        if min_x == float('inf'):
            return None
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def _get_multi_selected_bounds(self) -> Optional[QRectF]:
        """计算多选卡片的包围盒"""
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        for idx in self._multi_selected:
            if 0 <= idx < len(self.cards):
                card = self.cards[idx]
                pos = card.scenePos()
                min_x = min(min_x, pos.x())
                min_y = min(min_y, pos.y())
                max_x = max(max_x, pos.x() + SceneCanvasCard.CARD_WIDTH)
                max_y = max(max_y, pos.y() + SceneCanvasCard.CARD_HEIGHT)

        if min_x == float('inf'):
            return None
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def _update_all_group_rects(self):
        """刷新所有组的包围框位置"""
        for group in self._groups:
            self._draw_group_rect(group)

    def _find_group_at(self, view_pos) -> Optional[CardGroup]:
        """检查视口坐标处是否有组背景"""
        scene_pos = self.mapToScene(view_pos)
        for group in self._groups:
            if group.rect_item:
                if group.rect_item.sceneBoundingRect().contains(scene_pos):
                    return group
        return None

    # ==================== 组工具栏 ====================

    def _show_group_toolbar(self, group: CardGroup):
        """在组上方显示组工具栏"""
        self._group_toolbar.set_group(group.group_id, group.card_indices, group.color)
        self._group_toolbar._apply_style()
        self._group_toolbar.adjustSize()

        if self._group_toolbar_proxy is None:
            self._group_toolbar_proxy = self._canvas_scene.addWidget(self._group_toolbar)
            self._group_toolbar_proxy.setZValue(1001)
        elif not self._group_toolbar_proxy.scene():
            self._canvas_scene.addItem(self._group_toolbar_proxy)

        rect = self._get_group_bounds(group)
        if rect is None:
            return
        toolbar_w = self._group_toolbar.sizeHint().width()
        toolbar_h = self._group_toolbar.sizeHint().height()
        tx = rect.center().x() - toolbar_w / 2
        ty = rect.top() - toolbar_h - 30
        self._group_toolbar_proxy.setPos(tx, ty)
        self._group_toolbar_proxy.setVisible(True)

        # 淡入
        self._group_toolbar_opacity.setOpacity(0)
        self._gt_fade = QPropertyAnimation(self._group_toolbar_opacity, b"opacity")
        self._gt_fade.setDuration(150)
        self._gt_fade.setStartValue(0.0)
        self._gt_fade.setEndValue(1.0)
        self._gt_fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._gt_fade.start()

    def _hide_group_toolbar(self):
        if self._group_toolbar_proxy and self._group_toolbar_proxy.isVisible():
            self._group_toolbar_proxy.setVisible(False)
        self._active_group = None

    # ==================== 组操作回调 ====================

    def _on_group_color_change(self, group_id: int, color: QColor):
        group = self._find_group_by_id(group_id)
        if group:
            group.color = color
            self._draw_group_rect(group)

    def _on_group_layout_grid(self, group_id: int):
        group = self._find_group_by_id(group_id)
        if not group:
            return
        indices = group.card_indices
        cols = max(1, int(len(indices) ** 0.5))
        base_x, base_y = self._get_group_origin(group)
        for i, idx in enumerate(indices):
            if 0 <= idx < len(self.cards):
                row = i // cols
                col = i % cols
                x = base_x + col * (SceneCanvasCard.CARD_WIDTH + 30)
                y = base_y + row * (SceneCanvasCard.CARD_HEIGHT + 30)
                self.cards[idx].setPos(x, y)
        self._draw_group_rect(group)
        self._update_connections()
        if self._active_group == group:
            self._show_group_toolbar(group)

    def _on_group_layout_horizontal(self, group_id: int):
        group = self._find_group_by_id(group_id)
        if not group:
            return
        base_x, base_y = self._get_group_origin(group)
        for i, idx in enumerate(group.card_indices):
            if 0 <= idx < len(self.cards):
                x = base_x + i * (SceneCanvasCard.CARD_WIDTH + 30)
                y = base_y
                self.cards[idx].setPos(x, y)
        self._draw_group_rect(group)
        self._update_connections()
        if self._active_group == group:
            self._show_group_toolbar(group)

    def _on_group_execute(self, group_id: int, card_indices: list):
        self.batch_generate_from_group.emit(card_indices)

    def _on_group_ungroup(self, group_id: int):
        group = self._find_group_by_id(group_id)
        if group:
            if group.rect_item and group.rect_item.scene():
                self._canvas_scene.removeItem(group.rect_item)
            if group.label_item and hasattr(group.label_item, 'scene') and group.label_item.scene():
                self._canvas_scene.removeItem(group.label_item)
            self._groups.remove(group)
        self._hide_group_toolbar()

    def _find_group_by_id(self, group_id: int) -> Optional[CardGroup]:
        for g in self._groups:
            if g.group_id == group_id:
                return g
        return None

    def _get_group_origin(self, group: CardGroup):
        """获取组内最左上角的卡片位置"""
        min_x = float('inf')
        min_y = float('inf')
        for idx in group.card_indices:
            if 0 <= idx < len(self.cards):
                pos = self.cards[idx].scenePos()
                min_x = min(min_x, pos.x())
                min_y = min(min_y, pos.y())
        return (min_x if min_x != float('inf') else 0,
                min_y if min_y != float('inf') else 0)


class CanvasModePanel(QFrame):
    """
    Canvas画布模式面板
    提供工具栏 + 左侧边栏 + 画布视图 + 右侧属性面板
    """

    scene_selected = pyqtSignal(int)  # scene_index
    back_to_editor = pyqtSignal()
    batch_generate_requested = pyqtSignal(list)  # [scene_index, ...]
    generate_image_requested = pyqtSignal(int)  # scene_index
    generate_video_requested = pyqtSignal(int)  # scene_index
    scene_deleted = pyqtSignal(int)  # scene_index
    scene_duplicated = pyqtSignal(int)  # scene_index
    character_dropped = pyqtSignal(int, dict)  # scene_index, char_data
    prop_dropped = pyqtSignal(int, dict)  # scene_index, prop_data
    property_changed_from_canvas = pyqtSignal(str, object)  # prop_name, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes_data: List[Dict[str, Any]] = []
        self._property_panel = None  # 延迟导入
        self.canvas_sidebar = None

        self.setObjectName("canvasModePanel")
        self._apply_panel_theme()

        self._init_ui()

    def _apply_panel_theme(self):
        bg = theme.bg_primary()
        self.setStyleSheet(f"""
            QFrame#canvasModePanel {{
                background-color: {bg};
            }}
        """)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 主内容区（左侧边栏 + 画布 + 可选属性面板）
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.05);
                width: 1px;
            }
        """)

        # 左侧边栏（角色区+道具区）
        from .canvas_sidebar import CanvasSidebar
        self.canvas_sidebar = CanvasSidebar()
        self.main_splitter.addWidget(self.canvas_sidebar)

        # 画布
        self.canvas_view = CanvasView()
        self.canvas_view.scene_selected.connect(self._on_scene_selected)
        self.canvas_view.card_double_clicked.connect(self._on_card_double_clicked)
        self.canvas_view.cards_multi_selected.connect(self._on_multi_selected)
        self.canvas_view.card_context_menu_requested.connect(self._on_context_menu_requested)
        self.canvas_view.zoom_changed.connect(self._on_zoom_changed)
        self.canvas_view.character_dropped_on_card.connect(self._on_character_dropped)
        self.canvas_view.prop_dropped_on_card.connect(self._on_prop_dropped)
        self.canvas_view.batch_generate_from_group.connect(
            lambda indices: self.batch_generate_requested.emit(indices)
        )
        self.main_splitter.addWidget(self.canvas_view)

        # 属性面板占位（延迟创建）
        self._property_panel_container = QFrame()
        self._property_panel_container.setVisible(False)
        self._property_panel_container.setMinimumWidth(320)
        self._property_panel_container.setMaximumWidth(400)
        self.main_splitter.addWidget(self._property_panel_container)
        self.main_splitter.setSizes([220, 1, 0])

        layout.addWidget(self.main_splitter, 1)

    def _create_toolbar(self) -> QFrame:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFixedHeight(44)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: rgb(28, 28, 32);
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 0, 12, 0)
        toolbar_layout.setSpacing(8)

        # 返回编辑器按钮
        back_btn = QPushButton("< 返回编辑器")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_to_editor.emit)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none; padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover { color: white; }
        """)
        toolbar_layout.addWidget(back_btn)

        # 分隔
        toolbar_layout.addWidget(self._create_sep())

        # 排列方式按钮组
        grid_btn = QPushButton("网格")
        grid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        grid_btn.clicked.connect(self._arrange_grid)
        grid_btn.setStyleSheet(self._get_tool_btn_style())
        toolbar_layout.addWidget(grid_btn)

        timeline_btn = QPushButton("时间线")
        timeline_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        timeline_btn.clicked.connect(self._arrange_horizontal)
        timeline_btn.setStyleSheet(self._get_tool_btn_style())
        toolbar_layout.addWidget(timeline_btn)

        storyboard_btn = QPushButton("故事板")
        storyboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        storyboard_btn.clicked.connect(self._arrange_storyboard)
        storyboard_btn.setStyleSheet(self._get_tool_btn_style())
        toolbar_layout.addWidget(storyboard_btn)

        toolbar_layout.addWidget(self._create_sep())

        # 连线开关
        self.conn_btn = QPushButton("显示连线")
        self.conn_btn.setCheckable(True)
        self.conn_btn.setChecked(True)
        self.conn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.conn_btn.clicked.connect(self._toggle_connections)
        self.conn_btn.setStyleSheet(self._get_tool_btn_style())
        toolbar_layout.addWidget(self.conn_btn)

        # 适应视图
        fit_btn = QPushButton("适应视图")
        fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fit_btn.clicked.connect(self._fit_view)
        fit_btn.setStyleSheet(self._get_tool_btn_style())
        toolbar_layout.addWidget(fit_btn)

        toolbar_layout.addWidget(self._create_sep())

        # 批量生成按钮
        self.batch_gen_btn = QPushButton("批量生成")
        self.batch_gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.batch_gen_btn.clicked.connect(self._on_batch_generate)
        self.batch_gen_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 122, 204, 0.2);
                color: rgb(100, 180, 255);
                border: 1px solid rgba(0, 122, 204, 0.3);
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(0, 122, 204, 0.3);
                color: white;
            }
        """)
        toolbar_layout.addWidget(self.batch_gen_btn)

        toolbar_layout.addStretch()

        # 缩放百分比
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px; font-family: Consolas;")
        toolbar_layout.addWidget(self.zoom_label)

        # 分隔
        toolbar_layout.addWidget(self._create_sep())

        # 场景统计
        self.stats_label = QLabel("0 场景")
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px;")
        toolbar_layout.addWidget(self.stats_label)

        return toolbar

    def _create_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFixedSize(1, 24)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        return sep

    def _get_tool_btn_style(self):
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
            QPushButton:checked {
                background-color: rgba(0, 122, 204, 0.3);
                border-color: rgba(0, 122, 204, 0.5);
                color: white;
            }
        """

    def _ensure_property_panel(self):
        """确保属性面板已创建"""
        if self._property_panel is None:
            from .canvas_property_panel import CanvasPropertyPanel
            self._property_panel = CanvasPropertyPanel()
            self._property_panel.close_requested.connect(self._hide_property_panel)
            self._property_panel.property_changed.connect(self._on_property_changed_from_panel)
            self._property_panel.generate_image_requested.connect(
                lambda idx: self.generate_image_requested.emit(idx)
            )
            self._property_panel.generate_video_requested.connect(
                lambda idx: self.generate_video_requested.emit(idx)
            )

            panel_layout = QVBoxLayout(self._property_panel_container)
            panel_layout.setContentsMargins(0, 0, 0, 0)
            panel_layout.addWidget(self._property_panel)

    def _show_property_panel(self, scene_index: int):
        """显示属性面板"""
        self._ensure_property_panel()

        if 0 <= scene_index < len(self.scenes_data):
            self._property_panel.set_scene(scene_index, self.scenes_data[scene_index])
            self._property_panel_container.setVisible(True)
            self.main_splitter.setSizes([220, self.width() - 580, 360])

    def _hide_property_panel(self):
        """隐藏属性面板"""
        self._property_panel_container.setVisible(False)
        self.main_splitter.setSizes([220, 1, 0])

    # ==================== 信号处理 ====================

    def _on_scene_selected(self, index: int):
        """场景被单击选中"""
        self.scene_selected.emit(index)

    def _on_card_double_clicked(self, index: int):
        """卡片被双击 → 显示属性面板"""
        self._show_property_panel(index)

    def _on_multi_selected(self, indices: List[int]):
        """多选变化"""
        pass

    def _on_context_menu_requested(self, scene_index: int, global_pos: QPointF):
        """右键菜单请求"""
        from .canvas_context_menu import show_canvas_context_menu
        multi_selected = self.canvas_view.get_multi_selected_indices()
        if scene_index not in multi_selected:
            multi_selected = []

        show_canvas_context_menu(
            parent=self,
            scene_index=scene_index,
            global_pos=global_pos,
            multi_selected=multi_selected,
            on_generate_image=lambda idx: self.generate_image_requested.emit(idx),
            on_generate_video=lambda idx: self.generate_video_requested.emit(idx),
            on_open_property=lambda idx: self._show_property_panel(idx),
            on_batch_generate=lambda indices: self.batch_generate_requested.emit(indices),
            on_delete_scene=lambda idx: self.scene_deleted.emit(idx),
            on_duplicate_scene=lambda idx: self.scene_duplicated.emit(idx),
        )

    def _on_zoom_changed(self, percent: int):
        """缩放变化"""
        self.zoom_label.setText(f"{percent}%")

    def _on_batch_generate(self):
        """批量生成按钮点击"""
        multi = self.canvas_view.get_multi_selected_indices()
        if multi:
            self.batch_generate_requested.emit(multi)
        else:
            # 所有未生成的场景
            all_indices = list(range(len(self.scenes_data)))
            self.batch_generate_requested.emit(all_indices)

    def _on_property_changed_from_panel(self, prop: str, value):
        """属性面板中的属性变化 → 转发到外部处理"""
        if self._property_panel and self._property_panel.current_scene_index >= 0:
            idx = self._property_panel.current_scene_index
            # 更新本地数据
            if 0 <= idx < len(self.scenes_data):
                if prop == "video_prompt_details":
                    gen_params = dict(self.scenes_data[idx].get('generation_params') or {})
                    gen_params.update(value)
                    self.scenes_data[idx]['generation_params'] = gen_params
                else:
                    self.scenes_data[idx][prop] = value
        # 转发给上层（scene_editor_page）
        self.property_changed_from_canvas.emit(prop, value)

    # ==================== 拖放处理 ====================

    def _on_character_dropped(self, scene_index: int, char_data: dict):
        """角色被拖放到卡片"""
        self.character_dropped.emit(scene_index, char_data)
        # 更新卡片角色显示
        if 0 <= scene_index < len(self.scenes_data):
            chars = self.scenes_data[scene_index].get('characters', [])
            if not any(c.get('id') == char_data.get('id') for c in chars):
                chars.append(char_data)
                self.scenes_data[scene_index]['characters'] = chars
                self.canvas_view.update_card_characters(scene_index, chars)

    def _on_prop_dropped(self, scene_index: int, prop_data: dict):
        """道具被拖放到卡片"""
        self.prop_dropped.emit(scene_index, prop_data)
        # 更新卡片道具数据
        if 0 <= scene_index < len(self.scenes_data):
            props = self.scenes_data[scene_index].get('props', [])
            if not any(p.get('id') == prop_data.get('id') for p in props):
                props.append(prop_data)
                self.scenes_data[scene_index]['props'] = props

    # ==================== 公开API ====================

    def load_scenes(self, scenes: List[Dict[str, Any]]):
        """加载场景数据"""
        self.scenes_data = scenes
        self.canvas_view.load_scenes(scenes)
        self.stats_label.setText(f"{len(scenes)} 场景")

    def select_scene(self, index: int):
        """选中场景"""
        self.canvas_view.select_card(index)

    def update_scene_data(self, index: int, scene_data: Dict[str, Any]):
        """更新单个场景数据"""
        if 0 <= index < len(self.scenes_data):
            self.scenes_data[index] = scene_data
            self.canvas_view.update_card(index, scene_data)

            # 更新属性面板（如果显示中）
            if (self._property_panel and
                    self._property_panel_container.isVisible() and
                    self._property_panel.current_scene_index == index):
                self._property_panel.set_scene(index, scene_data)

    def update_generation_progress(self, index: int, progress: int, is_generating: bool = True):
        """更新场景生成进度"""
        self.canvas_view.update_card_progress(index, progress, is_generating)

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
