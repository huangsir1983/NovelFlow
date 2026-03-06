"""
涛割 - 场次控制器
管理 Act（大场景/场次）的 CRUD + 分镜拆分
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtCore import QObject, pyqtSignal

from database import session_scope, Act, Scene, Project


class ActController(QObject):
    """场次控制器"""

    acts_changed = pyqtSignal(int)  # project_id

    def __init__(self, parent=None):
        super().__init__(parent)

    def create_acts_from_ai(self, project_id: int, act_data_list: List[Dict]) -> List[Dict]:
        """
        根据 AI 拆分结果批量创建 Act

        Args:
            project_id: 项目 ID
            act_data_list: AI 返回的场次列表
                [{"title": "...", "summary": "...", "source_text_range": [s, e],
                  "rhythm_label": "...", "tags": [...]}]

        Returns:
            创建后的 Act dict 列表
        """
        results = []
        with session_scope() as session:
            # 清除该项目旧的 acts
            session.query(Act).filter(Act.project_id == project_id).delete()

            for i, data in enumerate(act_data_list):
                act = Act(
                    project_id=project_id,
                    act_index=i,
                    title=data.get('title', f'场次 {i + 1}'),
                    summary=data.get('summary', ''),
                    source_text_range=data.get('source_text_range'),
                    tags=data.get('tags', []),
                    rhythm_label=data.get('rhythm_label', ''),
                    target_duration=data.get('target_duration', 0.0),
                    status='analyzed',
                )
                session.add(act)
                session.flush()
                results.append(act.to_dict())

        self.acts_changed.emit(project_id)
        return results

    def get_project_acts(self, project_id: int) -> List[Dict]:
        """获取项目所有场次"""
        with session_scope() as session:
            acts = session.query(Act).filter(
                Act.project_id == project_id
            ).order_by(Act.act_index).all()
            return [a.to_dict() for a in acts]

    def get_act_scenes(self, act_id: int) -> List[Dict]:
        """获取某场次下的所有分镜(Scene)"""
        with session_scope() as session:
            scenes = session.query(Scene).filter(
                Scene.act_id == act_id
            ).order_by(Scene.scene_index).all()
            return [s.to_dict() for s in scenes]

    def update_act(self, act_id: int, **kwargs) -> bool:
        """更新场次属性"""
        with session_scope() as session:
            act = session.query(Act).get(act_id)
            if not act:
                return False
            for key, value in kwargs.items():
                if hasattr(act, key):
                    setattr(act, key, value)
            project_id = act.project_id
        self.acts_changed.emit(project_id)
        return True

    def merge_acts(self, project_id: int, act_ids: List[int]) -> Optional[int]:
        """
        合并多个场次为一个

        Returns:
            合并后的 act_id，失败返回 None
        """
        if len(act_ids) < 2:
            return None

        with session_scope() as session:
            acts = session.query(Act).filter(
                Act.id.in_(act_ids),
                Act.project_id == project_id
            ).order_by(Act.act_index).all()

            if len(acts) < 2:
                return None

            # 保留第一个，合并信息
            primary = acts[0]
            merged_summary_parts = [primary.summary or '']
            merged_tags = list(primary.tags or [])

            for act in acts[1:]:
                if act.summary:
                    merged_summary_parts.append(act.summary)
                merged_tags.extend(act.tags or [])
                # 将子场次的 scenes 移到 primary
                session.query(Scene).filter(Scene.act_id == act.id).update(
                    {Scene.act_id: primary.id}
                )
                session.delete(act)

            primary.summary = '\n'.join(p for p in merged_summary_parts if p)
            primary.tags = list(set(merged_tags))

            # 重排 source_text_range
            if primary.source_text_range and acts[-1].source_text_range:
                primary.source_text_range = [
                    primary.source_text_range[0],
                    acts[-1].source_text_range[1]
                ]

            session.flush()
            result_id = primary.id

            # 重排序
            self._reindex_acts(session, project_id)

        self.acts_changed.emit(project_id)
        return result_id

    def split_act(self, act_id: int, split_after_scene_index: int) -> Optional[tuple]:
        """
        拆分场次：在 split_after_scene_index 之后断开

        Returns:
            (act_id_1, act_id_2) 或 None
        """
        with session_scope() as session:
            act = session.query(Act).get(act_id)
            if not act:
                return None

            scenes = session.query(Scene).filter(
                Scene.act_id == act_id
            ).order_by(Scene.scene_index).all()

            if split_after_scene_index < 0 or split_after_scene_index >= len(scenes) - 1:
                return None

            project_id = act.project_id

            # 创建新 Act
            new_act = Act(
                project_id=project_id,
                act_index=act.act_index + 1,
                title=f"{act.title or '场次'} (续)",
                summary='',
                status='analyzed',
            )
            session.add(new_act)
            session.flush()

            # 后半部分 scenes 移到新 act
            for scene in scenes[split_after_scene_index + 1:]:
                scene.act_id = new_act.id

            self._reindex_acts(session, project_id)
            result = (act.id, new_act.id)

        self.acts_changed.emit(project_id)
        return result

    def reorder_acts(self, project_id: int, act_ids_in_order: List[int]) -> bool:
        """重新排序场次"""
        with session_scope() as session:
            for i, aid in enumerate(act_ids_in_order):
                act = session.query(Act).get(aid)
                if act and act.project_id == project_id:
                    act.act_index = i

        self.acts_changed.emit(project_id)
        return True

    def skip_act(self, act_id: int, skip: bool) -> bool:
        """设置场次跳过状态"""
        return self.update_act(act_id, is_skipped=skip)

    def delete_act(self, act_id: int) -> bool:
        """删除场次及其关联 scenes 的 act_id"""
        with session_scope() as session:
            act = session.query(Act).get(act_id)
            if not act:
                return False
            project_id = act.project_id
            # 解除 scenes 的关联（不删除 scenes）
            session.query(Scene).filter(Scene.act_id == act_id).update(
                {Scene.act_id: None}
            )
            session.delete(act)
            self._reindex_acts(session, project_id)

        self.acts_changed.emit(project_id)
        return True

    def split_act_into_shots(self, act_id: int, shot_data_list: List[Dict]) -> List[Dict]:
        """
        将 AI 拆分的分镜数据写入 Scene 表

        Args:
            act_id: 场次 ID
            shot_data_list: 分镜列表
                基础字段: subtitle_text, duration, shot_label, scene_type
                导演指令字段（可选）: image_prompt, camera_motion, visual_prompt_struct,
                    audio_config, generation_params

        Returns:
            创建的 Scene dict 列表
        """
        results = []
        with session_scope() as session:
            act = session.query(Act).get(act_id)
            if not act:
                return []

            project_id = act.project_id

            # 先删除该场次下的旧分镜记录（避免重复累积）
            session.query(Scene).filter(
                Scene.act_id == act_id
            ).delete()

            # 找到当前项目最大 scene_index（排除已删除的本场次分镜）
            max_idx = session.query(Scene.scene_index).filter(
                Scene.project_id == project_id
            ).order_by(Scene.scene_index.desc()).first()
            next_index = (max_idx[0] + 1) if max_idx else 0

            for i, data in enumerate(shot_data_list):
                scene = Scene(
                    project_id=project_id,
                    act_id=act_id,
                    scene_index=next_index + i,
                    subtitle_text=data.get('subtitle_text', ''),
                    duration=data.get('duration', 10.0),
                    shot_label=data.get('shot_label', ''),
                    scene_type=data.get('scene_type', 'normal'),
                    status='pending',
                    # 导演指令字段（AI 拆分时填充，快速拆分时为 None）
                    image_prompt=data.get('image_prompt'),
                    video_prompt=data.get('video_prompt'),
                    camera_motion=data.get('camera_motion', '静止'),
                    visual_prompt_struct=data.get('visual_prompt_struct'),
                    audio_config=data.get('audio_config'),
                    generation_params=data.get('generation_params'),
                    # v1.2 增强字段
                    scene_environment=data.get('scene_environment'),
                    shot_size=data.get('shot_size'),
                    character_actions=data.get('character_actions'),
                    atmosphere=data.get('atmosphere'),
                    is_empty_shot=data.get('is_empty_shot', False),
                    continuity_notes=data.get('continuity_notes'),
                    interaction_desc=data.get('interaction_desc'),
                )
                session.add(scene)
                session.flush()
                results.append(scene.to_dict())

            # 更新 act 状态
            act.status = 'ready'

            # 更新项目场景计数
            total = session.query(Scene).filter(
                Scene.project_id == project_id
            ).count()
            session.query(Project).filter(Project.id == project_id).update(
                {Project.total_scenes: total}
            )

        self.acts_changed.emit(project_id)
        return results

    def _reindex_acts(self, session, project_id: int):
        """重排序场次索引"""
        acts = session.query(Act).filter(
            Act.project_id == project_id
        ).order_by(Act.act_index).all()
        for i, act in enumerate(acts):
            act.act_index = i

    def update_acts_tags(self, project_id: int, acts_data: List[Dict]) -> bool:
        """
        批量更新场次的标签信息（爆点/情绪/冲突分析结果）

        Args:
            project_id: 项目 ID
            acts_data: 场次数据列表，每项含 id, tags, summary, emotion 等字段
        """
        from sqlalchemy.orm.attributes import flag_modified

        with session_scope() as session:
            for data in acts_data:
                act_id = data.get('id')
                if not act_id:
                    continue
                act = session.query(Act).get(act_id)
                if not act or act.project_id != project_id:
                    continue

                # 保存 summary 到 Act.summary 列
                if 'summary' in data and data['summary']:
                    act.summary = data['summary']

                # 将 tags + emotion/detail 数据打包为 dict 存入 tags JSON 字段
                raw_tags = data.get('tags', [])
                if isinstance(raw_tags, dict):
                    # 已经是 dict 格式，直接保存
                    act.tags = raw_tags
                elif isinstance(raw_tags, list):
                    # 将 list 格式升级为 dict，附带 emotion/detail
                    tags_dict = {'labels': raw_tags}
                    for key in ('emotion', 'emotion_detail',
                                'explosion_detail', 'conflict_detail'):
                        if data.get(key):
                            tags_dict[key] = data[key]
                    # 仅当有额外数据时才用 dict 格式，否则保持 list 兼容
                    if any(tags_dict.get(k) for k in ('emotion', 'emotion_detail',
                                                       'explosion_detail', 'conflict_detail')):
                        act.tags = tags_dict
                    else:
                        act.tags = raw_tags
                flag_modified(act, 'tags')

        self.acts_changed.emit(project_id)
        return True
