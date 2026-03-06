"""
涛割 - 剧本与分镜拆解区
QStackedWidget 模式切换：模式选择页 / 剧情模式页 / 解说模式页
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QFileDialog, QMessageBox, QStackedWidget,
    QGraphicsRectItem, QGraphicsItem, QGraphicsView, QStyleOptionGraphicsItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from ui import theme
from ui.components.base_canvas_view import BaseCanvasView, LOD_TEXT_MIN_PX
from ..character_extraction_widget import CharacterExtractionWidget
from ..scene_adjustment_widget import SceneAdjustmentWidget
from ..srt_import_dialog import SrtImportDialog
from .mode_select_panel import ModeSelectPanel


# ==================== 文本块卡片 ====================

class TextBlockCard(QGraphicsRectItem):
    """剧本文本块卡片"""

    CARD_WIDTH = 320
    MIN_HEIGHT = 120
    MAX_HEIGHT = 260
    CORNER_RADIUS = 10
    LINE_HEIGHT = 16

    def __init__(self, index: int, text: str, title: str = "", parent=None):
        super().__init__(parent)
        self.block_index = index
        self.text = text
        self.title = title
        self._is_selected = False

        # 动态计算高度
        line_count = min(12, max(3, len(text) // 30 + 1))
        card_h = max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, 50 + line_count * self.LINE_HEIGHT))

        self.setRect(0, 0, self.CARD_WIDTH, card_h)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()

        # 背景
        if self._is_selected:
            bg = QColor(45, 45, 55) if dark else QColor(225, 235, 250)
        else:
            bg = QColor(38, 38, 42) if dark else QColor(255, 255, 255)
        painter.setBrush(QBrush(bg))

        # 边框
        if self._is_selected:
            painter.setPen(QPen(QColor(0, 122, 204), 2))
        else:
            painter.setPen(QPen(QColor(60, 60, 65) if dark else QColor(210, 210, 215), 1))

        painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        # 序号标签
        index_text = f"#{self.block_index + 1:02d}"
        painter.setPen(QColor(0, 180, 255))
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.drawText(int(rect.x() + 12), int(rect.y() + 24), index_text)

        # 标题（如果有）
        if self.title:
            painter.setPen(QColor(245, 245, 247) if dark else QColor(28, 28, 30))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(int(rect.x() + 50), int(rect.y() + 24), self.title[:20])

        # 文本内容
        text_y = 40
        painter.setPen(QColor(200, 200, 205) if dark else QColor(60, 60, 65))
        painter.setFont(QFont("Arial", 10))

        max_lines = int((rect.height() - 60) / self.LINE_HEIGHT)
        lines = self.text.split('\n')
        drawn = 0
        for line in lines:
            if drawn >= max_lines:
                break
            # 自动换行
            while len(line) > 28 and drawn < max_lines:
                painter.drawText(int(rect.x() + 12), int(rect.y() + text_y + drawn * self.LINE_HEIGHT), line[:28])
                line = line[28:]
                drawn += 1
            if drawn < max_lines:
                painter.drawText(int(rect.x() + 12), int(rect.y() + text_y + drawn * self.LINE_HEIGHT), line[:28])
                drawn += 1

        if drawn >= max_lines and len(self.text) > max_lines * 28:
            painter.setPen(QColor(142, 142, 147))
            painter.drawText(int(rect.x() + 12), int(rect.y() + text_y + drawn * self.LINE_HEIGHT), "...")

        # 底部字数统计
        char_count = len(self.text)
        painter.setPen(QColor(142, 142, 147) if dark else QColor(174, 174, 178))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(
            int(rect.x() + 12), int(rect.y() + rect.height() - 8),
            f"{char_count} 字"
        )

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.update()

    def hoverEnterEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


# ==================== 剧本画布视图 ====================

class ScriptCanvasView(BaseCanvasView):
    """剧本画布 - 显示文本块卡片"""

    card_selected = pyqtSignal(int)
    card_double_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: List[TextBlockCard] = []
        self._selected_card: Optional[TextBlockCard] = None

    def load_text_blocks(self, blocks: list):
        """加载文本块列表 blocks = [{"index": 0, "text": "...", "title": "场景1"}, ...]"""
        self._canvas_scene.clear()
        self._cards.clear()
        self._selected_card = None

        cols = max(1, min(5, len(blocks)))
        for i, block in enumerate(blocks):
            card = TextBlockCard(
                block.get('index', i),
                block.get('text', ''),
                block.get('title', '')
            )
            row = i // cols
            col = i % cols
            x = 30 + col * (TextBlockCard.CARD_WIDTH + 24)
            y = 30 + row * (card.rect().height() + 24)
            card.setPos(x, y)
            self._canvas_scene.addItem(card)
            self._cards.append(card)

        self._expand_scene_rect()

    def load_source_text(self, text: str):
        """将整段文本拆成段落，每段一个 TextBlockCard"""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if not paragraphs:
            self.show_placeholder()
            return

        blocks = []
        for i, para in enumerate(paragraphs):
            blocks.append({"index": i, "text": para, "title": ""})
        self.load_text_blocks(blocks)

    def load_scenes(self, scenes: list):
        """加载分割后的场景"""
        blocks = []
        for i, s in enumerate(scenes):
            text = s.get('scene_text', s.get('subtitle_text', ''))
            title = s.get('description', f'场景 {i+1}')
            blocks.append({"index": i, "text": text, "title": title})
        self.load_text_blocks(blocks)

    def show_placeholder(self):
        """在画布中心显示占位提示"""
        self._canvas_scene.clear()
        self._cards.clear()
        self._selected_card = None

        dark = theme.is_dark()
        text = self._canvas_scene.addText(
            "导入文案开始\n支持 SRT 字幕、剧本文件或粘贴文本",
            QFont("Arial", 14)
        )
        text.setDefaultTextColor(QColor(142, 142, 147) if dark else QColor(174, 174, 178))
        br = text.boundingRect()
        text.setPos(-br.width() / 2, -br.height() / 2)

    def mousePressEvent(self, event):
        """点击检测"""
        item = self.itemAt(event.pos())
        if isinstance(item, TextBlockCard):
            if self._selected_card and self._selected_card is not item:
                self._selected_card.set_selected(False)
            self._selected_card = item
            item.set_selected(True)
            self.card_selected.emit(item.block_index)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            if self._selected_card:
                self._selected_card.set_selected(False)
                self._selected_card = None
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, TextBlockCard):
            self.card_double_clicked.emit(item.block_index)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._expand_scene_rect()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)


# ==================== 解说模式页（原 ScriptZone 逻辑）====================

class CommentaryModePanel(QWidget):
    """
    解说模式页 - SRT 导入 + 三步工作流
    从原 ScriptZone 逻辑迁移
    """

    analysis_completed = pyqtSignal(int, list, list)
    project_created = pyqtSignal(dict)

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self._source_text = ""
        self._characters = []
        self._scenes = []
        self._current_step = 0

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 画布
        self._canvas = ScriptCanvasView()
        layout.addWidget(self._canvas, 1)

        # === 浮动导入按钮组（右上角）===
        self._import_float = QWidget(self)
        import_layout = QHBoxLayout(self._import_float)
        import_layout.setContentsMargins(10, 6, 10, 6)
        import_layout.setSpacing(8)

        self._srt_btn = QPushButton("导入 SRT")
        self._srt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._srt_btn.clicked.connect(self._import_srt)
        import_layout.addWidget(self._srt_btn)

        self._script_btn = QPushButton("导入剧本")
        self._script_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._script_btn.clicked.connect(self._import_script)
        import_layout.addWidget(self._script_btn)

        self._paste_btn = QPushButton("粘贴文本")
        self._paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._paste_btn.clicked.connect(self._paste_text)
        import_layout.addWidget(self._paste_btn)

        self._import_float.adjustSize()
        self._import_float.raise_()

        # === 浮动步骤导航（底部居中）===
        self._nav_float = QWidget(self)
        nav_layout = QHBoxLayout(self._nav_float)
        nav_layout.setContentsMargins(12, 6, 12, 6)
        nav_layout.setSpacing(10)

        self.step_label = QLabel("步骤 0/3：文案预览")
        nav_layout.addWidget(self.step_label)

        self.prev_btn = QPushButton("上一步")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(self._go_prev)
        self.prev_btn.setVisible(False)
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("下一步")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self._go_next)
        self.next_btn.setVisible(False)
        nav_layout.addWidget(self.next_btn)

        self.confirm_btn = QPushButton("确认并保存")
        self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_btn.clicked.connect(self._confirm_analysis)
        self.confirm_btn.setVisible(False)
        nav_layout.addWidget(self.confirm_btn)

        self._start_btn = QPushButton("开始分镜分析")
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._start_analysis)
        self._start_btn.setVisible(False)
        nav_layout.addWidget(self._start_btn)

        self._nav_float.adjustSize()
        self._nav_float.raise_()

        # === 浮动工作流面板（居中覆盖）===
        self._workflow_overlay = QFrame(self)
        self._workflow_overlay.setVisible(False)
        self._workflow_overlay_layout = QVBoxLayout(self._workflow_overlay)
        self._workflow_overlay_layout.setContentsMargins(20, 20, 20, 20)

        # 关闭按钮
        close_row = QHBoxLayout()
        close_row.addStretch()
        self._overlay_close_btn = QPushButton("X")
        self._overlay_close_btn.setFixedSize(30, 30)
        self._overlay_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._overlay_close_btn.clicked.connect(self._close_workflow_overlay)
        close_row.addWidget(self._overlay_close_btn)
        self._workflow_overlay_layout.addLayout(close_row)

        # 工作流 widget 容器
        self._workflow_container = QWidget()
        self._workflow_container_layout = QVBoxLayout(self._workflow_container)
        self._workflow_container_layout.setContentsMargins(0, 0, 0, 0)
        self._workflow_overlay_layout.addWidget(self._workflow_container, 1)

        # 延迟创建工作流 widget
        self.character_widget = None
        self.scene_adjust_widget = None
        self._scene_split_widget = None

        # 初始占位
        self._canvas.show_placeholder()
        self._apply_theme()

    def set_source_text(self, text: str):
        """外部设置源文本"""
        self._source_text = text
        self._canvas.load_source_text(text)
        self._start_btn.setVisible(True)
        if self.character_widget:
            self.character_widget.set_source_text(text)

    def _ensure_character_widget(self):
        if self.character_widget is None:
            self.character_widget = CharacterExtractionWidget()
            self.character_widget.characters_changed.connect(self._on_characters_changed)
        return self.character_widget

    def _ensure_scene_adjust_widget(self):
        if self.scene_adjust_widget is None:
            self.scene_adjust_widget = SceneAdjustmentWidget()
        return self.scene_adjust_widget

    def _ensure_scene_split_widget(self):
        if self._scene_split_widget is None:
            self._scene_split_widget = self._create_scene_split_page()
        return self._scene_split_widget

    def _create_scene_split_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        self._split_hint = QLabel("正在进行场景分割...")
        layout.addWidget(self._split_hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.deepseek_split_btn = QPushButton("DeepSeek AI 分割")
        self.deepseek_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deepseek_split_btn.clicked.connect(self._start_deepseek_split)
        btn_row.addWidget(self.deepseek_split_btn)

        self.paragraph_split_btn = QPushButton("快速分割")
        self.paragraph_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paragraph_split_btn.clicked.connect(self._start_paragraph_split)
        btn_row.addWidget(self.paragraph_split_btn)

        btn_row.addStretch()

        self.split_status_label = QLabel("")
        btn_row.addWidget(self.split_status_label)

        layout.addLayout(btn_row)

        self.split_result_edit = QTextEdit()
        self.split_result_edit.setReadOnly(True)
        self.split_result_edit.setPlaceholderText("分割结果将显示在这里...")
        layout.addWidget(self.split_result_edit, 1)

        return page

    # ==================== 主题 ====================

    def apply_theme(self, dark: bool = None):
        self._apply_theme()

    def _apply_theme(self):
        self._import_float.setStyleSheet(theme.float_panel_style())
        self._nav_float.setStyleSheet(theme.float_panel_style())

        fbtn = theme.float_btn_style()
        self._srt_btn.setStyleSheet(fbtn)
        self._script_btn.setStyleSheet(fbtn)
        self._paste_btn.setStyleSheet(fbtn)
        self.prev_btn.setStyleSheet(fbtn)

        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()}; color: white;
                border: none; border-radius: 8px;
                padding: 6px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
        """)
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.success()}; color: white;
                border: none; border-radius: 8px;
                padding: 6px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #34c759; }}
        """)
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()}; color: white;
                border: none; border-radius: 8px;
                padding: 6px 16px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
        """)
        self.step_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 12px; background: transparent;")

        self._workflow_overlay.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.bg_elevated()};
                border-radius: 16px;
                border: 1px solid {theme.border()};
            }}
        """)
        self._overlay_close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.btn_bg()}; color: {theme.text_secondary()};
                border: 1px solid {theme.btn_border()}; border-radius: 15px;
                font-size: 14px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.btn_bg_hover()}; color: {theme.text_primary()}; }}
        """)

        if self._scene_split_widget:
            self._split_hint.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 13px; background: transparent;")
            self.deepseek_split_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.accent()}; color: white;
                    border: none; border-radius: 8px; padding: 8px 16px;
                    font-size: 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
            """)
            self.paragraph_split_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.btn_bg()}; color: {theme.text_secondary()};
                    border: 1px solid {theme.btn_border()}; border-radius: 8px;
                    padding: 8px 16px; font-size: 12px; font-weight: 500;
                }}
                QPushButton:hover {{ background-color: {theme.btn_bg_hover()}; color: {theme.text_primary()}; }}
            """)
            self.split_status_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 11px; background: transparent;")
            self.split_result_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {theme.bg_secondary()};
                    border: 1px solid {theme.border()};
                    border-radius: 12px; padding: 14px;
                    color: {theme.text_primary()}; font-size: 13px;
                }}
            """)

        self._canvas.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_floats()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_floats()

    def _position_floats(self):
        self._import_float.adjustSize()
        iw = self._import_float.sizeHint().width()
        ih = self._import_float.sizeHint().height()
        self._import_float.setGeometry(self.width() - iw - 12, 12, iw, ih)

        self._nav_float.adjustSize()
        nw = self._nav_float.sizeHint().width()
        nh = self._nav_float.sizeHint().height()
        self._nav_float.setGeometry((self.width() - nw) // 2, self.height() - nh - 12, nw, nh)

        if self._workflow_overlay.isVisible():
            ow = min(700, self.width() - 60)
            oh = min(550, self.height() - 80)
            self._workflow_overlay.setGeometry(
                (self.width() - ow) // 2,
                (self.height() - oh) // 2,
                ow, oh
            )

    # ==================== 导入操作 ====================

    def _import_srt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择SRT字幕文件", "",
            "SRT字幕文件 (*.srt);;所有文件 (*.*)"
        )
        if file_path:
            dialog = SrtImportDialog(file_path, self)
            dialog.project_created.connect(self._on_srt_project_created)
            dialog.exec()

    def _on_srt_project_created(self, project_data):
        self.project_created.emit(project_data)

    def _import_script(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择剧本文件", "",
            "文本文件 (*.txt);;Word文档 (*.docx);;所有文件 (*.*)"
        )
        if not file_path:
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
                return
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取文件: {e}")
            return
        if not content.strip():
            QMessageBox.warning(self, "错误", "文件内容为空")
            return
        self._set_source_text(content)
        if self.data_hub and self.data_hub.current_project_id:
            self.data_hub.save_source_content(self.data_hub.current_project_id, content, "script")

    def _paste_text(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text and text.strip():
            self._set_source_text(text)
        else:
            QMessageBox.information(self, "提示", "剪贴板中没有文本内容")

    def _set_source_text(self, text: str):
        self._source_text = text
        self._canvas.load_source_text(text)
        self._start_btn.setVisible(True)
        if self.character_widget:
            self.character_widget.set_source_text(text)

    # ==================== 工作流覆盖层 ====================

    def _show_workflow_overlay(self, widget: QWidget):
        while self._workflow_container_layout.count():
            item = self._workflow_container_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        self._workflow_container_layout.addWidget(widget)
        self._workflow_overlay.setVisible(True)
        self._workflow_overlay.raise_()
        self._position_floats()

    def _close_workflow_overlay(self):
        self._workflow_overlay.setVisible(False)

    # ==================== 分镜分析流程 ====================

    def _start_analysis(self):
        if not self._source_text:
            QMessageBox.warning(self, "提示", "请先导入文案")
            return
        self._go_to_step(1)

    def _go_to_step(self, step: int):
        self._current_step = step
        step_names = ["文案预览", "角色提取", "场景分割", "场景调整"]
        self.step_label.setText(f"步骤 {step}/3：{step_names[step]}")
        self.prev_btn.setVisible(step > 0)
        self.next_btn.setVisible(0 < step < 3)
        self.confirm_btn.setVisible(step == 3)
        self._start_btn.setVisible(step == 0 and bool(self._source_text))
        self._nav_float.adjustSize()
        self._position_floats()

        if step == 0:
            self._close_workflow_overlay()
            if self._source_text:
                if self._scenes:
                    self._canvas.load_scenes(self._scenes)
                else:
                    self._canvas.load_source_text(self._source_text)
        elif step == 1:
            widget = self._ensure_character_widget()
            widget.set_source_text(self._source_text)
            self._show_workflow_overlay(widget)
        elif step == 2:
            widget = self._ensure_scene_split_widget()
            self._show_workflow_overlay(widget)
        elif step == 3:
            widget = self._ensure_scene_adjust_widget()
            if self._scenes:
                widget.set_scenes(self._scenes)
            self._show_workflow_overlay(widget)

    def _go_prev(self):
        if self._current_step > 0:
            self._go_to_step(self._current_step - 1)

    def _go_next(self):
        if self._current_step == 1:
            if self.character_widget:
                self._characters = self.character_widget.get_characters()
            self._go_to_step(2)
        elif self._current_step == 2:
            if self._scenes:
                self._go_to_step(3)
            else:
                QMessageBox.warning(self, "提示", "请先进行场景分割")

    def _on_characters_changed(self, characters: list):
        self._characters = characters

    def _start_deepseek_split(self):
        self._do_split("deepseek")

    def _start_paragraph_split(self):
        self._do_split("paragraph")

    def _do_split(self, mode: str):
        if not self._source_text:
            return
        self.deepseek_split_btn.setEnabled(False)
        self.paragraph_split_btn.setEnabled(False)
        self.split_status_label.setText("正在分割..." if mode == "paragraph" else "DeepSeek AI 分割中...")
        from ..storyboard_analysis_dialog import SceneSplitWorker
        char_names = [c.get('name', '') for c in self._characters]
        self._split_worker = SceneSplitWorker(self._source_text, char_names, mode=mode)
        self._split_worker.split_completed.connect(self._on_split_completed)
        self._split_worker.split_failed.connect(self._on_split_failed)
        self._split_worker.start()

    def _on_split_completed(self, scenes: list):
        self.deepseek_split_btn.setEnabled(True)
        self.paragraph_split_btn.setEnabled(True)
        self._scenes = scenes
        self.split_status_label.setText(f"已分割为 {len(scenes)} 个场景")
        preview_text = ""
        for i, s in enumerate(scenes):
            text = s.get('scene_text', s.get('subtitle_text', ''))
            desc = s.get('description', '')
            preview_text += f"--- 场景 {i+1} ---\n"
            if desc:
                preview_text += f"[{desc}]\n"
            preview_text += f"{text}\n\n"
        self.split_result_edit.setPlainText(preview_text)
        self._canvas.load_scenes(scenes)

    def _on_split_failed(self, error: str):
        self.deepseek_split_btn.setEnabled(True)
        self.paragraph_split_btn.setEnabled(True)
        self.split_status_label.setText(f"分割失败: {error}")

    def _confirm_analysis(self):
        scenes = self.scene_adjust_widget.get_scenes() if (self.scene_adjust_widget and hasattr(self.scene_adjust_widget, 'get_scenes')) else self._scenes
        characters = self._characters
        if not scenes:
            QMessageBox.warning(self, "提示", "没有场景数据")
            return
        if self.data_hub and self.data_hub.current_project_id:
            success = self.data_hub.save_analysis_results(
                self.data_hub.current_project_id, characters, scenes
            )
            if success:
                self.analysis_completed.emit(self.data_hub.current_project_id, scenes, characters)
                self._close_workflow_overlay()
                self._go_to_step(0)
                QMessageBox.information(self, "成功", "分镜分析结果已保存")
            else:
                QMessageBox.warning(self, "错误", "保存分析结果失败")
        else:
            self.analysis_completed.emit(0, scenes, characters)


# ==================== 主区域 ====================

class ScriptZone(QWidget):
    """
    剧本与分镜拆解区
    QStackedWidget 模式切换：模式选择页 / 剧情模式页 / 解说模式页
    """

    analysis_completed = pyqtSignal(int, list, list)
    project_created = pyqtSignal(dict)

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self._current_mode = None  # "story" / "commentary" / None

        self._init_ui()
        self._connect_data_hub()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()

        # page 0: 模式选择
        self._mode_panel = ModeSelectPanel()
        self._mode_panel.mode_selected.connect(self._on_mode_selected)
        self._stack.addWidget(self._mode_panel)

        # page 1: 剧情模式（延迟导入，避免循环）
        self._story_panel = None

        # page 2: 解说模式
        self._commentary_panel = CommentaryModePanel(data_hub=self.data_hub)
        self._commentary_panel.analysis_completed.connect(self.analysis_completed.emit)
        self._commentary_panel.project_created.connect(self.project_created.emit)
        self._stack.addWidget(self._commentary_panel)  # index 1 暂时

        layout.addWidget(self._stack)

    def _ensure_story_panel(self):
        """延迟创建剧情模式面板"""
        if self._story_panel is None:
            from .story_mode_panel import StoryModePanel
            self._story_panel = StoryModePanel(data_hub=self.data_hub)
            self._story_panel.analysis_completed.connect(self.analysis_completed.emit)
            # 插入到 index 1（解说模式变为 index 2）
            self._stack.insertWidget(1, self._story_panel)

            # 延迟创建时，DataHub 的 project_loaded 信号已错过
            # 需要手动补发当前项目信息
            if self.data_hub and self.data_hub.current_project_id:
                project_info = self.data_hub.project_info or {}
                self._story_panel._canvas.on_project_loaded(
                    self.data_hub.current_project_id, project_info
                )
                # 如果已有场次数据也一并加载
                if self.data_hub.acts_data:
                    self._story_panel._canvas.on_acts_loaded(
                        self.data_hub.acts_data
                    )

        return self._story_panel

    def _on_mode_selected(self, mode: str):
        """切换模式"""
        self._current_mode = mode
        if mode == "story":
            self._ensure_story_panel()
            self._stack.setCurrentIndex(1)
        elif mode == "commentary":
            idx = 2 if self._story_panel else 1
            self._stack.setCurrentIndex(idx)

    def _connect_data_hub(self):
        if not self.data_hub:
            return
        self.data_hub.project_loaded.connect(self._on_project_loaded)

    def _on_project_loaded(self, project_id: int, project_info: dict):
        """项目加载后，根据 source_type 决定模式"""
        source_type = project_info.get('source_type', '')
        source = project_info.get('source_content', '')

        if source_type == 'srt':
            # SRT 项目 → 解说模式
            self._on_mode_selected("commentary")
            if source:
                self._commentary_panel.set_source_text(source)
        elif source_type in ('story', 'novel', 'script_story'):
            # 剧本/小说项目 → 剧情模式
            self._on_mode_selected("story")
        elif not source_type:
            # 空白项目（无 source_type）→ 直接进入剧情模式（画布以 WELCOME 状态启动）
            self._on_mode_selected("story")
        else:
            # 未知类型，显示模式选择
            self._stack.setCurrentIndex(0)

    def get_current_mode(self) -> Optional[str]:
        """获取当前模式"""
        return self._current_mode

    def switch_to_mode_select(self):
        """返回模式选择页"""
        self._stack.setCurrentIndex(0)
        self._current_mode = None

    # ==================== 主题 ====================

    def apply_theme(self, dark: bool):
        self._mode_panel.apply_theme()
        self._commentary_panel.apply_theme(dark)
        if self._story_panel and hasattr(self._story_panel, 'apply_theme'):
            self._story_panel.apply_theme(dark)
