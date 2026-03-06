"""
涛割 - 底部控制台浮动栏
底部居中的浮动控制栏，包含场景化、场景分析、分镜化三个按钮。
每个按钮上方可叠加 4px 进度条。
支持上下文感知的滑入/滑出动画。
"""

from typing import Optional, Set

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QProgressBar,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QRect, QEasingCurve,
)
from PyQt6.QtGui import QFont

from ui import theme


class BottomConsoleBar(QWidget):
    """
    底部控制台浮动栏 — viewport 子控件。
    三个按钮：场景化 | 场景分析 | 分镜化
    通过父视图 resizeEvent + _position_console_bar() 定位在底部居中。

    上下文感知模式：
    - set_active_button() 设置当前应显示的按钮
    - slide_up() / slide_down() 控制滑入/滑出动画
    """

    scene_split_requested = pyqtSignal()
    scene_analysis_requested = pyqtSignal()
    shot_split_requested = pyqtSignal()

    # 按钮名 → 内部 key 映射
    _BTN_KEYS = ("scene_split", "scene_analysis", "shot_split")

    # 动画参数
    SLIDE_DURATION = 200  # ms
    SLIDE_OFFSET = 60     # 滑入/滑出的像素偏移

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("console_bar_root")
        self.setFixedHeight(60)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # 按钮和进度条引用
        self._buttons: dict[str, QPushButton] = {}
        self._progress_bars: dict[str, QProgressBar] = {}
        self._original_texts: dict[str, str] = {}

        # 滑入/滑出动画状态
        self._slide_anim: Optional[QPropertyAnimation] = None
        self._is_visible_state = False  # 逻辑可见性（区别于 QWidget.isVisible()）

        # 上下文感知按钮模式
        self._active_button: Optional[str] = None  # "scene_split" / "scene_analysis" / "shot_split"
        self._active_mode: str = 'all'              # "all" / "single" / "selected"
        self._target_act_ids: Optional[Set[int]] = None

        self._init_ui()
        self._apply_theme()
        # 初始隐藏
        self.setVisible(False)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 8)
        layout.setSpacing(12)

        btn_font = QFont("Microsoft YaHei", 10, QFont.Weight.Medium)

        btn_configs = [
            ("scene_split", "场景化", self.scene_split_requested),
            ("scene_analysis", "场景分析", self.scene_analysis_requested),
            ("shot_split", "分镜化", self.shot_split_requested),
        ]

        # 每个按钮的容器 QWidget，方便整体隐藏/显示
        self._btn_containers: dict[str, QWidget] = {}

        for key, text, signal in btn_configs:
            container = QWidget()
            container.setStyleSheet("background: transparent; border: none;")
            group = QVBoxLayout(container)
            group.setContentsMargins(0, 0, 0, 0)
            group.setSpacing(2)

            # 进度条（4px 高，默认隐藏）
            bar = QProgressBar()
            bar.setFixedHeight(4)
            bar.setTextVisible(False)
            bar.setVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: rgba(255, 255, 255, 0.1);
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background: {theme.accent()};
                    border-radius: 2px;
                }}
            """)
            group.addWidget(bar)
            self._progress_bars[key] = bar

            # 按钮
            btn = QPushButton(text)
            btn.setFont(btn_font)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setEnabled(False)
            btn.clicked.connect(signal.emit)
            group.addWidget(btn)
            self._buttons[key] = btn
            self._original_texts[key] = text

            # 默认隐藏容器
            container.setVisible(False)
            self._btn_containers[key] = container
            layout.addWidget(container)

        # 快捷属性
        self._scene_split_btn = self._buttons["scene_split"]
        self._scene_analysis_btn = self._buttons["scene_analysis"]
        self._shot_split_btn = self._buttons["shot_split"]

    # ==================== 滑入/滑出动画 ====================

    @property
    def is_visible_state(self) -> bool:
        """逻辑可见性（动画进行中也返回目标状态）"""
        return self._is_visible_state

    def slide_up(self):
        """从下方滑入视口"""
        if self._is_visible_state:
            return
        self._is_visible_state = True
        self._stop_anim()

        # 确保可见并在正确的 Z 层级
        self.setVisible(True)
        self.raise_()

        # 计算目标位置（正常位置）和起始位置（下方偏移）
        target_geo = self.geometry()
        start_geo = QRect(
            target_geo.x(),
            target_geo.y() + self.SLIDE_OFFSET,
            target_geo.width(),
            target_geo.height(),
        )

        self._slide_anim = QPropertyAnimation(self, b"geometry")
        self._slide_anim.setDuration(self.SLIDE_DURATION)
        self._slide_anim.setStartValue(start_geo)
        self._slide_anim.setEndValue(target_geo)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._slide_anim.start()

    def slide_down(self):
        """滑出到下方并隐藏"""
        if not self._is_visible_state:
            return
        self._is_visible_state = False
        self._stop_anim()

        start_geo = self.geometry()
        end_geo = QRect(
            start_geo.x(),
            start_geo.y() + self.SLIDE_OFFSET,
            start_geo.width(),
            start_geo.height(),
        )

        self._slide_anim = QPropertyAnimation(self, b"geometry")
        self._slide_anim.setDuration(self.SLIDE_DURATION)
        self._slide_anim.setStartValue(start_geo)
        self._slide_anim.setEndValue(end_geo)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._slide_anim.finished.connect(self._on_slide_down_finished)
        self._slide_anim.start()

    def _on_slide_down_finished(self):
        """滑出动画完成后隐藏"""
        if not self._is_visible_state:
            self.setVisible(False)

    def _stop_anim(self):
        """停止正在进行的动画"""
        if self._slide_anim and self._slide_anim.state() == QPropertyAnimation.State.Running:
            self._slide_anim.stop()
            self._slide_anim = None

    # ==================== 上下文感知按钮模式 ====================

    # 按钮名 → 显示文本模板
    _MODE_LABELS = {
        "scene_split": {
            "all": "场景化",
        },
        "scene_analysis": {
            "all": "场景分析",
            "single": "场景分析（本组）",
        },
        "shot_split": {
            "all": "分镜化",
            "single": "分镜化（本场景）",
            "selected": "分镜化（{n}个场景）",
        },
    }

    def set_active_button(self, button_name: Optional[str],
                          mode: str = 'all',
                          target_act_ids: Optional[Set[int]] = None):
        """设置当前激活的按钮。None 表示无激活按钮。
        只显示激活的那一个按钮，其余隐藏。

        button_name: "scene_split" / "scene_analysis" / "shot_split" / None
        mode: "all" / "single" / "selected"
        target_act_ids: 用于 single/selected 模式
        """
        self._active_button = button_name
        self._active_mode = mode
        self._target_act_ids = target_act_ids

        if button_name is None:
            # 全部隐藏
            for key in self._btn_containers:
                self._btn_containers[key].setVisible(False)
                self._buttons[key].setEnabled(False)
            return

        # 只显示指定按钮的容器，其余隐藏
        for key in self._btn_containers:
            if key == button_name:
                self._btn_containers[key].setVisible(True)
                btn = self._buttons[key]
                btn.setEnabled(True)
                # 更新按钮文本
                label_map = self._MODE_LABELS.get(key, {})
                label = label_map.get(mode, label_map.get('all', self._original_texts[key]))
                if '{n}' in label and target_act_ids:
                    label = label.replace('{n}', str(len(target_act_ids)))
                btn.setText(label)
                self._update_btn_style(btn, True)
            else:
                self._btn_containers[key].setVisible(False)
                self._buttons[key].setEnabled(False)

    # ==================== 进度条 API ====================

    _PROGRESS_LABELS = {
        "scene_split": "场景化中...",
        "scene_analysis": "分析中...",
        "shot_split": "分镜化中...",
    }

    def start_progress(self, button_name: str):
        """显示对应按钮的进度条（初始 0%），按钮文本改为进行中提示"""
        bar = self._progress_bars.get(button_name)
        btn = self._buttons.get(button_name)
        if not bar or not btn:
            return
        # 确保该按钮容器可见
        container = self._btn_containers.get(button_name)
        if container:
            container.setVisible(True)
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setVisible(True)
        btn.setText(self._PROGRESS_LABELS.get(button_name, "处理中..."))
        btn.setEnabled(False)
        self._update_btn_style(btn, False)

    def update_progress(self, button_name: str, value: int, maximum: int):
        """更新进度条数值"""
        bar = self._progress_bars.get(button_name)
        if not bar:
            return
        bar.setRange(0, maximum)
        bar.setValue(value)

    def finish_progress(self, button_name: str):
        """隐藏进度条，恢复按钮文本"""
        bar = self._progress_bars.get(button_name)
        btn = self._buttons.get(button_name)
        if not bar or not btn:
            return
        bar.setVisible(False)
        btn.setText(self._original_texts.get(button_name, ""))

    # ==================== 按钮启用 API（向后兼容） ====================

    def set_scene_split_enabled(self, enabled: bool):
        self._scene_split_btn.setEnabled(enabled)
        self._update_btn_style(self._scene_split_btn, enabled)
        self._btn_containers["scene_split"].setVisible(enabled)

    def set_scene_analysis_enabled(self, enabled: bool):
        self._scene_analysis_btn.setEnabled(enabled)
        self._update_btn_style(self._scene_analysis_btn, enabled)
        self._btn_containers["scene_analysis"].setVisible(enabled)

    def set_shot_split_enabled(self, enabled: bool):
        self._shot_split_btn.setEnabled(enabled)
        self._update_btn_style(self._shot_split_btn, enabled)
        self._btn_containers["shot_split"].setVisible(enabled)

    def _update_btn_style(self, btn: QPushButton, enabled: bool):
        """根据启用状态更新单个按钮样式"""
        if enabled:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.accent()};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 20px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {theme.accent_hover()};
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.bg_tertiary()};
                    color: {theme.text_tertiary()};
                    border: 1px solid {theme.border()};
                    border-radius: 8px;
                    padding: 6px 20px;
                    font-size: 12px;
                    font-weight: 500;
                }}
            """)

    def _apply_theme(self):
        """应用主题"""
        dark = theme.is_dark()
        if dark:
            self.setStyleSheet("""
                #console_bar_root {
                    background-color: rgba(30, 30, 34, 220);
                    border-radius: 12px;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                }
            """)
        else:
            self.setStyleSheet("""
                #console_bar_root {
                    background-color: rgba(248, 248, 252, 230);
                    border-radius: 12px;
                    border: 1px solid rgba(0, 0, 0, 0.08);
                }
            """)
        # 初始状态：所有按钮禁用
        for btn in self._buttons.values():
            self._update_btn_style(btn, btn.isEnabled())
        # 更新进度条主题色
        for bar in self._progress_bars.values():
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background: rgba(255, 255, 255, 0.1);
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background: {theme.accent()};
                    border-radius: 2px;
                }}
            """)

    def apply_theme(self):
        self._apply_theme()
