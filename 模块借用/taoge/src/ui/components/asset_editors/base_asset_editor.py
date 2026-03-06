"""
涛割 - 资产编辑器基类
全屏页面框架：顶栏 + QSplitter(上半画布 + 下半信息栏)
子类实现 _create_canvas() 和 _create_info_panel()。
"""

import os
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont

from ui import theme

# ── 资产类型 badge 配色 ──
_TYPE_BADGE = {
    'character': ('#6495ED', '角色'),
    'scene_bg':  ('#50c878', '场景'),
    'prop':      ('#a078dc', '道具'),
    'lighting_ref': ('#FFD700', '照明'),
}


class BaseAssetEditor(QWidget):
    """资产编辑器基类 — 全屏嵌入 MainWindow 的 content_stack"""

    asset_saved = pyqtSignal(int)      # asset_id
    back_requested = pyqtSignal()

    def __init__(self, asset_data: dict, controller, parent=None):
        super().__init__(parent)
        self._asset_data = dict(asset_data)
        self._controller = controller
        self._asset_id = asset_data.get('id')
        self._asset_type = asset_data.get('asset_type', 'character')
        self._modified = False

        self._init_ui()
        self._load_data()

    # ──────── UI 构建 ────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 顶栏 ──
        top_bar = self._build_top_bar()
        root.addWidget(top_bar)

        # ── 分隔线 ──
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {theme.separator()};")
        root.addWidget(sep)

        # ── QSplitter: 上半画布 + 下半信息栏 ──
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setHandleWidth(4)
        self._splitter.setStyleSheet("""
            QSplitter::handle {
                background: rgba(255,255,255,0.06);
            }
            QSplitter::handle:hover {
                background: rgba(255,255,255,0.12);
            }
        """)

        # 上半部分：画布
        self._canvas_widget = self._create_canvas()
        self._splitter.addWidget(self._canvas_widget)

        # 下半部分：信息栏
        self._info_panel = self._create_info_panel()
        self._splitter.addWidget(self._info_panel)

        # 初始比例 6:4
        self._splitter.setStretchFactor(0, 6)
        self._splitter.setStretchFactor(1, 4)

        root.addWidget(self._splitter, 1)

        self.setStyleSheet(f"background: {theme.bg_primary()};")

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"""
            QWidget {{
                background: {theme.bg_secondary()};
            }}
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(12)

        # 返回按钮
        back_btn = QPushButton("← 返回资产库")
        back_btn.setFixedHeight(32)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {theme.accent()};
                font-size: 13px;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                color: {theme.accent_hover()};
            }}
        """)
        back_btn.clicked.connect(self._on_back)
        layout.addWidget(back_btn)

        # 类型 badge
        color, label = _TYPE_BADGE.get(
            self._asset_type, ('#888', '未知')
        )
        badge = QLabel(label)
        badge.setFixedHeight(22)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {color};
                color: white;
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(badge)

        # 资产名
        self._name_label = QLabel(
            self._asset_data.get('name', '未命名')
        )
        self._name_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text_primary()};
                font-size: 15px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        layout.addWidget(self._name_label)

        layout.addStretch()

        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.setFixedSize(72, 32)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.accent()};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme.accent_hover()};
            }}
        """)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        # 删除按钮
        del_btn = QPushButton("删除")
        del_btn.setFixedSize(60, 32)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.danger()};
                border: 1px solid {theme.danger()};
                border-radius: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(255,69,58,0.15);
            }}
        """)
        del_btn.clicked.connect(self._delete)
        layout.addWidget(del_btn)

        return bar

    # ──────── 抽象方法（子类实现）────────

    def _create_canvas(self) -> QWidget:
        """创建上半部分画布区域，子类必须重写"""
        raise NotImplementedError

    def _create_info_panel(self) -> QWidget:
        """创建下半部分信息栏，子类必须重写"""
        raise NotImplementedError

    def _load_data(self):
        """加载资产数据到画布和信息栏，子类必须重写"""
        raise NotImplementedError

    def _collect_data(self) -> dict:
        """从信息栏收集编辑后的数据，子类必须重写"""
        raise NotImplementedError

    # ──────── 共享操作 ────────

    def _save(self):
        data = self._collect_data()
        if not data:
            return

        if self._asset_id:
            ok = self._controller.update_asset(self._asset_id, **data)
            if ok:
                self._name_label.setText(data.get('name', ''))
                self.asset_saved.emit(self._asset_id)
        else:
            result = self._controller.create_asset(
                self._asset_type, data.pop('name', '未命名'),
                data.pop('project_id', None), **data
            )
            if result:
                self._asset_id = result['id']
                self._name_label.setText(result.get('name', ''))
                self.asset_saved.emit(self._asset_id)

    def _delete(self):
        if not self._asset_id:
            self.back_requested.emit()
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除「{self._asset_data.get('name', '')}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._controller.delete_asset(self._asset_id)
            self.back_requested.emit()

    def _on_back(self):
        self.back_requested.emit()

    def update_asset_data(self, new_data: dict):
        """外部更新资产数据（如保存后刷新）"""
        self._asset_data.update(new_data)
        self._asset_id = new_data.get('id', self._asset_id)
        self._name_label.setText(new_data.get('name', ''))
