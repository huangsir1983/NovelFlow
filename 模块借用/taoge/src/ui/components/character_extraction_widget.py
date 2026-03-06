"""
涛割 - 角色提取组件
分镜分析第一步：从文案中提取角色信息
"""

import re
import json
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QTextEdit, QComboBox,
    QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPixmap

from ui.pixmap_cache import PixmapCache


class CharacterExtractionWorker(QThread):
    """角色提取工作线程"""

    extraction_completed = pyqtSignal(list)  # [{"name": str, "type": str, "appearance": str}]
    extraction_failed = pyqtSignal(str)

    MODE_REGEX = "regex"
    MODE_DEEPSEEK = "deepseek"

    def __init__(self, text: str, mode: str = "regex"):
        super().__init__()
        self.text = text
        self.mode = mode

    def run(self):
        try:
            if self.mode == self.MODE_DEEPSEEK:
                characters = self._extract_by_deepseek(self.text)
                if characters is not None:
                    self.extraction_completed.emit(characters)
                    return
                self.extraction_failed.emit("DeepSeek未返回有效结果，请检查API密钥或尝试快速提取")
            else:
                characters = self._extract_by_regex(self.text)
                self.extraction_completed.emit(characters)
        except Exception as e:
            self.extraction_failed.emit(str(e))

    def _extract_by_deepseek(self, text: str):
        """通过 DeepSeek API 提取角色"""
        from config.settings import SettingsManager
        from config.constants import CHARACTER_EXTRACTION_PROMPT

        settings = SettingsManager().settings
        api_key = settings.api.deepseek_api_key

        if not api_key:
            raise ValueError("未配置DeepSeek API密钥，请在设置中填写")

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=settings.api.deepseek_base_url,
        )

        truncated = text[:3000]
        prompt = CHARACTER_EXTRACTION_PROMPT.format(text=truncated)

        response = client.chat.completions.create(
            model=settings.api.deepseek_model,
            messages=[
                {"role": "system", "content": "你是一个文本分析助手，擅长从文本中提取角色信息。请只返回JSON数组，不要包含其他内容。"},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )

        content = response.choices[0].message.content.strip()

        # 移除可能的 markdown 代码块标记
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        characters = json.loads(content)

        if isinstance(characters, list) and len(characters) > 0:
            result = []
            for char in characters:
                if isinstance(char, dict) and 'name' in char:
                    result.append({
                        'name': char.get('name', ''),
                        'type': char.get('type', 'human'),
                        'appearance': char.get('appearance', ''),
                    })
            return result if result else None

        return None

    def _extract_by_regex(self, text: str) -> List[Dict[str, Any]]:
        """正则匹配提取中文人名"""
        # 常见称呼模式
        patterns = [
            r'(["\u201c])([^"\u201d]{1,6}?)(["\u201d])\s*(?:说|道|问|答|喊|叫|笑)',
            r'(?:^|\n)\s*([^\s\n:：]{1,6})\s*[:：]',
            r'(?:^|\s)([^\s\n]{2,4})(?:走|跑|站|坐|看|说|想|笑|哭|来|去|拿|抱)',
        ]

        names = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    name = match[1] if len(match) > 1 else match[0]
                else:
                    name = match
                name = name.strip()
                if 1 < len(name) <= 6 and not any(c in name for c in '的了在是有不'):
                    names.add(name)

        # 去重后生成结果
        result = []
        for name in sorted(names):
            result.append({
                'name': name,
                'type': 'human',
                'appearance': '',
            })

        return result


class CharacterCard(QFrame):
    """单个角色卡片"""

    removed = pyqtSignal(object)  # self
    changed = pyqtSignal()

    def __init__(self, char_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.char_data = char_data

        self.setObjectName("charCard")
        self.setStyleSheet("""
            QFrame#charCard {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # 参考图区域
        self.ref_image_label = QLabel()
        self.ref_image_label.setFixedSize(48, 48)
        self.ref_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ref_image_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px dashed rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                font-size: 18px;
                color: rgba(255, 255, 255, 0.3);
            }
        """)
        self.ref_image_label.setText("?")
        self.ref_image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ref_image_label.mousePressEvent = lambda e: self._select_reference_image()
        layout.addWidget(self.ref_image_label)

        # 更新参考图预览
        ref = self.char_data.get('reference_image', '')
        if ref:
            self._update_ref_preview(ref)

        # 信息编辑区
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # 名称行
        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        self.name_edit = QLineEdit(self.char_data.get('name', ''))
        self.name_edit.setPlaceholderText("角色名称")
        self.name_edit.textChanged.connect(self._on_name_changed)
        self.name_edit.setStyleSheet(self._get_input_style())
        name_row.addWidget(self.name_edit, 1)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["人物", "动物", "生物", "物体"])
        type_map = {"human": 0, "animal": 1, "creature": 2, "object": 3}
        self.type_combo.setCurrentIndex(type_map.get(self.char_data.get('type', 'human'), 0))
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.type_combo.setStyleSheet(self._get_combo_style())
        self.type_combo.setFixedWidth(70)
        name_row.addWidget(self.type_combo)

        info_layout.addLayout(name_row)

        # 外貌描述
        self.appearance_edit = QLineEdit(self.char_data.get('appearance', ''))
        self.appearance_edit.setPlaceholderText("外貌描述（可选）")
        self.appearance_edit.textChanged.connect(self._on_appearance_changed)
        self.appearance_edit.setStyleSheet(self._get_input_style())
        info_layout.addWidget(self.appearance_edit)

        layout.addLayout(info_layout, 1)

        # 删除按钮
        del_btn = QPushButton("x")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.4);
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: rgb(239, 68, 68);
            }
        """)
        del_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(del_btn, alignment=Qt.AlignmentFlag.AlignTop)

    def _on_name_changed(self, text):
        self.char_data['name'] = text
        self.changed.emit()

    def _on_type_changed(self, index):
        type_values = ["human", "animal", "creature", "object"]
        self.char_data['type'] = type_values[index]
        self.changed.emit()

    def _on_appearance_changed(self, text):
        self.char_data['appearance'] = text
        self.changed.emit()

    def _select_reference_image(self):
        """选择参考图"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择角色参考图", "",
            "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.char_data['reference_image'] = file_path
            self._update_ref_preview(file_path)
            self.changed.emit()

    def _update_ref_preview(self, path: str):
        """更新参考图预览"""
        import os
        if path and os.path.exists(path):
            scaled = PixmapCache.instance().get_scaled(path, 48, 48)
            if scaled:
                self.ref_image_label.setPixmap(scaled)
                self.ref_image_label.setStyleSheet("""
                    QLabel {
                        border-radius: 24px;
                        border: 2px solid rgba(139, 92, 246, 0.5);
                    }
                """)

    def _get_input_style(self):
        return """
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 5px 8px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: rgb(0, 122, 204);
            }
        """

    def _get_combo_style(self):
        return """
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 4px 8px;
                color: white;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid rgba(255, 255, 255, 0.5);
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(45, 45, 48);
                border: 1px solid rgba(255, 255, 255, 0.1);
                selection-background-color: rgb(0, 122, 204);
                color: white;
            }
        """

    def get_data(self) -> Dict[str, Any]:
        return dict(self.char_data)


class CharacterExtractionWidget(QWidget):
    """角色提取组件 - 分镜分析步骤1"""

    characters_changed = pyqtSignal(list)  # 当角色列表变化时发出

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[CharacterExtractionWorker] = None
        self._source_text = ""
        self._cards: List[CharacterCard] = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # 说明
        hint = QLabel("从文案中提取角色信息，也可手动添加或修改")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        layout.addWidget(hint)

        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.deepseek_btn = QPushButton("DeepSeek AI提取")
        self.deepseek_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deepseek_btn.clicked.connect(self._start_deepseek_extraction)
        self.deepseek_btn.setStyleSheet("""
            QPushButton {
                background-color: rgb(0, 122, 204);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgb(0, 140, 220); }
            QPushButton:disabled { background-color: rgba(0, 122, 204, 0.4); }
        """)
        btn_row.addWidget(self.deepseek_btn)

        self.extract_btn = QPushButton("快速提取")
        self.extract_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.extract_btn.clicked.connect(self._start_regex_extraction)
        self.extract_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.12); color: white; }
            QPushButton:disabled { background-color: rgba(255, 255, 255, 0.04); color: rgba(255, 255, 255, 0.3); }
        """)
        btn_row.addWidget(self.extract_btn)

        add_btn = QPushButton("+ 手动添加角色")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_empty_character)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgb(0, 150, 200);
                border: 1px dashed rgba(0, 150, 200, 0.5);
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(0, 150, 200, 0.1); }
        """)
        btn_row.addWidget(add_btn)

        btn_row.addStretch()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 11px;")
        btn_row.addWidget(self.status_label)

        layout.addLayout(btn_row)

        # 角色卡片滚动区
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

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, 1)

    def set_source_text(self, text: str):
        """设置源文案"""
        self._source_text = text

    def _start_deepseek_extraction(self):
        """通过 DeepSeek AI 提取角色"""
        if not self._source_text:
            self.status_label.setText("请先导入文案")
            return

        self.deepseek_btn.setEnabled(False)
        self.extract_btn.setEnabled(False)
        self.status_label.setText("DeepSeek AI 正在分析...")

        self._worker = CharacterExtractionWorker(self._source_text, mode="deepseek")
        self._worker.extraction_completed.connect(self._on_extraction_completed)
        self._worker.extraction_failed.connect(self._on_extraction_failed)
        self._worker.start()

    def _start_regex_extraction(self):
        """通过正则快速提取角色"""
        if not self._source_text:
            self.status_label.setText("请先导入文案")
            return

        self.deepseek_btn.setEnabled(False)
        self.extract_btn.setEnabled(False)
        self.status_label.setText("正在快速提取...")

        self._worker = CharacterExtractionWorker(self._source_text, mode="regex")
        self._worker.extraction_completed.connect(self._on_extraction_completed)
        self._worker.extraction_failed.connect(self._on_extraction_failed)
        self._worker.start()

    def _on_extraction_completed(self, characters: List[Dict[str, Any]]):
        """提取完成"""
        self.deepseek_btn.setEnabled(True)
        self.extract_btn.setEnabled(True)
        self.status_label.setText(f"已提取 {len(characters)} 个角色")

        # 与现有角色去重
        existing_names = {c.char_data.get('name', '') for c in self._cards}
        for char in characters:
            if char.get('name', '') not in existing_names:
                self._add_character_card(char)

        self.characters_changed.emit(self.get_characters())

    def _on_extraction_failed(self, error: str):
        """提取失败"""
        self.deepseek_btn.setEnabled(True)
        self.extract_btn.setEnabled(True)
        self.status_label.setText(f"提取失败: {error}")

    def _add_empty_character(self):
        """手动添加空角色"""
        self._add_character_card({'name': '', 'type': 'human', 'appearance': ''})
        self.characters_changed.emit(self.get_characters())

    def _add_character_card(self, char_data: Dict[str, Any]):
        """添加角色卡片"""
        card = CharacterCard(char_data)
        card.removed.connect(self._remove_card)
        card.changed.connect(lambda: self.characters_changed.emit(self.get_characters()))
        self._cards.append(card)
        # 在 stretch 前插入
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _remove_card(self, card: CharacterCard):
        """移除角色卡片"""
        if card in self._cards:
            self._cards.remove(card)
        card.deleteLater()
        self.characters_changed.emit(self.get_characters())

    def get_characters(self) -> List[Dict[str, Any]]:
        """获取所有角色数据"""
        return [c.get_data() for c in self._cards if c.char_data.get('name')]

    def set_characters(self, characters: List[Dict[str, Any]]):
        """设置角色数据"""
        # 清除现有卡片
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        for char in characters:
            self._add_character_card(char)
