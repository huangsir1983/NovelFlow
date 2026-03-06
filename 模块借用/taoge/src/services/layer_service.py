"""
涛割 - 图层管理服务 + AI 分层工作线程
"""

import os
import time
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import QThread, pyqtSignal

from database.session import session_scope
from database.models import Scene, Layer


class LayerService:
    """图层管理服务"""

    def create_layers_from_image(self, scene_id: int, image_path: str) -> List[dict]:
        """
        AI 分层：调用 API 将图片分解为多个图层。
        初版：创建一个包含完整图片的 background 层。
        AI 分层由 AILayeringWorker 异步执行。
        """
        if not os.path.exists(image_path):
            return []

        # 创建默认背景层
        layer_data = {
            'scene_id': scene_id,
            'name': '背景',
            'layer_type': 'background',
            'z_order': 0,
            'image_path': image_path,
            'original_image_path': image_path,
            'is_visible': True,
            'is_locked': False,
        }
        layer_id = self.save_layer(layer_data)
        layer_data['id'] = layer_id

        return [layer_data]

    def save_layer(self, layer_data: dict) -> int:
        """保存/更新图层到数据库"""
        with session_scope() as session:
            layer_id = layer_data.get('id')

            if layer_id:
                layer = session.query(Layer).filter(Layer.id == layer_id).first()
                if layer:
                    for key in ['name', 'layer_type', 'z_order', 'is_visible',
                                'is_locked', 'is_reference', 'color_label',
                                'image_path', 'original_image_path',
                                'mask_path', 'transform', 'blend_mode',
                                'opacity', 'prompt_history', 'character_id']:
                        if key in layer_data:
                            setattr(layer, key, layer_data[key])
                    return layer.id
            else:
                layer = Layer(
                    scene_id=layer_data['scene_id'],
                    name=layer_data.get('name', 'Layer'),
                    layer_type=layer_data.get('layer_type', 'background'),
                    z_order=layer_data.get('z_order', 0),
                    is_visible=layer_data.get('is_visible', True),
                    is_locked=layer_data.get('is_locked', False),
                    is_reference=layer_data.get('is_reference', False),
                    color_label=layer_data.get('color_label'),
                    image_path=layer_data.get('image_path'),
                    original_image_path=layer_data.get('original_image_path'),
                    mask_path=layer_data.get('mask_path'),
                    transform=layer_data.get('transform', {}),
                    blend_mode=layer_data.get('blend_mode', 'normal'),
                    opacity=layer_data.get('opacity', 1.0),
                    prompt_history=layer_data.get('prompt_history', []),
                    character_id=layer_data.get('character_id'),
                )
                session.add(layer)
                session.flush()
                return layer.id

        return 0

    def get_scene_layers(self, scene_id: int) -> List[dict]:
        """获取场景所有图层"""
        with session_scope() as session:
            layers = session.query(Layer).filter(
                Layer.scene_id == scene_id
            ).order_by(Layer.z_order).all()
            return [l.to_dict() for l in layers]

    def delete_layer(self, layer_id: int) -> bool:
        """删除图层"""
        with session_scope() as session:
            layer = session.query(Layer).filter(Layer.id == layer_id).first()
            if layer:
                session.delete(layer)
                return True
        return False

    def delete_scene_layers(self, scene_id: int) -> int:
        """删除场景的所有图层，返回删除数量"""
        with session_scope() as session:
            count = session.query(Layer).filter(Layer.scene_id == scene_id).delete()
            return count

    def reorder_layers(self, layer_ids: List[int]) -> bool:
        """重排图层顺序"""
        with session_scope() as session:
            for z_order, layer_id in enumerate(layer_ids):
                layer = session.query(Layer).filter(Layer.id == layer_id).first()
                if layer:
                    layer.z_order = z_order
        return True

    def merge_layers(self, layer_ids: List[int], output_path: str) -> str:
        """合并多个图层为一张图片"""
        try:
            from PIL import Image

            layers_data = []
            with session_scope() as session:
                for lid in layer_ids:
                    layer = session.query(Layer).filter(Layer.id == lid).first()
                    if layer and layer.image_path and os.path.exists(layer.image_path):
                        layers_data.append({
                            'image_path': layer.image_path,
                            'transform': layer.transform or {},
                            'z_order': layer.z_order,
                        })

            if not layers_data:
                return ""

            # 按 z_order 排序（底层在前）
            layers_data.sort(key=lambda l: l['z_order'])

            # 打开第一张图片确定尺寸
            base_img = Image.open(layers_data[0]['image_path']).convert('RGBA')
            result = Image.new('RGBA', base_img.size, (0, 0, 0, 0))

            for ld in layers_data:
                img = Image.open(ld['image_path']).convert('RGBA')
                # 调整到基础尺寸
                if img.size != result.size:
                    img = img.resize(result.size, Image.Resampling.LANCZOS)
                result = Image.alpha_composite(result, img)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            result.save(output_path, 'PNG')
            return output_path

        except Exception as e:
            print(f"合并图层失败: {e}")
            return ""


class AILayeringWorker(QThread):
    """AI 分层工作线程"""

    layering_completed = pyqtSignal(list)  # [layer_data, ...]
    layering_failed = pyqtSignal(str)
    layering_progress = pyqtSignal(int)

    def __init__(self, scene_id: int, image_path: str, provider: str = 'jimeng'):
        super().__init__()
        self._scene_id = scene_id
        self._image_path = image_path
        self._provider = provider

    def run(self):
        """
        AI 分层流程：
        1. 调用 Jimeng 抠图 API 或 ComfyUI 分割工作流
        2. 获取前景/背景/各人物蒙版
        3. 按蒙版切割原图为独立图层
        4. 保存到 generated/{project_id}/layers/
        5. 创建 Layer 记录
        """
        try:
            self.layering_progress.emit(10)

            # 获取项目 ID
            with session_scope() as session:
                scene = session.query(Scene).filter(
                    Scene.id == self._scene_id
                ).first()
                if not scene:
                    self.layering_failed.emit("场景不存在")
                    return
                project_id = scene.project_id

            layers_dir = os.path.join('generated', str(project_id), 'layers',
                                      str(self._scene_id))
            os.makedirs(layers_dir, exist_ok=True)

            self.layering_progress.emit(30)

            # 当前版本：创建基础背景层 + 前景层（使用完整图片）
            # 后续版本将接入真实 API 进行智能分割
            service = LayerService()

            # 背景层
            bg_data = {
                'scene_id': self._scene_id,
                'name': '背景',
                'layer_type': 'background',
                'z_order': 0,
                'image_path': self._image_path,
                'original_image_path': self._image_path,
                'is_visible': True,
            }
            bg_id = service.save_layer(bg_data)
            bg_data['id'] = bg_id

            self.layering_progress.emit(70)

            # 前景层（占位 — 等待 API 接入）
            fg_data = {
                'scene_id': self._scene_id,
                'name': '前景',
                'layer_type': 'foreground',
                'z_order': 1,
                'image_path': None,  # 等待 API 填充
                'is_visible': True,
            }
            fg_id = service.save_layer(fg_data)
            fg_data['id'] = fg_id

            self.layering_progress.emit(100)

            layers = service.get_scene_layers(self._scene_id)
            self.layering_completed.emit(layers)

        except Exception as e:
            self.layering_failed.emit(str(e))
