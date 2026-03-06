"""
涛割 - 主题颜色系统
提供深色/浅色两套颜色 token，所有组件通过此模块获取当前主题颜色。
Apple 设计语言：SF Pro、大圆角、柔和层级、不是纯白而是暖灰。
"""

_current_dark = True


def is_dark() -> bool:
    return _current_dark


def set_dark(dark: bool):
    global _current_dark
    _current_dark = dark


# ============================================================
#  颜色 Token 函数 —— 根据当前主题返回对应颜色
# ============================================================

def bg_primary() -> str:
    """主背景"""
    return "#1c1c1e" if _current_dark else "#f2f2f7"


def bg_secondary() -> str:
    """次级背景（卡片、输入框）"""
    return "#2c2c2e" if _current_dark else "#ffffff"


def bg_tertiary() -> str:
    """三级背景（悬停态、分割线区域）"""
    return "#3a3a3c" if _current_dark else "#e5e5ea"


def bg_elevated() -> str:
    """浮动层背景"""
    return "rgba(28, 28, 30, 0.85)" if _current_dark else "rgba(255, 255, 255, 0.88)"


def text_primary() -> str:
    """主文字"""
    return "#f5f5f7" if _current_dark else "#1c1c1e"


def text_secondary() -> str:
    """次级文字"""
    return "#8e8e93" if _current_dark else "#6e6e73"


def text_tertiary() -> str:
    """三级文字 / 占位符"""
    return "#636366" if _current_dark else "#aeaeb2"


def accent() -> str:
    """强调色（蓝色按钮、链接）"""
    return "#0a84ff" if _current_dark else "#007aff"


def accent_hover() -> str:
    return "#409cff" if _current_dark else "#409cff"


def accent_bg() -> str:
    """强调色淡底"""
    return "rgba(10, 132, 255, 0.12)" if _current_dark else "rgba(0, 122, 255, 0.08)"


def success() -> str:
    return "#30d158" if _current_dark else "#34c759"


def danger() -> str:
    return "#ff453a" if _current_dark else "#ff3b30"


def warning_color() -> str:
    return "#ff9f0a" if _current_dark else "#ff9500"


def border() -> str:
    """通用边框"""
    return "rgba(255, 255, 255, 0.06)" if _current_dark else "rgba(0, 0, 0, 0.06)"


def border_hover() -> str:
    return "rgba(255, 255, 255, 0.15)" if _current_dark else "rgba(0, 0, 0, 0.12)"


def separator() -> str:
    """分割线"""
    return "rgba(255, 255, 255, 0.04)" if _current_dark else "rgba(0, 0, 0, 0.04)"


def btn_bg() -> str:
    """普通按钮背景"""
    return "rgba(255, 255, 255, 0.05)" if _current_dark else "rgba(0, 0, 0, 0.03)"


def btn_bg_hover() -> str:
    return "rgba(255, 255, 255, 0.08)" if _current_dark else "rgba(0, 0, 0, 0.06)"


def btn_border() -> str:
    return "rgba(255, 255, 255, 0.06)" if _current_dark else "rgba(0, 0, 0, 0.06)"


def scrollbar_bg() -> str:
    return "rgba(255, 255, 255, 0.02)" if _current_dark else "rgba(0, 0, 0, 0.02)"


def scrollbar_handle() -> str:
    return "rgba(255, 255, 255, 0.15)" if _current_dark else "rgba(0, 0, 0, 0.12)"


def dot_grid_color() -> tuple:
    """点阵网格颜色 (r, g, b, a)"""
    return (255, 255, 255, 8) if _current_dark else (0, 0, 0, 12)


def canvas_bg_rgb() -> tuple:
    """画布深色底 (r, g, b) for QPainter"""
    return (20, 20, 24) if _current_dark else (242, 242, 247)


def canvas_dot_rgba() -> tuple:
    """画布点阵 (r, g, b, a) for QPainter"""
    return (255, 255, 255, 15) if _current_dark else (0, 0, 0, 18)


# ============================================================
#  样式片段工具函数
# ============================================================

def float_panel_style() -> str:
    """浮动面板通用样式"""
    return f"""
        QWidget {{
            background-color: {bg_elevated()};
            border-radius: 12px;
        }}
    """


def float_btn_style() -> str:
    """浮动面板内按钮样式"""
    return f"""
        QPushButton {{
            background-color: {btn_bg()};
            color: {text_secondary()};
            border: 1px solid {btn_border()};
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {btn_bg_hover()};
            color: {text_primary()};
        }}
    """


def scroll_area_style() -> str:
    """滚动区域通用样式"""
    return f"""
        QScrollArea {{ background: transparent; }}
        QScrollBar:vertical {{
            background-color: {scrollbar_bg()}; width: 6px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {scrollbar_handle()}; border-radius: 3px; min-height: 30px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """


def tool_btn_style() -> str:
    """工具栏按钮样式"""
    return f"""
        QPushButton {{
            background-color: {btn_bg()};
            color: {text_secondary()};
            border: 1px solid {btn_border()};
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {btn_bg_hover()};
            color: {text_primary()};
        }}
        QPushButton:checked {{
            background-color: {accent_bg()};
            border-color: rgba(10, 132, 255, 0.3);
            color: {accent()};
        }}
    """
