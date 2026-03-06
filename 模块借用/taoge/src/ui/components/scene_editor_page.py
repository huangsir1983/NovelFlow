"""
涛割 - 场景编辑器页面
三栏布局：左侧剧本结构 | 中间视频预览+时间轴 | 右侧镜头属性
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSplitter, QMessageBox, QFileDialog, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from database import session_scope, Project, Scene, SceneCharacter, Character, Prop, SceneProp
from sqlalchemy.orm.attributes import flag_modified
from .script_structure_panel import ScriptStructurePanel
from .video_preview_panel import VideoPreviewPanel
from .shot_property_panel import ShotPropertyPanel
from .first_last_frame import FirstLastFrameDialog
from .canvas_mode import CanvasModePanel
from .storyboard_analysis_dialog import StoryboardAnalysisDialog
from services.controllers import ProjectController, GenerationController, CanvasController, PropController
from services.export.jianying_exporter import JianyingExporter


class SceneEditorPage(QWidget):
    """场景编辑器页面 - 三栏布局"""

    back_requested = pyqtSignal()  # 返回信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_id: Optional[int] = None
        self.scenes_data: List[Dict[str, Any]] = []
        self.selected_scene_index: int = -1

        # 控制器
        self._project_controller = ProjectController()
        self._generation_controller = GenerationController()
        self._canvas_controller = CanvasController()
        self._prop_controller = PropController()

        # 连接生成控制器信号
        self._generation_controller.generation_started.connect(self._on_generation_started)
        self._generation_controller.generation_progress.connect(self._on_generation_progress)
        self._generation_controller.generation_completed.connect(self._on_generation_completed)
        self._generation_controller.generation_failed.connect(self._on_generation_failed)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 内容切换（编辑器模式 / 画布模式）
        self.mode_stack = QStackedWidget()

        # === 编辑器模式 (index=0) ===
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        # 主内容区（三栏分割器）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.05);
                width: 1px;
            }
            QSplitter::handle:hover {
                background-color: rgba(0, 122, 204, 0.5);
            }
        """)

        # 左侧：剧本结构面板
        self.script_panel = ScriptStructurePanel()
        self.script_panel.scene_selected.connect(self._on_scene_selected)
        main_splitter.addWidget(self.script_panel)

        # 中间：视频预览面板
        self.preview_panel = VideoPreviewPanel()
        self.preview_panel.scene_changed.connect(self._on_scene_selected)
        main_splitter.addWidget(self.preview_panel)

        # 右侧：镜头属性面板
        self.property_panel = ShotPropertyPanel()
        self.property_panel.property_changed.connect(self._on_property_changed)
        self.property_panel.generate_image_requested.connect(self._on_generate_current_image)
        self.property_panel.generate_video_requested.connect(self._on_generate_current_video)
        main_splitter.addWidget(self.property_panel)

        # 设置初始比例
        main_splitter.setSizes([280, 600, 350])
        main_splitter.setStretchFactor(0, 0)  # 左侧固定
        main_splitter.setStretchFactor(1, 1)  # 中间可伸缩
        main_splitter.setStretchFactor(2, 0)  # 右侧固定

        editor_layout.addWidget(main_splitter)
        self.mode_stack.addWidget(editor_widget)  # index 0

        # === 画布模式 (index=1) ===
        self.canvas_panel = CanvasModePanel()
        self.canvas_panel.scene_selected.connect(self._on_canvas_scene_selected)
        self.canvas_panel.back_to_editor.connect(self._switch_to_editor_mode)
        self.canvas_panel.batch_generate_requested.connect(self._on_canvas_batch_generate)
        self.canvas_panel.generate_image_requested.connect(self._generate_image)
        self.canvas_panel.generate_video_requested.connect(self._generate_video)
        self.canvas_panel.scene_deleted.connect(self._on_canvas_delete_scene)
        self.canvas_panel.scene_duplicated.connect(self._on_canvas_duplicate_scene)
        self.canvas_panel.character_dropped.connect(self._on_canvas_character_dropped)
        self.canvas_panel.prop_dropped.connect(self._on_canvas_prop_dropped)
        self.canvas_panel.property_changed_from_canvas.connect(self._on_canvas_property_changed)
        self.mode_stack.addWidget(self.canvas_panel)  # index 1

        layout.addWidget(self.mode_stack)

    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFixedHeight(56)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: rgb(25, 25, 28);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # 返回按钮
        back_btn = QPushButton("←")
        back_btn.setFixedSize(36, 36)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested.emit)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 18px;
                color: rgba(255, 255, 255, 0.7);
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        layout.addWidget(back_btn)

        # 项目名称
        self.project_name_label = QLabel("未选择项目")
        self.project_name_label.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        self.project_name_label.setStyleSheet("color: white;")
        layout.addWidget(self.project_name_label)

        # 场景统计
        self.stats_label = QLabel("0 场景")
        self.stats_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.4);
            font-size: 12px;
            margin-left: 10px;
        """)
        layout.addWidget(self.stats_label)

        layout.addStretch()

        # 批量操作按钮
        batch_gen_image = QPushButton("批量生成图片")
        batch_gen_image.setCursor(Qt.CursorShape.PointingHandCursor)
        batch_gen_image.clicked.connect(self._batch_generate_images)
        batch_gen_image.setStyleSheet(self._get_toolbar_btn_style())
        layout.addWidget(batch_gen_image)

        batch_gen_video = QPushButton("批量生成视频")
        batch_gen_video.setCursor(Qt.CursorShape.PointingHandCursor)
        batch_gen_video.clicked.connect(self._batch_generate_videos)
        batch_gen_video.setStyleSheet(self._get_toolbar_btn_style(primary=True))
        layout.addWidget(batch_gen_video)

        export_btn = QPushButton("导出到剪映")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_to_jianying)
        export_btn.setStyleSheet(self._get_toolbar_btn_style(outline=True))
        layout.addWidget(export_btn)

        # 画布模式切换
        self.canvas_mode_btn = QPushButton("画布模式")
        self.canvas_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.canvas_mode_btn.clicked.connect(self._switch_to_canvas_mode)
        self.canvas_mode_btn.setStyleSheet(self._get_toolbar_btn_style(outline=True))
        layout.addWidget(self.canvas_mode_btn)

        # 分镜分析按钮
        self.analysis_btn = QPushButton("分镜分析")
        self.analysis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analysis_btn.clicked.connect(self._open_storyboard_analysis)
        self.analysis_btn.setStyleSheet(self._get_toolbar_btn_style(primary=True))
        layout.addWidget(self.analysis_btn)

        return toolbar

    def _get_toolbar_btn_style(self, primary=False, outline=False):
        if primary:
            return """
                QPushButton {
                    background-color: rgb(0, 122, 204);
                    border: none;
                    border-radius: 4px;
                    color: white;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgb(0, 140, 220);
                }
            """
        elif outline:
            return """
                QPushButton {
                    background-color: transparent;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 4px;
                    color: rgba(255, 255, 255, 0.8);
                    padding: 8px 16px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    border-color: rgba(255, 255, 255, 0.3);
                }
            """
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
                color: white;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
        """

    def load_project(self, project_id: int):
        """加载项目"""
        self.current_project_id = project_id
        self.scenes_data.clear()
        self.selected_scene_index = -1

        with session_scope() as session:
            project = session.query(Project).get(project_id)
            if not project:
                return

            self.project_name_label.setText(project.name)

            scenes = session.query(Scene).filter(
                Scene.project_id == project_id
            ).order_by(Scene.scene_index).all()

            self.stats_label.setText(f"{len(scenes)} 场景")

            # 转换为字典列表，并加载关联角色和道具
            for scene in scenes:
                scene_dict = scene.to_dict()

                # 加载场景关联的角色
                scene_chars = session.query(SceneCharacter).filter(
                    SceneCharacter.scene_id == scene.id
                ).all()
                char_list = []
                for sc in scene_chars:
                    char = session.query(Character).get(sc.character_id)
                    if char and char.is_active:
                        char_dict = char.to_dict()
                        char_dict['scene_character_id'] = sc.id
                        char_dict['expression'] = sc.expression
                        char_dict['position_x'] = sc.position_x
                        char_dict['position_y'] = sc.position_y
                        char_dict['scale'] = sc.scale
                        char_list.append(char_dict)

                scene_dict['characters'] = char_list

                # 加载场景关联的道具
                scene_props = session.query(SceneProp).filter(
                    SceneProp.scene_id == scene.id
                ).all()
                prop_list = []
                for sp in scene_props:
                    prop = session.query(Prop).get(sp.prop_id)
                    if prop and prop.is_active:
                        prop_dict = prop.to_dict()
                        prop_dict['scene_prop_id'] = sp.id
                        prop_dict['position_x'] = sp.position_x
                        prop_dict['position_y'] = sp.position_y
                        prop_dict['scale'] = sp.scale
                        prop_list.append(prop_dict)

                scene_dict['props'] = prop_list
                self.scenes_data.append(scene_dict)

        # 加载到各面板
        self.script_panel.load_scenes(self.scenes_data)
        self.preview_panel.load_scenes(self.scenes_data)

        # 默认选中第一个场景
        if self.scenes_data:
            self._on_scene_selected(0)

    def _on_scene_selected(self, index: int):
        """场景选中事件"""
        if index < 0 or index >= len(self.scenes_data):
            return

        self.selected_scene_index = index
        scene_data = self.scenes_data[index]

        # 同步各面板（不发信号避免递归）
        self.script_panel.select_scene(index, emit_signal=False)
        self.preview_panel.set_current_scene(index, scene_data)
        self.property_panel.set_scene(index, scene_data)

        # 更新角色列表
        characters = scene_data.get('characters', [])
        self.property_panel.update_characters(characters)

    def _on_property_changed(self, prop: str, value):
        """属性变更事件"""
        if self.selected_scene_index < 0:
            return

        scene_data = self.scenes_data[self.selected_scene_index]
        scene_id = scene_data.get('id')

        if not scene_id:
            return

        # 处理角色添加/移除（特殊属性，不直接写Scene表）
        if prop == "scene_characters_add":
            self._add_scene_character(scene_id, value)
            return
        elif prop == "scene_characters_remove":
            self._remove_scene_character(scene_id, value)
            return
        elif prop in ("consistency_mode", "consistency_strength"):
            # 一致性参数保存到 generation_params
            gen_params = dict(scene_data.get('generation_params') or {})
            gen_params[prop] = value
            with session_scope() as session:
                scene = session.query(Scene).get(scene_id)
                if scene:
                    scene.generation_params = gen_params
                    flag_modified(scene, "generation_params")
            scene_data['generation_params'] = gen_params
            return
        elif prop == "video_prompt_details":
            # 视频提示词子维度存入 generation_params
            gen_params = dict(scene_data.get('generation_params') or {})
            gen_params.update(value)
            with session_scope() as session:
                scene = session.query(Scene).get(scene_id)
                if scene:
                    scene.generation_params = gen_params
                    flag_modified(scene, "generation_params")
            scene_data['generation_params'] = gen_params
            return

        # 更新数据库
        with session_scope() as session:
            scene = session.query(Scene).get(scene_id)
            if scene:
                setattr(scene, prop, value)

        # 更新本地数据
        scene_data[prop] = value

        # 更新各面板
        self.script_panel.update_scene(self.selected_scene_index, scene_data)
        self.preview_panel.set_current_scene(self.selected_scene_index, scene_data)

    def _add_scene_character(self, scene_id: int, char_data: dict):
        """添加角色到场景（创建SceneCharacter记录）"""
        char_id = char_data.get('id')
        if not char_id:
            return

        try:
            with session_scope() as session:
                # 检查是否已存在关联
                existing = session.query(SceneCharacter).filter(
                    SceneCharacter.scene_id == scene_id,
                    SceneCharacter.character_id == char_id
                ).first()
                if existing:
                    return

                sc = SceneCharacter(
                    scene_id=scene_id,
                    character_id=char_id,
                )
                session.add(sc)
                session.flush()

                char_data['scene_character_id'] = sc.id

            # 更新本地数据
            scene_data = self.scenes_data[self.selected_scene_index]
            chars = scene_data.get('characters', [])
            chars.append(char_data)
            scene_data['characters'] = chars

        except Exception as e:
            print(f"添加场景角色失败: {e}")

    def _remove_scene_character(self, scene_id: int, char_id: int):
        """从场景移除角色（删除SceneCharacter记录）"""
        try:
            with session_scope() as session:
                sc = session.query(SceneCharacter).filter(
                    SceneCharacter.scene_id == scene_id,
                    SceneCharacter.character_id == char_id
                ).first()
                if sc:
                    session.delete(sc)

            # 更新本地数据
            scene_data = self.scenes_data[self.selected_scene_index]
            chars = scene_data.get('characters', [])
            scene_data['characters'] = [c for c in chars if c.get('id') != char_id]

        except Exception as e:
            print(f"移除场景角色失败: {e}")

    def _on_generate_current_image(self):
        """生成当前场景图片"""
        if self.selected_scene_index < 0:
            return
        self._generate_image(self.selected_scene_index)

    def _on_generate_current_video(self):
        """生成当前场景视频"""
        if self.selected_scene_index < 0:
            return
        self._generate_video(self.selected_scene_index)

    def _generate_image(self, index: int):
        """生成图片"""
        if not self.current_project_id or index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[index]
        scene_id = scene_data.get('id')

        if not scene_id:
            QMessageBox.warning(self, "错误", "场景不存在")
            return

        # 调用生成控制器
        task_id = self._generation_controller.generate_image(scene_id)
        if not task_id:
            QMessageBox.warning(self, "错误", "启动图片生成失败，请检查API配置")

    def _generate_video(self, index: int):
        """生成视频"""
        if not self.current_project_id or index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[index]
        scene_id = scene_data.get('id')

        # 检查是否有图片
        if not scene_data.get('generated_image_path'):
            QMessageBox.warning(self, "提示", "请先生成图片，再生成视频")
            return

        # 调用生成控制器（使用I2V模式）
        task_id = self._generation_controller.generate_video(scene_id, use_i2v=True)
        if not task_id:
            QMessageBox.warning(self, "错误", "启动视频生成失败，请检查API配置")

    def _batch_generate_images(self):
        """批量生成图片"""
        if not self.current_project_id:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        pending_scenes = [s for s in self.scenes_data if s.get('status') == 'pending']

        if not pending_scenes:
            QMessageBox.information(self, "提示", "没有待生成图片的场景")
            return

        reply = QMessageBox.question(
            self,
            "确认批量生成",
            f"将为 {len(pending_scenes)} 个场景生成图片，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            scene_ids = [s['id'] for s in pending_scenes]
            task_ids = self._generation_controller.batch_generate_images(
                self.current_project_id, scene_ids
            )

            if task_ids:
                QMessageBox.information(
                    self, "提示",
                    f"已启动 {len(task_ids)} 个图片生成任务"
                )
            else:
                QMessageBox.warning(self, "错误", "启动批量生成失败")

    def _batch_generate_videos(self):
        """批量生成视频"""
        if not self.current_project_id:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        ready_scenes = [s for s in self.scenes_data if s.get('status') == 'image_generated']

        if not ready_scenes:
            QMessageBox.information(self, "提示", "没有可生成视频的场景（需要先生成图片）")
            return

        reply = QMessageBox.question(
            self,
            "确认批量生成",
            f"将为 {len(ready_scenes)} 个场景生成视频，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            scene_ids = [s['id'] for s in ready_scenes]
            task_ids = self._generation_controller.batch_generate_videos(
                self.current_project_id, scene_ids
            )

            if task_ids:
                QMessageBox.information(
                    self, "提示",
                    f"已启动 {len(task_ids)} 个视频生成任务"
                )
            else:
                QMessageBox.warning(self, "错误", "启动批量生成失败")

    def _export_to_jianying(self):
        """导出到剪映"""
        if not self.current_project_id:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        video_scenes = [s for s in self.scenes_data if s.get('generated_video_path')]

        if not video_scenes:
            QMessageBox.warning(self, "提示", "没有已生成的视频，无法导出")
            return

        export_dir = QFileDialog.getExistingDirectory(self, "选择导出目录", "")

        if not export_dir:
            return

        try:
            project_data = self._project_controller.get_project(self.current_project_id)
            if not project_data:
                QMessageBox.warning(self, "错误", "获取项目信息失败")
                return

            exporter = JianyingExporter(export_dir)

            export_scenes = []
            for scene in self.scenes_data:
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

    # ==================== 生成回调 ====================

    def _on_generation_started(self, scene_id: int, task_type: str):
        """生成开始回调"""
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self.scenes_data[index]['status'] = f'{task_type}_generating'
            self.script_panel.update_scene(index, self.scenes_data[index])
            # 同步画布
            self.canvas_panel.update_scene_data(index, self.scenes_data[index])
            self.canvas_panel.update_generation_progress(index, 5, True)

    def _on_generation_progress(self, scene_id: int, task_type: str, progress: int):
        """生成进度回调"""
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self.canvas_panel.update_generation_progress(index, progress, True)

    def _on_generation_completed(self, scene_id: int, task_type: str, result_path: str):
        """生成完成回调"""
        index = self._find_scene_index(scene_id)
        if index < 0:
            return

        # 更新本地数据
        with session_scope() as session:
            scene = session.query(Scene).get(scene_id)
            if scene:
                scene_dict = scene.to_dict()
                # 保留角色数据
                scene_dict['characters'] = self.scenes_data[index].get('characters', [])
                self.scenes_data[index] = scene_dict

        # 更新各面板
        self.script_panel.update_scene(index, self.scenes_data[index])

        if index == self.selected_scene_index:
            self.preview_panel.set_current_scene(index, self.scenes_data[index])
            self.property_panel.set_scene(index, self.scenes_data[index])

        # 同步画布
        self.canvas_panel.update_scene_data(index, self.scenes_data[index])
        self.canvas_panel.update_generation_progress(index, 100, False)

    def _on_generation_failed(self, scene_id: int, task_type: str, error: str):
        """生成失败回调"""
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self.scenes_data[index]['status'] = 'failed'
            self.script_panel.update_scene(index, self.scenes_data[index])
            # 同步画布
            self.canvas_panel.update_scene_data(index, self.scenes_data[index])
            self.canvas_panel.update_generation_progress(index, 0, False)

        QMessageBox.warning(self, "生成失败", f"场景生成失败: {error}")

    def _find_scene_index(self, scene_id: int) -> int:
        """根据场景ID查找索引"""
        for i, scene in enumerate(self.scenes_data):
            if scene.get('id') == scene_id:
                return i
        return -1

    # ==================== 画布模式 ====================

    def _switch_to_canvas_mode(self):
        """切换到画布模式"""
        # 传递角色数据到画布卡片
        self.canvas_panel.load_scenes(self.scenes_data)
        if self.selected_scene_index >= 0:
            self.canvas_panel.select_scene(self.selected_scene_index)
        self.mode_stack.setCurrentIndex(1)
        self.canvas_mode_btn.setText("编辑器模式")
        self.canvas_mode_btn.clicked.disconnect()
        self.canvas_mode_btn.clicked.connect(self._switch_to_editor_mode)

        # 加载角色和道具到侧边栏
        self._load_sidebar_data()

    def _switch_to_editor_mode(self):
        """切换回编辑器模式"""
        self.mode_stack.setCurrentIndex(0)
        self.canvas_mode_btn.setText("画布模式")
        self.canvas_mode_btn.clicked.disconnect()
        self.canvas_mode_btn.clicked.connect(self._switch_to_canvas_mode)

        # 同步选中状态
        if self.selected_scene_index >= 0:
            self._on_scene_selected(self.selected_scene_index)

        # 刷新左侧面板（场景顺序可能已改变）
        self.script_panel.load_scenes(self.scenes_data)

    def _on_canvas_scene_selected(self, index: int):
        """画布中场景被选中"""
        self.selected_scene_index = index

    def _on_canvas_property_changed(self, prop: str, value):
        """画布属性面板中属性变化 → 保存到数据库"""
        # 获取画布属性面板当前编辑的场景索引
        if (self.canvas_panel._property_panel and
                self.canvas_panel._property_panel.current_scene_index >= 0):
            idx = self.canvas_panel._property_panel.current_scene_index
        else:
            idx = self.selected_scene_index

        if idx < 0 or idx >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[idx]
        scene_id = scene_data.get('id')
        if not scene_id:
            return

        if prop == "video_prompt_details":
            gen_params = dict(scene_data.get('generation_params') or {})
            gen_params.update(value)
            with session_scope() as session:
                scene = session.query(Scene).get(scene_id)
                if scene:
                    scene.generation_params = gen_params
                    flag_modified(scene, "generation_params")
            scene_data['generation_params'] = gen_params
            return

        # 通用属性写入
        with session_scope() as session:
            scene = session.query(Scene).get(scene_id)
            if scene and hasattr(scene, prop):
                setattr(scene, prop, value)

        scene_data[prop] = value

    def _on_canvas_batch_generate(self, indices: list):
        """画布批量生成请求"""
        if not self.current_project_id:
            return

        scene_ids = []
        for idx in indices:
            if 0 <= idx < len(self.scenes_data):
                sid = self.scenes_data[idx].get('id')
                if sid:
                    scene_ids.append(sid)

        if not scene_ids:
            return

        reply = QMessageBox.question(
            self,
            "确认批量生成",
            f"将为 {len(scene_ids)} 个场景生成图片，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            task_ids = self._generation_controller.batch_generate_images(
                self.current_project_id, scene_ids
            )
            if task_ids:
                QMessageBox.information(
                    self, "提示",
                    f"已启动 {len(task_ids)} 个图片生成任务"
                )

    def _on_canvas_delete_scene(self, index: int):
        """画布删除场景"""
        if index < 0 or index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[index]
        scene_id = scene_data.get('id')
        if not scene_id:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除场景 #{index + 1} 吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._canvas_controller.delete_scene(scene_id):
                del self.scenes_data[index]
                # 重新加载画布
                self.canvas_panel.load_scenes(self.scenes_data)
                self.script_panel.load_scenes(self.scenes_data)
                self.stats_label.setText(f"{len(self.scenes_data)} 场景")

    def _on_canvas_duplicate_scene(self, index: int):
        """画布复制场景"""
        if index < 0 or index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[index]
        scene_id = scene_data.get('id')
        if not scene_id:
            return

        new_id = self._canvas_controller.duplicate_scene(scene_id)
        if new_id:
            # 重新加载项目数据
            self.load_project(self.current_project_id)
            # 如果在画布模式，重新加载画布
            if self.mode_stack.currentIndex() == 1:
                self.canvas_panel.load_scenes(self.scenes_data)

    def _on_canvas_character_dropped(self, scene_index: int, char_data: dict):
        """画布中角色被拖放到场景"""
        if scene_index < 0 or scene_index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[scene_index]
        scene_id = scene_data.get('id')
        char_id = char_data.get('id')

        if not scene_id or not char_id:
            return

        self._add_scene_character(scene_id, char_data)

    def _on_canvas_prop_dropped(self, scene_index: int, prop_data: dict):
        """画布中道具被拖放到场景"""
        if scene_index < 0 or scene_index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[scene_index]
        scene_id = scene_data.get('id')
        prop_id = prop_data.get('id')

        if not scene_id:
            return

        # 如果道具没有ID，先创建
        if not prop_id:
            result = self._prop_controller.create_prop(
                name=prop_data.get('name', '未知'),
                prop_type=prop_data.get('prop_type', 'object'),
                project_id=self.current_project_id,
                description=prop_data.get('description'),
                prompt_description=prop_data.get('prompt_description'),
            )
            if result:
                prop_id = result['id']
                prop_data['id'] = prop_id
            else:
                return

        self._add_scene_prop(scene_id, prop_data)

    def _add_scene_prop(self, scene_id: int, prop_data: dict):
        """添加道具到场景"""
        prop_id = prop_data.get('id')
        if not prop_id:
            return

        result = self._prop_controller.add_prop_to_scene(scene_id, prop_id)
        if result:
            # 更新本地数据
            if self.selected_scene_index >= 0:
                scene_data = self.scenes_data[self.selected_scene_index]
                props = scene_data.get('props', [])
                if not any(p.get('id') == prop_id for p in props):
                    props.append(prop_data)
                    scene_data['props'] = props

    def _remove_scene_prop(self, scene_id: int, prop_id: int):
        """从场景移除道具"""
        if self._prop_controller.remove_prop_from_scene(scene_id, prop_id):
            if self.selected_scene_index >= 0:
                scene_data = self.scenes_data[self.selected_scene_index]
                props = scene_data.get('props', [])
                scene_data['props'] = [p for p in props if p.get('id') != prop_id]

    # ==================== 分镜分析 ====================

    def _open_storyboard_analysis(self):
        """打开分镜分析对话框"""
        if not self.current_project_id:
            QMessageBox.warning(self, "提示", "请先选择项目")
            return

        # 获取项目源文案
        source_text = ""
        with session_scope() as session:
            project = session.query(Project).get(self.current_project_id)
            if project:
                source_text = project.source_content or ""

                # 如果没有 source_content，尝试从现有场景拼接
                if not source_text:
                    scenes = session.query(Scene).filter(
                        Scene.project_id == self.current_project_id
                    ).order_by(Scene.scene_index).all()
                    source_text = "\n".join(s.subtitle_text or "" for s in scenes if s.subtitle_text)

        if not source_text:
            QMessageBox.warning(self, "提示", "没有可用的文案内容，请先导入文案")
            return

        dialog = StoryboardAnalysisDialog(self.current_project_id, source_text, self)
        dialog.analysis_completed.connect(self._on_analysis_completed)
        dialog.exec()

    def _on_analysis_completed(self, project_id: int, scenes: list, characters: list):
        """分镜分析完成回调"""
        # 保存分析结果到数据库
        success = self._canvas_controller.save_analysis_results(
            project_id, characters, scenes
        )

        if not success:
            QMessageBox.warning(self, "错误", "保存分析结果失败")
            return

        # 重新加载项目
        self.load_project(project_id)

        # 切换到画布模式
        self._switch_to_canvas_mode()

    def _load_sidebar_data(self):
        """加载角色和道具数据到侧边栏"""
        if not self.canvas_panel.canvas_sidebar or not self.current_project_id:
            return

        sidebar = self.canvas_panel.canvas_sidebar

        # 收集所有场景中的角色（去重）
        char_map = {}
        for scene_data in self.scenes_data:
            for char in scene_data.get('characters', []):
                cid = char.get('id')
                if cid and cid not in char_map:
                    char_map[cid] = char

        sidebar.load_characters(list(char_map.values()))

        # 收集所有场景中的道具（去重）
        prop_map = {}
        for scene_data in self.scenes_data:
            for prop in scene_data.get('props', []):
                pid = prop.get('id')
                if pid and pid not in prop_map:
                    prop_map[pid] = prop

        # 同时加载项目级道具
        project_props = self._prop_controller.get_project_props(self.current_project_id)
        for pp in project_props:
            pid = pp.get('id')
            if pid not in prop_map:
                prop_map[pid] = pp

        sidebar.load_props(list(prop_map.values()))
