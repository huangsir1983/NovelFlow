"""
涛割 - 画布属性面板
精简版镜头属性面板，适配画布模式的浮动/可关闭特性
"""

import os
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QTextEdit, QComboBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from ui.pixmap_cache import PixmapCache
from services.ai_analyzer import AIAnalysisWorker


class CanvasPropertyPanel(QFrame):
    """
    画布属性面板 - 精简版 ShotPropertyPanel
    布局：关闭按钮+场景序号 | 大图预览 | 叙事内容 | 视觉设定 | 视频提示词 | 角色 | 生成按钮
    """

    property_changed = pyqtSignal(str, object)  # property_name, value
    generate_image_requested = pyqtSignal(int)  # scene_index
    generate_video_requested = pyqtSignal(int)  # scene_index
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_scene_index: int = -1
        self._scene_data: Dict[str, Any] = {}
        self._is_updating = False  # 防止循环更新
        self._ai_worker: Optional[AIAnalysisWorker] = None

        self.setObjectName("canvasPropertyPanel")
        self.setStyleSheet("""
            QFrame#canvasPropertyPanel {
                background-color: rgb(25, 25, 30);
                border-left: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部标题栏（关闭按钮 + 场景序号）
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet("""
            QFrame {
                background-color: rgb(30, 30, 35);
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)

        self.title_label = QLabel("属性面板")
        self.title_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_requested.emit)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.5);
                border: none;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        # 可滚动内容区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.02);
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(12)

        # 大图预览
        self.preview_label = QLabel()
        self.preview_label.setFixedHeight(180)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                color: rgba(255, 255, 255, 0.3);
                font-size: 12px;
            }
        """)
        self.preview_label.setText("无预览")
        self.content_layout.addWidget(self.preview_label)

        # 叙事内容区
        self._add_section_header("叙事内容")

        self.subtitle_edit = QTextEdit()
        self.subtitle_edit.setMaximumHeight(80)
        self.subtitle_edit.setPlaceholderText("场景叙事文本...")
        self.subtitle_edit.textChanged.connect(self._on_subtitle_changed)
        self.subtitle_edit.setStyleSheet(self._get_textedit_style())
        self.content_layout.addWidget(self.subtitle_edit)

        # 视觉设定区
        self._add_section_header("视觉设定")

        self.image_prompt_edit = QTextEdit()
        self.image_prompt_edit.setMaximumHeight(60)
        self.image_prompt_edit.setPlaceholderText("图像生成提示词...")
        self.image_prompt_edit.textChanged.connect(self._on_image_prompt_changed)
        self.image_prompt_edit.setStyleSheet(self._get_textedit_style())
        self.content_layout.addWidget(self.image_prompt_edit)

        # 一键分析画面提示词按钮
        self.ai_image_prompt_btn = QPushButton("一键分析画面提示词")
        self.ai_image_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_image_prompt_btn.clicked.connect(self._ai_generate_image_prompt)
        self.ai_image_prompt_btn.setStyleSheet(self._get_ai_btn_style())
        self.content_layout.addWidget(self.ai_image_prompt_btn)

        # 视频提示词区
        self._add_section_header("视频提示词")

        self.video_prompt_edit = QTextEdit()
        self.video_prompt_edit.setMaximumHeight(80)
        self.video_prompt_edit.setPlaceholderText("综合性的视频提示词...")
        self.video_prompt_edit.textChanged.connect(self._on_video_prompt_changed)
        self.video_prompt_edit.setStyleSheet(self._get_textedit_style())
        self.content_layout.addWidget(self.video_prompt_edit)

        # 5个只读详情标签
        detail_style = """
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 10px;
                padding: 3px 6px;
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: 3px;
            }
        """

        self.camera_motion_label = QLabel("运镜方式：-")
        self.camera_motion_label.setStyleSheet(detail_style)
        self.camera_motion_label.setWordWrap(True)
        self.content_layout.addWidget(self.camera_motion_label)

        self.shot_size_label = QLabel("景别：-")
        self.shot_size_label.setStyleSheet(detail_style)
        self.shot_size_label.setWordWrap(True)
        self.content_layout.addWidget(self.shot_size_label)

        self.character_actions_label = QLabel("角色动作：-")
        self.character_actions_label.setStyleSheet(detail_style)
        self.character_actions_label.setWordWrap(True)
        self.content_layout.addWidget(self.character_actions_label)

        self.expression_changes_label = QLabel("表情变化：-")
        self.expression_changes_label.setStyleSheet(detail_style)
        self.expression_changes_label.setWordWrap(True)
        self.content_layout.addWidget(self.expression_changes_label)

        self.vfx_analysis_label = QLabel("特效分析：-")
        self.vfx_analysis_label.setStyleSheet(detail_style)
        self.vfx_analysis_label.setWordWrap(True)
        self.content_layout.addWidget(self.vfx_analysis_label)

        # 生成视频提示词按钮
        self.ai_video_prompt_btn = QPushButton("生成视频提示词")
        self.ai_video_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_video_prompt_btn.clicked.connect(self._ai_generate_video_prompt)
        self.ai_video_prompt_btn.setStyleSheet(self._get_ai_btn_style())
        self.content_layout.addWidget(self.ai_video_prompt_btn)

        # 角色
        self._add_section_header("角色")

        self.characters_label = QLabel("无角色关联")
        self.characters_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.4);
            font-size: 11px;
            padding: 8px;
            background-color: rgba(255, 255, 255, 0.02);
            border-radius: 4px;
        """)
        self.content_layout.addWidget(self.characters_label)

        self.content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # 底部生成按钮
        btn_frame = QFrame()
        btn_frame.setFixedHeight(56)
        btn_frame.setStyleSheet("""
            QFrame {
                background-color: rgb(30, 30, 35);
                border-top: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(12, 0, 12, 0)
        btn_layout.setSpacing(8)

        self.ai_all_btn = QPushButton("一键生成")
        self.ai_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ai_all_btn.clicked.connect(self._ai_analyze_all)
        self.ai_all_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(139, 92, 246, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(139, 92, 246, 1.0); }
            QPushButton:disabled { background-color: rgba(139, 92, 246, 0.3); }
        """)
        btn_layout.addWidget(self.ai_all_btn)

        gen_img_btn = QPushButton("生成图片")
        gen_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gen_img_btn.clicked.connect(lambda: self.generate_image_requested.emit(self.current_scene_index))
        gen_img_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgb(0, 140, 220); }
        """)
        btn_layout.addWidget(gen_img_btn)

        gen_vid_btn = QPushButton("生成视频")
        gen_vid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gen_vid_btn.clicked.connect(lambda: self.generate_video_requested.emit(self.current_scene_index))
        gen_vid_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(76, 175, 80, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(76, 175, 80, 1.0); }
        """)
        btn_layout.addWidget(gen_vid_btn)

        layout.addWidget(btn_frame)

    def _add_section_header(self, text: str):
        """添加区块标题"""
        label = QLabel(text)
        label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.5);
            font-size: 11px;
            font-weight: bold;
            padding-top: 4px;
        """)
        self.content_layout.addWidget(label)

    def _get_textedit_style(self):
        return """
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                padding: 6px;
                color: rgba(255, 255, 255, 0.85);
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: rgba(0, 122, 204, 0.5);
            }
        """

    def _get_ai_btn_style(self):
        return """
            QPushButton {
                background-color: rgba(139, 92, 246, 0.15);
                color: rgba(139, 92, 246, 0.9);
                border: 1px solid rgba(139, 92, 246, 0.3);
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(139, 92, 246, 0.25);
                color: rgb(139, 92, 246);
            }
            QPushButton:disabled {
                background-color: rgba(139, 92, 246, 0.05);
                color: rgba(139, 92, 246, 0.3);
                border-color: rgba(139, 92, 246, 0.1);
            }
        """

    # ==================== 数据绑定 ====================

    def set_scene(self, index: int, scene_data: Dict[str, Any]):
        """设置场景数据并更新面板"""
        self._is_updating = True
        self.current_scene_index = index
        self._scene_data = scene_data

        # 标题
        self.title_label.setText(f"场景 #{index + 1}")

        # 预览图
        self._update_preview(scene_data)

        # 叙事
        self.subtitle_edit.setPlainText(scene_data.get('subtitle_text', ''))

        # 图像prompt
        self.image_prompt_edit.setPlainText(scene_data.get('image_prompt', ''))

        # 视频提示词
        self.video_prompt_edit.setPlainText(scene_data.get('video_prompt', ''))

        # 从generation_params恢复5个详情标签
        gen_params = scene_data.get('generation_params') or {}
        self.camera_motion_label.setText(f"运镜方式：{gen_params.get('camera_motion', '-')}")
        self.shot_size_label.setText(f"景别：{gen_params.get('shot_size', '-')}")
        self.character_actions_label.setText(f"角色动作：{gen_params.get('character_actions', '-')}")
        self.expression_changes_label.setText(f"表情变化：{gen_params.get('expression_changes', '-')}")
        self.vfx_analysis_label.setText(f"特效分析：{gen_params.get('vfx_analysis', '-')}")

        # 角色
        chars = scene_data.get('characters', [])
        if chars:
            names = []
            for c in chars:
                if isinstance(c, dict):
                    names.append(c.get('name', '?'))
                elif isinstance(c, str):
                    names.append(c)
            self.characters_label.setText(", ".join(names))
            self.characters_label.setStyleSheet("""
                color: rgba(139, 92, 246, 0.8);
                font-size: 11px;
                padding: 8px;
                background-color: rgba(139, 92, 246, 0.08);
                border-radius: 4px;
            """)
        else:
            self.characters_label.setText("无角色关联")
            self.characters_label.setStyleSheet("""
                color: rgba(255, 255, 255, 0.4);
                font-size: 11px;
                padding: 8px;
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 4px;
            """)

        self._is_updating = False

    def _update_preview(self, scene_data: Dict[str, Any]):
        """更新预览图"""
        cache = PixmapCache.instance()
        for key in ('generated_image_path', 'start_frame_path'):
            path = scene_data.get(key, '')
            if path and os.path.exists(path):
                scaled = cache.get_scaled(path, 300, 170)
                if scaled:
                    self.preview_label.setPixmap(scaled)
                    return

        self.preview_label.clear()
        self.preview_label.setText("无预览")

    # ==================== 属性变更回调 ====================

    def _on_subtitle_changed(self):
        if not self._is_updating and self.current_scene_index >= 0:
            text = self.subtitle_edit.toPlainText()
            self.property_changed.emit('subtitle_text', text)

    def _on_image_prompt_changed(self):
        if not self._is_updating and self.current_scene_index >= 0:
            text = self.image_prompt_edit.toPlainText()
            self.property_changed.emit('image_prompt', text)

    def _on_video_prompt_changed(self):
        if not self._is_updating and self.current_scene_index >= 0:
            text = self.video_prompt_edit.toPlainText()
            self.property_changed.emit('video_prompt', text)

    # ==================== AI 分析 ====================

    def _get_scene_characters(self) -> List[str]:
        """获取当前场景角色名列表"""
        chars = self._scene_data.get('characters', [])
        names = []
        for c in chars:
            if isinstance(c, dict):
                names.append(c.get('name', ''))
            elif isinstance(c, str):
                names.append(c)
        return [n for n in names if n]

    def _set_ai_buttons_enabled(self, enabled: bool):
        """设置所有AI按钮的启用状态"""
        self.ai_image_prompt_btn.setEnabled(enabled)
        self.ai_video_prompt_btn.setEnabled(enabled)
        self.ai_all_btn.setEnabled(enabled)

    def _ai_generate_image_prompt(self):
        """一键分析画面提示词"""
        text = self.subtitle_edit.toPlainText().strip()
        if not text:
            return

        self._set_ai_buttons_enabled(False)
        self.ai_image_prompt_btn.setText("分析中...")

        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_IMAGE_PROMPT,
            text,
            characters=self._get_scene_characters(),
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def _ai_generate_video_prompt(self):
        """生成视频提示词"""
        text = self.subtitle_edit.toPlainText().strip()
        if not text:
            return

        self._set_ai_buttons_enabled(False)
        self.ai_video_prompt_btn.setText("生成中...")

        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_VIDEO_PROMPT,
            text,
            characters=self._get_scene_characters(),
            image_prompt=self.image_prompt_edit.toPlainText().strip(),
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def _ai_analyze_all(self):
        """一键生成（画面提示词+视频提示词）"""
        text = self.subtitle_edit.toPlainText().strip()
        if not text:
            return

        self._set_ai_buttons_enabled(False)
        self.ai_all_btn.setText("生成中...")

        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_ALL,
            text,
            characters=self._get_scene_characters(),
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def _on_ai_completed(self, analysis_type: str, result: dict):
        """AI 分析完成"""
        self._set_ai_buttons_enabled(True)
        self._reset_ai_btn_texts()

        self._is_updating = True

        if analysis_type == AIAnalysisWorker.TYPE_IMAGE_PROMPT:
            prompt = result.get('image_prompt', '')
            if prompt:
                self.image_prompt_edit.setPlainText(prompt)
                self._is_updating = False
                self.property_changed.emit('image_prompt', prompt)
                self._is_updating = True

        elif analysis_type == AIAnalysisWorker.TYPE_VIDEO_PROMPT:
            self._fill_video_prompt_result(result)

        elif analysis_type == AIAnalysisWorker.TYPE_ALL:
            prompt = result.get('image_prompt', '')
            if prompt:
                self.image_prompt_edit.setPlainText(prompt)
                self._is_updating = False
                self.property_changed.emit('image_prompt', prompt)
                self._is_updating = True

            self._fill_video_prompt_result(result)

        self._is_updating = False

    def _fill_video_prompt_result(self, result: dict):
        """填充视频提示词相关结果"""
        video_prompt = result.get('video_prompt', '')
        if video_prompt:
            self.video_prompt_edit.setPlainText(video_prompt)
            self._is_updating = False
            self.property_changed.emit('video_prompt', video_prompt)
            self._is_updating = True

        # 填充5个详情标签
        camera_motion = result.get('camera_motion', '-')
        shot_size = result.get('shot_size', '-')
        character_actions = result.get('character_actions', '-')
        expression_changes = result.get('expression_changes', '-')
        vfx_analysis = result.get('vfx_analysis', '-')

        self.camera_motion_label.setText(f"运镜方式：{camera_motion}")
        self.shot_size_label.setText(f"景别：{shot_size}")
        self.character_actions_label.setText(f"角色动作：{character_actions}")
        self.expression_changes_label.setText(f"表情变化：{expression_changes}")
        self.vfx_analysis_label.setText(f"特效分析：{vfx_analysis}")

        # 回写camera_motion
        if camera_motion and camera_motion != '-':
            self._is_updating = False
            self.property_changed.emit('camera_motion', camera_motion)
            self._is_updating = True

        # 将5个子维度存入generation_params
        video_details = {
            'camera_motion': camera_motion,
            'shot_size': shot_size,
            'character_actions': character_actions,
            'expression_changes': expression_changes,
            'vfx_analysis': vfx_analysis,
        }
        self._is_updating = False
        self.property_changed.emit('video_prompt_details', video_details)
        self._is_updating = True

    def _on_ai_failed(self, analysis_type: str, error: str):
        """AI 分析失败"""
        self._set_ai_buttons_enabled(True)
        self._reset_ai_btn_texts()
        print(f"AI分析失败 [{analysis_type}]: {error}")

    def _reset_ai_btn_texts(self):
        """重置AI按钮文本"""
        self.ai_image_prompt_btn.setText("一键分析画面提示词")
        self.ai_video_prompt_btn.setText("生成视频提示词")
        self.ai_all_btn.setText("一键生成")
