"""
涛割 - 素材管理控制器（已废弃）
所有方法代理到 AssetController，保持向后兼容。
新代码请直接使用 AssetController。
"""

import os
import shutil
import warnings
from typing import List, Optional, Dict, Any
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from database.session import session_scope
from database.models import Character
from config.settings import SettingsManager


class MaterialController(QObject):
    """
    素材管理控制器（已废弃 — 代理到 AssetController）
    保持向后兼容，内部方法尽可能代理到 AssetController
    """

    # 信号定义（保留兼容）
    character_created = pyqtSignal(int)  # character_id
    character_updated = pyqtSignal(int)
    character_deleted = pyqtSignal(int)
    material_list_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._settings = SettingsManager()
        self._asset_controller = None  # 延迟初始化

    def _get_asset_controller(self):
        """延迟获取 AssetController 实例"""
        if self._asset_controller is None:
            from services.controllers.asset_controller import AssetController
            self._asset_controller = AssetController()
        return self._asset_controller

    @property
    def materials_dir(self) -> Path:
        """素材库目录"""
        return Path(self._settings.settings.materials_dir)

    # ==================== 角色CRUD ====================

    def create_character(self, name: str, character_type: str = "human",
                         **kwargs) -> Optional[Dict[str, Any]]:
        """创建新角色（已废弃，同时写入旧 Character 表和新 Asset 表）"""
        warnings.warn(
            "MaterialController.create_character() 已废弃，请使用 AssetController.create_asset('character', ...)",
            DeprecationWarning, stacklevel=2,
        )
        # 1. 写入旧 Character 表（保持旧流程和测试兼容）
        result = None
        try:
            with session_scope() as session:
                character = Character(
                    name=name,
                    character_type=character_type,
                    description=kwargs.get('description', ''),
                    appearance=kwargs.get('appearance', ''),
                    clothing=kwargs.get('clothing', ''),
                    personality=kwargs.get('personality', ''),
                    voice_style=kwargs.get('voice_style', ''),
                    reference_images=kwargs.get('reference_images', []),
                    main_reference_image=kwargs.get('main_reference_image'),
                    project_id=kwargs.get('project_id'),
                    is_global=kwargs.get('is_global', True),
                )
                session.add(character)
                session.flush()
                result = character.to_dict()
        except Exception as e:
            print(f"创建角色(旧表)失败: {e}")
            return None

        # 2. 同时写入新 Asset 表
        try:
            ac = self._get_asset_controller()
            visual_attrs = {}
            if kwargs.get('appearance'):
                visual_attrs['appearance'] = kwargs['appearance']
            if kwargs.get('personality'):
                visual_attrs['personality'] = kwargs['personality']
            if character_type:
                visual_attrs['character_type'] = character_type

            ac.create_asset(
                asset_type='character',
                name=name,
                project_id=kwargs.get('project_id'),
                description=kwargs.get('description', ''),
                visual_attributes=visual_attrs,
                reference_images=kwargs.get('reference_images', []),
                main_reference_image=kwargs.get('main_reference_image'),
                is_global=kwargs.get('is_global', True),
            )
        except Exception as e:
            print(f"创建角色(Asset表)失败: {e}")

        if result:
            self.character_created.emit(result['id'])
            self.material_list_changed.emit()
        return result

    def get_character(self, character_id: int) -> Optional[Dict[str, Any]]:
        """获取角色详情（先从旧 Character 表查，无结果则从 Asset 表查）"""
        try:
            with session_scope() as session:
                character = session.query(Character).filter(
                    Character.id == character_id
                ).first()
                if character:
                    return character.to_dict()
        except Exception as e:
            print(f"获取角色失败: {e}")

        # fallback: 从 Asset 表查
        ac = self._get_asset_controller()
        result = ac.get_asset(character_id)
        if result:
            va = result.get('visual_attributes') or {}
            result.setdefault('appearance', va.get('appearance', ''))
            result.setdefault('character_type', va.get('character_type', 'human'))
            return result
        return None

    def get_all_characters(self, character_type: str = None,
                           project_id: int = None,
                           include_global: bool = True,
                           active_only: bool = True) -> List[Dict[str, Any]]:
        """获取角色列表"""
        try:
            with session_scope() as session:
                query = session.query(Character)

                if active_only:
                    query = query.filter(Character.is_active == True)

                if character_type:
                    query = query.filter(Character.character_type == character_type)

                if project_id is not None:
                    if include_global:
                        from sqlalchemy import or_
                        query = query.filter(or_(
                            Character.project_id == project_id,
                            Character.is_global == True
                        ))
                    else:
                        query = query.filter(Character.project_id == project_id)

                query = query.order_by(Character.created_at.desc())
                characters = query.all()

                return [c.to_dict() for c in characters]

        except Exception as e:
            print(f"获取角色列表失败: {e}")
            return []

    def update_character(self, character_id: int, **kwargs) -> bool:
        """更新角色信息"""
        try:
            with session_scope() as session:
                character = session.query(Character).filter(
                    Character.id == character_id
                ).first()
                if not character:
                    return False

                allowed_fields = [
                    'name', 'description', 'character_type', 'appearance',
                    'clothing', 'personality', 'voice_style',
                    'reference_images', 'main_reference_image',
                    'consistency_embedding', 'consistency_model',
                    'expression_assets', 'left_hand_assets',
                    'right_hand_assets', 'body_assets',
                    'is_global', 'is_active',
                ]

                for field, value in kwargs.items():
                    if field in allowed_fields and hasattr(character, field):
                        setattr(character, field, value)

                self.character_updated.emit(character_id)
                return True

        except Exception as e:
            print(f"更新角色失败: {e}")
            return False

    def delete_character(self, character_id: int, soft: bool = True) -> bool:
        """删除角色"""
        try:
            with session_scope() as session:
                character = session.query(Character).filter(
                    Character.id == character_id
                ).first()
                if not character:
                    return False

                if soft:
                    character.is_active = False
                else:
                    session.delete(character)

                self.character_deleted.emit(character_id)
                self.material_list_changed.emit()
                return True

        except Exception as e:
            print(f"删除角色失败: {e}")
            return False

    # ==================== 参考图片管理 ====================

    def add_reference_image(self, character_id: int, image_path: str,
                            copy_to_materials: bool = True) -> Optional[str]:
        """为角色添加参考图片"""
        try:
            if not os.path.exists(image_path):
                print(f"图片不存在: {image_path}")
                return None

            stored_path = image_path

            if copy_to_materials:
                char_dir = self.materials_dir / "characters" / str(character_id)
                char_dir.mkdir(parents=True, exist_ok=True)

                filename = os.path.basename(image_path)
                dest_path = char_dir / filename

                counter = 1
                while dest_path.exists():
                    name, ext = os.path.splitext(filename)
                    dest_path = char_dir / f"{name}_{counter}{ext}"
                    counter += 1

                shutil.copy2(image_path, dest_path)
                stored_path = str(dest_path)

            with session_scope() as session:
                character = session.query(Character).filter(
                    Character.id == character_id
                ).first()
                if not character:
                    return None

                images = list(character.reference_images or [])
                images.append(stored_path)
                character.reference_images = images

                if not character.main_reference_image:
                    character.main_reference_image = stored_path

            self.character_updated.emit(character_id)
            return stored_path

        except Exception as e:
            print(f"添加参考图片失败: {e}")
            return None

    def remove_reference_image(self, character_id: int, image_path: str,
                                delete_file: bool = False) -> bool:
        """移除角色参考图片"""
        try:
            with session_scope() as session:
                character = session.query(Character).filter(
                    Character.id == character_id
                ).first()
                if not character:
                    return False

                images = list(character.reference_images or [])
                if image_path in images:
                    images.remove(image_path)
                    character.reference_images = images

                    if character.main_reference_image == image_path:
                        character.main_reference_image = images[0] if images else None

            if delete_file and os.path.exists(image_path):
                os.remove(image_path)

            self.character_updated.emit(character_id)
            return True

        except Exception as e:
            print(f"移除参考图片失败: {e}")
            return False

    def set_main_reference(self, character_id: int, image_path: str) -> bool:
        """设置主参考图"""
        return self.update_character(character_id, main_reference_image=image_path)

    # ==================== 角色搜索 ====================

    def search_characters(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索角色"""
        try:
            with session_scope() as session:
                query = session.query(Character).filter(
                    Character.is_active == True,
                    Character.name.contains(keyword)
                )
                query = query.limit(limit)
                characters = query.all()
                return [c.to_dict() for c in characters]

        except Exception as e:
            print(f"搜索角色失败: {e}")
            return []

    # ==================== 项目角色关联 ====================

    def get_project_characters(self, project_id: int) -> List[Dict[str, Any]]:
        """获取项目的所有角色（包含全局角色）"""
        return self.get_all_characters(project_id=project_id, include_global=True)

    def assign_to_project(self, character_id: int, project_id: int) -> bool:
        """将角色分配到项目"""
        return self.update_character(character_id, project_id=project_id)

    # ==================== 统计 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取素材库统计信息"""
        try:
            with session_scope() as session:
                total = session.query(Character).filter(
                    Character.is_active == True
                ).count()

                by_type = {}
                for char_type in ['human', 'animal', 'creature', 'object', 'background']:
                    count = session.query(Character).filter(
                        Character.is_active == True,
                        Character.character_type == char_type
                    ).count()
                    if count > 0:
                        by_type[char_type] = count

                global_count = session.query(Character).filter(
                    Character.is_active == True,
                    Character.is_global == True
                ).count()

                return {
                    'total': total,
                    'by_type': by_type,
                    'global_count': global_count,
                }

        except Exception as e:
            print(f"获取统计失败: {e}")
            return {'total': 0, 'by_type': {}, 'global_count': 0}


# 便捷函数
def get_material_controller() -> MaterialController:
    """获取素材管理控制器单例"""
    return MaterialController()
