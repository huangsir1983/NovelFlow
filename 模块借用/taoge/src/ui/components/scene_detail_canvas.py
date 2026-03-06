"""
涛割 - 场景精编画布面板
双击分镜卡片后从右侧滑入的独立精编面板，用于精细化编辑、生成图片/视频。
基于 CanvasPropertyPanel 增强，支持更大预览区、更丰富编辑体验。
"""

import os
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from ui import theme
from ui.pixmap_cache import PixmapCache
from services.ai_analyzer import AIAnalysisWorker


class SceneDetailCanvas(QFrame):
    """
    场景精编画布面板
    布局：顶栏(返回+标题+关闭) | 大图预览 | 叙事/画面/视频提示词编辑 |
          只读标签 | 角色列表 | 底部操作栏
    """

    property_changed = pyqtSignal(str, object)
    generate_image_requested = pyqtSignal(int)
    generate_video_requested = pyqtSignal(int)
    ai_analyze_requested = pyqtSignal(int)
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_scene_index: int = -1
        self._scene_data: Dict[str, Any] = {}
        self._is_updating = False
        self._ai_worker: Optional[AIAnalysisWorker] = None

        self.setObjectName("sceneDetailCanvas")
        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ========== 顶部标题栏 ==========
        header = QFrame()
        header.setObjectName("detailHeader")
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        self._back_btn = QPushButton("\u2190 返回")
        self._back_btn.setFixedHeight(30)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self._back_btn)

        self._title_label = QLabel("场景精编")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self._title_label, 1)

        self._close_btn = QPushButton("\u2715")
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self._close_btn)

        layout.addWidget(header)

        # ========== 可滚动内容区 ==========
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("detailScroll")

        content = QWidget()
        content.setObjectName("detailContent")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(16, 16, 16, 16)
        self._content_layout.setSpacing(14)

        # ---- 大图预览区 ----
        self._preview_label = QLabel()
        self._preview_label.setMinimumHeight(240)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_label.setObjectName("detailPreview")
        self._preview_label.setText("无预览")
        self._content_layout.addWidget(self._preview_label)

        # ---- 叙事内容 ----
        self._add_section_header("叙事内容")
        self._subtitle_edit = QTextEdit()
        self._subtitle_edit.setMinimumHeight(80)
        self._subtitle_edit.setMaximumHeight(120)
        self._subtitle_edit.setPlaceholderText("场景叙事文本...")
        self._subtitle_edit.textChanged.connect(self._on_subtitle_changed)
        self._subtitle_edit.setObjectName("detailTextEdit")
        self._content_layout.addWidget(self._subtitle_edit)

        # ---- 画面提示词 ----
        self._add_section_header("画面提示词")
        self._image_prompt_edit = QTextEdit()
        self._image_prompt_edit.setMinimumHeight(60)
        self._image_prompt_edit.setMaximumHeight(100)
        self._image_prompt_edit.setPlaceholderText("图像生成提示词...")
        self._image_prompt_edit.textChanged.connect(self._on_image_prompt_changed)
        self._image_prompt_edit.setObjectName("detailTextEdit")
        self._content_layout.addWidget(self._image_prompt_edit)

        # ---- 视频提示词 ----
        self._add_section_header("视频提示词")
        self._video_prompt_edit = QTextEdit()
        self._video_prompt_edit.setMinimumHeight(80)
        self._video_prompt_edit.setMaximumHeight(120)
        self._video_prompt_edit.setPlaceholderText("综合性的视频提示词...")
        self._video_prompt_edit.textChanged.connect(self._on_video_prompt_changed)
        self._video_prompt_edit.setObjectName("detailTextEdit")
        self._content_layout.addWidget(self._video_prompt_edit)

        # ---- 只读详情标签 ----
        self._add_section_header("视频参数")
        tags_frame = QFrame()
        tags_frame.setObjectName("detailTagsFrame")
        tags_layout = QVBoxLayout(tags_frame)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        tags_layout.setSpacing(6)

        self._camera_motion_label = QLabel("运镜：-")
        self._shot_size_label = QLabel("景别：-")
        self._character_actions_label = QLabel("动作：-")
        self._expression_changes_label = QLabel("表情：-")
        self._vfx_analysis_label = QLabel("特效：-")

        for lbl in (self._camera_motion_label, self._shot_size_label,
                    self._character_actions_label, self._expression_changes_label,
                    self._vfx_analysis_label):
            lbl.setWordWrap(True)
            lbl.setObjectName("detailTagLabel")
            tags_layout.addWidget(lbl)

        self._content_layout.addWidget(tags_frame)

        # ---- 角色列表 ----
        self._add_section_header("角色")
        self._characters_label = QLabel("无角色关联")
        self._characters_label.setObjectName("detailCharactersLabel")
        self._content_layout.addWidget(self._characters_label)

        self._content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # ========== 底部操作栏 ==========
        btn_frame = QFrame()
        btn_frame.setObjectName("detailBottomBar")
        btn_frame.setFixedHeight(60)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(16, 0, 16, 0)
        btn_layout.setSpacing(10)

        self._ai_all_btn = QPushButton("一键AI分析")
        self._ai_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_all_btn.clicked.connect(self._ai_analyze_all)
        self._ai_all_btn.setObjectName("detailAiBtn")
        btn_layout.addWidget(self._ai_all_btn)

        self._gen_img_btn = QPushButton("生成图片")
        self._gen_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_img_btn.clicked.connect(
            lambda: self.generate_image_requested.emit(self.current_scene_index)
        )
        self._gen_img_btn.setObjectName("detailGenImgBtn")
        btn_layout.addWidget(self._gen_img_btn)

        self._gen_vid_btn = QPushButton("生成视频")
        self._gen_vid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_vid_btn.clicked.connect(
            lambda: self.generate_video_requested.emit(self.current_scene_index)
        )
        self._gen_vid_btn.setObjectName("detailGenVidBtn")
        btn_layout.addWidget(self._gen_vid_btn)

        layout.addWidget(btn_frame)

    def _add_section_header(self, text: str):
        label = QLabel(text)
        label.setObjectName("detailSectionHeader")
        self._content_layout.addWidget(label)

    # ==================== 主题 ====================

    def _apply_theme(self):
        dark = theme.is_dark()

        self.setStyleSheet(f"""
            QFrame#sceneDetailCanvas {{
                background-color: {theme.bg_primary()};
            }}

            QFrame#detailHeader {{
                background-color: {theme.bg_secondary()};
                border-bottom: 1px solid {theme.border()};
            }}

            QLabel#detailSectionHeader {{
                color: {theme.text_secondary()};
                font-size: 11px;
                font-weight: bold;
                padding-top: 4px;
            }}

            QLabel#detailPreview {{
                background-color: {"rgba(255,255,255,0.03)" if dark else "rgba(0,0,0,0.03)"};
                border: 1px solid {theme.border()};
                border-radius: 8px;
                color: {theme.text_tertiary()};
                font-size: 12px;
            }}

            QTextEdit#detailTextEdit {{
                background-color: {"rgba(255,255,255,0.04)" if dark else "rgba(0,0,0,0.02)"};
                border: 1px solid {theme.border()};
                border-radius: 6px;
                padding: 8px;
                color: {theme.text_primary()};
                font-size: 12px;
            }}
            QTextEdit#detailTextEdit:focus {{
                border-color: {theme.accent()};
            }}

            QLabel#detailTagLabel {{
                color: {theme.text_secondary()};
                font-size: 11px;
                padding: 4px 8px;
                background-color: {"rgba(255,255,255,0.03)" if dark else "rgba(0,0,0,0.02)"};
                border-radius: 4px;
            }}

            QLabel#detailCharactersLabel {{
                color: {theme.text_tertiary()};
                font-size: 11px;
                padding: 8px;
                background-color: {"rgba(255,255,255,0.02)" if dark else "rgba(0,0,0,0.01)"};
                border-radius: 4px;
            }}

            QFrame#detailBottomBar {{
                background-color: {theme.bg_secondary()};
                border-top: 1px solid {theme.border()};
            }}

            QScrollArea#detailScroll {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background-color: {theme.scrollbar_bg()};
                width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme.scrollbar_handle()};
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}

            QWidget#detailContent {{
                background: transparent;
            }}
        """)

        # 按钮样式
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.text_secondary()};
                border: none;
                font-size: 13px;
            }}
            QPushButton:hover {{
                color: {theme.text_primary()};
            }}
        """)

        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.text_tertiary()};
                border: none;
                font-size: 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.btn_bg_hover()};
                color: {theme.text_primary()};
            }}
        """)

        self._title_label.setStyleSheet(f"""
            color: {theme.text_primary()};
            font-size: 14px;
            font-weight: bold;
        """)

        self._ai_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(139, 92, 246, 0.8);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: rgba(139, 92, 246, 1.0); }}
            QPushButton:disabled {{ background-color: rgba(139, 92, 246, 0.3); }}
        """)

        self._gen_img_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.accent()};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {theme.accent_hover()}; }}
        """)

        self._gen_vid_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(76, 175, 80, 0.85);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: rgba(76, 175, 80, 1.0); }}
        """)

    # ==================== 数据绑定 ====================

    def set_scene(self, index: int, scene_data: Dict[str, Any]):
        self._is_updating = True
        self.current_scene_index = index
        self._scene_data = scene_data

        self._title_label.setText(f"场景 #{index + 1} 精编")

        # 预览图
        self._update_preview(scene_data)

        # 叙事
        self._subtitle_edit.setPlainText(scene_data.get('subtitle_text', ''))

        # 画面提示词
        self._image_prompt_edit.setPlainText(scene_data.get('image_prompt', ''))

        # 视频提示词
        self._video_prompt_edit.setPlainText(scene_data.get('video_prompt', ''))

        # 5个详情标签
        gen_params = scene_data.get('generation_params') or {}
        self._camera_motion_label.setText(f"运镜：{gen_params.get('camera_motion', '-')}")
        self._shot_size_label.setText(f"景别：{gen_params.get('shot_size', '-')}")
        self._character_actions_label.setText(f"动作：{gen_params.get('character_actions', '-')}")
        self._expression_changes_label.setText(f"表情：{gen_params.get('expression_changes', '-')}")
        self._vfx_analysis_label.setText(f"特效：{gen_params.get('vfx_analysis', '-')}")

        # 角色
        chars = scene_data.get('characters', [])
        if chars:
            names = []
            for c in chars:
                if isinstance(c, dict):
                    names.append(c.get('name', '?'))
                elif isinstance(c, str):
                    names.append(c)
            self._characters_label.setText("  ".join(f"[{n}]" for n in names))
            self._characters_label.setStyleSheet(f"""
                color: rgba(139, 92, 246, 0.85);
                font-size: 12px;
                padding: 8px;
                background-color: rgba(139, 92, 246, 0.08);
                border-radius: 4px;
            """)
        else:
            self._characters_label.setText("无角色关联")
            self._characters_label.setStyleSheet(f"""
                color: {theme.text_tertiary()};
                font-size: 11px;
                padding: 8px;
                background-color: {"rgba(255,255,255,0.02)" if theme.is_dark() else "rgba(0,0,0,0.01)"};
                border-radius: 4px;
            """)

        self._is_updating = False

    def _update_preview(self, scene_data: Dict[str, Any]):
        cache = PixmapCache.instance()
        preview_w = max(self.width() - 40, 300)
        preview_h = 220
        for key in ('generated_image_path', 'start_frame_path'):
            path = scene_data.get(key, '')
            if path and os.path.exists(path):
                scaled = cache.get_scaled(path, preview_w, preview_h)
                if scaled:
                    self._preview_label.setPixmap(scaled)
                    return
        self._preview_label.clear()
        self._preview_label.setText("无预览")

    # ==================== 属性变更回调 ====================

    def _on_subtitle_changed(self):
        if not self._is_updating and self.current_scene_index >= 0:
            text = self._subtitle_edit.toPlainText()
            self.property_changed.emit('subtitle_text', text)

    def _on_image_prompt_changed(self):
        if not self._is_updating and self.current_scene_index >= 0:
            text = self._image_prompt_edit.toPlainText()
            self.property_changed.emit('image_prompt', text)

    def _on_video_prompt_changed(self):
        if not self._is_updating and self.current_scene_index >= 0:
            text = self._video_prompt_edit.toPlainText()
            self.property_changed.emit('video_prompt', text)

    # ==================== AI 分析 ====================

    def _get_scene_characters(self) -> List[str]:
        chars = self._scene_data.get('characters', [])
        names = []
        for c in chars:
            if isinstance(c, dict):
                names.append(c.get('name', ''))
            elif isinstance(c, str):
                names.append(c)
        return [n for n in names if n]

    def _set_ai_buttons_enabled(self, enabled: bool):
        self._ai_all_btn.setEnabled(enabled)

    def _ai_analyze_all(self):
        """一键AI分析（画面+视频提示词）"""
        text = self._subtitle_edit.toPlainText().strip()
        if not text:
            return

        self._set_ai_buttons_enabled(False)
        self._ai_all_btn.setText("分析中...")

        self._ai_worker = AIAnalysisWorker(
            AIAnalysisWorker.TYPE_ALL,
            text,
            characters=self._get_scene_characters(),
        )
        self._ai_worker.analysis_completed.connect(self._on_ai_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

        # 同时发出信号通知外部
        self.ai_analyze_requested.emit(self.current_scene_index)

    def _on_ai_completed(self, analysis_type: str, result: dict):
        self._set_ai_buttons_enabled(True)
        self._ai_all_btn.setText("一键AI分析")

        self._is_updating = True

        # 画面提示词
        prompt = result.get('image_prompt', '')
        if prompt:
            self._image_prompt_edit.setPlainText(prompt)
            self._is_updating = False
            self.property_changed.emit('image_prompt', prompt)
            self._is_updating = True

        # 视频提示词
        video_prompt = result.get('video_prompt', '')
        if video_prompt:
            self._video_prompt_edit.setPlainText(video_prompt)
            self._is_updating = False
            self.property_changed.emit('video_prompt', video_prompt)
            self._is_updating = True

        # 5个详情标签
        camera_motion = result.get('camera_motion', '-')
        shot_size = result.get('shot_size', '-')
        character_actions = result.get('character_actions', '-')
        expression_changes = result.get('expression_changes', '-')
        vfx_analysis = result.get('vfx_analysis', '-')

        self._camera_motion_label.setText(f"运镜：{camera_motion}")
        self._shot_size_label.setText(f"景别：{shot_size}")
        self._character_actions_label.setText(f"动作：{character_actions}")
        self._expression_changes_label.setText(f"表情：{expression_changes}")
        self._vfx_analysis_label.setText(f"特效：{vfx_analysis}")

        # 回写 camera_motion
        if camera_motion and camera_motion != '-':
            self._is_updating = False
            self.property_changed.emit('camera_motion', camera_motion)
            self._is_updating = True

        # 将5个子维度存入 generation_params
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

        self._is_updating = False

    def _on_ai_failed(self, analysis_type: str, error: str):
        self._set_ai_buttons_enabled(True)
        self._ai_all_btn.setText("一键AI分析")
        print(f"AI分析失败 [{analysis_type}]: {error}")
