"""
涛割 - 区域交互委托
BaseZoneDelegate / ActSequenceZoneDelegate / ShotRhythmZoneDelegate
/ CharacterPropZoneDelegate / AssetRequirementZoneDelegate
从原有的 ActSequenceCanvasView 和 ShotRhythmCanvasView 中提取交互逻辑，
适配 ZoneFrame 容器坐标体系。
"""

import re
from typing import Optional, List, Dict, Any, Set

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QMenu, QFileDialog, QMessageBox,
    QGraphicsRectItem, QGraphicsPathItem, QGraphicsProxyWidget,
    QGraphicsItem, QGraphicsScene, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QFontMetrics, QAction,
)

from ui import theme
from ui.components.canvas_mode import GROUP_PRESET_COLORS

# 从 act_sequence_panel.py 复用这些类（不删除，只新增委托）
from .act_sequence_panel import (
    SentenceCard, ActSummaryCard, ActGroupBackground,
    split_text_to_sentences, split_text_to_sentence_spans, _GroupIdGen,
    DRAG_THRESHOLD,
)
from .shot_rhythm_panel import ShotCanvasCard, ActSectionHeader, CollapsedShotCard
from .character_prop_zone import CharacterCanvasCard, PropCanvasCard
from .unified_story_canvas import ZoneFrame, TITLE_BAR_HEIGHT


# ============================================================
#  辅助函数
# ============================================================

def _tags_has_content(tags) -> bool:
    """判断 tags 是否有实质内容（兼容 list 和 dict 两种格式）"""
    if isinstance(tags, dict):
        labels = tags.get('labels', [])
        return bool(labels) or any(
            tags.get(k) for k in ('emotion', 'emotion_detail',
                                   'explosion_detail', 'conflict_detail')
        )
    if isinstance(tags, list):
        return len(tags) > 0
    return False


def _extract_tags_labels(tags) -> list:
    """从 tags 中提取标签列表（兼容 list 和 dict 两种格式）"""
    if isinstance(tags, dict):
        return tags.get('labels', [])
    if isinstance(tags, list):
        return tags
    return []


def _extract_tags_detail(tags, key: str) -> str:
    """从 tags dict 中提取 detail 字段"""
    if isinstance(tags, dict):
        return tags.get(key, '')
    return ''


# ============================================================
#  BaseZoneDelegate — 区域交互委托基类
# ============================================================

class BaseZoneDelegate(QObject):
    """区域交互委托基类"""

    def __init__(self, zone_frame: ZoneFrame, scene: QGraphicsScene,
                 data_hub, view, parent=None):
        super().__init__(parent)
        self._zone = zone_frame
        self._scene = scene
        self.data_hub = data_hub
        self._view = view  # UnifiedStoryCanvasView

        # 鼠标交互状态
        self._mouse_active = False

    def is_mouse_active(self) -> bool:
        return self._mouse_active

    def handle_mouse_press(self, scene_pos: QPointF, event, item):
        pass

    def handle_mouse_move(self, scene_pos: QPointF, event):
        pass

    def handle_mouse_release(self, scene_pos: QPointF, event):
        self._mouse_active = False

    def handle_context_menu(self, scene_pos: QPointF, event, item):
        pass

    def layout_items(self):
        """重新布局区域内所有子项"""
        pass

    def apply_theme(self):
        """刷新主题 — 子类按需覆写"""
        pass


# ============================================================
#  ActSequenceZoneDelegate — 大场景序列区委托
# ============================================================

class ActSequenceZoneDelegate(BaseZoneDelegate):
    """
    大场景序列区交互委托。
    从 ActSequenceCanvasView + ActSequenceCanvasPanel 中迁移全部逻辑。
    """

    act_clicked = pyqtSignal(int)       # act_id
    groups_changed = pyqtSignal()       # 分组变化
    analysis_completed = pyqtSignal()   # 场景分析完成（启用下游按钮）
    single_act_shot_requested = pyqtSignal(int)  # act_id — 请求单场景分镜化
    analysis_progress = pyqtSignal(int, int)     # (done, total) — 场景分析进度
    summary_selection_changed = pyqtSignal()     # 场景卡（摘要卡）选中变化

    # 布局常量
    SENTENCE_X = 8
    SENTENCE_X_GROUPED = 8        # 有分析时句子也在左侧（不再偏移到右侧）
    SENTENCE_SPACING = 4
    SUMMARY_ABOVE_OFFSET = 70     # 场景卡距组背景顶部的间距（向上伸出）
    CURVE_GAP = 90
    GROUP_GAP = 30
    GROUP_X_GAP = 40              # 组之间的水平间距（横向排列）
    MAX_VISIBLE_CARDS = 10        # 每组最多同时显示的卡片数

    def __init__(self, zone_frame: ZoneFrame, scene: QGraphicsScene,
                 data_hub, view, parent=None):
        super().__init__(zone_frame, scene, data_hub, view, parent)

        self._project_id: Optional[int] = None
        self._source_text = ""
        self._current_acts_data: list = []
        self._split_worker = None
        self._tag_worker = None
        self._selected_act_id: Optional[int] = None

        self._sentence_cards: List[SentenceCard] = []
        self._groups: List[Dict[str, Any]] = []

        # 多选状态
        self._multi_selected: Set[int] = set()

        # 场景卡（摘要卡）多选
        self._selected_summary_ids: Set[int] = set()  # 选中的 act_ids

        # 框选状态
        self._is_rubber_banding = False
        self._rubber_band_start: Optional[QPointF] = None
        self._rubber_band_rect_item: Optional[QGraphicsRectItem] = None

        # 打组按钮
        self._group_btn: Optional[QPushButton] = None

        # 单卡片拖拽排序
        self._is_dragging_card = False
        self._drag_card: Optional[SentenceCard] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._drag_card_origin: Optional[QPointF] = None
        self._drag_indicator: Optional[QGraphicsRectItem] = None
        self._drag_pending = False

        # 整组拖拽排序
        self._is_dragging_group = False
        self._drag_group_idx: int = -1
        self._drag_group_start_pos: Optional[QPointF] = None
        self._drag_group_origins: List[QPointF] = []
        self._drag_group_bg_origin: Optional[QPointF] = None
        self._drag_group_summary_origin: Optional[QPointF] = None
        self._drag_group_pending = False

        # 对齐 Zone 2 时保存的各组 X 坐标（由 _do_layout(group_x_positions=...) 设置）
        # 后续无参 _do_layout() 调用会自动复用，保持与 Zone 2 的对齐
        self._aligned_x_positions: Optional[Dict[int, float]] = None

    # ==================== 外部接口 ====================

    def set_project_id(self, project_id: int):
        self._project_id = project_id

    def get_group_count(self) -> int:
        return len(self._groups)

    def get_selected_summary_card(self) -> Optional[ActSummaryCard]:
        """获取当前选中的摘要卡片"""
        for group in self._groups:
            if group.get('summary') and group['summary']._selected:
                return group['summary']
        return None

    def get_selected_background(self) -> Optional[ActGroupBackground]:
        """获取当前选中 act 对应的组背景（用于无摘要卡片时的跨区域连线源）"""
        if self._selected_act_id is None:
            return None
        for group in self._groups:
            if group['act_data'].get('id') == self._selected_act_id:
                return group.get('background')
        return None

    def load_acts(self, acts_data: list):
        """加载场次列表"""
        source = self._get_source_text()
        if source and not self._sentence_cards:
            self._load_source_text(source)
            self._source_text = source

        if acts_data:
            self._current_acts_data = acts_data
            has_analysis = any(
                _tags_has_content(a.get('tags')) or a.get('summary')
                for a in acts_data
            )
            if has_analysis:
                self._apply_act_groups(acts_data)
            else:
                self._apply_grouping_only(acts_data)
            self._zone.set_status(f"{len(acts_data)} 个场次")

    # ==================== 标题栏按钮回调 ====================

    def import_file(self):
        """导入文件"""
        import os
        filters = "文本文件 (*.txt);;Word文档 (*.docx);;PDF文档 (*.pdf);;所有文件 (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self._view, "选择文件", "", filters
        )
        if not file_path:
            return

        try:
            from services.scene.processor import SceneProcessor
            content = SceneProcessor.parse_file(file_path)
        except Exception as e:
            QMessageBox.warning(self._view, "导入失败", f"无法读取文件: {e}")
            return

        if not content.strip():
            QMessageBox.warning(self._view, "导入失败", "文件内容为空")
            return

        project_name = os.path.splitext(os.path.basename(file_path))[0]
        self._on_text_loaded(content, "story", project_name)

    def ai_split(self):
        """AI 场景拆分"""
        text = self._get_source_text()
        if not text:
            QMessageBox.warning(self._view, "提示", "请先导入文案")
            return

        self._zone.set_status("AI 拆分中...")

        from services.ai_analyzer import StoryActSplitWorker
        self._split_worker = StoryActSplitWorker(text)
        self._split_worker.split_completed.connect(self._on_ai_split_completed)
        self._split_worker.split_failed.connect(self._on_split_failed)
        self._split_worker.start()

    def quick_split(self):
        """快速拆分"""
        text = self._get_source_text()
        if not text:
            QMessageBox.warning(self._view, "提示", "请先导入文案")
            return

        from services.scene.processor import SceneProcessor
        act_candidates = SceneProcessor.parse_plain_text_to_acts(text)
        if not act_candidates:
            QMessageBox.warning(self._view, "提示", "无法拆分文本")
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

    def scene_analysis(self):
        """场景分析"""
        if not self._current_acts_data and len(self._groups) == 0:
            QMessageBox.warning(self._view, "提示", "请先进行场景拆分")
            return

        self._zone.set_status("场景分析中...")
        self.analysis_progress.emit(0, 0)  # indeterminate

        groups_data = self._get_groups_data_for_save()
        if not groups_data:
            groups_data = self._current_acts_data

        source = self._get_source_text()
        enriched = []
        enriched_indices = []
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
            self._zone.set_status("所有场次均已剔除")
            return

        from services.ai_analyzer import ActTagAnalysisWorker
        self._tag_worker = ActTagAnalysisWorker(enriched)
        self._tag_worker._enriched_indices = enriched_indices
        self._tag_worker._groups_data = groups_data
        self._tag_worker.analysis_completed.connect(self._on_tag_analysis_completed)
        self._tag_worker.analysis_failed.connect(self._on_tag_analysis_failed)
        self._tag_worker.start()

    # ==================== 鼠标事件处理 ====================

    def handle_mouse_press(self, scene_pos: QPointF, event, item):
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        # ProxyWidget → 不拦截
        if isinstance(item, QGraphicsProxyWidget):
            return

        # 沿父链查找真正的卡片类型（itemAt 可能返回子项）
        resolved = item
        while resolved and not isinstance(resolved, (ActSummaryCard, SentenceCard, ActGroupBackground, ZoneFrame)):
            resolved = resolved.parentItem()

        # 摘要卡片（场景卡）— 支持 Ctrl 多选
        if isinstance(resolved, ActSummaryCard):
            act_id = resolved.act_id
            if ctrl:
                # Ctrl+点击 → 切换多选
                if act_id in self._selected_summary_ids:
                    self._selected_summary_ids.discard(act_id)
                    resolved.set_selected(False)
                else:
                    self._selected_summary_ids.add(act_id)
                    resolved.set_selected(True)
            else:
                # 单击 → 单选（清除其他摘要卡选中）
                self._deselect_all_summaries()
                self._selected_summary_ids.add(act_id)
                resolved.set_selected(True)
            self._selected_act_id = act_id
            self.act_clicked.emit(act_id)
            self.summary_selection_changed.emit()
            return

        # 句子卡片
        if isinstance(resolved, SentenceCard):
            if ctrl:
                idx = resolved.sentence_index
                if idx in self._multi_selected:
                    self._multi_selected.discard(idx)
                    resolved.set_selected(False)
                else:
                    self._multi_selected.add(idx)
                    resolved.set_selected(True)
                self._update_group_btn()
            else:
                self._drag_pending = True
                self._drag_card = resolved
                self._drag_start_pos = scene_pos
                self._drag_card_origin = resolved.pos()
                if resolved.sentence_index not in self._multi_selected:
                    self._deselect_all()
                    resolved.set_selected(True)

                # 点击句子卡片时，如果该卡片属于某个组，也触发 act 选中
                group_idx = self._find_group_of_card(resolved)
                if group_idx is not None:
                    act_id = self._groups[group_idx]['act_data'].get('id', 0)
                    if act_id:
                        self._selected_act_id = act_id
                        self.act_clicked.emit(act_id)
            self._mouse_active = True
            return

        # 组背景
        if isinstance(resolved, ActGroupBackground):
            self._deselect_all()
            group_idx = self._find_group_of_background(resolved)
            if group_idx is not None:
                # 发出 act_clicked 信号，以便第二栏加载对应分镜
                group = self._groups[group_idx]
                act_id = group['act_data'].get('id', 0)
                if act_id:
                    self._selected_act_id = act_id
                    self.act_clicked.emit(act_id)

                self._drag_group_pending = True
                self._drag_group_idx = group_idx
                self._drag_group_start_pos = scene_pos
                self._drag_group_origins = [c.pos() for c in group['cards']]
                bg = group.get('background')
                self._drag_group_bg_origin = bg.pos() if bg else None
                summary = group.get('summary')
                self._drag_group_summary_origin = summary.pos() if summary else None
            self._mouse_active = True
            return

        # 空白区域 → 框选
        if not ctrl:
            self._deselect_all()
        self._is_rubber_banding = True
        self._rubber_band_start = scene_pos
        self._mouse_active = True

    def handle_mouse_move(self, scene_pos: QPointF, event):
        # 整组拖拽 pending
        if self._drag_group_pending and self._drag_group_start_pos:
            delta = scene_pos - self._drag_group_start_pos
            if abs(delta.y()) > DRAG_THRESHOLD or abs(delta.x()) > DRAG_THRESHOLD:
                self._drag_group_pending = False
                self._is_dragging_group = True
                group = self._groups[self._drag_group_idx]
                for card in group['cards']:
                    card.setOpacity(0.5)
                if group.get('background'):
                    group['background'].setOpacity(0.5)
                if group.get('summary'):
                    group['summary'].setOpacity(0.5)
                if group.get('connection'):
                    group['connection'].setOpacity(0.3)
            else:
                return

        # 整组拖拽中
        if self._is_dragging_group and self._drag_group_idx >= 0:
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
            self._update_group_drag_indicator(group, dy)
            return

        # 单卡片拖拽 pending
        if self._drag_pending and self._drag_card:
            delta = scene_pos - self._drag_start_pos
            if abs(delta.y()) > DRAG_THRESHOLD or abs(delta.x()) > DRAG_THRESHOLD:
                self._drag_pending = False
                self._is_dragging_card = True
                self._drag_card.setOpacity(0.5)
                self._drag_card.setZValue(100)
            else:
                return

        # 单卡片拖拽中
        if self._is_dragging_card and self._drag_card:
            new_y = self._drag_card_origin.y() + (scene_pos.y() - self._drag_start_pos.y())
            self._drag_card.setPos(self._drag_card_origin.x(), new_y)
            self._update_drag_indicator(new_y)
            return

        # 框选
        if self._is_rubber_banding and self._rubber_band_start is not None:
            rect = QRectF(self._rubber_band_start, scene_pos).normalized()
            if self._rubber_band_rect_item is None:
                self._rubber_band_rect_item = self._scene.addRect(
                    rect,
                    QPen(QColor(0, 122, 204, 180), 1.5, Qt.PenStyle.DashLine),
                    QBrush(QColor(0, 122, 204, 25))
                )
                self._rubber_band_rect_item.setZValue(2000)
            else:
                self._rubber_band_rect_item.setRect(rect)
            self._update_rubber_band_selection(rect)

    def handle_mouse_release(self, scene_pos: QPointF, event):
        # 整组拖拽完成
        if self._is_dragging_group:
            self._finish_group_drag()
            self._mouse_active = False
            return

        if self._drag_group_pending:
            self._drag_group_pending = False
            self._drag_group_idx = -1
            self._drag_group_start_pos = None

        # 单卡片拖拽完成
        if self._is_dragging_card and self._drag_card:
            self._finish_drag()
            self._mouse_active = False
            return

        if self._drag_pending:
            self._drag_pending = False
            self._drag_card = None
            self._drag_start_pos = None
            self._drag_card_origin = None

        # 框选完成
        if self._is_rubber_banding:
            self._is_rubber_banding = False
            if self._rubber_band_rect_item:
                if self._rubber_band_rect_item.scene():
                    self._scene.removeItem(self._rubber_band_rect_item)
                self._rubber_band_rect_item = None

            if len(self._multi_selected) >= 2:
                self._show_group_btn()
            else:
                self._hide_group_btn()

            self._rubber_band_start = None

        self._mouse_active = False

    def handle_context_menu(self, scene_pos: QPointF, event, item):
        if isinstance(item, SentenceCard):
            self._show_card_context_menu(item, event.globalPos())
            return
        if isinstance(item, ActGroupBackground):
            self._show_group_context_menu(item, event.globalPos())
            return
        if isinstance(item, ActSummaryCard):
            self._show_summary_context_menu(item, event.globalPos())
            return

    # ==================== 源文本加载 ====================

    def _load_source_text(self, text: str):
        """加载源文本为句子卡片，卡片作为 ZoneFrame 的子项"""
        self._clear_all()

        spans = split_text_to_sentence_spans(text)
        content_y = TITLE_BAR_HEIGHT + 20

        for i, (sent_text, start, end) in enumerate(spans):
            card = SentenceCard(i, sent_text)
            card.original_start = start
            card.original_end = end

            # 设为 ZoneFrame 子项
            card.setParentItem(self._zone)
            card.setPos(self.SENTENCE_X, content_y)
            self._sentence_cards.append(card)
            content_y += card.rect().height() + self.SENTENCE_SPACING

        # 自适应 ZoneFrame 大小
        self._zone.auto_fit_content(self._sentence_cards)

    def _on_text_loaded(self, content: str, source_type: str, project_name: str = ""):
        self._save_source_content(content, source_type)
        self._source_text = content
        self._load_source_text(content)
        count = len(self._sentence_cards)
        self._zone.set_status(f"已导入 {len(content)} 字 / {count} 句")
        if project_name:
            self._update_project_name(project_name)

    def _save_source_content(self, content: str, source_type: str):
        if self.data_hub and self._project_id:
            self.data_hub.save_source_content(self._project_id, content, source_type)
            self.data_hub.project_info['source_content'] = content
            self.data_hub.project_info['source_type'] = source_type

    def _update_project_name(self, name: str):
        if not self.data_hub or not self._project_id or not name:
            return
        from services.controllers.project_controller import ProjectController
        ProjectController().update_project(self._project_id, name=name)
        self.data_hub.project_info['name'] = name
        self.data_hub.project_name_changed.emit(name)

    def _get_source_text(self) -> str:
        if self._source_text:
            return self._source_text
        if self.data_hub:
            return self.data_hub.get_source_content()
        return ""

    # ==================== 分组 ====================

    def _apply_grouping_only(self, acts_data: list):
        self._clear_groups()
        if not self._sentence_cards or not acts_data:
            return
        self._build_groups_from_acts(acts_data, with_summary=False)
        self._do_layout()

    def _apply_act_groups(self, acts_data: list):
        """场景分析完成后：更新分析数据 + 重新布局。
        如果分组已存在（场景化时已创建），不重新分配卡片到组，
        只更新每组的 act_data（tags/summary），然后重新布局。
        这避免 _sync_group_ranges_to_data_hub 修改过的边界导致
        第二次分组时卡片分配不均。
        """
        if self._groups and len(self._groups) == len(acts_data):
            # 分组已存在且数量匹配 → 就地更新 act_data，不重新分组
            for gi, group in enumerate(self._groups):
                act_data = acts_data[gi]
                act_data_copy = dict(act_data)
                act_data_copy['source_sentences'] = [c.text for c in group['cards']]

                # 从 dict 格式 tags 中提取 detail 字段到顶层
                raw_tags = act_data_copy.get('tags')
                if isinstance(raw_tags, dict):
                    for key in ('emotion', 'emotion_detail',
                                'explosion_detail', 'conflict_detail'):
                        if raw_tags.get(key) and not act_data_copy.get(key):
                            act_data_copy[key] = raw_tags[key]

                group['act_data'] = act_data_copy
                group['excluded'] = bool(act_data.get('is_skipped', False))
            self._do_layout()
        else:
            # 首次加载或组数不匹配 → 全量重建
            self._clear_groups()
            if not self._sentence_cards or not acts_data:
                return
            self._build_groups_from_acts(acts_data, with_summary=True)
            self._do_layout()

    def _build_groups_from_acts(self, acts_data: list, with_summary: bool = False):
        """按原文顺序将句子卡片拆分到各场景组。

        核心原则：原文顺序不可改变。句子按 sentence_index 从前到后遍历，
        用每个 act 的 range_start 作为边界点依次切分，保证每组内的句子
        是原文中连续的一段。
        """
        self._groups = []
        self._aligned_x_positions = None  # 新分组时清除旧对齐位置
        total_cards = len(self._sentence_cards)
        if not total_cards or not acts_data:
            return

        # ── 按原文顺序排列所有句子卡片 ──
        sorted_cards = sorted(self._sentence_cards, key=lambda c: c.sentence_index)

        # ── 收集每个 act 的 range_start 作为边界 ──
        act_starts = []
        for act_data in acts_data:
            tr = act_data.get('source_text_range', [])
            if tr and len(tr) == 2:
                act_starts.append(tr[0])
            else:
                act_starts.append(None)

        has_ranges = any(s is not None for s in act_starts)

        # ── 分配句子到各组 ──
        groups_cards: list[list] = [[] for _ in acts_data]

        if has_ranges:
            # 边界拆分：按顺序遍历句子，用下一个 act 的 range_start
            # 作为推进边界。句子永远只会往后走，不会回退，保证原文顺序。
            act_ptr = 0
            for card in sorted_cards:
                card_mid = (card.original_start + card.original_end) / 2.0
                # 尝试推进到下一个 act
                while act_ptr < len(acts_data) - 1:
                    next_start = act_starts[act_ptr + 1]
                    if next_start is not None and card_mid >= next_start:
                        act_ptr += 1
                    elif next_start is None:
                        # 跳过没有范围的 act
                        act_ptr += 1
                    else:
                        break
                groups_cards[act_ptr].append(card)
        else:
            # 完全没有范围信息 → 按顺序均分
            per_act = max(1, total_cards // len(acts_data))
            for ci, card in enumerate(sorted_cards):
                act_idx = min(ci // per_act, len(acts_data) - 1)
                groups_cards[act_idx].append(card)

        # ── 构建分组数据 ──
        for act_idx, act_data in enumerate(acts_data):
            cards = groups_cards[act_idx]

            if not cards:
                print(f"[涛割] 警告: 场次 {act_idx} (id={act_data.get('id')}) "
                      f"未分配到任何句子卡片, range={act_data.get('source_text_range')}")

            act_data_copy = dict(act_data)
            act_data_copy['source_sentences'] = [c.text for c in cards]

            # 从 dict 格式 tags 中提取 detail 字段到顶层，供 ActSummaryCard 读取
            raw_tags = act_data_copy.get('tags')
            if isinstance(raw_tags, dict):
                for key in ('emotion', 'emotion_detail',
                            'explosion_detail', 'conflict_detail'):
                    if raw_tags.get(key) and not act_data_copy.get(key):
                        act_data_copy[key] = raw_tags[key]

            color_tuple = GROUP_PRESET_COLORS[act_idx % len(GROUP_PRESET_COLORS)]
            color = color_tuple[1]
            display_color = QColor(color.red(), color.green(), color.blue(), 80)

            has_analysis = with_summary and _tags_has_content(act_data.get('tags'))

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

        # ── 用实际卡片范围更新 source_text_range ──
        # 边界拆分可能将序幕/间隙句子合并到相邻组，
        # 需要将 source_text_range 更新为组内卡片的真实范围，
        # 确保后续 AI 拆分分镜时能取到完整文本。
        self._sync_group_ranges_to_data_hub()

    def _sync_group_ranges_to_data_hub(self):
        """将分组内卡片的实际文本范围同步回 act_data 和 data_hub.acts_data。"""
        for group in self._groups:
            cards = group['cards']
            if not cards:
                continue
            actual_start = min(c.original_start for c in cards)
            actual_end = max(c.original_end for c in cards)
            group['act_data']['source_text_range'] = [actual_start, actual_end]
            group['act_data']['source_sentences'] = [c.text for c in cards]

        # 同步到 data_hub.acts_data，使 Zone 2 能获取到完整文本范围
        if self.data_hub and self.data_hub.acts_data:
            # 按 act_id 匹配更新
            hub_acts_map = {}
            for a in self.data_hub.acts_data:
                aid = a.get('id')
                if aid is not None:
                    hub_acts_map[aid] = a

            for group in self._groups:
                act_id = group['act_data'].get('id')
                if act_id is not None and act_id in hub_acts_map:
                    hub_acts_map[act_id]['source_text_range'] = \
                        group['act_data']['source_text_range']

    def _do_layout(self, group_x_positions: dict = None):
        """统一布局：分组后横向排列，所有组背景统一高度，场景卡在组上方。

        Args:
            group_x_positions: 可选的 {group_index: x} 字典，
                用于对齐 Zone 2 时指定每组的自定义 X 坐标。
                未提供时自动复用上次保存的对齐位置（如果组数匹配）。
        """
        # 保存/复用对齐位置
        if group_x_positions is not None:
            self._aligned_x_positions = dict(group_x_positions)
        elif (self._aligned_x_positions is not None
              and len(self._aligned_x_positions) == len(self._groups)):
            group_x_positions = self._aligned_x_positions
        # 清理旧视觉元素
        for group in self._groups:
            if group.get('background') and group['background'].scene():
                self._scene.removeItem(group['background'])
            group['background'] = None
            if group.get('summary') and group['summary'].scene():
                self._scene.removeItem(group['summary'])
            group['summary'] = None
            if group.get('connection') and group['connection'].scene():
                self._scene.removeItem(group['connection'])
            group['connection'] = None

        grouped_indices = set()
        for group in self._groups:
            for c in group['cards']:
                grouped_indices.add(c.sentence_index)

        sentence_x = self.SENTENCE_X
        padding = ActGroupBackground.PADDING
        content_top = TITLE_BAR_HEIGHT + 20

        if not self._groups:
            # 未分组的句子竖向排列
            y_off = content_top
            for card in self._sentence_cards:
                card.setVisible(True)
                card.setPos(sentence_x, y_off)
                y_off += card.rect().height() + self.SENTENCE_SPACING
            self._zone.auto_fit_content(self._sentence_cards)
            if self._zone._on_resized_callback:
                self._zone._on_resized_callback()
            return

        # ══════════════════════════════════════════════════
        #  第一轮：定位每组的可见卡片，记录每组的实际内容高度
        # ══════════════════════════════════════════════════
        max_visible = self.MAX_VISIBLE_CARDS
        group_layout_info = []   # [(x, visible_cards, total, vis_start, vis_end, content_h)]
        x_offset = sentence_x

        for gi, group in enumerate(self._groups):
            # 使用自定义 X 坐标（对齐 Zone 2 时）或顺序排列
            if group_x_positions and gi in group_x_positions:
                gx = group_x_positions[gi]
            else:
                gx = x_offset

            cards = group['cards']
            color = group['color']
            excluded = group['excluded']

            if not cards:
                group_layout_info.append((gx, [], 0, 0, 0, 0))
                x_offset = gx + SentenceCard.CARD_WIDTH + self.GROUP_X_GAP
                continue

            # 滚动偏移
            if 'scroll_offset' not in group:
                group['scroll_offset'] = 0
            scroll_offset = group['scroll_offset']
            total_cards = len(cards)
            visible_start = min(scroll_offset, max(0, total_cards - max_visible))
            visible_end = min(visible_start + max_visible, total_cards)

            # 定位可见卡片
            y_off = content_top
            for ci, card in enumerate(cards):
                if visible_start <= ci < visible_end:
                    card.setVisible(True)
                    card.setPos(gx, y_off)
                    card.set_group(group['group_id'], color)
                    card.set_excluded(excluded)
                    y_off += card.rect().height() + self.SENTENCE_SPACING
                else:
                    card.setVisible(False)
                    card.set_group(group['group_id'], color)
                    card.set_excluded(excluded)

            content_h = y_off - content_top  # 可见卡片的实际堆叠高度
            visible_cards = cards[visible_start:visible_end]
            group_layout_info.append((gx, visible_cards, total_cards,
                                      visible_start, visible_end, content_h))
            x_offset = gx + SentenceCard.CARD_WIDTH + self.GROUP_X_GAP

        # ══════════════════════════════════════════════════
        #  计算统一的组背景高度 = 所有组中最高的那个
        # ══════════════════════════════════════════════════
        max_content_h = max((info[5] for info in group_layout_info), default=0)
        # 至少能容纳一张最小高度的卡片
        min_bg_h = SentenceCard.CARD_MIN_HEIGHT + self.SENTENCE_SPACING
        uniform_content_h = max(max_content_h, min_bg_h)
        uniform_bg_h = uniform_content_h + padding * 2

        # ══════════════════════════════════════════════════
        #  第二轮：创建统一高度的组背景 + 摘要卡片
        # ══════════════════════════════════════════════════
        for gi, group in enumerate(self._groups):
            info = group_layout_info[gi]
            gx, visible_cards, total_cards, vis_start, vis_end, _ = info
            color = group['color']
            excluded = group['excluded']

            bg = ActGroupBackground(group['group_id'], color)
            bg.set_excluded(excluded)
            bg.setParentItem(self._zone)

            # 统一高度的背景矩形
            bg_rect = QRectF(
                gx - padding,
                content_top - padding,
                SentenceCard.CARD_WIDTH + padding * 2,
                uniform_bg_h,
            )
            bg_path = QPainterPath()
            bg_path.addRoundedRect(bg_rect, ActGroupBackground.CORNER_RADIUS,
                                   ActGroupBackground.CORNER_RADIUS)
            bg.setPath(bg_path)
            bg.set_scroll_info(total_cards, vis_start, len(visible_cards))
            group['background'] = bg

            # 摘要卡片（在组上方）
            act_data = group['act_data']
            if _tags_has_content(act_data.get('tags')) and not excluded:
                summary_card = ActSummaryCard(gi, act_data, color)
                summary_card.setParentItem(self._zone)
                summary_x = bg_rect.center().x() - ActSummaryCard.CARD_WIDTH / 2
                summary_y = bg_rect.top() - self.SUMMARY_ABOVE_OFFSET - summary_card.rect().height()
                summary_card.setPos(summary_x, summary_y)
                group['summary'] = summary_card

                conn = self._create_connection(summary_card, bg, color)
                group['connection'] = conn

        # 未分组的句子（保持竖向排列在最左侧）
        y_offset_ungrouped = content_top
        for card in self._sentence_cards:
            if card.sentence_index not in grouped_indices:
                card.setPos(sentence_x, y_offset_ungrouped)
                card.act_group_id = None
                card._group_color = None
                card._is_excluded = False
                card.update()
                y_offset_ungrouped += card.rect().height() + self.SENTENCE_SPACING

        # ══════════════════════════════════════════════════
        #  ZoneFrame 紧贴组背景 — 只用背景+摘要计算大小
        # ══════════════════════════════════════════════════
        fit_items = []
        for g in self._groups:
            if g.get('background'):
                fit_items.append(g['background'])
            if g.get('summary'):
                fit_items.append(g['summary'])
        if fit_items:
            self._zone.auto_fit_content(fit_items)

        # 确保最小宽度包含所有组的横向排列
        if self._groups and group_layout_info:
            # 使用实际布局信息计算右边缘（兼容自定义 X 位置）
            max_right = max(info[0] + SentenceCard.CARD_WIDTH
                            for info in group_layout_info)
            min_width = max_right + 10
            current = self._zone.rect()
            if current.width() < min_width:
                self._zone.setRect(0, 0, min_width, current.height())

        # 通知 Zone 尺寸变化（触发 Zone 2/3 位置自适应）
        if self._zone._on_resized_callback:
            self._zone._on_resized_callback()

    def scroll_group(self, group_id: int, delta: int):
        """滚轮翻页组内卡片。delta > 0 表示向上滚（显示前面的卡片）。"""
        for group in self._groups:
            if group['group_id'] == group_id:
                cards = group['cards']
                total = len(cards)
                if total <= self.MAX_VISIBLE_CARDS:
                    return  # 不需要滚动
                old_offset = group.get('scroll_offset', 0)
                # delta > 0 → 向上翻（offset 减小）
                new_offset = old_offset - delta
                new_offset = max(0, min(new_offset, total - self.MAX_VISIBLE_CARDS))
                if new_offset != old_offset:
                    group['scroll_offset'] = new_offset
                    self._do_layout()
                return

    def find_group_by_background(self, bg_item) -> Optional[int]:
        """根据 ActGroupBackground 实例找到对应的 group_id"""
        for group in self._groups:
            if group.get('background') is bg_item:
                return group['group_id']
        return None

    def _create_connection(self, summary_card: ActSummaryCard,
                           group_bg: ActGroupBackground,
                           color: QColor) -> QGraphicsPathItem:
        # 所有项都是 ZoneFrame 子项，使用局部坐标
        # 连线方向：组背景顶部中点 → 摘要卡片底部中点（垂直，从下到上）
        group_rect = group_bg.path().boundingRect()
        summary_rect = summary_card.mapRectToItem(
            self._zone, summary_card.boundingRect()
        )

        # 从组背景顶部中点到摘要卡片底部中点
        start = QPointF(
            group_rect.center().x(),
            group_rect.top()
        )
        end = QPointF(
            summary_rect.center().x(),
            summary_rect.bottom()
        )

        offset = abs(end.y() - start.y()) * 0.5
        ctrl1 = QPointF(start.x(), start.y() - offset)
        ctrl2 = QPointF(end.x(), end.y() + offset)

        path = QPainterPath(start)
        path.cubicTo(ctrl1, ctrl2, end)

        line_item = QGraphicsPathItem()
        brighter = QColor(color.red(), color.green(), color.blue(), 140)
        pen = QPen(brighter, 1.5)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_item.setPen(pen)
        line_item.setPath(path)
        line_item.setZValue(-5)
        line_item.setParentItem(self._zone)
        return line_item

    def _rebuild_zone1_connections(self):
        """重建 Zone 1 内部的场景卡到组背景之间的虚线连接"""
        for group in self._groups:
            # 移除旧连线
            if group.get('connection') and group['connection'].scene():
                self._scene.removeItem(group['connection'])
            group['connection'] = None

            summary = group.get('summary')
            bg = group.get('background')
            color = group.get('color', QColor(100, 100, 100))
            excluded = group.get('excluded', False)

            if summary and bg and not excluded:
                conn = self._create_connection(summary, bg, color)
                group['connection'] = conn

    # ==================== AI 拆分回调 ====================

    def _on_ai_split_completed(self, acts: list):
        self._save_acts(acts)

    def _on_split_failed(self, error: str):
        self._zone.set_status(f"拆分失败: {error}")

    def _fill_uncovered_text(self, act_data_list: list) -> list:
        """检测 AI 拆分是否遗漏了原文开头或结尾，自动补全。

        AI 场景拆分可能从原文中间开始（跳过序幕/背景介绍），
        也可能提前结束（遗漏结尾段落）。
        此方法检测这些空洞并插入独立的序幕/尾声 act，
        确保整篇原文都有对应的 act，后续 AI 拆分分镜时不会遗漏。
        """
        if not act_data_list:
            return act_data_list

        source = self._get_source_text()
        if not source:
            return act_data_list

        source_len = len(source)

        # 找到第一个和最后一个有效 range
        first_start = None
        last_end = None
        for a in act_data_list:
            tr = a.get('source_text_range', [])
            if tr and len(tr) == 2:
                if first_start is None or tr[0] < first_start:
                    first_start = tr[0]
                if last_end is None or tr[1] > last_end:
                    last_end = tr[1]

        if first_start is None:
            return act_data_list

        result = list(act_data_list)

        # ── 序幕检测 ──
        # 如果第一个 act 不从原文开头开始，且遗漏的文本足够长（>10字符）
        MIN_GAP = 10
        if first_start > MIN_GAP:
            prologue_text = source[:first_start].strip()
            if prologue_text:
                prologue_act = {
                    'title': '序幕',
                    'summary': prologue_text[:100],
                    'source_text_range': [0, first_start],
                    'rhythm_label': '',
                    'tags': [],
                }
                result.insert(0, prologue_act)

        # ── 尾声检测 ──
        if last_end is not None and source_len - last_end > MIN_GAP:
            epilogue_text = source[last_end:].strip()
            if epilogue_text:
                epilogue_act = {
                    'title': '尾声',
                    'summary': epilogue_text[:100],
                    'source_text_range': [last_end, source_len],
                    'rhythm_label': '',
                    'tags': [],
                }
                result.append(epilogue_act)

        return result

    def _save_acts(self, act_data_list: list):
        if not self.data_hub or not self._project_id:
            self._zone.set_status("保存失败: 未关联项目")
            return

        # ── 补全序幕/尾声 ──
        # AI 拆分可能跳过原文开头或结尾的文本。
        # 检测遗漏并自动插入序幕/尾声 act，确保整篇原文都被覆盖。
        act_data_list = self._fill_uncovered_text(act_data_list)

        results = self.data_hub.act_controller.create_acts_from_ai(
            self._project_id, act_data_list
        )
        self._current_acts_data = results

        # 同步刷新 data_hub.acts_data，确保第二栏能通过 act_id 找到场次
        self.data_hub.acts_data = results

        source = self._get_source_text()
        if source and not self._sentence_cards:
            self._load_source_text(source)
            self._source_text = source

        self._apply_grouping_only(results)
        self._zone.set_status(f"已拆分为 {len(results)} 个场次")
        self.groups_changed.emit()

    # ==================== 场景分析回调 ====================

    def _on_tag_analysis_completed(self, tag_results: list):
        self._zone.set_status("场景分析完成")

        enriched_indices = getattr(self._tag_worker, '_enriched_indices', [])
        groups_data = getattr(self._tag_worker, '_groups_data', self._current_acts_data)

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

            # 构造 tags 为 dict 格式，包含 labels + detail 字段
            raw_labels = tag_item.get('tags', [])
            tags_dict = {
                'labels': raw_labels if isinstance(raw_labels, list) else [],
            }
            for key in ('emotion', 'emotion_detail',
                        'explosion_detail', 'conflict_detail'):
                if tag_item.get(key):
                    tags_dict[key] = tag_item[key]

            groups_data[real_idx]['tags'] = tags_dict

            # summary 作为顶层字段保留
            if tag_item.get('summary'):
                groups_data[real_idx]['summary'] = tag_item['summary']

            # 同时保留顶层 emotion/detail 字段供 ActSummaryCard 直接读取
            for key in ('emotion', 'emotion_detail',
                        'explosion_detail', 'conflict_detail'):
                if tag_item.get(key):
                    groups_data[real_idx][key] = tag_item[key]

        self._current_acts_data = groups_data

        if self.data_hub and self._project_id:
            self.data_hub.act_controller.update_acts_tags(
                self._project_id, self._current_acts_data
            )
            # 同步刷新 data_hub.acts_data
            self.data_hub.acts_data = self._current_acts_data

        # ── 将分析结果直接注入到现有分组中，不重新分配卡片 ──
        if self._groups:
            # 构建 groups_data 的 act_id → data 映射
            gd_by_id = {}
            for gd in groups_data:
                aid = gd.get('id')
                if aid is not None:
                    gd_by_id[aid] = gd

            for group in self._groups:
                act_id = group['act_data'].get('id')
                matched_data = gd_by_id.get(act_id) if act_id is not None else None
                if matched_data:
                    act_data_copy = dict(matched_data)
                    act_data_copy['source_sentences'] = [c.text for c in group['cards']]
                    # 从 dict 格式 tags 中提取 detail 字段到顶层
                    raw_tags = act_data_copy.get('tags')
                    if isinstance(raw_tags, dict):
                        for key in ('emotion', 'emotion_detail',
                                    'explosion_detail', 'conflict_detail'):
                            if raw_tags.get(key) and not act_data_copy.get(key):
                                act_data_copy[key] = raw_tags[key]
                    group['act_data'] = act_data_copy
                    group['excluded'] = bool(matched_data.get('is_skipped', False))

            self._do_layout()
        else:
            # 没有现有分组（不应该发生，但做兜底）
            self._apply_act_groups(self._current_acts_data)

        self.analysis_completed.emit()
        self.analysis_progress.emit(1, 1)  # 完成

    def _on_tag_analysis_failed(self, error: str):
        self._zone.set_status(f"场景分析失败: {error}")
        self.analysis_progress.emit(1, 1)  # 失败也结束进度

    # ==================== 框选 + 打组 ====================

    def _update_rubber_band_selection(self, rect: QRectF):
        self._multi_selected.clear()
        for card in self._sentence_cards:
            if rect.intersects(card.sceneBoundingRect()):
                self._multi_selected.add(card.sentence_index)
                card.set_selected(True)
            else:
                card.set_selected(False)

    def _show_group_btn(self):
        self._hide_group_btn()
        bounds = self._get_multi_selected_bounds()
        if bounds is None:
            return

        self._group_btn = QPushButton("打组", self._view.viewport())
        self._group_btn.setFixedSize(60, 28)
        self._group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._group_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()}; color: white;
                border: none; border-radius: 6px;
                font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
        """)
        self._group_btn.clicked.connect(self._on_create_group)

        center_scene = bounds.center()
        top_scene = QPointF(center_scene.x(), bounds.top() - 40)
        vp_pos = self._view.mapFromScene(top_scene)
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
        if len(self._multi_selected) >= 2:
            self._show_group_btn()
        else:
            self._hide_group_btn()

    def _get_multi_selected_bounds(self) -> Optional[QRectF]:
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
                    max_y = max(max_y, pos.y() + card.rect().height())
                    break
        if min_x == float('inf'):
            return None
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def _on_create_group(self):
        if len(self._multi_selected) < 2:
            return

        # Undo: 拍摄 before 快照
        if hasattr(self._view, '_undo_manager'):
            self._view._undo_manager.begin_operation("手动打组")

        selected_indices = sorted(self._multi_selected)
        selected_cards = []
        for idx in selected_indices:
            for card in self._sentence_cards:
                if card.sentence_index == idx:
                    selected_cards.append(card)
                    break

        if len(selected_cards) < 2:
            return

        groups_to_remove = []
        for gi, group in enumerate(self._groups):
            original_count = len(group['cards'])
            group['cards'] = [c for c in group['cards']
                              if c.sentence_index not in self._multi_selected]
            if len(group['cards']) != original_count:
                self._remove_group_analysis(group)
            if not group['cards']:
                groups_to_remove.append(gi)

        for gi in reversed(groups_to_remove):
            group = self._groups[gi]
            if group.get('background') and group['background'].scene():
                self._scene.removeItem(group['background'])
            self._groups.pop(gi)

        color_idx = len(self._groups) % len(GROUP_PRESET_COLORS)
        color_tuple = GROUP_PRESET_COLORS[color_idx]
        display_color = QColor(color_tuple[1].red(), color_tuple[1].green(),
                               color_tuple[1].blue(), 80)

        source_sentences = [c.text for c in selected_cards]
        new_act_data = {
            'title': f'手动分组 {len(self._groups) + 1}',
            'source_sentences': source_sentences,
            'tags': {},
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

        insert_pos = len(self._groups)
        first_idx = selected_cards[0].sentence_index
        for gi, g in enumerate(self._groups):
            if g['cards'] and g['cards'][0].sentence_index > first_idx:
                insert_pos = gi
                break
        self._groups.insert(insert_pos, new_group)

        self._clear_multi_selection()
        self._hide_group_btn()
        self._do_layout()
        self.groups_changed.emit()

    # ==================== 右键菜单 ====================

    def _show_card_context_menu(self, card: SentenceCard, global_pos):
        menu = QMenu()
        menu.setStyleSheet(self._context_menu_style())
        group_idx = self._find_group_of_card(card)

        if group_idx is not None:
            group = self._groups[group_idx]
            cards_in_group = group['cards']
            card_pos_in_group = -1
            for i, c in enumerate(cards_in_group):
                if c.sentence_index == card.sentence_index:
                    card_pos_in_group = i
                    break

            if card_pos_in_group > 0:
                split_up = menu.addAction("向上拆分 (含本条及以上为一组)")
                split_up.triggered.connect(
                    lambda: self._split_group(group_idx, card_pos_in_group, 'up'))

            if card_pos_in_group < len(cards_in_group) - 1:
                split_down = menu.addAction("向下拆分 (含本条及以下为一组)")
                split_down.triggered.connect(
                    lambda: self._split_group(group_idx, card_pos_in_group, 'down'))

        if not menu.actions():
            hint = menu.addAction("(此卡片不在任何组中)")
            hint.setEnabled(False)

        menu.exec(global_pos)

    def _show_group_context_menu(self, bg_item: ActGroupBackground, global_pos):
        group_idx = self._find_group_of_background(bg_item)
        if group_idx is None:
            return

        group = self._groups[group_idx]
        act_id = group.get('act_data', {}).get('id')
        menu = QMenu()
        menu.setStyleSheet(self._context_menu_style())

        analyze_action = menu.addAction("场景分析（本组）")
        analyze_action.triggered.connect(lambda: self._on_single_analysis(group_idx))

        if act_id:
            shot_action = menu.addAction("分镜化（本场景）")
            shot_action.triggered.connect(
                lambda: self.single_act_shot_requested.emit(act_id))

        menu.addSeparator()

        if group['excluded']:
            include_action = menu.addAction("取消剔除")
            include_action.triggered.connect(
                lambda: self._set_group_excluded(group_idx, False))
        else:
            exclude_action = menu.addAction("剔除场景")
            exclude_action.triggered.connect(
                lambda: self._set_group_excluded(group_idx, True))

        menu.exec(global_pos)

    def _show_summary_context_menu(self, card: ActSummaryCard, global_pos):
        """摘要卡片（场景卡）右键菜单"""
        act_id = card.act_id
        group_idx = None
        for i, g in enumerate(self._groups):
            if g.get('summary') is card:
                group_idx = i
                break

        menu = QMenu()
        menu.setStyleSheet(self._context_menu_style())

        if group_idx is not None:
            analyze_action = menu.addAction("重新分析（本组）")
            analyze_action.triggered.connect(lambda: self._on_single_analysis(group_idx))

        if act_id:
            shot_action = menu.addAction("分镜化（本场景）")
            shot_action.triggered.connect(
                lambda: self.single_act_shot_requested.emit(act_id))

        if not menu.actions():
            hint = menu.addAction("(无可用操作)")
            hint.setEnabled(False)

        menu.exec(global_pos)

    def _context_menu_style(self) -> str:
        return f"""
            QMenu {{
                background: {theme.bg_elevated()};
                border: 1px solid {theme.border()};
                border-radius: 8px; padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px; color: {theme.text_primary()};
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background: {theme.accent()}; color: white;
            }}
            QMenu::item:disabled {{ color: {theme.text_tertiary()}; }}
            QMenu::separator {{
                height: 1px; background: {theme.border()}; margin: 4px 8px;
            }}
        """

    # ==================== 拆分组 ====================

    def _split_group(self, group_idx: int, card_pos: int, direction: str):
        if group_idx < 0 or group_idx >= len(self._groups):
            return

        # Undo: 拍摄 before 快照
        if hasattr(self._view, '_undo_manager'):
            self._view._undo_manager.begin_operation("拆分组")

        group = self._groups[group_idx]
        cards = group['cards']

        if direction == 'up':
            split_point = card_pos + 1
        else:
            split_point = card_pos

        cards_a = cards[:split_point]
        cards_b = cards[split_point:]
        if not cards_a or not cards_b:
            return

        self._remove_group_analysis(group)
        if group.get('background') and group['background'].scene():
            self._scene.removeItem(group['background'])

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
                'tags': {},
            },
            'cards': cards_a,
            'color': color_a,
            'background': None, 'summary': None, 'connection': None,
            'excluded': group['excluded'],
        }
        group_b = {
            'group_id': _GroupIdGen.next_id(),
            'act_data': {
                'title': f'{group["act_data"].get("title", "")} (下)',
                'source_sentences': [c.text for c in cards_b],
                'tags': {},
            },
            'cards': cards_b,
            'color': color_b,
            'background': None, 'summary': None, 'connection': None,
            'excluded': group['excluded'],
        }

        idx = self._groups.index(group)
        self._groups[idx:idx + 1] = [group_a, group_b]
        self._do_layout()
        self.groups_changed.emit()

    # ==================== 剔除 ====================

    def _set_group_excluded(self, group_idx: int, excluded: bool):
        if group_idx < 0 or group_idx >= len(self._groups):
            return

        # Undo: 拍摄 before 快照 + 直接 commit（不经过 groups_changed）
        undo_mgr = getattr(self._view, '_undo_manager', None)
        if undo_mgr:
            undo_mgr.begin_operation("剔除场景" if excluded else "取消剔除")

        group = self._groups[group_idx]
        group['excluded'] = excluded

        if group.get('background'):
            group['background'].set_excluded(excluded)
        for card in group['cards']:
            card.set_excluded(excluded)

        if excluded:
            self._remove_group_analysis(group)
            self._do_layout()

        self._on_exclude_changed(group_idx, excluded)

    def _on_exclude_changed(self, group_idx: int, excluded: bool):
        self._current_acts_data = self._get_groups_data_for_save()
        if self.data_hub and self._project_id:
            self.data_hub.act_controller.create_acts_from_ai(
                self._project_id, self._current_acts_data
            )
        # Undo: 直接 commit（剔除操作不触发 groups_changed）
        undo_mgr = getattr(self._view, '_undo_manager', None)
        if undo_mgr and undo_mgr.is_operation_pending():
            undo_mgr.commit_operation()

    # ==================== 单组分析 ====================

    def _on_single_analysis(self, group_index: int):
        text = self._get_group_text(group_index)
        if not text:
            return
        self._zone.set_status(f"分析第 {group_index + 1} 组...")

        act_data = {'text': text, 'act_index': 0}
        from services.ai_analyzer import ActTagAnalysisWorker
        worker = ActTagAnalysisWorker([act_data])
        worker._target_group_index = group_index

        def on_done(results):
            self._zone.set_status("单组分析完成")
            if results:
                result = results[0]
                self._update_single_group_analysis(group_index, result)
                self._current_acts_data = self._get_groups_data_for_save()
                if self.data_hub and self._project_id:
                    self.data_hub.act_controller.create_acts_from_ai(
                        self._project_id, self._current_acts_data
                    )

        def on_fail(err):
            self._zone.set_status(f"分析失败: {err}")

        worker.analysis_completed.connect(on_done)
        worker.analysis_failed.connect(on_fail)
        self._tag_worker = worker
        worker.start()

    def _update_single_group_analysis(self, group_index: int, result: dict):
        if group_index < 0 or group_index >= len(self._groups):
            return
        group = self._groups[group_index]
        self._remove_group_analysis(group)
        act_data = group['act_data']

        # 构造 dict 格式 tags
        raw_labels = result.get('tags', [])
        tags_dict = {
            'labels': raw_labels if isinstance(raw_labels, list) else [],
        }
        for key in ('emotion', 'emotion_detail',
                    'explosion_detail', 'conflict_detail'):
            if result.get(key):
                tags_dict[key] = result[key]
        act_data['tags'] = tags_dict

        if result.get('summary'):
            act_data['summary'] = result['summary']
        for key in ('emotion', 'emotion_detail',
                     'explosion_detail', 'conflict_detail'):
            if result.get(key):
                act_data[key] = result[key]
        self._do_layout()

    # ==================== 拖拽排序 ====================

    def _update_drag_indicator(self, card_y: float):
        best_y = None
        for card in self._sentence_cards:
            if card is self._drag_card:
                continue
            cy = card.scenePos().y()
            if best_y is None or abs(cy - card_y) < abs(best_y - card_y):
                best_y = cy
            cy_bottom = cy + card.rect().height() + self.SENTENCE_SPACING / 2
            if abs(cy_bottom - card_y) < abs(best_y - card_y):
                best_y = cy_bottom
        if best_y is None:
            return

        indicator_x = self._drag_card.scenePos().x() - 5
        indicator_w = SentenceCard.CARD_WIDTH + 10
        if self._drag_indicator is None:
            self._drag_indicator = self._scene.addRect(
                QRectF(indicator_x, best_y - 1.5, indicator_w, 3),
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(0, 122, 204, 200))
            )
            self._drag_indicator.setZValue(99)
        else:
            self._drag_indicator.setRect(
                QRectF(indicator_x, best_y - 1.5, indicator_w, 3))

    def _finish_drag(self):
        if not self._drag_card:
            return

        # Undo: 拍摄 before 快照
        if hasattr(self._view, '_undo_manager'):
            self._view._undo_manager.begin_operation("拖拽排序")

        self._drag_card.setOpacity(1.0)
        self._drag_card.setZValue(0)

        drag_y = self._drag_card.scenePos().y() + self._drag_card.rect().height() / 2
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

        if target_index != old_index:
            card = self._sentence_cards.pop(old_index)
            if target_index > old_index:
                target_index = min(target_index, len(self._sentence_cards))
            self._sentence_cards.insert(target_index, card)
            for i, c in enumerate(self._sentence_cards):
                c.sentence_index = i
            for group in self._groups:
                group['cards'].sort(key=lambda c: c.sentence_index)
            self._do_layout()
            self.groups_changed.emit()
        else:
            self._drag_card.setPos(self._drag_card_origin)

        if self._drag_indicator and self._drag_indicator.scene():
            self._scene.removeItem(self._drag_indicator)
        self._drag_indicator = None
        self._is_dragging_card = False
        self._drag_card = None
        self._drag_start_pos = None
        self._drag_card_origin = None
        self._drag_pending = False

    # ==================== 整组拖拽排序 ====================

    def _update_group_drag_indicator(self, dragging_group: dict, dy: float):
        if not dragging_group['cards']:
            return
        first_card = dragging_group['cards'][0]
        last_card = dragging_group['cards'][-1]
        group_center_y = (first_card.scenePos().y() +
                          last_card.scenePos().y() + last_card.rect().height()) / 2

        gaps = []
        insert_idx = 0
        prev_bottom = None
        for gi, g in enumerate(self._groups):
            if gi == self._drag_group_idx:
                continue
            if not g['cards'] or not g.get('background'):
                continue
            bg_rect = g['background'].path().boundingRect()
            gap_y = bg_rect.top() - self.GROUP_GAP / 2
            gaps.append((gap_y, insert_idx))
            insert_idx += 1
            prev_bottom = bg_rect.bottom()

        if prev_bottom is not None:
            gaps.append((prev_bottom + self.GROUP_GAP / 2, insert_idx))

        if not gaps:
            return

        best_gap = min(gaps, key=lambda g: abs(g[0] - group_center_y))
        best_gap_y = best_gap[0]

        indicator_x = first_card.scenePos().x() - 5
        indicator_w = SentenceCard.CARD_WIDTH + 10
        if self._drag_indicator is None:
            self._drag_indicator = self._scene.addRect(
                QRectF(indicator_x, best_gap_y - 2, indicator_w, 4),
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(0, 122, 204, 200))
            )
            self._drag_indicator.setZValue(99)
        else:
            self._drag_indicator.setRect(
                QRectF(indicator_x, best_gap_y - 2, indicator_w, 4))

    def _finish_group_drag(self):
        if self._drag_group_idx < 0 or self._drag_group_idx >= len(self._groups):
            self._cleanup_group_drag()
            return

        # Undo: 拍摄 before 快照
        if hasattr(self._view, '_undo_manager'):
            self._view._undo_manager.begin_operation("拖拽组排序")

        group = self._groups[self._drag_group_idx]
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

        first_card = group['cards'][0]
        last_card = group['cards'][-1]
        group_center_y = (first_card.scenePos().y() +
                          last_card.scenePos().y() + last_card.rect().height()) / 2

        old_idx = self._drag_group_idx
        other_seq = []
        for gi, g in enumerate(self._groups):
            if gi == old_idx:
                continue
            if g['cards'] and g.get('background'):
                bg_rect = g['background'].path().boundingRect()
                other_seq.append(bg_rect.center().y())
            else:
                other_seq.append(float('inf'))

        insert_pos = len(other_seq)
        for i, cy in enumerate(other_seq):
            if group_center_y < cy:
                insert_pos = i
                break

        if insert_pos == old_idx:
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

            for i, c in enumerate(self._sentence_cards):
                c.sentence_index = i

            self._do_layout()
            self.groups_changed.emit()

        self._cleanup_group_drag()

    def _cleanup_group_drag(self):
        if self._drag_indicator and self._drag_indicator.scene():
            self._scene.removeItem(self._drag_indicator)
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
        for gi, group in enumerate(self._groups):
            for c in group['cards']:
                if c.sentence_index == card.sentence_index:
                    return gi
        return None

    def _find_group_of_background(self, bg_item: ActGroupBackground) -> Optional[int]:
        for gi, group in enumerate(self._groups):
            if group.get('background') is bg_item:
                return gi
        return None

    def _remove_group_analysis(self, group: dict):
        if group.get('summary') and group['summary'].scene():
            self._scene.removeItem(group['summary'])
        group['summary'] = None
        if group.get('connection') and group['connection'].scene():
            self._scene.removeItem(group['connection'])
        group['connection'] = None
        group['act_data']['tags'] = {}
        group.pop('_has_analysis', None)

    def _deselect_all(self):
        self._multi_selected.clear()
        self._selected_summary_ids.clear()
        for card in self._sentence_cards:
            card.set_selected(False)
        for group in self._groups:
            if group.get('summary'):
                group['summary'].set_selected(False)
        self._hide_group_btn()

    def _deselect_all_summaries(self):
        """清除所有摘要卡片的选中状态"""
        self._selected_summary_ids.clear()
        for group in self._groups:
            if group.get('summary'):
                group['summary'].set_selected(False)

    def get_selected_summary_act_ids(self) -> Set[int]:
        """获取当前选中的摘要卡片的 act_id 集合"""
        return set(self._selected_summary_ids)

    def get_all_summary_act_ids(self) -> Set[int]:
        """获取所有非剔除组的 act_id 集合"""
        result = set()
        for group in self._groups:
            if group.get('excluded'):
                continue
            act_id = group.get('act_data', {}).get('id')
            if act_id:
                result.add(act_id)
        return result

    def _clear_multi_selection(self):
        self._multi_selected.clear()
        for card in self._sentence_cards:
            card.set_selected(False)

    def _get_groups_data_for_save(self) -> List[Dict[str, Any]]:
        result = []
        for gi, group in enumerate(self._groups):
            cards = group['cards']
            act_data = dict(group['act_data'])
            if cards:
                start = min(c.original_start for c in cards)
                end = max(c.original_end for c in cards)
                act_data['source_text_range'] = [start, end]
                act_data['source_sentences'] = [c.text for c in cards]
            else:
                # 空组也保留，不跳过
                act_data.setdefault('source_sentences', [])
            act_data['is_skipped'] = group['excluded']
            result.append(act_data)
        return result

    def _get_group_text(self, group_index: int) -> str:
        if 0 <= group_index < len(self._groups):
            return ''.join(c.text for c in self._groups[group_index]['cards'])
        return ''

    def _clear_groups(self):
        for group in self._groups:
            if group.get('connection') and group['connection'].scene():
                self._scene.removeItem(group['connection'])
            if group.get('background') and group['background'].scene():
                self._scene.removeItem(group['background'])
            if group.get('summary') and group['summary'].scene():
                self._scene.removeItem(group['summary'])
        self._groups.clear()
        for card in self._sentence_cards:
            card.act_group_id = None
            card._group_color = None
            card._is_excluded = False
            card.update()

    def _clear_all(self):
        self._clear_groups()
        self._clear_multi_selection()
        self._hide_group_btn()
        for card in self._sentence_cards:
            if card.scene():
                self._scene.removeItem(card)
        self._sentence_cards.clear()

    # ==================== 分组变化持久化 ====================

    def _on_groups_changed_internal(self):
        groups_data = self._get_groups_data_for_save()
        self._current_acts_data = groups_data
        if self.data_hub and self._project_id and groups_data:
            self.data_hub.act_controller.create_acts_from_ai(
                self._project_id, groups_data
            )
        self.groups_changed.emit()

    def apply_theme(self):
        """刷新所有子项的主题"""
        for card in self._sentence_cards:
            card.update()
        for group in self._groups:
            if group.get('background'):
                group['background'].update()
            if group.get('summary'):
                group['summary'].update()
            if group.get('connection'):
                group['connection'].update()
        if self._group_btn:
            self._group_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.accent()}; color: white;
                    border: none; border-radius: 6px;
                    font-size: 12px; font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
            """)


# ============================================================
#  ShotRhythmZoneDelegate — 分镜节奏区委托（全场景模式）
# ============================================================

class ShotRhythmZoneDelegate(BaseZoneDelegate):
    """
    分镜节奏区交互委托。
    全场景模式：显示所有场次的分镜，按场次顺序从上到下排列，
    每组分镜用场景颜色标记。
    """

    shot_clicked = pyqtSignal(int)   # scene_index (全局)
    shots_changed = pyqtSignal()
    act_shot_completed = pyqtSignal(int)   # act_id — 单个场次分镜完成
    batch_progress = pyqtSignal(int, int)  # (done, total) — 批量进度
    batch_all_completed = pyqtSignal()     # 批量分镜全部完成
    generate_image_requested = pyqtSignal(int, float, float)  # scene_index, scene_x, scene_y — 请求生成图片
    generate_video_requested = pyqtSignal(int, float, float)  # scene_index, scene_x, scene_y — 请求生成视频
    smart_ps_requested = pyqtSignal(int, float, float)        # scene_index, scene_x, scene_y — 请求智能PS

    CARD_SPACING = 40
    SECTION_GAP = 60        # 场次组之间的水平间距
    GROUP_GAP = 40           # 分镜组间水平间距
    START_Y_OFFSET = 20     # 相对于 content_origin
    CARD_X = 20             # 卡片左边距（首组起始X）
    CARDS_Y = None          # 分镜卡统一 Y（在 load 时计算）

    def __init__(self, zone_frame: ZoneFrame, scene: QGraphicsScene,
                 data_hub, view, parent=None):
        super().__init__(zone_frame, scene, data_hub, view, parent)

        self._shot_cards: List[ShotCanvasCard] = []
        self._selected_global_index: Optional[int] = None
        self._current_act_id: Optional[int] = None
        self._split_worker = None

        # 批量拆分状态
        self._pending_batch: List[tuple] = []
        self._batch_total: int = 0
        self._batch_done: int = 0
        self._current_batch_act_idx: int = 0

        # 全场景模式数据
        self._all_act_ids: List[int] = []
        self._act_colors: Dict[int, QColor] = {}
        self._section_headers: List[QGraphicsRectItem] = []
        self._section_headers_map: Dict[int, QGraphicsRectItem] = {}  # act_id → header
        self._act_card_groups: Dict[int, List[ShotCanvasCard]] = {}  # act_id → cards
        self._collapsed_cards: Dict[int, CollapsedShotCard] = {}  # act_id → collapsed card

        # 框选状态
        self._is_rubber_banding = False
        self._rubber_band_start: Optional[QPointF] = None
        self._rubber_band_rect_item: Optional[QGraphicsRectItem] = None
        self._multi_selected_shots: Set[int] = set()  # 选中的 global_index 集合

    # ==================== 外部接口 ====================

    def load_act_shots(self, act_id: int):
        """加载指定场次的分镜（兼容旧接口，选中该场次卡片高亮）"""
        self._current_act_id = act_id

        # 如果已经是全场景模式且有卡片，只需高亮对应场次
        if self._shot_cards and act_id in self._act_card_groups:
            self._highlight_act_section(act_id)
            return

        # 否则尝试加载全部
        if self.data_hub and self.data_hub.acts_data:
            self.load_all_acts_shots()
        else:
            # Fallback: 只加载单场次
            if not self.data_hub:
                return
            scenes = self.data_hub.act_controller.get_act_scenes(act_id)
            if not scenes:
                self._clear_cards()
                self._zone.set_status("无分镜")
                return
            self._load_shots(scenes)
            self._zone.set_status(f"{len(scenes)} 个分镜")

    def load_all_acts_shots(self):
        """加载所有场次的分镜（全场景模式 — 所有分镜卡在同一水平行，组间有间距）

        每组占用的水平空间至少为 SentenceCard.CARD_WIDTH（600），
        分镜卡在槽位内居中，确保与 Zone 1 句子卡片的水平对齐。
        """
        if not self.data_hub:
            return

        acts_data = self.data_hub.acts_data
        if not acts_data:
            return

        self._clear_cards()

        # Zone 1 句子卡片宽度 — 每组最小占位宽度
        min_group_width = SentenceCard.CARD_WIDTH

        total_shots = 0
        has_any_shots = False

        # 所有分镜卡在同一水平 Y 行（标题栏下方固定位置）
        cards_y = TITLE_BAR_HEIGHT + self.START_Y_OFFSET
        # 从左到右横排，组间 GROUP_GAP 分隔
        x = self.CARD_X

        for act_idx, act in enumerate(acts_data):
            act_id = act.get('id')
            if not act_id:
                continue
            if act.get('is_skipped'):
                continue

            scenes = self.data_hub.act_controller.get_act_scenes(act_id)
            if not scenes:
                continue

            has_any_shots = True

            # 场次颜色
            color_tuple = GROUP_PRESET_COLORS[act_idx % len(GROUP_PRESET_COLORS)]
            act_color = QColor(color_tuple[1].red(), color_tuple[1].green(),
                               color_tuple[1].blue(), 180)
            self._act_colors[act_id] = act_color
            self._all_act_ids.append(act_id)

            # 计算该组分镜卡的实际宽度
            num_cards = len(scenes)
            actual_width = (num_cards * ShotCanvasCard.CARD_WIDTH
                            + max(0, num_cards - 1) * self.CARD_SPACING)
            slot_width = max(actual_width, min_group_width)
            # 分镜卡居中于槽位
            card_offset = (slot_width - actual_width) / 2

            group_start_x = x + card_offset

            # 分镜卡片 — 横向排列（从左到右，居中于槽位）
            act_cards = []
            cx = group_start_x
            for i, scene_data in enumerate(scenes):
                card = ShotCanvasCard(scene_data, total_shots)
                card.set_act_color(act_color)
                card._on_generate_image = self._on_card_generate_image
                card._on_generate_video = self._on_card_generate_video
                card._on_smart_ps = self._on_card_smart_ps
                card.setParentItem(self._zone)
                card.setPos(cx, cards_y)
                self._shot_cards.append(card)
                act_cards.append(card)
                cx += ShotCanvasCard.CARD_WIDTH + self.CARD_SPACING
                total_shots += 1

            self._act_card_groups[act_id] = act_cards

            # 该组分镜卡结束 X（去掉最后一个间距）
            group_end_x = cx - self.CARD_SPACING
            group_width = group_end_x - group_start_x

            # 场次标题栏 — 在分镜卡组下方居中
            header_y = cards_y + ShotCanvasCard.CARD_HEIGHT + 8
            header = self._create_section_header(
                act_idx, act.get('title', f'场次 {act_idx + 1}'),
                act_color, header_y
            )
            header.setRect(0, 0, max(ShotCanvasCard.CARD_WIDTH, group_width),
                           ActSectionHeader.HEADER_HEIGHT)
            header.setPos(group_start_x, header_y)
            self._section_headers.append(header)
            self._section_headers_map[act_id] = header

            # 组间间距（从槽位右边缘算起）
            x += slot_width + self.GROUP_GAP

        if has_any_shots:
            self._zone.set_status(f"{total_shots} 个分镜 / {len(self._all_act_ids)} 个场次")
            self._zone.auto_fit_content(self._shot_cards + self._section_headers)
        else:
            self._zone.set_status("无分镜（请先拆分）")

        # 高亮当前选中的场次
        if self._current_act_id:
            self._highlight_act_section(self._current_act_id)

    def add_act_shot_cards(self, act_id: int, scenes: list, act_idx: int):
        """逐组加载 — 生成完一组后立即追加到最右侧"""
        if not scenes:
            return

        # Zone 1 句子卡片宽度 — 每组最小占位宽度
        min_group_width = SentenceCard.CARD_WIDTH

        color_tuple = GROUP_PRESET_COLORS[act_idx % len(GROUP_PRESET_COLORS)]
        act_color = QColor(color_tuple[1].red(), color_tuple[1].green(),
                           color_tuple[1].blue(), 180)
        self._act_colors[act_id] = act_color
        if act_id not in self._all_act_ids:
            self._all_act_ids.append(act_id)

        # 分镜卡统一 Y
        cards_y = TITLE_BAR_HEIGHT + self.START_Y_OFFSET

        # X 位置：追加到最右侧（已有卡片的最大右边缘 + GROUP_GAP）
        x = self.CARD_X
        if self._shot_cards:
            max_right = max(
                c.pos().x() + c.rect().width()
                for c in self._shot_cards
            )
            x = max_right + self.GROUP_GAP

        # 计算该组分镜卡的实际宽度和槽位宽度
        num_cards = len(scenes)
        actual_width = (num_cards * ShotCanvasCard.CARD_WIDTH
                        + max(0, num_cards - 1) * self.CARD_SPACING)
        slot_width = max(actual_width, min_group_width)
        card_offset = (slot_width - actual_width) / 2

        group_start_x = x + card_offset

        # 分镜卡片 — 横向排列（居中于槽位），序号基于已有卡片总数全局递增
        global_offset = len(self._shot_cards)
        act_cards = []
        cx = group_start_x
        for i, scene_data in enumerate(scenes):
            card = ShotCanvasCard(scene_data, global_offset + i)
            card.set_act_color(act_color)
            card._on_generate_image = self._on_card_generate_image
            card._on_generate_video = self._on_card_generate_video
            card._on_smart_ps = self._on_card_smart_ps
            card.setParentItem(self._zone)
            card.setPos(cx, cards_y)
            self._shot_cards.append(card)
            act_cards.append(card)
            cx += ShotCanvasCard.CARD_WIDTH + self.CARD_SPACING

        self._act_card_groups[act_id] = act_cards

        group_end_x = cx - self.CARD_SPACING
        group_width = group_end_x - group_start_x

        # 场次标题栏 — 在分镜卡组下方居中
        header_y = cards_y + ShotCanvasCard.CARD_HEIGHT + 8
        header = self._create_section_header(
            act_idx, f'场次 {act_idx + 1}', act_color, header_y
        )
        header.setRect(0, 0, max(ShotCanvasCard.CARD_WIDTH, group_width),
                       ActSectionHeader.HEADER_HEIGHT)
        header.setPos(group_start_x, header_y)
        self._section_headers.append(header)
        self._section_headers_map[act_id] = header

        self._zone.auto_fit_content(self._shot_cards + self._section_headers)

    def _create_section_header(self, act_idx: int, title: str,
                               color: QColor, y: float) -> ActSectionHeader:
        """创建场次分隔标题栏"""
        header = ActSectionHeader(act_idx, title, color)
        header.setRect(0, 0, ShotCanvasCard.CARD_WIDTH, ActSectionHeader.HEADER_HEIGHT)
        header.setParentItem(self._zone)
        header.setPos(self.CARD_X, y)
        header.setZValue(-1)
        return header

    def _highlight_act_section(self, act_id: int):
        """高亮指定场次的卡片组"""
        # 暂不实现额外高亮，颜色竖条已足够区分
        pass

    def clear(self):
        self._current_act_id = None
        self._all_act_ids.clear()
        self._act_colors.clear()
        self._act_card_groups.clear()
        self._section_headers_map.clear()
        # 清除折叠卡片
        for cc in self._collapsed_cards.values():
            if cc.scene():
                self._scene.removeItem(cc)
        self._collapsed_cards.clear()
        self._clear_cards()
        self._zone.set_status("")

    def get_all_shot_cards(self) -> List[ShotCanvasCard]:
        return list(self._shot_cards)

    def get_act_shot_cards(self, act_id: int) -> List[ShotCanvasCard]:
        """获取指定场次的分镜卡片列表"""
        return self._act_card_groups.get(act_id, [])

    def get_selected_card(self) -> Optional[ShotCanvasCard]:
        for card in self._shot_cards:
            if card._selected:
                return card
        return None

    def relayout_after_toggle(self):
        """折叠/展开后重新布局卡片。
        展开组: 水平排列分镜卡，header 在下方。
        折叠组: 显示宽条折叠卡片，在原位占位（Y 不变，与展开卡片同行）。

        关键：每组占用的水平空间至少为 SentenceCard.CARD_WIDTH（600），
        确保 Zone 1 中的句子卡片（600宽）不会因为防重叠而偏移，
        从而保证两个 Zone 之间的水平对齐。
        """
        # Zone 1 句子卡片宽度 — 每组最小占位宽度
        min_group_width = SentenceCard.CARD_WIDTH

        cards_y = TITLE_BAR_HEIGHT + self.START_Y_OFFSET
        x = self.CARD_X

        for act_id in self._all_act_ids:
            cards = self._act_card_groups.get(act_id, [])
            visible_cards = [c for c in cards if c.isVisible()]
            header = self._section_headers_map.get(act_id)
            collapsed_card = self._collapsed_cards.get(act_id)

            if not visible_cards:
                # 该组全部折叠 → 显示折叠摘要卡片（原位占位）
                if header:
                    header.setVisible(False)

                if not collapsed_card:
                    # 创建折叠卡片
                    act_color = self._act_colors.get(act_id, QColor(100, 100, 100))
                    act_title = ""
                    if header:
                        act_title = header._title
                    total_dur = sum(c.scene_data.get('duration', 0) for c in cards)
                    collapsed_card = CollapsedShotCard(
                        act_id, act_title, len(cards),
                        total_dur, act_color, parent=self._zone
                    )
                    self._collapsed_cards[act_id] = collapsed_card

                # 折叠卡片居中于 min_group_width 槽位
                slot_width = max(CollapsedShotCard.CARD_WIDTH, min_group_width)
                card_offset = (slot_width - CollapsedShotCard.CARD_WIDTH) / 2
                collapsed_card.setVisible(True)
                collapsed_card.setPos(x + card_offset, cards_y)
                x += slot_width + self.GROUP_GAP
                continue

            # 展开状态 → 隐藏折叠卡片
            if collapsed_card:
                collapsed_card.setVisible(False)

            # 计算该组分镜卡的实际宽度
            actual_width = (len(visible_cards) * ShotCanvasCard.CARD_WIDTH
                            + (len(visible_cards) - 1) * self.CARD_SPACING)
            slot_width = max(actual_width, min_group_width)
            # 分镜卡居中于槽位
            card_offset = (slot_width - actual_width) / 2

            group_start_x = x + card_offset

            # 横向排列可见卡片
            cx = group_start_x
            for card in visible_cards:
                card.setPos(cx, cards_y)
                cx += ShotCanvasCard.CARD_WIDTH + self.CARD_SPACING

            group_end_x = cx - self.CARD_SPACING
            group_width = group_end_x - group_start_x

            # header 在分镜卡下方
            if header:
                header.setVisible(True)
                header_y = cards_y + ShotCanvasCard.CARD_HEIGHT + 8
                header.setPos(group_start_x, header_y)
                header.setRect(0, 0, max(ShotCanvasCard.CARD_WIDTH, group_width),
                               ActSectionHeader.HEADER_HEIGHT)

            x += slot_width + self.GROUP_GAP

    def get_visible_items(self) -> list:
        """返回可见的卡片和标题列表（含折叠卡片），用于 auto_fit_content()"""
        items = []
        for card in self._shot_cards:
            if card.isVisible():
                items.append(card)
        for header in self._section_headers:
            if header.isVisible():
                items.append(header)
        for cc in self._collapsed_cards.values():
            if cc.isVisible():
                items.append(cc)
        return items

    # ==================== 标题栏按钮回调 ====================

    def ai_split_single_act(self, act_id: int):
        """对单个场次进行 AI 分镜拆分"""
        if not self.data_hub:
            return

        acts = self.data_hub.acts_data
        if not acts:
            return

        source = self.data_hub.get_source_content()
        act_data = None
        act_idx = 0
        for i, a in enumerate(acts):
            if a.get('id') == act_id:
                act_data = a
                act_idx = i
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

        self._zone.set_status(f"正在分镜化场次 {act_idx + 1}...")

        # 只清除本场次的旧卡片（保留其他场次）
        self._remove_act_cards(act_id)

        # 设置单场景拆分状态（复用批量框架）
        self._pending_batch = []
        self._batch_total = 1
        self._batch_done = 0
        self._current_batch_act_idx = act_idx

        from services.ai_analyzer import ActToShotsWorker
        self._split_worker = ActToShotsWorker(act_id, act_text)
        self._split_worker.split_completed.connect(self._on_batch_act_completed)
        self._split_worker.split_failed.connect(self._on_batch_act_failed)
        self._split_worker.start()

    def ai_split_selected_acts(self, act_ids: list):
        """对指定的 act_ids 进行分镜拆分（复用批量框架）"""
        if not self.data_hub or not act_ids:
            return

        acts = self.data_hub.acts_data
        if not acts:
            return

        source = self.data_hub.get_source_content()
        pending_acts = []
        for act_idx, a in enumerate(acts):
            act_id = a.get('id')
            if act_id not in act_ids:
                continue
            if a.get('is_skipped'):
                continue
            text_range = a.get('source_text_range')
            if text_range and source:
                act_text = source[text_range[0]:text_range[1]]
            else:
                act_text = a.get('summary', '')
            if act_text:
                pending_acts.append((act_id, act_text, act_idx))

        if not pending_acts:
            return

        # 按 act_idx 排序，确保无论用户点击顺序如何，分镜组按场景顺序排列
        pending_acts.sort(key=lambda t: t[2])

        # 只清除待重新处理的场次的卡片（保留其他场次的卡片）
        for aid, _, _ in pending_acts:
            self._remove_act_cards(aid)

        self._pending_batch = list(pending_acts)
        self._batch_total = len(pending_acts)
        self._batch_done = 0
        self._zone.set_status(f"已生成：0/{self._batch_total}")
        self._process_next_batch_act()

    def ai_split_shots(self):
        """AI 拆分所有未剔除场次的分镜（全场景轮流拆分，逐组显示）"""
        if not self.data_hub:
            return

        acts = self.data_hub.acts_data
        if not acts:
            QMessageBox.warning(self._view, "提示", "请先进行场景拆分")
            return

        source = self.data_hub.get_source_content()

        # 收集所有待拆分的场次
        pending_acts = []
        for act_idx, a in enumerate(acts):
            if a.get('is_skipped'):
                continue
            act_id = a.get('id')
            if not act_id:
                continue
            text_range = a.get('source_text_range')
            if text_range and source:
                act_text = source[text_range[0]:text_range[1]]
            else:
                act_text = a.get('summary', '')
            if act_text:
                pending_acts.append((act_id, act_text, act_idx))

        if not pending_acts:
            QMessageBox.warning(self._view, "提示", "没有可拆分的场次")
            return

        # 清除旧数据，准备逐组加载
        self._clear_cards()

        self._pending_batch = list(pending_acts)
        self._batch_total = len(pending_acts)
        self._batch_done = 0
        self._zone.set_status(f"已生成：0/{self._batch_total}")
        self._process_next_batch_act()

    def _process_next_batch_act(self):
        """处理下一个待拆分的场次"""
        if not self._pending_batch:
            # 所有场次拆分完成 — 从数据库重新加载，确保按场景顺序排列
            self.load_all_acts_shots()
            self._zone.set_status(
                f"已生成：{self._batch_total}/{self._batch_total} (完成)"
            )
            self.shots_changed.emit()
            self.batch_all_completed.emit()
            return

        act_id, act_text, act_idx = self._pending_batch.pop(0)
        self._current_act_id = act_id
        self._current_batch_act_idx = act_idx
        self._zone.set_status(
            f"已生成：{self._batch_done}/{self._batch_total}"
        )

        from services.ai_analyzer import ActToShotsWorker
        self._split_worker = ActToShotsWorker(act_id, act_text)
        self._split_worker.split_completed.connect(self._on_batch_act_completed)
        self._split_worker.split_failed.connect(self._on_batch_act_failed)
        self._split_worker.start()

    def _on_batch_act_completed(self, act_id: int, shots: list):
        """单个场次 AI 拆分完成 → 保存、显示该组分镜卡、继续下一个"""
        if self.data_hub:
            self.data_hub.act_controller.split_act_into_shots(act_id, shots)

        # 逐组显示：立即加载该场次的分镜卡
        scenes = self.data_hub.act_controller.get_act_scenes(act_id) if self.data_hub else []
        act_idx = getattr(self, '_current_batch_act_idx', 0)
        self.add_act_shot_cards(act_id, scenes, act_idx)

        self._batch_done += 1
        self._zone.set_status(f"已生成：{self._batch_done}/{self._batch_total}")
        self.act_shot_completed.emit(act_id)
        self.batch_progress.emit(self._batch_done, self._batch_total)
        self._process_next_batch_act()

    def _on_batch_act_failed(self, act_id: int, error: str):
        """单个场次拆分失败 → 跳过继续下一个"""
        self._zone.set_status(
            f"场次 {act_id} 拆分失败: {error}，继续下一个..."
        )
        self._process_next_batch_act()

    def quick_split_shots(self):
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

    def set_duration_preset(self, duration: float):
        if self._selected_global_index is not None:
            self._set_shot_duration(self._selected_global_index, duration)

    # ==================== 鼠标事件 ====================

    def handle_mouse_press(self, scene_pos: QPointF, event, item):
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        # + 号按钮自行处理事件
        from .shot_card_actions import ShotCardPlusButton, ShotDragActionMenu
        if isinstance(item, (ShotCardPlusButton, ShotDragActionMenu)):
            self._mouse_active = True
            return

        # 沿父链查找 ShotCanvasCard（itemAt 可能返回子项）
        resolved = item
        while resolved and not isinstance(resolved, (ShotCanvasCard, ZoneFrame)):
            resolved = resolved.parentItem()

        if isinstance(resolved, ShotCanvasCard):
            if ctrl:
                # Ctrl+点击 → 切换多选
                gi = resolved.global_index
                if gi in self._multi_selected_shots:
                    self._multi_selected_shots.discard(gi)
                    resolved.set_selected(False)
                else:
                    self._multi_selected_shots.add(gi)
                    resolved.set_selected(True)
            else:
                self._select_card(resolved)
            self._mouse_active = True
            return

        # 点击空白区域时移除任何存在的 ShotDragActionMenu
        for it in list(self._scene.items()):
            if isinstance(it, ShotDragActionMenu):
                self._scene.removeItem(it)

        # 空白区域 → 框选
        if not ctrl:
            self._deselect_all_cards()
            self._multi_selected_shots.clear()
        self._is_rubber_banding = True
        self._rubber_band_start = scene_pos
        self._mouse_active = True

    def handle_mouse_move(self, scene_pos: QPointF, event):
        # 框选
        if self._is_rubber_banding and self._rubber_band_start is not None:
            rect = QRectF(self._rubber_band_start, scene_pos).normalized()
            if self._rubber_band_rect_item is None:
                self._rubber_band_rect_item = self._scene.addRect(
                    rect,
                    QPen(QColor(0, 122, 204, 180), 1.5, Qt.PenStyle.DashLine),
                    QBrush(QColor(0, 122, 204, 25))
                )
                self._rubber_band_rect_item.setZValue(2000)
            else:
                self._rubber_band_rect_item.setRect(rect)
            self._update_shot_rubber_band(rect)

    def handle_mouse_release(self, scene_pos: QPointF, event):
        if self._is_rubber_banding:
            self._is_rubber_banding = False
            if self._rubber_band_rect_item:
                if self._rubber_band_rect_item.scene():
                    self._scene.removeItem(self._rubber_band_rect_item)
                self._rubber_band_rect_item = None
            self._rubber_band_start = None
        self._mouse_active = False

    def _update_shot_rubber_band(self, rect: QRectF):
        """更新框选中的分镜卡片选中状态"""
        self._multi_selected_shots.clear()
        for card in self._shot_cards:
            if rect.intersects(card.sceneBoundingRect()):
                self._multi_selected_shots.add(card.global_index)
                card.set_selected(True)
            else:
                card.set_selected(False)

    def handle_context_menu(self, scene_pos: QPointF, event, item):
        if isinstance(item, ShotCanvasCard):
            self._show_context_menu(item.global_index, event.globalPos())

    # ==================== 内部逻辑 ====================

    def _load_shots(self, scenes_data: list):
        """加载单场次分镜卡片（Fallback）"""
        self._clear_cards()
        y = TITLE_BAR_HEIGHT + self.START_Y_OFFSET
        for i, scene_data in enumerate(scenes_data):
            card = ShotCanvasCard(scene_data, i)
            card._on_generate_image = self._on_card_generate_image
            card._on_generate_video = self._on_card_generate_video
            card._on_smart_ps = self._on_card_smart_ps
            card.setParentItem(self._zone)
            card.setPos(self.CARD_X, y)
            self._shot_cards.append(card)
            y += card.rect().height() + self.CARD_SPACING

        self._zone.auto_fit_content(self._shot_cards)

    def _clear_cards(self):
        for card in self._shot_cards:
            if card.scene():
                self._scene.removeItem(card)
        self._shot_cards.clear()
        for header in self._section_headers:
            if header.scene():
                self._scene.removeItem(header)
        self._section_headers.clear()
        self._section_headers_map.clear()
        self._selected_global_index = None
        self._all_act_ids.clear()
        self._act_colors.clear()
        self._act_card_groups.clear()

    def _remove_act_cards(self, act_id: int):
        """移除指定场次的分镜卡和标题栏（保留其他场次的数据）"""
        cards = self._act_card_groups.pop(act_id, [])
        for card in cards:
            if card.scene():
                self._scene.removeItem(card)
            if card in self._shot_cards:
                self._shot_cards.remove(card)
        header = self._section_headers_map.pop(act_id, None)
        if header:
            if header.scene():
                self._scene.removeItem(header)
            if header in self._section_headers:
                self._section_headers.remove(header)
        collapsed = self._collapsed_cards.pop(act_id, None)
        if collapsed and collapsed.scene():
            self._scene.removeItem(collapsed)
        if act_id in self._all_act_ids:
            self._all_act_ids.remove(act_id)
        self._act_colors.pop(act_id, None)

    def _select_card(self, card: ShotCanvasCard):
        self._deselect_all_cards()
        card.set_selected(True)
        self._selected_global_index = card.global_index

        # 更新 _current_act_id 为该卡片所属场次
        act_id = card.scene_data.get('act_id')
        if act_id:
            self._current_act_id = act_id

        self.shot_clicked.emit(card.global_index)

    def _deselect_all_cards(self):
        for card in self._shot_cards:
            card.set_selected(False)
        self._selected_global_index = None

    def _on_card_generate_image(self, scene_index: int, pos=None):
        """分镜卡 + 号 → 生成图片"""
        if pos is not None:
            self.generate_image_requested.emit(scene_index, pos.x(), pos.y())
        else:
            self.generate_image_requested.emit(scene_index, 0.0, 0.0)

    def _on_card_generate_video(self, scene_index: int, pos=None):
        """分镜卡 + 号 → 生成视频"""
        if pos is not None:
            self.generate_video_requested.emit(scene_index, pos.x(), pos.y())
        else:
            self.generate_video_requested.emit(scene_index, 0.0, 0.0)

    def _on_card_smart_ps(self, scene_index: int, pos=None):
        """分镜卡 + 号 → 智能PS"""
        if pos is not None:
            self.smart_ps_requested.emit(scene_index, pos.x(), pos.y())
        else:
            self.smart_ps_requested.emit(scene_index, 0.0, 0.0)

    def _show_context_menu(self, global_index: int, pos):
        menu = QMenu(self._view)
        merge = QAction("合并到下一个", self._view)
        merge.triggered.connect(lambda: self._merge_shots(global_index))
        menu.addAction(merge)

        split_action = QAction("拆分", self._view)
        split_action.triggered.connect(lambda: self._split_shot(global_index))
        menu.addAction(split_action)

        menu.addSeparator()
        for dur in [8, 10, 12]:
            dur_action = QAction(f"设为 {dur}s", self._view)
            dur_action.triggered.connect(
                lambda checked, d=dur: self._set_shot_duration(global_index, d))
            menu.addAction(dur_action)

        # 运镜子菜单
        menu.addSeparator()
        camera_menu = menu.addMenu("设置运镜")
        from config.constants import CAMERA_MOVES
        for move_key, move_label in CAMERA_MOVES.items():
            cam_action = QAction(f"{move_label} ({move_key})", self._view)
            cam_action.triggered.connect(
                lambda checked, mk=move_key: self._set_camera_move(global_index, mk))
            camera_menu.addAction(cam_action)

        menu.exec(pos)

    # ==================== 分镜操作 ====================

    def _on_ai_shots_completed(self, act_id: int, shots: list):
        self._zone.set_status(f"已拆分为 {len(shots)} 个分镜")
        self._save_shots(shots)

    def _on_shots_failed(self, act_id: int, error: str):
        self._zone.set_status(f"拆分失败: {error}")

    def _save_shots(self, shots: list):
        if not self.data_hub or not self._current_act_id:
            return
        self.data_hub.act_controller.split_act_into_shots(
            self._current_act_id, shots
        )
        # 重新加载全部
        self.load_all_acts_shots()
        self.shots_changed.emit()

    def _merge_shots(self, global_index: int):
        if not self.data_hub:
            return
        cards = self._shot_cards
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

        self.load_all_acts_shots()
        self.shots_changed.emit()

    def _split_shot(self, global_index: int):
        if not self.data_hub:
            return
        card = None
        for c in self._shot_cards:
            if c.global_index == global_index:
                card = c
                break
        if not card:
            return

        text = card.scene_data.get('subtitle_text', '')
        if len(text) < 10:
            QMessageBox.information(self._view, "提示", "文本太短，无法拆分")
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

        self.load_all_acts_shots()
        self.shots_changed.emit()

    def _set_shot_duration(self, global_index: int, duration: float):
        if not self.data_hub:
            return
        for card in self._shot_cards:
            if card.global_index == global_index:
                from database import session_scope, Scene
                with session_scope() as session:
                    scene = session.query(Scene).get(card.scene_id)
                    if scene:
                        scene.duration = duration
                card.scene_data['duration'] = duration
                card.update()
                break

    def _set_camera_move(self, global_index: int, move_key: str):
        """设置分镜的运镜类型"""
        from config.constants import CAMERA_MOVES
        move_label = CAMERA_MOVES.get(move_key, move_key)

        for card in self._shot_cards:
            if card.global_index == global_index:
                from database.session import session_scope
                from database.models import Scene
                with session_scope() as session:
                    scene = session.query(Scene).get(card.scene_id)
                    if scene:
                        scene.camera_motion = move_label
                card.scene_data['camera_motion'] = move_label
                card.update()
                break

        # 检测运镜冲突
        self._check_camera_conflicts()

    def _check_camera_conflicts(self) -> list:
        """
        检测相邻分镜的运镜冲突。
        返回冲突列表 [{scene_index_a, scene_index_b, level, description}]
        """
        from config.constants import CAMERA_CONFLICT_RULES, CAMERA_MOVES

        # 建立中文→英文反向映射
        label_to_key = {v: k for k, v in CAMERA_MOVES.items()}

        conflicts = []
        for i in range(len(self._shot_cards) - 1):
            card_a = self._shot_cards[i]
            card_b = self._shot_cards[i + 1]

            motion_a = card_a.scene_data.get('camera_motion', '静止')
            motion_b = card_b.scene_data.get('camera_motion', '静止')

            key_a = label_to_key.get(motion_a, motion_a)
            key_b = label_to_key.get(motion_b, motion_b)

            for rule_a, rule_b, level, desc in CAMERA_CONFLICT_RULES:
                if key_a == rule_a and key_b == rule_b:
                    conflicts.append({
                        'scene_index_a': card_a.global_index,
                        'scene_index_b': card_b.global_index,
                        'level': level,
                        'description': desc,
                    })

        # TODO: 在卡片间连接线上标注红色冲突
        if conflicts:
            self._zone.set_status(
                f"{len(self._shot_cards)} 个分镜 / {len(self._all_act_ids)} 个场次"
                f" / ⚠ {len(conflicts)} 个运镜冲突"
            )

        return conflicts

    def apply_theme(self):
        """刷新所有分镜卡片的主题"""
        for card in self._shot_cards:
            card.update()
        for header in self._section_headers:
            header.update()


# ============================================================
#  CharacterPropZoneDelegate — 角色道具区委托
# ============================================================

class CharacterPropZoneDelegate(BaseZoneDelegate):
    """
    角色道具区交互委托。
    在 ZoneFrame 内展示角色卡片和道具卡片，支持 AI 提取。
    """

    characters_changed = pyqtSignal()
    props_changed = pyqtSignal()

    CARD_X = 20
    CARD_SPACING = 12
    SECTION_GAP = 24

    def __init__(self, zone_frame: ZoneFrame, scene: QGraphicsScene,
                 data_hub, view, parent=None):
        super().__init__(zone_frame, scene, data_hub, view, parent)

        self._char_cards: List[CharacterCanvasCard] = []
        self._prop_cards: List[PropCanvasCard] = []
        self._group_labels: List[QGraphicsItem] = []
        self._extract_worker = None

    # ==================== 外部接口 ====================

    def load_data(self):
        """从 data_hub 加载角色和道具数据"""
        if not self.data_hub:
            return

        self._clear_all()

        characters = getattr(self.data_hub, 'characters_data', []) or []
        props = getattr(self.data_hub, 'props_data', []) or []

        y = TITLE_BAR_HEIGHT + 20

        # 角色区域
        if characters:
            label = self._scene.addText("角色", QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            label.setDefaultTextColor(QColor(10, 132, 255, 180))
            label.setParentItem(self._zone)
            label.setPos(self.CARD_X, y)
            self._group_labels.append(label)
            y += 30

            cols = 2
            for i, char in enumerate(characters):
                card = CharacterCanvasCard(char)
                card.setParentItem(self._zone)
                col = i % cols
                row = i // cols
                x = self.CARD_X + col * (CharacterCanvasCard.CARD_WIDTH + self.CARD_SPACING)
                cy = y + row * (CharacterCanvasCard.CARD_HEIGHT + self.CARD_SPACING)
                card.setPos(x, cy)
                self._char_cards.append(card)

            total_rows = (len(characters) + cols - 1) // cols
            y += total_rows * (CharacterCanvasCard.CARD_HEIGHT + self.CARD_SPACING)
            y += self.SECTION_GAP

        # 道具区域
        if props:
            label = self._scene.addText("道具", QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            label.setDefaultTextColor(QColor(255, 159, 10, 180))
            label.setParentItem(self._zone)
            label.setPos(self.CARD_X, y)
            self._group_labels.append(label)
            y += 30

            cols = 2
            for i, prop in enumerate(props):
                card = PropCanvasCard(prop)
                card.setParentItem(self._zone)
                col = i % cols
                row = i // cols
                x = self.CARD_X + col * (PropCanvasCard.CARD_WIDTH + self.CARD_SPACING)
                cy = y + row * (PropCanvasCard.CARD_HEIGHT + self.CARD_SPACING)
                card.setPos(x, cy)
                self._prop_cards.append(card)

            total_rows = (len(props) + cols - 1) // cols
            y += total_rows * (PropCanvasCard.CARD_HEIGHT + self.CARD_SPACING)

        # 更新状态文本
        char_count = len(characters)
        prop_count = len(props)
        if char_count or prop_count:
            self._zone.set_status(f"{char_count} 角色 / {prop_count} 道具")
        else:
            self._zone.set_status("暂无角色和道具")

        # 自适应 ZoneFrame
        all_items = self._char_cards + self._prop_cards + self._group_labels
        if all_items:
            self._zone.auto_fit_content(all_items)

    def clear(self):
        self._clear_all()
        self._zone.set_status("")

    def _clear_all(self):
        for card in self._char_cards:
            if card.scene():
                self._scene.removeItem(card)
        self._char_cards.clear()
        for card in self._prop_cards:
            if card.scene():
                self._scene.removeItem(card)
        self._prop_cards.clear()
        for label in self._group_labels:
            if label.scene():
                self._scene.removeItem(label)
        self._group_labels.clear()

    # ==================== 标题栏按钮回调 ====================

    def ai_extract_characters(self):
        """AI 提取角色"""
        if not self.data_hub:
            return
        source = self.data_hub.get_source_content()
        if not source:
            QMessageBox.warning(self._view, "提示", "请先导入文案")
            return

        self._zone.set_status("AI 提取角色中...")
        from services.ai_analyzer import AIAnalysisWorker
        self._extract_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_CHARACTER_GENERATE, source
        )
        self._extract_worker.analysis_completed.connect(self._on_chars_extracted)
        self._extract_worker.analysis_failed.connect(
            lambda t, err: self._zone.set_status(f"提取失败: {err}"))
        self._extract_worker.start()

    def _on_chars_extracted(self, analysis_type: str, result: dict):
        """角色提取完成"""
        if not self.data_hub or not self.data_hub.current_project_id:
            return
        characters = result.get('characters', [])
        # 保存到数据库
        for char in characters:
            self.data_hub.material_controller.create_character(
                project_id=self.data_hub.current_project_id,
                name=char.get('name', ''),
                character_type=char.get('type', 'human'),
                appearance=char.get('appearance', ''),
            )
        # 刷新
        chars = self.data_hub.material_controller.get_project_characters(
            self.data_hub.current_project_id
        )
        self.data_hub.characters_data = chars
        self.load_data()
        self._zone.set_status(f"提取到 {len(characters)} 个角色")
        self.characters_changed.emit()

    def ai_extract_props(self):
        """AI 提取道具"""
        if not self.data_hub:
            return
        source = self.data_hub.get_source_content()
        if not source:
            QMessageBox.warning(self._view, "提示", "请先导入文案")
            return

        self._zone.set_status("AI 提取道具中...")
        from services.ai_analyzer import AIAnalysisWorker
        self._extract_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_PROP_GENERATE, source
        )
        self._extract_worker.analysis_completed.connect(self._on_props_extracted)
        self._extract_worker.analysis_failed.connect(
            lambda t, err: self._zone.set_status(f"提取失败: {err}"))
        self._extract_worker.start()

    def _on_props_extracted(self, analysis_type: str, result: dict):
        """道具提取完成"""
        if not self.data_hub or not self.data_hub.current_project_id:
            return
        props = result.get('props', [])
        for prop in props:
            self.data_hub.prop_controller.create_prop(
                name=prop.get('name', ''),
                prop_type=prop.get('type', 'object'),
                project_id=self.data_hub.current_project_id,
                description=prop.get('description', ''),
            )
        props_data = self.data_hub.prop_controller.get_project_props(
            self.data_hub.current_project_id
        )
        self.data_hub.props_data = props_data
        self.load_data()
        self._zone.set_status(f"提取到 {len(props)} 个道具")
        self.props_changed.emit()

    # ==================== 鼠标事件 ====================

    def handle_mouse_press(self, scene_pos: QPointF, event, item):
        # 角色/道具卡片支持拖拽，由 QGraphicsItem 自己处理
        self._mouse_active = False

    def handle_context_menu(self, scene_pos: QPointF, event, item):
        pass

    def apply_theme(self):
        for card in self._char_cards:
            card.update()
        for card in self._prop_cards:
            card.update()


# ============================================================
#  AssetRequirementZoneDelegate — 资产需求区委托
# ============================================================

class AssetRequirementZoneDelegate(BaseZoneDelegate):
    """
    资产需求区交互委托。
    分镜拆分完成后，在分镜框左侧展开思维导图式的资产需求卡片系统。
    """

    requirement_selected = pyqtSignal(dict)
    generate_asset_requested = pyqtSignal(dict)   # 请求生成资产图片
    bind_asset_requested = pyqtSignal(dict)       # 请求从资产库绑定
    ai_fill_requested = pyqtSignal(dict)          # 单个资产 AI 补全请求
    multi_angle_requested = pyqtSignal(dict)      # 请求多视角生成

    # 布局常量
    CATEGORY_GAP = 80       # summary→category / category→requirement 水平间距
    CATEGORY_FAN_GAP = 20   # 分类卡纵向扇形间距
    REQ_FAN_GAP = 12        # 需求卡纵向扇形间距
    VARIANT_GAP = 60        # 基础卡到衍生卡的水平间距
    VARIANT_FAN_GAP = 10    # 衍生卡之间纵向间距

    def __init__(self, zone_frame, scene: QGraphicsScene,
                 data_hub, view, parent=None):
        super().__init__(zone_frame, scene, data_hub, view, parent)

        self._summary_card = None
        self._category_cards: Dict[str, 'AssetCategoryCard'] = {}
        self._requirement_cards: Dict[str, List['AssetRequirementCard']] = {}
        self._connection_mgr = None
        self._extract_worker = None
        self._requirements_data: Dict = {}
        self._inline_input = None  # InlineNameInput 引用
        self._multi_angle_groups: Dict[int, 'MultiAnglePreviewGroup'] = {}

    # ==================== 外部接口 ====================

    def extract_requirements(self):
        """触发 AI 提取资产需求"""
        if not self.data_hub or not self.data_hub.current_project_id:
            return

        # 收集所有分镜文本
        shots_data = []
        for scene_data in (self.data_hub.scenes_data or []):
            shots_data.append({
                'image_prompt': scene_data.get('image_prompt', ''),
                'subtitle_text': scene_data.get('subtitle_text', ''),
            })

        if not shots_data:
            self._zone.set_status("请先完成分镜拆分")
            return

        # 获取源文本
        source_text = self.data_hub.get_source_content() or ''

        self._zone.set_status("AI 正在提取资产需求...")

        from services.ai_analyzer import AssetRequirementExtractionWorker
        self._extract_worker = AssetRequirementExtractionWorker(
            shots_data, source_text
        )
        self._extract_worker.extraction_completed.connect(self._on_extraction_completed)
        self._extract_worker.extraction_failed.connect(self._on_extraction_failed)
        self._extract_worker.extraction_progress.connect(
            lambda text: self._zone.set_status(text)
        )
        self._extract_worker.start()

    def _on_extraction_completed(self, result: dict):
        """AI 提取完成"""
        self._requirements_data = result
        project_id = self.data_hub.current_project_id if self.data_hub else None
        if not project_id:
            return

        # 转换并保存到数据库
        flat_reqs = self._flatten_requirements(result)
        saved = self.data_hub.asset_controller.save_requirements(project_id, flat_reqs)

        # 从 saved 重建 raw_data（确保 items 和 saved_by_type 数量一致）
        raw_data = {'characters': [], 'scenes': [], 'props': [], 'lightings': []}
        _type_to_key = {
            'character': 'characters', 'scene_bg': 'scenes',
            'prop': 'props', 'lighting_ref': 'lightings',
        }
        for req in saved:
            _key = _type_to_key.get(req.get('requirement_type', ''), 'props')
            item = dict(req.get('attributes', {}))
            item['name'] = req.get('name', '')
            item['scene_indices'] = req.get('scene_indices', [])
            raw_data[_key].append(item)

        # 加载到 UI
        self.load_requirements(raw_data, saved)

        stats = self.data_hub.asset_controller.get_fulfillment_stats(project_id)
        total = stats.get('total', 0)
        self._zone.set_status(f"提取完成：{total} 个资产需求")
        self.data_hub.asset_requirements_loaded.emit(saved)

    def _on_extraction_failed(self, error: str):
        self._zone.set_status(f"提取失败: {error}")

    def _flatten_requirements(self, result: dict) -> list:
        """将 AI 返回的分类结构展平为统一的需求列表"""
        flat = []
        type_map = {
            'characters': 'character',
            'scenes': 'scene_bg',
            'props': 'prop',
            'lightings': 'lighting_ref',
        }
        for key, req_type in type_map.items():
            items = result.get(key, [])
            for item in items:
                if key == 'characters':
                    # 创建基础角色卡
                    excluded_keys = ('name', 'scene_indices', 'source_excerpt',
                                     'costume_variants', 'variants')
                    char_attrs = {k: v for k, v in item.items()
                                  if k not in excluded_keys}
                    base_name = item.get('name', '未命名')

                    flat.append({
                        'requirement_type': 'character',
                        'name': base_name,
                        'attributes': char_attrs,
                        'scene_indices': item.get('scene_indices', []),
                        'source_text_excerpts': [item.get('source_excerpt', '')]
                                                if item.get('source_excerpt') else [],
                    })

                    # 处理 variants 子数组
                    variants = item.get('variants', [])
                    for vi, var in enumerate(variants):
                        vtype = var.get('variant_type', 'costume_variant')
                        vname = var.get('variant_name', f'衍生{vi+1}')
                        vdesc = var.get('variant_description', '')
                        var_attrs = {
                            'is_variant': True,
                            'variant_index': vi + 1,
                            'variant_type': vtype,
                            'variant_name': vname,
                            'variant_description': vdesc,
                            'base_character_name': base_name,
                        }
                        # 复制 variant 级别的属性
                        for vk, vv in var.items():
                            if vk not in ('variant_type', 'variant_name',
                                          'variant_description', 'scene_indices'):
                                var_attrs[vk] = vv

                        flat.append({
                            'requirement_type': 'character',
                            'name': f"{base_name}（{vname}）",
                            'attributes': var_attrs,
                            'scene_indices': var.get('scene_indices',
                                                     item.get('scene_indices', [])),
                            'source_text_excerpts': [],
                        })

                    # 向后兼容旧格式 costume_variants
                    old_variants = item.get('costume_variants', [])
                    if old_variants and not variants:
                        for vi, var in enumerate(old_variants):
                            var_attrs = {
                                'is_variant': True,
                                'variant_index': vi + 1,
                                'variant_type': 'costume_variant',
                                'variant_name': var.get('variant_name', f'服装{vi+1}'),
                                'variant_description': var.get('clothing_style', ''),
                                'base_character_name': base_name,
                                'clothing_style': var.get('clothing_style', ''),
                                'clothing_color': var.get('clothing_color', ''),
                            }
                            flat.append({
                                'requirement_type': 'character',
                                'name': f"{base_name}（{var.get('variant_name', '服装')}）",
                                'attributes': var_attrs,
                                'scene_indices': var.get('scene_indices',
                                                         item.get('scene_indices', [])),
                                'source_text_excerpts': [],
                            })

                else:
                    # 场景/道具/照明 → 原逻辑
                    attrs = {k: v for k, v in item.items()
                             if k not in ('name', 'scene_indices', 'source_excerpt')}
                    flat.append({
                        'requirement_type': req_type,
                        'name': item.get('name', '未命名'),
                        'attributes': attrs,
                        'scene_indices': item.get('scene_indices', []),
                        'source_text_excerpts': [item.get('source_excerpt', '')]
                                                if item.get('source_excerpt') else [],
                    })

        # 向后兼容：旧数据可能有 costumes 顶级 key → 转为 costume_variant
        old_costumes = result.get('costumes', [])
        for item in old_costumes:
            owner = item.get('owner', '')
            var_attrs = {
                'is_variant': True,
                'variant_index': 1,
                'variant_type': 'costume_variant',
                'variant_name': item.get('name', '服装'),
                'variant_description': item.get('clothing_style', ''),
                'base_character_name': owner,
                'clothing_style': item.get('clothing_style', ''),
                'clothing_color': item.get('clothing_color', ''),
            }
            flat.append({
                'requirement_type': 'character',
                'name': item.get('name', '未命名'),
                'attributes': var_attrs,
                'scene_indices': item.get('scene_indices', []),
                'source_text_excerpts': [item.get('source_excerpt', '')]
                                        if item.get('source_excerpt') else [],
            })

        return flat

    def load_requirements(self, raw_data: dict, saved_reqs: list = None):
        """加载资产需求卡片到画布"""
        from .asset_requirement_cards import (
            AssetSummaryCard, AssetCategoryCard, AssetRequirementCard,
            AssetConnectionManager, CATEGORY_LABELS,
        )

        self._clear_all()

        project_id = self.data_hub.current_project_id if self.data_hub else None
        stats = (self.data_hub.asset_controller.get_fulfillment_stats(project_id)
                 if project_id else
                 {'total': 0, 'fulfilled': 0, 'percentage': 0, 'by_type': {}})

        # 初始化连线管理器
        self._connection_mgr = AssetConnectionManager(self._scene, self._zone)

        # ── 准备分类数据 ──
        type_map = {
            'characters': 'character',
            'scenes': 'scene_bg',
            'props': 'prop',
            'lightings': 'lighting_ref',
        }
        categories_order = ['character', 'scene_bg', 'prop', 'lighting_ref']

        # 收集有内容的分类及其需求条目
        active_cats = []
        for cat in categories_order:
            key = [k for k, v in type_map.items() if v == cat]
            key = key[0] if key else cat + 's'
            items = raw_data.get(key, [])
            if items:
                active_cats.append((cat, items))

        if not active_cats:
            return

        # ── 1. 先创建所有需求卡（不定位），计算每个分类的垂直空间 ──
        cat_req_heights = {}  # {cat: total_height_of_req_cards}
        for cat, items in active_cats:
            saved_by_type = [r for r in (saved_reqs or [])
                             if r.get('requirement_type') == cat]
            req_cards = []
            for j, item in enumerate(items):
                if j < len(saved_by_type):
                    req_dict = saved_by_type[j]
                else:
                    attrs = {k: v for k, v in item.items()
                             if k not in ('name', 'scene_indices', 'source_excerpt')}
                    req_dict = {
                        'name': item.get('name', '未命名'),
                        'requirement_type': cat,
                        'attributes': attrs,
                        'scene_indices': item.get('scene_indices', []),
                        'is_fulfilled': False,
                    }
                req_card = AssetRequirementCard(
                    req_dict, cat,
                    on_generate=self._on_requirement_generate,
                    on_bind=self._on_requirement_bind,
                    on_ai_fill=self._on_ai_fill_requested,
                    on_multi_angle=self._on_multi_angle_generate,
                )
                req_card._on_pos_changed = self._on_card_pos_changed
                req_card.setParentItem(self._zone)
                req_cards.append(req_card)
            self._requirement_cards[cat] = req_cards

            # 计算本分类需求卡总高度
            if req_cards:
                total_h = sum(c.rect().height() for c in req_cards) + \
                          (len(req_cards) - 1) * self.REQ_FAN_GAP
            else:
                total_h = 0
            cat_req_heights[cat] = total_h

        # ── 2. 计算每个分类的纵向区段高度（取分类卡高度和需求卡总高的较大者）──
        cat_section_heights = {}
        for cat, items in active_cats:
            req_h = cat_req_heights.get(cat, 0)
            cat_section_heights[cat] = max(AssetCategoryCard.CARD_HEIGHT, req_h)

        # ── 3. 计算总垂直空间和起始 Y ──
        total_h = sum(cat_section_heights[c] for c, _ in active_cats) + \
                  (len(active_cats) - 1) * self.CATEGORY_FAN_GAP
        start_y = TITLE_BAR_HEIGHT + 20

        # ── 4. Summary 卡（最右侧，垂直居中于内容区域）──
        self._summary_card = AssetSummaryCard(
            stats, on_toggle_all=self._on_toggle_all
        )
        self._summary_card.setParentItem(self._zone)
        zone_w = self._zone.rect().width()
        sx = zone_w - AssetSummaryCard.CARD_WIDTH - 20
        sy = start_y + (total_h - AssetSummaryCard.CARD_HEIGHT) / 2
        if sy < start_y:
            sy = start_y
        self._summary_card.setPos(sx, sy)

        # ── 5. 分类卡 + 需求卡定位 ──
        cat_x = sx - self.CATEGORY_GAP - AssetCategoryCard.CARD_WIDTH
        req_base_x = cat_x - self.CATEGORY_GAP - AssetRequirementCard.CARD_WIDTH
        curr_y = start_y

        for cat, items in active_cats:
            section_h = cat_section_heights[cat]
            by_type = stats.get('by_type', {}).get(cat, {'total': 0, 'fulfilled': 0})

            # 分类卡垂直居中于该区段
            cat_card = AssetCategoryCard(
                cat, len(items), by_type.get('fulfilled', 0),
                raw_data.get('project_meta'),
                on_toggle=self._on_category_toggle,
                on_drag_release=self._on_category_drag_release,
            )
            cat_card.setParentItem(self._zone)
            cat_cy = curr_y + (section_h - AssetCategoryCard.CARD_HEIGHT) / 2
            cat_card.setPos(cat_x, cat_cy)
            self._category_cards[cat] = cat_card

            # 需求卡垂直排列（起始 Y = 区段顶部）
            req_cards = self._requirement_cards.get(cat, [])
            if req_cards:
                # 区分基础卡和衍生卡
                base_cards = []
                variant_map = {}  # {base_name: [variant_card, ...]}
                for rc in req_cards:
                    ra = rc.req_data.get('attributes', {})
                    if ra.get('is_variant') and ra.get('base_character_name'):
                        bn = ra['base_character_name']
                        variant_map.setdefault(bn, []).append(rc)
                    else:
                        base_cards.append(rc)

                # 基础卡定位
                base_total_h = (sum(c.rect().height() for c in base_cards) +
                                max(0, len(base_cards) - 1) * self.REQ_FAN_GAP) if base_cards else 0
                req_start_y = curr_y + (section_h - base_total_h) / 2
                ry = req_start_y
                variant_x = req_base_x - self.VARIANT_GAP - AssetRequirementCard.CARD_WIDTH

                for rc in base_cards:
                    saved_x = rc.req_data.get('card_pos_x')
                    saved_y = rc.req_data.get('card_pos_y')
                    if saved_x is not None and saved_y is not None:
                        rc.setPos(saved_x, saved_y)
                    else:
                        rc.setPos(req_base_x, ry)

                    # 该基础卡的衍生卡在左侧扇形排列
                    base_name = rc.req_data.get('name', '')
                    variants = variant_map.get(base_name, [])
                    if variants:
                        base_cy = ry + rc.rect().height() / 2
                        vtotal_h = (sum(vc.rect().height() for vc in variants) +
                                    max(0, len(variants) - 1) * self.VARIANT_FAN_GAP)
                        vy = base_cy - vtotal_h / 2
                        for vc in variants:
                            saved_vx = vc.req_data.get('card_pos_x')
                            saved_vy = vc.req_data.get('card_pos_y')
                            if saved_vx is not None and saved_vy is not None:
                                vc.setPos(saved_vx, saved_vy)
                            else:
                                vc.setPos(variant_x, vy)
                            vy += vc.rect().height() + self.VARIANT_FAN_GAP

                    ry += rc.rect().height() + self.REQ_FAN_GAP

                # 无基础卡的孤立衍生卡（fallback 定位）
                for bn, vcs in variant_map.items():
                    if not any(bc.req_data.get('name', '') == bn for bc in base_cards):
                        for vc in vcs:
                            saved_vx = vc.req_data.get('card_pos_x')
                            saved_vy = vc.req_data.get('card_pos_y')
                            if saved_vx is not None and saved_vy is not None:
                                vc.setPos(saved_vx, saved_vy)
                            else:
                                vc.setPos(req_base_x, ry)
                                ry += vc.rect().height() + self.REQ_FAN_GAP

            curr_y += section_h + self.CATEGORY_FAN_GAP

        # ── 6. 自适应 zone 大小（必须在连线之前，否则 zone 位置变化导致连线错位）──
        all_items = [self._summary_card]
        all_items.extend(self._category_cards.values())
        for cards in self._requirement_cards.values():
            all_items.extend(cards)
        if all_items:
            self._zone.auto_fit_content(all_items)

        # ── 7. 重建连线（在 zone 大小确定后，mapToScene 坐标才准确）──
        self._connection_mgr.rebuild_connections(
            self._summary_card, self._category_cards, self._requirement_cards
        )

    def load_from_db(self):
        """从数据库加载已保存的需求"""
        if not self.data_hub or not self.data_hub.current_project_id:
            return

        saved = self.data_hub.asset_controller.get_requirements(
            self.data_hub.current_project_id
        )
        if not saved:
            return

        # 重建 raw_data 结构
        raw_data = {'characters': [], 'scenes': [], 'props': [], 'lightings': []}
        type_to_key = {
            'character': 'characters',
            'scene_bg': 'scenes',
            'prop': 'props',
            'lighting_ref': 'lightings',
        }
        for req in saved:
            req_type = req.get('requirement_type', '')
            # 向后兼容：DB 中残留的 costume 类型透明转为 character variant
            if req_type == 'costume':
                req_type = 'character'
                attrs = dict(req.get('attributes', {}))
                if not attrs.get('is_variant'):
                    attrs['is_variant'] = True
                    attrs['variant_type'] = 'costume_variant'
                    attrs['variant_description'] = attrs.get('clothing_style', '')
                    attrs['base_character_name'] = attrs.get('owner', '')
                req['attributes'] = attrs
                req['requirement_type'] = 'character'
            # 向后兼容：已被 DB 迁移为 character 的旧 costume 记录
            # （attributes 中有 wearer/style 等服装特有字段但无 is_variant 标记）
            elif req_type == 'character':
                attrs = req.get('attributes', {})
                if (not attrs.get('is_variant')
                        and attrs.get('wearer')
                        and not attrs.get('gender')):
                    attrs = dict(attrs)
                    attrs['is_variant'] = True
                    attrs['variant_type'] = 'costume_variant'
                    attrs['variant_description'] = attrs.get('style', '')
                    attrs['base_character_name'] = attrs.get('wearer', '')
                    req['attributes'] = attrs
            key = type_to_key.get(req_type, 'props')
            item = dict(req.get('attributes', {}))
            item['name'] = req.get('name', '')
            item['scene_indices'] = req.get('scene_indices', [])
            raw_data[key].append(item)

        self.load_requirements(raw_data, saved)

        # 恢复多视角状态
        for req in saved:
            req_id = req.get('id')
            attrs = req.get('attributes', {})
            multi_paths = attrs.get('multi_angle_paths', [])

            # 如果需求本身没有多视角路径，尝试从绑定的 Asset 获取
            if not multi_paths and req.get('bound_asset_id') and self.data_hub:
                try:
                    asset_data = self.data_hub.asset_controller.get_asset(
                        req['bound_asset_id']
                    )
                    if asset_data:
                        ma_images = asset_data.get('multi_angle_images', [])
                        for img in ma_images:
                            if isinstance(img, dict):
                                p = img.get('path', '')
                            else:
                                p = str(img)
                            if p:
                                multi_paths.append(p)
                except Exception:
                    pass

            if multi_paths and req_id:
                self.set_card_multi_angle_paths(req_id, multi_paths)

    def clear(self):
        """清理所有卡片和连线"""
        self._clear_all()
        self._zone.set_status("")

    def _clear_all(self):
        # 清除多视角预览组
        for group in self._multi_angle_groups.values():
            group.clear()
        self._multi_angle_groups.clear()

        if self._connection_mgr:
            self._connection_mgr.clear_all()
        if self._summary_card and self._summary_card.scene():
            self._scene.removeItem(self._summary_card)
        self._summary_card = None
        for card in self._category_cards.values():
            if card.scene():
                self._scene.removeItem(card)
        self._category_cards.clear()
        for cards in self._requirement_cards.values():
            for card in cards:
                if card.scene():
                    self._scene.removeItem(card)
        self._requirement_cards.clear()

    # ==================== 回调 ====================

    def _on_category_toggle(self, category: str, expanded: bool):
        """分类卡折叠/展开 — 同步隐藏/显示需求分卡、主图、多视角缩略图"""
        req_cards = self._requirement_cards.get(category, [])
        for card in req_cards:
            card.setVisible(expanded)
            # 同步主图 + 连线的可见性
            if card._linked_image_node:
                card._linked_image_node.setVisible(expanded)
            if card._linked_connection:
                card._linked_connection.set_visible(expanded)
            # 同步多视角缩略图的可见性
            req_id = card.req_id
            if req_id and req_id in self._multi_angle_groups:
                group = self._multi_angle_groups[req_id]
                for thumb in group._thumbnails:
                    thumb.setVisible(expanded)
                group._remove_connection_lines()
                if expanded:
                    group._create_connection_lines()

        if self._connection_mgr:
            self._connection_mgr.toggle_category(category, expanded)
            self._connection_mgr.rebuild_connections(
                self._summary_card, self._category_cards, self._requirement_cards
            )

    def _on_toggle_all(self, expanded: bool):
        """总览卡折叠/展开所有"""
        for cat in self._category_cards:
            cat_card = self._category_cards[cat]
            cat_card._expanded = expanded
            cat_card.update()
            self._on_category_toggle(cat, expanded)

    def _on_requirement_generate(self, req_data: dict):
        """需求卡 → 生成图片"""
        self.generate_asset_requested.emit(req_data)

    def _on_requirement_bind(self, req_data: dict):
        """需求卡 → 从资产库绑定"""
        self.bind_asset_requested.emit(req_data)

    def _on_ai_fill_requested(self, req_data: dict):
        """需求卡 AI 补全按钮点击"""
        self.ai_fill_requested.emit(req_data)

    def _on_multi_angle_generate(self, req_data: dict):
        """需求卡 → 多视角生成"""
        self.multi_angle_requested.emit(req_data)

    def set_card_multi_angle_loading(self, req_id: int, loading: bool):
        """设置指定需求卡的多视角加载状态"""
        for cards in self._requirement_cards.values():
            for card in cards:
                if card.req_id == req_id:
                    card.set_multi_angle_loading(loading)
                    return

    def set_card_multi_angle_paths(self, req_id: int, paths: list):
        """设置指定需求卡的多视角图片路径"""
        for cards in self._requirement_cards.values():
            for card in cards:
                if card.req_id == req_id:
                    card.set_multi_angle_paths(paths)
                    self._ensure_multi_angle_group(card, paths)
                    return

    def update_cards_by_bound_asset(self, asset_id: int,
                                     asset_name: str,
                                     multi_angle_images: list):
        """资产库更新后，同步多视角图片到绑定了该资产的需求卡。
        匹配策略：先按 bound_asset_id 精确匹配，再按 name 模糊匹配（fallback）。
        同时将路径持久化到 AssetRequirement.attributes['multi_angle_paths']。
        """
        paths = []
        for img in (multi_angle_images or []):
            if isinstance(img, dict):
                p = img.get('path', '')
            else:
                p = str(img)
            if p:
                paths.append(p)

        if not paths:
            return

        matched_cards = []

        # 策略1：按 bound_asset_id 精确匹配
        for category_cards in self._requirement_cards.values():
            for card in category_cards:
                if card._data.get('bound_asset_id') == asset_id:
                    matched_cards.append(card)

        # 策略2：按 name 匹配（fallback）
        if not matched_cards and asset_name:
            for category_cards in self._requirement_cards.values():
                for card in category_cards:
                    card_name = card._data.get('name', '')
                    if card_name and card_name == asset_name:
                        matched_cards.append(card)

        # 更新匹配到的卡片
        for card in matched_cards:
            card.set_multi_angle_paths(paths)
            self._ensure_multi_angle_group(card, paths)
            # 持久化到 AssetRequirement.attributes['multi_angle_paths']
            req_id = card.req_id
            if req_id and self.data_hub:
                try:
                    from database import session_scope
                    from database.models.asset import AssetRequirement
                    from sqlalchemy.orm.attributes import flag_modified
                    with session_scope() as session:
                        req = session.query(AssetRequirement).get(req_id)
                        if req:
                            attrs = dict(req.attributes or {})
                            attrs['multi_angle_paths'] = paths
                            req.attributes = attrs
                            flag_modified(req, 'attributes')
                except Exception:
                    pass

    def update_card_multi_angle_single(self, req_id: int,
                                        angle_idx: int, path: str):
        """逐张更新指定需求卡的单个角度图片（生成过程中实时刷新）"""
        group = self._multi_angle_groups.get(req_id)
        if group:
            group.update_single_path(angle_idx, path)
        else:
            # group 还不存在 → 先创建一个空 group 再更新
            for cards in self._requirement_cards.values():
                for card in cards:
                    if card.req_id == req_id:
                        from .asset_requirement_cards import MultiAnglePreviewGroup
                        group = MultiAnglePreviewGroup(
                            self._scene, card, [], self._zone
                        )
                        group.build([])
                        card.set_multi_angle_group(group)
                        self._multi_angle_groups[req_id] = group
                        group.update_single_path(angle_idx, path)
                        return

    # ==================== 多视角预览组管理 ====================

    def _ensure_multi_angle_group(self, card, paths: list):
        """创建/更新/清除指定卡片的多视角预览组"""
        from .asset_requirement_cards import MultiAnglePreviewGroup

        req_id = card.req_id
        if req_id is None:
            return

        existing = self._multi_angle_groups.get(req_id)

        if paths:
            if existing:
                existing.update_paths(paths)
            else:
                group = MultiAnglePreviewGroup(
                    self._scene, card, paths, self._zone
                )
                group.build(paths)
                card.set_multi_angle_group(group)
                card._linked_multi_angle = group
                self._multi_angle_groups[req_id] = group
        else:
            # 无路径 → 清除已有 group
            if existing:
                existing.clear()
                card.set_multi_angle_group(None)
                card._linked_multi_angle = None
                del self._multi_angle_groups[req_id]

    # ==================== 拖拽新增 ====================

    def _on_category_drag_release(self, category: str, scene_pos: QPointF):
        """分类卡拖拽释放 → 创建内联输入框"""
        from .asset_requirement_cards import InlineNameInput

        # 清理已有的内联输入框
        if self._inline_input and self._inline_input.scene():
            self._inline_input.scene().removeItem(self._inline_input)
        self._inline_input = None

        self._inline_input = InlineNameInput(
            category, scene_pos,
            on_confirm=self._on_inline_name_confirmed,
            on_cancel=self._on_inline_name_cancelled,
        )
        self._scene.addItem(self._inline_input)

    def _on_inline_name_confirmed(self, category: str, name: str, scene_pos: QPointF):
        """内联输入框确认 → 创建手动需求卡"""
        self._inline_input = None
        self._add_manual_requirement(category, name, scene_pos)

    def _on_inline_name_cancelled(self):
        """内联输入框取消"""
        self._inline_input = None

    def _add_manual_requirement(self, category: str, name: str, scene_pos: QPointF):
        """手动新增一条资产需求"""
        from .asset_requirement_cards import (
            AssetRequirementCard, AssetConnectionManager, CATEGORY_LABELS,
        )

        project_id = self.data_hub.current_project_id if self.data_hub else None
        if not project_id:
            return

        # 构建最小 req_data
        req_data = {
            'requirement_type': category,
            'name': name,
            'attributes': {},
            'scene_indices': [],
            'is_fulfilled': False,
        }

        # 保存到数据库
        saved = self.data_hub.asset_controller.add_single_requirement(project_id, req_data)
        if not saved:
            return

        # 创建卡片
        req_card = AssetRequirementCard(
            saved, category,
            on_generate=self._on_requirement_generate,
            on_bind=self._on_requirement_bind,
            on_ai_fill=self._on_ai_fill_requested,
            on_multi_angle=self._on_multi_angle_generate,
        )
        req_card._on_pos_changed = self._on_card_pos_changed
        req_card.setParentItem(self._zone)

        # 用 zone 本地坐标定位
        local_pos = self._zone.mapFromScene(scene_pos)
        req_card.setPos(local_pos.x(), local_pos.y())

        # 保存位置到数据库
        if saved.get('id'):
            self.data_hub.asset_controller.update_requirement_card_pos(
                saved['id'], local_pos.x(), local_pos.y()
            )

        # 加入跟踪列表
        if category not in self._requirement_cards:
            self._requirement_cards[category] = []
        self._requirement_cards[category].append(req_card)

        # 更新分类卡计数
        cat_card = self._category_cards.get(category)
        if cat_card:
            count = len(self._requirement_cards.get(category, []))
            cat_card.update_counts(count, cat_card._fulfilled_count)

        # 更新总览卡统计
        if self._summary_card and project_id:
            stats = self.data_hub.asset_controller.get_fulfillment_stats(project_id)
            self._summary_card.update_stats(stats)

        # 重建连线
        if self._connection_mgr:
            self._connection_mgr.rebuild_connections(
                self._summary_card, self._category_cards, self._requirement_cards
            )

    def update_requirement_after_ai_fill(self, req_id: int, new_data: dict):
        """AI 补全完成后更新卡片"""
        for cards in self._requirement_cards.values():
            for card in cards:
                if card.req_id == req_id:
                    card.set_ai_filling(False)
                    card.update_data(new_data)
                    # 重建连线（卡片高度可能变化）
                    if self._connection_mgr:
                        self._connection_mgr.rebuild_connections(
                            self._summary_card, self._category_cards,
                            self._requirement_cards
                        )
                    return

    def set_card_ai_filling(self, req_id: int, filling: bool):
        """设置指定需求卡的 AI 补全加载状态"""
        for cards in self._requirement_cards.values():
            for card in cards:
                if card.req_id == req_id:
                    card.set_ai_filling(filling)
                    return

    # ==================== 卡片移动 + 重排 ====================

    def _on_card_pos_changed(self, card):
        """需求卡拖拽结束 → 持久化位置 + 更新连线 + 更新多视角预览组"""
        req_id = card.req_id
        if req_id and self.data_hub:
            pos = card.pos()
            self.data_hub.asset_controller.update_requirement_card_pos(
                req_id, pos.x(), pos.y()
            )
        # 拖拽后更新多视角预览组位置
        if req_id and req_id in self._multi_angle_groups:
            self._multi_angle_groups[req_id].update_positions()
        # 拖拽后更新连线
        if self._connection_mgr:
            self._connection_mgr.rebuild_connections(
                self._summary_card, self._category_cards, self._requirement_cards
            )

    def relayout_cards(self):
        """重排所有需求卡到标准布局位置（清除自定义位置）"""
        from .asset_requirement_cards import (
            AssetSummaryCard, AssetCategoryCard, AssetRequirementCard,
        )

        if not self._category_cards:
            return

        categories_order = ['character', 'scene_bg', 'prop', 'lighting_ref']
        active_cats = [(cat, self._requirement_cards.get(cat, []))
                       for cat in categories_order
                       if cat in self._category_cards]

        # 计算每个分类的需求卡总高度
        cat_req_heights = {}
        for cat, req_cards in active_cats:
            if req_cards:
                total_h = sum(c.rect().height() for c in req_cards) + \
                          (len(req_cards) - 1) * self.REQ_FAN_GAP
            else:
                total_h = 0
            cat_req_heights[cat] = total_h

        cat_section_heights = {}
        for cat, req_cards in active_cats:
            req_h = cat_req_heights.get(cat, 0)
            cat_section_heights[cat] = max(AssetCategoryCard.CARD_HEIGHT, req_h)

        # 根据 summary card 和 category card 确定 req_base_x
        if self._summary_card:
            sx = self._summary_card.pos().x()
            cat_x = sx - self.CATEGORY_GAP - AssetCategoryCard.CARD_WIDTH
        else:
            cat_x = self._zone.rect().width() - 20 - 160 - self.CATEGORY_GAP - AssetCategoryCard.CARD_WIDTH
        req_base_x = cat_x - self.CATEGORY_GAP - AssetRequirementCard.CARD_WIDTH

        start_y = 60  # TITLE_BAR_HEIGHT + 20
        curr_y = start_y

        for cat, req_cards in active_cats:
            section_h = cat_section_heights[cat]

            # 重新定位分类卡
            cat_card = self._category_cards.get(cat)
            if cat_card:
                cat_cy = curr_y + (section_h - AssetCategoryCard.CARD_HEIGHT) / 2
                cat_card.setPos(cat_x, cat_cy)

            # 重新排列需求卡
            if req_cards:
                req_total_h = cat_req_heights[cat]
                req_start_y = curr_y + (section_h - req_total_h) / 2
                ry = req_start_y
                for rc in req_cards:
                    rc.setPos(req_base_x, ry)
                    # 持久化新位置
                    rid = rc.req_id
                    if rid and self.data_hub:
                        self.data_hub.asset_controller.update_requirement_card_pos(
                            rid, req_base_x, ry
                        )
                    ry += rc.rect().height() + self.REQ_FAN_GAP

            curr_y += section_h + self.CATEGORY_FAN_GAP

        # 自适应 zone 大小
        all_items = []
        if self._summary_card:
            all_items.append(self._summary_card)
        all_items.extend(self._category_cards.values())
        for cards in self._requirement_cards.values():
            all_items.extend(cards)
        if all_items:
            self._zone.auto_fit_content(all_items)

        # 重建连线
        if self._connection_mgr:
            self._connection_mgr.rebuild_connections(
                self._summary_card, self._category_cards, self._requirement_cards
            )

    # ==================== 删除选中卡片 ====================

    def delete_selected_card(self) -> bool:
        """删除当前选中的需求卡，返回是否成功删除"""
        for cat, cards in self._requirement_cards.items():
            for card in cards:
                if card._selected:
                    req_id = card.req_id
                    # 从 DB 删除
                    if req_id and self.data_hub:
                        self.data_hub.asset_controller.delete_requirement(req_id)
                    # 从场景移除
                    if card.scene():
                        card.scene().removeItem(card)
                    # 从跟踪列表移除
                    cards.remove(card)
                    # 更新分类卡计数
                    cat_card = self._category_cards.get(cat)
                    if cat_card:
                        fulfilled = sum(1 for c in cards if c._data.get('is_fulfilled'))
                        cat_card.update_counts(len(cards), fulfilled)
                    # 更新 summary 统计
                    if self._summary_card:
                        total = sum(len(cl) for cl in self._requirement_cards.values())
                        fulfilled_total = sum(
                            1 for cl in self._requirement_cards.values()
                            for c in cl if c._data.get('is_fulfilled')
                        )
                        pct = int(fulfilled_total / total * 100) if total else 0
                        self._summary_card.update_stats({
                            'total': total,
                            'fulfilled': fulfilled_total,
                            'percentage': pct,
                        })
                    # 重建连线
                    if self._connection_mgr:
                        self._connection_mgr.rebuild_connections(
                            self._summary_card, self._category_cards,
                            self._requirement_cards
                        )
                    return True
        return False

    # ==================== 鼠标事件 (AssetRequirementZoneDelegate) ====================

    def handle_mouse_press(self, scene_pos: QPointF, event, item):
        from .asset_requirement_cards import (
            AssetRequirementCard, AssetPlusButton, AssetActionMenu,
            InlineNameInput, AssetCategoryCard,
        )

        # 旁路：这些 item 由画布视图直接处理（bypass → super().mousePressEvent）
        if isinstance(item, (AssetPlusButton, AssetActionMenu,
                             InlineNameInput, AssetCategoryCard,
                             AssetRequirementCard)):
            self._mouse_active = False
            return

        # 父链检查：子项也旁路
        target = item
        while target:
            if isinstance(target, AssetRequirementCard):
                self._mouse_active = False
                return
            target = target.parentItem()

        # 点击空白处取消所有选中
        for cards in self._requirement_cards.values():
            for c in cards:
                c.set_selected(False)

        self._mouse_active = False

    def handle_context_menu(self, scene_pos: QPointF, event, item):
        pass

    def apply_theme(self):
        if self._summary_card:
            self._summary_card.update()
        for card in self._category_cards.values():
            card.update()
        for cards in self._requirement_cards.values():
            for card in cards:
                card.update()
