"""
涛割 - 画布控制器
负责画布模式下的场景CRUD、排序持久化、批量生成桥接、分析结果保存
"""

from typing import List, Optional, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal

from database.session import session_scope
from database.models import Project, Scene, Character, SceneCharacter


class CanvasController(QObject):
    """
    画布控制器
    管理画布模式下的场景操作和数据持久化
    """

    scene_deleted = pyqtSignal(int)  # scene_id
    scene_duplicated = pyqtSignal(int, int)  # original_scene_id, new_scene_id
    scenes_reordered = pyqtSignal(int)  # project_id
    analysis_saved = pyqtSignal(int)  # project_id

    def __init__(self):
        super().__init__()

    # ==================== 场景CRUD ====================

    def delete_scene(self, scene_id: int) -> bool:
        """
        删除场景并重新排序

        Args:
            scene_id: 场景ID

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if not scene:
                    return False

                project_id = scene.project_id
                deleted_index = scene.scene_index
                session.delete(scene)

                # 重新排序后续场景
                remaining = session.query(Scene).filter(
                    Scene.project_id == project_id,
                    Scene.scene_index > deleted_index
                ).order_by(Scene.scene_index).all()

                for s in remaining:
                    s.scene_index -= 1

                # 更新项目场景计数
                project = session.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.total_scenes = max(0, project.total_scenes - 1)

            self.scene_deleted.emit(scene_id)
            return True

        except Exception as e:
            print(f"删除场景失败: {e}")
            return False

    def duplicate_scene(self, scene_id: int) -> Optional[int]:
        """
        复制场景（在原场景后插入）

        Args:
            scene_id: 要复制的场景ID

        Returns:
            新场景ID，失败返回None
        """
        try:
            with session_scope() as session:
                original = session.query(Scene).filter(Scene.id == scene_id).first()
                if not original:
                    return None

                project_id = original.project_id
                insert_index = original.scene_index + 1

                # 后移后续场景的索引
                later_scenes = session.query(Scene).filter(
                    Scene.project_id == project_id,
                    Scene.scene_index >= insert_index
                ).order_by(Scene.scene_index.desc()).all()

                for s in later_scenes:
                    s.scene_index += 1

                # 创建副本
                new_scene = Scene(
                    project_id=project_id,
                    scene_index=insert_index,
                    name=f"{original.name} (副本)" if original.name else None,
                    start_time=original.start_time,
                    end_time=original.end_time,
                    duration=original.duration,
                    subtitle_text=original.subtitle_text,
                    subtitle_segments=original.subtitle_segments,
                    ai_tags=original.ai_tags,
                    image_prompt=original.image_prompt,
                    camera_motion=original.camera_motion,
                    motion_intensity=original.motion_intensity,
                    generation_params=original.generation_params,
                    status="pending",
                )
                session.add(new_scene)
                session.flush()

                new_id = new_scene.id

                # 复制角色关联
                scene_chars = session.query(SceneCharacter).filter(
                    SceneCharacter.scene_id == scene_id
                ).all()
                for sc in scene_chars:
                    new_sc = SceneCharacter(
                        scene_id=new_id,
                        character_id=sc.character_id,
                        expression=sc.expression,
                        left_hand_action=sc.left_hand_action,
                        right_hand_action=sc.right_hand_action,
                        position_x=sc.position_x,
                        position_y=sc.position_y,
                        scale=sc.scale,
                    )
                    session.add(new_sc)

                # 更新项目场景计数
                project = session.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.total_scenes += 1

            self.scene_duplicated.emit(scene_id, new_id)
            return new_id

        except Exception as e:
            print(f"复制场景失败: {e}")
            return None

    # ==================== 排序持久化 ====================

    def reorder_scenes(self, project_id: int, scene_ids_in_order: List[int]) -> bool:
        """
        按新顺序重排场景索引

        Args:
            project_id: 项目ID
            scene_ids_in_order: 按新顺序排列的场景ID列表

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                for new_index, scene_id in enumerate(scene_ids_in_order):
                    scene = session.query(Scene).filter(
                        Scene.id == scene_id,
                        Scene.project_id == project_id
                    ).first()
                    if scene:
                        scene.scene_index = new_index

            self.scenes_reordered.emit(project_id)
            return True

        except Exception as e:
            print(f"重排场景失败: {e}")
            return False

    # ==================== 批量生成桥接 ====================

    def get_scene_ids_for_generation(self, project_id: int,
                                     scene_indices: List[int] = None,
                                     status_filter: str = None) -> List[int]:
        """
        获取需要生成的场景ID列表

        Args:
            project_id: 项目ID
            scene_indices: 按画布索引筛选（可选）
            status_filter: 按状态筛选（可选）

        Returns:
            场景ID列表
        """
        try:
            with session_scope() as session:
                query = session.query(Scene).filter(
                    Scene.project_id == project_id
                )

                if scene_indices is not None:
                    query = query.filter(Scene.scene_index.in_(scene_indices))

                if status_filter:
                    query = query.filter(Scene.status == status_filter)

                query = query.order_by(Scene.scene_index)
                return [s.id for s in query.all()]

        except Exception as e:
            print(f"获取生成场景列表失败: {e}")
            return []

    # ==================== 分析结果保存 ====================

    def save_analysis_results(self, project_id: int,
                              characters: List[Dict[str, Any]],
                              scenes: List[Dict[str, Any]]) -> bool:
        """
        保存分镜分析结果到数据库

        Args:
            project_id: 项目ID
            characters: 角色列表 [{"name": str, "type": str, "appearance": str, "reference_image": str}]
            scenes: 场景列表 [{"subtitle_text": str, "characters": [name, ...]}]

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                project = session.query(Project).filter(Project.id == project_id).first()
                if not project:
                    return False

                # 清理旧数据
                session.query(Scene).filter(Scene.project_id == project_id).delete()
                session.query(Character).filter(Character.project_id == project_id).delete()

                # 创建角色
                char_name_to_id = {}
                for char_data in characters:
                    char = Character(
                        project_id=project_id,
                        name=char_data.get('name', '未知角色'),
                        character_type=char_data.get('type', 'human'),
                        appearance=char_data.get('appearance', ''),
                        main_reference_image=char_data.get('reference_image'),
                        is_active=True,
                    )
                    session.add(char)
                    session.flush()
                    char_name_to_id[char.name] = char.id

                # 创建场景
                total_duration = 0.0
                for idx, scene_data in enumerate(scenes):
                    duration = scene_data.get('duration', 4.0)
                    total_duration += duration

                    scene = Scene(
                        project_id=project_id,
                        scene_index=idx,
                        name=scene_data.get('name', f"场景 {idx + 1}"),
                        subtitle_text=scene_data.get('subtitle_text', ''),
                        duration=duration,
                        start_time=scene_data.get('start_time', ''),
                        end_time=scene_data.get('end_time', ''),
                        ai_tags=scene_data.get('ai_tags', {}),
                        image_prompt=scene_data.get('image_prompt', ''),
                        status="pending",
                    )
                    session.add(scene)
                    session.flush()

                    # 创建场景-角色关联
                    scene_char_names = scene_data.get('characters', [])
                    for char_name in scene_char_names:
                        char_id = char_name_to_id.get(char_name)
                        if char_id:
                            sc = SceneCharacter(
                                scene_id=scene.id,
                                character_id=char_id,
                            )
                            session.add(sc)

                # 更新项目统计
                project.total_scenes = len(scenes)
                project.total_duration = total_duration
                project.completed_scenes = 0

            self.analysis_saved.emit(project_id)
            return True

        except Exception as e:
            print(f"保存分析结果失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_source_content(self, project_id: int, content: str,
                            source_type: str = "script") -> bool:
        """
        保存源文案到项目

        Args:
            project_id: 项目ID
            content: 文案内容
            source_type: 源类型

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                project = session.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.source_content = content
                    project.source_type = source_type
                    return True
            return False
        except Exception as e:
            print(f"保存源文案失败: {e}")
            return False

    def set_chapter_start(self, scene_id: int) -> bool:
        """
        将场景标记为章节起始

        Args:
            scene_id: 场景ID

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if scene:
                    gen_params = dict(scene.generation_params or {})
                    gen_params['is_chapter_start'] = True
                    scene.generation_params = gen_params
                    return True
            return False
        except Exception as e:
            print(f"设置章节起始失败: {e}")
            return False
