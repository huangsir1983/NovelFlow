"""
涛割 - 源文本框
虚拟滚动文本显示 + 四角半圆缩放手柄。
用于导入文本后在画布上展示源文本内容。
"""

from typing import List, Optional

from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QPainterPath, QCursor,
)

from ui import theme
from ui.components.base_canvas_view import LOD_TEXT_MIN_PX


class CornerResizeHandle(QGraphicsEllipseItem):
    """
    四角半圆缩放手柄。
    半径 14px，hover 时显示，拖拽调整父 SourceTextBox 尺寸。
    """

    RADIUS = 14

    def __init__(self, corner: str, parent_box: 'SourceTextBox'):
        super().__init__(parent_box)
        self._corner = corner  # "tl" / "tr" / "bl" / "br"
        self._parent_box = parent_box
        self._dragging = False
        self._drag_start = QPointF()
        self._start_rect = QRectF()

        d = self.RADIUS * 2
        self.setRect(0, 0, d, d)
        self.setVisible(False)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        # 光标
        if corner in ("tl", "br"):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(theme.accent())))
        painter.setOpacity(0.7)
        painter.drawEllipse(self.rect())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start = event.scenePos()
            self._start_rect = QRectF(self._parent_box.rect())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.scenePos() - self._drag_start
            self._parent_box.resize_from_corner(self._corner, delta, self._start_rect)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()

    @property
    def is_dragging(self) -> bool:
        return self._dragging


class SourceTextBox(QGraphicsRectItem):
    """
    源文本框 — 虚拟滚动文本显示。
    - 默认 500x400，最小 300x200
    - 虚拟滚动：只绘制可见行
    - 四角半圆缩放手柄（hover 时显示）
    - 单击选中（accent 边框），再次单击取消
    - 顶部标题行 + 右侧迷你滚动条
    """

    MIN_WIDTH = 300
    MIN_HEIGHT = 200
    DEFAULT_WIDTH = 500
    DEFAULT_HEIGHT = 400
    CORNER_RADIUS = 12
    TITLE_HEIGHT = 36
    PADDING = 14
    LINE_SPACING = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text: str = ""
        self._wrapped_lines: List[str] = []
        self._scroll_offset: int = 0  # 第一个可见行的索引
        self._selected = False

        self.setRect(0, 0, self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        self.setAcceptHoverEvents(True)
        self.setZValue(5)

        # 字体
        self._text_font = QFont("Microsoft YaHei", 11)
        self._title_font = QFont("Microsoft YaHei", 10, QFont.Weight.Bold)
        self._fm = QFontMetrics(self._text_font)
        self._line_height = self._fm.height() + self.LINE_SPACING

        # 四角缩放手柄
        self._handles = {
            corner: CornerResizeHandle(corner, self)
            for corner in ("tl", "tr", "bl", "br")
        }
        self._update_handles()

    def set_text(self, text: str):
        """设置文本内容"""
        self._full_text = text
        self._scroll_offset = 0
        self._recompute_lines()
        self.update()

    def get_text(self) -> str:
        return self._full_text

    @property
    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def scroll_by(self, delta_lines: int):
        """滚动指定行数（正=向下，负=向上）"""
        max_offset = max(0, len(self._wrapped_lines) - self._visible_line_count())
        self._scroll_offset = max(0, min(max_offset, self._scroll_offset + delta_lines))
        self.update()

    def _visible_line_count(self) -> int:
        """当前可见行数"""
        content_h = self.rect().height() - self.TITLE_HEIGHT - self.PADDING * 2
        return max(1, int(content_h / self._line_height))

    def _recompute_lines(self):
        """根据当前宽度重新计算行换行"""
        self._wrapped_lines.clear()
        if not self._full_text:
            return

        text_width = int(self.rect().width() - self.PADDING * 2 - 16)  # 16 for scrollbar
        if text_width <= 0:
            return

        for paragraph in self._full_text.split('\n'):
            if not paragraph:
                self._wrapped_lines.append("")
                continue
            # 手动按宽度换行
            remaining = paragraph
            while remaining:
                # 二分查找一行能容纳的字符数
                fit = len(remaining)
                if self._fm.horizontalAdvance(remaining) <= text_width:
                    self._wrapped_lines.append(remaining)
                    break
                # 逐字查找换行点
                for i in range(1, len(remaining) + 1):
                    if self._fm.horizontalAdvance(remaining[:i]) > text_width:
                        fit = max(1, i - 1)
                        break
                self._wrapped_lines.append(remaining[:fit])
                remaining = remaining[fit:]

    def resize_from_corner(self, corner: str, delta: QPointF, start_rect: QRectF):
        """从角拖拽缩放"""
        new_w = start_rect.width()
        new_h = start_rect.height()

        if 'r' in corner:
            new_w = max(self.MIN_WIDTH, start_rect.width() + delta.x())
        if 'l' in corner:
            new_w = max(self.MIN_WIDTH, start_rect.width() - delta.x())
        if 'b' in corner:
            new_h = max(self.MIN_HEIGHT, start_rect.height() + delta.y())
        if 't' in corner:
            new_h = max(self.MIN_HEIGHT, start_rect.height() - delta.y())

        self.setRect(0, 0, new_w, new_h)
        self._recompute_lines()
        self._update_handles()
        self.update()

    def _update_handles(self):
        """更新四角手柄的位置"""
        r = self.rect()
        d = CornerResizeHandle.RADIUS * 2
        offset = -CornerResizeHandle.RADIUS

        positions = {
            "tl": QPointF(offset, offset),
            "tr": QPointF(r.width() + offset - d, offset),
            "bl": QPointF(offset, r.height() + offset - d),
            "br": QPointF(r.width() + offset - d, r.height() + offset - d),
        }
        for corner, pos in positions.items():
            self._handles[corner].setPos(pos)

    # ==================== 绘制 ====================

    def boundingRect(self) -> QRectF:
        r = self.rect()
        return QRectF(r.x(), r.y() - 22, r.width(), r.height() + 22)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < 0.12:
            bg = QColor(28, 28, 32) if dark else QColor(252, 252, 255)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # LOD 文本隐藏优化
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        # 外部标签"源文本"
        if not _hide_text:
            label_font = QFont("Microsoft YaHei", 9)
            painter.setFont(label_font)
            painter.setPen(QColor(theme.text_tertiary()))
            painter.drawText(
                QRectF(4, -20, 200, 18),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                "源文本"
            )

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        bg_color = QColor(28, 28, 32, 240) if dark else QColor(252, 252, 255, 240)
        painter.fillPath(bg_path, QBrush(bg_color))

        # 边框
        if self._selected:
            border_pen = QPen(QColor(theme.accent()), 2.5)
        else:
            border_pen = QPen(QColor(theme.border()), 1)
        painter.setPen(border_pen)
        painter.drawPath(bg_path)

        if not _hide_text:
            # 标题栏
            title_rect = QRectF(0, 0, rect.width(), self.TITLE_HEIGHT)
            painter.setPen(QPen(QColor(theme.separator()), 0.5))
            painter.drawLine(
                QPointF(self.PADDING, self.TITLE_HEIGHT),
                QPointF(rect.width() - self.PADDING, self.TITLE_HEIGHT),
            )

            # 标题文本
            painter.setFont(self._title_font)
            painter.setPen(QColor(theme.text_primary()))
            char_count = len(self._full_text)
            total_lines = len(self._wrapped_lines)
            visible = self._visible_line_count()
            current_page = (self._scroll_offset // max(1, visible)) + 1 if total_lines > 0 else 0
            total_pages = max(1, (total_lines + visible - 1) // max(1, visible))

            title_str = f"{char_count}字"
            painter.drawText(
                QRectF(self.PADDING, 0, rect.width() * 0.6, self.TITLE_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                title_str,
            )

            # 页码
            page_str = f"{current_page}/{total_pages}"
            painter.setPen(QColor(theme.text_tertiary()))
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.drawText(
                QRectF(rect.width() * 0.5, 0, rect.width() * 0.5 - self.PADDING, self.TITLE_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                page_str,
            )

            # 文本区域
            painter.setFont(self._text_font)
            painter.setPen(QColor(theme.text_secondary()))
            text_x = self.PADDING
            text_y = self.TITLE_HEIGHT + self.PADDING
            total_lines = len(self._wrapped_lines)
            visible = self._visible_line_count()
            end_line = min(self._scroll_offset + visible, total_lines)

            for i in range(self._scroll_offset, end_line):
                line = self._wrapped_lines[i]
                painter.drawText(
                    QPointF(text_x, text_y + (i - self._scroll_offset) * self._line_height
                            + self._fm.ascent()),
                    line,
                )

        # 右侧迷你滚动条指示器
        total_lines = len(self._wrapped_lines)
        visible = self._visible_line_count()
        if total_lines > visible:
            sb_x = rect.width() - 6
            sb_top = self.TITLE_HEIGHT + 4
            sb_height = rect.height() - self.TITLE_HEIGHT - 8
            track_h = sb_height

            thumb_ratio = visible / total_lines
            thumb_h = max(20, track_h * thumb_ratio)
            thumb_top = sb_top + (self._scroll_offset / max(1, total_lines - visible)) * (track_h - thumb_h)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 30) if dark else QColor(0, 0, 0, 20))
            painter.drawRoundedRect(QRectF(sb_x, sb_top, 4, sb_height), 2, 2)

            painter.setBrush(QColor(255, 255, 255, 80) if dark else QColor(0, 0, 0, 60))
            painter.drawRoundedRect(QRectF(sb_x, thumb_top, 4, thumb_h), 2, 2)

    # ==================== hover ====================

    def hoverEnterEvent(self, event):
        for h in self._handles.values():
            h.setVisible(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # 如果有手柄正在拖拽，不隐藏
        if not any(h.is_dragging for h in self._handles.values()):
            for h in self._handles.values():
                h.setVisible(False)
        super().hoverLeaveEvent(event)
