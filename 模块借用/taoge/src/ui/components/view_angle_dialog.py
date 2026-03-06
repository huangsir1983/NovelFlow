"""
涛割 - 视角转换对话框
预设下拉框 + 3D 交互控件 + 提示词预览 + 生成/进度
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from ui import theme
from ui.components.view_angle_widget import AngleControlCanvas
from services.view_angle_service import (
    AZIMUTH_PRESETS, ELEVATION_PRESETS, DISTANCE_PRESETS,
    angle_to_prompt, ViewAngleConvertWorker,
)


class ViewAngleDialog(QDialog):
    """视角转换对话框"""

    convert_completed = pyqtSignal(str)  # output_path

    def __init__(self, layer_id: int, original_image_path: str,
                 scene_id: int, parent=None):
        super().__init__(parent)
        self._layer_id = layer_id
        self._original_image_path = original_image_path
        self._scene_id = scene_id
        self._worker: Optional[ViewAngleConvertWorker] = None
        self._syncing_combos = False  # 防止下拉框信号回环

        self.setWindowTitle("视角转换")
        self.setFixedSize(400, 620)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        self._init_ui()
        self._connect_signals()
        # 同步下拉框到控件的初始角度值
        self._sync_combos_to_angle(
            self._angle_canvas.azimuth,
            self._angle_canvas.elevation,
            self._angle_canvas.distance,
        )
        self._update_prompt_preview()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # === 预设下拉框 ===
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(8)

        # 方位角
        az_layout = QVBoxLayout()
        az_layout.setSpacing(2)
        az_label = QLabel("方位角 (H)")
        az_label.setFont(QFont("Microsoft YaHei", 9))
        az_layout.addWidget(az_label)
        self._az_combo = QComboBox()
        for name in AZIMUTH_PRESETS:
            self._az_combo.addItem(name)
        az_layout.addWidget(self._az_combo)
        preset_layout.addLayout(az_layout)

        # 俯仰角
        el_layout = QVBoxLayout()
        el_layout.setSpacing(2)
        el_label = QLabel("俯仰角 (V)")
        el_label.setFont(QFont("Microsoft YaHei", 9))
        el_layout.addWidget(el_label)
        self._el_combo = QComboBox()
        for name in ELEVATION_PRESETS:
            self._el_combo.addItem(name)
        self._el_combo.setCurrentText("平视")
        el_layout.addWidget(self._el_combo)
        preset_layout.addLayout(el_layout)

        # 距离
        dist_layout = QVBoxLayout()
        dist_layout.setSpacing(2)
        dist_label = QLabel("距离 (Z)")
        dist_label.setFont(QFont("Microsoft YaHei", 9))
        dist_layout.addWidget(dist_label)
        self._dist_combo = QComboBox()
        for name in DISTANCE_PRESETS:
            self._dist_combo.addItem(name)
        self._dist_combo.setCurrentText("中景")
        dist_layout.addWidget(self._dist_combo)
        preset_layout.addLayout(dist_layout)

        layout.addLayout(preset_layout)

        # === 3D 控件 ===
        canvas_frame = QFrame()
        canvas_frame.setStyleSheet(
            "QFrame { border: 1px solid #3a3a4a; border-radius: 8px; }"
        )
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(4, 4, 4, 4)

        self._angle_canvas = AngleControlCanvas()
        pixmap = QPixmap(self._original_image_path)
        if not pixmap.isNull():
            self._angle_canvas.set_image(pixmap)
        canvas_layout.addWidget(self._angle_canvas, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(canvas_frame)

        # === 重置按钮 ===
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_btn = QPushButton("重置")
        reset_btn.setFixedWidth(60)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._on_reset)
        reset_layout.addWidget(reset_btn)
        layout.addLayout(reset_layout)

        # === 提示词预览 ===
        self._prompt_label = QLabel()
        self._prompt_label.setFont(QFont("Consolas", 9))
        self._prompt_label.setWordWrap(True)
        self._prompt_label.setStyleSheet(
            "background: #1a1a2e; color: #a0a0c0; padding: 8px; "
            "border-radius: 6px; border: 1px solid #2a2a3a;"
        )
        layout.addWidget(self._prompt_label)

        # === 生成按钮 ===
        self._generate_btn = QPushButton("生成视角转换")
        self._generate_btn.setFixedHeight(36)
        self._generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()};
                color: white; border: none; border-radius: 8px;
                font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
            QPushButton:disabled {{ background-color: #555; }}
        """)
        self._generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self._generate_btn)

        # === 进度条 ===
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(6)
        layout.addWidget(self._progress_bar)

        # === 状态 ===
        self._status_label = QLabel("")
        self._status_label.setFont(QFont("Microsoft YaHei", 9))
        self._status_label.setStyleSheet("color: #888;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

    def _connect_signals(self):
        # 下拉框 → 3D 控件同步
        self._az_combo.currentTextChanged.connect(self._on_az_preset)
        self._el_combo.currentTextChanged.connect(self._on_el_preset)
        self._dist_combo.currentTextChanged.connect(self._on_dist_preset)

        # 3D 控件拖拽 → 数值 + 提示词更新
        self._angle_canvas.angle_changed.connect(self._on_angle_changed)

    # === 预设下拉框回调 ===

    def _on_az_preset(self, name: str):
        if self._syncing_combos:
            return
        az_angles = {
            '正面': 0, '右前方': 45, '右侧': 90, '右后方': 135,
            '背面': 180, '左后方': -135, '左侧': -90, '左前方': -45,
        }
        if name in az_angles:
            self._angle_canvas.set_azimuth(az_angles[name])
            self._update_prompt_preview()

    def _on_el_preset(self, name: str):
        if self._syncing_combos:
            return
        el_angles = {'仰视': -30, '平视': 0, '俯视': 30, '高角度': 60}
        if name in el_angles:
            self._angle_canvas.set_elevation(el_angles[name])
            self._update_prompt_preview()

    def _on_dist_preset(self, name: str):
        if self._syncing_combos:
            return
        dist_values = {'特写': 2.0, '中景': 5.0, '远景': 8.0}
        if name in dist_values:
            self._angle_canvas.set_distance(dist_values[name])
            self._update_prompt_preview()

    # === 3D 控件拖拽回调 ===

    def _on_angle_changed(self, az: float, el: float, dist: float):
        self._sync_combos_to_angle(az, el, dist)
        self._update_prompt_preview()

    def _sync_combos_to_angle(self, az: float, el: float, dist: float):
        """根据当前角度值自动更新下拉框到最近的预设"""
        self._syncing_combos = True
        try:
            # 方位角 → 最近预设
            az_presets = [
                (0, '正面'), (45, '右前方'), (90, '右侧'), (135, '右后方'),
                (180, '背面'), (-135, '左后方'), (-90, '左侧'), (-45, '左前方'),
            ]
            best_az = min(az_presets,
                          key=lambda x: min(abs(az - x[0]),
                                            360 - abs(az - x[0])))
            self._az_combo.setCurrentText(best_az[1])

            # 俯仰角 → 最近预设
            el_presets = [(-30, '仰视'), (0, '平视'), (30, '俯视'), (60, '高角度')]
            best_el = min(el_presets, key=lambda x: abs(el - x[0]))
            self._el_combo.setCurrentText(best_el[1])

            # 距离 → 最近预设
            if dist <= 3.3:
                self._dist_combo.setCurrentText('特写')
            elif dist <= 6.6:
                self._dist_combo.setCurrentText('中景')
            else:
                self._dist_combo.setCurrentText('远景')
        finally:
            self._syncing_combos = False

    def _update_prompt_preview(self):
        """从 3D 控件的角度值生成提示词预览"""
        prompt = angle_to_prompt(
            self._angle_canvas.azimuth,
            self._angle_canvas.elevation,
            self._angle_canvas.distance,
        )
        self._prompt_label.setText(f"提示词: {prompt}")

    # === 重置 ===

    def _on_reset(self):
        self._az_combo.setCurrentText("正面")
        self._el_combo.setCurrentText("平视")
        self._dist_combo.setCurrentText("中景")
        self._angle_canvas.set_azimuth(0)
        self._angle_canvas.set_elevation(0)
        self._angle_canvas.set_distance(5.0)
        self._update_prompt_preview()

    # === 生成 ===

    def _on_generate(self):
        self._generate_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._status_label.setText("正在启动视角转换...")

        # 从 3D 控件角度值构建提示词（映射到最近预设文本）
        prompt = angle_to_prompt(
            self._angle_canvas.azimuth,
            self._angle_canvas.elevation,
            self._angle_canvas.distance,
        )
        self._status_label.setText(f"提示词: {prompt}")

        # 获取 API 配置
        from config.settings import SettingsManager
        settings = SettingsManager()
        api_key = settings.settings.api.runninghub_api_key
        base_url = settings.settings.api.runninghub_base_url
        instance_type = settings.settings.api.runninghub_instance_type

        if not api_key:
            self._status_label.setText("RunningHub API Key 未配置，请在设置中配置")
            self._generate_btn.setEnabled(True)
            self._progress_bar.setVisible(False)
            return

        # 保存目录
        import os
        save_dir = os.path.join('generated', 'view_angle', str(self._scene_id))

        self._worker = ViewAngleConvertWorker(
            source_image_path=self._original_image_path,
            prompt=prompt,
            save_dir=save_dir,
            api_key=api_key,
            base_url=base_url,
            instance_type=instance_type,
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_completed)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_label.setText(msg)

    def _on_completed(self, success: bool, local_path: str, error: str):
        self._generate_btn.setEnabled(True)
        self._progress_bar.setVisible(False)

        if success:
            self._status_label.setText(f"视角转换完成: {local_path}")
            self.convert_completed.emit(local_path)
        else:
            self._status_label.setText(f"失败: {error}")
