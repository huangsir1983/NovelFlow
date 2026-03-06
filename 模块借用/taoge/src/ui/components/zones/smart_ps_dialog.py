"""
涛割 - 智能PS弹窗 [DEPRECATED]
已被 smart_ps_agent_node.py 中的 SmartPSAgentNode 替代。
保留本文件以兼容旧代码引用，新流程不再使用本模块。

原功能：从分镜卡 + 号菜单"智能PS"选项打开的独立弹窗，
内嵌 IntelligentCanvasPage，自动加载场景关联的资产图层。
"""

from typing import Optional, List

from PyQt6.QtWidgets import QDialog, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation
from PyQt6.QtGui import QScreen


class SmartPSDialog(QDialog):
    """
    智能PS独立弹窗。
    - modeless（非模态），允许同时操作画布
    - 嵌入 IntelligentCanvasPage
    - 首次打开：清空旧图层 + 重新加载资产
    - 再次打开（双击PS卡）：保留已有图层状态
    - 关闭时通过 image_saved 信号通知画布
    """

    image_saved = pyqtSignal(str)  # 保存后的图片路径

    def __init__(self, scene_id: int, data_hub, assets: list = None,
                 first_open: bool = True, parent=None):
        super().__init__(parent)
        self._scene_id = scene_id
        self._data_hub = data_hub
        self._assets = assets or []
        self._first_open = first_open

        self.setWindowTitle(f"智能PS — 场景 {scene_id}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )

        # 窗口大小：屏幕 80%
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            w = int(geo.width() * 0.8)
            h = int(geo.height() * 0.8)
            self.resize(w, h)
            # 居中
            x = geo.x() + (geo.width() - w) // 2
            y = geo.y() + (geo.height() - h) // 2
            self.move(x, y)
        else:
            self.resize(1400, 900)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 嵌入 IntelligentCanvasPage
        from ui.components.intelligent_canvas_page import IntelligentCanvasPage
        self._canvas_page = IntelligentCanvasPage(
            data_hub=data_hub, parent=self)
        layout.addWidget(self._canvas_page)

        # 信号连接
        self._canvas_page.back_requested.connect(self.close)
        self._canvas_page.scene_saved.connect(self._on_scene_saved)

        # 加载场景
        self._canvas_page.load_scene(scene_id)

        # 首次打开：清空旧图层 + 重新加载资产
        # 再次打开（双击PS卡）：已有图层由 load_scene 从 DB 恢复，跳过清空
        if self._first_open:
            self._load_asset_layers()

        # 打开动画：渐显
        self.setWindowOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _load_asset_layers(self):
        """清空旧图层 → 重新加载资产图层"""
        import os
        try:
            from services.layer_service import LayerService
            layer_service = LayerService()

            # 1. 清空该场景的所有旧图层（数据库）
            layer_service.delete_scene_layers(self._scene_id)

            # 2. 清空画布上的图层 items
            canvas_view = self._canvas_page._current_canvas()
            if canvas_view:
                for lid in list(canvas_view._layer_items.keys()):
                    canvas_view.remove_layer(lid)

            # 3. 无资产则跳过
            if not self._assets:
                return

            # 按类型排序：background(z=0) → prop(z=1+) → character(z=N)
            type_order = {'background': 0, 'prop': 1, 'character': 2}
            sorted_assets = sorted(
                self._assets,
                key=lambda a: type_order.get(a.get('type', ''), 1)
            )

            z_order = 0
            for asset in sorted_assets:
                image_path = asset.get('image_path', '')
                name = asset.get('name', '')
                asset_type = asset.get('type', 'prop')

                if not image_path or not os.path.isfile(image_path):
                    continue

                # 保存图层到数据库
                layer_data = {
                    'scene_id': self._scene_id,
                    'name': name or f'资产 {z_order + 1}',
                    'layer_type': asset_type,
                    'z_order': z_order,
                    'is_visible': True,
                    'is_locked': False,
                    'image_path': image_path,
                    'original_image_path': image_path,
                }
                layer_id = layer_service.save_layer(layer_data)
                layer_data['id'] = layer_id

                # 添加到画布
                if canvas_view:
                    canvas_view.add_layer(layer_data)

                z_order += 1

            # 刷新图层面板
            self._canvas_page._refresh_layer_panel()

        except Exception as e:
            print(f"[涛割] 智能PS加载资产图层失败: {e}")

    def _on_scene_saved(self, scene_id: int):
        """场景保存完成"""
        # 尝试获取导出的图片路径
        try:
            canvas_view = self._canvas_page._current_canvas()
            if canvas_view and hasattr(canvas_view, '_export_path'):
                self.image_saved.emit(canvas_view._export_path)
        except Exception:
            pass

    def closeEvent(self, event):
        """关闭时自动保存 + 导出合成图"""
        try:
            canvas_view = self._canvas_page._current_canvas()
            if canvas_view:
                canvas_view.save_scene()
                export_path = canvas_view.export_composite_image()
                if export_path:
                    self.image_saved.emit(export_path)
        except Exception as e:
            print(f"[涛割] 智能PS关闭保存失败: {e}")
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """Esc 关闭弹窗"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
