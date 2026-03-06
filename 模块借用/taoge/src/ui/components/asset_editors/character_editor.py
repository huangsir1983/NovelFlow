"""
涛割 - 角色资产编辑器
全屏页面：上半画布（基础形象→衍生形象思维导图 + 多角度卡片）+ 下半信息栏。
"""

import os
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QComboBox, QTextEdit,
    QGraphicsScene, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsEllipseItem, QGraphicsItem, QSizePolicy,
    QStackedWidget, QFileDialog, QFormLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainterPath, QPen, QBrush, QColor, QPainter, QFont,
    QPixmap, QRadialGradient, QLinearGradient,
)

from ui import theme
from ui.components.base_canvas_view import BaseCanvasView
from ui.components.asset_editors.base_asset_editor import BaseAssetEditor
from ui.components.asset_detail_window import TagEditor, ImageGalleryStrip
from ui.components.image_preview_dialog import ImagePreviewDialog
from ui.pixmap_cache import PixmapCache

# ── 常量 ──
BASE_NODE_W, BASE_NODE_H = 220, 300
VARIANT_NODE_W, VARIANT_NODE_H = 180, 240
ANGLE_CARD_SIZE = 90          # 保留向后兼容（供 scene_editor 等 import）
ANGLE_CARD_MAX_SIDE = 90      # 有图时按比例缩放的最大边长
ANGLE_GAP = 12
VARIANT_GAP_Y = 160
VARIANT_OFFSET_X = 500
ANGLE_OFFSET_Y = 30
CORNER_RADIUS = 12

ANGLE_LABELS = ["正前", "正左", "正右", "正后", "上半身"]

# 连线颜色
COLOR_LINK = QColor(0, 180, 255, 150)
COLOR_FAN = QColor(100, 160, 255, 100)


# ============================================================
#  画布节点
# ============================================================

class _ImageCardBase(QGraphicsRectItem):
    """图片卡片基类 — 显示图片/空白+标签，可选中"""

    def __init__(self, w: float, h: float, parent=None):
        super().__init__(0, 0, w, h, parent)
        self._pixmap: Optional[QPixmap] = None
        self._label = ""
        self._sublabel = ""
        self._selected = False
        self._card_w = w
        self._card_h = h
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

    def set_image(self, path: str):
        if path and os.path.isfile(path):
            self._pixmap = QPixmap(path)
        else:
            self._pixmap = None
        self.update()

    def set_label(self, text: str, sub: str = ""):
        self._label = text
        self._sublabel = sub
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 背景
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)
        painter.setClipPath(path)

        bg = QColor(theme.bg_secondary())
        painter.fillPath(path, QBrush(bg))

        # 图片
        if self._pixmap and not self._pixmap.isNull():
            pw, ph = self._pixmap.width(), self._pixmap.height()
            img_area = QRectF(rect.x(), rect.y(),
                              rect.width(), rect.height() - 40)
            scale = max(img_area.width() / pw, img_area.height() / ph)
            sw, sh = pw * scale, ph * scale
            sx = img_area.x() + (img_area.width() - sw) / 2
            sy = img_area.y() + (img_area.height() - sh) / 2
            painter.drawPixmap(
                QRectF(sx, sy, sw, sh).toRect(),
                self._pixmap
            )
        else:
            # 空白占位
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1.5, Qt.PenStyle.DashLine))
            cx, cy = rect.center().x(), rect.center().y() - 20
            painter.drawLine(int(cx - 16), int(cy), int(cx + 16), int(cy))
            painter.drawLine(int(cx), int(cy - 16), int(cx), int(cy + 16))

        painter.setClipRect(rect)

        # 底部标签区
        label_rect = QRectF(
            rect.x(), rect.bottom() - 40,
            rect.width(), 40
        )
        grad = QLinearGradient(
            label_rect.topLeft(), label_rect.bottomLeft()
        )
        grad.setColorAt(0, QColor(0, 0, 0, 120))
        grad.setColorAt(1, QColor(0, 0, 0, 180))
        painter.fillRect(label_rect, grad)

        painter.setPen(QColor(255, 255, 255, 230))
        painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.DemiBold))
        painter.drawText(
            label_rect.adjusted(10, 0, -10, -4 if self._sublabel else 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
            if self._sublabel else
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._label
        )

        if self._sublabel:
            painter.setPen(QColor(255, 255, 255, 140))
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.drawText(
                label_rect.adjusted(10, 4, -10, 0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                self._sublabel
            )

        # 选中边框
        painter.setClipping(False)
        if self.isSelected():
            pen = QPen(QColor(theme.accent()), 2.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                rect.adjusted(1, 1, -1, -1), CORNER_RADIUS, CORNER_RADIUS
            )


class CharacterBaseNode(_ImageCardBase):
    """基础形象卡 220×300"""

    def __init__(self, parent=None):
        super().__init__(BASE_NODE_W, BASE_NODE_H, parent)
        self.asset_id: Optional[int] = None


class CharacterVariantNode(_ImageCardBase):
    """衍生形象卡 180×240"""

    def __init__(self, parent=None):
        super().__init__(VARIANT_NODE_W, VARIANT_NODE_H, parent)
        self.variant_id: Optional[int] = None
        self.variant_type: str = ""


class MultiAngleCard(QGraphicsRectItem):
    """多角度卡片 90×90，三态：空白/加载中/已完成"""

    def __init__(self, angle_index: int, label: str, parent=None):
        super().__init__(0, 0, ANGLE_CARD_MAX_SIDE, ANGLE_CARD_MAX_SIDE, parent)
        self._angle_index = angle_index
        self._label = label
        self._pixmap: Optional[QPixmap] = None
        self._image_path: str = ""
        self._is_loading = False
        self._spin_angle = 0
        self._spin_timer: Optional[QTimer] = None
        self.setAcceptHoverEvents(True)

    @property
    def angle_index(self) -> int:
        return self._angle_index

    def set_loading(self, loading: bool):
        self._is_loading = loading
        if loading and not self._spin_timer:
            self._spin_timer = QTimer()
            self._spin_timer.timeout.connect(self._on_spin)
            self._spin_timer.start(30)
        elif not loading and self._spin_timer:
            self._spin_timer.stop()
            self._spin_timer = None
        self.update()

    def set_pixmap_from_path(self, path: str):
        self._image_path = path or ""
        if path and os.path.isfile(path):
            self._pixmap = QPixmap(path)
            # 按实际图片比例调整卡片尺寸
            if self._pixmap and not self._pixmap.isNull():
                pw, ph = self._pixmap.width(), self._pixmap.height()
                if pw >= ph:
                    w = ANGLE_CARD_MAX_SIDE
                    h = max(40, int(ANGLE_CARD_MAX_SIDE * ph / pw))
                else:
                    w = max(40, int(ANGLE_CARD_MAX_SIDE * pw / ph))
                    h = ANGLE_CARD_MAX_SIDE
                self.setRect(0, 0, w, h)
        self._is_loading = False
        if self._spin_timer:
            self._spin_timer.stop()
            self._spin_timer = None
        self.update()

    def _on_spin(self):
        self._spin_angle = (self._spin_angle + 6) % 360
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        painter.setClipPath(path)

        # 背景
        painter.fillRect(rect, QBrush(QColor(theme.bg_secondary())))

        if self._pixmap and not self._pixmap.isNull():
            # 居中裁剪
            pw, ph = self._pixmap.width(), self._pixmap.height()
            s = max(rect.width() / pw, rect.height() / ph)
            sw, sh = pw * s, ph * s
            sx = (rect.width() - sw) / 2
            sy = (rect.height() - sh) / 2
            painter.drawPixmap(
                QRectF(sx, sy, sw, sh).toRect(), self._pixmap
            )
            # 底部角度标签叠加
            label_h = 18
            label_rect = QRectF(0, rect.height() - label_h, rect.width(), label_h)
            painter.setClipping(False)
            grad = QLinearGradient(label_rect.topLeft(), label_rect.bottomLeft())
            grad.setColorAt(0, QColor(0, 0, 0, 100))
            grad.setColorAt(1, QColor(0, 0, 0, 160))
            painter.fillRect(label_rect, grad)
            painter.setPen(QColor(255, 255, 255, 210))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._label)
        elif self._is_loading:
            # 旋转加载指示器
            cx, cy = rect.center().x(), rect.center().y()
            painter.translate(cx, cy)
            painter.rotate(self._spin_angle)
            pen = QPen(QColor(theme.accent()), 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            import math
            for j in range(8):
                angle = j * 45
                alpha = 40 + int(215 * ((j + 1) / 8))
                c = QColor(theme.accent())
                c.setAlpha(alpha)
                painter.setPen(QPen(c, 2.5, cap=Qt.PenCapStyle.RoundCap))
                rad = math.radians(angle)
                painter.drawLine(
                    QPointF(12 * math.cos(rad), 12 * math.sin(rad)),
                    QPointF(18 * math.cos(rad), 18 * math.sin(rad)),
                )
            painter.resetTransform()
            # 恢复位置
            self_pos = self.scenePos()
            painter.translate(self_pos)
        else:
            # 空白虚线框
            painter.setClipping(False)
            painter.setPen(
                QPen(QColor(255, 255, 255, 50), 1, Qt.PenStyle.DashLine)
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 6, 6)

            # 角度标签
            painter.setPen(QColor(255, 255, 255, 100))
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, self._label
            )


class _AddVariantNode(QGraphicsRectItem):
    """虚线加号卡片 — 点击新增衍生"""

    def __init__(self, parent=None):
        super().__init__(0, 0, VARIANT_NODE_W, 60, parent)
        self.setAcceptHoverEvents(True)
        self._hovered = False

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        alpha = 80 if self._hovered else 40
        painter.setPen(
            QPen(QColor(255, 255, 255, alpha), 1.5, Qt.PenStyle.DashLine)
        )
        painter.setBrush(QBrush(QColor(255, 255, 255, 8 if self._hovered else 3)))
        painter.drawRoundedRect(rect, 10, 10)

        painter.setPen(QColor(255, 255, 255, alpha + 40))
        painter.setFont(QFont("Microsoft YaHei", 11))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "+ 新增衍生形象")


class _GenerateAngleButton(QGraphicsRectItem):
    """形象卡右上角浮动"生成多视角"按钮"""

    BTN_W, BTN_H = 90, 28

    def __init__(self, group_id: int, on_click_cb, parent=None):
        super().__init__(0, 0, self.BTN_W, self.BTN_H, parent)
        self._group_id = group_id
        self._on_click_cb = on_click_cb
        self._hovered = False
        self._is_loading = False
        self._has_all = False  # 5张多角度全部已存在
        self._spin_angle = 0
        self._spin_timer: Optional[QTimer] = None
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    def set_has_all_angles(self, has_all: bool):
        self._has_all = has_all
        self.update()

    def set_loading(self, loading: bool):
        self._is_loading = loading
        if loading and not self._spin_timer:
            self._spin_timer = QTimer()
            self._spin_timer.timeout.connect(self._on_spin)
            self._spin_timer.start(30)
        elif not loading and self._spin_timer:
            self._spin_timer.stop()
            self._spin_timer = None
        self.update()

    def _on_spin(self):
        self._spin_angle = (self._spin_angle + 6) % 360
        self.update()

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if not self._is_loading and self._on_click_cb:
            self._on_click_cb(self._group_id)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        if self._is_loading:
            # 生成中 — 灰色背景 + 旋转指示器
            bg = QColor(100, 100, 100, 180)
            painter.setBrush(QBrush(bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 6, 6)

            import math
            cx, cy = rect.center().x(), rect.center().y()
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(self._spin_angle)
            for j in range(8):
                angle = j * 45
                alpha = 80 + int(175 * ((j + 1) / 8))
                c = QColor(255, 255, 255, alpha)
                painter.setPen(QPen(c, 1.5, cap=Qt.PenCapStyle.RoundCap))
                rad = math.radians(angle)
                painter.drawLine(
                    QPointF(5 * math.cos(rad), 5 * math.sin(rad)),
                    QPointF(9 * math.cos(rad), 9 * math.sin(rad)),
                )
            painter.restore()
        else:
            # 可点击状态
            if self._has_all:
                bg = QColor(80, 80, 100, 160) if self._hovered else QColor(60, 60, 80, 140)
                text = "重新生成"
            else:
                accent = QColor(theme.accent())
                if self._hovered:
                    accent = accent.lighter(115)
                bg = accent
                text = "生成多视角"

            painter.setBrush(QBrush(bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 6, 6)

            painter.setPen(QColor(255, 255, 255, 230))
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.DemiBold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


# ============================================================
#  角色编辑器画布
# ============================================================

class CharacterEditorCanvas(BaseCanvasView):
    """角色编辑器的无限画布"""

    node_selected = pyqtSignal(str, object)  # ("base"|"variant"|"angle"|..., node)
    generate_angle_requested = pyqtSignal(int)  # group_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_node: Optional[CharacterBaseNode] = None
        self._variant_nodes: List[CharacterVariantNode] = []
        self._angle_groups: Dict[int, List[MultiAngleCard]] = {}
        # node_id → angle_cards，node_id: -1=base, >=0=variant index
        self._connection_lines: List[QGraphicsPathItem] = []
        self._add_variant_node: Optional[_AddVariantNode] = None
        self._gen_buttons: Dict[int, _GenerateAngleButton] = {}

    def build_layout(self, base_data: dict,
                     variants: List[dict],
                     controller):
        """构建完整画布布局"""
        self._controller = controller
        scene = self._canvas_scene
        scene.clear()
        self._variant_nodes.clear()
        self._angle_groups.clear()
        self._connection_lines.clear()
        self._gen_buttons.clear()

        # ── 基础形象 ──
        self._base_node = CharacterBaseNode()
        self._base_node.asset_id = base_data.get('id')
        self._base_node.set_label(
            base_data.get('name', '基础形象')
        )
        self._base_node.set_image(
            base_data.get('main_reference_image', '')
        )
        self._base_node.setPos(0, 0)
        scene.addItem(self._base_node)

        # 基础形象多角度卡
        self._create_angle_group(-1, self._base_node, base_data)

        # 基础形象"生成多视角"按钮（有主图时显示）
        if base_data.get('main_reference_image'):
            self._create_gen_button(-1, self._base_node, base_data)

        # ── 衍生形象 ──
        for idx, var_data in enumerate(variants):
            self._add_variant(idx, var_data)

        # ── 添加衍生按钮 ──
        self._add_variant_node = _AddVariantNode()
        scene.addItem(self._add_variant_node)
        self._position_add_node()

        # 连线
        self._rebuild_connections()

        # fit
        QTimer.singleShot(100, self.fit_all_in_view)

    def _add_variant(self, idx: int, var_data: dict):
        node = CharacterVariantNode()
        node.variant_id = var_data.get('id')
        node.variant_type = var_data.get('variant_type', '')
        from ui.components.asset_detail_window import _VARIANT_TYPE_LABELS
        type_label = _VARIANT_TYPE_LABELS.get(
            node.variant_type, node.variant_type
        )
        node.set_label(
            var_data.get('name', f'衍生{idx+1}'),
            type_label
        )
        node.set_image(var_data.get('main_reference_image', ''))

        # 定位：基础形象右侧
        x = VARIANT_OFFSET_X
        y = idx * (VARIANT_NODE_H + VARIANT_GAP_Y)
        # 暂用idx简单定位，后面rebuild时统一
        node.setPos(x, y)

        self._canvas_scene.addItem(node)
        self._variant_nodes.append(node)

        # 多角度卡
        self._create_angle_group(idx, node, var_data)

        # "生成多视角"按钮（有主图时显示）
        if var_data.get('main_reference_image'):
            self._create_gen_button(idx, node, var_data)

    def _create_angle_group(self, group_id: int,
                            parent_node: _ImageCardBase,
                            data: dict):
        """在 parent_node 下方创建5张多角度卡"""
        angles = data.get('multi_angle_images', [])
        cards = []

        for i, label in enumerate(ANGLE_LABELS):
            card = MultiAngleCard(i, label)
            self._canvas_scene.addItem(card)

            # 加载已有图片
            if i < len(angles):
                img = angles[i]
                path = img.get('path', '') if isinstance(img, dict) else img
                if path and os.path.isfile(path):
                    card.set_pixmap_from_path(path)

            cards.append(card)

        self._angle_groups[group_id] = cards
        self._position_angle_cards(group_id, parent_node)

    def _position_angle_cards(self, group_id: int,
                              parent_node: _ImageCardBase):
        """将多角度卡片排列在父节点下方（支持可变宽度）"""
        cards = self._angle_groups.get(group_id, [])
        if not cards:
            return

        total_w = sum(c.rect().width() for c in cards) + (len(cards) - 1) * ANGLE_GAP
        parent_rect = parent_node.sceneBoundingRect()
        start_x = parent_rect.center().x() - total_w / 2
        y = parent_rect.bottom() + ANGLE_OFFSET_Y

        x_cursor = start_x
        for card in cards:
            card.setPos(x_cursor, y)
            x_cursor += card.rect().width() + ANGLE_GAP

    def _create_gen_button(self, group_id: int,
                           parent_node: _ImageCardBase,
                           data: dict):
        """在父节点右上角创建"生成多视角"按钮"""
        btn = _GenerateAngleButton(
            group_id,
            lambda gid: self.generate_angle_requested.emit(gid)
        )
        self._canvas_scene.addItem(btn)
        self._gen_buttons[group_id] = btn

        # 检查是否已有全部5张多角度
        angles = data.get('multi_angle_images', [])
        has_all = len(angles) >= 5 and all(
            (isinstance(a, dict) and a.get('path') and os.path.isfile(a['path']))
            or (isinstance(a, str) and os.path.isfile(a))
            for a in angles
        )
        btn.set_has_all_angles(has_all)

        self._position_gen_button(group_id, parent_node)

    def _position_gen_button(self, group_id: int,
                             parent_node: _ImageCardBase):
        """定位按钮在父节点右上角"""
        btn = self._gen_buttons.get(group_id)
        if not btn:
            return
        pr = parent_node.sceneBoundingRect()
        btn.setPos(
            pr.right() - _GenerateAngleButton.BTN_W - 5,
            pr.top() + 5
        )

    def _position_all_nodes(self):
        """重新排列所有节点位置"""
        if not self._base_node:
            return

        # 基础形象固定在左侧
        self._base_node.setPos(0, 0)
        self._position_angle_cards(-1, self._base_node)
        self._position_gen_button(-1, self._base_node)

        # 衍生形象在右侧垂直排列
        n = len(self._variant_nodes)
        if n > 0:
            total_h = n * VARIANT_NODE_H + (n - 1) * VARIANT_GAP_Y
            start_y = (BASE_NODE_H - total_h) / 2

            for idx, node in enumerate(self._variant_nodes):
                x = VARIANT_OFFSET_X
                y = start_y + idx * (VARIANT_NODE_H + VARIANT_GAP_Y)
                node.setPos(x, y)
                self._position_angle_cards(idx, node)
                self._position_gen_button(idx, node)

        self._position_add_node()

    def _position_add_node(self):
        if not self._add_variant_node:
            return
        if self._variant_nodes:
            last = self._variant_nodes[-1]
            x = VARIANT_OFFSET_X
            y = last.sceneBoundingRect().bottom() + 20
        else:
            x = VARIANT_OFFSET_X
            y = BASE_NODE_H / 2 - 30
        self._add_variant_node.setPos(x, y)

    def _rebuild_connections(self):
        """重建所有连线"""
        # 清除旧连线
        for line in self._connection_lines:
            if line.scene():
                self._canvas_scene.removeItem(line)
        self._connection_lines.clear()

        if not self._base_node:
            return

        # 基础形象 → 衍生（水平贝塞尔）
        for node in self._variant_nodes:
            line = self._create_h_bezier(
                self._base_node.sceneBoundingRect(),
                node.sceneBoundingRect(),
                COLOR_LINK
            )
            self._connection_lines.append(line)

        # 各父节点 → 多角度卡（垂直扇形）
        self._create_fan_lines(-1, self._base_node)
        for idx, node in enumerate(self._variant_nodes):
            self._create_fan_lines(idx, node)

    def _create_h_bezier(self, from_rect: QRectF, to_rect: QRectF,
                         color: QColor) -> QGraphicsPathItem:
        """创建水平贝塞尔连线"""
        start = QPointF(from_rect.right(), from_rect.center().y())
        end = QPointF(to_rect.left(), to_rect.center().y())
        offset = abs(end.x() - start.x()) * 0.4

        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + offset, start.y()),
            QPointF(end.x() - offset, end.y()),
            end
        )

        item = QGraphicsPathItem(path)
        pen = QPen(color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        item.setPen(pen)
        item.setZValue(-1)
        self._canvas_scene.addItem(item)
        return item

    def _create_fan_lines(self, group_id: int,
                          parent_node: _ImageCardBase):
        """父节点底部 → 各多角度卡顶部的扇形连线"""
        cards = self._angle_groups.get(group_id, [])
        if not cards:
            return

        parent_rect = parent_node.sceneBoundingRect()
        start = QPointF(
            parent_rect.center().x(), parent_rect.bottom()
        )

        for card in cards:
            card_rect = card.sceneBoundingRect()
            end = QPointF(card_rect.center().x(), card_rect.top())
            offset_y = abs(end.y() - start.y()) * 0.5

            path = QPainterPath(start)
            path.cubicTo(
                QPointF(start.x(), start.y() + offset_y),
                QPointF(end.x(), end.y() - offset_y),
                end
            )

            item = QGraphicsPathItem(path)
            pen = QPen(COLOR_FAN, 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            item.setPen(pen)
            item.setZValue(-1)
            self._canvas_scene.addItem(item)
            self._connection_lines.append(item)

    def mousePressEvent(self, event):
        # _GenerateAngleButton 自行处理点击，直接交给 QGraphicsScene
        item = self.itemAt(event.pos())
        if item:
            target = item
            while target:
                if isinstance(target, _GenerateAngleButton):
                    super().mousePressEvent(event)
                    return
                target = target.parentItem()

        super().mousePressEvent(event)

        if not item:
            self.node_selected.emit("none", None)
            return

        # 查找点击的节点类型
        target = item
        while target:
            if isinstance(target, CharacterBaseNode):
                self.node_selected.emit("base", target)
                return
            elif isinstance(target, CharacterVariantNode):
                self.node_selected.emit("variant", target)
                return
            elif isinstance(target, MultiAngleCard):
                self.node_selected.emit("angle", target)
                return
            elif isinstance(target, _AddVariantNode):
                self.node_selected.emit("add_variant", target)
                return
            target = target.parentItem()

    def mouseDoubleClickEvent(self, event):
        """双击形象卡片弹出大图预览"""
        super().mouseDoubleClickEvent(event)
        item = self.itemAt(event.pos())
        if not item:
            return
        target = item
        while target:
            if isinstance(target, (CharacterBaseNode, CharacterVariantNode)):
                self.node_selected.emit("dblclick_preview", target)
                return
            target = target.parentItem()

    # ── 公共方法 ──

    def get_angle_cards(self, group_id: int) -> List[MultiAngleCard]:
        return self._angle_groups.get(group_id, [])

    def add_new_variant(self, var_data: dict):
        """新增衍生节点"""
        idx = len(self._variant_nodes)
        self._add_variant(idx, var_data)
        self._position_all_nodes()
        self._rebuild_connections()

    def remove_variant(self, variant_idx: int):
        """删除衍生节点"""
        if variant_idx < 0 or variant_idx >= len(self._variant_nodes):
            return

        node = self._variant_nodes.pop(variant_idx)
        if node.scene():
            self._canvas_scene.removeItem(node)

        # 移除对应的多角度卡
        old_cards = self._angle_groups.pop(variant_idx, [])
        for card in old_cards:
            if card.scene():
                self._canvas_scene.removeItem(card)

        # 移除对应的生成按钮
        old_btn = self._gen_buttons.pop(variant_idx, None)
        if old_btn and old_btn.scene():
            self._canvas_scene.removeItem(old_btn)

        # 重新编号 angle_groups
        new_groups = {}
        for key, cards in self._angle_groups.items():
            if key == -1:
                new_groups[-1] = cards
            elif key > variant_idx:
                new_groups[key - 1] = cards
            else:
                new_groups[key] = cards
        self._angle_groups = new_groups

        # 重新编号 gen_buttons
        new_btns = {}
        for key, btn in self._gen_buttons.items():
            if key == -1:
                new_btns[-1] = btn
            elif key > variant_idx:
                btn._group_id = key - 1
                new_btns[key - 1] = btn
            else:
                new_btns[key] = btn
        self._gen_buttons = new_btns

        self._position_all_nodes()
        self._rebuild_connections()

    def refresh_base_image(self, path: str):
        if self._base_node:
            self._base_node.set_image(path)

    def refresh_variant_image(self, idx: int, path: str):
        if 0 <= idx < len(self._variant_nodes):
            self._variant_nodes[idx].set_image(path)


# ============================================================
#  信息栏面板
# ============================================================

class _BaseInfoPanel(QScrollArea):
    """基础形象信息面板"""

    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        self._form = QFormLayout(container)
        self._form.setContentsMargins(16, 12, 16, 12)
        self._form.setSpacing(10)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        style = f"""
            QLineEdit, QTextEdit, QComboBox {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                padding: 4px 8px;
                color: {theme.text_primary()};
            }}
            QLabel {{
                color: {theme.text_secondary()};
                font-size: 12px;
                background: transparent;
            }}
        """
        container.setStyleSheet(style)

        # 字段
        self._name_edit = QLineEdit()
        self._form.addRow("名称", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setFixedHeight(60)
        self._form.addRow("描述", self._desc_edit)

        self._gender_combo = QComboBox()
        self._gender_combo.addItems(["", "男", "女", "其他"])
        self._form.addRow("性别", self._gender_combo)

        self._age_combo = QComboBox()
        self._age_combo.addItems(["", "儿童", "少年", "青年", "中年", "老年"])
        self._form.addRow("年龄段", self._age_combo)

        self._hair_edit = QLineEdit()
        self._form.addRow("发型", self._hair_edit)

        self._hair_color_edit = QLineEdit()
        self._form.addRow("发色", self._hair_color_edit)

        self._body_edit = QLineEdit()
        self._form.addRow("体型", self._body_edit)

        self._clothing_edit = QTextEdit()
        self._clothing_edit.setFixedHeight(50)
        self._form.addRow("穿着", self._clothing_edit)

        self._anchor_edit = QTextEdit()
        self._anchor_edit.setFixedHeight(50)
        self._anchor_edit.setPlaceholderText("视觉锚点（如：左眼下方小痣）")
        self._form.addRow("视觉锚点", self._anchor_edit)

        self._tag_editor = TagEditor()
        self._form.addRow("标签", self._tag_editor)

        self._gallery = ImageGalleryStrip()
        self._form.addRow("参考图片", self._gallery)

        self.setWidget(container)

    def load(self, data: dict):
        self._name_edit.setText(data.get('name', ''))
        self._desc_edit.setPlainText(data.get('description', ''))

        attrs = data.get('visual_attributes', {}) or {}
        gender = attrs.get('gender', data.get('gender', ''))
        idx = self._gender_combo.findText(gender)
        self._gender_combo.setCurrentIndex(max(0, idx))

        age = attrs.get('age_group', data.get('age_group', ''))
        idx = self._age_combo.findText(age)
        self._age_combo.setCurrentIndex(max(0, idx))

        self._hair_edit.setText(attrs.get('hairstyle', ''))
        self._hair_color_edit.setText(attrs.get('hair_color', ''))
        self._body_edit.setText(attrs.get('body_type', ''))
        self._clothing_edit.setPlainText(attrs.get('clothing_style', ''))

        anchors = data.get('visual_anchors', [])
        self._anchor_edit.setPlainText(
            '\n'.join(anchors) if isinstance(anchors, list) else str(anchors)
        )

        self._tag_editor = TagEditor(data.get('tags', []))
        # 重新添加到表单
        self._gallery = ImageGalleryStrip(data.get('reference_images', []))

    def collect(self) -> dict:
        attrs = {
            'gender': self._gender_combo.currentText(),
            'age_group': self._age_combo.currentText(),
            'hairstyle': self._hair_edit.text().strip(),
            'hair_color': self._hair_color_edit.text().strip(),
            'body_type': self._body_edit.text().strip(),
            'clothing_style': self._clothing_edit.toPlainText().strip(),
        }
        anchors_text = self._anchor_edit.toPlainText().strip()
        anchors = [a.strip() for a in anchors_text.split('\n') if a.strip()]

        return {
            'name': self._name_edit.text().strip() or '未命名',
            'description': self._desc_edit.toPlainText().strip(),
            'visual_attributes': attrs,
            'gender': attrs['gender'],
            'age_group': attrs['age_group'],
            'visual_anchors': anchors,
            'tags': self._tag_editor.get_tags(),
            'reference_images': self._gallery.get_images(),
        }


class _VariantInfoPanel(QScrollArea):
    """衍生形象信息面板"""

    delete_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        self._form = QFormLayout(container)
        self._form.setContentsMargins(16, 12, 16, 12)
        self._form.setSpacing(10)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        style = f"""
            QLineEdit, QTextEdit, QComboBox {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                padding: 4px 8px;
                color: {theme.text_primary()};
            }}
            QLabel {{
                color: {theme.text_secondary()};
                font-size: 12px;
                background: transparent;
            }}
        """
        container.setStyleSheet(style)

        self._name_edit = QLineEdit()
        self._form.addRow("衍生名称", self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItems([
            "costume_variant", "age_variant", "appearance_variant"
        ])
        self._form.addRow("衍生类型", self._type_combo)

        self._desc_edit = QTextEdit()
        self._desc_edit.setFixedHeight(60)
        self._form.addRow("衍生描述", self._desc_edit)

        self._clothing_edit = QTextEdit()
        self._clothing_edit.setFixedHeight(50)
        self._form.addRow("穿着变化", self._clothing_edit)

        # 删除按钮
        del_btn = QPushButton("删除此衍生")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.danger()};
                border: 1px solid {theme.danger()};
                border-radius: 6px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,58,0.15);
            }}
        """)
        del_btn.clicked.connect(self.delete_requested.emit)
        self._form.addRow("", del_btn)

        self.setWidget(container)

    def load(self, data: dict):
        self._name_edit.setText(data.get('name', ''))
        idx = self._type_combo.findText(
            data.get('variant_type', 'costume_variant')
        )
        self._type_combo.setCurrentIndex(max(0, idx))
        self._desc_edit.setPlainText(
            data.get('variant_description', '')
        )
        attrs = data.get('visual_attributes', {}) or {}
        self._clothing_edit.setPlainText(
            attrs.get('clothing_style', '')
        )

    def collect(self) -> dict:
        return {
            'name': self._name_edit.text().strip() or '未命名衍生',
            'variant_type': self._type_combo.currentText(),
            'variant_description': self._desc_edit.toPlainText().strip(),
            'visual_attributes': {
                'clothing_style': self._clothing_edit.toPlainText().strip(),
            },
        }


# ============================================================
#  CharacterEditor — 角色编辑器主类
# ============================================================

class CharacterEditor(BaseAssetEditor):
    """角色资产全屏编辑器"""

    def __init__(self, asset_data: dict, controller, parent=None):
        self._variants: List[dict] = []
        self._selected_variant_idx: int = -1
        super().__init__(asset_data, controller, parent)

    def _create_canvas(self) -> QWidget:
        self._canvas = CharacterEditorCanvas()
        self._canvas.node_selected.connect(self._on_node_selected)
        self._canvas.generate_angle_requested.connect(
            self.start_multi_angle_generation
        )
        return self._canvas

    def _create_info_panel(self) -> QWidget:
        self._info_stack = QStackedWidget()
        self._info_stack.setStyleSheet(
            f"background: {theme.bg_secondary()};"
        )

        # Page 0: 基础形象
        self._base_panel = _BaseInfoPanel()
        self._info_stack.addWidget(self._base_panel)

        # Page 1: 衍生形象
        self._variant_panel = _VariantInfoPanel()
        self._variant_panel.delete_requested.connect(
            self._on_delete_variant
        )
        self._info_stack.addWidget(self._variant_panel)

        return self._info_stack

    def _load_data(self):
        # 加载基础形象
        self._base_panel.load(self._asset_data)

        # 加载衍生
        self._variants = self._controller.get_character_variants(
            self._asset_id
        ) if self._asset_id else []

        # 构建画布
        self._canvas.build_layout(
            self._asset_data, self._variants, self._controller
        )

        # 默认显示基础形象信息
        self._info_stack.setCurrentIndex(0)

    def _collect_data(self) -> dict:
        return self._base_panel.collect()

    # ── 节点选中 ──

    def _on_node_selected(self, node_type: str, node):
        if node_type == "base":
            self._info_stack.setCurrentIndex(0)
            self._selected_variant_idx = -1
        elif node_type == "variant" and isinstance(node, CharacterVariantNode):
            for idx, var in enumerate(self._variants):
                if var.get('id') == node.variant_id:
                    self._selected_variant_idx = idx
                    self._variant_panel.load(var)
                    self._info_stack.setCurrentIndex(1)
                    break
        elif node_type == "add_variant":
            self._on_add_variant()
        elif node_type == "angle" and isinstance(node, MultiAngleCard):
            self._on_angle_card_clicked(node)
        elif node_type == "dblclick_preview":
            self._preview_node_image(node)

    def _preview_node_image(self, node: _ImageCardBase):
        """预览形象卡的图片"""
        if node._pixmap and not node._pixmap.isNull():
            dlg = ImagePreviewDialog(node._pixmap, self)
            dlg.exec()

    def _on_add_variant(self):
        if not self._asset_id:
            return
        result = self._controller.create_character_variant(
            self._asset_id, 'costume_variant', '新衍生形象'
        )
        if result:
            self._variants.append(result)
            self._canvas.add_new_variant(result)

    def _on_delete_variant(self):
        if self._selected_variant_idx < 0:
            return
        var = self._variants[self._selected_variant_idx]
        var_id = var.get('id')
        if var_id:
            self._controller.delete_asset(var_id)

        self._variants.pop(self._selected_variant_idx)
        self._canvas.remove_variant(self._selected_variant_idx)
        self._selected_variant_idx = -1
        self._info_stack.setCurrentIndex(0)

    def _on_angle_card_clicked(self, card: MultiAngleCard):
        """多角度卡片点击 — 有图片则预览，空卡则上传"""
        if card._pixmap and not card._pixmap.isNull():
            dlg = ImagePreviewDialog(card._pixmap, self)
            dlg.exec()
        else:
            self._upload_angle_image(card)

    def _upload_angle_image(self, card: MultiAngleCard):
        """空卡点击 → 文件选择器上传图片"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        # 复制到资产目录
        src_dir = os.path.dirname(
            self._asset_data.get('main_reference_image', '') or ''
        )
        if not src_dir:
            src_dir = os.path.join('generated', 'angle_uploads')
        os.makedirs(src_dir, exist_ok=True)
        ext = os.path.splitext(path)[1]
        dest = os.path.join(src_dir, f"angle_{card.angle_index}{ext}")
        import shutil
        shutil.copy2(path, dest)
        card.set_pixmap_from_path(dest)
        # 更新数据库
        if self._asset_id:
            angles = list(self._asset_data.get('multi_angle_images', []) or [])
            while len(angles) <= card.angle_index:
                angles.append({})
            angles[card.angle_index] = {
                "angle": ANGLE_LABELS[card.angle_index],
                "path": dest
            }
            self._asset_data['multi_angle_images'] = angles
            self._controller.update_asset(
                self._asset_id, multi_angle_images=angles
            )

    # ── 多角度生成 ──

    def start_multi_angle_generation(self, group_id: int):
        """启动5角度批量生成（支持多组并行）"""
        # 确定源图路径
        if group_id == -1:
            src = self._asset_data.get('main_reference_image', '')
        elif 0 <= group_id < len(self._variants):
            src = self._variants[group_id].get(
                'main_reference_image', ''
            )
        else:
            return

        if not src or not os.path.isfile(src):
            return

        from config.settings import SettingsManager
        api_cfg = SettingsManager().settings.api
        api_key = api_cfg.runninghub_api_key
        base_url = api_cfg.runninghub_base_url
        if not api_key:
            return

        # 初始化 workers 字典
        if not hasattr(self, '_ma_workers'):
            self._ma_workers: dict = {}

        # 同一组不重复启动
        if group_id in self._ma_workers and self._ma_workers[group_id].isRunning():
            return

        save_dir = os.path.join(
            os.path.dirname(src), f"multi_angle_{group_id}"
        )

        from services.multi_angle_batch_service import MultiAngleBatchWorker
        worker = MultiAngleBatchWorker(
            src, save_dir, api_key, base_url, parent=self
        )
        self._ma_workers[group_id] = worker

        cards = self._canvas.get_angle_cards(group_id)

        _gid = group_id  # 闭包捕获

        def on_angle_done(idx, path):
            if idx < len(cards):
                cards[idx].set_pixmap_from_path(path)

        def on_all_done(success, paths, error):
            self._ma_workers.pop(_gid, None)
            # 恢复按钮状态
            gen_btn = self._canvas._gen_buttons.get(_gid)
            if gen_btn:
                gen_btn.set_loading(False)
                gen_btn.set_has_all_angles(success and len(paths) >= 5)
            if success and self._asset_id:
                angle_images = [
                    {"angle": ANGLE_LABELS[i], "path": p}
                    for i, p in enumerate(paths)
                ]
                self._controller.update_asset(
                    self._asset_id if _gid == -1
                    else self._variants[_gid].get('id'),
                    multi_angle_images=angle_images
                )

        # 设置加载状态
        for card in cards:
            card.set_loading(True)

        # 设置按钮加载状态
        gen_btn = self._canvas._gen_buttons.get(group_id)
        if gen_btn:
            gen_btn.set_loading(True)

        worker.angle_completed.connect(on_angle_done)
        worker.all_completed.connect(on_all_done)
        worker.start()
