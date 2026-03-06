"""
涛割 - 资产需求卡片系统
分镜拆分完成后，在分镜框左侧展开思维导图式的资产需求卡片。
包含：AssetSummaryCard → AssetCategoryCard → AssetRequirementCard
以及连线管理器 AssetConnectionManager。
"""

import math
import os
from typing import Optional, List, Dict, Callable

from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsItem,
    QGraphicsPathItem, QGraphicsScene, QStyleOptionGraphicsItem,
    QGraphicsProxyWidget, QLineEdit,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QFontMetrics, QRadialGradient, QPixmap,
)

from ui import theme
from ui.components.base_canvas_view import LOD_TEXT_MIN_PX, LOD_CARD_SIMPLIFY_ZOOM


# ── 类型标识颜色 ──
CATEGORY_COLORS = {
    'character':    QColor('#6495ED'),   # 蓝色
    'scene_bg':     QColor('#50c878'),   # 绿色
    'prop':         QColor('#a078dc'),   # 紫色
    'lighting_ref': QColor('#FFD700'),   # 金黄色
}

# ── 衍生形象颜色 ──
VARIANT_TYPE_COLORS = {
    'costume_variant':    QColor('#e8943a'),  # 橙色
    'age_variant':        QColor('#78b4e8'),  # 浅蓝
    'appearance_variant': QColor('#4ecdc4'),  # 青色
}

CATEGORY_LABELS = {
    'character':    '角色',
    'scene_bg':     '场景',
    'prop':         '道具',
    'lighting_ref': '照明',
}

CATEGORY_ICONS = {
    'character':    '\U0001F464',  # 👤
    'scene_bg':     '\U0001F3DE',  # 🏞️
    'prop':         '\U0001F528',  # 🔨
    'lighting_ref': '\U0001F4A1',  # 💡
}


# ============================================================
#  AssetRequirementCard — 单个资产需求卡
# ============================================================

class AssetRequirementCard(QGraphicsRectItem):
    """
    单个资产需求卡 — 显示角色/服装/场景/道具的详细信息。
    """

    CARD_WIDTH = 200
    CARD_HEIGHT = 160  # 基础高度，内容自适应
    CORNER_RADIUS = 10

    def __init__(self, req_data: dict, req_type: str,
                 on_generate: Optional[Callable] = None,
                 on_bind: Optional[Callable] = None,
                 on_ai_fill: Optional[Callable] = None,
                 on_multi_angle: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self._data = req_data
        self._type = req_type
        self._on_generate = on_generate
        self._on_bind = on_bind
        self._on_ai_fill = on_ai_fill
        self._on_multi_angle = on_multi_angle
        self._fulfilled = req_data.get('is_fulfilled', False)
        self._selected = False
        self._hovered = False
        self._plus_btn = None

        # AI 补全状态
        self._is_ai_filling = False
        self._ai_fill_hovered = False
        self._ai_fill_btn_rect = QRectF()

        # 多视角状态
        self._multi_angle_paths: list = []
        self._multi_angle_loading = False
        self._multi_angle_group: Optional['MultiAnglePreviewGroup'] = None

        # 变体卡根据 variant_type 选择颜色
        attrs = req_data.get('attributes', {})
        variant_type = attrs.get('variant_type', '')
        if attrs.get('is_variant') and variant_type:
            self._color = VARIANT_TYPE_COLORS.get(variant_type, QColor('#e8943a'))
        else:
            self._color = CATEGORY_COLORS.get(req_type, QColor('#888888'))

        # 计算高度
        self._computed_height = self._compute_height()

        self.setRect(0, 0, self.CARD_WIDTH, self._computed_height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(20)

        # 拖拽位置追踪
        self._drag_started = False
        self._last_drag_pos = QPointF()
        self._on_pos_changed: Optional[Callable] = None
        # 拖拽联动：主图 + 多视角缩略图 + 连线跟随移动
        self._linked_image_node = None   # ImagePreviewNode（场景级）
        self._linked_multi_angle = None  # MultiAnglePreviewGroup
        self._linked_connection = None   # ShotImageConnection（卡片→主图连线）

    @property
    def req_id(self) -> Optional[int]:
        return self._data.get('id')

    @property
    def req_type(self) -> str:
        return self._type

    @property
    def req_data(self) -> dict:
        return self._data

    def _compute_height(self) -> float:
        """根据内容计算卡片高度"""
        font = QFont("Microsoft YaHei", 9)
        fm = QFontMetrics(font)
        attrs = self._data.get('attributes', {})

        line_h = fm.height() + 4
        # 标题行 + 类型标签行 + 分隔线
        h = 40 + 22

        # 属性行数
        attr_lines = self._get_display_attrs()
        if attr_lines:
            h += len(attr_lines) * line_h
        elif self._data.get('source_text_excerpts') is not None and not attrs:
            # AI 补全过但无信息 — "无信息"占一行
            h += line_h

        # AI 补全按钮行（如果有回调且未完成）
        if self._on_ai_fill and not self._fulfilled:
            # 同步预计算按钮热区（不依赖 paint 调用）
            x = 15  # color_bar_width(5) + margin(10)
            btn_y = h + 2
            self._ai_fill_btn_rect = QRectF(x, btn_y, 70, 22)
            h += 28
        else:
            self._ai_fill_btn_rect = QRectF()

        # 多视角指示器行
        if self._multi_angle_paths or self._multi_angle_loading:
            h += 20

        # 底部出现场次 + 状态
        h += 30

        return max(self.CARD_HEIGHT, h)

    def _get_display_attrs(self) -> list:
        """获取要显示的属性行列表"""
        attrs = self._data.get('attributes', {})
        lines = []

        if self._type == 'character':
            # 衍生描述优先显示
            variant_desc = attrs.get('variant_description', '')
            if variant_desc:
                lines.append(f"衍生: {variant_desc}")
            # costume_variant 显示服装信息
            vtype = attrs.get('variant_type', '')
            if vtype == 'costume_variant':
                for k in ('clothing_style', 'clothing_color'):
                    v = attrs.get(k)
                    if v:
                        label = {'clothing_style': '服装样式', 'clothing_color': '颜色'}
                        lines.append(f"{label.get(k, k)}: {v}")
            # age_variant 优先显示年龄
            elif vtype == 'age_variant':
                for k in ('age', 'age_group'):
                    v = attrs.get(k)
                    if v:
                        label = {'age': '年龄', 'age_group': '年龄段'}
                        lines.append(f"{label.get(k, k)}: {v}")
            # 通用角色属性
            for k in ('gender', 'age', 'hairstyle', 'hair_color',
                       'body_type', 'role_tag'):
                v = attrs.get(k)
                if v:
                    label = {'gender': '性别', 'age': '年龄', 'hairstyle': '发型',
                             'hair_color': '发色', 'body_type': '体型',
                             'role_tag': '定位'}
                    line = f"{label.get(k, k)}: {v}"
                    if line not in lines:
                        lines.append(line)
            # Visual Anchors
            anchors = attrs.get('visual_anchors', [])
            if anchors:
                lines.append(f"锚点: {'、'.join(anchors[:3])}")
        elif self._type == 'scene_bg':
            for k in ('location', 'time_of_day', 'weather', 'mood', 'era'):
                v = attrs.get(k)
                if v:
                    label = {'location': '地点', 'time_of_day': '时间',
                             'weather': '天气', 'mood': '氛围', 'era': '时代'}
                    lines.append(f"{label.get(k, k)}: {v}")
        elif self._type == 'prop':
            for k in ('description', 'material', 'size', 'usage', 'owner'):
                v = attrs.get(k)
                if v:
                    label = {'description': '描述', 'material': '材质',
                             'size': '大小', 'usage': '用途', 'owner': '所属'}
                    lines.append(f"{label.get(k, k)}: {v}")
        elif self._type == 'lighting_ref':
            for k in ('light_source', 'color_temperature', 'direction',
                       'mood_effect', 'time_context'):
                v = attrs.get(k)
                if v:
                    label = {'light_source': '光源', 'color_temperature': '色温',
                             'direction': '方向', 'mood_effect': '情绪',
                             'time_context': '时间'}
                    lines.append(f"{label.get(k, k)}: {v}")

        return lines[:6]  # 最多显示 6 行

    def set_fulfilled(self, fulfilled: bool):
        self._fulfilled = fulfilled
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected and not self._plus_btn:
            self._plus_btn = AssetPlusButton(
                self, self._on_generate, self._on_bind, self._on_multi_angle
            )
            self._plus_btn.setParentItem(self)
            self._plus_btn.setPos(-36, self._computed_height / 2 - 14)
        elif not selected and self._plus_btn:
            if self._plus_btn.scene():
                self._plus_btn.scene().removeItem(self._plus_btn)
            self._plus_btn = None
        self.update()

    def set_ai_filling(self, filling: bool):
        """设置 AI 补全加载状态"""
        self._is_ai_filling = filling
        self.update()

    def set_multi_angle_paths(self, paths: list):
        """设置已下载的多视角图片路径"""
        self._multi_angle_paths = paths or []
        self._multi_angle_loading = False
        self._computed_height = self._compute_height()
        self.setRect(0, 0, self.CARD_WIDTH, self._computed_height)
        self.update()

    def set_multi_angle_group(self, group: Optional['MultiAnglePreviewGroup']):
        """设置多视角预览组引用"""
        self._multi_angle_group = group

    def set_multi_angle_loading(self, loading: bool):
        """设置多视角生成中的加载状态"""
        self._multi_angle_loading = loading
        self._computed_height = self._compute_height()
        self.setRect(0, 0, self.CARD_WIDTH, self._computed_height)
        self.update()

    def update_data(self, new_data: dict):
        """AI 补全后更新卡片数据并重算高度"""
        self._data = new_data
        self._fulfilled = new_data.get('is_fulfilled', False)
        self._computed_height = self._compute_height()
        self.setRect(0, 0, self.CARD_WIDTH, self._computed_height)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # LOD 极简模式
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(36, 36, 44) if theme.is_dark() else QColor(255, 255, 255)
            painter.fillRect(rect, bg)
            painter.fillRect(QRectF(0, 0, 5, rect.height()), self._color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = theme.is_dark()

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        bg = QColor(36, 36, 44) if dark else QColor(255, 255, 255)
        if self._hovered:
            bg = bg.lighter(115) if dark else bg.darker(105)
        painter.fillPath(bg_path, QBrush(bg))

        # 左侧颜色条
        bar = QPainterPath()
        bar.addRoundedRect(QRectF(0, 0, 5, rect.height()),
                           self.CORNER_RADIUS, self.CORNER_RADIUS)
        painter.fillPath(bar, QBrush(self._color))

        # 选中边框
        if self._selected:
            painter.setPen(QPen(self._color, 2))
            painter.drawPath(bg_path)

        # 完成覆盖
        if self._fulfilled:
            overlay = QPainterPath()
            overlay.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
            painter.fillPath(overlay, QBrush(QColor(0, 200, 80, 40)))
            # 对勾
            painter.setPen(QPen(QColor(0, 200, 80), 3))
            cx, cy = rect.width() - 24, 20
            painter.drawLine(QPointF(cx - 6, cy), QPointF(cx - 1, cy + 5))
            painter.drawLine(QPointF(cx - 1, cy + 5), QPointF(cx + 8, cy - 6))

        # ── LOD 文本优化 ──
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        # ── 内容绘制 ──
        text_color = QColor(230, 230, 230) if dark else QColor(40, 40, 40)
        sub_color = QColor(160, 160, 170) if dark else QColor(120, 120, 130)

        x = 14
        y = 12

        # 名称
        name_font = QFont("Microsoft YaHei", 11, QFont.Weight.Bold)
        painter.setFont(name_font)
        painter.setPen(QPen(text_color))
        name = self._data.get('name', '未命名')
        painter.drawText(QRectF(x, y, rect.width() - x - 10, 22),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         name)
        y += 26

        # 类型标签
        tag_font = QFont("Microsoft YaHei", 8)
        painter.setFont(tag_font)
        tag_text = CATEGORY_LABELS.get(self._type, self._type)
        tag_fm = QFontMetrics(tag_font)
        tw = tag_fm.horizontalAdvance(tag_text) + 12
        tag_rect = QRectF(x, y, tw, 16)
        tag_bg = QPainterPath()
        tag_bg.addRoundedRect(tag_rect, 4, 4)
        painter.fillPath(tag_bg, QBrush(QColor(self._color.red(),
                                                self._color.green(),
                                                self._color.blue(), 50)))
        painter.setPen(QPen(self._color))
        painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag_text)

        # 变体标签（如果是服装变体）
        variant_name = self._data.get('attributes', {}).get('variant_name', '')
        if variant_name:
            vt_text = f"变体: {variant_name}"
            vt_x = x + tw + 6
            vt_w = tag_fm.horizontalAdvance(vt_text) + 12
            vt_rect = QRectF(vt_x, y, vt_w, 16)
            vt_bg = QPainterPath()
            vt_bg.addRoundedRect(vt_rect, 4, 4)
            painter.fillPath(vt_bg, QBrush(QColor(232, 148, 58, 50)))
            painter.setPen(QPen(QColor('#e8943a')))
            painter.drawText(vt_rect, Qt.AlignmentFlag.AlignCenter, vt_text)

        y += 22

        # 分隔线
        painter.setPen(QPen(QColor(80, 80, 90) if dark else QColor(220, 220, 225), 1))
        painter.drawLine(QPointF(x, y), QPointF(rect.width() - 10, y))
        y += 8

        # 属性行
        attr_font = QFont("Microsoft YaHei", 9)
        painter.setFont(attr_font)
        attr_fm = QFontMetrics(attr_font)
        line_h = attr_fm.height() + 4

        for line in self._get_display_attrs():
            painter.setPen(QPen(sub_color))
            painter.drawText(QRectF(x, y, rect.width() - x - 10, line_h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             line)
            y += line_h

        # AI 补全过但无属性信息
        if not self._get_display_attrs() and \
                self._data.get('source_text_excerpts') is not None and \
                not self._data.get('attributes'):
            painter.setPen(QPen(QColor(140, 140, 150) if dark else QColor(160, 160, 170)))
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.drawText(QRectF(x, y, rect.width() - x - 10, line_h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             "无信息")
            y += line_h

        # AI 补全按钮（属性行之后）
        if self._on_ai_fill and not self._fulfilled:
            btn_w = 70
            btn_h = 22
            btn_x = x
            btn_y = y + 2
            self._ai_fill_btn_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

            btn_path = QPainterPath()
            btn_path.addRoundedRect(self._ai_fill_btn_rect, 4, 4)

            if self._is_ai_filling:
                painter.fillPath(btn_path, QBrush(QColor(91, 141, 239, 30)))
                painter.setPen(QPen(QColor(91, 141, 239, 150)))
                btn_font = QFont("Microsoft YaHei", 8)
                painter.setFont(btn_font)
                painter.drawText(self._ai_fill_btn_rect,
                                 Qt.AlignmentFlag.AlignCenter, "补全中...")
            else:
                if self._ai_fill_hovered:
                    painter.fillPath(btn_path, QBrush(QColor(91, 141, 239, 50)))
                else:
                    painter.fillPath(btn_path, QBrush(QColor(91, 141, 239, 25)))
                painter.setPen(QPen(QColor(91, 141, 239)))
                btn_font = QFont("Microsoft YaHei", 8)
                painter.setFont(btn_font)
                painter.drawText(self._ai_fill_btn_rect,
                                 Qt.AlignmentFlag.AlignCenter, "AI补全")

        # 多视角指示器
        if self._multi_angle_loading:
            painter.setPen(QPen(QColor(91, 141, 239, 180)))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(QRectF(x, y, rect.width() - x - 10, 16),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             "多视角生成中...")
            y += 20
        elif self._multi_angle_paths:
            # 卡内文字提示（缩略图由 MultiAnglePreviewGroup 在卡片左侧展开）
            painter.setPen(QPen(QColor(120, 120, 140) if dark else QColor(150, 150, 160)))
            painter.setFont(QFont("Microsoft YaHei", 8))
            hint = f"多视角×{len(self._multi_angle_paths)}"
            if not (self._multi_angle_group and self._multi_angle_group.is_expanded):
                hint += "（点击展开）"
            painter.drawText(QRectF(x, y, rect.width() - x - 10, 16),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             hint)
            y += 20

        # 底部出现场次
        y = rect.height() - 22
        scene_indices = self._data.get('scene_indices', [])
        if scene_indices:
            idx_font = QFont("Microsoft YaHei", 8)
            painter.setFont(idx_font)
            painter.setPen(QPen(QColor(120, 120, 140) if dark else QColor(150, 150, 160)))
            idx_text = f"出现: 分镜 {', '.join(str(i) for i in scene_indices[:5])}"
            if len(scene_indices) > 5:
                idx_text += f" +{len(scene_indices) - 5}"
            painter.drawText(QRectF(x, y, rect.width() - x - 10, 16),
                             Qt.AlignmentFlag.AlignLeft, idx_text)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self._ai_fill_hovered = False
        self.update()

    def hoverMoveEvent(self, event):
        old = self._ai_fill_hovered
        self._ai_fill_hovered = (
            not self._ai_fill_btn_rect.isNull()
            and self._ai_fill_btn_rect.contains(event.pos())
        )
        if old != self._ai_fill_hovered:
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击了 AI 补全按钮
            if (self._on_ai_fill
                    and not self._ai_fill_btn_rect.isNull()
                    and self._ai_fill_btn_rect.contains(event.pos())
                    and not self._is_ai_filling):
                self._on_ai_fill(self._data)
                event.accept()
                return
            self._drag_started = False
            self._last_drag_pos = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._drag_started = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_started and event.button() == Qt.MouseButton.LeftButton:
            self._drag_started = False
            # 拖拽结束 → 通知持久化位置
            if self._on_pos_changed:
                self._on_pos_changed(self)
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if (change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
                and self._drag_started):
            new_pos = value
            delta = new_pos - self._last_drag_pos
            self._last_drag_pos = QPointF(new_pos.x(), new_pos.y())
            # 联动：移动主图（场景级 item，delta 相同因为父 ZoneFrame 无缩放/旋转）
            if self._linked_image_node:
                img_pos = self._linked_image_node.pos()
                self._linked_image_node.setPos(
                    img_pos.x() + delta.x(), img_pos.y() + delta.y())
            # 联动：平移多视角缩略图（同在 ZoneFrame 本地坐标系）
            if self._linked_multi_angle:
                self._linked_multi_angle.shift_all(delta.x(), delta.y())
            # 联动：刷新卡片→主图连线路径
            if self._linked_connection:
                self._linked_connection.update_positions()
        return super().itemChange(change, value)


# ============================================================
#  AssetPlusButton — 需求卡左侧 + 号按钮
# ============================================================

class AssetPlusButton(QGraphicsEllipseItem):
    """需求卡左侧的 + 号按钮，点击弹出操作菜单"""

    RADIUS = 14

    def __init__(self, parent_card: AssetRequirementCard,
                 on_generate: Optional[Callable] = None,
                 on_bind: Optional[Callable] = None,
                 on_multi_angle: Optional[Callable] = None,
                 parent=None):
        super().__init__(-self.RADIUS, -self.RADIUS,
                         self.RADIUS * 2, self.RADIUS * 2, parent)
        self._parent_card = parent_card
        self._on_generate = on_generate
        self._on_bind = on_bind
        self._on_multi_angle = on_multi_angle
        self._hovered = False

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(100)

    def paint(self, painter: QPainter, option, widget=None):
        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            return  # 太小不画

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.RADIUS
        if self._hovered:
            r += 2

        color = CATEGORY_COLORS.get(self._parent_card.req_type, QColor('#5b8def'))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(0, 0), r, r)

        # 十字线
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(QPointF(-5, 0), QPointF(5, 0))
        painter.drawLine(QPointF(0, -5), QPointF(0, 5))

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 弹出操作菜单
            scene_pos = self.mapToScene(QPointF(0, 0))
            menu = AssetActionMenu(
                self._parent_card.req_data,
                self._on_generate,
                self._on_bind,
                scene_pos,
                on_multi_angle=self._on_multi_angle,
            )
            if self.scene():
                self.scene().addItem(menu)
                menu.setPos(scene_pos.x() - AssetActionMenu.MENU_WIDTH - 10,
                            scene_pos.y() - AssetActionMenu.MENU_HEIGHT / 2)
            event.accept()
        else:
            super().mousePressEvent(event)


# ============================================================
#  AssetActionMenu — 操作菜单
# ============================================================

class AssetActionMenu(QGraphicsRectItem):
    """操作菜单：生成图片 / 多视角生成 / 从资产库查找"""

    MENU_WIDTH = 300
    MENU_HEIGHT = 36

    def __init__(self, req_data: dict,
                 on_generate: Optional[Callable],
                 on_bind: Optional[Callable],
                 scene_pos: QPointF,
                 on_multi_angle: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self._req_data = req_data
        self._on_generate = on_generate
        self._on_bind = on_bind
        self._on_multi_angle = on_multi_angle

        # 多视角按钮仅在已有主图时可用
        self._multi_angle_enabled = bool(req_data.get('is_fulfilled'))

        self.setRect(0, 0, self.MENU_WIDTH, self.MENU_HEIGHT)
        self.setZValue(1000)
        self.setAcceptHoverEvents(True)

        # 5 秒超时自动消失
        self._timeout = QTimer()
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(5000)
        self._timeout.timeout.connect(self._auto_close)
        self._timeout.start()

        self._hover_idx = -1  # 0=生成图片, 1=多视角生成, 2=资产库查找

    def _auto_close(self):
        if self.scene():
            self.scene().removeItem(self)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(45, 45, 55) if dark else QColor(250, 250, 252)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, 8, 8)
        bg = QColor(45, 45, 55) if dark else QColor(250, 250, 252)
        painter.fillPath(bg_path, QBrush(bg))
        painter.setPen(QPen(QColor(80, 80, 90) if dark else QColor(200, 200, 210), 1))
        painter.drawPath(bg_path)

        # ── LOD 文本优化 ──
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        btn_w = self.MENU_WIDTH / 3
        font = QFont("Microsoft YaHei", 9, QFont.Weight.Bold)
        painter.setFont(font)

        # 按钮 0: 生成图片
        btn0_rect = QRectF(2, 2, btn_w - 2, self.MENU_HEIGHT - 4)
        if self._hover_idx == 0:
            p = QPainterPath()
            p.addRoundedRect(btn0_rect, 6, 6)
            painter.fillPath(p, QBrush(QColor(91, 141, 239, 40)))
        painter.setPen(QPen(QColor(91, 141, 239)))
        painter.drawText(btn0_rect, Qt.AlignmentFlag.AlignCenter, "生成图片")

        # 按钮 1: 多视角生成
        btn1_rect = QRectF(btn_w, 2, btn_w - 2, self.MENU_HEIGHT - 4)
        if self._multi_angle_enabled:
            if self._hover_idx == 1:
                p = QPainterPath()
                p.addRoundedRect(btn1_rect, 6, 6)
                painter.fillPath(p, QBrush(QColor(232, 148, 58, 40)))
            painter.setPen(QPen(QColor(232, 148, 58)))
        else:
            painter.setPen(QPen(QColor(100, 100, 110)))
        painter.drawText(btn1_rect, Qt.AlignmentFlag.AlignCenter, "多视角")

        # 按钮 2: 从资产库查找
        btn2_rect = QRectF(btn_w * 2, 2, btn_w - 2, self.MENU_HEIGHT - 4)
        if self._hover_idx == 2:
            p = QPainterPath()
            p.addRoundedRect(btn2_rect, 6, 6)
            painter.fillPath(p, QBrush(QColor(160, 160, 170, 40)))
        painter.setPen(QPen(QColor(160, 160, 170) if dark else QColor(100, 100, 110)))
        painter.drawText(btn2_rect, Qt.AlignmentFlag.AlignCenter, "资产库查找")

    def hoverMoveEvent(self, event):
        x = event.pos().x()
        btn_w = self.MENU_WIDTH / 3
        if x < btn_w:
            self._hover_idx = 0
        elif x < btn_w * 2:
            self._hover_idx = 1
        else:
            self._hover_idx = 2
        self.update()

    def hoverLeaveEvent(self, event):
        self._hover_idx = -1
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.pos().x()
            btn_w = self.MENU_WIDTH / 3
            if x < btn_w:
                if self._on_generate:
                    self._on_generate(self._req_data)
            elif x < btn_w * 2:
                if self._multi_angle_enabled and self._on_multi_angle:
                    self._on_multi_angle(self._req_data)
            else:
                if self._on_bind:
                    self._on_bind(self._req_data)
            self._timeout.stop()
            QTimer.singleShot(0, self._auto_close)
            event.accept()


# ============================================================
#  AssetCategoryCard — 分类卡片
# ============================================================

class AssetCategoryCard(QGraphicsRectItem):
    """分类卡片（角色/服装/场景/道具），可折叠子需求卡"""

    CARD_WIDTH = 140
    CARD_HEIGHT = 160
    CORNER_RADIUS = 10

    def __init__(self, category: str, items_count: int,
                 fulfilled_count: int, meta: Optional[dict] = None,
                 on_toggle: Optional[Callable] = None,
                 on_drag_release: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self._category = category
        self._items_count = items_count
        self._fulfilled_count = fulfilled_count
        self._meta = meta or {}
        self._on_toggle = on_toggle
        self._on_drag_release = on_drag_release
        self._expanded = True
        self._hovered = False

        # 拖拽交互
        self._is_dragging = False
        self._drag_start: Optional[QPointF] = None
        self._drag_line: Optional[QGraphicsPathItem] = None
        self._drag_threshold = 6

        self._color = CATEGORY_COLORS.get(category, QColor('#888888'))

        self.setRect(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setAcceptHoverEvents(True)
        self.setZValue(30)

    @property
    def category(self) -> str:
        return self._category

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def update_counts(self, items_count: int, fulfilled_count: int):
        self._items_count = items_count
        self._fulfilled_count = fulfilled_count
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # LOD 极简模式
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(40, 40, 50) if dark else QColor(252, 252, 255)
            painter.fillRect(rect, bg)
            painter.fillRect(QRectF(0, 0, rect.width(), 4), self._color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        bg = QColor(40, 40, 50) if dark else QColor(252, 252, 255)
        if self._hovered:
            bg = bg.lighter(115) if dark else bg.darker(105)
        painter.fillPath(bg_path, QBrush(bg))

        # 顶部颜色条
        top_bar = QPainterPath()
        top_bar.addRoundedRect(QRectF(0, 0, rect.width(), 6),
                               self.CORNER_RADIUS, self.CORNER_RADIUS)
        top_clip = QPainterPath()
        top_clip.addRect(QRectF(0, 0, rect.width(), 6))
        painter.fillPath(top_bar, QBrush(self._color))

        # ── LOD 文本优化 ──
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        text_color = QColor(230, 230, 230) if dark else QColor(40, 40, 40)
        sub_color = QColor(140, 140, 150) if dark else QColor(110, 110, 120)

        cx = rect.width() / 2
        y = 20

        # 类别名
        cat_font = QFont("Microsoft YaHei", 12, QFont.Weight.Bold)
        painter.setFont(cat_font)
        painter.setPen(QPen(text_color))
        label = CATEGORY_LABELS.get(self._category, self._category)
        painter.drawText(QRectF(0, y, rect.width(), 22),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                         label)
        y += 30

        # 数量
        count_font = QFont("Microsoft YaHei", 22, QFont.Weight.Bold)
        painter.setFont(count_font)
        painter.setPen(QPen(self._color))
        painter.drawText(QRectF(0, y, rect.width(), 32),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                         str(self._items_count))
        y += 36

        # 完成度
        small_font = QFont("Microsoft YaHei", 9)
        painter.setFont(small_font)
        painter.setPen(QPen(sub_color))
        painter.drawText(QRectF(0, y, rect.width(), 16),
                         Qt.AlignmentFlag.AlignHCenter,
                         f"已完成 {self._fulfilled_count}/{self._items_count}")
        y += 22

        # 进度条
        bar_w = rect.width() - 30
        bar_x = 15
        bar_h = 4
        # 背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(60, 60, 70) if dark else QColor(220, 220, 225)))
        painter.drawRoundedRect(QRectF(bar_x, y, bar_w, bar_h), 2, 2)
        # 填充
        if self._items_count > 0:
            fill_w = bar_w * self._fulfilled_count / self._items_count
            painter.setBrush(QBrush(self._color))
            painter.drawRoundedRect(QRectF(bar_x, y, fill_w, bar_h), 2, 2)
        y += 10

        # 折叠/展开指示
        arrow = '\u25BC' if self._expanded else '\u25B6'
        arrow_font = QFont("Microsoft YaHei", 8)
        painter.setFont(arrow_font)
        painter.setPen(QPen(sub_color))
        painter.drawText(QRectF(0, rect.height() - 18, rect.width(), 14),
                         Qt.AlignmentFlag.AlignHCenter, arrow)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.scenePos()
            self._is_dragging = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            scene_pos = event.scenePos()
            dist = (scene_pos - self._drag_start).manhattanLength()
            if dist > self._drag_threshold:
                self._is_dragging = True

            if self._is_dragging:
                # 清除旧拖拽线
                if self._drag_line and self._drag_line.scene():
                    self._drag_line.scene().removeItem(self._drag_line)
                    self._drag_line = None

                # 从卡片左侧中点画贝塞尔虚线到鼠标位置
                start = self.mapToScene(QPointF(0, self.rect().height() / 2))
                end = scene_pos
                path = QPainterPath()
                path.moveTo(start)
                dx = abs(end.x() - start.x()) * 0.5
                cp1 = QPointF(start.x() - dx, start.y())
                cp2 = QPointF(end.x() + dx, end.y())
                path.cubicTo(cp1, cp2, end)

                self._drag_line = QGraphicsPathItem()
                pen = QPen(self._color, 2.0)
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
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            # 清除拖拽线
            if self._drag_line and self._drag_line.scene():
                self._drag_line.scene().removeItem(self._drag_line)
                self._drag_line = None

            if self._is_dragging:
                # 拖拽释放 → 回调
                if self._on_drag_release:
                    self._on_drag_release(self._category, event.scenePos())
            else:
                # 短距离点击 → 原有 toggle 行为
                self._expanded = not self._expanded
                self.update()
                if self._on_toggle:
                    self._on_toggle(self._category, self._expanded)

            self._drag_start = None
            self._is_dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ============================================================
#  AssetSummaryCard — 资产需求总览卡
# ============================================================

# ============================================================
#  InlineNameInput — 鼠标释放位置的临时内联输入框
# ============================================================

class InlineNameInput(QGraphicsProxyWidget):
    """拖拽释放位置的内联输入框，输入名称后创建需求卡"""

    def __init__(self, category: str, scene_pos: QPointF,
                 on_confirm: Callable, on_cancel: Callable,
                 parent=None):
        super().__init__(parent)
        self._category = category
        self._scene_pos = scene_pos
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

        color = CATEGORY_COLORS.get(category, QColor('#888888'))
        label = CATEGORY_LABELS.get(category, category)

        line_edit = QLineEdit()
        line_edit.setFixedSize(200, 32)
        line_edit.setPlaceholderText(f"输入{label}名称...")
        line_edit.setStyleSheet(
            f"QLineEdit {{"
            f"  background: #2a2a34;"
            f"  color: #e0e0e0;"
            f"  border: 2px solid {color.name()};"
            f"  border-radius: 6px;"
            f"  padding: 2px 8px;"
            f"  font-size: 12px;"
            f"  font-family: 'Microsoft YaHei';"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border: 2px solid {color.lighter(130).name()};"
            f"}}"
        )
        line_edit.returnPressed.connect(self._handle_confirm)

        self.setWidget(line_edit)
        self.setZValue(2000)
        self.setPos(scene_pos)

        # 10 秒超时自动取消
        self._timeout = QTimer()
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(10000)
        self._timeout.timeout.connect(self._handle_cancel)
        self._timeout.start()

        # 延迟聚焦
        QTimer.singleShot(50, lambda: line_edit.setFocus())

    def _handle_confirm(self):
        self._timeout.stop()
        line_edit = self.widget()
        name = line_edit.text().strip() if line_edit else ''
        if name:
            self._on_confirm(self._category, name, self._scene_pos)
        self._remove_self()

    def _handle_cancel(self):
        self._timeout.stop()
        self._on_cancel()
        self._remove_self()

    def _remove_self(self):
        if self.scene():
            self.scene().removeItem(self)

    def keyPressEvent(self, event):
        from PyQt6.QtCore import Qt as _Qt
        if event.key() == _Qt.Key.Key_Escape:
            self._handle_cancel()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # 失焦时取消（延迟执行避免 returnPressed 和 focusOut 冲突）
        QTimer.singleShot(100, lambda: self._handle_cancel() if self.scene() else None)
        super().focusOutEvent(event)


# ============================================================

class AssetSummaryCard(QGraphicsRectItem):
    """资产需求总览卡（最右侧，紧挨分镜框）"""

    CARD_WIDTH = 120
    CARD_HEIGHT = 280
    CORNER_RADIUS = 12

    def __init__(self, stats: dict,
                 on_toggle_all: Optional[Callable] = None,
                 on_sync_to_library: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self._stats = stats
        self._on_toggle_all = on_toggle_all
        self._on_sync_to_library = on_sync_to_library
        self._expanded = True
        self._hovered = False
        self._sync_btn_rect = QRectF()  # 刷新按钮热区

        self.setRect(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setAcceptHoverEvents(True)
        self.setZValue(40)

    def update_stats(self, stats: dict):
        self._stats = stats
        self.update()

    def _is_all_fulfilled(self) -> bool:
        return self._stats.get('percentage', 0) >= 100 and self._stats.get('total', 0) > 0

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(42, 42, 52) if dark else QColor(250, 250, 253)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        bg = QColor(42, 42, 52) if dark else QColor(250, 250, 253)
        if self._hovered:
            bg = bg.lighter(115) if dark else bg.darker(105)
        painter.fillPath(bg_path, QBrush(bg))

        # 边框
        painter.setPen(QPen(QColor(70, 70, 85) if dark else QColor(210, 210, 220), 1))
        painter.drawPath(bg_path)

        # ── LOD 文本优化 ──
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        text_color = QColor(230, 230, 230) if dark else QColor(40, 40, 40)
        sub_color = QColor(140, 140, 155) if dark else QColor(110, 110, 120)

        cx = rect.width() / 2
        y = 14

        # 标题
        title_font = QFont("Microsoft YaHei", 10, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QPen(text_color))
        painter.drawText(QRectF(0, y, rect.width(), 18),
                         Qt.AlignmentFlag.AlignHCenter, "资产需求")
        y += 24

        # 圆形进度环
        pct = self._stats.get('percentage', 0)
        ring_r = 28
        ring_cx = cx
        ring_cy = y + ring_r + 2

        # 背景环
        painter.setPen(QPen(QColor(60, 60, 70) if dark else QColor(210, 210, 215), 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(ring_cx, ring_cy), ring_r, ring_r)

        # 进度环
        if pct > 0:
            arc_rect = QRectF(ring_cx - ring_r, ring_cy - ring_r,
                              ring_r * 2, ring_r * 2)
            painter.setPen(QPen(QColor(91, 141, 239), 4))
            span = int(pct / 100 * 360 * 16)
            painter.drawArc(arc_rect, 90 * 16, -span)

        # 百分比文字
        pct_font = QFont("Microsoft YaHei", 11, QFont.Weight.Bold)
        painter.setFont(pct_font)
        painter.setPen(QPen(text_color))
        painter.drawText(QRectF(ring_cx - ring_r, ring_cy - 8, ring_r * 2, 18),
                         Qt.AlignmentFlag.AlignCenter, f"{int(pct)}%")

        y = ring_cy + ring_r + 12

        # 统计行
        stat_font = QFont("Microsoft YaHei", 9)
        painter.setFont(stat_font)
        by_type = self._stats.get('by_type', {})
        for cat in ('character', 'scene_bg', 'prop', 'lighting_ref'):
            info = by_type.get(cat, {'total': 0, 'fulfilled': 0})
            if info['total'] == 0:
                continue
            color = CATEGORY_COLORS.get(cat, QColor('#888'))
            label = CATEGORY_LABELS.get(cat, cat)

            # 彩色圆点
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(14, y + 7), 4, 4)

            # 文本
            painter.setPen(QPen(sub_color))
            text = f"{label} {info['fulfilled']}/{info['total']}"
            painter.drawText(QRectF(24, y, rect.width() - 30, 16),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             text)
            y += 20

        # "刷新到资产库"按钮
        btn_w = rect.width() - 20
        btn_h = 24
        btn_x = 10
        btn_y = rect.height() - btn_h - 10
        self._sync_btn_rect = QRectF(btn_x, btn_y, btn_w, btn_h)

        btn_path = QPainterPath()
        btn_path.addRoundedRect(self._sync_btn_rect, 6, 6)

        if self._is_all_fulfilled():
            painter.fillPath(btn_path, QBrush(QColor(91, 141, 239)))
            painter.setPen(QPen(QColor(255, 255, 255)))
        else:
            painter.fillPath(btn_path, QBrush(QColor(60, 60, 70) if dark else QColor(220, 220, 225)))
            painter.setPen(QPen(QColor(120, 120, 130)))

        btn_font = QFont("Microsoft YaHei", 8)
        painter.setFont(btn_font)
        painter.drawText(self._sync_btn_rect, Qt.AlignmentFlag.AlignCenter, "刷新到资产库")

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            # 检查是否点击了"刷新到资产库"按钮
            if self._sync_btn_rect.contains(pos) and self._is_all_fulfilled():
                if self._on_sync_to_library:
                    self._on_sync_to_library()
                event.accept()
                return
            self._expanded = not self._expanded
            if self._on_toggle_all:
                self._on_toggle_all(self._expanded)
            event.accept()
        else:
            super().mousePressEvent(event)


# ============================================================
#  AssetConnectionManager — 资产需求连线管理器
# ============================================================

class AssetConnectionManager:
    """管理资产需求卡之间的思维导图连线"""

    def __init__(self, scene: QGraphicsScene, parent_item):
        self._scene = scene
        self._parent = parent_item
        self._lines: List[QGraphicsPathItem] = []
        self._category_expanded: Dict[str, bool] = {
            'character': True,
            'scene_bg': True,
            'prop': True,
            'lighting_ref': True,
        }

    def clear_all(self):
        for line in self._lines:
            if line.scene():
                line.scene().removeItem(line)
        self._lines.clear()

    def rebuild_connections(self, summary_card: Optional[AssetSummaryCard],
                            category_cards: Dict[str, AssetCategoryCard],
                            requirement_cards: Dict[str, List[AssetRequirementCard]]):
        """重建所有连线"""
        self.clear_all()

        if not summary_card:
            return

        summary_center = summary_card.mapToScene(
            QPointF(0, summary_card.rect().height() / 2)
        )

        for cat, cat_card in category_cards.items():
            # summary → category 连线
            cat_right = cat_card.mapToScene(
                QPointF(cat_card.rect().width(), cat_card.rect().height() / 2)
            )
            self._create_bezier_line(
                cat_right, summary_center,
                CATEGORY_COLORS.get(cat, QColor('#888')),
                solid=True,
            )

            # category → requirements 连线
            if self._category_expanded.get(cat, True):
                cat_left = cat_card.mapToScene(
                    QPointF(0, cat_card.rect().height() / 2)
                )
                req_cards = requirement_cards.get(cat, [])

                # 区分基础卡和衍生卡
                base_cards = []
                variant_map = {}  # {base_character_name: [variant_card, ...]}
                for rc in req_cards:
                    ra = rc.req_data.get('attributes', {})
                    if ra.get('is_variant') and ra.get('base_character_name'):
                        bn = ra['base_character_name']
                        variant_map.setdefault(bn, []).append(rc)
                    else:
                        base_cards.append(rc)

                for req_card in base_cards:
                    req_right = req_card.mapToScene(
                        QPointF(req_card.rect().width(),
                                req_card.rect().height() / 2)
                    )
                    self._create_bezier_line(
                        req_right, cat_left,
                        CATEGORY_COLORS.get(cat, QColor('#888')),
                        solid=False,
                    )

                # 基础角色卡 ← 衍生卡连线
                if cat == 'character':
                    self._create_variant_connections(base_cards, variant_map)

    def _create_variant_connections(self, base_cards, variant_map):
        """创建基础角色卡 ← 衍生卡的贝塞尔曲线连线"""
        for base_card in base_cards:
            base_name = base_card.req_data.get('name', '')
            variants = variant_map.get(base_name, [])
            if not variants:
                continue

            base_left = base_card.mapToScene(
                QPointF(0, base_card.rect().height() / 2)
            )
            for vc in variants:
                vc_right = vc.mapToScene(
                    QPointF(vc.rect().width(), vc.rect().height() / 2)
                )
                vtype = vc.req_data.get('attributes', {}).get('variant_type', '')
                color = VARIANT_TYPE_COLORS.get(vtype, QColor('#e8943a'))
                self._create_bezier_line(vc_right, base_left, color, solid=False)

    def _create_bezier_line(self, start: QPointF, end: QPointF,
                            color: QColor, solid: bool = True):
        """创建直线连接（从左到右 / 从右到左）"""
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)

        line = QGraphicsPathItem()
        pen = QPen(QColor(color.red(), color.green(), color.blue(), 120), 1.5)
        if not solid:
            pen.setStyle(Qt.PenStyle.DashLine)
        line.setPen(pen)
        line.setPath(path)
        line.setZValue(5)

        self._scene.addItem(line)
        self._lines.append(line)

    def toggle_category(self, category: str, expanded: bool):
        self._category_expanded[category] = expanded

    def toggle_all(self, expanded: bool):
        for cat in self._category_expanded:
            self._category_expanded[cat] = expanded

    def update_all(self):
        """外部调用：连线位置需要更新时重建"""
        # 连线位置基于 mapToScene，移动后需要 rebuild
        pass


# ============================================================
#  MultiAngleThumbnailNode — 多视角缩略图节点
# ============================================================

class MultiAngleThumbnailNode(QGraphicsRectItem):
    """轻量级多视角缩略图节点（90×60），懒加载图片。"""

    NODE_WIDTH = 90
    NODE_HEIGHT = 60
    CORNER_RADIUS = 6

    # 角度标签常量
    ANGLE_LABELS = ["正前", "正左", "正右", "正后", "上半身"]

    def __init__(self, index: int, image_path: str, parent_zone=None):
        super().__init__(parent_zone)
        self._index = index
        self._image_path = image_path
        self._pixmap: Optional[QPixmap] = None
        self._hovered = False
        self._angle_label: str = ""

        self.setRect(0, 0, self.NODE_WIDTH, self.NODE_HEIGHT)
        self.setAcceptHoverEvents(True)
        self.setZValue(22)

        # 自动设置角度标签
        if index < len(self.ANGLE_LABELS):
            self._angle_label = self.ANGLE_LABELS[index]

    def set_angle_label(self, label: str):
        self._angle_label = label
        self.update()

    def load_pixmap(self):
        """懒加载：展开时才加载图片到内存，横竖版自适应尺寸"""
        if not self._pixmap and self._image_path and os.path.isfile(self._image_path):
            self._pixmap = QPixmap(self._image_path)
            if self._pixmap and not self._pixmap.isNull():
                pw, ph = self._pixmap.width(), self._pixmap.height()
                if pw >= ph:
                    # 横版：宽度撑满，高度按比例
                    w = self.NODE_WIDTH
                    h = max(50, int(self.NODE_WIDTH * ph / pw))
                else:
                    # 竖版：高度撑满，宽度按比例
                    h = self.NODE_HEIGHT
                    w = max(50, int(self.NODE_HEIGHT * pw / ph))
                self.setRect(0, 0, w, h)

    def release_pixmap(self):
        """折叠时释放图片内存"""
        self._pixmap = None

    def set_image_path(self, path: str):
        """动态更新图片路径并重新加载"""
        self._image_path = path
        self._pixmap = None
        self.load_pixmap()
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()

        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # LOD 检查：缩放过小时跳过图片渲染，只画背景+边框
        from ui.components.base_canvas_view import LOD_IMAGE_MIN_PX
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        if _lod * rect.height() < LOD_IMAGE_MIN_PX:
            bg = QColor(36, 36, 44) if dark else QColor(245, 245, 248)
            painter.fillPath(bg_path, QBrush(bg))
            border_c = QColor(255, 255, 255, 30) if dark else QColor(0, 0, 0, 20)
            painter.setPen(QPen(border_c, 0.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(bg_path)
            return

        if self._pixmap and not self._pixmap.isNull():
            # fit-inside 显示（保持完整图片，不裁剪）
            painter.setClipPath(bg_path)
            pm = self._pixmap
            pw, ph = pm.width(), pm.height()
            rw, rh = rect.width(), rect.height()
            scale = min(rw / pw, rh / ph)
            sw, sh = pw * scale, ph * scale
            dx = (rw - sw) / 2
            dy = (rh - sh) / 2
            painter.drawPixmap(QRectF(dx, dy, sw, sh), pm,
                               QRectF(0, 0, pw, ph))
            painter.setClipping(False)

            # 底部角度标签叠加
            if self._angle_label:
                label_h = 16
                label_rect = QRectF(0, rect.height() - label_h, rect.width(), label_h)
                from PyQt6.QtGui import QLinearGradient
                grad = QLinearGradient(label_rect.topLeft(), label_rect.bottomLeft())
                grad.setColorAt(0, QColor(0, 0, 0, 100))
                grad.setColorAt(1, QColor(0, 0, 0, 160))
                painter.fillRect(label_rect, grad)
                painter.setPen(QColor(255, 255, 255, 210))
                painter.setFont(QFont("Microsoft YaHei", 7))
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._angle_label)

            # 选中高亮边框
            if self._hovered:
                painter.setPen(QPen(QColor(91, 141, 239), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(bg_path)
        else:
            # 灰色虚线边框 + 序号
            bg = QColor(36, 36, 44) if dark else QColor(245, 245, 248)
            painter.fillPath(bg_path, QBrush(bg))
            pen = QPen(QColor(80, 80, 90) if dark else QColor(200, 200, 210), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawPath(bg_path)

            # 序号 + 角度标签
            painter.setPen(QPen(QColor(100, 100, 120) if dark else QColor(160, 160, 170)))
            painter.setFont(QFont("Microsoft YaHei", 9))
            label = self._angle_label or str(self._index + 1)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap and not self._pixmap.isNull():
            from ui.components.image_preview_dialog import ImagePreviewDialog
            views = self.scene().views() if self.scene() else []
            if views:
                dlg = ImagePreviewDialog(self._pixmap, views[0])
                dlg.exec()
            event.accept()
            return
        super().mousePressEvent(event)


# ============================================================
#  MultiAngleFoldIndicator — 多视角折叠指示器
# ============================================================

class MultiAngleFoldIndicator(QGraphicsRectItem):
    """折叠态指示器（80×28 圆角药丸），显示"多视角×N"，点击展开。"""

    WIDTH = 80
    HEIGHT = 28

    def __init__(self, count: int, color: QColor,
                 on_click: Callable, parent_zone=None):
        super().__init__(parent_zone)
        self._count = count
        self._color = color
        self._on_click = on_click
        self._hovered = False

        self.setRect(0, 0, self.WIDTH, self.HEIGHT)
        self.setAcceptHoverEvents(True)
        self.setZValue(22)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(self._color.red(), self._color.green(),
                        self._color.blue(), 50)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = rect.height() / 2  # 药丸形圆角

        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, r, r)

        # 半透明 accent 色背景
        alpha = 80 if self._hovered else 50
        bg = QColor(self._color.red(), self._color.green(),
                    self._color.blue(), alpha)
        painter.fillPath(bg_path, QBrush(bg))

        # 边框
        painter.setPen(QPen(QColor(self._color.red(), self._color.green(),
                                   self._color.blue(), 140), 1))
        painter.drawPath(bg_path)

        # 文字
        painter.setPen(QPen(QColor(220, 220, 230)))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                         f"多视角×{self._count}")

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
            event.accept()
        else:
            super().mousePressEvent(event)

    def set_count(self, count: int):
        """更新显示的数量"""
        self._count = count
        self.update()


# ============================================================
#  MultiAnglePreviewGroup — 多视角缩略图水平排列 + 直线连线
# ============================================================

class MultiAnglePreviewGroup:
    """
    管理单张卡片的多视角缩略图，在卡片左侧水平排列。
    缩略图始终可见（无折叠/展开），使用直线连接到卡片。
    """

    THUMB_GAP = 16       # 缩略图之间间距
    CARD_THUMB_GAP = 40  # 卡片左边缘到最右缩略图的间距

    def __init__(self, scene: QGraphicsScene,
                 source_card: AssetRequirementCard,
                 paths: list, parent_zone):
        self._scene = scene
        self._source_card = source_card
        self._paths = paths
        self._parent_zone = parent_zone
        self._expanded = True  # 始终展开
        self._thumbnails: List[MultiAngleThumbnailNode] = []
        self._lines: List[QGraphicsPathItem] = []
        self._fold_indicator = None  # 保留属性以兼容旧代码
        self._image_node = None  # 关联的 ImagePreviewNode（缩略图从此节点左侧伸出）

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def set_image_node(self, node):
        """设置关联的 ImagePreviewNode，缩略图将从此节点左侧伸出"""
        self._image_node = node
        if self._expanded:
            self._position_thumbnails()
            self._remove_connection_lines()
            self._create_connection_lines()

    def build(self, paths: list):
        """创建缩略图节点（始终可见）+ 连线"""
        self._paths = paths

        # 为每个 path 创建缩略图节点
        for i, p in enumerate(paths):
            thumb = MultiAngleThumbnailNode(i, p, parent_zone=self._parent_zone)
            thumb.load_pixmap()
            thumb.setVisible(True)
            self._thumbnails.append(thumb)

        self._position_thumbnails()
        self._create_connection_lines()

    def expand(self):
        """兼容接口：显示缩略图 + 连线"""
        self._expanded = True
        for thumb in self._thumbnails:
            thumb.load_pixmap()
            thumb.setVisible(True)
        self._position_thumbnails()
        self._remove_connection_lines()
        self._create_connection_lines()

    def collapse(self):
        """兼容接口：隐藏缩略图 + 释放内存"""
        self._expanded = False
        for thumb in self._thumbnails:
            thumb.setVisible(False)
            thumb.release_pixmap()
        self._remove_connection_lines()

    def toggle(self):
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def update_positions(self):
        """卡片拖拽后更新缩略图和连线位置"""
        if self._expanded:
            self._position_thumbnails()
            self._remove_connection_lines()
            self._create_connection_lines()

    def shift_all(self, dx: float, dy: float):
        """拖拽过程中平移所有缩略图（不重建连线，提高性能）"""
        for thumb in self._thumbnails:
            p = thumb.pos()
            thumb.setPos(p.x() + dx, p.y() + dy)
        # 拖拽中移除连线（释放时 update_positions 重建）
        if self._lines:
            self._remove_connection_lines()

    def _position_thumbnails(self):
        """水平排列缩略图到卡片左侧"""
        positions = self._compute_horizontal_positions()
        for i, thumb in enumerate(self._thumbnails):
            if i < len(positions):
                thumb.setPos(positions[i])

    def _get_anchor_left_and_cy(self):
        """获取锚点的左边缘 X 和垂直中心 Y（ZoneFrame 本地坐标系）
        优先用 ImagePreviewNode（场景坐标→本地坐标），否则用卡片坐标。
        """
        if self._image_node and hasattr(self._image_node, 'pos') and self._parent_zone:
            # ImagePreviewNode 是场景级 item，需要转换到 ZoneFrame 本地坐标
            img_rect = self._image_node.rect()
            scene_tl = self._image_node.mapToScene(img_rect.topLeft())
            scene_bl = self._image_node.mapToScene(
                QPointF(img_rect.left(), img_rect.top() + img_rect.height() / 2))
            local_tl = self._parent_zone.mapFromScene(scene_tl)
            local_mid = self._parent_zone.mapFromScene(scene_bl)
            return local_tl.x(), local_mid.y()
        else:
            card_pos = self._source_card.pos()
            card_rect = self._source_card.rect()
            return card_pos.x(), card_pos.y() + card_rect.height() / 2

    def _compute_horizontal_positions(self) -> List[QPointF]:
        """计算水平排列的缩略图位置（从左到右，在锚点左侧）
        锚点优先级：ImagePreviewNode > AssetRequirementCard
        """
        anchor_left, anchor_cy = self._get_anchor_left_and_cy()

        # 计算所有缩略图的总宽度
        total_w = 0
        for i, thumb in enumerate(self._thumbnails):
            total_w += thumb.rect().width()
            if i > 0:
                total_w += self.THUMB_GAP

        # 从右到左排列：最右缩略图紧靠锚点左侧
        x = anchor_left - self.CARD_THUMB_GAP - total_w
        positions = []
        for thumb in self._thumbnails:
            th = thumb.rect().height()
            positions.append(QPointF(x, anchor_cy - th / 2))
            x += thumb.rect().width() + self.THUMB_GAP
        return positions

    def _create_connection_lines(self):
        """创建从锚点左边缘到每个缩略图右边缘的直线"""
        anchor_x, _ = self._get_anchor_left_and_cy()
        color = self._source_card._color

        for thumb in self._thumbnails:
            if not thumb.isVisible():
                continue
            tr = thumb.rect()
            thumb_right_x = thumb.pos().x() + tr.width()
            thumb_cy = thumb.pos().y() + tr.height() / 2

            # 缩略图右边缘中心 → 锚点左边缘（Y 对齐缩略图中心）
            start = QPointF(anchor_x, thumb_cy)
            end = QPointF(thumb_right_x, thumb_cy)

            path = QPainterPath()
            path.moveTo(start)
            path.lineTo(end)

            line = QGraphicsPathItem(self._parent_zone)
            pen = QPen(QColor(color.red(), color.green(),
                              color.blue(), 100), 1.2)
            line.setPen(pen)
            line.setPath(path)
            line.setZValue(15)
            self._lines.append(line)

    def _remove_connection_lines(self):
        for line in self._lines:
            if line.scene():
                line.scene().removeItem(line)
        self._lines.clear()

    def update_paths(self, new_paths: list):
        """路径更新（重新生成后）"""
        was_expanded = self._expanded
        self.clear()
        self._paths = new_paths
        self.build(new_paths)
        if not was_expanded:
            self.collapse()

    def update_single_path(self, angle_idx: int, path: str):
        """逐张更新单个角度的图片路径（生成过程中实时刷新）"""
        while len(self._paths) <= angle_idx:
            self._paths.append('')
        self._paths[angle_idx] = path

        if angle_idx < len(self._thumbnails):
            thumb = self._thumbnails[angle_idx]
            thumb.set_image_path(path)
            if self._expanded:
                thumb.setVisible(True)
        else:
            thumb = MultiAngleThumbnailNode(
                angle_idx, path, parent_zone=self._parent_zone
            )
            thumb.setVisible(self._expanded)
            if self._expanded:
                thumb.load_pixmap()
            self._thumbnails.append(thumb)

        # 重新定位和连线
        if self._expanded:
            self._position_thumbnails()
            self._remove_connection_lines()
            self._create_connection_lines()

    def clear(self):
        """清除所有场景项"""
        self._remove_connection_lines()
        for thumb in self._thumbnails:
            if thumb.scene():
                thumb.scene().removeItem(thumb)
        self._thumbnails.clear()
        if self._fold_indicator and hasattr(self._fold_indicator, 'scene') and self._fold_indicator.scene():
            self._fold_indicator.scene().removeItem(self._fold_indicator)
        self._fold_indicator = None
        self._expanded = True


# ============================================================
#  VariantLinkAnchor — 基础角色图片 → 变体卡拖拽锚点
# ============================================================

class VariantLinkAnchor(QGraphicsEllipseItem):
    """
    橙色拖拽锚点，附着在 ImagePreviewNode 底部中央。
    用户从此锚点向下拖拽到变体 AssetRequirementCard 上释放，
    即可建立"基础角色图 → 变体卡"的参考图连线。
    """

    RADIUS = 8
    HOVER_RADIUS = 10
    COLOR = QColor('#e8943a')

    def __init__(self, source_node, on_link_created=None, parent=None):
        super().__init__(parent)
        self._source_node = source_node
        self._on_link_created = on_link_created
        self._is_hovered = False
        self._is_dragging = False
        self._drag_start: Optional[QPointF] = None
        self._drag_line: Optional[QGraphicsPathItem] = None

        r = self.RADIUS
        # 定位在父节点底部中央
        from .shot_card_actions import ImagePreviewNode
        nw = ImagePreviewNode.NODE_WIDTH
        nh = ImagePreviewNode.NODE_HEIGHT
        self.setRect(nw / 2 - r, nh + 6 - r, r * 2, r * 2)

        self.setZValue(1600)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            return  # 太小不画

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = rect.center()

        r = self.HOVER_RADIUS if self._is_hovered else self.RADIUS

        # 圆圈
        if self._is_hovered:
            painter.setBrush(QBrush(QColor(self.COLOR.red(), self.COLOR.green(),
                                            self.COLOR.blue(), 60)))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self.COLOR, 2))
        painter.drawEllipse(center, r, r)

        # 中心链接图标 — 两个交叉小圆环
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(center.x() - 2.5, center.y()), 3.5, 3.5)
        painter.drawEllipse(QPointF(center.x() + 2.5, center.y()), 3.5, 3.5)

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()

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

            # 清除旧拖拽线
            if self._drag_line and self._drag_line.scene():
                self._drag_line.scene().removeItem(self._drag_line)
                self._drag_line = None

            # 绘制橙色虚线贝塞尔曲线
            path = QPainterPath()
            path.moveTo(start)
            dy = abs(scene_pos.y() - start.y())
            ctrl_offset = dy * 0.4
            path.cubicTo(
                QPointF(start.x(), start.y() + ctrl_offset),
                QPointF(scene_pos.x(), scene_pos.y() - ctrl_offset),
                scene_pos,
            )

            self._drag_line = QGraphicsPathItem()
            pen = QPen(self.COLOR, 2.0)
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
            release_pos = event.scenePos()

            # 清除拖拽线
            if self._drag_line and self._drag_line.scene():
                self._drag_line.scene().removeItem(self._drag_line)
                self._drag_line = None

            # 在释放位置查找目标 AssetRequirementCard
            if self.scene():
                items = self.scene().items(release_pos)
                target_card = None
                for it in items:
                    # 沿父链查找 AssetRequirementCard
                    check = it
                    while check:
                        if isinstance(check, AssetRequirementCard):
                            target_card = check
                            break
                        check = check.parentItem()
                    if target_card:
                        break

                if target_card:
                    # 验证：必须是角色类型 + 变体卡
                    rd = target_card.req_data
                    # 验证：目标必须是角色类型，且不是自己
                    is_valid = (
                        rd.get('requirement_type') == 'character'
                        and target_card is not self._source_node.parentItem()
                    )
                    if is_valid and self._on_link_created:
                        self._on_link_created(self._source_node, target_card)

            self._drag_start = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ============================================================
#  VariantLinkLine — 基础角色图 → 变体卡持久连线
# ============================================================

class VariantLinkLine:
    """
    管理基础角色 ImagePreviewNode → 变体 AssetRequirementCard 之间的
    橙色虚线贝塞尔曲线连线。定时刷新路径以跟随节点/卡片位置变化。
    """

    COLOR = QColor('#e8943a')

    def __init__(self, scene: QGraphicsScene,
                 source_node, target_card: AssetRequirementCard):
        self._scene = scene
        self._source_node = source_node
        self._target_card = target_card

        # 创建曲线
        self._curve = QGraphicsPathItem()
        pen = QPen(QColor(self.COLOR.red(), self.COLOR.green(),
                          self.COLOR.blue(), 160), 1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        self._curve.setPen(pen)
        self._curve.setZValue(15)
        self._scene.addItem(self._curve)

        # 定时器刷新路径
        self._timer = QTimer()
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.update_path)
        self._timer.start()

        self.update_path()

    def update_path(self):
        """根据 source_node 和 target_card 的当前位置更新曲线"""
        if not self._source_node.scene() or not self._target_card.scene():
            return

        from .shot_card_actions import ImagePreviewNode
        src_rect = self._source_node.mapRectToScene(self._source_node.rect())
        tgt_rect = self._target_card.mapRectToScene(self._target_card.rect())

        start = QPointF(src_rect.center().x(), src_rect.bottom())
        end = QPointF(tgt_rect.center().x(), tgt_rect.top())

        dy = abs(end.y() - start.y())
        ctrl_offset = dy * 0.4

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(
            QPointF(start.x(), start.y() + ctrl_offset),
            QPointF(end.x(), end.y() - ctrl_offset),
            end,
        )
        self._curve.setPath(path)

    def remove(self):
        """移除连线"""
        self._timer.stop()
        if self._curve.scene():
            self._scene.removeItem(self._curve)

    @property
    def source_image_path(self) -> str:
        """获取源节点的图片路径"""
        return getattr(self._source_node, '_image_path', '')

    @property
    def source_node(self):
        return self._source_node

    @property
    def target_card(self) -> AssetRequirementCard:
        return self._target_card
