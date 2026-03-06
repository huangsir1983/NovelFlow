"""
涛割 - 项目控制器
负责项目的CRUD操作和状态管理
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from database.session import session_scope, get_session
from database.models import Project, Scene
from services.scene.processor import SceneProcessor


class ProjectController(QObject):
    """
    项目控制器
    连接UI与数据库的桥梁，处理项目相关的业务逻辑
    """

    # 信号定义
    project_created = pyqtSignal(int)  # 项目ID
    project_updated = pyqtSignal(int)
    project_deleted = pyqtSignal(int)
    project_list_changed = pyqtSignal()
    scenes_imported = pyqtSignal(int, int)  # project_id, scene_count

    _instance: Optional['ProjectController'] = None

    def __init__(self):
        super().__init__()

    # ==================== 项目CRUD ====================

    def create_project(self, name: str, description: str = "",
                       source_type: str = "srt", **kwargs) -> Optional[Dict[str, Any]]:
        """
        创建新项目

        Args:
            name: 项目名称
            description: 项目描述
            source_type: 源类型 (srt, script, video)
            **kwargs: 其他项目属性

        Returns:
            创建的项目字典，失败返回None
        """
        try:
            with session_scope() as session:
                project = Project(
                    name=name,
                    description=description,
                    source_type=source_type,
                    canvas_width=kwargs.get('canvas_width', 1920),
                    canvas_height=kwargs.get('canvas_height', 1080),
                    fps=kwargs.get('fps', 30),
                    default_model=kwargs.get('default_model', 'vidu'),
                    status='draft'
                )
                session.add(project)
                session.flush()  # 获取ID

                project_id = project.id
                project_dict = project.to_dict()

                self.project_created.emit(project_id)
                self.project_list_changed.emit()

                return project_dict

        except Exception as e:
            print(f"创建项目失败: {e}")
            return None

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        获取项目详情

        Args:
            project_id: 项目ID

        Returns:
            项目字典，不存在返回None
        """
        try:
            with session_scope() as session:
                project = session.query(Project).filter(Project.id == project_id).first()
                if project:
                    return project.to_dict()
                return None
        except Exception as e:
            print(f"获取项目失败: {e}")
            return None

    def get_all_projects(self, status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取所有项目列表

        Args:
            status: 筛选状态 (draft, processing, completed)
            limit: 返回数量限制

        Returns:
            项目字典列表
        """
        try:
            with session_scope() as session:
                query = session.query(Project)

                if status:
                    query = query.filter(Project.status == status)

                query = query.order_by(Project.updated_at.desc().nullsfirst())
                query = query.limit(limit)

                projects = query.all()
                return [p.to_dict() for p in projects]

        except Exception as e:
            print(f"获取项目列表失败: {e}")
            return []

    def update_project(self, project_id: int, **kwargs) -> bool:
        """
        更新项目信息

        Args:
            project_id: 项目ID
            **kwargs: 要更新的字段

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                project = session.query(Project).filter(Project.id == project_id).first()
                if not project:
                    return False

                # 更新允许的字段
                allowed_fields = [
                    'name', 'description', 'canvas_width', 'canvas_height',
                    'fps', 'default_model', 'status', 'total_duration',
                    'total_scenes', 'completed_scenes', 'total_cost'
                ]

                for field, value in kwargs.items():
                    if field in allowed_fields and hasattr(project, field):
                        setattr(project, field, value)

                self.project_updated.emit(project_id)
                return True

        except Exception as e:
            print(f"更新项目失败: {e}")
            return False

    def delete_project(self, project_id: int) -> bool:
        """
        删除项目（级联删除场景、任务等）

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                project = session.query(Project).filter(Project.id == project_id).first()
                if not project:
                    return False

                session.delete(project)
                self.project_deleted.emit(project_id)
                self.project_list_changed.emit()
                return True

        except Exception as e:
            print(f"删除项目失败: {e}")
            return False

    # ==================== SRT导入 ====================

    def import_srt(self, project_id: int, srt_path: str,
                   grouping_strategy: str = "duration",
                   **kwargs) -> int:
        """
        导入SRT文件并创建场景

        Args:
            project_id: 项目ID
            srt_path: SRT文件路径
            grouping_strategy: 分组策略 (duration, content)
            **kwargs: 其他参数

        Returns:
            导入的场景数量，失败返回-1
        """
        try:
            # 解析SRT文件
            processor = SceneProcessor()
            segments = processor.parse_srt_file(srt_path)

            if not segments:
                print("SRT文件解析失败或为空")
                return -1

            # 分组场景
            scene_groups = processor.group_segments(
                segments,
                strategy=grouping_strategy,
                max_duration=kwargs.get('max_duration', 6.0),
                min_duration=kwargs.get('min_duration', 2.0)
            )

            # 创建场景记录
            with session_scope() as session:
                project = session.query(Project).filter(Project.id == project_id).first()
                if not project:
                    return -1

                # 更新项目源文件信息
                project.source_path = srt_path
                project.source_type = "srt"

                # 创建场景
                total_duration = 0.0
                for idx, group in enumerate(scene_groups):
                    # 合并字幕文本
                    subtitle_text = "\n".join([seg.text for seg in group.segments])

                    # 计算时间
                    start_time = group.segments[0].start if group.segments else "00:00:00,000"
                    end_time = group.segments[-1].end if group.segments else "00:00:00,000"
                    duration = sum(seg.duration for seg in group.segments)
                    total_duration += duration

                    scene = Scene(
                        project_id=project_id,
                        scene_index=idx + 1,
                        name=f"场景 {idx + 1}",
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        subtitle_text=subtitle_text,
                        subtitle_segments=[{
                            'index': seg.index,
                            'start': seg.start,
                            'end': seg.end,
                            'text': seg.text,
                            'duration': seg.duration
                        } for seg in group.segments],
                        ai_tags=group.ai_tags if hasattr(group, 'ai_tags') else {},
                        status="pending"
                    )
                    session.add(scene)

                # 更新项目统计
                project.total_scenes = len(scene_groups)
                project.total_duration = total_duration
                project.completed_scenes = 0

                scene_count = len(scene_groups)
                self.scenes_imported.emit(project_id, scene_count)
                self.project_updated.emit(project_id)

                return scene_count

        except Exception as e:
            print(f"导入SRT失败: {e}")
            import traceback
            traceback.print_exc()
            return -1

    # ==================== 场景操作 ====================

    def get_project_scenes(self, project_id: int) -> List[Dict[str, Any]]:
        """
        获取项目的所有场景

        Args:
            project_id: 项目ID

        Returns:
            场景字典列表
        """
        try:
            with session_scope() as session:
                scenes = session.query(Scene).filter(
                    Scene.project_id == project_id
                ).order_by(Scene.scene_index).all()

                return [s.to_dict() for s in scenes]

        except Exception as e:
            print(f"获取场景列表失败: {e}")
            return []

    def get_scene(self, scene_id: int) -> Optional[Dict[str, Any]]:
        """获取单个场景详情"""
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if scene:
                    return scene.to_dict()
                return None
        except Exception as e:
            print(f"获取场景失败: {e}")
            return None

    def update_scene(self, scene_id: int, **kwargs) -> bool:
        """
        更新场景信息

        Args:
            scene_id: 场景ID
            **kwargs: 要更新的字段

        Returns:
            是否成功
        """
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if not scene:
                    return False

                # 更新允许的字段
                allowed_fields = [
                    'name', 'subtitle_text', 'ai_tags', 'image_prompt',
                    'video_prompt', 'reference_images', 'generated_image_path',
                    'generated_video_path', 'start_frame_path', 'end_frame_path',
                    'start_frame_description', 'end_frame_description',
                    'camera_motion', 'motion_intensity', 'model_used',
                    'generation_params', 'status', 'error_message'
                ]

                for field, value in kwargs.items():
                    if field in allowed_fields and hasattr(scene, field):
                        setattr(scene, field, value)

                return True

        except Exception as e:
            print(f"更新场景失败: {e}")
            return False

    def update_scene_status(self, scene_id: int, status: str,
                            error_message: str = None) -> bool:
        """更新场景状态"""
        kwargs = {'status': status}
        if error_message:
            kwargs['error_message'] = error_message
        return self.update_scene(scene_id, **kwargs)

    def delete_scene(self, scene_id: int) -> bool:
        """删除场景"""
        try:
            with session_scope() as session:
                scene = session.query(Scene).filter(Scene.id == scene_id).first()
                if not scene:
                    return False

                project_id = scene.project_id
                session.delete(scene)

                # 更新项目场景计数
                project = session.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.total_scenes = max(0, project.total_scenes - 1)

                return True

        except Exception as e:
            print(f"删除场景失败: {e}")
            return False

    # ==================== 统计与状态 ====================

    def get_project_stats(self, project_id: int) -> Dict[str, Any]:
        """
        获取项目统计信息

        Returns:
            {
                'total_scenes': int,
                'pending_scenes': int,
                'image_generated': int,
                'video_generated': int,
                'completed_scenes': int,
                'failed_scenes': int,
                'progress': float (0-100)
            }
        """
        try:
            with session_scope() as session:
                scenes = session.query(Scene).filter(
                    Scene.project_id == project_id
                ).all()

                stats = {
                    'total_scenes': len(scenes),
                    'pending_scenes': 0,
                    'image_generated': 0,
                    'video_generated': 0,
                    'completed_scenes': 0,
                    'failed_scenes': 0,
                }

                for scene in scenes:
                    if scene.status == 'pending':
                        stats['pending_scenes'] += 1
                    elif scene.status == 'image_generated':
                        stats['image_generated'] += 1
                    elif scene.status == 'video_generated':
                        stats['video_generated'] += 1
                    elif scene.status == 'completed':
                        stats['completed_scenes'] += 1
                    elif scene.status == 'failed':
                        stats['failed_scenes'] += 1

                # 计算进度
                if stats['total_scenes'] > 0:
                    completed = stats['completed_scenes'] + stats['video_generated']
                    stats['progress'] = (completed / stats['total_scenes']) * 100
                else:
                    stats['progress'] = 0

                return stats

        except Exception as e:
            print(f"获取项目统计失败: {e}")
            return {}

    def update_project_status(self, project_id: int) -> str:
        """
        根据场景状态自动更新项目状态

        Returns:
            更新后的状态
        """
        try:
            stats = self.get_project_stats(project_id)

            if stats['total_scenes'] == 0:
                new_status = 'draft'
            elif stats['completed_scenes'] == stats['total_scenes']:
                new_status = 'completed'
            elif stats['pending_scenes'] == stats['total_scenes']:
                new_status = 'draft'
            else:
                new_status = 'processing'

            self.update_project(project_id, status=new_status,
                                completed_scenes=stats['completed_scenes'])

            return new_status

        except Exception as e:
            print(f"更新项目状态失败: {e}")
            return 'draft'


# 便捷函数
def get_project_controller() -> ProjectController:
    """获取项目控制器单例"""
    return ProjectController()
