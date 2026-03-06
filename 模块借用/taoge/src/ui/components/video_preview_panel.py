"""
涛割 - 视频预览面板
中间区域：视频预览 + 底部时间轴
"""

import os
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSlider, QSizePolicy, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QUrl
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush

from ui.pixmap_cache import PixmapCache

# 尝试导入多媒体模块（PyQt6-Multimedia可能未安装）
_HAS_MULTIMEDIA = False
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    _HAS_MULTIMEDIA = True
except ImportError:
    pass


class AudioTimelineTrack(QWidget):
    """音频轨道绘制 — 与视频轨道平行，显示每个场景的音频状态"""

    audio_segment_clicked = pyqtSignal(int)          # 单击：scene_index
    audio_segment_double_clicked = pyqtSignal(int)   # 双击：scene_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes: List[Dict[str, Any]] = []
        self.current_scene_index = 0
        self.total_duration = 0.0
        self._hover_index = -1

        self.setFixedHeight(24)
        self.setMinimumWidth(200)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def load_scenes(self, scenes: List[Dict[str, Any]]):
        self.scenes = scenes
        self.total_duration = sum(s.get("duration", 0) for s in scenes)
        self.update()

    def set_current_scene(self, index: int):
        self.current_scene_index = index
        self.update()

    def _scene_index_at(self, x: float) -> int:
        """根据 x 坐标返回场景索引"""
        if not self.scenes or self.total_duration <= 0:
            return -1
        bx = 0.0
        width = self.width()
        for i, scene in enumerate(self.scenes):
            duration = scene.get("duration", 0)
            block_width = max(2, (duration / self.total_duration) * width)
            if bx <= x < bx + block_width:
                return i
            bx += block_width
        return -1

    def paintEvent(self, event):
        if not self.scenes or self.total_duration <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # 背景
        painter.fillRect(0, 0, width, height, QColor(32, 32, 36))

        x = 0.0
        for i, scene in enumerate(self.scenes):
            duration = scene.get("duration", 0)
            block_width = max(2, (duration / self.total_duration) * width)

            has_audio = bool(scene.get("generated_audio_path"))
            is_current = (i == self.current_scene_index)
            is_hover = (i == self._hover_index)

            bx = int(x)
            bw = int(block_width) - 1
            by = 2
            bh = height - 4

            if has_audio:
                # 有音频：绿色/青色块
                if is_current:
                    color = QColor(0, 200, 160)
                elif is_hover:
                    color = QColor(0, 180, 140)
                else:
                    color = QColor(0, 150, 120)
                painter.fillRect(bx, by, bw, bh, color)
                # 小音频图标
                icon_font = painter.font()
                icon_font.setPixelSize(10)
                painter.setFont(icon_font)
                painter.setPen(QColor(255, 255, 255, 180))
                if bw > 20:
                    painter.drawText(bx + 3, by, bw, bh,
                                     Qt.AlignmentFlag.AlignVCenter, "♪")
            else:
                # 无音频：深灰虚线边框空块
                fill_color = QColor(45, 45, 50) if not is_hover else QColor(50, 50, 58)
                painter.fillRect(bx, by, bw, bh, fill_color)
                pen = QPen(QColor(80, 80, 90), 1, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(bx, by, bw, bh)

            # 当前场景高亮边框
            if is_current:
                pen = QPen(QColor(0, 180, 255), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(bx, by, bw, bh)

            x += block_width

        painter.end()

    def mouseMoveEvent(self, event):
        idx = self._scene_index_at(event.position().x())
        if idx != self._hover_index:
            self._hover_index = idx
            self.update()

    def leaveEvent(self, event):
        self._hover_index = -1
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._scene_index_at(event.position().x())
            if idx >= 0:
                self.audio_segment_clicked.emit(idx)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._scene_index_at(event.position().x())
            if idx >= 0:
                self.audio_segment_double_clicked.emit(idx)


class TimelineWidget(QFrame):
    """时间轴组件（含视频轨道 + 音频播放按钮 + 音频轨道）"""

    scene_clicked = pyqtSignal(int)  # scene_index
    position_changed = pyqtSignal(float)  # 时间位置（秒）
    audio_play_requested = pyqtSignal()
    audio_segment_double_clicked = pyqtSignal(int)  # scene_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes: List[Dict[str, Any]] = []
        self.current_scene_index = 0
        self.total_duration = 0.0
        self.current_position = 0.0

        self.setFixedHeight(140)
        self.setStyleSheet("""
            QFrame {
                background-color: rgb(25, 25, 28);
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 6, 15, 6)
        layout.setSpacing(3)

        # 时间显示行
        time_row = QHBoxLayout()
        time_row.setSpacing(10)

        self.current_time_label = QLabel("00:00.0")
        self.current_time_label.setStyleSheet("""
            color: rgb(0, 180, 255);
            font-family: Consolas;
            font-size: 12px;
        """)
        time_row.addWidget(self.current_time_label)

        time_row.addStretch()

        self.scene_info_label = QLabel("场景 1/0")
        self.scene_info_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.6);
            font-size: 11px;
        """)
        time_row.addWidget(self.scene_info_label)

        time_row.addStretch()

        self.total_time_label = QLabel("00:00.0")
        self.total_time_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.5);
            font-family: Consolas;
            font-size: 12px;
        """)
        time_row.addWidget(self.total_time_label)

        layout.addLayout(time_row)

        # 音频播放预览按钮行（居中圆形按钮）
        play_preview_row = QHBoxLayout()
        play_preview_row.setSpacing(0)
        play_preview_row.addStretch()

        self.audio_play_btn = QPushButton("▶")
        self.audio_play_btn.setFixedSize(36, 36)
        self.audio_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.audio_play_btn.setToolTip("播放当前场景音频")
        self.audio_play_btn.clicked.connect(lambda: self.audio_play_requested.emit())
        self.audio_play_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 122, 204, 0.15);
                color: rgb(0, 180, 255);
                border: 2px solid rgb(0, 122, 204);
                border-radius: 18px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 122, 204, 0.35);
                border-color: rgb(0, 180, 255);
            }
            QPushButton:pressed {
                background-color: rgb(0, 122, 204);
                color: white;
            }
        """)
        play_preview_row.addWidget(self.audio_play_btn)

        play_preview_row.addStretch()
        layout.addLayout(play_preview_row)

        # 视频时间轴轨道
        self.track_widget = TimelineTrack()
        self.track_widget.scene_clicked.connect(self._on_track_scene_clicked)
        layout.addWidget(self.track_widget)

        # 音频时间轴轨道
        self.audio_track = AudioTimelineTrack()
        self.audio_track.audio_segment_clicked.connect(self._on_track_scene_clicked)
        self.audio_track.audio_segment_double_clicked.connect(
            lambda idx: self.audio_segment_double_clicked.emit(idx)
        )
        layout.addWidget(self.audio_track)

        # 控制按钮行
        control_row = QHBoxLayout()
        control_row.setSpacing(8)

        # 上一场景
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(28, 24)
        self.prev_btn.clicked.connect(self._prev_scene)
        self.prev_btn.setStyleSheet(self._get_btn_style())
        control_row.addWidget(self.prev_btn)

        # 播放/暂停
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(32, 24)
        self.play_btn.setStyleSheet(self._get_btn_style(primary=True))
        control_row.addWidget(self.play_btn)

        # 下一场景
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(28, 24)
        self.next_btn.clicked.connect(self._next_scene)
        self.next_btn.setStyleSheet(self._get_btn_style())
        control_row.addWidget(self.next_btn)

        control_row.addStretch()

        # 缩放控制
        zoom_label = QLabel("缩放")
        zoom_label.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 10px;")
        control_row.addWidget(zoom_label)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setFixedWidth(80)
        self.zoom_slider.setRange(50, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.1);
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: rgb(0, 122, 204);
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        control_row.addWidget(self.zoom_slider)

        layout.addLayout(control_row)

    def _get_btn_style(self, primary=False):
        if primary:
            return """
                QPushButton {
                    background-color: rgb(0, 122, 204);
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: rgb(0, 140, 220);
                }
            """
        return """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.7);
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """

    def load_scenes(self, scenes: List[Dict[str, Any]]):
        """加载场景数据"""
        self.scenes = scenes
        self.total_duration = sum(s.get("duration", 0) for s in scenes)
        self.track_widget.load_scenes(scenes)
        self.audio_track.load_scenes(scenes)

        self.total_time_label.setText(self._format_time(self.total_duration))
        self._update_scene_info()

    def set_current_scene(self, index: int):
        """设置当前场景"""
        if index < 0 or index >= len(self.scenes):
            return
        self.current_scene_index = index
        self.track_widget.set_current_scene(index)
        self.audio_track.set_current_scene(index)
        self._update_scene_info()

        # 计算当前时间位置
        pos = sum(s.get("duration", 0) for s in self.scenes[:index])
        self.current_position = pos
        self.current_time_label.setText(self._format_time(pos))

    def _update_scene_info(self):
        total = len(self.scenes)
        current = self.current_scene_index + 1 if total > 0 else 0
        self.scene_info_label.setText(f"场景 {current}/{total}")

    def _format_time(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins:02d}:{secs:04.1f}"

    def _prev_scene(self):
        if self.current_scene_index > 0:
            self.scene_clicked.emit(self.current_scene_index - 1)

    def _next_scene(self):
        if self.current_scene_index < len(self.scenes) - 1:
            self.scene_clicked.emit(self.current_scene_index + 1)

    def _on_track_scene_clicked(self, index: int):
        self.scene_clicked.emit(index)

    def set_audio_playing(self, is_playing: bool):
        """更新音频播放按钮图标"""
        self.audio_play_btn.setText("||" if is_playing else "▶")

    def load_audio_data(self, scenes: List[Dict[str, Any]]):
        """刷新音频轨道数据"""
        self.audio_track.load_scenes(scenes)


class TimelineTrack(QWidget):
    """时间轴轨道绘制"""

    scene_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scenes: List[Dict[str, Any]] = []
        self.current_scene_index = 0
        self.total_duration = 0.0

        self.setFixedHeight(24)
        self.setMinimumWidth(200)

    def load_scenes(self, scenes: List[Dict[str, Any]]):
        self.scenes = scenes
        self.total_duration = sum(s.get("duration", 0) for s in scenes)
        self.update()

    def set_current_scene(self, index: int):
        self.current_scene_index = index
        self.update()

    def paintEvent(self, event):
        if not self.scenes or self.total_duration <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # 绘制背景
        painter.fillRect(0, 0, width, height, QColor(40, 40, 45))

        # 绘制场景块
        x = 0
        for i, scene in enumerate(self.scenes):
            duration = scene.get("duration", 0)
            if self.total_duration > 0:
                block_width = max(2, (duration / self.total_duration) * width)
            else:
                block_width = width / len(self.scenes)

            # 根据状态选择颜色
            status = scene.get("status", "pending")
            if i == self.current_scene_index:
                color = QColor(0, 122, 204)
            elif status == "completed":
                color = QColor(0, 200, 83)
            elif status == "video_generated":
                color = QColor(76, 175, 80)
            elif status == "image_generated":
                color = QColor(0, 150, 136)
            elif status == "failed":
                color = QColor(244, 67, 54)
            else:
                color = QColor(70, 70, 75)

            # 绘制块
            painter.fillRect(int(x), 2, int(block_width) - 1, height - 4, color)

            x += block_width

        painter.end()

    def mousePressEvent(self, event):
        if not self.scenes or self.total_duration <= 0:
            return

        click_x = event.position().x()
        width = self.width()

        # 计算点击的场景
        x = 0
        for i, scene in enumerate(self.scenes):
            duration = scene.get("duration", 0)
            block_width = (duration / self.total_duration) * width
            if x <= click_x < x + block_width:
                self.scene_clicked.emit(i)
                break
            x += block_width


class VideoPreviewPanel(QFrame):
    """视频预览面板 - 中间区域"""

    scene_changed = pyqtSignal(int)
    audio_generated = pyqtSignal(int, str)  # scene_index, audio_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_scene: Optional[Dict[str, Any]] = None
        self.scenes: List[Dict[str, Any]] = []
        self._is_playing = False
        self._media_player: Optional[object] = None
        self._audio_output: Optional[object] = None
        self._video_widget: Optional[QWidget] = None

        # 独立音频播放器
        self._audio_player: Optional[object] = None
        self._audio_player_output: Optional[object] = None
        self._is_audio_playing = False

        self.setObjectName("videoPreviewPanel")
        self.setStyleSheet("""
            QFrame#videoPreviewPanel {
                background-color: rgb(18, 18, 20);
            }
        """)

        self._init_ui()
        self._init_audio_player()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 预览区域
        preview_container = QFrame()
        preview_container.setStyleSheet("background-color: rgb(12, 12, 14);")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(20, 20, 20, 20)

        # 预览堆叠（占位符=0 / 图片=1 / 视频=2）
        self.preview_stack = QStackedWidget()

        # 占位符
        placeholder = QFrame()
        placeholder.setStyleSheet("""
            QFrame {
                background-color: rgb(30, 30, 35);
                border: 2px dashed rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)
        placeholder_layout = QVBoxLayout(placeholder)
        placeholder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        placeholder_icon = QLabel("?")
        placeholder_icon.setStyleSheet("font-size: 48px; color: rgba(255, 255, 255, 0.3);")
        placeholder_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_icon)

        placeholder_text = QLabel("选择场景以预览")
        placeholder_text.setStyleSheet("""
            color: rgba(255, 255, 255, 0.4);
            font-size: 14px;
        """)
        placeholder_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_text)

        self.preview_stack.addWidget(placeholder)  # index 0

        # 图片预览
        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet("""
            QLabel {
                background-color: rgb(20, 20, 22);
                border-radius: 4px;
            }
        """)
        self.image_preview.setScaledContents(False)
        self.preview_stack.addWidget(self.image_preview)  # index 1

        # 视频播放器
        if _HAS_MULTIMEDIA:
            self._video_widget = QVideoWidget()
            self._video_widget.setStyleSheet("background-color: black;")
            self.preview_stack.addWidget(self._video_widget)  # index 2

            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(0.5)

            self._media_player = QMediaPlayer()
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.setVideoOutput(self._video_widget)
            self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)
            self._media_player.positionChanged.connect(self._on_position_changed)
            self._media_player.durationChanged.connect(self._on_duration_changed)
        else:
            # 没有多媒体模块时，用标签代替
            no_video_label = QLabel("视频播放需要安装 PyQt6-Multimedia")
            no_video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_video_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.4);
                font-size: 12px;
                background-color: rgb(20, 20, 22);
                border-radius: 4px;
            """)
            self.preview_stack.addWidget(no_video_label)  # index 2

        preview_layout.addWidget(self.preview_stack)

        # 视频播放控制栏（仅视频模式可见）
        self.video_control_bar = QFrame()
        self.video_control_bar.setFixedHeight(36)
        self.video_control_bar.setVisible(False)
        vc_layout = QHBoxLayout(self.video_control_bar)
        vc_layout.setContentsMargins(0, 4, 0, 0)
        vc_layout.setSpacing(8)

        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setFixedSize(32, 28)
        self.play_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_pause_btn.clicked.connect(self._toggle_play)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                color: white; border: none;
                border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background-color: rgb(0, 140, 220); }
        """)
        vc_layout.addWidget(self.play_pause_btn)

        self.video_position_label = QLabel("0:00")
        self.video_position_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px; font-family: Consolas;")
        vc_layout.addWidget(self.video_position_label)

        self.video_seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_seek_slider.setRange(0, 0)
        self.video_seek_slider.sliderMoved.connect(self._on_seek)
        self.video_seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.1);
                height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: rgb(0, 122, 204);
                width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: rgb(0, 122, 204);
                border-radius: 2px;
            }
        """)
        vc_layout.addWidget(self.video_seek_slider, 1)

        self.video_duration_label = QLabel("0:00")
        self.video_duration_label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px; font-family: Consolas;")
        vc_layout.addWidget(self.video_duration_label)

        # 音量控制
        vol_label = QLabel("Vol")
        vol_label.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 10px;")
        vc_layout.addWidget(vol_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setFixedWidth(60)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.1);
                height: 3px; border-radius: 1px;
            }
            QSlider::handle:horizontal {
                background: rgba(255, 255, 255, 0.6);
                width: 10px; height: 10px;
                margin: -3px 0; border-radius: 5px;
            }
        """)
        vc_layout.addWidget(self.volume_slider)

        preview_layout.addWidget(self.video_control_bar)

        # 预览信息栏
        info_bar = QFrame()
        info_bar.setFixedHeight(36)
        info_bar.setStyleSheet("background-color: transparent;")
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(0, 8, 0, 0)

        self.preview_type_label = QLabel("无预览")
        self.preview_type_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.5);
            font-size: 11px;
            background-color: rgba(255, 255, 255, 0.05);
            padding: 4px 10px;
            border-radius: 10px;
        """)
        info_layout.addWidget(self.preview_type_label)

        info_layout.addStretch()

        self.resolution_label = QLabel("")
        self.resolution_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.4);
            font-size: 11px;
        """)
        info_layout.addWidget(self.resolution_label)

        preview_layout.addWidget(info_bar)

        layout.addWidget(preview_container, 1)

        # 时间轴
        self.timeline = TimelineWidget()
        self.timeline.scene_clicked.connect(self._on_timeline_scene_clicked)
        self.timeline.audio_play_requested.connect(self._on_audio_play_requested)
        self.timeline.audio_segment_double_clicked.connect(self._on_audio_segment_double_clicked)
        layout.addWidget(self.timeline)

    def load_scenes(self, scenes: List[Dict[str, Any]]):
        """加载场景列表"""
        self.scenes = scenes
        self.timeline.load_scenes(scenes)

    def set_current_scene(self, index: int, scene_data: Dict[str, Any]):
        """设置当前场景"""
        self.current_scene = scene_data
        self.timeline.set_current_scene(index)
        self._update_preview()
        # 切换场景时停止独立音频播放
        self._stop_audio()

    def _update_preview(self):
        """更新预览内容"""
        if not self.current_scene:
            self._stop_video()
            self.preview_stack.setCurrentIndex(0)
            self.preview_type_label.setText("无预览")
            self.resolution_label.setText("")
            self.video_control_bar.setVisible(False)
            return

        # 优先显示视频，其次图片
        video_path = self.current_scene.get("generated_video_path")
        image_path = self.current_scene.get("generated_image_path")
        start_frame = self.current_scene.get("start_frame_path")

        if video_path and os.path.exists(video_path):
            self.preview_type_label.setText("视频预览")
            self._play_video(video_path)
        elif image_path:
            self._stop_video()
            self.video_control_bar.setVisible(False)
            self.preview_type_label.setText("生成图片")
            self._show_image(image_path)
        elif start_frame:
            self._stop_video()
            self.video_control_bar.setVisible(False)
            self.preview_type_label.setText("首帧图片")
            self._show_image(start_frame)
        else:
            self._stop_video()
            self.preview_stack.setCurrentIndex(0)
            self.preview_type_label.setText("无预览")
            self.resolution_label.setText("")
            self.video_control_bar.setVisible(False)

    def _show_image(self, path: str):
        """显示图片"""
        try:
            cache = PixmapCache.instance()
            # 先获取原图用于分辨率信息
            original = cache.get_original(path)
            if original and not original.isNull():
                w = self.image_preview.width()
                h = self.image_preview.height()
                scaled = cache.get_scaled(path, w, h)
                if scaled:
                    self.image_preview.setPixmap(scaled)
                    self.preview_stack.setCurrentIndex(1)
                    self.resolution_label.setText(f"{original.width()} x {original.height()}")
                else:
                    self.preview_stack.setCurrentIndex(0)
                    self.preview_type_label.setText("图片加载失败")
            else:
                self.preview_stack.setCurrentIndex(0)
                self.preview_type_label.setText("图片加载失败")
        except Exception:
            self.preview_stack.setCurrentIndex(0)
            self.preview_type_label.setText("图片加载失败")

    # ==================== 视频播放控制 ====================

    def _play_video(self, path: str):
        """播放视频文件"""
        if not _HAS_MULTIMEDIA or not self._media_player:
            # 无多媒体模块，回退到图片显示
            self.preview_stack.setCurrentIndex(2)
            self.video_control_bar.setVisible(False)
            self.resolution_label.setText("")
            return

        self.preview_stack.setCurrentIndex(2)
        self.video_control_bar.setVisible(True)

        url = QUrl.fromLocalFile(path)
        self._media_player.setSource(url)
        self._media_player.play()
        self._is_playing = True
        self.play_pause_btn.setText("||")
        self.resolution_label.setText("")

    def _stop_video(self):
        """停止视频播放"""
        if self._media_player and _HAS_MULTIMEDIA:
            self._media_player.stop()
            self._media_player.setSource(QUrl())
        self._is_playing = False
        self.play_pause_btn.setText("▶")

    def _toggle_play(self):
        """播放/暂停切换"""
        if not self._media_player or not _HAS_MULTIMEDIA:
            return

        if self._is_playing:
            self._media_player.pause()
        else:
            self._media_player.play()

    def _on_playback_state_changed(self, state):
        """播放状态变更"""
        if not _HAS_MULTIMEDIA:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._is_playing = True
            self.play_pause_btn.setText("||")
        else:
            self._is_playing = False
            self.play_pause_btn.setText("▶")

    def _on_position_changed(self, position_ms: int):
        """播放位置变更"""
        if not self.video_seek_slider.isSliderDown():
            self.video_seek_slider.setValue(position_ms)
        self.video_position_label.setText(self._format_ms(position_ms))

    def _on_duration_changed(self, duration_ms: int):
        """视频时长变更"""
        self.video_seek_slider.setRange(0, duration_ms)
        self.video_duration_label.setText(self._format_ms(duration_ms))

    def _on_seek(self, position_ms: int):
        """拖动进度条"""
        if self._media_player and _HAS_MULTIMEDIA:
            self._media_player.setPosition(position_ms)

    def _on_volume_changed(self, value: int):
        """音量变化"""
        if self._audio_output and _HAS_MULTIMEDIA:
            self._audio_output.setVolume(value / 100.0)

    @staticmethod
    def _format_ms(ms: int) -> str:
        """毫秒转显示时间"""
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def _on_timeline_scene_clicked(self, index: int):
        """时间轴场景点击"""
        self.scene_changed.emit(index)

    def resizeEvent(self, event):
        """窗口大小改变时重新缩放图片"""
        super().resizeEvent(event)
        if self.current_scene and not self._is_playing:
            # 只在非视频播放模式下重新缩放
            video_path = self.current_scene.get("generated_video_path")
            if not (video_path and os.path.exists(video_path)):
                self._update_preview()

    # ==================== 独立音频播放 ====================

    def _init_audio_player(self):
        """初始化独立音频播放器"""
        if not _HAS_MULTIMEDIA:
            return
        self._audio_player_output = QAudioOutput()
        self._audio_player_output.setVolume(0.8)
        self._audio_player = QMediaPlayer()
        self._audio_player.setAudioOutput(self._audio_player_output)
        self._audio_player.playbackStateChanged.connect(self._on_audio_playback_state_changed)

    def _on_audio_play_requested(self):
        """播放/暂停当前场景音频"""
        if not self.current_scene:
            return

        audio_path = self.current_scene.get("generated_audio_path")
        if not audio_path or not os.path.exists(audio_path):
            return

        if self._is_audio_playing:
            self._stop_audio()
        else:
            self._play_audio(audio_path)

    def _play_audio(self, path: str):
        """播放音频文件"""
        if not _HAS_MULTIMEDIA or not self._audio_player:
            return
        url = QUrl.fromLocalFile(path)
        self._audio_player.setSource(url)
        self._audio_player.play()
        self._is_audio_playing = True
        self.timeline.set_audio_playing(True)

    def _stop_audio(self):
        """停止音频播放"""
        if self._audio_player and _HAS_MULTIMEDIA:
            self._audio_player.stop()
            self._audio_player.setSource(QUrl())
        self._is_audio_playing = False
        self.timeline.set_audio_playing(False)

    def _on_audio_playback_state_changed(self, state):
        """音频播放状态变更"""
        if not _HAS_MULTIMEDIA:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._is_audio_playing = True
            self.timeline.set_audio_playing(True)
        else:
            self._is_audio_playing = False
            self.timeline.set_audio_playing(False)

    def _on_audio_segment_double_clicked(self, index: int):
        """双击音频片段 → 弹出音频生成对话框"""
        if not self.scenes or index < 0 or index >= len(self.scenes):
            return

        scene_data = self.scenes[index]
        # 确定输出目录
        output_dir = os.path.join("generated", "audio")

        from ui.components.audio_generation_dialog import AudioGenerationDialog
        dialog = AudioGenerationDialog(
            scene_index=index,
            scene_data=scene_data,
            output_dir=output_dir,
            parent=self,
        )
        dialog.audio_generated.connect(self._on_audio_generated)
        dialog.exec()

    def _on_audio_generated(self, index: int, audio_path: str):
        """音频生成完成"""
        # 更新本地 scenes 数据
        if 0 <= index < len(self.scenes):
            self.scenes[index]['generated_audio_path'] = audio_path
            self.timeline.load_audio_data(self.scenes)
        # 向上层发出信号
        self.audio_generated.emit(index, audio_path)
