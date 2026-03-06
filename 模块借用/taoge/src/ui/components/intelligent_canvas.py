"""
涛割 - 智能画布核心视图 + 连贯性微观工具
全屏多层编辑环境
"""

from typing import Optional, List, Dict, Any, Set

from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsPathItem, QGraphicsEllipseItem,
    QGraphicsRectItem, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QPixmap, QTransform, QAction,
)

from ui import theme
from ui.components.base_canvas_view import BaseCanvasView
from ui.components.layer_item import LayerItem
from ui.components.selection_tools import (
    MagicWandTool, LassoTool, SelectionOverlay,
)


# ============================================================
#  连贯性微观工具
# ============================================================

class EyeFocusCrosshair(QGraphicsItem):
    """视线落点十字准星"""

    SIZE = 30

    def __init__(self, pos: QPointF = None, parent=None):
        super().__init__(parent)
        self._color = QColor(255, 80, 80, 180)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(500)
        self.setCursor(Qt.CursorShape.CrossCursor)
        if pos:
            self.setPos(pos)

    def boundingRect(self) -> QRectF:
        s = self.SIZE
        return QRectF(-s, -s, s * 2, s * 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.SIZE

        # 十字线
        pen = QPen(self._color, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(-s, 0), QPointF(s, 0))
        painter.drawLine(QPointF(0, -s), QPointF(0, s))

        # 中心圆
        painter.setPen(QPen(self._color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), 6, 6)

        # 中心点
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(QPointF(0, 0), 2, 2)

    def get_focus_data(self) -> dict:
        pos = self.pos()
        return {'x': pos.x(), 'y': pos.y()}


class MotionVectorGuide(QGraphicsPathItem):
    """动势引导线 - 带箭头的贝塞尔曲线"""

    def __init__(self, start: QPointF, end: QPointF, parent=None):
        super().__init__(parent)
        self._start = start
        self._end = end
        self._is_ghost = False  # 幽灵层（从上一镜继承）

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setZValue(400)
        self._rebuild_path()

    def set_ghost(self, ghost: bool):
        self._is_ghost = ghost
        self._rebuild_path()

    def _rebuild_path(self):
        path = QPainterPath()
        path.moveTo(self._start)

        # 贝塞尔曲线
        dx = self._end.x() - self._start.x()
        dy = self._end.y() - self._start.y()
        cp1 = QPointF(self._start.x() + dx * 0.3, self._start.y())
        cp2 = QPointF(self._end.x() - dx * 0.3, self._end.y())
        path.cubicTo(cp1, cp2, self._end)

        self.setPath(path)

        # 样式
        if self._is_ghost:
            pen = QPen(QColor(100, 200, 255, 60), 2, Qt.PenStyle.DashLine)
        else:
            pen = QPen(QColor(100, 200, 255, 200), 2.5)
        self.setPen(pen)

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)

        # 画箭头
        import math
        path = self.path()
        if path.isEmpty():
            return

        percent = path.percentAtLength(path.length())
        end_pt = path.pointAtPercent(min(0.98, percent))
        tangent_pt = path.pointAtPercent(min(0.95, percent))

        angle = math.atan2(
            self._end.y() - tangent_pt.y(),
            self._end.x() - tangent_pt.x()
        )
        arrow_size = 10
        p1 = QPointF(
            self._end.x() - arrow_size * math.cos(angle - math.pi / 6),
            self._end.y() - arrow_size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            self._end.x() - arrow_size * math.cos(angle + math.pi / 6),
            self._end.y() - arrow_size * math.sin(angle + math.pi / 6),
        )

        arrow_path = QPainterPath()
        arrow_path.moveTo(self._end)
        arrow_path.lineTo(p1)
        arrow_path.lineTo(p2)
        arrow_path.closeSubpath()

        color = QColor(100, 200, 255, 60 if self._is_ghost else 200)
        painter.fillPath(arrow_path, QBrush(color))

    def get_vector_data(self) -> dict:
        return {
            'x1': self._start.x(), 'y1': self._start.y(),
            'x2': self._end.x(), 'y2': self._end.y(),
        }


# ============================================================
#  CanvasFrame — 画框（图层裁剪容器）
# ============================================================

class CanvasFrame(QGraphicsRectItem):
    """
    画框容器 — 类似 PS 的画板边界。
    所有 LayerItem 作为子项添加。
    不使用 ItemClipsChildrenToShape（使画框外图层仍可选中/拖拽），
    像素裁剪由 LayerItem.paint() 内部手动 setClipPath 实现。
    """

    DEFAULT_W = 1920
    DEFAULT_H = 1080

    def __init__(self, w: float = DEFAULT_W, h: float = DEFAULT_H, parent=None):
        super().__init__(0, 0, w, h, parent)
        # 不裁剪子项 — 超出画框的图层仍可见可选
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, False)
        self.setPen(QPen(QColor(100, 100, 100, 180), 1))
        self.setBrush(QBrush(QColor(30, 30, 30)))  # 画框内背景
        self.setZValue(-10)

    def resize_frame(self, w: float, h: float):
        self.setRect(0, 0, w, h)


# ============================================================
#  IntelligentCanvasView — 智能画布核心视图
# ============================================================

class IntelligentCanvasView(BaseCanvasView):
    """智能画布 - 全屏多层编辑环境"""

    # 信号
    layer_selected = pyqtSignal(int)              # layer_id
    layer_transform_changed = pyqtSignal(int, dict)  # layer_id, transform
    canvas_saved = pyqtSignal(int)                # scene_id
    generate_layer_requested = pyqtSignal(int, str)  # layer_id, prompt
    layer_context_menu_requested = pyqtSignal(int, object)  # layer_id, QPoint(global)
    multi_selection_changed = pyqtSignal(list)    # [layer_id, ...]

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self._data_hub = data_hub
        self._scene_id: Optional[int] = None
        self._layer_items: Dict[int, LayerItem] = {}  # layer_id → LayerItem
        self._selected_layer_id: Optional[int] = None
        self._selected_layer_ids: Set[int] = set()  # Ctrl+多选

        # 画框（图层裁剪容器）
        self._canvas_frame = CanvasFrame()
        self._canvas_scene.addItem(self._canvas_frame)

        # 连贯性工具
        self._eye_focus: Optional[EyeFocusCrosshair] = None
        self._motion_vectors: List[MotionVectorGuide] = []
        self._continuity_enabled = False
        self._onion_item: Optional[LayerItem] = None

        # 工具模式
        self._current_tool: str = 'select'
        self._magic_wand = MagicWandTool()
        self._lasso = LassoTool()
        self._selection_overlay: Optional[SelectionOverlay] = None
        self._current_mask: Optional[Any] = None  # QImage 蒙版
        self._is_lasso_drawing = False

        # 画笔工具
        self._brush_color = QColor(255, 0, 0)   # 默认红色
        self._brush_size = 5                      # 默认 5px
        self._is_brush_drawing = False            # 是否正在画笔绘制
        self._brush_path: Optional[QPainterPath] = None  # 当前笔画路径
        self._brush_preview_item: Optional[QGraphicsPathItem] = None  # 实时预览
        self._brush_target_layer: Optional[LayerItem] = None  # 绘制目标图层

    # === 场景加载 ===

    def load_scene(self, scene_id: int):
        """加载场景所有层"""
        self._scene_id = scene_id
        self.clear_all()

        if not self._data_hub:
            return

        from services.layer_service import LayerService
        service = LayerService()
        layers = service.get_scene_layers(scene_id)

        self._build_layer_items(layers)

        # 加载连贯性数据
        self._load_continuity_data(scene_id)

    def save_scene(self):
        """保存所有层变换到 DB"""
        if not self._scene_id:
            return

        from services.layer_service import LayerService
        service = LayerService()

        for layer_id, item in self._layer_items.items():
            transform = item.get_transform()
            service.save_layer({
                'id': layer_id,
                'transform': transform,
            })

        # 保存连贯性数据
        self._save_continuity_data()

        self.canvas_saved.emit(self._scene_id)

    def export_composite_image(self) -> str:
        """将画框内所有可见图层合成为一张 PNG 导出"""
        import os
        import time

        if not self._scene_id:
            return ""

        # 获取画框区域
        frame_rect = self._canvas_frame.rect()
        if frame_rect.width() <= 0 or frame_rect.height() <= 0:
            return ""

        # 渲染到 QImage
        from PyQt6.QtGui import QImage
        w = int(frame_rect.width())
        h = int(frame_rect.height())
        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 渲染画框内容（场景坐标映射到画框区域）
        source_rect = self._canvas_frame.mapRectToScene(frame_rect)
        self._canvas_scene.render(
            painter,
            QRectF(0, 0, w, h),
            source_rect,
        )
        painter.end()

        # 保存路径
        project_id = 0
        try:
            from database.session import session_scope
            from database.models import Scene
            with session_scope() as session:
                scene = session.query(Scene).filter(
                    Scene.id == self._scene_id).first()
                if scene:
                    project_id = scene.project_id
        except Exception:
            pass

        output_dir = os.path.join('generated', str(project_id), 'composites')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir,
            f"scene_{self._scene_id}_{int(time.time())}.png"
        )
        image.save(output_path, "PNG")
        self._export_path = output_path
        return output_path

    def clear_all(self):
        """清空所有图层（保留画框）"""
        for item in self._layer_items.values():
            if item.scene():
                self._canvas_scene.removeItem(item)
        self._layer_items.clear()
        self._selected_layer_id = None
        self._selected_layer_ids.clear()

        # 清除连贯性工具
        if self._eye_focus and self._eye_focus.scene():
            self._canvas_scene.removeItem(self._eye_focus)
        self._eye_focus = None

        for mv in self._motion_vectors:
            if mv.scene():
                self._canvas_scene.removeItem(mv)
        self._motion_vectors.clear()

        if self._onion_item and self._onion_item.scene():
            self._canvas_scene.removeItem(self._onion_item)
        self._onion_item = None

        # 确保画框存在
        if not self._canvas_frame.scene():
            self._canvas_scene.addItem(self._canvas_frame)

    # === 图层管理 ===

    def add_layer(self, layer_data: dict) -> LayerItem:
        """添加图层到画布（作为画框子项，自动裁剪）"""
        item = LayerItem(layer_data, canvas_view=self)
        item.setParentItem(self._canvas_frame)
        self._layer_items[layer_data['id']] = item
        return item

    def remove_layer(self, layer_id: int):
        item = self._layer_items.pop(layer_id, None)
        if item and item.scene():
            self._canvas_scene.removeItem(item)

    def reorder_layers(self, layer_ids: List[int]):
        """根据 layer_ids 顺序设置 z_order"""
        for z, lid in enumerate(layer_ids):
            item = self._layer_items.get(lid)
            if item:
                item.setZValue(z)

    def select_layer(self, layer_id: int):
        # 取消之前所有选中
        for lid in self._selected_layer_ids:
            if lid in self._layer_items:
                self._layer_items[lid].set_layer_selected(False)

        self._selected_layer_id = layer_id
        self._selected_layer_ids = {layer_id}
        if layer_id in self._layer_items:
            self._layer_items[layer_id].set_layer_selected(True)
        self.layer_selected.emit(layer_id)
        self.multi_selection_changed.emit(list(self._selected_layer_ids))

    def toggle_layer_selection(self, layer_id: int):
        """Ctrl+点击：切换图层的多选状态"""
        if layer_id in self._selected_layer_ids:
            # 取消选中
            self._selected_layer_ids.discard(layer_id)
            if layer_id in self._layer_items:
                self._layer_items[layer_id].set_layer_selected(False)
        else:
            # 添加到选中集
            self._selected_layer_ids.add(layer_id)
            if layer_id in self._layer_items:
                self._layer_items[layer_id].set_layer_selected(True)

        # 更新主选中 ID
        self._selected_layer_id = layer_id if layer_id in self._selected_layer_ids else (
            next(iter(self._selected_layer_ids)) if self._selected_layer_ids else None
        )
        self.layer_selected.emit(layer_id)
        self.multi_selection_changed.emit(list(self._selected_layer_ids))

    def get_selected_layer_ids(self) -> List[int]:
        return list(self._selected_layer_ids)

    # === AI 操作 ===

    def ai_auto_layer(self):
        """AI 自动分层"""
        if not self._scene_id:
            return

        from services.layer_service import AILayeringWorker
        # 获取当前场景的生成图片
        from database.session import session_scope
        from database.models import Scene
        with session_scope() as session:
            scene = session.query(Scene).filter(Scene.id == self._scene_id).first()
            if not scene or not scene.generated_image_path:
                return
            image_path = scene.generated_image_path

        self._layering_worker = AILayeringWorker(self._scene_id, image_path)
        self._layering_worker.layering_completed.connect(self._on_layering_completed)
        self._layering_worker.layering_failed.connect(self._on_layering_failed)
        self._layering_worker.start()

    def _on_layering_completed(self, layers: list):
        """AI 分层完成"""
        self.clear_all()
        self._build_layer_items(layers)

    def _on_layering_failed(self, error: str):
        print(f"AI 分层失败: {error}")

    def ai_redraw_layer(self, layer_id: int, prompt: str):
        """单层 AI 重绘"""
        self.generate_layer_requested.emit(layer_id, prompt)

    # === 洋葱皮 ===

    def load_onion_skin(self, prev_scene_id: int):
        """加载上一镜图片作为洋葱皮参考"""
        if self._onion_item and self._onion_item.scene():
            self._canvas_scene.removeItem(self._onion_item)
            self._onion_item = None

        from database.session import session_scope
        from database.models import Scene
        with session_scope() as session:
            prev = session.query(Scene).filter(Scene.id == prev_scene_id).first()
            if not prev or not prev.generated_image_path:
                return

            onion_data = {
                'id': -1,
                'layer_type': 'reference',
                'is_reference': True,
                'image_path': prev.generated_image_path,
                'transform': {},
            }
            self._onion_item = LayerItem(onion_data, canvas_view=None)
            self._onion_item.is_locked = True
            self._onion_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            self._onion_item.setZValue(-100)
            self._onion_item.setParentItem(self._canvas_frame)

    def set_onion_opacity(self, opacity: float):
        if self._onion_item:
            self._onion_item.setOpacity(opacity / 100.0)

    # === 连贯性辅助 ===

    def toggle_continuity_tools(self, enabled: bool):
        self._continuity_enabled = enabled
        if self._eye_focus:
            self._eye_focus.setVisible(enabled)
        for mv in self._motion_vectors:
            mv.setVisible(enabled)

    def set_eye_focus(self, pos: QPointF):
        if self._eye_focus:
            self._eye_focus.setPos(pos)
        else:
            self._eye_focus = EyeFocusCrosshair(pos)
            self._canvas_scene.addItem(self._eye_focus)
            self._eye_focus.setVisible(self._continuity_enabled)

    def add_motion_vector(self, start: QPointF, end: QPointF):
        guide = MotionVectorGuide(start, end)
        self._canvas_scene.addItem(guide)
        guide.setVisible(self._continuity_enabled)
        self._motion_vectors.append(guide)

    # === 工具模式 ===

    def set_tool(self, tool_name: str):
        """切换工具模式"""
        self._current_tool = tool_name
        self._clear_selection()

        if tool_name in ('select', 'move', 'rotate', 'scale'):
            self.setCursor(Qt.CursorShape.ArrowCursor)
            # 启用图层交互
            for item in self._layer_items.values():
                if not item.is_locked:
                    item.setFlag(item.GraphicsItemFlag.ItemIsMovable, tool_name == 'move')
        elif tool_name == 'magic_wand':
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool_name == 'lasso':
            self.setCursor(Qt.CursorShape.CrossCursor)
            self._lasso.reset()
        elif tool_name == 'brush':
            self.setCursor(Qt.CursorShape.CrossCursor)
            self._is_brush_drawing = False

    def _clear_selection(self):
        """清除当前选区"""
        if self._selection_overlay:
            self._selection_overlay.remove()
            self._selection_overlay = None
        self._current_mask = None
        self._is_lasso_drawing = False
        self._lasso.reset()

    def contextMenuEvent(self, event):
        """右键菜单被 BaseCanvasView 拦截，此处作为后备"""
        scene_pos = self.mapToScene(event.pos())
        layer_item = self._find_layer_at(scene_pos)
        if layer_item:
            self.select_layer(layer_item.layer_id)
            self.layer_context_menu_requested.emit(
                layer_item.layer_id, event.globalPos()
            )
            event.accept()
            return
        super().contextMenuEvent(event)

    def mouseReleaseEvent(self, event):
        """右键释放且未拖动 → 弹出图层右键菜单"""
        if (event.button() == Qt.MouseButton.RightButton
                and hasattr(self, '_pan_moved') and not self._pan_moved):
            scene_pos = self.mapToScene(event.position().toPoint())
            layer_item = self._find_layer_at(scene_pos)
            if layer_item:
                self.select_layer(layer_item.layer_id)
                self.layer_context_menu_requested.emit(
                    layer_item.layer_id, event.globalPosition().toPoint()
                )
                self._is_panning = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._current_tool == 'magic_wand':
                self._handle_magic_wand_click(event)
                return
            elif self._current_tool == 'lasso':
                self._handle_lasso_start(event)
                return
            elif self._current_tool == 'brush':
                self._handle_brush_start(event)
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_brush_drawing:
            self._handle_brush_move(event)
            return
        if self._is_lasso_drawing:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._lasso.add_point(scene_pos)
            # 实时绘制套索路径
            self._update_lasso_preview()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_brush_drawing and event.button() == Qt.MouseButton.LeftButton:
            self._handle_brush_end()
            return
        if self._is_lasso_drawing and event.button() == Qt.MouseButton.LeftButton:
            self._handle_lasso_end()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self._current_mask is not None:
            self._delete_selection()
            return
        # 工具快捷键
        key_tool_map = {
            Qt.Key.Key_V: 'select',
            Qt.Key.Key_G: 'move',
            Qt.Key.Key_R: 'rotate',
            Qt.Key.Key_S: 'scale',
            Qt.Key.Key_W: 'magic_wand',
            Qt.Key.Key_L: 'lasso',
            Qt.Key.Key_B: 'brush',
        }
        tool = key_tool_map.get(event.key())
        if tool:
            self.set_tool(tool)
            return
        super().keyPressEvent(event)

    def _handle_magic_wand_click(self, event):
        """魔棒点击 — flood fill 选区"""
        scene_pos = self.mapToScene(event.position().toPoint())

        # 找到点击位置的图层
        layer_item = self._find_layer_at(scene_pos)
        if not layer_item:
            self._clear_selection()
            return

        # 转换为图层本地坐标
        local_pos = layer_item.mapFromScene(scene_pos)

        mask = self._magic_wand.select_at(layer_item, local_pos)
        if mask is None:
            return

        self._current_mask = mask
        self._show_mask_selection(layer_item, mask)

    def _handle_lasso_start(self, event):
        """套索开始"""
        self._clear_selection()
        self._is_lasso_drawing = True
        scene_pos = self.mapToScene(event.position().toPoint())
        self._lasso.reset()
        self._lasso.add_point(scene_pos)

    def _handle_lasso_end(self):
        """套索结束 — 闭合路径"""
        self._is_lasso_drawing = False
        path = self._lasso.close_path()
        if path is None:
            self._clear_selection()
            return

        # 显示选区
        if self._selection_overlay:
            self._selection_overlay.remove()
        self._selection_overlay = SelectionOverlay(path)
        self._canvas_scene.addItem(self._selection_overlay)

        # 生成蒙版
        layer_item = self._get_selected_layer_item()
        if layer_item:
            # 转换路径到图层本地坐标
            local_path = layer_item.mapFromScene(path)
            mask = self._lasso.make_mask(layer_item, local_path)
            self._current_mask = mask

    def _update_lasso_preview(self):
        """实时绘制套索路径预览"""
        if self._selection_overlay:
            self._selection_overlay.remove()

        path = QPainterPath()
        points = self._lasso._points
        if len(points) < 2:
            return
        path.moveTo(points[0])
        for pt in points[1:]:
            path.lineTo(pt)

        self._selection_overlay = SelectionOverlay(path)
        self._canvas_scene.addItem(self._selection_overlay)

    # === 画笔工具 ===

    def set_brush_color(self, color: QColor):
        self._brush_color = color

    def set_brush_size(self, size: int):
        self._brush_size = max(1, min(50, size))

    def _handle_brush_start(self, event):
        """画笔按下 — 找到目标图层，开始路径"""
        scene_pos = self.mapToScene(event.position().toPoint())

        # 优先在选中图层上绘制
        layer = self._get_selected_layer_item()
        if not layer:
            layer = self._find_layer_at(scene_pos)
        if not layer or layer.is_locked:
            return

        self._brush_target_layer = layer
        self._is_brush_drawing = True

        # 转换为图层本地坐标
        local_pos = layer.mapFromScene(scene_pos)

        # 创建路径
        self._brush_path = QPainterPath()
        self._brush_path.moveTo(local_pos)

        # 创建实时预览 item（作为图层子项，跟随图层变换）
        self._brush_preview_item = QGraphicsPathItem(layer)
        pen = QPen(self._brush_color, self._brush_size,
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)
        self._brush_preview_item.setPen(pen)
        self._brush_preview_item.setZValue(999)

        event.accept()

    def _handle_brush_move(self, event):
        """画笔拖动 — 追加路径点 + 更新预览"""
        if not self._brush_target_layer or not self._brush_path:
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        local_pos = self._brush_target_layer.mapFromScene(scene_pos)
        self._brush_path.lineTo(local_pos)
        self._brush_preview_item.setPath(self._brush_path)
        event.accept()

    def _handle_brush_end(self):
        """画笔释放 — 将路径渲染到图层 pixmap"""
        self._is_brush_drawing = False
        layer = self._brush_target_layer

        if layer and self._brush_path:
            pm = layer.pixmap()
            if pm and not pm.isNull():
                # 在 pixmap 副本上绘制
                new_pm = QPixmap(pm)
                painter = QPainter(new_pm)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                pen = QPen(self._brush_color, self._brush_size,
                           Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                           Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(self._brush_path)
                painter.end()

                # 更新图层
                layer.update_pixmap(new_pm)
                layer._emit_transform_changed()

        # 清理预览
        if self._brush_preview_item:
            if self._brush_preview_item.scene():
                self._canvas_scene.removeItem(self._brush_preview_item)
            self._brush_preview_item = None
        self._brush_path = None
        self._brush_target_layer = None

    def _show_mask_selection(self, layer_item: LayerItem, mask):
        """将蒙版转为选区路径并显示蚁行线"""
        from PyQt6.QtGui import QImage
        # 简化：用蒙版的外轮廓创建选区路径
        # 扫描蒙版边界
        w, h = mask.width(), mask.height()

        path = QPainterPath()
        # 简单方式：遍历每行找到选中像素的边界矩形
        min_x, min_y = w, h
        max_x, max_y = 0, 0
        for y in range(h):
            for x in range(w):
                if mask.pixelColor(x, y).red() > 128:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        if max_x > min_x and max_y > min_y:
            # 转换边界到场景坐标
            tl = layer_item.mapToScene(QPointF(min_x, min_y))
            br = layer_item.mapToScene(QPointF(max_x + 1, max_y + 1))
            path.addRect(QRectF(tl, br))

        if self._selection_overlay:
            self._selection_overlay.remove()
        self._selection_overlay = SelectionOverlay(path)
        self._canvas_scene.addItem(self._selection_overlay)

    def _delete_selection(self):
        """Delete 键 — 删除当前选区"""
        if self._current_mask is None:
            return

        layer_item = self._get_selected_layer_item()
        if not layer_item:
            return

        if self._current_tool == 'magic_wand':
            self._magic_wand.delete_selection(layer_item, self._current_mask)
        elif self._current_tool == 'lasso':
            self._lasso.delete_selection(layer_item, self._current_mask)

        # 通知变换
        layer_item._emit_transform_changed()
        self._clear_selection()

    def _find_layer_at(self, scene_pos: QPointF) -> Optional[LayerItem]:
        """查找场景位置下的最顶层图层"""
        items = self._canvas_scene.items(scene_pos)
        for item in items:
            if isinstance(item, LayerItem) and not item.is_locked:
                return item
        return None

    def _get_selected_layer_item(self) -> Optional[LayerItem]:
        """获取当前选中的图层"""
        if self._selected_layer_id and self._selected_layer_id in self._layer_items:
            return self._layer_items[self._selected_layer_id]
        return None

    # === 内部方法 ===

    def _build_layer_items(self, layers: List[dict]):
        """从图层数据构建 LayerItem，添加为画框子项"""
        frame_sized = False

        for layer_data in layers:
            item = LayerItem(layer_data, canvas_view=self)
            item.setZValue(layer_data.get('z_order', 0))
            item.setParentItem(self._canvas_frame)
            self._layer_items[layer_data['id']] = item

            # 用第一张有效图片的尺寸设定画框大小
            if not frame_sized and not item.pixmap().isNull():
                pw = item.pixmap().width()
                ph = item.pixmap().height()
                if pw > 0 and ph > 0:
                    self._canvas_frame.resize_frame(pw, ph)
                    frame_sized = True

        # 图层较多时启用可见区域渲染优化
        self._update_layer_performance_flags()

    def _load_continuity_data(self, scene_id: int):
        """从数据库加载连贯性数据"""
        from database.session import session_scope
        from database.models import Scene
        with session_scope() as session:
            scene = session.query(Scene).filter(Scene.id == scene_id).first()
            if not scene:
                return

            # 视线落点
            if scene.eye_focus:
                ef = scene.eye_focus
                self.set_eye_focus(QPointF(ef.get('x', 0), ef.get('y', 0)))

            # 动势引导线
            if scene.motion_vectors:
                for mv_data in scene.motion_vectors:
                    start = QPointF(mv_data.get('x1', 0), mv_data.get('y1', 0))
                    end = QPointF(mv_data.get('x2', 0), mv_data.get('y2', 0))
                    self.add_motion_vector(start, end)

    def _save_continuity_data(self):
        """保存连贯性数据到数据库"""
        if not self._scene_id:
            return

        from database.session import session_scope
        from database.models import Scene
        from sqlalchemy.orm.attributes import flag_modified

        with session_scope() as session:
            scene = session.query(Scene).filter(Scene.id == self._scene_id).first()
            if not scene:
                return

            # 视线落点
            if self._eye_focus:
                scene.eye_focus = self._eye_focus.get_focus_data()
                flag_modified(scene, 'eye_focus')

            # 动势引导线
            if self._motion_vectors:
                scene.motion_vectors = [
                    mv.get_vector_data() for mv in self._motion_vectors
                ]
                flag_modified(scene, 'motion_vectors')

    # === 性能优化 ===

    def _update_layer_performance_flags(self):
        """图层数量较多时启用可见区域渲染优化"""
        from PyQt6.QtWidgets import QGraphicsView

        count = len(self._layer_items)
        if count > 15:
            # 只渲染视口可见区域内的 item
            self.setViewportUpdateMode(
                QGraphicsView.ViewportUpdateMode.SmartViewportUpdate
            )
            # 启用 BSP 索引加速碰撞检测
            self._canvas_scene.setItemIndexMethod(
                self._canvas_scene.ItemIndexMethod.BspTreeIndex
            )
        else:
            # 少量图层时完整刷新，避免残影
            self.setViewportUpdateMode(
                QGraphicsView.ViewportUpdateMode.FullViewportUpdate
            )
            self._canvas_scene.setItemIndexMethod(
                self._canvas_scene.ItemIndexMethod.NoIndex
            )
