"""
涛割 - 统一剧情模式无限画布
三个区域（大场景序列、分镜节奏、剧本执行）合并为一个统一无限画布，
每个区域用 ZoneFrame（可拖拽可缩放的圆角容器）包裹。
支持跨区域曲线连线 + AnimatedDot 动画。
支持渐进式工作流：空白画布 → 导入文本 → 场景化 → 分析 → 分镜化。
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Set
import copy
import os

from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsPathItem, QGraphicsItem,
    QGraphicsScene, QMenu, QPushButton, QFileDialog, QMessageBox,
    QGraphicsSimpleTextItem, QWidget, QStyleOptionGraphicsItem,
    QSlider, QLabel, QHBoxLayout, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QFontMetrics, QCursor, QTransform,
)

from ui import theme
from ui.components.base_canvas_view import BaseCanvasView, LOD_TEXT_MIN_PX
from ui.components.canvas_connections import (
    compute_bezier_path, AnimatedDot, CurvedConnectionLine,
)
from ui.components.zones.mindmap_branch_node import (
    SceneConnectionManager, MindMapBranchNode,
)
from ui.components.zones.undo_manager import UndoManager, CanvasSnapshot


# ============================================================
#  常量
# ============================================================

TITLE_BAR_HEIGHT = 40
CORNER_RADIUS = 12
RESIZE_HANDLE_SIZE = 16
ZONE_GAP = 350  # 区域之间的间距（加大以让跨区域曲线更自然）
SOURCE_BOX_GAP = 80  # SourceTextBox 与 Zone 1 底边之间的间距

# ── 风格提示词映射 ──
STYLE_PROMPTS = {
    '无风格': '',
    '真人电影': '4K超高清，真人实拍质感，电影级柔光，面部光影均匀，无过曝无暗角，细节拉满，画面通透无噪点。',
    '3D国漫': '3D风格，超高清，最高画质，电影级高质量写实逼真，艳丽色彩，高质量画面4k高清，3d半写实画风，unity渲染效果。',
    '2D国漫': '2D国漫风格，中国动画风格，赛璐珞上色，干净线稿，平涂，杰作，高分辨率。',
    '现代3D国风': '新三维现代都市3D风格，超高清，最高画质，细腻渲染，高质量写实逼真，艳丽色彩，高质量画面4k高清，3d半写实画风，unity渲染效果。',
    '赛博朋克': '赛博朋克风格，霓虹粉蓝光影，清晰对焦，杰作，3D CGI渲染，电影级光影，8k分辨率，极高细节。',
}

# ── 分镜组图系统指令（作为 Gemini systemInstruction 字段，不混入用户消息） ──
STORYBOARD_SYSTEM_PROMPT = """你是一个专业的视觉导演Agent，专门为"分镜（Division）"生成多宫格图片。
将用户输入的画面描述生成为一组{grid}宫格图片的完整故事板,不带任何字幕，中间有逻辑的发展。
确保生成的画面在色彩、角色和情绪上具有极高的一致性，使其看起来像是一组电影分镜头或情绪短片的图片素材。"""


# ============================================================
#  CanvasState — 画布状态枚举
# ============================================================

class CanvasState(Enum):
    WELCOME = "welcome"              # 空白画布 + "双击画布开始造梦"
    IMPORT_POPUP = "import_popup"    # 导入按钮组显示中
    SOURCE_LOADED = "source_loaded"  # 源文本框已加载
    SCENES_SPLIT = "scenes_split"    # 场景拆分完成
    SCENES_ANALYZED = "analyzed"     # 场景分析完成
    SHOTS_CREATED = "shots_created"  # 分镜创建完成


# ============================================================
#  ZoneHeaderButton — 标题栏按钮数据
# ============================================================

class ZoneHeaderButton:
    """标题栏按钮（非 QWidget，用 hit-test + QPainter 实现）"""

    def __init__(self, label: str, callback: Callable, accent: bool = False,
                 enabled: bool = True):
        self.label = label
        self.callback = callback
        self.accent = accent
        self.enabled = enabled
        self.rect = QRectF()  # 由 paint 时计算
        self._hovered = False


# ============================================================
#  ZoneFrame — 可拖拽可缩放的区域容器
# ============================================================

class ZoneFrame(QGraphicsRectItem):
    """
    统一画布中的区域容器。
    - 标题栏可拖拽移动整个 ZoneFrame
    - 右下角手柄可缩放
    - 内容区域内的子图形项由 ZoneDelegate 管理
    """

    MIN_WIDTH = 200
    MIN_HEIGHT = 150

    def __init__(self, zone_id: str, title: str, width: float, height: float,
                 parent=None):
        super().__init__(parent)
        self.zone_id = zone_id
        self._title = title
        self._buttons: List[ZoneHeaderButton] = []
        self._is_active = False
        self._status_text = ""

        # 拖拽状态
        self._is_dragging_title = False
        self._drag_start_scene = QPointF()
        self._drag_start_pos = QPointF()

        # 缩放状态
        self._is_resizing = False
        self._resize_start_scene = QPointF()
        self._resize_start_rect = QRectF()

        # 回调
        self._on_moved_callback: Optional[Callable] = None
        self._on_resized_callback: Optional[Callable] = None

        self.setRect(0, 0, width, height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(0)

    @property
    def content_origin(self) -> QPointF:
        """内容区域的左上角（相对于 ZoneFrame）"""
        return QPointF(0, TITLE_BAR_HEIGHT)

    @property
    def content_rect(self) -> QRectF:
        """内容区域的矩形"""
        r = self.rect()
        return QRectF(0, TITLE_BAR_HEIGHT, r.width(), r.height() - TITLE_BAR_HEIGHT)

    def set_active(self, active: bool):
        self._is_active = active
        self.update()

    def set_status(self, text: str):
        self._status_text = text
        self.update()

    def add_button(self, label: str, callback: Callable, accent: bool = False,
                   enabled: bool = True) -> ZoneHeaderButton:
        btn = ZoneHeaderButton(label, callback, accent, enabled)
        self._buttons.append(btn)
        self.update()
        return btn

    def set_on_moved(self, callback: Callable):
        self._on_moved_callback = callback

    def set_on_resized(self, callback: Callable):
        self._on_resized_callback = callback

    def auto_fit_content(self, items: list):
        """根据子项的包围盒自动调整 ZoneFrame 大小"""
        if not items:
            return
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        for item in items:
            br = item.mapRectToItem(self, item.boundingRect())
            min_x = min(min_x, br.left())
            min_y = min(min_y, br.top())
            max_x = max(max_x, br.right())
            max_y = max(max_y, br.bottom())

        if min_x == float('inf'):
            return

        padding = 20
        new_w = max(self.MIN_WIDTH, max_x + padding)
        new_h = max(self.MIN_HEIGHT, max_y + padding)
        self.setRect(0, 0, new_w, new_h)
        if self._on_resized_callback:
            self._on_resized_callback()

    # ==================== 绘制 ====================

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < 0.12:
            bg = QColor(30, 30, 34) if dark else QColor(248, 248, 252)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)
        bg_color = QColor(30, 30, 34, 230) if dark else QColor(248, 248, 252, 230)
        painter.fillPath(bg_path, QBrush(bg_color))

        # 边框
        if self._is_active:
            border_pen = QPen(QColor(theme.accent()), 2)
        else:
            border_pen = QPen(QColor(theme.border()), 1)
        painter.setPen(border_pen)
        painter.drawPath(bg_path)

        # 标题栏背景
        title_path = QPainterPath()
        title_rect = QRectF(0, 0, rect.width(), TITLE_BAR_HEIGHT)
        # 用 clip 只圆化上面两个角
        title_path.addRoundedRect(
            QRectF(0, 0, rect.width(), TITLE_BAR_HEIGHT + CORNER_RADIUS),
            CORNER_RADIUS, CORNER_RADIUS
        )
        title_clip = QPainterPath()
        title_clip.addRect(QRectF(0, 0, rect.width(), TITLE_BAR_HEIGHT))
        title_path = title_path & title_clip

        title_bg = QColor(38, 38, 42, 200) if dark else QColor(240, 240, 244, 200)
        painter.fillPath(title_path, QBrush(title_bg))

        # 标题栏分隔线
        painter.setPen(QPen(QColor(theme.separator()), 0.5))
        painter.drawLine(
            QPointF(0, TITLE_BAR_HEIGHT),
            QPointF(rect.width(), TITLE_BAR_HEIGHT)
        )

        # LOD 文本隐藏优化
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        if not _hide_text:
            # 标题文本
            painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            painter.setPen(QPen(QColor(theme.text_primary())))
            painter.drawText(
                QRectF(14, 0, 200, TITLE_BAR_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self._title
            )

            # 状态文本（标题右侧）
            if self._status_text:
                painter.setFont(QFont("Microsoft YaHei", 9))
                painter.setPen(QPen(QColor(theme.text_tertiary())))
                painter.drawText(
                    QRectF(180, 0, 200, TITLE_BAR_HEIGHT),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    self._status_text
                )

            # 标题栏按钮
            self._paint_buttons(painter, rect)

        # 右下角缩放手柄
        self._paint_resize_handle(painter, rect)

    def _paint_buttons(self, painter: QPainter, rect: QRectF):
        """绘制标题栏按钮并计算热区"""
        btn_font = QFont("Microsoft YaHei", 10)
        fm = QFontMetrics(btn_font)

        x = rect.width() - 12
        btn_h = 26
        btn_y = (TITLE_BAR_HEIGHT - btn_h) / 2

        # 从右往左绘制
        for btn in reversed(self._buttons):
            text_w = fm.horizontalAdvance(btn.label)
            btn_w = text_w + 20
            x -= btn_w

            btn_rect = QRectF(x, btn_y, btn_w, btn_h)
            btn.rect = btn_rect

            # 按钮背景
            btn_path = QPainterPath()
            btn_path.addRoundedRect(btn_rect, 6, 6)

            if not btn.enabled:
                bg = QColor(theme.bg_tertiary())
                fg = QColor(theme.text_tertiary())
            elif btn.accent:
                bg = QColor(theme.accent()) if not btn._hovered else QColor(theme.accent_hover())
                fg = QColor(255, 255, 255)
            else:
                bg = QColor(theme.btn_bg()) if not btn._hovered else QColor(theme.btn_bg_hover())
                fg = QColor(theme.text_secondary()) if not btn._hovered else QColor(theme.text_primary())

            painter.fillPath(btn_path, QBrush(bg))
            if not btn.accent:
                painter.setPen(QPen(QColor(theme.btn_border()), 0.5))
                painter.drawPath(btn_path)

            painter.setFont(btn_font)
            painter.setPen(QPen(fg))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, btn.label)

            x -= 6  # 按钮间距

    def _paint_resize_handle(self, painter: QPainter, rect: QRectF):
        """绘制右下角缩放手柄"""
        handle_rect = self._resize_handle_rect()
        color = QColor(theme.text_tertiary())
        painter.setPen(QPen(color, 1.5))
        # 画两条对角线表示拖拽
        x = handle_rect.right() - 4
        y = handle_rect.bottom() - 4
        for offset in [0, 5]:
            painter.drawLine(
                QPointF(x - 10 + offset, y),
                QPointF(x, y - 10 + offset)
            )

    def _resize_handle_rect(self) -> QRectF:
        r = self.rect()
        return QRectF(
            r.width() - RESIZE_HANDLE_SIZE,
            r.height() - RESIZE_HANDLE_SIZE,
            RESIZE_HANDLE_SIZE,
            RESIZE_HANDLE_SIZE
        )

    # ==================== 鼠标事件 ====================

    def _is_in_title_bar(self, local_pos: QPointF) -> bool:
        return 0 <= local_pos.y() < TITLE_BAR_HEIGHT

    def _is_in_resize_handle(self, local_pos: QPointF) -> bool:
        return self._resize_handle_rect().contains(local_pos)

    def _hit_test_button(self, local_pos: QPointF) -> Optional[ZoneHeaderButton]:
        for btn in self._buttons:
            if btn.rect.contains(local_pos) and btn.enabled:
                return btn
        return None

    def handle_title_press(self, scene_pos: QPointF, local_pos: QPointF) -> bool:
        """处理标题栏按下事件，返回 True 表示已处理"""
        # 检查按钮点击
        btn = self._hit_test_button(local_pos)
        if btn:
            btn.callback()
            return True

        # 否则开始拖拽
        self._is_dragging_title = True
        self._drag_start_scene = scene_pos
        self._drag_start_pos = self.pos()
        return True

    def handle_resize_press(self, scene_pos: QPointF) -> bool:
        self._is_resizing = True
        self._resize_start_scene = scene_pos
        self._resize_start_rect = QRectF(self.rect())
        return True

    def handle_mouse_move(self, scene_pos: QPointF):
        if self._is_dragging_title:
            delta = scene_pos - self._drag_start_scene
            self.setPos(self._drag_start_pos + delta)
            if self._on_moved_callback:
                self._on_moved_callback()
        elif self._is_resizing:
            delta = scene_pos - self._resize_start_scene
            new_w = max(self.MIN_WIDTH, self._resize_start_rect.width() + delta.x())
            new_h = max(self.MIN_HEIGHT, self._resize_start_rect.height() + delta.y())
            self.setRect(0, 0, new_w, new_h)
            if self._on_resized_callback:
                self._on_resized_callback()
            self.update()

    def handle_mouse_release(self):
        was_dragging = self._is_dragging_title or self._is_resizing
        self._is_dragging_title = False
        self._is_resizing = False
        return was_dragging

    def is_busy(self) -> bool:
        return self._is_dragging_title or self._is_resizing

    def hoverMoveEvent(self, event):
        local_pos = event.pos()

        # 更新按钮 hover 状态
        any_hovered = False
        for btn in self._buttons:
            was_hovered = btn._hovered
            btn._hovered = btn.rect.contains(local_pos) and btn.enabled
            if btn._hovered != was_hovered:
                self.update()
            if btn._hovered:
                any_hovered = True

        # 更新光标
        if self._is_in_resize_handle(local_pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif any_hovered:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        elif self._is_in_title_bar(local_pos):
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        for btn in self._buttons:
            btn._hovered = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()
        super().hoverLeaveEvent(event)


# ============================================================
#  CrossZoneConnectionManager — 跨区域连线管理
# ============================================================

class CrossZoneConnectionManager:
    """
    管理跨区域连线：
    - Act 选中 → Zone1 到 Zone2 的连线
    - Shot 选中 → Zone2 到 Zone3 的连线
    """

    def __init__(self, scene: QGraphicsScene):
        self._scene = scene
        self._act_connection: Optional[CurvedConnectionLine] = None
        self._shot_connection: Optional[CurvedConnectionLine] = None

        # 当前连线的源/目标项
        self._act_source_item: Optional[QGraphicsItem] = None
        self._act_target_items: List[QGraphicsItem] = []
        self._shot_source_item: Optional[QGraphicsItem] = None
        self._shot_target_item: Optional[QGraphicsItem] = None

        # 连线图形项列表（用于批量清理）
        self._act_lines: List[QGraphicsPathItem] = []
        self._act_dots: List[AnimatedDot] = []
        self._shot_line: Optional[QGraphicsPathItem] = None
        self._shot_dot: Optional[AnimatedDot] = None

    def show_act_connections(self, source_item: QGraphicsItem,
                             target_items: List[QGraphicsItem]):
        """显示 Act → Shot 连线"""
        self.clear_act_connections()
        if not source_item or not target_items:
            return

        self._act_source_item = source_item
        self._act_target_items = target_items

        for target in target_items:
            from_rect = source_item.sceneBoundingRect()
            to_rect = target.sceneBoundingRect()
            path = compute_bezier_path(from_rect, to_rect)

            line_item = QGraphicsPathItem()
            pen = QPen(QColor(0, 180, 255, 150), 2)
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            line_item.setPen(pen)
            line_item.setPath(path)
            line_item.setZValue(500)
            self._scene.addItem(line_item)
            self._act_lines.append(line_item)

            dot = AnimatedDot(self._scene, path)
            dot.start()
            self._act_dots.append(dot)

    def show_shot_connection(self, source_item: QGraphicsItem,
                             target_item: QGraphicsItem):
        """显示 Shot → Execution 连线"""
        self.clear_shot_connection()
        if not source_item or not target_item:
            return

        self._shot_source_item = source_item
        self._shot_target_item = target_item

        from_rect = source_item.sceneBoundingRect()
        to_rect = target_item.sceneBoundingRect()
        path = compute_bezier_path(from_rect, to_rect)

        line_item = QGraphicsPathItem()
        pen = QPen(QColor(76, 217, 100, 150), 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_item.setPen(pen)
        line_item.setPath(path)
        line_item.setZValue(500)
        self._scene.addItem(line_item)
        self._shot_line = line_item

        self._shot_dot = AnimatedDot(self._scene, path)
        self._shot_dot.start()

    def update_all(self):
        """Zone 移动后更新所有连线"""
        self._update_act_connections()
        self._update_shot_connection()

    def _update_act_connections(self):
        if not self._act_source_item or not self._act_target_items:
            return
        for i, target in enumerate(self._act_target_items):
            if i >= len(self._act_lines):
                break
            from_rect = self._act_source_item.sceneBoundingRect()
            to_rect = target.sceneBoundingRect()
            path = compute_bezier_path(from_rect, to_rect)
            self._act_lines[i].setPath(path)
            if i < len(self._act_dots):
                self._act_dots[i].set_path(path)

    def _update_shot_connection(self):
        if not self._shot_source_item or not self._shot_target_item:
            return
        if self._shot_line:
            from_rect = self._shot_source_item.sceneBoundingRect()
            to_rect = self._shot_target_item.sceneBoundingRect()
            path = compute_bezier_path(from_rect, to_rect)
            self._shot_line.setPath(path)
            if self._shot_dot:
                self._shot_dot.set_path(path)

    def clear_act_connections(self):
        for dot in self._act_dots:
            dot.remove()
        self._act_dots.clear()
        for line in self._act_lines:
            if line.scene():
                self._scene.removeItem(line)
        self._act_lines.clear()
        self._act_source_item = None
        self._act_target_items.clear()

    def clear_shot_connection(self):
        if self._shot_dot:
            self._shot_dot.remove()
            self._shot_dot = None
        if self._shot_line and self._shot_line.scene():
            self._scene.removeItem(self._shot_line)
        self._shot_line = None
        self._shot_source_item = None
        self._shot_target_item = None

    def clear_all(self):
        self.clear_act_connections()
        self.clear_shot_connection()


# ============================================================
#  QuickNavBar — 右上角快速导航按钮区
# ============================================================

class QuickNavBar(QWidget):
    """
    画布右上角的快速导航按钮条（viewport 子控件）。
    水平排列：场景区 | 分镜区 | 角色道具 | 图片 | 视频
    """

    nav_clicked = pyqtSignal(str)  # key: 'act' / 'shot' / 'asset' / 'images' / 'video'

    BTN_HEIGHT = 30
    BTN_PADDING_H = 14
    BTN_SPACING = 2
    BAR_PADDING = 6
    CORNER_RADIUS = 10

    BUTTONS = [
        ('act', '场景区', True),
        ('shot', '分镜区', True),
        ('asset_req', '资产需求', True),
        ('images', '图片', True),
        ('video', '视频', False),  # 暂时 disabled
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered_key: Optional[str] = None
        self._btn_rects: dict = {}  # key -> QRectF
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._calculate_size()

    def _calculate_size(self):
        """计算按钮布局和总尺寸"""
        font = QFont("Microsoft YaHei", 9)
        fm = QFontMetrics(font)
        x = self.BAR_PADDING
        for key, label, enabled in self.BUTTONS:
            text_w = fm.horizontalAdvance(label)
            btn_w = text_w + self.BTN_PADDING_H * 2
            self._btn_rects[key] = QRectF(x, self.BAR_PADDING,
                                           btn_w, self.BTN_HEIGHT)
            x += btn_w + self.BTN_SPACING
        total_w = x - self.BTN_SPACING + self.BAR_PADDING
        total_h = self.BTN_HEIGHT + self.BAR_PADDING * 2
        self.setFixedSize(int(total_w), int(total_h))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        dark = theme.is_dark()
        rect = QRectF(0, 0, self.width(), self.height())

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        bg_color = QColor(28, 28, 32, 220) if dark else QColor(250, 250, 254, 235)
        painter.fillPath(bg_path, QBrush(bg_color))

        # 边框
        border_c = QColor(255, 255, 255, 12) if dark else QColor(0, 0, 0, 8)
        painter.setPen(QPen(border_c, 0.5))
        painter.drawPath(bg_path)

        # 按钮
        btn_font = QFont("Microsoft YaHei", 9)
        painter.setFont(btn_font)

        for key, label, enabled in self.BUTTONS:
            btn_rect = self._btn_rects.get(key)
            if not btn_rect:
                continue

            is_hovered = (key == self._hovered_key and enabled)

            # 按钮背景
            btn_path = QPainterPath()
            btn_path.addRoundedRect(btn_rect, 6, 6)

            if not enabled:
                fg = QColor(255, 255, 255, 50) if dark else QColor(0, 0, 0, 60)
            elif is_hovered:
                hover_bg = QColor(theme.accent())
                hover_bg.setAlpha(30)
                painter.fillPath(btn_path, QBrush(hover_bg))
                fg = QColor(theme.accent())
            else:
                fg = QColor(200, 200, 200) if dark else QColor(80, 80, 80)

            painter.setPen(QPen(fg))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, label)

        painter.end()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        old = self._hovered_key
        self._hovered_key = None
        for key, label, enabled in self.BUTTONS:
            rect = self._btn_rects.get(key)
            if rect and rect.contains(QPointF(pos.x(), pos.y())) and enabled:
                self._hovered_key = key
                break
        if self._hovered_key != old:
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_key = None
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            for key, label, enabled in self.BUTTONS:
                rect = self._btn_rects.get(key)
                if rect and rect.contains(QPointF(pos.x(), pos.y())) and enabled:
                    self.nav_clicked.emit(key)
                    return
        super().mousePressEvent(event)


# ============================================================
#  ScriptCanvasMiniMap — 剧本画布小地图
# ============================================================

class ScriptCanvasMiniMap(QWidget):
    """剧本画布导航小地图 — 显示 ZoneFrame 布局和视口范围"""

    MINIMAP_W = 200
    MINIMAP_H = 140

    def __init__(self, canvas_view: 'UnifiedStoryCanvasView', parent=None):
        super().__init__(parent)
        self._canvas_view = canvas_view
        self._dragging = False

        self.setFixedSize(self.MINIMAP_W, self.MINIMAP_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(100)
        self._refresh_timer.timeout.connect(self.update)
        self._refresh_timer.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        painter.setBrush(QBrush(QColor(20, 20, 25, 210)))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)

        scene = self._canvas_view._canvas_scene
        zones = getattr(self._canvas_view, '_zones', {})
        if not zones:
            painter.setPen(QColor(255, 255, 255, 50))
            painter.setFont(QFont("Arial", 9))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无内容")
            painter.end()
            return

        items_rect = scene.itemsBoundingRect()
        if items_rect.isEmpty():
            painter.end()
            return

        pad = 12
        draw_w = self.width() - pad * 2
        draw_h = self.height() - pad * 2

        sx = draw_w / items_rect.width() if items_rect.width() > 0 else 1
        sy = draw_h / items_rect.height() if items_rect.height() > 0 else 1
        scale = min(sx, sy)

        scaled_w = items_rect.width() * scale
        scaled_h = items_rect.height() * scale
        off_x = pad + (draw_w - scaled_w) / 2
        off_y = pad + (draw_h - scaled_h) / 2

        def to_mini(scene_x, scene_y):
            return (
                off_x + (scene_x - items_rect.left()) * scale,
                off_y + (scene_y - items_rect.top()) * scale,
            )

        self._map_items_rect = items_rect
        self._map_scale = scale
        self._map_off_x = off_x
        self._map_off_y = off_y

        # 绘制 ZoneFrame
        zone_colors = {
            'act': QColor(0, 122, 204, 140),
            'shot': QColor(0, 180, 100, 140),
            'asset_req': QColor(200, 120, 50, 140),
        }
        for zid, zone in zones.items():
            rect = zone.sceneBoundingRect()
            mx, my = to_mini(rect.left(), rect.top())
            mw = rect.width() * scale
            mh = rect.height() * scale
            fill = zone_colors.get(zid, QColor(80, 80, 90, 140))
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor(255, 255, 255, 40), 0.5))
            painter.drawRoundedRect(QRectF(mx, my, mw, mh), 2, 2)

        # 视口范围
        vp_rect = self._canvas_view.mapToScene(
            self._canvas_view.viewport().rect()
        ).boundingRect()
        vx, vy = to_mini(vp_rect.left(), vp_rect.top())
        vw = vp_rect.width() * scale
        vh = vp_rect.height() * scale

        painter.setBrush(QBrush(QColor(255, 255, 255, 15)))
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1.5))
        painter.drawRoundedRect(QRectF(vx, vy, vw, vh), 2, 2)

        painter.end()

    def _mini_to_scene(self, mx, my):
        if not hasattr(self, '_map_items_rect'):
            return QPointF(0, 0)
        scene_x = self._map_items_rect.left() + (mx - self._map_off_x) / self._map_scale
        scene_y = self._map_items_rect.top() + (my - self._map_off_y) / self._map_scale
        return QPointF(scene_x, scene_y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._navigate_to(event.pos())

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._navigate_to(event.pos())

    def mouseReleaseEvent(self, event):
        self._dragging = False

    def _navigate_to(self, pos):
        scene_pt = self._mini_to_scene(pos.x(), pos.y())
        self._canvas_view.centerOn(scene_pt)


# ============================================================
#  ScriptCanvasControlBar — 剧本画布左下角控制栏
# ============================================================

class ScriptCanvasControlBar(QWidget):
    """
    剧本画布左下角控制栏：
    - 小地图开关
    - 适应视图按钮
    - 缩放滑块 + 百分比
    """

    MARGIN = 10

    def __init__(self, canvas_view: 'UnifiedStoryCanvasView', parent=None):
        super().__init__(parent)
        self._canvas_view = canvas_view
        self._mini_map: Optional[ScriptCanvasMiniMap] = None
        self._mini_map_visible = False

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._init_ui()
        self._apply_style()

        self._canvas_view.zoom_changed.connect(self._on_zoom_changed)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 小地图开关
        self._minimap_btn = QPushButton("小地图")
        self._minimap_btn.setCheckable(True)
        self._minimap_btn.setFixedHeight(24)
        self._minimap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._minimap_btn.clicked.connect(self._toggle_minimap)
        layout.addWidget(self._minimap_btn)

        # 适应视图
        self._fit_btn = QPushButton("适应")
        self._fit_btn.setFixedHeight(24)
        self._fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_btn.clicked.connect(self._fit_view)
        layout.addWidget(self._fit_btn)

        # 分隔线
        sep = QFrame()
        sep.setFixedSize(1, 18)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.15);")
        layout.addWidget(sep)

        # 缩放滑块
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setFixedWidth(100)
        self._zoom_slider.setFixedHeight(20)
        self._zoom_slider.setMinimum(5)
        self._zoom_slider.setMaximum(500)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self._zoom_slider)

        # 缩放百分比标签
        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(40)
        layout.addWidget(self._zoom_label)

        self.adjustSize()

    def _apply_style(self):
        self.setStyleSheet("""
            ScriptCanvasControlBar {
                background-color: rgba(20, 20, 25, 210);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
                color: white;
            }
            QPushButton:checked {
                background-color: rgba(0, 122, 204, 0.4);
                border-color: rgba(0, 122, 204, 0.6);
                color: white;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: rgba(0, 122, 204, 0.9);
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: rgba(0, 122, 204, 0.4);
                border-radius: 2px;
            }
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 10px;
                font-family: Consolas;
            }
        """)

    def reposition(self):
        """定位到父控件左下角"""
        if self.parent():
            ph = self.parent().height()
            self.move(self.MARGIN, ph - self.height() - self.MARGIN)
            if self._mini_map and self._mini_map.isVisible():
                self._mini_map.move(
                    self.MARGIN,
                    ph - self.height() - self.MARGIN - ScriptCanvasMiniMap.MINIMAP_H - 6
                )

    def _toggle_minimap(self):
        if self._mini_map is None:
            self._mini_map = ScriptCanvasMiniMap(self._canvas_view, parent=self.parent())
        self._mini_map_visible = not self._mini_map_visible
        self._mini_map.setVisible(self._mini_map_visible)
        self._minimap_btn.setChecked(self._mini_map_visible)
        self.reposition()

    def _fit_view(self):
        self._canvas_view.fit_all_in_view()

    def _on_slider_changed(self, value):
        self._canvas_view.set_zoom(value)

    def _on_zoom_changed(self, percent: int):
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(min(500, max(5, percent)))
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{percent}%")
# ============================================================

class UnifiedStoryCanvasView(BaseCanvasView):
    """
    统一剧情模式画布视图。
    一个 QGraphicsScene 承载三个 ZoneFrame 及其内容，
    支持跨区域曲线连线和动画。
    支持渐进式工作流状态机。
    """

    # 对外信号
    act_selected = pyqtSignal(int)       # act_id
    shot_selected = pyqtSignal(int)      # scene_index (全局)
    groups_changed = pyqtSignal()        # 分组变化
    shots_changed = pyqtSignal()         # 分镜变化

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # 接收键盘事件
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        # Undo/Redo 管理器
        self._undo_manager = UndoManager(self)

        # 视图状态缓存（按 project_id 保存缩放比例和滚动位置）
        self._view_states: Dict[int, dict] = {}  # {project_id: {zoom, h_scroll, v_scroll, canvas_state}}
        self._current_project_id: Optional[int] = None

        # 画布状态机
        self._canvas_state = CanvasState.WELCOME

        # ZoneFrame 实例（懒创建）
        self._zone_act: Optional[ZoneFrame] = None
        self._zone_shot: Optional[ZoneFrame] = None
        self._zone_asset_req: Optional[ZoneFrame] = None
        self._zones: Dict[str, ZoneFrame] = {}

        # Delegates（懒创建）
        self._act_delegate = None
        self._shot_delegate = None
        self._asset_req_delegate = None
        self._ai_single_search_worker = None  # AI 单资产搜索 worker 引用
        self._ma_workers: dict = {}             # 多视角生成 workers {req_id: worker}

        # 跨区域连线管理
        self._connection_mgr: Optional[SceneConnectionManager] = None

        # ZoneFrame 操作状态
        self._active_zone: Optional[ZoneFrame] = None
        self._zone_interacting: Optional[ZoneFrame] = None

        # 左键交互追踪（确保 mouseMoveEvent 能路由到 delegate）
        self._left_press_delegate = None  # 左键按下时激活的 delegate

        # 画布级别框选（Zone 外空白区域）
        self._is_canvas_rubber_banding = False
        self._canvas_rubber_band_start: Optional[QPointF] = None
        self._canvas_rubber_band_rect: Optional[QGraphicsRectItem] = None

        # 按钮引用（懒创建时赋值）
        self._act_analysis_btn = None
        self._shot_ai_split_btn = None

        # 欢迎状态组件
        self._welcome_text: Optional[QGraphicsSimpleTextItem] = None

        # 源文本框
        self._source_text_box: Optional['SourceTextBox'] = None

        # 导入弹出按钮组
        self._import_popup: Optional['ImportPopup'] = None

        # 底部控制台
        self._console_bar: Optional['BottomConsoleBar'] = None

        # 图片控制台
        self._image_console: Optional['ShotImageConsole'] = None

        # 视频控制台
        self._video_console: Optional['ShotVideoConsole'] = None

        # 源文本→组背景的贝塞尔曲线
        self._source_to_group_curves: List[QGraphicsPathItem] = []

        # 变体连线管理（基础角色图 → 变体卡）
        # key = variant 的 asset_idx（负数），value = VariantLinkLine
        self._variant_links: dict = {}

        # 控制台当前关联的目标图片节点（解决同 scene_index 多节点时的定位问题）
        self._console_target_node = None

        # 从已有图片节点触发重新生成时，标记源节点（生成时创建新节点而非复用）
        self._regenerate_from_node = None

        # 提示词 tooltip（hover 图片节点时显示）
        self._prompt_tooltip = None
        self._tooltip_source_node = None

        # 快速导航栏
        self._quick_nav: Optional[QuickNavBar] = None

        # 动画光点全局开关
        self._animations_enabled = True

        # 连接 data_hub 信号
        if self.data_hub:
            self.data_hub.asset_library_updated.connect(self._on_asset_library_updated)
        self._anim_toggle_btn = QPushButton("✦", self.viewport())
        self._anim_toggle_btn.setFixedSize(32, 32)
        self._anim_toggle_btn.setCheckable(True)
        self._anim_toggle_btn.setChecked(True)
        self._anim_toggle_btn.setToolTip("开关曲线光点动画")
        self._anim_toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._anim_toggle_btn.clicked.connect(self._toggle_animations)
        self._apply_anim_toggle_style()

        # 底部左下角控制栏（小地图+适应+缩放滑块）
        self._control_bar = ScriptCanvasControlBar(self, parent=self)
        self._control_bar.show()

        # 视口懒加载：可视区域变化时加载/卸载图片
        self._lazy_load_margin = 200  # 预加载边距（像素）
        self.viewport_rect_changed.connect(self._on_viewport_changed)

        # 缩放期间暂停动画（减少重绘，大幅提升缩放流畅度）
        self.zooming_active_changed.connect(self._on_zooming_active_changed)

        # 进入初始状态
        self._setup_welcome_state()

    # ==================== Undo/Redo 快照 ====================

    def capture_snapshot(self) -> CanvasSnapshot:
        """拍摄当前画布的完整快照"""
        groups_data = []
        sentence_order = []
        if self._act_delegate:
            groups_data = self._act_delegate._get_groups_data_for_save()
            sentence_order = [c.sentence_index for c in self._act_delegate._sentence_cards]

        db_acts_data = []
        if self.data_hub and self.data_hub.acts_data:
            db_acts_data = copy.deepcopy(self.data_hub.acts_data)

        zone_positions = {}
        zone_sizes = {}
        for zid, zone in self._zones.items():
            pos = zone.pos()
            zone_positions[zid] = (pos.x(), pos.y())
            rect = zone.rect()
            zone_sizes[zid] = (rect.width(), rect.height())

        return CanvasSnapshot(
            canvas_state=self._canvas_state.value,
            groups_data=copy.deepcopy(groups_data),
            sentence_order=sentence_order,
            db_acts_data=db_acts_data,
            zone_positions=zone_positions,
            zone_sizes=zone_sizes,
        )

    def restore_from_snapshot(self, snap: CanvasSnapshot):
        """从快照恢复画布状态"""
        # 1. 恢复画布状态
        for state in CanvasState:
            if state.value == snap.canvas_state:
                self._canvas_state = state
                break

        # 2. 恢复 Zone 位置和大小
        for zid, (x, y) in snap.zone_positions.items():
            zone = self._zones.get(zid)
            if zone:
                zone.setPos(x, y)
        for zid, (w, h) in snap.zone_sizes.items():
            zone = self._zones.get(zid)
            if zone:
                zone.setRect(0, 0, w, h)

        # 3. 恢复 data_hub.acts_data
        if self.data_hub:
            self.data_hub.acts_data = copy.deepcopy(snap.db_acts_data)

        # 4. 恢复分组数据 → 重建 UI
        if self._act_delegate and snap.groups_data:
            # 同步数据库
            if self.data_hub and self.data_hub.current_project_id:
                self.data_hub.act_controller.create_acts_from_ai(
                    self.data_hub.current_project_id, snap.groups_data
                )
                # 刷新 data_hub
                self.data_hub.acts_data = copy.deepcopy(snap.db_acts_data)

            # 检查是否有分析数据
            from .zone_delegates import _tags_has_content
            has_analysis = any(
                _tags_has_content(a.get('tags')) or a.get('summary')
                for a in snap.groups_data
            )
            if has_analysis:
                self._act_delegate._apply_act_groups(snap.groups_data)
            else:
                self._act_delegate._apply_grouping_only(snap.groups_data)

            self._act_delegate._current_acts_data = snap.groups_data

        # 5. 刷新分镜区
        if self._shot_delegate:
            self._shot_delegate.load_all_acts_shots()

        # 6. 重建连线
        self._rebuild_persistent_connections()
        self._reposition_source_text_box()
        self._rebuild_source_to_group_curves()

        # 7. 恢复图片预览节点
        QTimer.singleShot(200, self._restore_image_preview_nodes)

        # 8. 更新控制台状态
        self._update_console_buttons()

    # ==================== 状态管理 ====================

    def _setup_welcome_state(self):
        """初始化欢迎状态"""
        self._canvas_state = CanvasState.WELCOME
        self.set_locked(True)

        # 隐藏快速导航栏
        if self._quick_nav:
            self._quick_nav.setVisible(False)

        # 创建欢迎提示文字
        self._welcome_text = QGraphicsSimpleTextItem("双击画布开始造梦")
        font = QFont("Microsoft YaHei", 18, QFont.Weight.Light)
        self._welcome_text.setFont(font)
        dark = theme.is_dark()
        self._welcome_text.setBrush(QBrush(
            QColor(255, 255, 255, 80) if dark else QColor(0, 0, 0, 60)
        ))
        self._welcome_text.setZValue(100)
        self._canvas_scene.addItem(self._welcome_text)
        # 居中定位到视口中心
        QTimer.singleShot(50, self._center_welcome_text)

    def _center_welcome_text(self):
        if self._welcome_text:
            vp_center = self.mapToScene(self.viewport().rect().center())
            br = self._welcome_text.boundingRect()
            self._welcome_text.setPos(
                vp_center.x() - br.width() / 2,
                vp_center.y() - br.height() / 2,
            )

    def _remove_welcome_text(self):
        if self._welcome_text:
            if self._welcome_text.scene():
                self._canvas_scene.removeItem(self._welcome_text)
            self._welcome_text = None

    def _transition_to(self, new_state: CanvasState):
        """切换画布状态"""
        self._canvas_state = new_state
        self._update_console_buttons()
        self._update_quick_nav_visibility()

    # ==================== ZoneFrame 懒创建 ====================

    def _ensure_act_zone(self):
        """懒创建 Zone 1（大场景序列区）"""
        if self._zone_act:
            self._zone_act.setVisible(True)
            return
        self._zone_act = ZoneFrame("act", "大场景序列", 1200, 500)
        self._canvas_scene.addItem(self._zone_act)
        self._zones["act"] = self._zone_act
        self._zone_act.set_on_moved(self._on_zone_moved)
        self._zone_act.set_on_resized(self._on_zone_resized)

        # 定位在 SourceTextBox 上方
        if self._source_text_box:
            box_pos = self._source_text_box.scenePos()
            self._zone_act.setPos(box_pos.x(), box_pos.y() - ZONE_GAP - 500)
        else:
            self._zone_act.setPos(0, 1200)

        # 持久连线管理器
        if not self._connection_mgr:
            self._connection_mgr = SceneConnectionManager(self._canvas_scene)
            self._connection_mgr.set_on_toggle(self._on_branch_toggled)
            self._connection_mgr.set_on_solo(self._on_branch_solo)

        # 创建 Act 委托
        if not self._act_delegate:
            from .zone_delegates import ActSequenceZoneDelegate
            self._act_delegate = ActSequenceZoneDelegate(
                self._zone_act, self._canvas_scene, self.data_hub, self
            )
            self._act_delegate.act_clicked.connect(self._on_act_clicked)
            self._act_delegate.groups_changed.connect(self._on_groups_changed)
            self._act_delegate.analysis_completed.connect(self._on_analysis_completed)
            self._act_delegate.single_act_shot_requested.connect(
                self._on_single_act_shot_requested)
            self._act_delegate.analysis_progress.connect(
                self._on_analysis_progress)
            self._act_delegate.summary_selection_changed.connect(
                self._on_summary_selection_changed)

        # 标题栏按钮
        self._zone_act.add_button("导入", self._act_delegate.import_file)
        self._zone_act.add_button("场景拆分", self._act_delegate.ai_split, accent=True)
        self._zone_act.add_button("快速拆分", self._act_delegate.quick_split)
        self._act_analysis_btn = self._zone_act.add_button(
            "场景分析", self._act_delegate.scene_analysis,
            accent=True, enabled=False
        )

    def _ensure_shot_zone(self):
        """懒创建 Zone 2（分镜节奏区）"""
        if self._zone_shot:
            self._zone_shot.setVisible(True)
            return
        self._ensure_act_zone()  # 依赖 Zone 1

        zone2_h = 600
        act_top = self._zone_act.pos().y()
        zone2_y = act_top - ZONE_GAP - zone2_h
        self._zone_shot = ZoneFrame("shot", "分镜节奏", 1200, zone2_h)
        self._zone_shot.setPos(self._zone_act.pos().x(), zone2_y)
        self._canvas_scene.addItem(self._zone_shot)
        self._zones["shot"] = self._zone_shot
        self._zone_shot.set_on_moved(self._on_zone_moved)
        self._zone_shot.set_on_resized(self._on_zone_resized)

        # 创建 Shot 委托
        if not self._shot_delegate:
            from .zone_delegates import ShotRhythmZoneDelegate
            self._shot_delegate = ShotRhythmZoneDelegate(
                self._zone_shot, self._canvas_scene, self.data_hub, self
            )
            self._shot_delegate.shot_clicked.connect(self._on_shot_clicked)
            self._shot_delegate.shots_changed.connect(self._on_shots_changed)
            self._shot_delegate.act_shot_completed.connect(
                self._on_act_shot_completed)
            self._shot_delegate.batch_progress.connect(
                self._on_batch_progress)
            self._shot_delegate.batch_all_completed.connect(
                self._auto_extract_asset_requirements)
            self._shot_delegate.generate_image_requested.connect(
                self._on_generate_image_requested)
            self._shot_delegate.generate_video_requested.connect(
                self._on_generate_video_requested)  # (int, float, float)
            self._shot_delegate.smart_ps_requested.connect(
                self._on_smart_ps_requested)

        # 标题栏按钮
        self._shot_ai_split_btn = self._zone_shot.add_button(
            "分镜化", self._shot_delegate.ai_split_shots,
            accent=True, enabled=False
        )

    def _ensure_asset_req_zone(self):
        """懒创建 Zone 5（资产需求区）— 位于 Zone 2 左侧"""
        if self._zone_asset_req:
            self._zone_asset_req.setVisible(True)
            return
        self._ensure_shot_zone()  # 依赖 Zone 2

        zone5_w = 900
        zone5_h = 600
        zone2_left = self._zone_shot.pos().x()
        zone2_y = self._zone_shot.pos().y()
        self._zone_asset_req = ZoneFrame("asset_req", "资产需求", zone5_w, zone5_h)
        self._zone_asset_req.setPos(zone2_left - ZONE_GAP - zone5_w, zone2_y)
        self._canvas_scene.addItem(self._zone_asset_req)
        self._zones["asset_req"] = self._zone_asset_req
        self._zone_asset_req.set_on_moved(self._on_zone_moved)
        self._zone_asset_req.set_on_resized(self._on_zone_resized)

        # 创建委托
        if not self._asset_req_delegate:
            from .zone_delegates import AssetRequirementZoneDelegate
            self._asset_req_delegate = AssetRequirementZoneDelegate(
                self._zone_asset_req, self._canvas_scene, self.data_hub, self
            )
            self._asset_req_delegate.generate_asset_requested.connect(
                self._on_generate_asset_requested)
            self._asset_req_delegate.bind_asset_requested.connect(
                self._on_bind_asset_requested)
            self._asset_req_delegate.ai_fill_requested.connect(
                self._on_ai_fill_asset_requested)
            self._asset_req_delegate.multi_angle_requested.connect(
                self._on_multi_angle_requested)

        # 标题栏按钮（先 add 的在列表前面，reversed 绘制时显示在最左边）
        self._zone_asset_req.add_button(
            "重排", self._asset_req_delegate.relayout_cards,
            accent=False
        )
        self._zone_asset_req.add_button(
            "更新到资产库", self._on_sync_assets_to_library,
            accent=False
        )
        self._zone_asset_req.add_button(
            "提取资产需求", self._asset_req_delegate.extract_requirements,
            accent=True
        )

    def _ensure_all_zones(self):
        """创建所有 Zone（用于恢复已有项目），并确保可见"""
        self._ensure_act_zone()
        self._ensure_shot_zone()
        self._ensure_asset_req_zone()
        # 确保所有 Zone 可见（切换项目时可能被隐藏）
        if self._zone_act:
            self._zone_act.setVisible(True)
        if self._zone_shot:
            self._zone_shot.setVisible(True)
        if self._zone_asset_req:
            self._zone_asset_req.setVisible(True)

    # ==================== 底部控制台 ====================

    def _ensure_console_bar(self):
        """懒创建底部控制台"""
        if self._console_bar:
            return
        from .bottom_console_bar import BottomConsoleBar
        self._console_bar = BottomConsoleBar(self.viewport())
        self._console_bar.scene_split_requested.connect(self._on_scene_split_requested)
        self._console_bar.scene_analysis_requested.connect(self._on_scene_analysis_requested)
        self._console_bar.shot_split_requested.connect(self._on_shot_split_requested)
        self._console_bar.raise_()
        self._position_console_bar()

    def _position_console_bar(self):
        """定位底部控制台到视口底部居中"""
        if not self._console_bar:
            return
        self._console_bar.adjustSize()
        w = self._console_bar.sizeHint().width()
        h = self._console_bar.height()
        vp = self.viewport().rect()
        self._console_bar.setGeometry(
            (vp.width() - w) // 2,
            vp.height() - h - 16,
            w, h,
        )

    def _ensure_image_console(self):
        """懒创建图片控制台"""
        if self._image_console:
            return
        from .shot_image_console import ShotImageConsole
        self._image_console = ShotImageConsole(self.viewport())
        self._image_console.generate_image_requested.connect(
            self._on_console_generate_image)
        self._image_console.generate_board_requested.connect(
            self._on_console_generate_board)
        self._image_console.raise_()
        self._position_image_console()

    def _ensure_prompt_tooltip(self):
        """懒创建提示词 tooltip"""
        if self._prompt_tooltip:
            return
        from .shot_card_actions import ImagePromptTooltip
        self._prompt_tooltip = ImagePromptTooltip(self.viewport())
        self._prompt_tooltip.fill_console_requested.connect(
            self._on_fill_console_from_tooltip)

    def _on_image_hover_show(self, node):
        """图片节点 hover 进入 → 显示提示词 tooltip"""
        self._ensure_prompt_tooltip()
        self._tooltip_source_node = node
        self._prompt_tooltip.cancel_hide()
        self._prompt_tooltip.set_data(node._gen_params)

        # 计算 tooltip 位置：图片节点下方（viewport 坐标）
        node_scene_rect = node.mapRectToScene(node.rect())
        bottom_center = QPointF(node_scene_rect.center().x(),
                                node_scene_rect.bottom())
        vp_pos = self.mapFromScene(bottom_center)
        tooltip_x = vp_pos.x() - self._prompt_tooltip.width() // 2
        tooltip_y = vp_pos.y() + 8

        # 边界修正
        vp = self.viewport().rect()
        tooltip_x = max(4, min(tooltip_x, vp.width() - self._prompt_tooltip.width() - 4))
        if tooltip_y + self._prompt_tooltip.height() > vp.height() - 10:
            # 放到节点上方
            top_pos = self.mapFromScene(QPointF(node_scene_rect.center().x(),
                                                 node_scene_rect.top()))
            tooltip_y = top_pos.y() - self._prompt_tooltip.height() - 8

        self._prompt_tooltip.move(int(tooltip_x), int(tooltip_y))
        self._prompt_tooltip.show()
        self._prompt_tooltip.raise_()

    def _on_image_hover_hide(self):
        """图片节点 hover 离开 → 延迟隐藏 tooltip"""
        if self._prompt_tooltip:
            self._prompt_tooltip.schedule_hide()

    def _on_fill_console_from_tooltip(self, params: dict):
        """tooltip "填入控制台"按钮 → 打开控制台并填入参数"""
        scene_index = params.get('scene_index')
        self._ensure_image_console()
        if self._image_console and scene_index is not None:
            self._image_console.set_scene_index(scene_index)

            # ── 从数据库重新加载资产数据（与 _on_generate_image_requested 相同逻辑）──
            # 加载该项目所有已绑定资产（供 @ 提及弹窗使用）
            all_assets_by_type: dict = {}
            try:
                project_id = self.data_hub.current_project_id
                if project_id:
                    all_project_assets = self.data_hub.asset_controller.get_all_assets(
                        project_id)
                    for a in all_project_assets:
                        t = a.get('asset_type', '')
                        all_assets_by_type.setdefault(t, []).append(a)
            except Exception as e:
                print(f"[涛割] 加载项目资产失败: {e}")
            self._image_console.set_available_assets(all_assets_by_type)

            # 恢复提示词 + 资产内联缩略图（从数据库获取最新资产数据）
            base_prompt = params.get('base_prompt', '')
            prompt = params.get('prompt', '')
            text = base_prompt if base_prompt else prompt
            if not base_prompt and '\n参考资产：' in text:
                text = text[:text.find('\n参考资产：')]

            asset_thumbnails = []
            asset_ref_images = []
            try:
                project_id = self.data_hub.current_project_id
                if project_id:
                    assets = self.data_hub.asset_controller.get_assets_for_scene(
                        project_id, scene_index)
                    for a in assets:
                        img = a.get('main_reference_image', '')
                        name = a.get('name', '')
                        asset_thumbnails.append({
                            'name': name,
                            'type': a.get('asset_type', ''),
                            'image_path': img,
                        })
                        if img:
                            asset_ref_images.append(img)
            except Exception as e:
                print(f"[涛割] 关联资产查询失败: {e}")

            # 如果数据库中没有找到资产，回退使用 params 中保存的资产数据
            if not asset_thumbnails:
                saved_assets = params.get('assets', [])
                if saved_assets:
                    asset_thumbnails = saved_assets
                    asset_ref_images = [
                        a.get('image_path', '') for a in saved_assets
                        if a.get('image_path', '')
                    ]

            self._image_console.set_prompt_with_assets(text, asset_thumbnails)
            self._image_console.set_reference_images(asset_ref_images)

            # 恢复非提示词参数（ratio、model、style 等），跳过提示词（已由上面处理）
            self._image_console.set_params_from_dict(params, skip_prompt=True)

            self._position_image_console()
            if not self._image_console.is_visible_state:
                self._hide_context_buttons()
                self._image_console.slide_up()

    # ==================== 快速导航栏 ====================

    def _ensure_quick_nav(self):
        """懒创建快速导航栏"""
        if self._quick_nav:
            return
        self._quick_nav = QuickNavBar(self.viewport())
        self._quick_nav.nav_clicked.connect(self._on_quick_nav)
        self._position_quick_nav()

    def _position_quick_nav(self):
        """定位快速导航栏到 viewport 右上角"""
        if not self._quick_nav:
            return
        vp = self.viewport().rect()
        x = vp.width() - self._quick_nav.width() - 16
        y = 16
        self._quick_nav.move(int(x), int(y))

    def _position_anim_toggle_btn(self):
        """定位动画光点开关按钮到 viewport 右上角（在 quick_nav 下方）"""
        vp = self.viewport().rect()
        x = vp.width() - 42
        # 如果有 quick_nav 且可见，放在其下方
        y_offset = 10
        if self._quick_nav and self._quick_nav.isVisible():
            y_offset = self._quick_nav.y() + self._quick_nav.height() + 6
        self._anim_toggle_btn.move(int(x), int(y_offset))
        self._anim_toggle_btn.raise_()

    def _on_zooming_active_changed(self, active: bool):
        """缩放期间暂停所有动画定时器，缩放结束后恢复（大幅降低重绘开销）"""
        if not self._animations_enabled:
            # 用户已手动关闭动画，无需管理
            return
        if active:
            # 暂停 — SceneConnectionManager 光点
            if self._connection_mgr:
                self._connection_mgr.set_animations_enabled(False)
            # 暂停 — ShotImageConnection 粒子 + 路径更新定时器
            if hasattr(self, '_image_connections'):
                conns = self._image_connections.values() if isinstance(self._image_connections, dict) else self._image_connections
                for conn in conns:
                    conn.set_animations_enabled(False)
            # 暂停 — 小地图刷新定时器
            if hasattr(self, '_control_bar') and self._control_bar:
                mm = getattr(self._control_bar, '_mini_map', None)
                if mm and hasattr(mm, '_refresh_timer'):
                    mm._refresh_timer.stop()
        else:
            # 恢复 — SceneConnectionManager 光点
            if self._connection_mgr:
                self._connection_mgr.set_animations_enabled(True)
            # 恢复 — ShotImageConnection 粒子
            if hasattr(self, '_image_connections'):
                conns = self._image_connections.values() if isinstance(self._image_connections, dict) else self._image_connections
                for conn in conns:
                    conn.set_animations_enabled(True)
            # 恢复 — 小地图刷新定时器
            if hasattr(self, '_control_bar') and self._control_bar:
                mm = getattr(self._control_bar, '_mini_map', None)
                if mm and hasattr(mm, '_refresh_timer'):
                    mm._refresh_timer.start()

    def _toggle_animations(self, checked: bool):
        """切换曲线光点动画的显示/隐藏"""
        self._animations_enabled = checked
        self._apply_anim_toggle_style()
        # SceneConnectionManager 的光点
        if self._connection_mgr:
            self._connection_mgr.set_animations_enabled(checked)
        # ShotImageConnection 的粒子
        if hasattr(self, '_image_connections'):
            for conn in self._image_connections:
                conn.set_animations_enabled(checked)

    def _apply_anim_toggle_style(self):
        """刷新动画开关按钮样式"""
        checked = self._anim_toggle_btn.isChecked()
        accent = theme.accent()
        if checked:
            self._anim_toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {accent};
                    color: #fff;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {theme.accent_hover()};
                }}
            """)
        else:
            dark = theme.is_dark()
            bg = "rgba(40, 40, 44, 200)" if dark else "rgba(240, 240, 244, 220)"
            fg = "#666" if dark else "#999"
            self._anim_toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg};
                    color: {fg};
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {accent};
                    color: #fff;
                }}
            """)

    def _on_viewport_changed(self, visible_rect: QRectF):
        """视口变化回调：对可视区域内/外的图片节点执行懒加载/卸载"""
        expanded = visible_rect.adjusted(
            -self._lazy_load_margin, -self._lazy_load_margin,
            self._lazy_load_margin, self._lazy_load_margin
        )
        for item in self._canvas_scene.items():
            if hasattr(item, 'load_pixmap') and hasattr(item, 'release_pixmap'):
                if expanded.intersects(item.sceneBoundingRect()):
                    item.load_pixmap()
                else:
                    item.release_pixmap()

    def _update_quick_nav_visibility(self):
        """根据画布状态显示/隐藏快速导航栏"""
        if self._canvas_state == CanvasState.WELCOME:
            if self._quick_nav:
                self._quick_nav.setVisible(False)
        else:
            self._ensure_quick_nav()
            self._quick_nav.setVisible(True)
            self._quick_nav.raise_()

    def _on_quick_nav(self, key: str):
        """快速导航按钮点击回调"""
        if key == 'act':
            self._scroll_to_zone(self._zone_act)
        elif key == 'shot':
            self._scroll_to_zone(self._zone_shot)
        elif key == 'asset_req':
            self._scroll_to_zone(self._zone_asset_req)
        elif key == 'images':
            self._scroll_to_images()
        elif key == 'video':
            pass  # 暂未实现

    def _scroll_to_zone(self, zone, zoom: float = 0.6):
        """通用方法：将视口居中到指定 zone"""
        if not zone:
            return
        t = QTransform()
        t.scale(zoom, zoom)
        self.setTransform(t)
        self._zoom_factor = zoom
        self._expand_scene_rect()
        zone_center = zone.sceneBoundingRect().center()
        self.centerOn(zone_center)
        self._expand_scene_rect()
        self.zoom_changed.emit(int(self._zoom_factor * 100))

    def _scroll_to_images(self):
        """将视口居中到所有 ImagePreviewNode 的联合区域"""
        if not hasattr(self, '_image_preview_nodes') or not self._image_preview_nodes:
            # 没有图片节点，fallback 到分镜区
            self._scroll_to_zone(self._zone_shot)
            return

        # 计算所有图片节点的联合 bounding rect
        union_rect = QRectF()
        for node in self._image_preview_nodes:
            if node.scene():
                node_rect = node.mapRectToScene(node.rect())
                if union_rect.isNull():
                    union_rect = node_rect
                else:
                    union_rect = union_rect.united(node_rect)

        if union_rect.isNull():
            self._scroll_to_zone(self._zone_shot)
            return

        # 加边距
        margin = 100
        union_rect.adjust(-margin, -margin, margin, margin)
        self.fitInView(union_rect, Qt.AspectRatioMode.KeepAspectRatio)
        # 更新缩放因子
        self._zoom_factor = self.transform().m11()
        self._expand_scene_rect()
        self.zoom_changed.emit(int(self._zoom_factor * 100))

    def _position_image_console(self):
        """定位图片控制台 — 下边缘锚定到视口下边缘"""
        if not self._image_console:
            return
        vp = self.viewport().rect()
        w = min(vp.width() - self.MARGIN_CONSOLE * 2, 960)
        h = self._image_console.PANEL_HEIGHT

        # 控制台下边缘距离窗口下边缘的固定间距
        bottom_margin = 10
        x = (vp.width() - w) // 2
        y = vp.height() - h - bottom_margin

        # 如果动画正在运行，更新动画的终点值而不是直接 setGeometry
        # （防止动画把 geometry 覆盖回旧值）
        from PyQt6.QtCore import QRect, QPropertyAnimation as _QPA
        anim = getattr(self._image_console, '_slide_anim', None)
        if anim and anim.state() == _QPA.State.Running:
            end_geo = QRect(x, y, w, h)
            start_geo = QRect(x, y + self._image_console.SLIDE_OFFSET, w, h)
            anim.setStartValue(start_geo)
            anim.setEndValue(end_geo)
        else:
            self._image_console.setGeometry(x, y, w, h)

    MARGIN_CONSOLE = 20  # 图片控制台边距

    def _ensure_video_console(self):
        """懒创建视频控制台"""
        if self._video_console:
            return
        from .shot_video_console import ShotVideoConsole
        self._video_console = ShotVideoConsole(self.viewport())
        self._video_console.generate_video_requested.connect(
            self._on_console_generate_video)
        self._video_console.raise_()
        self._position_video_console()

    def _position_video_console(self):
        """定位视频控制台 — 下边缘锚定到视口下边缘"""
        if not self._video_console:
            return
        vp = self.viewport().rect()
        w = min(vp.width() - self.MARGIN_CONSOLE * 2,
                self._video_console.MAX_WIDTH)
        h = self._video_console.PANEL_HEIGHT

        bottom_margin = 10
        x = (vp.width() - w) // 2
        y = vp.height() - h - bottom_margin

        from PyQt6.QtCore import QRect, QPropertyAnimation as _QPA
        anim = getattr(self._video_console, '_slide_anim', None)
        if anim and anim.state() == _QPA.State.Running:
            end_geo = QRect(x, y, w, h)
            start_geo = QRect(x, y + self._video_console.SLIDE_OFFSET, w, h)
            anim.setStartValue(start_geo)
            anim.setEndValue(end_geo)
        else:
            self._video_console.setGeometry(x, y, w, h)

    def _update_console_buttons(self):
        """根据当前画布状态更新控制台按钮启用状态"""
        if not self._console_bar:
            return
        state = self._canvas_state

        if state == CanvasState.SOURCE_LOADED:
            # 源文本已加载 → 场景化可用（当 SourceTextBox 选中时）
            selected = self._source_text_box and self._source_text_box.is_selected
            self._console_bar.set_scene_split_enabled(bool(selected))
            self._console_bar.set_scene_analysis_enabled(False)
            self._console_bar.set_shot_split_enabled(False)
        elif state == CanvasState.SCENES_SPLIT:
            self._console_bar.set_scene_split_enabled(False)
            self._console_bar.set_scene_analysis_enabled(True)
            self._console_bar.set_shot_split_enabled(False)
        elif state == CanvasState.SCENES_ANALYZED:
            self._console_bar.set_scene_split_enabled(False)
            self._console_bar.set_scene_analysis_enabled(False)
            self._console_bar.set_shot_split_enabled(True)
        elif state == CanvasState.SHOTS_CREATED:
            self._console_bar.set_scene_split_enabled(False)
            self._console_bar.set_scene_analysis_enabled(False)
            self._console_bar.set_shot_split_enabled(False)
        else:
            self._console_bar.set_scene_split_enabled(False)
            self._console_bar.set_scene_analysis_enabled(False)
            self._console_bar.set_shot_split_enabled(False)

    # ==================== 上下文感知控制栏 ====================

    def _show_context_button(self, button_name: str, mode: str = 'all',
                             act_ids: Optional[Set[int]] = None):
        """上下文感知地显示控制栏的指定按钮"""
        # 互斥：隐藏图片控制台
        if self._image_console and self._image_console.is_visible_state:
            self._image_console.slide_down()
            # 恢复自动切换的横竖屏状态
            if hasattr(self, '_pre_asset_orientation'):
                self._image_console.set_orientation(self._pre_asset_orientation)
                del self._pre_asset_orientation
        # 互斥：隐藏视频控制台
        if self._video_console and self._video_console.is_visible_state:
            self._video_console.slide_down()
        self._ensure_console_bar()
        self._console_bar.set_active_button(button_name, mode, act_ids)
        # 设置按钮后重新定位（宽度可能变化）
        self._position_console_bar()
        if not self._console_bar.is_visible_state:
            self._console_bar.slide_up()

    def _hide_context_buttons(self):
        """隐藏控制栏"""
        if self._console_bar and self._console_bar.is_visible_state:
            self._console_bar.slide_down()

    def _on_summary_selection_changed(self):
        """场景卡（摘要卡）选中变化 → 更新控制栏"""
        if not self._act_delegate:
            return
        ids = self._act_delegate.get_selected_summary_act_ids()
        all_ids = self._act_delegate.get_all_summary_act_ids()
        if not ids:
            # 无选中 → 隐藏
            self._hide_context_buttons()
            return
        if len(ids) == 1:
            mode = 'single'
        elif ids == all_ids:
            mode = 'all'
        else:
            mode = 'selected'
        self._show_context_button("shot_split", mode, ids)

    def _handle_title_bar_context_button(self, zone):
        """标题栏空白区域点击 → 根据 zone_id 显示上下文按钮"""
        if zone.zone_id == "act":
            if self._canvas_state in (CanvasState.SCENES_SPLIT,
                                      CanvasState.SCENES_ANALYZED,
                                      CanvasState.SHOTS_CREATED):
                self._show_context_button("scene_analysis", mode='all')

    def _handle_act_zone_context_button(self, item):
        """Zone 1 内容区点击 → 上下文感知按钮"""
        from .act_sequence_panel import SentenceCard, ActSummaryCard, ActGroupBackground

        # 沿父链查找真正的卡片类型（itemAt 可能返回子项）
        target = item
        while target:
            if isinstance(target, (ActSummaryCard, SentenceCard, ActGroupBackground)):
                break
            target = target.parentItem()

        if isinstance(target, ActSummaryCard):
            # 场景分析卡点击 → 显示"分镜化"按钮
            # 使用 delegate 的实际选中状态决定 mode（支持多选）
            ids = self._act_delegate.get_selected_summary_act_ids() if self._act_delegate else set()
            all_ids = self._act_delegate.get_all_summary_act_ids() if self._act_delegate else set()
            if not ids:
                return
            if len(ids) == 1:
                mode = 'single'
            elif ids == all_ids:
                mode = 'all'
            else:
                mode = 'selected'
            self._show_context_button("shot_split", mode=mode, act_ids=ids)
            return

        if isinstance(target, (SentenceCard, ActGroupBackground)):
            # 句子卡 / 组背景 → 显示"场景分析"按钮
            if self._canvas_state in (CanvasState.SCENES_SPLIT,
                                      CanvasState.SCENES_ANALYZED,
                                      CanvasState.SHOTS_CREATED):
                self._show_context_button("scene_analysis", mode='all')
            return

        # 其他区域内的空白点击 → 不改变按钮状态

    # ==================== 导入处理 ====================

    def _show_import_popup(self, scene_pos: QPointF):
        """在指定位置弹出导入按钮组"""
        from .import_popup import ImportPopup
        if not self._import_popup:
            self._import_popup = ImportPopup()

        callbacks = [
            ("导入小说", "📖", self._on_import_novel),
            ("导入剧本", "🎬", self._on_import_script),
            ("导入解说SRT", "🎤", self._on_import_srt),
        ]
        self._import_popup.show_at(scene_pos, self._canvas_scene, callbacks)
        self._transition_to(CanvasState.IMPORT_POPUP)

    def _on_import_novel(self):
        """导入小说文件"""
        self._do_import_file("小说文件", "文本文件 (*.txt);;所有文件 (*.*)", "novel")

    def _on_import_script(self):
        """导入剧本文件"""
        self._do_import_file("剧本文件", "文本文件 (*.txt);;Word文档 (*.docx);;所有文件 (*.*)", "script_story")

    def _on_import_srt(self):
        """导入 SRT"""
        if self._import_popup:
            self._import_popup.hide()
        QMessageBox.information(self, "提示", "SRT 导入请使用解说模式")
        self._transition_to(CanvasState.WELCOME)

    def _do_import_file(self, title: str, filters: str, source_type: str):
        """通用文件导入"""
        if self._import_popup:
            self._import_popup.hide()

        file_path, _ = QFileDialog.getOpenFileName(self, f"选择{title}", "", filters)
        if not file_path:
            self._transition_to(CanvasState.WELCOME)
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法读取文件: {e}")
                self._transition_to(CanvasState.WELCOME)
                return
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取文件: {e}")
            self._transition_to(CanvasState.WELCOME)
            return

        if not content.strip():
            QMessageBox.warning(self, "错误", "文件内容为空")
            self._transition_to(CanvasState.WELCOME)
            return

        self._load_source_text(content, source_type, file_path)

    def _load_source_text(self, content: str, source_type: str,
                          file_path: Optional[str] = None):
        """加载源文本到画布"""
        # 移除欢迎文字
        self._remove_welcome_text()

        # 创建 SourceTextBox
        from .source_text_box import SourceTextBox
        if not self._source_text_box:
            self._source_text_box = SourceTextBox()
            self._canvas_scene.addItem(self._source_text_box)
            # 定位到视口中心
            vp_center = self.mapToScene(self.viewport().rect().center())
            self._source_text_box.setPos(
                vp_center.x() - SourceTextBox.DEFAULT_WIDTH / 2,
                vp_center.y() - SourceTextBox.DEFAULT_HEIGHT / 2,
            )

        self._source_text_box.set_text(content)

        # 保存到数据库
        if self.data_hub and self.data_hub.current_project_id:
            self.data_hub.save_source_content(
                self.data_hub.current_project_id, content, source_type
            )
            # 用文件名更新项目名
            if file_path:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                self.data_hub.rename_project(base_name)

        # 显示底部控制台（初始隐藏，等用户点击源文本框后才滑入）
        self._ensure_console_bar()
        self._position_console_bar()

        # 解锁画布
        self.set_locked(False)

        # 状态切换
        self._transition_to(CanvasState.SOURCE_LOADED)

        # 视口聚焦到文本框
        if self._source_text_box:
            box_rect = self._source_text_box.sceneBoundingRect().adjusted(-50, -50, 50, 50)
            self.fitInView(box_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_factor = self.transform().m11()
            self.zoom_changed.emit(int(self._zoom_factor * 100))

    # ==================== 控制台按钮处理 ====================

    def _on_scene_split_requested(self):
        """场景化按钮 → 懒创建 Zone 1 + AI 拆分"""
        if not self._source_text_box or not self._source_text_box.get_text():
            return

        # Undo: 拍摄 before 快照
        self._undo_manager.begin_operation("场景化")

        self._ensure_act_zone()

        # 重新定位 Zone 1 在 SourceTextBox 上方
        if self._source_text_box:
            box_pos = self._source_text_box.scenePos()
            self._zone_act.setPos(
                box_pos.x(),
                box_pos.y() - ZONE_GAP - self._zone_act.rect().height(),
            )

        # 设置项目 ID 并加载文本
        if self.data_hub and self.data_hub.current_project_id:
            self._act_delegate.set_project_id(self.data_hub.current_project_id)

        # 显示进度条（indeterminate）
        if self._console_bar:
            self._console_bar.start_progress("scene_split")

        # 触发 AI 拆分
        self._act_delegate.ai_split()

    def _on_scene_analysis_requested(self):
        """场景分析按钮"""
        if not self._act_delegate:
            return
        # Undo: 拍摄 before 快照
        self._undo_manager.begin_operation("场景分析")
        if self._console_bar:
            self._console_bar.start_progress("scene_analysis")
        self._act_delegate.scene_analysis()

    def _on_shot_split_requested(self):
        """分镜化按钮 → 懒创建 Zone 2 + AI 分镜拆分（上下文感知）"""
        self._ensure_shot_zone()

        # Undo: 拍摄 before 快照
        self._undo_manager.begin_operation("分镜化")

        if self._console_bar:
            self._console_bar.start_progress("shot_split")

        # 读取上下文感知模式
        mode = getattr(self._console_bar, '_active_mode', 'all') if self._console_bar else 'all'
        act_ids = getattr(self._console_bar, '_target_act_ids', None) if self._console_bar else None

        if self._shot_delegate:
            if mode == 'single' and act_ids and len(act_ids) == 1:
                self._shot_delegate.ai_split_single_act(next(iter(act_ids)))
            elif mode == 'selected' and act_ids:
                self._shot_delegate.ai_split_selected_acts(list(act_ids))
            else:
                self._shot_delegate.ai_split_shots()

    # ==================== 源文本框定位 + 曲线 ====================

    def _reposition_source_text_box(self):
        """将源文本框重新定位到大场景序列框 (Zone 1) 正下方居中"""
        if not self._source_text_box or not self._zone_act:
            return
        zone_rect = self._zone_act.sceneBoundingRect()
        box_w = self._source_text_box.rect().width()
        # 水平居中对齐 Zone 1
        box_x = zone_rect.center().x() - box_w / 2
        # 垂直定位在 Zone 1 正下方
        box_y = zone_rect.bottom() + SOURCE_BOX_GAP
        self._source_text_box.setPos(box_x, box_y)

    def _rebuild_source_to_group_curves(self):
        """绘制从各组底部到 SourceTextBox 顶部的贝塞尔虚线曲线"""
        # 清除旧曲线
        for curve in self._source_to_group_curves:
            if curve.scene():
                self._canvas_scene.removeItem(curve)
        self._source_to_group_curves.clear()

        if not self._source_text_box or not self._act_delegate:
            return

        groups = self._act_delegate._groups
        if not groups:
            return

        box_rect = self._source_text_box.sceneBoundingRect()
        created = 0

        for group in groups:
            if group.get('excluded', False):
                continue
            cards = group.get('cards', [])
            if not cards:
                continue
            color = group.get('color', QColor(100, 100, 100))

            # 起点：优先使用组背景底部中点，否则用最底部卡片
            bg = group.get('background')
            if bg and bg.scene():
                bg_rect = bg.mapRectToScene(bg.path().boundingRect())
                start = QPointF(bg_rect.center().x(), bg_rect.bottom())
            else:
                bottom_card = max(cards, key=lambda c: c.sceneBoundingRect().bottom())
                card_rect = bottom_card.sceneBoundingRect()
                start = QPointF(card_rect.center().x(), card_rect.bottom())

            # 终点：SourceTextBox 顶部（X 限制在文本框范围内）
            end_x = max(box_rect.left() + 10, min(box_rect.right() - 10, start.x()))
            end = QPointF(end_x, box_rect.top())

            # 贝塞尔曲线（从组底部向下弯曲到文本框顶部）
            path = QPainterPath()
            path.moveTo(start)
            ctrl_offset = abs(end.y() - start.y()) * 0.4
            path.cubicTo(
                QPointF(start.x(), start.y() + ctrl_offset),
                QPointF(end.x(), end.y() - ctrl_offset),
                end,
            )

            curve_item = QGraphicsPathItem()
            pen = QPen(QColor(color.red(), color.green(), color.blue(), 160), 2.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            curve_item.setPen(pen)
            curve_item.setPath(path)
            curve_item.setZValue(10)
            self._canvas_scene.addItem(curve_item)
            self._source_to_group_curves.append(curve_item)

    # ==================== 外部接口 ====================

    def on_project_loaded(self, project_id: int, project_info: dict):
        """项目加载后初始化"""
        # 保存当前项目的视图状态
        self._save_view_state()

        # 清空 undo 栈（切换项目时不保留旧项目的 undo 历史）
        self._undo_manager.clear()

        # ── 先彻底清理上一个项目的画布内容 ──
        self._cleanup_previous_project()

        self._current_project_id = project_id
        source_content = project_info.get('source_content', '')
        source_type = project_info.get('source_type', '')

        # 判断应该恢复到什么状态
        if source_content and source_type in ('story', 'novel', 'script_story'):
            # 有内容 → 检查是否有 acts
            if self.data_hub and self.data_hub.acts_data:
                # 有 acts → 直接恢复所有 zones
                self._remove_welcome_text()
                self._ensure_all_zones()

                if self._act_delegate:
                    self._act_delegate.set_project_id(project_id)
                if self._shot_delegate:
                    self._shot_delegate.clear()
                if self._asset_req_delegate:
                    self._asset_req_delegate.load_from_db()
                    # 延迟恢复资产图片（等卡片位置确定）
                    QTimer.singleShot(300, self._restore_asset_image_nodes)
                if self._connection_mgr:
                    self._connection_mgr.clear_all()

                # 加载源文本框
                self._load_source_text(source_content, source_type)
                self._transition_to(CanvasState.SCENES_SPLIT)
            else:
                # 有内容但无 acts → SOURCE_LOADED
                self._load_source_text(source_content, source_type)
        else:
            # 无内容或不匹配 → WELCOME
            if self._act_delegate:
                self._act_delegate.set_project_id(project_id)
            # 进入 WELCOME 状态
            if self._canvas_state != CanvasState.WELCOME:
                self._setup_welcome_state()

        # 延迟恢复视图状态（等待内容加载完成）
        QTimer.singleShot(150, self._restore_or_init_view)

    def _cleanup_previous_project(self):
        """彻底清理上一个项目的画布内容，为新项目做准备"""
        # 清理大场景序列区
        if self._act_delegate:
            self._act_delegate._clear_all()

        # 清理分镜区
        if self._shot_delegate:
            self._shot_delegate.clear()

        # 清理连线管理器
        if self._connection_mgr:
            self._connection_mgr.clear_all()

        # 清理资产需求区
        if self._asset_req_delegate:
            try:
                self._asset_req_delegate.clear()
            except Exception:
                pass

        # 清理源文本→组背景的曲线
        for curve in self._source_to_group_curves:
            if curve.scene():
                self._canvas_scene.removeItem(curve)
        self._source_to_group_curves.clear()

        # 清理源文本框
        if self._source_text_box:
            if self._source_text_box.scene():
                self._canvas_scene.removeItem(self._source_text_box)
            self._source_text_box = None

        # 清理图片预览节点和连线
        if hasattr(self, '_image_preview_nodes'):
            for node in list(self._image_preview_nodes.values()) if isinstance(self._image_preview_nodes, dict) else list(self._image_preview_nodes):
                try:
                    if hasattr(node, 'scene') and node.scene():
                        self._canvas_scene.removeItem(node)
                except Exception:
                    pass
            if isinstance(self._image_preview_nodes, dict):
                self._image_preview_nodes.clear()
            else:
                self._image_preview_nodes = []

        if hasattr(self, '_image_connections'):
            for conn in list(self._image_connections.values()) if isinstance(self._image_connections, dict) else list(self._image_connections):
                try:
                    if hasattr(conn, 'remove'):
                        conn.remove()
                except Exception:
                    pass
            if isinstance(self._image_connections, dict):
                self._image_connections.clear()
            else:
                self._image_connections = []

        # 清理变体连线
        for link in list(self._variant_links.values()):
            try:
                if hasattr(link, 'scene') and link.scene():
                    self._canvas_scene.removeItem(link)
            except Exception:
                pass
        self._variant_links.clear()

        # 隐藏 Zone Frames
        if self._zone_act:
            self._zone_act.setVisible(False)
        if self._zone_shot:
            self._zone_shot.setVisible(False)
        if self._zone_asset_req:
            self._zone_asset_req.setVisible(False)

        # 隐藏底部控制台和图片控制台
        if self._console_bar:
            self._console_bar.setVisible(False)
        if self._image_console:
            self._image_console.setVisible(False)
        if self._video_console:
            self._video_console.setVisible(False)

        # 清理欢迎文字
        self._remove_welcome_text()

    def on_acts_loaded(self, acts_data: list):
        """场次数据加载"""
        if not acts_data:
            return

        # 确保 zones 已创建
        self._ensure_act_zone()

        if self._act_delegate:
            self._act_delegate.load_acts(acts_data)

        # 加载已有的分镜卡
        self._ensure_shot_zone()
        if self._shot_delegate:
            self._shot_delegate.load_all_acts_shots()
            self._rebuild_persistent_connections()
            self._on_zone_resized()
            # 恢复已生成图片的预览节点（延迟确保卡片位置已确定）
            QTimer.singleShot(200, self._restore_image_preview_nodes)

        # 如果已有场景分析数据，启用 AI 拆分按钮
        if self._shot_ai_split_btn:
            from .zone_delegates import _tags_has_content
            has_analysis = any(
                _tags_has_content(a.get('tags')) or a.get('summary')
                for a in acts_data
            )
            self._shot_ai_split_btn.enabled = has_analysis
            if self._zone_shot:
                self._zone_shot.update()

        # 更新状态
        if acts_data:
            from .zone_delegates import _tags_has_content
            has_analysis = any(
                _tags_has_content(a.get('tags')) or a.get('summary')
                for a in acts_data
            )
            if has_analysis:
                self._transition_to(CanvasState.SCENES_ANALYZED)
            else:
                self._transition_to(CanvasState.SCENES_SPLIT)

        # 重新定位源文本框到 Zone 1 下方 + 重建源文本→组曲线
        self._reposition_source_text_box()
        self._rebuild_source_to_group_curves()

        # 确保控制台已创建（不自动显示，等用户点击触发滑入）
        self._ensure_console_bar()
        self._position_console_bar()

    # ==================== 信号处理 ====================

    def _on_act_clicked(self, act_id: int):
        """Act 选中 → 加载全场景分镜（连线始终显示，不依赖点击）"""
        self.act_selected.emit(act_id)
        if self._shot_delegate:
            self._shot_delegate.load_act_shots(act_id)

    def _on_shot_clicked(self, scene_index: int):
        """Shot 选中"""
        self.shot_selected.emit(scene_index)

    def _on_groups_changed(self):
        """分组变化通知"""
        self.groups_changed.emit()

        # Undo: commit（覆盖场景化 + 所有手动分组操作）
        if self._undo_manager.is_operation_pending():
            self._undo_manager.commit_operation()

        # 结束场景化进度条
        if self._console_bar:
            self._console_bar.finish_progress("scene_split")
        # 启用场景分析按钮
        if self._act_delegate and self._act_analysis_btn:
            self._act_analysis_btn.enabled = self._act_delegate.get_group_count() > 0
            if self._zone_act:
                self._zone_act.update()
        # 分组变化时禁用 AI 拆分按钮（需要重新分析）
        if self._shot_ai_split_btn:
            self._shot_ai_split_btn.enabled = False
            if self._zone_shot:
                self._zone_shot.update()
        # 刷新分镜区（全场景模式）
        if self._shot_delegate:
            self._shot_delegate.load_all_acts_shots()
        # 重建持久连线
        self._rebuild_persistent_connections()
        # 重新定位源文本框到 Zone 1 下方
        self._reposition_source_text_box()
        # 重建源文本→组曲线
        self._rebuild_source_to_group_curves()
        # 更新状态
        self._transition_to(CanvasState.SCENES_SPLIT)

    def _on_analysis_completed(self):
        """场景分析完成 → 启用分镜区 AI 拆分按钮"""
        # Undo: commit
        if self._undo_manager.is_operation_pending():
            self._undo_manager.commit_operation()

        if self._console_bar:
            self._console_bar.finish_progress("scene_analysis")
        if self._shot_ai_split_btn:
            self._shot_ai_split_btn.enabled = True
            if self._zone_shot:
                self._zone_shot.update()
        # 确保分镜 Zone 已创建
        self._ensure_shot_zone()
        self._transition_to(CanvasState.SCENES_ANALYZED)
        # 重建连线和曲线
        self._rebuild_persistent_connections()
        self._reposition_source_text_box()
        self._rebuild_source_to_group_curves()

    def _on_shots_changed(self):
        """分镜变化通知 — 重建持久连线"""
        self.shots_changed.emit()

        # Undo: commit
        if self._undo_manager.is_operation_pending():
            self._undo_manager.commit_operation()

        # 结束分镜化进度条
        if self._console_bar:
            self._console_bar.finish_progress("shot_split")
        self._rebuild_persistent_connections()
        self._reposition_source_text_box()
        self._rebuild_source_to_group_curves()
        self._transition_to(CanvasState.SHOTS_CREATED)

    def _on_single_act_shot_requested(self, act_id: int):
        """右键请求单场景分镜化"""
        self._ensure_shot_zone()
        if self._console_bar:
            self._console_bar.start_progress("shot_split")
        if self._shot_delegate:
            self._shot_delegate.ai_split_single_act(act_id)

    def _on_act_shot_completed(self, act_id: int):
        """单个场次分镜完成 → 增量重建连线"""
        self._rebuild_persistent_connections()
        self._reposition_source_text_box()
        self._rebuild_source_to_group_curves()

    def _on_batch_progress(self, done: int, total: int):
        """分镜化批量进度更新"""
        if self._console_bar:
            self._console_bar.update_progress("shot_split", done, total)

    def _on_analysis_progress(self, done: int, total: int):
        """场景分析进度更新（完成态由 _on_analysis_completed 处理）"""
        if self._console_bar and done > 0 and total > 0 and done < total:
            self._console_bar.update_progress("scene_analysis", done, total)

    def _on_generate_image_requested(self, scene_index: int,
                                      scene_x: float = 0.0, scene_y: float = 0.0):
        """分镜卡 + 号 → 生成图片 → 创建图片框 + 连线 + 弹出图片控制台"""
        from .shot_card_actions import ImagePreviewNode, ShotImageConnection

        # 找到对应的分镜卡
        shot_card = None
        if self._shot_delegate:
            for card in self._shot_delegate._shot_cards:
                if card.global_index == scene_index:
                    shot_card = card
                    break

        if shot_card:
            # 图片卡位置：以鼠标释放点为底部中心（连线锚点）
            if scene_x != 0.0 or scene_y != 0.0:
                # 用户指定了鼠标释放位置
                img_x = scene_x - ImagePreviewNode.NODE_WIDTH / 2
                img_y = scene_y - ImagePreviewNode.NODE_HEIGHT
            else:
                # 默认 fallback：分镜卡上方 50px
                card_scene_rect = shot_card.mapRectToScene(shot_card.rect())
                img_x = card_scene_rect.center().x() - ImagePreviewNode.NODE_WIDTH / 2
                img_y = card_scene_rect.top() - ImagePreviewNode.NODE_HEIGHT - 50

            img_node = ImagePreviewNode(
                scene_index,
                on_delete=self._on_image_node_deleted,
                on_open_canvas=self._open_intelligent_canvas_for_scene,
            )
            img_node._on_hover_show = self._on_image_hover_show
            img_node._on_hover_hide = self._on_image_hover_hide
            img_node.setPos(img_x, img_y)
            self._canvas_scene.addItem(img_node)

            # 创建连线（初始虚线，生成成功后变实线）
            connection = ShotImageConnection(self._canvas_scene, shot_card, img_node)
            if not self._animations_enabled:
                connection.set_animations_enabled(False)

            # 记录到列表以便后续清理
            if not hasattr(self, '_image_preview_nodes'):
                self._image_preview_nodes = []
                self._image_connections = []
            self._image_preview_nodes.append(img_node)
            self._image_connections.append(connection)

            # 记录当前控制台关联的目标节点
            self._console_target_node = img_node

        # 弹出图片控制台
        self._ensure_image_console()
        if self._image_console:
            self._image_console.set_scene_index(scene_index)

            # ── 先设置数据（影响面板高度），再定位，最后启动动画 ──

            # 加载该项目所有已绑定资产（供 @ 提及弹窗使用）
            all_assets_by_type: dict = {}
            try:
                project_id = self.data_hub.current_project_id
                if project_id:
                    all_project_assets = self.data_hub.asset_controller.get_all_assets(
                        project_id)
                    for a in all_project_assets:
                        t = a.get('asset_type', '')
                        all_assets_by_type.setdefault(t, []).append(a)
            except Exception as e:
                print(f"[涛割] 加载项目资产失败: {e}")
            self._image_console.set_available_assets(all_assets_by_type)

            if shot_card:
                prompt = shot_card.scene_data.get('image_prompt', '')
                if not prompt:
                    prompt = shot_card.scene_data.get('text', '')

                # 关联资产：查找该分镜涉及的已绑定资产
                asset_thumbnails = []
                asset_ref_images = []
                try:
                    project_id = self.data_hub.current_project_id
                    if project_id:
                        assets = self.data_hub.asset_controller.get_assets_for_scene(
                            project_id, scene_index)
                        for idx, a in enumerate(assets, 1):
                            img = a.get('main_reference_image', '')
                            name = a.get('name', '')
                            asset_thumbnails.append({
                                'name': name,
                                'type': a.get('asset_type', ''),
                                'image_path': img,
                            })
                            if img:
                                asset_ref_images.append(img)
                except Exception as e:
                    print(f"[涛割] 关联资产查询失败: {e}")

                self._image_console.set_prompt_with_assets(prompt, asset_thumbnails)
                self._image_console.set_reference_images(asset_ref_images)

            # 数据设完后定位（此时高度已确定），再启动滑入动画
            self._position_image_console()
            if not self._image_console.is_visible_state:
                self._hide_context_buttons()
                # 互斥：隐藏视频控制台
                if self._video_console and self._video_console.is_visible_state:
                    self._video_console.slide_down()
                self._image_console.slide_up()

    def _on_generate_video_requested(self, scene_index: int,
                                      scene_x: float = 0.0, scene_y: float = 0.0):
        """分镜卡 + 号 → 弹出视频控制台"""
        # 找到对应的分镜卡获取提示词和已生成图片
        shot_card = None
        prompt = ""
        source_image = ""
        if self._shot_delegate:
            for card in self._shot_delegate._shot_cards:
                if card.global_index == scene_index:
                    shot_card = card
                    prompt = card.scene_data.get('video_prompt', '')
                    if not prompt:
                        prompt = card.scene_data.get('image_prompt', '')
                    if not prompt:
                        prompt = card.scene_data.get('text', '')
                    source_image = card.scene_data.get('generated_image_path', '') or ''
                    break

        # 弹出视频控制台
        self._ensure_video_console()
        if self._video_console:
            self._video_console.set_scene_index(scene_index)
            self._video_console.set_source_image(source_image)
            self._video_console._update_source_image_indicator()

            # 加载该项目所有已绑定资产（供 @ 提及弹窗使用）
            all_assets_by_type: dict = {}
            try:
                project_id = self.data_hub.current_project_id
                if project_id:
                    all_project_assets = self.data_hub.asset_controller.get_all_assets(
                        project_id)
                    for a in all_project_assets:
                        t = a.get('asset_type', '')
                        all_assets_by_type.setdefault(t, []).append(a)
            except Exception as e:
                print(f"[涛割] 加载项目资产失败: {e}")
            self._video_console.set_available_assets(all_assets_by_type)

            if shot_card:
                # 关联资产
                asset_thumbnails = []
                asset_ref_images = []
                try:
                    project_id = self.data_hub.current_project_id
                    if project_id:
                        assets = self.data_hub.asset_controller.get_assets_for_scene(
                            project_id, scene_index)
                        for a in assets:
                            img = a.get('main_reference_image', '')
                            name = a.get('name', '')
                            asset_thumbnails.append({
                                'name': name,
                                'type': a.get('asset_type', ''),
                                'image_path': img,
                            })
                            if img:
                                asset_ref_images.append(img)
                except Exception as e:
                    print(f"[涛割] 关联资产查询失败: {e}")

                self._video_console.set_prompt_with_assets(prompt, asset_thumbnails)
                self._video_console.set_reference_images(asset_ref_images)
            else:
                self._video_console.set_prompt(prompt)

            self._position_video_console()
            if not self._video_console.is_visible_state:
                # 互斥：隐藏图片控制台和底部控制栏
                self._hide_context_buttons()
                if self._image_console and self._image_console.is_visible_state:
                    self._image_console.slide_down()
                self._video_console.slide_up()

    def _on_smart_ps_requested(self, scene_index: int,
                                scene_x: float = 0.0, scene_y: float = 0.0,
                                first_open: bool = True):
        """分镜卡 + 号 → 智能PS → 打开独立最大化窗口"""
        # 获取 scene_id
        scene_id = None
        shot_card = None
        if self._shot_delegate:
            for card in self._shot_delegate._shot_cards:
                if card.global_index == scene_index:
                    scene_id = card.scene_data.get('id', card.scene_id)
                    shot_card = card
                    break

        if scene_id is None:
            scene_id = scene_index  # fallback

        # 如果已有该场景的窗口且未关闭，聚焦
        if not hasattr(self, '_smart_ps_windows'):
            self._smart_ps_windows = {}
        existing = self._smart_ps_windows.get(scene_index)
        if existing and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        # 记录点击位置，供关闭后创建PS卡使用
        if not hasattr(self, '_ps_click_positions'):
            self._ps_click_positions = {}
        if first_open and (scene_x or scene_y):
            self._ps_click_positions[scene_index] = (scene_x, scene_y)

        # 收集场景关联的资产图片
        assets = self._collect_scene_assets(scene_index)

        # 创建独立最大化窗口
        from .smart_ps_window import SmartPSWindow

        window = SmartPSWindow(
            scene_index=scene_index,
            scene_id=scene_id,
            data_hub=self.data_hub,
            assets=assets,
            first_open=first_open,
            parent=self.window(),
        )
        window.image_saved.connect(self._on_smart_ps_saved)
        window.closed.connect(self._on_smart_ps_window_closed)

        self._smart_ps_windows[scene_index] = window

    def _on_smart_ps_window_closed(self, scene_index: int):
        """智能PS窗口关闭回调"""
        if hasattr(self, '_smart_ps_windows'):
            self._smart_ps_windows.pop(scene_index, None)

    def _on_smart_ps_saved(self, scene_index: int, scene_id: int,
                            image_path: str, shot_card=None):
        """智能PS导出合成图后 → 在画布上创建PS预览卡"""
        import os
        if not image_path or not os.path.isfile(image_path):
            return

        from .shot_card_actions import PSPreviewNode, ShotImageConnection
        from PyQt6.QtGui import QPixmap

        # 查找 shot_card（如果未传入）
        if shot_card is None and self._shot_delegate:
            for card in self._shot_delegate._shot_cards:
                if card.global_index == scene_index:
                    shot_card = card
                    break

        # 删除已有的同场景PS预览卡
        if not hasattr(self, '_ps_preview_nodes'):
            self._ps_preview_nodes = []
        if not hasattr(self, '_ps_connections'):
            self._ps_connections = []

        for i, node in enumerate(self._ps_preview_nodes):
            if node.scene_index == scene_index:
                # 移除旧连线
                for conn in self._ps_connections:
                    try:
                        if conn._image_node == node:
                            conn.remove()
                            self._ps_connections.remove(conn)
                            break
                    except Exception:
                        pass
                if node.scene():
                    self.scene().removeItem(node)
                self._ps_preview_nodes.pop(i)
                break

        # 确定位置：优先用点击智能PS按钮时记录的坐标
        ps_x, ps_y = 100, 100
        click_pos = getattr(self, '_ps_click_positions', {}).get(scene_index)
        if click_pos:
            ps_x, ps_y = click_pos
        elif shot_card:
            card_rect = shot_card.mapRectToScene(shot_card.rect())
            ps_x = card_rect.right() + 30
            ps_y = card_rect.top()

        # 创建PS预览卡
        ps_node = PSPreviewNode(
            scene_index=scene_index,
            scene_id=scene_id,
            on_delete=self._on_ps_node_deleted,
            on_reopen_ps=self._on_ps_card_reopen,
            on_moved=self._save_ps_card_pos,
        )
        ps_node.setPos(ps_x, ps_y)

        pixmap = QPixmap(image_path)
        ps_node.set_pixmap(pixmap, image_path)

        self._canvas_scene.addItem(ps_node)
        self._ps_preview_nodes.append(ps_node)

        # 创建连线（分镜卡 → PS卡）
        if shot_card:
            connection = ShotImageConnection(
                self._canvas_scene, shot_card, ps_node)
            connection.set_solid()
            self._ps_connections.append(connection)

        # 持久化PS卡位置
        self._save_ps_card_pos(scene_index, ps_x, ps_y, image_path)

    def _on_ps_node_deleted(self, node):
        """PS预览卡被删除"""
        scene_index = node.scene_index
        if hasattr(self, '_ps_preview_nodes'):
            if node in self._ps_preview_nodes:
                self._ps_preview_nodes.remove(node)
        if hasattr(self, '_ps_connections'):
            for conn in self._ps_connections:
                try:
                    if conn._image_node == node:
                        conn.remove()
                        self._ps_connections.remove(conn)
                        break
                except Exception:
                    pass
        if node.scene():
            node.scene().removeItem(node)

        # 清除数据库中的持久化数据，防止下次打开项目时恢复
        self._clear_ps_card_data(scene_index)

    def _clear_ps_card_data(self, scene_index: int):
        """清除 generation_params 中的 PS 卡数据（内存+数据库）"""
        try:
            scene_id = self._find_scene_id_by_index(scene_index)

            # 1. 清除内存中的 card.scene_data
            if self._shot_delegate:
                for card in self._shot_delegate._shot_cards:
                    if card.global_index == scene_index:
                        gp = card.scene_data.get('generation_params') or {}
                        if isinstance(gp, str):
                            import json
                            try:
                                gp = json.loads(gp)
                            except Exception:
                                gp = {}
                        gp.pop('ps_card_pos', None)
                        gp.pop('ps_composite_image', None)
                        card.scene_data['generation_params'] = gp

                        # 2. 写数据库
                        if scene_id and self.data_hub:
                            self.data_hub.project_controller.update_scene(
                                scene_id, generation_params=gp)
                        break
        except Exception as e:
            print(f"[涛割] 清除PS卡数据失败: {e}")

    def _on_ps_card_reopen(self, scene_index: int):
        """双击PS预览卡 → 重新打开智能PS（保留已有图层状态）"""
        self._on_smart_ps_requested(scene_index, first_open=False)

    def _save_ps_card_pos(self, scene_index: int, x: float, y: float,
                           image_path: str):
        """持久化PS卡位置到 scene.generation_params（内存+数据库）"""
        try:
            scene_id = self._find_scene_id_by_index(scene_index)

            # 1. 同步更新内存中的 card.scene_data
            if self._shot_delegate:
                for card in self._shot_delegate._shot_cards:
                    if card.global_index == scene_index:
                        gp = card.scene_data.get('generation_params') or {}
                        if isinstance(gp, str):
                            import json
                            try:
                                gp = json.loads(gp)
                            except Exception:
                                gp = {}
                        gp['ps_card_pos'] = {'x': x, 'y': y}
                        gp['ps_composite_image'] = image_path
                        card.scene_data['generation_params'] = gp

                        # 2. 写数据库
                        if scene_id and self.data_hub:
                            self.data_hub.project_controller.update_scene(
                                scene_id, generation_params=gp)
                        break
        except Exception as e:
            print(f"[涛割] 保存PS卡位置失败: {e}")

    def _collect_scene_assets(self, scene_index: int) -> list:
        """收集分镜关联的资产列表（有 image_path 的）"""
        assets = []
        try:
            project_id = self.data_hub.current_project_id
            if project_id:
                bound_assets = self.data_hub.asset_controller.get_assets_for_scene(
                    project_id, scene_index)
                for a in bound_assets:
                    img = a.get('main_reference_image', '')
                    if img:
                        import os
                        if os.path.isfile(img):
                            assets.append({
                                'name': a.get('name', ''),
                                'image_path': img,
                                'type': a.get('asset_type', 'prop'),
                                'multi_angle_images': a.get('multi_angle_images', []),
                            })
        except Exception as e:
            print(f"[涛割] 收集场景资产失败: {e}")
        return assets

    def _on_console_generate_video(self, params: dict):
        """视频控制台"生成"按钮 → 实际调用 API"""
        from PyQt6.QtCore import QThread, pyqtSignal as _pyqtSignal

        scene_index = params.get('scene_index')
        prompt = params.get('base_prompt', '') or params.get('prompt', '')
        source_image = params.get('source_image', '')
        duration = params.get('duration', 10)
        model = params.get('model', 'sora-2-all')
        size = params.get('size', 'large')
        orientation = params.get('orientation', 'landscape')
        style_name = params.get('style', '无风格')

        # 获取完整资产上下文
        project_id = self.data_hub.current_project_id if self.data_hub else None
        asset_context = None
        if project_id is not None and scene_index is not None:
            try:
                asset_context = self.data_hub.asset_controller.assemble_generation_context(
                    project_id, scene_index
                )
            except Exception as e:
                print(f"[涛割] 获取视频资产上下文失败: {e}")

        # 追加风格提示词
        style_suffix = STYLE_PROMPTS.get(style_name, '')

        # 构建增强提示词（包含视频特有的景别、镜头、动作等信息）
        prompt = self._build_video_enhanced_prompt(prompt, style_suffix, asset_context, scene_index)

        if not prompt:
            print("[涛割] 无视频提示词，跳过生成")
            return

        class _VideoGenWorker(QThread):
            finished = _pyqtSignal(bool, str, str)  # success, url, error

            def __init__(self, prompt: str, source_image: str,
                         duration: int, model: str, size: str,
                         orientation: str):
                super().__init__()
                self._prompt = prompt
                self._source_image = source_image
                self._duration = duration
                self._model = model
                self._size = size
                self._orientation = orientation

            def run(self):
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._do_generate())
                    loop.close()
                except Exception as e:
                    self.finished.emit(False, "", str(e))

            async def _do_generate(self):
                from config.settings import SettingsManager
                settings = SettingsManager().settings

                from services.generation.closed_source.yunwu_provider import YunwuProvider
                provider = YunwuProvider(
                    api_key=settings.api.yunwu_api_key,
                    base_url=settings.api.yunwu_base_url,
                )

                from services.generation.base_provider import VideoGenerationRequest

                images = []
                if self._source_image:
                    images = [self._source_image]

                request = VideoGenerationRequest(
                    prompt=self._prompt,
                    duration=self._duration,
                    source_image=self._source_image if self._source_image else None,
                    model_params={
                        'model': self._model,
                        'orientation': self._orientation,
                        'size': self._size,
                        'watermark': False,
                        'images': images,
                    },
                )

                result = await provider.generate_video(request)
                await provider.close()

                if result.success:
                    self.finished.emit(True, result.result_url or "", "")
                else:
                    self.finished.emit(False, "", result.error_message or "视频生成失败")

        worker = _VideoGenWorker(prompt, source_image, duration, model, size, orientation)
        worker.finished.connect(
            lambda ok, url, err: self._on_video_gen_finished(ok, url, err, scene_index))
        if not hasattr(self, '_gen_workers'):
            self._gen_workers = []
        self._gen_workers.append(worker)
        worker.start()
        if source_image:
            print(f"[涛割] I2V 视频生成任务已启动 (scene_index={scene_index}, model={model}, image={source_image})")
        else:
            print(f"[涛割] 纯文本视频生成任务已启动 (scene_index={scene_index}, model={model})")

    # ─── 资产需求回调 ───

    def _auto_extract_asset_requirements(self):
        """分镜全部完成后，自动创建资产需求区并触发 AI 提取"""
        # 延迟执行，等当前事件处理完毕
        QTimer.singleShot(500, self._do_auto_extract_asset_requirements)

    def _do_auto_extract_asset_requirements(self):
        """延迟执行：创建资产需求 Zone + 触发 AI 提取"""
        self._ensure_asset_req_zone()
        if self._asset_req_delegate:
            self._asset_req_delegate.extract_requirements()

    def _on_asset_library_updated(self, asset_id: int):
        """资产库资产被更新（如编辑器生成多视角后保存），同步到画布需求卡"""
        if not self._asset_req_delegate:
            return
        try:
            asset_data = self.data_hub.asset_controller.get_asset(asset_id)
            if not asset_data:
                return
            multi_angle_images = asset_data.get('multi_angle_images', [])
            asset_name = asset_data.get('name', '')
            self._asset_req_delegate.update_cards_by_bound_asset(
                asset_id, asset_name, multi_angle_images
            )
        except Exception:
            pass

    def _on_sync_assets_to_library(self):
        """标题栏"更新到资产库"按钮回调：同步已完成需求到 Asset 表"""
        project_id = self.data_hub.current_project_id if self.data_hub else 0
        if not project_id:
            if self._zone_asset_req:
                self._zone_asset_req.set_status("未找到当前项目")
            return
        results = self.data_hub.asset_controller.sync_requirements_to_assets(project_id)
        if self._zone_asset_req:
            if results:
                # 统计有多少资产含多视角
                ma_count = sum(
                    1 for r in results
                    if r.get('multi_angle_images')
                )
                status = f"已同步 {len(results)} 个资产"
                if ma_count:
                    status += f"（含 {ma_count} 个多视角）"
                self._zone_asset_req.set_status(status)
            else:
                self._zone_asset_req.set_status("没有需要同步的资产（需先生成图片）")
        # 同步后刷新分镜卡（从 DB 读取最新的 bound_assets）
        if self._shot_delegate:
            self._shot_delegate.load_all_acts_shots()

    def _on_ai_fill_asset_requested(self, req_data: dict):
        """资产需求卡 AI 补全按钮 → 启动搜索"""
        req_id = req_data.get('id')
        name = req_data.get('name', '')
        req_type = req_data.get('requirement_type', '')
        if not req_id or not name:
            return

        # 获取源文本
        source_text = ''
        if self.data_hub:
            source_text = self.data_hub.get_source_content() or ''
        if not source_text:
            if self._zone_asset_req:
                self._zone_asset_req.set_status("缺少源文本，无法 AI 补全")
            return

        # 收集分镜数据，构建文本供 AI 匹配
        shots_text = ''
        if self.data_hub and self.data_hub.scenes_data:
            lines = []
            for sd in self.data_hub.scenes_data:
                idx = sd.get('scene_index', 0)
                subtitle = sd.get('subtitle_text', '') or ''
                prompt = sd.get('image_prompt', '') or ''
                line = f"【分镜 {idx}】台词：{subtitle}"
                if prompt:
                    line += f" | 画面：{prompt}"
                lines.append(line)
            shots_text = '\n'.join(lines)

        # 设置卡片 loading 状态
        if self._asset_req_delegate:
            self._asset_req_delegate.set_card_ai_filling(req_id, True)

        # 启动 AI 搜索
        from services.ai_analyzer import AssetSingleSearchWorker
        self._ai_single_search_worker = AssetSingleSearchWorker(
            req_id, name, req_type, source_text, shots_text
        )
        self._ai_single_search_worker.search_completed.connect(
            self._on_ai_single_search_completed)
        self._ai_single_search_worker.search_failed.connect(
            self._on_ai_single_search_failed)
        self._ai_single_search_worker.start()

        if self._zone_asset_req:
            self._zone_asset_req.set_status(f"AI 正在搜索「{name}」...")

    def _on_ai_single_search_completed(self, req_id: int, result: dict):
        """AI 单资产搜索完成"""
        attributes = result.get('attributes', {})
        scene_indices = result.get('scene_indices')
        source_excerpts = result.get('source_excerpts')

        # 持久化到数据库
        updated = self.data_hub.asset_controller.update_requirement_attributes(
            req_id, attributes, scene_indices, source_excerpts
        )

        # 更新卡片
        if self._asset_req_delegate and updated:
            self._asset_req_delegate.update_requirement_after_ai_fill(req_id, updated)

        name = result.get('name', '')
        if self._zone_asset_req:
            if attributes:
                self._zone_asset_req.set_status(f"「{name}」补全完成")
            else:
                self._zone_asset_req.set_status(f"「{name}」在原文中未找到详细信息")

    def _on_ai_single_search_failed(self, req_id: int, error: str):
        """AI 单资产搜索失败"""
        if self._asset_req_delegate:
            self._asset_req_delegate.set_card_ai_filling(req_id, False)
        if self._zone_asset_req:
            self._zone_asset_req.set_status(f"AI 补全失败: {error}")

    def _on_generate_asset_requested(self, req_data: dict):
        """资产需求卡 → 生成图片"""
        from .shot_card_actions import ImagePreviewNode, ShotImageConnection

        # 用 requirement id 的负数作为唯一标识（避免与分镜的 scene_index 冲突）
        req_id = req_data.get('id')
        asset_idx = -(req_id if req_id else id(req_data) % 100000)

        # 找到触发生成的需求卡，在其左侧创建图片预览节点
        req_card = None
        if self._asset_req_delegate:
            for cards in self._asset_req_delegate._requirement_cards.values():
                for c in cards:
                    if c.req_data is req_data or c.req_data.get('id') == req_id:
                        req_card = c
                        break
                if req_card:
                    break

        if req_card:
            card_scene_rect = req_card.mapRectToScene(req_card.rect())
            img_x = card_scene_rect.left() - ImagePreviewNode.NODE_WIDTH - 30
            img_y = card_scene_rect.center().y() - ImagePreviewNode.NODE_HEIGHT / 2

            # 检查是否已存在同 asset_idx 的图片卡
            existing = None
            if hasattr(self, '_image_preview_nodes'):
                for n in self._image_preview_nodes:
                    if n.scene_index == asset_idx:
                        existing = n
                        break

            if not existing:
                img_node = ImagePreviewNode(
                    asset_idx,
                    on_delete=self._on_image_node_deleted,
                    on_open_canvas=self._open_intelligent_canvas_for_scene,
                )
                img_node.setPos(img_x, img_y)
                self._canvas_scene.addItem(img_node)

                # 创建连线（需求卡 → 图片节点）
                connection = ShotImageConnection(
                    self._canvas_scene, req_card, img_node)
                if not self._animations_enabled:
                    connection.set_animations_enabled(False)

                if not hasattr(self, '_image_preview_nodes'):
                    self._image_preview_nodes = []
                    self._image_connections = []
                self._image_preview_nodes.append(img_node)
                self._image_connections.append(connection)

                # 联动拖拽：卡片拖动时主图+连线跟随
                req_card._linked_image_node = img_node
                req_card._linked_connection = connection

                # 多视角预览组关联图片节点
                if req_id and self._asset_req_delegate and req_id in self._asset_req_delegate._multi_angle_groups:
                    self._asset_req_delegate._multi_angle_groups[req_id].set_image_node(img_node)
                    req_card._linked_multi_angle = self._asset_req_delegate._multi_angle_groups[req_id]

        # 角色生成 → 自动切竖屏
        req_type = req_data.get('requirement_type', '')
        if req_type == 'character':
            self._ensure_image_console()
            if self._image_console:
                if not hasattr(self, '_pre_asset_orientation'):
                    self._pre_asset_orientation = self._image_console.orientation
                self._image_console.set_orientation('portrait')

        # 打开图片控制台，预填资产描述作为提示词
        self._ensure_image_console()
        if self._image_console:
            name = req_data.get('name', '')
            attrs = req_data.get('attributes', {})

            # 检查是否是衍生角色 → 图片编辑模式
            reference_image = ''
            variant_type = attrs.get('variant_type', '')
            if attrs.get('is_variant') and variant_type and req_type == 'character':
                # 优先级 1: 手动连线
                variant_asset_idx = -(req_data.get('id', 0))
                link = self._variant_links.get(variant_asset_idx)
                if link:
                    reference_image = link.source_image_path
                # 优先级 2: 自动查找 fallback
                if not reference_image:
                    base_name = attrs.get('base_character_name', '')
                    reference_image = self._find_base_variant_image(base_name)

            if reference_image and variant_type == 'costume_variant':
                # 服装衍生：基于基础角色图换装
                clothing = attrs.get('clothing_style', '')
                color = attrs.get('clothing_color', '')
                prompt = (f"请将这个角色的服装更换为{clothing}，{color}，"
                          f"保持角色的脸型、发型、发色不变")
            elif reference_image and variant_type == 'age_variant':
                # 年龄衍生：基于基础角色图修改年龄
                age_desc = attrs.get('variant_description', '')
                prompt = (f"请将这个角色修改为{age_desc}，"
                          f"保持角色的整体特征不变")
            elif reference_image and variant_type == 'appearance_variant':
                # 外貌衍生：按描述修改外观
                desc = attrs.get('variant_description', '')
                prompt = f"请将这个角色修改为{desc}，保持角色的基本特征不变"
            else:
                if req_type == 'character':
                    # 角色卡：一个人 + 结构化属性 + 白色背景前全身像
                    parts = ['一个人', name]
                    _CHAR_FIELDS = [
                        ('gender', '性别'),
                        ('age', '年龄'),
                        ('hairstyle', '发型'),
                        ('hair_color', '发色'),
                        ('body_type', '体型'),
                        ('clothing_style', '穿着'),
                    ]
                    for key, label in _CHAR_FIELDS:
                        val = attrs.get(key, '')
                        if val:
                            parts.append(f'{label}：{val}')
                    # 其他有值的描述性属性
                    _SKIP = {'scene_indices', 'source_excerpt',
                             'is_variant', 'variant_index',
                             'base_character_name', 'variant_name',
                             'variant_type', 'variant_description',
                             'gender', 'age', 'hairstyle', 'hair_color',
                             'body_type', 'clothing_style', 'age_group'}
                    for k, v in attrs.items():
                        if v and k not in _SKIP:
                            if isinstance(v, list):
                                parts.append('，'.join(str(i) for i in v))
                            else:
                                parts.append(str(v))
                    parts.append('白色背景，全身像')
                    prompt = '，'.join(parts)

                elif req_type == 'prop':
                    # 道具卡：没有人 + 属性 + 白色背景
                    parts = ['没有人', name]
                    _SKIP = {'scene_indices', 'source_excerpt',
                             'owner'}
                    for k, v in attrs.items():
                        if v and k not in _SKIP:
                            if isinstance(v, list):
                                parts.append('，'.join(str(i) for i in v))
                            else:
                                parts.append(str(v))
                    parts.append('白色背景')
                    prompt = '，'.join(parts)

                elif req_type == 'scene_bg':
                    # 场景卡：属性 + 没有人
                    desc_parts = [name]
                    for k, v in attrs.items():
                        if v and k not in ('scene_indices', 'source_excerpt'):
                            if isinstance(v, list):
                                desc_parts.append('，'.join(str(i) for i in v))
                            else:
                                desc_parts.append(str(v))
                    desc_parts.append('没有人')
                    prompt = '，'.join(desc_parts)

                else:
                    # 照明 / 其他类型：默认拼接
                    desc_parts = [name]
                    for k, v in attrs.items():
                        if v and k not in ('scene_indices', 'source_excerpt'):
                            if isinstance(v, list):
                                desc_parts.append('，'.join(str(i) for i in v))
                            else:
                                desc_parts.append(str(v))
                    prompt = '，'.join(desc_parts)

            self._image_console.set_scene_index(asset_idx)
            self._image_console.set_prompt(prompt)
            self._image_console.set_reference_image(reference_image)
            self._hide_context_buttons()
            if not self._image_console.is_visible_state:
                self._image_console.slide_up()
            self._position_image_console()

    def _on_bind_asset_requested(self, req_data: dict):
        """资产需求卡 → 从资产库绑定（TODO: 弹出资产选择面板）"""
        print(f"[涛割] 请求绑定资产: {req_data.get('name', '')}")

    # ─── 多视角生成 ───

    def _on_multi_angle_requested(self, req_data: dict):
        """资产需求卡 → 多视角生成（支持多卡片并行）"""
        import os
        req_id = req_data.get('id')
        name = req_data.get('name', '')
        img_path = req_data.get('generated_image_path', '')
        is_fulfilled = req_data.get('is_fulfilled', False)

        if not is_fulfilled or not img_path or not os.path.isfile(img_path):
            if self._zone_asset_req:
                self._zone_asset_req.set_status("请先生成图片")
            return

        # 读取 API 配置
        from config.settings import SettingsManager
        api_cfg = SettingsManager().settings.api
        api_key = api_cfg.runninghub_api_key
        base_url = api_cfg.runninghub_base_url
        instance_type = api_cfg.runninghub_instance_type

        if not api_key:
            if self._zone_asset_req:
                self._zone_asset_req.set_status("请先配置 RunningHub API Key")
            return

        # 构建保存目录
        project_id = self.data_hub.current_project_id if self.data_hub else 0
        save_dir = os.path.join(
            'generated', str(project_id), 'multi_angle',
            name.replace(' ', '_').replace('/', '_')
        )

        # 同一需求不重复启动（不同需求可并行）
        if req_id in self._ma_workers and self._ma_workers[req_id].isRunning():
            if self._zone_asset_req:
                self._zone_asset_req.set_status(f"「{name}」多视角正在生成中...")
            return

        # 设置卡片 loading 状态
        if self._asset_req_delegate:
            self._asset_req_delegate.set_card_multi_angle_loading(req_id, True)

        # 启动 worker（改用5角度批量生成）
        from services.multi_angle_batch_service import (
            MultiAngleBatchWorker, ANGLE_PROMPTS, ANGLE_LABELS,
        )
        worker = MultiAngleBatchWorker(
            img_path, save_dir, api_key, base_url,
            prompts=ANGLE_PROMPTS, labels=ANGLE_LABELS,
            instance_type=instance_type,
        )
        self._ma_workers[req_id] = worker

        worker.progress.connect(
            self._on_multi_angle_progress
        )
        worker.angle_completed.connect(
            lambda idx, path, _rid=req_id: self._on_multi_angle_single(
                _rid, idx, path
            )
        )
        worker.all_completed.connect(
            lambda ok, paths, err, _rid=req_id: self._on_multi_angle_finished(
                _rid, ok, paths, err
            )
        )
        worker.start()

        if self._zone_asset_req:
            active = sum(1 for w in self._ma_workers.values() if w.isRunning())
            self._zone_asset_req.set_status(
                f"「{name}」多视角生成中... (共 {active} 个任务)"
            )

    def _on_multi_angle_progress(self, msg: str):
        """多视角生成进度回调 — 更新 zone 标题栏"""
        if self._zone_asset_req:
            self._zone_asset_req.set_status(msg)

    def _on_multi_angle_single(self, req_id: int, angle_idx: int,
                                local_path: str):
        """单个角度完成 — 逐张更新缩略图"""
        if self._asset_req_delegate:
            self._asset_req_delegate.update_card_multi_angle_single(
                req_id, angle_idx, local_path
            )

    def _on_multi_angle_finished(self, req_id: int,
                                  success: bool, paths: list, error: str):
        """多视角生成完成回调"""
        # 清理 worker 引用
        self._ma_workers.pop(req_id, None)
        # 取消 loading 状态
        if self._asset_req_delegate:
            self._asset_req_delegate.set_card_multi_angle_loading(req_id, False)

        if success:
            # 持久化到数据库
            if self.data_hub:
                self.data_hub.asset_controller.update_requirement_multi_angle(
                    req_id, paths
                )
            # 更新卡片
            if self._asset_req_delegate:
                self._asset_req_delegate.set_card_multi_angle_paths(req_id, paths)
            if self._zone_asset_req:
                active = sum(1 for w in self._ma_workers.values() if w.isRunning())
                if active > 0:
                    self._zone_asset_req.set_status(
                        f"多视角完成 {len(paths)} 张，还有 {active} 个任务..."
                    )
                else:
                    self._zone_asset_req.set_status(
                        f"多视角生成完成：{len(paths)} 张图片"
                    )
        else:
            if self._zone_asset_req:
                self._zone_asset_req.set_status(f"多视角生成失败: {error}")

    def _find_base_variant_image(self, base_character_name: str) -> str:
        """查找基础角色变体（variant_index == 0）已生成的图片路径"""
        if not self._asset_req_delegate or not base_character_name:
            return ''
        # 在所有需求卡中找同名角色的基础变体
        for cards in self._asset_req_delegate._requirement_cards.values():
            for c in cards:
                rd = c.req_data
                if rd.get('requirement_type') != 'character':
                    continue
                a = rd.get('attributes', {})
                # 基础变体：同名且 variant_index == 0 或非变体
                is_base = (not a.get('is_variant')
                           or a.get('variant_index', 0) == 0)
                card_base_name = a.get('base_character_name', rd.get('name', ''))
                if card_base_name == base_character_name and is_base:
                    # 检查该卡是否已有生成的图片
                    base_idx = -(rd.get('id', 0) if rd.get('id') else id(rd) % 100000)
                    if hasattr(self, '_image_preview_nodes'):
                        for node in self._image_preview_nodes:
                            if node.scene_index == base_idx and node._pixmap is not None:
                                # 从已保存的生成结果中获取路径
                                path = getattr(node, '_image_path', '')
                                if path:
                                    return path
        return ''

    def _on_variant_link_created(self, source_node, target_card):
        """基础角色图片 → 变体卡手动连线建立回调"""
        from .asset_requirement_cards import VariantLinkLine

        variant_req_id = target_card.req_data.get('id')
        if not variant_req_id:
            return
        variant_asset_idx = -variant_req_id

        # 找到 source_node 对应的基础角色 requirement id
        base_req_id = None
        if self._asset_req_delegate:
            src_idx = source_node.scene_index
            for cards in self._asset_req_delegate._requirement_cards.values():
                for c in cards:
                    rid = c.req_data.get('id')
                    if rid and -rid == src_idx:
                        base_req_id = rid
                        break
                if base_req_id:
                    break

        # 移除旧连线
        old_link = self._variant_links.get(variant_asset_idx)
        if old_link:
            old_link.remove()

        # 创建新连线
        link = VariantLinkLine(self._canvas_scene, source_node, target_card)
        self._variant_links[variant_asset_idx] = link

        # 持久化
        if base_req_id and self.data_hub:
            self.data_hub.asset_controller.set_variant_link(variant_req_id, base_req_id)
        print(f"[涛割] 变体连线已建立: base_req={base_req_id} → variant_req={variant_req_id}")

    def _show_variant_anchor_if_character(self, node, asset_idx: int):
        """如果 asset_idx 对应的是角色类型需求卡，则显示变体拖拽锚点"""
        if not self._asset_req_delegate:
            return
        for cards in self._asset_req_delegate._requirement_cards.values():
            for c in cards:
                rid = c.req_data.get('id')
                if rid and -rid == asset_idx:
                    if c.req_data.get('requirement_type') == 'character':
                        node.show_variant_anchor(self._on_variant_link_created)
                    return

    # ─── 图片/视频控制台生成回调 ───

    def _on_console_generate_image(self, params: dict):
        """图片控制台 → 生成图片（调用云雾 API）"""
        from PyQt6.QtCore import QThread, pyqtSignal

        # 获取完整资产上下文并增强提示词
        scene_index = params.get('scene_index')
        project_id = self.data_hub.current_project_id if self.data_hub else None
        asset_context = None
        if project_id is not None and scene_index is not None:
            try:
                asset_context = self.data_hub.asset_controller.assemble_generation_context(
                    project_id, scene_index
                )
            except Exception as e:
                print(f"[涛割] 获取资产上下文失败: {e}")

        # 追加风格描述到提示词
        style = params.get('style', '无风格')
        style_suffix = STYLE_PROMPTS.get(style, '')

        # 构建增强提示词
        params = dict(params)  # 不修改原 dict
        user_prompt = params.get('prompt', '')
        params['prompt'] = self._build_enhanced_prompt(user_prompt, style_suffix, asset_context)

        # 收集参考图（角色+服装+场景参考图）
        if asset_context:
            all_ref_images = list(params.get('reference_images', []))
            for c in asset_context.get('characters', []):
                all_ref_images.extend(c.get('ref_images', []))
            if (asset_context.get('scene_bg') or {}).get('ref_images'):
                all_ref_images.extend(asset_context['scene_bg']['ref_images'])
            # 去重
            seen = set()
            unique_refs = []
            for r in all_ref_images:
                if r and r not in seen:
                    seen.add(r)
                    unique_refs.append(r)
            params['reference_images'] = unique_refs

        class _ImageGenWorker(QThread):
            finished = pyqtSignal(bool, str, str)  # success, url_or_path, error

            def __init__(self, params: dict):
                super().__init__()
                self._params = params

            def run(self):
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(self._do_generate())
                    loop.close()
                except Exception as e:
                    self.finished.emit(False, "", str(e))

            async def _do_generate(self):
                from config.settings import SettingsManager
                settings = SettingsManager().settings
                model_name = self._params.get('model_name', 'gemini-3-pro-image-preview')

                # 根据设置中的 image_provider 选择渠道（geek / yunwu）
                channel = settings.api.image_provider or "geek"
                if channel == "geek":
                    from services.generation.closed_source.geek_provider import GeekProvider
                    provider = GeekProvider(
                        api_key=settings.api.geek_api_key,
                        base_url=settings.api.geek_base_url,
                    )
                else:
                    from services.generation.closed_source.yunwu_provider import YunwuProvider
                    provider = YunwuProvider(
                        api_key=settings.api.yunwu_api_key,
                        base_url=settings.api.yunwu_base_url,
                    )

                # 宽高比直接传给 provider（Gemini API 原生支持 aspectRatio）
                ratio = self._params.get('ratio', '16:9')
                resolution = self._params.get('resolution', '1K')
                # imageSize: 如 "1024x1024"
                res_map = {'1K': 1024, '2K': 2048, '4K': 4096}
                base = res_map.get(resolution, 1024)
                image_size = f"{base}x{base}"

                from services.generation.base_provider import ImageGenerationRequest
                ref_images = []
                ref_img = self._params.get('reference_image', '')
                if ref_img:
                    ref_images.append(ref_img)
                ref_images.extend(self._params.get('reference_images', []))
                request = ImageGenerationRequest(
                    prompt=self._params.get('prompt', ''),
                    num_images=1,
                    reference_images=ref_images,
                    model_params={
                        'model': model_name,
                        'aspect_ratio': ratio,
                        'image_size': image_size,
                        'system_instruction': self._params.get('system_instruction', ''),
                    },
                )

                result = await provider.generate_image(request)
                await provider.close()

                if result.success:
                    # 优先使用本地路径（Gemini 原生 API 返回 base64 已保存到本地）
                    path_or_url = result.result_path or result.result_url or ""
                    self.finished.emit(True, path_or_url, "")
                else:
                    self.finished.emit(False, "", result.error_message or "生成失败")

            def _ratio_to_size(self, ratio: str, resolution: str) -> tuple:
                res_map = {'1K': 1024, '2K': 2048, '4K': 4096}
                base = res_map.get(resolution, 1024)
                parts = ratio.split(':')
                if len(parts) == 2:
                    w_ratio, h_ratio = int(parts[0]), int(parts[1])
                    if w_ratio >= h_ratio:
                        w = base
                        h = int(base * h_ratio / w_ratio)
                    else:
                        h = base
                        w = int(base * w_ratio / h_ratio)
                    return w, h
                return base, base

        scene_index = params.get('scene_index')
        print(f"[涛割] _on_console_generate_image: scene_index={scene_index}, "
              f"model={params.get('model_name')}, prompt长度={len(params.get('prompt', ''))}")

        target_node = None

        # ── 从已有图片节点触发重新生成 → 创建新节点 ──
        if self._regenerate_from_node is not None:
            source_node = self._regenerate_from_node
            self._regenerate_from_node = None  # 清除标记

            from .shot_card_actions import ImagePreviewNode, ShotImageConnection

            # 创建新的 ImagePreviewNode
            new_node = ImagePreviewNode(
                scene_index,
                on_delete=self._on_image_node_deleted,
                on_open_canvas=self._open_intelligent_canvas_for_scene,
            )
            new_node._on_hover_show = self._on_image_hover_show
            new_node._on_hover_hide = self._on_image_hover_hide

            # 新节点位置：在源节点右侧偏移
            new_x = source_node.pos().x() + ImagePreviewNode.NODE_WIDTH + 20
            new_y = source_node.pos().y()
            new_node.setPos(new_x, new_y)
            self._canvas_scene.addItem(new_node)

            # 创建连线（找到对应的分镜卡）
            shot_card = None
            if self._shot_delegate:
                for card in self._shot_delegate._shot_cards:
                    if card.global_index == scene_index:
                        shot_card = card
                        break
            if shot_card:
                connection = ShotImageConnection(self._canvas_scene, shot_card, new_node)
                if not self._animations_enabled:
                    connection.set_animations_enabled(False)
                if not hasattr(self, '_image_connections'):
                    self._image_connections = []
                self._image_connections.append(connection)

            if not hasattr(self, '_image_preview_nodes'):
                self._image_preview_nodes = []
            self._image_preview_nodes.append(new_node)

            new_node.set_loading(True)
            target_node = new_node
            self._console_target_node = new_node
            print(f"[涛割] 从已有图片节点重新生成 → 创建新节点")

        else:
            # ── 常规流程：找到已有图片卡开始转圈 ──
            # 优先使用 _console_target_node（精确定位到最新创建的节点）
            target_node = self._console_target_node
            if target_node is not None:
                # 验证节点仍在场景中且 scene_index 匹配
                if target_node.scene() and target_node.scene_index == scene_index:
                    target_node.set_loading(True)
                    print(f"[涛割] 使用 _console_target_node 设置 loading=True")
                else:
                    target_node = None

            # fallback：用 reversed 找最新的匹配节点
            if target_node is None and scene_index is not None and hasattr(self, '_image_preview_nodes'):
                print(f"[涛割] fallback 搜索图片节点: 共 {len(self._image_preview_nodes)} 个")
                for node in reversed(self._image_preview_nodes):
                    if node.scene_index == scene_index and node.scene():
                        node.set_loading(True)
                        target_node = node
                        print(f"[涛割] fallback 找到匹配图片卡，已设置 loading=True")
                        break

        if target_node is None:
            print(f"[涛割] 警告：未找到 scene_index={scene_index} 的图片卡")

        # 保存生成参数到目标节点（用于 hover 提示词显示）
        if target_node is not None:
            target_node.set_gen_params(params)

        # 通过 lambda 默认参数捕获 target_node，传入完成回调
        captured_node = target_node
        worker = _ImageGenWorker(params)
        worker.finished.connect(
            lambda ok, url, err, _si=scene_index, _tn=captured_node:
                self._on_image_gen_finished_for_node(ok, url, err, _si, _tn))
        # 保持引用
        if not hasattr(self, '_gen_workers'):
            self._gen_workers = []
        self._gen_workers.append(worker)
        worker.start()

    def _on_image_gen_finished(self, success: bool, path_or_url: str, error: str,
                                scene_index: int):
        """图片生成完成回调"""
        print(f"[涛割] _on_image_gen_finished: success={success}, scene_index={scene_index}, "
              f"path={path_or_url[:80] if path_or_url else 'None'}")
        if success and path_or_url:
            print(f"[涛割] 图片生成成功: {path_or_url}")

            # ── 持久化 ──
            if scene_index is not None and scene_index >= 0:
                # 分镜图片：保存到 Scene 表
                self._save_generated_image_to_db(scene_index, path_or_url)
            elif scene_index is not None and scene_index < 0:
                # 资产需求图片：保存到 AssetRequirement 表
                # fallback 路径：尝试从匹配节点获取 prompt
                gen_prompt = ''
                if hasattr(self, '_image_preview_nodes'):
                    for node in self._image_preview_nodes:
                        if node.scene_index == scene_index and hasattr(node, '_gen_params'):
                            gen_prompt = node._gen_params.get('prompt', '')
                            break
                self._save_asset_image_to_db(scene_index, path_or_url, gen_prompt)

            # 更新图片预览节点
            if hasattr(self, '_image_preview_nodes'):
                for node in self._image_preview_nodes:
                    if node.scene_index == scene_index:
                        node.set_loading(False)
                        # 判断是本地路径还是远程 URL
                        if os.path.isfile(path_or_url):
                            # 本地文件：直接加载 QPixmap
                            from PyQt6.QtGui import QPixmap
                            pixmap = QPixmap(path_or_url)
                            if not pixmap.isNull():
                                node.set_pixmap(pixmap)
                                node._image_path = path_or_url
                                print(f"[涛割] 已加载本地图片: {path_or_url}")
                        else:
                            # 远程 URL：下载后显示
                            self._download_and_set_preview(node, path_or_url)
                        # 连线从虚线切换为实线+粒子
                        self._set_connection_solid(scene_index)
                        # 资产图片生成成功后，如果是基础角色 → 显示变体拖拽锚点
                        if scene_index < 0:
                            self._show_variant_anchor_if_character(node, scene_index)
                        break
        else:
            print(f"[涛割] 图片生成失败: {error}")
            if hasattr(self, '_image_preview_nodes'):
                for node in self._image_preview_nodes:
                    if node.scene_index == scene_index:
                        node.set_loading(False)
                        break

    def _on_image_gen_finished_for_node(self, success: bool, path_or_url: str,
                                         error: str, scene_index: int,
                                         target_node):
        """图片生成完成回调 — 直接操作指定的目标节点"""
        print(f"[涛割] _on_image_gen_finished_for_node: success={success}, "
              f"scene_index={scene_index}, path={path_or_url[:80] if path_or_url else 'None'}")
        if success and path_or_url:
            print(f"[涛割] 图片生成成功: {path_or_url}")

            # ── 持久化 ──
            if scene_index is not None and scene_index >= 0:
                self._save_generated_image_to_db(scene_index, path_or_url)
            elif scene_index is not None and scene_index < 0:
                # 从目标节点获取生成时使用的提示词
                gen_prompt = ''
                if target_node and hasattr(target_node, '_gen_params'):
                    gen_prompt = target_node._gen_params.get('prompt', '')
                self._save_asset_image_to_db(scene_index, path_or_url, gen_prompt)

            # 更新指定的目标节点
            node = target_node
            if node is not None and node.scene():
                node.set_loading(False)
                if os.path.isfile(path_or_url):
                    from PyQt6.QtGui import QPixmap
                    pixmap = QPixmap(path_or_url)
                    if not pixmap.isNull():
                        node.set_pixmap(pixmap)
                        node._image_path = path_or_url
                        print(f"[涛割] 已加载本地图片到目标节点: {path_or_url}")
                else:
                    self._download_and_set_preview(node, path_or_url)
                # 按 index 找到对应连线设为实线
                self._set_connection_solid_for_node(node)
                if scene_index is not None and scene_index < 0:
                    self._show_variant_anchor_if_character(node, scene_index)
            else:
                # 目标节点已被删除，fallback 到旧逻辑
                self._on_image_gen_finished(success, path_or_url, error, scene_index)
        else:
            print(f"[涛割] 图片生成失败: {error}")
            if target_node is not None and target_node.scene():
                target_node.set_loading(False)
            elif hasattr(self, '_image_preview_nodes'):
                for node in reversed(self._image_preview_nodes):
                    if node.scene_index == scene_index:
                        node.set_loading(False)
                        break

    def _set_connection_solid_for_node(self, target_node):
        """将指定节点对应的连线切换为实线+粒子"""
        if not hasattr(self, '_image_connections') or not hasattr(self, '_image_preview_nodes'):
            return
        for i, node in enumerate(self._image_preview_nodes):
            if node is target_node and i < len(self._image_connections):
                self._image_connections[i].set_solid()
                break

    def _download_and_set_preview(self, node, url: str):
        """下载图片并设置到预览节点"""
        from PyQt6.QtCore import QThread, pyqtSignal
        from PyQt6.QtGui import QPixmap
        import tempfile
        import os

        class _DownloadWorker(QThread):
            done = pyqtSignal(str)  # local_path

            def __init__(self, url: str):
                super().__init__()
                self._url = url

            def run(self):
                try:
                    import urllib.request
                    suffix = '.png'
                    if '.jpg' in self._url or '.jpeg' in self._url:
                        suffix = '.jpg'
                    fd, path = tempfile.mkstemp(suffix=suffix, prefix='taoge_img_')
                    os.close(fd)
                    urllib.request.urlretrieve(self._url, path)
                    self.done.emit(path)
                except Exception as e:
                    print(f"[涛割] 下载图片失败: {e}")
                    self.done.emit("")

        def _on_downloaded(path: str):
            if path:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    node.set_pixmap(pixmap)
                    node._image_path = path

        worker = _DownloadWorker(url)
        worker.done.connect(_on_downloaded)
        if not hasattr(self, '_gen_workers'):
            self._gen_workers = []
        self._gen_workers.append(worker)
        worker.start()

    def _build_enhanced_prompt(self, base_prompt: str, style_prefix: str,
                                context: dict = None) -> str:
        """构建增强提示词，拼接资产上下文"""
        parts = []

        # 风格前缀
        if style_prefix:
            parts.append(style_prefix)

        if context:
            segs = context.get('prompt_segments', {})

            # 场景描述
            scene_seg = segs.get('scene_segment', '')
            if scene_seg:
                parts.append(scene_seg)

            # 角色描述
            char_seg = segs.get('character_segment', '')
            if char_seg:
                parts.append(char_seg)

            # 道具描述
            prop_seg = segs.get('prop_segment', '')
            if prop_seg:
                parts.append(f"道具：{prop_seg}")

            # 光线描述
            light_seg = segs.get('lighting_segment', '')
            if light_seg:
                parts.append(f"光线：{light_seg}")

        # 用户基础提示词
        if base_prompt:
            parts.append(base_prompt)

        # Visual Anchors → 追加到末尾
        if context:
            neg = context.get('prompt_segments', {}).get('negative_prompt', '')
            if neg:
                parts.append(neg)

        return '\n'.join(parts) if parts else base_prompt

    def _build_video_enhanced_prompt(self, base_prompt: str, style_prefix: str,
                                      context: dict = None,
                                      scene_index: int = None) -> str:
        """构建视频增强提示词，包含景别、镜头移动、角色动作/表情、互动、氛围等"""
        parts = []

        # 风格前缀
        if style_prefix:
            parts.append(style_prefix)

        if context:
            segs = context.get('prompt_segments', {})

            # 场景描述
            scene_seg = segs.get('scene_segment', '')
            if scene_seg:
                parts.append(scene_seg)

            # 角色描述
            char_seg = segs.get('character_segment', '')
            if char_seg:
                parts.append(char_seg)

            # 道具描述
            prop_seg = segs.get('prop_segment', '')
            if prop_seg:
                parts.append(f"道具：{prop_seg}")

            # 光线描述
            light_seg = segs.get('lighting_segment', '')
            if light_seg:
                parts.append(f"光线：{light_seg}")

        # 从 Scene 模型读取视频特有信息
        if scene_index is not None and self.data_hub:
            scene_data = self._get_scene_data_by_index(scene_index)
            if scene_data:
                # 景别
                shot_size = scene_data.get('shot_size', '')
                if shot_size:
                    parts.append(f"景别：{shot_size}")

                # 镜头移动
                camera_motion = scene_data.get('camera_motion', '')
                if camera_motion:
                    parts.append(f"镜头：{camera_motion}")

                # 角色动作/表情/互动
                char_actions = scene_data.get('character_actions')
                if char_actions and isinstance(char_actions, list):
                    action_descs = []
                    for ca in char_actions:
                        name = ca.get('character', '')
                        action = ca.get('action', '')
                        expression = ca.get('expression', '')
                        dialogue = ca.get('dialogue', '')
                        desc = name
                        if action:
                            desc += f"，动作：{action}"
                        if expression:
                            desc += f"，表情：{expression}"
                        if dialogue:
                            desc += f"，台词：「{dialogue}」"
                        action_descs.append(desc)
                    if action_descs:
                        parts.append("角色表演：" + "；".join(action_descs))

                # 互动描述
                interaction = scene_data.get('interaction_desc', '')
                if interaction:
                    parts.append(f"互动：{interaction}")

                # 氛围
                atmosphere = scene_data.get('atmosphere', '')
                if atmosphere:
                    parts.append(f"氛围：{atmosphere}")

                # 连续性提示
                continuity = scene_data.get('continuity_notes')
                if continuity and isinstance(continuity, dict):
                    prev_note = continuity.get('prev_shot_note', '')
                    if prev_note:
                        parts.append(f"连续性：{prev_note}")

        # 项目级电影语法
        if context:
            cine = context.get('cinematography', {})
            if cine:
                cam_style = cine.get('default_camera_style', '')
                if cam_style:
                    parts.append(f"镜头风格：{cam_style}")

        # 用户基础提示词
        if base_prompt:
            parts.append(base_prompt)

        # Visual Anchors → 追加到末尾
        if context:
            neg = context.get('prompt_segments', {}).get('negative_prompt', '')
            if neg:
                parts.append(neg)

        return '\n'.join(parts) if parts else base_prompt

    def _get_scene_data_by_index(self, scene_index: int) -> dict:
        """按 scene_index 查询 Scene 数据"""
        if not self.data_hub or not self.data_hub.current_project_id:
            return None
        try:
            from database.session import session_scope
            from database.models import Scene
            with session_scope() as session:
                scene = session.query(Scene).filter_by(
                    project_id=self.data_hub.current_project_id,
                    scene_index=scene_index
                ).first()
                if scene:
                    return scene.to_dict()
        except Exception as e:
            print(f"[涛割] 查询 scene_index={scene_index} 失败: {e}")
        return None

    def _on_console_generate_board(self, params: dict):
        """图片控制台 → 分镜组图生成（系统指令通过 systemInstruction 字段传递）"""
        # 从 grid_count 提取宫格数量（"4张"→4, "9张"→9, "16张"→16）
        grid_str = params.get('grid_count', '4张')
        grid_num = int(''.join(c for c in grid_str if c.isdigit()) or '4')

        # 系统指令走 Gemini systemInstruction 字段（不混入用户提示词）
        system_instruction = STORYBOARD_SYSTEM_PROMPT.format(grid=grid_num)
        params = dict(params)  # 不修改原 dict
        params['system_instruction'] = system_instruction

        print(f"[涛割] 分镜组图生成请求: grid={grid_num}, style={params.get('style')}")
        # 设置目标节点为加载状态（优先用 _console_target_node）
        scene_index = params.get('scene_index')
        target_node = self._console_target_node
        if target_node and target_node.scene() and target_node.scene_index == scene_index:
            target_node.set_loading(True)
        elif hasattr(self, '_image_preview_nodes'):
            for node in reversed(self._image_preview_nodes):
                if node.scene_index == scene_index:
                    node.set_loading(True)
                    break
        # 复用单图生成 API 调用逻辑（风格追加在 _on_console_generate_image 中处理）
        self._on_console_generate_image(params)

    def _set_connection_solid(self, scene_index: int):
        """将指定 scene_index 的连线切换为实线+粒子"""
        if not hasattr(self, '_image_connections') or not hasattr(self, '_image_preview_nodes'):
            return
        for i, node in enumerate(self._image_preview_nodes):
            if node.scene_index == scene_index and i < len(self._image_connections):
                self._image_connections[i].set_solid()
                break

    def _open_intelligent_canvas_for_scene(self, scene_index: int):
        """双击图片预览节点 → 打开智能画布"""
        scene_id = self._find_scene_id_by_index(scene_index)
        if scene_id and self.data_hub:
            self.data_hub.open_intelligent_canvas.emit(scene_id)

    def _on_image_node_deleted(self, node):
        """图片预览节点删除回调 — 清理节点和对应连线"""
        # 清除控制台目标节点引用
        if self._console_target_node is node:
            self._console_target_node = None
        # 清除 tooltip 源节点引用
        if self._tooltip_source_node is node:
            self._tooltip_source_node = None
            if self._prompt_tooltip:
                self._prompt_tooltip.hide()

        # 清除多视角预览组的图片节点引用
        if self._asset_req_delegate:
            for group in self._asset_req_delegate._multi_angle_groups.values():
                if group._image_node is node:
                    group._image_node = None
                    group.update_positions()
                    break

        # 清除需求卡上的联动引用
        if self._asset_req_delegate:
            for cards in self._asset_req_delegate._requirement_cards.values():
                for card in cards:
                    if card._linked_image_node is node:
                        card._linked_image_node = None
                        card._linked_connection = None
                        break

        if not hasattr(self, '_image_preview_nodes'):
            return

        idx = None
        for i, n in enumerate(self._image_preview_nodes):
            if n is node:
                idx = i
                break

        if idx is not None:
            # 移除连线
            if idx < len(self._image_connections):
                self._image_connections[idx].remove()
                self._image_connections.pop(idx)
            # 移除节点
            if node.scene():
                self._canvas_scene.removeItem(node)
            self._image_preview_nodes.pop(idx)

        # 清除以该节点为 source 的所有变体连线
        keys_to_remove = []
        for key, link in self._variant_links.items():
            if link.source_node is node:
                link.remove()
                keys_to_remove.append(key)
                # 清除 DB 中的 linked_base_req_id
                variant_req_id = -key  # key = -variant_req_id
                if self.data_hub:
                    self.data_hub.asset_controller.clear_variant_link(variant_req_id)
        for key in keys_to_remove:
            del self._variant_links[key]

        # 持久化：清除数据库中的 generated_image_path 和 image_card_pos
        scene_id = self._find_scene_id_by_index(node.scene_index)
        if scene_id and self.data_hub:
            self.data_hub.project_controller.update_scene(
                scene_id,
                generated_image_path=None,
                status='pending',
            )
            # 同步更新分镜卡的 scene_data
            if self._shot_delegate:
                for card in self._shot_delegate._shot_cards:
                    if card.global_index == node.scene_index:
                        card.scene_data['generated_image_path'] = None
                        card.scene_data['status'] = 'pending'
                        # 清除 image_card_pos
                        gp = card.scene_data.get('generation_params') or {}
                        if isinstance(gp, dict) and 'image_card_pos' in gp:
                            del gp['image_card_pos']
                            card.scene_data['generation_params'] = gp
                            self.data_hub.project_controller.update_scene(
                                scene_id, generation_params=gp,
                            )
                        card.update()
                        break

    def _save_generated_image_to_db(self, scene_index: int, path_or_url: str):
        """将生成的图片路径保存到数据库 Scene.generated_image_path"""
        scene_id = self._find_scene_id_by_index(scene_index)
        if scene_id and self.data_hub:
            self.data_hub.project_controller.update_scene(
                scene_id,
                generated_image_path=path_or_url,
                status='image_generated',
            )
            # 同步更新分镜卡的 scene_data（内存副本）
            if self._shot_delegate:
                for card in self._shot_delegate._shot_cards:
                    if card.global_index == scene_index:
                        card.scene_data['generated_image_path'] = path_or_url
                        card.scene_data['status'] = 'image_generated'
                        card.update()
                        break

            # 持久化图片卡位置到 generation_params
            self._save_image_card_pos(scene_index)

            # 持久化生成参数到 generation_params（用于 hover 提示词恢复）
            self._save_image_gen_params(scene_index)

            print(f"[涛割] 图片路径已保存到数据库: scene_id={scene_id}")

    def _save_asset_image_to_db(self, asset_idx: int, path_or_url: str,
                                prompt: str = ''):
        """将资产需求生成的图片路径（及提示词）保存到数据库"""
        if not self.data_hub:
            return
        # asset_idx 是负数，对应的 requirement_id 取绝对值（可能是 id 或 hash）
        # 遍历需求卡找到匹配的记录
        if self._asset_req_delegate:
            for cards in self._asset_req_delegate._requirement_cards.values():
                for c in cards:
                    req_id = c.req_data.get('id')
                    if req_id and -(req_id) == asset_idx:
                        self.data_hub.asset_controller.fulfill_requirement(
                            req_id, image_path=path_or_url)
                        # 保存生成提示词到 attributes
                        if prompt:
                            self.data_hub.asset_controller.update_requirement_attributes(
                                req_id,
                                attributes={'prompt_description': prompt},
                            )
                            # 同步到内存中的 req_data
                            attrs = c.req_data.get('attributes', {}) or {}
                            attrs['prompt_description'] = prompt
                            c.req_data['attributes'] = attrs
                        c.set_fulfilled(True)
                        print(f"[涛割] 资产图片已保存: req_id={req_id}, prompt长度={len(prompt)}")
                        return

    def _find_scene_id_by_index(self, scene_index: int) -> Optional[int]:
        """根据 scene_index (global_index) 查找 scene_id"""
        if self._shot_delegate:
            for card in self._shot_delegate._shot_cards:
                if card.global_index == scene_index:
                    return card.scene_id
        return None

    def _save_image_card_pos(self, scene_index: int):
        """将图片卡当前位置持久化到 scene.generation_params['image_card_pos']"""
        if not hasattr(self, '_image_preview_nodes'):
            return
        node = None
        for n in self._image_preview_nodes:
            if n.scene_index == scene_index:
                node = n
                break
        if not node:
            return

        scene_id = self._find_scene_id_by_index(scene_index)
        if not scene_id or not self.data_hub:
            return

        # 读取当前 generation_params 并更新 image_card_pos
        if self._shot_delegate:
            for card in self._shot_delegate._shot_cards:
                if card.global_index == scene_index:
                    gp = card.scene_data.get('generation_params') or {}
                    if isinstance(gp, str):
                        import json
                        try:
                            gp = json.loads(gp)
                        except Exception:
                            gp = {}
                    gp['image_card_pos'] = {
                        'x': node.pos().x(),
                        'y': node.pos().y(),
                    }
                    card.scene_data['generation_params'] = gp
                    self.data_hub.project_controller.update_scene(
                        scene_id, generation_params=gp,
                    )
                    break

    def _save_image_gen_params(self, scene_index: int):
        """将图片节点的生成参数持久化到 generation_params['image_gen_params']"""
        if not hasattr(self, '_image_preview_nodes'):
            return
        # 找到最新的（最后一个）匹配节点
        node = None
        for n in reversed(self._image_preview_nodes):
            if n.scene_index == scene_index:
                node = n
                break
        if not node or not node._gen_params:
            return

        scene_id = self._find_scene_id_by_index(scene_index)
        if not scene_id or not self.data_hub:
            return

        if self._shot_delegate:
            for card in self._shot_delegate._shot_cards:
                if card.global_index == scene_index:
                    gp = card.scene_data.get('generation_params') or {}
                    if isinstance(gp, str):
                        import json
                        try:
                            gp = json.loads(gp)
                        except Exception:
                            gp = {}
                    # 保存生成参数（排除大体积字段如 reference_images）
                    save_params = {k: v for k, v in node._gen_params.items()
                                   if k not in ('reference_images',)}
                    gp['image_gen_params'] = save_params
                    card.scene_data['generation_params'] = gp
                    self.data_hub.project_controller.update_scene(
                        scene_id, generation_params=gp,
                    )
                    break

    def _clear_image_preview_nodes(self):
        """清理所有图片预览节点和连线"""
        if hasattr(self, '_image_connections'):
            for conn in self._image_connections:
                conn.remove()
            self._image_connections.clear()
        if hasattr(self, '_image_preview_nodes'):
            for node in self._image_preview_nodes:
                if node.scene():
                    self._canvas_scene.removeItem(node)
            self._image_preview_nodes.clear()
        # 清除所有变体连线
        for link in self._variant_links.values():
            link.remove()
        self._variant_links.clear()

    def _restore_image_preview_nodes(self):
        """项目加载后恢复已有生成图片的 ImagePreviewNode + 实线连线"""
        if not self._shot_delegate:
            return

        from .shot_card_actions import ImagePreviewNode, ShotImageConnection
        from PyQt6.QtGui import QPixmap

        # 先清理旧的图片节点和连线（undo 恢复等场景）
        self._clear_image_preview_nodes()

        if not hasattr(self, '_image_preview_nodes'):
            self._image_preview_nodes = []
            self._image_connections = []

        for card in self._shot_delegate._shot_cards:
            img_path = card.scene_data.get('generated_image_path')
            if not img_path:
                continue

            scene_index = card.global_index

            # 避免重复创建（已有同 scene_index 的节点则跳过）
            already_exists = any(
                n.scene_index == scene_index
                for n in self._image_preview_nodes
            )
            if already_exists:
                continue

            # 创建图片预览节点 — 优先使用持久化的位置
            img_node = ImagePreviewNode(
                scene_index,
                on_delete=self._on_image_node_deleted,
                on_open_canvas=self._open_intelligent_canvas_for_scene,
            )
            img_node._on_hover_show = self._on_image_hover_show
            img_node._on_hover_hide = self._on_image_hover_hide

            # 从 generation_params 读取保存的位置
            gp = card.scene_data.get('generation_params') or {}
            if isinstance(gp, str):
                import json
                try:
                    gp = json.loads(gp)
                except Exception:
                    gp = {}
            saved_pos = gp.get('image_card_pos')
            if saved_pos and isinstance(saved_pos, dict):
                img_x = saved_pos.get('x', 0)
                img_y = saved_pos.get('y', 0)
            else:
                # 默认 fallback：分镜卡上方 50px
                card_scene_rect = card.mapRectToScene(card.rect())
                img_x = card_scene_rect.center().x() - ImagePreviewNode.NODE_WIDTH / 2
                img_y = card_scene_rect.top() - ImagePreviewNode.NODE_HEIGHT - 50
            img_node.setPos(img_x, img_y)
            # 恢复的节点已有图片，停止空闲自毁计时器
            img_node._idle_timer.stop()

            # 恢复生成参数（用于 hover 提示词显示）
            saved_gen_params = gp.get('image_gen_params')
            if saved_gen_params and isinstance(saved_gen_params, dict):
                img_node.set_gen_params(saved_gen_params)

            self._canvas_scene.addItem(img_node)

            # 创建实线连线（图片已生成，直接实线+粒子）
            connection = ShotImageConnection(self._canvas_scene, card, img_node)
            connection.set_solid()
            if not self._animations_enabled:
                connection.set_animations_enabled(False)

            self._image_preview_nodes.append(img_node)
            self._image_connections.append(connection)

            # 加载图片到节点
            if os.path.isfile(img_path):
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    img_node.set_pixmap(pixmap)
            else:
                # 远程 URL：下载后显示
                self._download_and_set_preview(img_node, img_path)

        restored_count = len(self._image_preview_nodes)
        if restored_count:
            print(f"[涛割] 已恢复 {restored_count} 个图片预览节点")

        # ── 恢复资产需求卡的已生成图片 ──
        self._restore_asset_image_nodes()

        # ── 恢复PS预览卡 ──
        self._restore_ps_preview_nodes()

    def _restore_ps_preview_nodes(self):
        """项目加载后恢复已有 PS 合成图的 PSPreviewNode + 连线"""
        if not self._shot_delegate:
            return

        import os
        from .shot_card_actions import PSPreviewNode, ShotImageConnection
        from PyQt6.QtGui import QPixmap

        # 初始化列表（如果还没有）
        if not hasattr(self, '_ps_preview_nodes'):
            self._ps_preview_nodes = []
        if not hasattr(self, '_ps_connections'):
            self._ps_connections = []

        # 清理旧的 PS 节点和连线
        for node in list(self._ps_preview_nodes):
            if node.scene():
                self._canvas_scene.removeItem(node)
        self._ps_preview_nodes.clear()

        for conn in list(self._ps_connections):
            try:
                conn.remove()
            except Exception:
                pass
        self._ps_connections.clear()

        # 遍历所有分镜卡，查找有 ps_composite_image 的场景
        for card in self._shot_delegate._shot_cards:
            gp = card.scene_data.get('generation_params') or {}
            if isinstance(gp, str):
                import json
                try:
                    gp = json.loads(gp)
                except Exception:
                    gp = {}

            ps_image_path = gp.get('ps_composite_image', '')
            if not ps_image_path or not os.path.isfile(ps_image_path):
                continue

            scene_index = card.global_index
            scene_id = card.scene_data.get('id', getattr(card, 'scene_id', 0))

            # 避免重复创建
            already_exists = any(
                n.scene_index == scene_index
                for n in self._ps_preview_nodes
            )
            if already_exists:
                continue

            # 读取保存的位置
            saved_pos = gp.get('ps_card_pos')
            if saved_pos and isinstance(saved_pos, dict):
                ps_x = saved_pos.get('x', 0)
                ps_y = saved_pos.get('y', 0)
            else:
                # 默认 fallback：分镜卡右侧
                card_rect = card.mapRectToScene(card.rect())
                ps_x = card_rect.right() + 30
                ps_y = card_rect.top()

            # 创建 PS 预览节点
            ps_node = PSPreviewNode(
                scene_index=scene_index,
                scene_id=scene_id,
                on_delete=self._on_ps_node_deleted,
                on_reopen_ps=self._on_ps_card_reopen,
                on_moved=self._save_ps_card_pos,
            )
            ps_node.setPos(ps_x, ps_y)

            # 加载合成图
            pixmap = QPixmap(ps_image_path)
            if not pixmap.isNull():
                ps_node.set_pixmap(pixmap, ps_image_path)

            self._canvas_scene.addItem(ps_node)
            self._ps_preview_nodes.append(ps_node)

            # 创建连线（分镜卡 → PS卡）
            connection = ShotImageConnection(
                self._canvas_scene, card, ps_node)
            connection.set_solid()
            if not self._animations_enabled:
                connection.set_animations_enabled(False)
            self._ps_connections.append(connection)

        restored_count = len(self._ps_preview_nodes)
        if restored_count:
            print(f"[涛割] 已恢复 {restored_count} 个PS预览节点")

    def _restore_asset_image_nodes(self):
        """恢复资产需求卡的已生成图片的 ImagePreviewNode + 连线 + 变体连线"""
        if not self._asset_req_delegate:
            return
        from .shot_card_actions import ImagePreviewNode, ShotImageConnection
        from .asset_requirement_cards import VariantLinkLine
        from PyQt6.QtGui import QPixmap

        if not hasattr(self, '_image_preview_nodes'):
            self._image_preview_nodes = []
            self._image_connections = []

        count = 0
        for cards in self._asset_req_delegate._requirement_cards.values():
            for card in cards:
                img_path = card.req_data.get('generated_image_path')
                if not img_path:
                    continue

                req_id = card.req_data.get('id')
                if not req_id:
                    continue
                asset_idx = -req_id

                # 避免重复
                if any(n.scene_index == asset_idx for n in self._image_preview_nodes):
                    continue

                # 在需求卡左侧创建图片节点
                card_scene_rect = card.mapRectToScene(card.rect())
                img_x = card_scene_rect.left() - ImagePreviewNode.NODE_WIDTH - 30
                img_y = card_scene_rect.center().y() - ImagePreviewNode.NODE_HEIGHT / 2

                img_node = ImagePreviewNode(
                    asset_idx,
                    on_delete=self._on_image_node_deleted,
                    on_open_canvas=self._open_intelligent_canvas_for_scene,
                )
                img_node.setPos(img_x, img_y)
                img_node._idle_timer.stop()
                self._canvas_scene.addItem(img_node)

                # 实线连线 + 粒子
                connection = ShotImageConnection(
                    self._canvas_scene, card, img_node)
                connection.set_solid()
                if not self._animations_enabled:
                    connection.set_animations_enabled(False)

                self._image_preview_nodes.append(img_node)
                self._image_connections.append(connection)

                # 联动拖拽：卡片拖动时主图+连线跟随
                card._linked_image_node = img_node
                card._linked_connection = connection

                # 加载图片
                if os.path.isfile(img_path):
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        img_node.set_pixmap(pixmap)
                        img_node._image_path = img_path
                else:
                    self._download_and_set_preview(img_node, img_path)
                    img_node._image_path = img_path

                # 基础角色 → 显示变体拖拽锚点
                self._show_variant_anchor_if_character(img_node, asset_idx)

                # 标记卡片为已完成
                card.set_fulfilled(True)

                # 多视角预览组关联图片节点（缩略图从图片节点左侧伸出）
                if req_id in self._asset_req_delegate._multi_angle_groups:
                    group = self._asset_req_delegate._multi_angle_groups[req_id]
                    group.set_image_node(img_node)
                    card._linked_multi_angle = group

                count += 1

        if count:
            print(f"[涛割] 已恢复 {count} 个资产图片预览节点")

        # ── 恢复变体连线 ──
        self._restore_variant_links()

    def _restore_variant_links(self):
        """从数据库恢复变体连线关系"""
        if not self._asset_req_delegate:
            return
        from .asset_requirement_cards import VariantLinkLine

        if not hasattr(self, '_image_preview_nodes'):
            return

        for cards in self._asset_req_delegate._requirement_cards.values():
            for card in cards:
                attrs = card.req_data.get('attributes', {})
                linked_base_req_id = attrs.get('linked_base_req_id')
                if not linked_base_req_id:
                    continue

                variant_req_id = card.req_data.get('id')
                if not variant_req_id:
                    continue
                variant_asset_idx = -variant_req_id

                # 已有连线则跳过
                if variant_asset_idx in self._variant_links:
                    continue

                # 找到基础角色的图片节点
                base_asset_idx = -linked_base_req_id
                source_node = None
                for n in self._image_preview_nodes:
                    if n.scene_index == base_asset_idx and n._pixmap is not None:
                        source_node = n
                        break

                if source_node:
                    link = VariantLinkLine(self._canvas_scene, source_node, card)
                    self._variant_links[variant_asset_idx] = link

        if self._variant_links:
            print(f"[涛割] 已恢复 {len(self._variant_links)} 条变体连线")

    def _on_video_gen_finished(self, success: bool, url: str, error: str,
                                scene_index: int):
        """视频生成完成回调 — 下载视频到本地并保存路径到数据库"""
        if not success or not url:
            print(f"[涛割] 视频生成失败 (scene={scene_index}): {error}")
            return

        print(f"[涛割] 视频生成成功 (scene={scene_index}): {url}")

        # 下载视频到本地
        import os
        import urllib.request
        import uuid

        output_dir = os.path.join("generated", "videos")
        os.makedirs(output_dir, exist_ok=True)

        ext = ".mp4"
        if ".webm" in url:
            ext = ".webm"
        filename = f"sora_{scene_index}_{uuid.uuid4().hex[:8]}{ext}"
        local_path = os.path.join(output_dir, filename)

        try:
            print(f"[涛割] 正在下载视频到 {local_path} ...")
            urllib.request.urlretrieve(url, local_path)
            file_size = os.path.getsize(local_path)
            print(f"[涛割] 视频下载完成: {local_path} ({file_size} bytes)")
        except Exception as e:
            print(f"[涛割] 视频下载失败: {e}，保存远程 URL")
            local_path = url  # fallback: 保存远程 URL

        # 保存路径到数据库 Scene.generated_video_path
        scene_id = self._find_scene_id_by_index(scene_index)
        if scene_id and self.data_hub:
            self.data_hub.project_controller.update_scene(
                scene_id,
                generated_video_path=local_path,
                status='video_generated',
            )
            # 同步更新分镜卡的内存副本
            if self._shot_delegate:
                for card in self._shot_delegate._shot_cards:
                    if card.global_index == scene_index:
                        card.scene_data['generated_video_path'] = local_path
                        card.scene_data['status'] = 'video_generated'
                        card.update()
                        break
            print(f"[涛割] 视频路径已保存到数据库: scene_id={scene_id}")

    def _rebuild_persistent_connections(self):
        """重建所有场景卡→分支节点→分镜卡的持久连线，并平移 Zone 1 元素对齐"""
        if not self._connection_mgr:
            return
        if not self._act_delegate or not self._shot_delegate:
            return

        act_groups = {}
        for group in self._act_delegate._groups:
            act_data = group.get('act_data', {})
            act_id = act_data.get('id')
            summary = group.get('summary')  # 可以为 None
            color = group.get('color', QColor(100, 100, 100))

            if not act_id:
                continue

            # 获取该场次在分镜区的卡片
            shot_cards = self._shot_delegate.get_act_shot_cards(act_id)
            if not shot_cards:
                continue

            act_groups[act_id] = {
                'summary': summary,  # 允许 None，连线生成时会跳过
                'shot_cards': shot_cards,
                'color': color,
            }

        # 在 Zone 2 (分镜区) 上重建连线，获取每组分镜的中心 X
        collapsed_cards = self._shot_delegate._collapsed_cards if self._shot_delegate else {}
        center_x_map = self._connection_mgr.rebuild_all_connections(
            act_groups, parent_item=self._zone_shot,
            collapsed_cards=collapsed_cards
        )

        # 平移 Zone 1 中的场景卡+组背景，使其 X 中心对齐分镜组中心
        if center_x_map and self._zone_act and self._zone_shot:
            self._align_zone1_to_shot_centers(act_groups, center_x_map)
            # 同步更新后的 summary 引用到连线管理器（alignment 重建了 summary card）
            for group in self._act_delegate._groups:
                act_data = group.get('act_data', {})
                act_id = act_data.get('id')
                if act_id:
                    self._connection_mgr._summary_cards[act_id] = group.get('summary')
            # 立即更新节点位置和主干线端点以匹配新的 summary 位置
            self._connection_mgr.update_all()

    def _align_zone1_to_shot_centers(self, act_groups: dict,
                                      center_x_map: dict):
        """将 Zone 1 中的场景组水平定位，对齐 Zone 2 分镜组中心，防止重叠。

        只计算各组的目标 X 坐标，然后委托 _do_layout(group_x_positions=...)
        执行布局，确保统一高度、滚动窗口、ZoneFrame 紧贴等逻辑一致。
        """
        from .act_sequence_panel import SentenceCard

        GROUP_X_GAP = self._act_delegate.GROUP_X_GAP

        # ── 计算每组的目标 X 坐标 ──
        group_x_positions = {}
        next_min_x = self._act_delegate.SENTENCE_X

        for gi, group in enumerate(self._act_delegate._groups):
            act_data = group.get('act_data', {})
            act_id = act_data.get('id')
            cards = group.get('cards', [])
            if not cards:
                # 空组也要占位，避免后续组的 X 不连续
                group_x_positions[gi] = next_min_x
                next_min_x += SentenceCard.CARD_WIDTH + GROUP_X_GAP
                continue

            if act_id and act_id in center_x_map:
                # 该组在 Zone 2 有对应的可见分镜 → 对齐到分镜中心
                center_x_zone2 = center_x_map[act_id]
                scene_pt = self._zone_shot.mapToScene(QPointF(center_x_zone2, 0))
                zone1_pt = self._zone_act.mapFromScene(scene_pt)
                target_x = zone1_pt.x() - SentenceCard.CARD_WIDTH / 2
            else:
                # 该组被折叠或无分镜 → 紧跟前一组
                target_x = next_min_x

            # 防重叠：确保不与前一组重叠
            if target_x < next_min_x:
                target_x = next_min_x

            group_x_positions[gi] = target_x
            next_min_x = target_x + SentenceCard.CARD_WIDTH + GROUP_X_GAP

        # ── 委托 _do_layout 执行统一布局 ──
        self._act_delegate._do_layout(group_x_positions=group_x_positions)

    def _on_branch_toggled(self, act_id: int, collapsed: bool):
        """分支节点折叠/展开 → 延迟重排（避免 clear_all 销毁正在回调的节点）"""
        if not self._shot_delegate:
            return
        # 延迟到下一事件循环，避免在节点回调链中销毁节点自身
        QTimer.singleShot(0, self._deferred_relayout_and_rebuild)

    def _on_branch_solo(self, act_id: int):
        """分支节点 solo → 延迟重排"""
        if not self._shot_delegate:
            return
        QTimer.singleShot(0, self._deferred_relayout_and_rebuild)

    def _deferred_relayout_and_rebuild(self):
        """延迟执行的重排+重建连线，供分支节点 toggle/solo 回调使用"""
        if not self._shot_delegate:
            return

        # 记住 Zone 2 当前位置（toggle 不应改变 Zone 2 的 Y 位置）
        zone2_pos = self._zone_shot.pos() if self._zone_shot else None

        # 1. 重排可见分镜卡位置（Zone 2）
        self._shot_delegate.relayout_after_toggle()
        visible = self._shot_delegate.get_visible_items()
        if visible:
            self._zone_shot.auto_fit_content(visible)

        # 恢复 Zone 2 的 Y 位置
        if zone2_pos and self._zone_shot:
            self._zone_shot.setPos(zone2_pos)

        # 2. 重建连线
        self._rebuild_persistent_connections()

        # 3. 最终恢复 Zone 2 位置
        if zone2_pos and self._zone_shot:
            self._zone_shot.setPos(zone2_pos)

        # 4. 更新连线管理器
        if self._connection_mgr:
            self._connection_mgr.update_all()

    def _update_asset_connections(self):
        """更新资产需求区连线（Zone 移动/resize 后重建）"""
        if self._asset_req_delegate and self._asset_req_delegate._connection_mgr:
            self._asset_req_delegate._connection_mgr.rebuild_connections(
                self._asset_req_delegate._summary_card,
                self._asset_req_delegate._category_cards,
                self._asset_req_delegate._requirement_cards,
            )

    def _on_zone_moved(self):
        """ZoneFrame 移动后更新连线 + 源文本框位置"""
        if self._connection_mgr:
            self._connection_mgr.update_all()
        self._update_asset_connections()
        self._reposition_source_text_box()
        self._rebuild_source_to_group_curves()

    def _on_zone_resized(self):
        """ZoneFrame 缩放后更新委托布局 + Zone 位置自适应（垂直：从下到上）"""
        # Zone 2 (分镜) 底边锚定在 Zone 1 顶边上方
        if self._zone_act and self._zone_shot:
            act_top = self._zone_act.pos().y()
            shot_bottom = act_top - ZONE_GAP
            shot_y = shot_bottom - self._zone_shot.rect().height()
            self._zone_shot.setPos(self._zone_shot.pos().x(), shot_y)
        # Zone 5 (资产需求) 在 Zone 2 左侧
        if self._zone_shot and self._zone_asset_req:
            shot_left = self._zone_shot.pos().x()
            zone5_w = self._zone_asset_req.rect().width()
            self._zone_asset_req.setPos(
                shot_left - ZONE_GAP - zone5_w,
                self._zone_shot.pos().y()
            )
        if self._connection_mgr:
            self._connection_mgr.update_all()
        self._update_asset_connections()
        # SourceTextBox 跟随 Zone 1 定位
        self._reposition_source_text_box()
        self._rebuild_source_to_group_curves()

    # ==================== 鼠标事件路由 ====================

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self._canvas_scene.itemAt(scene_pos, self.transform())

            # IMPORT_POPUP 状态：点击按钮以外 → 关闭弹出
            if self._canvas_state == CanvasState.IMPORT_POPUP:
                from .import_popup import ImportButton
                if not isinstance(item, ImportButton):
                    if self._import_popup:
                        self._import_popup.hide()
                    self._transition_to(CanvasState.WELCOME)
                    event.accept()
                    return
                else:
                    # 按钮自己处理点击
                    super().mousePressEvent(event)
                    return

            # SOURCE_LOADED 状态：点击 SourceTextBox → 选中 + 滑入场景化按钮
            if self._canvas_state == CanvasState.SOURCE_LOADED:
                from .source_text_box import SourceTextBox, CornerResizeHandle
                if isinstance(item, (SourceTextBox, CornerResizeHandle)):
                    if isinstance(item, CornerResizeHandle):
                        # 手柄拖拽由手柄自己处理
                        super().mousePressEvent(event)
                        return
                    self._source_text_box.set_selected(True)
                    self._show_context_button("scene_split")
                    event.accept()
                    return
                elif self._source_text_box and self._source_text_box.is_selected:
                    self._source_text_box.set_selected(False)
                    self._hide_context_buttons()

            # 后续状态（SCENES_SPLIT 等）：点击 SourceTextBox → 滑入场景化按钮
            if self._canvas_state in (CanvasState.SCENES_SPLIT,
                                      CanvasState.SCENES_ANALYZED,
                                      CanvasState.SHOTS_CREATED):
                from .source_text_box import SourceTextBox, CornerResizeHandle
                if isinstance(item, SourceTextBox):
                    self._source_text_box.set_selected(True)
                    self._show_context_button("scene_split")
                    event.accept()
                    return

            # [DEPRECATED] SmartPSAgentNode 已迁移到独立窗口，不再嵌入统一画布

            # ShotCardPlusButton / ShotDragActionMenu / ImagePreviewNode / PSPreviewNode 自行处理事件
            from .shot_card_actions import ShotCardPlusButton, ShotDragActionMenu, ImagePreviewNode, PSPreviewNode
            if isinstance(item, (ShotCardPlusButton, ShotDragActionMenu, PSPreviewNode)):
                super().mousePressEvent(event)
                return
            if isinstance(item, ImagePreviewNode):
                # 点击已有图片的节点 → 弹出控制台以便重新生成（创建新卡）
                if item._pixmap is not None and hasattr(item, '_gen_params') and item._gen_params:
                    self._regenerate_from_node = item
                    self._on_fill_console_from_tooltip(item._gen_params)
                super().mousePressEvent(event)
                return

            # AssetPlusButton / AssetActionMenu / VariantLinkAnchor / InlineNameInput /
            # AssetCategoryCard / AssetRequirementCard 自行处理事件
            # （AssetCategoryCard 需要拖拽新增，AssetRequirementCard 需要 ItemIsMovable 拖拽移动）
            from .asset_requirement_cards import (
                AssetPlusButton, AssetActionMenu, VariantLinkAnchor, InlineNameInput,
                AssetCategoryCard, AssetRequirementCard,
                MultiAngleThumbnailNode,
            )
            if isinstance(item, (AssetPlusButton, AssetActionMenu,
                                 VariantLinkAnchor, InlineNameInput,
                                 AssetCategoryCard,
                                 MultiAngleThumbnailNode)):
                super().mousePressEvent(event)
                return

            # AssetRequirementCard：先在 delegate 中做选中 + AI补全检测，
            # 然后交还给 QGraphicsScene 以支持 ItemIsMovable 拖拽
            if isinstance(item, AssetRequirementCard) or (
                    item and self._find_parent_of_type(item, AssetRequirementCard)):
                target_card = item if isinstance(item, AssetRequirementCard) \
                    else self._find_parent_of_type(item, AssetRequirementCard)
                if target_card and self._asset_req_delegate:
                    # AI 补全按钮 hit-test
                    local_pos = target_card.mapFromScene(scene_pos)
                    if (target_card._on_ai_fill
                            and not target_card._ai_fill_btn_rect.isNull()
                            and target_card._ai_fill_btn_rect.contains(local_pos)
                            and not target_card._is_ai_filling):
                        target_card._on_ai_fill(target_card._data)
                        event.accept()
                        return
                    # 选中逻辑
                    for cards in self._asset_req_delegate._requirement_cards.values():
                        for c in cards:
                            if c is not target_card:
                                c.set_selected(False)
                    target_card.set_selected(True)
                    self._asset_req_delegate.requirement_selected.emit(target_card.req_data)
                # 交给 QGraphicsScene 处理 ItemIsMovable
                super().mousePressEvent(event)
                return

            # MindMapBranchNode 自己处理点击（折叠/展开）
            if isinstance(item, MindMapBranchNode):
                super().mousePressEvent(event)
                return

            # 找到点击所在的 ZoneFrame
            zone = self._find_parent_zone(item)

            if zone:
                local_pos = zone.mapFromScene(scene_pos)

                if zone._is_in_title_bar(local_pos):
                    # 标题栏点击（按钮或拖拽）
                    self._zone_interacting = zone
                    handled = zone.handle_title_press(scene_pos, local_pos)
                    if zone._is_dragging_title:
                        self._undo_manager.begin_operation("移动区域")
                    self._set_active_zone(zone)
                    # 标题栏点击（非按钮区域）→ 显示上下文按钮
                    if zone._is_dragging_title:
                        self._handle_title_bar_context_button(zone)
                    event.accept()
                    return

                if zone._is_in_resize_handle(local_pos):
                    # 缩放手柄
                    self._zone_interacting = zone
                    zone.handle_resize_press(scene_pos)
                    self._undo_manager.begin_operation("调整区域大小")
                    event.accept()
                    return

                # 内容区域 → 委托给 delegate
                self._set_active_zone(zone)
                delegate = self._get_delegate(zone.zone_id)
                if delegate:
                    delegate.handle_mouse_press(scene_pos, event, item)
                    self._left_press_delegate = delegate

                    # 上下文感知按钮：根据点击对象决定显示哪个按钮
                    if zone.zone_id == "act":
                        self._handle_act_zone_context_button(item)

                    event.accept()
                    return

            # 空白区域 — 先检查是否在某个 zone 的内容区域内
            zone_by_pos = self._find_zone_by_pos(scene_pos)
            if zone_by_pos:
                local_pos = zone_by_pos.mapFromScene(scene_pos)
                if not zone_by_pos._is_in_title_bar(local_pos):
                    delegate = self._get_delegate(zone_by_pos.zone_id)
                    if delegate:
                        self._set_active_zone(zone_by_pos)
                        delegate.handle_mouse_press(scene_pos, event, item)
                        self._left_press_delegate = delegate
                        event.accept()
                        return
            # Zone 外空白区域 → 画布级别框选
            self._left_press_delegate = None
            self._deselect_all_zones()
            self._is_canvas_rubber_banding = True
            self._canvas_rubber_band_start = scene_pos
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 检查是否有 ZoneFrame 在交互（拖拽/缩放）
        if self._zone_interacting and self._zone_interacting.is_busy():
            scene_pos = self.mapToScene(event.position().toPoint())
            self._zone_interacting.handle_mouse_move(scene_pos)
            event.accept()
            return

        # 画布级别框选
        if self._is_canvas_rubber_banding and self._canvas_rubber_band_start is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._canvas_rubber_band_start, scene_pos).normalized()
            if self._canvas_rubber_band_rect is None:
                self._canvas_rubber_band_rect = self._canvas_scene.addRect(
                    rect,
                    QPen(QColor(0, 122, 204, 180), 1.5, Qt.PenStyle.DashLine),
                    QBrush(QColor(0, 122, 204, 25))
                )
                self._canvas_rubber_band_rect.setZValue(2000)
            else:
                self._canvas_rubber_band_rect.setRect(rect)
            event.accept()
            return

        # 左键按下时激活的 delegate（最可靠的路由）
        if self._left_press_delegate and self._left_press_delegate.is_mouse_active():
            scene_pos = self.mapToScene(event.position().toPoint())
            self._left_press_delegate.handle_mouse_move(scene_pos, event)
            event.accept()
            return

        # 兜底：通过 _active_zone 查找 delegate
        if self._active_zone:
            delegate = self._get_delegate(self._active_zone.zone_id)
            if delegate and delegate.is_mouse_active():
                scene_pos = self.mapToScene(event.position().toPoint())
                delegate.handle_mouse_move(scene_pos, event)
                event.accept()
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 画布级别框选结束
            if self._is_canvas_rubber_banding:
                self._is_canvas_rubber_banding = False
                if self._canvas_rubber_band_rect:
                    if self._canvas_rubber_band_rect.scene():
                        self._canvas_scene.removeItem(self._canvas_rubber_band_rect)
                    self._canvas_rubber_band_rect = None
                self._canvas_rubber_band_start = None
                event.accept()
                return

            # ZoneFrame 交互结束
            if self._zone_interacting:
                was_interacting = self._zone_interacting.is_busy()
                self._zone_interacting.handle_mouse_release()
                self._zone_interacting = None
                # Undo: commit zone 移动/缩放
                if was_interacting and self._undo_manager.is_operation_pending():
                    self._undo_manager.commit_operation()
                self._left_press_delegate = None
                event.accept()
                return

            # 左键按下时激活的 delegate
            if self._left_press_delegate and self._left_press_delegate.is_mouse_active():
                scene_pos = self.mapToScene(event.position().toPoint())
                self._left_press_delegate.handle_mouse_release(scene_pos, event)
                self._left_press_delegate = None
                event.accept()
                return

            # 兜底：通过 _active_zone 查找 delegate
            if self._active_zone:
                delegate = self._get_delegate(self._active_zone.zone_id)
                if delegate and delegate.is_mouse_active():
                    scene_pos = self.mapToScene(event.position().toPoint())
                    delegate.handle_mouse_release(scene_pos, event)
                    self._left_press_delegate = None
                    event.accept()
                    return

            self._left_press_delegate = None

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """滚轮事件：SourceTextBox / ShotCanvasCard 选中且鼠标在其上方时转发"""
        scene_pos = self.mapToScene(event.position().toPoint())

        # 选中的 SourceTextBox 内滚动
        if self._source_text_box and self._source_text_box.is_selected:
            if self._source_text_box.sceneBoundingRect().contains(scene_pos):
                delta = event.angleDelta().y()
                lines = -1 if delta > 0 else 1  # 滚轮上=向上翻
                self._source_text_box.scroll_by(lines * 3)
                event.accept()
                return

        # 选中的分镜卡内滚动
        if self._shot_delegate:
            selected_card = self._shot_delegate.get_selected_card()
            if selected_card and selected_card.is_scrollable:
                if selected_card.sceneBoundingRect().contains(scene_pos):
                    delta = event.angleDelta().y()
                    selected_card.scroll_content(-delta * 0.5)
                    event.accept()
                    return

        # 大场景序列区组内滚轮翻页（无修饰键时）
        modifiers = event.modifiers()
        if not (modifiers & (Qt.KeyboardModifier.ControlModifier |
                             Qt.KeyboardModifier.ShiftModifier)):
            if self._act_delegate:
                from .act_sequence_panel import ActGroupBackground, SentenceCard
                item = self._canvas_scene.itemAt(scene_pos, self.transform())
                # 沿父链查找 ActGroupBackground 或 SentenceCard
                target = item
                while target:
                    if isinstance(target, ActGroupBackground):
                        group_id = self._act_delegate.find_group_by_background(target)
                        if group_id is not None:
                            delta = event.angleDelta().y()
                            scroll_dir = 1 if delta > 0 else -1
                            self._act_delegate.scroll_group(group_id, scroll_dir)
                            event.accept()
                            return
                        break
                    if isinstance(target, SentenceCard) and target.act_group_id is not None:
                        delta = event.angleDelta().y()
                        scroll_dir = 1 if delta > 0 else -1
                        self._act_delegate.scroll_group(target.act_group_id, scroll_dir)
                        event.accept()
                        return
                    target = target.parentItem() if hasattr(target, 'parentItem') else None

        super().wheelEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单路由"""
        if self._pan_moved:
            return

        scene_pos = self.mapToScene(event.pos())
        item = self._canvas_scene.itemAt(scene_pos, self.transform())

        # MindMapBranchNode 自己处理右键菜单（solo等）
        if isinstance(item, MindMapBranchNode):
            super().contextMenuEvent(event)
            return

        zone = self._find_parent_zone(item)

        if zone:
            delegate = self._get_delegate(zone.zone_id)
            if delegate:
                delegate.handle_context_menu(scene_pos, event, item)
                return

        super().contextMenuEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击画布"""
        scene_pos = self.mapToScene(event.position().toPoint())

        # WELCOME 状态：双击 → 弹出导入按钮
        if self._canvas_state == CanvasState.WELCOME:
            self._show_import_popup(scene_pos)
            event.accept()
            return

        # 其他状态：双击标题栏 → zoom to fit 该 zone
        item = self._canvas_scene.itemAt(scene_pos, self.transform())
        zone = self._find_parent_zone(item)

        if zone:
            local_pos = zone.mapFromScene(scene_pos)
            if zone._is_in_title_bar(local_pos):
                zone_rect = zone.sceneBoundingRect().adjusted(-20, -20, 20, 20)
                self.fitInView(zone_rect, Qt.AspectRatioMode.KeepAspectRatio)
                self._zoom_factor = self.transform().m11()
                self.zoom_changed.emit(int(self._zoom_factor * 100))
                event.accept()
                return

        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Escape → fit all zones, Ctrl+Z → undo, Ctrl+Shift+Z / Ctrl+Y → redo, Delete → 删除选中卡片"""
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        if event.key() == Qt.Key.Key_Escape:
            self.fit_all_in_view()
            event.accept()
            return

        # Delete / Backspace → 删除选中的资产需求卡
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._asset_req_delegate:
                if self._asset_req_delegate.delete_selected_card():
                    event.accept()
                    return

        if ctrl and event.key() == Qt.Key.Key_Z:
            if shift:
                # Ctrl+Shift+Z → redo
                self._undo_manager.redo()
            else:
                # Ctrl+Z → undo
                self._undo_manager.undo()
            event.accept()
            return

        if ctrl and event.key() == Qt.Key.Key_Y:
            # Ctrl+Y → redo
            self._undo_manager.redo()
            event.accept()
            return

        super().keyPressEvent(event)

    def resizeEvent(self, event):
        """视口大小变化 → 重定位浮动组件"""
        super().resizeEvent(event)
        self._position_console_bar()
        self._position_image_console()
        self._position_video_console()
        self._position_quick_nav()
        self._position_anim_toggle_btn()
        if hasattr(self, '_control_bar'):
            self._control_bar.reposition()
        # WELCOME 状态时重新居中欢迎文字
        if self._canvas_state == CanvasState.WELCOME:
            self._center_welcome_text()

    # ==================== 辅助方法 ====================

    def _find_parent_zone(self, item: Optional[QGraphicsItem]) -> Optional[ZoneFrame]:
        """查找 item 所属的 ZoneFrame（沿父链向上查找）"""
        if item is None:
            return None

        # 直接是 ZoneFrame
        if isinstance(item, ZoneFrame):
            return item

        # 沿父链查找
        current = item.parentItem()
        while current:
            if isinstance(current, ZoneFrame):
                return current
            current = current.parentItem()

        # 如果没有父子关系，检查场景位置
        scene_pos = item.sceneBoundingRect().center()
        for zone in self._zones.values():
            if zone.sceneBoundingRect().contains(scene_pos):
                return zone

        return None

    def _find_parent_of_type(self, item: Optional[QGraphicsItem], cls) -> Optional[QGraphicsItem]:
        """沿父链向上查找指定类型的 item"""
        current = item
        while current:
            if isinstance(current, cls):
                return current
            current = current.parentItem()
        return None

    def _find_zone_by_pos(self, scene_pos: QPointF) -> Optional[ZoneFrame]:
        """根据场景坐标查找所在的 ZoneFrame（用于空白区域检测）"""
        for zone in self._zones.values():
            if zone.sceneBoundingRect().contains(scene_pos):
                return zone
        return None

    def _get_delegate(self, zone_id: str):
        if zone_id == "act":
            return self._act_delegate
        elif zone_id == "shot":
            return self._shot_delegate
        elif zone_id == "asset_req":
            return self._asset_req_delegate
        return None

    def _set_active_zone(self, zone: ZoneFrame):
        if self._active_zone and self._active_zone is not zone:
            self._active_zone.set_active(False)
        zone.set_active(True)
        self._active_zone = zone

    def _deselect_all_zones(self):
        for zone in self._zones.values():
            zone.set_active(False)
        self._active_zone = None
        # 取消 SourceTextBox 选中
        if self._source_text_box and hasattr(self._source_text_box, 'is_selected'):
            if self._source_text_box.is_selected:
                self._source_text_box.set_selected(False)
        # 取消 Act delegate 选中
        if self._act_delegate:
            self._act_delegate._deselect_all()
        # 移除任何存在的 ShotDragActionMenu / AssetActionMenu
        from .shot_card_actions import ShotDragActionMenu
        from .asset_requirement_cards import AssetActionMenu
        for it in list(self._canvas_scene.items()):
            if isinstance(it, (ShotDragActionMenu, AssetActionMenu)):
                self._canvas_scene.removeItem(it)
        # 滑出控制栏
        self._hide_context_buttons()
        # 隐藏图片控制台
        if self._image_console and self._image_console.is_visible_state:
            self._image_console.slide_down()
            # 恢复自动切换的横竖屏状态
            if hasattr(self, '_pre_asset_orientation'):
                self._image_console.set_orientation(self._pre_asset_orientation)
                del self._pre_asset_orientation
            # 控制台下滑时，对所有空白图片卡启动 10 秒倒计时
            if hasattr(self, '_image_preview_nodes'):
                for node in self._image_preview_nodes:
                    if hasattr(node, 'start_idle_countdown'):
                        node.start_idle_countdown()
        # 隐藏视频控制台
        if self._video_console and self._video_console.is_visible_state:
            self._video_console.slide_down()

    def fit_all_zones(self):
        """适应视口显示所有 zone"""
        self.fit_all_in_view()

    def _scroll_to_act_zone(self):
        """将视口滚动到底部大场景序列区"""
        if self._zone_act:
            default_zoom = 0.6
            t = QTransform()
            t.scale(default_zoom, default_zoom)
            self.setTransform(t)
            self._zoom_factor = default_zoom
            self._expand_scene_rect()
            zone_center = self._zone_act.sceneBoundingRect().center()
            self.centerOn(zone_center)
            self._expand_scene_rect()
            self.zoom_changed.emit(int(self._zoom_factor * 100))

    def _save_view_state(self):
        """保存当前项目的视图状态"""
        if self._current_project_id is not None:
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            self._view_states[self._current_project_id] = {
                'zoom': self._zoom_factor,
                'h_scroll': h_bar.value(),
                'v_scroll': v_bar.value(),
                'canvas_state': self._canvas_state.value,
            }

    def _restore_or_init_view(self):
        """恢复已保存的视图状态，或首次进入时定位到内容区域"""
        if self._current_project_id is None:
            return
        state = self._view_states.get(self._current_project_id)
        if state:
            # 恢复缩放比例
            zoom = state['zoom']
            zoom = max(0.05, min(10.0, zoom))
            t = QTransform()
            t.scale(zoom, zoom)
            self.setTransform(t)
            self._zoom_factor = zoom
            self._expand_scene_rect()
            # 恢复滚动位置
            self.horizontalScrollBar().setValue(state['h_scroll'])
            self.verticalScrollBar().setValue(state['v_scroll'])
            self.zoom_changed.emit(int(self._zoom_factor * 100))
        else:
            # 首次进入
            if self._zone_act:
                self._scroll_to_act_zone()
            elif self._source_text_box:
                box_rect = self._source_text_box.sceneBoundingRect().adjusted(-50, -50, 50, 50)
                self.fitInView(box_rect, Qt.AspectRatioMode.KeepAspectRatio)
                self._zoom_factor = self.transform().m11()
                self.zoom_changed.emit(int(self._zoom_factor * 100))

    # ==================== 主题 ====================

    def apply_theme(self):
        """刷新主题"""
        for zone in self._zones.values():
            zone.update()
        if self._act_delegate:
            self._act_delegate.apply_theme()
        if self._shot_delegate:
            self._shot_delegate.apply_theme()
        if self._asset_req_delegate:
            self._asset_req_delegate.apply_theme()
        if self._console_bar:
            self._console_bar.apply_theme()
        if self._image_console:
            self._image_console.apply_theme()
        if self._video_console:
            self._video_console.apply_theme()
        self.viewport().update()
