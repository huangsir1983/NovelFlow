"""
涛割 - 画布撤销管理器
基于 QUndoStack 的快照式 Undo/Redo 系统。
每次操作前拍摄完整快照（CanvasSnapshot），undo 时恢复快照并重建 UI。
"""

import copy
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

from PyQt6.QtGui import QUndoStack, QUndoCommand


# ============================================================
#  CanvasSnapshot — 画布快照数据
# ============================================================

@dataclass
class CanvasSnapshot:
    """画布某一时刻的完整状态快照"""
    canvas_state: str                           # CanvasState.value
    groups_data: List[Dict[str, Any]]           # _get_groups_data_for_save() 的返回值
    sentence_order: List[int]                   # sentence_index 列表
    db_acts_data: List[Dict[str, Any]]          # data_hub.acts_data 深拷贝
    zone_positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    zone_sizes: Dict[str, Tuple[float, float]] = field(default_factory=dict)


# ============================================================
#  CanvasSnapshotCommand — QUndoCommand
# ============================================================

class CanvasSnapshotCommand(QUndoCommand):
    """快照式 undo command：保存操作前后的完整画布快照"""

    def __init__(self, canvas_view, description: str,
                 before: CanvasSnapshot, after: CanvasSnapshot):
        super().__init__(description)
        self._canvas = canvas_view
        self._before = before
        self._after = after
        self._first_redo = True

    def undo(self):
        self._canvas.restore_from_snapshot(self._before)

    def redo(self):
        if self._first_redo:
            # 第一次 redo 不执行（push 时已经是 after 状态）
            self._first_redo = False
            return
        self._canvas.restore_from_snapshot(self._after)


# ============================================================
#  UndoManager — 撤销管理器
# ============================================================

class UndoManager:
    """
    画布撤销管理器。
    用法：
        undo_mgr.begin_operation("场景化")
        # ... 执行操作 ...
        undo_mgr.commit_operation()
    """

    UNDO_LIMIT = 50

    def __init__(self, canvas_view):
        self._canvas = canvas_view
        self._stack = QUndoStack()
        self._stack.setUndoLimit(self.UNDO_LIMIT)

        # 当前操作的 before 快照（begin 时拍摄）
        self._pending_before: Optional[CanvasSnapshot] = None
        self._pending_description: str = ""

    @property
    def stack(self) -> QUndoStack:
        return self._stack

    def begin_operation(self, description: str):
        """开始一个可撤销操作，拍摄 before 快照"""
        self._pending_description = description
        self._pending_before = self._canvas.capture_snapshot()

    def commit_operation(self):
        """结束操作，拍摄 after 快照并推入 undo stack"""
        if self._pending_before is None:
            return
        after = self._canvas.capture_snapshot()
        cmd = CanvasSnapshotCommand(
            self._canvas,
            self._pending_description,
            self._pending_before,
            after,
        )
        self._stack.push(cmd)
        self._pending_before = None
        self._pending_description = ""

    def cancel_operation(self):
        """取消当前操作（不推入 stack）"""
        self._pending_before = None
        self._pending_description = ""

    def is_operation_pending(self) -> bool:
        """是否有未提交的操作"""
        return self._pending_before is not None

    def undo(self):
        if self._stack.canUndo():
            self._stack.undo()

    def redo(self):
        if self._stack.canRedo():
            self._stack.redo()

    def clear(self):
        self._stack.clear()
        self._pending_before = None
        self._pending_description = ""

    def can_undo(self) -> bool:
        return self._stack.canUndo()

    def can_redo(self) -> bool:
        return self._stack.canRedo()
