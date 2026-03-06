"""
涛割 - UI组件
"""

from .scene_card import SceneCard
from .settings_page import SettingsPage
from .materials_page import MaterialsPage, MaterialCard, CharacterEditDialog
from .tasks_page import TasksPage, TaskRow, TaskStatusBadge
from .srt_import_dialog import SrtImportDialog
from .projects_page import ProjectsPage, ProjectCard
from .scene_editor_page import SceneEditorPage
from .first_last_frame import FirstLastFramePanel, FirstLastFrameDialog, FramePreview
from .script_structure_panel import ScriptStructurePanel, SceneListItem
from .video_preview_panel import VideoPreviewPanel, TimelineWidget
from .shot_property_panel import ShotPropertyPanel, CollapsibleSection
from .canvas_mode import CanvasModePanel, CanvasView, SceneCanvasCard

__all__ = [
    "SceneCard",
    "SettingsPage",
    "MaterialsPage",
    "MaterialCard",
    "CharacterEditDialog",
    "TasksPage",
    "TaskRow",
    "TaskStatusBadge",
    "SrtImportDialog",
    "ProjectsPage",
    "ProjectCard",
    "SceneEditorPage",
    "FirstLastFramePanel",
    "FirstLastFrameDialog",
    "FramePreview",
    # 三栏布局组件
    "ScriptStructurePanel",
    "SceneListItem",
    "VideoPreviewPanel",
    "TimelineWidget",
    "ShotPropertyPanel",
    "CollapsibleSection",
    # Canvas画布模式
    "CanvasModePanel",
    "CanvasView",
    "SceneCanvasCard",
]
