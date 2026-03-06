"""
涛割 - 全屏入口页（替代 SceneEditorPage）
进入项目后的全屏工作区，顶部导航栏 + 四区域 QStackedWidget
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QMessageBox, QFileDialog
)
from PyQt6.QtCore import pyqtSignal

from .project_data_hub import ProjectDataHub
from .top_navigation_bar import TopNavigationBar
from .zones.script_zone import ScriptZone
from .zones.character_prop_zone import CharacterPropZone
from .zones.director_zone import DirectorZone
from .zones.pre_edit_zone import PreEditZone
from .animatic_panel import AnimaticPanel
from .consistency_dashboard import ConsistencyDashboard
from ui import theme


class InfiniteCanvasPage(QWidget):
    """
    全屏入口页 - 四区域无限画布模式
    布局: QVBoxLayout → TopNavigationBar + QStackedWidget（四个区域）
    """

    back_requested = pyqtSignal()  # 返回项目列表

    def __init__(self, parent=None):
        super().__init__(parent)

        # 数据中心
        self.data_hub = ProjectDataHub(self)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setStyleSheet(f"background-color: {theme.bg_primary()};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部导航栏（苹果风格，通透背景）
        self.nav_bar = TopNavigationBar()
        layout.addWidget(self.nav_bar)

        # 四区域 QStackedWidget
        self.zone_stack = QStackedWidget()

        # 0: 剧本区
        self.script_zone = ScriptZone(data_hub=self.data_hub)
        self.zone_stack.addWidget(self.script_zone)

        # 1: 角色道具区
        self.character_prop_zone = CharacterPropZone(data_hub=self.data_hub)
        self.zone_stack.addWidget(self.character_prop_zone)

        # 2: 导演画布区
        self.director_zone = DirectorZone(data_hub=self.data_hub)
        self.zone_stack.addWidget(self.director_zone)

        # 3: 预编辑区
        self.pre_edit_zone = PreEditZone(data_hub=self.data_hub)
        self.zone_stack.addWidget(self.pre_edit_zone)

        # 4: Animatic 预览 + 一致性仪表盘
        self._animatic_container = QWidget()
        from PyQt6.QtWidgets import QSplitter
        animatic_layout = QVBoxLayout(self._animatic_container)
        animatic_layout.setContentsMargins(0, 0, 0, 0)
        animatic_splitter = QSplitter()
        self.animatic_panel = AnimaticPanel(data_hub=self.data_hub)
        self.consistency_dashboard = ConsistencyDashboard(data_hub=self.data_hub)
        animatic_splitter.addWidget(self.animatic_panel)
        animatic_splitter.addWidget(self.consistency_dashboard)
        animatic_splitter.setStretchFactor(0, 2)
        animatic_splitter.setStretchFactor(1, 1)
        animatic_layout.addWidget(animatic_splitter)
        self.zone_stack.addWidget(self._animatic_container)

        layout.addWidget(self.zone_stack, 1)

    def _connect_signals(self):
        # 导航栏信号
        self.nav_bar.zone_requested.connect(self._navigate_to_zone)
        self.nav_bar.back_requested.connect(self.back_requested.emit)

        # 数据中心信号 → 导航栏更新
        self.data_hub.project_loaded.connect(self._on_project_loaded)
        self.data_hub.project_name_changed.connect(
            lambda name: self.nav_bar.set_project_info(name, len(self.data_hub.scenes_data))
        )
        self.data_hub.scenes_loaded.connect(
            lambda scenes: self.nav_bar.update_scene_count(len(scenes))
        )
        self.data_hub.generation_failed.connect(self._on_generation_failed)

        # 导航栏项目名编辑 → 数据中心
        self.nav_bar.project_name_changed.connect(self.data_hub.rename_project)

        # 导演画布区信号 → 数据中心
        self.director_zone.generate_image_requested.connect(
            lambda idx: self._generate_image(idx)
        )
        self.director_zone.generate_video_requested.connect(
            lambda idx: self._generate_video(idx)
        )
        self.director_zone.scene_deleted.connect(self._delete_scene)
        self.director_zone.scene_duplicated.connect(self._duplicate_scene)
        self.director_zone.batch_generate_requested.connect(self._batch_generate_from_indices)
        self.director_zone.character_dropped.connect(
            lambda idx, data: self.data_hub.update_scene_property(idx, 'scene_characters_add', data)
        )
        self.director_zone.prop_dropped.connect(
            lambda idx, data: self.data_hub.add_scene_prop(idx, data)
        )

        # 智能画布入口
        self.data_hub.open_intelligent_canvas.connect(
            self.director_zone.enter_intelligent_canvas
        )

        # 剧本区信号
        self.script_zone.analysis_completed.connect(self._on_analysis_completed)
        self.script_zone.project_created.connect(self._on_script_project_created)

        # Animatic 面板信号
        self.animatic_panel.open_canvas_requested.connect(
            self.data_hub.open_intelligent_canvas.emit
        )

    # ==================== 项目加载 ====================

    def load_project(self, project_id: int):
        """加载项目 → 委托给 DataHub"""
        self.data_hub.load_project(project_id)

    def _on_project_loaded(self, project_id: int, project_info: dict):
        """项目加载完成"""
        self.nav_bar.set_project_info(
            project_info.get('name', '未命名'),
            len(self.data_hub.scenes_data)
        )

    # ==================== 区域切换 ====================

    def _navigate_to_zone(self, index: int):
        """切换到指定区域"""
        self.zone_stack.setCurrentIndex(index)
        # Animatic 区域加载
        if index == 4 and self.data_hub.current_project_id:
            self.animatic_panel.load_project(self.data_hub.current_project_id)
            self.consistency_dashboard.analyze_project()
        self.nav_bar.set_active_zone(index)

    # ==================== 生成操作 ====================

    def _generate_image(self, scene_index: int):
        task_id = self.data_hub.generate_image(scene_index)
        if not task_id:
            QMessageBox.warning(self, "错误", "启动图片生成失败，请检查API配置")

    def _generate_video(self, scene_index: int):
        if scene_index < len(self.data_hub.scenes_data):
            scene_data = self.data_hub.scenes_data[scene_index]
            if not scene_data.get('generated_image_path'):
                QMessageBox.warning(self, "提示", "请先生成图片，再生成视频")
                return

        task_id = self.data_hub.generate_video(scene_index)
        if not task_id:
            QMessageBox.warning(self, "错误", "启动视频生成失败，请检查API配置")

    def _batch_generate_images(self):
        pending = [s for s in self.data_hub.scenes_data if s.get('status') == 'pending']
        if not pending:
            QMessageBox.information(self, "提示", "没有待生成图片的场景")
            return

        reply = QMessageBox.question(
            self, "确认批量生成",
            f"将为 {len(pending)} 个场景生成图片，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            task_ids = self.data_hub.batch_generate_images()
            if task_ids:
                QMessageBox.information(self, "提示", f"已启动 {len(task_ids)} 个图片生成任务")
            else:
                QMessageBox.warning(self, "错误", "启动批量生成失败")

    def _batch_generate_videos(self):
        ready = [s for s in self.data_hub.scenes_data if s.get('status') == 'image_generated']
        if not ready:
            QMessageBox.information(self, "提示", "没有可生成视频的场景（需要先生成图片）")
            return

        reply = QMessageBox.question(
            self, "确认批量生成",
            f"将为 {len(ready)} 个场景生成视频，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            task_ids = self.data_hub.batch_generate_videos()
            if task_ids:
                QMessageBox.information(self, "提示", f"已启动 {len(task_ids)} 个视频生成任务")
            else:
                QMessageBox.warning(self, "错误", "启动批量生成失败")

    def _batch_generate_from_indices(self, indices: list):
        if not indices:
            return

        reply = QMessageBox.question(
            self, "确认批量生成",
            f"将为 {len(indices)} 个场景生成图片，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            task_ids = self.data_hub.batch_generate_images(indices)
            if task_ids:
                QMessageBox.information(self, "提示", f"已启动 {len(task_ids)} 个图片生成任务")

    def _on_generation_failed(self, scene_id: int, task_type: str, error: str):
        QMessageBox.warning(self, "生成失败", f"场景生成失败: {error}")

    # ==================== 场景操作 ====================

    def _delete_scene(self, index: int):
        if index < 0 or index >= len(self.data_hub.scenes_data):
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除场景 #{index + 1} 吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.data_hub.delete_scene(index)

    def _duplicate_scene(self, index: int):
        self.data_hub.duplicate_scene(index)

    # ==================== 导出 ====================

    def _export_to_jianying(self):
        """导出到剪映"""
        if not self.data_hub.current_project_id:
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

    # ==================== 分镜分析 ====================

    def _open_storyboard_analysis(self):
        """打开分镜分析"""
        source_text = self.data_hub.get_source_content()

        if not source_text:
            QMessageBox.warning(self, "提示", "没有可用的文案内容，请先在剧本区导入文案")
            # 自动切换到剧本区
            self._navigate_to_zone(0)
            return

        from .storyboard_analysis_dialog import StoryboardAnalysisDialog
        dialog = StoryboardAnalysisDialog(
            self.data_hub.current_project_id, source_text, self
        )
        dialog.analysis_completed.connect(self._on_dialog_analysis_completed)
        dialog.exec()

    def _on_dialog_analysis_completed(self, project_id: int, scenes: list, characters: list):
        """分镜分析对话框完成"""
        success = self.data_hub.save_analysis_results(
            project_id, characters, scenes
        )
        if success:
            # 自动跳转到导演画布区
            self._navigate_to_zone(2)

    def _on_analysis_completed(self, project_id: int, scenes: list, characters: list):
        """剧本区分镜分析完成 → 自动跳转到导演画布区"""
        self._navigate_to_zone(2)

    def _on_script_project_created(self, project_data):
        """剧本区创建新项目后加载"""
        project_id = project_data.get('id')
        if project_id:
            self.load_project(project_id)

    def apply_theme(self, dark: bool):
        """切换主题 → 传播给所有子区域"""
        self.setStyleSheet(f"background-color: {theme.bg_primary()};")
        self.nav_bar.set_theme(dark)
        self.script_zone.apply_theme(dark)
        self.character_prop_zone.apply_theme(dark)
        self.director_zone.apply_theme(dark)
        if hasattr(self.pre_edit_zone, 'apply_theme'):
            self.pre_edit_zone.apply_theme(dark)
        self.animatic_panel.apply_theme()
        self.consistency_dashboard.apply_theme()
