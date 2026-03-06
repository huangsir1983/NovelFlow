"""
涛割 - 导入按钮组（动画弹出）
双击画布后从点击位置向上依次弹出导入按钮。
"""

from typing import Callable, Optional, List

from PyQt6.QtWidgets import QGraphicsObject, QGraphicsScene, QStyleOptionGraphicsItem
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, pyqtProperty, QPropertyAnimation,
    QEasingCurve, QTimer,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QFontMetrics, QCursor,
)

from ui import theme
from ui.components.base_canvas_view import LOD_TEXT_MIN_PX


class ImportButton(QGraphicsObject):
    """
    单个导入按钮 — 180x44 圆角矩形。
    继承 QGraphicsObject 以支持 QPropertyAnimation 驱动 pos/opacity。
    """

    BTN_WIDTH = 180
    BTN_HEIGHT = 44
    CORNER_RADIUS = 10

    def __init__(self, label: str, icon_char: str, callback: Callable, parent=None):
        super().__init__(parent)
        self._label = label
        self._icon_char = icon_char
        self._callback = callback
        self._hovered = False
        self._opacity_val = 0.0

        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setZValue(1000)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.BTN_WIDTH, self.BTN_HEIGHT)

    @pyqtProperty(float)
    def btn_opacity(self) -> float:
        return self._opacity_val

    @btn_opacity.setter
    def btn_opacity(self, val: float):
        self._opacity_val = val
        self.setOpacity(val)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect()
        dark = theme.is_dark()

        # 背景
        path = QPainterPath()
        path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        if self._hovered:
            bg = QColor(theme.accent())
        else:
            bg = QColor(45, 45, 52, 230) if dark else QColor(255, 255, 255, 240)
        painter.fillPath(path, QBrush(bg))

        # 边框
        if not self._hovered:
            painter.setPen(QPen(QColor(theme.border()), 1))
            painter.drawPath(path)

        _lod = QStyleOptionGraphicsItem.levelOfDetailFromTransform(painter.worldTransform())
        _hide_text = (_lod * 10 < LOD_TEXT_MIN_PX)
        if _hide_text:
            return

        # 图标字符
        icon_font = QFont("Microsoft YaHei", 16)
        painter.setFont(icon_font)
        if self._hovered:
            painter.setPen(QColor(255, 255, 255))
        else:
            painter.setPen(QColor(theme.accent()))
        painter.drawText(
            QRectF(12, 0, 32, self.BTN_HEIGHT),
            Qt.AlignmentFlag.AlignCenter,
            self._icon_char,
        )

        # 标签文本
        label_font = QFont("Microsoft YaHei", 11, QFont.Weight.Medium)
        painter.setFont(label_font)
        if self._hovered:
            painter.setPen(QColor(255, 255, 255))
        else:
            painter.setPen(QColor(theme.text_primary()))
        painter.drawText(
            QRectF(48, 0, self.BTN_WIDTH - 60, self.BTN_HEIGHT),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._label,
        )

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._callback()
            event.accept()


class ImportPopup:
    """
    管理 3 个 ImportButton 的动画弹出和隐藏。
    show_at(scene_pos, scene) 在指定位置创建按钮并依次弹出。
    """

    BUTTON_GAP = 12
    ANIM_DURATION = 350
    ANIM_STAGGER = 100

    def __init__(self):
        self._buttons: List[ImportButton] = []
        self._anims: List[QPropertyAnimation] = []
        self._scene: Optional[QGraphicsScene] = None
        self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible

    def show_at(self, scene_pos: QPointF, scene: QGraphicsScene,
                callbacks: List[tuple]):
        """
        在 scene_pos 位置弹出按钮组。
        callbacks: [(label, icon_char, callback), ...]
        """
        self.hide(immediate=True)
        self._scene = scene
        self._visible = True

        total_h = len(callbacks) * (ImportButton.BTN_HEIGHT + self.BUTTON_GAP)
        start_x = scene_pos.x() - ImportButton.BTN_WIDTH / 2

        for i, (label, icon, cb) in enumerate(callbacks):
            btn = ImportButton(label, icon, cb)
            # 初始位置在点击位置
            final_y = scene_pos.y() - (i + 1) * (ImportButton.BTN_HEIGHT + self.BUTTON_GAP)
            btn.setPos(start_x, scene_pos.y())
            btn.setOpacity(0.0)
            scene.addItem(btn)
            self._buttons.append(btn)

            # 位置动画
            pos_anim = QPropertyAnimation(btn, b"pos")
            pos_anim.setDuration(self.ANIM_DURATION)
            pos_anim.setStartValue(QPointF(start_x, scene_pos.y()))
            pos_anim.setEndValue(QPointF(start_x, final_y))
            pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)

            # 透明度动画
            opacity_anim = QPropertyAnimation(btn, b"btn_opacity")
            opacity_anim.setDuration(self.ANIM_DURATION)
            opacity_anim.setStartValue(0.0)
            opacity_anim.setEndValue(1.0)
            opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            # 延迟启动
            QTimer.singleShot(i * self.ANIM_STAGGER, pos_anim.start)
            QTimer.singleShot(i * self.ANIM_STAGGER, opacity_anim.start)

            self._anims.extend([pos_anim, opacity_anim])

    def hide(self, immediate: bool = False):
        """隐藏并移除所有按钮"""
        # 停止所有动画
        for anim in self._anims:
            anim.stop()
        self._anims.clear()

        for btn in self._buttons:
            if btn.scene():
                btn.scene().removeItem(btn)
        self._buttons.clear()
        self._visible = False

    def contains_item(self, item) -> bool:
        """检查 item 是否是弹出按钮之一"""
        return item in self._buttons
