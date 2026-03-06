"""
涛割 - 区域模块
四个工作区域：剧本区、角色道具区、导演画布区、预编辑区
"""

from .script_zone import ScriptZone
from .character_prop_zone import CharacterPropZone
from .director_zone import DirectorZone
from .pre_edit_zone import PreEditZone

__all__ = [
    'ScriptZone',
    'CharacterPropZone',
    'DirectorZone',
    'PreEditZone',
]
