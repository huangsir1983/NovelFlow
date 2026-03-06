"""
涛割 - 3D 视角控制控件
参照 Qwen-Multiangle-Camera 节点交互（参考截图）：
- 粉红色椭圆环：方位角 azimuth（水平面上的大椭圆，环绕图片前后分层）
- 金色径向线 + 圆点：距离/缩放（圆环内侧，与方位角联动）
- 青色竖直弧 + 圆点：俯仰角 elevation（图片左侧，上下弧线）
- 中心角色图片：透视预览，初始向左旋转20度透视效果
- 反转交互：控制点向左 → 图片向右转；控制点向上 → 图片向下转
- 正面线条（前半环 + 俯仰弧 + 距离线）盖住图片，图片在线的包围中

角度约定：
- 水平角度 azimuth: -180° ~ +180°, 0°=正面, 正=向右, 负=向左
- 垂直角度 elevation: -30° ~ +60°, 0°=平视, 正=俯视, 负=仰视
- 距离 distance: 0 ~ 10
"""

import math
from typing import Optional

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPixmap, QTransform,
    QFont, QRadialGradient, QPainterPath, QPolygonF,
)


class AngleControlCanvas(QWidget):
    """3D 视角控制画布"""

    angle_changed = pyqtSignal(float, float, float)  # azimuth, elevation, distance
    WIDTH = 320
    HEIGHT = 360  # 增高，给底部数值留空间

    # ── 颜色 ──
    COLOR_AZIMUTH   = QColor(255, 100, 150)    # 粉红 — 方位角
    COLOR_ELEVATION = QColor(80, 220, 220)     # 青色 — 俯仰角
    COLOR_DISTANCE  = QColor(240, 200, 80)     # 金色 — 距离
    COLOR_BG        = QColor(25, 25, 35)       # 深色背景

    HANDLE_RADIUS = 8
    HIT_RADIUS    = 20

    # ── 几何参数 ──
    IMAGE_SIZE      = 200                       # 预览图尺寸（放大以看清角色）
    RING_RX         = 140                       # 方位角椭圆长轴（大环）
    RING_RY         = 50                        # 方位角椭圆短轴（透视压缩）
    RING_CY_OFFSET  = 10                        # 环中心相对控件中心向下偏移
    DIST_SCALE_MIN  = 0.15
    DIST_SCALE_MAX  = 0.92
    ELEV_ARC_CX_OFF = -10
    ELEV_RX         = 70
    ELEV_RY         = 120
    AZ_RENDER_OFFSET = 30                       # 正视位在椭圆上稍偏左，匹配固定透视角度
    ELEV_RENDER_OFFSET = -10                     # 俯仰控制点初始向下偏移10°

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        self._azimuth   = 0.0       # -180° ~ +180°
        self._elevation = 0.0       # -30° ~ +60°
        self._distance  = 5.0       # 0 ~ 10

        self._dragging: Optional[str] = None
        self._preview_pixmap: Optional[QPixmap] = None
        self._center = QPointF(self.WIDTH / 2, self.WIDTH / 2)  # 绘图区域中心

        self.setMouseTracking(True)

    # ═══════════════════ 外部接口 ═══════════════════

    def set_image(self, pixmap: QPixmap):
        self._preview_pixmap = pixmap
        self.update()

    def set_azimuth(self, value: float):
        v = value % 360
        if v > 180:
            v -= 360
        self._azimuth = v
        self.update()

    def set_elevation(self, value: float):
        self._elevation = max(-30, min(60, value))
        self.update()

    def set_distance(self, value: float):
        self._distance = max(0, min(10, value))
        self.update()

    @property
    def azimuth(self) -> float:
        return self._azimuth

    @property
    def elevation(self) -> float:
        return self._elevation

    @property
    def distance(self) -> float:
        return self._distance

    # ═══════════════════ 内部角度转换 ═══════════════════

    def _az_to_render(self) -> float:
        """将显示角度转换为椭圆渲染角度

        椭圆参数角: 0°=右端, 90°=底端, 180°=左端, 270°=顶端
        俯视图约定:
        - 底端(90°) = 观察者正前方 = 显示角 0°
        - 右端(0°)  = 角色右侧 = 显示角 +90°（向右转）
        - 左端(180°)= 角色左侧 = 显示角 -90°（向左转）

        display=0°  → render=90°  (底端=正面)
        display=+38°→ render=52°  (偏右=椭圆右下方)
        display=-90°→ render=180° (左端=左侧面)
        display=+90°→ render=0°   (右端=右侧面)
        """
        # render = 90 - display + offset
        return math.radians(90 - self._azimuth + self.AZ_RENDER_OFFSET)

    # ═══════════════════ 环中心 ═══════════════════

    def _ring_center(self):
        return self._center.x(), self._center.y() + self.RING_CY_OFFSET

    # ═══════════════════ 圆点位置计算 ═══════════════════

    def _azimuth_handle_pos(self, rcx, rcy):
        a = self._az_to_render()
        return (rcx + self.RING_RX * math.cos(a),
                rcy + self.RING_RY * math.sin(a))

    def _distance_handle_pos(self, rcx, rcy):
        a = self._az_to_render()
        t = self._distance / 10.0
        s = self.DIST_SCALE_MIN + t * (self.DIST_SCALE_MAX - self.DIST_SCALE_MIN)
        return (rcx + s * self.RING_RX * math.cos(a),
                rcy + s * self.RING_RY * math.sin(a))

    def _elevation_handle_pos(self, rcx, rcy):
        arc_cx = rcx + self.ELEV_ARC_CX_OFF
        arc_cy = rcy - 20
        e = math.radians(self._elevation + self.ELEV_RENDER_OFFSET)
        return (arc_cx - self.ELEV_RX * math.cos(e),
                arc_cy - self.ELEV_RY * math.sin(e))

    # ═══════════════════ 绘制 ═══════════════════

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), self.COLOR_BG)

        rcx, rcy = self._ring_center()

        # ① 方位角环 — 后半（图片后面的半圈，被图片遮挡）
        self._paint_ring_half(p, rcx, rcy, back=True)
        # ② 中心图片（透视变换）
        self._paint_preview(p, rcx, rcy)
        # ③ 方位角环 — 前半（盖住图片，表示在图片前面）
        self._paint_ring_half(p, rcx, rcy, back=False)
        # ④ 青色俯仰弧（盖住图片）
        self._paint_elevation_arc(p, rcx, rcy)
        # ⑤ 金色距离线（盖住图片）
        self._paint_distance_line(p, rcx, rcy)
        # ⑥ 三个控制圆点（最顶层）
        for pos, color in [
            (self._elevation_handle_pos(rcx, rcy), self.COLOR_ELEVATION),
            (self._distance_handle_pos(rcx, rcy),  self.COLOR_DISTANCE),
            (self._azimuth_handle_pos(rcx, rcy),   self.COLOR_AZIMUTH),
        ]:
            self._paint_handle(p, pos[0], pos[1], color)
        # ⑦ 底部数值
        self._paint_values(p)

        p.end()

    def _paint_ring_half(self, p: QPainter, rcx: float, rcy: float, back: bool):
        path = QPainterPath()
        if back:
            start_deg, end_deg = 180, 360
            alpha = 100
            line_width = 2.0
        else:
            start_deg, end_deg = 0, 180
            alpha = 255
            line_width = 2.5

        steps = 80
        for i in range(steps + 1):
            angle = math.radians(start_deg + i * (end_deg - start_deg) / steps)
            x = rcx + self.RING_RX * math.cos(angle)
            y = rcy + self.RING_RY * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        color = QColor(self.COLOR_AZIMUTH)
        color.setAlpha(alpha)
        p.setPen(QPen(color, line_width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def _paint_preview(self, p: QPainter, rcx: float, rcy: float):
        """中心图片 — 真实 3D 透视模拟 + 镜像翻转

        非线性角度映射: effective = -azimuth - 35*cos(azimuth)
        - 0° → -35°（初始向左倾斜）
        - ±90° → ∓90°（正侧面，一条线）
        - 超过±90° → 镜像翻转，继续旋转（背面视角）
        """
        img_cx = rcx
        img_cy = rcy - 35                              # 相对于环中心下移（原 -50）

        if not self._preview_pixmap or self._preview_pixmap.isNull():
            p.setPen(QPen(QColor(80, 80, 80), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            hs = self.IMAGE_SIZE // 2
            p.drawRect(QRectF(img_cx - hs, img_cy - hs, hs * 2, hs * 2))
            return

        pm = self._preview_pixmap.scaled(
            self.IMAGE_SIZE, self.IMAGE_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # ── 非线性角度映射（水平） ──
        # effective = -azimuth - offset * cos(azimuth)
        # 0° → -35°, ±90° → ∓90°, ±180° → ∓145°
        AZ_OFFSET = 35
        effective_deg = -self._azimuth - AZ_OFFSET * math.cos(math.radians(self._azimuth))

        # ── 超过 ±90° → 镜像翻转（正面→背面过渡）──
        mirror = False
        if effective_deg > 90:
            mirror = True
            effective_deg -= 180
        elif effective_deg < -90:
            mirror = True
            effective_deg += 180

        if mirror:
            pm = QPixmap.fromImage(pm.toImage().mirrored(True, False))

        w, h = pm.width(), pm.height()
        hw, hh = w / 2, h / 2

        az_rad = math.radians(effective_deg)
        el_rad = math.radians(self._elevation * 0.5 + 20)  # 反转垂直 + 向下20°偏移

        # ── 虚拟相机参数 ──
        focal = 450.0
        cam_depth = 300.0 + self._distance * 30.0

        # ── 卡片四角 3D 旋转 → 透视投影 ──
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        projected = []

        for cx3, cy3 in corners:
            # 绕 Y 轴旋转（方位角 — 水平转体）
            x1 = cx3 * math.cos(az_rad)
            y1 = cy3
            z1 = cx3 * math.sin(az_rad)

            # 绕 X 轴旋转（俯仰角 — 前后倾斜）
            x2 = x1
            y2 = y1 * math.cos(el_rad) - z1 * math.sin(el_rad)
            z2 = y1 * math.sin(el_rad) + z1 * math.cos(el_rad)

            # 透视投影
            z_final = max(z2 + cam_depth, 1.0)
            px = x2 * focal / z_final + img_cx
            py = y2 * focal / z_final + img_cy
            projected.append(QPointF(px, py))

        src = QPolygonF([
            QPointF(0, 0), QPointF(w, 0),
            QPointF(w, h), QPointF(0, h),
        ])
        dst = QPolygonF(projected)

        t = QTransform()
        ok = QTransform.quadToQuad(src, dst, t)
        if not ok:
            p.drawPixmap(int(img_cx - hw), int(img_cy - hh), pm)
            return

        p.save()
        p.setTransform(t, True)

        # 阴影
        p.setBrush(QBrush(QColor(0, 0, 0, 50)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(3, 3, w, h), 4, 4)

        # 背景垫
        p.setBrush(QBrush(QColor(0, 0, 0, 80)))
        p.drawRoundedRect(QRectF(-3, -3, w + 6, h + 6), 5, 5)

        # 图片
        p.drawPixmap(0, 0, pm)

        # 边框
        p.setPen(QPen(QColor(255, 255, 255, 80), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0, 0, w, h), 3, 3)

        p.restore()

    def _paint_elevation_arc(self, p: QPainter, rcx: float, rcy: float):
        arc_cx = rcx + self.ELEV_ARC_CX_OFF
        arc_cy = rcy - 20
        path = QPainterPath()
        steps = 120
        arc_start, arc_end = -50, 80
        for i in range(steps + 1):
            theta = math.radians(arc_start + i * (arc_end - arc_start) / steps)
            x = arc_cx - self.ELEV_RX * math.cos(theta)
            y = arc_cy - self.ELEV_RY * math.sin(theta)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        p.setPen(QPen(self.COLOR_ELEVATION, 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def _paint_distance_line(self, p: QPainter, rcx: float, rcy: float):
        a = self._az_to_render()
        cos_a, sin_a = math.cos(a), math.sin(a)
        x1 = rcx + self.DIST_SCALE_MIN * self.RING_RX * cos_a
        y1 = rcy + self.DIST_SCALE_MIN * self.RING_RY * sin_a
        x2 = rcx + self.DIST_SCALE_MAX * self.RING_RX * cos_a
        y2 = rcy + self.DIST_SCALE_MAX * self.RING_RY * sin_a
        p.setPen(QPen(self.COLOR_DISTANCE, 2.5))
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _paint_handle(self, p: QPainter, x: float, y: float, color: QColor):
        grad = QRadialGradient(x, y, self.HANDLE_RADIUS * 2.5)
        grad.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 160))
        grad.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x, y),
                       self.HANDLE_RADIUS * 2.5, self.HANDLE_RADIUS * 2.5)
        p.setBrush(QBrush(color))
        p.setPen(QPen(QColor(255, 255, 255), 1.5))
        p.drawEllipse(QPointF(x, y), self.HANDLE_RADIUS, self.HANDLE_RADIUS)

    def _paint_values(self, p: QPainter):
        """底部数值（在控件底部，不与绘图区重叠）"""
        label_font = QFont("Microsoft YaHei", 8)
        value_font = QFont("Microsoft YaHei", 11, QFont.Weight.Bold)
        y_label = self.HEIGHT - 30
        y_value = self.HEIGHT - 12

        p.setFont(label_font)
        p.setPen(QColor(150, 150, 170))
        p.drawText(15, y_label, "水平角度")
        p.setFont(value_font)
        p.setPen(self.COLOR_AZIMUTH)
        p.drawText(15, y_value, f"{self._azimuth:.0f}°")

        p.setFont(label_font)
        p.setPen(QColor(150, 150, 170))
        p.drawText(115, y_label, "垂直角度")
        p.setFont(value_font)
        p.setPen(self.COLOR_ELEVATION)
        p.drawText(115, y_value, f"{self._elevation:.0f}°")

        p.setFont(label_font)
        p.setPen(QColor(150, 150, 170))
        p.drawText(225, y_label, "距离")
        p.setFont(value_font)
        p.setPen(self.COLOR_DISTANCE)
        p.drawText(225, y_value, f"{self._distance:.1f}")

    # ═══════════════════ 交互 ═══════════════════

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = self._hit_test(event.position())
        if self._dragging:
            self._update_value(event.position())

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._update_value(event.position())

    def mouseReleaseEvent(self, event):
        self._dragging = None

    def _hit_test(self, pos: QPointF) -> Optional[str]:
        rcx, rcy = self._ring_center()
        thr = self.HIT_RADIUS
        ax, ay = self._azimuth_handle_pos(rcx, rcy)
        if self._pt_dist(pos, ax, ay) <= thr:
            return 'azimuth'
        dx, dy = self._distance_handle_pos(rcx, rcy)
        if self._pt_dist(pos, dx, dy) <= thr:
            return 'distance'
        ex, ey = self._elevation_handle_pos(rcx, rcy)
        if self._pt_dist(pos, ex, ey) <= thr:
            return 'elevation'
        return None

    def _update_value(self, pos: QPointF):
        rcx, rcy = self._ring_center()

        if self._dragging == 'azimuth':
            nx = (pos.x() - rcx) / self.RING_RX
            ny = (pos.y() - rcy) / self.RING_RY
            render_deg = math.degrees(math.atan2(ny, nx))
            # render = 90 - display + offset → display = 90 + offset - render
            display = 90 + self.AZ_RENDER_OFFSET - render_deg
            # 规范化到 -180 ~ +180
            if display > 180:
                display -= 360
            elif display < -180:
                display += 360
            self._azimuth = display

        elif self._dragging == 'distance':
            a = self._az_to_render()
            cos_a, sin_a = math.cos(a), math.sin(a)
            x1 = rcx + self.DIST_SCALE_MIN * self.RING_RX * cos_a
            y1 = rcy + self.DIST_SCALE_MIN * self.RING_RY * sin_a
            x2 = rcx + self.DIST_SCALE_MAX * self.RING_RX * cos_a
            y2 = rcy + self.DIST_SCALE_MAX * self.RING_RY * sin_a
            ddx, ddy = x2 - x1, y2 - y1
            lsq = ddx * ddx + ddy * ddy
            if lsq > 0:
                t = ((pos.x() - x1) * ddx + (pos.y() - y1) * ddy) / lsq
                t = max(0.0, min(1.0, t))
                self._distance = t * 10.0

        elif self._dragging == 'elevation':
            arc_cx = rcx + self.ELEV_ARC_CX_OFF
            arc_cy = rcy - 20
            nx = -(pos.x() - arc_cx) / self.ELEV_RX
            ny = -(pos.y() - arc_cy) / self.ELEV_RY
            theta = math.degrees(math.atan2(ny, nx))
            self._elevation = max(-30, min(60, theta - self.ELEV_RENDER_OFFSET))

        self.update()
        self.angle_changed.emit(self._azimuth, self._elevation, self._distance)

    @staticmethod
    def _pt_dist(pos: QPointF, x: float, y: float) -> float:
        return math.sqrt((pos.x() - x) ** 2 + (pos.y() - y) ** 2)
