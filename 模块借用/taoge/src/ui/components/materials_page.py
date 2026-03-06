"""
涛割 - 素材库页面组件
改用统一 Asset 模型，支持 角色/服装/场景/道具/照明参考 分类 Tab。
"""

import os
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QGridLayout, QMessageBox,
    QFileDialog, QTabWidget, QMenu, QDialog, QFormLayout,
    QTextEdit, QComboBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap, QAction

from ui.pixmap_cache import PixmapCache, ThumbnailLoader

from services.controllers.asset_controller import AssetController


# ── 资产类型显示映射 ──
ASSET_TYPE_LABELS = {
    'character': '角色',
    'scene_bg': '场景',
    'prop': '道具',
    'lighting_ref': '照明参考',
}

ASSET_TYPE_COLORS = {
    'character': 'rgba(100, 149, 237, 0.5)',   # 蓝
    'scene_bg': 'rgba(80, 200, 120, 0.5)',      # 绿
    'prop': 'rgba(160, 120, 220, 0.5)',          # 紫
    'lighting_ref': 'rgba(255, 215, 0, 0.5)',    # 金
}


class MaterialCard(QFrame):
    """资产卡片组件（统一 Asset 模型）"""

    clicked = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    edit_requested = pyqtSignal(object)
    multi_angle_requested = pyqtSignal(object)

    def __init__(self, asset_data: dict, parent=None):
        super().__init__(parent)
        self.asset_data = asset_data

        self.setFixedSize(180, 220)  # 默认尺寸，_init_ui 会动态更新
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            MaterialCard {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
            MaterialCard:hover {
                background-color: rgba(255, 255, 255, 0.08);
                border-color: rgba(0, 122, 204, 0.5);
            }
        """)

        self._init_ui()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # 向后兼容：旧代码通过 .character 访问
    @property
    def character(self):
        return self.asset_data

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 根据图片原始比例计算缩略图高度
        thumb_w = 160
        thumb_h = 140  # 默认高度
        ref_img = self.asset_data.get('main_reference_image', '')
        if ref_img and os.path.exists(ref_img):
            px = QPixmap(ref_img)
            if not px.isNull() and px.width() > 0:
                ratio = px.height() / px.width()
                thumb_h = int(thumb_w * ratio)
                thumb_h = max(80, min(200, thumb_h))  # 限制范围 80~200

        # 更新卡片总高度 = 缩略图高度 + 边距 + 名称标签 + 类型标签 (~80px)
        card_h = thumb_h + 80
        self.setFixedSize(180, card_h)

        # 缩略图
        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(thumb_w, thumb_h)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.03);
            border-radius: 6px;
            color: rgba(255, 255, 255, 0.3);
        """)

        if ref_img and os.path.exists(ref_img):
            scaled = PixmapCache.instance().get_scaled(ref_img, thumb_w, thumb_h)
            if scaled:
                self.thumbnail.setPixmap(scaled)
            else:
                self.thumbnail.setText("无图片")
        else:
            self.thumbnail.setText("无图片")

        layout.addWidget(self.thumbnail)

        # 多视角 badge（缩略图右下角）
        self._angle_badge = QLabel(self.thumbnail)
        self._angle_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._angle_badge.setStyleSheet("""
            QLabel {
                background: rgba(0, 180, 255, 0.85);
                border-radius: 8px;
                font-size: 10px;
                color: white;
                padding: 1px 6px;
            }
        """)
        self._angle_badge.setVisible(False)

        multi_angles = self.asset_data.get('multi_angle_images', [])
        if multi_angles:
            count = len(multi_angles)
            self._angle_badge.setText(f"\u00d7{count}")
            self._angle_badge.adjustSize()
            bw, bh = self._angle_badge.width(), self._angle_badge.height()
            self._angle_badge.move(thumb_w - bw - 4, thumb_h - bh - 4)
            self._angle_badge.setVisible(True)

        # 名称
        self.name_label = QLabel(self.asset_data.get('name', '未命名'))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("""
            color: white;
            font-size: 13px;
            font-weight: bold;
        """)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # 类型标签
        asset_type = self.asset_data.get('asset_type', '')
        type_text = ASSET_TYPE_LABELS.get(asset_type, asset_type)
        type_color = ASSET_TYPE_COLORS.get(asset_type, 'rgba(255, 255, 255, 0.5)')

        self.type_label = QLabel(type_text)
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_label.setStyleSheet(f"""
            color: {type_color};
            font-size: 11px;
        """)
        layout.addWidget(self.type_label)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(40, 40, 40);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 5px;
            }
            QMenu::item {
                color: white;
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: rgb(0, 122, 204);
            }
        """)

        edit_action = menu.addAction("编辑")
        edit_action.triggered.connect(lambda: self.edit_requested.emit(self.asset_data))

        # 仅有主图时才能生成多视角
        if self.asset_data.get('main_reference_image'):
            multi_action = menu.addAction("生成多视角")
            multi_action.triggered.connect(
                lambda: self.multi_angle_requested.emit(self.asset_data)
            )

        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self.asset_data))

        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.asset_data)
        super().mousePressEvent(event)


class AssetEditDialog(QDialog):
    """资产编辑对话框（适配 Asset 模型的所有字段）"""

    def __init__(self, asset_data: Optional[dict] = None, asset_type: str = 'character', parent=None):
        super().__init__(parent)
        self.asset_data = asset_data
        self.is_new = asset_data is None
        self.asset_type = asset_data.get('asset_type', asset_type) if asset_data else asset_type
        self.selected_images: List[str] = []

        if asset_data and asset_data.get('reference_images'):
            self.selected_images = list(asset_data['reference_images'])

        type_label = ASSET_TYPE_LABELS.get(self.asset_type, '资产')
        self.setWindowTitle(f"新建{type_label}" if self.is_new else f"编辑{type_label}")
        self.setFixedSize(520, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(30, 30, 30);
            }
            QLabel {
                color: white;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px;
                color: white;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: rgb(0, 122, 204);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px 16px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)

        self._init_ui()
        if asset_data:
            self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # 名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("输入名称")
        form.addRow("名称:", self.name_input)

        # 资产类型（新建时可选，编辑时只读）
        self.type_combo = QComboBox()
        self.type_combo.addItems(['character', 'scene_bg', 'prop', 'lighting_ref'])
        self.type_combo.setCurrentText(self.asset_type)
        self.type_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px;
                color: white;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(40, 40, 40);
                color: white;
                selection-background-color: rgb(0, 122, 204);
            }
        """)
        if not self.is_new:
            self.type_combo.setEnabled(False)
        form.addRow("类型:", self.type_combo)

        # 描述
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("描述")
        self.desc_input.setMaximumHeight(60)
        form.addRow("描述:", self.desc_input)

        # 视觉属性（JSON 摘要展示）
        self.appearance_input = QTextEdit()
        self.appearance_input.setPlaceholderText("视觉特征描述")
        self.appearance_input.setMaximumHeight(80)
        form.addRow("视觉特征:", self.appearance_input)

        # Visual Anchors（角色专用）
        self.anchors_input = QLineEdit()
        self.anchors_input.setPlaceholderText("视觉锚点（逗号分隔），如：左眼下方小痣, 银色手表左腕")
        form.addRow("视觉锚点:", self.anchors_input)

        # 标签
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("标签（逗号分隔），如：主角, 战士, 东方")
        form.addRow("标签:", self.tags_input)

        layout.addLayout(form)

        # 参考图片区域
        images_label = QLabel("参考图片:")
        layout.addWidget(images_label)

        images_layout = QHBoxLayout()

        self.images_preview = QLabel("未选择图片")
        self.images_preview.setFixedHeight(80)
        self.images_preview.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px dashed rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            color: rgba(255, 255, 255, 0.5);
        """)
        self.images_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        images_layout.addWidget(self.images_preview, 1)

        select_btn = QPushButton("选择图片")
        select_btn.clicked.connect(self._select_images)
        images_layout.addWidget(select_btn)

        layout.addLayout(images_layout)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                border: none;
            }
            QPushButton:hover {
                background-color: rgb(0, 140, 230);
            }
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_data(self):
        """加载资产数据"""
        a = self.asset_data
        self.name_input.setText(a.get('name', ''))
        self.desc_input.setPlainText(a.get('description', ''))

        # 视觉特征从 visual_attributes 提取
        va = a.get('visual_attributes') or {}
        appearance = va.get('appearance', '') or a.get('prompt_description', '')
        self.appearance_input.setPlainText(appearance)

        # Visual Anchors
        anchors = a.get('visual_anchors') or []
        if anchors:
            self.anchors_input.setText(', '.join(anchors))

        # 标签
        tags = a.get('tags') or []
        if tags:
            self.tags_input.setText(', '.join(tags))

        if self.selected_images:
            self.images_preview.setText(f"已选择 {len(self.selected_images)} 张图片")

    def _select_images(self):
        """选择参考图片"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择参考图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp);;所有文件 (*.*)"
        )
        if files:
            self.selected_images = files
            self.images_preview.setText(f"已选择 {len(files)} 张图片")

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入名称")
            return
        self.accept()

    def get_data(self) -> dict:
        """获取表单数据"""
        anchors_text = self.anchors_input.text().strip()
        anchors = [a.strip() for a in anchors_text.split(',') if a.strip()] if anchors_text else []

        tags_text = self.tags_input.text().strip()
        tags = [t.strip() for t in tags_text.split(',') if t.strip()] if tags_text else []

        return {
            'name': self.name_input.text().strip(),
            'asset_type': self.type_combo.currentText(),
            'description': self.desc_input.toPlainText().strip(),
            'prompt_description': self.appearance_input.toPlainText().strip(),
            'visual_anchors': anchors,
            'tags': tags,
            'reference_images': self.selected_images,
            'main_reference_image': self.selected_images[0] if self.selected_images else None,
        }


# 旧名向后兼容
CharacterEditDialog = AssetEditDialog


class MaterialsPage(QWidget):
    """素材库页面（使用 Asset 模型）"""

    edit_asset_requested = pyqtSignal(dict)  # asset_data → 全屏编辑器

    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = AssetController()
        self._init_ui()
        self._load_materials()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # 标题栏
        header = QHBoxLayout()

        title = QLabel("资产库")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索资产...")
        self.search_input.setFixedWidth(250)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 8px 12px;
                color: white;
            }
            QLineEdit:focus {
                border-color: rgb(0, 122, 204);
            }
        """)
        self.search_input.textChanged.connect(self._filter_materials)
        header.addWidget(self.search_input)

        # 新建按钮
        add_btn = QPushButton("+ 新建资产")
        add_btn.setFixedSize(120, 36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgb(0, 140, 230);
            }
        """)
        add_btn.clicked.connect(self._add_asset)
        header.addWidget(add_btn)

        layout.addLayout(header)

        # 选项卡
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.02);
            }
            QTabBar::tab {
                background-color: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.6);
                padding: 10px 25px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: rgba(0, 122, 204, 0.3);
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)

        # Tab: 全部 / 角色 / 场景 / 道具 / 照明参考
        self.all_tab = self._create_materials_grid()
        self.tab_widget.addTab(self.all_tab, "全部")

        self.character_tab = self._create_materials_grid()
        self.tab_widget.addTab(self.character_tab, "角色")

        self.scene_tab = self._create_materials_grid()
        self.tab_widget.addTab(self.scene_tab, "场景")

        self.prop_tab = self._create_materials_grid()
        self.tab_widget.addTab(self.prop_tab, "道具")

        self.lighting_tab = self._create_materials_grid()
        self.tab_widget.addTab(self.lighting_tab, "照明参考")

        layout.addWidget(self.tab_widget)

    def _create_materials_grid(self) -> QScrollArea:
        """创建素材网格"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")

        grid = QGridLayout(content)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setSpacing(20)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(content)
        return scroll

    def _get_tab_for_type(self, asset_type: str) -> QScrollArea:
        """根据资产类型获取对应 Tab"""
        tab_map = {
            'character': self.character_tab,
            'scene_bg': self.scene_tab,
            'prop': self.prop_tab,
            'lighting_ref': self.lighting_tab,
        }
        return tab_map.get(asset_type)

    def _load_materials(self):
        """加载所有资产"""
        assets = self._controller.get_all_assets()

        # 清空所有 Tab
        all_tabs = [self.all_tab, self.character_tab,
                    self.scene_tab, self.prop_tab, self.lighting_tab]
        for tab in all_tabs:
            self._clear_grid(tab)

        # 分类计数器
        all_grid = self.all_tab.widget().layout()
        type_grids = {
            'character': self.character_tab.widget().layout(),
            'scene_bg': self.scene_tab.widget().layout(),
            'prop': self.prop_tab.widget().layout(),
            'lighting_ref': self.lighting_tab.widget().layout(),
        }
        type_idx = {k: 0 for k in type_grids}
        all_idx = 0
        cols = 5

        for asset_dict in assets:
            asset_type = asset_dict.get('asset_type', '')

            # 创建卡片到"全部"Tab
            card = MaterialCard(asset_dict)
            card.clicked.connect(self._on_card_clicked)
            card.edit_requested.connect(self._edit_asset)
            card.delete_requested.connect(self._delete_asset)
            card.multi_angle_requested.connect(self._generate_multi_angle)

            all_grid.addWidget(card, all_idx // cols, all_idx % cols)
            all_idx += 1

            # 添加到类型 Tab
            type_grid = type_grids.get(asset_type)
            if type_grid is not None:
                card2 = MaterialCard(asset_dict)
                card2.clicked.connect(self._on_card_clicked)
                card2.edit_requested.connect(self._edit_asset)
                card2.delete_requested.connect(self._delete_asset)
                card2.multi_angle_requested.connect(self._generate_multi_angle)
                idx = type_idx[asset_type]
                type_grid.addWidget(card2, idx // cols, idx % cols)
                type_idx[asset_type] = idx + 1

        # 强制 QScrollArea 重新计算内部尺寸（修复标签页无数据显示的问题）
        for i in range(self.tab_widget.count()):
            scroll = self.tab_widget.widget(i)
            if scroll:
                content = scroll.widget()
                if content:
                    content.adjustSize()

    def _clear_grid(self, scroll_area: QScrollArea):
        """清空网格"""
        content = scroll_area.widget()
        layout = content.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _filter_materials(self, text: str):
        """过滤素材"""
        text = text.lower()

        def filter_grid(scroll_area: QScrollArea):
            content = scroll_area.widget()
            layout = content.layout()
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if isinstance(card, MaterialCard):
                        name = card.asset_data.get('name', '').lower()
                        tags = card.asset_data.get('tags') or []
                        tag_match = any(text in t.lower() for t in tags)
                        visible = text in name or tag_match
                        card.setVisible(visible)

        all_tabs = [self.all_tab, self.character_tab,
                    self.scene_tab, self.prop_tab, self.lighting_tab]
        for tab in all_tabs:
            filter_grid(tab)

    def _add_asset(self):
        """添加新资产"""
        dialog = AssetEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            result = self._controller.create_asset(
                name=data['name'],
                asset_type=data['asset_type'],
                description=data.get('description', ''),
                prompt_description=data.get('prompt_description', ''),
                tags=data.get('tags'),
                reference_images=data.get('reference_images'),
                main_reference_image=data.get('main_reference_image'),
                visual_anchors=data.get('visual_anchors'),
            )

            if result:
                self._load_materials()
                type_label = ASSET_TYPE_LABELS.get(data['asset_type'], '资产')
                QMessageBox.information(self, "提示", f"{type_label} '{data['name']}' 已创建")
            else:
                QMessageBox.warning(self, "错误", "创建资产失败")

    def _edit_asset(self, asset_data: dict):
        """编辑资产 — 发出信号，由 MainWindow 打开全屏编辑器"""
        asset_id = asset_data.get('id')
        if not asset_id:
            return
        self.edit_asset_requested.emit(asset_data)

    def _delete_asset(self, asset_data: dict):
        """删除资产"""
        name = asset_data.get('name', '未命名')
        asset_id = asset_data.get('id')

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除资产 '{name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._controller.delete_asset(asset_id)
            self._load_materials()

    def _on_card_clicked(self, asset_data: dict):
        """卡片点击事件"""
        self._edit_asset(asset_data)

    # ── 向后兼容方法 ──

    def _add_character(self):
        """向后兼容"""
        self._add_asset()

    def _edit_character(self, char_data: dict):
        """向后兼容"""
        self._edit_asset(char_data)

    def _delete_character(self, char_data: dict):
        """向后兼容"""
        self._delete_asset(char_data)

    # ── 多视角生成 ──

    def _generate_multi_angle(self, asset_data: dict):
        """右键菜单 → 生成多视角图片（支持多卡片并行）"""
        import os
        asset_id = asset_data.get('id')
        name = asset_data.get('name', '')
        img_path = asset_data.get('main_reference_image', '')

        if not img_path or not os.path.isfile(img_path):
            QMessageBox.warning(self, "提示", "该资产没有主图，无法生成多视角")
            return

        from config.settings import SettingsManager
        api_cfg = SettingsManager().settings.api
        api_key = api_cfg.runninghub_api_key
        base_url = api_cfg.runninghub_base_url

        if not api_key:
            QMessageBox.warning(self, "提示", "请先在设置中配置 RunningHub API Key")
            return

        # 初始化 workers 字典（首次）
        if not hasattr(self, '_ma_workers'):
            self._ma_workers: dict = {}

        # 同一资产不重复启动
        if asset_id in self._ma_workers and self._ma_workers[asset_id].isRunning():
            QMessageBox.information(self, "提示", f"「{name}」多视角正在生成中")
            return

        save_dir = os.path.join(
            os.path.dirname(img_path), 'multi_angle'
        )

        from services.multi_angle_batch_service import (
            MultiAngleBatchWorker, ANGLE_PROMPTS, ANGLE_LABELS,
        )

        worker = MultiAngleBatchWorker(
            img_path, save_dir, api_key, base_url,
            prompts=ANGLE_PROMPTS, labels=ANGLE_LABELS,
        )
        self._ma_workers[asset_id] = worker

        # 捕获变量到闭包
        _aid, _name = asset_id, name

        def on_all_done(success, paths, error):
            # 清理引用
            self._ma_workers.pop(_aid, None)
            if success and _aid:
                angle_images = [
                    {"angle": ANGLE_LABELS[i], "path": p}
                    for i, p in enumerate(paths)
                ]
                self._controller.update_asset(
                    _aid, multi_angle_images=angle_images
                )
                QMessageBox.information(
                    self, "完成",
                    f"「{_name}」多视角生成完成：{len(paths)} 张图片"
                )
            elif error:
                QMessageBox.warning(self, "失败", f"「{_name}」多视角生成失败: {error}")

        worker.all_completed.connect(on_all_done)
        worker.start()
        QMessageBox.information(
            self, "已启动",
            f"「{name}」多视角生成已启动（5张），请稍候..."
        )
