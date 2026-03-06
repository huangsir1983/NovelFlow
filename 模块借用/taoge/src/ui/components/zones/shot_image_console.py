"""
涛割 - 图片控制台面板（重构版）
ShotImageConsole: viewport 子控件，底部滑入/滑出的图片生成参数面板。

布局:
┌────────────────────────────────────────────────────────────────┐
│ [16:9] [1张] [1K] [Fast]  │  ┌──────────────────────┐ │ [4张│横│竖] [无风格] │
│   ↑可展开               │  │ 提示词输入区           │ │      ↑可展开        │
│                          │  │                        │ │                     │
│                          │  │ 字数     [分镜] [生成]  │ │                     │
└────────────────────────────────────────────────────────────────┘
"""

from typing import Optional, Set, List, Dict
import os

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QSizePolicy, QGraphicsDropShadowEffect,
    QGridLayout, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPointF, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QFont, QColor, QPixmap, QTextImageFormat

from ui import theme


# ============================================================
#  PopupSelector — 向上展开的选项弹窗
# ============================================================

class PopupSelector(QFrame):
    """
    从按钮上方弹出的选项面板。
    支持单选和双列布局。
    """

    item_selected = pyqtSignal(str, str)  # (key, display_text)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._items: List[dict] = []
        self._buttons: List[QPushButton] = []
        self._columns = 2
        self._key = ""

    def setup(self, key: str, items: List[dict], columns: int = 2):
        """
        items: [{'value': '16:9', 'label': '16:9', 'subtitle': ''}, ...]
        """
        self._key = key
        self._items = items
        self._columns = columns

        # 清除旧布局
        old = self.layout()
        if old:
            while old.count():
                w = old.takeAt(0).widget()
                if w:
                    w.deleteLater()
            QWidget().setLayout(old)

        self._buttons.clear()

        from PyQt6.QtWidgets import QGridLayout
        grid = QGridLayout(self)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(4)

        for i, item in enumerate(items):
            btn = QPushButton()
            btn.setFixedHeight(36 if not item.get('subtitle') else 44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Microsoft YaHei", 10))

            # 如果有副标题
            if item.get('subtitle'):
                btn.setText(f"{item['label']}\n{item['subtitle']}")
                btn.setFont(QFont("Microsoft YaHei", 9))
            else:
                btn.setText(item['label'])

            val = item['value']
            btn.clicked.connect(lambda checked, v=val, l=item['label']: self._on_item_clicked(v, l))

            row = i // columns
            col = i % columns
            grid.addWidget(btn, row, col)
            self._buttons.append(btn)

        self._apply_theme()

    def _on_item_clicked(self, value: str, label: str):
        self.item_selected.emit(value, label)
        self.hide()

    def show_above(self, anchor: QWidget):
        """在 anchor 按钮上方弹出"""
        self.adjustSize()
        # 计算位置：anchor 左上方
        global_pos = anchor.mapToGlobal(anchor.rect().topLeft())
        popup_h = self.sizeHint().height()
        popup_w = max(self.sizeHint().width(), anchor.width())
        self.setFixedWidth(popup_w)
        x = global_pos.x()
        y = global_pos.y() - popup_h - 4
        self.move(x, y)
        self.show()

    def _apply_theme(self):
        dark = theme.is_dark()
        bg = "rgba(36, 36, 40, 250)" if dark else "rgba(255, 255, 255, 250)"
        border = "rgba(255, 255, 255, 12)" if dark else "rgba(0, 0, 0, 8)"
        btn_bg = "rgba(48, 48, 52, 255)" if dark else "rgba(245, 245, 249, 255)"
        btn_hover = "rgba(60, 60, 66, 255)" if dark else "rgba(230, 230, 236, 255)"
        text_color = "rgba(255, 255, 255, 220)" if dark else "rgba(0, 0, 0, 200)"
        sub_color = "rgba(255, 255, 255, 100)" if dark else "rgba(0, 0, 0, 100)"

        self.setStyleSheet(f"""
            PopupSelector {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QPushButton {{
                background: {btn_bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {text_color};
                padding: 4px 12px;
                text-align: center;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
        """)


# ============================================================
#  ToolbarButton — 底部工具栏按钮
# ============================================================

class ToolbarButton(QPushButton):
    """底部工具栏按钮，显示当前值，点击向上展开选择器"""

    def __init__(self, initial_text: str = "", parent=None):
        super().__init__(initial_text, parent)
        self.setFont(QFont("Microsoft YaHei", 10))
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# ============================================================
#  AssetMentionPopup — 输入 @ 后弹出的资产选择器
#  左列: 角色(N) / 场景(N) / 道具(N) 三个类别按钮
#  右列: hover 类别后展开该类别下的资产卡片列表
# ============================================================

class AssetMentionPopup(QFrame):
    """
    从提示词框上方弹出的 @ 资产选择面板。
    左侧三个类别条目，hover 后右侧展开该类别资产列表。
    选中后发射 asset_selected 信号。
    """

    asset_selected = pyqtSignal(dict)  # {'name','type','image_path'}

    CATEGORY_WIDTH = 120
    ASSET_ITEM_SIZE = 56
    MAX_VISIBLE_ITEMS = 6

    _TYPE_LABELS = {
        'character': '角色',
        'scene_bg': '场景',
        'prop': '道具',
    }
    _TYPE_ORDER = ['character', 'scene_bg', 'prop']

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._all_assets: Dict[str, List[dict]] = {}  # type -> list of asset dicts
        self._category_btns: List[QPushButton] = []
        self._asset_widgets: List[QWidget] = []  # 右侧的资产项
        self._current_category: Optional[str] = None

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        main_h = QHBoxLayout(self)
        main_h.setContentsMargins(6, 6, 6, 6)
        main_h.setSpacing(0)

        # 左列: 类别列表
        self._cat_frame = QFrame()
        self._cat_frame.setFixedWidth(self.CATEGORY_WIDTH)
        cat_layout = QVBoxLayout(self._cat_frame)
        cat_layout.setContentsMargins(0, 0, 0, 0)
        cat_layout.setSpacing(2)
        # 按钮在 set_assets 中动态创建
        cat_layout.addStretch()
        main_h.addWidget(self._cat_frame)

        # 右列: 资产列表（初始隐藏，hover 类别后展开）
        self._asset_scroll = QScrollArea()
        self._asset_scroll.setWidgetResizable(True)
        self._asset_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._asset_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._asset_scroll.setFixedWidth(200)
        self._asset_scroll.setVisible(False)
        self._asset_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._asset_frame = QFrame()
        self._asset_layout = QVBoxLayout(self._asset_frame)
        self._asset_layout.setContentsMargins(6, 0, 0, 0)
        self._asset_layout.setSpacing(4)

        self._asset_scroll.setWidget(self._asset_frame)
        main_h.addWidget(self._asset_scroll)

    def set_assets(self, assets_by_type: Dict[str, List[dict]]):
        """
        设置可选资产。
        assets_by_type: {'character': [{name, image_path, ...}], 'scene_bg': [...], 'prop': [...]}
        """
        self._all_assets = assets_by_type

        # 清旧类别按钮
        cat_layout = self._cat_frame.layout()
        for btn in self._category_btns:
            btn.deleteLater()
        self._category_btns.clear()

        # 移除旧 stretch
        while cat_layout.count():
            cat_layout.takeAt(0)

        for t in self._TYPE_ORDER:
            items = assets_by_type.get(t, [])
            label_text = f"{self._TYPE_LABELS.get(t, t)}({len(items)})"
            btn = QPushButton(label_text)
            btn.setFont(QFont("Microsoft YaHei", 10))
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty('asset_type', t)
            btn.installEventFilter(self)
            btn.clicked.connect(lambda checked, at=t: self._expand_category(at))
            cat_layout.addWidget(btn)
            self._category_btns.append(btn)
        cat_layout.addStretch()

        self._apply_theme()
        self.adjustSize()

    def eventFilter(self, obj, event):
        """hover 类别按钮时展开对应资产"""
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Enter and isinstance(obj, QPushButton):
            t = obj.property('asset_type')
            if t:
                self._expand_category(t)
        return super().eventFilter(obj, event)

    def _expand_category(self, asset_type: str):
        if self._current_category == asset_type:
            return
        self._current_category = asset_type

        # 清旧资产项
        for w in self._asset_widgets:
            w.deleteLater()
        self._asset_widgets.clear()
        # 移除旧 stretch 和返回按钮
        while self._asset_layout.count():
            item = self._asset_layout.takeAt(0)
            w = item.widget()
            if w and w not in self._asset_widgets:
                w.deleteLater()

        items = self._all_assets.get(asset_type, [])
        if not items:
            self._asset_scroll.setVisible(False)
            self._resize_popup()
            return

        # 返回按钮
        back_btn = QPushButton("← 返回")
        back_btn.setFont(QFont("Microsoft YaHei", 9))
        back_btn.setFixedHeight(28)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self._collapse_asset_list)
        self._asset_layout.addWidget(back_btn)

        for asset in items:
            row = self._make_asset_row(asset)
            self._asset_layout.addWidget(row)
            self._asset_widgets.append(row)
        self._asset_layout.addStretch()

        self._asset_scroll.setVisible(True)
        # 高亮当前类别按钮
        for btn in self._category_btns:
            btn.setProperty('active', btn.property('asset_type') == asset_type)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._resize_popup()

    def _collapse_asset_list(self):
        """收起右侧资产列表，回到类别选择"""
        self._current_category = None
        self._asset_scroll.setVisible(False)
        for btn in self._category_btns:
            btn.setProperty('active', False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._resize_popup()

    def _make_asset_row(self, asset: dict) -> QWidget:
        """单个资产条目：缩略图 + 名称"""
        row = QWidget()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        h_layout = QHBoxLayout(row)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(8)

        # 缩略图
        thumb = QLabel()
        thumb.setFixedSize(40, 40)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            "border: 1px solid rgba(255,255,255,12); border-radius: 6px; "
            "background: rgba(255,255,255,5);"
        )
        img_path = asset.get('main_reference_image', '') or asset.get('image_path', '')
        if img_path and os.path.isfile(img_path):
            pm = QPixmap(img_path).scaled(
                40, 40,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            if pm.width() > 40 or pm.height() > 40:
                cx = (pm.width() - 40) // 2
                cy = (pm.height() - 40) // 2
                pm = pm.copy(cx, cy, 40, 40)
            thumb.setPixmap(pm)
        else:
            thumb.setText(asset.get('name', '?')[:2])
            thumb.setFont(QFont("Microsoft YaHei", 9))
        h_layout.addWidget(thumb)

        # 名称
        name_lbl = QLabel(asset.get('name', ''))
        name_lbl.setFont(QFont("Microsoft YaHei", 10))
        h_layout.addWidget(name_lbl, stretch=1)

        # 点击整行 → 选中
        row.mousePressEvent = lambda e, a=asset: self._on_asset_clicked(a)
        return row

    def _on_asset_clicked(self, asset: dict):
        self.asset_selected.emit(asset)
        self.hide()

    def _resize_popup(self):
        """调整弹窗尺寸"""
        self.adjustSize()
        # 重新定位（保持左下角锚定）
        if hasattr(self, '_anchor_global_bottom_left'):
            x, y = self._anchor_global_bottom_left
            self.move(x, y - self.sizeHint().height())

    def show_above_widget(self, anchor: QWidget):
        """在 anchor（提示词框）上方弹出"""
        self.setMaximumHeight(350)
        self._current_category = None
        self._asset_scroll.setVisible(False)
        self.adjustSize()
        global_pos = anchor.mapToGlobal(anchor.rect().topLeft())
        popup_h = self.sizeHint().height()
        x = global_pos.x()
        y = global_pos.y() - popup_h - 4
        self._anchor_global_bottom_left = (x, global_pos.y() - 4)
        self.move(x, y)
        self.show()

    def _apply_theme(self):
        dark = theme.is_dark()
        bg = "rgba(32, 32, 36, 252)" if dark else "rgba(255, 255, 255, 252)"
        border = "rgba(255, 255, 255, 10)" if dark else "rgba(0, 0, 0, 8)"
        btn_bg = "rgba(44, 44, 48, 255)" if dark else "rgba(242, 242, 246, 255)"
        btn_hover = "rgba(58, 58, 64, 255)" if dark else "rgba(228, 228, 234, 255)"
        btn_active = "rgba(70, 70, 80, 255)" if dark else "rgba(215, 215, 225, 255)"
        text_c = "rgba(255, 255, 255, 210)" if dark else "rgba(0, 0, 0, 200)"
        row_hover = "rgba(255, 255, 255, 8)" if dark else "rgba(0, 0, 0, 4)"

        self.setStyleSheet(f"""
            AssetMentionPopup {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QPushButton {{
                background: {btn_bg};
                border: 1px solid {border};
                border-radius: 6px;
                color: {text_c};
                padding: 4px 10px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
            QPushButton[active="true"] {{
                background: {btn_active};
                border-left: 3px solid {theme.accent()};
            }}
            QLabel {{
                color: {text_c};
                background: transparent;
                border: none;
            }}
            QWidget {{
                background: transparent;
            }}
        """)


# ============================================================
#  ShotImageConsole — 图片控制台（重构版）
# ============================================================

class ShotImageConsole(QWidget):
    """
    底部滑入/滑出的图片生成参数面板。
    布局: 左侧4按钮 | 中间提示词大框 | 右侧三联框+风格
    """

    generate_image_requested = pyqtSignal(dict)   # 单图生成
    generate_board_requested = pyqtSignal(dict)    # 分镜组图生成

    SLIDE_DURATION = 200
    SLIDE_OFFSET = 220
    PANEL_HEIGHT = 210
    MAX_WIDTH = 1060
    MARGIN = 20

    # 比例映射: 横屏 ↔ 竖屏
    RATIO_PAIRS = {
        '16:9': '9:16', '9:16': '16:9',
        '4:3': '3:4', '3:4': '4:3',
        '21:9': '9:21', '9:21': '21:9',
        '2:1': '1:2', '1:2': '2:1',
        '1:1': '1:1',
    }
    LANDSCAPE_RATIOS = {'16:9', '4:3', '21:9', '2:1', '1:1'}
    PORTRAIT_RATIOS = {'9:16', '3:4', '9:21', '1:2'}

    # 模型映射
    MODEL_MAP = {
        'gemini-3-pro': 'gemini-3-pro-image-preview',
        'Fast': 'gemini-2.5-flash-image',
        'Pro': 'gemini-3-pro-image-preview',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_visible_state = False
        self._slide_anim: Optional[QPropertyAnimation] = None
        self._current_scene_index: Optional[int] = None

        # 当前选中值
        self._ratio = '16:9'
        self._count = '1张'
        self._resolution = '1K'
        self._model_key = 'gemini-3-pro'
        self._model_name = 'gemini-3-pro-image-preview'
        self._grid_count = '4张'
        self._orientation = 'landscape'
        self._style = '无风格'
        self._reference_image = ''
        self._reference_images: List[str] = []

        # @ 资产提及
        self._available_assets: Dict[str, List[dict]] = {}  # type -> [asset_dict]
        self._mentioned_assets: List[dict] = []  # 用户手动选中的资产
        self._current_assets: List[dict] = []    # 当前关联资产（自动加载 + 手动提及）
        self._asset_mention_popup: Optional[AssetMentionPopup] = None
        self._suppress_text_changed = False  # 防止插入 @ 文本时再次触发弹窗

        self.setFixedHeight(self.PANEL_HEIGHT)
        self.setVisible(False)

        self._init_ui()
        self._apply_theme()

        # 弹窗选择器（懒创建共用）
        self._popup: Optional[PopupSelector] = None

    @property
    def is_visible_state(self) -> bool:
        return self._is_visible_state

    def set_scene_index(self, scene_index: int):
        self._current_scene_index = scene_index

    def set_prompt(self, text: str):
        """设置提示词（从分镜卡带入）"""
        self._prompt_edit.setPlainText(text)

    def set_reference_image(self, path: str):
        """设置参考图片路径（用于图片编辑模式）"""
        self._reference_image = path or ''

    def set_reference_images(self, paths: List[str]):
        """设置多张参考图片路径（来自关联资产）"""
        self._reference_images = paths or []

    def set_available_assets(self, assets_by_type: Dict[str, List[dict]]):
        """
        设置可供 @ 提及的资产库数据。
        assets_by_type: {'character': [...], 'scene_bg': [...], 'prop': [...]}
        """
        self._available_assets = assets_by_type or {}

    def add_mentioned_asset(self, asset: dict):
        """
        用户通过 @ 弹窗手动选中一个资产：
        1. 在提示词光标位置插入内联缩略图 + @名称
        2. 将资产加入 _mentioned_assets
        3. 将资产参考图加入 _reference_images
        """
        name = asset.get('name', '')
        if not name:
            return

        # 避免重复
        existing_names = {a.get('name') for a in self._mentioned_assets}
        if name in existing_names:
            return

        self._mentioned_assets.append(asset)

        # 在提示词光标处插入内联缩略图 + @名称
        cursor = self._prompt_edit.textCursor()
        # 删除触发弹窗的 @ 字符（光标前一个字符）
        pos = cursor.position()
        if pos > 0:
            cursor.setPosition(pos - 1)
            cursor.setPosition(pos, cursor.MoveMode.KeepAnchor)
            if cursor.selectedText() == '@':
                cursor.removeSelectedText()

        self._suppress_text_changed = True
        img_path = asset.get('main_reference_image', '') or asset.get('image_path', '')
        self._insert_inline_thumbnail(cursor, name, img_path)
        self._suppress_text_changed = False

        # 参考图加入列表
        if img_path and img_path not in self._reference_images:
            self._reference_images.append(img_path)

    def _insert_inline_thumbnail(self, cursor, name: str, image_path: str):
        """在 cursor 位置插入内联缩略图 + @名称。
        图片上方留 5px 间距（通过将缩略图绘制到稍高的透明画布底部实现）。
        """
        THUMB_SIZE = 40
        TOP_MARGIN = 5
        resource_url = f"asset://{name}"
        doc = self._prompt_edit.document()

        if image_path and os.path.isfile(image_path):
            pm = QPixmap(image_path).scaled(
                THUMB_SIZE, THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            if pm.width() > THUMB_SIZE or pm.height() > THUMB_SIZE:
                cx = (pm.width() - THUMB_SIZE) // 2
                cy = (pm.height() - THUMB_SIZE) // 2
                pm = pm.copy(cx, cy, THUMB_SIZE, THUMB_SIZE)

            # 将缩略图画到带上边距的透明画布底部
            from PyQt6.QtGui import QPainter
            total_h = THUMB_SIZE + TOP_MARGIN
            canvas = QPixmap(THUMB_SIZE, total_h)
            canvas.fill(QColor(0, 0, 0, 0))
            painter = QPainter(canvas)
            painter.drawPixmap(0, TOP_MARGIN, pm)
            painter.end()

            doc.addResource(
                doc.ResourceType.ImageResource.value,
                QUrl(resource_url),
                canvas.toImage())
            img_fmt = QTextImageFormat()
            img_fmt.setName(resource_url)
            img_fmt.setWidth(THUMB_SIZE)
            img_fmt.setHeight(total_h)
            cursor.insertImage(img_fmt)

        cursor.insertText(f"@{name} ")

    def set_prompt_with_assets(self, base_prompt: str, assets: List[dict]):
        """
        设置提示词并在末尾插入关联资产的内联缩略图。
        assets: [{'name': '...', 'image_path': '...'}, ...]
        """
        # 记录当前关联资产（供 _build_params 导出）
        self._current_assets = list(assets) if assets else []

        self._suppress_text_changed = True
        self._prompt_edit.clear()
        cursor = self._prompt_edit.textCursor()
        cursor.insertText(base_prompt)

        if assets:
            cursor.insertText("\n参考资产：")
            for a in assets:
                name = a.get('name', '')
                img_path = a.get('image_path', '')
                self._insert_inline_thumbnail(cursor, name, img_path)

        self._suppress_text_changed = False
        self._update_char_count()

    # ==================== UI 初始化 ====================

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 0, 12, 8)
        main_layout.setSpacing(10)

        # ── 左侧: 4 个工具栏按钮（底部对齐）──
        left_layout = QVBoxLayout()
        left_layout.setSpacing(0)
        left_layout.addStretch()

        left_btns = QHBoxLayout()
        left_btns.setSpacing(4)

        self._ratio_btn = ToolbarButton(self._ratio)
        self._ratio_btn.setFixedWidth(60)
        self._ratio_btn.clicked.connect(self._show_ratio_popup)
        left_btns.addWidget(self._ratio_btn)

        self._count_btn = ToolbarButton(self._count)
        self._count_btn.setFixedWidth(50)
        self._count_btn.clicked.connect(self._show_count_popup)
        left_btns.addWidget(self._count_btn)

        self._resolution_btn = ToolbarButton(self._resolution)
        self._resolution_btn.setFixedWidth(40)
        self._resolution_btn.clicked.connect(self._show_resolution_popup)
        left_btns.addWidget(self._resolution_btn)

        self._model_btn = ToolbarButton(self._model_key)
        self._model_btn.setFixedWidth(52)
        self._model_btn.clicked.connect(self._show_model_popup)
        left_btns.addWidget(self._model_btn)

        left_layout.addLayout(left_btns)
        main_layout.addLayout(left_layout)

        # ── 中间: 提示词大框（底部对齐）──
        center_layout = QVBoxLayout()
        center_layout.setSpacing(0)
        center_layout.setContentsMargins(0, 8, 0, 0)

        # 提示词容器框
        self._prompt_frame = QFrame()
        prompt_inner = QVBoxLayout(self._prompt_frame)
        prompt_inner.setContentsMargins(10, 8, 10, 6)
        prompt_inner.setSpacing(4)

        # 提示词输入
        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlaceholderText("描述画面...输入@选择资产，/快捷操作")
        self._prompt_edit.setFont(QFont("Microsoft YaHei", 10))
        self._prompt_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._prompt_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._prompt_edit.textChanged.connect(self._update_char_count)
        prompt_inner.addWidget(self._prompt_edit, stretch=1)

        # 底部行: 字数 + 按钮
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self._char_count_label = QLabel("0字")
        self._char_count_label.setFont(QFont("Microsoft YaHei", 8))
        bottom_row.addWidget(self._char_count_label)

        bottom_row.addStretch()

        self._storyboard_btn = QPushButton("分镜")
        self._storyboard_btn.setFont(QFont("Microsoft YaHei", 9))
        self._storyboard_btn.setFixedSize(60, 28)
        self._storyboard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._storyboard_btn.clicked.connect(self._on_storyboard_clicked)
        bottom_row.addWidget(self._storyboard_btn)

        self._generate_btn = QPushButton("生成")
        self._generate_btn.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self._generate_btn.setFixedSize(60, 28)
        self._generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generate_btn.clicked.connect(self._on_generate_clicked)
        bottom_row.addWidget(self._generate_btn)

        prompt_inner.addLayout(bottom_row)
        center_layout.addWidget(self._prompt_frame)
        main_layout.addLayout(center_layout, stretch=1)

        # ── 右侧: 三联框 + 风格按钮（底部对齐）──
        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.addStretch()

        right_btns = QHBoxLayout()
        right_btns.setSpacing(0)

        # 三联框容器
        self._trio_frame = QFrame()
        trio_layout = QHBoxLayout(self._trio_frame)
        trio_layout.setContentsMargins(0, 0, 0, 0)
        trio_layout.setSpacing(0)

        self._grid_btn = QPushButton(self._grid_count)
        self._grid_btn.setFont(QFont("Microsoft YaHei", 9))
        self._grid_btn.setFixedSize(44, 36)
        self._grid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._grid_btn.clicked.connect(self._show_grid_popup)
        trio_layout.addWidget(self._grid_btn)

        self._landscape_btn = QPushButton("横")
        self._landscape_btn.setFont(QFont("Microsoft YaHei", 9))
        self._landscape_btn.setFixedSize(36, 36)
        self._landscape_btn.setCheckable(True)
        self._landscape_btn.setChecked(True)
        self._landscape_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._landscape_btn.clicked.connect(lambda: self._set_orientation('landscape'))
        trio_layout.addWidget(self._landscape_btn)

        self._portrait_btn = QPushButton("竖")
        self._portrait_btn.setFont(QFont("Microsoft YaHei", 9))
        self._portrait_btn.setFixedSize(36, 36)
        self._portrait_btn.setCheckable(True)
        self._portrait_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._portrait_btn.clicked.connect(lambda: self._set_orientation('portrait'))
        trio_layout.addWidget(self._portrait_btn)

        right_btns.addWidget(self._trio_frame)
        right_btns.addSpacing(6)

        self._style_btn = ToolbarButton(self._style)
        self._style_btn.setFixedWidth(72)
        self._style_btn.clicked.connect(self._show_style_popup)
        right_btns.addWidget(self._style_btn)

        right_layout.addLayout(right_btns)
        main_layout.addLayout(right_layout)

    # ==================== 弹窗展开 ====================

    def _ensure_popup(self) -> PopupSelector:
        if not self._popup:
            self._popup = PopupSelector()
            self._popup.item_selected.connect(self._on_popup_selected)
        return self._popup

    def _show_ratio_popup(self):
        popup = self._ensure_popup()
        popup.setup('ratio', [
            {'value': '1:1', 'label': '1:1'},
            {'value': '16:9', 'label': '16:9'},
            {'value': '9:16', 'label': '9:16'},
            {'value': '4:3', 'label': '4:3'},
            {'value': '3:4', 'label': '3:4'},
            {'value': '21:9', 'label': '21:9'},
            {'value': '2:1', 'label': '2:1'},
            {'value': '1:2', 'label': '1:2'},
        ], columns=2)
        popup.show_above(self._ratio_btn)

    def _show_count_popup(self):
        popup = self._ensure_popup()
        popup.setup('count', [
            {'value': '1张', 'label': '1张'},
            {'value': '2张', 'label': '2张'},
            {'value': '4张', 'label': '4张'},
        ], columns=3)
        popup.show_above(self._count_btn)

    def _show_resolution_popup(self):
        popup = self._ensure_popup()
        popup.setup('resolution', [
            {'value': '1K', 'label': '1K'},
            {'value': '2K', 'label': '2K'},
            {'value': '4K', 'label': '4K'},
        ], columns=3)
        popup.show_above(self._resolution_btn)

    def _show_model_popup(self):
        popup = self._ensure_popup()
        popup.setup('model', [
            {'value': 'gemini-3-pro', 'label': 'Gemini 3 Pro', 'subtitle': '云雾图片'},
            {'value': 'Fast', 'label': 'Fast', 'subtitle': '快速'},
            {'value': 'Pro', 'label': 'Pro', 'subtitle': '高质量'},
        ], columns=1)
        popup.show_above(self._model_btn)

    def _show_grid_popup(self):
        popup = self._ensure_popup()
        popup.setup('grid', [
            {'value': '4张', 'label': '4张'},
            {'value': '9张', 'label': '9张'},
            {'value': '16张', 'label': '16张'},
        ], columns=3)
        popup.show_above(self._grid_btn)

    def _show_style_popup(self):
        popup = self._ensure_popup()
        popup.setup('style', [
            {'value': '无风格', 'label': '无风格'},
            {'value': '真人电影', 'label': '真人电影'},
            {'value': '3D国漫', 'label': '3D国漫'},
            {'value': '2D国漫', 'label': '2D国漫'},
            {'value': '现代3D国风', 'label': '现代3D国风'},
            {'value': '赛博朋克', 'label': '赛博朋克'},
        ], columns=2)
        popup.show_above(self._style_btn)

    def _on_popup_selected(self, value: str, label: str):
        """弹窗选中回调"""
        key = self._popup._key if self._popup else ''

        if key == 'ratio':
            self._ratio = value
            self._ratio_btn.setText(value)
            # 同步横竖屏按钮
            if value in self.LANDSCAPE_RATIOS:
                self._orientation = 'landscape'
                self._landscape_btn.setChecked(True)
                self._portrait_btn.setChecked(False)
            elif value in self.PORTRAIT_RATIOS:
                self._orientation = 'portrait'
                self._landscape_btn.setChecked(False)
                self._portrait_btn.setChecked(True)

        elif key == 'count':
            self._count = value
            self._count_btn.setText(value)

        elif key == 'resolution':
            self._resolution = value
            self._resolution_btn.setText(value)

        elif key == 'model':
            self._model_key = value
            self._model_name = self.MODEL_MAP.get(value, value)
            self._model_btn.setText(value)

        elif key == 'grid':
            self._grid_count = value
            self._grid_btn.setText(value)

        elif key == 'style':
            self._style = value
            self._style_btn.setText(value)

    # ==================== 横竖屏联动 ====================

    def _set_orientation(self, orient: str):
        self._orientation = orient
        if orient == 'landscape':
            self._landscape_btn.setChecked(True)
            self._portrait_btn.setChecked(False)
            # 转换当前比例为横屏
            if self._ratio in self.PORTRAIT_RATIOS:
                new_ratio = self.RATIO_PAIRS.get(self._ratio, '16:9')
                self._ratio = new_ratio
                self._ratio_btn.setText(new_ratio)
        else:
            self._landscape_btn.setChecked(False)
            self._portrait_btn.setChecked(True)
            # 转换当前比例为竖屏
            if self._ratio in self.LANDSCAPE_RATIOS and self._ratio != '1:1':
                new_ratio = self.RATIO_PAIRS.get(self._ratio, '9:16')
                self._ratio = new_ratio
                self._ratio_btn.setText(new_ratio)

    # ==================== 公开 API ====================

    @property
    def orientation(self) -> str:
        """当前横竖屏状态（'landscape' 或 'portrait'）"""
        return self._orientation

    def set_orientation(self, orient: str):
        """外部设置横竖屏"""
        self._set_orientation(orient)

    # ==================== 交互逻辑 ====================

    def _update_char_count(self):
        if not hasattr(self, '_char_count_label'):
            return
        text = self._prompt_edit.toPlainText()
        clean_text = text.replace('\uFFFC', '')
        self._char_count_label.setText(f"{len(clean_text)}字")

        # 检测 @ 触发资产选择弹窗
        if self._suppress_text_changed:
            return
        cursor = self._prompt_edit.textCursor()
        pos = cursor.position()
        if pos > 0 and text[pos - 1] == '@':
            # 前一个字符不是字母/数字（排除 email 等误触发）
            if pos == 1 or not text[pos - 2].isalnum():
                self._show_asset_mention_popup()

    def _show_asset_mention_popup(self):
        """显示 @ 资产选择弹窗"""
        if not self._available_assets:
            return
        if not self._asset_mention_popup:
            self._asset_mention_popup = AssetMentionPopup()
            self._asset_mention_popup.asset_selected.connect(
                self._on_mention_asset_selected)
        self._asset_mention_popup.set_assets(self._available_assets)
        self._asset_mention_popup.show_above_widget(self._prompt_frame)

    def _on_mention_asset_selected(self, asset: dict):
        """@ 弹窗选中资产回调"""
        self.add_mentioned_asset(asset)

    def _on_generate_clicked(self):
        """生成（单图）"""
        params = self._build_params()
        params['mode'] = 'single'
        self.generate_image_requested.emit(params)

    def _on_storyboard_clicked(self):
        """分镜（组图）"""
        params = self._build_params()
        params['mode'] = 'storyboard'
        params['grid_count'] = self._grid_count
        self.generate_board_requested.emit(params)

    def _build_params(self) -> dict:
        raw_text = self._prompt_edit.toPlainText()
        clean_text = raw_text.replace('\uFFFC', '')  # 剥离内联图片占位符

        # 提取纯净 base_prompt（去掉 "\n参考资产：..." 后缀）
        base_prompt = clean_text
        asset_sep = '\n参考资产：'
        sep_idx = clean_text.find(asset_sep)
        if sep_idx >= 0:
            base_prompt = clean_text[:sep_idx]

        # 收集所有关联资产：自动加载 + 手动 @ 提及
        all_assets: List[dict] = list(getattr(self, '_current_assets', []))
        existing_names = {a.get('name') for a in all_assets}
        for a in self._mentioned_assets:
            if a.get('name') not in existing_names:
                all_assets.append(a)
                existing_names.add(a.get('name'))

        params = {
            'scene_index': self._current_scene_index,
            'ratio': self._ratio,
            'count': self._count,
            'resolution': self._resolution,
            'model_key': self._model_key,
            'model_name': self._model_name,
            'prompt': clean_text,
            'base_prompt': base_prompt,
            'style': self._style,
            'orientation': self._orientation,
        }
        if all_assets:
            params['assets'] = all_assets
        if self._reference_image:
            params['reference_image'] = self._reference_image
        if self._reference_images:
            params['reference_images'] = list(self._reference_images)
        return params

    def set_params_from_dict(self, params: dict, skip_prompt: bool = False):
        """从参数字典恢复控制台状态（用于"填入控制台"功能）
        skip_prompt=True 时跳过提示词和资产恢复（已由外部 set_prompt_with_assets 处理）
        """
        if not skip_prompt:
            # 恢复提示词 + 资产内联缩略图
            assets = params.get('assets', [])
            base_prompt = params.get('base_prompt', '')
            prompt = params.get('prompt', '')

            if assets:
                # 有资产数据 → 用 set_prompt_with_assets 恢复内联缩略图
                text = base_prompt if base_prompt else prompt
                # 如果没有 base_prompt，尝试从 prompt 中剥离 "参考资产：..." 后缀
                if not base_prompt and '\n参考资产：' in text:
                    text = text[:text.find('\n参考资产：')]
                self.set_prompt_with_assets(text, assets)
                # 恢复参考图（从资产数据重建）
                self._reference_images = []
                for a in assets:
                    img = a.get('image_path', '')
                    if img and img not in self._reference_images:
                        self._reference_images.append(img)
            elif prompt:
                self._prompt_edit.setPlainText(prompt)

        # 恢复比例
        ratio = params.get('ratio', '')
        if ratio:
            self._ratio = ratio
            self._ratio_btn.setText(ratio)
            if ratio in self.LANDSCAPE_RATIOS:
                self._orientation = 'landscape'
                self._landscape_btn.setChecked(True)
                self._portrait_btn.setChecked(False)
            elif ratio in self.PORTRAIT_RATIOS:
                self._orientation = 'portrait'
                self._landscape_btn.setChecked(False)
                self._portrait_btn.setChecked(True)

        # 恢复模型
        model_key = params.get('model_key', '')
        if model_key:
            self._model_key = model_key
            self._model_name = self.MODEL_MAP.get(model_key, model_key)
            self._model_btn.setText(model_key)

        # 恢复风格
        style = params.get('style', '')
        if style:
            self._style = style
            self._style_btn.setText(style)

        # 恢复分辨率
        resolution = params.get('resolution', '')
        if resolution:
            self._resolution = resolution
            self._resolution_btn.setText(resolution)

        # 恢复参考图（仅当未跳过提示词时，避免覆盖外部已设置的数据）
        if not skip_prompt:
            ref_img = params.get('reference_image', '')
            if ref_img:
                self._reference_image = ref_img
            ref_imgs = params.get('reference_images', [])
            if ref_imgs:
                self._reference_images = list(ref_imgs)

    # ==================== 滑入/滑出动画 ====================

    def slide_up(self):
        self._stop_anim()
        self._is_visible_state = True
        self.setVisible(True)
        self.raise_()

        geo = self.geometry()
        start_geo = QRect(geo.x(), geo.y() + self.SLIDE_OFFSET,
                          geo.width(), geo.height())
        end_geo = geo

        self._slide_anim = QPropertyAnimation(self, b"geometry")
        self._slide_anim.setDuration(self.SLIDE_DURATION)
        self._slide_anim.setStartValue(start_geo)
        self._slide_anim.setEndValue(end_geo)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide_anim.start()

    def slide_down(self):
        self._stop_anim()
        self._is_visible_state = False
        self._mentioned_assets.clear()
        self._auto_asset_thumbnails = []

        geo = self.geometry()
        start_geo = geo
        end_geo = QRect(geo.x(), geo.y() + self.SLIDE_OFFSET,
                        geo.width(), geo.height())

        self._slide_anim = QPropertyAnimation(self, b"geometry")
        self._slide_anim.setDuration(self.SLIDE_DURATION)
        self._slide_anim.setStartValue(start_geo)
        self._slide_anim.setEndValue(end_geo)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._slide_anim.finished.connect(self._on_slide_down_finished)
        self._slide_anim.start()

    def _stop_anim(self):
        if self._slide_anim and self._slide_anim.state() == QPropertyAnimation.State.Running:
            self._slide_anim.stop()
            self._slide_anim = None

    def _on_slide_down_finished(self):
        self.setVisible(False)

    # ==================== 主题 ====================

    def _apply_theme(self):
        dark = theme.is_dark()
        accent_c = theme.accent()

        if dark:
            panel_bg = "rgba(26, 26, 30, 245)"
            panel_border = "rgba(255, 255, 255, 8)"
            frame_bg = "rgba(38, 38, 42, 255)"
            frame_border = "rgba(255, 255, 255, 10)"
            input_bg = "transparent"
            text_c = "rgba(255, 255, 255, 220)"
            sub_c = "rgba(255, 255, 255, 80)"
            btn_bg = "rgba(48, 48, 52, 255)"
            btn_hover = "rgba(60, 60, 66, 255)"
            btn_border = "rgba(255, 255, 255, 10)"
            trio_bg = "rgba(38, 38, 42, 255)"
            trio_border = "rgba(255, 255, 255, 10)"
        else:
            panel_bg = "rgba(248, 248, 252, 248)"
            panel_border = "rgba(0, 0, 0, 6)"
            frame_bg = "rgba(255, 255, 255, 255)"
            frame_border = "rgba(0, 0, 0, 8)"
            input_bg = "transparent"
            text_c = "rgba(0, 0, 0, 200)"
            sub_c = "rgba(0, 0, 0, 100)"
            btn_bg = "rgba(245, 245, 249, 255)"
            btn_hover = "rgba(230, 230, 236, 255)"
            btn_border = "rgba(0, 0, 0, 6)"
            trio_bg = "rgba(245, 245, 249, 255)"
            trio_border = "rgba(0, 0, 0, 8)"

        # 主面板
        self.setStyleSheet(f"""
            ShotImageConsole {{
                background: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 14px;
            }}
        """)

        # 提示词框
        self._prompt_frame.setStyleSheet(f"""
            QFrame {{
                background: {frame_bg};
                border: 1px solid {frame_border};
                border-radius: 10px;
            }}
        """)

        # 提示词输入
        self._prompt_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {input_bg};
                border: none;
                color: {text_c};
            }}
        """)

        # 字数标签
        self._char_count_label.setStyleSheet(f"color: {sub_c}; background: transparent; border: none;")

        # 工具栏按钮样式
        toolbar_style = f"""
            QPushButton {{
                background: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 8px;
                color: {text_c};
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
        """
        self._ratio_btn.setStyleSheet(toolbar_style)
        self._count_btn.setStyleSheet(toolbar_style)
        self._resolution_btn.setStyleSheet(toolbar_style)
        self._model_btn.setStyleSheet(toolbar_style)
        self._style_btn.setStyleSheet(toolbar_style)

        # 分镜按钮
        self._storyboard_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_bg};
                border: 1px solid {btn_border};
                border-radius: 6px;
                color: {text_c};
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
        """)

        # 生成按钮 (accent)
        self._generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: {accent_c};
                border: none;
                border-radius: 6px;
                color: white;
            }}
            QPushButton:hover {{
                background: {theme.accent_hover()};
            }}
        """)

        # 三联框
        self._trio_frame.setStyleSheet(f"""
            QFrame {{
                background: {trio_bg};
                border: 1px solid {trio_border};
                border-radius: 8px;
            }}
        """)

        trio_inner_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 0;
                color: {text_c};
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
            QPushButton:checked {{
                background: {accent_c};
                color: white;
            }}
        """
        self._grid_btn.setStyleSheet(trio_inner_style)
        self._landscape_btn.setStyleSheet(trio_inner_style)
        self._portrait_btn.setStyleSheet(trio_inner_style)

    def apply_theme(self):
        self._apply_theme()
