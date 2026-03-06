"""
涛割 - 剧本执行区纯绘制节点
ShotExecutionNode(QGraphicsRectItem) — 纯 QPainter 绘制的执行区表单节点
EditableTextField — 可编辑文本字段（用 QGraphicsTextItem 实现）
"""

from typing import Optional, Dict, List

from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsItem, QGraphicsTextItem,
    QMenu, QMessageBox, QStyleOptionGraphicsItem,
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QFontMetrics, QTextCursor,
)

from ui import theme
from ui.components.base_canvas_view import LOD_TEXT_MIN_PX


# 画面类型选项
SCENE_TYPES = [
    ('normal', '常规'),
    ('flashback', '闪回'),
    ('transition', '转场'),
    ('montage', '蒙太奇'),
]

# 布局常量
NODE_WIDTH = 320
CORNER_RADIUS = 10
FIELD_HEIGHT = 40
FIELD_LABEL_HEIGHT = 18
SECTION_HEADER_HEIGHT = 28
BUTTON_HEIGHT = 32
PADDING = 12
FIELD_SPACING = 4


# ============================================================
#  EditableTextField — 可编辑文本字段
# ============================================================

class EditableTextField(QGraphicsTextItem):
    """
    可编辑文本字段，嵌入 ShotExecutionNode。
    单击进入编辑状态，失去焦点时提交。
    """

    def __init__(self, field_key: str, placeholder: str = "",
                 on_changed=None, parent=None):
        super().__init__(parent)
        self.field_key = field_key
        self._placeholder = placeholder
        self._on_changed = on_changed
        self._editing = False

        self.setFont(QFont("Microsoft YaHei", 10))
        self.setDefaultTextColor(QColor(theme.text_primary()))
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setTextWidth(NODE_WIDTH - PADDING * 2 - 4)

        # 最小高度
        self._min_height = FIELD_HEIGHT

    def set_text(self, text: str):
        """设置文本（非编辑模式下调用）"""
        self.blockSignals(True)
        self.setPlainText(text)
        self.blockSignals(False)
        self.update()

    def get_text(self) -> str:
        return self.toPlainText()

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < 0.12:
            bg = QColor(theme.bg_secondary())
            painter.fillRect(QRectF(0, 0, rect.width(), max(rect.height(), self._min_height)), bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_rect = QRectF(0, 0, rect.width(), max(rect.height(), self._min_height))
        bg_path.addRoundedRect(bg_rect, 4, 4)

        if self._editing:
            bg = QColor(theme.bg_primary())
            border = QColor(theme.accent())
        else:
            bg = QColor(theme.bg_secondary())
            border = QColor(theme.border())

        painter.fillPath(bg_path, QBrush(bg))
        painter.setPen(QPen(border, 1))
        painter.drawPath(bg_path)

        # LOD 文本隐藏优化
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        if not _hide_text:
            # 占位文本
            if not self.toPlainText() and not self._editing:
                painter.setFont(self.font())
                painter.setPen(QPen(QColor(theme.text_tertiary())))
                painter.drawText(
                    QRectF(4, 2, rect.width() - 8, rect.height()),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    self._placeholder
                )
            else:
                super().paint(painter, option, widget)

    def mousePressEvent(self, event):
        if not self._editing:
            self._editing = True
            self.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextEditorInteraction
            )
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.update()
        super().mousePressEvent(event)

    def focusOutEvent(self, event):
        self._editing = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.update()
        if self._on_changed:
            self._on_changed(self.field_key, self.toPlainText())
        super().focusOutEvent(event)


# ============================================================
#  ShotExecutionNode — 剧本执行区纯绘制节点
# ============================================================

class ShotExecutionNode(QGraphicsRectItem):
    """
    纯 QGraphicsItem 绘制的第三栏表单节点。
    替代原 ShotExecutionPanel（QWidget 表单）。
    """

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self._current_scene_index: Optional[int] = None
        self._current_scene_data: Optional[dict] = None
        self._ai_worker = None
        self._scene_type = 'normal'

        # 可编辑字段
        self._visual_fields: Dict[str, EditableTextField] = {}
        self._audio_fields: Dict[str, EditableTextField] = {}

        self._is_loaded = False
        self._ai_status_text = ""

        # 按钮热区
        self._btn_ai_prompt = QRectF()
        self._btn_ai_full = QRectF()
        self._btn_type_area = QRectF()

        self._setup_fields()
        self._update_rect()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)

    def _setup_fields(self):
        """创建可编辑字段"""
        visual_config = [
            ('subject', '主体', '描述画面中的主要人物/物体'),
            ('action', '动作', '描述主体的动作行为'),
            ('asset_needs', '资产需求', '场景、人物、道具等资产需求'),
            ('camera', '镜头', '描述摄影机角度、景别、运镜'),
        ]
        for key, label, placeholder in visual_config:
            field = EditableTextField(
                key, placeholder,
                on_changed=self._on_visual_field_changed,
                parent=self
            )
            self._visual_fields[key] = field

        audio_config = [
            ('dialogue', '对白', '角色的台词对白'),
            ('narration', '旁白', '旁白/画外音'),
            ('sfx', '音效', '环境音/特殊音效'),
        ]
        for key, label, placeholder in audio_config:
            field = EditableTextField(
                key, placeholder,
                on_changed=self._on_audio_field_changed,
                parent=self
            )
            self._audio_fields[key] = field

    def _update_rect(self):
        """计算节点总高度"""
        # 标题 + 画面类型 + 视觉字段(4) + 音频头 + 音频字段(3) + 按钮 + AI状态
        total_h = (
            40  # 标题 + 分镜信息
            + 30  # 画面类型
            + (FIELD_LABEL_HEIGHT + FIELD_HEIGHT + FIELD_SPACING) * 4  # 4个视觉字段
            + 8  # 间距
            + SECTION_HEADER_HEIGHT  # "音频配置"
            + (FIELD_LABEL_HEIGHT + FIELD_HEIGHT + FIELD_SPACING) * 3  # 3个音频字段
            + 12  # 间距
            + BUTTON_HEIGHT  # AI 按钮
            + 24  # AI 状态 + 底部
        )
        self.setRect(0, 0, NODE_WIDTH, total_h)
        self._layout_fields()

    def _layout_fields(self):
        """布局所有子字段的位置"""
        y = 40 + 30  # 标题+类型

        visual_keys = ['subject', 'action', 'asset_needs', 'camera']
        for key in visual_keys:
            field = self._visual_fields[key]
            y += FIELD_LABEL_HEIGHT
            field.setPos(PADDING, y)
            y += FIELD_HEIGHT + FIELD_SPACING

        y += 8 + SECTION_HEADER_HEIGHT  # 间距 + 音频头

        audio_keys = ['dialogue', 'narration', 'sfx']
        for key in audio_keys:
            field = self._audio_fields[key]
            y += FIELD_LABEL_HEIGHT
            field.setPos(PADDING, y)
            y += FIELD_HEIGHT + FIELD_SPACING

        y += 12
        # AI 按钮区域
        btn_w = (NODE_WIDTH - PADDING * 2 - 8) / 2
        self._btn_ai_prompt = QRectF(PADDING, y, btn_w, BUTTON_HEIGHT)
        self._btn_ai_full = QRectF(PADDING + btn_w + 8, y, btn_w, BUTTON_HEIGHT)

    # ==================== 绘制 ====================

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()
        dark = theme.is_dark()

        # ── LOD 极简绘制 ──
        _zoom = painter.worldTransform().m11()
        if _zoom < 0.12:
            bg = QColor(38, 38, 42) if dark else QColor(255, 255, 255)
            painter.fillRect(rect, bg)
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)
        bg = QColor(38, 38, 42) if dark else QColor(255, 255, 255)
        painter.fillPath(bg_path, QBrush(bg))

        # 边框
        painter.setPen(QPen(QColor(theme.border()), 1))
        painter.drawPath(bg_path)

        # LOD 文本隐藏优化
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        if not self._is_loaded:
            if not _hide_text:
                # 占位文本
                painter.setFont(QFont("Microsoft YaHei", 12))
                painter.setPen(QPen(QColor(theme.text_tertiary())))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "选择分镜查看详情")
            return

        if _hide_text:
            return

        y = 0.0

        # ─── 标题行 ───
        painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(theme.text_primary())))
        title = f"分镜 #{self._current_scene_index + 1}" if self._current_scene_index is not None else "分镜"
        painter.drawText(QRectF(PADDING, y + 8, NODE_WIDTH - PADDING * 2, 24),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         title)
        y += 40

        # ─── 画面类型 ───
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(theme.text_primary())))
        painter.drawText(QRectF(PADDING, y, 60, 24),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         "画面类型")

        # 类型选择框
        type_rect = QRectF(80, y, 100, 24)
        self._btn_type_area = type_rect
        type_path = QPainterPath()
        type_path.addRoundedRect(type_rect, 4, 4)
        painter.fillPath(type_path, QBrush(QColor(theme.bg_secondary())))
        painter.setPen(QPen(QColor(theme.border()), 1))
        painter.drawPath(type_path)

        display_name = self._scene_type
        for val, name in SCENE_TYPES:
            if val == self._scene_type:
                display_name = name
                break
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.setPen(QPen(QColor(theme.text_primary())))
        painter.drawText(type_rect.adjusted(8, 0, -20, 0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         display_name)
        # 下拉箭头
        painter.setPen(QPen(QColor(theme.text_tertiary()), 1.5))
        ax = type_rect.right() - 14
        ay = type_rect.center().y() - 2
        painter.drawLine(QPointF(ax, ay), QPointF(ax + 4, ay + 4))
        painter.drawLine(QPointF(ax + 4, ay + 4), QPointF(ax + 8, ay))

        y += 30

        # ─── 视觉字段 ───
        visual_labels = ['主体', '动作', '资产需求', '镜头']
        for label_text in visual_labels:
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor(theme.text_secondary())))
            painter.drawText(QRectF(PADDING, y, NODE_WIDTH - PADDING * 2, FIELD_LABEL_HEIGHT),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             label_text)
            y += FIELD_LABEL_HEIGHT + FIELD_HEIGHT + FIELD_SPACING

        y += 8

        # ─── 音频配置 ───
        painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(theme.text_primary())))
        painter.drawText(QRectF(PADDING, y, NODE_WIDTH - PADDING * 2, SECTION_HEADER_HEIGHT),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         "音频配置")
        y += SECTION_HEADER_HEIGHT

        audio_labels = ['对白', '旁白', '音效']
        for label_text in audio_labels:
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor(theme.text_secondary())))
            painter.drawText(QRectF(PADDING, y, NODE_WIDTH - PADDING * 2, FIELD_LABEL_HEIGHT),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             label_text)
            y += FIELD_LABEL_HEIGHT + FIELD_HEIGHT + FIELD_SPACING

        y += 12

        # ─── AI 按钮 ───
        self._paint_button(painter, self._btn_ai_prompt, "AI 生成提示词",
                           QColor(theme.accent()), QColor(255, 255, 255))
        self._paint_button(painter, self._btn_ai_full, "AI 全量分析",
                           QColor(theme.success()), QColor(255, 255, 255))

        # AI 状态
        if self._ai_status_text:
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.setPen(QPen(QColor(theme.text_tertiary())))
            painter.drawText(
                QRectF(PADDING, y + BUTTON_HEIGHT + 4, NODE_WIDTH - PADDING * 2, 16),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self._ai_status_text
            )

    def _paint_button(self, painter: QPainter, rect: QRectF,
                      text: str, bg_color: QColor, fg_color: QColor):
        btn_path = QPainterPath()
        btn_path.addRoundedRect(rect, 6, 6)
        painter.fillPath(btn_path, QBrush(bg_color))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.setPen(QPen(fg_color))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    # ==================== 鼠标事件 ====================

    def mousePressEvent(self, event):
        local_pos = event.pos()

        # 画面类型选择
        if self._btn_type_area.contains(local_pos):
            self._show_type_menu(local_pos)
            event.accept()
            return

        # AI 按钮
        if self._btn_ai_prompt.contains(local_pos):
            self.ai_generate_prompt()
            event.accept()
            return

        if self._btn_ai_full.contains(local_pos):
            self.ai_full_analysis()
            event.accept()
            return

        super().mousePressEvent(event)

    def _show_type_menu(self, local_pos: QPointF):
        """弹出画面类型选择菜单"""
        menu = QMenu()
        for val, name in SCENE_TYPES:
            action = menu.addAction(name)
            action.triggered.connect(
                lambda checked, v=val: self._on_type_selected(v)
            )
        # 映射到全局坐标
        scene_pos = self.mapToScene(local_pos)
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view:
            global_pos = view.mapToGlobal(view.mapFromScene(scene_pos))
            menu.exec(global_pos)

    def _on_type_selected(self, type_val: str):
        self._scene_type = type_val
        self.update()
        self._update_scene_prop('scene_type', type_val)

    # ==================== 外部接口 ====================

    def load_scene(self, scene_index: int):
        """加载选中的分镜"""
        if not self.data_hub:
            return

        scene_data = None
        for s in self.data_hub.scenes_data:
            if s.get('scene_index') == scene_index:
                scene_data = s
                break

        if not scene_data:
            from database import session_scope, Scene
            with session_scope() as session:
                scene = session.query(Scene).filter(
                    Scene.scene_index == scene_index).first()
                if scene:
                    scene_data = scene.to_dict()

        if not scene_data:
            return

        self._current_scene_index = scene_index
        self._current_scene_data = scene_data
        self._is_loaded = True

        # 画面类型
        self._scene_type = scene_data.get('scene_type', 'normal')

        # 视觉字段
        visual_struct = scene_data.get('visual_prompt_struct') or {}
        for key, field in self._visual_fields.items():
            field.set_text(visual_struct.get(key, ''))

        # 音频字段
        audio_conf = scene_data.get('audio_config') or {}
        for key, field in self._audio_fields.items():
            field.set_text(audio_conf.get(key, ''))

        self._ai_status_text = ""
        self.update()

    def clear(self):
        self._current_scene_index = None
        self._current_scene_data = None
        self._is_loaded = False
        self._ai_status_text = ""

        for field in self._visual_fields.values():
            field.set_text("")
        for field in self._audio_fields.values():
            field.set_text("")

        self.update()

    # ==================== 字段变更 ====================

    def _on_visual_field_changed(self, key: str, value: str):
        if self._current_scene_index is None or not self.data_hub:
            return
        struct = {}
        for k, field in self._visual_fields.items():
            struct[k] = field.get_text()
        self._update_scene_prop('visual_prompt_struct', struct)

    def _on_audio_field_changed(self, key: str, value: str):
        if self._current_scene_index is None or not self.data_hub:
            return
        config = {}
        for k, field in self._audio_fields.items():
            config[k] = field.get_text()
        self._update_scene_prop('audio_config', config)

    def _update_scene_prop(self, prop: str, value):
        if not self.data_hub or self._current_scene_index is None:
            return

        for i, s in enumerate(self.data_hub.scenes_data):
            if s.get('scene_index') == self._current_scene_index:
                self.data_hub.update_scene_property(i, prop, value)
                return

        scene_data = self._current_scene_data
        if scene_data and scene_data.get('id'):
            from database import session_scope, Scene
            from sqlalchemy.orm.attributes import flag_modified
            with session_scope() as session:
                scene = session.query(Scene).get(scene_data['id'])
                if scene and hasattr(scene, prop):
                    setattr(scene, prop, value)
                    if prop in ('visual_prompt_struct', 'audio_config'):
                        flag_modified(scene, prop)

    # ==================== AI 生成 ====================

    def ai_generate_prompt(self):
        if not self._current_scene_data:
            return
        text = self._current_scene_data.get('subtitle_text', '')
        if not text:
            return

        self._ai_status_text = "AI 生成中..."
        self.update()

        from services.ai_analyzer import AIAnalysisWorker
        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_IMAGE_PROMPT, text
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_prompt_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def ai_full_analysis(self):
        if not self._current_scene_data:
            return
        text = self._current_scene_data.get('subtitle_text', '')
        if not text:
            return

        self._ai_status_text = "AI 全量分析中..."
        self.update()

        from services.ai_analyzer import AIAnalysisWorker
        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_ALL, text
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_full_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def _on_ai_prompt_completed(self, analysis_type: str, result: dict):
        self._ai_status_text = "生成完成"
        image_prompt = result.get('image_prompt', '')
        if image_prompt:
            self._visual_fields['subject'].set_text(image_prompt)
            if self.data_hub and self._current_scene_index is not None:
                self._update_scene_prop('image_prompt', image_prompt)
        self.update()

    def _on_ai_full_completed(self, analysis_type: str, result: dict):
        self._ai_status_text = "全量分析完成"
        image_prompt = result.get('image_prompt', '')
        if image_prompt:
            self._visual_fields['subject'].set_text(image_prompt)
        camera = result.get('camera_motion', '')
        if camera:
            self._visual_fields['camera'].set_text(camera)
        actions = result.get('character_actions', '')
        if actions:
            self._visual_fields['action'].set_text(actions)

        if self.data_hub and self._current_scene_index is not None:
            if image_prompt:
                self._update_scene_prop('image_prompt', image_prompt)
            video_prompt = result.get('video_prompt', '')
            if video_prompt:
                self._update_scene_prop('video_prompt', video_prompt)
        self.update()

    def _on_ai_failed(self, analysis_type: str, error: str):
        self._ai_status_text = f"失败: {error}"
        self.update()
