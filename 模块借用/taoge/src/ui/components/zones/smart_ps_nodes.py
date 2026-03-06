"""
涛割 - 智能PS节点类型
ComfyUI 风格节点画布中的节点：
  1. InputAssetNode  — 输入资产节点（缩略图 + 名称 + 类型 + 多视角选择）
  2. PSCanvasNode    — PS画布节点（嵌入 EmbeddedCanvasWidget，动态尺寸）
  3. SnapshotNode    — 快照节点（从PS拖拽创建，可多个）
  4. DissolveNode    — 溶图节点（默认直通）
  5. HDOutputNode    — 高清化+输出节点（默认直通 + 确认输出）

已删除: PreprocessChainNode / OutputNode（拆分为独立节点）
"""

import os
from typing import Optional, Callable, List

from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsItem, QGraphicsProxyWidget,
    QGraphicsSimpleTextItem, QGraphicsPixmapItem, QMenu,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPixmap, QLinearGradient, QFontMetrics,
)

from ui import theme

# ============================================================
#  常量
# ============================================================

ANCHOR_R = 6
CORNER_R = 12

# 节点颜色
COLOR_NODE_BG = QColor(28, 28, 40, 240)
COLOR_NODE_BG_LIGHT = QColor(245, 245, 252, 240)
COLOR_NODE_BORDER = QColor(60, 60, 80)
COLOR_NODE_BORDER_LIGHT = QColor(200, 200, 215)
COLOR_ACCENT = QColor(91, 127, 255)
COLOR_ANCHOR = QColor(91, 127, 255, 200)
COLOR_ANCHOR_OUTLINE = QColor(91, 127, 255, 80)
COLOR_HEADER_BG = QColor(40, 42, 58)
COLOR_HEADER_BG_LIGHT = QColor(230, 232, 240)
COLOR_GREEN = QColor(50, 180, 100)

# 类型颜色映射
TYPE_COLORS = {
    'character': QColor(255, 127, 80),
    'scene': QColor(80, 180, 255),
    'prop': QColor(180, 130, 255),
    'background': QColor(100, 200, 150),
}

HEADER_H = 32
ARROW_SIZE = 8


# ============================================================
#  _paint_anchor — 绘制锚点圆
# ============================================================

def _paint_anchor(painter: QPainter, center: QPointF, is_output: bool = False):
    """绘制输入/输出锚点圆"""
    painter.setBrush(QBrush(COLOR_ACCENT))
    painter.setPen(QPen(COLOR_ANCHOR_OUTLINE, 2))
    painter.drawEllipse(center, ANCHOR_R, ANCHOR_R)


# ============================================================
#  _paint_node_frame — 通用节点框架绘制
# ============================================================

def _paint_node_frame(painter: QPainter, rect: QRectF, title: str,
                      is_dark: bool, is_selected: bool,
                      header_color: QColor = None,
                      draw_in_anchor: bool = True,
                      draw_out_anchor: bool = True):
    """绘制通用节点背景 + 标题栏 + 锚点"""
    w, h = rect.width(), rect.height()

    # 背景
    path = QPainterPath()
    path.addRoundedRect(rect, CORNER_R, CORNER_R)
    bg = COLOR_NODE_BG if is_dark else COLOR_NODE_BG_LIGHT
    painter.fillPath(path, bg)

    # 边框
    border = COLOR_NODE_BORDER if is_dark else COLOR_NODE_BORDER_LIGHT
    if is_selected:
        border = COLOR_ACCENT
    painter.setPen(QPen(border, 1.5))
    painter.drawPath(path)

    # 标题栏
    hdr_color = header_color or (COLOR_HEADER_BG if is_dark else COLOR_HEADER_BG_LIGHT)
    header_path = QPainterPath()
    header_path.addRoundedRect(QRectF(0, 0, w, HEADER_H), CORNER_R, CORNER_R)
    header_path.addRect(QRectF(0, HEADER_H - CORNER_R, w, CORNER_R))
    painter.fillPath(header_path, hdr_color)

    # 标题文字
    font = QFont("Microsoft YaHei", 9, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(220, 220, 235) if is_dark else QColor(40, 40, 50))
    painter.drawText(QRectF(24, 0, w - 48, HEADER_H),
                     Qt.AlignmentFlag.AlignVCenter, title)

    # 锚点
    if draw_in_anchor:
        _paint_anchor(painter, QPointF(0, h / 2))
    if draw_out_anchor:
        _paint_anchor(painter, QPointF(w, h / 2), is_output=True)


# ============================================================
#  1. InputAssetNode — 输入资产节点（带多视角选择）
# ============================================================

class InputAssetNode(QGraphicsRectItem):
    """
    输入资产节点 — 显示资产缩略图 + 名称 + 类型标签 + 多视角选择。
    ┌─────────────────┐
    │ ■ 资产名称       │  <- 标题栏(类型色)
    │ ┌─────────────┐ │
    │ │  缩略图      │ │
    │ │  120x90      │ │
    │ └─────────────┘ │
    │  类型: character │
    │  [当前视角] badge ● │  <- 底部 + 输出锚点
    └─────────────────┘
    """

    NODE_WIDTH = 320
    NODE_HEIGHT = 380

    def __init__(self, asset: dict, parent=None,
                 on_moved: Optional[Callable] = None,
                 on_angle_changed: Optional[Callable] = None):
        super().__init__(parent)
        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)

        self._asset = asset
        self._name = asset.get('name', '未命名资产')
        self._image_path = asset.get('image_path', '')
        self._asset_type = asset.get('type', 'prop')
        self._on_moved = on_moved
        self._on_angle_changed = on_angle_changed

        # 多视角
        self._multi_angle_images: list = asset.get('multi_angle_images', [])
        self._selected_angle: str = "原视角"

        # 缩略图
        self._thumb: Optional[QPixmap] = None
        self._load_thumb(self._image_path)

        # 缩略图点击热区
        self._thumb_area_rect = QRectF(30, HEADER_H + 12, 260, 180)

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(100)

    def _load_thumb(self, path: str):
        """加载缩略图"""
        self._thumb = None
        if path and os.path.isfile(path):
            px = QPixmap(path)
            if not px.isNull():
                self._thumb = px.scaled(
                    260, 180, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)

    def get_current_image_path(self) -> str:
        """返回当前选中视角的图片路径"""
        if self._selected_angle == "原视角":
            return self._image_path
        for img in self._multi_angle_images:
            if isinstance(img, dict):
                if img.get('angle', '') == self._selected_angle:
                    return img.get('path', '')
            elif isinstance(img, str):
                return img
        return self._image_path

    def get_current_pixmap(self) -> Optional[QPixmap]:
        """返回当前选中视角的完整 pixmap"""
        path = self.get_current_image_path()
        if path and os.path.isfile(path):
            px = QPixmap(path)
            if not px.isNull():
                return px
        return None

    def get_output_anchor(self) -> QPointF:
        """右侧输出锚点（场景坐标）"""
        return self.mapToScene(QPointF(self.NODE_WIDTH, self.NODE_HEIGHT / 2))

    def get_input_anchor(self) -> QPointF:
        """左侧输入锚点（场景坐标）"""
        return self.mapToScene(QPointF(0, self.NODE_HEIGHT / 2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._on_moved()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            if self._thumb_area_rect.contains(pos) and self._multi_angle_images:
                self._show_angle_menu(event)
                event.accept()
                return
        super().mousePressEvent(event)

    def _show_angle_menu(self, event):
        """弹出视角选择菜单"""
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: #2a2a3e; color: #e0e0ef; border: 1px solid #3a3a50; "
            "border-radius: 6px; padding: 4px; }"
            "QMenu::item { padding: 6px 16px; }"
            "QMenu::item:selected { background: #5b7fff; border-radius: 4px; }"
        )

        # 原视角选项
        act_orig = menu.addAction("原视角 (默认)")
        act_orig.setCheckable(True)
        act_orig.setChecked(self._selected_angle == "原视角")
        act_orig.triggered.connect(lambda: self._select_angle("原视角", self._image_path))

        menu.addSeparator()

        # 多视角选项
        for img in self._multi_angle_images:
            if isinstance(img, dict):
                angle_name = img.get('angle', '未知视角')
                angle_path = img.get('path', '')
            else:
                continue

            act = menu.addAction(angle_name)
            act.setCheckable(True)
            act.setChecked(self._selected_angle == angle_name)
            act.triggered.connect(
                lambda checked, n=angle_name, p=angle_path: self._select_angle(n, p))

        # 在节点下方弹出
        scene_pos = self.mapToScene(event.pos())
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view:
            global_pos = view.mapToGlobal(view.mapFromScene(scene_pos))
            menu.exec(global_pos)

    def _select_angle(self, angle_name: str, path: str):
        """选中视角后更新缩略图"""
        self._selected_angle = angle_name
        self._load_thumb(path if path else self._image_path)
        self.update()

        if self._on_angle_changed:
            new_pixmap = self.get_current_pixmap()
            if new_pixmap:
                self._on_angle_changed(self, new_pixmap)

    def paint(self, painter: QPainter, option, widget=None):
        is_dark = theme.is_dark()
        rect = self.rect()
        w, h = rect.width(), rect.height()

        # 背景
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER_R, CORNER_R)
        bg = COLOR_NODE_BG if is_dark else COLOR_NODE_BG_LIGHT
        painter.fillPath(path, bg)

        # 边框
        border = COLOR_NODE_BORDER if is_dark else COLOR_NODE_BORDER_LIGHT
        if self.isSelected():
            border = COLOR_ACCENT
        painter.setPen(QPen(border, 1.5))
        painter.drawPath(path)

        # 标题栏
        type_color = TYPE_COLORS.get(self._asset_type, COLOR_ACCENT)
        header_path = QPainterPath()
        header_path.addRoundedRect(QRectF(0, 0, w, HEADER_H), CORNER_R, CORNER_R)
        header_path.addRect(QRectF(0, HEADER_H - CORNER_R, w, CORNER_R))
        painter.fillPath(header_path, type_color.darker(140) if is_dark else type_color.lighter(150))

        # 标题文字
        font = QFont("Microsoft YaHei", 11, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255) if is_dark else QColor(30, 30, 30))
        fm = QFontMetrics(font)
        elided = fm.elidedText(self._name, Qt.TextElideMode.ElideRight, int(w - 40))
        painter.drawText(QRectF(16, 0, w - 32, HEADER_H),
                         Qt.AlignmentFlag.AlignVCenter, elided)

        # 缩略图
        thumb_y = HEADER_H + 12
        thumb_area = QRectF(30, thumb_y, 260, 180)
        self._thumb_area_rect = thumb_area

        if self._thumb and not self._thumb.isNull():
            tx = thumb_area.x() + (thumb_area.width() - self._thumb.width()) / 2
            ty = thumb_area.y() + (thumb_area.height() - self._thumb.height()) / 2
            painter.drawPixmap(int(tx), int(ty), self._thumb)
        else:
            painter.setPen(QPen(QColor(100, 100, 120), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(thumb_area)
            painter.setPen(QColor(120, 120, 140))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(thumb_area, Qt.AlignmentFlag.AlignCenter, "无图片")

        # 多视角指示器（缩略图右下角）
        if self._multi_angle_images:
            badge_w = 80
            badge_h = 20
            badge_x = thumb_area.right() - badge_w - 4
            badge_y = thumb_area.bottom() - badge_h - 4
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
            badge_path = QPainterPath()
            badge_path.addRoundedRect(badge_rect, 4, 4)
            painter.fillPath(badge_path, QColor(0, 0, 0, 160))
            painter.setPen(QColor(200, 200, 220))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter,
                             f"x{len(self._multi_angle_images)}视角")

        # 底部类型标签
        label_y = thumb_area.bottom() + 8
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.setPen(QColor(160, 160, 180) if is_dark else QColor(100, 100, 120))
        type_labels = {'character': '角色', 'scene': '场景', 'prop': '道具', 'background': '背景'}
        painter.drawText(QRectF(16, label_y, w - 50, 22),
                         Qt.AlignmentFlag.AlignVCenter,
                         type_labels.get(self._asset_type, self._asset_type))

        # 当前视角 badge
        if self._selected_angle != "原视角":
            angle_y = label_y + 24
            angle_rect = QRectF(16, angle_y, w - 32, 20)
            angle_path = QPainterPath()
            angle_path.addRoundedRect(angle_rect, 3, 3)
            painter.fillPath(angle_path, COLOR_ACCENT.darker(150))
            painter.setPen(QColor(180, 200, 255))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(angle_rect, Qt.AlignmentFlag.AlignCenter,
                             self._selected_angle)

        # 右侧输出锚点
        _paint_anchor(painter, QPointF(w, h / 2), is_output=True)


# ============================================================
#  2. PSCanvasNode — PS画布节点（动态尺寸）
# ============================================================

class PSCanvasNode(QGraphicsRectItem):
    """
    PS画布节点 — 通过 QGraphicsProxyWidget 嵌入 EmbeddedCanvasWidget。
    尺寸根据首张资产图片实际宽高比动态计算。
    """

    MIN_W, MIN_H = 1200, 800
    MAX_W, MAX_H = 2800, 2000
    DEFAULT_W, DEFAULT_H = 1800, 1400

    CANVAS_PADDING = 0  # 无间距，PS内部画布与节点外框对齐

    def __init__(self, scene_id: int, data_hub, first_open: bool = True,
                 assets: list = None, parent=None,
                 on_moved: Optional[Callable] = None,
                 scene_dimensions: tuple = None):
        super().__init__(parent)

        self._scene_id = scene_id
        self._data_hub = data_hub
        self._first_open = first_open
        self._assets = assets or []
        self._on_moved = on_moved

        # 动态计算节点尺寸
        self._node_w, self._node_h = self._compute_dimensions(scene_dimensions)
        self.setRect(0, 0, self._node_w, self._node_h)

        self._canvas_proxy: Optional[QGraphicsProxyWidget] = None
        self._embedded_widget = None

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setZValue(100)

        # 延迟初始化（需要 scene 可用）
        QTimer.singleShot(0, self._init_canvas)

    def _compute_dimensions(self, scene_dimensions: tuple = None) -> tuple:
        """根据场景尺寸或首张资产图计算节点宽高"""
        sw, sh = 0, 0

        if scene_dimensions and len(scene_dimensions) == 2:
            sw, sh = scene_dimensions

        if sw <= 0 or sh <= 0:
            # 尝试从首张资产图检测
            for asset in self._assets:
                img_path = asset.get('image_path', '')
                if img_path and os.path.isfile(img_path):
                    px = QPixmap(img_path)
                    if not px.isNull():
                        sw, sh = px.width(), px.height()
                        break

        if sw <= 0 or sh <= 0:
            return self.DEFAULT_W, self.DEFAULT_H

        aspect = sw / sh
        # 以默认高度为基准，按比例缩放宽度
        target_h = self.DEFAULT_H
        target_w = int(target_h * aspect)

        # 约束范围
        target_w = max(self.MIN_W, min(self.MAX_W, target_w))
        target_h = max(self.MIN_H, min(self.MAX_H, target_h))

        # 如果宽度被约束了，反算高度
        if target_w == self.MAX_W or target_w == self.MIN_W:
            target_h = int(target_w / aspect)
            target_h = max(self.MIN_H, min(self.MAX_H, target_h))

        return target_w, target_h

    def _init_canvas(self):
        """延迟创建 EmbeddedCanvasWidget（需 scene 可用）"""
        if not self.scene():
            QTimer.singleShot(50, self._init_canvas)
            return

        from .smart_ps_agent_node import EmbeddedCanvasWidget

        # 无间距：PS画布左边缘对齐节点外框，上边缘对齐标题栏下方
        cw = self._node_w
        ch = self._node_h - HEADER_H

        self._embedded_widget = EmbeddedCanvasWidget(
            data_hub=self._data_hub,
            scene_id=self._scene_id,
            assets=self._assets,
            first_open=self._first_open,
        )
        self._embedded_widget.setFixedSize(int(cw), int(ch))

        # 画框尺寸匹配节点实际空间
        self._embedded_widget.set_canvas_frame_size(cw, ch)

        self._canvas_proxy = QGraphicsProxyWidget(self)
        self._canvas_proxy.setWidget(self._embedded_widget)
        self._canvas_proxy.setPos(0, HEADER_H)

    def add_layer_from_pixmap(self, pixmap: QPixmap, name: str = "资产图层"):
        """从外部接收图片 -> 在画布中创建新图层"""
        if not self._embedded_widget:
            return
        try:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False,
                                              prefix='ps_layer_')
            tmp_path = tmp.name
            tmp.close()
            pixmap.save(tmp_path, 'PNG')

            from services.layer_service import LayerService
            layer_service = LayerService()
            layer_data = {
                'scene_id': self._scene_id,
                'name': name,
                'layer_type': 'prop',
                'z_order': len(self._embedded_widget._canvas_view._layer_items),
                'is_visible': True,
                'is_locked': False,
                'image_path': tmp_path,
                'original_image_path': tmp_path,
            }
            layer_id = layer_service.save_layer(layer_data)
            layer_data['id'] = layer_id
            self._embedded_widget._canvas_view.add_layer(layer_data)
            self._embedded_widget._refresh_layer_panel()
        except Exception as e:
            print(f"[涛割] PSCanvasNode 添加图层失败: {e}")

    def export_composite_image(self) -> str:
        """导出合成图"""
        if self._embedded_widget:
            return self._embedded_widget.export_composite_image()
        return ''

    def save_scene(self):
        if self._embedded_widget:
            self._embedded_widget.save_scene()

    def get_input_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(0, self._node_h / 2))

    def get_output_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(self._node_w, self._node_h / 2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._on_moved()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        is_dark = theme.is_dark()
        rect = self.rect()
        w, h = rect.width(), rect.height()

        # LOD: 缩放太小时简化绘制
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < 0.15:
            painter.fillRect(rect, COLOR_NODE_BG if is_dark else COLOR_NODE_BG_LIGHT)
            return

        _paint_node_frame(painter, rect, "PS 画布", is_dark, self.isSelected())


# ============================================================
#  3. SnapshotNode — 快照节点
# ============================================================

class SnapshotNode(QGraphicsRectItem):
    """
    快照节点 — 从PS画布拖拽创建，可多个。
    ┌─────────────────┐
    │ ● in  快照 #N   │
    │ ┌─────────────┐ │
    │ │ 快照缩略图  │ │  150x100
    │ └─────────────┘ │
    │  [重新拍摄]  ● out│
    └─────────────────┘
    """

    NODE_WIDTH = 200
    NODE_HEIGHT = 180

    def __init__(self, snapshot_index: int = 1, parent=None,
                 on_retake: Optional[Callable] = None,
                 on_moved: Optional[Callable] = None):
        super().__init__(parent)
        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)

        self._snapshot_index = snapshot_index
        self._on_retake = on_retake
        self._on_moved = on_moved

        self._snapshot_pixmap: Optional[QPixmap] = None
        self._snapshot_path: str = ''
        self._retake_btn_hovered = False
        self._retake_btn_rect = QRectF()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(100)

    def set_snapshot(self, pixmap: QPixmap, path: str = ''):
        """设置快照图"""
        self._snapshot_pixmap = pixmap.scaled(
            170, 100, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._snapshot_path = path
        self.update()

    def get_snapshot_path(self) -> str:
        return self._snapshot_path

    def get_snapshot_pixmap(self) -> Optional[QPixmap]:
        """获取完整快照 pixmap（非缩略图）"""
        if self._snapshot_path and os.path.isfile(self._snapshot_path):
            return QPixmap(self._snapshot_path)
        return None

    def get_input_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(0, self.NODE_HEIGHT / 2))

    def get_output_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(self.NODE_WIDTH, self.NODE_HEIGHT / 2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._on_moved()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._retake_btn_rect.contains(event.pos()):
                if self._on_retake:
                    self._on_retake(self)
                event.accept()
                return
        super().mousePressEvent(event)

    def hoverMoveEvent(self, event):
        old = self._retake_btn_hovered
        self._retake_btn_hovered = self._retake_btn_rect.contains(event.pos())
        if old != self._retake_btn_hovered:
            self.update()

    def hoverLeaveEvent(self, event):
        self._retake_btn_hovered = False
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        is_dark = theme.is_dark()
        rect = self.rect()
        w, h = rect.width(), rect.height()

        _paint_node_frame(painter, rect, f"快照 #{self._snapshot_index}",
                          is_dark, self.isSelected())

        # 缩略图区域
        thumb_y = HEADER_H + 8
        thumb_rect = QRectF(15, thumb_y, 170, 100)

        if self._snapshot_pixmap and not self._snapshot_pixmap.isNull():
            tx = thumb_rect.x() + (thumb_rect.width() - self._snapshot_pixmap.width()) / 2
            ty = thumb_rect.y() + (thumb_rect.height() - self._snapshot_pixmap.height()) / 2
            painter.drawPixmap(int(tx), int(ty), self._snapshot_pixmap)
        else:
            painter.setPen(QPen(QColor(80, 80, 100), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(thumb_rect)
            painter.setPen(QColor(100, 100, 120))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "等待快照")

        # 重新拍摄按钮
        btn_y = h - 36
        self._retake_btn_rect = QRectF(12, btn_y, w - 24, 28)
        btn_bg = COLOR_ACCENT.lighter(120) if self._retake_btn_hovered else COLOR_ACCENT
        btn_path = QPainterPath()
        btn_path.addRoundedRect(self._retake_btn_rect, 5, 5)
        painter.fillPath(btn_path, btn_bg)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
        painter.drawText(self._retake_btn_rect, Qt.AlignmentFlag.AlignCenter,
                         "重新拍摄")


# ============================================================
#  4. DissolveNode — 溶图节点（默认直通）
# ============================================================

class DissolveNode(QGraphicsRectItem):
    """
    溶图节点 — 默认直通，输入图原样传到输出。
    ┌─────────────────┐
    │ ● in   溶图     │
    │ ┌─────────────┐ │
    │ │  预览区域   │ │
    │ └─────────────┘ │
    │  [溶图处理]  ● out│
    └─────────────────┘
    """

    NODE_WIDTH = 200
    NODE_HEIGHT = 200

    # 状态: idle → ready → preview → confirmed
    STATE_IDLE = 'idle'
    STATE_READY = 'ready'
    STATE_PREVIEW = 'preview'
    STATE_CONFIRMED = 'confirmed'

    def __init__(self, parent=None,
                 on_moved: Optional[Callable] = None):
        super().__init__(parent)
        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)

        self._on_moved = on_moved
        self._state = self.STATE_IDLE
        self._input_pixmap: Optional[QPixmap] = None
        self._output_pixmap: Optional[QPixmap] = None
        self._btn_hovered = False
        self._btn_rect = QRectF()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(100)

    def set_input(self, pixmap: QPixmap, path: str = ''):
        """接收输入图片（默认直通）"""
        self._input_pixmap = pixmap
        # 默认直通：输入即输出
        self._output_pixmap = pixmap
        self._state = self.STATE_READY
        self.update()

    def get_output_pixmap(self) -> Optional[QPixmap]:
        """获取输出（默认直通=输入）"""
        return self._output_pixmap or self._input_pixmap

    def get_input_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(0, self.NODE_HEIGHT / 2))

    def get_output_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(self.NODE_WIDTH, self.NODE_HEIGHT / 2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._on_moved()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._btn_rect.contains(event.pos()):
                # 预留：溶图处理
                event.accept()
                return
        super().mousePressEvent(event)

    def hoverMoveEvent(self, event):
        old = self._btn_hovered
        self._btn_hovered = self._btn_rect.contains(event.pos())
        if old != self._btn_hovered:
            self.update()

    def hoverLeaveEvent(self, event):
        self._btn_hovered = False
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        is_dark = theme.is_dark()
        rect = self.rect()
        w, h = rect.width(), rect.height()

        _paint_node_frame(painter, rect, "溶图", is_dark, self.isSelected())

        # 预览区域
        preview_y = HEADER_H + 8
        preview_rect = QRectF(12, preview_y, w - 24, 100)

        display = self._output_pixmap or self._input_pixmap
        if display and not display.isNull():
            thumb = display.scaled(
                int(preview_rect.width()), int(preview_rect.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            tx = preview_rect.x() + (preview_rect.width() - thumb.width()) / 2
            ty = preview_rect.y() + (preview_rect.height() - thumb.height()) / 2
            painter.drawPixmap(int(tx), int(ty), thumb)
        else:
            painter.setPen(QPen(QColor(80, 80, 100), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(preview_rect)
            painter.setPen(QColor(100, 100, 120))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(preview_rect, Qt.AlignmentFlag.AlignCenter, "等待输入")

        # 直通标记
        if self._state == self.STATE_READY:
            pass_rect = QRectF(w - 60, preview_y + 4, 48, 16)
            pass_path = QPainterPath()
            pass_path.addRoundedRect(pass_rect, 3, 3)
            painter.fillPath(pass_path, QColor(50, 180, 100, 180))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Microsoft YaHei", 7))
            painter.drawText(pass_rect, Qt.AlignmentFlag.AlignCenter, "直通")

        # 溶图处理按钮（预留）
        btn_y = h - 36
        self._btn_rect = QRectF(12, btn_y, w - 24, 28)
        btn_bg = QColor(80, 80, 100) if not self._btn_hovered else QColor(100, 100, 120)
        btn_path = QPainterPath()
        btn_path.addRoundedRect(self._btn_rect, 5, 5)
        painter.fillPath(btn_path, btn_bg)
        painter.setPen(QColor(180, 180, 200))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(self._btn_rect, Qt.AlignmentFlag.AlignCenter, "溶图处理 (即将推出)")


# ============================================================
#  5. HDOutputNode — 高清化+输出节点（默认直通）
# ============================================================

class HDOutputNode(QGraphicsRectItem):
    """
    高清化+输出节点 — 默认直通 + 确认输出。
    ┌─────────────────────┐
    │ ● in  高清化+输出    │
    │ ┌─────────────────┐ │
    │ │  最终预览       │ │
    │ └─────────────────┘ │
    │  [高清化处理]       │
    │  ┌─────────────────┐│
    │  │  [确认输出]     ││
    │  └─────────────────┘│
    └─────────────────────┘
    """

    NODE_WIDTH = 220
    NODE_HEIGHT = 280

    def __init__(self, parent=None,
                 on_output: Optional[Callable] = None,
                 on_moved: Optional[Callable] = None):
        super().__init__(parent)
        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)

        self._on_output = on_output
        self._on_moved = on_moved

        self._input_pixmap: Optional[QPixmap] = None
        self._output_pixmap: Optional[QPixmap] = None
        self._output_path: str = ''

        self._hd_btn_hovered = False
        self._output_btn_hovered = False
        self._hd_btn_rect = QRectF()
        self._output_btn_rect = QRectF()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(100)

    def set_input(self, pixmap: QPixmap, path: str = ''):
        """接收输入图片（默认直通）"""
        self._input_pixmap = pixmap
        self._output_pixmap = pixmap  # 默认直通
        self._output_path = path
        self.update()

    def get_output_path(self) -> str:
        return self._output_path

    def get_input_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(0, self.NODE_HEIGHT / 2))

    def get_output_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(self.NODE_WIDTH, self.NODE_HEIGHT / 2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._on_moved()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            if self._output_btn_rect.contains(pos):
                if self._on_output:
                    self._on_output()
                event.accept()
                return
            if self._hd_btn_rect.contains(pos):
                # 预留：高清化处理
                event.accept()
                return
        super().mousePressEvent(event)

    def hoverMoveEvent(self, event):
        pos = event.pos()
        old_h = self._hd_btn_hovered
        old_o = self._output_btn_hovered
        self._hd_btn_hovered = self._hd_btn_rect.contains(pos)
        self._output_btn_hovered = self._output_btn_rect.contains(pos)
        if old_h != self._hd_btn_hovered or old_o != self._output_btn_hovered:
            self.update()

    def hoverLeaveEvent(self, event):
        self._hd_btn_hovered = False
        self._output_btn_hovered = False
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        is_dark = theme.is_dark()
        rect = self.rect()
        w, h = rect.width(), rect.height()

        _paint_node_frame(painter, rect, "高清化+输出", is_dark, self.isSelected())

        # 预览区域
        preview_y = HEADER_H + 8
        preview_rect = QRectF(12, preview_y, w - 24, 120)

        display = self._output_pixmap or self._input_pixmap
        if display and not display.isNull():
            thumb = display.scaled(
                int(preview_rect.width()), int(preview_rect.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            tx = preview_rect.x() + (preview_rect.width() - thumb.width()) / 2
            ty = preview_rect.y() + (preview_rect.height() - thumb.height()) / 2
            painter.drawPixmap(int(tx), int(ty), thumb)

            # 直通标记
            pass_rect = QRectF(w - 60, preview_y + 4, 48, 16)
            pass_path = QPainterPath()
            pass_path.addRoundedRect(pass_rect, 3, 3)
            painter.fillPath(pass_path, QColor(50, 180, 100, 180))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Microsoft YaHei", 7))
            painter.drawText(pass_rect, Qt.AlignmentFlag.AlignCenter, "直通")
        else:
            painter.setPen(QPen(QColor(80, 80, 100), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(preview_rect)
            painter.setPen(QColor(100, 100, 120))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(preview_rect, Qt.AlignmentFlag.AlignCenter, "等待输入")

        # 高清化按钮（预留）
        hd_y = preview_y + 120 + 12
        self._hd_btn_rect = QRectF(12, hd_y, w - 24, 32)
        hd_bg = QColor(80, 80, 100) if not self._hd_btn_hovered else QColor(100, 100, 120)
        hd_path = QPainterPath()
        hd_path.addRoundedRect(self._hd_btn_rect, 5, 5)
        painter.fillPath(hd_path, hd_bg)
        painter.setPen(QColor(180, 180, 200))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(self._hd_btn_rect, Qt.AlignmentFlag.AlignCenter,
                         "高清化处理 (即将推出)")

        # 确认输出按钮
        self._output_btn_rect = QRectF(12, h - 48, w - 24, 40)
        out_color = COLOR_GREEN.lighter(120) if self._output_btn_hovered else COLOR_GREEN
        out_path = QPainterPath()
        out_path.addRoundedRect(self._output_btn_rect, 6, 6)
        painter.fillPath(out_path, out_color)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(self._output_btn_rect, Qt.AlignmentFlag.AlignCenter,
                         "确认输出")
