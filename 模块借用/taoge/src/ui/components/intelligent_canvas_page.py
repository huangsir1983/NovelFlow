"""
涛割 - 智能画布全屏页面容器
替代 SceneWorkCanvas 的顶层包装
"""

from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabBar, QStackedWidget,
    QFrame, QLabel, QProgressBar, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from ui import theme
from ui.components.intelligent_canvas import IntelligentCanvasView
from ui.components.layer_panel import LayerPanel
from ui.components.canvas_toolbar import CanvasToolbar


class IntelligentCanvasPage(QWidget):
    """智能画布全屏页面（替代 SceneWorkCanvas 的顶层包装）"""

    back_requested = pyqtSignal()
    scene_saved = pyqtSignal(int)  # scene_id

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self._data_hub = data_hub
        self._current_scene_id: Optional[int] = None
        self._tabs: Dict[int, int] = {}  # scene_id → tab_index

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 工具栏 (44px) ===
        self._toolbar = CanvasToolbar()
        main_layout.addWidget(self._toolbar)

        # === 多标签页 ===
        self._tab_bar = QTabBar()
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.setVisible(False)
        main_layout.addWidget(self._tab_bar)

        # === 内容区 ===
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 画布（QStackedWidget 支持多标签）
        self._canvas_stack = QStackedWidget()
        content_layout.addWidget(self._canvas_stack, 1)

        # 图层面板 (260px)
        self._layer_panel = LayerPanel()
        content_layout.addWidget(self._layer_panel)

        main_layout.addLayout(content_layout, 1)

        # === 抠图进度条（浮动在 canvas_stack 底部居中）===
        self._matting_progress_frame = QFrame(self._canvas_stack)
        self._matting_progress_frame.setFixedSize(360, 56)
        self._matting_progress_frame.setStyleSheet(
            "QFrame { background: rgba(30,30,40,0.92); border-radius: 10px; }"
        )
        self._matting_progress_frame.setVisible(False)

        pf_layout = QVBoxLayout(self._matting_progress_frame)
        pf_layout.setContentsMargins(14, 8, 14, 8)
        pf_layout.setSpacing(4)

        self._matting_progress_label = QLabel("准备中...")
        self._matting_progress_label.setFont(QFont("Microsoft YaHei", 9))
        self._matting_progress_label.setStyleSheet("color: #ddd; background: transparent;")
        pf_layout.addWidget(self._matting_progress_label)

        self._matting_progress_bar = QProgressBar()
        self._matting_progress_bar.setRange(0, 100)
        self._matting_progress_bar.setValue(0)
        self._matting_progress_bar.setFixedHeight(14)
        self._matting_progress_bar.setTextVisible(False)
        self._matting_progress_bar.setStyleSheet(
            "QProgressBar { background: #444; border-radius: 7px; }"
            "QProgressBar::chunk { background: #5b7fff; border-radius: 7px; }"
        )
        pf_layout.addWidget(self._matting_progress_bar)

    def _connect_signals(self):
        # 工具栏信号
        self._toolbar.back_clicked.connect(self._on_back)
        self._toolbar.save_clicked.connect(self._on_save)
        self._toolbar.ai_auto_layer.connect(self._on_ai_auto_layer)
        self._toolbar.tool_changed.connect(self._on_tool_changed)
        self._toolbar.flip_h_clicked.connect(self._on_flip_h)
        self._toolbar.flip_v_clicked.connect(self._on_flip_v)
        self._toolbar.add_material_clicked.connect(self._on_add_material)
        self._toolbar.onion_toggled.connect(self._on_onion_toggled)
        self._toolbar.onion_opacity_changed.connect(self._on_onion_opacity)
        self._toolbar.continuity_toggled.connect(self._on_continuity_toggled)
        self._toolbar.inherit_prev_clicked.connect(self._on_inherit_prev)
        self._toolbar.brush_color_changed.connect(self._on_brush_color_changed)
        self._toolbar.brush_size_changed.connect(self._on_brush_size_changed)
        self._toolbar.merge_clicked.connect(self._on_merge_from_toolbar)

        # 图层面板信号
        self._layer_panel.layer_selected.connect(self._on_panel_layer_selected)
        self._layer_panel.layer_visibility_changed.connect(self._on_layer_visibility)
        self._layer_panel.layer_locked_changed.connect(self._on_layer_locked)
        self._layer_panel.layer_deleted.connect(self._on_layer_deleted)
        self._layer_panel.layer_order_changed.connect(self._on_layer_order_changed)
        self._layer_panel.ai_redraw_requested.connect(self._on_ai_redraw)
        self._layer_panel.view_angle_requested.connect(self._on_view_angle_requested)
        self._layer_panel.matting_requested.connect(self._on_matting_requested)
        self._layer_panel.blend_mode_changed.connect(self._on_blend_mode_changed)
        self._layer_panel.opacity_changed.connect(self._on_opacity_changed)
        self._layer_panel.merge_layers_requested.connect(self._on_merge_layers)
        self._layer_panel.flip_h_requested.connect(self._on_layer_flip_h)
        self._layer_panel.flip_v_requested.connect(self._on_layer_flip_v)
        self._layer_panel.layer_copied.connect(self._on_layer_copied)
        self._layer_panel.change_expression_requested.connect(self._on_change_expression)

    def _current_canvas(self) -> Optional[IntelligentCanvasView]:
        widget = self._canvas_stack.currentWidget()
        if isinstance(widget, IntelligentCanvasView):
            return widget
        return None

    # === 外部接口 ===

    def load_scene(self, scene_id: int):
        """加载场景到智能画布"""
        if scene_id in self._tabs:
            # 已有标签页，切换
            self._tab_bar.setCurrentIndex(self._tabs[scene_id])
            return

        # 新建画布
        canvas = IntelligentCanvasView(data_hub=self._data_hub)
        canvas.layer_selected.connect(self._on_canvas_layer_selected)
        canvas.layer_transform_changed.connect(self._on_layer_transform)
        canvas.canvas_saved.connect(self.scene_saved.emit)
        canvas.layer_context_menu_requested.connect(self._on_canvas_context_menu)
        canvas.multi_selection_changed.connect(self._on_canvas_multi_selection)

        idx = self._canvas_stack.addWidget(canvas)
        self._canvas_stack.setCurrentIndex(idx)

        # 标签页
        tab_idx = self._tab_bar.addTab(f"场景 #{scene_id}")
        self._tabs[scene_id] = tab_idx
        self._tab_bar.setCurrentIndex(tab_idx)
        self._tab_bar.setVisible(self._tab_bar.count() > 1)

        self._current_scene_id = scene_id
        canvas.load_scene(scene_id)

        # 更新工具栏和图层面板
        self._toolbar.set_scene_info(scene_id - 1)  # 0-indexed display
        self._refresh_layer_panel()

    def save_and_close(self):
        """保存当前场景并关闭"""
        canvas = self._current_canvas()
        if canvas:
            canvas.save_scene()
        self.back_requested.emit()

    def open_scene_tab(self, scene_id: int):
        """新增标签页或切换到已有"""
        self.load_scene(scene_id)

    def close_scene_tab(self, scene_id: int):
        if scene_id in self._tabs:
            tab_idx = self._tabs.pop(scene_id)
            widget = self._canvas_stack.widget(tab_idx)
            if widget:
                self._canvas_stack.removeWidget(widget)
                widget.deleteLater()
            self._tab_bar.removeTab(tab_idx)
            # 更新索引映射
            self._tabs = {
                sid: (i if i < tab_idx else i - 1)
                for sid, i in self._tabs.items()
            }
            self._tab_bar.setVisible(self._tab_bar.count() > 1)

    # === 内部方法 ===

    def _on_back(self):
        canvas = self._current_canvas()
        if canvas:
            canvas.save_scene()
        self.back_requested.emit()

    def _on_save(self):
        canvas = self._current_canvas()
        if canvas:
            canvas.save_scene()

    def _on_ai_auto_layer(self):
        canvas = self._current_canvas()
        if canvas:
            canvas.ai_auto_layer()

    def _on_tool_changed(self, tool: str):
        canvas = self._current_canvas()
        if canvas and hasattr(canvas, 'set_tool'):
            canvas.set_tool(tool)

    def _on_flip_h(self):
        canvas = self._current_canvas()
        if canvas and canvas._selected_layer_id:
            item = canvas._layer_items.get(canvas._selected_layer_id)
            if item:
                t = item.get_transform()
                item.set_flip_h(not t.get('flip_h', False))

    def _on_flip_v(self):
        canvas = self._current_canvas()
        if canvas and canvas._selected_layer_id:
            item = canvas._layer_items.get(canvas._selected_layer_id)
            if item:
                t = item.get_transform()
                item.set_flip_v(not t.get('flip_v', False))

    def _on_layer_flip_h(self, layer_id: int):
        """图层面板右键菜单 — 左右镜像"""
        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                t = item.get_transform()
                item.set_flip_h(not t.get('flip_h', False))

    def _on_layer_flip_v(self, layer_id: int):
        """图层面板右键菜单 — 上下镜像"""
        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                t = item.get_transform()
                item.set_flip_v(not t.get('flip_v', False))

    def _on_onion_toggled(self, enabled: bool):
        canvas = self._current_canvas()
        if canvas and self._current_scene_id:
            if enabled:
                # 查找上一个场景
                from database.session import session_scope
                from database.models import Scene
                with session_scope() as session:
                    current = session.query(Scene).filter(
                        Scene.id == self._current_scene_id
                    ).first()
                    if current:
                        prev = session.query(Scene).filter(
                            Scene.project_id == current.project_id,
                            Scene.scene_index == current.scene_index - 1
                        ).first()
                        if prev:
                            canvas.load_onion_skin(prev.id)
            else:
                # 移除洋葱皮
                if canvas._onion_item and canvas._onion_item.scene():
                    canvas._canvas_scene.removeItem(canvas._onion_item)
                    canvas._onion_item = None

    def _on_onion_opacity(self, value: int):
        canvas = self._current_canvas()
        if canvas:
            canvas.set_onion_opacity(float(value))

    def _on_continuity_toggled(self, enabled: bool):
        canvas = self._current_canvas()
        if canvas:
            canvas.toggle_continuity_tools(enabled)

    def _on_inherit_prev(self):
        """继承上一镜尾帧作为起始帧"""
        if not self._current_scene_id:
            return
        from services.controllers.generation_controller import GenerationController
        ctrl = GenerationController()
        from database.session import session_scope
        from database.models import Scene
        with session_scope() as session:
            scene = session.query(Scene).filter(
                Scene.id == self._current_scene_id
            ).first()
            if scene:
                scene.use_prev_end_frame = True

    def _on_brush_color_changed(self, color):
        canvas = self._current_canvas()
        if canvas:
            canvas.set_brush_color(color)

    def _on_brush_size_changed(self, size: int):
        canvas = self._current_canvas()
        if canvas:
            canvas.set_brush_size(size)

    def _on_panel_layer_selected(self, layer_id: int):
        """图层面板点击 → 同步画布选中（支持多选）"""
        canvas = self._current_canvas()
        if not canvas:
            return
        # 读取面板当前的多选集，同步到画布
        panel_ids = self._layer_panel._selected_layer_ids
        if len(panel_ids) > 1:
            # 多选：先取消画布所有选中，再逐个设选中
            for lid in list(canvas._selected_layer_ids):
                if lid in canvas._layer_items:
                    canvas._layer_items[lid].set_layer_selected(False)
            canvas._selected_layer_ids = set(panel_ids)
            canvas._selected_layer_id = layer_id
            for lid in panel_ids:
                if lid in canvas._layer_items:
                    canvas._layer_items[lid].set_layer_selected(True)
            canvas.multi_selection_changed.emit(list(panel_ids))
        else:
            canvas.select_layer(layer_id)

    def _on_canvas_layer_selected(self, layer_id: int):
        self._layer_panel.select_layer(layer_id)

    def _on_canvas_multi_selection(self, layer_ids: list):
        """画布多选状态变化 → 同步图层面板 + 合并按钮可见性"""
        # 同步图层面板的多选高亮
        id_set = set(layer_ids)
        self._layer_panel._selected_layer_ids = id_set
        for row in self._layer_panel._rows:
            row.set_selected(row._layer_id in id_set)
        # 合并按钮：>=2 个图层时显示
        self._toolbar.set_merge_visible(len(layer_ids) >= 2)

    def _on_merge_from_toolbar(self):
        """工具栏合并按钮 → 获取画布多选列表 → 合并"""
        canvas = self._current_canvas()
        if canvas:
            layer_ids = canvas.get_selected_layer_ids()
            if len(layer_ids) >= 2:
                self._on_merge_layers(layer_ids)

    def _on_canvas_context_menu(self, layer_id: int, pos):
        """画布上右键图层 — 复用图层面板的菜单逻辑"""
        self._layer_panel._on_context_menu(layer_id, pos)

    def _on_layer_transform(self, layer_id: int, transform: dict):
        # 实时保存变换到 DB
        from services.layer_service import LayerService
        service = LayerService()
        service.save_layer({'id': layer_id, 'transform': transform})

    def _on_layer_visibility(self, layer_id: int, visible: bool):
        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                item.setVisible(visible)
        from services.layer_service import LayerService
        LayerService().save_layer({'id': layer_id, 'is_visible': visible})

    def _on_layer_locked(self, layer_id: int, locked: bool):
        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                item.is_locked = locked
                item.setFlag(
                    item.GraphicsItemFlag.ItemIsMovable, not locked
                )
        from services.layer_service import LayerService
        LayerService().save_layer({'id': layer_id, 'is_locked': locked})

    def _on_layer_deleted(self, layer_id: int):
        canvas = self._current_canvas()
        if canvas:
            canvas.remove_layer(layer_id)
        from services.layer_service import LayerService
        LayerService().delete_layer(layer_id)
        self._refresh_layer_panel()

    def _on_layer_order_changed(self, layer_ids: list):
        """图层顺序变化（z_order 升序列表）"""
        canvas = self._current_canvas()
        if canvas:
            canvas.reorder_layers(layer_ids)
        from services.layer_service import LayerService
        LayerService().reorder_layers(layer_ids)

    def _on_ai_redraw(self, layer_id: int):
        canvas = self._current_canvas()
        if canvas:
            canvas.ai_redraw_layer(layer_id, "")  # TODO: 弹出 prompt 输入

    def _on_view_angle_requested(self, layer_id: int):
        """视角转换 — 打开对话框"""
        if not self._current_scene_id:
            return

        # 获取图层原始图路径
        from services.layer_service import LayerService
        layers = LayerService().get_scene_layers(self._current_scene_id)
        layer_data = None
        for l in layers:
            if l.get('id') == layer_id:
                layer_data = l
                break
        if not layer_data:
            return

        # 优先使用 original_image_path，其次 image_path
        original_path = layer_data.get('original_image_path') or layer_data.get('image_path', '')
        if not original_path:
            return

        from ui.components.view_angle_dialog import ViewAngleDialog
        dialog = ViewAngleDialog(
            layer_id=layer_id,
            original_image_path=original_path,
            scene_id=self._current_scene_id,
            parent=self,
        )
        dialog.convert_completed.connect(
            lambda path: self._on_angle_convert_done(layer_id, path)
        )
        # 保持引用防止 GC
        self._view_angle_dialog = dialog
        dialog.show()

    def _on_angle_convert_done(self, layer_id: int, new_image_path: str):
        """视角转换完成 — 更新图层图片"""
        import os
        if not new_image_path or not os.path.isfile(new_image_path):
            return

        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                from PyQt6.QtGui import QPixmap
                pm = QPixmap(new_image_path)
                if not pm.isNull():
                    item.update_pixmap(pm)
                    # 强制刷新画布视图
                    item.update()
                    if canvas._canvas_scene:
                        canvas._canvas_scene.update()

        # 更新 DB（image_path 更新，original_image_path 不动）
        from services.layer_service import LayerService
        import time
        service = LayerService()
        service.save_layer({
            'id': layer_id,
            'image_path': new_image_path,
            'prompt_history': [{
                'action': 'view_angle_convert',
                'output_path': new_image_path,
                'timestamp': time.time(),
            }],
        })
        self._refresh_layer_panel()

    def _on_blend_mode_changed(self, layer_id: int, mode: str):
        """混合模式变化"""
        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                item.blend_mode = mode

        from services.layer_service import LayerService
        LayerService().save_layer({'id': layer_id, 'blend_mode': mode})

    def _on_opacity_changed(self, layer_id: int, opacity: float):
        """透明度变化"""
        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                item.layer_opacity = opacity

        from services.layer_service import LayerService
        LayerService().save_layer({'id': layer_id, 'opacity': opacity})

    def _on_merge_layers(self, layer_ids: list):
        """合并选中图层 — 新建图层，保留原图层不变，完整保留位置/大小/旋转/翻转"""
        if len(layer_ids) < 2 or not self._current_scene_id:
            return

        canvas = self._current_canvas()
        if not canvas:
            return

        # 获取画框尺寸作为合成画布
        frame_rect = canvas._canvas_frame.rect()
        w = int(frame_rect.width())
        h = int(frame_rect.height())
        if w <= 0 or h <= 0:
            return

        from PyQt6.QtGui import QImage, QPixmap, QPainter

        # 收集选中的可见图层，按 z_order 排序（底层先画）
        items = []
        for lid in layer_ids:
            item = canvas._layer_items.get(lid)
            if item and item.isVisible():
                pm = item.pixmap()
                if pm and not pm.isNull():
                    items.append(item)
        if not items:
            return
        items.sort(key=lambda it: it.zValue())

        # 创建透明画布
        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        for item in items:
            painter.save()
            painter.setOpacity(item.opacity())

            # 混合模式
            from ui.components.layer_item import LayerItem
            mode = LayerItem.BLEND_MODES.get(
                item.blend_mode,
                QPainter.CompositionMode.CompositionMode_SourceOver,
            )
            painter.setCompositionMode(mode)

            # 获取图层到画框的完整变换（包含位置/旋转/缩放/翻转）
            transform_to_frame, ok = item.itemTransform(canvas._canvas_frame)
            if ok:
                painter.setTransform(transform_to_frame)

            painter.drawPixmap(0, 0, item.pixmap())
            painter.restore()

        painter.end()

        # 保存合成图片
        import os
        import time
        output_dir = os.path.join('generated', 'merged')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(
            output_dir, f"merged_{self._current_scene_id}_{int(time.time())}.png"
        )
        image.save(output_path, "PNG")

        # 新建合并图层（不删除原图层），z_order 放到最顶层
        from services.layer_service import LayerService
        service = LayerService()
        all_layers = service.get_scene_layers(self._current_scene_id)
        max_z = max((l.get('z_order', 0) for l in all_layers), default=0)

        merged_data = {
            'scene_id': self._current_scene_id,
            'name': '合并图层',
            'layer_type': 'merged',
            'z_order': max_z + 1,
            'is_visible': True,
            'is_locked': False,
            'image_path': output_path,
            'original_image_path': output_path,
        }
        new_id = service.save_layer(merged_data)
        merged_data['id'] = new_id

        canvas.add_layer(merged_data)
        self._refresh_layer_panel()

    def _on_tab_close(self, index: int):
        scene_id = None
        for sid, idx in self._tabs.items():
            if idx == index:
                scene_id = sid
                break
        if scene_id:
            self.close_scene_tab(scene_id)

    def _on_tab_changed(self, index: int):
        for sid, idx in self._tabs.items():
            if idx == index:
                self._current_scene_id = sid
                self._canvas_stack.setCurrentIndex(index)
                self._toolbar.set_scene_info(sid - 1)
                self._refresh_layer_panel()
                break

    def _refresh_layer_panel(self):
        """刷新图层面板"""
        if not self._current_scene_id:
            return
        from services.layer_service import LayerService
        layers = LayerService().get_scene_layers(self._current_scene_id)
        self._layer_panel.set_layers(layers)

    def apply_theme(self):
        self._toolbar.apply_theme()
        self._layer_panel.apply_theme()
        self.setStyleSheet(f"background: {theme.bg_primary()};")

    # === 抠图功能 ===

    def _on_matting_requested(self, layer_id: int):
        """AI 抠图 — 获取图层当前图片（修改后的）→ 启动 MattingWorker"""
        if not self._current_scene_id:
            return

        # 获取图层当前图路径（优先 image_path，即修改后的图）
        from services.layer_service import LayerService
        layers = LayerService().get_scene_layers(self._current_scene_id)
        layer_data = None
        for l in layers:
            if l.get('id') == layer_id:
                layer_data = l
                break
        if not layer_data:
            return

        current_path = layer_data.get('image_path') or layer_data.get('original_image_path', '')
        if not current_path:
            return

        import os
        if not os.path.isfile(current_path):
            return

        # 读取 RunningHub 配置
        from config.settings import SettingsManager
        api_cfg = SettingsManager().settings.api
        api_key = api_cfg.runninghub_api_key
        base_url = api_cfg.runninghub_base_url
        instance_type = api_cfg.runninghub_instance_type

        if not api_key:
            self._matting_progress_label.setText("错误：RunningHub API Key 未配置")
            self._matting_progress_frame.setVisible(True)
            self._position_matting_progress()
            return

        save_dir = os.path.join('generated', 'matting')

        from services.matting_service import MattingWorker
        worker = MattingWorker(
            source_image_path=current_path,
            save_dir=save_dir,
            api_key=api_key,
            base_url=base_url,
            instance_type=instance_type,
            parent=self,
        )
        worker.progress.connect(self._on_matting_progress)
        worker.completed.connect(
            lambda ok, path, err: self._on_matting_completed(layer_id, ok, path, err)
        )

        # 显示进度条
        self._matting_progress_bar.setValue(0)
        self._matting_progress_label.setText("准备中...")
        self._matting_progress_frame.setVisible(True)
        self._position_matting_progress()

        # 保持引用防止 GC
        self._matting_worker = worker
        worker.start()

    def _on_matting_progress(self, msg: str, pct: int):
        """更新抠图进度"""
        self._matting_progress_label.setText(msg)
        self._matting_progress_bar.setValue(pct)

    def _on_matting_completed(self, layer_id: int, success: bool,
                              local_path: str, error: str):
        """抠图完成回调"""
        if success:
            import os
            if local_path and os.path.isfile(local_path):
                # 更新画布 pixmap
                canvas = self._current_canvas()
                if canvas:
                    item = canvas._layer_items.get(layer_id)
                    if item:
                        from PyQt6.QtGui import QPixmap
                        pm = QPixmap(local_path)
                        if not pm.isNull():
                            item.update_pixmap(pm)
                            item.update()
                            if canvas._canvas_scene:
                                canvas._canvas_scene.update()

                # 更新 DB
                import time
                from services.layer_service import LayerService
                LayerService().save_layer({
                    'id': layer_id,
                    'image_path': local_path,
                    'prompt_history': [{
                        'action': 'matting',
                        'output_path': local_path,
                        'timestamp': time.time(),
                    }],
                })
                self._refresh_layer_panel()

            self._matting_progress_label.setText("抠图完成！")
            self._matting_progress_bar.setValue(100)
        else:
            self._matting_progress_label.setText(f"抠图失败: {error[:60]}")

        # 2 秒后隐藏进度条
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, self._hide_matting_progress)

    def _hide_matting_progress(self):
        self._matting_progress_frame.setVisible(False)

    def _position_matting_progress(self):
        """将抠图进度条定位到 canvas_stack 底部居中"""
        pw = self._matting_progress_frame.width()
        ph = self._matting_progress_frame.height()
        cw = self._canvas_stack.width()
        ch = self._canvas_stack.height()
        x = (cw - pw) // 2
        y = ch - ph - 16
        self._matting_progress_frame.move(x, y)
        self._matting_progress_frame.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_matting_progress_frame') and self._matting_progress_frame.isVisible():
            self._position_matting_progress()
        if hasattr(self, '_expression_panel') and self._expression_panel.isVisible():
            self._position_expression_panel()

    # === 复制图层 ===

    def _on_layer_copied(self, layer_id: int):
        """复制图层 — 复制图片文件 + 创建新图层记录"""
        import os
        import shutil
        import time

        if not self._current_scene_id:
            return

        from services.layer_service import LayerService
        service = LayerService()
        layers = service.get_scene_layers(self._current_scene_id)

        # 找到源图层数据
        src_data = None
        for l in layers:
            if l.get('id') == layer_id:
                src_data = l
                break
        if not src_data:
            return

        # 复制图片文件
        src_image = src_data.get('image_path', '')
        new_image_path = ''
        if src_image and os.path.isfile(src_image):
            base, ext = os.path.splitext(src_image)
            new_image_path = f"{base}_copy_{int(time.time())}{ext}"
            shutil.copy2(src_image, new_image_path)

        # 创建新图层
        max_z = max((l.get('z_order', 0) for l in layers), default=0)
        copy_data = {
            'scene_id': self._current_scene_id,
            'name': (src_data.get('name', 'Layer') + ' 副本'),
            'layer_type': src_data.get('layer_type', 'background'),
            'z_order': max_z + 1,
            'is_visible': True,
            'is_locked': False,
            'image_path': new_image_path or src_image,
            'original_image_path': src_data.get('original_image_path', ''),
            'blend_mode': src_data.get('blend_mode', 'normal'),
            'opacity': src_data.get('opacity', 1.0),
            'transform': dict(src_data.get('transform', {})),
        }
        new_id = service.save_layer(copy_data)
        copy_data['id'] = new_id

        canvas = self._current_canvas()
        if canvas:
            canvas.add_layer(copy_data)

        self._refresh_layer_panel()

    # === 添加素材 ===

    def _on_add_material(self):
        """工具栏"添加素材"按钮 → 文件选择 → 添加为新图层"""
        import os
        from PyQt6.QtWidgets import QFileDialog

        if not self._current_scene_id:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择素材图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*)"
        )
        if not file_path or not os.path.isfile(file_path):
            return

        from services.layer_service import LayerService
        service = LayerService()
        layers = service.get_scene_layers(self._current_scene_id)
        max_z = max((l.get('z_order', 0) for l in layers), default=0)

        layer_data = {
            'scene_id': self._current_scene_id,
            'name': os.path.splitext(os.path.basename(file_path))[0],
            'layer_type': 'prop',
            'z_order': max_z + 1,
            'is_visible': True,
            'is_locked': False,
            'image_path': file_path,
            'original_image_path': file_path,
        }
        new_id = service.save_layer(layer_data)
        layer_data['id'] = new_id

        canvas = self._current_canvas()
        if canvas:
            canvas.add_layer(layer_data)

        self._refresh_layer_panel()

    # === 改表情动作 ===

    def _on_change_expression(self, layer_id: int):
        """右键菜单"改表情动作" → 显示浮动面板"""
        if not self._current_scene_id:
            return

        # 获取图层当前图路径（优先 image_path，即编辑后的图）
        from services.layer_service import LayerService
        layers = LayerService().get_scene_layers(self._current_scene_id)
        layer_data = None
        for l in layers:
            if l.get('id') == layer_id:
                layer_data = l
                break
        if not layer_data:
            return

        current_path = layer_data.get('image_path') or layer_data.get('original_image_path', '')
        if not current_path:
            return

        import os
        if not os.path.isfile(current_path):
            return

        # 选中图层高亮
        canvas = self._current_canvas()
        if canvas:
            canvas.select_layer(layer_id)
        self._layer_panel.select_layer(layer_id)

        # 显示浮动面板
        self._show_expression_panel(layer_id, current_path)

    def _show_expression_panel(self, layer_id: int, image_path: str):
        """显示改表情动作的浮动面板"""
        from PyQt6.QtWidgets import QLineEdit

        if not hasattr(self, '_expression_panel') or self._expression_panel is None:
            self._expression_panel = QFrame(self._canvas_stack)
            self._expression_panel.setFixedSize(520, 56)
            self._expression_panel.setStyleSheet(
                "QFrame { background: rgba(30,30,40,0.95); border-radius: 10px; }"
            )

            ep_layout = QHBoxLayout(self._expression_panel)
            ep_layout.setContentsMargins(12, 8, 12, 8)
            ep_layout.setSpacing(8)

            self._expr_input = QLineEdit()
            self._expr_input.setPlaceholderText("描述表情/动作变化...")
            self._expr_input.setText("保持人物一致性，保持视角一致，")
            self._expr_input.setStyleSheet(
                "QLineEdit { background: #333; color: #eee; border: 1px solid #555; "
                "border-radius: 6px; padding: 4px 8px; font-size: 13px; }"
            )
            ep_layout.addWidget(self._expr_input, 1)

            from PyQt6.QtGui import QFont as _QFont

            self._expr_gen_btn = QPushButton("生成")
            self._expr_gen_btn.setFixedSize(60, 32)
            self._expr_gen_btn.setFont(_QFont("Microsoft YaHei", 9))
            self._expr_gen_btn.setStyleSheet(
                "QPushButton { background: #5b7fff; color: white; border-radius: 6px; }"
                "QPushButton:hover { background: #4a6eee; }"
            )
            self._expr_gen_btn.clicked.connect(self._on_expression_generate)
            ep_layout.addWidget(self._expr_gen_btn)

            # 生成中状态标签（初始隐藏）
            self._expr_status_label = QLabel("")
            self._expr_status_label.setFixedHeight(32)
            self._expr_status_label.setStyleSheet(
                "QLabel { color: #aaa; background: transparent; font-size: 12px; }"
            )
            self._expr_status_label.setVisible(False)
            ep_layout.addWidget(self._expr_status_label)

            cancel_btn = QPushButton("取消")
            cancel_btn.setFixedSize(48, 32)
            cancel_btn.setFont(_QFont("Microsoft YaHei", 9))
            cancel_btn.setStyleSheet(
                "QPushButton { background: #555; color: #ccc; border-radius: 6px; }"
                "QPushButton:hover { background: #666; }"
            )
            cancel_btn.clicked.connect(self._hide_expression_panel)
            ep_layout.addWidget(cancel_btn)

        # 重置状态
        self._expr_target_layer_id = layer_id
        self._expr_source_image = image_path
        self._expr_result_path = None
        self._expr_input.setText("保持人物一致性，保持视角一致，")
        self._expr_input.setEnabled(True)
        self._expr_gen_btn.setVisible(True)
        self._expr_gen_btn.setEnabled(True)
        self._expr_status_label.setVisible(False)
        self._expression_panel.setVisible(True)
        self._position_expression_panel()
        self._expression_panel.raise_()
        self._expr_input.setFocus()

    def _position_expression_panel(self):
        """定位改表情浮动面板到画布底部居中"""
        if not hasattr(self, '_expression_panel'):
            return
        pw = self._expression_panel.width()
        ph = self._expression_panel.height()
        cw = self._canvas_stack.width()
        ch = self._canvas_stack.height()
        x = (cw - pw) // 2
        y = ch - ph - 16
        self._expression_panel.move(x, y)

    def _hide_expression_panel(self):
        if hasattr(self, '_expression_panel') and self._expression_panel:
            self._expression_panel.setVisible(False)

    def _on_expression_generate(self):
        """发送编辑后的图片+提示词到 Gemini API"""
        if not hasattr(self, '_expr_source_image'):
            return

        prompt = self._expr_input.text().strip()
        if not prompt:
            return

        # 切换到"生成中"状态
        self._expr_input.setEnabled(False)
        self._expr_gen_btn.setVisible(False)
        self._expr_status_label.setText("生成中...")
        self._expr_status_label.setVisible(True)

        # 启动转圈动画
        self._expr_spinner_angle = 0
        self._expr_spinner_timer = QTimer(self)
        self._expr_spinner_timer.setInterval(150)
        self._expr_spinner_timer.timeout.connect(self._tick_expression_spinner)
        self._expr_spinner_timer.start()

        from PyQt6.QtCore import QThread, pyqtSignal as _pyqtSignal

        class _ExpressionWorker(QThread):
            finished = _pyqtSignal(bool, str, str)  # success, path, error

            def __init__(self, prompt: str, image_path: str):
                super().__init__()
                self._prompt = prompt
                self._image_path = image_path

            def run(self):
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._do_generate())
                    loop.close()
                except Exception as e:
                    self.finished.emit(False, "", str(e))

            async def _do_generate(self):
                from config.settings import SettingsManager
                settings = SettingsManager().settings

                channel = settings.api.image_provider or "geek"
                if channel == "geek":
                    from services.generation.closed_source.geek_provider import GeekProvider
                    provider = GeekProvider(
                        api_key=settings.api.geek_api_key,
                        base_url=settings.api.geek_base_url,
                    )
                else:
                    from services.generation.closed_source.yunwu_provider import YunwuProvider
                    provider = YunwuProvider(
                        api_key=settings.api.yunwu_api_key,
                        base_url=settings.api.yunwu_base_url,
                    )

                from services.generation.base_provider import ImageGenerationRequest
                request = ImageGenerationRequest(
                    prompt=self._prompt,
                    num_images=1,
                    reference_images=[self._image_path],
                    model_params={
                        'model': 'gemini-3-pro-image-preview',
                        'aspect_ratio': '1:1',
                    },
                )

                result = await provider.generate_image(request)
                await provider.close()

                if result.success:
                    path = result.result_path or result.result_url or ""
                    self.finished.emit(True, path, "")
                else:
                    self.finished.emit(False, "", result.error_message or "生成失败")

        worker = _ExpressionWorker(prompt, self._expr_source_image)
        worker.finished.connect(self._on_expression_generated)
        self._expr_worker = worker
        worker.start()

    def _tick_expression_spinner(self):
        """转圈文字动画"""
        dots = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self._expr_spinner_angle = (self._expr_spinner_angle + 1) % len(dots)
        self._expr_status_label.setText(f"{dots[self._expr_spinner_angle]} 生成中...")

    def _stop_expression_spinner(self):
        """停止转圈动画"""
        if hasattr(self, '_expr_spinner_timer') and self._expr_spinner_timer:
            self._expr_spinner_timer.stop()

    def _on_expression_generated(self, success: bool, path: str, error: str):
        """表情生成完成回调 → 弹出预览窗口"""
        self._stop_expression_spinner()
        self._expr_input.setEnabled(True)
        self._expr_gen_btn.setVisible(True)
        self._expr_gen_btn.setEnabled(True)
        self._expr_status_label.setVisible(False)

        if success and path:
            import os
            self._expr_result_path = path
            # 弹出预览窗口
            self._show_expression_preview(path)
        else:
            self._expr_status_label.setText(f"失败: {error[:40]}")
            self._expr_status_label.setStyleSheet(
                "QLabel { color: #ff5555; background: transparent; font-size: 12px; }"
            )
            self._expr_status_label.setVisible(True)

    def _show_expression_preview(self, result_path: str):
        """弹出预览对话框：左边原图 / 右边生成图 / 底部替换+取消按钮"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        from PyQt6.QtGui import QPixmap as _QPixmap

        dialog = QDialog(self)
        dialog.setWindowTitle("改表情动作 — 预览")
        dialog.setFixedSize(720, 420)
        dialog.setStyleSheet(
            "QDialog { background: #1e1e26; }"
            "QLabel { color: #eee; background: transparent; }"
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题
        title = QLabel("对比预览")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.DemiBold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 图片对比区
        compare_layout = QHBoxLayout()
        compare_layout.setSpacing(16)

        # 原图
        orig_frame = QVBoxLayout()
        orig_label = QLabel("原图")
        orig_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orig_label.setFont(QFont("Microsoft YaHei", 9))
        orig_frame.addWidget(orig_label)

        orig_img_label = QLabel()
        orig_img_label.setFixedSize(320, 280)
        orig_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        orig_img_label.setStyleSheet(
            "QLabel { background: #2a2a34; border: 1px solid #444; border-radius: 8px; }"
        )
        orig_pm = _QPixmap(self._expr_source_image)
        if not orig_pm.isNull():
            orig_img_label.setPixmap(orig_pm.scaled(
                316, 276,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        orig_frame.addWidget(orig_img_label)
        compare_layout.addLayout(orig_frame)

        # 生成图
        gen_frame = QVBoxLayout()
        gen_label = QLabel("生成结果")
        gen_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gen_label.setFont(QFont("Microsoft YaHei", 9))
        gen_frame.addWidget(gen_label)

        gen_img_label = QLabel()
        gen_img_label.setFixedSize(320, 280)
        gen_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gen_img_label.setStyleSheet(
            "QLabel { background: #2a2a34; border: 1px solid #444; border-radius: 8px; }"
        )
        gen_pm = _QPixmap(result_path)
        if not gen_pm.isNull():
            gen_img_label.setPixmap(gen_pm.scaled(
                316, 276,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        gen_frame.addWidget(gen_img_label)
        compare_layout.addLayout(gen_frame)

        layout.addLayout(compare_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 34)
        cancel_btn.setStyleSheet(
            "QPushButton { background: #555; color: #ccc; border-radius: 6px; font-size: 13px; }"
            "QPushButton:hover { background: #666; }"
        )
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)

        replace_btn = QPushButton("替换原图")
        replace_btn.setFixedSize(100, 34)
        replace_btn.setStyleSheet(
            "QPushButton { background: #2ecc71; color: white; border-radius: 6px; "
            "font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #27ae60; }"
        )
        replace_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(replace_btn)

        layout.addLayout(btn_layout)

        # 保持引用
        self._expr_preview_dialog = dialog

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._on_expression_replace()

    def _on_expression_replace(self):
        """点击替换 → 更新图层图片"""
        if not self._expr_result_path:
            return

        import os
        import time

        layer_id = self._expr_target_layer_id
        new_path = self._expr_result_path

        if not os.path.isfile(new_path):
            return

        # 更新画布 pixmap
        canvas = self._current_canvas()
        if canvas:
            item = canvas._layer_items.get(layer_id)
            if item:
                from PyQt6.QtGui import QPixmap
                pm = QPixmap(new_path)
                if not pm.isNull():
                    item.update_pixmap(pm)
                    item.update()
                    if canvas._canvas_scene:
                        canvas._canvas_scene.update()

        # 更新 DB
        from services.layer_service import LayerService
        LayerService().save_layer({
            'id': layer_id,
            'image_path': new_path,
            'prompt_history': [{
                'action': 'change_expression',
                'prompt': self._expr_input.text(),
                'output_path': new_path,
                'timestamp': time.time(),
            }],
        })
        self._refresh_layer_panel()
        self._hide_expression_panel()