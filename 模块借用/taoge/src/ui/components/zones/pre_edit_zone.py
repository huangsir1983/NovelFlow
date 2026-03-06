"""
涛割 - 预编辑与输出区
三栏布局：场景列表 + 视频预览 + 镜头属性，以及导出操作。
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSplitter, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..script_structure_panel import ScriptStructurePanel
from ..video_preview_panel import VideoPreviewPanel
from ..shot_property_panel import ShotPropertyPanel


class PreEditZone(QWidget):
    """
    预编辑与输出区
    复用 ScriptStructurePanel + VideoPreviewPanel + ShotPropertyPanel
    """

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self.data_hub = data_hub
        self.selected_scene_index: int = -1

        self._init_ui()
        self._connect_data_hub()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部：导出操作栏
        export_bar = self._create_export_bar()
        layout.addWidget(export_bar)

        # 三栏分割器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.04);
                width: 1px;
            }
            QSplitter::handle:hover {
                background-color: rgba(10, 132, 255, 0.4);
            }
        """)

        # 左侧：场景列表
        self.script_panel = ScriptStructurePanel()
        self.script_panel.scene_selected.connect(self._on_scene_selected)
        main_splitter.addWidget(self.script_panel)

        # 中间：视频预览
        self.preview_panel = VideoPreviewPanel()
        self.preview_panel.scene_changed.connect(self._on_scene_selected)
        main_splitter.addWidget(self.preview_panel)

        # 右侧：镜头属性
        self.property_panel = ShotPropertyPanel()
        self.property_panel.property_changed.connect(self._on_property_changed)
        self.property_panel.generate_image_requested.connect(self._on_generate_image)
        self.property_panel.generate_video_requested.connect(self._on_generate_video)
        main_splitter.addWidget(self.property_panel)

        main_splitter.setSizes([280, 600, 350])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)

        layout.addWidget(main_splitter, 1)

    def _create_export_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(40)
        bar.setObjectName("preEditExportBar")
        bar.setStyleSheet("""
            QFrame#preEditExportBar {
                background-color: transparent;
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            }
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        layout.addStretch()

        export_btn = QPushButton("导出到剪映")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_to_jianying)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #409cff; }
            QPushButton:pressed { background-color: #0071e3; }
        """)
        layout.addWidget(export_btn)

        return bar

    def _connect_data_hub(self):
        if not self.data_hub:
            return
        self.data_hub.scenes_loaded.connect(self._on_scenes_loaded)
        self.data_hub.scene_updated.connect(self._on_scene_updated)
        self.data_hub.generation_completed.connect(self._on_generation_completed)
        self.preview_panel.audio_generated.connect(self._on_audio_generated)

    def _on_scenes_loaded(self, scenes: list):
        self.script_panel.load_scenes(scenes)
        self.preview_panel.load_scenes(scenes)
        if scenes:
            self._on_scene_selected(0)

    def _on_scene_updated(self, index: int, scene_data: dict):
        self.script_panel.update_scene(index, scene_data)
        if index == self.selected_scene_index:
            self.preview_panel.set_current_scene(index, scene_data)
            self.property_panel.set_scene(index, scene_data)

    def _on_scene_selected(self, index: int):
        if not self.data_hub:
            return
        if index < 0 or index >= len(self.data_hub.scenes_data):
            return

        self.selected_scene_index = index
        scene_data = self.data_hub.scenes_data[index]

        self.script_panel.select_scene(index, emit_signal=False)
        self.preview_panel.set_current_scene(index, scene_data)
        self.property_panel.set_scene(index, scene_data)

        characters = scene_data.get('characters', [])
        self.property_panel.update_characters(characters)

    def _on_property_changed(self, prop: str, value):
        if self.selected_scene_index < 0 or not self.data_hub:
            return
        self.data_hub.update_scene_property(self.selected_scene_index, prop, value)

    def _on_generate_image(self):
        if self.selected_scene_index >= 0 and self.data_hub:
            task_id = self.data_hub.generate_image(self.selected_scene_index)
            if not task_id:
                QMessageBox.warning(self, "错误", "启动图片生成失败，请检查API配置")

    def _on_generate_video(self):
        if self.selected_scene_index >= 0 and self.data_hub:
            scene_data = self.data_hub.scenes_data[self.selected_scene_index]
            if not scene_data.get('generated_image_path'):
                QMessageBox.warning(self, "提示", "请先生成图片，再生成视频")
                return
            task_id = self.data_hub.generate_video(self.selected_scene_index)
            if not task_id:
                QMessageBox.warning(self, "错误", "启动视频生成失败，请检查API配置")

    def _on_generation_completed(self, scene_id: int, task_type: str, result_path: str):
        """生成完成后刷新面板"""
        if not self.data_hub:
            return
        index = self.data_hub._find_scene_index(scene_id)
        if index >= 0 and index == self.selected_scene_index:
            scene_data = self.data_hub.scenes_data[index]
            self.preview_panel.set_current_scene(index, scene_data)
            self.property_panel.set_scene(index, scene_data)

    def _export_to_jianying(self):
        """导出到剪映"""
        if not self.data_hub or not self.data_hub.current_project_id:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        video_scenes = [s for s in self.data_hub.scenes_data if s.get('generated_video_path')]
        if not video_scenes:
            QMessageBox.warning(self, "提示", "没有已生成的视频，无法导出")
            return

        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", "")
        if not export_dir:
            return

        try:
            from services.export.jianying_exporter import JianyingExporter

            project_data = self.data_hub.project_controller.get_project(
                self.data_hub.current_project_id
            )
            if not project_data:
                QMessageBox.warning(self, "错误", "获取项目信息失败")
                return

            exporter = JianyingExporter(export_dir)

            export_scenes = []
            for scene in self.data_hub.scenes_data:
                if scene.get('generated_video_path'):
                    export_scenes.append({
                        'video_path': scene['generated_video_path'],
                        'subtitle': scene.get('subtitle_text', ''),
                        'start_time': scene.get('start_time', '00:00:00,000'),
                        'end_time': scene.get('end_time', '00:00:00,000'),
                        'duration': scene.get('duration', 4.0),
                    })

            result = exporter.export_project(
                project_name=project_data.get('name', '未命名项目'),
                scenes=export_scenes,
                fps=project_data.get('fps', 30),
                width=project_data.get('canvas_width', 1920),
                height=project_data.get('canvas_height', 1080)
            )

            if result:
                QMessageBox.information(
                    self, "导出成功",
                    f"项目已导出到:\n{export_dir}\n\n请在剪映中导入草稿"
                )
            else:
                QMessageBox.warning(self, "导出失败", "导出过程中发生错误")

        except Exception as e:
            QMessageBox.critical(self, "导出错误", f"导出失败: {str(e)}")

    def _on_audio_generated(self, scene_index: int, audio_path: str):
        """音频生成完成 → 更新 data_hub + 持久化到 DB"""
        if not self.data_hub:
            return
        if scene_index < 0 or scene_index >= len(self.data_hub.scenes_data):
            return

        # 更新内存数据
        self.data_hub.scenes_data[scene_index]['generated_audio_path'] = audio_path

        # 持久化到数据库
        scene_id = self.data_hub.scenes_data[scene_index].get('id')
        if scene_id:
            try:
                from database.session import session_scope
                from database.models.scene import Scene
                with session_scope() as session:
                    scene = session.query(Scene).get(scene_id)
                    if scene:
                        scene.generated_audio_path = audio_path
            except Exception as e:
                print(f"保存音频路径失败: {e}")

        # 通知更新
        if hasattr(self.data_hub, 'scene_updated'):
            self.data_hub.scene_updated.emit(
                scene_index, self.data_hub.scenes_data[scene_index]
            )
