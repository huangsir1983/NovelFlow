"""
涛割 - 分镜调整组件
分镜分析第三步：调整场景顺序、合并、拆分
"""

from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class ScenePreviewCard(QFrame):
    """场景预览卡片"""

    selected_changed = pyqtSignal(object, bool)  # self, is_selected

    def __init__(self, index: int, scene_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.index = index
        self.scene_data = scene_data
        self._is_selected = False

        self.setObjectName("scenePreviewCard")
        self._update_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(60)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 序号
        self.index_label = QLabel(f"#{self.index + 1:02d}")
        self.index_label.setFixedWidth(36)
        self.index_label.setStyleSheet("""
            color: rgb(0, 180, 255);
            font-family: Consolas;
            font-size: 12px;
            font-weight: bold;
        """)
        layout.addWidget(self.index_label)

        # 文本
        text = self.scene_data.get('subtitle_text', '') or self.scene_data.get('scene_text', '')
        self.text_label = QLabel(text[:80] + ("..." if len(text) > 80 else ""))
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 12px;")
        layout.addWidget(self.text_label, 1)

        # 角色标签
        chars = self.scene_data.get('characters', [])
        if chars:
            chars_text = ", ".join(chars[:3])
            if len(chars) > 3:
                chars_text += f" +{len(chars) - 3}"
            char_label = QLabel(chars_text)
            char_label.setStyleSheet("""
                color: rgba(139, 92, 246, 0.8);
                font-size: 10px;
                background-color: rgba(139, 92, 246, 0.1);
                padding: 2px 6px;
                border-radius: 3px;
            """)
            layout.addWidget(char_label)

    def mousePressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._is_selected = not self._is_selected
        else:
            self._is_selected = True
        self._update_style()
        self.selected_changed.emit(self, self._is_selected)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._update_style()

    def is_selected(self) -> bool:
        return self._is_selected

    def update_index(self, new_index: int):
        self.index = new_index
        self.index_label.setText(f"#{new_index + 1:02d}")

    def _update_style(self):
        if self._is_selected:
            self.setStyleSheet("""
                QFrame#scenePreviewCard {
                    background-color: rgba(0, 122, 204, 0.15);
                    border: 1px solid rgba(0, 122, 204, 0.4);
                    border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#scenePreviewCard {
                    background-color: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 6px;
                }
                QFrame#scenePreviewCard:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    border-color: rgba(255, 255, 255, 0.1);
                }
            """)


class SceneAdjustmentWidget(QWidget):
    """分镜调整组件 - 分镜分析步骤3"""

    scenes_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: List[ScenePreviewCard] = []
        self._scenes_data: List[Dict[str, Any]] = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # 说明
        hint = QLabel("调整场景顺序、合并或拆分场景。支持 Ctrl+Click 多选")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        layout.addWidget(hint)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        merge_btn = QPushButton("合并选中")
        merge_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        merge_btn.clicked.connect(self._merge_selected)
        merge_btn.setStyleSheet(self._get_btn_style())
        toolbar.addWidget(merge_btn)

        split_btn = QPushButton("拆分选中")
        split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        split_btn.clicked.connect(self._split_selected)
        split_btn.setStyleSheet(self._get_btn_style())
        toolbar.addWidget(split_btn)

        sep = QFrame()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")
        toolbar.addWidget(sep)

        up_btn = QPushButton("上移")
        up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        up_btn.clicked.connect(self._move_up)
        up_btn.setStyleSheet(self._get_btn_style())
        toolbar.addWidget(up_btn)

        down_btn = QPushButton("下移")
        down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        down_btn.clicked.connect(self._move_down)
        down_btn.setStyleSheet(self._get_btn_style())
        toolbar.addWidget(down_btn)

        toolbar.addStretch()

        self.stats_label = QLabel("0 个场景")
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px;")
        toolbar.addWidget(self.stats_label)

        layout.addLayout(toolbar)

        # 场景列表滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.02);
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch()

        scroll.setWidget(self.list_container)
        layout.addWidget(scroll, 1)

    def _get_btn_style(self):
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """

    def set_scenes(self, scenes: List[Dict[str, Any]]):
        """设置场景数据"""
        self._scenes_data = [dict(s) for s in scenes]
        self._rebuild_cards()

    def _rebuild_cards(self):
        """重建所有卡片"""
        # 清除现有卡片
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        for i, scene_data in enumerate(self._scenes_data):
            card = ScenePreviewCard(i, scene_data)
            card.selected_changed.connect(self._on_card_selected)
            self._cards.append(card)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

        self.stats_label.setText(f"{len(self._scenes_data)} 个场景")

    def _on_card_selected(self, card: ScenePreviewCard, is_selected: bool):
        """卡片选中事件"""
        # 如果不是 Ctrl 点击，取消其他选中
        from PyQt6.QtWidgets import QApplication
        if not (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier):
            for c in self._cards:
                if c is not card:
                    c.set_selected(False)

    def _get_selected_indices(self) -> List[int]:
        """获取选中的卡片索引"""
        return sorted([c.index for c in self._cards if c.is_selected()])

    def _merge_selected(self):
        """合并选中的场景"""
        selected = self._get_selected_indices()
        if len(selected) < 2:
            return

        # 合并文本
        merged_text = "\n".join(
            self._scenes_data[i].get('subtitle_text', '') or self._scenes_data[i].get('scene_text', '')
            for i in selected
        )

        # 合并角色
        merged_chars = []
        seen = set()
        for i in selected:
            for ch in self._scenes_data[i].get('characters', []):
                if ch not in seen:
                    merged_chars.append(ch)
                    seen.add(ch)

        # 合并时长
        merged_duration = sum(self._scenes_data[i].get('duration', 4.0) for i in selected)

        # 使用第一个场景作为基础
        first_idx = selected[0]
        merged = dict(self._scenes_data[first_idx])
        merged['subtitle_text'] = merged_text
        merged['scene_text'] = merged_text
        merged['characters'] = merged_chars
        merged['duration'] = merged_duration

        # 从后往前删除选中场景，保留第一个
        for i in sorted(selected[1:], reverse=True):
            del self._scenes_data[i]

        self._scenes_data[first_idx] = merged

        self._rebuild_cards()
        self.scenes_changed.emit(self.get_scenes())

    def _split_selected(self):
        """拆分选中的场景（按句号/换行拆分）"""
        selected = self._get_selected_indices()
        if len(selected) != 1:
            return

        idx = selected[0]
        scene = self._scenes_data[idx]
        text = scene.get('subtitle_text', '') or scene.get('scene_text', '')

        # 按换行或句号拆分
        import re
        parts = re.split(r'[。\n]+', text)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) < 2:
            return

        # 替换原场景为多个
        base_chars = scene.get('characters', [])
        new_scenes = []
        for part in parts:
            new_scene = dict(scene)
            new_scene['subtitle_text'] = part
            new_scene['scene_text'] = part
            new_scene['characters'] = list(base_chars)
            new_scene['duration'] = max(2.0, scene.get('duration', 4.0) / len(parts))
            new_scenes.append(new_scene)

        self._scenes_data[idx:idx + 1] = new_scenes

        self._rebuild_cards()
        self.scenes_changed.emit(self.get_scenes())

    def _move_up(self):
        """上移选中场景"""
        selected = self._get_selected_indices()
        if not selected or selected[0] == 0:
            return

        for idx in selected:
            if idx > 0:
                self._scenes_data[idx], self._scenes_data[idx - 1] = \
                    self._scenes_data[idx - 1], self._scenes_data[idx]

        self._rebuild_cards()
        # 重新选中移动后的位置
        for card in self._cards:
            if card.index in [i - 1 for i in selected]:
                card.set_selected(True)

        self.scenes_changed.emit(self.get_scenes())

    def _move_down(self):
        """下移选中场景"""
        selected = self._get_selected_indices()
        if not selected or selected[-1] >= len(self._scenes_data) - 1:
            return

        for idx in reversed(selected):
            if idx < len(self._scenes_data) - 1:
                self._scenes_data[idx], self._scenes_data[idx + 1] = \
                    self._scenes_data[idx + 1], self._scenes_data[idx]

        self._rebuild_cards()
        # 重新选中
        for card in self._cards:
            if card.index in [i + 1 for i in selected]:
                card.set_selected(True)

        self.scenes_changed.emit(self.get_scenes())

    def get_scenes(self) -> List[Dict[str, Any]]:
        """获取当前场景数据"""
        return [dict(s) for s in self._scenes_data]
