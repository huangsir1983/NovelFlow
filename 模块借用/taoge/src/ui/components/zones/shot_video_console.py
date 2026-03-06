"""
涛割 - 视频控制台面板
ShotVideoConsole: viewport 子控件，底部滑入/滑出的视频生成参数面板。

布局:
┌──────────────────────────────────────────────────────────┐
│ [10s] [sora-2-all] [large]  │  提示词输入区          │ [横│竖] [无风格] │
│   ↑可展开                   │  支持@资产             │                  │
│                              │  字数        [生成]    │                  │
└──────────────────────────────────────────────────────────┘
"""

from typing import Optional, List, Dict
import os

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtGui import QFont, QColor, QPixmap, QTextImageFormat

from ui import theme

# 复用图片控制台的通用组件
from .shot_image_console import PopupSelector, ToolbarButton, AssetMentionPopup


# ============================================================
#  ShotVideoConsole — 视频控制台
# ============================================================

class ShotVideoConsole(QWidget):
    """
    底部滑入/滑出的视频生成参数面板。
    布局: 左侧3按钮 | 中间提示词大框 | 右侧横竖屏+风格
    """

    generate_video_requested = pyqtSignal(dict)

    SLIDE_DURATION = 200
    SLIDE_OFFSET = 200
    PANEL_HEIGHT = 180
    MAX_WIDTH = 960
    MARGIN = 20

    # 模型映射
    MODEL_MAP = {
        'sora-2-all': 'sora-2-all',
        'sora-2-pro': 'sora-2-pro',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_visible_state = False
        self._slide_anim: Optional[QPropertyAnimation] = None
        self._current_scene_index: Optional[int] = None

        # 当前选中值
        self._duration = '10'
        self._model_key = 'sora-2-all'
        self._size = 'large'
        self._orientation = 'landscape'
        self._style = '无风格'
        self._source_image = ''
        self._reference_images: List[str] = []

        # @ 资产提及
        self._available_assets: Dict[str, List[dict]] = {}
        self._mentioned_assets: List[dict] = []
        self._current_assets: List[dict] = []
        self._asset_mention_popup: Optional[AssetMentionPopup] = None
        self._suppress_text_changed = False

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

    def set_source_image(self, path: str):
        """设置 I2V 源图片路径"""
        self._source_image = path or ''

    def set_reference_images(self, paths: List[str]):
        """设置多张参考图片路径"""
        self._reference_images = paths or []

    def set_available_assets(self, assets_by_type: Dict[str, List[dict]]):
        """设置可供 @ 提及的资产库数据"""
        self._available_assets = assets_by_type or {}

    def add_mentioned_asset(self, asset: dict):
        """用户通过 @ 弹窗手动选中一个资产"""
        name = asset.get('name', '')
        if not name:
            return

        existing_names = {a.get('name') for a in self._mentioned_assets}
        if name in existing_names:
            return

        self._mentioned_assets.append(asset)

        cursor = self._prompt_edit.textCursor()
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

        if img_path and img_path not in self._reference_images:
            self._reference_images.append(img_path)

    def _insert_inline_thumbnail(self, cursor, name: str, image_path: str):
        """在 cursor 位置插入内联缩略图 + @名称"""
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
        """设置提示词并在末尾插入关联资产的内联缩略图"""
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

        # ── 左侧: 3 个工具栏按钮（底部对齐）──
        left_layout = QVBoxLayout()
        left_layout.setSpacing(0)
        left_layout.addStretch()

        left_btns = QHBoxLayout()
        left_btns.setSpacing(4)

        self._duration_btn = ToolbarButton(f"{self._duration}s")
        self._duration_btn.setFixedWidth(50)
        self._duration_btn.clicked.connect(self._show_duration_popup)
        left_btns.addWidget(self._duration_btn)

        self._model_btn = ToolbarButton(self._model_key)
        self._model_btn.setFixedWidth(90)
        self._model_btn.clicked.connect(self._show_model_popup)
        left_btns.addWidget(self._model_btn)

        self._size_btn = ToolbarButton(self._size)
        self._size_btn.setFixedWidth(56)
        self._size_btn.clicked.connect(self._show_size_popup)
        left_btns.addWidget(self._size_btn)

        left_layout.addLayout(left_btns)
        main_layout.addLayout(left_layout)

        # ── 中间: 提示词大框（底部对齐）──
        center_layout = QVBoxLayout()
        center_layout.setSpacing(0)
        center_layout.setContentsMargins(0, 8, 0, 0)

        self._prompt_frame = QFrame()
        prompt_inner = QVBoxLayout(self._prompt_frame)
        prompt_inner.setContentsMargins(10, 8, 10, 6)
        prompt_inner.setSpacing(4)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlaceholderText("描述视频画面...输入@选择资产")
        self._prompt_edit.setFont(QFont("Microsoft YaHei", 10))
        self._prompt_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._prompt_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._prompt_edit.textChanged.connect(self._update_char_count)
        prompt_inner.addWidget(self._prompt_edit, stretch=1)

        # 底部行: 字数 + 生成按钮
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self._char_count_label = QLabel("0字")
        self._char_count_label.setFont(QFont("Microsoft YaHei", 8))
        bottom_row.addWidget(self._char_count_label)

        bottom_row.addStretch()

        # I2V 源图指示
        self._source_image_label = QLabel("")
        self._source_image_label.setFont(QFont("Microsoft YaHei", 8))
        self._source_image_label.setVisible(False)
        bottom_row.addWidget(self._source_image_label)

        self._generate_btn = QPushButton("生成")
        self._generate_btn.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self._generate_btn.setFixedSize(60, 28)
        self._generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generate_btn.clicked.connect(self._on_generate_clicked)
        bottom_row.addWidget(self._generate_btn)

        prompt_inner.addLayout(bottom_row)
        center_layout.addWidget(self._prompt_frame)
        main_layout.addLayout(center_layout, stretch=1)

        # ── 右侧: 横竖屏 + 风格按钮（底部对齐）──
        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.addStretch()

        right_btns = QHBoxLayout()
        right_btns.setSpacing(0)

        # 横竖屏容器
        self._orient_frame = QFrame()
        orient_layout = QHBoxLayout(self._orient_frame)
        orient_layout.setContentsMargins(0, 0, 0, 0)
        orient_layout.setSpacing(0)

        self._landscape_btn = QPushButton("横")
        self._landscape_btn.setFont(QFont("Microsoft YaHei", 9))
        self._landscape_btn.setFixedSize(36, 36)
        self._landscape_btn.setCheckable(True)
        self._landscape_btn.setChecked(True)
        self._landscape_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._landscape_btn.clicked.connect(lambda: self._set_orientation('landscape'))
        orient_layout.addWidget(self._landscape_btn)

        self._portrait_btn = QPushButton("竖")
        self._portrait_btn.setFont(QFont("Microsoft YaHei", 9))
        self._portrait_btn.setFixedSize(36, 36)
        self._portrait_btn.setCheckable(True)
        self._portrait_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._portrait_btn.clicked.connect(lambda: self._set_orientation('portrait'))
        orient_layout.addWidget(self._portrait_btn)

        right_btns.addWidget(self._orient_frame)
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

    def _show_duration_popup(self):
        popup = self._ensure_popup()
        popup.setup('duration', [
            {'value': '10', 'label': '10s'},
            {'value': '15', 'label': '15s'},
        ], columns=2)
        popup.show_above(self._duration_btn)

    def _show_model_popup(self):
        popup = self._ensure_popup()
        popup.setup('model', [
            {'value': 'sora-2-all', 'label': 'sora-2-all', 'subtitle': '标准'},
            {'value': 'sora-2-pro', 'label': 'sora-2-pro', 'subtitle': '高质量'},
        ], columns=1)
        popup.show_above(self._model_btn)

    def _show_size_popup(self):
        popup = self._ensure_popup()
        popup.setup('size', [
            {'value': 'large', 'label': 'large'},
            {'value': 'small', 'label': 'small'},
        ], columns=2)
        popup.show_above(self._size_btn)

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

        if key == 'duration':
            self._duration = value
            self._duration_btn.setText(f"{value}s")

        elif key == 'model':
            self._model_key = value
            self._model_btn.setText(value)

        elif key == 'size':
            self._size = value
            self._size_btn.setText(value)

        elif key == 'style':
            self._style = value
            self._style_btn.setText(value)

    # ==================== 横竖屏 ====================

    def _set_orientation(self, orient: str):
        self._orientation = orient
        if orient == 'landscape':
            self._landscape_btn.setChecked(True)
            self._portrait_btn.setChecked(False)
        else:
            self._landscape_btn.setChecked(False)
            self._portrait_btn.setChecked(True)

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
        """生成按钮"""
        params = self._build_params()
        self.generate_video_requested.emit(params)

    def _build_params(self) -> dict:
        raw_text = self._prompt_edit.toPlainText()
        clean_text = raw_text.replace('\uFFFC', '')

        # 提取纯净 base_prompt
        base_prompt = clean_text
        asset_sep = '\n参考资产：'
        sep_idx = clean_text.find(asset_sep)
        if sep_idx >= 0:
            base_prompt = clean_text[:sep_idx]

        # 收集所有关联资产
        all_assets: List[dict] = list(getattr(self, '_current_assets', []))
        existing_names = {a.get('name') for a in all_assets}
        for a in self._mentioned_assets:
            if a.get('name') not in existing_names:
                all_assets.append(a)
                existing_names.add(a.get('name'))

        params = {
            'scene_index': self._current_scene_index,
            'prompt': clean_text,
            'base_prompt': base_prompt,
            'duration': int(self._duration),
            'model': self._model_key,
            'size': self._size,
            'orientation': self._orientation,
            'style': self._style,
            'watermark': False,
            'source_image': self._source_image,
        }
        if all_assets:
            params['assets'] = all_assets
        if self._reference_images:
            params['reference_images'] = list(self._reference_images)
        return params

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

    # ==================== I2V 源图指示 ====================

    def _update_source_image_indicator(self):
        """更新 I2V 源图指示标签"""
        if self._source_image and os.path.isfile(self._source_image):
            self._source_image_label.setText("I2V")
            self._source_image_label.setVisible(True)
        else:
            self._source_image_label.setVisible(False)

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
            orient_bg = "rgba(38, 38, 42, 255)"
            orient_border = "rgba(255, 255, 255, 10)"
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
            orient_bg = "rgba(245, 245, 249, 255)"
            orient_border = "rgba(0, 0, 0, 8)"

        # 主面板
        self.setStyleSheet(f"""
            ShotVideoConsole {{
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

        # I2V 标签
        self._source_image_label.setStyleSheet(
            f"color: {accent_c}; background: transparent; border: none; font-weight: bold;")

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
        self._duration_btn.setStyleSheet(toolbar_style)
        self._model_btn.setStyleSheet(toolbar_style)
        self._size_btn.setStyleSheet(toolbar_style)
        self._style_btn.setStyleSheet(toolbar_style)

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

        # 横竖屏框
        self._orient_frame.setStyleSheet(f"""
            QFrame {{
                background: {orient_bg};
                border: 1px solid {orient_border};
                border-radius: 8px;
            }}
        """)

        orient_inner_style = f"""
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
        self._landscape_btn.setStyleSheet(orient_inner_style)
        self._portrait_btn.setStyleSheet(orient_inner_style)

    def apply_theme(self):
        self._apply_theme()
