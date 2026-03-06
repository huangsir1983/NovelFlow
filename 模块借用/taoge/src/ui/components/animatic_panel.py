"""
涛割 - Animatic 动态分镜预览面板
时间线 + 预览区 + 播放控件 + 卡顿热力图
"""

import os
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QSplitter, QComboBox,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QPainterPath,
    QPixmap, QTransform,
)

from ui import theme


# ============================================================
#  AnimaticPreviewWidget — 预览区
# ============================================================

class AnimaticPreviewWidget(QWidget):
    """预览区 - 显示当前帧 + Ken Burns 相机动画"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._camera_move = 'Static'
        self._anim_progress = 0.0  # 0.0 ~ 1.0
        self._duration_ms = 3000
        self.setMinimumSize(320, 180)
        self.setStyleSheet("background: black;")

    def set_image(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._anim_progress = 0.0
        self.update()

    def set_camera_move(self, move_type: str, duration_ms: int):
        self._camera_move = move_type
        self._duration_ms = duration_ms
        self._anim_progress = 0.0

    def set_progress(self, progress: float):
        """0.0 ~ 1.0 动画进度"""
        self._anim_progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(0, 0, 0))

        if not self._pixmap or self._pixmap.isNull():
            p.setPen(QPen(QColor(255, 255, 255, 80)))
            p.setFont(QFont("Microsoft YaHei", 14))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无预览图片")
            return

        vw, vh = self.width(), self.height()
        pw, ph = self._pixmap.width(), self._pixmap.height()

        # 计算 Ken Burns 变换
        t = self._anim_progress
        sx, sy, tx, ty = 1.0, 1.0, 0.0, 0.0

        if self._camera_move == 'ZoomIn':
            s = 1.0 + 0.2 * t
            sx, sy = s, s
            tx = -pw * 0.1 * t
            ty = -ph * 0.1 * t
        elif self._camera_move == 'ZoomOut':
            s = 1.2 - 0.2 * t
            sx, sy = s, s
            tx = -pw * 0.1 * (1 - t)
            ty = -ph * 0.1 * (1 - t)
        elif self._camera_move == 'PanLeft':
            tx = pw * 0.15 * t
        elif self._camera_move == 'PanRight':
            tx = -pw * 0.15 * t
        elif self._camera_move == 'TiltUp':
            ty = ph * 0.15 * t
        elif self._camera_move == 'TiltDown':
            ty = -ph * 0.15 * t
        elif self._camera_move == 'Truck':
            tx = -pw * 0.1 * t
            s = 1.0 + 0.05 * t
            sx, sy = s, s
        elif self._camera_move == 'Dolly':
            s = 1.0 + 0.15 * t
            sx, sy = s, s
            tx = -pw * 0.075 * t
            ty = -ph * 0.075 * t

        # 缩放并居中绘制
        scaled = self._pixmap.scaled(
            int(pw * sx), int(ph * sy),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # 适配视口
        display = scaled.scaled(
            vw, vh,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        dx = (display.width() - vw) / 2 - tx * (vw / pw)
        dy = (display.height() - vh) / 2 - ty * (vh / ph)
        p.drawPixmap(0, 0, display,
                      int(dx), int(dy), vw, vh)


# ============================================================
#  TimelineClip — 时间线片段
# ============================================================

class TimelineClip(QGraphicsRectItem):
    """时间线中的单个分镜片段"""

    CLIP_HEIGHT = 60
    MIN_WIDTH = 40

    def __init__(self, scene_data: dict, pixels_per_second: float = 60.0):
        super().__init__()
        self._scene_data = scene_data
        self._pps = pixels_per_second
        self._duration = scene_data.get('duration', 3.0)
        self._thumbnail: Optional[QPixmap] = None
        self._conflict = False

        width = max(self.MIN_WIDTH, self._duration * self._pps)
        self.setRect(0, 0, width, self.CLIP_HEIGHT)
        self.setAcceptHoverEvents(True)

        # 加载缩略图
        img_path = scene_data.get('generated_image_path', '')
        if img_path and os.path.exists(img_path):
            self._thumbnail = QPixmap(img_path)

    @property
    def duration(self):
        return self._duration

    def set_duration(self, seconds: float):
        self._duration = max(0.5, seconds)
        width = max(self.MIN_WIDTH, self._duration * self._pps)
        self.setRect(0, 0, width, self.CLIP_HEIGHT)
        self.update()

    def set_conflict(self, conflict: bool):
        self._conflict = conflict
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
        dark = theme.is_dark()
        bg = QColor(50, 50, 58) if dark else QColor(245, 245, 248)
        painter.fillPath(bg_path, QBrush(bg))

        # 缩略图
        if self._thumbnail and not self._thumbnail.isNull():
            thumb_rect = QRectF(2, 2, rect.width() - 4, 36)
            painter.setClipPath(bg_path)
            scaled = self._thumbnail.scaled(
                int(thumb_rect.width()), int(thumb_rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            sx = (scaled.width() - thumb_rect.width()) / 2
            painter.drawPixmap(
                thumb_rect.toRect(), scaled,
                QRectF(sx, 0, thumb_rect.width(), thumb_rect.height()).toRect(),
            )
            painter.setClipping(False)

        # 场景号 + 时长
        painter.setPen(QPen(QColor(theme.text_primary())))
        painter.setFont(QFont("Microsoft YaHei", 8))
        scene_idx = self._scene_data.get('scene_index', 0)
        label = f"#{scene_idx + 1}  {self._duration:.1f}s"
        painter.drawText(
            QRectF(4, rect.height() - 20, rect.width() - 8, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )

        # 运镜图标
        camera = self._scene_data.get('camera_motion', '')
        if camera and camera != 'Static':
            painter.setFont(QFont("Microsoft YaHei", 7))
            painter.setPen(QPen(QColor(100, 200, 255)))
            painter.drawText(
                QRectF(rect.width() - 50, rect.height() - 20, 46, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                camera,
            )

        # 冲突边框
        if self._conflict:
            painter.setPen(QPen(QColor(255, 80, 80), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
        else:
            painter.setPen(QPen(QColor(theme.border()), 0.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)


# ============================================================
#  AnimaticTimeline — 时间线视图
# ============================================================

class AnimaticTimeline(QGraphicsView):
    """时间线视图 - 横向分镜卡片序列"""

    clip_clicked = pyqtSignal(int)  # scene_index
    clip_double_clicked = pyqtSignal(int)  # scene_index → 跳转到智能画布

    CLIP_GAP = 4
    PIXELS_PER_SECOND = 60.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tl_scene = QGraphicsScene(self)
        self.setScene(self._tl_scene)
        self.setFixedHeight(80)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._clips: List[TimelineClip] = []
        self._playhead_x = 0.0

    def load_scenes(self, scenes: List[dict]):
        self._tl_scene.clear()
        self._clips.clear()

        x = 10
        for i, scene_data in enumerate(scenes):
            clip = TimelineClip(scene_data, self.PIXELS_PER_SECOND)
            clip.setPos(x, 5)
            self._tl_scene.addItem(clip)
            self._clips.append(clip)
            x += clip.rect().width() + self.CLIP_GAP

        self._tl_scene.setSceneRect(0, 0, x + 20, 70)
        self._check_conflicts()

    def _check_conflicts(self):
        """检测相邻运镜冲突"""
        from config.constants import CAMERA_CONFLICT_RULES
        for i in range(len(self._clips) - 1):
            a = self._clips[i]._scene_data.get('camera_motion', 'Static')
            b = self._clips[i + 1]._scene_data.get('camera_motion', 'Static')
            conflict = False
            for rule in CAMERA_CONFLICT_RULES:
                if (a == rule[0] and b == rule[1]) or (a == rule[1] and b == rule[0]):
                    conflict = True
                    break
            self._clips[i].set_conflict(conflict)
            if i == len(self._clips) - 2:
                self._clips[i + 1].set_conflict(conflict)

    def get_total_duration(self) -> float:
        return sum(c.duration for c in self._clips)

    def get_clip_at_time(self, time_s: float) -> int:
        """返回指定时间所在的片段 index"""
        t = 0.0
        for i, clip in enumerate(self._clips):
            if t + clip.duration > time_s:
                return i
            t += clip.duration
        return max(0, len(self._clips) - 1)

    def get_clip_start_time(self, index: int) -> float:
        t = 0.0
        for i in range(min(index, len(self._clips))):
            t += self._clips[i].duration
        return t

    def set_playhead(self, time_s: float):
        """设置播放头位置"""
        t = 0.0
        for clip in self._clips:
            if t + clip.duration > time_s:
                frac = (time_s - t) / clip.duration
                self._playhead_x = clip.pos().x() + clip.rect().width() * frac
                break
            t += clip.duration
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF):
        """绘制播放头"""
        super().drawForeground(painter, rect)
        x = self._playhead_x
        painter.setPen(QPen(QColor(255, 80, 80), 2))
        painter.drawLine(QPointF(x, 0), QPointF(x, 70))
        # 三角形头
        path = QPainterPath()
        path.moveTo(x - 5, 0)
        path.lineTo(x + 5, 0)
        path.lineTo(x, 8)
        path.closeSubpath()
        painter.fillPath(path, QBrush(QColor(255, 80, 80)))

    def mousePressEvent(self, event):
        pos = self.mapToScene(event.pos())
        for i, clip in enumerate(self._clips):
            if clip.mapRectToScene(clip.rect()).contains(pos):
                self.clip_clicked.emit(i)
                break
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = self.mapToScene(event.pos())
        for i, clip in enumerate(self._clips):
            if clip.mapRectToScene(clip.rect()).contains(pos):
                self.clip_double_clicked.emit(i)
                break
        super().mouseDoubleClickEvent(event)


# ============================================================
#  StutterHeatmap — 卡顿热力图
# ============================================================

class StutterHeatmap(QWidget):
    """卡顿热力图 - 分析分镜节奏"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._bars: List[Dict[str, Any]] = []  # [{color, width, label}]

    def analyze(self, scenes: List[dict]):
        """分析场景序列生成热力图"""
        from config.constants import CAMERA_CONFLICT_RULES
        self._bars.clear()
        if not scenes:
            self.update()
            return

        durations = [s.get('duration', 3.0) for s in scenes]
        avg_dur = sum(durations) / len(durations) if durations else 3.0

        for i, scene in enumerate(scenes):
            dur = scene.get('duration', 3.0)
            cam = scene.get('camera_motion', 'Static')

            # 检查相邻冲突
            has_conflict = False
            if i < len(scenes) - 1:
                next_cam = scenes[i + 1].get('camera_motion', 'Static')
                for rule in CAMERA_CONFLICT_RULES:
                    if (cam == rule[0] and next_cam == rule[1]) or \
                       (cam == rule[1] and next_cam == rule[0]):
                        has_conflict = True
                        break

            # 时长异常
            dur_anomaly = dur > avg_dur * 3 or dur < avg_dur * 0.3

            if has_conflict:
                color = QColor(255, 80, 80)  # 红色 - 冲突
            elif dur_anomaly:
                color = QColor(255, 180, 0)  # 黄色 - 时长异常
            else:
                color = QColor(80, 200, 120)  # 绿色 - 正常

            self._bars.append({
                'color': color,
                'width': max(8, dur * 20),
                'label': f"#{i + 1}",
            })
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._bars:
            return

        x = 4
        bar_h = self.height() - 16
        for bar in self._bars:
            w = bar['width']
            rect = QRectF(x, 4, w, bar_h)
            path = QPainterPath()
            path.addRoundedRect(rect, 3, 3)
            p.fillPath(path, QBrush(bar['color']))

            # 标签
            p.setPen(QPen(QColor(theme.text_tertiary())))
            p.setFont(QFont("Microsoft YaHei", 7))
            p.drawText(
                QRectF(x, bar_h + 4, w, 12),
                Qt.AlignmentFlag.AlignCenter, bar['label'],
            )
            x += w + 2


# ============================================================
#  PlaybackBar — 播放控件栏
# ============================================================

class PlaybackBar(QFrame):
    """播放控件"""

    play_toggled = pyqtSignal(bool)
    seek_requested = pyqtSignal(float)  # time_s
    speed_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._is_playing = False
        self._current_time = 0.0
        self._total_duration = 0.0

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # |<
        self._start_btn = QPushButton("|<")
        self._start_btn.setFixedSize(28, 28)
        self._start_btn.clicked.connect(lambda: self.seek_requested.emit(0))
        layout.addWidget(self._start_btn)

        # <
        self._prev_btn = QPushButton("<")
        self._prev_btn.setFixedSize(28, 28)
        self._prev_btn.clicked.connect(self._seek_prev)
        layout.addWidget(self._prev_btn)

        # Play/Pause
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedSize(36, 28)
        self._play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self._play_btn)

        # >
        self._next_btn = QPushButton(">")
        self._next_btn.setFixedSize(28, 28)
        self._next_btn.clicked.connect(self._seek_next)
        layout.addWidget(self._next_btn)

        # >|
        self._end_btn = QPushButton(">|")
        self._end_btn.setFixedSize(28, 28)
        self._end_btn.clicked.connect(
            lambda: self.seek_requested.emit(self._total_duration)
        )
        layout.addWidget(self._end_btn)

        layout.addSpacing(8)

        # 时间码
        self._time_label = QLabel("00:00.0 / 00:00.0")
        self._time_label.setFont(QFont("Consolas", 10))
        layout.addWidget(self._time_label)

        layout.addStretch()

        # 速度
        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self._speed_combo.setCurrentIndex(1)
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)
        layout.addWidget(self._speed_combo)

    def set_time(self, current: float, total: float):
        self._current_time = current
        self._total_duration = total
        self._time_label.setText(
            f"{self._fmt(current)} / {self._fmt(total)}"
        )

    def set_playing(self, playing: bool):
        self._is_playing = playing
        self._play_btn.setText("⏸" if playing else "▶")

    def _toggle_play(self):
        self._is_playing = not self._is_playing
        self._play_btn.setText("⏸" if self._is_playing else "▶")
        self.play_toggled.emit(self._is_playing)

    def _seek_prev(self):
        self.seek_requested.emit(max(0, self._current_time - 3.0))

    def _seek_next(self):
        self.seek_requested.emit(
            min(self._total_duration, self._current_time + 3.0)
        )

    def _on_speed_changed(self, text: str):
        try:
            speed = float(text.replace('x', ''))
            self.speed_changed.emit(speed)
        except ValueError:
            pass

    @staticmethod
    def _fmt(seconds: float) -> str:
        m = int(seconds) // 60
        s = seconds - m * 60
        return f"{m:02d}:{s:04.1f}"


# ============================================================
#  AnimaticPanel — 完整 Animatic 面板
# ============================================================

class AnimaticPanel(QWidget):
    """Animatic 动态分镜预览面板"""

    open_canvas_requested = pyqtSignal(int)  # scene_id

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self._data_hub = data_hub
        self._scenes: List[dict] = []
        self._current_clip_index = 0
        self._current_time = 0.0
        self._speed = 1.0
        self._is_playing = False

        self._init_ui()
        self._connect_signals()

        # 播放定时器
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(33)  # ~30fps
        self._play_timer.timeout.connect(self._tick)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 预览区
        self._preview = AnimaticPreviewWidget()
        layout.addWidget(self._preview, 1)

        # 播放控件
        self._playback_bar = PlaybackBar()
        layout.addWidget(self._playback_bar)

        # 时间线
        self._timeline = AnimaticTimeline()
        layout.addWidget(self._timeline)

        # 热力图
        self._heatmap = StutterHeatmap()
        layout.addWidget(self._heatmap)

    def _connect_signals(self):
        self._playback_bar.play_toggled.connect(self._on_play_toggled)
        self._playback_bar.seek_requested.connect(self._seek_to)
        self._playback_bar.speed_changed.connect(self._on_speed_changed)
        self._timeline.clip_clicked.connect(self._on_clip_clicked)
        self._timeline.clip_double_clicked.connect(self._on_clip_double_clicked)

    # === 外部接口 ===

    def load_project(self, project_id: int):
        """加载项目分镜到 Animatic"""
        if self._data_hub:
            self._scenes = list(self._data_hub.scenes_data)
        else:
            self._scenes = []

        # 确保每个场景有 duration
        for s in self._scenes:
            if 'duration' not in s:
                s['duration'] = 3.0

        self._timeline.load_scenes(self._scenes)
        self._heatmap.analyze(self._scenes)
        self._current_time = 0.0
        self._current_clip_index = 0
        self._update_preview()

        total = self._timeline.get_total_duration()
        self._playback_bar.set_time(0, total)

    def play(self):
        self._is_playing = True
        self._playback_bar.set_playing(True)
        self._play_timer.start()

    def pause(self):
        self._is_playing = False
        self._playback_bar.set_playing(False)
        self._play_timer.stop()

    def stop(self):
        self.pause()
        self._current_time = 0.0
        self._current_clip_index = 0
        self._update_preview()

    # === 内部 ===

    def _on_play_toggled(self, playing: bool):
        if playing:
            self.play()
        else:
            self.pause()

    def _seek_to(self, time_s: float):
        total = self._timeline.get_total_duration()
        self._current_time = max(0, min(time_s, total))
        self._current_clip_index = self._timeline.get_clip_at_time(
            self._current_time
        )
        self._update_preview()
        self._playback_bar.set_time(self._current_time, total)
        self._timeline.set_playhead(self._current_time)

    def _on_speed_changed(self, speed: float):
        self._speed = speed

    def _on_clip_clicked(self, index: int):
        if 0 <= index < len(self._scenes):
            t = self._timeline.get_clip_start_time(index)
            self._seek_to(t)

    def _on_clip_double_clicked(self, index: int):
        if 0 <= index < len(self._scenes):
            scene_id = self._scenes[index].get('id')
            if scene_id:
                self.open_canvas_requested.emit(scene_id)

    def _tick(self):
        """播放 tick"""
        dt = 0.033 * self._speed
        total = self._timeline.get_total_duration()
        self._current_time += dt

        if self._current_time >= total:
            self._current_time = 0.0
            self._current_clip_index = 0

        self._current_clip_index = self._timeline.get_clip_at_time(
            self._current_time
        )
        self._update_preview()
        self._playback_bar.set_time(self._current_time, total)
        self._timeline.set_playhead(self._current_time)

    def _update_preview(self):
        """更新预览区图片和动画"""
        if not self._scenes or self._current_clip_index >= len(self._scenes):
            return

        scene = self._scenes[self._current_clip_index]
        img_path = scene.get('generated_image_path', '')
        if img_path and os.path.exists(img_path):
            pm = QPixmap(img_path)
            self._preview.set_image(pm)
        else:
            self._preview.set_image(QPixmap())

        camera = scene.get('camera_motion', 'Static')
        dur = scene.get('duration', 3.0)
        self._preview.set_camera_move(camera, int(dur * 1000))

        # 计算当前片段内的进度
        clip_start = self._timeline.get_clip_start_time(self._current_clip_index)
        clip_dur = scene.get('duration', 3.0)
        if clip_dur > 0:
            frac = (self._current_time - clip_start) / clip_dur
            self._preview.set_progress(max(0, min(1, frac)))

    def apply_theme(self):
        dark = theme.is_dark()
        bg = theme.bg_primary()
        self.setStyleSheet(f"background: {bg};")
        self._playback_bar.setStyleSheet(f"""
            QFrame {{
                background: {theme.bg_secondary()};
                border-top: 1px solid {theme.border()};
            }}
            QPushButton {{
                background: {theme.bg_secondary()};
                color: {theme.text_primary()};
                border: 1px solid {theme.border()};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {theme.bg_hover()};
            }}
            QLabel {{
                color: {theme.text_secondary()};
                background: transparent;
            }}
        """)
