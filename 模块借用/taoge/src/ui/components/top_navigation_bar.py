"""
涛割 - 顶部导航栏 (Apple 风格)
极简设计：左上角返回圆钮 + 居中四按钮分段控件 + 右侧 Mac 红绿灯窗口按钮
无标题栏模式下导航栏空白区域可拖拽移动窗口
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QFrame, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent
from PyQt6.QtGui import QPainter, QColor, QPen


class AppleBackButton(QPushButton):
    """
    苹果风格圆形返回按钮
    半透明圆底 + chevron-left 箭头，支持深色/浅色
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("返回主页")
        self._hovered = False
        self._dark = True

    def set_dark(self, dark: bool):
        self._dark = dark
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 圆形背景
        if self._dark:
            bg_alpha = 20 if self._hovered else 8
            p.setBrush(QColor(255, 255, 255, bg_alpha))
        else:
            bg_alpha = 30 if self._hovered else 12
            p.setBrush(QColor(0, 0, 0, bg_alpha))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 32, 32)

        # chevron-left 箭头
        if self._dark:
            arrow_alpha = 200 if self._hovered else 140
            pen = QPen(QColor(255, 255, 255, arrow_alpha))
        else:
            arrow_alpha = 220 if self._hovered else 160
            pen = QPen(QColor(0, 0, 0, arrow_alpha))
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        cx, cy = 18, 18
        p.drawLine(int(cx + 2), int(cy - 6), int(cx - 4), cy)
        p.drawLine(int(cx - 4), cy, int(cx + 2), int(cy + 6))

        p.end()


class TrafficLightButton(QPushButton):
    """
    Mac 红绿灯风格窗口控制按钮
    小圆点，hover 时显示图标符号
    """

    # 按钮类型
    CLOSE = "close"
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"

    # 颜色定义
    COLORS = {
        "close": QColor(255, 95, 87),       # 红
        "minimize": QColor(255, 189, 46),    # 黄
        "maximize": QColor(39, 201, 63),     # 绿
    }
    COLORS_HOVER = {
        "close": QColor(255, 70, 60),
        "minimize": QColor(230, 170, 30),
        "maximize": QColor(30, 180, 50),
    }
    COLORS_INACTIVE = {
        "close": QColor(128, 128, 128, 80),
        "minimize": QColor(128, 128, 128, 80),
        "maximize": QColor(128, 128, 128, 80),
    }

    def __init__(self, btn_type: str, parent=None):
        super().__init__(parent)
        self._type = btn_type
        self._hovered = False
        self._group_hovered = False  # 整组 hover
        self.setFixedSize(14, 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        tooltips = {"close": "关闭", "minimize": "最小化", "maximize": "最大化/还原"}
        self.setToolTip(tooltips.get(btn_type, ""))

    def set_group_hovered(self, hovered: bool):
        self._group_hovered = hovered
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 始终显示彩色，hover 时颜色加深
        if self._hovered:
            color = self.COLORS_HOVER[self._type]
        else:
            color = self.COLORS[self._type]

        # 圆形
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(1, 1, 12, 12)

        # 始终画图标
        icon_pen = QPen(QColor(80, 30, 20, 200) if self._type == "close" else QColor(50, 50, 0, 180))
        icon_pen.setWidthF(1.4)
        icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(icon_pen)

        cx, cy = 7, 7
        if self._type == self.CLOSE:
            # X
            p.drawLine(int(cx - 2.5), int(cy - 2.5), int(cx + 2.5), int(cy + 2.5))
            p.drawLine(int(cx + 2.5), int(cy - 2.5), int(cx - 2.5), int(cy + 2.5))
        elif self._type == self.MINIMIZE:
            # —
            p.drawLine(int(cx - 3), cy, int(cx + 3), cy)
        elif self._type == self.MAXIMIZE:
            # △ (三角/全屏符号简化为对角箭头)
            p.drawLine(int(cx - 2.5), int(cy + 2), int(cx - 2.5), int(cy - 2.5))
            p.drawLine(int(cx - 2.5), int(cy - 2.5), int(cx + 2), int(cy - 2.5))
            p.drawLine(int(cx + 2.5), int(cy - 2), int(cx + 2.5), int(cy + 2.5))
            p.drawLine(int(cx + 2.5), int(cy + 2.5), int(cx - 2), int(cy + 2.5))

        p.end()


class TrafficLightGroup(QWidget):
    """
    Mac 红绿灯按钮组（关闭 + 最小化 + 最大化）
    整组 hover 时所有按钮显示彩色
    """

    close_clicked = pyqtSignal()
    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(62, 14)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.btn_close = TrafficLightButton(TrafficLightButton.CLOSE)
        self.btn_minimize = TrafficLightButton(TrafficLightButton.MINIMIZE)
        self.btn_maximize = TrafficLightButton(TrafficLightButton.MAXIMIZE)

        self.btn_close.clicked.connect(self.close_clicked.emit)
        self.btn_minimize.clicked.connect(self.minimize_clicked.emit)
        self.btn_maximize.clicked.connect(self.maximize_clicked.emit)

        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_maximize)
        layout.addWidget(self.btn_close)

        self._buttons = [self.btn_minimize, self.btn_maximize, self.btn_close]

    def enterEvent(self, event):
        for btn in self._buttons:
            btn.set_group_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        for btn in self._buttons:
            btn.set_group_hovered(False)
        super().leaveEvent(event)


class SegmentedControl(QFrame):
    """
    苹果风格分段控件 (Segmented Control)
    带圆角胶囊背景 + 滑动选中指示器
    """

    segment_clicked = pyqtSignal(int)

    def __init__(self, labels: list, parent=None):
        super().__init__(parent)
        self._labels = labels
        self._buttons = []
        self._active = 0
        self._dark = True

        self.setFixedHeight(36)
        self.setObjectName("segmentedControl")

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        for i, label in enumerate(self._labels):
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._on_clicked(idx))
            btn.setObjectName(f"seg_{i}")
            self._buttons.append(btn)
            layout.addWidget(btn)

        if self._buttons:
            self._buttons[0].setChecked(True)

        self._apply_style()

    def _on_clicked(self, index: int):
        self.set_active(index)
        self.segment_clicked.emit(index)

    def set_active(self, index: int):
        self._active = index
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)

    def set_dark(self, dark: bool):
        self._dark = dark
        self._apply_style()

    def _apply_style(self):
        if self._dark:
            self.setStyleSheet("""
                QFrame#segmentedControl {
                    background-color: rgba(255, 255, 255, 0.06);
                    border-radius: 18px;
                    border: 1px solid rgba(255, 255, 255, 0.04);
                }
            """)
            for btn in self._buttons:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: rgba(255, 255, 255, 0.50);
                        border: none;
                        border-radius: 15px;
                        padding: 4px 20px;
                        font-size: 10pt;
                        font-weight: 600;
                        font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif;
                    }
                    QPushButton:hover {
                        color: rgba(255, 255, 255, 0.75);
                    }
                    QPushButton:checked {
                        background-color: rgba(255, 255, 255, 0.12);
                        color: #ffffff;
                    }
                """)
        else:
            self.setStyleSheet("""
                QFrame#segmentedControl {
                    background-color: rgba(0, 0, 0, 0.06);
                    border-radius: 18px;
                    border: 1px solid rgba(0, 0, 0, 0.04);
                }
            """)
            for btn in self._buttons:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: rgba(0, 0, 0, 0.45);
                        border: none;
                        border-radius: 15px;
                        padding: 4px 20px;
                        font-size: 10pt;
                        font-weight: 600;
                        font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif;
                    }
                    QPushButton:hover {
                        color: rgba(0, 0, 0, 0.70);
                    }
                    QPushButton:checked {
                        background-color: rgba(255, 255, 255, 0.85);
                        color: #1c1c1e;
                    }
                """)


class TopNavigationBar(QFrame):
    """
    苹果风格顶部导航栏
    - 通透背景，融入画布
    - 左上角：苹果圆形返回按钮
    - 正中央：四按钮分段控件
    - 右侧：Mac 红绿灯窗口按钮（关闭/最小化/最大化）
    - 空白区域可拖拽移动窗口
    """

    zone_requested = pyqtSignal(int)
    back_requested = pyqtSignal()
    project_name_changed = pyqtSignal(str)  # 项目名编辑完成

    ZONE_NAMES = ["剧本", "角色道具", "导演画布", "预编辑", "Animatic"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_zone = 0
        self._drag_pos = None  # 拖拽窗口用

        self.setFixedHeight(40)
        self.setObjectName("topNavigationBar")
        self.setStyleSheet("""
            QFrame#topNavigationBar {
                background-color: transparent;
                border: none;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 2, 16, 2)
        layout.setSpacing(0)

        # === 左侧：返回按钮 ===
        self.back_btn = AppleBackButton()
        self.back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_btn)

        # === 项目名标签 + 编辑框 ===
        self._project_name_label = QLabel("")
        self._project_name_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.65); font-size: 12px; "
            "font-weight: 500; padding-left: 8px; background: transparent;"
        )
        self._project_name_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._project_name_label.setToolTip("双击编辑项目名")
        self._project_name_label.installEventFilter(self)
        layout.addWidget(self._project_name_label)

        self._project_name_edit = QLineEdit()
        self._project_name_edit.setFixedHeight(26)
        self._project_name_edit.setMaximumWidth(200)
        self._project_name_edit.setStyleSheet(
            "QLineEdit { color: white; background: rgba(255,255,255,0.1); "
            "border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; "
            "padding: 2px 6px; font-size: 12px; }"
        )
        self._project_name_edit.setVisible(False)
        self._project_name_edit.editingFinished.connect(self._finish_name_edit)
        layout.addWidget(self._project_name_edit)

        # 弹性空间 → 把分段控件推到中间
        layout.addStretch(1)

        # === 中间：分段控件 ===
        self.segment = SegmentedControl(self.ZONE_NAMES)
        self.segment.segment_clicked.connect(self._on_zone_clicked)
        layout.addWidget(self.segment)

        # 弹性空间 → 对称
        layout.addStretch(1)

        # === 右侧：Mac 红绿灯窗口按钮 ===
        self.traffic_lights = TrafficLightGroup()
        self.traffic_lights.close_clicked.connect(self._on_close)
        self.traffic_lights.minimize_clicked.connect(self._on_minimize)
        self.traffic_lights.maximize_clicked.connect(self._on_maximize)
        layout.addWidget(self.traffic_lights)

    def _on_zone_clicked(self, index: int):
        self._active_zone = index
        self.zone_requested.emit(index)

    def set_active_zone(self, index: int):
        self._active_zone = index
        self.segment.set_active(index)

    def set_project_info(self, name: str, scene_count: int):
        """更新项目名显示"""
        self._project_name_label.setText(name or "未命名")

    def update_scene_count(self, count: int):
        """保留接口兼容"""
        pass

    def _start_name_edit(self):
        """双击项目名 → 切换到编辑模式"""
        self._project_name_label.setVisible(False)
        self._project_name_edit.setText(self._project_name_label.text())
        self._project_name_edit.setVisible(True)
        self._project_name_edit.setFocus()
        self._project_name_edit.selectAll()

    def _finish_name_edit(self):
        """编辑完成 → 切回 label"""
        new_name = self._project_name_edit.text().strip()
        self._project_name_edit.setVisible(False)
        self._project_name_label.setVisible(True)
        if new_name and new_name != self._project_name_label.text():
            self._project_name_label.setText(new_name)
            self.project_name_changed.emit(new_name)

    def eventFilter(self, obj, event):
        """拦截项目名 label 的双击事件"""
        if obj is self._project_name_label and event.type() == QEvent.Type.MouseButtonDblClick:
            self._start_name_edit()
            return True
        return super().eventFilter(obj, event)

    def set_theme(self, dark: bool):
        """切换深色/浅色主题"""
        self.back_btn.set_dark(dark)
        self.segment.set_dark(dark)

    # ==================== 窗口控制 ====================

    def _on_close(self):
        w = self.window()
        if w:
            w.close()

    def _on_minimize(self):
        w = self.window()
        if w:
            w.showMinimized()

    def _on_maximize(self):
        w = self.window()
        if w:
            if w.isMaximized():
                w.showNormal()
            else:
                w.showMaximized()

    # ==================== 拖拽移动窗口 ====================

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            w = self.window()
            if w:
                if w.isMaximized():
                    # 最大化状态：记录位置，mouseMoveEvent 中先还原再交给系统
                    self._drag_pos = event.globalPosition().toPoint()
                else:
                    # 非最大化：直接使用系统原生拖拽（避免 setGeometry 警告）
                    wh = w.windowHandle()
                    if wh:
                        wh.startSystemMove()
                    self._drag_pos = None
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            w = self.window()
            if w and w.isMaximized():
                # 从最大化状态拖出：先还原，再交给系统原生拖拽
                ratio = event.position().x() / self.width()
                w.showNormal()
                new_x = int(event.globalPosition().x() - w.width() * ratio)
                new_y = int(event.globalPosition().y() - 20)
                w.move(new_x, new_y)
                self._drag_pos = None
                # 交给操作系统继续处理拖拽（原生支持多显示器 + Aero Snap）
                wh = w.windowHandle()
                if wh:
                    wh.startSystemMove()
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击导航栏空白区域 → 最大化/还原"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
