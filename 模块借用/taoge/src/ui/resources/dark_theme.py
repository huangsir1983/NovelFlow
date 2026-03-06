"""
涛割 - Apple 风格 UI 主题
支持深色 (Dark) 和浅色 (Light) 两套配色
设计语言：SF Pro 字体、大圆角、毛玻璃质感、微妙层级
"""

# ============================================================
#  Apple Dark Theme
# ============================================================
APPLE_DARK_QSS = """

/* ---- 全局 ---- */
QMainWindow, QDialog {
    background-color: #1c1c1e;
    color: #f5f5f7;
}

QWidget {
    color: #f5f5f7;
    font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 10pt;
}

/* ---- 标签 ---- */
QLabel {
    color: #f5f5f7;
    background: transparent;
}

/* ---- 按钮 ---- */
QPushButton {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 7px 16px;
    min-height: 20px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3a3a3c;
}
QPushButton:pressed {
    background-color: #1c1c1e;
}
QPushButton:disabled {
    background-color: #1c1c1e;
    color: #48484a;
}
QPushButton[primary="true"] {
    background-color: #0a84ff;
    border: none;
    color: white;
}
QPushButton[primary="true"]:hover {
    background-color: #409cff;
}
QPushButton[danger="true"] {
    background-color: #ff453a;
    border: none;
    color: white;
}
QPushButton[danger="true"]:hover {
    background-color: #ff6961;
}

/* ---- 输入框 ---- */
QLineEdit {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: rgba(10, 132, 255, 0.4);
}
QLineEdit:focus {
    border-color: #0a84ff;
}

/* ---- 文本编辑 ---- */
QTextEdit, QPlainTextEdit {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 8px;
    selection-background-color: rgba(10, 132, 255, 0.4);
}

/* ---- 下拉框 ---- */
QComboBox {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: rgba(255, 255, 255, 0.15);
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    selection-background-color: #0a84ff;
    outline: none;
}

/* ---- 数值输入 ---- */
QSpinBox, QDoubleSpinBox {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 5px 8px;
}

/* ---- 列表 ---- */
QListWidget {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 8px;
    margin: 2px 4px;
}
QListWidget::item:selected {
    background-color: rgba(10, 132, 255, 0.25);
    color: white;
}
QListWidget::item:hover:!selected {
    background-color: rgba(255, 255, 255, 0.04);
}

/* ---- 滑块 ---- */
QSlider::groove:horizontal {
    height: 4px;
    background: #48484a;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: white;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}
QSlider::sub-page:horizontal {
    background: #0a84ff;
    border-radius: 2px;
}

/* ---- 选项卡 ---- */
QTabWidget::pane {
    background: #1c1c1e;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}
QTabBar::tab {
    background: transparent;
    color: #8e8e93;
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}
QTabBar::tab:selected {
    color: #0a84ff;
    border-bottom-color: #0a84ff;
}
QTabBar::tab:hover:!selected {
    color: #f5f5f7;
}

/* ---- 滚动条 ---- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 0.22);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 4px;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(255, 255, 255, 0.22);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ---- 滚动区域 ---- */
QScrollArea {
    background: transparent;
    border: none;
}

/* ---- 分割器 ---- */
QSplitter::handle {
    background-color: rgba(255, 255, 255, 0.04);
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}
QSplitter::handle:hover {
    background-color: rgba(10, 132, 255, 0.4);
}

/* ---- 分组框 ---- */
QGroupBox {
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #8e8e93;
}

/* ---- 复选框 ---- */
QCheckBox {
    color: #f5f5f7;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #636366;
    border-radius: 5px;
    background: transparent;
}
QCheckBox::indicator:checked {
    background-color: #0a84ff;
    border-color: #0a84ff;
}

/* ---- 单选按钮 ---- */
QRadioButton {
    color: #f5f5f7;
    spacing: 8px;
}
QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #636366;
    border-radius: 9px;
    background: transparent;
}
QRadioButton::indicator:checked {
    background-color: #0a84ff;
    border-color: #0a84ff;
}

/* ---- 进度条 ---- */
QProgressBar {
    background-color: #38383a;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: white;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar::chunk {
    background-color: #0a84ff;
    border-radius: 4px;
}

/* ---- 菜单栏 ---- */
QMenuBar {
    background-color: rgba(28, 28, 30, 0.85);
    color: #f5f5f7;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
QMenuBar::item {
    padding: 6px 12px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background-color: rgba(255, 255, 255, 0.08);
}

/* ---- 菜单 ---- */
QMenu {
    background-color: #2c2c2e;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 24px 8px 12px;
    border-radius: 6px;
    color: #f5f5f7;
}
QMenu::item:selected {
    background-color: #0a84ff;
    color: white;
}
QMenu::separator {
    height: 1px;
    background: rgba(255, 255, 255, 0.06);
    margin: 4px 8px;
}

/* ---- 工具栏 ---- */
QToolBar {
    background-color: #1c1c1e;
    border: none;
    spacing: 2px;
    padding: 4px;
}
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px;
    color: #f5f5f7;
}
QToolButton:hover {
    background-color: rgba(255, 255, 255, 0.06);
}

/* ---- 状态栏 ---- */
QStatusBar {
    background-color: #1c1c1e;
    color: #8e8e93;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
}

/* ---- 提示框 ---- */
QToolTip {
    background-color: #3a3a3c;
    color: #f5f5f7;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px 10px;
}

/* ---- 表格 ---- */
QTableWidget, QTableView {
    background-color: #2c2c2e;
    color: #f5f5f7;
    gridline-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    outline: none;
}
QTableWidget::item, QTableView::item {
    padding: 6px;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: rgba(10, 132, 255, 0.25);
}
QHeaderView::section {
    background-color: #2c2c2e;
    color: #8e8e93;
    padding: 8px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    font-weight: 600;
}

"""


# ============================================================
#  Apple Light Theme
# ============================================================
APPLE_LIGHT_QSS = """

/* ---- 全局 ---- */
QMainWindow, QDialog {
    background-color: #f2f2f7;
    color: #1c1c1e;
}

QWidget {
    color: #1c1c1e;
    font-family: "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 10pt;
}

/* ---- 标签 ---- */
QLabel {
    color: #1c1c1e;
    background: transparent;
}

/* ---- 按钮 ---- */
QPushButton {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 8px;
    padding: 7px 16px;
    min-height: 20px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #f2f2f7;
}
QPushButton:pressed {
    background-color: #e5e5ea;
}
QPushButton:disabled {
    background-color: #f2f2f7;
    color: #c7c7cc;
}
QPushButton[primary="true"] {
    background-color: #007aff;
    border: none;
    color: white;
}
QPushButton[primary="true"]:hover {
    background-color: #409cff;
}
QPushButton[danger="true"] {
    background-color: #ff3b30;
    border: none;
    color: white;
}

/* ---- 输入框 ---- */
QLineEdit {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: rgba(0, 122, 255, 0.25);
}
QLineEdit:focus {
    border-color: #007aff;
}

/* ---- 文本编辑 ---- */
QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 10px;
    padding: 8px;
}

/* ---- 下拉框 ---- */
QComboBox {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 8px;
    padding: 6px 10px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 10px;
    selection-background-color: #007aff;
    selection-color: white;
    outline: none;
}

/* ---- 数值输入 ---- */
QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 8px;
    padding: 5px 8px;
}

/* ---- 列表 ---- */
QListWidget {
    background-color: #ffffff;
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 12px;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 8px;
    margin: 2px 4px;
}
QListWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.12);
    color: #007aff;
}
QListWidget::item:hover:!selected {
    background-color: rgba(0, 0, 0, 0.03);
}

/* ---- 滑块 ---- */
QSlider::groove:horizontal {
    height: 4px;
    background: #d1d1d6;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: white;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
    border: 1px solid rgba(0, 0, 0, 0.08);
}
QSlider::sub-page:horizontal {
    background: #007aff;
    border-radius: 2px;
}

/* ---- 选项卡 ---- */
QTabWidget::pane {
    background: #ffffff;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 12px;
}
QTabBar::tab {
    background: transparent;
    color: #8e8e93;
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}
QTabBar::tab:selected {
    color: #007aff;
    border-bottom-color: #007aff;
}
QTabBar::tab:hover:!selected {
    color: #1c1c1e;
}

/* ---- 滚动条 ---- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 0.12);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(0, 0, 0, 0.2);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 4px;
}
QScrollBar::handle:horizontal {
    background: rgba(0, 0, 0, 0.12);
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ---- 滚动区域 ---- */
QScrollArea {
    background: transparent;
    border: none;
}

/* ---- 分割器 ---- */
QSplitter::handle {
    background-color: rgba(0, 0, 0, 0.04);
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}
QSplitter::handle:hover {
    background-color: rgba(0, 122, 255, 0.3);
}

/* ---- 分组框 ---- */
QGroupBox {
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 12px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #8e8e93;
}

/* ---- 复选框 ---- */
QCheckBox {
    color: #1c1c1e;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #c7c7cc;
    border-radius: 5px;
    background: transparent;
}
QCheckBox::indicator:checked {
    background-color: #007aff;
    border-color: #007aff;
}

/* ---- 单选按钮 ---- */
QRadioButton {
    color: #1c1c1e;
    spacing: 8px;
}
QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #c7c7cc;
    border-radius: 9px;
    background: transparent;
}
QRadioButton::indicator:checked {
    background-color: #007aff;
    border-color: #007aff;
}

/* ---- 进度条 ---- */
QProgressBar {
    background-color: #e5e5ea;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #1c1c1e;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar::chunk {
    background-color: #007aff;
    border-radius: 4px;
}

/* ---- 菜单栏 ---- */
QMenuBar {
    background-color: rgba(255, 255, 255, 0.85);
    color: #1c1c1e;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
QMenuBar::item {
    padding: 6px 12px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background-color: rgba(0, 0, 0, 0.05);
}

/* ---- 菜单 ---- */
QMenu {
    background-color: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    padding: 8px 24px 8px 12px;
    border-radius: 6px;
    color: #1c1c1e;
}
QMenu::item:selected {
    background-color: #007aff;
    color: white;
}
QMenu::separator {
    height: 1px;
    background: rgba(0, 0, 0, 0.06);
    margin: 4px 8px;
}

/* ---- 状态栏 ---- */
QStatusBar {
    background-color: #f2f2f7;
    color: #8e8e93;
    border-top: 1px solid rgba(0, 0, 0, 0.04);
}

/* ---- 提示框 ---- */
QToolTip {
    background-color: rgba(255, 255, 255, 0.95);
    color: #1c1c1e;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 8px;
    padding: 6px 10px;
}

/* ---- 表格 ---- */
QTableWidget, QTableView {
    background-color: #ffffff;
    color: #1c1c1e;
    gridline-color: rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 12px;
    outline: none;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: rgba(0, 122, 255, 0.12);
}
QHeaderView::section {
    background-color: #f2f2f7;
    color: #8e8e93;
    padding: 8px;
    border: none;
    border-bottom: 1px solid rgba(0, 0, 0, 0.04);
    font-weight: 600;
}

"""

# ============================================================
#  保留旧名称的兼容别名（默认使用深色）
# ============================================================
DARK_THEME_QSS = APPLE_DARK_QSS


def get_theme_qss(theme_name: str) -> str:
    """根据主题名返回对应 QSS，支持 'dark' 和 'light'"""
    if theme_name == "light":
        return APPLE_LIGHT_QSS
    return APPLE_DARK_QSS


def is_dark_theme(theme_name: str) -> bool:
    """判断是否为深色主题"""
    return theme_name != "light"

# ============================================================
#  组件级样式 token
# ============================================================
SIDEBAR_STYLE = """
QWidget#sidebar {
    background-color: #1c1c1e;
}
"""

CARD_STYLE = """
QFrame#card {
    background-color: #2c2c2e;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 0;
}
QFrame#card:hover {
    border-color: rgba(10, 132, 255, 0.4);
}
"""

TAG_STYLE = """
QLabel#tag {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
}
"""
