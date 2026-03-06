"""
涛割 - 智能PS预处理管线节点
视角转换 / 改表情动作 / AI抠图 / 高清化 四种管线阶段节点。
每个节点有：左输入锚点 + 预览图区域(按比例) + 操作按钮 + 嵌入控件区 + 预览结果面板 + 右输出锚点

v2.6.1 交互重构:
  - 预览区域跟随图片宽高比，操作按钮在图片下方
  - ViewAngleNode: 3个下拉框+3D画布嵌入节点下方（无弹窗）
  - ExpressionNode: QLineEdit+生成按钮嵌入节点下方（无弹窗）
  - AIMattingNode: 进度文字+预览面板+确认回调
  - HDUpscaleNode: 按钮下移，预留
"""

import os
import tempfile
import time
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsItem, QGraphicsProxyWidget,
    QPushButton, QWidget, QHBoxLayout, QVBoxLayout, QLineEdit,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPixmap, QLinearGradient,
)

from ui import theme


# ============================================================
#  常量
# ============================================================

STAGE_WIDTH = 320
BASE_PREVIEW_H = 90
PANEL_H = 36
CORNER_R = 10
ANCHOR_R = 5

COLOR_ACCENT = QColor(91, 127, 255)
COLOR_STAGE_BG = QColor(32, 32, 44, 220)
COLOR_STAGE_BG_LIGHT = QColor(245, 245, 252, 230)
COLOR_CONFIRMED = QColor(50, 180, 100)
COLOR_PENDING = QColor(160, 160, 175)
COLOR_LOADING = QColor(255, 180, 0)


# ============================================================
#  _get_api_config — 统一获取 API 配置
# ============================================================

def _get_api_config() -> dict:
    """获取 RunningHub + Geek API 配置"""
    try:
        from config.settings import SettingsManager
        api_cfg = SettingsManager().settings.api
        return {
            'runninghub_api_key': api_cfg.runninghub_api_key,
            'runninghub_base_url': api_cfg.runninghub_base_url,
            'runninghub_instance_type': api_cfg.runninghub_instance_type,
            'geek_api_key': api_cfg.geek_api_key,
            'geek_base_url': api_cfg.geek_base_url,
        }
    except Exception:
        return {}


def _save_pixmap_to_temp(pixmap: QPixmap) -> str:
    """将 QPixmap 保存为临时 PNG 文件，返回路径"""
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False, prefix='ps_stage_')
    tmp_path = tmp.name
    tmp.close()
    pixmap.save(tmp_path, 'PNG')
    return tmp_path


# ============================================================
#  PipelineStageNode — 管线阶段节点基类
#  动态高度 = 22(标题) + _preview_h(按图片比例) + PANEL_H(按钮)
#              + _controls_h(嵌入控件) + _preview_panel_h(预览结果)
# ============================================================

class PipelineStageNode(QGraphicsRectItem):
    """
    管线阶段节点基类。
    布局（从上到下）:
      - 颜色条 3px + 名称 18px  (合计22px)
      - 预览图 (_preview_h, 按图片宽高比动态)
      - 操作按钮 (PANEL_H = 36px)
      - 嵌入控件区 (_controls_h, 子类定义, 基类默认0)
      - 预览结果面板 (_preview_panel_h, 确认后显示, 默认0)
    左侧：输入锚点
    右侧：输出锚点
    """

    STAGE_NAME = "基础节点"
    STAGE_COLOR = COLOR_ACCENT

    def __init__(self, parent=None,
                 on_output_ready: Optional[Callable] = None):
        super().__init__(parent)

        self._input_pixmap: Optional[QPixmap] = None
        self._output_pixmap: Optional[QPixmap] = None
        self._preview_result_pixmap: Optional[QPixmap] = None
        self._is_loading = False
        self._is_confirmed = False
        self._on_output_ready = on_output_ready

        # 动态高度
        self._preview_h: int = BASE_PREVIEW_H
        self._controls_h: int = 0        # 子类覆盖
        self._preview_panel_h: int = 0   # show_preview_panel 时设置

        # 操作按钮 hover
        self._btn_hovered = False
        self._btn_text = "生成"

        # 预览面板确认按钮 hover
        self._confirm_btn_hovered = False

        # 重置按钮 hover
        self._reset_btn_hovered = False

        # 进度文字（AI抠图等用）
        self._progress_text = ""

        # Worker 引用（防止 GC）
        self._worker: Optional[QThread] = None

        # 嵌入控件 proxy
        self._controls_proxy: Optional[QGraphicsProxyWidget] = None

        self._update_rect()
        self.setAcceptHoverEvents(True)

    def _get_total_height(self) -> int:
        return 22 + self._preview_h + PANEL_H + self._controls_h + self._preview_panel_h

    def _update_rect(self):
        total_h = self._get_total_height()
        self.setRect(0, 0, STAGE_WIDTH, total_h)

    def set_input_image(self, pixmap: QPixmap):
        """接收上游输出图片 — 根据比例调整预览高度"""
        self._input_pixmap = pixmap
        self._output_pixmap = None
        self._preview_result_pixmap = None
        self._is_confirmed = False
        self._preview_panel_h = 0

        # 根据图片宽高比计算预览区高度
        if pixmap and not pixmap.isNull():
            preview_w = STAGE_WIDTH - 16  # 左右各8px padding
            aspect = pixmap.width() / max(pixmap.height(), 1)
            self._preview_h = int(preview_w / aspect)
            self._preview_h = max(60, min(200, self._preview_h))
        else:
            self._preview_h = BASE_PREVIEW_H

        self._update_rect()
        self._reposition_controls()
        self.update()

    def get_output_image(self) -> Optional[QPixmap]:
        """获取处理后的输出（仅确认后有效）"""
        if self._is_confirmed and self._output_pixmap:
            return self._output_pixmap
        return None

    def set_loading(self, loading: bool):
        self._is_loading = loading
        self.update()

    def confirm_result(self):
        """确认处理结果，替换输出"""
        if self._output_pixmap:
            self._is_confirmed = True
            self._input_pixmap = self._output_pixmap  # 确认后替换预览为输出图
            if self._on_output_ready:
                self._on_output_ready(self._output_pixmap)
            self.update()

    def set_result(self, pixmap: QPixmap):
        """设置处理结果（生成完成后调用）"""
        self._output_pixmap = pixmap
        self._is_loading = False
        self._btn_text = "确认"
        self.update()

    # --- 预览面板 ---

    def show_preview_panel(self, pixmap: QPixmap):
        """显示预览结果面板（缩略图 + 确认按钮）"""
        self._preview_result_pixmap = pixmap
        self._preview_panel_h = 140  # 预览缩略图100 + 按钮区40
        self._update_rect()
        self.update()

    def hide_preview_panel(self):
        self._preview_result_pixmap = None
        self._preview_panel_h = 0
        self._update_rect()
        self.update()

    # --- 坐标计算 ---

    def _get_controls_y(self) -> float:
        """嵌入控件区域的起始 y 坐标"""
        return 22 + self._preview_h + PANEL_H

    def _get_preview_panel_y(self) -> float:
        """预览面板的起始 y 坐标"""
        return self._get_controls_y() + self._controls_h

    def _reposition_controls(self):
        """重新定位嵌入控件 proxy"""
        if self._controls_proxy:
            self._controls_proxy.setPos(4, self._get_controls_y())

    # --- 锚点 ---

    def get_input_anchor_pos(self) -> QPointF:
        """左侧输入锚点的场景坐标"""
        total_h = self.rect().height()
        local = QPointF(-ANCHOR_R - 2, total_h / 2)
        return self.mapToScene(local)

    def get_output_anchor_pos(self) -> QPointF:
        """右侧输出锚点的场景坐标"""
        total_h = self.rect().height()
        local = QPointF(STAGE_WIDTH + ANCHOR_R + 2, total_h / 2)
        return self.mapToScene(local)

    def _on_action_clicked(self):
        """子类重写：点击操作按钮的行为"""
        if self._output_pixmap and not self._is_confirmed:
            self.confirm_result()

    # === 绘制 ===

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        dark = theme.is_dark()
        total_h = rect.height()

        # 背景
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, CORNER_R, CORNER_R)
        bg = COLOR_STAGE_BG if dark else COLOR_STAGE_BG_LIGHT
        painter.fillPath(bg_path, QBrush(bg))

        # 顶部颜色条
        color_bar = QRectF(rect.x(), rect.y(), rect.width(), 3)
        bar_color = COLOR_CONFIRMED if self._is_confirmed else self.STAGE_COLOR
        if self._is_loading:
            bar_color = COLOR_LOADING
        painter.fillRect(color_bar, bar_color)

        # 节点名称
        name_rect = QRectF(rect.x(), rect.y() + 3, rect.width(), 18)
        painter.setPen(QPen(QColor(180, 190, 210) if dark else QColor(70, 70, 90)))
        painter.setFont(QFont("Microsoft YaHei", 7, QFont.Weight.Bold))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter, self.STAGE_NAME)

        # 预览图区域
        preview_rect = QRectF(rect.x() + 8, rect.y() + 22,
                              rect.width() - 16, self._preview_h)

        # 显示输出或输入图
        display_pixmap = self._output_pixmap if self._output_pixmap else self._input_pixmap

        if display_pixmap and not display_pixmap.isNull():
            clip = QPainterPath()
            clip.addRoundedRect(preview_rect, 6, 6)
            painter.setClipPath(clip)
            scaled = display_pixmap.scaled(
                int(preview_rect.width()), int(preview_rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            sx = (scaled.width() - preview_rect.width()) / 2
            sy = (scaled.height() - preview_rect.height()) / 2
            painter.drawPixmap(
                preview_rect.toRect(), scaled,
                QRectF(sx, sy, preview_rect.width(), preview_rect.height()).toRect())
            painter.setClipping(False)

            # 已确认标记
            if self._is_confirmed:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(50, 180, 100, 140)))
                check_rect = QRectF(preview_rect.right() - 22,
                                    preview_rect.top() + 4, 18, 18)
                painter.drawEllipse(check_rect)
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                cx = check_rect.center().x()
                cy = check_rect.center().y()
                painter.drawLine(QPointF(cx - 4, cy), QPointF(cx - 1, cy + 3))
                painter.drawLine(QPointF(cx - 1, cy + 3), QPointF(cx + 4, cy - 3))

        elif self._is_loading:
            painter.fillRect(preview_rect, QColor(40, 40, 50, 100))
            painter.setPen(QPen(QColor(200, 200, 210)))
            painter.setFont(QFont("Microsoft YaHei", 9))
            loading_text = self._progress_text if self._progress_text else "处理中..."
            painter.drawText(preview_rect, Qt.AlignmentFlag.AlignCenter, loading_text)
        else:
            pen = QPen(QColor(80, 80, 100) if dark else QColor(180, 180, 200), 1)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(preview_rect, 6, 6)
            painter.setPen(QPen(QColor(120, 120, 140) if dark else QColor(150, 150, 170)))
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(preview_rect, Qt.AlignmentFlag.AlignCenter, "等待输入")

        # 操作面板（预览图下方）— 操作按钮 + 重置按钮
        btn_y = 22 + self._preview_h + 4
        reset_w = 52
        btn_gap = 4
        action_w = rect.width() - 24 - btn_gap - reset_w
        btn_rect = QRectF(rect.x() + 12, btn_y, action_w, PANEL_H - 8)
        self._action_btn_rect = btn_rect

        btn_bg = self.STAGE_COLOR if not self._btn_hovered \
            else self.STAGE_COLOR.lighter(120)
        if self._is_confirmed:
            btn_bg = COLOR_CONFIRMED if not self._btn_hovered \
                else COLOR_CONFIRMED.lighter(120)
        if self._is_loading:
            btn_bg = QColor(100, 100, 110)

        btn_path = QPainterPath()
        btn_path.addRoundedRect(btn_rect, 5, 5)
        painter.fillPath(btn_path, QBrush(btn_bg))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei", 8))

        btn_label = self._btn_text
        if self._is_loading:
            btn_label = self._progress_text if self._progress_text else "处理中..."
        elif self._is_confirmed:
            btn_label = "已确认"
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, btn_label)

        # 重置按钮（操作按钮右侧）
        reset_rect = QRectF(btn_rect.right() + btn_gap, btn_y,
                            reset_w, PANEL_H - 8)
        self._reset_btn_rect = reset_rect
        has_reset_state = (self._output_pixmap is not None or self._is_confirmed)
        if has_reset_state:
            rst_bg = QColor(140, 70, 70) if self._reset_btn_hovered \
                else QColor(100, 60, 60)
        else:
            rst_bg = QColor(60, 60, 70)
        rst_path = QPainterPath()
        rst_path.addRoundedRect(reset_rect, 5, 5)
        painter.fillPath(rst_path, QBrush(rst_bg))
        painter.setPen(QPen(QColor(220, 200, 200) if has_reset_state
                            else QColor(100, 100, 120)))
        painter.setFont(QFont("Microsoft YaHei", 7))
        painter.drawText(reset_rect, Qt.AlignmentFlag.AlignCenter, "重置")

        # 预览结果面板（如果有）
        if self._preview_result_pixmap and self._preview_panel_h > 0:
            self._paint_preview_panel(painter, dark)

        # 左侧输入锚点
        in_cx = -ANCHOR_R - 2
        in_cy = total_h / 2
        painter.setPen(QPen(QColor(150, 160, 180) if dark else QColor(100, 110, 130), 1.5))
        painter.setBrush(QBrush(QColor(60, 60, 80) if dark else QColor(220, 220, 235)))
        painter.drawEllipse(QPointF(in_cx, in_cy), ANCHOR_R, ANCHOR_R)

        # 右侧输出锚点
        out_cx = STAGE_WIDTH + ANCHOR_R + 2
        out_cy = total_h / 2
        out_color = COLOR_CONFIRMED if self._is_confirmed else self.STAGE_COLOR
        painter.setPen(QPen(out_color, 1.5))
        painter.setBrush(QBrush(out_color.lighter(140)))
        painter.drawEllipse(QPointF(out_cx, out_cy), ANCHOR_R, ANCHOR_R)

        # 外边框
        border_c = QColor(60, 60, 80, 80) if dark else QColor(180, 180, 200, 80)
        painter.setPen(QPen(border_c, 0.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(bg_path)

    def _paint_preview_panel(self, painter: QPainter, dark: bool):
        """绘制预览结果面板 — 缩略图 + 确认/取消按钮"""
        panel_y = self._get_preview_panel_y()
        panel_w = STAGE_WIDTH - 8
        panel_x = 4

        # 分隔线
        painter.setPen(QPen(QColor(80, 80, 100, 120), 1))
        painter.drawLine(QPointF(panel_x, panel_y),
                         QPointF(panel_x + panel_w, panel_y))

        # 小标题
        painter.setPen(QPen(QColor(160, 170, 190) if dark else QColor(80, 80, 100)))
        painter.setFont(QFont("Microsoft YaHei", 7))
        painter.drawText(QRectF(panel_x + 4, panel_y + 2, panel_w, 16),
                         Qt.AlignmentFlag.AlignVCenter, "预览结果")

        # 缩略图
        thumb_rect = QRectF(panel_x + 4, panel_y + 20,
                            panel_w - 8, 80)
        if self._preview_result_pixmap and not self._preview_result_pixmap.isNull():
            clip = QPainterPath()
            clip.addRoundedRect(thumb_rect, 4, 4)
            painter.setClipPath(clip)
            scaled = self._preview_result_pixmap.scaled(
                int(thumb_rect.width()), int(thumb_rect.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            tx = thumb_rect.x() + (thumb_rect.width() - scaled.width()) / 2
            ty = thumb_rect.y() + (thumb_rect.height() - scaled.height()) / 2
            painter.drawPixmap(int(tx), int(ty), scaled)
            painter.setClipping(False)

        # 确认按钮
        confirm_rect = QRectF(panel_x + 8, panel_y + 104,
                              panel_w / 2 - 12, 28)
        self._confirm_btn_rect = confirm_rect
        c_bg = COLOR_CONFIRMED.lighter(120) if self._confirm_btn_hovered \
            else COLOR_CONFIRMED
        c_path = QPainterPath()
        c_path.addRoundedRect(confirm_rect, 5, 5)
        painter.fillPath(c_path, QBrush(c_bg))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei", 8, QFont.Weight.Bold))
        painter.drawText(confirm_rect, Qt.AlignmentFlag.AlignCenter, "确认")

        # 取消按钮
        cancel_rect = QRectF(panel_x + panel_w / 2 + 4, panel_y + 104,
                             panel_w / 2 - 12, 28)
        self._cancel_btn_rect = cancel_rect
        cancel_path = QPainterPath()
        cancel_path.addRoundedRect(cancel_rect, 5, 5)
        painter.fillPath(cancel_path, QBrush(QColor(80, 80, 100)))
        painter.setPen(QPen(QColor(200, 200, 210)))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(cancel_rect, Qt.AlignmentFlag.AlignCenter, "取消")

    # === 事件 ===

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()

            # 预览面板按钮
            if self._preview_panel_h > 0 and self._preview_result_pixmap:
                if hasattr(self, '_confirm_btn_rect') and self._confirm_btn_rect.contains(pos):
                    self._on_preview_confirm()
                    event.accept()
                    return
                if hasattr(self, '_cancel_btn_rect') and self._cancel_btn_rect.contains(pos):
                    self._on_preview_cancel()
                    event.accept()
                    return

            # 操作按钮
            if hasattr(self, '_action_btn_rect') and self._action_btn_rect.contains(pos):
                if not self._is_loading:
                    self._on_action_clicked()
                event.accept()
                return

            # 重置按钮
            if hasattr(self, '_reset_btn_rect') and self._reset_btn_rect.contains(pos):
                self._reset_node()
                event.accept()
                return
        super().mousePressEvent(event)

    def _on_preview_confirm(self):
        """预览面板确认"""
        self.confirm_result()
        self.hide_preview_panel()

    def _on_preview_cancel(self):
        """预览面板取消"""
        self._output_pixmap = None
        self._btn_text = self._get_default_btn_text()
        self.hide_preview_panel()

    def _reset_node(self):
        """重置节点状态（清除输出，恢复默认）"""
        if not self._output_pixmap and not self._is_confirmed:
            return
        self._output_pixmap = None
        self._preview_result_pixmap = None
        self._is_confirmed = False
        self._preview_panel_h = 0
        self._progress_text = ""
        self._btn_text = self._get_default_btn_text()
        self._on_reset()
        self._update_rect()
        self._reposition_controls()
        self.update()

    def _on_reset(self):
        """子类覆盖：重置时的额外操作"""
        pass

    def _get_default_btn_text(self) -> str:
        """子类覆盖：默认按钮文字"""
        return "生成"

    # === 状态持久化 ===

    def get_state(self) -> dict:
        """导出节点状态用于持久化。子类可覆盖以添加额外字段。"""
        state = {
            'confirmed': self._is_confirmed,
            'output_image': '',
            'btn_text': self._btn_text,
        }
        # 无论是否 confirmed，只要有输出图就保存到持久路径
        if self._output_pixmap and not self._output_pixmap.isNull():
            state['output_image'] = self._save_output_to_persistent()
        return state

    def restore_state(self, state: dict):
        """从持久化数据恢复节点状态。子类可覆盖以恢复额外字段。"""
        if not state:
            return
        output_path = state.get('output_image', '')
        was_confirmed = state.get('confirmed', False)
        btn_text = state.get('btn_text', '')

        if output_path and os.path.isfile(output_path):
            px = QPixmap(output_path)
            if not px.isNull():
                self._output_pixmap = px
                if was_confirmed:
                    self._is_confirmed = True
                    self._input_pixmap = px
                    self._btn_text = "已确认"
                else:
                    # 有输出但未确认 → 显示"确认"按钮
                    self._btn_text = btn_text if btn_text else "确认"
                self.update()
                return

        # 没有输出图但有其他状态 → 恢复按钮文字
        if btn_text and btn_text != self._btn_text:
            self._btn_text = btn_text
            self.update()

    def _save_output_to_persistent(self) -> str:
        """将输出 pixmap 保存到持久路径（使用绝对路径）"""
        if not self._output_pixmap or self._output_pixmap.isNull():
            return ''
        save_dir = os.path.join(os.getcwd(), 'generated', 'pipeline')
        os.makedirs(save_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        # 使用英文名避免潜在编码问题
        stage_key = self.STAGE_NAME.replace(' ', '_')
        filename = f'{stage_key}_{timestamp}.png'
        save_path = os.path.join(save_dir, filename)
        self._output_pixmap.save(save_path, 'PNG')
        return save_path

    def hoverMoveEvent(self, event):
        pos = event.pos()
        old_btn = self._btn_hovered
        old_confirm = self._confirm_btn_hovered
        self._btn_hovered = (hasattr(self, '_action_btn_rect')
                             and self._action_btn_rect.contains(pos))
        self._confirm_btn_hovered = (hasattr(self, '_confirm_btn_rect')
                                     and self._preview_panel_h > 0
                                     and self._confirm_btn_rect.contains(pos))
        old_reset = self._reset_btn_hovered
        self._reset_btn_hovered = (hasattr(self, '_reset_btn_rect')
                                   and self._reset_btn_rect.contains(pos))
        if (old_btn != self._btn_hovered or old_confirm != self._confirm_btn_hovered
                or old_reset != self._reset_btn_hovered):
            self.update()

    def hoverLeaveEvent(self, event):
        self._btn_hovered = False
        self._confirm_btn_hovered = False
        self._reset_btn_hovered = False
        self.update()


# ============================================================
#  ViewAngleNode — 视角转换节点
#  嵌入3个下拉框 + 生成按钮（无弹窗）
# ============================================================

class ViewAngleNode(PipelineStageNode):
    """视角转换：嵌入 3D 视角控制画布 → RunningHub API"""

    STAGE_NAME = "视角转换"
    STAGE_COLOR = QColor(100, 140, 255)

    # AngleControlCanvas 原始 320x360，缩放适配节点宽度
    _CANVAS_ORIG_W = 320
    _CANVAS_ORIG_H = 360
    _CANVAS_SCALE = (STAGE_WIDTH - 8) / 320  # ≈0.6

    def __init__(self, parent=None, on_output_ready=None):
        super().__init__(parent, on_output_ready)
        self._btn_text = "生成视角转换"
        # 缩放后的画布高度 + 生成按钮行(30) + 间距
        scaled_h = int(self._CANVAS_ORIG_H * self._CANVAS_SCALE)
        self._controls_h = scaled_h + 38
        self._update_rect()

        # 控件引用
        self._angle_canvas = None    # AngleControlCanvas
        self._angle_proxy = None     # 3D 画布的 proxy
        self._gen_btn = None
        self._gen_proxy = None       # 生成按钮的 proxy

        QTimer.singleShot(0, self._embed_controls)

    def _get_default_btn_text(self) -> str:
        return "生成视角转换"

    def _embed_controls(self):
        """延迟创建嵌入控件"""
        if not self.scene():
            QTimer.singleShot(50, self._embed_controls)
            return

        try:
            from ui.components.view_angle_widget import AngleControlCanvas
        except ImportError:
            return

        ctrl_x = 4
        ctrl_y = self._get_controls_y()

        # 1) 3D 视角控制画布 — 原始 320x360 缩放嵌入
        self._angle_canvas = AngleControlCanvas()
        if self._input_pixmap and not self._input_pixmap.isNull():
            self._angle_canvas.set_image(self._input_pixmap)

        self._angle_proxy = QGraphicsProxyWidget(self)
        self._angle_proxy.setWidget(self._angle_canvas)
        self._angle_proxy.setScale(self._CANVAS_SCALE)
        self._angle_proxy.setPos(ctrl_x, ctrl_y)

        # 2) 生成按钮（独立 proxy，在 3D 画布下方）
        scaled_canvas_h = int(self._CANVAS_ORIG_H * self._CANVAS_SCALE)
        btn_widget = QPushButton("生成")
        btn_widget.setFont(QFont("Microsoft YaHei", 9))
        btn_widget.setFixedSize(STAGE_WIDTH - 16, 28)
        btn_widget.setStyleSheet(
            "QPushButton { background: #5b7fff; color: white; border-radius: 4px; }"
            "QPushButton:hover { background: #4a6eee; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )
        btn_widget.clicked.connect(self._start_view_angle_convert)
        self._gen_btn = btn_widget

        self._gen_proxy = QGraphicsProxyWidget(self)
        self._gen_proxy.setWidget(btn_widget)
        self._gen_proxy.setPos(8, ctrl_y + scaled_canvas_h + 4)

    def set_input_image(self, pixmap: QPixmap):
        """覆写：输入图更新时同步到 3D 画布"""
        super().set_input_image(pixmap)
        if self._angle_canvas and pixmap and not pixmap.isNull():
            self._angle_canvas.set_image(pixmap)

    def _on_reset(self):
        """重置 3D 画布角度到默认值"""
        if self._angle_canvas:
            self._angle_canvas.set_azimuth(0.0)
            self._angle_canvas.set_elevation(0.0)
            self._angle_canvas.set_distance(5.0)
        if self._gen_btn:
            self._gen_btn.setEnabled(True)

    def _reposition_controls(self):
        """覆写：控件区域位置更新"""
        ctrl_y = self._get_controls_y()
        if self._angle_proxy:
            self._angle_proxy.setPos(4, ctrl_y)
        if self._gen_proxy:
            scaled_canvas_h = int(self._CANVAS_ORIG_H * self._CANVAS_SCALE)
            self._gen_proxy.setPos(8, ctrl_y + scaled_canvas_h + 4)

    def _on_action_clicked(self):
        """操作按钮 — 有预览结果时确认，否则触发生成"""
        if self._preview_result_pixmap:
            self._on_preview_confirm()
        elif self._output_pixmap and not self._is_confirmed:
            self.confirm_result()
        elif self._input_pixmap and not self._is_loading:
            self._start_view_angle_convert()

    # --- 状态持久化覆盖 ---

    def get_state(self) -> dict:
        state = super().get_state()
        # 额外保存 3D 角度参数
        if self._angle_canvas:
            state['azimuth'] = getattr(self._angle_canvas, 'azimuth', 0.0)
            state['elevation'] = getattr(self._angle_canvas, 'elevation', 0.0)
            state['distance'] = getattr(self._angle_canvas, 'distance', 5.0)
        return state

    def restore_state(self, state: dict):
        if not state:
            return
        super().restore_state(state)
        # 恢复 3D 角度参数
        az = state.get('azimuth', 0.0)
        el = state.get('elevation', 0.0)
        dist = state.get('distance', 5.0)
        if self._angle_canvas:
            self._restore_angle_params(az, el, dist)
        else:
            # 控件尚未创建，延迟恢复
            QTimer.singleShot(200, lambda: self._restore_angle_params(az, el, dist))

    def _restore_angle_params(self, az: float, el: float, dist: float):
        """恢复 3D 角度参数到画布控件"""
        if not self._angle_canvas:
            return
        if hasattr(self._angle_canvas, 'set_azimuth'):
            self._angle_canvas.set_azimuth(az)
        if hasattr(self._angle_canvas, 'set_elevation'):
            self._angle_canvas.set_elevation(el)
        if hasattr(self._angle_canvas, 'set_distance'):
            self._angle_canvas.set_distance(dist)

    def _start_view_angle_convert(self):
        """从 3D 画布读取角度 → angle_to_prompt → ViewAngleConvertWorker"""
        if not self._input_pixmap or self._is_loading:
            return

        try:
            from services.view_angle_service import (
                angle_to_prompt, ViewAngleConvertWorker,
            )
        except ImportError:
            print("[涛割] ViewAngleNode: 缺少 view_angle_service 模块")
            return

        cfg = _get_api_config()
        api_key = cfg.get('runninghub_api_key', '')
        base_url = cfg.get('runninghub_base_url', '')
        instance_type = cfg.get('runninghub_instance_type', 'default')

        if not api_key:
            print("[涛割] ViewAngleNode: 未配置 RunningHub API Key")
            return

        # 从 3D 画布读取角度值
        az = self._angle_canvas.azimuth if self._angle_canvas else 0.0
        el = self._angle_canvas.elevation if self._angle_canvas else 0.0
        dist = self._angle_canvas.distance if self._angle_canvas else 5.0

        prompt = angle_to_prompt(az, el, dist)

        src_path = _save_pixmap_to_temp(self._input_pixmap)
        save_dir = os.path.join('generated', 'view_angle')
        os.makedirs(save_dir, exist_ok=True)

        self.set_loading(True)
        self._progress_text = "上传中..."

        if self._gen_btn:
            self._gen_btn.setEnabled(False)

        self._worker = ViewAngleConvertWorker(
            source_image_path=src_path,
            prompt=prompt,
            save_dir=save_dir,
            api_key=api_key,
            base_url=base_url,
            instance_type=instance_type,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_convert_done)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._progress_text = msg
        self.update()

    def _on_convert_done(self, success: bool, local_path: str, error_msg: str):
        """视角转换完成 → 展开预览面板"""
        self._worker = None
        self._progress_text = ""
        self.set_loading(False)

        if self._gen_btn:
            self._gen_btn.setEnabled(True)

        if success and local_path and os.path.isfile(local_path):
            px = QPixmap(local_path)
            if not px.isNull():
                self._output_pixmap = px
                self.show_preview_panel(px)
                return

        print(f"[涛割] 视角转换失败: {error_msg}")
        self._btn_text = "生成视角转换"
        self.update()


# ============================================================
#  ExpressionNode — 改表情/动作节点
#  嵌入 QLineEdit + 生成按钮（无弹窗）
# ============================================================

class ExpressionNode(PipelineStageNode):
    """改表情/动作：嵌入提示词输入 → GeekProvider async API"""

    STAGE_NAME = "表情动作"
    STAGE_COLOR = QColor(255, 140, 80)

    def __init__(self, parent=None, on_output_ready=None):
        super().__init__(parent, on_output_ready)
        self._prompt = "保持人物一致性，保持视角一致，"
        self._btn_text = "修改表情"
        self._controls_h = 60  # 嵌入控件区高度
        self._expr_input: Optional[QLineEdit] = None
        self._expr_gen_btn: Optional[QPushButton] = None
        self._update_rect()

        QTimer.singleShot(0, self._embed_controls)

    def _get_default_btn_text(self) -> str:
        return "修改表情"

    def _embed_controls(self):
        """嵌入 QLineEdit + 生成按钮"""
        if not self.scene():
            QTimer.singleShot(50, self._embed_controls)
            return

        ctrl_w = STAGE_WIDTH - 8

        panel = QWidget()
        panel.setFont(QFont("Microsoft YaHei", 9))
        panel.setFixedSize(ctrl_w, 50)
        panel.setStyleSheet(
            "QWidget { background: transparent; }"
            "QLineEdit { background: #333; color: #ddd; border: 1px solid #555; "
            "border-radius: 4px; padding: 4px 6px; font-size: 11px; }"
            "QPushButton { background: #ff8c50; color: white; border-radius: 4px; "
            "font-size: 11px; min-height: 24px; min-width: 40px; }"
            "QPushButton:hover { background: #e07840; }"
            "QPushButton:disabled { background: #555; color: #888; }"
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(4)

        self._expr_input = QLineEdit()
        self._expr_input.setText(self._prompt)
        self._expr_input.setPlaceholderText("描述表情/动作变化...")
        self._expr_input.returnPressed.connect(self._start_expression_gen)
        row.addWidget(self._expr_input, 1)

        self._expr_gen_btn = QPushButton("生成")
        self._expr_gen_btn.clicked.connect(self._start_expression_gen)
        row.addWidget(self._expr_gen_btn)

        layout.addLayout(row)

        self._controls_proxy = QGraphicsProxyWidget(self)
        self._controls_proxy.setWidget(panel)
        self._controls_proxy.setPos(4, self._get_controls_y())

    def _on_action_clicked(self):
        """按钮点击"""
        if self._preview_result_pixmap:
            self._on_preview_confirm()
        elif self._output_pixmap and not self._is_confirmed:
            self.confirm_result()
        elif self._input_pixmap and not self._is_loading:
            self._start_expression_gen()

    # --- 状态持久化覆盖 ---

    def get_state(self) -> dict:
        state = super().get_state()
        # 额外保存提示词文本
        prompt = self._expr_input.text().strip() if self._expr_input else self._prompt
        state['prompt'] = prompt
        return state

    def restore_state(self, state: dict):
        if not state:
            return
        super().restore_state(state)
        # 恢复提示词文本
        prompt = state.get('prompt', '')
        if prompt:
            self._prompt = prompt
            if self._expr_input:
                self._expr_input.setText(prompt)
            else:
                # 控件尚未创建，延迟恢复
                QTimer.singleShot(200, lambda: (
                    self._expr_input.setText(prompt) if self._expr_input else None
                ))

    def _on_reset(self):
        """重置提示词和按钮状态"""
        self._prompt = "保持人物一致性，保持视角一致，"
        if self._expr_input:
            self._expr_input.setText(self._prompt)
        if self._expr_gen_btn:
            self._expr_gen_btn.setEnabled(True)

    def _start_expression_gen(self):
        """从嵌入输入框读取提示词 → _ExpressionWorker"""
        prompt = self._expr_input.text().strip() if self._expr_input else self._prompt
        if not prompt or not self._input_pixmap or self._is_loading:
            return
        self._prompt = prompt
        self.set_loading(True)
        self._progress_text = "生成中..."

        if self._expr_gen_btn:
            self._expr_gen_btn.setEnabled(False)

        src_path = _save_pixmap_to_temp(self._input_pixmap)
        self._worker = _ExpressionWorker(prompt, src_path)
        self._worker.finished.connect(self._on_expression_done)
        self._worker.start()

    def _on_expression_done(self, success: bool, path: str, error: str):
        """表情修改完成 → 展开预览面板"""
        self._worker = None
        self._progress_text = ""
        self.set_loading(False)

        if self._expr_gen_btn:
            self._expr_gen_btn.setEnabled(True)

        if success and path and os.path.isfile(path):
            px = QPixmap(path)
            if not px.isNull():
                self._output_pixmap = px
                self.show_preview_panel(px)
                return

        print(f"[涛割] 改表情失败: {error}")
        self._btn_text = "修改表情"
        self.update()


# ============================================================
#  AIMattingNode — AI抠图节点
#  进度显示 + 预览面板 + on_matting_confirmed 回调
# ============================================================

class AIMattingNode(PipelineStageNode):
    """AI抠图：调用 RunningHub AI抠图 API，确认后通知 PS 画布更新图层"""

    STAGE_NAME = "AI 抠图"
    STAGE_COLOR = QColor(180, 100, 255)

    def __init__(self, parent=None, on_output_ready=None,
                 on_matting_confirmed: Optional[Callable] = None):
        super().__init__(parent, on_output_ready)
        self._btn_text = "一键抠图"
        self._on_matting_confirmed = on_matting_confirmed

    def _get_default_btn_text(self) -> str:
        return "一键抠图"

    def _on_action_clicked(self):
        if self._preview_result_pixmap:
            self._on_preview_confirm()
        elif self._output_pixmap and not self._is_confirmed:
            self.confirm_result()
            # 确认时额外回调：通知更新PS图层
            if self._on_matting_confirmed and self._output_pixmap:
                self._on_matting_confirmed(self._output_pixmap)
        elif self._input_pixmap and not self._is_loading:
            self._start_matting_api()

    def _on_preview_confirm(self):
        """预览面板确认 — 额外通知 PS 图层"""
        self.confirm_result()
        self.hide_preview_panel()
        if self._on_matting_confirmed and self._output_pixmap:
            self._on_matting_confirmed(self._output_pixmap)

    def _start_matting_api(self):
        """调用 RunningHub AI 抠图 API"""
        cfg = _get_api_config()
        api_key = cfg.get('runninghub_api_key', '')
        base_url = cfg.get('runninghub_base_url', '')
        instance_type = cfg.get('runninghub_instance_type', 'default')

        if not api_key:
            print("[涛割] AI抠图: 未配置 RunningHub API Key")
            return

        src_path = _save_pixmap_to_temp(self._input_pixmap)
        save_dir = os.path.join('generated', 'matting')
        os.makedirs(save_dir, exist_ok=True)

        from services.matting_service import MattingWorker

        self.set_loading(True)
        self._progress_text = "上传中..."

        self._worker = MattingWorker(
            source_image_path=src_path,
            save_dir=save_dir,
            api_key=api_key,
            base_url=base_url,
            instance_type=instance_type,
        )
        self._worker.progress.connect(self._on_matting_progress)
        self._worker.completed.connect(self._on_matting_done)
        self._worker.start()

    def _on_matting_progress(self, msg: str, pct: int):
        """抠图进度更新"""
        if pct > 0:
            self._progress_text = f"{msg} {pct}%"
        else:
            self._progress_text = msg
        self.update()

    def _on_matting_done(self, success: bool, local_path: str, error_msg: str):
        """抠图完成 → 展开预览面板"""
        self._worker = None
        self._progress_text = ""
        self.set_loading(False)

        if success and local_path and os.path.isfile(local_path):
            px = QPixmap(local_path)
            if not px.isNull():
                self._output_pixmap = px
                self.show_preview_panel(px)
                return

        print(f"[涛割] AI抠图失败: {error_msg}")
        self._btn_text = "一键抠图"
        self.update()


# ============================================================
#  HDUpscaleNode — 高清化节点（预留）
# ============================================================

class HDUpscaleNode(PipelineStageNode):
    """高清化（预留）：标记为"即将推出" """

    STAGE_NAME = "高清化"
    STAGE_COLOR = QColor(100, 200, 150)

    def __init__(self, parent=None, on_output_ready=None):
        super().__init__(parent, on_output_ready)
        self._btn_text = "即将推出"

    def _get_default_btn_text(self) -> str:
        return "即将推出"

    def _on_action_clicked(self):
        pass  # 预留，暂不可用

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)

        rect = self.rect()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        overlay_path = QPainterPath()
        overlay_path.addRoundedRect(rect, CORNER_R, CORNER_R)
        painter.fillPath(overlay_path, QBrush(QColor(0, 0, 0, 80)))

        painter.setPen(QPen(QColor(200, 200, 210)))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "即将推出")


# ============================================================
#  _ExpressionWorker — 改表情 Worker
#  使用 GeekProvider.generate_image() async API
# ============================================================

class _ExpressionWorker(QThread):
    """改表情动作 Worker — 通过 GeekProvider/YunwuProvider async API 调用"""

    finished = pyqtSignal(bool, str, str)  # success, path, error

    def __init__(self, prompt: str, image_path: str):
        super().__init__()
        self._prompt = prompt
        self._image_path = image_path

    def run(self):
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._do_generate())
            loop.close()
        except Exception as e:
            self.finished.emit(False, "", str(e))

    async def _do_generate(self):
        from config.settings import SettingsManager
        settings = SettingsManager().settings

        channel = settings.api.image_provider or "geek"
        if channel == "geek":
            from services.generation.closed_source.geek_provider import GeekProvider
            provider = GeekProvider(
                api_key=settings.api.geek_api_key,
                base_url=settings.api.geek_base_url,
            )
        else:
            from services.generation.closed_source.yunwu_provider import YunwuProvider
            provider = YunwuProvider(
                api_key=settings.api.yunwu_api_key,
                base_url=settings.api.yunwu_base_url,
            )

        from services.generation.base_provider import ImageGenerationRequest
        request = ImageGenerationRequest(
            prompt=self._prompt,
            num_images=1,
            reference_images=[self._image_path],
            model_params={
                'model': 'gemini-3-pro-image-preview',
                'aspect_ratio': '1:1',
            },
        )

        result = await provider.generate_image(request)
        await provider.close()

        if result.success:
            path = result.result_path or result.result_url or ""
            self.finished.emit(True, path, "")
        else:
            self.finished.emit(False, "", result.error_message or "生成失败")
