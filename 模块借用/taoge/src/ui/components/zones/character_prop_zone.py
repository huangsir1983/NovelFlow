"""
涛割 - 角色道具区
QGraphicsView 无限画布 + 角色卡片 / 道具卡片，支持自由拖拽、缩放、平移。
画布风格：dot grid 背景 + 浮动按钮，支持深色/浅色主题。
"""

import os
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QMessageBox, QDialog, QDialogButtonBox,
    QGraphicsRectItem, QGraphicsItem, QGraphicsTextItem, QGraphicsView,
    QStyleOptionGraphicsItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from ui import theme
from ui.pixmap_cache import PixmapCache
from ui.components.base_canvas_view import BaseCanvasView, LOD_TEXT_MIN_PX


# ==================== 画布卡片 ====================

class CharacterCanvasCard(QGraphicsRectItem):
    """画布上的角色卡片"""

    CARD_WIDTH = 200
    CARD_HEIGHT = 160
    CORNER_RADIUS = 10

    def __init__(self, char_data: dict, parent=None):
        super().__init__(parent)
        self.char_data = char_data
        self._is_selected = False

        self.setRect(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self._thumbnail = None
        self._load_thumbnail()

    def _load_thumbnail(self):
        ref_img = self.char_data.get('main_reference_image', '')
        if ref_img and os.path.exists(ref_img):
            cache = PixmapCache.instance()
            self._thumbnail = cache.get_scaled(ref_img, 60, 60)

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

        # 卡片背景
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

        # LOD 文本隐藏优化
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        # 参考图 / 首字母占位
        avatar_rect = QRectF(rect.width() / 2 - 30, 14, 60, 60)
        if self._thumbnail:
            painter.drawPixmap(int(avatar_rect.x()), int(avatar_rect.y()), self._thumbnail)
        else:
            painter.setBrush(QBrush(QColor(10, 132, 255, 30)))
            painter.setPen(QPen(QColor(10, 132, 255, 60), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(avatar_rect, 8, 8)

            if not _hide_text:
                name = self.char_data.get('name', '?')
                painter.setPen(QColor(10, 132, 255, 140))
                painter.setFont(QFont("Arial", 18, QFont.Weight.Bold))
                painter.drawText(avatar_rect, Qt.AlignmentFlag.AlignCenter, name[0] if name else '?')

        if not _hide_text:
            # 角色名
            name = self.char_data.get('name', '未知')
            painter.setPen(QColor(245, 245, 247) if dark else QColor(28, 28, 30))
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            name_rect = QRectF(8, 82, rect.width() - 16, 20)
            painter.drawText(name_rect, Qt.AlignmentFlag.AlignHCenter, name)

            # 类型标签
            type_names = {"human": "人物", "animal": "动物", "creature": "生物", "object": "物体"}
            type_name = type_names.get(self.char_data.get('character_type', ''), '角色')
            painter.setPen(QColor(10, 132, 255))
            painter.setFont(QFont("Arial", 9))
            type_rect = QRectF(8, 104, rect.width() - 16, 16)
            painter.drawText(type_rect, Qt.AlignmentFlag.AlignHCenter, type_name)

            # 外观描述（截断）
            appearance = self.char_data.get('appearance', '')
            if appearance:
                display = appearance[:24] + ('...' if len(appearance) > 24 else '')
                painter.setPen(QColor(142, 142, 147) if dark else QColor(110, 110, 115))
                painter.setFont(QFont("Arial", 9))
                desc_rect = QRectF(10, 124, rect.width() - 20, 30)
                painter.drawText(desc_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, display)

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


class PropCanvasCard(QGraphicsRectItem):
    """画布上的道具卡片"""

    CARD_WIDTH = 160
    CARD_HEIGHT = 100
    CORNER_RADIUS = 8

    def __init__(self, prop_data: dict, parent=None):
        super().__init__(parent)
        self.prop_data = prop_data
        self._is_selected = False

        self.setRect(0, 0, self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

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
        if self._is_selected:
            bg = QColor(50, 45, 35) if dark else QColor(255, 245, 230)
        else:
            bg = QColor(38, 38, 42) if dark else QColor(255, 255, 255)
        painter.setBrush(QBrush(bg))

        if self._is_selected:
            painter.setPen(QPen(QColor(255, 159, 10), 2))
        else:
            painter.setPen(QPen(QColor(60, 60, 65) if dark else QColor(210, 210, 215), 1))

        painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        # LOD 文本隐藏优化
        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)

        # 图标（首字母圆）
        icon_rect = QRectF(12, rect.height() / 2 - 18, 36, 36)
        painter.setBrush(QBrush(QColor(255, 159, 10, 30)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(icon_rect, 6, 6)

        if not _hide_text:
            name = self.prop_data.get('name', '?')
            painter.setPen(QColor(255, 159, 10))
            painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, name[0] if name else '?')

            # 名称
            painter.setPen(QColor(245, 245, 247) if dark else QColor(28, 28, 30))
            painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            painter.drawText(QRectF(56, 20, rect.width() - 64, 20), Qt.AlignmentFlag.AlignVCenter, name)

            # 描述
            desc = self.prop_data.get('description', '')
            if desc:
                display = desc[:20] + ('...' if len(desc) > 20 else '')
                painter.setPen(QColor(142, 142, 147) if dark else QColor(110, 110, 115))
                painter.setFont(QFont("Arial", 9))
                painter.drawText(QRectF(56, 44, rect.width() - 64, 40), Qt.AlignmentFlag.AlignTop, display)

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


# ==================== 资产画布视图 ====================

class AssetCanvasView(BaseCanvasView):
    """资产画布 - 角色卡 + 道具卡"""

    character_selected = pyqtSignal(dict)
    character_double_clicked = pyqtSignal(dict)
    prop_selected = pyqtSignal(dict)
    prop_double_clicked = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._char_cards: List[CharacterCanvasCard] = []
        self._prop_cards: List[PropCanvasCard] = []
        self._selected_card = None
        self._group_rects = []

    def load_characters(self, characters: list):
        """加载角色卡到画布"""
        # 清除旧角色卡
        for card in self._char_cards:
            if card.scene():
                self._canvas_scene.removeItem(card)
        self._char_cards.clear()

        for i, char in enumerate(characters):
            card = CharacterCanvasCard(char)
            self._char_cards.append(card)
            self._canvas_scene.addItem(card)

        self._auto_layout()
        self._expand_scene_rect()

    def load_props(self, props: list):
        """加载道具卡到画布"""
        for card in self._prop_cards:
            if card.scene():
                self._canvas_scene.removeItem(card)
        self._prop_cards.clear()

        for i, prop in enumerate(props):
            card = PropCanvasCard(prop)
            self._prop_cards.append(card)
            self._canvas_scene.addItem(card)

        self._auto_layout()
        self._expand_scene_rect()

    def _auto_layout(self):
        """自动排列：角色区（左侧）+ 道具区（右侧）"""
        # 清除旧分组矩形和标签
        for item in self._group_rects:
            if item.scene():
                self._canvas_scene.removeItem(item)
        self._group_rects.clear()

        dark = theme.is_dark()
        x_offset = 30
        y_start = 60

        # 角色区域标签
        if self._char_cards:
            char_label = self._canvas_scene.addText("角色", QFont("Arial", 14, QFont.Weight.Bold))
            char_label.setDefaultTextColor(QColor(10, 132, 255, 180))
            char_label.setPos(x_offset, 20)
            self._group_rects.append(char_label)

            cols = max(1, min(4, len(self._char_cards)))
            for i, card in enumerate(self._char_cards):
                row = i // cols
                col = i % cols
                x = x_offset + col * (CharacterCanvasCard.CARD_WIDTH + 20)
                y = y_start + row * (CharacterCanvasCard.CARD_HEIGHT + 20)
                card.setPos(x, y)

            # 分组矩形
            total_rows = (len(self._char_cards) + cols - 1) // cols
            group_w = cols * (CharacterCanvasCard.CARD_WIDTH + 20) + 10
            group_h = total_rows * (CharacterCanvasCard.CARD_HEIGHT + 20) + 10
            group_rect = self._canvas_scene.addRect(
                QRectF(x_offset - 10, y_start - 10, group_w, group_h),
                QPen(QColor(10, 132, 255, 40), 1, Qt.PenStyle.DashLine),
                QBrush(QColor(10, 132, 255, 8))
            )
            group_rect.setZValue(-1)
            self._group_rects.append(group_rect)

        # 道具区域
        prop_x_offset = x_offset
        if self._char_cards:
            cols = max(1, min(4, len(self._char_cards)))
            prop_x_offset = x_offset + cols * (CharacterCanvasCard.CARD_WIDTH + 20) + 60

        if self._prop_cards:
            prop_label = self._canvas_scene.addText("道具", QFont("Arial", 14, QFont.Weight.Bold))
            prop_label.setDefaultTextColor(QColor(255, 159, 10, 180))
            prop_label.setPos(prop_x_offset, 20)
            self._group_rects.append(prop_label)

            prop_cols = max(1, min(4, len(self._prop_cards)))
            for i, card in enumerate(self._prop_cards):
                row = i // prop_cols
                col = i % prop_cols
                x = prop_x_offset + col * (PropCanvasCard.CARD_WIDTH + 16)
                y = y_start + row * (PropCanvasCard.CARD_HEIGHT + 16)
                card.setPos(x, y)

            total_rows = (len(self._prop_cards) + prop_cols - 1) // prop_cols
            group_w = prop_cols * (PropCanvasCard.CARD_WIDTH + 16) + 10
            group_h = total_rows * (PropCanvasCard.CARD_HEIGHT + 16) + 10
            group_rect = self._canvas_scene.addRect(
                QRectF(prop_x_offset - 10, y_start - 10, group_w, group_h),
                QPen(QColor(255, 159, 10, 40), 1, Qt.PenStyle.DashLine),
                QBrush(QColor(255, 159, 10, 8))
            )
            group_rect.setZValue(-1)
            self._group_rects.append(group_rect)

    def show_placeholder(self):
        """显示占位提示"""
        self._canvas_scene.clear()
        self._char_cards.clear()
        self._prop_cards.clear()
        self._group_rects.clear()

        dark = theme.is_dark()
        text = self._canvas_scene.addText(
            "暂无角色和道具\n完成分镜分析后自动出现",
            QFont("Arial", 14)
        )
        text.setDefaultTextColor(QColor(142, 142, 147) if dark else QColor(174, 174, 178))
        br = text.boundingRect()
        text.setPos(-br.width() / 2, -br.height() / 2)

    def mousePressEvent(self, event):
        """点击检测：选中角色卡或道具卡"""
        item = self.itemAt(event.pos())

        if isinstance(item, (CharacterCanvasCard, PropCanvasCard)):
            # 清除旧选中
            if self._selected_card and self._selected_card is not item:
                self._selected_card.set_selected(False)
            self._selected_card = item
            item.set_selected(True)

            if isinstance(item, CharacterCanvasCard):
                self.character_selected.emit(item.char_data)
            else:
                self.prop_selected.emit(item.prop_data)

            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            if self._selected_card:
                self._selected_card.set_selected(False)
                self._selected_card = None
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击角色/道具卡"""
        item = self.itemAt(event.pos())
        if isinstance(item, CharacterCanvasCard):
            self.character_double_clicked.emit(item.char_data)
        elif isinstance(item, PropCanvasCard):
            self.prop_double_clicked.emit(item.prop_data)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        super().mouseReleaseEvent(event)
        self._expand_scene_rect()
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)


# ==================== 主区域 ====================

class CharacterPropZone(QWidget):
    """
    角色道具区 - QGraphicsView 无限画布
    角色卡 + 道具卡以分组形式排列，支持自由拖拽
    """

    character_edited = pyqtSignal(dict)
    prop_edited = pyqtSignal(dict)

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub

        self._init_ui()
        self._connect_data_hub()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 画布
        self._canvas = AssetCanvasView()
        self._canvas.character_double_clicked.connect(self._on_edit_character)
        self._canvas.prop_double_clicked.connect(self._on_edit_prop)
        layout.addWidget(self._canvas, 1)

        # 浮动按钮面板（右上角）
        self._float_panel = QWidget(self)
        float_layout = QHBoxLayout(self._float_panel)
        float_layout.setContentsMargins(10, 6, 10, 6)
        float_layout.setSpacing(8)

        self.char_count_label = QLabel("0 个角色")
        float_layout.addWidget(self.char_count_label)

        self._add_char_btn = QPushButton("+ 添加角色")
        self._add_char_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_char_btn.clicked.connect(self._add_character)
        float_layout.addWidget(self._add_char_btn)

        sep = QFrame()
        sep.setFixedSize(1, 20)
        float_layout.addWidget(sep)

        self.prop_count_label = QLabel("0 个道具")
        float_layout.addWidget(self.prop_count_label)

        self._add_prop_btn = QPushButton("+ 添加道具")
        self._add_prop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_prop_btn.clicked.connect(self._add_prop)
        float_layout.addWidget(self._add_prop_btn)

        self._float_panel.adjustSize()
        self._float_panel.raise_()

        # 初始占位
        self._canvas.show_placeholder()
        self._apply_theme()

    # ==================== 主题 ====================

    def apply_theme(self, dark: bool):
        self._apply_theme()

    def _apply_theme(self):
        self._float_panel.setStyleSheet(theme.float_panel_style())

        self.char_count_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 12px; background: transparent;")
        self.prop_count_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 12px; background: transparent;")

        self._add_char_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent_bg()}; color: {theme.accent()};
                border: 1px solid rgba(10, 132, 255, 0.2); border-radius: 8px;
                padding: 6px 14px; font-size: 12px; font-weight: 500;
            }}
            QPushButton:hover {{ background-color: rgba(10, 132, 255, 0.2); }}
        """)
        self._add_prop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 159, 10, 0.12); color: #ff9f0a;
                border: 1px solid rgba(255, 159, 10, 0.2); border-radius: 8px;
                padding: 6px 14px; font-size: 12px; font-weight: 500;
            }}
            QPushButton:hover {{ background-color: rgba(255, 159, 10, 0.2); }}
        """)

        # 分隔线
        for child in self._float_panel.findChildren(QFrame):
            child.setStyleSheet(f"background-color: {theme.separator()};")

        # 刷新画布
        self._canvas.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_floats()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_floats()

    def _position_floats(self):
        self._float_panel.adjustSize()
        fw = self._float_panel.sizeHint().width()
        fh = self._float_panel.sizeHint().height()
        self._float_panel.setGeometry(self.width() - fw - 12, 12, fw, fh)

    # ==================== DataHub ====================

    def _connect_data_hub(self):
        if not self.data_hub:
            return
        self.data_hub.characters_loaded.connect(self._load_characters)
        self.data_hub.props_loaded.connect(self._load_props)
        self.data_hub.characters_updated.connect(self._load_characters)
        self.data_hub.scenes_loaded.connect(self._on_scenes_loaded)

    def _on_scenes_loaded(self, scenes: list):
        self._refresh_character_cards()

    # ==================== 角色管理 ====================

    def _load_characters(self, characters: list):
        self._canvas.load_characters(characters)
        self.char_count_label.setText(f"{len(characters)} 个角色")
        if not characters and not self._canvas._prop_cards:
            self._canvas.show_placeholder()

    def _refresh_character_cards(self):
        if self.data_hub:
            self._load_characters(self.data_hub.characters_data)

    def _on_edit_character(self, char_data: dict):
        self.character_edited.emit(char_data)

    def _on_edit_prop(self, prop_data: dict):
        self.prop_edited.emit(prop_data)

    def _add_character(self):
        QMessageBox.information(self, "提示", "请通过分镜分析或导演画布区添加角色")

    # ==================== 道具管理 ====================

    def _load_props(self, props: list):
        self._canvas.load_props(props)
        self.prop_count_label.setText(f"{len(props)} 个道具")
        if not props and not self._canvas._char_cards:
            self._canvas.show_placeholder()

    def _on_delete_prop(self, prop_data: dict):
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除道具 \"{prop_data.get('name', '')}\" 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.data_hub:
                prop_id = prop_data.get('id')
                if prop_id:
                    self.data_hub.prop_controller.delete_prop(prop_id)
                    props = self.data_hub.prop_controller.get_project_props(
                        self.data_hub.current_project_id
                    )
                    self.data_hub.props_data = props
                    self.data_hub.props_loaded.emit(props)

    def _add_prop(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("添加道具")
        dialog.setFixedSize(300, 200)
        dialog.setStyleSheet(f"""
            QDialog {{ background-color: {theme.bg_secondary()}; border-radius: 12px; }}
            QLabel {{ color: {theme.text_primary()}; }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        name_label = QLabel("道具名称")
        name_label.setStyleSheet(f"color: {theme.text_secondary()}; font-size: 12px;")
        layout.addWidget(name_label)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("输入道具名称...")
        name_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.btn_bg()}; border: 1px solid {theme.border()};
                border-radius: 8px; padding: 8px 12px;
                color: {theme.text_primary()}; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {theme.accent()}; }}
        """)
        layout.addWidget(name_edit)

        desc_label = QLabel("描述（可选）")
        desc_label.setStyleSheet(f"color: {theme.text_secondary()}; font-size: 12px;")
        layout.addWidget(desc_label)

        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("简短描述...")
        desc_edit.setStyleSheet(name_edit.styleSheet())
        layout.addWidget(desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.btn_bg()}; border: 1px solid {theme.btn_border()};
                border-radius: 8px; padding: 8px 18px; color: {theme.text_primary()};
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {theme.btn_bg_hover()}; }}
        """)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            if name and self.data_hub and self.data_hub.current_project_id:
                result = self.data_hub.prop_controller.create_prop(
                    name=name,
                    prop_type='object',
                    project_id=self.data_hub.current_project_id,
                    description=desc_edit.text().strip(),
                )
                if result:
                    props = self.data_hub.prop_controller.get_project_props(
                        self.data_hub.current_project_id
                    )
                    self.data_hub.props_data = props
                    self.data_hub.props_loaded.emit(props)
