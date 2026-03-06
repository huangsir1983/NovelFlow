"""
涛割 - BaseCanvasView 通用无限画布基类
提供 dot grid 背景、缩放、平移、无限扩展等基础画布功能。

交互模型：
  - 右键长按拖动 → 平移画布
  - 滚轮上下 → 垂直平移（反向：滚轮上=画布下移，滚轮下=画布上移）
  - Shift+滚轮 → 水平平移（反向：滚轮上=画布左移，滚轮下=画布右移）
  - Ctrl+滚轮 → 以鼠标为中心缩放
  - 左键 → 由子类处理（框选/点击卡片等）
"""

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QTransform

from ui import theme

# LOD 文本隐藏阈值（屏幕像素）— 文字屏幕高度低于此值时跳过 drawText
LOD_TEXT_MIN_PX = 4

# LOD 图片隐藏阈值（屏幕像素）— 图片屏幕高度低于此值时隐藏，仅显示占位边框
LOD_IMAGE_MIN_PX = 50

# LOD 卡片简化绘制阈值 — 缩放低于此值时，卡片只画填充矩形（跳过文本/阴影/渐变等）
LOD_CARD_SIMPLIFY_ZOOM = 0.12


class BaseCanvasView(QGraphicsView):
    """通用无限画布视图 - dot grid 背景、缩放、平移、无限扩展"""

    zoom_changed = pyqtSignal(int)  # zoom_percent
    viewport_rect_changed = pyqtSignal(QRectF)  # 可视区域变化（懒加载用）
    zooming_active_changed = pyqtSignal(bool)  # True=缩放中, False=缩放结束

    # 滚轮平移速度（像素/每个 angleDelta 单位）
    SCROLL_SPEED = 1.5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvas_scene = QGraphicsScene(self)
        self.setScene(self._canvas_scene)

        # 视图设置 — 默认 NoDrag，平移由右键手动实现
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 性能优化标志
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True
        )

        self._zoom_factor = 1.0

        # 画布锁定（锁定时禁止平移和缩放）
        self._canvas_locked = False

        # 右键平移状态
        self._is_panning = False
        self._pan_start = QPointF()
        self._pan_moved = False  # 右键是否发生了移动（用于区分点击和拖拽）

        # 嵌入模式（禁用右键平移和普通滚轮平移，仅保留 Ctrl+滚轮缩放）
        self._embedded_mode = False

        # 网格吸附
        self._grid_snap_enabled = False
        self.GRID_SNAP_SIZE = 30

        # 视口变化通知（防抖 100ms）
        self._viewport_notify_timer = QTimer()
        self._viewport_notify_timer.setSingleShot(True)
        self._viewport_notify_timer.setInterval(100)
        self._viewport_notify_timer.timeout.connect(self._notify_viewport_change)

        # 场景矩形扩展防抖（150ms）— 避免每次滚轮都遍历所有图形项
        self._scene_expand_timer = QTimer()
        self._scene_expand_timer.setSingleShot(True)
        self._scene_expand_timer.setInterval(150)
        self._scene_expand_timer.timeout.connect(self._expand_scene_rect)

        # 缩放激活状态追踪（300ms 无滚轮后视为缩放结束）
        self._is_zooming = False
        self._zoom_idle_timer = QTimer()
        self._zoom_idle_timer.setSingleShot(True)
        self._zoom_idle_timer.setInterval(300)
        self._zoom_idle_timer.timeout.connect(self._on_zoom_idle)

    def set_locked(self, locked: bool):
        """锁定/解锁画布（锁定时禁止平移和缩放）"""
        self._canvas_locked = locked

    # ==================== 内部平移方法 ====================

    def _pan_view(self, dx_viewport: float, dy_viewport: float):
        """
        平移画布（视口像素为单位）。
        使用 scrollBar().setValue() 实现，不污染变换矩阵，从而保证缩放补偿计算正确。
        ScrollBarAlwaysOff 只是视觉隐藏滚动条，编程操作仍有效。
        """
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        h_bar.setValue(h_bar.value() - int(dx_viewport))
        v_bar.setValue(v_bar.value() - int(dy_viewport))

    # ==================== 背景绘制 ====================

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """绘制点阵网格背景（含 LOD 自适应）"""
        r, g, b = theme.canvas_bg_rgb()
        painter.fillRect(rect, QColor(r, g, b))

        # 缩放过小时跳过点阵（点在屏幕上 < 0.5px，不可见且极耗性能）
        if self._zoom_factor < 0.15:
            return

        # 自适应间距：缩放越小间距越大，大幅减少绘制数量
        base_spacing = 30
        if self._zoom_factor < 0.3:
            spacing = base_spacing * 4   # 120px
        elif self._zoom_factor < 0.5:
            spacing = base_spacing * 2   # 60px
        else:
            spacing = base_spacing       # 30px

        left = int(rect.left()) - (int(rect.left()) % spacing)
        top = int(rect.top()) - (int(rect.top()) % spacing)

        # 估算点数，超限则跳过（防止极端场景矩形导致卡死）
        cols = max(1, int((rect.right() - left) / spacing) + 1)
        rows = max(1, int((rect.bottom() - top) / spacing) + 1)
        if cols * rows > 40000:
            return

        dr, dg, db, da = theme.canvas_dot_rgba()
        dot_color = QColor(dr, dg, db, da)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(dot_color))

        x = left
        while x < rect.right():
            y = top
            while y < rect.bottom():
                painter.drawEllipse(QPointF(x, y), 1.0, 1.0)
                y += spacing
            x += spacing

    # ==================== 滚轮事件 ====================

    def wheelEvent(self, event):
        """滚轮事件：Ctrl+滚轮=缩放，Shift+滚轮=水平平移，普通滚轮=垂直平移"""
        if self._canvas_locked:
            event.accept()
            return
        modifiers = event.modifiers()
        delta = event.angleDelta().y()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+滚轮 → 以鼠标位置为中心缩放
            if delta > 0:
                factor = 1.15
            else:
                factor = 1 / 1.15

            new_zoom = self._zoom_factor * factor
            if 0.05 <= new_zoom <= 10.0:
                # 通知缩放开始（首次进入时发射信号暂停动画）
                if not self._is_zooming:
                    self._is_zooming = True
                    # 临时切换为 MinimalViewportUpdate，减少重绘面积
                    self.setViewportUpdateMode(
                        QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
                    self.zooming_active_changed.emit(True)
                self._zoom_idle_timer.start()

                # 批量化视口更新：抑制 setTransform+_pan_view 之间的多次重绘
                vp = self.viewport()
                vp.setUpdatesEnabled(False)

                # 缩放前：鼠标在 scene 中的坐标
                mouse_scene = self.mapToScene(event.position().toPoint())
                # 用 setTransform 直接设置纯缩放矩阵（不含平移分量）
                t = QTransform()
                t.scale(new_zoom, new_zoom)
                self.setTransform(t)
                self._zoom_factor = new_zoom
                # 轻量扩展场景矩形（确保滚动条范围足够补偿）
                self._quick_expand_scene_rect()
                # 缩放后：让鼠标下的 scene 点回到同一个视口位置
                mouse_scene_after = self.mapToScene(event.position().toPoint())
                diff = mouse_scene - mouse_scene_after
                # diff 是 scene 坐标差，转换为视口像素差 = diff * zoom
                self._pan_view(-diff.x() * new_zoom, -diff.y() * new_zoom)

                # 恢复视口更新 — 触发单次合并重绘
                vp.setUpdatesEnabled(True)

                self.zoom_changed.emit(int(self._zoom_factor * 100))
                # 防抖调度完整扩展（不阻塞滚轮）
                self._scene_expand_timer.start()

        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Shift+滚轮 → 垂直平移（嵌入模式下禁用）
            if self._embedded_mode:
                event.accept()
                return
            scroll_px = delta * self.SCROLL_SPEED
            self._pan_view(0, scroll_px)
            self._scene_expand_timer.start()

        else:
            # 普通滚轮 → 水平平移（嵌入模式下禁用）
            if self._embedded_mode:
                event.accept()
                return
            scroll_px = delta * self.SCROLL_SPEED
            self._pan_view(scroll_px, 0)
            self._scene_expand_timer.start()

        self._schedule_viewport_notify()

    def set_zoom(self, zoom_percent: int):
        """外部设置缩放比例（以视口中心为缩放中心）"""
        new_zoom = zoom_percent / 100.0
        new_zoom = max(0.05, min(10.0, new_zoom))
        # 缩放前：视口中心在 scene 中的坐标
        center_scene = self.mapToScene(self.viewport().rect().center())
        # 用 setTransform 直接设置纯缩放矩阵
        t = QTransform()
        t.scale(new_zoom, new_zoom)
        self.setTransform(t)
        self._zoom_factor = new_zoom
        self._quick_expand_scene_rect()
        # 缩放后：补偿偏移让视口中心不变
        center_scene_after = self.mapToScene(self.viewport().rect().center())
        diff = center_scene - center_scene_after
        self._pan_view(-diff.x() * new_zoom, -diff.y() * new_zoom)
        self.zoom_changed.emit(int(self._zoom_factor * 100))
        self._scene_expand_timer.start()
        self._schedule_viewport_notify()

    def get_zoom_percent(self) -> int:
        return int(self._zoom_factor * 100)

    # ==================== 场景矩形 ====================

    def _quick_expand_scene_rect(self):
        """轻量扩展：仅确保场景矩形包含当前视口（不遍历 items，O(1)）"""
        vp_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        current = self._canvas_scene.sceneRect()
        margin = max(vp_rect.width(), vp_rect.height()) * 0.5
        needed = vp_rect.adjusted(-margin, -margin, margin, margin)
        if not current.contains(needed):
            self._canvas_scene.setSceneRect(current.united(needed))

    def _expand_scene_rect(self):
        """动态扩展场景矩形，实现无限画布效果"""
        items_rect = self._canvas_scene.itemsBoundingRect()
        viewport_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        united = items_rect.united(viewport_rect)
        margin_w = viewport_rect.width()
        margin_h = viewport_rect.height()
        self._canvas_scene.setSceneRect(
            united.adjusted(-margin_w, -margin_h, margin_w, margin_h)
        )

    def fit_all_in_view(self):
        """适应视图显示所有内容"""
        items = self._canvas_scene.items()
        if items:
            rect = self._canvas_scene.itemsBoundingRect().adjusted(-30, -30, 30, 30)
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_factor = self.transform().m11()
            self.zoom_changed.emit(int(self._zoom_factor * 100))

    # ==================== 右键平移 ====================

    def mousePressEvent(self, event):
        """右键按下 → 开始平移（嵌入模式下禁用右键平移）"""
        if event.button() == Qt.MouseButton.RightButton:
            if self._canvas_locked or self._embedded_mode:
                event.accept()
                return
            self._is_panning = True
            self._pan_moved = False
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """右键拖动 → 平移画布"""
        if self._is_panning:
            delta = event.position() - self._pan_start
            if delta.manhattanLength() > 3:
                self._pan_moved = True
            self._pan_start = event.position()
            # 使用 scrollbar 平移（不污染变换矩阵，保证缩放计算正确）
            self._pan_view(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """右键释放 → 结束平移"""
        if event.button() == Qt.MouseButton.RightButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._expand_scene_rect()
            self._schedule_viewport_notify()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._expand_scene_rect()

    # ==================== 视口变化通知 ====================

    def _schedule_viewport_notify(self):
        """触发防抖的视口变化通知"""
        self._viewport_notify_timer.start()

    def _notify_viewport_change(self):
        """发射当前可见区域信号"""
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        self.viewport_rect_changed.emit(visible_rect)

    # ==================== 缩放状态 ====================

    def _on_zoom_idle(self):
        """缩放结束（300ms 无滚轮操作后触发）"""
        self._is_zooming = False
        # 恢复 FullViewportUpdate（点阵网格背景需要完整重绘）
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.viewport().update()  # 触发一次完整重绘恢复背景
        self.zooming_active_changed.emit(False)

    # ==================== 网格吸附 ====================

    def set_grid_snap(self, enabled: bool):
        """开关网格吸附"""
        self._grid_snap_enabled = enabled

    def snap_to_grid(self, pos: QPointF) -> QPointF:
        """将坐标吸附到最近的网格点"""
        if not self._grid_snap_enabled:
            return pos
        s = self.GRID_SNAP_SIZE
        x = round(pos.x() / s) * s
        y = round(pos.y() / s) * s
        return QPointF(x, y)
