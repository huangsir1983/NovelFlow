"""
涛割 - 资产控制器
管理统一资产（Asset）和资产需求（AssetRequirement）的 CRUD、绑定、统计
"""

from typing import Optional, List, Dict

from PyQt6.QtCore import QObject, pyqtSignal

from database.session import session_scope
from database.models import Asset, AssetRequirement, Scene, Project


class AssetController(QObject):
    """资产控制器"""

    asset_created = pyqtSignal(int)        # asset_id
    asset_updated = pyqtSignal(int)        # asset_id
    requirements_extracted = pyqtSignal(list)  # 提取完成后的需求列表
    requirement_fulfilled = pyqtSignal(int)    # requirement_id

    def __init__(self, parent=None):
        super().__init__(parent)

    # ── Asset CRUD ──

    def create_asset(self, asset_type: str, name: str,
                     project_id: Optional[int] = None, **kwargs) -> Optional[Dict]:
        """创建资产"""
        try:
            with session_scope() as session:
                asset = Asset(
                    asset_type=asset_type,
                    name=name,
                    project_id=project_id,
                    description=kwargs.get('description'),
                    visual_attributes=kwargs.get('visual_attributes', {}),
                    tags=kwargs.get('tags', []),
                    era=kwargs.get('era'),
                    reference_images=kwargs.get('reference_images', []),
                    main_reference_image=kwargs.get('main_reference_image'),
                    prompt_description=kwargs.get('prompt_description'),
                    is_global=kwargs.get('is_global', False),
                    # v1.2 新字段
                    visual_anchors=kwargs.get('visual_anchors', []),
                    sora_id=kwargs.get('sora_id'),
                    age_group=kwargs.get('age_group'),
                    gender=kwargs.get('gender'),
                    owner_asset_id=kwargs.get('owner_asset_id'),
                    variant_type=kwargs.get('variant_type'),
                    variant_description=kwargs.get('variant_description'),
                    state_variants=kwargs.get('state_variants', []),
                    multi_angle_images=kwargs.get('multi_angle_images', []),
                    establishing_shot=kwargs.get('establishing_shot'),
                )
                session.add(asset)
                session.flush()
                result = asset.to_dict()
                self.asset_created.emit(asset.id)
                return result
        except Exception as e:
            print(f"创建资产失败: {e}")
            return None

    def get_asset(self, asset_id: int) -> Optional[Dict]:
        """获取单个资产"""
        try:
            with session_scope() as session:
                asset = session.query(Asset).get(asset_id)
                if asset and asset.is_active:
                    return asset.to_dict()
                return None
        except Exception as e:
            print(f"获取资产失败: {e}")
            return None

    def get_assets_by_type(self, asset_type: str,
                           project_id: Optional[int] = None) -> List[Dict]:
        """按类型获取资产列表"""
        try:
            with session_scope() as session:
                query = session.query(Asset).filter(
                    Asset.asset_type == asset_type,
                    Asset.is_active == True,
                )
                if project_id is not None:
                    query = query.filter(
                        (Asset.project_id == project_id) | (Asset.is_global == True)
                    )
                assets = query.order_by(Asset.name).all()
                return [a.to_dict() for a in assets]
        except Exception as e:
            print(f"获取资产列表失败: {e}")
            return []

    def get_all_assets(self, project_id: Optional[int] = None) -> List[Dict]:
        """获取所有资产"""
        try:
            with session_scope() as session:
                query = session.query(Asset).filter(Asset.is_active == True)
                if project_id is not None:
                    query = query.filter(
                        (Asset.project_id == project_id) | (Asset.is_global == True)
                    )
                assets = query.order_by(Asset.asset_type, Asset.name).all()
                return [a.to_dict() for a in assets]
        except Exception as e:
            print(f"获取所有资产失败: {e}")
            return []

    def update_asset(self, asset_id: int, **kwargs) -> bool:
        """更新资产"""
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified
                asset = session.query(Asset).get(asset_id)
                if not asset:
                    return False
                # JSON 类型列名集合 — setattr 后需要 flag_modified 确保 dirty
                _json_cols = {
                    'visual_attributes', 'tags', 'reference_images',
                    'visual_anchors', 'state_variants', 'multi_angle_images',
                }
                for key, value in kwargs.items():
                    if hasattr(asset, key):
                        setattr(asset, key, value)
                        if key in _json_cols:
                            flag_modified(asset, key)
            # emit 必须在 session commit 之后，否则监听者读到的是旧数据
            self.asset_updated.emit(asset_id)
            return True
        except Exception as e:
            print(f"更新资产失败: {e}")
            return False

    def delete_asset(self, asset_id: int, soft: bool = True) -> bool:
        """删除资产"""
        try:
            with session_scope() as session:
                asset = session.query(Asset).get(asset_id)
                if not asset:
                    return False
                if soft:
                    asset.is_active = False
                else:
                    session.delete(asset)
                return True
        except Exception as e:
            print(f"删除资产失败: {e}")
            return False

    def search_assets(self, keyword: str,
                      asset_type: Optional[str] = None,
                      project_id: Optional[int] = None) -> List[Dict]:
        """搜索资产"""
        try:
            with session_scope() as session:
                query = session.query(Asset).filter(
                    Asset.is_active == True,
                    Asset.name.contains(keyword),
                )
                if asset_type:
                    query = query.filter(Asset.asset_type == asset_type)
                if project_id is not None:
                    query = query.filter(
                        (Asset.project_id == project_id) | (Asset.is_global == True)
                    )
                assets = query.order_by(Asset.name).all()
                return [a.to_dict() for a in assets]
        except Exception as e:
            print(f"搜索资产失败: {e}")
            return []

    # ── AssetRequirement CRUD ──

    def save_requirements(self, project_id: int,
                          requirements: list) -> List[Dict]:
        """保存资产需求列表（替换该项目的所有需求）"""
        try:
            with session_scope() as session:
                # 清除旧需求
                session.query(AssetRequirement).filter(
                    AssetRequirement.project_id == project_id
                ).delete()

                results = []
                for req in requirements:
                    ar = AssetRequirement(
                        project_id=project_id,
                        requirement_type=req.get('requirement_type', ''),
                        name=req.get('name', ''),
                        attributes=req.get('attributes', {}),
                        scene_indices=req.get('scene_indices', []),
                        source_text_excerpts=req.get('source_text_excerpts', []),
                        card_pos_x=req.get('card_pos_x'),
                        card_pos_y=req.get('card_pos_y'),
                    )
                    session.add(ar)
                    session.flush()
                    results.append(ar.to_dict())

                self.requirements_extracted.emit(results)
                return results
        except Exception as e:
            print(f"保存资产需求失败: {e}")
            return []

    def get_requirements(self, project_id: int,
                         req_type: Optional[str] = None) -> List[Dict]:
        """获取项目的资产需求"""
        try:
            with session_scope() as session:
                query = session.query(AssetRequirement).filter(
                    AssetRequirement.project_id == project_id
                )
                if req_type:
                    query = query.filter(
                        AssetRequirement.requirement_type == req_type
                    )
                reqs = query.order_by(
                    AssetRequirement.requirement_type,
                    AssetRequirement.name,
                ).all()
                return [r.to_dict() for r in reqs]
        except Exception as e:
            print(f"获取资产需求失败: {e}")
            return []

    def clear_requirements(self, project_id: int) -> bool:
        """清除项目的所有资产需求"""
        try:
            with session_scope() as session:
                session.query(AssetRequirement).filter(
                    AssetRequirement.project_id == project_id
                ).delete()
                return True
        except Exception as e:
            print(f"清除资产需求失败: {e}")
            return False

    def delete_requirement(self, requirement_id: int) -> bool:
        """删除单条资产需求"""
        try:
            with session_scope() as session:
                req = session.query(AssetRequirement).get(requirement_id)
                if not req:
                    return False
                session.delete(req)
                return True
        except Exception as e:
            print(f"删除资产需求失败: {e}")
            return False

    def add_single_requirement(self, project_id: int,
                                req_data: dict) -> Optional[Dict]:
        """单条新增资产需求（不清除现有需求）"""
        try:
            with session_scope() as session:
                ar = AssetRequirement(
                    project_id=project_id,
                    requirement_type=req_data.get('requirement_type', ''),
                    name=req_data.get('name', ''),
                    attributes=req_data.get('attributes', {}),
                    scene_indices=req_data.get('scene_indices', []),
                    source_text_excerpts=req_data.get('source_text_excerpts', []),
                    card_pos_x=req_data.get('card_pos_x'),
                    card_pos_y=req_data.get('card_pos_y'),
                )
                session.add(ar)
                session.flush()
                return ar.to_dict()
        except Exception as e:
            print(f"新增单条资产需求失败: {e}")
            return None

    def update_requirement_attributes(self, requirement_id: int,
                                       attributes: dict,
                                       scene_indices: Optional[list] = None,
                                       source_text_excerpts: Optional[list] = None) -> Optional[Dict]:
        """AI补全后更新需求属性（flag_modified for JSON fields）"""
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified
                req = session.query(AssetRequirement).get(requirement_id)
                if not req:
                    return None
                # 合并属性（保留已有值，新值覆盖）
                existing = dict(req.attributes or {})
                existing.update(attributes)
                req.attributes = existing
                flag_modified(req, 'attributes')

                if scene_indices is not None:
                    req.scene_indices = scene_indices
                    flag_modified(req, 'scene_indices')

                if source_text_excerpts is not None:
                    existing_excerpts = list(req.source_text_excerpts or [])
                    for exc in source_text_excerpts:
                        if exc and exc not in existing_excerpts:
                            existing_excerpts.append(exc)
                    req.source_text_excerpts = existing_excerpts
                    flag_modified(req, 'source_text_excerpts')

                return req.to_dict()
        except Exception as e:
            print(f"更新资产需求属性失败: {e}")
            return None

    # ── 绑定 ──

    def bind_asset_to_requirement(self, requirement_id: int,
                                   asset_id: int) -> bool:
        """将资产绑定到需求"""
        try:
            with session_scope() as session:
                req = session.query(AssetRequirement).get(requirement_id)
                if not req:
                    return False
                req.bound_asset_id = asset_id
                req.is_fulfilled = True
                self.requirement_fulfilled.emit(requirement_id)
                return True
        except Exception as e:
            print(f"绑定资产失败: {e}")
            return False

    def unbind_requirement(self, requirement_id: int) -> bool:
        """解除需求的资产绑定"""
        try:
            with session_scope() as session:
                req = session.query(AssetRequirement).get(requirement_id)
                if not req:
                    return False
                req.bound_asset_id = None
                req.is_fulfilled = False
                return True
        except Exception as e:
            print(f"解绑资产失败: {e}")
            return False

    def fulfill_requirement(self, requirement_id: int,
                            image_path: Optional[str] = None) -> bool:
        """标记需求为已完成（生成图片后调用）"""
        try:
            with session_scope() as session:
                req = session.query(AssetRequirement).get(requirement_id)
                if not req:
                    return False
                req.is_fulfilled = True
                if image_path:
                    req.generated_image_path = image_path
                self.requirement_fulfilled.emit(requirement_id)
                return True
        except Exception as e:
            print(f"完成需求失败: {e}")
            return False

    # ── 统计 ──

    def get_fulfillment_stats(self, project_id: int) -> Dict:
        """获取需求完成统计"""
        try:
            with session_scope() as session:
                reqs = session.query(AssetRequirement).filter(
                    AssetRequirement.project_id == project_id
                ).all()
                total = len(reqs)
                fulfilled = sum(1 for r in reqs if r.is_fulfilled)
                by_type = {}
                for t in ('character', 'scene_bg', 'prop', 'lighting_ref'):
                    type_reqs = [r for r in reqs if r.requirement_type == t]
                    type_fulfilled = sum(1 for r in type_reqs if r.is_fulfilled)
                    by_type[t] = {
                        'total': len(type_reqs),
                        'fulfilled': type_fulfilled,
                    }
                return {
                    'total': total,
                    'fulfilled': fulfilled,
                    'percentage': round(fulfilled / total * 100, 1) if total > 0 else 0,
                    'by_type': by_type,
                }
        except Exception as e:
            print(f"获取统计失败: {e}")
            return {'total': 0, 'fulfilled': 0, 'percentage': 0, 'by_type': {}}

    # ── 位置持久化 ──

    def update_requirement_card_pos(self, requirement_id: int,
                                     x: float, y: float) -> bool:
        """更新需求卡片的画布位置"""
        try:
            with session_scope() as session:
                req = session.query(AssetRequirement).get(requirement_id)
                if not req:
                    return False
                req.card_pos_x = x
                req.card_pos_y = y
                return True
        except Exception as e:
            print(f"更新卡片位置失败: {e}")
            return False

    def update_requirement_multi_angle(self, requirement_id: int,
                                        paths: list) -> bool:
        """将多视角图片路径写入 AssetRequirement.attributes['multi_angle_paths']"""
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified
                req = session.query(AssetRequirement).get(requirement_id)
                if not req:
                    return False
                attrs = dict(req.attributes or {})
                attrs['multi_angle_paths'] = paths
                req.attributes = attrs
                flag_modified(req, 'attributes')
                return True
        except Exception as e:
            print(f"更新多视角图片路径失败: {e}")
            return False

    # ── 变体连接 ──

    def set_variant_link(self, variant_req_id: int, base_req_id: int) -> bool:
        """将 linked_base_req_id 写入变体 AssetRequirement 的 attributes JSON"""
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified
                req = session.query(AssetRequirement).get(variant_req_id)
                if not req:
                    return False
                attrs = dict(req.attributes or {})
                attrs['linked_base_req_id'] = base_req_id
                req.attributes = attrs
                flag_modified(req, 'attributes')
                return True
        except Exception as e:
            print(f"设置变体连接失败: {e}")
            return False

    # ── 同步到资产库（旧版已合并到下方完整版） ──

    def sync_fulfilled_requirements(self, project_id: int) -> List[Dict]:
        """向后兼容别名"""
        return self.sync_requirements_to_assets(project_id)

    def get_assets_for_scene(self, project_id: int,
                              scene_index: int) -> List[Dict]:
        """
        获取指定 scene_index 关联的所有已绑定资产。
        通过 AssetRequirement.scene_indices（JSON 数组）在 Python 端过滤。
        """
        try:
            with session_scope() as session:
                reqs = session.query(AssetRequirement).filter(
                    AssetRequirement.project_id == project_id,
                    AssetRequirement.bound_asset_id.isnot(None),
                ).all()

                # Python 端过滤 scene_index in scene_indices
                asset_ids = set()
                for req in reqs:
                    indices = req.scene_indices or []
                    if scene_index in indices:
                        asset_ids.add(req.bound_asset_id)

                if not asset_ids:
                    return []

                assets = session.query(Asset).filter(
                    Asset.id.in_(asset_ids),
                    Asset.is_active == True,
                ).all()
                return [a.to_dict() for a in assets]
        except Exception as e:
            print(f"获取场景关联资产失败: {e}")
            return []

    def clear_variant_link(self, variant_req_id: int) -> bool:
        """移除变体 AssetRequirement 的 linked_base_req_id"""
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified
                req = session.query(AssetRequirement).get(variant_req_id)
                if not req:
                    return False
                attrs = dict(req.attributes or {})
                attrs.pop('linked_base_req_id', None)
                req.attributes = attrs
                flag_modified(req, 'attributes')
                return True
        except Exception as e:
            print(f"清除变体连接失败: {e}")
            return False

    # ── 服装相关 ──

    def get_character_variants(self, base_asset_id: int) -> List[Dict]:
        """获取角色的所有衍生形象资产"""
        try:
            with session_scope() as session:
                variants = session.query(Asset).filter(
                    Asset.owner_asset_id == base_asset_id,
                    Asset.is_active == True,
                ).order_by(Asset.name).all()
                return [v.to_dict() for v in variants]
        except Exception as e:
            print(f"获取角色衍生形象失败: {e}")
            return []

    def create_character_variant(self, base_asset_id: int,
                                  variant_type: str,
                                  variant_description: str,
                                  **kwargs) -> Optional[Dict]:
        """创建角色衍生形象"""
        try:
            with session_scope() as session:
                base = session.query(Asset).get(base_asset_id)
                if not base or base.asset_type != 'character':
                    return None
                asset = Asset(
                    asset_type='character',
                    name=kwargs.get('name', f"{base.name}（衍生）"),
                    project_id=base.project_id,
                    owner_asset_id=base_asset_id,
                    variant_type=variant_type,
                    variant_description=variant_description,
                    description=kwargs.get('description', variant_description),
                    visual_attributes=kwargs.get('visual_attributes', base.visual_attributes or {}),
                    tags=kwargs.get('tags', base.tags or []),
                    era=base.era,
                    visual_anchors=kwargs.get('visual_anchors', base.visual_anchors or []),
                    age_group=kwargs.get('age_group', base.age_group),
                    gender=kwargs.get('gender', base.gender),
                )
                session.add(asset)
                session.flush()
                result = asset.to_dict()
                self.asset_created.emit(asset.id)
                return result
        except Exception as e:
            print(f"创建角色衍生形象失败: {e}")
            return None

    # 向后兼容
    def get_costumes_for_character(self, character_asset_id: int) -> List[Dict]:
        """向后兼容：获取角色关联的服装资产 → 实际返回衍生形象"""
        return self.get_character_variants(character_asset_id)

    def create_costume(self, name: str, owner_asset_id: int, **kwargs) -> Optional[Dict]:
        """向后兼容：创建服装 → 实际创建 costume_variant 衍生"""
        return self.create_character_variant(
            base_asset_id=owner_asset_id,
            variant_type='costume_variant',
            variant_description=kwargs.get('description', ''),
            name=name,
            **{k: v for k, v in kwargs.items() if k != 'description'},
        )

    # ── 场景绑定增强 ──

    def bind_assets_to_scene(self, scene_id: int, bindings: List[Dict]) -> bool:
        """批量绑定资产到分镜（写入 Scene.bound_assets）
        bindings: [{"asset_id": 1, "type": "character"}, ...]
        """
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified
                scene = session.query(Scene).get(scene_id)
                if not scene:
                    return False
                scene.bound_assets = bindings
                flag_modified(scene, 'bound_assets')
                return True
        except Exception as e:
            print(f"绑定资产到场景失败: {e}")
            return False

    def auto_bind_from_requirements(self, project_id: int) -> Dict:
        """将所有需求绑定到对应分镜
        遍历所有需求（包括未生成图片的），按 scene_indices 写入各 Scene.bound_assets
        返回 {"bound_count": N, "unbound_count": M}
        """
        bound_count = 0
        unbound_count = 0
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified

                # 获取所有需求（不再要求 is_fulfilled 和 bound_asset_id）
                reqs = session.query(AssetRequirement).filter(
                    AssetRequirement.project_id == project_id,
                ).all()

                if not reqs:
                    return {'bound_count': 0, 'unbound_count': 0}

                # 按 scene_index 聚合需求
                scene_bindings = {}  # {scene_index: [binding_dict, ...]}
                for req in reqs:
                    indices = req.scene_indices or []
                    binding = {
                        'type': req.requirement_type,
                        'name': req.name,
                    }
                    # 优先使用 asset_id，没有则用 requirement_id 作为标识
                    if req.bound_asset_id:
                        binding['asset_id'] = req.bound_asset_id
                        # 从 Asset 取图片路径
                        asset = session.query(Asset).get(req.bound_asset_id)
                        if asset and asset.main_reference_image:
                            binding['image_path'] = asset.main_reference_image
                    else:
                        binding['requirement_id'] = req.id
                        # 从需求取已生成图片路径
                        if req.generated_image_path:
                            binding['image_path'] = req.generated_image_path

                    # 衍生角色的基础角色名（从 attributes 中获取）
                    req_attrs = req.attributes or {}
                    base_name = req_attrs.get('base_character_name', '')
                    if base_name:
                        binding['base_character_name'] = base_name

                    # 如果是衍生角色且有绑定资产，查找基础角色的 asset_id
                    if req_attrs.get('is_variant') and req.bound_asset_id:
                        asset = session.query(Asset).get(req.bound_asset_id)
                        if asset and asset.owner_asset_id:
                            binding['owner_asset_id'] = asset.owner_asset_id
                    for idx in indices:
                        if idx not in scene_bindings:
                            scene_bindings[idx] = []
                        scene_bindings[idx].append(binding)

                # 更新各 Scene 的 bound_assets
                scenes = session.query(Scene).filter(
                    Scene.project_id == project_id,
                ).all()

                for scene in scenes:
                    bindings = scene_bindings.get(scene.scene_index, [])
                    if bindings:
                        # 合并现有绑定（避免覆盖手动绑定）
                        existing = list(scene.bound_assets or [])
                        existing_ids = set()
                        for b in existing:
                            if b.get('asset_id'):
                                existing_ids.add(('asset', b['asset_id']))
                            elif b.get('requirement_id'):
                                existing_ids.add(('req', b['requirement_id']))
                        for b in bindings:
                            key = None
                            if b.get('asset_id'):
                                key = ('asset', b['asset_id'])
                            elif b.get('requirement_id'):
                                key = ('req', b['requirement_id'])
                            if key and key not in existing_ids:
                                existing.append(b)
                                existing_ids.add(key)
                                bound_count += 1
                        scene.bound_assets = existing
                        flag_modified(scene, 'bound_assets')
                    else:
                        unbound_count += 1

        except Exception as e:
            print(f"自动绑定资产失败: {e}")

        return {'bound_count': bound_count, 'unbound_count': unbound_count}

    # ── 同步增强 ──

    def sync_requirements_to_assets(self, project_id: int) -> List[Dict]:
        """
        将已完成(is_fulfilled=True)的资产需求同步到 Asset 表。
        同步后自动调用 auto_bind_from_requirements。
        """
        synced = []
        try:
            with session_scope() as session:
                from sqlalchemy.orm.attributes import flag_modified
                reqs = session.query(AssetRequirement).filter(
                    AssetRequirement.project_id == project_id,
                    AssetRequirement.is_fulfilled == True,
                ).all()

                for req in reqs:
                    img_path = req.generated_image_path or ''
                    attrs = req.attributes or {}
                    multi_angle_paths = attrs.get('multi_angle_paths', [])

                    if req.bound_asset_id:
                        # 更新已绑定的 Asset
                        asset = session.query(Asset).get(req.bound_asset_id)
                        if asset and img_path and asset.main_reference_image != img_path:
                            asset.main_reference_image = img_path
                            ref_imgs = list(asset.reference_images or [])
                            if img_path not in ref_imgs:
                                ref_imgs.append(img_path)
                                asset.reference_images = ref_imgs
                                flag_modified(asset, 'reference_images')
                            synced.append(asset.to_dict())
                        elif asset:
                            synced.append(asset.to_dict())
                        # 同步提示词
                        if asset:
                            saved_prompt = attrs.get('prompt_description', '')
                            if saved_prompt:
                                asset.prompt_description = saved_prompt
                        # 同步多视角图片
                        if asset and multi_angle_paths:
                            from services.multi_angle_batch_service import ANGLE_LABELS
                            angle_list = [
                                {"angle": ANGLE_LABELS[i] if i < len(ANGLE_LABELS) else f"视角{i+1}", "path": p}
                                for i, p in enumerate(multi_angle_paths)
                            ]
                            asset.multi_angle_images = angle_list
                            flag_modified(asset, 'multi_angle_images')
                    else:
                        # 创建新 Asset
                        ref_imgs = [img_path] if img_path else []
                        attrs = req.attributes or {}
                        multi_angle_paths = attrs.get('multi_angle_paths', [])
                        if multi_angle_paths:
                            from services.multi_angle_batch_service import ANGLE_LABELS
                            angle_list = [
                                {"angle": ANGLE_LABELS[i] if i < len(ANGLE_LABELS) else f"视角{i+1}", "path": p}
                                for i, p in enumerate(multi_angle_paths)
                            ]
                        else:
                            angle_list = []

                        asset = Asset(
                            asset_type=req.requirement_type,
                            name=req.name,
                            project_id=project_id,
                            visual_attributes=attrs,
                            main_reference_image=img_path or None,
                            reference_images=ref_imgs,
                            prompt_description=attrs.get('prompt_description') or req.name,
                            # v1.2: 衍生角色外键
                            owner_asset_id=self._find_owner_asset_id(
                                session, project_id, attrs.get('base_character_name', '')
                            ) if attrs.get('is_variant') else None,
                            variant_type=attrs.get('variant_type'),
                            variant_description=attrs.get('variant_description'),
                            state_variants=attrs.get('state_variants', []),
                            multi_angle_images=angle_list,
                            # v1.2: 角色特有字段
                            visual_anchors=attrs.get('visual_anchors', []),
                            age_group=attrs.get('age_group'),
                            gender=attrs.get('gender'),
                        )
                        session.add(asset)
                        session.flush()
                        req.bound_asset_id = asset.id
                        synced.append(asset.to_dict())
        except Exception as e:
            import traceback
            print(f"同步资产需求到资产库失败: {e}\n{traceback.format_exc()}")

        # 同步完成后自动绑定到分镜（无论是否有新同步的资产，都执行绑定）
        self.auto_bind_from_requirements(project_id)

        return synced

    def _find_owner_asset_id(self, session, project_id: int, owner_name: str) -> Optional[int]:
        """根据角色名在 Asset 表中查找角色资产 ID"""
        if not owner_name:
            return None
        asset = session.query(Asset).filter(
            Asset.project_id == project_id,
            Asset.asset_type == 'character',
            Asset.name == owner_name,
            Asset.is_active == True,
        ).first()
        return asset.id if asset else None

    # ── 生成时资产组装 ──

    def assemble_generation_context(self, project_id: int, scene_index: int) -> Dict:
        """组装完整的生成上下文（供图片/视频生成调用）"""
        context = {
            'characters': [],
            'scene_bg': None,
            'props': [],
            'lighting': None,
            'cinematography': None,
            'continuity': None,
            'prompt_segments': {
                'character_segment': '',
                'scene_segment': '',
                'prop_segment': '',
                'lighting_segment': '',
                'negative_prompt': '',
            },
        }
        try:
            with session_scope() as session:
                # 获取场景
                scene = session.query(Scene).filter(
                    Scene.project_id == project_id,
                    Scene.scene_index == scene_index,
                ).first()

                if not scene:
                    return context

                # 获取项目
                project = session.query(Project).get(project_id)

                # 从 bound_assets 读取绑定的资产
                bound = scene.bound_assets or []
                asset_ids = [b.get('asset_id') for b in bound if b.get('asset_id')]
                assets_map = {}
                if asset_ids:
                    assets = session.query(Asset).filter(
                        Asset.id.in_(asset_ids),
                        Asset.is_active == True,
                    ).all()
                    assets_map = {a.id: a for a in assets}

                char_descs = []
                prop_descs = []

                for binding in bound:
                    aid = binding.get('asset_id')
                    asset = assets_map.get(aid)
                    if not asset:
                        continue

                    a_dict = asset.to_dict()

                    if asset.asset_type == 'character':
                        char_info = {
                            'name': asset.name,
                            'prompt_desc': asset.prompt_description or asset.description or '',
                            'ref_images': asset.reference_images or [],
                            'visual_anchors': asset.visual_anchors or [],
                            'visual_attributes': asset.visual_attributes or {},
                        }
                        context['characters'].append(char_info)
                        desc_parts = [asset.name]
                        if asset.prompt_description:
                            desc_parts.append(asset.prompt_description)
                        elif asset.description:
                            desc_parts.append(asset.description)
                        va = asset.visual_attributes or {}
                        if va.get('appearance'):
                            desc_parts.append(va['appearance'])
                        # 衍生角色（costume_variant）的服装描述合并到角色段
                        if asset.variant_type == 'costume_variant':
                            clothing = va.get('clothing_style', '')
                            if clothing:
                                desc_parts.append(f"穿着{clothing}")
                        char_descs.append('，'.join(desc_parts))

                    elif asset.asset_type == 'scene_bg':
                        context['scene_bg'] = {
                            'name': asset.name,
                            'prompt_desc': asset.prompt_description or asset.description or '',
                            'ref_images': asset.reference_images or [],
                        }

                    elif asset.asset_type == 'prop':
                        context['props'].append({
                            'name': asset.name,
                            'prompt_desc': asset.prompt_description or asset.description or '',
                        })
                        prop_descs.append(asset.name)

                # 如果没有从 bound_assets 找到场景，用 AssetRequirement 回退
                if not context['scene_bg']:
                    reqs = session.query(AssetRequirement).filter(
                        AssetRequirement.project_id == project_id,
                        AssetRequirement.requirement_type == 'scene_bg',
                        AssetRequirement.bound_asset_id.isnot(None),
                    ).all()
                    for req in reqs:
                        indices = req.scene_indices or []
                        if scene_index in indices:
                            a = session.query(Asset).get(req.bound_asset_id)
                            if a and a.is_active:
                                context['scene_bg'] = {
                                    'name': a.name,
                                    'prompt_desc': a.prompt_description or a.description or '',
                                    'ref_images': a.reference_images or [],
                                }
                                break

                # 项目级视觉圣经
                if project:
                    context['lighting'] = project.lighting_bible
                    context['cinematography'] = project.cinematography_guide
                    context['continuity'] = project.continuity_bible

                # 构建 prompt_segments
                context['prompt_segments']['character_segment'] = '；'.join(char_descs) if char_descs else ''
                context['prompt_segments']['prop_segment'] = '、'.join(prop_descs) if prop_descs else ''

                if context['scene_bg']:
                    context['prompt_segments']['scene_segment'] = context['scene_bg'].get('prompt_desc', '')

                # 光线描述
                if project and project.lighting_bible:
                    lb = project.lighting_bible
                    context['prompt_segments']['lighting_segment'] = lb.get('default_lighting', '')

                # Visual Anchors → negative prompt
                anchors = []
                for ch in context['characters']:
                    anchors.extend(ch.get('visual_anchors', []))
                if anchors:
                    context['prompt_segments']['negative_prompt'] = (
                        '不要改变以下特征：' + '、'.join(anchors)
                    )

        except Exception as e:
            print(f"组装生成上下文失败: {e}")

        return context
