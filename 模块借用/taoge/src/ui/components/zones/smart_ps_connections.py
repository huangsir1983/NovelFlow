"""
涛割 - 智能PS连线管理器
管理 AgentNode 内所有贝塞尔曲线连线：
  - 输入槽 → 预处理节点
  - 预处理节点间的链式连线
  - 预处理输出 → 图层
  - 快照 → 后处理节点
"""

from typing import Optional, List, Dict, Tuple

from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsScene
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainterPath, QPen, QBrush, QColor

from ui.components.canvas_connections import compute_bezier_path, AnimatedDot


# ============================================================
#  常量
# ============================================================

COLOR_CONNECTED = QColor(91, 127, 255, 180)
COLOR_CONFIRMED = QColor(50, 180, 100, 180)
COLOR_PENDING = QColor(120, 120, 140, 100)
COLOR_DRAGGING = QColor(91, 127, 255, 120)


# ============================================================
#  PSConnection — 单条连线
# ============================================================

class PSConnection:
    """AgentNode 内部一条贝塞尔连线"""

    def __init__(self, scene: QGraphicsScene,
                 start_pos: QPointF, end_pos: QPointF,
                 is_confirmed: bool = False,
                 z_value: float = 600):
        self._scene = scene
        self._start = start_pos
        self._end = end_pos
        self._is_confirmed = is_confirmed

        # 动画圆点
        self._dot: Optional[AnimatedDot] = None

        # 曲线路径
        self._path_item = QGraphicsPathItem()
        self._path_item.setZValue(z_value)
        self._apply_style()
        self._update_path()
        self._scene.addItem(self._path_item)

        if is_confirmed:
            self._start_animation()

    def set_confirmed(self, confirmed: bool):
        if confirmed == self._is_confirmed:
            return
        self._is_confirmed = confirmed
        self._apply_style()
        if confirmed:
            self._start_animation()
        else:
            self._stop_animation()

    def update_positions(self, start: QPointF, end: QPointF):
        self._start = start
        self._end = end
        self._update_path()

    def remove(self):
        self._stop_animation()
        if self._path_item.scene():
            self._scene.removeItem(self._path_item)

    def _apply_style(self):
        if self._is_confirmed:
            pen = QPen(COLOR_CONFIRMED, 2)
            pen.setStyle(Qt.PenStyle.SolidLine)
        else:
            pen = QPen(COLOR_PENDING, 1.5)
            pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._path_item.setPen(pen)

    def _update_path(self):
        path = self._compute_path()
        self._path_item.setPath(path)
        if self._dot:
            self._dot.set_path(path)

    def _compute_path(self) -> QPainterPath:
        """计算水平贝塞尔曲线（从左到右）"""
        dx = abs(self._end.x() - self._start.x())
        offset = max(dx * 0.4, 30)

        ctrl1 = QPointF(self._start.x() + offset, self._start.y())
        ctrl2 = QPointF(self._end.x() - offset, self._end.y())

        path = QPainterPath(self._start)
        path.cubicTo(ctrl1, ctrl2, self._end)
        return path

    def _start_animation(self):
        if self._dot is None:
            self._dot = AnimatedDot(self._scene, self._path_item.path())
        self._dot.start()

    def _stop_animation(self):
        if self._dot:
            self._dot.remove()
            self._dot = None


# ============================================================
#  DragConnectionLine — 拖拽时的临时连线
# ============================================================

class DragConnectionLine:
    """拖拽锚点时的临时贝塞尔虚线"""

    def __init__(self, scene: QGraphicsScene, start_pos: QPointF):
        self._scene = scene
        self._start = start_pos

        self._path_item = QGraphicsPathItem()
        self._path_item.setZValue(1000)
        pen = QPen(COLOR_DRAGGING, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._path_item.setPen(pen)
        self._scene.addItem(self._path_item)

    def update_end(self, end_pos: QPointF):
        dx = abs(end_pos.x() - self._start.x())
        offset = max(dx * 0.4, 20)

        ctrl1 = QPointF(self._start.x() + offset, self._start.y())
        ctrl2 = QPointF(end_pos.x() - offset, end_pos.y())

        path = QPainterPath(self._start)
        path.cubicTo(ctrl1, ctrl2, end_pos)
        self._path_item.setPath(path)

    def remove(self):
        if self._path_item.scene():
            self._scene.removeItem(self._path_item)


# ============================================================
#  PSNodeConnectionManager — 连线管理器
# ============================================================

class PSNodeConnectionManager:
    """
    管理 SmartPSAgentNode 内所有连线。
    - 输入槽 → 管线节点
    - 管线节点间串联
    - 管线输出 → 图层
    - 快照 → 后处理
    """

    def __init__(self, scene: QGraphicsScene):
        self._scene = scene
        self._connections: Dict[str, PSConnection] = {}  # id → PSConnection
        self._drag_line: Optional[DragConnectionLine] = None
        self._next_id = 0

    def add_connection(self, start_pos: QPointF, end_pos: QPointF,
                       is_confirmed: bool = False,
                       connection_id: str = None) -> str:
        """添加一条连线，返回 connection_id"""
        cid = connection_id or f"conn_{self._next_id}"
        self._next_id += 1

        conn = PSConnection(self._scene, start_pos, end_pos, is_confirmed)
        self._connections[cid] = conn
        return cid

    def update_connection(self, connection_id: str,
                          start: QPointF = None, end: QPointF = None,
                          confirmed: bool = None):
        """更新连线位置或状态"""
        conn = self._connections.get(connection_id)
        if not conn:
            return
        if start is not None and end is not None:
            conn.update_positions(start, end)
        if confirmed is not None:
            conn.set_confirmed(confirmed)

    def remove_connection(self, connection_id: str):
        conn = self._connections.pop(connection_id, None)
        if conn:
            conn.remove()

    def clear_all(self):
        for conn in self._connections.values():
            conn.remove()
        self._connections.clear()
        self.cancel_drag()

    def start_drag(self, start_pos: QPointF):
        """开始拖拽连线"""
        self.cancel_drag()
        self._drag_line = DragConnectionLine(self._scene, start_pos)

    def update_drag(self, end_pos: QPointF):
        """更新拖拽连线终点"""
        if self._drag_line:
            self._drag_line.update_end(end_pos)

    def cancel_drag(self):
        """取消拖拽连线"""
        if self._drag_line:
            self._drag_line.remove()
            self._drag_line = None

    def finish_drag(self, end_pos: QPointF) -> str:
        """完成拖拽，转为正式连线"""
        if not self._drag_line:
            return ""
        start = self._drag_line._start
        self._drag_line.remove()
        self._drag_line = None
        return self.add_connection(start, end_pos)

    def update_all_positions(self):
        """全部连线更新位置（节点移动后调用）"""
        # 由外部提供新坐标时手动调用 update_connection
        pass

    def get_connection_ids(self) -> List[str]:
        return list(self._connections.keys())
