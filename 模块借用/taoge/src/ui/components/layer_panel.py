"""
涛割 - 图层面板（类 PS 图层列表）
支持：拖放排序、右键菜单（重命名/AI重绘/复制/删除/视角转换/混合模式/合并图层）、
Ctrl+多选、透明度滑块
"""

from typing import Optional, List, Dict, Any, Set

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QLineEdit, QMenu, QSlider,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QSize
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPixmap, QIcon,
    QDrag, QAction,
)

from ui import theme

# 混合模式名称映射（英文 key → 中文显示）
BLEND_MODE_NAMES = {
    'normal': '正常',
    'multiply': '正片叠底',
    'screen': '滤色',
    'overlay': '叠加',
    'darken': '变暗',
    'lighten': '变亮',
    'color_dodge': '颜色减淡',
    'color_burn': '颜色加深',
    'soft_light': '柔光',
    'difference': '差值',
}


class LayerRow(QFrame):
    """单行图层条目"""

    HEIGHT = 48
    DRAG_THRESHOLD = 8  # 拖拽启动阈值（像素）

    # 信号
    clicked = pyqtSignal(int, bool)       # layer_id, ctrl_held
    visibility_toggled = pyqtSignal(int, bool)  # layer_id, visible
    lock_toggled = pyqtSignal(int, bool)        # layer_id, locked
    renamed = pyqtSignal(int, str)              # layer_id, new_name
    context_menu_requested = pyqtSignal(int, object)  # layer_id, QPoint
    opacity_changed = pyqtSignal(int, float)    # layer_id, opacity

    def __init__(self, layer_data: dict, parent=None):
        super().__init__(parent)
        self._data = layer_data
        self._layer_id = layer_data.get('id', 0)
        self._selected = False
        self._editing_name = False
        self._hidden = not layer_data.get('is_visible', True)
        self._drag_start_pos = None  # 拖拽起始位置

        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # 可见性按钮（眼睛图标）
        self._vis_btn = QPushButton("👁")
        self._vis_btn.setFixedSize(24, 24)
        self._vis_btn.setCheckable(True)
        self._vis_btn.setChecked(self._data.get('is_visible', True))
        self._vis_btn.clicked.connect(self._on_visibility_toggled)
        layout.addWidget(self._vis_btn)

        # 缩略图
        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(40, 40)
        self._thumb_label.setScaledContents(True)
        self._load_thumbnail()
        layout.addWidget(self._thumb_label)

        # 名称 + 类型 + 透明度
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        self._name_label = QLabel(self._data.get('name', 'Layer'))
        self._name_label.setFont(QFont("Microsoft YaHei", 9))
        info_layout.addWidget(self._name_label)

        # 类型 + 透明度行
        type_opacity_layout = QHBoxLayout()
        type_opacity_layout.setContentsMargins(0, 0, 0, 0)
        type_opacity_layout.setSpacing(4)

        type_label = QLabel(self._data.get('layer_type', ''))
        type_label.setFont(QFont("Microsoft YaHei", 8))
        type_label.setStyleSheet(f"color: {theme.text_tertiary()};")
        type_opacity_layout.addWidget(type_label)

        type_opacity_layout.addStretch()

        # 透明度滑块（微型）
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setFixedWidth(50)
        self._opacity_slider.setFixedHeight(12)
        self._opacity_slider.setRange(0, 100)
        opacity_val = self._data.get('opacity', 1.0)
        self._opacity_slider.setValue(int(opacity_val * 100))
        self._opacity_slider.setToolTip(f"透明度 {int(opacity_val * 100)}%")
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        type_opacity_layout.addWidget(self._opacity_slider)

        info_layout.addLayout(type_opacity_layout)

        layout.addLayout(info_layout, 1)

        # 颜色标签
        color_label = self._data.get('color_label')
        if color_label:
            color_dot = QLabel()
            color_dot.setFixedSize(12, 12)
            color_dot.setStyleSheet(
                f"background: {color_label}; border-radius: 6px;"
            )
            layout.addWidget(color_dot)

        # 锁定按钮
        self._lock_btn = QPushButton("🔒" if self._data.get('is_locked') else "🔓")
        self._lock_btn.setFixedSize(24, 24)
        self._lock_btn.setCheckable(True)
        self._lock_btn.setChecked(self._data.get('is_locked', False))
        self._lock_btn.clicked.connect(self._on_lock_toggled)
        layout.addWidget(self._lock_btn)

    def _load_thumbnail(self):
        image_path = self._data.get('image_path')
        if image_path:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self._thumb_label.setPixmap(
                    pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
                )
                return
        # 占位
        self._thumb_label.setStyleSheet(
            f"background: {theme.bg_tertiary()}; border-radius: 4px;"
        )

    def set_selected(self, selected: bool):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                f"LayerRow {{ background: {theme.accent()}20; "
                f"border: 1px solid {theme.accent()}; border-radius: 6px; }}"
            )
        elif self._hidden:
            self.setStyleSheet(
                f"LayerRow {{ background: transparent; border: none; border-radius: 6px; opacity: 0.4; }}"
            )
        else:
            self.setStyleSheet(
                f"LayerRow {{ background: transparent; border: none; border-radius: 6px; }}"
                f"LayerRow:hover {{ background: {theme.btn_bg_hover()}; }}"
            )

        # 隐藏图层的缩略图和名称半透明
        opacity_val = 0.35 if self._hidden else 1.0
        self._thumb_label.setStyleSheet(
            self._thumb_label.styleSheet() + f"opacity: {opacity_val};"
            if self._hidden else self._thumb_label.styleSheet()
        )
        self._name_label.setStyleSheet(
            f"color: {theme.text_tertiary()}; text-decoration: line-through;"
            if self._hidden else ""
        )

    def _on_visibility_toggled(self):
        visible = self._vis_btn.isChecked()
        self._hidden = not visible
        self._vis_btn.setText("👁" if visible else "👁‍🗨")
        self._update_style()
        self.visibility_toggled.emit(self._layer_id, visible)

    def _on_lock_toggled(self):
        locked = self._lock_btn.isChecked()
        self._lock_btn.setText("🔒" if locked else "🔓")
        self.lock_toggled.emit(self._layer_id, locked)

    def _on_opacity_changed(self, value: int):
        opacity = value / 100.0
        self._opacity_slider.setToolTip(f"透明度 {value}%")
        self.opacity_changed.emit(self._layer_id, opacity)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self.clicked.emit(self._layer_id, ctrl_held)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_start_pos is not None
                and (event.pos() - self._drag_start_pos).manhattanLength() >= self.DRAG_THRESHOLD):
            # 超过阈值，启动拖拽
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self._layer_id))
            drag.setMimeData(mime)
            # 半透明拖拽缩略图
            pixmap = self.grab()
            pixmap.setDevicePixelRatio(2.0)
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            self._drag_start_pos = None
            drag.exec(Qt.DropAction.MoveAction)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # 双击重命名
        self._start_rename()
        event.accept()

    def contextMenuEvent(self, event):
        self.context_menu_requested.emit(self._layer_id, event.globalPos())
        event.accept()

    def _start_rename(self):
        self._name_label.hide()
        edit = QLineEdit(self._data.get('name', 'Layer'), self)
        edit.setFont(QFont("Microsoft YaHei", 9))
        edit.selectAll()
        edit.setFocus()
        edit.editingFinished.connect(lambda: self._finish_rename(edit))
        # 替换 name_label 位置
        layout = self.layout()
        layout.insertWidget(3, edit)
        self._editing_name = True

    def _finish_rename(self, edit: QLineEdit):
        new_name = edit.text().strip()
        if new_name and new_name != self._data.get('name'):
            self._data['name'] = new_name
            self._name_label.setText(new_name)
            self.renamed.emit(self._layer_id, new_name)

        self._name_label.show()
        edit.deleteLater()
        self._editing_name = False


class LayerPanel(QFrame):
    """图层面板 - 类 PS 图层列表（右侧 dock）"""

    WIDTH = 260

    # 信号
    layer_selected = pyqtSignal(int)
    layer_visibility_changed = pyqtSignal(int, bool)
    layer_locked_changed = pyqtSignal(int, bool)
    layer_order_changed = pyqtSignal(list)         # [layer_id, ...]
    layer_renamed = pyqtSignal(int, str)
    layer_color_changed = pyqtSignal(int, str)
    layer_deleted = pyqtSignal(int)
    ai_redraw_requested = pyqtSignal(int)          # layer_id
    view_angle_requested = pyqtSignal(int)         # layer_id
    matting_requested = pyqtSignal(int)             # layer_id
    blend_mode_changed = pyqtSignal(int, str)      # layer_id, mode
    opacity_changed = pyqtSignal(int, float)       # layer_id, opacity
    merge_layers_requested = pyqtSignal(list)      # [layer_id, ...]
    flip_h_requested = pyqtSignal(int)             # layer_id
    flip_v_requested = pyqtSignal(int)             # layer_id
    layer_copied = pyqtSignal(int)                 # layer_id
    change_expression_requested = pyqtSignal(int)  # layer_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(self.WIDTH)
        self._rows: List[LayerRow] = []
        self._selected_layer_id: Optional[int] = None
        self._selected_layer_ids: Set[int] = set()  # Ctrl+多选
        self._drop_indicator_index: int = -1  # 拖放指示器位置

        self._init_ui()
        self.setAcceptDrops(True)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        header = QFrame()
        header.setFixedHeight(36)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 0, 10, 0)

        title = QLabel("图层")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.DemiBold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        # 新增图层按钮
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("新增图层")
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # 图层列表（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAcceptDrops(True)

        self._list_container = QWidget()
        self._list_container.setAcceptDrops(True)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(6, 6, 6, 6)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

    def set_layers(self, layers: List[dict]):
        """设置图层列表（z_order 降序 = 最上层在最前）"""
        # 清除旧行
        for row in self._rows:
            row.deleteLater()
        self._rows.clear()

        # 按 z_order 降序排列
        sorted_layers = sorted(layers, key=lambda l: l.get('z_order', 0), reverse=True)

        for layer_data in sorted_layers:
            row = self._create_layer_row(layer_data)
            # 在 stretch 之前插入
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

        # 恢复选中状态
        if self._selected_layer_id:
            self.select_layer(self._selected_layer_id)

    def select_layer(self, layer_id: int):
        """外部调用的选中方法 — 仅更新视觉状态，不发射信号（避免信号循环）"""
        self._selected_layer_id = layer_id
        self._selected_layer_ids = {layer_id}
        for row in self._rows:
            row.set_selected(row._layer_id == layer_id)

    def update_layer(self, layer_id: int, data: dict):
        for row in self._rows:
            if row._layer_id == layer_id:
                row._data.update(data)
                if 'name' in data:
                    row._name_label.setText(data['name'])
                row._load_thumbnail()
                break

    def _create_layer_row(self, layer_data: dict) -> LayerRow:
        row = LayerRow(layer_data)
        row.clicked.connect(self._on_row_clicked)
        row.visibility_toggled.connect(self.layer_visibility_changed.emit)
        row.lock_toggled.connect(self.layer_locked_changed.emit)
        row.renamed.connect(self.layer_renamed.emit)
        row.context_menu_requested.connect(self._on_context_menu)
        row.opacity_changed.connect(self.opacity_changed.emit)
        return row

    def _on_row_clicked(self, layer_id: int, ctrl_held: bool = False):
        if ctrl_held:
            # Ctrl+点击：切换多选
            if layer_id in self._selected_layer_ids:
                self._selected_layer_ids.discard(layer_id)
            else:
                self._selected_layer_ids.add(layer_id)
            # 更新视觉
            for row in self._rows:
                row.set_selected(row._layer_id in self._selected_layer_ids)
            # 主选中保持最后点击的
            self._selected_layer_id = layer_id
        else:
            # 普通点击：单选
            self._selected_layer_id = layer_id
            self._selected_layer_ids = {layer_id}
            for row in self._rows:
                row.set_selected(row._layer_id == layer_id)

        self.layer_selected.emit(layer_id)  # 仅用户点击时发射信号

    # === 拖放排序 ===

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasText():
            return
        # 计算鼠标在列表区域中的位置，确定插入索引
        pos = self._list_container.mapFrom(self, event.position().toPoint())
        insert_idx = self._calc_drop_index(pos.y())
        if insert_idx != self._drop_indicator_index:
            self._drop_indicator_index = insert_idx
            self._update_drop_indicator()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drop_indicator_index = -1
        self._clear_drop_indicator()

    def dropEvent(self, event):
        if not event.mimeData().hasText():
            return
        dragged_id = int(event.mimeData().text())
        pos = self._list_container.mapFrom(self, event.position().toPoint())
        insert_idx = self._calc_drop_index(pos.y())

        self._drop_indicator_index = -1
        self._clear_drop_indicator()

        # 找到被拖拽行的当前索引
        src_idx = -1
        for i, row in enumerate(self._rows):
            if row._layer_id == dragged_id:
                src_idx = i
                break
        if src_idx < 0 or insert_idx == src_idx or insert_idx == src_idx + 1:
            event.accept()
            return

        # 从列表中移除并插入到新位置
        row = self._rows.pop(src_idx)
        if insert_idx > src_idx:
            insert_idx -= 1
        self._rows.insert(insert_idx, row)

        # 重建布局顺序
        self._rebuild_layout_order()

        # 发射信号 — 面板从上到下 = z_order 从高到低（最顶层图层在面板最上面）
        # 反转为 z_order 升序列表
        ids_top_to_bottom = [r._layer_id for r in self._rows]
        ids_z_order_asc = list(reversed(ids_top_to_bottom))
        self.layer_order_changed.emit(ids_z_order_asc)

        event.accept()

    def _calc_drop_index(self, local_y: int) -> int:
        """根据鼠标 Y 位置计算插入行索引"""
        margin_top = self._list_layout.contentsMargins().top()
        spacing = self._list_layout.spacing()
        y = margin_top
        for i, row in enumerate(self._rows):
            row_h = row.height() + spacing
            mid = y + row_h / 2
            if local_y < mid:
                return i
            y += row_h
        return len(self._rows)

    def _update_drop_indicator(self):
        """显示蓝色拖放指示线"""
        self._clear_drop_indicator()
        idx = self._drop_indicator_index
        if idx < 0:
            return
        for i, row in enumerate(self._rows):
            if i == idx:
                row.setStyleSheet(
                    row.styleSheet() + f"\nLayerRow {{ border-top: 2px solid {theme.accent()}; }}"
                )
                return
        # 放在末尾 — 最后一行底部
        if self._rows:
            last = self._rows[-1]
            last.setStyleSheet(
                last.styleSheet() + f"\nLayerRow {{ border-bottom: 2px solid {theme.accent()}; }}"
            )

    def _clear_drop_indicator(self):
        """清除拖放指示线"""
        for row in self._rows:
            row._update_style()

    def _rebuild_layout_order(self):
        """根据 _rows 顺序重建 QVBoxLayout"""
        # 移除所有行（不 delete）
        for row in self._rows:
            self._list_layout.removeWidget(row)
        # 按新顺序重新插入（stretch 在末尾）
        for i, row in enumerate(self._rows):
            self._list_layout.insertWidget(i, row)

    def _on_context_menu(self, layer_id: int, pos):
        menu = QMenu(self)

        rename_action = QAction("重命名", self)
        rename_action.triggered.connect(lambda: self._rename_layer(layer_id))
        menu.addAction(rename_action)

        ai_action = QAction("AI 重绘本层", self)
        ai_action.triggered.connect(lambda: self.ai_redraw_requested.emit(layer_id))
        menu.addAction(ai_action)

        # 视角转换
        view_angle_action = QAction("视角转换", self)
        view_angle_action.triggered.connect(
            lambda: self.view_angle_requested.emit(layer_id)
        )
        menu.addAction(view_angle_action)

        # AI 抠图
        matting_action = QAction("AI 抠图", self)
        matting_action.triggered.connect(
            lambda: self.matting_requested.emit(layer_id)
        )
        menu.addAction(matting_action)

        menu.addSeparator()

        # 镜像
        flip_h_action = QAction("左右镜像", self)
        flip_h_action.triggered.connect(
            lambda: self.flip_h_requested.emit(layer_id)
        )
        menu.addAction(flip_h_action)

        flip_v_action = QAction("上下镜像", self)
        flip_v_action.triggered.connect(
            lambda: self.flip_v_requested.emit(layer_id)
        )
        menu.addAction(flip_v_action)

        menu.addSeparator()

        # 混合模式子菜单
        blend_menu = QMenu("混合模式", self)
        for mode_key, mode_name in BLEND_MODE_NAMES.items():
            action = QAction(mode_name, self)
            action.setCheckable(True)
            # 获取当前图层的混合模式
            current_mode = self._get_layer_data(layer_id).get('blend_mode', 'normal')
            action.setChecked(mode_key == current_mode)
            action.triggered.connect(
                lambda checked, m=mode_key: self.blend_mode_changed.emit(layer_id, m)
            )
            blend_menu.addAction(action)
        menu.addMenu(blend_menu)

        menu.addSeparator()

        # 合并选中图层（选中 >= 2 时启用）
        merge_action = QAction("合并选中图层", self)
        selected_ids = list(self._selected_layer_ids)
        merge_action.setEnabled(len(selected_ids) >= 2)
        merge_action.triggered.connect(
            lambda: self.merge_layers_requested.emit(selected_ids)
        )
        menu.addAction(merge_action)

        menu.addSeparator()

        # 改表情动作
        expr_action = QAction("改表情动作", self)
        expr_action.triggered.connect(
            lambda: self.change_expression_requested.emit(layer_id)
        )
        menu.addAction(expr_action)

        menu.addSeparator()

        copy_action = QAction("复制层", self)
        copy_action.triggered.connect(lambda: self._copy_layer(layer_id))
        menu.addAction(copy_action)

        delete_action = QAction("删除层", self)
        delete_action.triggered.connect(lambda: self.layer_deleted.emit(layer_id))
        menu.addAction(delete_action)

        menu.exec(pos)

    def _get_layer_data(self, layer_id: int) -> dict:
        """获取指定图层的数据"""
        for row in self._rows:
            if row._layer_id == layer_id:
                return row._data
        return {}

    def _rename_layer(self, layer_id: int):
        for row in self._rows:
            if row._layer_id == layer_id:
                row._start_rename()
                break

    def _copy_layer(self, layer_id: int):
        # 通过信号通知外部处理复制
        self.layer_copied.emit(layer_id)

    def apply_theme(self):
        self.setStyleSheet(f"""
            LayerPanel {{
                background: {theme.bg_primary()};
                border-left: 1px solid {theme.border()};
            }}
        """)
        for row in self._rows:
            row._update_style()
