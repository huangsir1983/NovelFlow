"""
涛割 - 轻量全屏图片预览对话框（公共组件）
"""

from typing import Optional

from PyQt6.QtWidgets import QDialog, QApplication
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor


class ImagePreviewDialog(QDialog):
    """轻量全屏图片预览 — 半透明黑色背景，居中显示图片，点击/Esc关闭"""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)

        # 获取屏幕尺寸
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
        else:
            geo = QRectF(0, 0, 1920, 1080).toRect()

        self.setGeometry(geo)

        self._pixmap = pixmap
        self._scaled: Optional[QPixmap] = None

        # 计算缩放后图片（最大不超过屏幕 90%）
        max_w = int(geo.width() * 0.9)
        max_h = int(geo.height() * 0.9)
        pw, ph = pixmap.width(), pixmap.height()
        if pw > 0 and ph > 0:
            scale = min(max_w / pw, max_h / ph, 1.0)
            self._scaled = pixmap.scaled(
                int(pw * scale), int(ph * scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

    def paintEvent(self, event):
        painter = QPainter(self)
        # 半透明黑色背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 216))

        # 居中绘制图片
        if self._scaled and not self._scaled.isNull():
            x = (self.width() - self._scaled.width()) // 2
            y = (self.height() - self._scaled.height()) // 2
            painter.drawPixmap(x, y, self._scaled)

        painter.end()

    def mousePressEvent(self, event):
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        super().keyPressEvent(event)
