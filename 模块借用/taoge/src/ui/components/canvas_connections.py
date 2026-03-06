"""
涛割 - 曲线连线模块
在无限画布上用贝塞尔曲线连接两个卡片，支持虚线/实线+动画圆点两种模式。
"""

from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsItem,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainterPath, QPen, QBrush, QColor, QPainter, QRadialGradient,
)

# ---------------------------------------------------------------------------
# 配色常量
# ---------------------------------------------------------------------------
COLOR_DASHED = QColor(0, 122, 204, 80)
COLOR_SOLID = QColor(0, 180, 255, 180)
COLOR_DOT = QColor(0, 200, 255)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def compute_bezier_path(from_rect: QRectF, to_rect: QRectF) -> QPainterPath:
    """根据两个矩形的相对位置，计算连接两者的三次贝塞尔曲线路径。

    竖向布局（dy >= dx）：从 from_rect 底部中心 → to_rect 顶部中心
    横向布局（dx >  dy）：从 from_rect 右侧中心 → to_rect 左侧中心
    """
    from_center = from_rect.center()
    to_center = to_rect.center()
    dx = abs(to_center.x() - from_center.x())
    dy = abs(to_center.y() - from_center.y())

    if dx > dy:
        # 横向布局
        start = QPointF(from_rect.right(), from_rect.center().y())
        end = QPointF(to_rect.left(), to_rect.center().y())
        offset = abs(end.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + offset, start.y())
        ctrl2 = QPointF(end.x() - offset, end.y())
    else:
        # 竖向布局
        start = QPointF(from_rect.center().x(), from_rect.bottom())
        end = QPointF(to_rect.center().x(), to_rect.top())
        offset = abs(end.y() - start.y()) * 0.5
        ctrl1 = QPointF(start.x(), start.y() + offset)
        ctrl2 = QPointF(end.x(), end.y() - offset)

    path = QPainterPath(start)
    path.cubicTo(ctrl1, ctrl2, end)
    return path


# ---------------------------------------------------------------------------
# AnimatedDot — 沿曲线循环移动的发光圆点
# ---------------------------------------------------------------------------

class AnimatedDot:
    """沿 QPainterPath 循环移动的发光圆点。"""

    RADIUS = 4.0
    INTERVAL_MS = 30
    STEP = 0.008  # 每 tick 前进量（0→1 大约 125 tick ≈ 3.75 s）

    def __init__(self, scene: QGraphicsScene, path: QPainterPath):
        self._scene = scene
        self._path = path
        self._t = 0.0

        # 圆点图形
        self._dot = QGraphicsEllipseItem(
            -self.RADIUS, -self.RADIUS,
            self.RADIUS * 2, self.RADIUS * 2,
        )
        self._dot.setZValue(1000)

        # 辉光渐变画刷
        gradient = QRadialGradient(0, 0, self.RADIUS * 2)
        gradient.setColorAt(0.0, QColor(COLOR_DOT.red(), COLOR_DOT.green(), COLOR_DOT.blue(), 220))
        gradient.setColorAt(0.5, QColor(COLOR_DOT.red(), COLOR_DOT.green(), COLOR_DOT.blue(), 100))
        gradient.setColorAt(1.0, QColor(COLOR_DOT.red(), COLOR_DOT.green(), COLOR_DOT.blue(), 0))
        self._dot.setBrush(QBrush(gradient))
        self._dot.setPen(QPen(Qt.PenStyle.NoPen))

        self._scene.addItem(self._dot)

        # 定时器
        self._timer = QTimer()
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    # -- 公开 API --

    def start(self):
        self._t = 0.0
        if self._dot_alive():
            self._update_pos()
            self._dot.setVisible(True)
            self._timer.start()

    def _dot_alive(self) -> bool:
        """检查 C++ 对象是否仍有效"""
        try:
            # 访问任一属性触发 RuntimeError 如果已被销毁
            self._dot.isVisible()
            return True
        except (RuntimeError, AttributeError):
            return False

    def stop(self):
        self._timer.stop()
        if self._dot_alive():
            self._dot.setVisible(False)

    def set_path(self, path: QPainterPath):
        self._path = path
        if self._dot_alive():
            self._update_pos()

    def remove(self):
        self.stop()
        if self._dot_alive() and self._dot.scene():
            self._scene.removeItem(self._dot)

    # -- 内部 --

    def _tick(self):
        if not self._dot_alive():
            self._timer.stop()
            return
        self._t += self.STEP
        if self._t > 1.0:
            self._t = 0.0
        self._update_pos()

    def _update_pos(self):
        # ease-in-out (smoothstep)
        t = self._t
        t_ease = t * t * (3.0 - 2.0 * t)
        pt = self._path.pointAtPercent(t_ease)
        try:
            self._dot.setPos(pt)
        except RuntimeError:
            self._timer.stop()


# ---------------------------------------------------------------------------
# CurvedConnectionLine — 连接两个卡片的贝塞尔曲线
# ---------------------------------------------------------------------------

class CurvedConnectionLine:
    """用贝塞尔曲线连接两个 QGraphicsItem，支持虚线/实线+动画。"""

    def __init__(
        self,
        scene: QGraphicsScene,
        from_item: QGraphicsItem,
        to_item: QGraphicsItem,
        is_linked: bool = False,
    ):
        self._scene = scene
        self._from_item = from_item
        self._to_item = to_item
        self._is_linked = is_linked

        # 曲线图形
        self._path_item = QGraphicsPathItem()
        self._path_item.setZValue(500)
        self._scene.addItem(self._path_item)

        # 动画圆点（延迟创建，先用 None 占位）
        self._animated_dot: AnimatedDot | None = None

        # 初始化
        self._apply_style()
        self.update_position()

        if self._is_linked:
            self.start_animation()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def update_position(self):
        """重新计算曲线路径（当卡片移动后调用）。"""
        try:
            from_rect = self._from_item.sceneBoundingRect()
            to_rect = self._to_item.sceneBoundingRect()
        except RuntimeError:
            return
        path = compute_bezier_path(from_rect, to_rect)
        try:
            self._path_item.setPath(path)
        except RuntimeError:
            return
        if self._animated_dot is not None:
            self._animated_dot.set_path(path)

    def set_linked(self, linked: bool):
        """切换 linked 状态：实线+动画 ↔ 虚线。"""
        if linked == self._is_linked:
            return
        self._is_linked = linked
        self._apply_style()
        if linked:
            self.start_animation()
        else:
            self.stop_animation()

    def start_animation(self):
        """启动动画圆点。"""
        if self._animated_dot is None:
            path = self._path_item.path()
            self._animated_dot = AnimatedDot(self._scene, path)
        self._animated_dot.start()

    def stop_animation(self):
        """停止并隐藏动画圆点。"""
        if self._animated_dot is not None:
            self._animated_dot.stop()

    def remove(self, scene: QGraphicsScene | None = None):
        """从场景中移除所有图形项。"""
        target = scene or self._scene
        if self._animated_dot is not None:
            self._animated_dot.remove()
            self._animated_dot = None
        try:
            if self._path_item.scene():
                target.removeItem(self._path_item)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _apply_style(self):
        if self._is_linked:
            pen = QPen(COLOR_SOLID, 2.5)
            pen.setStyle(Qt.PenStyle.SolidLine)
        else:
            pen = QPen(COLOR_DASHED, 1.5)
            pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._path_item.setPen(pen)
