"""
涛割 - 数据迁移脚本
将旧 Character/Prop 模型数据迁移到统一 Asset 模型

用法:
    python -m database.migrate_to_asset

注意:
    - 迁移前建议备份 data/ 目录下的 SQLite 数据库
    - 旧表数据保留不删（安全起见），代码引用全部切到 Asset
    - 迁移是幂等的，重复运行会跳过已迁移的记录
"""

from database.session import session_scope
from database.models import Character, Prop, SceneProp, Asset, Scene
from database.models.scene import SceneCharacter


def migrate_characters_to_assets():
    """将 Character 表记录迁移到 Asset 表"""
    migrated = 0
    skipped = 0
    try:
        with session_scope() as session:
            characters = session.query(Character).all()
            for char in characters:
                # 检查是否已迁移（按名称+项目+类型去重）
                existing = session.query(Asset).filter(
                    Asset.name == char.name,
                    Asset.project_id == char.project_id,
                    Asset.asset_type == 'character',
                ).first()
                if existing:
                    skipped += 1
                    continue

                # 构建 visual_attributes
                visual_attrs = {}
                if char.appearance:
                    visual_attrs['appearance'] = char.appearance
                if char.personality:
                    visual_attrs['personality'] = char.personality
                if char.voice_style:
                    visual_attrs['voice_style'] = char.voice_style
                if char.character_type:
                    visual_attrs['character_type'] = char.character_type

                asset = Asset(
                    asset_type='character',
                    name=char.name,
                    project_id=char.project_id,
                    description=char.description,
                    visual_attributes=visual_attrs,
                    reference_images=char.reference_images or [],
                    main_reference_image=char.main_reference_image,
                    consistency_embedding=char.consistency_embedding,
                    is_global=char.is_global,
                    is_active=char.is_active,
                )
                session.add(asset)
                session.flush()

                # 如果角色有服装描述，创建独立的 costume Asset
                if char.clothing:
                    costume = Asset(
                        asset_type='costume',
                        name=f"{char.name}的服装",
                        project_id=char.project_id,
                        description=char.clothing,
                        visual_attributes={
                            'clothing_style': char.clothing,
                        },
                        owner_asset_id=asset.id,
                        is_global=char.is_global,
                        is_active=char.is_active,
                    )
                    session.add(costume)

                migrated += 1

    except Exception as e:
        print(f"迁移角色失败: {e}")

    print(f"角色迁移完成: 迁移 {migrated} 条, 跳过 {skipped} 条")
    return migrated


def migrate_props_to_assets():
    """将 Prop 表记录迁移到 Asset 表"""
    migrated = 0
    skipped = 0
    try:
        with session_scope() as session:
            props = session.query(Prop).all()
            for prop in props:
                existing = session.query(Asset).filter(
                    Asset.name == prop.name,
                    Asset.project_id == prop.project_id,
                    Asset.asset_type == 'prop',
                ).first()
                if existing:
                    skipped += 1
                    continue

                visual_attrs = {}
                if prop.prop_type:
                    visual_attrs['prop_type'] = prop.prop_type

                ref_images = [prop.reference_image] if prop.reference_image else []

                asset = Asset(
                    asset_type='prop',
                    name=prop.name,
                    project_id=prop.project_id,
                    description=prop.description,
                    visual_attributes=visual_attrs,
                    reference_images=ref_images,
                    main_reference_image=prop.reference_image,
                    prompt_description=prop.prompt_description,
                    is_global=prop.is_global,
                    is_active=prop.is_active,
                )
                session.add(asset)
                migrated += 1

    except Exception as e:
        print(f"迁移道具失败: {e}")

    print(f"道具迁移完成: 迁移 {migrated} 条, 跳过 {skipped} 条")
    return migrated


def migrate_scene_associations():
    """将 SceneCharacter/SceneProp 关联迁移到 Scene.bound_assets JSON"""
    updated = 0
    try:
        with session_scope() as session:
            from sqlalchemy.orm.attributes import flag_modified

            scenes = session.query(Scene).all()
            for scene in scenes:
                # 跳过已有 bound_assets 的场景
                if scene.bound_assets:
                    continue

                bindings = []

                # 迁移 SceneCharacter
                scene_chars = session.query(SceneCharacter).filter(
                    SceneCharacter.scene_id == scene.id
                ).all()
                for sc in scene_chars:
                    char = session.query(Character).get(sc.character_id)
                    if not char:
                        continue
                    # 查找对应的 Asset
                    asset = session.query(Asset).filter(
                        Asset.name == char.name,
                        Asset.project_id == char.project_id,
                        Asset.asset_type == 'character',
                    ).first()
                    if asset:
                        bindings.append({
                            'asset_id': asset.id,
                            'type': 'character',
                            'expression': sc.expression,
                            'body_action': sc.body_action,
                        })

                # 迁移 SceneProp
                scene_props = session.query(SceneProp).filter(
                    SceneProp.scene_id == scene.id
                ).all()
                for sp in scene_props:
                    prop = session.query(Prop).get(sp.prop_id)
                    if not prop:
                        continue
                    asset = session.query(Asset).filter(
                        Asset.name == prop.name,
                        Asset.project_id == prop.project_id,
                        Asset.asset_type == 'prop',
                    ).first()
                    if asset:
                        bindings.append({
                            'asset_id': asset.id,
                            'type': 'prop',
                        })

                if bindings:
                    scene.bound_assets = bindings
                    flag_modified(scene, 'bound_assets')
                    updated += 1

    except Exception as e:
        print(f"迁移场景关联失败: {e}")

    print(f"场景关联迁移完成: 更新 {updated} 条场景")
    return updated


def run_migration():
    """执行完整迁移"""
    print("=" * 50)
    print("涛割 - 数据迁移: Character/Prop → Asset")
    print("=" * 50)

    print("\n[1/3] 迁移角色...")
    migrate_characters_to_assets()

    print("\n[2/3] 迁移道具...")
    migrate_props_to_assets()

    print("\n[3/3] 迁移场景关联...")
    migrate_scene_associations()

    print("\n迁移完成！")
    print("注意: 旧表数据已保留，可随时回退。")


if __name__ == '__main__':
    run_migration()
