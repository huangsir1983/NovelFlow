"""
涛割 - 分镜卡操作组件
ShotCardPlusButton: 选中分镜卡顶部的 + 号按钮
ShotDragActionMenu: 拖拽释放后弹出的生成菜单
ImagePreviewNode: 图片预览节点（分镜卡上方）
ImagePromptTooltip: 图片hover提示词tooltip
"""

import os
from typing import Optional, Callable, List

from PyQt6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsItem, QGraphicsScene, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QApplication, QStyleOptionGraphicsItem,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath, QFontMetrics,
    QRadialGradient, QPixmap,
)

from ui import theme
from ui.components.base_canvas_view import LOD_TEXT_MIN_PX, LOD_IMAGE_MIN_PX, LOD_CARD_SIMPLIFY_ZOOM


# ============================================================
#  ShotDragActionMenu — 拖拽释放后的生成菜单
# ============================================================

class ShotDragActionMenu(QGraphicsRectItem):
    """
    水平条形菜单，包含"快速出图"、"智能PS"和"生成视频"三个按钮。
    点击按钮后自动移除；5s 超时自动消失。
    """

    WIDTH = 300
    HEIGHT = 36
    CORNER_RADIUS = 8
    BTN_GAP = 6

    def __init__(self, scene_index: int,
                 menu_scene_pos: Optional[QPointF] = None,
                 on_generate_image: Optional[Callable] = None,
                 on_generate_video: Optional[Callable] = None,
                 on_smart_ps: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self.scene_index = scene_index
        self._menu_scene_pos = menu_scene_pos or QPointF(0, 0)
        self._on_generate_image = on_generate_image
        self._on_generate_video = on_generate_video
        self._on_smart_ps = on_smart_ps
        self._hovered_btn: Optional[str] = None

        self.setRect(0, 0, self.WIDTH, self.HEIGHT)
        self.setZValue(2000)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        # 按钮热区（三等分）
        btn_w = (self.WIDTH - self.BTN_GAP * 2) / 3
        self._btn_image_rect = QRectF(4, 4, btn_w - 4, self.HEIGHT - 8)
        self._btn_smart_ps_rect = QRectF(
            btn_w + self.BTN_GAP, 4, btn_w - 4, self.HEIGHT - 8)
        self._btn_video_rect = QRectF(
            (btn_w + self.BTN_GAP) * 2, 4, btn_w - 4, self.HEIGHT - 8)

        # 5s 超时自动消失
        self._timeout_timer = QTimer()
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.setInterval(5000)
        self._timeout_timer.timeout.connect(self._auto_remove)
        self._timeout_timer.start()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            dark = theme.is_dark()
            bg = QColor(44, 44, 48) if dark else QColor(255, 255, 255)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        dark = theme.is_dark()
        bg = QColor(44, 44, 48, 240) if dark else QColor(255, 255, 255, 245)
        painter.fillPath(bg_path, QBrush(bg))

        # 边框
        border_c = QColor(theme.border())
        border_c.setAlpha(80)
        painter.setPen(QPen(border_c, 0.5))
        painter.drawPath(bg_path)

        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        # "快速出图" 按钮
        self._draw_btn(painter, self._btn_image_rect, "快速出图",
                        accent=True, hovered=self._hovered_btn == 'image')

        # "智能PS" 按钮
        self._draw_btn(painter, self._btn_smart_ps_rect, "智能PS",
                        accent=False, hovered=self._hovered_btn == 'smart_ps',
                        secondary=True)

        # "生成视频" 按钮
        self._draw_btn(painter, self._btn_video_rect, "生成视频",
                        accent=False, hovered=self._hovered_btn == 'video')

    def _draw_btn(self, painter: QPainter, rect: QRectF, text: str,
                  accent: bool, hovered: bool, secondary: bool = False):
        btn_path = QPainterPath()
        btn_path.addRoundedRect(rect, 6, 6)

        if accent:
            bg = QColor(theme.accent()) if not hovered else QColor(theme.accent_hover())
            fg = QColor(255, 255, 255)
        elif secondary:
            # 智能PS 使用橙色系
            bg = QColor(255, 159, 10, 200) if not hovered else QColor(255, 179, 60, 230)
            fg = QColor(255, 255, 255)
        else:
            bg = QColor(theme.btn_bg()) if not hovered else QColor(theme.btn_bg_hover())
            fg = QColor(theme.text_secondary()) if not hovered else QColor(theme.text_primary())

        painter.fillPath(btn_path, QBrush(bg))
        if not accent:
            painter.setPen(QPen(QColor(theme.btn_border()), 0.5))
            painter.drawPath(btn_path)

        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QPen(fg))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def hoverMoveEvent(self, event):
        pos = event.pos()
        old = self._hovered_btn
        if self._btn_image_rect.contains(pos):
            self._hovered_btn = 'image'
        elif self._btn_smart_ps_rect.contains(pos):
            self._hovered_btn = 'smart_ps'
        elif self._btn_video_rect.contains(pos):
            self._hovered_btn = 'video'
        else:
            self._hovered_btn = None
        if self._hovered_btn != old:
            self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered_btn = None
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            if self._btn_image_rect.contains(pos):
                if self._on_generate_image:
                    self._on_generate_image(self.scene_index, self._menu_scene_pos)
                self._auto_remove()
                return
            elif self._btn_smart_ps_rect.contains(pos):
                if self._on_smart_ps:
                    self._on_smart_ps(self.scene_index, self._menu_scene_pos)
                self._auto_remove()
                return
            elif self._btn_video_rect.contains(pos):
                if self._on_generate_video:
                    self._on_generate_video(self.scene_index, self._menu_scene_pos)
                self._auto_remove()
                return
        super().mousePressEvent(event)

    def _auto_remove(self):
        self._timeout_timer.stop()
        if self.scene():
            self.scene().removeItem(self)


# ============================================================
#  ShotCardPlusButton — 分镜卡顶部 + 号按钮
# ============================================================

class ShotCardPlusButton(QGraphicsEllipseItem):
    """
    分镜卡选中时显示在卡片顶部中央的 + 号按钮。
    支持拖拽：向上拖拽 > 40px 后松开弹出 ShotDragActionMenu。
    """

    NORMAL_SIZE = 28
    HOVER_SIZE = 32

    def __init__(self, scene_index: int,
                 on_generate_image: Optional[Callable] = None,
                 on_generate_video: Optional[Callable] = None,
                 on_smart_ps: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self.scene_index = scene_index
        self._on_generate_image = on_generate_image
        self._on_generate_video = on_generate_video
        self._on_smart_ps = on_smart_ps

        self._is_hovered = False
        self._is_dragging = False
        self._drag_start: Optional[QPointF] = None
        self._drag_line: Optional[QGraphicsPathItem] = None
        self._current_menu: Optional[ShotDragActionMenu] = None

        size = self.NORMAL_SIZE
        # 定位在父卡片顶部中央
        parent_card = parent
        if parent_card:
            card_w = parent_card.rect().width()
            self.setRect(card_w / 2 - size / 2, -size / 2 - 4,
                         size, size)
        else:
            self.setRect(0, 0, size, size)

        self.setZValue(1500)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            return  # 太小不画

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 如果 hover 则放大
        if self._is_hovered and not self._is_dragging:
            expand = (self.HOVER_SIZE - self.NORMAL_SIZE) / 2
            rect = rect.adjusted(-expand, -expand, expand, expand)

        # accent 色圆底
        circle_path = QPainterPath()
        circle_path.addEllipse(rect)
        painter.fillPath(circle_path, QBrush(QColor(theme.accent())))

        # 白色 "+" 十字线
        center = rect.center()
        line_len = rect.width() * 0.35
        painter.setPen(QPen(QColor(255, 255, 255), 2.2, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(
            QPointF(center.x() - line_len, center.y()),
            QPointF(center.x() + line_len, center.y()),
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - line_len),
            QPointF(center.x(), center.y() + line_len),
        )

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start = event.scenePos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging and self._drag_start:
            scene_pos = event.scenePos()
            start = self.mapToScene(self.rect().center())

            # 绘制从按钮中心到鼠标位置的贝塞尔虚线
            if self._drag_line and self._drag_line.scene():
                self._drag_line.scene().removeItem(self._drag_line)
                self._drag_line = None

            path = QPainterPath()
            path.moveTo(start)
            # 向上弯曲的曲线
            ctrl_offset = abs(scene_pos.y() - start.y()) * 0.5
            path.cubicTo(
                QPointF(start.x(), start.y() - ctrl_offset),
                QPointF(scene_pos.x(), scene_pos.y() + ctrl_offset),
                scene_pos,
            )

            self._drag_line = QGraphicsPathItem()
            pen = QPen(QColor(theme.accent()), 2.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            self._drag_line.setPen(pen)
            self._drag_line.setPath(path)
            self._drag_line.setZValue(1800)
            if self.scene():
                self.scene().addItem(self._drag_line)

            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            scene_pos = event.scenePos()

            # 清除拖拽线
            if self._drag_line and self._drag_line.scene():
                self._drag_line.scene().removeItem(self._drag_line)
                self._drag_line = None

            # 检查拖拽距离
            if self._drag_start:
                dy = self._drag_start.y() - scene_pos.y()  # 向上为正
                if dy > 40:
                    # 在鼠标位置创建 ShotDragActionMenu
                    self._show_action_menu(scene_pos)
                elif abs(dy) <= 5 and abs(self._drag_start.x() - scene_pos.x()) <= 5:
                    # 视为点击 → 也弹出菜单
                    btn_center = self.mapToScene(self.rect().center())
                    menu_pos = QPointF(btn_center.x() - ShotDragActionMenu.WIDTH / 2,
                                       btn_center.y() - ShotDragActionMenu.HEIGHT - 10)
                    self._show_action_menu(menu_pos)

            self._drag_start = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _show_action_menu(self, scene_pos: QPointF):
        """在指定场景坐标弹出操作菜单"""
        # 移除旧菜单
        if self._current_menu and self._current_menu.scene():
            self._current_menu.scene().removeItem(self._current_menu)
        menu = ShotDragActionMenu(
            self.scene_index,
            menu_scene_pos=scene_pos,
            on_generate_image=self._on_generate_image,
            on_generate_video=self._on_generate_video,
            on_smart_ps=self._on_smart_ps,
        )
        menu.setPos(scene_pos.x() - ShotDragActionMenu.WIDTH / 2,
                     scene_pos.y() - ShotDragActionMenu.HEIGHT)
        if self.scene():
            self.scene().addItem(menu)
            self._current_menu = menu


# ============================================================
#  ImagePreviewNode — 图片预览节点
# ============================================================

class ImagePreviewNode(QGraphicsRectItem):
    """
    图片预览框 — 显示在分镜卡上方，展示生成的图片。
    初始为空白占位（虚线边框 + 加载动画），图片生成后显示缩略图。
    支持选中（蓝色边框高亮）和删除（Delete 键或右键菜单）。
    双击已有图片 → 进入智能画布编辑。
    """

    NODE_WIDTH = 180
    NODE_HEIGHT = 120
    CORNER_RADIUS = 10

    def __init__(self, scene_index: int, parent=None,
                 on_delete: Optional[Callable] = None,
                 on_open_canvas: Optional[Callable] = None):
        super().__init__(parent)
        self.scene_index = scene_index
        self._pixmap: Optional[QPixmap] = None
        self._is_loading = False
        self._loading_angle = 0
        self._loading_timer: Optional[QTimer] = None
        self._selected = False
        self._on_delete = on_delete
        self._on_open_canvas = on_open_canvas  # (scene_index) -> open intelligent canvas
        self._variant_anchor = None  # VariantLinkAnchor 实例
        self._image_path: str = ''   # 已生成图片的本地路径
        self._gen_params: dict = {}  # 生成参数快照（用于 hover 提示词显示）
        self._press_pos: Optional[QPointF] = None  # 记录按下位置，用于区分点击/拖拽

        # hover 回调（由画布注入）
        self._on_hover_show: Optional[Callable] = None
        self._on_hover_hide: Optional[Callable] = None

        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)
        self.setZValue(900)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        # 10 秒空闲自毁定时器：创建时不启动，等控制台下滑后外部调用 start_idle_countdown()
        self._idle_timer = QTimer()
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(10000)
        self._idle_timer.timeout.connect(self._idle_timeout)

    def set_loading(self, loading: bool):
        """设置加载状态"""
        self._is_loading = loading
        if loading:
            # 用户已点生成，停止空闲自毁
            self._idle_timer.stop()
            if not self._loading_timer:
                self._loading_timer = QTimer()
                self._loading_timer.setInterval(30)
                self._loading_timer.timeout.connect(self._tick_loading)
            self._loading_timer.start()
        else:
            if self._loading_timer:
                self._loading_timer.stop()
        self.update()

    def set_pixmap(self, pixmap: QPixmap):
        """设置图片"""
        self._pixmap = pixmap
        self._is_loading = False
        self._idle_timer.stop()
        if self._loading_timer:
            self._loading_timer.stop()
        self.update()

    # ── 懒加载接口 ──

    def load_pixmap(self):
        """懒加载：从磁盘路径重新加载图片（视口内可见时调用）"""
        if self._pixmap is None and self._image_path and os.path.isfile(self._image_path):
            self._pixmap = QPixmap(self._image_path)
            self.update()

    def release_pixmap(self):
        """释放内存：视口外时卸载图片（保留路径，可再次 load）"""
        if self._pixmap is not None and not self._is_loading and self._image_path:
            self._pixmap = None
            self.update()

    def _tick_loading(self):
        self._loading_angle = (self._loading_angle + 6) % 360
        self.update()

    def _idle_timeout(self):
        """10 秒空闲超时：仍为空白占位（无图片且未加载），自动消失"""
        if self._pixmap is None and not self._is_loading:
            self._do_delete()

    def start_idle_countdown(self):
        """外部调用：控制台下滑时启动 10 秒倒计时"""
        if self._pixmap is None and not self._is_loading:
            self._idle_timer.start()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # LOD 极简模式
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(34, 34, 38, 230) if theme.is_dark() else QColor(252, 252, 255, 240)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        dark = theme.is_dark()
        bg = QColor(34, 34, 38, 230) if dark else QColor(252, 252, 255, 240)
        painter.fillPath(bg_path, QBrush(bg))

        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        # LOD: 图片太小时跳过图片渲染，只画背景+边框
        if _lod * rect.height() < LOD_IMAGE_MIN_PX:
            painter.fillPath(bg_path, QBrush(bg))
            border_c = QColor(255, 255, 255, 30) if dark else QColor(0, 0, 0, 20)
            painter.setPen(QPen(border_c, 0.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(bg_path)
            return

        if self._pixmap and not self._pixmap.isNull():
            # 显示图片
            painter.setClipPath(bg_path)
            scaled = self._pixmap.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # 居中裁剪
            sx = (scaled.width() - rect.width()) / 2
            sy = (scaled.height() - rect.height()) / 2
            painter.drawPixmap(
                rect.toRect(),
                scaled,
                QRectF(sx, sy, rect.width(), rect.height()).toRect(),
            )
            painter.setClipping(False)
        else:
            # 空白占位 — 虚线边框
            pen = QPen(QColor(theme.border()) if not dark else QColor(255, 255, 255, 40), 1.5)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawPath(bg_path)

            if self._is_loading:
                # 旋转加载指示器
                center = rect.center()
                r = 12
                span = 90
                painter.setPen(QPen(QColor(theme.accent()), 2.5, Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap))
                painter.drawArc(
                    QRectF(center.x() - r, center.y() - r, r * 2, r * 2),
                    self._loading_angle * 16, span * 16,
                )
            else:
                # 图标占位
                if not _hide_text:
                    painter.setFont(QFont("Microsoft YaHei", 20))
                    painter.setPen(QPen(QColor(255, 255, 255, 40) if dark else QColor(0, 0, 0, 30)))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "🖼")

        # 边框 (有图片时)
        if self._pixmap and not self._pixmap.isNull():
            border_c = QColor(theme.border())
            border_c.setAlpha(30)
            painter.setPen(QPen(border_c, 0.5))
            painter.drawPath(bg_path)

        # 选中高亮边框
        if self.isSelected():
            sel_pen = QPen(QColor(theme.accent()), 2.5, Qt.PenStyle.SolidLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(bg_path)

    def mousePressEvent(self, event):
        """记录按下位置，用于在 release 中区分点击/拖拽"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """左键释放：拖拽距离 < 5px 且有图片 → 弹出预览"""
        if (event.button() == Qt.MouseButton.LeftButton
                and self._press_pos is not None):
            delta = event.pos() - self._press_pos
            self._press_pos = None
            if (delta.manhattanLength() < 5
                    and self._pixmap and not self._pixmap.isNull()):
                from ui.components.image_preview_dialog import ImagePreviewDialog
                views = self.scene().views() if self.scene() else []
                if views:
                    dlg = ImagePreviewDialog(self._pixmap, views[0])
                    dlg.exec()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        """Delete 键删除节点"""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._do_delete()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单 — 删除"""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        delete_action = menu.addAction("删除图片")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            self._do_delete()

    def _do_delete(self):
        """执行删除"""
        if self._on_delete:
            self._on_delete(self)
        elif self.scene():
            self.scene().removeItem(self)

    # ── 生成参数与 hover 提示词 ──

    def set_gen_params(self, params: dict):
        """保存生成参数快照"""
        self._gen_params = dict(params) if params else {}

    def hoverEnterEvent(self, event):
        if self._gen_params and self._pixmap and self._on_hover_show:
            self._on_hover_show(self)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if self._on_hover_hide:
            self._on_hover_hide()
        super().hoverLeaveEvent(event)

    # ── 变体连接锚点 ──

    def show_variant_anchor(self, on_link_created=None):
        """在节点底部显示橙色拖拽锚点，用于拉线连接到变体卡"""
        if self._variant_anchor is not None:
            return
        from .asset_requirement_cards import VariantLinkAnchor
        self._variant_anchor = VariantLinkAnchor(self, on_link_created)
        self._variant_anchor.setParentItem(self)

    def hide_variant_anchor(self):
        """移除变体连接锚点"""
        if self._variant_anchor is not None:
            if self._variant_anchor.scene():
                self._variant_anchor.scene().removeItem(self._variant_anchor)
            self._variant_anchor = None

    def mouseDoubleClickEvent(self, event):
        """双击 → 有图片时进入智能画布，否则全屏预览"""
        if self._pixmap and not self._pixmap.isNull():
            if self._on_open_canvas:
                self._on_open_canvas(self.scene_index)
            else:
                views = self.scene().views() if self.scene() else []
                if views:
                    viewport = views[0].viewport()
                    overlay = _ImageFullscreenOverlay(self._pixmap, viewport)
                    overlay.show()
        super().mouseDoubleClickEvent(event)


# ============================================================
#  _ImageFullscreenOverlay — 双击图片卡全屏预览
# ============================================================

class _ImageFullscreenOverlay(QWidget):
    """
    全屏半透明覆盖层，居中显示大图。
    点击或按 Esc 关闭。
    """

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self.setGeometry(parent.rect())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocus()
        self.raise_()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 暗色遮罩
        p.fillRect(self.rect(), QColor(0, 0, 0, 200))
        # 图片居中最大化（保持比例，占 85% 视口）
        vp = self.rect()
        max_w = int(vp.width() * 0.85)
        max_h = int(vp.height() * 0.85)
        scaled = self._pixmap.scaled(
            max_w, max_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (vp.width() - scaled.width()) // 2
        y = (vp.height() - scaled.height()) // 2
        # 圆角裁剪
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, scaled.width(), scaled.height()), 8, 8)
        p.setClipPath(path)
        p.drawPixmap(x, y, scaled)

    def mousePressEvent(self, event):
        self.close()
        self.deleteLater()

    def keyPressEvent(self, event):
        self.close()
        self.deleteLater()


# ============================================================
#  ShotImageConnection — 分镜卡→图片框的实线曲线+粒子
# ============================================================

class ShotImageConnection:
    """
    管理分镜卡到图片预览节点之间的连线和粒子动画。
    初始为虚线贝塞尔曲线（等待状态），图片生成成功后切换为实线+发光粒子。
    """

    PARTICLE_RADIUS = 3.5
    PARTICLE_INTERVAL = 30  # ms
    PARTICLE_STEP = 0.012   # 每 tick 前进量
    NUM_PARTICLES = 3       # 粒子数量
    LINE_COLOR = QColor(0, 180, 255, 160)
    LINE_COLOR_DASH = QColor(0, 180, 255, 80)
    PARTICLE_COLOR = QColor(0, 200, 255)

    def __init__(self, gfx_scene: QGraphicsScene,
                 shot_card: QGraphicsRectItem,
                 image_node: ImagePreviewNode):
        self._scene = gfx_scene
        self._shot_card = shot_card
        self._image_node = image_node
        self._is_solid = False

        # 曲线 — 初始虚线
        self._curve_item = QGraphicsPathItem()
        self._curve_item.setZValue(800)
        pen = QPen(self.LINE_COLOR_DASH, 2.0, Qt.PenStyle.DashLine,
                   Qt.PenCapStyle.RoundCap)
        self._curve_item.setPen(pen)
        self._scene.addItem(self._curve_item)

        # 粒子（初始不创建，等 set_solid 时再创建）
        self._particles: List[QGraphicsEllipseItem] = []
        self._particle_ts: List[float] = []

        # 路径
        self._path = QPainterPath()
        self._update_path()

        # 定时器 — 初始只用于更新曲线路径（无粒子）
        self._timer = QTimer()
        self._timer.setInterval(self.PARTICLE_INTERVAL)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_solid(self):
        """切换为实线 + 粒子动画（图片生成成功后调用）"""
        if self._is_solid:
            return
        self._is_solid = True

        # 更新曲线为实线
        pen = QPen(self.LINE_COLOR, 2.0, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        self._curve_item.setPen(pen)

        # 创建粒子
        for i in range(self.NUM_PARTICLES):
            dot = QGraphicsEllipseItem(
                -self.PARTICLE_RADIUS, -self.PARTICLE_RADIUS,
                self.PARTICLE_RADIUS * 2, self.PARTICLE_RADIUS * 2,
            )
            dot.setZValue(1000)
            gradient = QRadialGradient(0, 0, self.PARTICLE_RADIUS * 2.5)
            gradient.setColorAt(0.0, QColor(self.PARTICLE_COLOR.red(),
                                             self.PARTICLE_COLOR.green(),
                                             self.PARTICLE_COLOR.blue(), 220))
            gradient.setColorAt(0.5, QColor(self.PARTICLE_COLOR.red(),
                                             self.PARTICLE_COLOR.green(),
                                             self.PARTICLE_COLOR.blue(), 80))
            gradient.setColorAt(1.0, QColor(self.PARTICLE_COLOR.red(),
                                             self.PARTICLE_COLOR.green(),
                                             self.PARTICLE_COLOR.blue(), 0))
            dot.setBrush(QBrush(gradient))
            dot.setPen(QPen(Qt.PenStyle.NoPen))
            self._scene.addItem(dot)
            self._particles.append(dot)
            self._particle_ts.append(i / self.NUM_PARTICLES)

    def _update_path(self):
        """根据分镜卡和图片节点的当前位置计算曲线"""
        shot_rect = self._shot_card.mapRectToScene(self._shot_card.rect())
        img_rect = self._image_node.mapRectToScene(self._image_node.rect())

        # 判断方向：图片在上方 → 垂直连线；图片在左侧 → 水平连线
        dx = abs(img_rect.center().x() - shot_rect.center().x())
        dy = abs(img_rect.center().y() - shot_rect.center().y())

        if dx > dy:
            # 水平方向：从源卡左边缘中点 → 图片节点右边缘中点
            if img_rect.center().x() < shot_rect.center().x():
                start = QPointF(shot_rect.left(), shot_rect.center().y())
                end = QPointF(img_rect.right(), img_rect.center().y())
            else:
                start = QPointF(shot_rect.right(), shot_rect.center().y())
                end = QPointF(img_rect.left(), img_rect.center().y())
            offset = abs(end.x() - start.x()) * 0.4
            ctrl1 = QPointF(start.x() + (end.x() - start.x()) * 0.1,
                            start.y() - offset * 0.3)
            ctrl2 = QPointF(end.x() - (end.x() - start.x()) * 0.1,
                            end.y() + offset * 0.3)
        else:
            # 垂直方向：从分镜卡顶部中心 → 图片节点底部中心（向上流动）
            start = QPointF(shot_rect.center().x(), shot_rect.top())
            end = QPointF(img_rect.center().x(), img_rect.bottom())
            offset = abs(end.y() - start.y()) * 0.4
            ctrl1 = QPointF(start.x(), start.y() - offset)
            ctrl2 = QPointF(end.x(), end.y() + offset)

        path = QPainterPath(start)
        path.cubicTo(ctrl1, ctrl2, end)
        self._path = path
        self._curve_item.setPath(path)

    def _tick(self):
        self._update_path()
        if not self._is_solid or not self._particles:
            return
        for i in range(len(self._particles)):
            self._particle_ts[i] += self.PARTICLE_STEP
            if self._particle_ts[i] > 1.0:
                self._particle_ts[i] -= 1.0
            # ease-in-out (smoothstep)
            t = self._particle_ts[i]
            t_ease = t * t * (3.0 - 2.0 * t)
            pt = self._path.pointAtPercent(t_ease)
            self._particles[i].setPos(pt)

    def update_positions(self):
        """外部调用：分镜卡或图片节点位置变化后刷新"""
        self._update_path()

    def set_visible(self, visible: bool):
        """显示/隐藏整条连线（曲线 + 粒子 + 定时器）"""
        self._curve_item.setVisible(visible)
        for p in self._particles:
            p.setVisible(visible)
        if visible:
            self._timer.start()
        else:
            self._timer.stop()

    def set_animations_enabled(self, enabled: bool):
        """开启/关闭粒子动画"""
        if enabled:
            self._timer.start()
            for p in self._particles:
                p.setVisible(True)
        else:
            self._timer.stop()
            for p in self._particles:
                p.setVisible(False)

    def remove(self):
        """移除连线和粒子"""
        self._timer.stop()
        if self._curve_item.scene():
            self._scene.removeItem(self._curve_item)
        for dot in self._particles:
            if dot.scene():
                self._scene.removeItem(dot)
        self._particles.clear()


# ============================================================
#  ImagePromptTooltip — hover 图片节点时的提示词浮层
# ============================================================

class ImagePromptTooltip(QWidget):
    """
    图片节点的 hover 提示词浮层（viewport 子控件）。
    显示生成参数：提示词文本 + 模型/比例/风格 + 参照图缩略图行。
    支持"复制提示词"和"填入控制台"按钮。
    """

    fill_console_requested = pyqtSignal(dict)  # 发射完整 gen_params

    MAX_WIDTH = 320
    CORNER_RADIUS = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gen_params: dict = {}
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(200)
        self._hide_timer.timeout.connect(self.hide)

        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setVisible(False)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # 参数标签行（模型 / 比例 / 风格）
        self._params_label = QLabel()
        self._params_label.setFont(QFont("Microsoft YaHei", 8))
        self._params_label.setWordWrap(True)
        layout.addWidget(self._params_label)

        # 提示词区域（QScrollArea 支持滚轮翻动）
        self._prompt_scroll = QScrollArea()
        self._prompt_scroll.setWidgetResizable(True)
        self._prompt_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._prompt_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._prompt_scroll.setMaximumHeight(100)
        self._prompt_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }")

        self._prompt_label = QLabel()
        self._prompt_label.setFont(QFont("Microsoft YaHei", 9))
        self._prompt_label.setWordWrap(True)
        self._prompt_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._prompt_scroll.setWidget(self._prompt_label)
        layout.addWidget(self._prompt_scroll)

        # 参照图缩略图行
        self._ref_images_layout = QHBoxLayout()
        self._ref_images_layout.setSpacing(4)
        self._ref_images_layout.setContentsMargins(0, 0, 0, 0)
        self._ref_container = QWidget()
        self._ref_container.setLayout(self._ref_images_layout)
        self._ref_container.setVisible(False)
        layout.addWidget(self._ref_container)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._copy_btn = QPushButton("复制提示词")
        self._copy_btn.setFont(QFont("Microsoft YaHei", 8))
        self._copy_btn.setFixedHeight(26)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self._on_copy)
        btn_row.addWidget(self._copy_btn)

        self._fill_btn = QPushButton("填入控制台")
        self._fill_btn.setFont(QFont("Microsoft YaHei", 8))
        self._fill_btn.setFixedHeight(26)
        self._fill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fill_btn.clicked.connect(self._on_fill)
        btn_row.addWidget(self._fill_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def set_data(self, gen_params: dict):
        """填充显示内容"""
        self._gen_params = gen_params

        # 参数标签
        parts = []
        model = gen_params.get('model_key', '')
        if model:
            parts.append(f"模型: {model}")
        ratio = gen_params.get('ratio', '')
        if ratio:
            parts.append(f"比例: {ratio}")
        style = gen_params.get('style', '')
        if style and style != '无风格':
            parts.append(f"风格: {style}")
        res = gen_params.get('resolution', '')
        if res:
            parts.append(f"分辨率: {res}")
        self._params_label.setText("  |  ".join(parts) if parts else "")

        # 提示词
        prompt = gen_params.get('prompt', '')
        self._prompt_label.setText(prompt if prompt else "(无提示词)")

        # 参照资产缩略图（优先用 assets 字段，fallback 到 reference_images）
        self._clear_ref_images()
        assets = gen_params.get('assets', [])
        if assets:
            import os
            for a in assets[:4]:
                img_path = a.get('image_path', '')
                name = a.get('name', '')
                if img_path and os.path.isfile(img_path):
                    pm = QPixmap(img_path).scaled(
                        48, 48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    container = QWidget()
                    container.setFixedSize(56, 64)
                    v = QVBoxLayout(container)
                    v.setContentsMargins(0, 0, 0, 0)
                    v.setSpacing(2)
                    img_lbl = QLabel()
                    img_lbl.setPixmap(pm)
                    img_lbl.setFixedSize(48, 48)
                    img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    v.addWidget(img_lbl)
                    name_lbl = QLabel(name)
                    name_lbl.setFont(QFont("Microsoft YaHei", 7))
                    name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    v.addWidget(name_lbl)
                    self._ref_images_layout.addWidget(container)
            self._ref_container.setVisible(self._ref_images_layout.count() > 0)
        else:
            ref_images = gen_params.get('reference_images', [])
            ref_img = gen_params.get('reference_image', '')
            if ref_img:
                ref_images = [ref_img] + [r for r in ref_images if r != ref_img]
            if ref_images:
                import os
                for img_path in ref_images[:4]:
                    if os.path.isfile(img_path):
                        pm = QPixmap(img_path).scaled(
                            48, 48,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
                        lbl = QLabel()
                        lbl.setPixmap(pm)
                        lbl.setFixedSize(48, 48)
                        self._ref_images_layout.addWidget(lbl)
                self._ref_container.setVisible(self._ref_images_layout.count() > 0)
            else:
                self._ref_container.setVisible(False)

        self.adjustSize()

    def _clear_ref_images(self):
        while self._ref_images_layout.count():
            item = self._ref_images_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _on_copy(self):
        prompt = self._gen_params.get('prompt', '')
        if prompt:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(prompt)
            self._copy_btn.setText("已复制")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("复制提示词"))

    def _on_fill(self):
        if self._gen_params:
            self.fill_console_requested.emit(self._gen_params)
            self.hide()

    def schedule_hide(self):
        """延迟隐藏（防闪烁）"""
        self._hide_timer.start()

    def cancel_hide(self):
        """取消延迟隐藏"""
        self._hide_timer.stop()

    def enterEvent(self, event):
        self.cancel_hide()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.schedule_hide()
        super().leaveEvent(event)

    def _apply_theme(self):
        dark = theme.is_dark()
        bg = "rgba(30, 30, 34, 245)" if dark else "rgba(255, 255, 255, 250)"
        border = "rgba(255, 255, 255, 15)" if dark else "rgba(0, 0, 0, 10)"
        text_primary = "#e0e0e0" if dark else "#1a1a1a"
        text_secondary = "#999" if dark else "#666"
        btn_bg = "rgba(55, 55, 60, 255)" if dark else "rgba(240, 240, 244, 255)"
        btn_hover = "rgba(70, 70, 76, 255)" if dark else "rgba(225, 225, 230, 255)"
        accent = theme.accent()

        self.setStyleSheet(f"""
            ImagePromptTooltip {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {self.CORNER_RADIUS}px;
            }}
            QLabel {{
                color: {text_primary};
                background: transparent;
            }}
            QPushButton {{
                background: {btn_bg};
                border: 1px solid {border};
                border-radius: 5px;
                color: {text_primary};
                padding: 2px 10px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
                color: {accent};
            }}
        """)
        self._params_label.setStyleSheet(f"color: {text_secondary};")


# ============================================================
#  PSPreviewNode — 智能PS合成图预览卡片
# ============================================================

class PSPreviewNode(QGraphicsRectItem):
    """
    PS预览卡片 — 显示智能PS导出的合成图缩略图。
    左上角标识"PS"文字，双击重新打开智能PS编辑。
    """

    NODE_WIDTH = 200
    NODE_HEIGHT = 140
    CORNER_RADIUS = 10

    def __init__(self, scene_index: int, scene_id: int, parent=None,
                 on_delete: Optional[Callable] = None,
                 on_reopen_ps: Optional[Callable] = None,
                 on_moved: Optional[Callable] = None):
        super().__init__(parent)
        self.scene_index = scene_index
        self.scene_id = scene_id
        self._pixmap: Optional[QPixmap] = None
        self._image_path: str = ''
        self._on_delete = on_delete
        self._on_reopen_ps = on_reopen_ps
        self._on_moved = on_moved

        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)
        self.setZValue(900)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def set_pixmap(self, pixmap: QPixmap, image_path: str = ''):
        """设置合成图缩略图"""
        self._pixmap = pixmap
        self._image_path = image_path
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(34, 34, 38) if dark else QColor(252, 252, 255)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        bg = QColor(34, 34, 38, 230) if dark else QColor(252, 252, 255, 240)
        painter.fillPath(bg_path, QBrush(bg))

        if self._pixmap and not self._pixmap.isNull():
            # 显示合成图
            painter.setClipPath(bg_path)
            scaled = self._pixmap.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            sx = (scaled.width() - rect.width()) / 2
            sy = (scaled.height() - rect.height()) / 2
            painter.drawPixmap(
                rect.toRect(),
                scaled,
                QRectF(sx, sy, rect.width(), rect.height()).toRect(),
            )
            painter.setClipping(False)
        else:
            # 空白占位
            pen = QPen(QColor(255, 255, 255, 40) if dark else QColor(0, 0, 0, 30), 1.5)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawPath(bg_path)

        # 左上角 PS 标记
        ps_rect = QRectF(rect.x() + 6, rect.y() + 6, 32, 20)
        ps_bg_path = QPainterPath()
        ps_bg_path.addRoundedRect(ps_rect, 4, 4)
        painter.fillPath(ps_bg_path, QBrush(QColor(0, 120, 215, 200)))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
        painter.drawText(ps_rect, Qt.AlignmentFlag.AlignCenter, "PS")

        # 边框
        border_c = QColor(theme.border())
        border_c.setAlpha(40)
        painter.setPen(QPen(border_c, 0.5))
        painter.drawPath(bg_path)

        # 选中高亮
        if self.isSelected():
            sel_pen = QPen(QColor(theme.accent()), 2.5)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(bg_path)

    def mouseDoubleClickEvent(self, event):
        """双击重新打开智能PS"""
        if self._on_reopen_ps:
            self._on_reopen_ps(self.scene_index)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._do_delete()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        reopen_action = menu.addAction("重新编辑 PS")
        delete_action = menu.addAction("删除 PS 预览")
        action = menu.exec(event.screenPos())
        if action == reopen_action and self._on_reopen_ps:
            self._on_reopen_ps(self.scene_index)
        elif action == delete_action:
            self._do_delete()

    def _do_delete(self):
        if self._on_delete:
            self._on_delete(self)
        elif self.scene():
            self.scene().removeItem(self)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # 拖拽移动后保存新位置
        if self._on_moved and event.button() == Qt.MouseButton.LeftButton:
            pos = self.pos()
            self._on_moved(self.scene_index, pos.x(), pos.y(),
                           self._image_path)

