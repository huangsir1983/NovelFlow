"""
涛割 - 场景资产编辑器
全屏页面：上半画布（核心形象 + 5张多角度卡）+ 下半信息栏。
"""

import os
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QComboBox, QTextEdit,
    QGraphicsScene, QGraphicsRectItem, QGraphicsPathItem,
    QFormLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import QPainterPath, QPen, QBrush, QColor, QPainter, QFont, QPixmap

from ui import theme
from ui.components.base_canvas_view import BaseCanvasView
from ui.components.asset_editors.base_asset_editor import BaseAssetEditor
from ui.components.asset_editors.character_editor import (
    _ImageCardBase, MultiAngleCard, ANGLE_CARD_SIZE, ANGLE_GAP,
    ANGLE_OFFSET_Y, COLOR_FAN, CORNER_RADIUS,
    _GenerateAngleButton,
)
from ui.components.image_preview_dialog import ImagePreviewDialog
from ui.components.asset_detail_window import TagEditor, ImageGalleryStrip

# 场景用的角度标签（第5张是近距离特写）
SCENE_ANGLE_LABELS = ["正前", "正左", "正右", "正后", "近距离特写"]

CORE_NODE_W, CORE_NODE_H = 220, 300


class _CoreImageNode(_ImageCardBase):
    """核心形象卡 220×300"""

    def __init__(self, parent=None):
        super().__init__(CORE_NODE_W, CORE_NODE_H, parent)


class _SimpleEditorCanvas(BaseCanvasView):
    """简化版编辑器画布：核心形象 + 多角度卡"""

    node_selected = pyqtSignal(str, object)  # "core" | "angle" | "dblclick_preview"
    generate_angle_requested = pyqtSignal()

    def __init__(self, angle_labels: List[str], parent=None):
        super().__init__(parent)
        self._angle_labels = angle_labels
        self._core_node: Optional[_CoreImageNode] = None
        self._angle_cards: List[MultiAngleCard] = []
        self._fan_lines: List[QGraphicsPathItem] = []
        self._gen_button: Optional[_GenerateAngleButton] = None

    def build_layout(self, data: dict):
        scene = self._canvas_scene
        scene.clear()
        self._angle_cards.clear()
        self._fan_lines.clear()
        self._gen_button = None

        # 核心形象
        self._core_node = _CoreImageNode()
        self._core_node.set_label(data.get('name', ''))
        self._core_node.set_image(data.get('main_reference_image', ''))
        self._core_node.setPos(0, 0)
        scene.addItem(self._core_node)

        # "生成多视角"按钮（有主图时显示）
        if data.get('main_reference_image'):
            self._gen_button = _GenerateAngleButton(
                0, lambda _gid: self.generate_angle_requested.emit()
            )
            scene.addItem(self._gen_button)
            # 检查是否已有全部5张多角度
            angles = data.get('multi_angle_images', [])
            has_all = len(angles) >= 5 and all(
                (isinstance(a, dict) and a.get('path') and os.path.isfile(a['path']))
                or (isinstance(a, str) and os.path.isfile(a))
                for a in angles
            )
            self._gen_button.set_has_all_angles(has_all)
            self._position_gen_button()

        # 多角度卡
        angles = data.get('multi_angle_images', [])
        for i, label in enumerate(self._angle_labels):
            card = MultiAngleCard(i, label)
            scene.addItem(card)

            if i < len(angles):
                img = angles[i]
                path = img.get('path', '') if isinstance(img, dict) else img
                if path and os.path.isfile(path):
                    card.set_pixmap_from_path(path)

            self._angle_cards.append(card)

        self._position_cards()
        self._rebuild_lines()
        QTimer.singleShot(100, self.fit_all_in_view)

    def _position_cards(self):
        if not self._core_node:
            return
        total_w = sum(c.rect().width() for c in self._angle_cards) + \
                  max(0, len(self._angle_cards) - 1) * ANGLE_GAP
        core_rect = self._core_node.sceneBoundingRect()
        start_x = core_rect.center().x() - total_w / 2
        y = core_rect.bottom() + ANGLE_OFFSET_Y

        x_cursor = start_x
        for card in self._angle_cards:
            card.setPos(x_cursor, y)
            x_cursor += card.rect().width() + ANGLE_GAP

    def _rebuild_lines(self):
        for line in self._fan_lines:
            if line.scene():
                self._canvas_scene.removeItem(line)
        self._fan_lines.clear()

        if not self._core_node:
            return

        core_rect = self._core_node.sceneBoundingRect()
        start = QPointF(core_rect.center().x(), core_rect.bottom())

        for card in self._angle_cards:
            card_rect = card.sceneBoundingRect()
            end = QPointF(card_rect.center().x(), card_rect.top())
            offset_y = abs(end.y() - start.y()) * 0.5

            path = QPainterPath(start)
            path.cubicTo(
                QPointF(start.x(), start.y() + offset_y),
                QPointF(end.x(), end.y() - offset_y),
                end
            )

            item = QGraphicsPathItem(path)
            pen = QPen(COLOR_FAN, 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            item.setPen(pen)
            item.setZValue(-1)
            self._canvas_scene.addItem(item)
            self._fan_lines.append(item)

    def get_angle_cards(self) -> List[MultiAngleCard]:
        return self._angle_cards

    def get_gen_button(self) -> Optional[_GenerateAngleButton]:
        return self._gen_button

    def refresh_core_image(self, path: str):
        if self._core_node:
            self._core_node.set_image(path)

    def _position_gen_button(self):
        if not self._gen_button or not self._core_node:
            return
        pr = self._core_node.sceneBoundingRect()
        self._gen_button.setPos(
            pr.right() - _GenerateAngleButton.BTN_W - 5,
            pr.top() + 5
        )

    def mousePressEvent(self, event):
        # _GenerateAngleButton 自行处理点击
        item = self.itemAt(event.pos())
        if item:
            target = item
            while target:
                if isinstance(target, _GenerateAngleButton):
                    super().mousePressEvent(event)
                    return
                target = target.parentItem()

        super().mousePressEvent(event)
        if not item:
            return
        target = item
        while target:
            if isinstance(target, _CoreImageNode):
                self.node_selected.emit("core", target)
                return
            elif isinstance(target, MultiAngleCard):
                self.node_selected.emit("angle", target)
                return
            target = target.parentItem()

    def mouseDoubleClickEvent(self, event):
        """双击核心形象卡片弹出大图预览"""
        super().mouseDoubleClickEvent(event)
        item = self.itemAt(event.pos())
        if not item:
            return
        target = item
        while target:
            if isinstance(target, _CoreImageNode):
                self.node_selected.emit("dblclick_preview", target)
                return
            target = target.parentItem()


class SceneEditor(BaseAssetEditor):
    """场景资产全屏编辑器"""

    def __init__(self, asset_data: dict, controller, parent=None):
        super().__init__(asset_data, controller, parent)

    def _create_canvas(self) -> QWidget:
        self._canvas = _SimpleEditorCanvas(SCENE_ANGLE_LABELS)
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

        self._location_edit = QLineEdit()
        self._form.addRow("地点", self._location_edit)

        self._time_edit = QLineEdit()
        self._form.addRow("时间", self._time_edit)

        self._weather_edit = QLineEdit()
        self._form.addRow("天气", self._weather_edit)

        self._mood_edit = QLineEdit()
        self._form.addRow("氛围", self._mood_edit)

        self._era_combo = QComboBox()
        self._era_combo.addItems(["", "古代", "现代", "未来", "架空"])
        self._form.addRow("时代", self._era_combo)

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
        self._location_edit.setText(attrs.get('location', ''))
        self._time_edit.setText(attrs.get('time_of_day', ''))
        self._weather_edit.setText(attrs.get('weather', ''))
        self._mood_edit.setText(attrs.get('mood', ''))

        era = attrs.get('era', d.get('era', ''))
        idx = self._era_combo.findText(era)
        self._era_combo.setCurrentIndex(max(0, idx))

        anchors = d.get('visual_anchors', [])
        self._anchor_edit.setPlainText(
            '\n'.join(anchors) if isinstance(anchors, list) else str(anchors or '')
        )

        self._tag_editor = TagEditor(d.get('tags', []))
        self._gallery = ImageGalleryStrip(d.get('reference_images', []))

        self._canvas.build_layout(d)

    def _collect_data(self) -> dict:
        attrs = {
            'location': self._location_edit.text().strip(),
            'time_of_day': self._time_edit.text().strip(),
            'weather': self._weather_edit.text().strip(),
            'mood': self._mood_edit.text().strip(),
            'era': self._era_combo.currentText(),
        }
        anchors_text = self._anchor_edit.toPlainText().strip()
        anchors = [a.strip() for a in anchors_text.split('\n') if a.strip()]

        return {
            'name': self._name_edit.text().strip() or '未命名场景',
            'description': self._desc_edit.toPlainText().strip(),
            'visual_attributes': attrs,
            'era': attrs['era'],
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
        dest = os.path.join(src_dir, f"scene_angle_{card.angle_index}{ext}")
        import shutil
        shutil.copy2(path, dest)
        card.set_pixmap_from_path(dest)
        if self._asset_id:
            angles = list(self._asset_data.get('multi_angle_images', []) or [])
            while len(angles) <= card.angle_index:
                angles.append({})
            angles[card.angle_index] = {
                "angle": SCENE_ANGLE_LABELS[card.angle_index],
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

        save_dir = os.path.join(os.path.dirname(src), "multi_angle_scene")

        from services.multi_angle_batch_service import (
            MultiAngleBatchWorker, ANGLE_PROMPTS,
        )
        # 场景第5张改为近距离特写
        scene_prompts = list(ANGLE_PROMPTS)
        scene_prompts[4] = "<sks> front view eye-level shot close-up"

        worker = MultiAngleBatchWorker(
            src, save_dir, api_key, base_url,
            prompts=scene_prompts,
            labels=SCENE_ANGLE_LABELS,
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
                    {"angle": SCENE_ANGLE_LABELS[i], "path": p}
                    for i, p in enumerate(paths)
                ]
                self._controller.update_asset(
                    self._asset_id, multi_angle_images=angle_images
                )

        worker.angle_completed.connect(on_angle_done)
        worker.all_completed.connect(on_all_done)
        worker.start()
