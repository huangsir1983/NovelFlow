"""
涛割 - 思维导图分支节点

场景卡到分镜卡之间的可交互分支节点。
分镜卡横向排列在上方，场景卡在下方居中，分支节点在中间。

结构：
    分镜卡1   分镜卡2   分镜卡3    ← 横向排列
        |         |         |
        +─────────+─────────+        ← 扇形曲线（底部→节点）
                 |
            [分支节点]              ← MindMapBranchNode
                 |
                 |                  ← 主干曲线
                 |
            [场景卡片]              ← 场景卡（在 Zone 1 中，通过坐标投影连线）
"""

from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsItem,
    QGraphicsScene, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPainterPath, QFont,
    QFontMetrics, QCursor, QRadialGradient,
)

from ui import theme


# ============================================================
#  MindMapBranchNode — 分支节点
# ============================================================

class MindMapBranchNode(QGraphicsEllipseItem):
    """
    场景卡到分镜卡之间的可交互分支节点。

    - 左键点击：折叠/展开该场景的分镜卡组
    - 右键点击：弹出菜单"只显示这个场景组"
    """

    NODE_RADIUS = 12

    def __init__(self, act_id: int, color: QColor, parent=None):
        super().__init__(
            -self.NODE_RADIUS, -self.NODE_RADIUS,
            self.NODE_RADIUS * 2, self.NODE_RADIUS * 2,
            parent
        )
        self._act_id = act_id
        self._collapsed = False
        self._color = color
        self._hovered = False

        # 信号通过回调传递（QGraphicsItem 不能直接使用 pyqtSignal）
        self._on_toggle_callback = None
        self._on_solo_callback = None

        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setZValue(100)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    @property
    def act_id(self) -> int:
        return self._act_id

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def set_on_toggle(self, callback):
        """设置折叠/展开回调 callback(act_id, collapsed)"""
        self._on_toggle_callback = callback

    def set_on_solo(self, callback):
        """设置只显示回调 callback(act_id)"""
        self._on_solo_callback = callback

    def paint(self, painter: QPainter, option, widget=None):
        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < 0.12:
            painter.setPen(Qt.PenStyle.NoPen)
            fill = QColor(self._color.red(), self._color.green(),
                          self._color.blue(), 160)
            painter.setBrush(QBrush(fill))
            painter.drawEllipse(self.rect())
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 节点填充
        if self._hovered:
            fill = QColor(self._color.red(), self._color.green(),
                          self._color.blue(), 220)
        else:
            fill = QColor(self._color.red(), self._color.green(),
                          self._color.blue(), 160)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(self.rect())

        # 外环
        ring_color = QColor(self._color.red(), self._color.green(),
                            self._color.blue(), 80)
        ring_pen = QPen(ring_color, 2)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        outer = self.rect().adjusted(-3, -3, 3, 3)
        painter.drawEllipse(outer)

        # 绘制折叠/展开图标
        cx, cy = 0, 0
        icon_pen = QPen(QColor(255, 255, 255, 220), 2)
        icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(icon_pen)

        if self._collapsed:
            # 绘制 "+" 表示已折叠（可展开）
            painter.drawLine(QPointF(cx - 4, cy), QPointF(cx + 4, cy))
            painter.drawLine(QPointF(cx, cy - 4), QPointF(cx, cy + 4))
        else:
            # 绘制 "−" 表示已展开（可折叠）
            painter.drawLine(QPointF(cx - 4, cy), QPointF(cx + 4, cy))

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._collapsed = not self._collapsed
            self.update()
            if self._on_toggle_callback:
                self._on_toggle_callback(self._act_id, self._collapsed)
            event.accept()
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        if self._collapsed:
            menu.addAction("展开分镜卡",
                           lambda: self._toggle_from_menu(False))
        else:
            menu.addAction("折叠分镜卡",
                           lambda: self._toggle_from_menu(True))
        menu.addSeparator()
        menu.addAction("只显示这个场景组",
                       lambda: self._solo())
        menu.exec(event.screenPos())
        event.accept()

    def _toggle_from_menu(self, collapsed: bool):
        self._collapsed = collapsed
        self.update()
        if self._on_toggle_callback:
            self._on_toggle_callback(self._act_id, self._collapsed)

    def _solo(self):
        if self._on_solo_callback:
            self._on_solo_callback(self._act_id)


# ============================================================
#  SceneConnectionManager — 持久连线管理器
# ============================================================

class SceneConnectionManager:
    """
    管理所有场景卡到分镜卡的持久连线（替代 CrossZoneConnectionManager）。

    连线结构（思维导图分支样式，从上到下）：
    - 各分镜卡底部中点 → 分支节点顶部（扇形曲线）
    - 分支节点底部 → 场景卡顶部中点（主干曲线）

    分镜卡横向排列，场景卡在分镜卡下方居中。
    场景卡位于 Zone 1，分镜卡位于 Zone 2，需要跨 Zone 坐标投影。
    所有连线始终显示，不依赖点击。
    """

    BRANCH_NODE_GAP = 30    # 分支节点距场景卡投影顶部的间距（短线）
    TRUNK_LINE_GAP = 20     # 保留

    def __init__(self, scene: QGraphicsScene):
        self._scene = scene

        # act_id → 数据
        self._branch_nodes: Dict[int, MindMapBranchNode] = {}
        self._trunk_lines: Dict[int, QGraphicsPathItem] = {}  # 节点→场景卡
        self._fan_lines: Dict[int, List[QGraphicsPathItem]] = {}  # 分镜卡→节点
        self._shot_cards_map: Dict[int, list] = {}  # act_id → shot_cards
        self._summary_cards: Dict[int, Optional[QGraphicsItem]] = {}  # act_id → summary card
        self._collapsed_cards: Dict[int, Optional[QGraphicsItem]] = {}  # act_id → collapsed card
        self._parent_item = None  # Zone 2 ZoneFrame（连线和节点的父项）

        # 动画圆点
        self._animated_dots: List[_FlowDot] = []
        # act_id → 对应的动画圆点映射（用于 update_all 同步路径）
        self._trunk_dots: Dict[int, _FlowDot] = {}  # act_id → trunk dot
        self._fan_dots: Dict[int, List[_FlowDot]] = {}  # act_id → fan dots

        # 动画开关状态
        self._animations_enabled = True

        # 折叠/solo 回调
        self._on_toggle_callback = None
        self._on_solo_callback = None

    def set_on_toggle(self, callback):
        """设置折叠回调 callback(act_id, collapsed)"""
        self._on_toggle_callback = callback

    def set_on_solo(self, callback):
        """设置solo回调 callback(act_id)"""
        self._on_solo_callback = callback

    def get_collapsed_states(self) -> Dict[int, bool]:
        """获取所有分支节点的折叠状态"""
        return {act_id: node.collapsed
                for act_id, node in self._branch_nodes.items()}

    def restore_collapsed_states(self, states: Dict[int, bool]):
        """恢复折叠状态（重建后调用）"""
        for act_id, collapsed in states.items():
            node = self._branch_nodes.get(act_id)
            if node:
                node._collapsed = collapsed
                node.update()
            # 同步可见性
            if collapsed:
                for card in self._shot_cards_map.get(act_id, []):
                    card.setVisible(False)
                for line in self._fan_lines.get(act_id, []):
                    line.setVisible(False)

    def rebuild_all_connections(self, act_groups: Dict[int, dict],
                                 parent_item=None,
                                 collapsed_cards: Dict[int, any] = None) -> Dict[int, float]:
        """
        重建所有连线。

        act_groups: {act_id: {
            'summary': ActSummaryCard (Zone 1 子项),
            'shot_cards': [ShotCanvasCard, ...] (Zone 2 子项),
            'color': QColor,
        }}
        parent_item: 父项（Zone 2 的 ZoneFrame），连线和节点作为其子项

        Returns:
            {act_id: shots_center_x_in_zone2} — 每组分镜的中心 X（Zone 2 坐标）
        """
        self.clear_all()
        self._parent_item = parent_item
        self._collapsed_cards = collapsed_cards or {}
        center_x_map: Dict[int, float] = {}

        for act_id, data in act_groups.items():
            summary = data.get('summary')
            shot_cards = data.get('shot_cards', [])
            color = data.get('color', QColor(100, 100, 100))

            if not shot_cards:
                continue

            # 始终注册到 map 以便 toggle/solo 管理
            self._shot_cards_map[act_id] = shot_cards
            self._summary_cards[act_id] = summary  # 保存引用供 update_all 使用

            visible_cards = [c for c in shot_cards if c.isVisible()]
            is_collapsed = len(visible_cards) == 0
            collapsed_card = self._collapsed_cards.get(act_id)

            # 没有 summary 时不生成分支节点和连线（但卡片已注册到 map）
            if not summary:
                if visible_cards:
                    shots_left = min(c.pos().x() for c in visible_cards)
                    shots_right = max(c.pos().x() + c.rect().width()
                                      for c in visible_cards)
                    center_x_map[act_id] = (shots_left + shots_right) / 2.0
                elif collapsed_card and collapsed_card.isVisible():
                    # 折叠组：使用折叠卡片的中心 X
                    cc_left = collapsed_card.pos().x()
                    cc_right = cc_left + collapsed_card.rect().width()
                    center_x_map[act_id] = (cc_left + cc_right) / 2.0
                continue

            # === 将场景卡（Zone 1 子项）的位置转换到 Zone 2 坐标系 ===
            summary_scene_rect = summary.mapRectToScene(
                summary.boundingRect()
            )
            summary_in_zone2 = parent_item.mapRectFromScene(
                summary_scene_rect
            )

            # === 计算分镜卡组的范围 ===
            if visible_cards:
                shots_left = min(c.pos().x() for c in visible_cards)
                shots_right = max(c.pos().x() + c.rect().width()
                                  for c in visible_cards)
                shots_center_x = (shots_left + shots_right) / 2.0
            elif collapsed_card and collapsed_card.isVisible():
                # 折叠组：使用折叠卡片中心
                cc_left = collapsed_card.pos().x()
                cc_right = cc_left + collapsed_card.rect().width()
                shots_center_x = (cc_left + cc_right) / 2.0
            else:
                shots_left = min(c.pos().x() for c in shot_cards)
                shots_right = max(c.pos().x() + c.rect().width()
                                  for c in shot_cards)
                shots_center_x = (shots_left + shots_right) / 2.0
            center_x_map[act_id] = shots_center_x

            # === 分支节点 X 跟随场景卡投影中心（而非分镜组中心） ===
            summary_center_x = summary_in_zone2.center().x()

            summary_top_center = QPointF(
                summary_center_x,
                summary_in_zone2.top()
            )

            # === 分支节点位置：X 与场景卡对齐，Y 在场景卡投影上方 ===
            node_x = summary_center_x
            node_y = summary_top_center.y() - self.BRANCH_NODE_GAP

            # 创建分支节点（折叠时也创建，以便用户点击展开）
            node = MindMapBranchNode(act_id, color, parent=parent_item)
            node.setPos(node_x, node_y)
            node._collapsed = is_collapsed
            node.set_on_toggle(self._on_branch_toggled)
            node.set_on_solo(self._on_branch_solo)
            self._branch_nodes[act_id] = node

            # === 主干线（分支节点底部 → 场景卡投影顶部）始终创建 ===
            node_bottom = QPointF(
                node_x, node_y + MindMapBranchNode.NODE_RADIUS
            )
            trunk = self._create_trunk_line(
                node_bottom, summary_top_center, color, parent_item
            )
            self._trunk_lines[act_id] = trunk

            # 折叠组：从折叠卡底部中点到分支节点顶部创建一根连线
            if is_collapsed:
                node_top = QPointF(node_x, node_y - MindMapBranchNode.NODE_RADIUS)
                if collapsed_card and collapsed_card.isVisible():
                    cc_rect = collapsed_card.mapRectToParent(
                        collapsed_card.boundingRect())
                    cc_bottom_center = QPointF(
                        cc_rect.center().x(), cc_rect.bottom())
                    fan = self._create_fan_line(
                        cc_bottom_center, node_top, color, parent_item)
                    self._fan_lines[act_id] = [fan]
                else:
                    self._fan_lines[act_id] = []
                continue

            # === 扇形线（长线）：各分镜卡底部中点 → 分支节点顶部 ===
            fan_lines = []
            node_top = QPointF(node_x, node_y - MindMapBranchNode.NODE_RADIUS)
            for card in visible_cards:
                card_rect = card.mapRectToParent(card.boundingRect())
                card_bottom_center = QPointF(
                    card_rect.center().x(), card_rect.bottom()
                )
                fan = self._create_fan_line(
                    card_bottom_center, node_top, color, parent_item
                )
                fan_lines.append(fan)
            self._fan_lines[act_id] = fan_lines

            # === 流动粒子动画（从下往上：场景卡→分支点→分镜卡） ===
            dot_color = QColor(color.red(), color.green(), color.blue(), 200)
            # 主干线动画（从下往上）
            trunk_dot = _FlowDot(trunk.path(), dot_color, parent_item, reverse=True)
            if self._animations_enabled:
                trunk_dot.start()
            self._animated_dots.append(trunk_dot)
            self._trunk_dots[act_id] = trunk_dot
            # 每条扇形线动画（从下往上，错开起始相位）
            act_fan_dots = []
            for idx, fan in enumerate(fan_lines):
                offset = (idx * 0.2) % 1.0
                fan_dot = _FlowDot(fan.path(), dot_color, parent_item,
                                   phase_offset=offset, reverse=True)
                if self._animations_enabled:
                    fan_dot.start()
                self._animated_dots.append(fan_dot)
                act_fan_dots.append(fan_dot)
            self._fan_dots[act_id] = act_fan_dots

        return center_x_map

    def update_all(self):
        """Zone 移动或卡片位置变化时，更新节点位置和主干线端点。

        主干线连接 分支节点底部 → 场景卡投影顶部中点。
        节点和连线都是 parent_item (Zone 2) 的子项。
        当 Zone 1 移动或 summary card 位置变化时，需要重新计算。
        同时更新节点的 X 和 Y 坐标以及所有连线端点。
        """
        if not self._parent_item:
            return

        for act_id, trunk_line in self._trunk_lines.items():
            node = self._branch_nodes.get(act_id)
            summary = self._summary_cards.get(act_id)
            if not node or not summary:
                continue
            if not summary.scene():
                continue

            # 将 summary（Zone 1 子项）当前位置转换到 Zone 2 坐标系
            summary_scene_rect = summary.mapRectToScene(summary.boundingRect())
            summary_in_zone2 = self._parent_item.mapRectFromScene(
                summary_scene_rect
            )

            # 节点 X 跟随场景卡投影中心（而非分镜卡组中心）
            target_x = summary_in_zone2.center().x()

            # 获取分镜卡可见状态（供扇形线更新使用）
            shot_cards = self._shot_cards_map.get(act_id, [])
            visible_cards = [c for c in shot_cards if c.isVisible()]
            collapsed_card = self._collapsed_cards.get(act_id)

            # 计算节点目标位置
            target_y = summary_in_zone2.top() - self.BRANCH_NODE_GAP

            # 更新节点位置（X 和 Y 都跟随）
            node.setPos(target_x, target_y)

            # 重建主干线路径：节点底部 → 场景卡投影顶部中点
            node_bottom = QPointF(
                target_x, target_y + MindMapBranchNode.NODE_RADIUS
            )
            summary_top_center = QPointF(
                target_x, summary_in_zone2.top()
            )

            trunk_path = QPainterPath(node_bottom)
            dy = abs(summary_top_center.y() - node_bottom.y())
            offset = dy * 0.3
            ctrl1 = QPointF(node_bottom.x(), node_bottom.y() + offset)
            ctrl2 = QPointF(summary_top_center.x(),
                            summary_top_center.y() - offset)
            trunk_path.cubicTo(ctrl1, ctrl2, summary_top_center)
            trunk_line.setPath(trunk_path)

            # 更新扇形线端点（终点 = 节点顶部）
            node_top = QPointF(
                target_x, target_y - MindMapBranchNode.NODE_RADIUS
            )
            fan_dots = self._fan_dots.get(act_id, [])
            fan_lines = self._fan_lines.get(act_id, [])

            # 折叠时：扇形线起点跟随折叠卡底部中点
            is_collapsed = not visible_cards and collapsed_card
            if is_collapsed and collapsed_card.isVisible() and fan_lines:
                cc_rect = collapsed_card.mapRectToParent(
                    collapsed_card.boundingRect())
                cc_bottom_center = QPointF(
                    cc_rect.center().x(), cc_rect.bottom())
                fan_path = QPainterPath(cc_bottom_center)
                fan_dy = abs(node_top.y() - cc_bottom_center.y())
                fan_offset = fan_dy * 0.4
                fc1 = QPointF(cc_bottom_center.x(),
                              cc_bottom_center.y() + fan_offset)
                fc2 = QPointF(node_top.x(), node_top.y() - fan_offset)
                fan_path.cubicTo(fc1, fc2, node_top)
                fan_lines[0].setPath(fan_path)
                if fan_dots:
                    fan_dots[0].set_path(fan_path)
            else:
                for fi, fan_line in enumerate(fan_lines):
                    old_path = fan_line.path()
                    if old_path.elementCount() < 1:
                        continue
                    start_el = old_path.elementAt(0)
                    fan_start = QPointF(start_el.x, start_el.y)
                    fan_path = QPainterPath(fan_start)
                    fan_dy = abs(node_top.y() - fan_start.y())
                    fan_offset = fan_dy * 0.4
                    fc1 = QPointF(fan_start.x(), fan_start.y() + fan_offset)
                    fc2 = QPointF(node_top.x(), node_top.y() - fan_offset)
                    fan_path.cubicTo(fc1, fc2, node_top)
                    fan_line.setPath(fan_path)
                    # 同步 FlowDot 路径
                    if fi < len(fan_dots):
                        fan_dots[fi].set_path(fan_path)

            # 同步主干线 FlowDot 路径
            trunk_dot = self._trunk_dots.get(act_id)
            if trunk_dot:
                trunk_dot.set_path(trunk_line.path())

    def toggle_group(self, act_id: int, collapsed: bool):
        """折叠/展开某个场景组的分镜卡和连线"""
        shot_cards = self._shot_cards_map.get(act_id, [])
        fan_lines = self._fan_lines.get(act_id, [])
        node = self._branch_nodes.get(act_id)

        for card in shot_cards:
            card.setVisible(not collapsed)
        for line in fan_lines:
            line.setVisible(not collapsed)
        if node:
            node._collapsed = collapsed
            node.update()

    def solo_group(self, act_id: int):
        """只显示指定场景组，隐藏其他组"""
        # 遍历所有注册的场景组（包含没有分支节点的场景）
        for other_id in self._shot_cards_map:
            is_solo = (other_id == act_id)
            shot_cards = self._shot_cards_map.get(other_id, [])
            fan_lines = self._fan_lines.get(other_id, [])
            node = self._branch_nodes.get(other_id)

            for card in shot_cards:
                card.setVisible(is_solo)
            for line in fan_lines:
                line.setVisible(is_solo)
            if node:
                node._collapsed = not is_solo
                node.update()

    def clear_all(self):
        """清除所有连线、节点和动画"""
        # 停止并清除所有动画圆点
        for dot in self._animated_dots:
            dot.stop()
            dot.remove()
        self._animated_dots.clear()
        self._trunk_dots.clear()
        self._fan_dots.clear()

        for node in self._branch_nodes.values():
            if node.scene():
                self._scene.removeItem(node)
        self._branch_nodes.clear()

        for line in self._trunk_lines.values():
            if line.scene():
                self._scene.removeItem(line)
        self._trunk_lines.clear()

        for lines in self._fan_lines.values():
            for line in lines:
                if line.scene():
                    self._scene.removeItem(line)
        self._fan_lines.clear()

        self._shot_cards_map.clear()
        self._summary_cards.clear()
        # 不要 .clear()，因为 _collapsed_cards 可能是外部传入的共享引用
        # （shot_delegate._collapsed_cards），清空会破坏外部数据
        self._collapsed_cards = {}
        self._parent_item = None

    def set_animations_enabled(self, enabled: bool):
        """开启/关闭所有流动光点动画"""
        self._animations_enabled = enabled
        for dot in self._animated_dots:
            if enabled:
                dot.start()
            else:
                dot.stop()

    def _create_trunk_line(self, start: QPointF, end: QPointF,
                            color: QColor,
                            parent=None) -> QGraphicsPathItem:
        """创建主干线（分支节点底部 → 场景卡顶部，垂直直线因 X 已对齐）"""
        path = QPainterPath(start)
        # X 已对齐，使用轻微弯曲的贝塞尔以保持视觉柔和
        offset = abs(end.y() - start.y()) * 0.3
        ctrl1 = QPointF(start.x(), start.y() + offset)
        ctrl2 = QPointF(end.x(), end.y() - offset)
        path.cubicTo(ctrl1, ctrl2, end)

        line = QGraphicsPathItem(parent)
        pen_color = QColor(color.red(), color.green(), color.blue(), 150)
        pen = QPen(pen_color, 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.setPath(path)
        line.setZValue(50)
        return line

    def _create_fan_line(self, start: QPointF, end: QPointF,
                          color: QColor,
                          parent=None) -> QGraphicsPathItem:
        """创建扇形贝塞尔曲线（分镜卡底部 → 分支节点顶部，从上到下）"""
        path = QPainterPath(start)
        offset = abs(end.y() - start.y()) * 0.4
        ctrl1 = QPointF(start.x(), start.y() + offset)  # 向下弯
        ctrl2 = QPointF(end.x(), end.y() - offset)        # 向上弯到终点
        path.cubicTo(ctrl1, ctrl2, end)

        line = QGraphicsPathItem(parent)
        pen_color = QColor(color.red(), color.green(), color.blue(), 100)
        pen = QPen(pen_color, 1.5)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.setPath(path)
        line.setZValue(50)
        return line

    def _on_branch_toggled(self, act_id: int, collapsed: bool):
        """分支节点折叠/展开回调"""
        self.toggle_group(act_id, collapsed)
        if self._on_toggle_callback:
            self._on_toggle_callback(act_id, collapsed)

    def _on_branch_solo(self, act_id: int):
        """分支节点solo回调"""
        self.solo_group(act_id)
        if self._on_solo_callback:
            self._on_solo_callback(act_id)


# ============================================================
#  _FlowDot — 沿贝塞尔曲线循环移动的发光圆点（轻量版）
# ============================================================

class _FlowDot:
    """沿 QPainterPath 循环流动的发光圆点，作为 parent_item 的子项。"""

    RADIUS = 3.0
    INTERVAL_MS = 35
    STEP = 0.01

    def __init__(self, path: QPainterPath, color: QColor,
                 parent_item=None, phase_offset: float = 0.0,
                 reverse: bool = False):
        self._path = path
        self._t = phase_offset
        self._parent = parent_item
        self._reverse = reverse

        # 圆点图形
        self._dot = QGraphicsEllipseItem(
            -self.RADIUS, -self.RADIUS,
            self.RADIUS * 2, self.RADIUS * 2,
            parent_item
        )
        self._dot.setZValue(200)

        # 辉光渐变画刷
        gradient = QRadialGradient(0, 0, self.RADIUS * 2)
        gradient.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 220))
        gradient.setColorAt(0.5, QColor(color.red(), color.green(), color.blue(), 100))
        gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
        self._dot.setBrush(QBrush(gradient))
        self._dot.setPen(QPen(Qt.PenStyle.NoPen))
        self._dot.setVisible(False)

        # 定时器
        self._timer = QTimer()
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._update_pos()
        self._dot.setVisible(True)
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._dot.setVisible(False)

    def set_path(self, path: QPainterPath):
        """更新流动路径（Zone 移动或连线重建后同步调用）"""
        self._path = path

    def remove(self):
        self.stop()
        if self._dot.scene():
            self._dot.scene().removeItem(self._dot)

    def _tick(self):
        self._t += self.STEP
        if self._t > 1.0:
            self._t -= 1.0
        self._update_pos()

    def _update_pos(self):
        t = self._t
        if self._reverse:
            t = 1.0 - t
        # smoothstep ease
        t_ease = t * t * (3.0 - 2.0 * t)
        pt = self._path.pointAtPercent(t_ease)
        self._dot.setPos(pt)
