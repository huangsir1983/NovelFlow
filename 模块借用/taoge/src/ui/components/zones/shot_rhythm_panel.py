"""
涛割 - 分镜节奏区（第二栏）— 无限画布模式
接收选中 Act 的 scenes 列表，在画布上显示分镜卡片
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu, QMessageBox,
    QGraphicsRectItem, QGraphicsItem, QGraphicsProxyWidget,
    QStyleOptionGraphicsItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QFontMetrics, QAction, QPixmap,
)

from ui import theme
from ui.components.base_canvas_view import BaseCanvasView, LOD_TEXT_MIN_PX, LOD_CARD_SIMPLIFY_ZOOM


# ============================================================
#  CollapsedShotCard — 折叠后的分镜组摘要卡片
# ============================================================

class CollapsedShotCard(QGraphicsRectItem):
    """
    折叠后显示的单张摘要卡片。
    显示场次标题、分镜数量、总时长。
    高度与 ShotCanvasCard 一致，底部可连线到分支节点。
    """

    CARD_WIDTH = 200
    CARD_HEIGHT = 200
    CORNER_RADIUS = 12

    def __init__(self, act_id: int, act_title: str, shot_count: int,
                 total_duration: float, color: QColor, parent=None):
        super().__init__(parent)
        self._act_id = act_id
        self._title = act_title
        self._shot_count = shot_count
        self._total_duration = total_duration
        self._color = color

        self.setRect(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    @property
    def act_id(self) -> int:
        return self._act_id

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # LOD 极简模式
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            from ui import theme as _th
            bg = QColor(42, 42, 48) if _th.is_dark() else QColor(250, 250, 255)
            painter.fillRect(rect, bg)
            painter.fillRect(QRectF(0, 0, 3, rect.height()), self._color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 底部微投影
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(rect.adjusted(1, 2, -1, 2),
                                   self.CORNER_RADIUS, self.CORNER_RADIUS)
        from ui import theme
        shadow_c = QColor(0, 0, 0, 20) if theme.is_dark() else QColor(0, 0, 0, 8)
        painter.fillPath(shadow_path, QBrush(shadow_c))

        # 背景
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        if theme.is_dark():
            bg = QColor(42, 42, 48)
        else:
            bg = QColor(250, 250, 255)
        painter.fillPath(card_path, QBrush(bg))

        # 超细边框
        border_c = QColor(self._color.red(), self._color.green(),
                          self._color.blue(), 60)
        painter.setPen(QPen(border_c, 1))
        painter.drawPath(card_path)

        # 左侧颜色条
        bar_path = QPainterPath()
        bar_rect = QRectF(2, 6, 3, rect.height() - 12)
        bar_path.addRoundedRect(bar_rect, 1.5, 1.5)
        painter.fillPath(bar_path, QBrush(self._color))

        content_w = rect.width() - 24
        y = 16

        # 折叠图标（居中 + 号）
        icon_cx = rect.width() / 2
        icon_cy = y + 6
        icon_c = QColor(self._color.red(), self._color.green(),
                        self._color.blue(), 180)
        painter.setPen(QPen(icon_c, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(icon_cx - 6, icon_cy), QPointF(icon_cx + 6, icon_cy))
        painter.drawLine(QPointF(icon_cx, icon_cy - 6), QPointF(icon_cx, icon_cy + 6))
        y += 24

        # LOD 文本隐藏
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        # 标题
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.DemiBold))
        painter.setPen(QPen(QColor(theme.text_primary())))
        title_rect = QRectF(12, y, content_w, 40)
        fm = QFontMetrics(painter.font())
        elided = fm.elidedText(self._title, Qt.TextElideMode.ElideRight,
                               int(content_w))
        painter.drawText(title_rect,
                         Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                         elided)
        y += 40

        # 分隔线
        sep_y = y
        line_c = QColor(self._color.red(), self._color.green(),
                        self._color.blue(), 40)
        painter.setPen(QPen(line_c, 1))
        painter.drawLine(QPointF(16, sep_y), QPointF(rect.width() - 16, sep_y))
        y += 12

        # 分镜数量
        painter.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        num_c = QColor(self._color.red(), self._color.green(),
                       self._color.blue(), 220)
        painter.setPen(QPen(num_c))
        painter.drawText(QRectF(12, y, content_w, 32),
                         Qt.AlignmentFlag.AlignCenter,
                         str(self._shot_count))
        y += 32

        # "个分镜" 标签
        painter.setFont(QFont("Microsoft YaHei", 9))
        info_c = QColor(theme.text_tertiary())
        info_c.setAlpha(160)
        painter.setPen(QPen(info_c))
        painter.drawText(QRectF(12, y, content_w, 18),
                         Qt.AlignmentFlag.AlignCenter,
                         "个分镜")
        y += 24

        # 总时长
        painter.setFont(QFont("Consolas", 11))
        painter.setPen(QPen(info_c))
        painter.drawText(QRectF(12, y, content_w, 20),
                         Qt.AlignmentFlag.AlignCenter,
                         f"{self._total_duration:.0f}s")


# ============================================================
#  ActSectionHeader — 场次分隔标题
# ============================================================

class ActSectionHeader(QGraphicsRectItem):
    """分镜区中的场次分隔标题栏，纯 QPainter 绘制"""

    HEADER_HEIGHT = 28

    def __init__(self, act_index: int, title: str, color: QColor, parent=None):
        super().__init__(parent)
        self.act_index = act_index
        self._title = title
        self._color = color
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # LOD 极简模式
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            painter.fillRect(QRectF(0, 0, 4, rect.height()), self._color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 左侧颜色条
        bar_rect = QRectF(0, 2, 4, rect.height() - 4)
        bar_path = QPainterPath()
        bar_path.addRoundedRect(bar_rect, 2, 2)
        painter.fillPath(bar_path, QBrush(self._color))

        # LOD 文本隐藏
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        # 场次序号
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        painter.setPen(QPen(self._color))
        painter.drawText(QRectF(10, 0, 40, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         f"#{self.act_index + 1:02d}")

        # 标题文本
        painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(theme.text_secondary())))
        fm = QFontMetrics(painter.font())
        elided = fm.elidedText(self._title, Qt.TextElideMode.ElideRight,
                               int(rect.width() - 60))
        painter.drawText(QRectF(48, 0, rect.width() - 58, rect.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         elided)

        # 底部分隔线
        painter.setPen(QPen(QColor(theme.separator()), 0.5))
        painter.drawLine(QPointF(0, rect.height() - 1),
                         QPointF(rect.width(), rect.height() - 1))


# ============================================================
#  ShotCanvasCard — 分镜卡片
# ============================================================

class ShotCanvasCard(QGraphicsRectItem):
    """
    分镜卡片 — 画布上的单个分镜，可选中不可拖拽。
    支持显示导演视觉指令（visual_description, camera_movement, action_reference, asset_needs, dialogue）。
    支持 act_color 场景颜色标记（左侧竖条）。
    """

    CARD_WIDTH = 200
    CARD_HEIGHT = 280
    COMPACT_HEIGHT = 200
    CORNER_RADIUS = 12

    # 状态颜色映射
    STATUS_COLORS = {
        'pending': '#636366',
        'image_generated': '#00966a',
        'video_generated': '#4caf50',
        'completed': '#30d158',
        'failed': '#ff453a',
    }

    def __init__(self, scene_data: dict, local_index: int, parent=None):
        super().__init__(parent)
        self.scene_data = scene_data
        self.scene_id = scene_data.get('id', 0)
        self.global_index = scene_data.get('scene_index', 0)
        self.local_index = local_index
        self._selected = False
        self._act_color: Optional[QColor] = None  # 场景颜色标记
        self._plus_button = None  # ShotCardPlusButton（选中时创建）
        self._on_generate_image = None  # 生成图片回调
        self._on_generate_video = None  # 生成视频回调
        self._on_smart_ps = None        # 智能PS回调

        # 内容滚动状态（选中时可滚轮翻页）
        self._scroll_offset: float = 0.0  # 像素偏移
        self._scroll_max: float = 0.0     # 最大可滚动像素

        # 检测是否有富数据（导演指令字段）
        self._has_rich_data = bool(scene_data.get('image_prompt'))

        # 无富数据时使用紧凑高度
        height = self.CARD_HEIGHT if self._has_rich_data else self.COMPACT_HEIGHT
        self.setRect(0, 0, self.CARD_WIDTH, height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)

    def set_act_color(self, color: Optional[QColor]):
        """设置场景颜色标记"""
        self._act_color = color
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        # 取消选中时重置滚动偏移
        if not selected:
            self._scroll_offset = 0.0
        # + 号按钮：选中时显示，取消选中时移除
        if selected and not self._plus_button:
            from .shot_card_actions import ShotCardPlusButton
            self._plus_button = ShotCardPlusButton(
                self.global_index,
                on_generate_image=self._on_generate_image,
                on_generate_video=self._on_generate_video,
                on_smart_ps=self._on_smart_ps,
                parent=self,
            )
        elif not selected and self._plus_button:
            if self._plus_button.scene():
                self._plus_button.scene().removeItem(self._plus_button)
            self._plus_button = None
        self.update()

    def boundingRect(self) -> QRectF:
        r = self.rect()
        return QRectF(r.x(), r.y() - 22, r.width(), r.height() + 22)

    @property
    def is_scrollable(self) -> bool:
        """内容是否可以滚动"""
        return self._scroll_max > 0

    def scroll_content(self, delta_pixels: float):
        """滚动内容（正=向下翻页看更多，负=向上回翻）"""
        if self._scroll_max <= 0:
            return
        old = self._scroll_offset
        self._scroll_offset = max(0.0, min(self._scroll_max, self._scroll_offset + delta_pixels))
        if self._scroll_offset != old:
            self.update()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # LOD 极简模式
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(40, 40, 44) if theme.is_dark() else QColor(255, 255, 255)
            painter.fillRect(rect, bg)
            if self._act_color:
                painter.fillRect(QRectF(0, 0, 3, rect.height()), self._act_color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        content_w = rect.width() - 24  # 12px 左右边距

        # LOD 文本隐藏
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        # 外部标签"分镜卡片"
        if not _hide_text:
            label_font = QFont("Microsoft YaHei", 9)
            painter.setFont(label_font)
            painter.setPen(QColor(theme.text_tertiary()))
            painter.drawText(
                QRectF(4, -18, 200, 16),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                "分镜卡片"
            )

        # Apple 风格底部微投影
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(rect.adjusted(1, 2, -1, 2),
                                   self.CORNER_RADIUS, self.CORNER_RADIUS)
        shadow_c = QColor(0, 0, 0, 22) if theme.is_dark() else QColor(0, 0, 0, 10)
        painter.fillPath(shadow_path, QBrush(shadow_c))

        # 卡片背景
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        if theme.is_dark():
            bg = QColor(40, 40, 44) if not self._selected else QColor(48, 48, 56)
        else:
            bg = QColor(255, 255, 255) if not self._selected else QColor(242, 246, 255)
        painter.fillPath(card_path, QBrush(bg))

        # 边框 — Apple 超细
        if self._selected:
            painter.setPen(QPen(QColor(theme.accent()), 1.5))
        else:
            border_c = QColor(theme.border())
            border_c.setAlpha(40 if theme.is_dark() else 60)
            painter.setPen(QPen(border_c, 0.5))
        painter.drawPath(card_path)

        # 左侧场景颜色竖条（Apple 胶囊）
        if self._act_color:
            bar_path = QPainterPath()
            bar_rect = QRectF(2, 8, 3, rect.height() - 16)
            bar_path.addRoundedRect(bar_rect, 1.5, 1.5)
            painter.fillPath(bar_path, QBrush(self._act_color))

        if _hide_text:
            return

        # ── 顶行：序号 + 时长 ──
        y_cur = 12
        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QPen(QColor(theme.text_tertiary())))
        painter.drawText(QRectF(12, y_cur, 40, 16),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         f"{self.local_index + 1:02d}")

        duration = self.scene_data.get('duration', 0)
        painter.setFont(QFont("Consolas", 8))
        dur_c = QColor(theme.text_tertiary())
        dur_c.setAlpha(160)
        painter.setPen(QPen(dur_c))
        painter.drawText(QRectF(rect.width() - 48, y_cur, 38, 16),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                         f"{duration:.1f}s")
        y_cur += 20

        # ── 运镜标签行（Apple 胶囊标签） ──
        camera_motion = self.scene_data.get('camera_motion', '')
        shot_label = self.scene_data.get('shot_label', '')
        tag_text = camera_motion if (camera_motion and camera_motion != '静止') else shot_label
        if tag_text:
            tag_text = tag_text[:8]
            painter.setFont(QFont("Microsoft YaHei", 8))
            fm_tag = QFontMetrics(painter.font())
            tw = min(fm_tag.horizontalAdvance(tag_text) + 12, int(content_w))
            tag_rect = QRectF(12, y_cur, tw, 18)
            tag_path_item = QPainterPath()
            tag_path_item.addRoundedRect(tag_rect, 9, 9)  # 全圆角胶囊
            if theme.is_dark():
                painter.fillPath(tag_path_item, QBrush(QColor(90, 70, 140, 80)))
                painter.setPen(QPen(QColor("#c4b5fd")))
            else:
                painter.fillPath(tag_path_item, QBrush(QColor(237, 233, 254)))
                painter.setPen(QPen(QColor("#6d28d9")))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag_text)
            y_cur += 22
        else:
            y_cur += 4

        # ── 场景环境标签（绿色胶囊） ──
        scene_env = self.scene_data.get('scene_environment', '')
        is_empty = self.scene_data.get('is_empty_shot', False)
        env_label = "空镜" if is_empty else scene_env[:12] if scene_env else ''
        if env_label:
            painter.setFont(QFont("Microsoft YaHei", 8))
            fm_env = QFontMetrics(painter.font())
            ew = min(fm_env.horizontalAdvance(env_label) + 12, int(content_w))
            env_rect = QRectF(12, y_cur, ew, 18)
            env_path = QPainterPath()
            env_path.addRoundedRect(env_rect, 9, 9)
            if theme.is_dark():
                painter.fillPath(env_path, QBrush(QColor(30, 80, 50, 80)))
                painter.setPen(QPen(QColor("#6ee7b7")))
            else:
                painter.fillPath(env_path, QBrush(QColor(220, 252, 231)))
                painter.setPen(QPen(QColor("#059669")))
            painter.drawText(env_rect, Qt.AlignmentFlag.AlignCenter, env_label)
            y_cur += 20

        # ── 角色胶囊行（蓝色胶囊，有台词的角色带橙色圆点） ──
        characters = self.scene_data.get('characters') or []
        if not characters:
            ca = self.scene_data.get('character_actions')
            if isinstance(ca, list):
                characters = ca
        if characters:
            painter.setFont(QFont("Microsoft YaHei", 7))
            char_x = 12
            for ch in characters[:3]:
                ch_name = (ch.get('name') or ch.get('character', ''))[:6]
                if not ch_name:
                    continue
                has_dial = bool(ch.get('dialogue'))
                fm_ch = QFontMetrics(painter.font())
                dot_space = 8 if has_dial else 0
                cw = fm_ch.horizontalAdvance(ch_name) + 12 + dot_space
                if char_x + cw > rect.width() - 12:
                    break
                ch_rect = QRectF(char_x, y_cur, cw, 18)
                ch_path = QPainterPath()
                ch_path.addRoundedRect(ch_rect, 9, 9)
                if theme.is_dark():
                    painter.fillPath(ch_path, QBrush(QColor(30, 50, 85, 80)))
                    painter.setPen(QPen(QColor("#93c5fd")))
                else:
                    painter.fillPath(ch_path, QBrush(QColor(219, 234, 254)))
                    painter.setPen(QPen(QColor("#2563eb")))
                text_x = char_x + 6
                if has_dial:
                    # 橙色圆点标记有台词
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(QColor("#ff9f0a")))
                    painter.drawEllipse(QPointF(char_x + 8, y_cur + 9), 3, 3)
                    text_x = char_x + 14
                    if theme.is_dark():
                        painter.setPen(QPen(QColor("#93c5fd")))
                    else:
                        painter.setPen(QPen(QColor("#2563eb")))
                painter.drawText(QRectF(text_x, y_cur, cw - (text_x - char_x) - 4, 18),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 ch_name)
                char_x += cw + 4
            y_cur += 20

        # ── 角色→服装关联行（橙色胶囊） ──
        y_cur = self._paint_asset_slots(painter, y_cur, content_w, rect)

        # ── 分隔线 ──
        sep_c = QColor(theme.separator())
        sep_c.setAlpha(40)
        painter.setPen(QPen(sep_c, 0.5))
        painter.drawLine(QPointF(12, y_cur), QPointF(rect.width() - 12, y_cur))
        y_cur += 8

        # ── 滚动内容区 ──
        # 可滚动区域：从 y_cur 到 rect.height() - 12（状态条上方）
        scroll_area_top = y_cur
        scroll_area_bottom = rect.height() - 12
        scroll_area_h = max(20, scroll_area_bottom - scroll_area_top)

        # 计算全部内容所需高度
        total_content_h = self._measure_content_height(content_w)
        self._scroll_max = max(0.0, total_content_h - scroll_area_h)

        # 裁剪到滚动区域并应用滚动偏移
        painter.save()
        clip_rect = QRectF(0, scroll_area_top, rect.width(), scroll_area_h)
        painter.setClipRect(clip_rect)
        painter.translate(0, -self._scroll_offset)

        # 从 scroll_area_top 开始绘制全部内容
        cy = scroll_area_top

        if self._has_rich_data:
            # 画面提示词
            visual_desc = self.scene_data.get('image_prompt', '')
            if visual_desc:
                painter.setFont(QFont("Microsoft YaHei", 9))
                painter.setPen(QPen(QColor(theme.text_primary())))
                fm_main = QFontMetrics(painter.font())
                text_br = fm_main.boundingRect(
                    0, 0, int(content_w), 0,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap,
                    visual_desc,
                )
                text_h = text_br.height()
                painter.drawText(QRectF(12, cy, content_w, text_h),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                                 | Qt.TextFlag.TextWordWrap,
                                 visual_desc)
                cy += text_h + 8

            # 动作参考
            action_ref = self.scene_data.get('action_reference', '')
            if not action_ref:
                vps = self.scene_data.get('visual_prompt_struct')
                if isinstance(vps, dict):
                    action_ref = vps.get('action', '')
            if action_ref:
                painter.setFont(QFont("Microsoft YaHei", 8))
                dim_color = QColor(theme.text_tertiary())
                dim_color.setAlpha(160)
                painter.setPen(QPen(dim_color))
                fm_small = QFontMetrics(painter.font())
                action_text = fm_small.elidedText("▸ " + action_ref,
                                                   Qt.TextElideMode.ElideRight,
                                                   int(content_w))
                painter.drawText(QRectF(12, cy, content_w, 16),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 action_text)
                cy += 20

            # 台词（多角色分行显示）
            _chars_for_dial = self.scene_data.get('characters') or []
            if not _chars_for_dial:
                ca = self.scene_data.get('character_actions')
                if isinstance(ca, list):
                    _chars_for_dial = ca
            _has_char_dialogue = False
            if _chars_for_dial:
                painter.setFont(QFont("Microsoft YaHei", 8))
                for ch in _chars_for_dial:
                    ch_dial = ch.get('dialogue', '')
                    if not ch_dial:
                        continue
                    _has_char_dialogue = True
                    ch_name = ch.get('name') or ch.get('character', '')
                    ch_expr = ch.get('dialogue_expression', '')
                    dial_line = f"{ch_name}：「{ch_dial}」"
                    if ch_expr:
                        dial_line += f"（{ch_expr}）"
                    painter.setPen(QPen(QColor("#ff9f0a")))
                    fm_dial = QFontMetrics(painter.font())
                    dial_text = fm_dial.elidedText(dial_line,
                                                     Qt.TextElideMode.ElideRight,
                                                     int(content_w))
                    painter.drawText(QRectF(12, cy, content_w, 16),
                                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                     dial_text)
                    cy += 18

            # 回退：无 characters 台词时用旧的 dialogue 字段
            if not _has_char_dialogue:
                dialogue = self.scene_data.get('dialogue', '')
                if not dialogue:
                    ac = self.scene_data.get('audio_config')
                    if isinstance(ac, dict):
                        dialogue = ac.get('dialogue', '')
                if dialogue:
                    painter.setFont(QFont("Microsoft YaHei", 8))
                    painter.setPen(QPen(QColor("#ff9f0a")))
                    fm_small = QFontMetrics(painter.font())
                    dial_text = fm_small.elidedText(dialogue,
                                                     Qt.TextElideMode.ElideRight,
                                                     int(content_w))
                    painter.drawText(QRectF(12, cy, content_w, 16),
                                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                     dial_text)
                    cy += 20
        else:
            text = self.scene_data.get('subtitle_text', '')
            if text:
                painter.setFont(QFont("Microsoft YaHei", 9))
                painter.setPen(QPen(QColor(theme.text_primary())))
                fm_main = QFontMetrics(painter.font())
                text_br = fm_main.boundingRect(
                    0, 0, int(content_w), 0,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap,
                    text,
                )
                text_h = text_br.height()
                painter.drawText(QRectF(12, cy, content_w, text_h),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                                 | Qt.TextFlag.TextWordWrap,
                                 text)
                cy += text_h + 8

        # 资产标签行（Apple 胶囊风格 — 支持 asset_needs 和 bound_assets）
        asset_needs = self.scene_data.get('asset_needs') or []
        if not asset_needs:
            gp = self.scene_data.get('generation_params')
            if isinstance(gp, dict):
                asset_needs = gp.get('asset_needs', [])

        # bound_assets 绑定的资产（优先显示）
        bound_assets = self.scene_data.get('bound_assets') or []
        _BOUND_TYPE_COLORS = {
            'character': ('#5b8def', '#1a3755'),
            'scene_bg': ('#5bb874', '#1a3d28'),
            'prop': ('#b07fe8', '#2d1a4a'),
            'lighting_ref': ('#f0c040', '#3d3510'),
        }

        if bound_assets:
            cy += 4
            painter.setFont(QFont("Microsoft YaHei", 7))

            # ── 分组：将衍生形象按 owner 关联到基础角色 ──
            char_map = {}  # {角色name: {'char': binding, 'variants': []}}
            standalone = []  # 无 owner 的资产
            for ba in bound_assets:
                ba_type = ba.get('type', '')
                ba_owner = ba.get('owner', '')
                variant_type = ba.get('variant_type', '')
                if ba_type == 'character' and not variant_type:
                    char_name = ba.get('name', '')
                    if char_name not in char_map:
                        char_map[char_name] = {'char': ba, 'variants': []}
                    else:
                        char_map[char_name]['char'] = ba
                elif ba_type == 'character' and variant_type and ba_owner:
                    if ba_owner not in char_map:
                        char_map[ba_owner] = {'char': None, 'variants': []}
                    char_map[ba_owner]['variants'].append(ba)
                else:
                    standalone.append(ba)

            # ── 渲染角色-衍生对（每对一行） ──
            THUMB_SIZE = 16
            for char_name, group in char_map.items():
                tag_x = 12
                char_ba = group['char']

                # 角色缩略图或胶囊标签
                char_img = char_ba.get('image_path', '') if char_ba else ''
                char_label = str(char_ba.get('name', char_name) if char_ba else char_name)[:6]
                if char_img:
                    pix = QPixmap(char_img)
                    if not pix.isNull():
                        pix = pix.scaled(THUMB_SIZE, THUMB_SIZE,
                                         Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
                        draw_x = tag_x + (THUMB_SIZE - pix.width()) // 2
                        draw_y = int(cy) + (THUMB_SIZE - pix.height()) // 2
                        painter.drawPixmap(draw_x, draw_y, pix)
                        tag_x += THUMB_SIZE + 2
                    else:
                        tag_x = self._draw_capsule_tag(
                            painter, tag_x, cy, char_label,
                            '#5b8def', '#1a3755', rect.width())
                else:
                    tag_x = self._draw_capsule_tag(
                        painter, tag_x, cy, char_label,
                        '#5b8def', '#1a3755', rect.width())

                # "衍生" 文字（如果有衍生形象）
                if group['variants']:
                    fm_wear = QFontMetrics(painter.font())
                    wear_text = "衍生"
                    wear_w = fm_wear.horizontalAdvance(wear_text) + 4
                    painter.setPen(QPen(QColor(theme.text_tertiary())))
                    painter.drawText(QRectF(tag_x, cy, wear_w, THUMB_SIZE),
                                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                     wear_text)
                    tag_x += wear_w

                    # 第一个衍生形象缩略图或胶囊标签
                    var_ba = group['variants'][0]
                    var_img = var_ba.get('image_path', '')
                    var_label = str(var_ba.get('name', ''))[:6]
                    if var_img:
                        pix = QPixmap(var_img)
                        if not pix.isNull():
                            pix = pix.scaled(THUMB_SIZE, THUMB_SIZE,
                                             Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation)
                            draw_x = tag_x + (THUMB_SIZE - pix.width()) // 2
                            draw_y = int(cy) + (THUMB_SIZE - pix.height()) // 2
                            painter.drawPixmap(draw_x, draw_y, pix)
                            tag_x += THUMB_SIZE + 2
                        else:
                            tag_x = self._draw_capsule_tag(
                                painter, tag_x, cy, var_label,
                                '#e8943a', '#3d2810', rect.width())
                    else:
                        tag_x = self._draw_capsule_tag(
                            painter, tag_x, cy, cos_label,
                            '#e8943a', '#3d2810', rect.width())

                cy += THUMB_SIZE + 2

            # ── 渲染独立资产（场景/道具/照明/无owner服装，横向排列） ──
            if standalone:
                tag_x = 12
                for ba in standalone:
                    ba_name = str(ba.get('name', ba.get('type', '')))[:8]
                    ba_type = ba.get('type', '')
                    fg_hex, bg_hex = _BOUND_TYPE_COLORS.get(ba_type, ('#888', '#333'))
                    tag_x = self._draw_capsule_tag(
                        painter, tag_x, cy, ba_name, fg_hex, bg_hex, rect.width())
                    if tag_x > rect.width() - 12:
                        break
                cy += 18
        elif asset_needs:
            cy += 4
            painter.setFont(QFont("Microsoft YaHei", 7))
            tag_x = 12
            for asset in asset_needs[:2]:
                a_tag = str(asset)[:10]
                fm_tag = QFontMetrics(painter.font())
                tw = fm_tag.horizontalAdvance(a_tag) + 10
                if tag_x + tw > rect.width() - 12:
                    break
                asset_rect = QRectF(tag_x, cy, tw, 16)
                asset_path = QPainterPath()
                asset_path.addRoundedRect(asset_rect, 8, 8)
                is_ref_img = 'Character' in a_tag or 'REF_IMG' in a_tag
                if theme.is_dark():
                    tag_bg = QColor(30, 55, 85, 100) if is_ref_img else QColor(60, 35, 20, 100)
                else:
                    tag_bg = QColor(220, 238, 255) if is_ref_img else QColor(255, 240, 220)
                painter.fillPath(asset_path, QBrush(tag_bg))
                tag_fg = QColor("#60a5fa") if is_ref_img else QColor("#f59e0b")
                painter.setPen(QPen(tag_fg))
                painter.drawText(asset_rect,
                                 Qt.AlignmentFlag.AlignCenter,
                                 a_tag)
                tag_x += tw + 4
            cy += 20

        # 底部状态条
        status = self.scene_data.get('status', 'pending')
        status_color = QColor(self.STATUS_COLORS.get(status, '#636366'))
        status_bar_rect = QRectF(12, cy + 4, rect.width() - 24, 3)
        status_bar_path = QPainterPath()
        status_bar_path.addRoundedRect(status_bar_rect, 1.5, 1.5)
        painter.fillPath(status_bar_path, QBrush(status_color))

        painter.restore()

        # ── 迷你滚动条指示器（仅选中且可滚动时显示） ──
        if self._selected and self._scroll_max > 0:
            sb_x = rect.width() - 5
            sb_track_top = scroll_area_top + 2
            sb_track_h = scroll_area_h - 4
            # 滑块比例
            visible_ratio = scroll_area_h / (scroll_area_h + self._scroll_max)
            sb_h = max(12, sb_track_h * visible_ratio)
            scroll_ratio = self._scroll_offset / self._scroll_max if self._scroll_max > 0 else 0
            sb_y = sb_track_top + (sb_track_h - sb_h) * scroll_ratio
            sb_path = QPainterPath()
            sb_path.addRoundedRect(QRectF(sb_x, sb_y, 3, sb_h), 1.5, 1.5)
            sb_color = QColor(theme.text_tertiary())
            sb_color.setAlpha(100)
            painter.fillPath(sb_path, QBrush(sb_color))

        # 场景类型标签（右上角，不受滚动影响）
        scene_type = self.scene_data.get('scene_type', 'normal')
        if scene_type != 'normal':
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.setPen(QPen(QColor(theme.warning_color())))
            type_rect = QRectF(rect.width() - 60, 30, 50, 14)
            painter.drawText(type_rect,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             scene_type)

    def _draw_capsule_tag(self, painter: QPainter, x: float, y: float,
                          text: str, fg_hex: str, bg_hex: str,
                          max_width: float) -> float:
        """绘制胶囊标签，返回更新后的 x 坐标（tag 右边缘 + 间距）"""
        fm_tag = QFontMetrics(painter.font())
        tw = fm_tag.horizontalAdvance(text) + 14
        if x + tw > max_width - 12:
            return x  # 超出则不绘制
        tag_rect = QRectF(x, y, tw, 16)
        tag_path = QPainterPath()
        tag_path.addRoundedRect(tag_rect, 8, 8)
        painter.fillPath(tag_path, QBrush(QColor(bg_hex)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(fg_hex)))
        painter.drawEllipse(QPointF(x + 6, y + 8), 3, 3)
        painter.setPen(QPen(QColor(fg_hex)))
        painter.drawText(QRectF(x + 12, y, tw - 14, 16),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         text)
        return x + tw + 4

    def _paint_asset_slots(self, painter: QPainter, y_cur: float,
                            content_w: float, rect: QRectF) -> float:
        """绘制资产位：角色穿着关联 + 照明标签"""
        # A. 角色穿着关联行（橙色胶囊）
        _chars = self.scene_data.get('characters') or []
        if not _chars:
            ca = self.scene_data.get('character_actions')
            if isinstance(ca, list):
                _chars = ca
        clothing_pairs = []
        for ch in _chars:
            ch_name = (ch.get('name') or ch.get('character', ''))[:6]
            clothing = ch.get('clothing_style', '') or ch.get('costume', '')
            if ch_name and clothing:
                clothing_short = str(clothing)[:6]
                clothing_pairs.append(f"{ch_name}\u2192{clothing_short}")
        if clothing_pairs:
            painter.setFont(QFont("Microsoft YaHei", 7))
            tag_x = 12
            for pair_text in clothing_pairs[:2]:
                fm_cp = QFontMetrics(painter.font())
                tw = fm_cp.horizontalAdvance(pair_text) + 12
                if tag_x + tw > rect.width() - 12:
                    break
                cp_rect = QRectF(tag_x, y_cur, tw, 16)
                cp_path = QPainterPath()
                cp_path.addRoundedRect(cp_rect, 8, 8)
                if theme.is_dark():
                    painter.fillPath(cp_path, QBrush(QColor(60, 40, 15, 100)))
                    painter.setPen(QPen(QColor("#e8943a")))
                else:
                    painter.fillPath(cp_path, QBrush(QColor(255, 240, 220)))
                    painter.setPen(QPen(QColor("#c2700a")))
                painter.drawText(cp_rect, Qt.AlignmentFlag.AlignCenter, pair_text)
                tag_x += tw + 4
            y_cur += 18

        # B. 照明标签行（金黄色胶囊）
        vps = self.scene_data.get('visual_prompt_struct')
        lighting_text = ''
        if isinstance(vps, dict):
            lighting_text = vps.get('lighting', '')
        if lighting_text:
            lighting_text = str(lighting_text)[:12]
            painter.setFont(QFont("Microsoft YaHei", 7))
            fm_lt = QFontMetrics(painter.font())
            tw = fm_lt.horizontalAdvance(lighting_text) + 12
            tw = min(tw, int(content_w))
            lt_rect = QRectF(12, y_cur, tw, 16)
            lt_path = QPainterPath()
            lt_path.addRoundedRect(lt_rect, 8, 8)
            if theme.is_dark():
                painter.fillPath(lt_path, QBrush(QColor(60, 50, 15, 100)))
                painter.setPen(QPen(QColor("#f0c040")))
            else:
                painter.fillPath(lt_path, QBrush(QColor(255, 248, 220)))
                painter.setPen(QPen(QColor("#a08010")))
            painter.drawText(lt_rect, Qt.AlignmentFlag.AlignCenter, lighting_text)
            y_cur += 18

        return y_cur

    def _measure_content_height(self, content_w: float) -> float:
        """测量全部内容所需的像素高度"""
        h = 0.0

        if self._has_rich_data:
            visual_desc = self.scene_data.get('image_prompt', '')
            if visual_desc:
                fm = QFontMetrics(QFont("Microsoft YaHei", 9))
                br = fm.boundingRect(
                    0, 0, int(content_w), 0,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap,
                    visual_desc,
                )
                h += br.height() + 8

            action_ref = self.scene_data.get('action_reference', '')
            if not action_ref:
                vps = self.scene_data.get('visual_prompt_struct')
                if isinstance(vps, dict):
                    action_ref = vps.get('action', '')
            if action_ref:
                h += 20

            # 多角色台词高度
            _chars = self.scene_data.get('characters') or []
            if not _chars:
                ca = self.scene_data.get('character_actions')
                if isinstance(ca, list):
                    _chars = ca
            _dial_count = 0
            if _chars:
                for ch in _chars:
                    if ch.get('dialogue'):
                        _dial_count += 1
            if _dial_count > 0:
                h += _dial_count * 18
            else:
                dialogue = self.scene_data.get('dialogue', '')
                if not dialogue:
                    ac = self.scene_data.get('audio_config')
                    if isinstance(ac, dict):
                        dialogue = ac.get('dialogue', '')
                if dialogue:
                    h += 20
        else:
            text = self.scene_data.get('subtitle_text', '')
            if text:
                fm = QFontMetrics(QFont("Microsoft YaHei", 9))
                br = fm.boundingRect(
                    0, 0, int(content_w), 0,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap,
                    text,
                )
                h += br.height() + 8

        # 角色穿着关联高度
        _chars_for_measure = self.scene_data.get('characters') or []
        if not _chars_for_measure:
            ca_m = self.scene_data.get('character_actions')
            if isinstance(ca_m, list):
                _chars_for_measure = ca_m
        if any(ch.get('clothing_style') or ch.get('costume') for ch in _chars_for_measure):
            h += 18

        # 照明标签高度
        _vps = self.scene_data.get('visual_prompt_struct')
        if isinstance(_vps, dict) and _vps.get('lighting'):
            h += 18

        asset_needs = self.scene_data.get('asset_needs') or []
        if not asset_needs:
            gp = self.scene_data.get('generation_params')
            if isinstance(gp, dict):
                asset_needs = gp.get('asset_needs', [])
        bound_assets = self.scene_data.get('bound_assets') or []
        if bound_assets or asset_needs:
            h += 24  # 4 gap + 16 tag + 4

        # 底部状态条
        h += 7  # 4 gap + 3 bar

        return h


# ============================================================
#  ShotRhythmCanvasView — 分镜画布视图
# ============================================================

class ShotRhythmCanvasView(BaseCanvasView):
    """
    分镜节奏画布视图。
    继承 BaseCanvasView 获取点阵网格、右键平移、Ctrl滚轮缩放。
    """

    shot_card_clicked = pyqtSignal(int)    # global_index (scene_index)
    shot_card_right_clicked = pyqtSignal(int, object)  # global_index, QPoint

    CARD_SPACING = 8
    START_Y = 20
    START_X = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shot_cards: List[ShotCanvasCard] = []
        self._selected_global_index: Optional[int] = None

    def load_shots(self, scenes_data: list):
        """加载分镜卡片列表"""
        self.clear_all()

        y = self.START_Y
        for i, scene_data in enumerate(scenes_data):
            card = ShotCanvasCard(scene_data, i)
            card.setPos(self.START_X, y)
            self._canvas_scene.addItem(card)
            self._shot_cards.append(card)
            y += card.rect().height() + self.CARD_SPACING

        self._expand_scene_rect()

    def clear_all(self):
        """清空所有卡片"""
        for card in self._shot_cards:
            if card.scene():
                self._canvas_scene.removeItem(card)
        self._shot_cards.clear()
        self._selected_global_index = None

    def get_shot_count(self) -> int:
        return len(self._shot_cards)

    # ==================== 鼠标事件 ====================

    def wheelEvent(self, event):
        """滚轮事件：选中分镜卡且鼠标在其上方时滚动卡片内容"""
        if self._selected_global_index is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            for card in self._shot_cards:
                if card._selected and card.is_scrollable:
                    if card.sceneBoundingRect().contains(scene_pos):
                        delta = event.angleDelta().y()
                        card.scroll_content(-delta * 0.5)
                        event.accept()
                        return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self._canvas_scene.itemAt(scene_pos, self.transform())

            if isinstance(item, ShotCanvasCard):
                self._select_card(item)
                event.accept()
                return

            # 取消选中
            self._deselect_all()

        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单 — 检测点击的卡片"""
        scene_pos = self.mapToScene(event.pos())
        item = self._canvas_scene.itemAt(scene_pos, self.transform())

        if isinstance(item, ShotCanvasCard):
            self.shot_card_right_clicked.emit(
                item.global_index, event.globalPos()
            )
            event.accept()
            return

        # 右键空白区域的菜单由基类处理（平移）
        super().contextMenuEvent(event)

    def _select_card(self, card: ShotCanvasCard):
        self._deselect_all()
        card.set_selected(True)
        self._selected_global_index = card.global_index
        self.shot_card_clicked.emit(card.global_index)

    def _deselect_all(self):
        for card in self._shot_cards:
            card.set_selected(False)
        self._selected_global_index = None


# ============================================================
#  _ExpandBtn — 放大/缩小自绘图标按钮
# ============================================================

class _ExpandBtn(QPushButton):
    """放大/缩小切换按钮，自绘展开/收起图标"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._hovered = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("放大")

    def set_expanded(self, v: bool):
        self._expanded = v
        self.setToolTip("缩小" if v else "放大")
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        if self._hovered:
            p.setPen(QPen(QColor(theme.border()), 1))
            p.setBrush(QBrush(QColor(theme.btn_bg_hover())))
        else:
            p.setPen(QPen(QColor(theme.border()), 0.5))
            p.setBrush(QBrush(QColor(theme.bg_secondary())))
        p.drawRoundedRect(r, 6, 6)
        color = QColor(theme.text_primary()) if self._hovered else QColor(theme.text_secondary())
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        a = 5
        if not self._expanded:
            for x, y, dx, dy in [(6,6,1,1),(22,6,-1,1),(6,22,1,-1),(22,22,-1,-1)]:
                p.drawLine(x, y, x + dx * a, y)
                p.drawLine(x, y, x, y + dy * a)
        else:
            for x, y, dx, dy in [(11,11,-1,-1),(17,11,1,-1),(11,17,-1,1),(17,17,1,1)]:
                p.drawLine(x, y, x + dx * a, y)
                p.drawLine(x, y, x, y + dy * a)
        p.end()


# ============================================================
#  ShotRhythmCanvasPanel — 包装面板
# ============================================================

class ShotRhythmCanvasPanel(QWidget):
    """
    分镜节奏面板 — 画布 + 浮动操作按钮。
    对外接口与旧 ShotRhythmPanel 保持一致。
    """

    shot_selected = pyqtSignal(int)   # scene_index (全局索引)
    shots_changed = pyqtSignal()
    maximize_requested = pyqtSignal()
    restore_requested = pyqtSignal()

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self._current_act_id = None
        self._split_worker = None
        self._is_maximized = False

        self._init_ui()
        self._connect_canvas_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 无限画布
        self._canvas = ShotRhythmCanvasView()
        layout.addWidget(self._canvas, 1)

        # === 浮动操作按钮组（左上角）===
        self._action_float = QWidget(self)
        action_layout = QHBoxLayout(self._action_float)
        action_layout.setContentsMargins(10, 6, 10, 6)
        action_layout.setSpacing(8)

        self._ai_split_btn = QPushButton("AI 拆分")
        self._ai_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_split_btn.clicked.connect(self._ai_split_shots)
        action_layout.addWidget(self._ai_split_btn)

        self._quick_split_btn = QPushButton("快速拆分")
        self._quick_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quick_split_btn.clicked.connect(self._quick_split_shots)
        action_layout.addWidget(self._quick_split_btn)

        # 时长预设按钮
        for dur in [8, 10, 12]:
            btn = QPushButton(f"{dur}s")
            btn.setFixedWidth(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, d=dur: self._set_duration_preset(d))
            action_layout.addWidget(btn)
            # 保存引用用于主题应用
            if not hasattr(self, '_dur_btns'):
                self._dur_btns = []
            self._dur_btns.append(btn)

        self._action_float.adjustSize()
        self._action_float.raise_()

        # === 浮动状态标签（右上角）===
        self._status_float = QWidget(self)
        status_layout = QHBoxLayout(self._status_float)
        status_layout.setContentsMargins(10, 6, 10, 6)
        status_layout.setSpacing(8)

        self._count_label = QLabel("")
        self._count_label.setFont(QFont("Arial", 10))
        status_layout.addWidget(self._count_label)

        self._status_label = QLabel("")
        self._status_label.setFont(QFont("Arial", 10))
        status_layout.addWidget(self._status_label)

        self._status_float.adjustSize()
        self._status_float.raise_()

        # === 放大按钮（左上角）===
        self._maximize_btn = _ExpandBtn(self)
        self._maximize_btn.clicked.connect(self._on_maximize_clicked)
        self._maximize_btn.raise_()

        # === 占位提示（画布中心）===
        self._placeholder = QLabel("选择左侧场次查看分镜", self)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setFont(QFont("Microsoft YaHei", 12))
        self._placeholder.setVisible(True)

    def _connect_canvas_signals(self):
        self._canvas.shot_card_clicked.connect(self._on_card_clicked)
        self._canvas.shot_card_right_clicked.connect(self._on_context_menu)

    def _on_card_clicked(self, global_index: int):
        self.shot_selected.emit(global_index)

    def _on_maximize_clicked(self):
        if self._is_maximized:
            self.restore_requested.emit()
        else:
            self.maximize_requested.emit()

    def set_maximized(self, maximized: bool):
        self._is_maximized = maximized
        self._maximize_btn.set_expanded(maximized)

    def _on_context_menu(self, global_index: int, pos):
        menu = QMenu(self)

        merge_action = QAction("合并到下一个", self)
        merge_action.triggered.connect(lambda: self._merge_shots(global_index))
        menu.addAction(merge_action)

        split_action = QAction("拆分", self)
        split_action.triggered.connect(lambda: self._split_shot(global_index))
        menu.addAction(split_action)

        menu.addSeparator()

        for dur in [8, 10, 12]:
            dur_action = QAction(f"设为 {dur}s", self)
            dur_action.triggered.connect(
                lambda checked, d=dur: self._set_shot_duration(global_index, d)
            )
            menu.addAction(dur_action)

        menu.exec(pos)

    # ==================== 外部接口 ====================

    def load_act_shots(self, act_id: int):
        """加载指定场次的分镜列表"""
        self._current_act_id = act_id

        if not self.data_hub:
            return

        scenes = self.data_hub.act_controller.get_act_scenes(act_id)
        if not scenes:
            self._canvas.clear_all()
            self._placeholder.setVisible(True)
            self._placeholder.setText("该场次暂无分镜，点击 AI 拆分 生成")
            self._count_label.setText("0 个分镜")
            return

        self._placeholder.setVisible(False)
        self._canvas.load_shots(scenes)
        self._count_label.setText(f"{len(scenes)} 个分镜")

    def clear(self):
        """清空面板"""
        self._current_act_id = None
        self._canvas.clear_all()
        self._placeholder.setVisible(True)
        self._placeholder.setText("选择左侧场次查看分镜")
        self._count_label.setText("")
        self._status_label.setText("")

    # ==================== 分镜操作 ====================

    def _ai_split_shots(self):
        if not self._current_act_id or not self.data_hub:
            QMessageBox.warning(self, "提示", "请先选择一个场次")
            return

        acts = self.data_hub.acts_data
        act_data = None
        for a in acts:
            if a.get('id') == self._current_act_id:
                act_data = a
                break

        if not act_data:
            return

        source = self.data_hub.get_source_content()
        text_range = act_data.get('source_text_range')
        if text_range and source:
            act_text = source[text_range[0]:text_range[1]]
        else:
            act_text = act_data.get('summary', '')

        if not act_text:
            QMessageBox.warning(self, "提示", "该场次没有关联文本")
            return

        self._ai_split_btn.setEnabled(False)
        self._status_label.setText("AI 分镜拆分中...")

        from services.ai_analyzer import ActToShotsWorker
        self._split_worker = ActToShotsWorker(self._current_act_id, act_text)
        self._split_worker.split_completed.connect(self._on_ai_shots_completed)
        self._split_worker.split_failed.connect(self._on_shots_failed)
        self._split_worker.start()

    def _quick_split_shots(self):
        if not self._current_act_id or not self.data_hub:
            return

        source = self.data_hub.get_source_content()
        acts = self.data_hub.acts_data
        act_data = None
        for a in acts:
            if a.get('id') == self._current_act_id:
                act_data = a
                break

        if not act_data:
            return

        text_range = act_data.get('source_text_range')
        if text_range and source:
            act_text = source[text_range[0]:text_range[1]]
        else:
            act_text = act_data.get('summary', '')

        if not act_text:
            return

        from services.scene.processor import SceneProcessor
        shots = SceneProcessor.split_act_text_to_shots(act_text)
        self._save_shots(shots)

    def _on_ai_shots_completed(self, act_id: int, shots: list):
        self._ai_split_btn.setEnabled(True)
        self._status_label.setText(f"已拆分为 {len(shots)} 个分镜")
        self._save_shots(shots)

    def _on_shots_failed(self, act_id: int, error: str):
        self._ai_split_btn.setEnabled(True)
        self._status_label.setText(f"拆分失败: {error}")

    def _save_shots(self, shots: list):
        if not self.data_hub or not self._current_act_id:
            return

        self.data_hub.act_controller.split_act_into_shots(
            self._current_act_id, shots
        )
        self.load_act_shots(self._current_act_id)
        self.shots_changed.emit()

    def _merge_shots(self, global_index: int):
        if not self.data_hub:
            return

        cards = self._canvas._shot_cards
        indices = [c.global_index for c in cards]
        try:
            local_idx = indices.index(global_index)
        except ValueError:
            return

        if local_idx + 1 >= len(cards):
            return

        current_card = cards[local_idx]
        next_card = cards[local_idx + 1]

        from database import session_scope, Scene
        with session_scope() as session:
            scene1 = session.query(Scene).get(current_card.scene_id)
            scene2 = session.query(Scene).get(next_card.scene_id)
            if scene1 and scene2:
                scene1.subtitle_text = (scene1.subtitle_text or '') + (scene2.subtitle_text or '')
                scene1.duration = (scene1.duration or 0) + (scene2.duration or 0)
                session.delete(scene2)

        self.load_act_shots(self._current_act_id)
        self.shots_changed.emit()

    def _split_shot(self, global_index: int):
        if not self.data_hub:
            return

        card = None
        for c in self._canvas._shot_cards:
            if c.global_index == global_index:
                card = c
                break
        if not card:
            return

        text = card.scene_data.get('subtitle_text', '')
        if len(text) < 10:
            QMessageBox.information(self, "提示", "文本太短，无法拆分")
            return

        mid = len(text) // 2
        for offset in range(min(20, len(text) // 4)):
            for pos in [mid + offset, mid - offset]:
                if 0 < pos < len(text) and text[pos] in '。！？.!?\n':
                    mid = pos + 1
                    break
            else:
                continue
            break

        text1 = text[:mid].strip()
        text2 = text[mid:].strip()
        dur = card.scene_data.get('duration', 10)

        from database import session_scope, Scene
        with session_scope() as session:
            scene = session.query(Scene).get(card.scene_id)
            if scene:
                scene.subtitle_text = text1
                scene.duration = dur * len(text1) / max(1, len(text))

                new_scene = Scene(
                    project_id=scene.project_id,
                    act_id=scene.act_id,
                    scene_index=scene.scene_index + 1,
                    subtitle_text=text2,
                    duration=dur * len(text2) / max(1, len(text)),
                    status='pending',
                )
                session.add(new_scene)

        self.load_act_shots(self._current_act_id)
        self.shots_changed.emit()

    def _set_shot_duration(self, global_index: int, duration: float):
        if not self.data_hub:
            return

        for card in self._canvas._shot_cards:
            if card.global_index == global_index:
                from database import session_scope, Scene
                with session_scope() as session:
                    scene = session.query(Scene).get(card.scene_id)
                    if scene:
                        scene.duration = duration
                card.scene_data['duration'] = duration
                card.update()
                break

    def _set_duration_preset(self, duration: float):
        """对当前选中的分镜设置时长"""
        if self._canvas._selected_global_index is not None:
            self._set_shot_duration(self._canvas._selected_global_index, duration)

    # ==================== 布局定位 ====================

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_floats()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_floats()

    def _position_floats(self):
        # 操作按钮 → 顶部居中
        self._action_float.adjustSize()
        aw = self._action_float.sizeHint().width()
        ah = self._action_float.sizeHint().height()
        self._action_float.setGeometry((self.width() - aw) // 2, 8, aw, ah)

        # 状态 → 右上角
        self._status_float.adjustSize()
        sw = self._status_float.sizeHint().width()
        sh = self._status_float.sizeHint().height()
        self._status_float.setGeometry(self.width() - sw - 8, 8, sw, sh)

        # 放大按钮 → 左上角
        self._maximize_btn.move(8, 8)

        # 占位提示 → 居中
        pw = self._placeholder.sizeHint().width()
        ph = self._placeholder.sizeHint().height()
        self._placeholder.setGeometry(
            (self.width() - pw) // 2,
            (self.height() - ph) // 2,
            pw, ph
        )

    # ==================== 主题 ====================

    def apply_theme(self):
        self._count_label.setStyleSheet(
            f"color: {theme.text_tertiary()}; background: transparent;"
        )
        self._status_label.setStyleSheet(
            f"color: {theme.text_tertiary()}; background: transparent;"
        )
        self._placeholder.setStyleSheet(f"color: {theme.text_tertiary()};")

        btn_style = theme.float_btn_style()
        self._quick_split_btn.setStyleSheet(btn_style)
        for btn in getattr(self, '_dur_btns', []):
            btn.setStyleSheet(btn_style)

        self._ai_split_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()}; color: white;
                border: none; border-radius: 8px;
                padding: 6px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
            QPushButton:disabled {{ background-color: {theme.bg_tertiary()}; color: {theme.text_tertiary()}; }}
        """)

        # 浮动面板背景
        float_bg = theme.bg_elevated()
        float_style = f"""
            background: {float_bg};
            border: 1px solid {theme.border()};
            border-radius: 10px;
        """
        self._action_float.setStyleSheet(float_style)
        self._status_float.setStyleSheet(float_style)

        self._maximize_btn.update()
