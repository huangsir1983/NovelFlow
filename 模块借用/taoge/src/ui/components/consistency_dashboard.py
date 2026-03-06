"""
涛割 - 一致性仪表盘
运镜冲突统计 / 轴线违背 / 时长异常 / AI 连贯性建议
"""

from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor

from ui import theme


# ============================================================
#  ContinuityAIWorker — AI 连贯性分析工作线程
# ============================================================

class ContinuityAIWorker(QThread):
    """AI 连贯性分析工作线程"""

    analysis_completed = pyqtSignal(list)  # [{scene_index, issue, suggestion}]
    analysis_failed = pyqtSignal(str)

    def __init__(self, scenes: List[dict]):
        super().__init__()
        self._scenes = scenes

    def run(self):
        try:
            from config.constants import AI_CONTINUITY_ANALYSIS_PROMPT
            from services.ai_analyzer import DeepSeekProvider

            # 构建分析输入
            scene_summaries = []
            for i, s in enumerate(self._scenes):
                summary = {
                    'index': i + 1,
                    'duration': s.get('duration', 3.0),
                    'camera_motion': s.get('camera_motion', 'Static'),
                    'image_prompt': s.get('image_prompt', ''),
                    'subtitle_text': s.get('subtitle_text', ''),
                }
                scene_summaries.append(str(summary))

            input_text = "\n".join(scene_summaries)

            provider = DeepSeekProvider()
            result = provider.chat(
                AI_CONTINUITY_ANALYSIS_PROMPT,
                input_text,
            )

            # 解析结果
            issues = []
            if result:
                import json
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, list):
                        issues = parsed
                except (json.JSONDecodeError, ValueError):
                    # 按行解析
                    for line in result.strip().split('\n'):
                        line = line.strip()
                        if line:
                            issues.append({
                                'scene_index': 0,
                                'issue': line,
                                'suggestion': '',
                            })

            self.analysis_completed.emit(issues)

        except Exception as e:
            self.analysis_failed.emit(str(e))


# ============================================================
#  IssueCard — 问题卡片
# ============================================================

class IssueCard(QFrame):
    """单个问题卡片"""

    def __init__(self, issue_data: dict, parent=None):
        super().__init__(parent)
        self._data = issue_data
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # 类型 + 场景号
        header = QHBoxLayout()
        issue_type = self._data.get('type', 'info')
        colors = {
            'conflict': ('#ff453a', '运镜冲突'),
            'axis': ('#ff9f0a', '轴线违背'),
            'duration': ('#ffd60a', '时长异常'),
            'ai': ('#5e5ce6', 'AI 建议'),
            'info': ('#8e8e93', '信息'),
        }
        color, type_label = colors.get(issue_type, colors['info'])

        badge = QLabel(type_label)
        badge.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
        badge.setStyleSheet(
            f"color: {color}; background: {color}20; "
            f"border-radius: 3px; padding: 1px 6px;"
        )
        badge.setFixedHeight(18)
        header.addWidget(badge)

        scene_idx = self._data.get('scene_index', 0)
        if scene_idx:
            scene_lbl = QLabel(f"场景 #{scene_idx}")
            scene_lbl.setFont(QFont("Microsoft YaHei", 8))
            scene_lbl.setStyleSheet(f"color: {theme.text_tertiary()};")
            header.addWidget(scene_lbl)

        header.addStretch()
        layout.addLayout(header)

        # 描述
        desc = QLabel(self._data.get('issue', ''))
        desc.setFont(QFont("Microsoft YaHei", 9))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {theme.text_primary()};")
        layout.addWidget(desc)

        # 建议
        suggestion = self._data.get('suggestion', '')
        if suggestion:
            sug = QLabel(f"建议: {suggestion}")
            sug.setFont(QFont("Microsoft YaHei", 8))
            sug.setWordWrap(True)
            sug.setStyleSheet(f"color: {theme.text_secondary()};")
            layout.addWidget(sug)


# ============================================================
#  ConsistencyDashboard — 一致性仪表盘
# ============================================================

class ConsistencyDashboard(QWidget):
    """一致性仪表盘"""

    def __init__(self, data_hub=None, parent=None):
        super().__init__(parent)
        self._data_hub = data_hub
        self._issues: List[dict] = []
        self._ai_worker: Optional[ContinuityAIWorker] = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("连贯性检查")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._analyze_btn = QPushButton("一键分析")
        self._analyze_btn.setFixedHeight(30)
        self._analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._analyze_btn.clicked.connect(self._on_analyze)
        header.addWidget(self._analyze_btn)

        self._ai_btn = QPushButton("AI 深度分析")
        self._ai_btn.setFixedHeight(30)
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_btn.clicked.connect(self._on_ai_analyze)
        header.addWidget(self._ai_btn)

        layout.addLayout(header)

        # 统计摘要
        self._summary_label = QLabel("未分析")
        self._summary_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self._summary_label)

        # 问题列表（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._issues_container = QWidget()
        self._issues_layout = QVBoxLayout(self._issues_container)
        self._issues_layout.setContentsMargins(0, 0, 0, 0)
        self._issues_layout.setSpacing(6)
        self._issues_layout.addStretch()
        scroll.setWidget(self._issues_container)
        layout.addWidget(scroll, 1)

    # === 外部接口 ===

    def analyze_project(self, project_id: int = None):
        """分析项目连贯性"""
        if not self._data_hub:
            return

        scenes = self._data_hub.scenes_data
        if not scenes:
            self._summary_label.setText("无场景数据")
            return

        self._issues.clear()
        self._issues.extend(self._check_camera_conflicts(scenes))
        self._issues.extend(self._check_axis_violations(scenes))
        self._issues.extend(self._check_duration_anomalies(scenes))
        self._refresh_ui()

    # === 检查方法 ===

    def _check_camera_conflicts(self, scenes: List[dict]) -> List[dict]:
        """检查运镜冲突"""
        issues = []
        from config.constants import CAMERA_CONFLICT_RULES

        for i in range(len(scenes) - 1):
            cam_a = scenes[i].get('camera_motion', 'Static')
            cam_b = scenes[i + 1].get('camera_motion', 'Static')

            for rule in CAMERA_CONFLICT_RULES:
                r_a, r_b, severity, desc = rule
                if (cam_a == r_a and cam_b == r_b) or \
                   (cam_a == r_b and cam_b == r_a):
                    issues.append({
                        'type': 'conflict',
                        'scene_index': i + 1,
                        'issue': f"场景 #{i + 1} → #{i + 2}: {desc}",
                        'suggestion': f"建议将 {cam_b} 改为其他运镜方式",
                    })
        return issues

    def _check_axis_violations(self, scenes: List[dict]) -> List[dict]:
        """检查 180 度轴线违背"""
        issues = []
        # 比较同角色在相邻镜头中的位置
        for i in range(len(scenes) - 1):
            chars_a = {
                c.get('id'): c for c in scenes[i].get('characters', [])
            }
            chars_b = {
                c.get('id'): c for c in scenes[i + 1].get('characters', [])
            }

            for char_id in set(chars_a.keys()) & set(chars_b.keys()):
                x_a = chars_a[char_id].get('position_x', 0)
                x_b = chars_b[char_id].get('position_x', 0)
                name = chars_a[char_id].get('name', f'角色{char_id}')

                # 如果左右关系反转（跨过中线）
                if x_a and x_b and (x_a - 0.5) * (x_b - 0.5) < 0:
                    issues.append({
                        'type': 'axis',
                        'scene_index': i + 1,
                        'issue': f"场景 #{i + 1} → #{i + 2}: "
                                 f"{name} 左右位置反转（疑似越轴）",
                        'suggestion': "确认是否故意越轴，否则调整角色位置",
                    })
        return issues

    def _check_duration_anomalies(self, scenes: List[dict]) -> List[dict]:
        """检查时长异常"""
        issues = []
        if not scenes:
            return issues

        durations = [s.get('duration', 3.0) for s in scenes]
        avg = sum(durations) / len(durations)

        for i, dur in enumerate(durations):
            if dur > avg * 3:
                issues.append({
                    'type': 'duration',
                    'scene_index': i + 1,
                    'issue': f"场景 #{i + 1} 时长 {dur:.1f}s，"
                             f"远超平均值 {avg:.1f}s",
                    'suggestion': "考虑拆分为多个镜头或缩短时长",
                })
            elif dur < avg * 0.3 and dur < 1.0:
                issues.append({
                    'type': 'duration',
                    'scene_index': i + 1,
                    'issue': f"场景 #{i + 1} 时长 {dur:.1f}s 过短",
                    'suggestion': "考虑合并到相邻镜头或增加时长",
                })
        return issues

    # === AI 分析 ===

    def _on_analyze(self):
        self.analyze_project()

    def _on_ai_analyze(self):
        if not self._data_hub or not self._data_hub.scenes_data:
            return

        self._ai_btn.setText("分析中...")
        self._ai_btn.setEnabled(False)

        self._ai_worker = ContinuityAIWorker(self._data_hub.scenes_data)
        self._ai_worker.analysis_completed.connect(self._on_ai_completed)
        self._ai_worker.analysis_failed.connect(self._on_ai_failed)
        self._ai_worker.start()

    def _on_ai_completed(self, ai_issues: list):
        self._ai_btn.setText("AI 深度分析")
        self._ai_btn.setEnabled(True)

        for issue in ai_issues:
            issue['type'] = 'ai'
            self._issues.append(issue)
        self._refresh_ui()

    def _on_ai_failed(self, error: str):
        self._ai_btn.setText("AI 深度分析")
        self._ai_btn.setEnabled(True)
        print(f"AI 连贯性分析失败: {error}")

    # === UI 刷新 ===

    def _refresh_ui(self):
        """刷新问题列表"""
        # 清空
        while self._issues_layout.count() > 1:
            item = self._issues_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # 统计
        conflicts = sum(1 for i in self._issues if i['type'] == 'conflict')
        axis = sum(1 for i in self._issues if i['type'] == 'axis')
        duration = sum(1 for i in self._issues if i['type'] == 'duration')
        ai = sum(1 for i in self._issues if i['type'] == 'ai')
        total = len(self._issues)

        if total == 0:
            self._summary_label.setText("未发现连贯性问题")
            self._summary_label.setStyleSheet(
                f"color: {QColor(80, 200, 120).name()};"
            )
        else:
            parts = []
            if conflicts:
                parts.append(f"运镜冲突 {conflicts}")
            if axis:
                parts.append(f"轴线违背 {axis}")
            if duration:
                parts.append(f"时长异常 {duration}")
            if ai:
                parts.append(f"AI建议 {ai}")
            self._summary_label.setText(
                f"发现 {total} 个问题: " + " | ".join(parts)
            )
            self._summary_label.setStyleSheet(
                f"color: {QColor(255, 180, 0).name()};"
            )

        # 添加问题卡片
        for issue in self._issues:
            card = IssueCard(issue)
            card.setStyleSheet(f"""
                IssueCard {{
                    background: {theme.bg_secondary()};
                    border: 1px solid {theme.border()};
                    border-radius: 8px;
                }}
            """)
            self._issues_layout.insertWidget(
                self._issues_layout.count() - 1, card
            )

    def apply_theme(self):
        self.setStyleSheet(f"background: {theme.bg_primary()};")
        self._analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.accent()};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme.accent_hover()};
            }}
        """)
