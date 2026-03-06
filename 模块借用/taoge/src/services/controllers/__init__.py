"""
涛割 - 控制器层
连接UI与服务层的桥梁
"""

from .project_controller import ProjectController
from .generation_controller import GenerationController
from .material_controller import MaterialController
from .canvas_controller import CanvasController
from .prop_controller import PropController
from .act_controller import ActController

__all__ = [
    'ProjectController',
    'GenerationController',
    'MaterialController',
    'CanvasController',
    'PropController',
    'ActController',
]
