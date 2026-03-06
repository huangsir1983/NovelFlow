"""
涛割 - 道具资产编辑器
全屏页面：上半画布（核心形象 + 5张多角度卡）+ 下半信息栏。
"""

import os
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QFrame, QLineEdit, QTextEdit,
    QComboBox, QFormLayout,
)
from PyQt6.QtCore import Qt

from ui import theme
from ui.components.asset_editors.base_asset_editor import BaseAssetEditor
from ui.components.asset_editors.scene_editor import (
    _SimpleEditorCanvas, SCENE_ANGLE_LABELS,
)
from ui.components.asset_editors.character_editor import (
    MultiAngleCard,
)
from ui.components.image_preview_dialog import ImagePreviewDialog
from ui.components.asset_detail_window import TagEditor, ImageGalleryStrip

# 道具角度标签（第5张：近距离特写）
PROP_ANGLE_LABELS = ["正前", "正左", "正右", "正后", "近距离特写"]


class PropEditor(BaseAssetEditor):
    """道具资产全屏编辑器"""

    def __init__(self, asset_data: dict, controller, parent=None):
        super().__init__(asset_data, controller, parent)

    def _create_canvas(self) -> QWidget:
        self._canvas = _SimpleEditorCanvas(PROP_ANGLE_LABELS)
        self._canvas.node_selected.connect(self._on_node_selected)
        self._canvas.generate_angle_requested.connect(
            self.start_multi_angle_generation
        )
        return self._canvas

    def _create_info_panel(self) -> QWidget:
        panel = QScrollArea()
        panel.setWidgetResizable(True)
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setStyleSheet(
            f"QScrollArea {{ background: {theme.bg_secondary()}; border: none; }}"
        )

        container = QWidget()
        self._form = QFormLayout(container)
        self._form.setContentsMargins(16, 12, 16, 12)
        self._form.setSpacing(10)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        style = f"""
            QLineEdit, QTextEdit, QComboBox {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                padding: 4px 8px;
                color: {theme.text_primary()};
            }}
            QLabel {{
                color: {theme.text_secondary()};
                font-size: 12px;
                background: transparent;
            }}
        """
        container.setStyleSheet(style)

        self._name_edit = QLineEdit()
        self._form.addRow("名称", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setFixedHeight(60)
        self._form.addRow("描述", self._desc_edit)

        self._material_edit = QLineEdit()
        self._form.addRow("材质", self._material_edit)

        self._size_edit = QLineEdit()
        self._form.addRow("大小", self._size_edit)

        self._color_edit = QLineEdit()
        self._form.addRow("颜色", self._color_edit)

        self._usage_edit = QLineEdit()
        self._form.addRow("用途", self._usage_edit)

        self._anchor_edit = QTextEdit()
        self._anchor_edit.setFixedHeight(50)
        self._anchor_edit.setPlaceholderText("视觉锚点描述")
        self._form.addRow("视觉锚点", self._anchor_edit)

        self._tag_editor = TagEditor()
        self._form.addRow("标签", self._tag_editor)

        self._gallery = ImageGalleryStrip()
        self._form.addRow("参考图片", self._gallery)

        panel.setWidget(container)
        return panel

    def _load_data(self):
        d = self._asset_data
        self._name_edit.setText(d.get('name', ''))
        self._desc_edit.setPlainText(d.get('description', ''))

        attrs = d.get('visual_attributes', {}) or {}
        self._material_edit.setText(attrs.get('material', ''))
        self._size_edit.setText(attrs.get('size', ''))
        self._color_edit.setText(attrs.get('color', ''))
        self._usage_edit.setText(attrs.get('usage', ''))

        anchors = d.get('visual_anchors', [])
        self._anchor_edit.setPlainText(
            '\n'.join(anchors) if isinstance(anchors, list) else str(anchors or '')
        )

        self._tag_editor = TagEditor(d.get('tags', []))
        self._gallery = ImageGalleryStrip(d.get('reference_images', []))

        self._canvas.build_layout(d)

    def _collect_data(self) -> dict:
        attrs = {
            'material': self._material_edit.text().strip(),
            'size': self._size_edit.text().strip(),
            'color': self._color_edit.text().strip(),
            'usage': self._usage_edit.text().strip(),
        }
        anchors_text = self._anchor_edit.toPlainText().strip()
        anchors = [a.strip() for a in anchors_text.split('\n') if a.strip()]

        return {
            'name': self._name_edit.text().strip() or '未命名道具',
            'description': self._desc_edit.toPlainText().strip(),
            'visual_attributes': attrs,
            'visual_anchors': anchors,
            'tags': self._tag_editor.get_tags(),
            'reference_images': self._gallery.get_images(),
        }

    def _on_node_selected(self, node_type: str, node):
        """画布节点点击/双击处理"""
        if node_type == "angle" and isinstance(node, MultiAngleCard):
            if node._pixmap and not node._pixmap.isNull():
                dlg = ImagePreviewDialog(node._pixmap, self)
                dlg.exec()
            else:
                self._upload_angle_image(node)
        elif node_type == "dblclick_preview":
            if hasattr(node, '_pixmap') and node._pixmap and not node._pixmap.isNull():
                dlg = ImagePreviewDialog(node._pixmap, self)
                dlg.exec()

    def _upload_angle_image(self, card: MultiAngleCard):
        """空卡点击 → 文件选择器上传图片"""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "",
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        src_dir = os.path.dirname(
            self._asset_data.get('main_reference_image', '') or ''
        )
        if not src_dir:
            src_dir = os.path.join('generated', 'angle_uploads')
        os.makedirs(src_dir, exist_ok=True)
        ext = os.path.splitext(path)[1]
        dest = os.path.join(src_dir, f"prop_angle_{card.angle_index}{ext}")
        import shutil
        shutil.copy2(path, dest)
        card.set_pixmap_from_path(dest)
        if self._asset_id:
            angles = list(self._asset_data.get('multi_angle_images', []) or [])
            while len(angles) <= card.angle_index:
                angles.append({})
            angles[card.angle_index] = {
                "angle": PROP_ANGLE_LABELS[card.angle_index],
                "path": dest
            }
            self._asset_data['multi_angle_images'] = angles
            self._controller.update_asset(
                self._asset_id, multi_angle_images=angles
            )

    def start_multi_angle_generation(self):
        """启动5角度批量生成"""
        src = self._asset_data.get('main_reference_image', '')
        if not src or not os.path.isfile(src):
            return

        from config.settings import SettingsManager
        api_cfg = SettingsManager().settings.api
        api_key = api_cfg.runninghub_api_key
        base_url = api_cfg.runninghub_base_url
        if not api_key:
            return

        # 防止同一编辑器重复启动
        if hasattr(self, '_ma_worker') and self._ma_worker and self._ma_worker.isRunning():
            return

        save_dir = os.path.join(os.path.dirname(src), "multi_angle_prop")

        from services.multi_angle_batch_service import (
            MultiAngleBatchWorker, ANGLE_PROMPTS,
        )
        prop_prompts = list(ANGLE_PROMPTS)
        prop_prompts[4] = "<sks> front view eye-level shot close-up"

        worker = MultiAngleBatchWorker(
            src, save_dir, api_key, base_url,
            prompts=prop_prompts,
            labels=PROP_ANGLE_LABELS,
            parent=self,
        )
        self._ma_worker = worker

        cards = self._canvas.get_angle_cards()
        for card in cards:
            card.set_loading(True)

        # 设置按钮加载状态
        gen_btn = self._canvas.get_gen_button()
        if gen_btn:
            gen_btn.set_loading(True)

        def on_angle_done(idx, path):
            if idx < len(cards):
                cards[idx].set_pixmap_from_path(path)

        def on_all_done(success, paths, error):
            self._ma_worker = None
            # 恢复按钮状态
            btn = self._canvas.get_gen_button()
            if btn:
                btn.set_loading(False)
                btn.set_has_all_angles(success and len(paths) >= 5)
            if success and self._asset_id:
                angle_images = [
                    {"angle": PROP_ANGLE_LABELS[i], "path": p}
                    for i, p in enumerate(paths)
                ]
                self._controller.update_asset(
                    self._asset_id, multi_angle_images=angle_images
                )

        worker.angle_completed.connect(on_angle_done)
        worker.all_completed.connect(on_all_done)
        worker.start()
