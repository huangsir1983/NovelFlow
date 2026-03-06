"""
涛割 - 剪映导出服务
生成剪映项目文件
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from config.constants import JIANYING_PLATFORM_INFO, JIANYING_NEW_VERSION, JIANYING_VERSION


@dataclass
class ExportConfig:
    """导出配置"""
    project_name: str = "涛割导出"
    export_path: str = ""
    canvas_width: int = 1920
    canvas_height: int = 1080
    fps: int = 30

    # 字幕设置
    subtitle_font: str = "系统默认"
    subtitle_font_path: str = ""
    subtitle_font_size: int = 7
    subtitle_style: str = "黑底白字"
    subtitle_position: int = -888

    # 导出选项
    include_subtitles: bool = True
    include_images: bool = True
    include_videos: bool = True
    copy_materials: bool = True  # 是否复制素材到导出目录


@dataclass
class TrackSegment:
    """轨道片段"""
    material_id: str
    material_path: str
    start_time: int  # 微秒
    end_time: int
    duration: int
    track_type: str = "video"  # video, audio, text


class JianyingExporter:
    """
    剪映项目导出器
    支持导出图像轨道、视频轨道和字幕轨道
    """

    def __init__(self, config: ExportConfig = None):
        self.config = config or ExportConfig()
        self._materials = []
        self._tracks = []

    def create_project(
        self,
        scenes: List[Dict[str, Any]],
        output_dir: str = None
    ) -> str:
        """
        创建剪映项目

        Args:
            scenes: 场景数据列表
            output_dir: 输出目录

        Returns:
            str: 项目目录路径
        """
        output_dir = output_dir or self.config.export_path
        if not output_dir:
            output_dir = os.path.join("generated", f"jianying_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

        # 创建项目目录结构
        project_dir = self._create_project_structure(output_dir)

        # 处理场景数据
        video_segments = []
        text_segments = []
        total_duration = 0

        for scene in scenes:
            start_time = scene.get('start_microseconds', total_duration)
            end_time = scene.get('end_microseconds', start_time + 4_000_000)
            duration = end_time - start_time

            # 添加视频/图像素材
            if self.config.include_videos and scene.get('video_path'):
                video_segments.append(TrackSegment(
                    material_id=str(uuid.uuid4()).upper(),
                    material_path=scene['video_path'],
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    track_type="video"
                ))
            elif self.config.include_images and scene.get('image_path'):
                video_segments.append(TrackSegment(
                    material_id=str(uuid.uuid4()).upper(),
                    material_path=scene['image_path'],
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    track_type="video"
                ))

            # 添加字幕
            if self.config.include_subtitles and scene.get('subtitle_text'):
                text_segments.append(TrackSegment(
                    material_id=str(uuid.uuid4()).upper(),
                    material_path="",
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    track_type="text"
                ))
                # 存储字幕文本
                text_segments[-1].text = scene['subtitle_text']

            total_duration = max(total_duration, end_time)

        # 生成draft_content.json
        draft_content = self._generate_draft_content(
            video_segments,
            text_segments,
            total_duration
        )

        # 写入文件
        draft_content_path = os.path.join(project_dir, "draft_content.json")
        with open(draft_content_path, 'w', encoding='utf-8') as f:
            json.dump(draft_content, f, ensure_ascii=False, indent=2)

        # 生成其他必要文件
        self._generate_draft_meta_info(project_dir, total_duration)
        self._generate_draft_virtual_store(project_dir)

        # 复制素材（如果需要）
        if self.config.copy_materials:
            self._copy_materials(project_dir, video_segments)

        return project_dir

    def _create_project_structure(self, output_dir: str) -> str:
        """创建项目目录结构"""
        project_name = self.config.project_name or f"project_{datetime.now().strftime('%H%M%S')}"
        project_dir = os.path.join(output_dir, project_name)

        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(os.path.join(project_dir, "Resources"), exist_ok=True)

        return project_dir

    def _generate_draft_content(
        self,
        video_segments: List[TrackSegment],
        text_segments: List[TrackSegment],
        total_duration: int
    ) -> Dict[str, Any]:
        """生成draft_content.json内容"""

        # 基础模板
        content = {
            "canvas_config": {
                "height": self.config.canvas_height,
                "ratio": "original",
                "width": self.config.canvas_width
            },
            "color_space": 0,
            "config": self._get_config_template(),
            "cover": None,
            "create_time": int(datetime.now().timestamp() * 1000000),
            "duration": total_duration,
            "extra_info": None,
            "fps": float(self.config.fps),
            "free_render_index_mode_on": False,
            "group_container": {"groups": []},
            "id": str(uuid.uuid4()).upper(),
            "keyframe_graph_list": [],
            "keyframes": self._get_keyframes_template(),
            "materials": self._get_materials_template(),
            "mutable_config": None,
            "name": self.config.project_name,
            "new_version": JIANYING_NEW_VERSION,
            "platform": JIANYING_PLATFORM_INFO.copy(),
            "relationships": [],
            "render_index_track_mode_on": False,
            "retouch_cover": None,
            "source": "default",
            "static_cover_image_path": "",
            "time_marks": None,
            "tracks": [],
            "update_time": int(datetime.now().timestamp() * 1000000),
            "version": JIANYING_VERSION
        }

        # 添加视频轨道
        if video_segments:
            video_track = self._create_video_track(video_segments, content["materials"])
            content["tracks"].append(video_track)

        # 添加字幕轨道
        if text_segments:
            text_track = self._create_text_track(text_segments, content["materials"])
            content["tracks"].append(text_track)

        return content

    def _create_video_track(
        self,
        segments: List[TrackSegment],
        materials: Dict
    ) -> Dict[str, Any]:
        """创建视频轨道"""
        track = {
            "attribute": 0,
            "flag": 0,
            "id": str(uuid.uuid4()).upper(),
            "is_default_name": True,
            "name": "",
            "segments": [],
            "type": "video"
        }

        for seg in segments:
            # 添加素材
            material = self._create_video_material(seg)
            materials["videos"].append(material)

            # 添加轨道片段
            segment = {
                "cartoon": False,
                "clip": {
                    "alpha": 1.0,
                    "flip": {"horizontal": False, "vertical": False},
                    "rotation": 0.0,
                    "scale": {"x": 1.0, "y": 1.0},
                    "transform": {"x": 0.0, "y": 0.0}
                },
                "common_keyframes": [],
                "enable_adjust": True,
                "enable_color_correct_adjust": False,
                "enable_color_curves": True,
                "enable_color_wheels": True,
                "enable_lut": True,
                "enable_smart_color_adjust": False,
                "extra_material_refs": [],
                "group_id": "",
                "hdr_settings": None,
                "id": str(uuid.uuid4()).upper(),
                "intensifies_audio": False,
                "is_placeholder": False,
                "is_tone_modify": False,
                "keyframe_refs": [],
                "last_nonzero_volume": 1.0,
                "material_id": material["id"],
                "render_index": 0,
                "responsive_layout": {"enable": False, "horizontal_pos_layout": 0, "size_layout": 0, "target_follow": "", "vertical_pos_layout": 0},
                "reverse": False,
                "source_timerange": {"duration": seg.duration, "start": 0},
                "speed": 1.0,
                "target_timerange": {"duration": seg.duration, "start": seg.start_time},
                "template_id": "",
                "template_scene": "default",
                "track_attribute": 0,
                "track_render_index": 0,
                "uniform_scale": {"on": True, "value": 1.0},
                "visible": True,
                "volume": 1.0
            }
            track["segments"].append(segment)

        return track

    def _create_video_material(self, segment: TrackSegment) -> Dict[str, Any]:
        """创建视频素材"""
        return {
            "audio_fade": None,
            "category_id": "",
            "category_name": "local",
            "check_flag": 63487,
            "crop": {"lower_left_x": 0.0, "lower_left_y": 1.0, "lower_right_x": 1.0, "lower_right_y": 1.0, "upper_left_x": 0.0, "upper_left_y": 0.0, "upper_right_x": 1.0, "upper_right_y": 0.0},
            "crop_ratio": "free",
            "crop_scale": 1.0,
            "duration": segment.duration,
            "extra_type_option": 0,
            "formula_id": "",
            "freeze": None,
            "gameplay": None,
            "has_audio": False,
            "height": self.config.canvas_height,
            "id": segment.material_id,
            "intensifies_audio_path": "",
            "intensifies_path": "",
            "is_ai_generate_content": False,
            "is_unified_beauty_mode": False,
            "local_id": "",
            "local_material_id": "",
            "material_id": "",
            "material_name": os.path.basename(segment.material_path),
            "material_url": "",
            "matting": {"flag": 0, "has_use_quick_brush": False, "has_use_quick_eraser": False, "interactiveTime": [], "path": "", "strokes": []},
            "media_path": "",
            "object_locked": None,
            "origin_material_id": "",
            "path": segment.material_path,
            "picture_from": "none",
            "picture_set_category_id": "",
            "picture_set_category_name": "",
            "request_id": "",
            "reverse_intensifies_path": "",
            "reverse_path": "",
            "smart_motion": None,
            "source": 0,
            "source_platform": 0,
            "stable": None,
            "team_id": "",
            "type": "photo" if segment.material_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')) else "video",
            "video_algorithm": {"algorithms": [], "deflicker": None, "motion_blur_config": None, "noise_reduction": None, "path": "", "quality_enhance": None, "time_range": None},
            "width": self.config.canvas_width
        }

    def _create_text_track(
        self,
        segments: List[TrackSegment],
        materials: Dict
    ) -> Dict[str, Any]:
        """创建字幕轨道"""
        track = {
            "attribute": 0,
            "flag": 0,
            "id": str(uuid.uuid4()).upper(),
            "is_default_name": True,
            "name": "",
            "segments": [],
            "type": "text"
        }

        for seg in segments:
            # 添加文本素材
            material = self._create_text_material(seg)
            materials["texts"].append(material)

            # 添加轨道片段
            segment = {
                "cartoon": False,
                "clip": {
                    "alpha": 1.0,
                    "flip": {"horizontal": False, "vertical": False},
                    "rotation": 0.0,
                    "scale": {"x": 1.0, "y": 1.0},
                    "transform": {"x": 0.0, "y": float(self.config.subtitle_position) / 1000.0}
                },
                "common_keyframes": [],
                "enable_adjust": False,
                "enable_color_correct_adjust": False,
                "enable_color_curves": True,
                "enable_color_wheels": True,
                "enable_lut": False,
                "enable_smart_color_adjust": False,
                "extra_material_refs": [],
                "group_id": "",
                "hdr_settings": None,
                "id": str(uuid.uuid4()).upper(),
                "intensifies_audio": False,
                "is_placeholder": False,
                "is_tone_modify": False,
                "keyframe_refs": [],
                "last_nonzero_volume": 1.0,
                "material_id": material["id"],
                "render_index": 10000,
                "responsive_layout": {"enable": False, "horizontal_pos_layout": 0, "size_layout": 0, "target_follow": "", "vertical_pos_layout": 0},
                "reverse": False,
                "source_timerange": {"duration": seg.duration, "start": 0},
                "speed": 1.0,
                "target_timerange": {"duration": seg.duration, "start": seg.start_time},
                "template_id": "",
                "template_scene": "default",
                "track_attribute": 0,
                "track_render_index": 0,
                "uniform_scale": {"on": True, "value": 1.0},
                "visible": True,
                "volume": 1.0
            }
            track["segments"].append(segment)

        return track

    def _create_text_material(self, segment: TrackSegment) -> Dict[str, Any]:
        """创建文本素材"""
        text_content = getattr(segment, 'text', '')

        # 获取字幕样式
        style = self._get_subtitle_style()

        return {
            "add_type": 0,
            "alignment": 1,
            "background_alpha": 1.0,
            "background_color": style["background_color"],
            "background_height": 0.14,
            "background_horizontal_offset": 0.0,
            "background_round_radius": 0.0,
            "background_style": 0,
            "background_vertical_offset": 0.0,
            "background_width": 0.14,
            "bold_width": 0.0,
            "border_alpha": 1.0,
            "border_color": "",
            "border_width": 0.08,
            "caption_template_info": {"category_id": "", "category_name": "", "effect_id": "", "is_new": False, "path": "", "request_id": "", "resource_id": "", "resource_name": "", "source_platform": 0},
            "check_flag": 7,
            "combo_info": {"text_templates": []},
            "content": text_content,
            "fixed_height": -1.0,
            "fixed_width": -1.0,
            "font_category_id": "",
            "font_category_name": "",
            "font_id": "",
            "font_name": "",
            "font_path": self.config.subtitle_font_path,
            "font_resource_id": "",
            "font_size": float(self.config.subtitle_font_size),
            "font_source_platform": 0,
            "font_team_id": "",
            "font_title": self.config.subtitle_font,
            "font_url": "",
            "fonts": [],
            "force_apply_line_max_width": False,
            "global_alpha": 1.0,
            "group_id": "",
            "has_shadow": False,
            "id": segment.material_id,
            "initial_scale": 1.0,
            "inner_padding": -1.0,
            "is_rich_text": False,
            "italic_degree": 0,
            "ktv_color": "",
            "language": "",
            "layer_weight": 1,
            "letter_spacing": 0.0,
            "line_feed": 1,
            "line_max_width": 0.82,
            "line_spacing": 0.02,
            "multi_language_current": "none",
            "name": "",
            "original_size": [],
            "preset_category": "",
            "preset_category_id": "",
            "preset_has_set_alignment": False,
            "preset_id": "",
            "preset_index": 0,
            "preset_name": "",
            "recognize_task_id": "",
            "recognize_type": 0,
            "relevance_segment": [],
            "shadow_alpha": 0.9,
            "shadow_angle": -45.0,
            "shadow_color": "",
            "shadow_distance": 5.0,
            "shadow_point": {"x": 0.6363961030678928, "y": -0.6363961030678928},
            "shadow_smoothing": 0.45,
            "shape_clip_x": False,
            "shape_clip_y": False,
            "style_name": "",
            "sub_type": 0,
            "subtitle_keywords": None,
            "text_alpha": 1.0,
            "text_color": style["text_color"],
            "text_curve": None,
            "text_preset_resource_id": "",
            "text_size": 30,
            "text_to_audio_ids": [],
            "tts_auto_update": False,
            "type": "text",
            "typesetting": 0,
            "underline": False,
            "underline_offset": 0.22,
            "underline_width": 0.05,
            "use_effect_default_color": True,
            "words": {"end_time": [], "start_time": [], "text": []}
        }

    def _get_subtitle_style(self) -> Dict[str, str]:
        """获取字幕样式"""
        if self.config.subtitle_style == "黑底白字":
            return {
                "background_color": "#000000",
                "text_color": "#ffffff"
            }
        else:
            return {
                "background_color": "#ffffff",
                "text_color": "#000000"
            }

    def _get_config_template(self) -> Dict[str, Any]:
        """获取config模板"""
        return {
            "adjust_max_index": 1,
            "attachment_info": [],
            "combination_max_index": 10,
            "export_range": None,
            "extract_audio_last_index": 1,
            "lyrics_recognition_id": "",
            "lyrics_sync": True,
            "lyrics_taskinfo": [],
            "maintrack_adsorb": True,
            "material_save_mode": 0,
            "multi_language_current": "none",
            "multi_language_list": [],
            "multi_language_main": "none",
            "multi_language_mode": "none",
            "original_sound_last_index": 1,
            "record_audio_last_index": 1,
            "sticker_max_index": 1,
            "subtitle_recognition_id": "",
            "subtitle_sync": True,
            "subtitle_taskinfo": [],
            "system_font_list": [],
            "video_mute": False,
            "zoom_info_params": None
        }

    def _get_keyframes_template(self) -> Dict[str, List]:
        """获取keyframes模板"""
        return {
            "adjusts": [], "audios": [], "effects": [], "filters": [],
            "handwrites": [], "stickers": [], "texts": [], "videos": []
        }

    def _get_materials_template(self) -> Dict[str, List]:
        """获取materials模板"""
        return {
            "ai_translates": [], "audio_balances": [], "audio_effects": [],
            "audio_fades": [], "audio_track_indexes": [], "audios": [],
            "beats": [], "canvases": [], "chromas": [], "color_curves": [],
            "digital_humans": [], "drafts": [], "effects": [], "flowers": [],
            "green_screens": [], "handwrites": [], "hsl": [], "images": [],
            "log_color_wheels": [], "loudnesses": [], "manual_deformations": [],
            "masks": [], "material_animations": [], "material_colors": [],
            "multi_language_refs": [], "placeholders": [], "plugin_effects": [],
            "primary_color_wheels": [], "realtime_denoises": [], "shapes": [],
            "smart_crops": [], "smart_relights": [], "sound_channel_mappings": [],
            "speeds": [], "stickers": [], "tail_leaders": [], "text_templates": [],
            "texts": [], "time_marks": [], "transitions": [], "video_effects": [],
            "video_trackings": [], "videos": [], "vocal_beautifys": [],
            "vocal_separations": []
        }

    def _generate_draft_meta_info(self, project_dir: str, duration: int):
        """生成draft_meta_info.json"""
        meta_info = {
            "cloud_package_completed_time": "",
            "draft_cloud_capcut_purchase_info": "",
            "draft_cloud_last_action_download": False,
            "draft_cloud_materials": [],
            "draft_cloud_purchase_info": "",
            "draft_cloud_template_id": "",
            "draft_cloud_tutorial_info": "",
            "draft_cloud_videocut_purchase_info": "",
            "draft_cover": "draft_cover.jpg",
            "draft_deeplink_url": "",
            "draft_enterprise_info": {
                "draft_enterprise_extra": "",
                "draft_enterprise_id": "",
                "draft_enterprise_name": "",
                "enterprise_material": []
            },
            "draft_fold_path": "",
            "draft_id": str(uuid.uuid4()).upper(),
            "draft_is_ai_packaging_used": False,
            "draft_is_ai_shorts": False,
            "draft_is_ai_translate": False,
            "draft_is_article_video_draft": False,
            "draft_is_from_deeplink": "false",
            "draft_is_invisible": False,
            "draft_materials": [
                {"type": 0, "value": []},
                {"type": 1, "value": []},
                {"type": 2, "value": []},
                {"type": 3, "value": []},
                {"type": 6, "value": []},
                {"type": 7, "value": []},
                {"type": 8, "value": []}
            ],
            "draft_materials_copied_info": [],
            "draft_name": self.config.project_name,
            "draft_new_version": JIANYING_NEW_VERSION,
            "draft_removable_storage_device": "",
            "draft_root_path": "",
            "draft_segment_extra_info": [],
            "draft_timeline_materials_size_": 0,
            "draft_type": "",
            "tm_draft_cloud_completed": "",
            "tm_draft_cloud_modified": 0,
            "tm_draft_create": int(datetime.now().timestamp() * 1000000),
            "tm_draft_modified": int(datetime.now().timestamp() * 1000000),
            "tm_draft_removed": 834793845,
            "tm_duration": duration
        }

        path = os.path.join(project_dir, "draft_meta_info.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(meta_info, f, ensure_ascii=False, indent=2)

    def _generate_draft_virtual_store(self, project_dir: str):
        """生成其他必要文件"""
        # draft_virtual_store.json
        virtual_store = {
            "draft_virtual_store": {
                "draft_cloud_materials": [],
                "draft_cloud_template_id": "",
                "draft_cloud_tutorial_info": "",
                "draft_enterprise_info": {
                    "draft_enterprise_extra": "",
                    "draft_enterprise_id": "",
                    "draft_enterprise_name": ""
                },
                "draft_is_ai_packaging_used": False,
                "draft_is_ai_shorts": False,
                "draft_is_ai_translate": False,
                "draft_is_article_video_draft": False,
                "draft_is_from_deeplink": "false",
                "draft_is_invisible": False,
                "draft_materials_copied_info": [],
                "draft_removable_storage_device": "",
                "draft_root_path": "",
                "draft_segment_extra_info": [],
                "draft_timeline_materials_size_": 0,
                "draft_type": "",
                "tm_draft_cloud_completed": "",
                "tm_draft_cloud_modified": 0,
                "tm_draft_create": 0,
                "tm_draft_modified": 0,
                "tm_draft_removed": 0,
                "tm_duration": 0
            }
        }

        path = os.path.join(project_dir, "draft_virtual_store.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(virtual_store, f, ensure_ascii=False, indent=2)

    def _copy_materials(self, project_dir: str, segments: List[TrackSegment]):
        """复制素材到项目目录"""
        resources_dir = os.path.join(project_dir, "Resources")

        for seg in segments:
            if seg.material_path and os.path.exists(seg.material_path):
                dest_path = os.path.join(resources_dir, os.path.basename(seg.material_path))
                try:
                    shutil.copy2(seg.material_path, dest_path)
                except Exception as e:
                    print(f"复制素材失败: {e}")

    def export_animatic_mp4(self, project_id: int, output_path: str,
                            scenes: List[Dict] = None) -> str:
        """
        导出 Animatic MP4 — 将图片序列按时长拼接为视频

        Args:
            project_id: 项目 ID
            output_path: 输出 MP4 路径
            scenes: 场景数据列表（需包含 generated_image_path、duration、camera_motion）

        Returns:
            输出文件路径，失败返回空字符串
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            print("需要 opencv-python-headless 来导出 Animatic MP4")
            return ""

        if not scenes:
            from database.session import session_scope
            from database.models import Scene
            with session_scope() as session:
                db_scenes = session.query(Scene).filter(
                    Scene.project_id == project_id
                ).order_by(Scene.scene_index).all()
                scenes = [s.to_dict() for s in db_scenes]

        if not scenes:
            return ""

        width = self.config.canvas_width
        height = self.config.canvas_height
        fps = self.config.fps

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not writer.isOpened():
            print(f"无法创建视频文件: {output_path}")
            return ""

        for scene in scenes:
            img_path = scene.get('generated_image_path', '')
            if not img_path or not os.path.exists(img_path):
                # 黑帧占位
                black = np.zeros((height, width, 3), dtype=np.uint8)
                duration = scene.get('duration', 3.0)
                for _ in range(int(duration * fps)):
                    writer.write(black)
                continue

            img = cv2.imread(img_path)
            if img is None:
                continue

            duration = scene.get('duration', 3.0)
            camera = scene.get('camera_motion', 'Static')
            total_frames = int(duration * fps)

            # Ken Burns 效果
            ih, iw = img.shape[:2]
            for fi in range(total_frames):
                t = fi / max(1, total_frames - 1)  # 0~1

                # 计算裁剪区域
                cx, cy, s = iw / 2, ih / 2, 1.0
                if camera == 'ZoomIn':
                    s = 1.0 / (1.0 + 0.2 * t)
                elif camera == 'ZoomOut':
                    s = 1.0 / (1.2 - 0.2 * t)
                elif camera == 'PanLeft':
                    cx = iw * (0.5 - 0.1 * t)
                elif camera == 'PanRight':
                    cx = iw * (0.5 + 0.1 * t)
                elif camera == 'TiltUp':
                    cy = ih * (0.5 - 0.1 * t)
                elif camera == 'TiltDown':
                    cy = ih * (0.5 + 0.1 * t)

                crop_w = int(iw * s)
                crop_h = int(ih * s)
                x1 = max(0, int(cx - crop_w / 2))
                y1 = max(0, int(cy - crop_h / 2))
                x2 = min(iw, x1 + crop_w)
                y2 = min(ih, y1 + crop_h)

                cropped = img[y1:y2, x1:x2]
                if cropped.size == 0:
                    cropped = img

                frame = cv2.resize(cropped, (width, height),
                                    interpolation=cv2.INTER_LINEAR)
                writer.write(frame)

        writer.release()
        return output_path if os.path.exists(output_path) else ""
