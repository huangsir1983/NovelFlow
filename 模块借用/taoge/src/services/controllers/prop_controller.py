"""
涛割 - 道具控制器（已废弃）
所有方法代理到 AssetController，保持向后兼容。
新代码请直接使用 AssetController。
"""

import warnings
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal

from database.session import session_scope
from database.models import Prop, SceneProp


class PropController(QObject):
    """道具控制器（已废弃 — 代理到 AssetController）"""

    prop_created = pyqtSignal(int)   # prop_id
    prop_updated = pyqtSignal(int)   # prop_id
    prop_deleted = pyqtSignal(int)   # prop_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._asset_controller = None

    def _get_asset_controller(self):
        """延迟获取 AssetController 实例"""
        if self._asset_controller is None:
            from services.controllers.asset_controller import AssetController
            self._asset_controller = AssetController()
        return self._asset_controller

    def create_prop(self, name: str, prop_type: str = "object",
                    project_id: Optional[int] = None, **kwargs) -> Optional[Dict]:
        """创建道具（已废弃，代理到 AssetController）"""
        warnings.warn(
            "PropController.create_prop() 已废弃，请使用 AssetController.create_asset('prop', ...)",
            DeprecationWarning, stacklevel=2,
        )
        ac = self._get_asset_controller()
        visual_attrs = {}
        if prop_type:
            visual_attrs['prop_type'] = prop_type

        result = ac.create_asset(
            asset_type='prop',
            name=name,
            project_id=project_id,
            description=kwargs.get('description'),
            visual_attributes=visual_attrs,
            reference_images=[kwargs['reference_image']] if kwargs.get('reference_image') else [],
            main_reference_image=kwargs.get('reference_image'),
            prompt_description=kwargs.get('prompt_description'),
            is_global=kwargs.get('is_global', False),
        )
        if result:
            self.prop_created.emit(result['id'])
        return result

    def get_all_props(self, project_id: Optional[int] = None,
                      include_global: bool = True) -> List[Dict]:
        """获取道具列表"""
        try:
            with session_scope() as session:
                query = session.query(Prop).filter(Prop.is_active == True)

                if project_id is not None:
                    if include_global:
                        query = query.filter(
                            (Prop.project_id == project_id) | (Prop.is_global == True)
                        )
                    else:
                        query = query.filter(Prop.project_id == project_id)

                props = query.order_by(Prop.name).all()
                return [p.to_dict() for p in props]
        except Exception as e:
            print(f"获取道具列表失败: {e}")
            return []

    def get_project_props(self, project_id: int) -> List[Dict]:
        """获取项目道具"""
        return self.get_all_props(project_id=project_id, include_global=True)

    def update_prop(self, prop_id: int, **kwargs) -> bool:
        """更新道具"""
        try:
            with session_scope() as session:
                prop = session.query(Prop).get(prop_id)
                if not prop:
                    return False

                for key, value in kwargs.items():
                    if hasattr(prop, key):
                        setattr(prop, key, value)

                self.prop_updated.emit(prop_id)
                return True
        except Exception as e:
            print(f"更新道具失败: {e}")
            return False

    def delete_prop(self, prop_id: int, soft: bool = True) -> bool:
        """删除道具"""
        try:
            with session_scope() as session:
                prop = session.query(Prop).get(prop_id)
                if not prop:
                    return False

                if soft:
                    prop.is_active = False
                else:
                    session.delete(prop)

                self.prop_deleted.emit(prop_id)
                return True
        except Exception as e:
            print(f"删除道具失败: {e}")
            return False

    def add_prop_to_scene(self, scene_id: int, prop_id: int,
                          position_x: float = 0.5,
                          position_y: float = 0.5) -> Optional[Dict]:
        """添加道具到场景"""
        try:
            with session_scope() as session:
                # 检查是否已存在
                existing = session.query(SceneProp).filter(
                    SceneProp.scene_id == scene_id,
                    SceneProp.prop_id == prop_id
                ).first()
                if existing:
                    return existing.to_dict()

                sp = SceneProp(
                    scene_id=scene_id,
                    prop_id=prop_id,
                    position_x=position_x,
                    position_y=position_y,
                )
                session.add(sp)
                session.flush()
                return sp.to_dict()
        except Exception as e:
            print(f"添加道具到场景失败: {e}")
            return None

    def remove_prop_from_scene(self, scene_id: int, prop_id: int) -> bool:
        """从场景移除道具"""
        try:
            with session_scope() as session:
                sp = session.query(SceneProp).filter(
                    SceneProp.scene_id == scene_id,
                    SceneProp.prop_id == prop_id
                ).first()
                if sp:
                    session.delete(sp)
                    return True
                return False
        except Exception as e:
            print(f"从场景移除道具失败: {e}")
            return False

    def get_scene_props(self, scene_id: int) -> List[Dict]:
        """获取场景的道具列表"""
        try:
            with session_scope() as session:
                scene_props = session.query(SceneProp).filter(
                    SceneProp.scene_id == scene_id
                ).all()

                result = []
                for sp in scene_props:
                    prop = session.query(Prop).get(sp.prop_id)
                    if prop and prop.is_active:
                        prop_dict = prop.to_dict()
                        prop_dict['scene_prop_id'] = sp.id
                        prop_dict['position_x'] = sp.position_x
                        prop_dict['position_y'] = sp.position_y
                        prop_dict['scale'] = sp.scale
                        result.append(prop_dict)

                return result
        except Exception as e:
            print(f"获取场景道具失败: {e}")
            return []
