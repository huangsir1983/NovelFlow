"""
涛割 - 分镜导出服务
分镜 PDF 导出 + 项目 JSON 备份
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from database.session import session_scope
from database.models import Scene, Project, Character, Layer


class StoryboardExporter:
    """分镜导出"""

    def export_pdf(self, project_id: int, output_path: str) -> str:
        """
        导出分镜 PDF

        每页 2-4 个分镜，包含：缩略图 + 场景号 + 时长 + 运镜 + 提示词

        Args:
            project_id: 项目 ID
            output_path: 输出路径

        Returns:
            输出文件路径，失败返回空字符串
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            print("需要 Pillow 来导出 PDF")
            return ""

        scenes = self._get_scenes(project_id)
        if not scenes:
            return ""

        project_name = self._get_project_name(project_id)

        # PDF 页面尺寸（A4 横版 150dpi）
        page_w, page_h = 1587, 1123
        margin = 50
        cols, rows = 2, 2
        scenes_per_page = cols * rows

        cell_w = (page_w - margin * (cols + 1)) // cols
        cell_h = (page_h - margin * (rows + 1) - 60) // rows  # 60 for header
        thumb_h = int(cell_h * 0.6)

        pages = []
        for page_idx in range(0, len(scenes), scenes_per_page):
            page_scenes = scenes[page_idx:page_idx + scenes_per_page]
            page = Image.new('RGB', (page_w, page_h), (255, 255, 255))
            draw = ImageDraw.Draw(page)

            # 页头
            try:
                font_title = ImageFont.truetype("msyh.ttc", 24)
                font_body = ImageFont.truetype("msyh.ttc", 14)
                font_small = ImageFont.truetype("msyh.ttc", 11)
            except (IOError, OSError):
                font_title = ImageFont.load_default()
                font_body = font_title
                font_small = font_title

            draw.text(
                (margin, 15),
                f"{project_name} — 分镜表",
                fill=(30, 30, 30), font=font_title,
            )
            draw.text(
                (page_w - margin - 200, 20),
                f"第 {page_idx // scenes_per_page + 1} 页",
                fill=(120, 120, 120), font=font_body,
            )

            for i, scene in enumerate(page_scenes):
                col = i % cols
                row = i // cols
                x = margin + col * (cell_w + margin)
                y = 60 + margin + row * (cell_h + margin)

                # 边框
                draw.rectangle(
                    [x, y, x + cell_w, y + cell_h],
                    outline=(200, 200, 200), width=1,
                )

                # 缩略图
                img_path = scene.get('generated_image_path', '')
                if img_path and os.path.exists(img_path):
                    try:
                        thumb = Image.open(img_path)
                        thumb.thumbnail((cell_w - 10, thumb_h - 10))
                        tx = x + (cell_w - thumb.width) // 2
                        ty = y + 5
                        page.paste(thumb, (tx, ty))
                    except Exception:
                        pass

                # 场景信息
                text_y = y + thumb_h + 5
                scene_idx = scene.get('scene_index', 0)
                duration = scene.get('duration', 3.0)
                camera = scene.get('camera_motion', 'Static')

                draw.text(
                    (x + 5, text_y),
                    f"#{scene_idx + 1}  {duration:.1f}s  {camera}",
                    fill=(50, 50, 50), font=font_body,
                )
                text_y += 20

                # 提示词（截断）
                prompt = scene.get('image_prompt', '')
                if prompt:
                    if len(prompt) > 80:
                        prompt = prompt[:77] + "..."
                    draw.text(
                        (x + 5, text_y),
                        prompt,
                        fill=(100, 100, 100), font=font_small,
                    )

            pages.append(page)

        if not pages:
            return ""

        # 保存为 PDF
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pages[0].save(
            output_path, "PDF", save_all=True,
            append_images=pages[1:] if len(pages) > 1 else [],
        )
        return output_path if os.path.exists(output_path) else ""

    def export_project_json(self, project_id: int, output_path: str) -> str:
        """
        导出项目完整 JSON 备份

        包含所有模型数据 + 图层信息 + 设置

        Args:
            project_id: 项目 ID
            output_path: 输出路径

        Returns:
            输出文件路径
        """
        data = {
            'export_version': '1.2.0',
            'exported_at': datetime.now().isoformat(),
            'project': {},
            'scenes': [],
            'characters': [],
            'layers': [],
        }

        with session_scope() as session:
            project = session.query(Project).get(project_id)
            if not project:
                return ""

            data['project'] = {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'source_type': project.source_type,
                'source_content': project.source_content,
                'total_scenes': project.total_scenes,
                'fps': project.fps,
                'canvas_width': project.canvas_width,
                'canvas_height': project.canvas_height,
                'animatic_settings': project.animatic_settings,
            }

            scenes = session.query(Scene).filter(
                Scene.project_id == project_id
            ).order_by(Scene.scene_index).all()
            for scene in scenes:
                data['scenes'].append(scene.to_dict())

            characters = session.query(Character).filter(
                Character.project_id == project_id,
                Character.is_active == True,
            ).all()
            for char in characters:
                data['characters'].append(char.to_dict())

            layers = session.query(Layer).filter(
                Layer.scene_id.in_([s.id for s in scenes])
            ).order_by(Layer.scene_id, Layer.z_order).all()
            for layer in layers:
                data['layers'].append(layer.to_dict())

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        return output_path if os.path.exists(output_path) else ""

    # === 辅助 ===

    def _get_scenes(self, project_id: int) -> List[dict]:
        with session_scope() as session:
            scenes = session.query(Scene).filter(
                Scene.project_id == project_id
            ).order_by(Scene.scene_index).all()
            return [s.to_dict() for s in scenes]

    def _get_project_name(self, project_id: int) -> str:
        with session_scope() as session:
            project = session.query(Project).get(project_id)
            return project.name if project else "未命名"
