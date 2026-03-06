"""
涛割 - 设置页面组件
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QMessageBox,
    QFileDialog, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from config import get_settings, get_settings_manager
from ui import theme


class SettingsSection(QGroupBox):
    """设置分组组件"""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._apply_theme()

        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(20, 25, 20, 15)
        self._layout.setSpacing(12)
        self._layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

    def _apply_theme(self):
        self.setStyleSheet(f"""
            QGroupBox {{
                font-size: 14px;
                font-weight: bold;
                color: {theme.accent()};
                border: 1px solid {theme.border()};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
            }}
        """)

    def add_row(self, label: str, widget: QWidget):
        """添加一行设置项"""
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {theme.text_secondary()}; font-weight: normal;")
        self._layout.addRow(label_widget, widget)


class ApiKeyInput(QWidget):
    """API密钥输入组件"""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setMinimumWidth(300)
        layout.addWidget(self.input, 1)

        self.toggle_btn = QPushButton("显示")
        self.toggle_btn.setFixedWidth(60)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_visibility)
        layout.addWidget(self.toggle_btn)

    def _toggle_visibility(self):
        if self.input.echoMode() == QLineEdit.EchoMode.Password:
            self.input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText("隐藏")
        else:
            self.input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText("显示")

    def text(self) -> str:
        return self.input.text()

    def setText(self, text: str):
        self.input.setText(text)


class SettingsPage(QWidget):
    """设置页面"""

    settings_changed = pyqtSignal()  # 设置变更信号

    def __init__(self, parent=None):
        super().__init__(parent)

        self.settings = get_settings()
        self.settings_manager = get_settings_manager()

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("设置")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        # 保存按钮
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setFixedSize(120, 40)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setProperty("primary", True)
        self.save_btn.clicked.connect(self._save_settings)
        header.addWidget(self.save_btn)

        layout.addLayout(header)

        # 创建选项卡
        self.tab_widget = QTabWidget()

        # 添加各个设置选项卡
        self.tab_widget.addTab(self._create_api_tab(), "API密钥")
        self.tab_widget.addTab(self._create_generation_tab(), "生成设置")
        self.tab_widget.addTab(self._create_prompt_tab(), "提示词设置")
        self.tab_widget.addTab(self._create_export_tab(), "导出设置")
        self.tab_widget.addTab(self._create_cost_tab(), "成本报表")
        self.tab_widget.addTab(self._create_ui_tab(), "界面设置")

        layout.addWidget(self.tab_widget)

    def _create_scrollable_tab(self) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        """创建可滚动的选项卡内容"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        scroll.setWidget(content)
        return scroll, content, content_layout

    def _create_api_tab(self) -> QWidget:
        """创建API密钥选项卡"""
        scroll, content, layout = self._create_scrollable_tab()

        # DeepSeek API
        deepseek_section = SettingsSection("DeepSeek (文本生成)")
        self.deepseek_key = ApiKeyInput("输入DeepSeek API密钥")
        deepseek_section.add_row("API密钥:", self.deepseek_key)

        self.deepseek_url = QLineEdit()
        self.deepseek_url.setPlaceholderText("https://api.deepseek.com")
        deepseek_section.add_row("API地址:", self.deepseek_url)
        layout.addWidget(deepseek_section)

        # Vidu API
        vidu_section = SettingsSection("Vidu (视频生成)")
        self.vidu_key = ApiKeyInput("输入Vidu API密钥")
        vidu_section.add_row("API密钥:", self.vidu_key)
        layout.addWidget(vidu_section)

        # Kling API
        kling_section = SettingsSection("Kling/可灵 (视频生成)")
        self.kling_access_key = ApiKeyInput("输入Access Key")
        kling_section.add_row("Access Key:", self.kling_access_key)
        self.kling_secret_key = ApiKeyInput("输入Secret Key")
        kling_section.add_row("Secret Key:", self.kling_secret_key)
        layout.addWidget(kling_section)

        # Jimeng API
        jimeng_section = SettingsSection("即梦 (图片生成)")
        self.jimeng_key = ApiKeyInput("输入即梦API密钥")
        jimeng_section.add_row("API密钥:", self.jimeng_key)
        layout.addWidget(jimeng_section)

        # Grok API
        grok_section = SettingsSection("Grok (图片生成)")
        self.grok_key = ApiKeyInput("输入Grok API密钥")
        grok_section.add_row("API密钥:", self.grok_key)
        layout.addWidget(grok_section)

        # 图片生成渠道选择
        from PyQt6.QtWidgets import QComboBox
        provider_section = SettingsSection("图片生成渠道")
        self.image_provider_combo = QComboBox()
        self.image_provider_combo.addItem("Geek (默认)", "geek")
        self.image_provider_combo.addItem("云雾", "yunwu")
        provider_section.add_row("当前渠道:", self.image_provider_combo)
        layout.addWidget(provider_section)

        # Geek API (geekapi.io)
        geek_section = SettingsSection("Geek (图片生成 — gemini 异步格式)")
        self.geek_key = ApiKeyInput("输入Geek API密钥")
        geek_section.add_row("API密钥:", self.geek_key)
        self.geek_url = QLineEdit()
        self.geek_url.setPlaceholderText("https://www.geeknow.top/v1")
        geek_section.add_row("API地址:", self.geek_url)
        layout.addWidget(geek_section)

        # 云雾 API (yunwu.ai)
        yunwu_section = SettingsSection("云雾 (图片生成 gemini-3-pro / 视频生成 sora-2)")
        self.yunwu_key = ApiKeyInput("输入云雾API密钥")
        yunwu_section.add_row("API密钥:", self.yunwu_key)

        self.yunwu_url = QLineEdit()
        self.yunwu_url.setPlaceholderText("https://yunwu.ai")
        yunwu_section.add_row("API地址:", self.yunwu_url)
        layout.addWidget(yunwu_section)

        # ComfyUI
        comfyui_section = SettingsSection("ComfyUI (本地生成)")
        self.comfyui_url = QLineEdit()
        self.comfyui_url.setPlaceholderText("http://127.0.0.1:8188")
        comfyui_section.add_row("服务地址:", self.comfyui_url)

        self.comfyui_enabled = QCheckBox("启用ComfyUI")
        comfyui_section.add_row("", self.comfyui_enabled)
        layout.addWidget(comfyui_section)

        layout.addStretch()
        return scroll

    def _create_generation_tab(self) -> QWidget:
        """创建生成设置选项卡"""
        scroll, content, layout = self._create_scrollable_tab()

        # 图片生成设置
        image_section = SettingsSection("图片生成")

        self.default_image_model = QComboBox()
        self.default_image_model.addItems(["jimeng", "grok", "comfyui"])
        self.default_image_model.setMinimumWidth(200)
        image_section.add_row("默认模型:", self.default_image_model)

        self.image_width = QSpinBox()
        self.image_width.setRange(512, 2048)
        self.image_width.setSingleStep(64)
        self.image_width.setValue(1280)
        self.image_width.setMinimumWidth(120)
        image_section.add_row("默认宽度:", self.image_width)

        self.image_height = QSpinBox()
        self.image_height.setRange(512, 2048)
        self.image_height.setSingleStep(64)
        self.image_height.setValue(720)
        image_section.add_row("默认高度:", self.image_height)

        layout.addWidget(image_section)

        # 视频生成设置
        video_section = SettingsSection("视频生成")

        self.default_video_model = QComboBox()
        self.default_video_model.addItems(["vidu", "kling", "comfyui"])
        video_section.add_row("默认模型:", self.default_video_model)

        self.video_duration = QComboBox()
        self.video_duration.addItems(["4秒", "8秒"])
        video_section.add_row("默认时长:", self.video_duration)

        self.video_fps = QSpinBox()
        self.video_fps.setRange(15, 60)
        self.video_fps.setValue(30)
        video_section.add_row("帧率(FPS):", self.video_fps)

        layout.addWidget(video_section)

        # 质量设置
        quality_section = SettingsSection("质量控制")

        self.auto_enhance = QCheckBox("自动增强Prompt")
        self.auto_enhance.setChecked(True)
        quality_section.add_row("", self.auto_enhance)

        self.retry_count = QSpinBox()
        self.retry_count.setRange(1, 5)
        self.retry_count.setValue(3)
        quality_section.add_row("失败重试次数:", self.retry_count)

        layout.addWidget(quality_section)

        layout.addStretch()
        return scroll

    def _create_prompt_tab(self) -> QWidget:
        """创建提示词设置选项卡"""
        scroll, content, layout = self._create_scrollable_tab()

        # 分镜拆分提示词
        shot_section = SettingsSection("分镜拆分提示词")

        shot_desc = QLabel(
            "AI 拆分分镜时使用的提示词。留空则使用系统默认提示词。\n"
            "可用变量：{act_text}（场景文本）"
        )
        shot_desc.setWordWrap(True)
        shot_desc.setStyleSheet(
            f"color: {theme.text_tertiary()}; font-size: 12px; font-weight: normal;"
        )
        shot_section._layout.addRow(shot_desc)

        self.shot_split_prompt = QTextEdit()
        self.shot_split_prompt.setPlaceholderText("留空使用系统默认提示词...")
        self.shot_split_prompt.setMinimumHeight(360)
        self.shot_split_prompt.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme.bg_secondary()};
                color: {theme.text_primary()};
                border: 1px solid {theme.border()};
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                font-family: "Microsoft YaHei", "Consolas", monospace;
            }}
            QTextEdit:focus {{
                border-color: {theme.accent()};
            }}
        """)
        shot_section._layout.addRow(self.shot_split_prompt)

        # 恢复默认按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        restore_btn = QPushButton("恢复默认提示词")
        restore_btn.setFixedWidth(140)
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.clicked.connect(self._restore_default_shot_prompt)
        btn_layout.addWidget(restore_btn)

        btn_widget = QWidget()
        btn_widget.setLayout(btn_layout)
        shot_section._layout.addRow(btn_widget)

        layout.addWidget(shot_section)

        layout.addStretch()
        return scroll

    def _restore_default_shot_prompt(self):
        """恢复默认分镜拆分提示词"""
        from config.constants import AI_ACT_TO_SHOTS_PROMPT
        self.shot_split_prompt.setPlainText(AI_ACT_TO_SHOTS_PROMPT)

    def _create_export_tab(self) -> QWidget:
        """创建导出设置选项卡"""
        scroll, content, layout = self._create_scrollable_tab()

        # 剪映导出设置
        jianying_section = SettingsSection("剪映导出")

        self.jianying_path = QLineEdit()
        self.jianying_path.setPlaceholderText("选择剪映草稿目录")

        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)
        path_layout.addWidget(self.jianying_path, 1)

        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(80)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_jianying_path)
        path_layout.addWidget(browse_btn)

        path_widget = QWidget()
        path_widget.setLayout(path_layout)
        jianying_section.add_row("草稿目录:", path_widget)

        self.auto_create_tracks = QCheckBox("自动创建字幕轨道")
        self.auto_create_tracks.setChecked(True)
        jianying_section.add_row("", self.auto_create_tracks)

        layout.addWidget(jianying_section)

        # 输出设置
        output_section = SettingsSection("输出设置")

        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("选择默认输出目录")

        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        output_layout.addWidget(self.output_path, 1)

        output_browse_btn = QPushButton("浏览")
        output_browse_btn.setFixedWidth(80)
        output_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        output_browse_btn.clicked.connect(self._browse_output_path)
        output_layout.addWidget(output_browse_btn)

        output_widget = QWidget()
        output_widget.setLayout(output_layout)
        output_section.add_row("输出目录:", output_widget)

        layout.addWidget(output_section)

        layout.addStretch()
        return scroll

    def _create_cost_tab(self) -> QWidget:
        """创建成本报表选项卡"""
        scroll, content, layout = self._create_scrollable_tab()

        # 积分概览卡片
        overview = QFrame()
        overview.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.btn_bg()};
                border: 1px solid {theme.border()};
                border-radius: 10px;
            }}
        """)
        overview_layout = QHBoxLayout(overview)
        overview_layout.setContentsMargins(25, 20, 25, 20)
        overview_layout.setSpacing(30)

        # 当前余额
        self.cost_balance_label = QLabel("--")
        self._add_stat_block(overview_layout, "当前余额", self.cost_balance_label, "rgb(0, 180, 255)")

        # 已使用
        self.cost_used_label = QLabel("--")
        self._add_stat_block(overview_layout, "累计消耗", self.cost_used_label, "rgb(245, 158, 11)")

        # 操作次数
        self.cost_count_label = QLabel("--")
        self._add_stat_block(overview_layout, "操作次数", self.cost_count_label, "rgb(139, 92, 246)")

        # 使用比例进度条
        ratio_block = QVBoxLayout()
        ratio_block.setSpacing(6)

        ratio_title = QLabel("使用比例")
        ratio_title.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        ratio_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ratio_block.addWidget(ratio_title)

        self.cost_ratio_bar = QProgressBar()
        self.cost_ratio_bar.setFixedHeight(12)
        self.cost_ratio_bar.setRange(0, 100)
        self.cost_ratio_bar.setTextVisible(False)
        self.cost_ratio_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: rgb(0, 180, 255);
                border-radius: 6px;
            }
        """)
        ratio_block.addWidget(self.cost_ratio_bar)

        self.cost_ratio_label = QLabel("0%")
        self.cost_ratio_label.setStyleSheet(f"color: {theme.text_primary()}; font-size: 14px; font-weight: bold;")
        self.cost_ratio_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ratio_block.addWidget(self.cost_ratio_label)

        overview_layout.addLayout(ratio_block)
        overview_layout.addStretch()

        layout.addWidget(overview)

        # 按操作类型分布
        type_section = SettingsSection("按操作类型分布")
        self.cost_by_type_layout = QVBoxLayout()
        type_section._layout.addRow(self.cost_by_type_layout)
        layout.addWidget(type_section)

        # 最近消费记录表格
        records_section = SettingsSection("最近消费记录")

        self.cost_table = QTableWidget()
        self.cost_table.setColumnCount(5)
        self.cost_table.setHorizontalHeaderLabels(["时间", "操作", "模型", "消耗积分", "余额"])
        self.cost_table.setAlternatingRowColors(True)
        self.cost_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cost_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cost_table.verticalHeader().setVisible(False)
        self.cost_table.setMinimumHeight(300)

        header = self.cost_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        records_section._layout.addRow(self.cost_table)

        # 刷新按钮
        refresh_btn = QPushButton("刷新报表")
        refresh_btn.setFixedWidth(120)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_cost_report)
        records_section._layout.addRow("", refresh_btn)

        layout.addWidget(records_section)

        layout.addStretch()

        # 首次加载数据
        QTimer.singleShot(100, self._refresh_cost_report)

        return scroll

    def _add_stat_block(self, parent_layout: QHBoxLayout, title: str,
                        value_label: QLabel, color: str):
        """添加统计块到布局"""
        block = QVBoxLayout()
        block.setSpacing(4)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.addWidget(title_label)

        value_label.setStyleSheet(f"color: {color}; font-size: 26px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        block.addWidget(value_label)

        parent_layout.addLayout(block)

    def _refresh_cost_report(self):
        """刷新成本报表数据"""
        try:
            from services.cost import get_cost_tracker
            tracker = get_cost_tracker()

            summary = tracker.get_summary()
            records = tracker.get_records(limit=50)

            # 更新概览
            balance = summary.get('current_balance', 0)
            total_used = summary.get('total_credits_used', 0)
            count = summary.get('records_count', 0)
            ratio = summary.get('usage_ratio', 0)

            self.cost_balance_label.setText(f"{balance:.1f}")
            self.cost_used_label.setText(f"{total_used:.1f}")
            self.cost_count_label.setText(str(count))

            ratio_pct = int(ratio * 100)
            self.cost_ratio_bar.setValue(ratio_pct)
            self.cost_ratio_label.setText(f"{ratio_pct}%")

            # 根据比例改变颜色
            if ratio >= 0.9:
                bar_color = "rgb(239, 68, 68)"  # 红色
            elif ratio >= 0.7:
                bar_color = "rgb(245, 158, 11)"  # 橙色
            else:
                bar_color = "rgb(0, 180, 255)"  # 蓝色
            self.cost_ratio_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 6px;
                }}
            """)

            # 更新按操作类型分布
            self._update_type_distribution(summary.get('credits_by_operation', {}))

            # 更新记录表格
            self._update_records_table(records)

        except Exception as e:
            print(f"刷新成本报表失败: {e}")

    def _update_type_distribution(self, by_operation: dict):
        """更新按操作类型分布"""
        # 清空
        while self.cost_by_type_layout.count():
            item = self.cost_by_type_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not by_operation:
            empty = QLabel("暂无消费记录")
            empty.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 13px;")
            self.cost_by_type_layout.addWidget(empty)
            return

        total = sum(by_operation.values())
        op_names = {
            'image_gen': '图像生成',
            'video_gen': '视频生成',
            'i2v': '图生视频',
            'tag_gen': 'AI标签',
            'comfyui_workflow': 'ComfyUI',
        }
        op_colors = {
            'image_gen': 'rgb(59, 130, 246)',
            'video_gen': 'rgb(139, 92, 246)',
            'i2v': 'rgb(245, 158, 11)',
            'tag_gen': 'rgb(16, 185, 129)',
            'comfyui_workflow': 'rgb(236, 72, 153)',
        }

        for op_type, amount in sorted(by_operation.items(), key=lambda x: x[1], reverse=True):
            row = QHBoxLayout()
            row.setSpacing(12)

            name = op_names.get(op_type, op_type)
            name_label = QLabel(name)
            name_label.setFixedWidth(100)
            name_label.setStyleSheet(f"color: {theme.text_secondary()}; font-size: 13px;")
            row.addWidget(name_label)

            bar = QProgressBar()
            bar.setFixedHeight(10)
            bar.setRange(0, int(total) if total > 0 else 1)
            bar.setValue(int(amount))
            bar.setTextVisible(False)
            color = op_colors.get(op_type, 'rgb(107, 114, 128)')
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: rgba(255, 255, 255, 0.05);
                    border-radius: 5px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 5px;
                }}
            """)
            row.addWidget(bar, 1)

            pct = (amount / total * 100) if total > 0 else 0
            amount_label = QLabel(f"{amount:.1f} ({pct:.0f}%)")
            amount_label.setFixedWidth(100)
            amount_label.setStyleSheet(f"color: {theme.text_tertiary()}; font-size: 12px;")
            amount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(amount_label)

            container = QWidget()
            container.setLayout(row)
            self.cost_by_type_layout.addWidget(container)

    def _update_records_table(self, records: list):
        """更新消费记录表格"""
        self.cost_table.setRowCount(len(records))

        for i, record in enumerate(records):
            # 时间
            time_str = record.get('created_at', '')
            if time_str:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(time_str)
                    time_str = dt.strftime("%m-%d %H:%M")
                except (ValueError, TypeError):
                    pass
            self.cost_table.setItem(i, 0, QTableWidgetItem(time_str))

            # 操作
            self.cost_table.setItem(i, 1, QTableWidgetItem(
                record.get('operation_name', record.get('operation_type', ''))
            ))

            # 模型
            self.cost_table.setItem(i, 2, QTableWidgetItem(
                record.get('model_used', '-')
            ))

            # 消耗
            credits_used = record.get('credits_used', 0)
            cost_item = QTableWidgetItem(f"-{credits_used:.1f}")
            cost_item.setForeground(QColor(239, 68, 68))
            self.cost_table.setItem(i, 3, cost_item)

            # 余额
            credits_after = record.get('credits_after', 0)
            self.cost_table.setItem(i, 4, QTableWidgetItem(f"{credits_after:.1f}"))

    def _create_ui_tab(self) -> QWidget:
        """创建界面设置选项卡"""
        scroll, content, layout = self._create_scrollable_tab()

        # 界面设置
        ui_section = SettingsSection("界面")

        self.theme = QComboBox()
        self.theme.addItems(["深色主题", "浅色主题"])
        ui_section.add_row("主题:", self.theme)

        self.language = QComboBox()
        self.language.addItems(["简体中文", "English"])
        ui_section.add_row("语言:", self.language)

        self.auto_save = QCheckBox("自动保存项目")
        self.auto_save.setChecked(True)
        ui_section.add_row("", self.auto_save)

        layout.addWidget(ui_section)

        # 积分设置
        credits_section = SettingsSection("积分")

        self.credits_balance = QDoubleSpinBox()
        self.credits_balance.setRange(0, 999999)
        self.credits_balance.setDecimals(1)
        self.credits_balance.setValue(1000)
        self.credits_balance.setMinimumWidth(150)
        credits_section.add_row("当前积分:", self.credits_balance)

        self.low_credits_warning = QSpinBox()
        self.low_credits_warning.setRange(0, 1000)
        self.low_credits_warning.setValue(100)
        self.low_credits_warning.setMinimumWidth(150)
        credits_section.add_row("低积分警告阈值:", self.low_credits_warning)

        layout.addWidget(credits_section)

        layout.addStretch()
        return scroll

    def _browse_jianying_path(self):
        """浏览剪映草稿目录"""
        path = QFileDialog.getExistingDirectory(self, "选择剪映草稿目录")
        if path:
            self.jianying_path.setText(path)

    def _browse_output_path(self):
        """浏览输出目录"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_path.setText(path)

    def _load_settings(self):
        """从配置加载设置"""
        settings = self.settings

        # API密钥
        self.deepseek_key.setText(settings.api.deepseek_api_key)
        self.deepseek_url.setText(settings.api.deepseek_base_url)
        self.vidu_key.setText(settings.api.vidu_api_key)
        self.kling_access_key.setText(settings.api.kling_api_key)
        self.kling_secret_key.setText("")  # kling只有一个api_key
        self.jimeng_key.setText(settings.api.jimeng_api_key)
        self.grok_key.setText(settings.api.grok_api_key)

        # 图片生成渠道
        idx = self.image_provider_combo.findData(settings.api.image_provider)
        if idx >= 0:
            self.image_provider_combo.setCurrentIndex(idx)

        # Geek
        self.geek_key.setText(settings.api.geek_api_key)
        self.geek_url.setText(settings.api.geek_base_url)

        # 云雾
        self.yunwu_key.setText(settings.api.yunwu_api_key)
        self.yunwu_url.setText(settings.api.yunwu_base_url)

        # ComfyUI
        self.comfyui_url.setText(settings.api.comfyui_server_url)
        self.comfyui_enabled.setChecked(settings.api.comfyui_enabled)

        # 生成设置
        self.image_width.setValue(settings.export.video_width)
        self.image_height.setValue(settings.export.video_height)
        self.video_fps.setValue(settings.export.video_fps)
        self.retry_count.setValue(settings.generation.retry_count)

        # 导出设置
        self.jianying_path.setText(settings.export.jianying_font_path)
        self.output_path.setText(settings.export.default_export_path)

        # 积分
        self.credits_balance.setValue(int(settings.credits.balance))
        self.low_credits_warning.setValue(int(settings.credits.warning_threshold * 100))

        # 提示词
        if hasattr(settings, 'prompts'):
            self.shot_split_prompt.setPlainText(settings.prompts.shot_split_prompt)

        # UI设置
        if hasattr(settings, 'ui'):
            theme_idx = 0 if settings.ui.theme == "dark" else 1
            self.theme.setCurrentIndex(theme_idx)

    def _save_settings(self):
        """保存设置"""
        settings = self.settings

        # API密钥
        settings.api.deepseek_api_key = self.deepseek_key.text()
        settings.api.deepseek_base_url = self.deepseek_url.text() or "https://api.deepseek.com"
        settings.api.vidu_api_key = self.vidu_key.text()
        settings.api.kling_api_key = self.kling_access_key.text()
        # kling_secret_key 不再使用，忽略
        settings.api.jimeng_api_key = self.jimeng_key.text()
        settings.api.grok_api_key = self.grok_key.text()

        # 图片生成渠道
        settings.api.image_provider = self.image_provider_combo.currentData() or "geek"

        # Geek
        settings.api.geek_api_key = self.geek_key.text()
        settings.api.geek_base_url = self.geek_url.text() or "https://www.geeknow.top/v1"

        # 云雾
        settings.api.yunwu_api_key = self.yunwu_key.text()
        settings.api.yunwu_base_url = self.yunwu_url.text() or "https://yunwu.ai"

        # ComfyUI
        settings.api.comfyui_server_url = self.comfyui_url.text() or "http://127.0.0.1:8188"
        settings.api.comfyui_enabled = self.comfyui_enabled.isChecked()

        # 生成设置
        settings.export.video_width = self.image_width.value()
        settings.export.video_height = self.image_height.value()
        settings.export.video_fps = self.video_fps.value()
        settings.generation.retry_count = self.retry_count.value()

        # 导出设置
        settings.export.jianying_font_path = self.jianying_path.text()
        settings.export.default_export_path = self.output_path.text()

        # 积分
        settings.credits.balance = float(self.credits_balance.value())
        settings.credits.warning_threshold = self.low_credits_warning.value() / 100.0

        # 提示词
        if hasattr(settings, 'prompts'):
            settings.prompts.shot_split_prompt = self.shot_split_prompt.toPlainText().strip()

        # UI设置
        if hasattr(settings, 'ui'):
            settings.ui.theme = "dark" if self.theme.currentIndex() == 0 else "light"

        # 保存到文件
        self.settings_manager.save_settings()

        # 发送信号
        self.settings_changed.emit()

        QMessageBox.information(self, "提示", "设置已保存")
