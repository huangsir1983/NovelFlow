"""
涛割 - 大场景序列区（第一栏）— 无限画布模式
导入文本 → 按标点分割为句子卡片 → AI拆分后分组 → 摘要卡片 + 贝塞尔曲线连接
手动操作：框选打组 / 拆分组 / 拖拽排序 / 剔除场景
"""

import re
from typing import Optional, List, Dict, Any, Set

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QTextEdit, QLineEdit, QDialog,
    QGraphicsRectItem, QGraphicsPathItem, QGraphicsProxyWidget,
    QGraphicsItem, QGraphicsTextItem, QMenu, QStyleOptionGraphicsItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QFontMetrics, QAction, QLinearGradient,
)

from ui import theme
from ui.components.base_canvas_view import BaseCanvasView, LOD_TEXT_MIN_PX, LOD_CARD_SIMPLIFY_ZOOM
from ui.components.canvas_mode import GROUP_PRESET_COLORS


# ==================== 常量 ====================

RHYTHM_COLORS = {
    '钩子': '#ff6b6b',
    '铺垫': '#ffd166',
    '高潮': '#ff453a',
    '收束': '#06d6a0',
}

# 侧边标签颜色
TAG_COLORS = {
    '爆点': '#ff453a',
    '情绪': '#ff9f0a',
    '冲突': '#8b5cf6',
}

# 句子分割正则
SENTENCE_SPLIT_RE = re.compile(r'(?<=[。！？.!?\n])')

# 拖拽阈值（像素）
DRAG_THRESHOLD = 6


def split_text_to_sentences(text: str) -> list:
    """
    智能句子分割：按标点拆行，但对话引号对内的内容不拆开。
    支持的引号对：「」、『』、""、''、""、''
    返回句子文本列表。
    """
    spans = split_text_to_sentence_spans(text)
    return [s[0] for s in spans]


def split_text_to_sentence_spans(text: str) -> list:
    """
    智能句子分割，返回 [(sentence_text, start, end), ...] 带原文位置。
    合并过短片段（纯数字、单字符等）到相邻句子，避免碎片化。
    """
    if not text:
        return []

    # 先将对话块提取为占位符，保护不被拆分
    dialogue_holders = []
    dialogue_re = re.compile(
        r'[「『""\u201c\u2018]'
        r'[^」』""\u201d\u2019]*'
        r'[」』""\u201d\u2019]'
    )

    # 记录对话块的原始位置
    protected = text
    dlg_map = {}  # placeholder → (original_text, original_pos)
    for m in dialogue_re.finditer(text):
        placeholder = f'\x00DLG{len(dialogue_holders):04d}\x00'
        dlg_map[placeholder] = m.group(0)
        dialogue_holders.append(m.group(0))
        protected = protected.replace(m.group(0), placeholder, 1)

    # 用正则在保护后的文本中找到所有分割点
    split_points = [0]
    for m in SENTENCE_SPLIT_RE.finditer(protected):
        pos = m.start()
        if pos not in split_points:
            split_points.append(pos)
    split_points.append(len(protected))

    # 提取片段（在 protected 文本中的位置）
    raw_spans = []
    for i in range(len(split_points) - 1):
        s, e = split_points[i], split_points[i + 1]
        segment = protected[s:e]
        # 还原对话占位符
        for placeholder, original in dlg_map.items():
            segment = segment.replace(placeholder, original)
        stripped = segment.strip()
        if stripped:
            raw_spans.append(stripped)

    # 现在把这些句子映射回原文中的精确位置
    spans = []
    search_pos = 0
    for sent in raw_spans:
        # 在原文中查找这个句子
        # 先尝试精确匹配
        idx = text.find(sent, search_pos)
        if idx == -1:
            # 尝试去除首尾空白后匹配（原文可能有不同空白）
            idx = text.find(sent.strip(), search_pos)
        if idx == -1:
            # 尝试匹配前15个非空字符
            prefix = sent[:15]
            idx = text.find(prefix, search_pos)
        if idx == -1:
            idx = search_pos

        end = idx + len(sent)
        # 确保 end 不超过原文（在原文中可能实际长度不同）
        actual = text.find(sent, idx)
        if actual == idx:
            end = idx + len(sent)
        spans.append((sent, idx, end))
        search_pos = end

    # 章节标题正则：匹配 "第X章"、"第X节"、"1."、"第一章"、"序章" 等
    _chapter_re = re.compile(
        r'^(第[一二三四五六七八九十百千\d]+[章节回幕部篇]'
        r'|序[章言]'
        r'|\d+[.、．]\s*'
        r'|Chapter\s*\d+'
        r')',
        re.IGNORECASE,
    )

    # 合并碎片 + 章节标题归属到下一句
    merged = []
    pending_fragment = None  # 暂存待合并到下一句的碎片/章节头
    for sent, start, end in spans:
        clean = sent.strip()
        # 判断是否是碎片：纯数字、少于3个有意义字符、纯标点
        is_fragment = (
            len(clean) < 3
            or re.fullmatch(r'[\d\s.、,，:：\-—]+', clean)
            or re.fullmatch(r'[^\u4e00-\u9fff\w]+', clean)
        )
        # 章节标题也必须向下合并（归属到下一句所在的场景）
        is_chapter_head = bool(_chapter_re.match(clean))

        if is_fragment or is_chapter_head:
            # 统一策略：暂存，等待合并到下一句（向下归属）
            if pending_fragment:
                # 已有暂存碎片，扩展其范围
                pf_sent, pf_start, pf_end = pending_fragment
                pending_fragment = (text[pf_start:end], pf_start, end)
            else:
                pending_fragment = (sent, start, end)
        else:
            if pending_fragment:
                # 把暂存碎片/章节头合并到当前句子
                frag_sent, frag_start, frag_end = pending_fragment
                combined = text[frag_start:end]
                merged.append((combined, frag_start, end))
                pending_fragment = None
            else:
                merged.append((sent, start, end))

    # 如果全是碎片或尾部有未消费的碎片，追加到最后一句或独立保留
    if pending_fragment:
        if merged:
            # 尾部碎片合并到最后一句
            prev_sent, prev_start, prev_end = merged[-1]
            combined = text[prev_start:pending_fragment[2]]
            merged[-1] = (combined, prev_start, pending_fragment[2])
        else:
            merged.append(pending_fragment)

    return merged


# ============================================================
#  SentenceCard — 句子卡片
# ============================================================

class SentenceCard(QGraphicsRectItem):
    """
    句子卡片 — 自适应高度（最多10行），支持滚轮查看超出文本。
    支持选中高亮、分组颜色条、剔除灰化。
    """

    CARD_WIDTH = 340
    CARD_HEIGHT = 36        # 最小高度（单行 fallback / 旧代码兼容）
    CARD_MAX_HEIGHT = 72    # 最大高度（约3行，配合窄卡片防止组背景过大）
    CARD_MIN_HEIGHT = 36    # 最小高度
    CORNER_RADIUS = 6
    TEXT_LEFT = 48           # 文本区左起始
    TEXT_RIGHT_PAD = 40      # 右侧留白（字数统计）
    TEXT_TOP_PAD = 8         # 文本区顶部内边距
    TEXT_BOTTOM_PAD = 8      # 文本区底部内边距
    LINE_HEIGHT = 18         # 估算行高

    def __init__(self, sentence_index: int, text: str, parent=None):
        super().__init__(parent)
        self.sentence_index = sentence_index
        self.text = text
        self.act_group_id: Optional[int] = None
        self._group_color: Optional[QColor] = None
        self._selected = False
        self._is_excluded = False

        # 在原文中的字符偏移（由 load_source_text 设定）
        self.original_start: int = 0
        self.original_end: int = 0

        # 文本滚动偏移（当内容超出最大高度时启用）
        self._text_offset_y = 0
        self._total_text_height = 0  # 文本实际需要的总高度

        # 计算自适应高度
        self._card_height = self._compute_height()
        self.setRect(0, 0, self.CARD_WIDTH, self._card_height)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)

    def _compute_height(self) -> float:
        """根据文本内容计算卡片高度（上限 CARD_MAX_HEIGHT）"""
        text_width = self.CARD_WIDTH - self.TEXT_LEFT - self.TEXT_RIGHT_PAD
        font = QFont("Microsoft YaHei", 10)
        fm = QFontMetrics(font)
        text_rect = fm.boundingRect(
            0, 0, int(text_width), 0,
            Qt.TextFlag.TextWordWrap, self.text
        )
        self._total_text_height = text_rect.height()
        content_h = self._total_text_height + self.TEXT_TOP_PAD + self.TEXT_BOTTOM_PAD
        return min(self.CARD_MAX_HEIGHT, max(self.CARD_MIN_HEIGHT, content_h))

    def _can_scroll(self) -> bool:
        """文本是否超出可见区域"""
        visible_h = self._card_height - self.TEXT_TOP_PAD - self.TEXT_BOTTOM_PAD
        return self._total_text_height > visible_h + 2

    def set_group(self, group_id: int, color: QColor):
        self.act_group_id = group_id
        self._group_color = color
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def set_excluded(self, excluded: bool):
        self._is_excluded = excluded
        self.update()

    def wheelEvent(self, event):
        """滚轮滚动文本（仅当文本超出最大高度时）"""
        if not self._can_scroll():
            event.ignore()
            return
        delta = event.delta() if hasattr(event, 'delta') else 0
        if delta == 0:
            # PyQt6: angleDelta
            delta = event.angleDelta().y()
        step = 20
        if delta > 0:
            self._text_offset_y = max(0, self._text_offset_y - step)
        else:
            visible_h = self._card_height - self.TEXT_TOP_PAD - self.TEXT_BOTTOM_PAD
            max_offset = max(0, self._total_text_height - visible_h)
            self._text_offset_y = min(max_offset, self._text_offset_y + step)
        self.update()
        event.accept()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # LOD 极简模式 — 缩放极小时只画填充矩形
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(44, 44, 48) if theme.is_dark() else QColor(255, 255, 255)
            painter.fillRect(rect, bg)
            if self._group_color:
                painter.fillRect(QRectF(0, 0, 3, rect.height()), self._group_color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # Apple 风格：柔和背景 + 微妙阴影
        if self._selected:
            if theme.is_dark():
                bg_color = QColor(44, 54, 78)
            else:
                bg_color = QColor(225, 237, 255)
        else:
            if theme.is_dark():
                bg_color = QColor(44, 44, 48)
            else:
                bg_color = QColor(255, 255, 255)

        # 底部微投影（偏移1px，模拟 iOS 卡片阴影）
        if not self._is_excluded:
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(rect.adjusted(0, 1, 0, 1),
                                       self.CORNER_RADIUS, self.CORNER_RADIUS)
            shadow_color = QColor(0, 0, 0, 18) if theme.is_dark() else QColor(0, 0, 0, 10)
            painter.fillPath(shadow_path, QBrush(shadow_color))

        painter.fillPath(path, QBrush(bg_color))

        # 边框：选中时强调色，默认用极淡分隔线
        if self._selected:
            painter.setPen(QPen(QColor(theme.accent()), 1.5))
            painter.drawPath(path)
        else:
            border_c = QColor(theme.border())
            border_c.setAlpha(40 if theme.is_dark() else 60)
            painter.setPen(QPen(border_c, 0.5))
            painter.drawPath(path)

        # 左侧颜色条（分组后显示，Apple 圆角胶囊条）
        if self._group_color:
            bar_path = QPainterPath()
            bar_rect = QRectF(2, 6, 3, rect.height() - 12)
            bar_path.addRoundedRect(bar_rect, 1.5, 1.5)
            painter.fillPath(bar_path, QBrush(self._group_color))

        # LOD 文本隐藏
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)  # 10pt 基准，屏幕 <12px 时隐藏

        # 文本区域尺寸（scroll indicator 也需要）
        text_x = self.TEXT_LEFT
        text_w = rect.width() - self.TEXT_LEFT - self.TEXT_RIGHT_PAD

        if not _hide_text:
            # 序号 — SF Mono 风格（固定在左上角）
            painter.setFont(QFont("Consolas", 8))
            painter.setPen(QPen(QColor(theme.text_tertiary())))
            painter.drawText(QRectF(12, 0, 32, self.CARD_MIN_HEIGHT),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             f"{self.sentence_index + 1:02d}")

            # 右侧字数统计 — 淡灰色（固定在右上角）
            painter.setFont(QFont("Consolas", 8))
            count_c = QColor(theme.text_tertiary())
            count_c.setAlpha(140)
            painter.setPen(QPen(count_c))
            painter.drawText(QRectF(rect.width() - 50, 0, 42, self.CARD_MIN_HEIGHT),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             f"{len(self.text)}字")

            # 文本内容 — 支持自动换行 + 滚动
            painter.save()
            text_y = self.TEXT_TOP_PAD
            visible_h = rect.height() - self.TEXT_TOP_PAD - self.TEXT_BOTTOM_PAD
            clip_rect = QRectF(text_x, text_y, text_w, visible_h)
            painter.setClipRect(clip_rect)

            painter.setFont(QFont("Microsoft YaHei", 10))
            painter.setPen(QPen(QColor(theme.text_primary())))
            draw_rect = QRectF(text_x, text_y - self._text_offset_y,
                               text_w, self._total_text_height + 20)
            painter.drawText(draw_rect,
                             Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                             self.text)
            painter.restore()

        # 可滚动指示器（底部渐变遮罩提示）
        if self._can_scroll():
            visible_h = rect.height() - self.TEXT_TOP_PAD - self.TEXT_BOTTOM_PAD
            max_offset = max(0, self._total_text_height - visible_h)
            if self._text_offset_y < max_offset - 2:
                # 底部有更多内容：绘制渐变提示
                grad = QLinearGradient(0, rect.height() - 16, 0, rect.height())
                grad.setColorAt(0.0, QColor(0, 0, 0, 0))
                fade_c = QColor(bg_color)
                fade_c.setAlpha(200)
                grad.setColorAt(1.0, fade_c)
                painter.fillRect(QRectF(text_x, rect.height() - 16, text_w, 16), grad)

        # 剔除覆盖层
        if self._is_excluded:
            overlay = QPainterPath()
            overlay.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
            painter.fillPath(overlay, QBrush(QColor(128, 128, 128, 100)))
            painter.setPen(QPen(QColor(160, 160, 160), 1))
            mid_y = rect.height() / 2
            painter.drawLine(QPointF(12, mid_y), QPointF(rect.width() - 12, mid_y))


# ============================================================
#  ActSummaryCard — 场次摘要卡片（场景分析后出现）
# ============================================================

class ActSummaryCard(QGraphicsRectItem):
    """
    场次摘要卡片 — 场景分析后出现在句子组左侧。
    上部：场景剧情总结
    下部：爆点/情绪/冲突标签（仅当存在时显示）
    所有文本区域根据实际渲染高度自适应。
    """

    CARD_WIDTH = 280
    MIN_HEIGHT = 100
    CORNER_RADIUS = 10
    CONTENT_LEFT = 14       # 内容左边距
    CONTENT_RIGHT = 14      # 内容右边距
    TAG_LABEL_WIDTH = 42    # 标签名宽度（"爆点"/"情绪"/"冲突"）

    def __init__(self, act_index: int, act_data: dict, group_color: QColor, parent=None):
        super().__init__(parent)
        self.act_index = act_index
        self.act_data = act_data
        self.act_id = act_data.get('id', 0)
        self._group_color = group_color
        self._selected = False

        # 提取分析结果
        self._summary = act_data.get('summary', '')
        raw_tags = act_data.get('tags', [])

        # 兼容 dict 和 list 两种 tags 格式
        if isinstance(raw_tags, dict):
            self._tag_labels = raw_tags.get('labels', [])
            self._emotion = raw_tags.get('emotion', '') or act_data.get('emotion', '')
            self._emotion_detail = raw_tags.get('emotion_detail', '') or act_data.get('emotion_detail', '')
            self._explosion_detail = raw_tags.get('explosion_detail', '') or act_data.get('explosion_detail', '')
            self._conflict_detail = raw_tags.get('conflict_detail', '') or act_data.get('conflict_detail', '')
        else:
            self._tag_labels = raw_tags if isinstance(raw_tags, list) else []
            self._emotion = act_data.get('emotion', '')
            self._emotion_detail = act_data.get('emotion_detail', '')
            self._explosion_detail = act_data.get('explosion_detail', '')
            self._conflict_detail = act_data.get('conflict_detail', '')

        # 构造标签行数据：[(color_str, label, detail_text), ...]
        self._tag_rows = self._build_tag_rows()

        # 预计算各区域高度（使用真实字体度量）
        self._section_heights = self._measure_sections()
        card_h = max(self.MIN_HEIGHT, self._section_heights['total'])
        self.setRect(0, 0, self.CARD_WIDTH, card_h)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)

    def _build_tag_rows(self) -> list:
        """构造标签行列表"""
        rows = []
        if '爆点' in self._tag_labels:
            rows.append(('#ff453a', '爆点', self._explosion_detail))
        if '情绪' in self._tag_labels:
            detail = self._emotion
            if self._emotion_detail:
                detail = f"{self._emotion} · {self._emotion_detail}"
            rows.append(('#ff9f0a', '情绪', detail))
        if '冲突' in self._tag_labels:
            rows.append(('#8b5cf6', '冲突', self._conflict_detail))
        return rows

    def _measure_sections(self) -> dict:
        """用 QFontMetrics + TextWordWrap 精确测量各区域高度"""
        content_w = self.CARD_WIDTH - self.CONTENT_LEFT - self.CONTENT_RIGHT

        # 标题区：固定高度
        title_h = 28

        # 摘要区
        summary_h = 0
        if self._summary:
            fm = QFontMetrics(QFont("Microsoft YaHei", 10))
            bound = fm.boundingRect(
                0, 0, int(content_w), 0,
                Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                self._summary,
            )
            summary_h = bound.height() + 8  # +底部间距

        # 标签区
        tags_h = 0
        tag_row_heights = []
        if self._tag_rows:
            tags_h += 10  # 分隔线上方间距 + 线 + 下方间距
            detail_w = int(content_w - self.TAG_LABEL_WIDTH - 26)  # 26 = 圆点+标签名左侧空间
            fm_detail = QFontMetrics(QFont("Microsoft YaHei", 9))
            for _, _, detail in self._tag_rows:
                if detail:
                    bound = fm_detail.boundingRect(
                        0, 0, detail_w, 0,
                        Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                        detail,
                    )
                    row_h = max(22, bound.height() + 6)
                else:
                    row_h = 22
                tag_row_heights.append(row_h)
                tags_h += row_h

        total = 10 + title_h + summary_h + tags_h + 12  # 上边距 + 各区域 + 底部间距

        return {
            'title_h': title_h,
            'summary_h': summary_h,
            'tags_h': tags_h,
            'tag_row_heights': tag_row_heights,
            'total': total,
        }

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def boundingRect(self) -> QRectF:
        r = self.rect()
        return QRectF(r.x(), r.y() - 22, r.width(), r.height() + 22)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # LOD 极简模式
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            bg = QColor(40, 40, 44) if theme.is_dark() else QColor(255, 255, 255)
            painter.fillRect(rect, bg)
            painter.fillRect(QRectF(0, 0, 3, rect.height()), self._group_color)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        content_w = rect.width() - self.CONTENT_LEFT - self.CONTENT_RIGHT

        # LOD 文本隐藏
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)  # 10pt 基准，屏幕 <12px 时隐藏

        # 外部标签"场景分析卡"
        if not _hide_text:
            label_font = QFont("Microsoft YaHei", 9)
            painter.setFont(label_font)
            painter.setPen(QColor(theme.text_tertiary()))
            painter.drawText(
                QRectF(4, -18, 200, 16),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                "场景分析卡"
            )

        # Apple 风格：底部微投影
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(rect.adjusted(1, 2, -1, 2),
                                   self.CORNER_RADIUS, self.CORNER_RADIUS)
        shadow_c = QColor(0, 0, 0, 25) if theme.is_dark() else QColor(0, 0, 0, 12)
        painter.fillPath(shadow_path, QBrush(shadow_c))

        # 卡片背景 — 毛玻璃白/深灰
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        if theme.is_dark():
            bg = QColor(40, 40, 44)
        else:
            bg = QColor(255, 255, 255)
        painter.fillPath(card_path, QBrush(bg))

        # 左侧颜色条（Apple 胶囊风格）
        bar_path = QPainterPath()
        bar_rect = QRectF(2, 8, 3, rect.height() - 16)
        bar_path.addRoundedRect(bar_rect, 1.5, 1.5)
        painter.fillPath(bar_path, QBrush(self._group_color))

        # 边框：Apple 超细边框
        if self._selected:
            painter.setPen(QPen(QColor(theme.accent()), 1.5))
        else:
            border_c = QColor(theme.border())
            border_c.setAlpha(50 if theme.is_dark() else 70)
            painter.setPen(QPen(border_c, 0.5))
        painter.drawPath(card_path)

        if _hide_text:
            return

        y = 12.0

        # ─── 标题行：序号 + 标题 ───
        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QPen(QColor(theme.text_tertiary())))
        painter.drawText(QRectF(self.CONTENT_LEFT, y, 30, 18),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         f"{self.act_index + 1:02d}")

        title = self.act_data.get('title', f'场次 {self.act_index + 1}')
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.DemiBold))
        painter.setPen(QPen(QColor(theme.text_primary())))
        fm_title = QFontMetrics(painter.font())
        elided_title = fm_title.elidedText(title, Qt.TextElideMode.ElideRight, int(content_w - 34))
        painter.drawText(QRectF(44, y, content_w - 30, 18),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         elided_title)
        y += self._section_heights['title_h']

        # ─── 剧情总结（自动换行） ───
        if self._summary:
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.setPen(QPen(QColor(theme.text_secondary())))
            summary_rect = QRectF(self.CONTENT_LEFT, y, content_w, self._section_heights['summary_h'])
            painter.drawText(summary_rect,
                             Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                             self._summary)
            y += self._section_heights['summary_h']

        # ─── 标签区域 ───
        if self._tag_rows:
            # Apple 风格细分隔线
            sep_c = QColor(theme.border())
            sep_c.setAlpha(40)
            painter.setPen(QPen(sep_c, 0.5))
            painter.drawLine(QPointF(self.CONTENT_LEFT, y),
                             QPointF(rect.width() - self.CONTENT_RIGHT, y))
            y += 10

            detail_x = self.CONTENT_LEFT + 18 + self.TAG_LABEL_WIDTH
            detail_w = content_w - 18 - self.TAG_LABEL_WIDTH

            for i, (color_str, label, detail) in enumerate(self._tag_rows):
                row_h = self._section_heights['tag_row_heights'][i]
                color = QColor(color_str)

                # 彩色圆点
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(self.CONTENT_LEFT + 8, y + 10), 3.5, 3.5)

                # 标签名 — 中粗
                painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.DemiBold))
                painter.setPen(QPen(color))
                painter.drawText(QRectF(self.CONTENT_LEFT + 18, y, self.TAG_LABEL_WIDTH, 20),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 label)

                # 详情文本
                if detail:
                    painter.setFont(QFont("Microsoft YaHei", 9))
                    painter.setPen(QPen(QColor(theme.text_secondary())))
                    painter.drawText(
                        QRectF(detail_x, y, detail_w, row_h),
                        Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        detail,
                    )

                y += row_h

    def mousePressEvent(self, event):
        super().mousePressEvent(event)


# ============================================================
#  ActGroupBackground — 场次分组背景
# ============================================================

class ActGroupBackground(QGraphicsPathItem):
    """
    包围同一组句子卡片的圆角矩形背景（半透明填充，不可拖拽）。
    支持剔除状态视觉（灰色虚点线边框、暗淡填充）。
    """

    CORNER_RADIUS = 12
    PADDING = 8

    def __init__(self, group_id: int, color: QColor, parent=None):
        super().__init__(parent)
        self.group_id = group_id
        self._color = color
        self._excluded = False
        self._scroll_total = 0     # 总卡片数
        self._scroll_offset = 0    # 当前滚动偏移（索引）
        self._scroll_visible = 0   # 可见卡片数
        self.setZValue(-10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        self._apply_style()

    def _apply_style(self):
        if self._excluded:
            pen = QPen(QColor(140, 140, 140), 1.5)
            pen.setStyle(Qt.PenStyle.DashDotLine)
            self.setPen(pen)
            fill = QColor(100, 100, 100, 20)
            self.setBrush(QBrush(fill))
        else:
            pen = QPen(self._color, 1.5)
            pen.setStyle(Qt.PenStyle.DashLine)
            self.setPen(pen)
            fill = QColor(self._color)
            fill.setAlpha(30)
            self.setBrush(QBrush(fill))

    def update_shape(self, sentence_cards: list):
        """根据句子卡片列表更新包围矩形。
        使用 pos()（局部坐标）而非 scenePos()，
        因为在统一画布中卡片和组背景共享同一个 parentItem (ZoneFrame)。
        """
        if not sentence_cards:
            return

        # 计算包围盒（使用局部坐标）
        min_x = min(c.pos().x() for c in sentence_cards)
        min_y = min(c.pos().y() for c in sentence_cards)
        max_x = max(c.pos().x() + c.rect().width() for c in sentence_cards)
        max_y = max(c.pos().y() + c.rect().height() for c in sentence_cards)

        rect = QRectF(
            min_x - self.PADDING,
            min_y - self.PADDING,
            (max_x - min_x) + self.PADDING * 2,
            (max_y - min_y) + self.PADDING * 2,
        )

        path = QPainterPath()
        path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        self.setPath(path)

    def set_color(self, color: QColor):
        self._color = color
        self._apply_style()

    def set_excluded(self, excluded: bool):
        self._excluded = excluded
        self._apply_style()

    def set_scroll_info(self, total: int, offset: int, visible_count: int):
        """设置滚动信息（用于绘制顶部/底部翻页提示）"""
        self._scroll_total = total
        self._scroll_offset = offset
        self._scroll_visible = visible_count
        self.update()

    def boundingRect(self) -> QRectF:
        r = super().boundingRect()
        return QRectF(r.x(), r.y() - 22, r.width(), r.height() + 22)

    def paint(self, painter: QPainter, option, widget=None):
        # LOD 极简模式 — 组背景只画简单填充，跳过虚线边框和文本
        _zoom = painter.worldTransform().m11()
        if _zoom < LOD_CARD_SIMPLIFY_ZOOM:
            path_rect = self.path().boundingRect()
            fill_c = QColor(self._color.red(), self._color.green(),
                            self._color.blue(), 20)
            painter.fillRect(path_rect, fill_c)
            return

        super().paint(painter, option, widget)

        # LOD 文本隐藏
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)  # 10pt 基准，屏幕 <12px 时隐藏
        if _hide_text:
            return

        path_rect = self.path().boundingRect()

        # 外部标签"场景文本"
        label_font = QFont("Microsoft YaHei", 9)
        painter.setFont(label_font)
        painter.setPen(QColor(theme.text_tertiary()))
        painter.drawText(
            QRectF(path_rect.x() + 4, path_rect.y() - 18, 200, 16),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "场景文本"
        )

        # 滚动指示（当组内卡片超过可见数量时）
        if self._scroll_total > self._scroll_visible:
            hint_font = QFont("Microsoft YaHei", 8)
            painter.setFont(hint_font)
            hint_color = QColor(self._color)
            hint_color.setAlpha(180)
            painter.setPen(QPen(hint_color))

            # 顶部 "▲ +N"
            if self._scroll_offset > 0:
                top_hidden = self._scroll_offset
                painter.drawText(
                    QRectF(path_rect.x(), path_rect.y() + 2,
                           path_rect.width(), 14),
                    Qt.AlignmentFlag.AlignCenter,
                    f"▲ +{top_hidden}"
                )

            # 底部 "▼ +N"
            remaining = self._scroll_total - self._scroll_offset - self._scroll_visible
            if remaining > 0:
                painter.drawText(
                    QRectF(path_rect.x(), path_rect.bottom() - 16,
                           path_rect.width(), 14),
                    Qt.AlignmentFlag.AlignCenter,
                    f"▼ +{remaining}"
                )

            # ── 右侧滚动条轨道 ──
            track_x = path_rect.right() - 6
            track_top = path_rect.y() + 20
            track_h = path_rect.height() - 40
            if track_h > 20:
                # 轨道背景
                track_color = QColor(255, 255, 255, 20)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(track_color))
                painter.drawRoundedRect(
                    QRectF(track_x, track_top, 4, track_h), 2, 2)

                # 滑块
                thumb_ratio = self._scroll_visible / max(1, self._scroll_total)
                thumb_h = max(12, track_h * thumb_ratio)
                scroll_range = self._scroll_total - self._scroll_visible
                if scroll_range > 0:
                    thumb_pos = track_top + (self._scroll_offset / scroll_range) * (track_h - thumb_h)
                else:
                    thumb_pos = track_top

                thumb_color = QColor(self._color)
                thumb_color.setAlpha(160)
                painter.setBrush(QBrush(thumb_color))
                painter.drawRoundedRect(
                    QRectF(track_x, thumb_pos, 4, thumb_h), 2, 2)


# ============================================================
#  _GroupIdGen — 组 ID 生成器
# ============================================================

class _GroupIdGen:
    _next = 0

    @classmethod
    def next_id(cls) -> int:
        cls._next += 1
        return cls._next


# ============================================================
#  ActSequenceCanvasView — 无限画布视图
# ============================================================

class ActSequenceCanvasView(BaseCanvasView):
    """
    大场景序列画布视图。
    继承 BaseCanvasView 获取点阵网格、右键平移、Ctrl滚轮缩放。
    支持多选、框选打组、右键菜单拆分/剔除、拖拽排序。
    """

    # 内部信号（供 Panel 层捕获）
    act_card_clicked = pyqtSignal(int)  # act_id
    sentence_clicked = pyqtSignal(int)  # sentence_index
    group_analysis_requested = pyqtSignal(int)   # group index → 单组分析
    groups_changed = pyqtSignal()                 # 分组变化 → 通知面板保存
    exclude_changed = pyqtSignal(int, bool)       # group_index, excluded

    # 布局常量
    SENTENCE_X = 20        # 句子卡片 X 起始位置（分组前无摘要卡片，靠左即可）
    SENTENCE_X_GROUPED = 400  # 分组后句子卡片 X 位置（让出摘要卡片+曲线空间）
    SENTENCE_SPACING = 4   # 句子卡片间垂直间距
    SUMMARY_X = 10         # 摘要卡片 X 位置（分组后）
    CURVE_GAP = 90         # 曲线间距（摘要右边缘到组背景左边缘）
    GROUP_GAP = 30         # 组与组之间的垂直间距

    def __init__(self, parent=None):
        super().__init__(parent)

        self._sentence_cards: List[SentenceCard] = []

        # 统一分组结构
        self._groups: List[Dict[str, Any]] = []
        # 每个 group: {
        #   'group_id': int,
        #   'act_data': dict,
        #   'cards': [SentenceCard],
        #   'color': QColor,
        #   'background': ActGroupBackground | None,
        #   'summary': ActSummaryCard | None,
        #   'connection': QGraphicsPathItem | None,
        #   'excluded': bool,
        # }

        # 多选状态
        self._multi_selected: Set[int] = set()  # sentence_index 集合

        # 框选状态
        self._is_rubber_banding = False
        self._rubber_band_start: Optional[QPointF] = None
        self._rubber_band_rect_item: Optional[QGraphicsRectItem] = None

        # 打组按钮（viewport 子控件，非 QGraphicsProxyWidget）
        self._group_btn: Optional[QPushButton] = None

        # 拖拽排序状态（单卡片）
        self._is_dragging_card = False
        self._drag_card: Optional[SentenceCard] = None
        self._drag_start_pos: Optional[QPointF] = None   # 鼠标按下时的 scene 坐标
        self._drag_card_origin: Optional[QPointF] = None  # 卡片原始 scene 位置
        self._drag_indicator: Optional[QGraphicsRectItem] = None  # 蓝色插入位置指示线
        self._drag_pending = False  # 等待超过阈值才进入拖拽

        # 拖拽排序状态（整组）
        self._is_dragging_group = False
        self._drag_group_idx: int = -1
        self._drag_group_start_pos: Optional[QPointF] = None
        self._drag_group_origins: List[QPointF] = []       # 组内所有卡片的原始位置
        self._drag_group_bg_origin: Optional[QPointF] = None
        self._drag_group_summary_origin: Optional[QPointF] = None
        self._drag_group_pending = False

    # ==================== 加载源文本 ====================

    def load_source_text(self, text: str):
        """按标点分割文本为句子，每句创建一个 SentenceCard（对话不拆开），并记录原文坐标"""
        self.clear_all()

        sentences = split_text_to_sentences(text)

        y = 20
        search_offset = 0
        for i, sent_text in enumerate(sentences):
            card = SentenceCard(i, sent_text)

            # 在原文中定位，记录原文坐标
            pos = text.find(sent_text, search_offset)
            if pos == -1:
                # 精确匹配失败，尝试取前20字匹配
                pos = text.find(sent_text[:20], search_offset) if len(sent_text) >= 20 else -1
            if pos == -1:
                pos = search_offset
            card.original_start = pos
            card.original_end = pos + len(sent_text)
            search_offset = card.original_end

            card.setPos(self.SENTENCE_X, y)
            self._canvas_scene.addItem(card)
            self._sentence_cards.append(card)
            y += SentenceCard.CARD_HEIGHT + self.SENTENCE_SPACING

        self._expand_scene_rect()
        # 导入后重置视图到左上角，确保卡片可见
        self._reset_view_to_origin()

    # ==================== 应用分组（仅分段，不出摘要卡片） ====================

    def apply_grouping_only(self, acts_data: list):
        """
        场景拆分后：给句子分组，创建组背景+颜色条，但不创建摘要卡片和曲线。
        acts_data: list of dict，每个含 source_text_range, title 等。
        """
        # 清除旧分组（保留句子卡片）
        self._clear_groups()

        if not self._sentence_cards or not acts_data:
            return

        self._build_groups_from_acts(acts_data, with_summary=False)
        self._do_layout()
        self._expand_scene_rect()
        self._reset_view_to_origin()

    # ==================== 应用分组 + 摘要卡片（场景分析后） ====================

    def apply_act_groups(self, acts_data: list):
        """
        场景分析后：给句子分组，创建组背景 + 摘要卡片 + 连接线。
        acts_data: list of dict，每个含 source_text_range, title, summary, tags 等。
        """
        # 清除旧分组（保留句子卡片）
        self._clear_groups()

        if not self._sentence_cards or not acts_data:
            return

        self._build_groups_from_acts(acts_data, with_summary=True)
        self._do_layout()
        self._expand_scene_rect()
        # 分组后定位到内容起始位置
        summaries = [g['summary'] for g in self._groups if g.get('summary')]
        if summaries:
            first = summaries[0]
            top_left = QPointF(first.pos().x() - 10, first.pos().y() - 10)
            vp_center = self.mapToScene(self.viewport().rect().center())
            vp_tl = self.mapToScene(self.viewport().rect().topLeft())
            offset = vp_center - vp_tl
            self.centerOn(top_left + offset)

    # ==================== 更新单组分析结果 ====================

    def update_single_group_analysis(self, group_index: int, result: dict):
        """单组分析完成后更新该组的摘要卡片"""
        if group_index < 0 or group_index >= len(self._groups):
            return
        group = self._groups[group_index]

        # 先移除旧的摘要卡片和连线（会清空旧 tags）
        self._remove_group_analysis(group)

        # 再合并新的分析结果到 act_data（覆盖被清空的 tags）
        act_data = group['act_data']
        for key in ('tags', 'summary', 'emotion', 'emotion_detail',
                     'explosion_detail', 'conflict_detail'):
            if result.get(key):
                act_data[key] = result[key]

        # 重新布局（_do_layout 检测到 tags 非空会创建摘要卡片）
        self._do_layout()
        self._expand_scene_rect()

    # ==================== 构建分组映射 ====================

    def _build_groups_from_acts(self, acts_data: list, with_summary: bool = False):
        """将 act 的 source_text_range 映射到句子卡片，构建统一 _groups 结构"""
        self._groups = []

        total_cards = len(self._sentence_cards)
        assigned: set = set()

        for act_idx, act_data in enumerate(acts_data):
            text_range = act_data.get('source_text_range', [])
            if text_range and len(text_range) == 2:
                range_start, range_end = text_range
            else:
                range_start, range_end = None, None

            if range_start is not None:
                # 用原文坐标匹配句子
                matched_indices = []
                for card in self._sentence_cards:
                    if card.sentence_index in assigned:
                        continue
                    if card.original_start < range_end and card.original_end > range_start:
                        matched_indices.append(card.sentence_index)
            else:
                matched_indices = []

            if not matched_indices:
                # 回退：平均分配
                per_act = max(1, total_cards // max(1, len(acts_data)))
                start_i = act_idx * per_act
                end_i = min(total_cards, (act_idx + 1) * per_act)
                if act_idx == len(acts_data) - 1:
                    end_i = total_cards
                matched_indices = [i for i in range(start_i, end_i) if i not in assigned]

            assigned.update(matched_indices)

            # 收集句子文本
            cards = []
            for idx in matched_indices:
                if 0 <= idx < total_cards:
                    cards.append(self._sentence_cards[idx])

            act_data_copy = dict(act_data)
            act_data_copy['source_sentences'] = [c.text for c in cards]

            # 组颜色
            color_tuple = GROUP_PRESET_COLORS[act_idx % len(GROUP_PRESET_COLORS)]
            color = color_tuple[1]
            display_color = QColor(color.red(), color.green(), color.blue(), 80)

            has_analysis = with_summary and bool(act_data.get('tags'))

            self._groups.append({
                'group_id': _GroupIdGen.next_id(),
                'act_data': act_data_copy,
                'cards': cards,
                'color': display_color,
                'background': None,
                'summary': None,
                'connection': None,
                'excluded': bool(act_data.get('is_skipped', False)),
                '_has_analysis': has_analysis,
            })

    # ==================== 统一布局 ====================

    def _do_layout(self):
        """根据 _groups 进行完整布局：句子位置、组背景、摘要卡片、连线"""
        # 先清理旧的视觉元素（保留 _groups 数据结构和 cards 引用）
        for group in self._groups:
            if group.get('background') and group['background'].scene():
                self._canvas_scene.removeItem(group['background'])
            group['background'] = None
            if group.get('summary') and group['summary'].scene():
                self._canvas_scene.removeItem(group['summary'])
            group['summary'] = None
            if group.get('connection') and group['connection'].scene():
                self._canvas_scene.removeItem(group['connection'])
            group['connection'] = None

        # 收集已分组的句子索引
        grouped_indices = set()
        for group in self._groups:
            for c in group['cards']:
                grouped_indices.add(c.sentence_index)

        # 判断是否有任何摘要卡片需要显示
        has_any_summary = any(
            g.get('_has_analysis') or (g['act_data'].get('tags'))
            for g in self._groups
        )
        sentence_x = self.SENTENCE_X_GROUPED if has_any_summary else self.SENTENCE_X

        y_offset = 20

        for gi, group in enumerate(self._groups):
            cards = group['cards']
            if not cards:
                continue

            color = group['color']
            excluded = group['excluded']

            # 设置句子卡片位置和分组颜色
            for card in cards:
                card.setPos(sentence_x, y_offset)
                card.set_group(group['group_id'], color)
                card.set_excluded(excluded)
                y_offset += SentenceCard.CARD_HEIGHT + self.SENTENCE_SPACING

            # 创建组背景
            bg = ActGroupBackground(group['group_id'], color)
            bg.set_excluded(excluded)
            bg.update_shape(cards)
            self._canvas_scene.addItem(bg)
            group['background'] = bg

            # 如果有分析数据，创建摘要卡片
            act_data = group['act_data']
            if act_data.get('tags') and not excluded:
                group_rect = bg.path().boundingRect()
                summary_card = ActSummaryCard(gi, act_data, color)
                summary_y = group_rect.center().y() - summary_card.rect().height() / 2
                summary_card.setPos(self.SUMMARY_X, summary_y)
                self._canvas_scene.addItem(summary_card)
                group['summary'] = summary_card

                # 创建贝塞尔曲线连接
                conn = self._create_connection(summary_card, bg, color)
                group['connection'] = conn

            y_offset += self.GROUP_GAP

        # 未分组的句子放到底部
        for card in self._sentence_cards:
            if card.sentence_index not in grouped_indices:
                card.setPos(sentence_x, y_offset)
                card.act_group_id = None
                card._group_color = None
                card._is_excluded = False
                card.update()
                y_offset += SentenceCard.CARD_HEIGHT + self.SENTENCE_SPACING

    def _create_connection(self, summary_card: ActSummaryCard,
                           group_bg: ActGroupBackground, color: QColor) -> QGraphicsPathItem:
        """创建从摘要卡片到组背景的贝塞尔曲线，返回 line_item"""
        summary_rect = summary_card.sceneBoundingRect()
        group_rect = group_bg.path().boundingRect()

        # 从摘要卡片右边缘中心到组背景左边缘中心
        start = QPointF(summary_rect.right(), summary_rect.center().y())
        end = QPointF(group_rect.left(), group_rect.center().y())

        offset = abs(end.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + offset, start.y())
        ctrl2 = QPointF(end.x() - offset, end.y())

        path = QPainterPath(start)
        path.cubicTo(ctrl1, ctrl2, end)

        line_item = QGraphicsPathItem()
        # 虚线样式，颜色跟组背景色一致但更亮
        brighter = QColor(color.red(), color.green(), color.blue(), 140)
        pen = QPen(brighter, 1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_item.setPen(pen)
        line_item.setPath(path)
        line_item.setZValue(-5)

        self._canvas_scene.addItem(line_item)
        return line_item

    # ==================== 鼠标事件 ====================

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self._canvas_scene.itemAt(scene_pos, self.transform())

            modifiers = event.modifiers()
            ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

            # 检查是否点击了 proxy widget（让 super 处理）
            if isinstance(item, QGraphicsProxyWidget):
                super().mousePressEvent(event)
                return

            # 检查是否点击了摘要卡片
            if isinstance(item, ActSummaryCard):
                self._deselect_all()
                item.set_selected(True)
                self.act_card_clicked.emit(item.act_id)
                event.accept()
                return

            # 检查是否点击了句子卡片
            if isinstance(item, SentenceCard):
                if ctrl:
                    # Ctrl+点击：切换选中
                    idx = item.sentence_index
                    if idx in self._multi_selected:
                        self._multi_selected.discard(idx)
                        item.set_selected(False)
                    else:
                        self._multi_selected.add(idx)
                        item.set_selected(True)
                    self._update_group_btn()
                else:
                    # 普通左键点击：准备拖拽
                    self._drag_pending = True
                    self._drag_card = item
                    self._drag_start_pos = scene_pos
                    self._drag_card_origin = item.pos()
                    # 同时做选中处理
                    if item.sentence_index not in self._multi_selected:
                        self._deselect_all()
                        item.set_selected(True)
                        self.sentence_clicked.emit(item.sentence_index)
                event.accept()
                return

            # 检查是否点击了组背景 — 准备整组拖拽
            if isinstance(item, ActGroupBackground):
                self._deselect_all()
                group_idx = self._find_group_of_background(item)
                if group_idx is not None:
                    self._drag_group_pending = True
                    self._drag_group_idx = group_idx
                    self._drag_group_start_pos = scene_pos
                    # 记录组内所有元素的原始位置
                    group = self._groups[group_idx]
                    self._drag_group_origins = [c.pos() for c in group['cards']]
                    bg = group.get('background')
                    self._drag_group_bg_origin = bg.pos() if bg else None
                    summary = group.get('summary')
                    self._drag_group_summary_origin = summary.pos() if summary else None
                event.accept()
                return

            # 点击空白区域 → 开始框选
            if not ctrl:
                self._deselect_all()
            self._is_rubber_banding = True
            self._rubber_band_start = scene_pos
            self.setMouseTracking(True)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 整组拖拽 pending → 超阈值后进入拖拽模式
        if self._drag_group_pending and self._drag_group_start_pos:
            scene_pos = self.mapToScene(event.position().toPoint())
            delta = scene_pos - self._drag_group_start_pos
            if abs(delta.y()) > DRAG_THRESHOLD or abs(delta.x()) > DRAG_THRESHOLD:
                self._drag_group_pending = False
                self._is_dragging_group = True
                group = self._groups[self._drag_group_idx]
                # 半透明化整组
                for card in group['cards']:
                    card.setOpacity(0.5)
                if group.get('background'):
                    group['background'].setOpacity(0.5)
                if group.get('summary'):
                    group['summary'].setOpacity(0.5)
                if group.get('connection'):
                    group['connection'].setOpacity(0.3)
            else:
                super().mouseMoveEvent(event)
                return

        # 整组拖拽中 — 仅 Y 轴移动
        if self._is_dragging_group and self._drag_group_idx >= 0:
            scene_pos = self.mapToScene(event.position().toPoint())
            dy = scene_pos.y() - self._drag_group_start_pos.y()
            group = self._groups[self._drag_group_idx]
            for i, card in enumerate(group['cards']):
                orig = self._drag_group_origins[i]
                card.setPos(orig.x(), orig.y() + dy)
            if group.get('background') and self._drag_group_bg_origin:
                group['background'].setPos(
                    self._drag_group_bg_origin.x(),
                    self._drag_group_bg_origin.y() + dy)
            if group.get('summary') and self._drag_group_summary_origin:
                group['summary'].setPos(
                    self._drag_group_summary_origin.x(),
                    self._drag_group_summary_origin.y() + dy)
            # 更新组间插入指示器
            self._update_group_drag_indicator(group, dy)
            event.accept()
            return

        # 单卡片拖拽排序
        if self._drag_pending and self._drag_card:
            scene_pos = self.mapToScene(event.position().toPoint())
            delta = scene_pos - self._drag_start_pos
            if abs(delta.y()) > DRAG_THRESHOLD or abs(delta.x()) > DRAG_THRESHOLD:
                self._drag_pending = False
                self._is_dragging_card = True
                self._drag_card.setOpacity(0.5)
                self._drag_card.setZValue(100)
            else:
                super().mouseMoveEvent(event)
                return

        if self._is_dragging_card and self._drag_card:
            scene_pos = self.mapToScene(event.position().toPoint())
            # 仅 Y 轴跟随
            new_y = self._drag_card_origin.y() + (scene_pos.y() - self._drag_start_pos.y())
            self._drag_card.setPos(self._drag_card_origin.x(), new_y)
            # 更新插入位置指示器
            self._update_drag_indicator(new_y)
            event.accept()
            return

        # 框选
        if self._is_rubber_banding and self._rubber_band_start is not None:
            current = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._rubber_band_start, current).normalized()

            if self._rubber_band_rect_item is None:
                self._rubber_band_rect_item = self._canvas_scene.addRect(
                    rect,
                    QPen(QColor(0, 122, 204, 180), 1.5, Qt.PenStyle.DashLine),
                    QBrush(QColor(0, 122, 204, 25))
                )
                self._rubber_band_rect_item.setZValue(2000)
            else:
                self._rubber_band_rect_item.setRect(rect)

            # 实时高亮框内卡片
            self._update_rubber_band_selection(rect)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 完成整组拖拽排序
            if self._is_dragging_group:
                self._finish_group_drag()
                event.accept()
                return

            # 取消整组拖拽 pending
            if self._drag_group_pending:
                self._drag_group_pending = False
                self._drag_group_idx = -1
                self._drag_group_start_pos = None

            # 完成单卡片拖拽排序
            if self._is_dragging_card and self._drag_card:
                self._finish_drag()
                event.accept()
                return

            # 取消拖拽 pending
            if self._drag_pending:
                self._drag_pending = False
                self._drag_card = None
                self._drag_start_pos = None
                self._drag_card_origin = None

            # 完成框选
            if self._is_rubber_banding:
                self._is_rubber_banding = False
                self.setMouseTracking(False)

                # 移除框选矩形
                if self._rubber_band_rect_item:
                    if self._rubber_band_rect_item.scene():
                        self._canvas_scene.removeItem(self._rubber_band_rect_item)
                    self._rubber_band_rect_item = None

                # 显示打组按钮
                if len(self._multi_selected) >= 2:
                    self._show_group_btn()
                else:
                    self._hide_group_btn()

                self._rubber_band_start = None
                event.accept()
                return

        super().mouseReleaseEvent(event)
        self._expand_scene_rect()

    def contextMenuEvent(self, event):
        """右键菜单"""
        # 右键拖拽后不弹出菜单
        if self._pan_moved:
            return

        scene_pos = self.mapToScene(event.pos())
        item = self._canvas_scene.itemAt(scene_pos, self.transform())

        if isinstance(item, SentenceCard):
            self._show_card_context_menu(item, event.globalPos())
            return

        if isinstance(item, ActGroupBackground):
            self._show_group_context_menu(item, event.globalPos())
            return

    # ==================== 框选 ====================

    def _update_rubber_band_selection(self, rect: QRectF):
        """根据框选矩形实时更新卡片的多选高亮"""
        self._multi_selected.clear()
        for card in self._sentence_cards:
            if rect.intersects(card.sceneBoundingRect()):
                self._multi_selected.add(card.sentence_index)
                card.set_selected(True)
            else:
                card.set_selected(False)

    # ==================== 打组按钮 ====================

    def _show_group_btn(self):
        """在多选卡片上方显示浮动"打组"按钮"""
        self._hide_group_btn()

        bounds = self._get_multi_selected_bounds()
        if bounds is None:
            return

        self._group_btn = QPushButton("打组", self.viewport())
        self._group_btn.setFixedSize(60, 28)
        self._group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._group_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.accent_hover()};
            }}
        """)
        self._group_btn.clicked.connect(self._on_create_group)

        # 定位到选区上方（视口坐标）
        center_scene = bounds.center()
        top_scene = QPointF(center_scene.x(), bounds.top() - 40)
        vp_pos = self.mapFromScene(top_scene)
        self._group_btn.move(int(vp_pos.x()) - 30, int(vp_pos.y()))
        self._group_btn.show()
        self._group_btn.raise_()

    def _hide_group_btn(self):
        if self._group_btn:
            self._group_btn.setVisible(False)
            QTimer.singleShot(0, self._destroy_group_btn)

    def _destroy_group_btn(self):
        if self._group_btn:
            self._group_btn.deleteLater()
            self._group_btn = None

    def _update_group_btn(self):
        """根据多选状态更新打组按钮"""
        if len(self._multi_selected) >= 2:
            self._show_group_btn()
        else:
            self._hide_group_btn()

    def _get_multi_selected_bounds(self) -> Optional[QRectF]:
        """计算多选卡片的包围盒（scene 坐标）"""
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        for idx in self._multi_selected:
            for card in self._sentence_cards:
                if card.sentence_index == idx:
                    pos = card.scenePos()
                    min_x = min(min_x, pos.x())
                    min_y = min(min_y, pos.y())
                    max_x = max(max_x, pos.x() + SentenceCard.CARD_WIDTH)
                    max_y = max(max_y, pos.y() + SentenceCard.CARD_HEIGHT)
                    break

        if min_x == float('inf'):
            return None
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    # ==================== 手动打组 ====================

    def _on_create_group(self):
        """将当前多选卡片创建为新组"""
        if len(self._multi_selected) < 2:
            return

        selected_indices = sorted(self._multi_selected)
        selected_cards = []
        for idx in selected_indices:
            for card in self._sentence_cards:
                if card.sentence_index == idx:
                    selected_cards.append(card)
                    break

        if len(selected_cards) < 2:
            return

        # 从原有组中移除这些卡片，如有空组则删除
        groups_to_remove = []
        for gi, group in enumerate(self._groups):
            original_count = len(group['cards'])
            group['cards'] = [c for c in group['cards'] if c.sentence_index not in self._multi_selected]
            if len(group['cards']) != original_count:
                # 卡片被移走了，移除该组的分析卡片
                self._remove_group_analysis(group)
            if not group['cards']:
                groups_to_remove.append(gi)

        # 删除空组（倒序删除避免索引偏移）
        for gi in reversed(groups_to_remove):
            group = self._groups[gi]
            if group.get('background') and group['background'].scene():
                self._canvas_scene.removeItem(group['background'])
            self._groups.pop(gi)

        # 创建新组
        color_idx = len(self._groups) % len(GROUP_PRESET_COLORS)
        color_tuple = GROUP_PRESET_COLORS[color_idx]
        display_color = QColor(color_tuple[1].red(), color_tuple[1].green(),
                               color_tuple[1].blue(), 80)

        # 构造 act_data（手动组没有 source_text_range，以句子文本为准）
        source_sentences = [c.text for c in selected_cards]
        new_act_data = {
            'title': f'手动分组 {len(self._groups) + 1}',
            'source_sentences': source_sentences,
            'tags': [],
        }

        new_group = {
            'group_id': _GroupIdGen.next_id(),
            'act_data': new_act_data,
            'cards': selected_cards,
            'color': display_color,
            'background': None,
            'summary': None,
            'connection': None,
            'excluded': False,
        }

        # 插入到合适的位置（按第一张卡片的 sentence_index 排序）
        insert_pos = len(self._groups)
        first_idx = selected_cards[0].sentence_index
        for gi, g in enumerate(self._groups):
            if g['cards'] and g['cards'][0].sentence_index > first_idx:
                insert_pos = gi
                break
        self._groups.insert(insert_pos, new_group)

        # 清除选中状态
        self._clear_multi_selection()
        self._hide_group_btn()

        # 重新布局
        self._do_layout()
        self._expand_scene_rect()

        # 通知面板保存
        self.groups_changed.emit()

    # ==================== 右键菜单 — 句子卡片 ====================

    def _show_card_context_menu(self, card: SentenceCard, global_pos):
        """句子卡片的右键菜单"""
        menu = QMenu()
        menu.setStyleSheet(self._context_menu_style())

        # 查找卡片所在的组
        group_idx = self._find_group_of_card(card)

        if group_idx is not None:
            group = self._groups[group_idx]
            cards_in_group = group['cards']

            # 找到卡片在组内的位置
            card_pos_in_group = -1
            for i, c in enumerate(cards_in_group):
                if c.sentence_index == card.sentence_index:
                    card_pos_in_group = i
                    break

            if card_pos_in_group > 0:
                split_up_action = menu.addAction("向上拆分 (含本条及以上为一组)")
                split_up_action.triggered.connect(
                    lambda: self._split_group(group_idx, card_pos_in_group, 'up'))

            if card_pos_in_group < len(cards_in_group) - 1:
                split_down_action = menu.addAction("向下拆分 (含本条及以下为一组)")
                split_down_action.triggered.connect(
                    lambda: self._split_group(group_idx, card_pos_in_group, 'down'))

        if not menu.actions():
            hint = menu.addAction("(此卡片不在任何组中)")
            hint.setEnabled(False)

        menu.exec(global_pos)

    # ==================== 右键菜单 — 组背景 ====================

    def _show_group_context_menu(self, bg_item: ActGroupBackground, global_pos):
        """组背景的右键菜单"""
        group_idx = self._find_group_of_background(bg_item)

        if group_idx is None:
            return

        group = self._groups[group_idx]
        menu = QMenu()
        menu.setStyleSheet(self._context_menu_style())

        # 场景分析（本组）
        analyze_action = menu.addAction("场景分析（本组）")
        analyze_action.triggered.connect(lambda: self.group_analysis_requested.emit(group_idx))

        menu.addSeparator()

        if group['excluded']:
            include_action = menu.addAction("取消剔除")
            include_action.triggered.connect(lambda: self._set_group_excluded(group_idx, False))
        else:
            exclude_action = menu.addAction("剔除场景")
            exclude_action.triggered.connect(lambda: self._set_group_excluded(group_idx, True))

        menu.exec(global_pos)

    def _context_menu_style(self) -> str:
        return f"""
            QMenu {{
                background: {theme.bg_elevated()};
                border: 1px solid {theme.border()};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                color: {theme.text_primary()};
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {theme.accent()};
                color: white;
            }}
            QMenu::item:disabled {{
                color: {theme.text_tertiary()};
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme.border()};
                margin: 4px 8px;
            }}
        """

    # ==================== 拆分组 ====================

    def _split_group(self, group_idx: int, card_pos: int, direction: str):
        """
        在指定位置拆分组。
        direction='up': 含 card_pos 及以上 → A 组，以下 → B 组
        direction='down': 以上 → A 组，含 card_pos 及以下 → B 组
        """
        if group_idx < 0 or group_idx >= len(self._groups):
            return

        group = self._groups[group_idx]
        cards = group['cards']

        if direction == 'up':
            split_point = card_pos + 1
        else:  # down
            split_point = card_pos

        cards_a = cards[:split_point]
        cards_b = cards[split_point:]

        if not cards_a or not cards_b:
            return

        # 移除旧组的分析卡片和背景
        self._remove_group_analysis(group)
        if group.get('background') and group['background'].scene():
            self._canvas_scene.removeItem(group['background'])

        # 创建两个新组替代旧组
        base_color_idx = self._groups.index(group) if group in self._groups else 0

        color_a_tuple = GROUP_PRESET_COLORS[base_color_idx % len(GROUP_PRESET_COLORS)]
        color_a = QColor(color_a_tuple[1].red(), color_a_tuple[1].green(),
                         color_a_tuple[1].blue(), 80)

        color_b_tuple = GROUP_PRESET_COLORS[(base_color_idx + 1) % len(GROUP_PRESET_COLORS)]
        color_b = QColor(color_b_tuple[1].red(), color_b_tuple[1].green(),
                         color_b_tuple[1].blue(), 80)

        group_a = {
            'group_id': _GroupIdGen.next_id(),
            'act_data': {
                'title': f'{group["act_data"].get("title", "")} (上)',
                'source_sentences': [c.text for c in cards_a],
                'tags': [],
            },
            'cards': cards_a,
            'color': color_a,
            'background': None,
            'summary': None,
            'connection': None,
            'excluded': group['excluded'],
        }

        group_b = {
            'group_id': _GroupIdGen.next_id(),
            'act_data': {
                'title': f'{group["act_data"].get("title", "")} (下)',
                'source_sentences': [c.text for c in cards_b],
                'tags': [],
            },
            'cards': cards_b,
            'color': color_b,
            'background': None,
            'summary': None,
            'connection': None,
            'excluded': group['excluded'],
        }

        # 替换旧组
        idx = self._groups.index(group)
        self._groups[idx:idx + 1] = [group_a, group_b]

        # 重新布局
        self._do_layout()
        self._expand_scene_rect()
        self.groups_changed.emit()

    # ==================== 剔除 / 取消剔除 ====================

    def _set_group_excluded(self, group_idx: int, excluded: bool):
        """设置组的剔除状态"""
        if group_idx < 0 or group_idx >= len(self._groups):
            return

        group = self._groups[group_idx]
        group['excluded'] = excluded

        # 更新视觉
        if group.get('background'):
            group['background'].set_excluded(excluded)
        for card in group['cards']:
            card.set_excluded(excluded)

        # 如果剔除，移除摘要卡片
        if excluded:
            self._remove_group_analysis(group)
            self._do_layout()
            self._expand_scene_rect()

        self.exclude_changed.emit(group_idx, excluded)

    # ==================== 拖拽排序 ====================

    def _update_drag_indicator(self, card_y: float):
        """更新拖拽时的蓝色插入位置指示器"""
        # 找到最近的插入位置
        best_y = None
        for card in self._sentence_cards:
            if card is self._drag_card:
                continue
            cy = card.scenePos().y()
            if best_y is None or abs(cy - card_y) < abs(best_y - card_y):
                best_y = cy
            # 也检查卡片底部
            cy_bottom = cy + SentenceCard.CARD_HEIGHT + self.SENTENCE_SPACING / 2
            if abs(cy_bottom - card_y) < abs(best_y - card_y):
                best_y = cy_bottom

        if best_y is None:
            return

        # 创建或更新指示器
        indicator_x = self._drag_card.scenePos().x() - 5
        indicator_w = SentenceCard.CARD_WIDTH + 10

        if self._drag_indicator is None:
            self._drag_indicator = self._canvas_scene.addRect(
                QRectF(indicator_x, best_y - 1.5, indicator_w, 3),
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(0, 122, 204, 200))
            )
            self._drag_indicator.setZValue(99)
        else:
            self._drag_indicator.setRect(
                QRectF(indicator_x, best_y - 1.5, indicator_w, 3))

    def _finish_drag(self):
        """完成拖拽排序"""
        if not self._drag_card:
            return

        # 恢复卡片样式
        self._drag_card.setOpacity(1.0)
        self._drag_card.setZValue(0)

        # 确定新位置
        drag_y = self._drag_card.scenePos().y() + SentenceCard.CARD_HEIGHT / 2

        # 找到插入位置
        old_index = self._sentence_cards.index(self._drag_card)
        target_index = old_index

        for i, card in enumerate(self._sentence_cards):
            if card is self._drag_card:
                continue
            if card.scenePos().y() > drag_y:
                target_index = i
                if i > old_index:
                    target_index = i - 1
                break
            target_index = i + 1 if i >= old_index else i + 1

        # 如果位置变了，重排列表
        if target_index != old_index:
            card = self._sentence_cards.pop(old_index)
            if target_index > old_index:
                target_index = min(target_index, len(self._sentence_cards))
            self._sentence_cards.insert(target_index, card)

            # 更新所有 sentence_index
            for i, c in enumerate(self._sentence_cards):
                c.sentence_index = i

            # 更新组中的 cards 引用顺序（按 sentence_index 排序）
            for group in self._groups:
                group['cards'].sort(key=lambda c: c.sentence_index)

            # 重新布局
            self._do_layout()
            self._expand_scene_rect()
            self.groups_changed.emit()

        else:
            # 位置没变，还原到原始位置
            self._drag_card.setPos(self._drag_card_origin)

        # 清理拖拽状态
        if self._drag_indicator and self._drag_indicator.scene():
            self._canvas_scene.removeItem(self._drag_indicator)
        self._drag_indicator = None
        self._is_dragging_card = False
        self._drag_card = None
        self._drag_start_pos = None
        self._drag_card_origin = None
        self._drag_pending = False

    # ==================== 整组拖拽排序 ====================

    def _update_group_drag_indicator(self, dragging_group: dict, dy: float):
        """更新整组拖拽时的蓝色插入位置指示器（显示在组间缝隙处）"""
        if not dragging_group['cards']:
            return

        # 被拖拽组的当前中心 Y
        first_card = dragging_group['cards'][0]
        last_card = dragging_group['cards'][-1]
        group_center_y = (first_card.scenePos().y() +
                          last_card.scenePos().y() + SentenceCard.CARD_HEIGHT) / 2

        # 收集其他组的背景边界，找到最近的组间缝隙
        gaps = []  # (y_position, insert_before_index)
        prev_bottom = None
        insert_idx = 0
        for gi, g in enumerate(self._groups):
            if gi == self._drag_group_idx:
                continue
            if not g['cards'] or not g.get('background'):
                continue
            bg_rect = g['background'].path().boundingRect()
            # 组顶部缝隙
            gap_y = bg_rect.top() - self.GROUP_GAP / 2
            gaps.append((gap_y, insert_idx))
            insert_idx += 1
            prev_bottom = bg_rect.bottom()

        # 最后一个组的底部缝隙
        if prev_bottom is not None:
            gaps.append((prev_bottom + self.GROUP_GAP / 2, insert_idx))

        if not gaps:
            return

        # 找到离组中心最近的缝隙
        best_gap = min(gaps, key=lambda g: abs(g[0] - group_center_y))
        best_gap_y = best_gap[0]

        indicator_x = first_card.scenePos().x() - 5
        indicator_w = SentenceCard.CARD_WIDTH + 10

        if self._drag_indicator is None:
            self._drag_indicator = self._canvas_scene.addRect(
                QRectF(indicator_x, best_gap_y - 2, indicator_w, 4),
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(0, 122, 204, 200))
            )
            self._drag_indicator.setZValue(99)
        else:
            self._drag_indicator.setRect(
                QRectF(indicator_x, best_gap_y - 2, indicator_w, 4))

    def _finish_group_drag(self):
        """完成整组拖拽排序"""
        if self._drag_group_idx < 0 or self._drag_group_idx >= len(self._groups):
            self._cleanup_group_drag()
            return

        group = self._groups[self._drag_group_idx]

        # 恢复透明度
        for card in group['cards']:
            card.setOpacity(1.0)
        if group.get('background'):
            group['background'].setOpacity(1.0)
        if group.get('summary'):
            group['summary'].setOpacity(1.0)
        if group.get('connection'):
            group['connection'].setOpacity(1.0)

        if not group['cards']:
            self._cleanup_group_drag()
            return

        # 被拖拽组的当前中心 Y
        first_card = group['cards'][0]
        last_card = group['cards'][-1]
        group_center_y = (first_card.scenePos().y() +
                          last_card.scenePos().y() + SentenceCard.CARD_HEIGHT) / 2

        old_idx = self._drag_group_idx

        # 构建其他组的中心 Y 列表（保留它们在 _groups 中的顺序）
        # other_seq 是 pop(old_idx) 后的组序列
        other_seq = []
        for gi, g in enumerate(self._groups):
            if gi == old_idx:
                continue
            if g['cards'] and g.get('background'):
                bg_rect = g['background'].path().boundingRect()
                other_seq.append(bg_rect.center().y())
            else:
                other_seq.append(float('inf'))

        # 在 other_seq 中找到插入位置
        insert_pos = len(other_seq)  # 默认放到末尾
        for i, cy in enumerate(other_seq):
            if group_center_y < cy:
                insert_pos = i
                break

        # 检查是否真的移动了（pop 后 insert_pos 对应的位置）
        # old_idx pop 后，insert_pos 就是新位置
        # 如果 insert_pos == old_idx，位置没变
        if insert_pos == old_idx:
            # 位置没变，还原
            for i, card in enumerate(group['cards']):
                if i < len(self._drag_group_origins):
                    card.setPos(self._drag_group_origins[i])
            if group.get('background') and self._drag_group_bg_origin:
                group['background'].setPos(self._drag_group_bg_origin)
            if group.get('summary') and self._drag_group_summary_origin:
                group['summary'].setPos(self._drag_group_summary_origin)
        else:
            moved = self._groups.pop(old_idx)
            insert_pos = max(0, min(insert_pos, len(self._groups)))
            self._groups.insert(insert_pos, moved)

            # 同步 _sentence_cards 顺序：按组顺序重排
            new_order = []
            grouped_set = set()
            for g in self._groups:
                for c in g['cards']:
                    new_order.append(c)
                    grouped_set.add(id(c))
            for c in self._sentence_cards:
                if id(c) not in grouped_set:
                    new_order.append(c)
            self._sentence_cards = new_order

            # 更新所有 sentence_index
            for i, c in enumerate(self._sentence_cards):
                c.sentence_index = i

            # 重新布局
            self._do_layout()
            self._expand_scene_rect()
            self.groups_changed.emit()

        self._cleanup_group_drag()

    def _cleanup_group_drag(self):
        """清理整组拖拽状态"""
        if self._drag_indicator and self._drag_indicator.scene():
            self._canvas_scene.removeItem(self._drag_indicator)
        self._drag_indicator = None
        self._is_dragging_group = False
        self._drag_group_idx = -1
        self._drag_group_start_pos = None
        self._drag_group_origins.clear()
        self._drag_group_bg_origin = None
        self._drag_group_summary_origin = None
        self._drag_group_pending = False

    # ==================== 辅助方法 ====================

    def _find_group_of_card(self, card: SentenceCard) -> Optional[int]:
        """返回卡片所属组的索引，未分组返回 None"""
        for gi, group in enumerate(self._groups):
            for c in group['cards']:
                if c.sentence_index == card.sentence_index:
                    return gi
        return None

    def _find_group_of_background(self, bg_item: ActGroupBackground) -> Optional[int]:
        """返回组背景对应的组索引"""
        for gi, group in enumerate(self._groups):
            if group.get('background') is bg_item:
                return gi
        return None

    def _remove_group_analysis(self, group: dict):
        """移除组的摘要卡片和连线"""
        if group.get('summary') and group['summary'].scene():
            self._canvas_scene.removeItem(group['summary'])
        group['summary'] = None

        if group.get('connection') and group['connection'].scene():
            self._canvas_scene.removeItem(group['connection'])
        group['connection'] = None

        # 清除分析数据
        group['act_data']['tags'] = []
        group.pop('_has_analysis', None)

    def _deselect_all(self):
        self._multi_selected.clear()
        for card in self._sentence_cards:
            card.set_selected(False)
        for group in self._groups:
            if group.get('summary'):
                group['summary'].set_selected(False)
        self._hide_group_btn()

    def _clear_multi_selection(self):
        """清除多选高亮"""
        self._multi_selected.clear()
        for card in self._sentence_cards:
            card.set_selected(False)

    # ==================== 数据导出（供面板层持久化） ====================

    def get_groups_data_for_save(self) -> List[Dict[str, Any]]:
        """将当前分组数据导出为可持久化的格式"""
        result = []
        for gi, group in enumerate(self._groups):
            cards = group['cards']
            if not cards:
                continue

            act_data = dict(group['act_data'])

            # 计算 source_text_range（基于成员卡片的原文坐标）
            if cards:
                start = min(c.original_start for c in cards)
                end = max(c.original_end for c in cards)
                act_data['source_text_range'] = [start, end]
            act_data['source_sentences'] = [c.text for c in cards]
            act_data['is_skipped'] = group['excluded']

            result.append(act_data)
        return result

    def get_group_text(self, group_index: int) -> str:
        """获取指定组的合并文本"""
        if 0 <= group_index < len(self._groups):
            return ''.join(c.text for c in self._groups[group_index]['cards'])
        return ''

    def get_group_count(self) -> int:
        return len(self._groups)

    def is_group_excluded(self, group_index: int) -> bool:
        if 0 <= group_index < len(self._groups):
            return self._groups[group_index]['excluded']
        return False

    # ==================== 清理 ====================

    def _clear_groups(self):
        """清除分组数据（保留句子卡片）"""
        for group in self._groups:
            if group.get('connection') and group['connection'].scene():
                self._canvas_scene.removeItem(group['connection'])
            if group.get('background') and group['background'].scene():
                self._canvas_scene.removeItem(group['background'])
            if group.get('summary') and group['summary'].scene():
                self._canvas_scene.removeItem(group['summary'])
        self._groups.clear()

        # 重置句子卡片的分组状态
        for card in self._sentence_cards:
            card.act_group_id = None
            card._group_color = None
            card._is_excluded = False
            card.update()

    def clear_all(self):
        """清空所有内容"""
        self._clear_groups()
        self._clear_multi_selection()
        self._hide_group_btn()

        for card in self._sentence_cards:
            if card.scene():
                self._canvas_scene.removeItem(card)
        self._sentence_cards.clear()

    def get_sentence_count(self) -> int:
        return len(self._sentence_cards)

    def _reset_view_to_origin(self):
        """将视图重置到内容左上角，确保句子卡片从左上角开始可见"""
        self.resetTransform()
        self._zoom_factor = 1.0
        if self._sentence_cards:
            # 让第一张卡片出现在视口左上角附近
            first = self._sentence_cards[0]
            top_left = QPointF(first.pos().x() - 10, first.pos().y() - 10)
            self.centerOn(top_left)
            # 微调：把 top_left 对齐到视口左上角
            vp_center = self.mapToScene(self.viewport().rect().center())
            vp_tl = self.mapToScene(self.viewport().rect().topLeft())
            offset = vp_center - vp_tl
            self.centerOn(top_left + offset)


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
#  ActSequenceCanvasPanel — 包装面板
# ============================================================

class ActSequenceCanvasPanel(QWidget):
    """
    大场景序列面板 — 画布 + 浮动按钮。
    对外接口与旧 ActSequencePanel 保持一致。
    """

    act_selected = pyqtSignal(int)  # act_id
    maximize_requested = pyqtSignal()
    restore_requested = pyqtSignal()

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self._project_id = None
        self._split_worker = None
        self._tag_worker = None
        self._source_text = ""
        self._current_acts_data = []  # 当前已拆分的场次数据（用于场景分析）
        self._is_maximized = False

        self._init_ui()
        self._connect_canvas_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 无限画布
        self._canvas = ActSequenceCanvasView()
        layout.addWidget(self._canvas, 1)

        # === 浮动导入按钮组（右上角 第1行）===
        self._import_float = QWidget(self)
        import_layout = QHBoxLayout(self._import_float)
        import_layout.setContentsMargins(10, 6, 10, 6)
        import_layout.setSpacing(8)

        self._import_txt_btn = QPushButton("TXT")
        self._import_txt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_txt_btn.clicked.connect(lambda: self._import_file("txt"))
        import_layout.addWidget(self._import_txt_btn)

        self._import_docx_btn = QPushButton("Word")
        self._import_docx_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_docx_btn.clicked.connect(lambda: self._import_file("docx"))
        import_layout.addWidget(self._import_docx_btn)

        self._import_pdf_btn = QPushButton("PDF")
        self._import_pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_pdf_btn.clicked.connect(lambda: self._import_file("pdf"))
        import_layout.addWidget(self._import_pdf_btn)

        self._paste_btn = QPushButton("粘贴")
        self._paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._paste_btn.clicked.connect(self._paste_text)
        import_layout.addWidget(self._paste_btn)

        self._import_float.adjustSize()
        self._import_float.raise_()

        # === 浮动拆分按钮组（右上角 第2行，在导入栏下方）===
        self._split_float = QWidget(self)
        split_layout = QHBoxLayout(self._split_float)
        split_layout.setContentsMargins(10, 6, 10, 6)
        split_layout.setSpacing(8)

        self._ai_split_btn = QPushButton("场景拆分")
        self._ai_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_split_btn.clicked.connect(self._ai_split)
        split_layout.addWidget(self._ai_split_btn)

        self._quick_split_btn = QPushButton("快速拆分")
        self._quick_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._quick_split_btn.clicked.connect(self._quick_split)
        split_layout.addWidget(self._quick_split_btn)

        self._scene_analysis_btn = QPushButton("场景分析")
        self._scene_analysis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scene_analysis_btn.setEnabled(False)
        self._scene_analysis_btn.clicked.connect(self._scene_analysis)
        split_layout.addWidget(self._scene_analysis_btn)

        self._status_label = QLabel("")
        self._status_label.setFont(QFont("Arial", 10))
        split_layout.addWidget(self._status_label)

        self._split_float.adjustSize()
        self._split_float.raise_()

        # === 放大按钮（左上角）===
        self._maximize_btn = _ExpandBtn(self)
        self._maximize_btn.clicked.connect(self._on_maximize_clicked)
        self._maximize_btn.raise_()

    def _connect_canvas_signals(self):
        self._canvas.act_card_clicked.connect(self._on_act_clicked)
        self._canvas.group_analysis_requested.connect(self._on_single_analysis)
        self._canvas.groups_changed.connect(self._on_groups_changed)
        self._canvas.exclude_changed.connect(self._on_exclude_changed)

    def _on_act_clicked(self, act_id: int):
        self.act_selected.emit(act_id)

    def _on_maximize_clicked(self):
        if self._is_maximized:
            self.restore_requested.emit()
        else:
            self.maximize_requested.emit()

    def set_maximized(self, maximized: bool):
        self._is_maximized = maximized
        self._maximize_btn.set_expanded(maximized)

    # ==================== 外部接口 ====================

    def set_project_id(self, project_id: int):
        self._project_id = project_id

    def load_acts(self, acts_data: list):
        """加载场次列表 — 先加载源文本句子，再应用分组"""
        # 获取源文本
        source = self._get_source_text()
        if source and not self._canvas.get_sentence_count():
            self._canvas.load_source_text(source)
            self._source_text = source

        if acts_data:
            self._current_acts_data = acts_data
            # 检查是否已有分析结果（tags 非空），如有则显示摘要卡片
            has_analysis = any(a.get('tags') for a in acts_data)
            if has_analysis:
                self._canvas.apply_act_groups(acts_data)
            else:
                self._canvas.apply_grouping_only(acts_data)
            self._status_label.setText(f"{len(acts_data)} 个场次")
            # 已有拆分数据 → 启用场景分析
            self._scene_analysis_btn.setEnabled(True)

    # ==================== 导入操作 ====================

    def _import_file(self, file_type: str):
        import os
        filters = {
            "txt": "文本文件 (*.txt);;所有文件 (*.*)",
            "docx": "Word文档 (*.docx);;所有文件 (*.*)",
            "pdf": "PDF文档 (*.pdf);;所有文件 (*.*)",
        }
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "", filters.get(file_type, "所有文件 (*.*)")
        )
        if not file_path:
            return

        try:
            from services.scene.processor import SceneProcessor
            content = SceneProcessor.parse_file(file_path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法读取文件: {e}")
            return

        if not content.strip():
            QMessageBox.warning(self, "导入失败", "文件内容为空")
            return

        # 用文件名（去扩展名）作为项目名
        project_name = os.path.splitext(os.path.basename(file_path))[0]
        self._on_text_loaded(content, "story", project_name)

    def _paste_text(self):
        """弹出粘贴对话框：顶部输入项目名 + 文本粘贴区 + 确定按钮"""
        dlg = QDialog(self)
        dlg.setWindowTitle("粘贴文本")
        dlg.setMinimumSize(500, 400)

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(16, 16, 16, 16)

        # 项目名输入
        name_row = QHBoxLayout()
        name_label = QLabel("项目名称：")
        name_input = QLineEdit()
        name_input.setPlaceholderText("输入项目名称...")
        name_row.addWidget(name_label)
        name_row.addWidget(name_input, 1)
        dlg_layout.addLayout(name_row)

        # 文本粘贴区
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("在此粘贴文本内容...")
        # 自动填入剪贴板内容
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clip_text = clipboard.text()
        if clip_text and clip_text.strip():
            text_edit.setPlainText(clip_text)
        dlg_layout.addWidget(text_edit, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        dlg_layout.addLayout(btn_row)

        # 样式
        dlg.setStyleSheet(f"""
            QDialog {{ background: {theme.bg_primary()}; }}
            QLabel {{ color: {theme.text_primary()}; font-size: 13px; }}
            QLineEdit {{
                background: {theme.bg_secondary()}; color: {theme.text_primary()};
                border: 1px solid {theme.border()}; border-radius: 6px;
                padding: 6px 10px; font-size: 13px;
            }}
            QTextEdit {{
                background: {theme.bg_secondary()}; color: {theme.text_primary()};
                border: 1px solid {theme.border()}; border-radius: 6px;
                padding: 8px; font-size: 13px;
            }}
            QPushButton {{
                background: {theme.btn_bg()}; color: {theme.text_primary()};
                border: 1px solid {theme.border()}; border-radius: 6px;
                padding: 6px 20px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {theme.btn_bg_hover()}; }}
        """)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.accent()}; color: white;
                border: none; border-radius: 6px;
                padding: 6px 20px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {theme.accent_hover()}; }}
        """)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        text = text_edit.toPlainText()
        if not text or not text.strip():
            QMessageBox.information(self, "提示", "文本内容为空")
            return

        project_name = name_input.text().strip()
        if not project_name:
            # 未填写则从文本取前30字
            first_line = text.strip().split('\n')[0].strip()
            project_name = re.sub(r'[。！？.!?\s]+$', '', first_line)[:30]
        if not project_name:
            project_name = "粘贴项目"

        self._on_text_loaded(text, "story", project_name)

    def _on_text_loaded(self, content: str, source_type: str,
                        project_name: str = ""):
        """文本加载后：保存 + 显示句子卡片 + 更新项目名"""
        self._save_source_content(content, source_type)
        self._source_text = content
        self._canvas.load_source_text(content)
        count = self._canvas.get_sentence_count()
        self._status_label.setText(f"已导入 {len(content)} 字 / {count} 句")
        # 更新项目名称
        if project_name:
            self._update_project_name(project_name)

    def _save_source_content(self, content: str, source_type: str):
        if self.data_hub and self._project_id:
            self.data_hub.save_source_content(self._project_id, content, source_type)
            self.data_hub.project_info['source_content'] = content
            self.data_hub.project_info['source_type'] = source_type

    def _update_project_name(self, name: str):
        """更新项目名称到数据库，并通知顶部导航栏"""
        if not self.data_hub or not self._project_id or not name:
            return
        from services.controllers.project_controller import ProjectController
        ProjectController().update_project(self._project_id, name=name)
        self.data_hub.project_info['name'] = name
        self.data_hub.project_name_changed.emit(name)

    # ==================== 拆分操作 ====================

    def _get_source_text(self) -> str:
        if self._source_text:
            return self._source_text
        if self.data_hub:
            return self.data_hub.get_source_content()
        return ""

    def _ai_split(self):
        text = self._get_source_text()
        if not text:
            QMessageBox.warning(self, "提示", "请先导入文案")
            return

        self._ai_split_btn.setEnabled(False)
        self._quick_split_btn.setEnabled(False)
        self._status_label.setText("AI 拆分中...")

        from services.ai_analyzer import StoryActSplitWorker
        self._split_worker = StoryActSplitWorker(text)
        self._split_worker.split_completed.connect(self._on_ai_split_completed)
        self._split_worker.split_failed.connect(self._on_split_failed)
        self._split_worker.start()

    def _quick_split(self):
        text = self._get_source_text()
        if not text:
            QMessageBox.warning(self, "提示", "请先导入文案")
            return

        from services.scene.processor import SceneProcessor
        act_candidates = SceneProcessor.parse_plain_text_to_acts(text)

        if not act_candidates:
            QMessageBox.warning(self, "提示", "无法拆分文本")
            return

        act_data_list = []
        for item in act_candidates:
            act_data_list.append({
                'title': item.get('title', ''),
                'summary': item.get('text', '')[:100],
                'source_text_range': [item.get('start_char', 0), item.get('end_char', 0)],
                'rhythm_label': '',
                'tags': [],
            })

        self._save_acts(act_data_list)

    def _on_ai_split_completed(self, acts: list):
        self._ai_split_btn.setEnabled(True)
        self._quick_split_btn.setEnabled(True)
        self._save_acts(acts)

    def _on_split_failed(self, error: str):
        self._ai_split_btn.setEnabled(True)
        self._quick_split_btn.setEnabled(True)
        self._status_label.setText(f"拆分失败: {error}")

    def _save_acts(self, act_data_list: list):
        if not self.data_hub or not self._project_id:
            self._status_label.setText("保存失败: 未关联项目")
            return

        results = self.data_hub.act_controller.create_acts_from_ai(
            self._project_id, act_data_list
        )
        self._current_acts_data = results
        # 拆分阶段：仅分组（组背景+颜色条），不出摘要卡片
        source = self._get_source_text()
        if source and not self._canvas.get_sentence_count():
            self._canvas.load_source_text(source)
            self._source_text = source
        self._canvas.apply_grouping_only(results)
        self._status_label.setText(f"已拆分为 {len(results)} 个场次")
        # 场景拆分完成 → 启用"场景分析"按钮
        self._scene_analysis_btn.setEnabled(True)

    # ==================== 场景分析 ====================

    def _scene_analysis(self):
        """对已拆分的场次进行爆点/情绪/冲突分析（跳过已剔除的组）"""
        if not self._current_acts_data and self._canvas.get_group_count() == 0:
            QMessageBox.warning(self, "提示", "请先进行场景拆分")
            return

        self._scene_analysis_btn.setEnabled(False)
        self._status_label.setText("场景分析中...")

        # 从画布获取最新分组数据
        groups_data = self._canvas.get_groups_data_for_save()
        if not groups_data:
            # 退回到旧数据
            groups_data = self._current_acts_data

        # 为每个 act 补充原文 text 字段（从 source_text_range 提取），跳过剔除的组
        source = self._get_source_text()
        enriched = []
        enriched_indices = []  # 记录在原始列表中的索引
        for i, act in enumerate(groups_data):
            if act.get('is_skipped'):
                continue
            act_copy = dict(act)
            if 'text' not in act_copy and source:
                rng = act_copy.get('source_text_range')
                if rng and len(rng) == 2:
                    act_copy['text'] = source[rng[0]:rng[1]]
                elif act_copy.get('source_sentences'):
                    act_copy['text'] = ''.join(act_copy['source_sentences'])
            enriched.append(act_copy)
            enriched_indices.append(i)

        if not enriched:
            self._scene_analysis_btn.setEnabled(True)
            self._status_label.setText("所有场次均已剔除")
            return

        from services.ai_analyzer import ActTagAnalysisWorker
        self._tag_worker = ActTagAnalysisWorker(enriched)
        self._tag_worker._enriched_indices = enriched_indices
        self._tag_worker._groups_data = groups_data
        self._tag_worker.analysis_completed.connect(self._on_tag_analysis_completed)
        self._tag_worker.analysis_failed.connect(self._on_tag_analysis_failed)
        self._tag_worker.start()

    def _on_tag_analysis_completed(self, tag_results: list):
        self._scene_analysis_btn.setEnabled(True)
        self._status_label.setText("场景分析完成")

        # 获取关联的索引映射
        enriched_indices = getattr(self._tag_worker, '_enriched_indices', [])
        groups_data = getattr(self._tag_worker, '_groups_data', self._current_acts_data)

        # 将标签和摘要写回场次数据
        for tag_item in tag_results:
            act_idx = tag_item.get('act_index', -1)
            if 0 <= act_idx < len(enriched_indices):
                real_idx = enriched_indices[act_idx]
            elif 0 <= act_idx < len(groups_data):
                real_idx = act_idx
            else:
                continue

            if real_idx >= len(groups_data):
                continue

            tags = tag_item.get('tags', [])
            groups_data[real_idx]['tags'] = tags
            for key in ('summary', 'emotion', 'emotion_detail',
                        'explosion_detail', 'conflict_detail'):
                if tag_item.get(key):
                    groups_data[real_idx][key] = tag_item[key]

        self._current_acts_data = groups_data

        # 持久化更新
        if self.data_hub and self._project_id:
            self.data_hub.act_controller.update_acts_tags(
                self._project_id, self._current_acts_data
            )

        # 场景分析完成 → 显示摘要卡片+曲线
        self._canvas.apply_act_groups(self._current_acts_data)

    def _on_tag_analysis_failed(self, error: str):
        self._scene_analysis_btn.setEnabled(True)
        self._status_label.setText(f"场景分析失败: {error}")

    # ==================== 单组分析 ====================

    def _on_single_analysis(self, group_index: int):
        """对单个组进行场景分析"""
        text = self._canvas.get_group_text(group_index)
        if not text:
            return

        self._status_label.setText(f"分析第 {group_index + 1} 组...")

        act_data = {'text': text, 'act_index': 0}

        from services.ai_analyzer import ActTagAnalysisWorker
        worker = ActTagAnalysisWorker([act_data])
        worker._target_group_index = group_index

        def on_done(results):
            self._status_label.setText("单组分析完成")
            if results:
                result = results[0]
                self._canvas.update_single_group_analysis(group_index, result)
                # 同步到 _current_acts_data
                self._current_acts_data = self._canvas.get_groups_data_for_save()
                # 持久化
                if self.data_hub and self._project_id:
                    self.data_hub.act_controller.create_acts_from_ai(
                        self._project_id, self._current_acts_data
                    )

        def on_fail(err):
            self._status_label.setText(f"分析失败: {err}")

        worker.analysis_completed.connect(on_done)
        worker.analysis_failed.connect(on_fail)
        self._tag_worker = worker
        worker.start()

    # ==================== 分组变化持久化 ====================

    def _on_groups_changed(self):
        """画布分组发生变化时，持久化保存"""
        groups_data = self._canvas.get_groups_data_for_save()
        self._current_acts_data = groups_data

        if self.data_hub and self._project_id and groups_data:
            self.data_hub.act_controller.create_acts_from_ai(
                self._project_id, groups_data
            )

        count = self._canvas.get_group_count()
        self._status_label.setText(f"{count} 个场次")
        self._scene_analysis_btn.setEnabled(count > 0)

    # ==================== 剔除持久化 ====================

    def _on_exclude_changed(self, group_index: int, excluded: bool):
        """剔除/取消剔除时持久化"""
        # 更新 _current_acts_data
        self._current_acts_data = self._canvas.get_groups_data_for_save()

        if self.data_hub and self._project_id:
            # 全量更新（简单可靠）
            self.data_hub.act_controller.create_acts_from_ai(
                self._project_id, self._current_acts_data
            )

    # ==================== 布局定位 ====================

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_floats()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_floats()

    def _position_floats(self):
        # 导入按钮 → 顶部居中 第1行
        self._import_float.adjustSize()
        iw = self._import_float.sizeHint().width()
        ih = self._import_float.sizeHint().height()
        self._import_float.setGeometry((self.width() - iw) // 2, 8, iw, ih)

        # 拆分按钮 → 顶部居中 第2行（紧接在导入栏下方）
        self._split_float.adjustSize()
        sw = self._split_float.sizeHint().width()
        sh = self._split_float.sizeHint().height()
        split_y = 8 + ih + 4  # 导入栏底部 + 间距
        self._split_float.setGeometry((self.width() - sw) // 2, split_y, sw, sh)

        # 放大按钮 → 左上角
        self._maximize_btn.move(8, 8)

    # ==================== 主题 ====================

    def apply_theme(self):
        self._status_label.setStyleSheet(
            f"color: {theme.text_tertiary()}; background: transparent;"
        )

        btn_style = theme.float_btn_style()
        self._import_txt_btn.setStyleSheet(btn_style)
        self._import_docx_btn.setStyleSheet(btn_style)
        self._import_pdf_btn.setStyleSheet(btn_style)
        self._paste_btn.setStyleSheet(btn_style)
        self._quick_split_btn.setStyleSheet(btn_style)

        accent_btn_style = f"""
            QPushButton {{
                background-color: {theme.accent()}; color: white;
                border: none; border-radius: 8px;
                padding: 6px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
            QPushButton:disabled {{ background-color: {theme.bg_tertiary()}; color: {theme.text_tertiary()}; }}
        """
        self._ai_split_btn.setStyleSheet(accent_btn_style)

        self._scene_analysis_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #8b5cf6; color: white;
                border: none; border-radius: 8px;
                padding: 6px 14px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #7c3aed; }}
            QPushButton:disabled {{ background-color: {theme.bg_tertiary()}; color: {theme.text_tertiary()}; }}
        """)

        # 浮动面板背景
        float_bg = theme.bg_elevated()
        float_style = f"""
            background: {float_bg};
            border: 1px solid {theme.border()};
            border-radius: 10px;
        """
        self._import_float.setStyleSheet(float_style)
        self._split_float.setStyleSheet(float_style)

        self._maximize_btn.update()
