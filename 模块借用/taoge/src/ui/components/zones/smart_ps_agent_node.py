"""
涛割 - 智能PS AGENT 流水线节点 [DEPRECATED]

此模块中的 SmartPSAgentNode 已被 smart_ps_window.py (SmartPSWindow) 替代。
SmartPSAgentNode 不再嵌入统一画布，改为独立最大化窗口内的 ComfyUI 风格节点画布。

EmbeddedCanvasWidget 类仍在使用，被 smart_ps_nodes.py 中的 PSCanvasNode 引用。
"""

import os
from typing import Optional, List, Dict, Callable

from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsProxyWidget,
    QWidget, QHBoxLayout, QVBoxLayout, QGraphicsPathItem,
    QMenu,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPixmap, QLinearGradient,
)

from ui import theme


# ============================================================
#  常量
# ============================================================

NODE_WIDTH = 1400
NODE_HEIGHT = 900
TITLE_H = 36
INPUT_COL_W = 130
OUTPUT_COL_W = 200
PIPELINE_H = 160
CORNER_RADIUS = 12

# LOD 简化阈值（与项目一致）
LOD_SIMPLIFY_ZOOM = 0.12

# 颜色
COLOR_ACCENT = QColor(91, 127, 255)
COLOR_TITLE_BG = QColor(28, 28, 36)
COLOR_NODE_BG = QColor(22, 22, 30, 240)
COLOR_BORDER = QColor(60, 60, 80, 120)
COLOR_CLOSE_HOVER = QColor(255, 70, 70)
COLOR_MINIMIZE_HOVER = QColor(255, 190, 0)
COLOR_SECTION_BORDER = QColor(50, 50, 70, 80)


# ============================================================
#  InputSlot — 单个输入槽
# ============================================================

class InputSlot(QGraphicsRectItem):
    """左侧输入列中的单个输入槽：缩略图 + 名称 + 右侧锚点"""

    SLOT_WIDTH = INPUT_COL_W - 16
    SLOT_HEIGHT = 76
    THUMB_SIZE = 52
    ANCHOR_RADIUS = 5

    def __init__(self, name: str, image_path: str = '',
                 slot_type: str = 'asset', parent=None):
        super().__init__(parent)
        self.slot_name = name
        self.slot_type = slot_type  # asset / tail_frame / paste
        self._image_path = image_path
        self._pixmap: Optional[QPixmap] = None

        self.setRect(0, 0, self.SLOT_WIDTH, self.SLOT_HEIGHT)
        self.setAcceptHoverEvents(True)
        self._hovered = False

        # 加载缩略图
        if image_path and os.path.isfile(image_path):
            self._pixmap = QPixmap(image_path)

    def get_anchor_scene_pos(self) -> QPointF:
        """获取右侧锚点的场景坐标"""
        local = QPointF(self.rect().right() + 4,
                        self.rect().center().y())
        return self.mapToScene(local)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()

        # 背景
        bg = QColor(35, 35, 45, 180) if dark else QColor(245, 245, 250, 200)
        if self._hovered:
            bg = QColor(45, 45, 60, 200) if dark else QColor(235, 235, 245, 220)

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        painter.fillPath(path, QBrush(bg))

        # 缩略图区域
        thumb_rect = QRectF(rect.x() + 6, rect.y() + (rect.height() - self.THUMB_SIZE) / 2,
                            self.THUMB_SIZE, self.THUMB_SIZE)

        if self._pixmap and not self._pixmap.isNull():
            # 居中裁剪绘制
            clip_path = QPainterPath()
            clip_path.addRoundedRect(thumb_rect, 6, 6)
            painter.setClipPath(clip_path)
            scaled = self._pixmap.scaled(
                int(self.THUMB_SIZE), int(self.THUMB_SIZE),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            sx = (scaled.width() - self.THUMB_SIZE) / 2
            sy = (scaled.height() - self.THUMB_SIZE) / 2
            painter.drawPixmap(
                thumb_rect.toRect(), scaled,
                QRectF(sx, sy, self.THUMB_SIZE, self.THUMB_SIZE).toRect())
            painter.setClipping(False)
        else:
            # 虚线占位
            pen = QPen(QColor(255, 255, 255, 40) if dark else QColor(0, 0, 0, 30), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(thumb_rect, 6, 6)

            # 类型图标文字
            icon_text = {'asset': '📦', 'tail_frame': '◀', 'paste': '📋'}.get(
                self.slot_type, '?')
            painter.setPen(QPen(QColor(180, 180, 190) if dark else QColor(100, 100, 110)))
            painter.setFont(QFont("Microsoft YaHei", 14))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, icon_text)

        # 名称（缩略图右侧）
        name_rect = QRectF(
            thumb_rect.right() + 6, rect.y() + 4,
            rect.width() - self.THUMB_SIZE - 18, rect.height() - 8)
        painter.setPen(QPen(QColor(200, 200, 210) if dark else QColor(60, 60, 70)))
        painter.setFont(QFont("Microsoft YaHei", 8))
        # 截断过长名称
        fm = painter.fontMetrics()
        elided = fm.elidedText(self.slot_name, Qt.TextElideMode.ElideRight,
                               int(name_rect.width()))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         elided)

        # 右侧锚点圆
        anchor_cx = rect.right() + 4
        anchor_cy = rect.center().y()
        painter.setPen(QPen(COLOR_ACCENT, 1.5))
        painter.setBrush(QBrush(COLOR_ACCENT.lighter(140)))
        painter.drawEllipse(QPointF(anchor_cx, anchor_cy),
                            self.ANCHOR_RADIUS, self.ANCHOR_RADIUS)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()


# ============================================================
#  InputColumnPanel — 左侧输入列
# ============================================================

class InputColumnPanel(QGraphicsRectItem):
    """左侧输入列，包含多个 InputSlot"""

    HEADER_H = 28
    SLOT_GAP = 6
    PADDING = 8

    def __init__(self, width: float, height: float, parent=None):
        super().__init__(parent)
        self.setRect(0, 0, width, height)
        self._slots: List[InputSlot] = []

    def add_slot(self, name: str, image_path: str = '',
                 slot_type: str = 'asset') -> InputSlot:
        """添加一个输入槽"""
        slot = InputSlot(name, image_path, slot_type, parent=self)
        self._slots.append(slot)
        self._layout_slots()
        return slot

    def clear_slots(self):
        for s in self._slots:
            if s.scene():
                s.scene().removeItem(s)
        self._slots.clear()

    def _layout_slots(self):
        y = self.HEADER_H + self.PADDING
        for slot in self._slots:
            slot.setPos(self.PADDING, y)
            y += slot.SLOT_HEIGHT + self.SLOT_GAP

    def get_slots(self) -> List[InputSlot]:
        return self._slots

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()

        # 背景
        bg = QColor(26, 26, 34, 200) if dark else QColor(248, 248, 252, 220)
        painter.fillRect(rect, bg)

        # 标题
        header_rect = QRectF(rect.x(), rect.y(), rect.width(), self.HEADER_H)
        hdr_bg = QColor(32, 32, 42, 220) if dark else QColor(240, 240, 248, 240)
        painter.fillRect(header_rect, hdr_bg)

        painter.setPen(QPen(QColor(160, 170, 200) if dark else QColor(80, 80, 100)))
        painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        painter.drawText(header_rect.adjusted(8, 0, 0, 0),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         "输入")

        # 右侧分隔线
        painter.setPen(QPen(COLOR_SECTION_BORDER, 1))
        painter.drawLine(QPointF(rect.right(), rect.top()),
                         QPointF(rect.right(), rect.bottom()))


# ============================================================
#  OutputColumnPanel — 右侧输出列
# ============================================================

class SnapshotSlot(QGraphicsRectItem):
    """快照缩略图槽"""

    SLOT_WIDTH = OUTPUT_COL_W - 24
    SLOT_HEIGHT = 100
    CORNER_R = 8

    def __init__(self, index: int, parent=None,
                 on_selected: Optional[Callable] = None):
        super().__init__(parent)
        self.snapshot_index = index
        self._pixmap: Optional[QPixmap] = None
        self._image_path: str = ''
        self._selected = False
        self._on_selected = on_selected

        self.setRect(0, 0, self.SLOT_WIDTH, self.SLOT_HEIGHT)
        self.setAcceptHoverEvents(True)
        self._hovered = False

    def set_pixmap(self, pixmap: QPixmap, path: str = ''):
        self._pixmap = pixmap
        self._image_path = path
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()

        clip = QPainterPath()
        clip.addRoundedRect(rect, self.CORNER_R, self.CORNER_R)

        # 背景
        bg = QColor(30, 30, 40, 200) if dark else QColor(248, 248, 255, 220)
        if self._hovered:
            bg = QColor(40, 40, 55, 220) if dark else QColor(238, 238, 250, 240)
        painter.fillPath(clip, QBrush(bg))

        if self._pixmap and not self._pixmap.isNull():
            painter.setClipPath(clip)
            scaled = self._pixmap.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            sx = (scaled.width() - rect.width()) / 2
            sy = (scaled.height() - rect.height()) / 2
            painter.drawPixmap(
                rect.toRect(), scaled,
                QRectF(sx, sy, rect.width(), rect.height()).toRect())
            painter.setClipping(False)
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 30) if dark else QColor(0, 0, 0, 20), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(255, 255, 255, 40), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawPath(clip)

        # 序号标记
        idx_rect = QRectF(rect.x() + 4, rect.y() + 4, 20, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 120)))
        painter.drawRoundedRect(idx_rect, 3, 3)
        painter.setPen(QPen(QColor(220, 220, 230)))
        painter.setFont(QFont("Microsoft YaHei", 7))
        painter.drawText(idx_rect, Qt.AlignmentFlag.AlignCenter,
                         str(self.snapshot_index + 1))

        # 选中边框
        if self._selected:
            sel_pen = QPen(COLOR_ACCENT, 2.5)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(clip)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._on_selected:
                self._on_selected(self.snapshot_index)
            event.accept()
            return
        super().mousePressEvent(event)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()


class OutputColumnPanel(QGraphicsRectItem):
    """右侧输出列：快照 + 后处理（预留）+ 输出预览"""

    HEADER_H = 28
    PADDING = 12
    SLOT_GAP = 8
    SNAPSHOT_BTN_H = 32

    def __init__(self, width: float, height: float, parent=None,
                 on_snapshot: Optional[Callable] = None,
                 on_output: Optional[Callable] = None):
        super().__init__(parent)
        self.setRect(0, 0, width, height)
        self._snapshots: List[SnapshotSlot] = []
        self._selected_snapshot: int = -1
        self._on_snapshot = on_snapshot
        self._on_output = on_output
        self._output_pixmap: Optional[QPixmap] = None

        self.setAcceptHoverEvents(True)
        self._snapshot_btn_hovered = False
        self._output_btn_hovered = False

    def add_snapshot(self, pixmap: QPixmap, path: str = '') -> SnapshotSlot:
        idx = len(self._snapshots)
        slot = SnapshotSlot(idx, parent=self,
                            on_selected=self._on_snapshot_selected)
        slot.set_pixmap(pixmap, path)
        self._snapshots.append(slot)
        self._layout()
        return slot

    def set_output_preview(self, pixmap: QPixmap):
        self._output_pixmap = pixmap
        self.update()

    def _on_snapshot_selected(self, index: int):
        """选中一个快照"""
        self._selected_snapshot = index
        for i, s in enumerate(self._snapshots):
            s.set_selected(i == index)

    def _layout(self):
        y = self.HEADER_H + self.PADDING + self.SNAPSHOT_BTN_H + 8
        for slot in self._snapshots:
            slot.setPos(self.PADDING, y)
            y += slot.SLOT_HEIGHT + self.SLOT_GAP

    def get_selected_snapshot(self) -> Optional[SnapshotSlot]:
        if 0 <= self._selected_snapshot < len(self._snapshots):
            return self._snapshots[self._selected_snapshot]
        return None

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()

        # 背景
        bg = QColor(26, 26, 34, 200) if dark else QColor(248, 248, 252, 220)
        painter.fillRect(rect, bg)

        # 标题
        header_rect = QRectF(rect.x(), rect.y(), rect.width(), self.HEADER_H)
        hdr_bg = QColor(32, 32, 42, 220) if dark else QColor(240, 240, 248, 240)
        painter.fillRect(header_rect, hdr_bg)

        painter.setPen(QPen(QColor(160, 170, 200) if dark else QColor(80, 80, 100)))
        painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        painter.drawText(header_rect.adjusted(8, 0, 0, 0),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         "输出")

        # "拍摄快照"按钮
        btn_y = self.HEADER_H + self.PADDING
        btn_rect = QRectF(self.PADDING, btn_y,
                          rect.width() - 2 * self.PADDING, self.SNAPSHOT_BTN_H)
        self._snapshot_btn_rect = btn_rect

        btn_bg = COLOR_ACCENT if not self._snapshot_btn_hovered else COLOR_ACCENT.lighter(120)
        btn_path = QPainterPath()
        btn_path.addRoundedRect(btn_rect, 6, 6)
        painter.fillPath(btn_path, QBrush(btn_bg))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, "📷 拍摄快照")

        # 后处理节点预留区域（在快照列表下方）
        snapshots_end_y = self.HEADER_H + self.PADDING + self.SNAPSHOT_BTN_H + 8
        if self._snapshots:
            last = self._snapshots[-1]
            snapshots_end_y = last.pos().y() + last.SLOT_HEIGHT + 12

        # 溶图（预留）
        postproc_rect = QRectF(self.PADDING, snapshots_end_y,
                               rect.width() - 2 * self.PADDING, 50)
        pp_path = QPainterPath()
        pp_path.addRoundedRect(postproc_rect, 6, 6)
        painter.fillPath(pp_path, QBrush(QColor(40, 40, 50, 100)))
        painter.setPen(QPen(QColor(120, 120, 140)))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(postproc_rect, Qt.AlignmentFlag.AlignCenter, "溶图 (即将推出)")

        # 高清化（预留）
        hd_rect = QRectF(self.PADDING, postproc_rect.bottom() + 8,
                         rect.width() - 2 * self.PADDING, 50)
        hd_path = QPainterPath()
        hd_path.addRoundedRect(hd_rect, 6, 6)
        painter.fillPath(hd_path, QBrush(QColor(40, 40, 50, 100)))
        painter.setPen(QPen(QColor(120, 120, 140)))
        painter.drawText(hd_rect, Qt.AlignmentFlag.AlignCenter, "高清化 (即将推出)")

        # 输出预览区域
        output_y = hd_rect.bottom() + 12
        output_rect = QRectF(self.PADDING, output_y,
                             rect.width() - 2 * self.PADDING,
                             rect.height() - output_y - self.PADDING - 40)
        if output_rect.height() > 40:
            out_path = QPainterPath()
            out_path.addRoundedRect(output_rect, 8, 8)

            if self._output_pixmap and not self._output_pixmap.isNull():
                painter.setClipPath(out_path)
                scaled = self._output_pixmap.scaled(
                    int(output_rect.width()), int(output_rect.height()),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                sx = (scaled.width() - output_rect.width()) / 2
                sy = (scaled.height() - output_rect.height()) / 2
                painter.drawPixmap(
                    output_rect.toRect(), scaled,
                    QRectF(sx, sy, output_rect.width(), output_rect.height()).toRect())
                painter.setClipping(False)
            else:
                painter.fillPath(out_path, QBrush(QColor(30, 30, 38, 150)))
                painter.setPen(QPen(QColor(100, 100, 120)))
                painter.setFont(QFont("Microsoft YaHei", 9))
                painter.drawText(output_rect, Qt.AlignmentFlag.AlignCenter, "输出预览")

        # 底部"输出到下一环节"按钮
        out_btn_rect = QRectF(self.PADDING,
                              rect.height() - self.PADDING - 32,
                              rect.width() - 2 * self.PADDING, 32)
        self._output_btn_rect = out_btn_rect
        out_btn_bg = QColor(50, 180, 100) if not self._output_btn_hovered \
            else QColor(60, 200, 120)
        out_btn_path = QPainterPath()
        out_btn_path.addRoundedRect(out_btn_rect, 6, 6)
        painter.fillPath(out_btn_path, QBrush(out_btn_bg))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.drawText(out_btn_rect, Qt.AlignmentFlag.AlignCenter, "输出到下一环节 →")

        # 左侧分隔线
        painter.setPen(QPen(COLOR_SECTION_BORDER, 1))
        painter.drawLine(QPointF(rect.x(), rect.top()),
                         QPointF(rect.x(), rect.bottom()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            if hasattr(self, '_snapshot_btn_rect') and self._snapshot_btn_rect.contains(pos):
                if self._on_snapshot:
                    self._on_snapshot()
                event.accept()
                return
            if hasattr(self, '_output_btn_rect') and self._output_btn_rect.contains(pos):
                if self._on_output:
                    self._on_output()
                event.accept()
                return
        super().mousePressEvent(event)

    def hoverMoveEvent(self, event):
        pos = event.pos()
        old_snap = self._snapshot_btn_hovered
        old_out = self._output_btn_hovered
        self._snapshot_btn_hovered = (hasattr(self, '_snapshot_btn_rect')
                                      and self._snapshot_btn_rect.contains(pos))
        self._output_btn_hovered = (hasattr(self, '_output_btn_rect')
                                     and self._output_btn_rect.contains(pos))
        if old_snap != self._snapshot_btn_hovered or old_out != self._output_btn_hovered:
            self.update()

    def hoverLeaveEvent(self, event):
        self._snapshot_btn_hovered = False
        self._output_btn_hovered = False
        self.update()


# ============================================================
#  EmbeddedCanvasWidget — 画布包装器
# ============================================================

class EmbeddedCanvasWidget(QWidget):
    """
    包装 IntelligentCanvasView + LayerPanel，
    禁用无限画布的右键平移和普通滚轮平移。
    """

    def __init__(self, data_hub=None, scene_id: int = 0,
                 assets: list = None, first_open: bool = True,
                 parent=None):
        super().__init__(parent)
        self._data_hub = data_hub
        self._scene_id = scene_id
        self._assets = assets or []
        self._first_open = first_open

        self._init_ui()
        self._connect_signals()

        # 加载场景
        if scene_id:
            self._canvas_view.load_scene(scene_id)
            if first_open:
                self._load_asset_layers()
            # 无论是否首次打开，都刷新图层面板
            self._refresh_layer_panel()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 图层面板（左侧 220px）
        from ui.components.layer_panel import LayerPanel
        self._layer_panel = LayerPanel()
        self._layer_panel.setFixedWidth(220)
        layout.addWidget(self._layer_panel)

        # 画布+工具栏（右侧）
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        # 画布
        from ui.components.intelligent_canvas import IntelligentCanvasView
        self._canvas_view = IntelligentCanvasView(data_hub=self._data_hub)
        # 禁用右键平移和普通滚轮平移（仅保留 Ctrl+滚轮缩放）
        self._canvas_view._embedded_mode = True
        canvas_layout.addWidget(self._canvas_view, 1)

        # 工具栏（底部）
        from ui.components.canvas_toolbar import CanvasToolbar
        self._toolbar = CanvasToolbar()
        # 隐藏返回按钮（由 AgentNode 标题栏控制）
        if hasattr(self._toolbar, '_back_btn'):
            self._toolbar._back_btn.setVisible(False)
        canvas_layout.addWidget(self._toolbar)

        layout.addWidget(canvas_container, 1)

    def _connect_signals(self):
        # 工具栏 → 画布
        self._toolbar.tool_changed.connect(self._on_tool_changed)
        self._toolbar.ai_auto_layer.connect(self._on_ai_auto_layer)
        self._toolbar.flip_h_clicked.connect(self._on_flip_h)
        self._toolbar.flip_v_clicked.connect(self._on_flip_v)
        self._toolbar.save_clicked.connect(self._on_save)
        self._toolbar.brush_color_changed.connect(self._on_brush_color)
        self._toolbar.brush_size_changed.connect(self._on_brush_size)
        self._toolbar.merge_clicked.connect(self._on_merge)
        self._toolbar.onion_toggled.connect(self._on_onion)
        self._toolbar.inherit_prev_clicked.connect(self._on_inherit_prev)
        self._toolbar.continuity_toggled.connect(self._on_continuity)

        # 画布 → 图层面板
        self._canvas_view.layer_selected.connect(self._on_canvas_layer_selected)
        self._canvas_view.layer_transform_changed.connect(self._on_layer_transform)
        self._canvas_view.multi_selection_changed.connect(self._on_multi_selection)
        self._canvas_view.layer_context_menu_requested.connect(
            self._on_canvas_context_menu)

        # 图层面板 → 画布
        self._layer_panel.layer_selected.connect(self._on_panel_layer_selected)
        self._layer_panel.layer_visibility_changed.connect(self._on_layer_visibility)
        self._layer_panel.layer_locked_changed.connect(self._on_layer_locked)
        self._layer_panel.layer_deleted.connect(self._on_layer_deleted)
        self._layer_panel.layer_order_changed.connect(self._on_layer_order)
        self._layer_panel.blend_mode_changed.connect(self._on_blend_mode)
        self._layer_panel.opacity_changed.connect(self._on_opacity)
        self._layer_panel.merge_layers_requested.connect(self._on_merge_layers)
        self._layer_panel.flip_h_requested.connect(self._on_layer_flip_h)
        self._layer_panel.flip_v_requested.connect(self._on_layer_flip_v)
        self._layer_panel.layer_copied.connect(self._on_layer_copied)
        self._layer_panel.ai_redraw_requested.connect(self._on_ai_redraw)
        self._layer_panel.view_angle_requested.connect(self._on_view_angle)
        self._layer_panel.matting_requested.connect(self._on_matting)
        self._layer_panel.change_expression_requested.connect(self._on_change_expression)

    # === 画布操作代理 ===

    def _on_tool_changed(self, tool: str):
        if hasattr(self._canvas_view, 'set_tool'):
            self._canvas_view.set_tool(tool)

    def _on_ai_auto_layer(self):
        if hasattr(self._canvas_view, 'ai_auto_layer'):
            self._canvas_view.ai_auto_layer()

    def _on_flip_h(self):
        lid = self._canvas_view._selected_layer_id
        if lid and lid in self._canvas_view._layer_items:
            item = self._canvas_view._layer_items[lid]
            item.set_flip_h(not item._flip_h)

    def _on_flip_v(self):
        lid = self._canvas_view._selected_layer_id
        if lid and lid in self._canvas_view._layer_items:
            item = self._canvas_view._layer_items[lid]
            item.set_flip_v(not item._flip_v)

    def _on_save(self):
        self._canvas_view.save_scene()

    def _on_brush_color(self, color):
        if hasattr(self._canvas_view, 'set_brush_color'):
            self._canvas_view.set_brush_color(color)

    def _on_brush_size(self, size):
        if hasattr(self._canvas_view, 'set_brush_size'):
            self._canvas_view.set_brush_size(size)

    def _on_merge(self):
        ids = list(self._canvas_view._selected_layer_ids)
        if len(ids) >= 2:
            self._canvas_view.merge_layers(ids)
            self._refresh_layer_panel()

    def _on_onion(self, enabled):
        if hasattr(self._canvas_view, 'load_onion_skin'):
            if enabled:
                self._canvas_view.load_onion_skin()
            elif hasattr(self._canvas_view, 'remove_onion_skin'):
                self._canvas_view.remove_onion_skin()

    def _on_inherit_prev(self):
        if hasattr(self._canvas_view, 'inherit_prev_end_frame'):
            self._canvas_view.inherit_prev_end_frame()

    def _on_continuity(self, enabled):
        if hasattr(self._canvas_view, 'toggle_continuity'):
            self._canvas_view.toggle_continuity(enabled)

    # === 画布 → 面板同步 ===

    def _on_canvas_layer_selected(self, layer_id: int):
        self._layer_panel.select_layer(layer_id)

    def _on_layer_transform(self, layer_id: int, transform: dict):
        # 保存变换到 DB
        try:
            from services.layer_service import LayerService
            LayerService().save_layer({'id': layer_id, 'transform': transform})
        except Exception:
            pass

    def _on_multi_selection(self, layer_ids: list):
        """画布多选变化 → 同步图层面板的选中高亮"""
        id_set = set(layer_ids)
        self._layer_panel._selected_layer_ids = id_set
        if layer_ids:
            self._layer_panel._selected_layer_id = layer_ids[-1]
        for row in self._layer_panel._rows:
            row.set_selected(row._layer_id in id_set)
        if hasattr(self._toolbar, 'set_merge_visible'):
            self._toolbar.set_merge_visible(len(layer_ids) >= 2)

    def _on_canvas_context_menu(self, layer_id: int, pos):
        self._layer_panel._on_context_menu(layer_id, pos)

    # === 面板 → 画布同步 ===

    def _on_panel_layer_selected(self, layer_id: int):
        self._canvas_view.select_layer(layer_id)

    def _on_layer_visibility(self, layer_id: int, visible: bool):
        if layer_id in self._canvas_view._layer_items:
            self._canvas_view._layer_items[layer_id].setVisible(visible)

    def _on_layer_locked(self, layer_id: int, locked: bool):
        if layer_id in self._canvas_view._layer_items:
            item = self._canvas_view._layer_items[layer_id]
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, not locked)

    def _on_layer_deleted(self, layer_id: int):
        self._canvas_view.remove_layer(layer_id)
        try:
            from services.layer_service import LayerService
            LayerService().delete_layer(layer_id)
        except Exception:
            pass

    def _on_layer_order(self, layer_ids: list):
        if hasattr(self._canvas_view, 'reorder_layers'):
            self._canvas_view.reorder_layers(layer_ids)

    def _on_blend_mode(self, layer_id: int, mode: str):
        if layer_id in self._canvas_view._layer_items:
            self._canvas_view._layer_items[layer_id].blend_mode = mode

    def _on_opacity(self, layer_id: int, opacity: float):
        if layer_id in self._canvas_view._layer_items:
            self._canvas_view._layer_items[layer_id].setOpacity(opacity / 100.0)

    def _on_merge_layers(self, layer_ids: list):
        if hasattr(self._canvas_view, 'merge_layers'):
            self._canvas_view.merge_layers(layer_ids)
            self._refresh_layer_panel()

    def _on_layer_flip_h(self, layer_id: int):
        if layer_id in self._canvas_view._layer_items:
            item = self._canvas_view._layer_items[layer_id]
            item.set_flip_h(not item._flip_h)

    def _on_layer_flip_v(self, layer_id: int):
        if layer_id in self._canvas_view._layer_items:
            item = self._canvas_view._layer_items[layer_id]
            item.set_flip_v(not item._flip_v)

    def _on_layer_copied(self, layer_id: int):
        if hasattr(self._canvas_view, 'copy_layer'):
            self._canvas_view.copy_layer(layer_id)
            self._refresh_layer_panel()

    def _on_ai_redraw(self, layer_id: int):
        pass  # TODO: AI 重绘功能

    def _on_view_angle(self, layer_id: int):
        pass  # TODO: 视角转换功能

    def _on_matting(self, layer_id: int):
        pass  # TODO: AI 抠图功能

    def _on_change_expression(self, layer_id: int):
        pass  # TODO: 改表情功能

    # === 图层加载 ===

    def _load_asset_layers(self):
        """清空旧图层 → 重新加载资产图层"""
        try:
            from services.layer_service import LayerService
            layer_service = LayerService()

            # 清空旧图层
            layer_service.delete_scene_layers(self._scene_id)
            for lid in list(self._canvas_view._layer_items.keys()):
                self._canvas_view.remove_layer(lid)

            if not self._assets:
                return

            # 按类型排序
            type_order = {'background': 0, 'prop': 1, 'character': 2}
            sorted_assets = sorted(
                self._assets,
                key=lambda a: type_order.get(a.get('type', ''), 1)
            )

            z_order = 0
            for asset in sorted_assets:
                image_path = asset.get('image_path', '')
                name = asset.get('name', '')
                asset_type = asset.get('type', 'prop')

                if not image_path or not os.path.isfile(image_path):
                    continue

                layer_data = {
                    'scene_id': self._scene_id,
                    'name': name or f'资产 {z_order + 1}',
                    'layer_type': asset_type,
                    'z_order': z_order,
                    'is_visible': True,
                    'is_locked': False,
                    'image_path': image_path,
                    'original_image_path': image_path,
                }
                layer_id = layer_service.save_layer(layer_data)
                layer_data['id'] = layer_id
                self._canvas_view.add_layer(layer_data)
                z_order += 1

            self._refresh_layer_panel()
        except Exception as e:
            print(f"[涛割] 智能PS加载资产图层失败: {e}")

    def _refresh_layer_panel(self):
        """刷新图层面板"""
        layers = []
        for layer_id, item in self._canvas_view._layer_items.items():
            data = getattr(item, '_data', {})
            layers.append({
                'id': layer_id,
                'name': data.get('name', f'图层 {layer_id}'),
                'layer_type': data.get('layer_type', 'prop'),
                'z_order': data.get('z_order', 0),
                'is_visible': item.isVisible(),
                'is_locked': not bool(item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable),
                'image_path': data.get('image_path', ''),
                'opacity': int(item.opacity() * 100),
                'blend_mode': getattr(item, 'blend_mode', 'normal'),
            })
        layers.sort(key=lambda x: x.get('z_order', 0), reverse=True)
        self._layer_panel.set_layers(layers)

    def save_scene(self):
        self._canvas_view.save_scene()

    def set_canvas_frame_size(self, w: float, h: float):
        """调整画框尺寸以匹配PS节点预留空间。
        自动扣除 LayerPanel 宽度和 Toolbar 高度，确保画框填满实际可视区域。
        """
        if hasattr(self._canvas_view, '_canvas_frame') and self._canvas_view._canvas_frame:
            # 扣除面板占用空间
            panel_w = self._layer_panel.width() if self._layer_panel else 220
            toolbar_h = 44  # CanvasToolbar.HEIGHT
            frame_w = max(100, w - panel_w)
            frame_h = max(100, h - toolbar_h)
            self._canvas_view._canvas_frame.resize_frame(frame_w, frame_h)
            # 延迟 fit — widget 可能尚未完成布局
            QTimer.singleShot(150, self._deferred_fit)

    def _deferred_fit(self):
        """延迟执行 fit_all_in_view，确保 widget 已完成布局且 viewport 尺寸有效"""
        if self._canvas_view and self._canvas_view.viewport().width() > 0:
            self._canvas_view.fit_all_in_view()

    def export_composite_image(self) -> str:
        return self._canvas_view.export_composite_image()

    def get_canvas_view(self):
        return self._canvas_view


# ============================================================
#  SmartPSAgentNode — 主容器
# ============================================================

class SmartPSAgentNode(QGraphicsRectItem):
    """
    [DEPRECATED] AGENT 风格 PS 流水线节点，原嵌入统一画布。
    已被 smart_ps_window.py (SmartPSWindow) + smart_ps_nodes.py 替代。
    保留此类是为了向后兼容，新代码请勿使用。
    """

    def __init__(self, scene_index: int, scene_id: int, data_hub,
                 assets: list = None, first_open: bool = True,
                 on_saved: Optional[Callable] = None,
                 on_closed: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)

        self.scene_index = scene_index
        self.scene_id = scene_id
        self._data_hub = data_hub
        self._assets = assets or []
        self._first_open = first_open
        self._on_saved = on_saved
        self._on_closed = on_closed

        # 状态
        self._is_minimized = False
        self._close_hovered = False
        self._minimize_hovered = False

        # 设置矩形
        self.setRect(0, 0, NODE_WIDTH, NODE_HEIGHT)
        self.setZValue(950)  # 高于一般卡片
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # 内部组件
        self._input_panel: Optional[InputColumnPanel] = None
        self._output_panel: Optional[OutputColumnPanel] = None
        self._canvas_proxy: Optional[QGraphicsProxyWidget] = None
        self._embedded_widget: Optional[EmbeddedCanvasWidget] = None
        self._pipeline_nodes: List = []  # PipelineStageNode 列表

        # 连线管理器
        self._connections: List = []

        # 延迟初始化内部组件
        QTimer.singleShot(0, self._init_internal_components)

    def _init_internal_components(self):
        """延迟初始化内部组件（确保 scene 已添加）"""
        if not self.scene():
            QTimer.singleShot(50, self._init_internal_components)
            return

        # 输入列
        input_h = NODE_HEIGHT - TITLE_H
        self._input_panel = InputColumnPanel(
            INPUT_COL_W, input_h, parent=self)
        self._input_panel.setPos(0, TITLE_H)

        # 加载输入槽
        for asset in self._assets:
            name = asset.get('name', '资产')
            img = asset.get('image_path', '')
            self._input_panel.add_slot(name, img, 'asset')

        # 输出列
        self._output_panel = OutputColumnPanel(
            OUTPUT_COL_W, input_h, parent=self,
            on_snapshot=self._do_snapshot,
            on_output=self._do_output)
        self._output_panel.setPos(NODE_WIDTH - OUTPUT_COL_W, TITLE_H)

        # PS 画布区（QGraphicsProxyWidget）
        canvas_w = NODE_WIDTH - INPUT_COL_W - OUTPUT_COL_W
        canvas_h = NODE_HEIGHT - TITLE_H - PIPELINE_H

        self._embedded_widget = EmbeddedCanvasWidget(
            data_hub=self._data_hub,
            scene_id=self.scene_id,
            assets=self._assets,
            first_open=self._first_open)
        self._embedded_widget.setFixedSize(int(canvas_w), int(canvas_h))

        self._canvas_proxy = QGraphicsProxyWidget(self)
        self._canvas_proxy.setWidget(self._embedded_widget)
        self._canvas_proxy.setPos(INPUT_COL_W, TITLE_H + PIPELINE_H)

        # 预处理管线区域（在画布上方）
        self._init_pipeline_area()

    def _init_pipeline_area(self):
        """初始化预处理管线节点区域"""
        from .smart_ps_pipeline import (
            ViewAngleNode, ExpressionNode, AIMattingNode, HDUpscaleNode
        )

        pipeline_x = INPUT_COL_W + 20
        pipeline_y = TITLE_H + 10
        stage_gap = 20

        stages = [
            ViewAngleNode(parent=self),
            ExpressionNode(parent=self),
            AIMattingNode(parent=self),
        ]

        x = pipeline_x
        for stage in stages:
            stage.setPos(x, pipeline_y)
            x += stage.STAGE_WIDTH + stage_gap
            self._pipeline_nodes.append(stage)

    def _do_snapshot(self):
        """拍摄快照：导出当前画布合成图"""
        if not self._embedded_widget:
            return
        export_path = self._embedded_widget.export_composite_image()
        if export_path and os.path.isfile(export_path):
            pixmap = QPixmap(export_path)
            if self._output_panel:
                self._output_panel.add_snapshot(pixmap, export_path)

    def _do_output(self):
        """输出到下一环节"""
        if not self._embedded_widget:
            return
        export_path = self._embedded_widget.export_composite_image()
        if export_path:
            if self._on_saved:
                self._on_saved(self.scene_index, self.scene_id, export_path)

    def _do_close(self):
        """关闭节点：保存 + 导出 + 通知"""
        if self._embedded_widget:
            self._embedded_widget.save_scene()
            export_path = self._embedded_widget.export_composite_image()
            if export_path and self._on_saved:
                self._on_saved(self.scene_index, self.scene_id, export_path)

        if self._on_closed:
            self._on_closed(self)

    def _do_minimize(self):
        """最小化：折叠为缩略图"""
        self._is_minimized = not self._is_minimized
        if self._is_minimized:
            # 隐藏内部组件
            if self._input_panel:
                self._input_panel.setVisible(False)
            if self._output_panel:
                self._output_panel.setVisible(False)
            if self._canvas_proxy:
                self._canvas_proxy.setVisible(False)
            for node in self._pipeline_nodes:
                node.setVisible(False)
            # 缩小矩形
            self.setRect(0, 0, 240, 60)
        else:
            # 恢复
            if self._input_panel:
                self._input_panel.setVisible(True)
            if self._output_panel:
                self._output_panel.setVisible(True)
            if self._canvas_proxy:
                self._canvas_proxy.setVisible(True)
            for node in self._pipeline_nodes:
                node.setVisible(True)
            self.setRect(0, 0, NODE_WIDTH, NODE_HEIGHT)
        self.update()

    # === 绘制 ===

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # LOD 极简
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_SIMPLIFY_ZOOM:
            painter.fillRect(rect, QColor(28, 28, 36) if dark else QColor(250, 250, 255))
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 节点背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)

        # 渐变背景
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if dark:
            grad.setColorAt(0, QColor(30, 30, 40, 245))
            grad.setColorAt(1, QColor(22, 22, 30, 250))
        else:
            grad.setColorAt(0, QColor(252, 252, 255, 250))
            grad.setColorAt(1, QColor(245, 245, 250, 250))
        painter.fillPath(bg_path, QBrush(grad))

        # 标题栏
        title_path = QPainterPath()
        title_rect = QRectF(rect.x(), rect.y(), rect.width(), TITLE_H)
        # 只圆角上边
        title_path.moveTo(rect.x() + CORNER_RADIUS, rect.y())
        title_path.lineTo(rect.right() - CORNER_RADIUS, rect.y())
        title_path.arcTo(QRectF(rect.right() - 2 * CORNER_RADIUS, rect.y(),
                                2 * CORNER_RADIUS, 2 * CORNER_RADIUS), 90, -90)
        title_path.lineTo(rect.right(), rect.y() + TITLE_H)
        title_path.lineTo(rect.x(), rect.y() + TITLE_H)
        title_path.lineTo(rect.x(), rect.y() + CORNER_RADIUS)
        title_path.arcTo(QRectF(rect.x(), rect.y(),
                                2 * CORNER_RADIUS, 2 * CORNER_RADIUS), 180, -90)
        title_path.closeSubpath()

        title_bg = QColor(32, 32, 42, 230) if dark else QColor(235, 238, 245, 240)
        painter.fillPath(title_path, QBrush(title_bg))

        # 标题文字
        if self._is_minimized:
            title_text = f"智能PS — 场景 {self.scene_index + 1} (已最小化)"
        else:
            title_text = f"智能PS — 场景 {self.scene_index + 1}"

        painter.setPen(QPen(QColor(200, 210, 230) if dark else QColor(50, 50, 70)))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(title_rect.adjusted(12, 0, -80, 0),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         title_text)

        # 关闭按钮 (右上角)
        close_rect = QRectF(rect.right() - 34, rect.y() + 6, 24, 24)
        self._close_rect = close_rect
        if self._close_hovered:
            close_path = QPainterPath()
            close_path.addRoundedRect(close_rect, 4, 4)
            painter.fillPath(close_path, QBrush(COLOR_CLOSE_HOVER))
        painter.setPen(QPen(QColor(200, 200, 210) if dark else QColor(80, 80, 90), 1.5))
        cx, cy = close_rect.center().x(), close_rect.center().y()
        painter.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
        painter.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx - 5, cy + 5))

        # 最小化按钮
        min_rect = QRectF(rect.right() - 62, rect.y() + 6, 24, 24)
        self._minimize_rect = min_rect
        if self._minimize_hovered:
            min_path = QPainterPath()
            min_path.addRoundedRect(min_rect, 4, 4)
            painter.fillPath(min_path, QBrush(COLOR_MINIMIZE_HOVER))
        painter.setPen(QPen(QColor(200, 200, 210) if dark else QColor(80, 80, 90), 1.5))
        mx, my = min_rect.center().x(), min_rect.center().y()
        painter.drawLine(QPointF(mx - 5, my), QPointF(mx + 5, my))

        # 外边框
        border_pen = QPen(COLOR_BORDER, 1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(bg_path)

        # 选中高亮
        if self.isSelected():
            sel_pen = QPen(COLOR_ACCENT, 2)
            painter.setPen(sel_pen)
            painter.drawPath(bg_path)

        # 预处理管线区域分隔线（画布上方）
        if not self._is_minimized:
            pipeline_line_y = TITLE_H + PIPELINE_H
            painter.setPen(QPen(COLOR_SECTION_BORDER, 1))
            painter.drawLine(
                QPointF(INPUT_COL_W, pipeline_line_y),
                QPointF(NODE_WIDTH - OUTPUT_COL_W, pipeline_line_y))

    # === 事件处理 ===

    def hoverMoveEvent(self, event):
        pos = event.pos()
        old_close = self._close_hovered
        old_min = self._minimize_hovered

        self._close_hovered = (hasattr(self, '_close_rect')
                               and self._close_rect.contains(pos))
        self._minimize_hovered = (hasattr(self, '_minimize_rect')
                                  and self._minimize_rect.contains(pos))

        if old_close != self._close_hovered or old_min != self._minimize_hovered:
            self.update()

    def hoverLeaveEvent(self, event):
        self._close_hovered = False
        self._minimize_hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            # 关闭按钮
            if hasattr(self, '_close_rect') and self._close_rect.contains(pos):
                QTimer.singleShot(0, self._do_close)
                event.accept()
                return
            # 最小化按钮
            if hasattr(self, '_minimize_rect') and self._minimize_rect.contains(pos):
                QTimer.singleShot(0, self._do_minimize)
                event.accept()
                return
            # 标题栏拖拽
            if pos.y() <= TITLE_H:
                super().mousePressEvent(event)
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击最小化状态下展开"""
        if self._is_minimized:
            self._do_minimize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        if self._is_minimized:
            expand = menu.addAction("展开")
            expand.triggered.connect(self._do_minimize)
        else:
            minimize = menu.addAction("最小化")
            minimize.triggered.connect(self._do_minimize)
        menu.addSeparator()
        snapshot = menu.addAction("拍摄快照")
        snapshot.triggered.connect(self._do_snapshot)
        menu.addSeparator()
        close = menu.addAction("关闭")
        close.triggered.connect(self._do_close)
        menu.exec(event.screenPos())
