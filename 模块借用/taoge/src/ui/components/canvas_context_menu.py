"""
涛割 - 画布右键菜单
提供场景卡片的上下文操作菜单
"""

from typing import List, Callable, Optional

from PyQt6.QtWidgets import QMenu, QWidget
from PyQt6.QtCore import QPointF, QPoint
from PyQt6.QtGui import QAction, QColor


def _get_menu_style() -> str:
    """深色主题菜单样式"""
    return """
        QMenu {
            background-color: rgb(35, 35, 40);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            padding: 4px;
        }
        QMenu::item {
            padding: 6px 24px 6px 12px;
            color: rgba(255, 255, 255, 0.8);
            font-size: 12px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: rgba(0, 122, 204, 0.3);
            color: white;
        }
        QMenu::item:disabled {
            color: rgba(255, 255, 255, 0.3);
        }
        QMenu::separator {
            height: 1px;
            background-color: rgba(255, 255, 255, 0.08);
            margin: 4px 8px;
        }
    """


def show_canvas_context_menu(
    parent: QWidget,
    scene_index: int,
    global_pos: QPointF,
    multi_selected: List[int] = None,
    on_generate_image: Callable = None,
    on_generate_video: Callable = None,
    on_open_property: Callable = None,
    on_batch_generate: Callable = None,
    on_delete_scene: Callable = None,
    on_duplicate_scene: Callable = None,
):
    """
    显示画布场景右键菜单

    Args:
        parent: 父组件
        scene_index: 右键的场景索引
        global_pos: 全局坐标位置
        multi_selected: 多选的索引列表（可选）
        on_generate_image: 生成图片回调
        on_generate_video: 生成视频回调
        on_open_property: 打开属性面板回调
        on_batch_generate: 批量生成回调
        on_delete_scene: 删除场景回调
        on_duplicate_scene: 复制场景回调
    """
    menu = QMenu(parent)
    menu.setStyleSheet(_get_menu_style())

    has_multi = multi_selected and len(multi_selected) > 1

    # 生成操作
    if on_generate_image:
        gen_img = menu.addAction(f"生成图片 - 场景 #{scene_index + 1}")
        gen_img.triggered.connect(lambda: on_generate_image(scene_index))

    if on_generate_video:
        gen_vid = menu.addAction(f"生成视频 - 场景 #{scene_index + 1}")
        gen_vid.triggered.connect(lambda: on_generate_video(scene_index))

    # 批量生成（多选时显示）
    if has_multi and on_batch_generate:
        menu.addSeparator()
        batch_action = menu.addAction(f"批量生成 ({len(multi_selected)} 个场景)")
        batch_action.triggered.connect(lambda: on_batch_generate(multi_selected))

    menu.addSeparator()

    # 属性面板
    if on_open_property:
        prop_action = menu.addAction("打开属性面板")
        prop_action.triggered.connect(lambda: on_open_property(scene_index))

    menu.addSeparator()

    # 编辑操作
    if on_duplicate_scene:
        dup_action = menu.addAction("复制场景")
        dup_action.triggered.connect(lambda: on_duplicate_scene(scene_index))

    if on_delete_scene:
        del_action = menu.addAction("删除场景")
        del_action.triggered.connect(lambda: on_delete_scene(scene_index))

    # 显示菜单
    pos = QPoint(int(global_pos.x()), int(global_pos.y()))
    menu.exec(pos)
