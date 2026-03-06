"""
涛割 - 项目数据中心
集中管理项目数据（场景、角色、道具），持有所有控制器实例，
通过信号广播数据变更，供四个区域共享和联动。
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal

from database import session_scope, Project, Scene, SceneCharacter, Character, Prop, SceneProp, Act
from sqlalchemy.orm.attributes import flag_modified
from services.controllers import ProjectController, GenerationController, CanvasController, PropController, ActController, MaterialController
from services.controllers.asset_controller import AssetController
from services.layer_service import LayerService


class ProjectDataHub(QObject):
    """
    项目数据中心 - 所有区域共享的数据总线
    """

    # 数据加载信号
    project_loaded = pyqtSignal(int, dict)          # project_id, project_info
    scenes_loaded = pyqtSignal(list)                 # [scene_dict, ...]
    characters_loaded = pyqtSignal(list)             # [char_dict, ...]
    props_loaded = pyqtSignal(list)                  # [prop_dict, ...]
    acts_loaded = pyqtSignal(list)                   # [act_dict, ...]
    assets_loaded = pyqtSignal(list)                 # [asset_dict, ...] — 统一资产信号

    # 数据变更信号
    scene_updated = pyqtSignal(int, dict)            # index, scene_data
    scene_property_changed = pyqtSignal(int, str, object)  # index, prop_name, value
    characters_updated = pyqtSignal(list)            # 角色列表更新
    scenes_reloaded = pyqtSignal()                   # 场景列表完全重载
    act_updated = pyqtSignal(int, dict)              # act_id, act_data

    # 项目信息变更
    project_name_changed = pyqtSignal(str)           # new_name

    # 跨区联动
    script_analysis_done = pyqtSignal(list, list)    # scenes, characters
    asset_requirements_loaded = pyqtSignal(list)     # 资产需求加载完成
    open_intelligent_canvas = pyqtSignal(int)        # scene_id → 打开智能画布
    asset_library_updated = pyqtSignal(int)          # asset_id — 资产库某资产被编辑器更新

    # 生成相关（桥接 GenerationController）
    generation_started = pyqtSignal(int, str)        # scene_id, task_type
    generation_progress = pyqtSignal(int, str, int)  # scene_id, task_type, progress
    generation_completed = pyqtSignal(int, str, str) # scene_id, task_type, result_path
    generation_failed = pyqtSignal(int, str, str)    # scene_id, task_type, error

    def __init__(self, parent=None):
        super().__init__(parent)

        # 当前项目
        self.current_project_id: Optional[int] = None
        self.project_info: Dict[str, Any] = {}

        # 数据存储
        self.scenes_data: List[Dict[str, Any]] = []
        self.characters_data: List[Dict[str, Any]] = []
        self.props_data: List[Dict[str, Any]] = []
        self.acts_data: List[Dict[str, Any]] = []
        self.assets_data: List[Dict[str, Any]] = []  # 统一资产列表

        # 控制器
        self.project_controller = ProjectController()
        self.generation_controller = GenerationController()
        self.canvas_controller = CanvasController()
        self.prop_controller = PropController()
        self.act_controller = ActController()
        self.material_controller = MaterialController()
        self.asset_controller = AssetController()
        self.layer_service = LayerService()

        # 桥接生成控制器信号
        self.generation_controller.generation_started.connect(self._on_generation_started)
        self.generation_controller.generation_progress.connect(self._on_generation_progress)
        self.generation_controller.generation_completed.connect(self._on_generation_completed)
        self.generation_controller.generation_failed.connect(self._on_generation_failed)

        # 桥接资产控制器信号 — 资产编辑器保存后同步到剧本画布
        self.asset_controller.asset_updated.connect(self.asset_library_updated.emit)

    # ==================== 项目加载 ====================

    def load_project(self, project_id: int):
        """加载项目（从 scene_editor_page.load_project 迁移）"""
        self.current_project_id = project_id
        self.scenes_data.clear()
        self.characters_data.clear()
        self.props_data.clear()
        self.acts_data.clear()

        with session_scope() as session:
            project = session.query(Project).get(project_id)
            if not project:
                return

            self.project_info = {
                'id': project.id,
                'name': project.name,
                'total_scenes': project.total_scenes,
                'source_content': project.source_content,
                'source_type': project.source_type,
                'fps': project.fps,
                'canvas_width': project.canvas_width,
                'canvas_height': project.canvas_height,
            }

            scenes = session.query(Scene).filter(
                Scene.project_id == project_id
            ).order_by(Scene.scene_index).all()

            # 收集角色和道具（去重）
            char_map = {}
            prop_map = {}

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
                        # 收集到全局角色表
                        if char.id not in char_map:
                            char_map[char.id] = char.to_dict()

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
                        if prop.id not in prop_map:
                            prop_map[prop.id] = prop.to_dict()

                scene_dict['props'] = prop_list
                self.scenes_data.append(scene_dict)

            # 加载项目级道具
            project_props = self.prop_controller.get_project_props(project_id)
            for pp in project_props:
                pid = pp.get('id')
                if pid and pid not in prop_map:
                    prop_map[pid] = pp

            self.characters_data = list(char_map.values())
            self.props_data = list(prop_map.values())

        # 加载场次数据
        self.acts_data = self.act_controller.get_project_acts(project_id)

        # 加载统一资产数据
        self.assets_data = self.asset_controller.get_all_assets(project_id=project_id)

        # 发出信号
        self.project_loaded.emit(project_id, self.project_info)
        self.scenes_loaded.emit(self.scenes_data)
        self.characters_loaded.emit(self.characters_data)
        self.props_loaded.emit(self.props_data)
        self.acts_loaded.emit(self.acts_data)
        self.assets_loaded.emit(self.assets_data)

    def get_assets_by_type(self, asset_type: str) -> List[Dict[str, Any]]:
        """按类型过滤资产列表"""
        return [a for a in self.assets_data if a.get('asset_type') == asset_type]

    def reload_assets(self):
        """重新加载统一资产数据并发出信号"""
        if not self.current_project_id:
            return
        self.assets_data = self.asset_controller.get_all_assets(project_id=self.current_project_id)
        self.assets_loaded.emit(self.assets_data)

    def reload_scenes_only(self):
        """仅重新加载场景数据并发出 scenes_loaded 信号。
        不触发 project_loaded / acts_loaded，避免大场景序列区布局被重置。
        """
        if not self.current_project_id:
            return

        self.scenes_data.clear()
        with session_scope() as session:
            scenes = session.query(Scene).filter(
                Scene.project_id == self.current_project_id
            ).order_by(Scene.scene_index).all()

            for scene in scenes:
                scene_dict = scene.to_dict()

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

        self.scenes_loaded.emit(self.scenes_data)

    # ==================== 场景属性修改 ====================

    def update_scene_property(self, index: int, prop: str, value):
        """更新场景属性（通用）"""
        if index < 0 or index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[index]
        scene_id = scene_data.get('id')
        if not scene_id:
            return

        # 处理特殊属性
        if prop == "scene_characters_add":
            self._add_scene_character(scene_id, index, value)
            return
        elif prop == "scene_characters_remove":
            self._remove_scene_character(scene_id, index, value)
            return
        elif prop in ("consistency_mode", "consistency_strength"):
            gen_params = dict(scene_data.get('generation_params') or {})
            gen_params[prop] = value
            with session_scope() as session:
                scene = session.query(Scene).get(scene_id)
                if scene:
                    scene.generation_params = gen_params
                    flag_modified(scene, "generation_params")
            scene_data['generation_params'] = gen_params
            self.scene_property_changed.emit(index, prop, value)
            return
        elif prop == "video_prompt_details":
            gen_params = dict(scene_data.get('generation_params') or {})
            gen_params.update(value)
            with session_scope() as session:
                scene = session.query(Scene).get(scene_id)
                if scene:
                    scene.generation_params = gen_params
                    flag_modified(scene, "generation_params")
            scene_data['generation_params'] = gen_params
            self.scene_property_changed.emit(index, prop, value)
            return

        # 通用属性
        with session_scope() as session:
            scene = session.query(Scene).get(scene_id)
            if scene and hasattr(scene, prop):
                setattr(scene, prop, value)

        scene_data[prop] = value
        self.scene_updated.emit(index, scene_data)
        self.scene_property_changed.emit(index, prop, value)

    def _add_scene_character(self, scene_id: int, scene_index: int, char_data: dict):
        """添加角色到场景"""
        char_id = char_data.get('id')
        if not char_id:
            return

        try:
            with session_scope() as session:
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

            scene_data = self.scenes_data[scene_index]
            chars = scene_data.get('characters', [])
            chars.append(char_data)
            scene_data['characters'] = chars

            self.scene_updated.emit(scene_index, scene_data)
            self._refresh_characters()
        except Exception as e:
            print(f"添加场景角色失败: {e}")

    def _remove_scene_character(self, scene_id: int, scene_index: int, char_id: int):
        """从场景移除角色"""
        try:
            with session_scope() as session:
                sc = session.query(SceneCharacter).filter(
                    SceneCharacter.scene_id == scene_id,
                    SceneCharacter.character_id == char_id
                ).first()
                if sc:
                    session.delete(sc)

            scene_data = self.scenes_data[scene_index]
            chars = scene_data.get('characters', [])
            scene_data['characters'] = [c for c in chars if c.get('id') != char_id]

            self.scene_updated.emit(scene_index, scene_data)
            self._refresh_characters()
        except Exception as e:
            print(f"移除场景角色失败: {e}")

    def _refresh_characters(self):
        """从场景数据中刷新全局角色列表"""
        char_map = {}
        for sd in self.scenes_data:
            for c in sd.get('characters', []):
                cid = c.get('id')
                if cid and cid not in char_map:
                    char_map[cid] = c
        self.characters_data = list(char_map.values())
        self.characters_updated.emit(self.characters_data)

    # ==================== 场景删除/复制 ====================

    def delete_scene(self, index: int) -> bool:
        """删除场景"""
        if index < 0 or index >= len(self.scenes_data):
            return False

        scene_id = self.scenes_data[index].get('id')
        if not scene_id:
            return False

        if self.canvas_controller.delete_scene(scene_id):
            del self.scenes_data[index]
            self.scenes_loaded.emit(self.scenes_data)
            return True
        return False

    def duplicate_scene(self, index: int) -> bool:
        """复制场景"""
        if index < 0 or index >= len(self.scenes_data):
            return False

        scene_id = self.scenes_data[index].get('id')
        if not scene_id:
            return False

        new_id = self.canvas_controller.duplicate_scene(scene_id)
        if new_id:
            self.load_project(self.current_project_id)
            return True
        return False

    # ==================== 道具操作 ====================

    def add_scene_prop(self, scene_index: int, prop_data: dict):
        """添加道具到场景"""
        if scene_index < 0 or scene_index >= len(self.scenes_data):
            return

        scene_data = self.scenes_data[scene_index]
        scene_id = scene_data.get('id')
        prop_id = prop_data.get('id')

        if not scene_id:
            return

        # 如果道具没有ID，先创建
        if not prop_id:
            result = self.prop_controller.create_prop(
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

        result = self.prop_controller.add_prop_to_scene(scene_id, prop_id)
        if result:
            props = scene_data.get('props', [])
            if not any(p.get('id') == prop_id for p in props):
                props.append(prop_data)
                scene_data['props'] = props
            self.scene_updated.emit(scene_index, scene_data)

    # ==================== 分镜分析结果保存 ====================

    def save_analysis_results(self, project_id: int, characters: list, scenes: list) -> bool:
        """保存分镜分析结果"""
        success = self.canvas_controller.save_analysis_results(
            project_id, characters, scenes
        )
        if success:
            self.load_project(project_id)
            self.script_analysis_done.emit(
                self.scenes_data, self.characters_data
            )
        return success

    def save_source_content(self, project_id: int, content: str, source_type: str):
        """保存源文案"""
        self.canvas_controller.save_source_content(project_id, content, source_type)

    def rename_project(self, name: str):
        """重命名当前项目"""
        if not self.current_project_id or not name:
            return
        self.project_controller.update_project(self.current_project_id, name=name)
        self.project_info['name'] = name
        self.project_name_changed.emit(name)

    # ==================== 生成操作 ====================

    def generate_image(self, scene_index: int) -> Optional[str]:
        """生成图片"""
        if scene_index < 0 or scene_index >= len(self.scenes_data):
            return None
        scene_id = self.scenes_data[scene_index].get('id')
        if not scene_id:
            return None
        return self.generation_controller.generate_image(scene_id)

    def generate_video(self, scene_index: int) -> Optional[str]:
        """生成视频"""
        if scene_index < 0 or scene_index >= len(self.scenes_data):
            return None
        scene_data = self.scenes_data[scene_index]
        scene_id = scene_data.get('id')
        if not scene_id:
            return None
        return self.generation_controller.generate_video(scene_id, use_i2v=True)

    def batch_generate_images(self, scene_indices: list = None) -> list:
        """批量生成图片"""
        if not self.current_project_id:
            return []
        if scene_indices is None:
            scene_ids = [s['id'] for s in self.scenes_data if s.get('status') == 'pending']
        else:
            scene_ids = []
            for idx in scene_indices:
                if 0 <= idx < len(self.scenes_data):
                    sid = self.scenes_data[idx].get('id')
                    if sid:
                        scene_ids.append(sid)
        if not scene_ids:
            return []
        return self.generation_controller.batch_generate_images(
            self.current_project_id, scene_ids
        ) or []

    def batch_generate_videos(self, scene_indices: list = None) -> list:
        """批量生成视频"""
        if not self.current_project_id:
            return []
        if scene_indices is None:
            scene_ids = [s['id'] for s in self.scenes_data if s.get('status') == 'image_generated']
        else:
            scene_ids = []
            for idx in scene_indices:
                if 0 <= idx < len(self.scenes_data):
                    sid = self.scenes_data[idx].get('id')
                    if sid:
                        scene_ids.append(sid)
        if not scene_ids:
            return []
        return self.generation_controller.batch_generate_videos(
            self.current_project_id, scene_ids
        ) or []

    # ==================== 生成回调 ====================

    def _on_generation_started(self, scene_id: int, task_type: str):
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self.scenes_data[index]['status'] = f'{task_type}_generating'
            self.generation_started.emit(scene_id, task_type)
            self.scene_updated.emit(index, self.scenes_data[index])

    def _on_generation_progress(self, scene_id: int, task_type: str, progress: int):
        self.generation_progress.emit(scene_id, task_type, progress)

    def _on_generation_completed(self, scene_id: int, task_type: str, result_path: str):
        index = self._find_scene_index(scene_id)
        if index >= 0:
            with session_scope() as session:
                scene = session.query(Scene).get(scene_id)
                if scene:
                    scene_dict = scene.to_dict()
                    scene_dict['characters'] = self.scenes_data[index].get('characters', [])
                    scene_dict['props'] = self.scenes_data[index].get('props', [])
                    self.scenes_data[index] = scene_dict

            self.generation_completed.emit(scene_id, task_type, result_path)
            self.scene_updated.emit(index, self.scenes_data[index])

    def _on_generation_failed(self, scene_id: int, task_type: str, error: str):
        index = self._find_scene_index(scene_id)
        if index >= 0:
            self.scenes_data[index]['status'] = 'failed'
            self.generation_failed.emit(scene_id, task_type, error)
            self.scene_updated.emit(index, self.scenes_data[index])

    # ==================== 辅助方法 ====================

    def _find_scene_index(self, scene_id: int) -> int:
        """根据场景ID查找索引"""
        for i, scene in enumerate(self.scenes_data):
            if scene.get('id') == scene_id:
                return i
        return -1

    def get_source_content(self) -> str:
        """获取项目源文案"""
        if not self.current_project_id:
            return ""

        with session_scope() as session:
            project = session.query(Project).get(self.current_project_id)
            if project:
                text = project.source_content or ""
                if not text:
                    scenes = session.query(Scene).filter(
                        Scene.project_id == self.current_project_id
                    ).order_by(Scene.scene_index).all()
                    text = "\n".join(s.subtitle_text or "" for s in scenes if s.subtitle_text)
                return text
        return ""
