"""
涛割 - 资产详情编辑窗口
独立窗口（非模态 QWidget），三列布局：左列图片区、中列信息区、右列侧边栏。
"""

import os
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QGridLayout, QMessageBox,
    QFileDialog, QTextEdit, QComboBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap, QColor

from ui.pixmap_cache import PixmapCache


# ── 资产类型颜色映射 ──
_TYPE_BADGE_COLORS = {
    'character': ('#6495ED', '角色'),
    'scene_bg': ('#50c878', '场景'),
    'prop': ('#a078dc', '道具'),
    'lighting_ref': ('#FFD700', '照明参考'),
}

# ── 衍生类型标签 ──
_VARIANT_TYPE_LABELS = {
    'costume_variant': '服装衍生',
    'age_variant': '年龄衍生',
    'appearance_variant': '外貌衍生',
}


# ============================================================
#  TagEditor — 可编辑 tag 列表
# ============================================================

class TagEditor(QWidget):
    """圆角标签列表：支持添加 + 删除"""

    tags_changed = pyqtSignal(list)

    def __init__(self, initial_tags: list = None, parent=None):
        super().__init__(parent)
        self._tags = list(initial_tags or [])
        self._init_ui()
        self._rebuild()

    def _init_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._tags_container = QWidget()
        self._tags_flow = QHBoxLayout(self._tags_container)
        self._tags_flow.setContentsMargins(0, 0, 0, 0)
        self._tags_flow.setSpacing(4)
        self._tags_flow.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # 包裹在滚动区（标签过多时水平滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(40)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.setWidget(self._tags_container)
        self._layout.addWidget(scroll)

        # 输入行
        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入标签，回车添加")
        self._input.setFixedHeight(28)
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 4px; padding: 2px 8px; color: white;
            }
        """)
        self._input.returnPressed.connect(self._add_tag)
        input_row.addWidget(self._input)
        self._layout.addLayout(input_row)

    def _add_tag(self):
        text = self._input.text().strip()
        if text and text not in self._tags:
            self._tags.append(text)
            self._input.clear()
            self._rebuild()
            self.tags_changed.emit(self._tags)

    def _remove_tag(self, tag: str):
        if tag in self._tags:
            self._tags.remove(tag)
            self._rebuild()
            self.tags_changed.emit(self._tags)

    def _rebuild(self):
        # 清除现有标签
        while self._tags_flow.count():
            item = self._tags_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for tag in self._tags:
            chip = QPushButton(f" {tag} ×")
            chip.setFixedHeight(26)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setStyleSheet("""
                QPushButton {
                    background: rgba(100,149,237,0.3);
                    border: 1px solid rgba(100,149,237,0.5);
                    border-radius: 12px; padding: 0 10px;
                    color: white; font-size: 11px;
                }
                QPushButton:hover { background: rgba(100,149,237,0.5); }
            """)
            chip.clicked.connect(lambda _, t=tag: self._remove_tag(t))
            self._tags_flow.addWidget(chip)

        self._tags_flow.addStretch()

    def get_tags(self) -> list:
        return list(self._tags)


# ============================================================
#  ImageGalleryStrip — 水平滚动图片条
# ============================================================

class ImageGalleryStrip(QWidget):
    """水平滚动的缩略图列表 + 添加按钮"""

    images_changed = pyqtSignal(list)

    def __init__(self, initial_images: list = None, parent=None):
        super().__init__(parent)
        self._images = list(initial_images or [])
        self._init_ui()
        self._rebuild()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(90)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self._container = QWidget()
        self._flow = QHBoxLayout(self._container)
        self._flow.setContentsMargins(0, 0, 0, 0)
        self._flow.setSpacing(8)
        self._flow.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def _rebuild(self):
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for img_path in self._images:
            thumb = QLabel()
            thumb.setFixedSize(70, 70)
            thumb.setStyleSheet("""
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
            """)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if os.path.exists(img_path):
                pix = PixmapCache.instance().get_scaled(img_path, 70, 70)
                if pix:
                    thumb.setPixmap(pix)
                else:
                    thumb.setText("...")
            else:
                thumb.setText("缺失")
            self._flow.addWidget(thumb)

        # 添加按钮
        add_btn = QPushButton("+")
        add_btn.setFixedSize(70, 70)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.03);
                border: 2px dashed rgba(255,255,255,0.2);
                border-radius: 6px; color: rgba(255,255,255,0.4);
                font-size: 24px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                border-color: rgba(0,122,204,0.5);
            }
        """)
        add_btn.clicked.connect(self._add_images)
        self._flow.addWidget(add_btn)
        self._flow.addStretch()

    def _add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择参考图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.webp);;所有文件 (*.*)"
        )
        if files:
            self._images.extend(files)
            self._rebuild()
            self.images_changed.emit(self._images)

    def get_images(self) -> list:
        return list(self._images)


# ============================================================
#  MultiAngleGrid — 2×2 多角度图片网格（预留占位）
# ============================================================

class MultiAngleGrid(QWidget):
    """2×2 多角度图片网格（预留占位）"""

    def __init__(self, images: list = None, parent=None):
        super().__init__(parent)
        self._images = images or []
        self._init_ui()

    def _init_ui(self):
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)

        for i in range(4):
            cell = QLabel()
            cell.setFixedSize(70, 70)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet("""
                background: rgba(255,255,255,0.02);
                border: 1px dashed rgba(255,255,255,0.15);
                border-radius: 6px;
                color: rgba(255,255,255,0.3);
                font-size: 9px;
            """)
            if i < len(self._images):
                img = self._images[i]
                # 兼容 dict 格式 {"angle": "...", "path": "..."} 和纯字符串路径
                img_path = img.get('path', '') if isinstance(img, dict) else img
                pix = None
                if img_path and os.path.exists(img_path):
                    pix = PixmapCache.instance().get_scaled(img_path, 70, 70)
                if pix:
                    cell.setPixmap(pix)
                else:
                    cell.setText("多角度\n(开发中)")
            else:
                cell.setText("多角度\n(开发中)")
            grid.addWidget(cell, i // 2, i % 2)


# ============================================================
#  AssetDetailWindow — 独立资产详情编辑窗口
# ============================================================

class AssetDetailWindow(QWidget):
    """独立资产详情编辑窗口（非模态）"""

    asset_saved = pyqtSignal(int)  # asset_id

    def __init__(self, asset_data: dict, controller, parent=None):
        super().__init__(parent)
        self._asset_data = dict(asset_data)
        self._controller = controller

        self.setWindowTitle(f"编辑资产 — {asset_data.get('name', '未命名')}")
        self.setMinimumSize(900, 650)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._apply_style()
        self._init_ui()
        self._load_data()

    def _apply_style(self):
        self.setStyleSheet("""
            AssetDetailWindow {
                background-color: rgb(28, 28, 35);
            }
            QLabel {
                color: rgba(255,255,255,0.85);
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 6px;
                padding: 6px 10px;
                color: white;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: rgb(0,122,204);
            }
            QPushButton {
                background-color: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.12);
            }
            QComboBox QAbstractItemView {
                background-color: rgb(40,40,50);
                color: white;
                selection-background-color: rgb(0,122,204);
            }
        """)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── 顶栏 ──
        top_bar = QHBoxLayout()
        back_btn = QPushButton("< 返回")
        back_btn.setFixedWidth(80)
        back_btn.clicked.connect(self.close)
        top_bar.addWidget(back_btn)

        title = QLabel(f"编辑资产 — {self._asset_data.get('name', '')}")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        top_bar.addWidget(title)
        top_bar.addStretch()

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton { background: rgb(0,122,204); border: none; font-weight: bold; }
            QPushButton:hover { background: rgb(0,140,230); }
        """)
        save_btn.clicked.connect(self._save)
        top_bar.addWidget(save_btn)

        del_btn = QPushButton("删除")
        del_btn.setStyleSheet("""
            QPushButton { background: rgba(220,50,50,0.8); border: none; }
            QPushButton:hover { background: rgba(220,50,50,1); }
        """)
        del_btn.clicked.connect(self._delete)
        top_bar.addWidget(del_btn)

        root.addLayout(top_bar)

        # ── 三列主体 ──
        body = QHBoxLayout()
        body.setSpacing(16)

        # 左列 — 图片区
        left = QVBoxLayout()
        left.setSpacing(12)

        # 主参考图
        self._main_image_label = QLabel("点击更换主图")
        self._main_image_label.setFixedSize(280, 360)
        self._main_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._main_image_label.setStyleSheet("""
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            color: rgba(255,255,255,0.3);
        """)
        self._main_image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._main_image_label.mousePressEvent = self._change_main_image
        left.addWidget(self._main_image_label)

        # 多角度图网格（预留）
        left.addWidget(QLabel("多角度图片"))
        self._multi_angle = MultiAngleGrid(
            self._asset_data.get('multi_angle_images', []))
        left.addWidget(self._multi_angle)

        # 参考图片条
        left.addWidget(QLabel("参考图片"))
        self._gallery = ImageGalleryStrip(
            self._asset_data.get('reference_images', []))
        left.addWidget(self._gallery)
        left.addStretch()

        body.addLayout(left)

        # 中列 — 信息区（QScrollArea）
        mid_scroll = QScrollArea()
        mid_scroll.setWidgetResizable(True)
        mid_scroll.setFrameShape(QFrame.Shape.NoFrame)
        mid_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        mid_widget = QWidget()
        mid = QVBoxLayout(mid_widget)
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(10)

        # 名称
        mid.addWidget(QLabel("名称"))
        self._name_input = QLineEdit()
        mid.addWidget(self._name_input)

        # 类型（只读 badge）
        asset_type = self._asset_data.get('asset_type', '')
        badge_color, badge_text = _TYPE_BADGE_COLORS.get(
            asset_type, ('#888', asset_type))
        type_label = QLabel(f"  {badge_text}  ")
        type_label.setStyleSheet(f"""
            background: {badge_color};
            color: white; border-radius: 10px;
            padding: 3px 12px; font-size: 11px;
        """)
        type_label.setFixedHeight(24)
        mid.addWidget(type_label)

        # 描述
        mid.addWidget(QLabel("描述"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(80)
        mid.addWidget(self._desc_edit)

        # 视觉特征
        mid.addWidget(QLabel("视觉特征"))
        self._appearance_edit = QTextEdit()
        self._appearance_edit.setMaximumHeight(70)
        mid.addWidget(self._appearance_edit)

        # 视觉锚点
        mid.addWidget(QLabel("视觉锚点"))
        self._anchors_editor = TagEditor(
            self._asset_data.get('visual_anchors', []))
        mid.addWidget(self._anchors_editor)

        # 标签
        mid.addWidget(QLabel("标签"))
        self._tags_editor = TagEditor(self._asset_data.get('tags', []))
        mid.addWidget(self._tags_editor)

        # 类型专属属性区
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.1);")
        mid.addWidget(sep)
        mid.addWidget(QLabel("类型专属属性"))

        self._type_fields = {}
        if asset_type == 'character':
            fields = [
                ('gender', '性别', 'combo', ['', '男', '女']),
                ('age', '年龄', 'text', None),
                ('age_group', '年龄段', 'combo',
                 ['', '儿童', '少年', '青年', '中年', '老年']),
                ('hairstyle', '发型', 'text', None),
                ('hair_color', '发色', 'text', None),
                ('body_type', '体型', 'combo',
                 ['', '普通', '偏瘦', '健壮', '丰满']),
                ('clothing_style', '穿着', 'text', None),
            ]
        elif asset_type == 'scene_bg':
            fields = [
                ('location', '地点', 'text', None),
                ('time_of_day', '时间', 'text', None),
                ('weather', '天气', 'text', None),
                ('mood', '氛围', 'text', None),
                ('era', '时代', 'text', None),
            ]
        elif asset_type == 'prop':
            fields = [
                ('material', '材质', 'text', None),
                ('size', '大小', 'text', None),
                ('color', '颜色', 'text', None),
                ('usage', '用途', 'text', None),
            ]
        else:
            fields = []

        for key, label_text, field_type, options in fields:
            row = QHBoxLayout()
            lbl = QLabel(f"{label_text}:")
            lbl.setFixedWidth(60)
            row.addWidget(lbl)

            if field_type == 'combo' and options:
                w = QComboBox()
                w.addItems(options)
                w.setStyleSheet("""
                    QComboBox {
                        background: rgba(255,255,255,0.05);
                        border: 1px solid rgba(255,255,255,0.15);
                        border-radius: 4px; padding: 4px 8px; color: white;
                    }
                """)
            else:
                w = QLineEdit()
            row.addWidget(w)
            mid.addLayout(row)
            self._type_fields[key] = w

        mid.addStretch()
        mid_scroll.setWidget(mid_widget)
        body.addWidget(mid_scroll, 1)

        # 右列 — 侧边栏
        right = QVBoxLayout()
        right.setSpacing(12)

        # 元信息
        right.addWidget(QLabel("元信息"))
        meta_frame = QFrame()
        meta_frame.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
            }
        """)
        meta_layout = QVBoxLayout(meta_frame)
        meta_layout.setContentsMargins(10, 10, 10, 10)
        meta_layout.setSpacing(6)

        created = self._asset_data.get('created_at', '—')
        updated = self._asset_data.get('updated_at', '—')
        meta_layout.addWidget(QLabel(f"创建: {str(created)[:19]}"))
        meta_layout.addWidget(QLabel(f"更新: {str(updated)[:19]}"))
        right.addWidget(meta_frame)

        # 衍生形象区（角色专用）
        if asset_type == 'character':
            right.addWidget(QLabel("衍生形象"))
            self._variant_container = QVBoxLayout()
            right.addLayout(self._variant_container)

            add_variant_btn = QPushButton("+ 新增衍生")
            add_variant_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_variant_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,122,204,0.3);
                    border: 1px dashed rgba(0,122,204,0.5);
                    border-radius: 6px;
                }
                QPushButton:hover { background: rgba(0,122,204,0.5); }
            """)
            add_variant_btn.clicked.connect(self._add_variant)
            right.addWidget(add_variant_btn)

        # 操作按钮
        right.addStretch()

        gen_btn = QPushButton("生成图片")
        gen_btn.setStyleSheet("""
            QPushButton { background: rgb(0,122,204); border: none; font-weight: bold; }
            QPushButton:hover { background: rgb(0,140,230); }
        """)
        right.addWidget(gen_btn)

        multi_gen_btn = QPushButton("多角度生成 (开发中)")
        multi_gen_btn.setEnabled(False)
        multi_gen_btn.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.3); }
        """)
        right.addWidget(multi_gen_btn)

        body.addLayout(right)
        root.addLayout(body, 1)

    def _load_data(self):
        """加载资产数据到表单"""
        a = self._asset_data
        self._name_input.setText(a.get('name', ''))
        self._desc_edit.setPlainText(a.get('description', ''))

        # 视觉特征
        va = a.get('visual_attributes') or {}
        appearance = va.get('appearance', '') or a.get('prompt_description', '')
        self._appearance_edit.setPlainText(appearance)

        # 主参考图
        main_img = a.get('main_reference_image', '')
        if main_img and os.path.exists(main_img):
            pix = PixmapCache.instance().get_scaled(main_img, 280, 360)
            if pix:
                self._main_image_label.setPixmap(pix)

        # 类型专属属性
        for key, widget in self._type_fields.items():
            val = va.get(key, '')
            if isinstance(widget, QComboBox):
                idx = widget.findText(str(val)) if val else 0
                widget.setCurrentIndex(max(0, idx))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val) if val else '')

        # 加载衍生形象
        if hasattr(self, '_variant_container'):
            self._load_variants()

    def _load_variants(self):
        """加载角色衍生形象列表"""
        asset_id = self._asset_data.get('id')
        if not asset_id:
            return
        variants = self._controller.get_character_variants(asset_id)
        for v in variants:
            card = self._create_variant_mini_card(v)
            self._variant_container.addWidget(card)

    def _create_variant_mini_card(self, variant_data: dict) -> QFrame:
        """创建衍生形象迷你卡片"""
        card = QFrame()
        card.setFixedHeight(60)
        card.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
            }
            QFrame:hover { background: rgba(255,255,255,0.08); }
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # 缩略图
        thumb = QLabel()
        thumb.setFixedSize(44, 44)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("""
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
        """)
        img = variant_data.get('main_reference_image', '')
        if img and os.path.exists(img):
            pix = PixmapCache.instance().get_scaled(img, 44, 44)
            if pix:
                thumb.setPixmap(pix)
            else:
                thumb.setText("...")
        else:
            thumb.setText("无图")
        layout.addWidget(thumb)

        # 名称 + variant_type 标签
        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(variant_data.get('name', ''))
        name_lbl.setFont(QFont("Microsoft YaHei", 10))
        name_lbl.setStyleSheet("color: white;")
        info.addWidget(name_lbl)

        vtype = variant_data.get('variant_type', '')
        vtype_text = _VARIANT_TYPE_LABELS.get(vtype, vtype)
        type_lbl = QLabel(vtype_text)
        type_lbl.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 10px;")
        info.addWidget(type_lbl)

        layout.addLayout(info, 1)
        return card

    def _change_main_image(self, event):
        """点击主图 → 更换"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择主参考图", "",
            "图片文件 (*.png *.jpg *.jpeg *.webp);;所有文件 (*.*)"
        )
        if files:
            self._asset_data['main_reference_image'] = files[0]
            pix = PixmapCache.instance().get_scaled(files[0], 280, 360)
            if pix:
                self._main_image_label.setPixmap(pix)

    def _add_variant(self):
        """新增衍生形象"""
        asset_id = self._asset_data.get('id')
        if not asset_id:
            return
        result = self._controller.create_character_variant(
            base_asset_id=asset_id,
            variant_type='costume_variant',
            variant_description='新衍生形象',
            name=f"{self._asset_data.get('name', '')}（新衍生）",
        )
        if result:
            card = self._create_variant_mini_card(result)
            self._variant_container.addWidget(card)

    def _collect_form_data(self) -> dict:
        """收集表单数据"""
        data = {
            'name': self._name_input.text().strip(),
            'description': self._desc_edit.toPlainText().strip(),
            'prompt_description': self._appearance_edit.toPlainText().strip(),
            'visual_anchors': self._anchors_editor.get_tags(),
            'tags': self._tags_editor.get_tags(),
            'reference_images': self._gallery.get_images(),
            'main_reference_image': self._asset_data.get('main_reference_image'),
        }

        # 类型专属属性 → visual_attributes
        va = dict(self._asset_data.get('visual_attributes') or {})
        for key, widget in self._type_fields.items():
            if isinstance(widget, QComboBox):
                val = widget.currentText()
            elif isinstance(widget, QLineEdit):
                val = widget.text().strip()
            else:
                val = ''
            if val:
                va[key] = val
            elif key in va:
                del va[key]
        # 保留 appearance
        appearance = self._appearance_edit.toPlainText().strip()
        if appearance:
            va['appearance'] = appearance
        data['visual_attributes'] = va

        return data

    def _save(self):
        data = self._collect_form_data()
        if not data['name']:
            QMessageBox.warning(self, "提示", "请输入名称")
            return

        asset_id = self._asset_data.get('id')
        self._controller.update_asset(asset_id, **data)
        self.asset_saved.emit(asset_id)
        self.close()

    def _delete(self):
        name = self._asset_data.get('name', '未命名')
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除资产 '{name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._controller.delete_asset(self._asset_data.get('id'))
            self.asset_saved.emit(self._asset_data.get('id', 0))
            self.close()
