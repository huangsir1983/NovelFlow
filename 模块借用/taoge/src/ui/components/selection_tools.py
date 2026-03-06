"""
涛割 - 选区工具（魔棒 + 套索）
用于智能画布中的像素级选区操作。
"""

import math
from typing import Optional, List
from collections import deque

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import (
    QImage, QPixmap, QColor, QPainter, QPen, QBrush,
    QPainterPath,
)
from PyQt6.QtWidgets import QGraphicsPathItem

from ui.components.layer_item import LayerItem


class MagicWandTool:
    """基于颜色容差的 flood fill 选区"""

    def __init__(self, tolerance: int = 32):
        self._tolerance = tolerance

    @property
    def tolerance(self) -> int:
        return self._tolerance

    @tolerance.setter
    def tolerance(self, value: int):
        self._tolerance = max(0, min(255, value))

    def select_at(self, layer_item: LayerItem, click_pos: QPointF) -> Optional[QImage]:
        """
        在 layer_item 的 click_pos（图层本地坐标）处执行 flood fill，
        返回二值蒙版 QImage（白色=选中，黑色=未选中）。
        """
        pixmap = layer_item.pixmap()
        if pixmap is None or pixmap.isNull():
            return None

        image = pixmap.toImage()
        w, h = image.width(), image.height()

        # 转换点击位置到像素坐标
        px = int(click_pos.x())
        py = int(click_pos.y())
        if px < 0 or px >= w or py < 0 or py >= h:
            return None

        # 目标颜色
        target = image.pixelColor(px, py)
        tr, tg, tb, ta = target.red(), target.green(), target.blue(), target.alpha()

        # 创建蒙版
        mask = QImage(w, h, QImage.Format.Format_Grayscale8)
        mask.fill(QColor(0, 0, 0))

        # BFS flood fill
        visited = set()
        queue = deque()
        queue.append((px, py))
        visited.add((px, py))

        tol = self._tolerance

        while queue:
            x, y = queue.popleft()

            color = image.pixelColor(x, y)
            dr = abs(color.red() - tr)
            dg = abs(color.green() - tg)
            db = abs(color.blue() - tb)
            da = abs(color.alpha() - ta)

            if dr <= tol and dg <= tol and db <= tol and da <= tol:
                mask.setPixelColor(x, y, QColor(255, 255, 255))

                # 四邻域
                for nx, ny in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        return mask

    def delete_selection(self, layer_item: LayerItem, mask: QImage):
        """将蒙版中白色区域对应的像素设为透明"""
        pixmap = layer_item.pixmap()
        if pixmap is None or pixmap.isNull():
            return

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w, h = image.width(), image.height()
        mw, mh = mask.width(), mask.height()

        for y in range(min(h, mh)):
            for x in range(min(w, mw)):
                if mask.pixelColor(x, y).red() > 128:
                    image.setPixelColor(x, y, QColor(0, 0, 0, 0))

        new_pixmap = QPixmap.fromImage(image)
        layer_item.update_pixmap(new_pixmap)


class LassoTool:
    """自由套索选区"""

    def __init__(self):
        self._points: List[QPointF] = []

    def reset(self):
        self._points.clear()

    def add_point(self, pos: QPointF):
        """鼠标移动时收集点"""
        self._points.append(pos)

    def close_path(self) -> Optional[QPainterPath]:
        """闭合路径"""
        if len(self._points) < 3:
            return None

        path = QPainterPath()
        path.moveTo(self._points[0])
        for pt in self._points[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        return path

    def make_mask(self, layer_item: LayerItem, path: QPainterPath) -> Optional[QImage]:
        """将 QPainterPath 转为二值蒙版"""
        pixmap = layer_item.pixmap()
        if pixmap is None or pixmap.isNull():
            return None

        w, h = pixmap.width(), pixmap.height()
        mask = QImage(w, h, QImage.Format.Format_Grayscale8)
        mask.fill(QColor(0, 0, 0))

        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        painter.end()

        return mask

    def delete_selection(self, layer_item: LayerItem, mask: QImage):
        """删除蒙版中白色区域的像素"""
        pixmap = layer_item.pixmap()
        if pixmap is None or pixmap.isNull():
            return

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w, h = image.width(), image.height()
        mw, mh = mask.width(), mask.height()

        for y in range(min(h, mh)):
            for x in range(min(w, mw)):
                if mask.pixelColor(x, y).red() > 128:
                    image.setPixelColor(x, y, QColor(0, 0, 0, 0))

        new_pixmap = QPixmap.fromImage(image)
        layer_item.update_pixmap(new_pixmap)


class SelectionOverlay(QGraphicsPathItem):
    """选区蚁行线（marching ants）可视化"""

    def __init__(self, path: QPainterPath, parent=None):
        super().__init__(path, parent)
        self._dash_offset = 0.0
        self.setZValue(999)

        # 蚁行线动画
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(100)

        self._update_pen()

    def _update_pen(self):
        pen = QPen(QColor(0, 0, 0), 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(self._dash_offset)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    def _animate(self):
        self._dash_offset += 1.0
        if self._dash_offset > 20:
            self._dash_offset = 0
        self._update_pen()

    def paint(self, painter: QPainter, option, widget=None):
        # 先画白色底线
        white_pen = QPen(QColor(255, 255, 255), 1.5)
        painter.setPen(white_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        # 再画黑色虚线（蚁行线效果）
        super().paint(painter, option, widget)

    def remove(self):
        """移除选区"""
        self._timer.stop()
        if self.scene():
            self.scene().removeItem(self)
