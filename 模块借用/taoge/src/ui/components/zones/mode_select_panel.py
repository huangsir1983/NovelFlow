"""
涛割 - 模式选择面板
两张大卡片：剧情模式 / 解说模式
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

from ui import theme


class _ModeCard(QFrame):
    """模式选择卡片"""

    clicked = pyqtSignal()

    def __init__(self, title: str, subtitle: str, icon_text: str, description: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._hovered = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(220)
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        # 图标
        icon_label = QLabel(icon_text)
        icon_label.setFont(QFont("Arial", 36))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        # 标题
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("background: transparent;")
        layout.addWidget(title_label)

        # 副标题
        sub_label = QLabel(subtitle)
        sub_label.setFont(QFont("Arial", 12))
        sub_label.setStyleSheet("background: transparent;")
        layout.addWidget(sub_label)

        # 描述
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 11))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("background: transparent;")
        layout.addWidget(desc_label)

        layout.addStretch()

        self._title_label = title_label
        self._sub_label = sub_label
        self._desc_label = desc_label
        self._icon_label = icon_label

    def enterEvent(self, event):
        self._hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def apply_theme(self):
        self._update_style()

    def _update_style(self):
        if self._hovered:
            bg = theme.bg_tertiary()
            border_color = theme.accent()
        else:
            bg = theme.bg_secondary()
            border_color = theme.border()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 2px solid {border_color};
                border-radius: 16px;
            }}
        """)
        self._title_label.setStyleSheet(f"color: {theme.text_primary()}; background: transparent;")
        self._sub_label.setStyleSheet(f"color: {theme.text_secondary()}; background: transparent;")
        self._desc_label.setStyleSheet(f"color: {theme.text_tertiary()}; background: transparent;")
        self._icon_label.setStyleSheet("background: transparent;")


class ModeSelectPanel(QWidget):
    """
    模式选择面板 - 两张大卡片
    信号: mode_selected(str)  "story" / "commentary"
    """

    mode_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 40)
        layout.setSpacing(20)

        # 顶部标题
        header = QLabel("选择创作模式")
        header.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        sub_header = QLabel("根据你的资产类型选择合适的工作流")
        sub_header.setFont(QFont("Arial", 13))
        sub_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_header)

        layout.addSpacing(20)

        # 卡片行
        card_row = QHBoxLayout()
        card_row.setSpacing(24)
        card_row.addStretch()

        # 剧情模式卡片
        self._story_card = _ModeCard(
            title="剧情模式",
            subtitle="小说 / 剧本 / 故事文本",
            icon_text="\U0001F3AC",  # 🎬
            description="导入小说或剧本，AI 自动拆分为场次和分镜，\n生成结构化视觉提示词，适合连续叙事类短剧。",
        )
        self._story_card.clicked.connect(lambda: self.mode_selected.emit("story"))
        card_row.addWidget(self._story_card)

        # 解说模式卡片
        self._commentary_card = _ModeCard(
            title="解说模式",
            subtitle="SRT 字幕 / 解说文案",
            icon_text="\U0001F399",  # 🎙
            description="导入 SRT 字幕或解说文案，按时间轴自动分割场景，\n适合知识科普、新闻解说等非叙事类内容。",
        )
        self._commentary_card.clicked.connect(lambda: self.mode_selected.emit("commentary"))
        card_row.addWidget(self._commentary_card)

        card_row.addStretch()
        layout.addLayout(card_row)

        layout.addStretch()

        self._header = header
        self._sub_header = sub_header

    def apply_theme(self):
        self._header.setStyleSheet(f"color: {theme.text_primary()};")
        self._sub_header.setStyleSheet(f"color: {theme.text_secondary()};")
        self._story_card.apply_theme()
        self._commentary_card.apply_theme()
