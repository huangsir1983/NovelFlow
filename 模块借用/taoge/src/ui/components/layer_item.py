"""
涛割 - 图层 QGraphicsItem + 变换手柄
"""

from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QGraphicsPixmapItem, QGraphicsEllipseItem, QGraphicsItem,
    QStyleOptionGraphicsItem, QWidget,
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QBrush, QColor, QTransform,
    QCursor, QFont, QPainterPath,
)

from ui import theme


class TransformHandle(QGraphicsEllipseItem):
    """变换控制手柄（8 个缩放 + 1 个旋转）"""

    HANDLE_SIZE = 14       # 可视圆点直径
    HIT_AREA_SIZE = 28     # 可点击热区直径（比可视区域大一圈，方便点击）

    # handle_type: tl/tc/tr/ml/mr/bl/bc/br/rotate
    CURSORS = {
        'tl': Qt.CursorShape.SizeFDiagCursor,
        'tr': Qt.CursorShape.SizeBDiagCursor,
        'bl': Qt.CursorShape.SizeBDiagCursor,
        'br': Qt.CursorShape.SizeFDiagCursor,
        'tc': Qt.CursorShape.SizeVerCursor,
        'bc': Qt.CursorShape.SizeVerCursor,
        'ml': Qt.CursorShape.SizeHorCursor,
        'mr': Qt.CursorShape.SizeHorCursor,
        'rotate': Qt.CursorShape.CrossCursor,
    }

    def __init__(self, handle_type: str, parent_layer: 'LayerItem'):
        s = self.HANDLE_SIZE
        super().__init__(-s / 2, -s / 2, s, s, parent_layer)
        self._handle_type = handle_type
        self._parent_layer = parent_layer
        self._drag_start: Optional[QPointF] = None
        self._initial_rect: Optional[QRectF] = None
        self._initial_transform: Optional[dict] = None

        self.setBrush(QBrush(QColor(255, 255, 255)))
        self.setPen(QPen(QColor(theme.accent()), 1.5))
        self.setCursor(QCursor(self.CURSORS.get(handle_type, Qt.CursorShape.ArrowCursor)))
        self.setZValue(1000)
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        """扩大碰撞检测区域，让手柄更容易点到"""
        h = self.HIT_AREA_SIZE
        return QRectF(-h / 2, -h / 2, h, h)

    def shape(self) -> QPainterPath:
        """扩大可点击热区为 HIT_AREA_SIZE 的圆形"""
        path = QPainterPath()
        h = self.HIT_AREA_SIZE
        path.addEllipse(-h / 2, -h / 2, h, h)
        return path

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.scenePos()
            self._initial_rect = self._parent_layer.boundingRect()
            self._initial_transform = self._parent_layer.get_transform()
            event.accept()
        else:
            super().mousePressEvent(event)

    # 旋转磁吸角度和阈值
    SNAP_ANGLES = [0, 90, 180, 270, 360]
    SNAP_THRESHOLD = 5  # 度

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            return

        delta = event.scenePos() - self._drag_start
        t = self._initial_transform
        shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        if self._handle_type == 'rotate':
            # 旋转：以图层中心为原点，计算角度差
            center = self._parent_layer.mapToScene(
                self._parent_layer.boundingRect().center()
            )
            import math
            start_angle = math.atan2(
                self._drag_start.y() - center.y(),
                self._drag_start.x() - center.x()
            )
            cur_angle = math.atan2(
                event.scenePos().y() - center.y(),
                event.scenePos().x() - center.x()
            )
            angle_delta = math.degrees(cur_angle - start_angle)
            new_rotation = t.get('rotation', 0) + angle_delta

            # 磁吸到 0/90/180/270/360 度
            normalized = new_rotation % 360
            if normalized < 0:
                normalized += 360
            for snap in self.SNAP_ANGLES:
                if abs(normalized - snap) <= self.SNAP_THRESHOLD:
                    new_rotation = new_rotation - normalized + snap
                    break

            self._parent_layer.setRotation(new_rotation)
        else:
            # 缩放：根据手柄方向计算缩放比
            sx = t.get('scale_x', 1.0)
            sy = t.get('scale_y', 1.0)
            rect = self._initial_rect
            w = max(rect.width(), 1)
            h = max(rect.height(), 1)

            if 'r' in self._handle_type:
                sx = max(0.1, sx + delta.x() / w)
            elif 'l' in self._handle_type:
                sx = max(0.1, sx - delta.x() / w)

            if 'b' in self._handle_type:
                sy = max(0.1, sy + delta.y() / h)
            elif 't' in self._handle_type:
                sy = max(0.1, sy - delta.y() / h)

            # 角手柄默认等比例缩放，按住 Shift 解锁自由缩放
            is_corner = self._handle_type in ('tl', 'tr', 'bl', 'br')
            if is_corner and not shift_held:
                # 等比例：取较大变化量作为统一缩放比
                ratio = max(sx, sy)
                sx = ratio
                sy = ratio

            # 围绕图片中心进行缩放
            transform = QTransform()
            pm = self._parent_layer.pixmap()
            if pm and not pm.isNull():
                cx = pm.width() / 2
                cy = pm.height() / 2
                transform.translate(cx, cy)
                transform.scale(sx, sy)
                transform.translate(-cx, -cy)
            else:
                transform.scale(sx, sy)
            self._parent_layer.setTransform(transform)

        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_start is not None:
            self._drag_start = None
            # 通知父图层变换已更改
            self._parent_layer._emit_transform_changed()
        event.accept()


class LayerItem(QGraphicsPixmapItem):
    """单个图层 - 支持移动/旋转/缩放/选中"""

    def __init__(self, layer_data: dict, canvas_view=None, parent=None):
        super().__init__(parent)
        self._data = layer_data
        self._canvas_view = canvas_view
        self._handles: List[TransformHandle] = []
        self._is_selected = False

        self.layer_id: int = layer_data.get('id', 0)
        self.layer_type: str = layer_data.get('layer_type', 'background')
        self.is_locked: bool = layer_data.get('is_locked', False)
        self.is_visible: bool = layer_data.get('is_visible', True)
        self.is_reference: bool = layer_data.get('is_reference', False)

        # 加载图片
        image_path = layer_data.get('image_path')
        if image_path:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self.setPixmap(pixmap)
                # 旋转围绕图片中心
                self.setTransformOriginPoint(
                    pixmap.width() / 2, pixmap.height() / 2
                )

        # 设置交互标志
        if not self.is_locked:
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # 洋葱皮参考层半透明
        if self.is_reference:
            self.setOpacity(0.3)
        else:
            # 应用保存的透明度
            opacity = layer_data.get('opacity', 1.0)
            if opacity < 1.0:
                self.setOpacity(opacity)

        # 应用保存的变换
        self.apply_transform(layer_data.get('transform') or {})

    def apply_transform(self, transform: dict):
        """应用变换参数 {x, y, rotation, scale_x, scale_y, flip_h, flip_v}"""
        # 确保旋转围绕图片中心
        pm = self.pixmap()
        if pm and not pm.isNull():
            cx = pm.width() / 2
            cy = pm.height() / 2
            self.setTransformOriginPoint(cx, cy)

        x = transform.get('x', 0)
        y = transform.get('y', 0)
        self.setPos(x, y)

        rotation = transform.get('rotation', 0)
        self.setRotation(rotation)

        sx = transform.get('scale_x', 1.0)
        sy = transform.get('scale_y', 1.0)
        flip_h = transform.get('flip_h', False)
        flip_v = transform.get('flip_v', False)

        if flip_h:
            sx = -abs(sx)
        if flip_v:
            sy = -abs(sy)

        # 围绕图片中心进行缩放/镜像
        t = QTransform()
        if pm and not pm.isNull():
            cx = pm.width() / 2
            cy = pm.height() / 2
            t.translate(cx, cy)
            t.scale(sx, sy)
            t.translate(-cx, -cy)
        else:
            t.scale(sx, sy)
        self.setTransform(t)

    def get_transform(self) -> dict:
        """导出当前变换参数"""
        pos = self.pos()
        t = self.transform()

        # 从围绕中心的变换矩阵中提取缩放因子
        # 矩阵结构: translate(cx,cy) * scale(sx,sy) * translate(-cx,-cy)
        # 展开后: m11=sx, m22=sy, m31=cx*(1-sx), m32=cy*(1-sy)
        # 所以 sx=m11(), sy=m22() 依然成立
        sx = t.m11()
        sy = t.m22()

        return {
            'x': pos.x(),
            'y': pos.y(),
            'rotation': self.rotation(),
            'scale_x': abs(sx),
            'scale_y': abs(sy),
            'flip_h': sx < 0,
            'flip_v': sy < 0,
        }

    def set_flip_h(self, flip: bool):
        t = self.get_transform()
        t['flip_h'] = flip
        self.apply_transform(t)
        self._emit_transform_changed()

    def set_flip_v(self, flip: bool):
        t = self.get_transform()
        t['flip_v'] = flip
        self.apply_transform(t)
        self._emit_transform_changed()

    def update_pixmap(self, pixmap: QPixmap):
        """设置新 pixmap + 重设旋转中心 + 更新手柄位置"""
        self.setPixmap(pixmap)
        if not pixmap.isNull():
            self.setTransformOriginPoint(
                pixmap.width() / 2, pixmap.height() / 2
            )
        if self._is_selected:
            self._position_handles()

    # === 混合模式 & 透明度 ===

    @property
    def blend_mode(self) -> str:
        return self._data.get('blend_mode', 'normal')

    @blend_mode.setter
    def blend_mode(self, mode: str):
        self._data['blend_mode'] = mode
        self.update()

    @property
    def layer_opacity(self) -> float:
        return self._data.get('opacity', 1.0)

    @layer_opacity.setter
    def layer_opacity(self, value: float):
        self._data['opacity'] = max(0.0, min(1.0, value))
        self.setOpacity(self._data['opacity'])

    def set_layer_selected(self, selected: bool):
        """设置选中状态，显示/隐藏手柄"""
        self._is_selected = selected
        if selected:
            self._create_handles()
        else:
            self._remove_handles()
        self.update()

    def _create_handles(self):
        """创建 8 个缩放手柄 + 1 个旋转手柄"""
        self._remove_handles()

        handle_types = ['tl', 'tc', 'tr', 'ml', 'mr', 'bl', 'bc', 'br', 'rotate']
        for ht in handle_types:
            handle = TransformHandle(ht, self)
            self._handles.append(handle)

        self._position_handles()

    def _remove_handles(self):
        for h in self._handles:
            if h.scene():
                h.scene().removeItem(h)
        self._handles.clear()

    def _position_handles(self):
        """根据当前 boundingRect 定位手柄"""
        rect = self.boundingRect()
        positions = {
            'tl': rect.topLeft(),
            'tc': QPointF(rect.center().x(), rect.top()),
            'tr': rect.topRight(),
            'ml': QPointF(rect.left(), rect.center().y()),
            'mr': QPointF(rect.right(), rect.center().y()),
            'bl': rect.bottomLeft(),
            'bc': QPointF(rect.center().x(), rect.bottom()),
            'br': rect.bottomRight(),
            'rotate': QPointF(rect.center().x(), rect.top() - 30),
        }
        for h in self._handles:
            pos = positions.get(h._handle_type)
            if pos:
                h.setPos(pos)

    # 混合模式映射
    BLEND_MODES = {
        'normal': QPainter.CompositionMode.CompositionMode_SourceOver,
        'multiply': QPainter.CompositionMode.CompositionMode_Multiply,
        'screen': QPainter.CompositionMode.CompositionMode_Screen,
        'overlay': QPainter.CompositionMode.CompositionMode_Overlay,
        'darken': QPainter.CompositionMode.CompositionMode_Darken,
        'lighten': QPainter.CompositionMode.CompositionMode_Lighten,
        'color_dodge': QPainter.CompositionMode.CompositionMode_ColorDodge,
        'color_burn': QPainter.CompositionMode.CompositionMode_ColorBurn,
        'soft_light': QPainter.CompositionMode.CompositionMode_SoftLight,
        'difference': QPainter.CompositionMode.CompositionMode_Difference,
    }

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        # 应用混合模式
        mode = self.BLEND_MODES.get(
            self.blend_mode, QPainter.CompositionMode.CompositionMode_SourceOver
        )
        painter.setCompositionMode(mode)

        # 将 pixmap 绘制区域裁剪到画框范围内（类似 PS 画板裁剪）
        # 画框外只显示选中边框/手柄，不显示图片像素
        frame = self.parentItem()
        clipped = False
        if frame is not None and hasattr(frame, 'rect'):
            frame_polygon = self.mapFromItem(frame, frame.rect())
            clip_path = QPainterPath()
            clip_path.addPolygon(frame_polygon)
            painter.save()
            painter.setClipPath(clip_path)
            clipped = True

        super().paint(painter, option, widget)

        if clipped:
            painter.restore()

        # 恢复默认混合模式
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        if self._is_selected:
            # 选中时绘制虚线边框（不受画框裁剪，画框外也可见）
            rect = self.boundingRect()
            painter.setPen(QPen(QColor(theme.accent()), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            # 旋转手柄连线
            center_top = QPointF(rect.center().x(), rect.top())
            rotate_pos = QPointF(rect.center().x(), rect.top() - 30)
            painter.setPen(QPen(QColor(theme.accent()), 1))
            painter.drawLine(center_top, rotate_pos)

    def mousePressEvent(self, event):
        if self.is_locked:
            event.ignore()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # 通知画布选中了这个图层
            if self._canvas_view:
                ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                if ctrl_held:
                    self._canvas_view.toggle_layer_selection(self.layer_id)
                else:
                    self._canvas_view.select_layer(self.layer_id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # ItemIsMovable 的 super() 会处理实际位移，之后更新手柄位置
        self._position_handles()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._emit_transform_changed()
        self._position_handles()

    def _emit_transform_changed(self):
        """发出变换变化信号"""
        if self._canvas_view:
            self._canvas_view.layer_transform_changed.emit(
                self.layer_id, self.get_transform()
            )
