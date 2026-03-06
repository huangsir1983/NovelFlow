"""
涛割 - 画布左侧边栏
角色区 + 道具区，支持拖拽到场景卡片中关联。
使用统一 Asset 模型，MIME type 统一为 application/x-taoge-asset。
"""

import json
import os
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QMenu, QDialog, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QFont, QPixmap, QDrag, QColor

from ui.pixmap_cache import PixmapCache


# ── 资产类型颜色 ──
_ASSET_TYPE_STYLE = {
    'character': {'color': 'rgba(139, 92, 246, {})', 'label': '角色'},
    'scene_bg': {'color': 'rgba(80, 200, 120, {})', 'label': '场景'},
    'prop': {'color': 'rgba(255, 209, 102, {})', 'label': '道具'},
    'lighting_ref': {'color': 'rgba(255, 215, 0, {})', 'label': '照明'},
}


class DraggableAssetItem(QFrame):
    """统一的可拖拽资产项（替代旧的 DraggableCharacterItem / DraggablePropItem）"""

    def __init__(self, asset_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.asset_data = asset_data
        self._drag_start_pos = None

        asset_type = asset_data.get('asset_type', 'character')
        style_info = _ASSET_TYPE_STYLE.get(asset_type, _ASSET_TYPE_STYLE['character'])
        base_color = style_info['color']

        self.setFixedHeight(56)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {base_color.format('0.08')};
                border: 1px solid {base_color.format('0.15')};
                border-radius: 6px;
            }}
            QFrame:hover {{
                background-color: {base_color.format('0.15')};
                border-color: {base_color.format('0.3')};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # 缩略图
        thumb = QLabel()
        thumb.setFixedSize(48, 48)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        """)

        ref_img = asset_data.get('main_reference_image', '')
        if ref_img and os.path.exists(ref_img):
            scaled = PixmapCache.instance().get_scaled(ref_img, 48, 48)
            if scaled:
                thumb.setPixmap(scaled)
            else:
                thumb.setText(asset_data.get('name', '?')[0])
        else:
            name = asset_data.get('name', '?')
            thumb.setText(name[0] if name else '?')
            thumb.setStyleSheet(f"""
                background-color: {base_color.format('0.2')};
                border-radius: 4px;
                font-size: 18px;
                color: {base_color.format('0.8')};
                font-weight: bold;
            """)

        layout.addWidget(thumb)

        # 信息
        info = QVBoxLayout()
        info.setSpacing(2)

        name_label = QLabel(asset_data.get('name', '未知'))
        name_label.setStyleSheet("color: white; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        info.addWidget(name_label)

        type_label = QLabel(style_info['label'])
        type_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10px; border: none; background: transparent;")
        info.addWidget(type_label)

        layout.addLayout(info, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_pos is None:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < 10:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        data = json.dumps(self.asset_data, ensure_ascii=False, default=str)
        # 统一 MIME type
        mime_data.setData("application/x-taoge-asset", data.encode('utf-8'))
        # 向后兼容：同时设置旧 MIME type
        asset_type = self.asset_data.get('asset_type', '')
        if asset_type == 'character':
            mime_data.setData("application/x-taoge-character", data.encode('utf-8'))
        elif asset_type == 'prop':
            mime_data.setData("application/x-taoge-prop", data.encode('utf-8'))
        drag.setMimeData(mime_data)

        drag.exec(Qt.DropAction.CopyAction)
        self._drag_start_pos = None

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(45, 45, 48);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                color: white;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 122, 204, 0.5);
            }
        """)

        save_action = menu.addAction("保存到资产库")
        save_action.triggered.connect(lambda: self._save_to_library())

        delete_action = menu.addAction("移除")
        delete_action.triggered.connect(lambda: self.deleteLater())

        menu.exec(event.globalPos())

    def _save_to_library(self):
        """保存到资产库"""
        try:
            from services.controllers.asset_controller import AssetController
            ctrl = AssetController()
            a = self.asset_data
            ctrl.create_asset(
                name=a.get('name', '未知'),
                asset_type=a.get('asset_type', 'character'),
                description=a.get('description', ''),
                prompt_description=a.get('appearance', '') or a.get('prompt_description', ''),
            )
        except Exception as e:
            print(f"保存资产到库失败: {e}")


# ── 向后兼容别名 ──
class DraggableCharacterItem(DraggableAssetItem):
    """向后兼容：角色项"""
    def __init__(self, char_data: Dict[str, Any], parent=None):
        if 'asset_type' not in char_data:
            char_data = dict(char_data, asset_type='character')
        super().__init__(char_data, parent)
        self.char_data = char_data


class DraggablePropItem(DraggableAssetItem):
    """向后兼容：道具项"""
    def __init__(self, prop_data: Dict[str, Any], parent=None):
        if 'asset_type' not in prop_data:
            prop_data = dict(prop_data, asset_type='prop')
        super().__init__(prop_data, parent)
        self.prop_data = prop_data


class CanvasSidebar(QFrame):
    """画布左侧边栏 - 角色区 + 道具区"""

    character_ai_generate_requested = pyqtSignal()
    prop_ai_generate_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedWidth(220)
        self.setObjectName("canvasSidebar")
        self.setStyleSheet("""
            QFrame#canvasSidebar {
                background-color: rgb(25, 25, 30);
                border-right: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet("""
            QFrame {
                background-color: rgb(30, 30, 35);
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        title = QLabel("资产")
        title.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addWidget(header)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.02);
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(12)

        # === 角色区 ===
        char_header = QLabel("角色区")
        char_header.setStyleSheet("""
            color: rgba(139, 92, 246, 0.8);
            font-size: 11px;
            font-weight: bold;
            padding: 4px 0;
        """)
        content_layout.addWidget(char_header)

        self.characters_container = QVBoxLayout()
        self.characters_container.setSpacing(4)

        self.no_char_label = QLabel("暂无角色")
        self.no_char_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_char_label.setStyleSheet("color: rgba(255, 255, 255, 0.2); font-size: 10px; padding: 10px;")
        self.characters_container.addWidget(self.no_char_label)

        content_layout.addLayout(self.characters_container)

        # 角色操作按钮
        char_btn_layout = QVBoxLayout()
        char_btn_layout.setSpacing(4)

        ai_char_btn = QPushButton("AI 生成角色")
        ai_char_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ai_char_btn.clicked.connect(self.character_ai_generate_requested.emit)
        ai_char_btn.setStyleSheet(self._get_sidebar_btn_style(purple=True))
        char_btn_layout.addWidget(ai_char_btn)

        pick_char_btn = QPushButton("从角色库选择")
        pick_char_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pick_char_btn.clicked.connect(self._show_character_picker)
        pick_char_btn.setStyleSheet(self._get_sidebar_btn_style())
        char_btn_layout.addWidget(pick_char_btn)

        content_layout.addLayout(char_btn_layout)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.06);")
        content_layout.addWidget(sep)

        # === 道具区 ===
        prop_header = QLabel("道具区")
        prop_header.setStyleSheet("""
            color: rgba(255, 209, 102, 0.8);
            font-size: 11px;
            font-weight: bold;
            padding: 4px 0;
        """)
        content_layout.addWidget(prop_header)

        self.props_container = QVBoxLayout()
        self.props_container.setSpacing(4)

        self.no_prop_label = QLabel("暂无道具")
        self.no_prop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_prop_label.setStyleSheet("color: rgba(255, 255, 255, 0.2); font-size: 10px; padding: 10px;")
        self.props_container.addWidget(self.no_prop_label)

        content_layout.addLayout(self.props_container)

        # 道具操作按钮
        prop_btn_layout = QVBoxLayout()
        prop_btn_layout.setSpacing(4)

        ai_prop_btn = QPushButton("AI 生成道具")
        ai_prop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ai_prop_btn.clicked.connect(self.prop_ai_generate_requested.emit)
        ai_prop_btn.setStyleSheet(self._get_sidebar_btn_style(yellow=True))
        prop_btn_layout.addWidget(ai_prop_btn)

        add_prop_btn = QPushButton("添加道具")
        add_prop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_prop_btn.clicked.connect(self._show_add_prop_dialog)
        add_prop_btn.setStyleSheet(self._get_sidebar_btn_style())
        prop_btn_layout.addWidget(add_prop_btn)

        content_layout.addLayout(prop_btn_layout)

        content_layout.addStretch()

        # 底部提示
        hint = QLabel("拖拽角色或道具到场景卡片")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.15); font-size: 9px; padding: 8px;")
        content_layout.addWidget(hint)

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _get_sidebar_btn_style(self, purple=False, yellow=False):
        if purple:
            return """
                QPushButton {
                    background-color: rgba(139, 92, 246, 0.15);
                    color: rgba(139, 92, 246, 0.9);
                    border: 1px solid rgba(139, 92, 246, 0.3);
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: rgba(139, 92, 246, 0.25);
                }
            """
        elif yellow:
            return """
                QPushButton {
                    background-color: rgba(255, 209, 102, 0.15);
                    color: rgba(255, 209, 102, 0.9);
                    border: 1px solid rgba(255, 209, 102, 0.3);
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 209, 102, 0.25);
                }
            """
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """

    # ==================== 公开方法 ====================

    def load_characters(self, characters: List[Dict]):
        """加载角色列表"""
        # 清空现有角色
        while self.characters_container.count():
            item = self.characters_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if characters:
            self.no_char_label = None
            for char_data in characters:
                item = DraggableCharacterItem(char_data)
                self.characters_container.addWidget(item)
        else:
            self.no_char_label = QLabel("暂无角色")
            self.no_char_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.no_char_label.setStyleSheet("color: rgba(255, 255, 255, 0.2); font-size: 10px; padding: 10px;")
            self.characters_container.addWidget(self.no_char_label)

    def load_props(self, props: List[Dict]):
        """加载道具列表"""
        while self.props_container.count():
            item = self.props_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if props:
            self.no_prop_label = None
            for prop_data in props:
                item = DraggablePropItem(prop_data)
                self.props_container.addWidget(item)
        else:
            self.no_prop_label = QLabel("暂无道具")
            self.no_prop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.no_prop_label.setStyleSheet("color: rgba(255, 255, 255, 0.2); font-size: 10px; padding: 10px;")
            self.props_container.addWidget(self.no_prop_label)

    def add_character(self, char_data: dict):
        """添加单个角色"""
        if self.no_char_label:
            self.no_char_label.deleteLater()
            self.no_char_label = None

        item = DraggableCharacterItem(char_data)
        self.characters_container.addWidget(item)

    def add_prop(self, prop_data: dict):
        """添加单个道具"""
        if self.no_prop_label:
            self.no_prop_label.deleteLater()
            self.no_prop_label = None

        item = DraggablePropItem(prop_data)
        self.props_container.addWidget(item)

    # ==================== 对话框 ====================

    def _show_character_picker(self):
        """显示资产选择对话框（从 Asset 表查询角色类型资产）"""
        try:
            from database.session import session_scope
            from database.models.asset import Asset

            dialog = QDialog(self)
            dialog.setWindowTitle("选择角色")
            dialog.setFixedSize(350, 400)
            dialog.setStyleSheet("""
                QDialog { background-color: rgb(30, 30, 30); }
                QLabel { color: white; }
            """)

            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(10)

            search = QLineEdit()
            search.setPlaceholderText("搜索角色...")
            search.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    padding: 6px 10px;
                    color: white;
                    font-size: 11px;
                }
            """)
            layout.addWidget(search)

            list_widget = QListWidget()
            list_widget.setStyleSheet("""
                QListWidget {
                    background-color: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    color: white;
                }
                QListWidget::item { padding: 8px; }
                QListWidget::item:selected { background-color: rgba(0, 122, 204, 0.3); }
            """)

            with session_scope() as session:
                assets = session.query(Asset).filter(
                    Asset.asset_type == 'character',
                    Asset.is_active == True
                ).order_by(Asset.name).all()

                for asset in assets:
                    asset_dict = asset.to_dict()
                    display = f"{asset.name}  (角色)"
                    item = QListWidgetItem(display)
                    item.setData(Qt.ItemDataRole.UserRole, asset_dict)
                    list_widget.addItem(item)

            def filter_list(text):
                text = text.lower()
                for i in range(list_widget.count()):
                    item = list_widget.item(i)
                    item.setHidden(text not in item.text().lower())

            search.textChanged.connect(filter_list)
            layout.addWidget(list_widget)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 4px;
                    padding: 6px 16px;
                    color: white;
                }
            """)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected = list_widget.currentItem()
                if selected:
                    char_data = selected.data(Qt.ItemDataRole.UserRole)
                    self.add_character(char_data)

        except Exception as e:
            print(f"打开角色选择器失败: {e}")

    def _show_add_prop_dialog(self):
        """显示添加道具对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加道具")
        dialog.setFixedSize(300, 200)
        dialog.setStyleSheet("""
            QDialog { background-color: rgb(30, 30, 30); }
            QLabel { color: white; }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        name_label = QLabel("道具名称")
        name_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        layout.addWidget(name_label)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("输入道具名称...")
        name_edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px 10px;
                color: white;
                font-size: 11px;
            }
        """)
        layout.addWidget(name_edit)

        desc_label = QLabel("描述（可选）")
        desc_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 11px;")
        layout.addWidget(desc_label)

        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("简短描述...")
        desc_edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px 10px;
                color: white;
                font-size: 11px;
            }
        """)
        layout.addWidget(desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 6px 16px;
                color: white;
            }
        """)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            if name:
                prop_data = {
                    'name': name,
                    'description': desc_edit.text().strip(),
                    'prop_type': 'object',
                }
                self.add_prop(prop_data)
