"""
涛割 - ComfyUI 风格智能PS节点画布
每个资产有独立的 4 节点管线链（ViewAngle→Expression→HDUpscale→AIMatting），
默认预加载资产图，修改后逐级向下传递直到 PS 图层。

拓扑:
  InputAsset₁ → ViewAngle₁ → Expression₁ → HDUpscale₁ → AIMatting₁ ─┐
  InputAsset₂ → ViewAngle₂ → Expression₂ → HDUpscale₂ → AIMatting₂ ─┤→ PSCanvasNode
  ...                                                                 ┘      │
                                                               (拖拽创建)      │
                    SnapshotNode(可多个) ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
                         │
                    DissolveNode (默认直通)
                         │
                    HDOutputNode (默认直通+确认输出)
"""

import os
import time
from typing import List, Optional, Dict, Tuple, Callable

from PyQt6.QtWidgets import QGraphicsScene, QGraphicsItem, QMenu, QApplication
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap

from ui.components.base_canvas_view import BaseCanvasView
from .smart_ps_nodes import (
    InputAssetNode, PSCanvasNode, SnapshotNode, DissolveNode, HDOutputNode,
    ANCHOR_R,
)
from .smart_ps_pipeline import (
    PipelineStageNode, ViewAngleNode, ExpressionNode, HDUpscaleNode, AIMattingNode,
    STAGE_WIDTH,
)
from .smart_ps_connections import PSNodeConnectionManager, DragConnectionLine


# ============================================================
#  常量
# ============================================================

COL_GAP = 100       # 列间距（适配更大节点）
ROW_GAP = 60        # 行间距（同列节点间 / 不同链间）
INITIAL_X = 50      # 第一列起始 X
INITIAL_Y = 50      # 第一行起始 Y
CHAIN_ROW_GAP = 30  # 同一链内管线节点间 Y 间距（紧凑）
STAGE_GAP = 30      # 管线节点之间的水平间距

ANCHOR_HIT_RADIUS = 14  # 锚点点击判定半径


# ============================================================
#  AssetPipelineChain — 单个资产的管线链数据
# ============================================================

class AssetPipelineChain:
    """
    管理单个资产的管线链:
    InputAssetNode → ViewAngle → Expression → HDUpscale → AIMatting → (PS图层)
    默认所有节点预加载资产图片。
    某节点修改后，将输出传递给下游所有节点直到 PS 图层。
    """

    def __init__(self, input_node: InputAssetNode,
                 stages: List[PipelineStageNode],
                 ps_node: PSCanvasNode,
                 asset_name: str = '',
                 on_upstream_changed: Optional[Callable] = None):
        self.input_node = input_node
        self.stages = stages  # [ViewAngle, Expression, HDUpscale, AIMatting]
        self.ps_node = ps_node
        self.asset_name = asset_name
        self._on_upstream_changed = on_upstream_changed  # 上游变更 → 同步PS图层

    def preload_asset_image(self, pixmap: QPixmap):
        """将资产原图预加载到所有管线节点"""
        for stage in self.stages:
            stage.set_input_image(pixmap)

    def on_stage_output(self, stage_index: int, pixmap: QPixmap):
        """某阶段确认输出后，向后续阶段传递（不入PS）。
        如果传播到了最后一个阶段（AI抠图），通知 PS 图层同步更新。"""
        for i in range(stage_index + 1, len(self.stages)):
            self.stages[i].set_input_image(pixmap)
        # 上游变更导致 AI 抠图输入更新 → 同步 PS 画布中对应图层
        if self._on_upstream_changed:
            self._on_upstream_changed(pixmap)

    def get_final_output(self) -> Optional[QPixmap]:
        """获取链的最终输出（从后往前找第一个确认的阶段输出，否则返回原图）"""
        for stage in reversed(self.stages):
            out = stage.get_output_image()
            if out:
                return out
        # 没有任何处理，返回输入的原图
        return self.input_node.get_current_pixmap()


# ============================================================
#  SmartPSNodeCanvas — ComfyUI 节点画布
# ============================================================

class SmartPSNodeCanvas(BaseCanvasView):
    """
    ComfyUI 风格无限画布，承载所有节点和连线。
    每个资产有独立的管线链 → PS画布 → 拖拽快照 → 溶图 → 高清化输出。
    """

    output_ready = pyqtSignal(str)  # 最终输出图片路径

    def __init__(self, scene_id: int, data_hub, assets: list,
                 first_open: bool = True, parent=None):
        super().__init__(parent)
        self._scene_id = scene_id
        self._data_hub = data_hub
        self._assets = assets or []
        self._first_open = first_open

        # 节点
        self._input_nodes: List[InputAssetNode] = []
        self._chains: List[AssetPipelineChain] = []  # 每个资产一条链
        self._ps_node: Optional[PSCanvasNode] = None
        self._snapshot_nodes: List[SnapshotNode] = []
        self._dissolve_node: Optional[DissolveNode] = None
        self._hd_output_node: Optional[HDOutputNode] = None

        # 连线管理器
        self._conn_mgr = PSNodeConnectionManager(self._canvas_scene)
        self._conn_ids: List[str] = []

        # 拖拽连线状态
        self._is_dragging_connection = False
        self._drag_source_node = None
        self._drag_from_ps = False
        self._right_click_in_ps = False  # 右键是否在PS画布内部
        self._snapshot_counter = 0

        self._build_graph()
        self._auto_layout()
        self._build_connections()

        # 延迟：预加载资产图到管线节点 + 加载到PS图层
        QTimer.singleShot(500, self._preload_all_chains)

        # 延迟：恢复管线节点状态（在预加载之后）
        QTimer.singleShot(800, self._restore_pipeline_state)

        # 初始 fit-all
        QTimer.singleShot(1000, self.fit_all_in_view)

    # ----------------------------------------------------------
    #  构建节点图
    # ----------------------------------------------------------

    def _build_graph(self):
        """创建所有节点"""
        move_cb = self._on_any_node_moved

        # 恢复动态创建的额外资产（粘贴/继承尾帧）
        self._restore_extra_assets()

        # 1. PSCanvasNode（单个，动态尺寸）
        self._ps_node = PSCanvasNode(
            scene_id=self._scene_id,
            data_hub=self._data_hub,
            first_open=self._first_open,
            assets=self._assets,
            on_moved=move_cb,
        )
        self._canvas_scene.addItem(self._ps_node)

        # 2. 每个 asset → InputAssetNode + 4个独立管线节点 = 一条链
        for idx, asset in enumerate(self._assets):
            inp = InputAssetNode(
                asset,
                on_moved=move_cb,
                on_angle_changed=self._on_asset_angle_changed,
            )
            self._canvas_scene.addItem(inp)
            self._input_nodes.append(inp)

            # 创建4个管线节点（带链式传播回调）
            stages = self._create_chain_stages(idx, move_cb)

            def make_upstream_cb(ci=idx):
                def cb(pixmap):
                    self._on_upstream_changed(ci, pixmap)
                return cb

            # 统一命名逻辑：与 _load_asset_layers 中的 `name or f'资产 {z+1}'` 保持一致
            _name = asset.get('name', '')
            _asset_name = _name or f'资产 {idx + 1}'

            chain = AssetPipelineChain(
                input_node=inp,
                stages=stages,
                ps_node=self._ps_node,
                asset_name=_asset_name,
                on_upstream_changed=make_upstream_cb(),
            )
            self._chains.append(chain)

        # 3. DissolveNode + HDOutputNode
        self._dissolve_node = DissolveNode(on_moved=move_cb)
        self._canvas_scene.addItem(self._dissolve_node)

        self._hd_output_node = HDOutputNode(
            on_output=self._do_output,
            on_moved=move_cb,
        )
        self._canvas_scene.addItem(self._hd_output_node)

    def _create_chain_stages(self, chain_idx: int, move_cb) -> List[PipelineStageNode]:
        """为一条资产链创建4个管线节点"""
        stage_classes = [ViewAngleNode, ExpressionNode, HDUpscaleNode, AIMattingNode]
        stages = []

        for stage_idx, cls in enumerate(stage_classes):
            # 链式回调：确认输出后 → 传播到后续阶段（不入PS）
            def make_callback(ci=chain_idx, si=stage_idx):
                def cb(pixmap):
                    if ci < len(self._chains):
                        self._chains[ci].on_stage_output(si, pixmap)
                return cb

            kwargs = {'parent': None, 'on_output_ready': make_callback()}

            # AI 抠图节点额外回调：确认后更新 PS 图层
            if cls is AIMattingNode:
                def make_matting_cb(ci=chain_idx):
                    def cb(pixmap):
                        self._on_matting_confirmed(ci, pixmap)
                    return cb
                kwargs['on_matting_confirmed'] = make_matting_cb()

            node = cls(**kwargs)
            node.setFlags(
                node.flags() |
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            )
            self._canvas_scene.addItem(node)
            stages.append(node)

        return stages

    # ----------------------------------------------------------
    #  自动布局 — 每资产一行
    # ----------------------------------------------------------

    def _auto_layout(self):
        """
        布局：
          列0: InputAsset
          列1~4: ViewAngle, Expression, HDUpscale, AIMatting (每资产一行)
          列5: PSCanvasNode (居中)
          列6: (快照区域，动态)
          列7: DissolveNode
          列8: HDOutputNode
        """
        n = max(len(self._chains), 1)
        stage_w = STAGE_WIDTH  # 200 (动态高度节点宽度)

        # 每条链一行的高度 — 取各行最大节点高度
        def get_chain_row_height(chain):
            max_stage_h = 0
            for stage in chain.stages:
                sh = stage.rect().height()
                if sh > max_stage_h:
                    max_stage_h = sh
            return max(InputAssetNode.NODE_HEIGHT, max_stage_h) + ROW_GAP

        # --- 列0: InputAsset ---
        x0 = INITIAL_X
        cum_y = INITIAL_Y
        row_ys = []  # 每行的 y 起始位置
        row_hs = []  # 每行的高度

        for i, chain in enumerate(self._chains):
            rh = get_chain_row_height(chain)
            row_ys.append(cum_y)
            row_hs.append(rh)
            self._input_nodes[i].setPos(x0, cum_y)
            cum_y += rh

        # --- 列1~4: 4个管线节点 ---
        x_stage_start = x0 + InputAssetNode.NODE_WIDTH + COL_GAP
        for i, chain in enumerate(self._chains):
            row_y = row_ys[i]
            for j, stage in enumerate(chain.stages):
                stage_h = stage.rect().height()
                # 垂直居中于该行 InputAssetNode 高度
                stage_base_y = row_y + (InputAssetNode.NODE_HEIGHT - stage_h) / 2
                sx = x_stage_start + j * (stage_w + STAGE_GAP)
                stage.setPos(sx, stage_base_y)

        # 管线列总宽
        stages_total_w = 4 * stage_w + 3 * STAGE_GAP

        # --- 列5: PSCanvasNode 居中 ---
        x_ps = x_stage_start + stages_total_w + COL_GAP
        ps_h = self._ps_node._node_h if self._ps_node else 700
        ps_w = self._ps_node._node_w if self._ps_node else 900

        chain_total_h = cum_y - INITIAL_Y - ROW_GAP if row_hs else 0
        if chain_total_h < ps_h:
            ps_y = INITIAL_Y
        else:
            ps_y = INITIAL_Y + (chain_total_h - ps_h) / 2
        self._ps_node.setPos(x_ps, ps_y)

        # --- 列6: 快照区域（动态创建时定位）---
        self._snapshot_col_x = x_ps + ps_w + COL_GAP

        # --- 列7: DissolveNode ---
        dissolve_x = self._snapshot_col_x + SnapshotNode.NODE_WIDTH + COL_GAP
        dissolve_y = ps_y + (ps_h - DissolveNode.NODE_HEIGHT) / 2
        self._dissolve_node.setPos(dissolve_x, max(INITIAL_Y, dissolve_y))

        # --- 列8: HDOutputNode ---
        hd_x = dissolve_x + DissolveNode.NODE_WIDTH + COL_GAP
        hd_y = ps_y + (ps_h - HDOutputNode.NODE_HEIGHT) / 2
        self._hd_output_node.setPos(hd_x, max(INITIAL_Y, hd_y))

    # ----------------------------------------------------------
    #  连线
    # ----------------------------------------------------------

    def _build_connections(self):
        """创建所有贝塞尔连线"""
        self._conn_mgr.clear_all()
        self._conn_ids.clear()

        for chain in self._chains:
            inp = chain.input_node
            stages = chain.stages

            # Input → 第一个管线节点
            if stages:
                cid = self._conn_mgr.add_connection(
                    inp.get_output_anchor(),
                    stages[0].get_input_anchor_pos())
                self._conn_ids.append(cid)

            # 管线节点串联
            for i in range(len(stages) - 1):
                cid = self._conn_mgr.add_connection(
                    stages[i].get_output_anchor_pos(),
                    stages[i + 1].get_input_anchor_pos())
                self._conn_ids.append(cid)

            # 最后一个管线节点 → PS
            if stages:
                cid = self._conn_mgr.add_connection(
                    stages[-1].get_output_anchor_pos(),
                    self._ps_node.get_input_anchor())
                self._conn_ids.append(cid)

        # 快照节点连线
        for snap in self._snapshot_nodes:
            cid = self._conn_mgr.add_connection(
                self._ps_node.get_output_anchor(), snap.get_input_anchor(),
                is_confirmed=True)
            self._conn_ids.append(cid)

        # 最后一个快照 → Dissolve
        if self._snapshot_nodes:
            last_snap = self._snapshot_nodes[-1]
            cid = self._conn_mgr.add_connection(
                last_snap.get_output_anchor(),
                self._dissolve_node.get_input_anchor())
            self._conn_ids.append(cid)

        # Dissolve → HDOutput
        cid = self._conn_mgr.add_connection(
            self._dissolve_node.get_output_anchor(),
            self._hd_output_node.get_input_anchor())
        self._conn_ids.append(cid)

    def _on_any_node_moved(self):
        """任意节点移动后重建连线"""
        self._build_connections()

    # ----------------------------------------------------------
    #  预加载：资产图 → 所有管线节点 + PS 图层
    # ----------------------------------------------------------

    def _preload_all_chains(self):
        """延迟预加载：把资产原图加载到每条链的所有管线节点
        注意：PS 图层由 EmbeddedCanvasWidget._load_asset_layers() 在初始化时创建，
        此处不再重复创建，避免每个资产出现两个同名图层。
        """
        if not self._ps_node:
            return
        for chain in self._chains:
            px = chain.input_node.get_current_pixmap()
            if px and not px.isNull():
                chain.preload_asset_image(px)

    def _on_asset_angle_changed(self, input_node: InputAssetNode, new_pixmap: QPixmap):
        """输入节点视角切换后，重新预加载该链的管线节点 + 同步PS画布图层"""
        for chain_idx, chain in enumerate(self._chains):
            if chain.input_node is input_node:
                chain.preload_asset_image(new_pixmap)
                # 视角变更后，管线节点的输出被重置，PS画布也要同步更新
                self._on_upstream_changed(chain_idx, new_pixmap)
                break

    def _on_upstream_changed(self, chain_idx: int, pixmap: QPixmap):
        """上游阶段输出变更 → 同步更新 PS 画布中对应图层（如果存在）"""
        if chain_idx >= len(self._chains):
            return
        chain = self._chains[chain_idx]
        layer_name = chain.asset_name

        ps = self._ps_node
        if not ps or not ps._embedded_widget:
            print(f"[涛割] _on_upstream_changed: ps._embedded_widget 不存在，跳过")
            return

        try:
            canvas_view = ps._embedded_widget._canvas_view
            # 获取原始资产图片路径（用于备用匹配）
            asset_image_path = ''
            if chain.input_node and hasattr(chain.input_node, '_image_path'):
                asset_image_path = chain.input_node._image_path

            # 策略1: 按名称匹配
            for lid, item in canvas_view._layer_items.items():
                data = getattr(item, '_data', None)
                if data and data.get('name', '') == layer_name:
                    self._replace_layer_image(lid, pixmap, canvas_view)
                    return

            # 策略2: 按原始图片路径匹配（名称不一致时的备用方案）
            if asset_image_path:
                for lid, item in canvas_view._layer_items.items():
                    data = getattr(item, '_data', None)
                    if data:
                        orig_path = data.get('original_image_path', '')
                        if orig_path and os.path.normpath(orig_path) == os.path.normpath(asset_image_path):
                            self._replace_layer_image(lid, pixmap, canvas_view)
                            return

            # 策略3: 按链索引顺序匹配（最后的回退手段）
            layer_ids = sorted(canvas_view._layer_items.keys())
            if chain_idx < len(layer_ids):
                lid = layer_ids[chain_idx]
                self._replace_layer_image(lid, pixmap, canvas_view)
                return

            print(f"[涛割] _on_upstream_changed: 未找到匹配图层 "
                  f"(chain_idx={chain_idx}, layer_name='{layer_name}')")
        except Exception as e:
            print(f"[涛割] 上游变更 → PS图层同步失败: {e}")
            import traceback
            traceback.print_exc()

    def _on_matting_confirmed(self, chain_idx: int, pixmap: QPixmap):
        """AI 抠图确认后，在 PS 画布中创建或替换对应图层（需求5/6）"""
        if chain_idx >= len(self._chains):
            return
        chain = self._chains[chain_idx]
        layer_name = chain.asset_name  # 图层名 = 资产名

        ps = self._ps_node
        if not ps or not ps._embedded_widget:
            return

        try:
            canvas_view = ps._embedded_widget._canvas_view
            # 获取原始资产图片路径（用于备用匹配）
            asset_image_path = ''
            if chain.input_node and hasattr(chain.input_node, '_image_path'):
                asset_image_path = chain.input_node._image_path

            # 策略1: 按名称匹配
            for lid, item in canvas_view._layer_items.items():
                data = getattr(item, '_data', None)
                if data and data.get('name', '') == layer_name:
                    self._replace_layer_image(lid, pixmap, canvas_view)
                    return

            # 策略2: 按原始图片路径匹配
            if asset_image_path:
                for lid, item in canvas_view._layer_items.items():
                    data = getattr(item, '_data', None)
                    if data:
                        orig_path = data.get('original_image_path', '')
                        if orig_path and os.path.normpath(orig_path) == os.path.normpath(asset_image_path):
                            self._replace_layer_image(lid, pixmap, canvas_view)
                            return

            # 策略3: 按链索引顺序匹配
            layer_ids = sorted(canvas_view._layer_items.keys())
            if chain_idx < len(layer_ids):
                lid = layer_ids[chain_idx]
                self._replace_layer_image(lid, pixmap, canvas_view)
                return

            # 都没找到 → 创建新图层
            ps.add_layer_from_pixmap(pixmap, layer_name)
        except Exception as e:
            print(f"[涛割] AI抠图确认 → PS图层更新失败: {e}")
            import traceback
            traceback.print_exc()

    def _replace_layer_image(self, layer_id: int, pixmap: QPixmap, canvas_view):
        """替换已有图层的图片"""
        try:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False,
                                              prefix='ps_matting_')
            tmp_path = tmp.name
            tmp.close()
            pixmap.save(tmp_path, 'PNG')

            # 更新图层数据库（save_layer 传入 id 即为更新模式）
            from services.layer_service import LayerService
            layer_service = LayerService()
            layer_service.save_layer({
                'id': layer_id,
                'image_path': tmp_path,
                'original_image_path': tmp_path,
            })

            # 刷新画布中的图层项
            if layer_id in canvas_view._layer_items:
                item = canvas_view._layer_items[layer_id]
                # 使用 update_pixmap 而非 setPixmap，确保旋转中心和手柄同步更新
                if hasattr(item, 'update_pixmap'):
                    item.update_pixmap(pixmap)
                else:
                    item.setPixmap(pixmap)
                # 同步更新 _data 字典
                if hasattr(item, '_data') and isinstance(item._data, dict):
                    item._data['image_path'] = tmp_path
                    item._data['original_image_path'] = tmp_path

            # 刷新图层面板
            if self._ps_node and self._ps_node._embedded_widget:
                self._ps_node._embedded_widget._refresh_layer_panel()
        except Exception as e:
            print(f"[涛割] 替换图层图片失败: {e}")
            import traceback
            traceback.print_exc()

    # ----------------------------------------------------------
    #  拖拽创建快照 + 通用锚点拖拽
    # ----------------------------------------------------------

    def mousePressEvent(self, event):
        """检测锚点拖拽 or PS画布内部点击"""
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())

            # 检测是否点击了某个节点的输出锚点
            source = self._find_drag_source_at(scene_pos)
            if source is not None:
                self._is_dragging_connection = True
                self._drag_source_node = source
                self._drag_from_ps = isinstance(source, PSCanvasNode)
                # 获取输出锚点位置
                anchor = source.get_output_anchor() if hasattr(source, 'get_output_anchor') \
                    else source.get_output_anchor_pos()
                self._conn_mgr.start_drag(anchor)
                event.accept()
                return

        # 检测是否点击了 PS 画布内部 proxy
        item = self.itemAt(event.pos())
        if item and self._is_inside_ps_node(item):
            if event.button() == Qt.MouseButton.RightButton:
                # 右键在 PS 画布内部 → 绕过外层平移逻辑，直接交给 QGraphicsView 分发到 proxy
                self._right_click_in_ps = True
                from PyQt6.QtWidgets import QGraphicsView
                QGraphicsView.mousePressEvent(self, event)
                return
            super().mousePressEvent(event)
            return

        self._right_click_in_ps = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """拖拽中更新连线"""
        if self._is_dragging_connection:
            scene_pos = self.mapToScene(event.pos())
            self._conn_mgr.update_drag(scene_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """拖拽结束：连到目标节点 or 从PS创建快照 or 右键菜单"""
        if self._is_dragging_connection and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self._is_dragging_connection = False

            target = self._find_node_input_at(scene_pos)
            if target is not None:
                anchor = target.get_input_anchor() if hasattr(target, 'get_input_anchor') \
                    else target.get_input_anchor_pos()
                cid = self._conn_mgr.finish_drag(anchor)
                if cid:
                    self._conn_ids.append(cid)
            elif self._drag_from_ps:
                self._conn_mgr.cancel_drag()
                self._create_snapshot_at(scene_pos)
            else:
                self._conn_mgr.cancel_drag()

            self._drag_source_node = None
            self._drag_from_ps = False
            event.accept()
            return

        # 右键释放
        if event.button() == Qt.MouseButton.RightButton:
            # 如果右键在 PS 画布内部 → 交给 proxy 处理（图层右键菜单）
            if getattr(self, '_right_click_in_ps', False):
                self._right_click_in_ps = False
                from PyQt6.QtWidgets import QGraphicsView
                QGraphicsView.mouseReleaseEvent(self, event)
                return

            # 外层画布右键菜单 — 先重置平移状态防止画布跟随鼠标
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

            if not self._pan_moved:
                self._show_canvas_context_menu(event.pos())
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def _is_inside_ps_node(self, item) -> bool:
        """检测 item 是否在 PSCanvasNode 内部（沿父链查找）"""
        parent = item
        while parent:
            if isinstance(parent, PSCanvasNode):
                return True
            parent = parent.parentItem()
        return False

    def _find_drag_source_at(self, scene_pos: QPointF):
        """遍历所有节点，检测哪个的输出锚点被点击"""
        all_nodes = []
        all_nodes.extend(self._input_nodes)
        if self._ps_node:
            all_nodes.append(self._ps_node)
        all_nodes.extend(self._snapshot_nodes)
        if self._dissolve_node:
            all_nodes.append(self._dissolve_node)
        for chain in self._chains:
            all_nodes.extend(chain.stages)

        for node in all_nodes:
            if self._is_on_output_anchor(node, scene_pos):
                return node
        return None

    def _find_node_input_at(self, scene_pos: QPointF):
        """遍历所有节点，检测哪个的输入锚点在附近"""
        all_nodes = []
        if self._ps_node:
            all_nodes.append(self._ps_node)
        all_nodes.extend(self._snapshot_nodes)
        if self._dissolve_node:
            all_nodes.append(self._dissolve_node)
        if self._hd_output_node:
            all_nodes.append(self._hd_output_node)
        for chain in self._chains:
            all_nodes.extend(chain.stages)

        for node in all_nodes:
            if self._is_on_input_anchor(node, scene_pos):
                return node
        return None

    def _is_on_output_anchor(self, node, scene_pos: QPointF,
                             radius: float = ANCHOR_HIT_RADIUS) -> bool:
        """判断 scene_pos 是否在节点输出锚点附近"""
        anchor = node.get_output_anchor() if hasattr(node, 'get_output_anchor') else \
                 (node.get_output_anchor_pos() if hasattr(node, 'get_output_anchor_pos') else None)
        if anchor is None:
            return False
        dx = scene_pos.x() - anchor.x()
        dy = scene_pos.y() - anchor.y()
        return (dx * dx + dy * dy) <= radius * radius

    def _is_on_input_anchor(self, node, scene_pos: QPointF,
                            radius: float = ANCHOR_HIT_RADIUS) -> bool:
        """判断 scene_pos 是否在节点输入锚点附近"""
        anchor = node.get_input_anchor() if hasattr(node, 'get_input_anchor') else \
                 (node.get_input_anchor_pos() if hasattr(node, 'get_input_anchor_pos') else None)
        if anchor is None:
            return False
        dx = scene_pos.x() - anchor.x()
        dy = scene_pos.y() - anchor.y()
        return (dx * dx + dy * dy) <= radius * radius

    # ----------------------------------------------------------
    #  快照创建
    # ----------------------------------------------------------

    def _create_snapshot_at(self, scene_pos: QPointF):
        """从PS导出合成图，创建快照节点"""
        if not self._ps_node:
            return
        path = self._ps_node.export_composite_image()
        if not path:
            return

        px = QPixmap(path)
        if px.isNull():
            return

        self._snapshot_counter += 1
        snap = SnapshotNode(
            snapshot_index=self._snapshot_counter,
            on_retake=self._on_snapshot_retake,
            on_moved=self._on_any_node_moved,
        )

        snap_x = scene_pos.x() - SnapshotNode.NODE_WIDTH / 2
        snap_y = scene_pos.y() - SnapshotNode.NODE_HEIGHT / 2
        snap.setPos(snap_x, snap_y)

        self._canvas_scene.addItem(snap)
        snap.set_snapshot(px, path)
        self._snapshot_nodes.append(snap)

        self._build_connections()
        self._propagate_snapshot_to_output(px, path)

    def _on_snapshot_retake(self, snap_node: SnapshotNode):
        """重新拍摄快照"""
        if not self._ps_node:
            return
        path = self._ps_node.export_composite_image()
        if path:
            px = QPixmap(path)
            if not px.isNull():
                snap_node.set_snapshot(px, path)
                self._propagate_snapshot_to_output(px, path)

    def _propagate_snapshot_to_output(self, pixmap: QPixmap, path: str):
        """快照图片直通传递到溶图→高清化输出"""
        if self._dissolve_node:
            self._dissolve_node.set_input(pixmap, path)
        if self._hd_output_node:
            self._hd_output_node.set_input(pixmap, path)

    # ----------------------------------------------------------
    #  输出
    # ----------------------------------------------------------

    def _do_output(self):
        """确认输出（从 HDOutputNode 触发）"""
        if not self._hd_output_node:
            return
        path = self._hd_output_node.get_output_path()
        if not path:
            if self._ps_node:
                path = self._ps_node.export_composite_image()
                if path:
                    px = QPixmap(path)
                    if not px.isNull():
                        self._hd_output_node.set_input(px, path)
        if path:
            self.output_ready.emit(path)

    # ----------------------------------------------------------
    #  PS画布保存
    # ----------------------------------------------------------

    def save_canvas(self):
        """保存 PS 画布场景"""
        if self._ps_node:
            self._ps_node.save_scene()

    # ----------------------------------------------------------
    #  额外资产持久化（粘贴/继承尾帧创建的管线链）
    # ----------------------------------------------------------

    def _save_extra_asset(self, asset: dict):
        """将动态创建的额外资产保存到数据库 generation_params['extra_pipeline_assets']"""
        if not self._scene_id:
            return
        try:
            from database.session import DatabaseManager
            from database.models.scene import Scene
            from sqlalchemy.orm.attributes import flag_modified

            # 确保使用绝对路径
            img_path = asset.get('image_path', '')
            if img_path and not os.path.isabs(img_path):
                img_path = os.path.abspath(img_path)

            db = DatabaseManager()
            with db.session_scope() as session:
                scene = session.query(Scene).filter_by(id=self._scene_id).first()
                if not scene:
                    return
                params = scene.generation_params or {}
                extras = params.get('extra_pipeline_assets', [])
                # 避免重复添加（按 image_path 去重）
                existing_paths = {a.get('image_path', '') for a in extras}
                if img_path not in existing_paths:
                    extras.append({
                        'name': asset.get('name', ''),
                        'image_path': img_path,
                        'type': asset.get('type', 'prop'),
                        'multi_angle_images': asset.get('multi_angle_images', []),
                    })
                params['extra_pipeline_assets'] = extras
                scene.generation_params = params
                flag_modified(scene, 'generation_params')
                print(f"[涛割] _save_extra_asset: 已保存额外资产 '{asset.get('name', '')}' → {img_path}")
        except Exception as e:
            print(f"[涛割] 保存额外资产失败: {e}")
            import traceback
            traceback.print_exc()

    def _restore_extra_assets(self):
        """从数据库读取额外资产，追加到 self._assets（在 _build_graph 开始时调用）"""
        if not self._scene_id:
            return
        try:
            from database.session import DatabaseManager
            from database.models.scene import Scene

            db = DatabaseManager()
            with db.session_scope() as session:
                scene = session.query(Scene).filter_by(id=self._scene_id).first()
                if not scene:
                    return
                params = scene.generation_params or {}
                extras = params.get('extra_pipeline_assets', [])
                if not extras:
                    return

                # 仅追加图片文件仍存在的额外资产
                existing_paths = {a.get('image_path', '') for a in self._assets}
                added = 0
                for extra in extras:
                    img_path = extra.get('image_path', '')
                    if img_path and img_path not in existing_paths:
                        if os.path.isfile(img_path):
                            self._assets.append(extra)
                            added += 1
                        else:
                            print(f"[涛割] _restore_extra_assets: 文件不存在，跳过 → {img_path}")
                if added:
                    print(f"[涛割] _restore_extra_assets: 恢复了 {added} 个额外资产")
        except Exception as e:
            print(f"[涛割] 恢复额外资产失败: {e}")
            import traceback
            traceback.print_exc()

    def save_pipeline_state(self):
        """将所有管线链的节点状态持久化到数据库 scene.generation_params['pipeline_state']"""
        if not self._scene_id or not self._chains:
            print(f"[涛割] save_pipeline_state: 跳过 (scene_id={self._scene_id}, chains={len(self._chains) if self._chains else 0})")
            return

        try:
            from database.session import DatabaseManager
            from database.models.scene import Scene
            from sqlalchemy.orm.attributes import flag_modified

            db = DatabaseManager()
            with db.session_scope() as session:
                scene = session.query(Scene).filter_by(id=self._scene_id).first()
                if not scene:
                    print(f"[涛割] save_pipeline_state: 场景 {self._scene_id} 不存在")
                    return

                params = scene.generation_params or {}

                chains_state = []
                stage_names = ['view_angle', 'expression', 'hd_upscale', 'ai_matting']

                for chain in self._chains:
                    chain_data = {
                        'asset_name': chain.asset_name,
                        'stages': {},
                    }
                    for i, stage in enumerate(chain.stages):
                        key = stage_names[i] if i < len(stage_names) else f'stage_{i}'
                        state = stage.get_state()
                        chain_data['stages'][key] = state
                    chains_state.append(chain_data)

                params['pipeline_state'] = {'chains': chains_state}
                scene.generation_params = params
                flag_modified(scene, 'generation_params')
                print(f"[涛割] save_pipeline_state: 已保存 {len(chains_state)} 条链到场景 {self._scene_id}")
        except Exception as e:
            print(f"[涛割] 管线状态保存失败: {e}")
            import traceback
            traceback.print_exc()

    def _restore_pipeline_state(self):
        """从数据库恢复管线链的节点状态"""
        if not self._scene_id or not self._chains:
            print(f"[涛割] _restore_pipeline_state: 跳过 (scene_id={self._scene_id}, chains={len(self._chains) if self._chains else 0})")
            return

        try:
            from database.session import DatabaseManager
            from database.models.scene import Scene

            db = DatabaseManager()
            with db.session_scope() as session:
                scene = session.query(Scene).filter_by(id=self._scene_id).first()
                if not scene:
                    print(f"[涛割] _restore_pipeline_state: 场景 {self._scene_id} 不存在")
                    return

                params = scene.generation_params or {}
                pipeline_state = params.get('pipeline_state', {})
                chains_state = pipeline_state.get('chains', [])

                if not chains_state:
                    print(f"[涛割] _restore_pipeline_state: 无保存状态")
                    return

                stage_names = ['view_angle', 'expression', 'hd_upscale', 'ai_matting']

                # 构建 asset_name → saved_chain 映射，优先按名称匹配
                saved_by_name = {}
                for sc in chains_state:
                    aname = sc.get('asset_name', '')
                    if aname:
                        saved_by_name[aname] = sc

                restored = 0
                for ci, chain in enumerate(self._chains):
                    # 优先按 asset_name 匹配，回退到索引匹配
                    saved_chain = saved_by_name.get(chain.asset_name)
                    if not saved_chain and ci < len(chains_state):
                        saved_chain = chains_state[ci]
                    if not saved_chain:
                        continue
                    stages_data = saved_chain.get('stages', {})

                    for si, stage in enumerate(chain.stages):
                        key = stage_names[si] if si < len(stage_names) else f'stage_{si}'
                        state = stages_data.get(key, {})
                        if state:
                            stage.restore_state(state)
                    restored += 1

                print(f"[涛割] _restore_pipeline_state: 已恢复 {restored}/{len(self._chains)} 条链")
        except Exception as e:
            print(f"[涛割] 管线状态恢复失败: {e}")
            import traceback
            traceback.print_exc()

    def export_output(self) -> str:
        """获取最终输出路径"""
        if self._hd_output_node:
            return self._hd_output_node.get_output_path()
        return ''

    # ----------------------------------------------------------
    #  右键菜单：粘贴图片 / 继承尾帧
    # ----------------------------------------------------------

    def _show_canvas_context_menu(self, view_pos):
        """在画布空白处右键弹出菜单"""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #2a2a3e; color: #e0e0ef; border: 1px solid #3a3a50; "
            "border-radius: 6px; padding: 4px; }"
            "QMenu::item { padding: 8px 20px; }"
            "QMenu::item:selected { background: #5b7fff; border-radius: 4px; }"
            "QMenu::item:disabled { color: #666680; }"
        )

        scene_pos = self.mapToScene(view_pos)

        # 粘贴外界图片
        paste_action = menu.addAction("粘贴外界图片")
        clipboard = QApplication.clipboard()
        has_image = clipboard and not clipboard.image().isNull()
        paste_action.setEnabled(has_image)
        paste_action.triggered.connect(lambda: self._paste_clipboard_image(scene_pos))

        menu.addSeparator()

        # 继承上一分镜尾帧
        inherit_action = menu.addAction("继承上一分镜尾帧")
        inherit_action.triggered.connect(lambda: self._inherit_prev_end_frame(scene_pos))

        menu.exec(self.mapToGlobal(view_pos))

    def _paste_clipboard_image(self, scene_pos: QPointF):
        """从剪贴板粘贴图片 → 创建完整管线链"""
        clipboard = QApplication.clipboard()
        if not clipboard:
            return
        q_image = clipboard.image()
        if q_image.isNull():
            print("[涛割] 剪贴板中没有图片")
            return

        pixmap = QPixmap.fromImage(q_image)
        if pixmap.isNull():
            return

        # 保存到持久文件
        save_dir = os.path.join(os.getcwd(), 'generated', 'paste')
        os.makedirs(save_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        save_path = os.path.join(save_dir, f'{timestamp}.png')
        pixmap.save(save_path, 'PNG')

        # 创建管线链
        self._create_chain_from_image(pixmap, save_path, '粘贴图片', 'prop', scene_pos)

    def _inherit_prev_end_frame(self, scene_pos: QPointF):
        """继承上一分镜的尾帧 → 创建管线链"""
        end_frame_path = self._get_prev_scene_end_frame()
        if not end_frame_path:
            print("[涛割] 上一分镜没有可用的视频尾帧")
            return

        pixmap = QPixmap(end_frame_path)
        if pixmap.isNull():
            print(f"[涛割] 无法加载尾帧图片: {end_frame_path}")
            return

        self._create_chain_from_image(
            pixmap, end_frame_path, '上一分镜尾帧', 'background', scene_pos)

    def _get_prev_scene_end_frame(self) -> Optional[str]:
        """获取上一分镜的尾帧路径"""
        if not self._scene_id or not self._data_hub:
            return None

        try:
            from database.session import DatabaseManager
            from database.models.scene import Scene

            db = DatabaseManager()
            with db.session_scope() as session:
                # 查询当前场景
                current = session.query(Scene).filter_by(id=self._scene_id).first()
                if not current:
                    return None

                # 查询上一分镜（scene_index - 1）
                prev = session.query(Scene).filter_by(
                    project_id=current.project_id,
                    scene_index=current.scene_index - 1
                ).first()
                if not prev:
                    return None

                # 优先级1: 已有尾帧路径
                if prev.end_frame_path and os.path.isfile(prev.end_frame_path):
                    return prev.end_frame_path

                # 优先级2: 从视频提取尾帧
                if prev.generated_video_path and os.path.isfile(prev.generated_video_path):
                    from services.utils.frame_extractor import FrameExtractor
                    save_dir = os.path.join('generated', 'end_frames')
                    os.makedirs(save_dir, exist_ok=True)
                    output_path = os.path.join(
                        save_dir, f'scene_{prev.scene_index}_end.png')
                    result = FrameExtractor.extract_last_frame(
                        prev.generated_video_path, output_path)
                    if result:
                        # 保存尾帧路径到数据库
                        prev.end_frame_path = result
                        session.commit()
                        return result

                return None
        except Exception as e:
            print(f"[涛割] 获取上一分镜尾帧失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _create_chain_from_image(self, pixmap: QPixmap, image_path: str,
                                  name: str, asset_type: str,
                                  scene_pos: QPointF):
        """从图片创建完整管线链（InputAssetNode + 4个管线节点 → PS图层）"""
        move_cb = self._on_any_node_moved

        asset = {
            'name': name,
            'image_path': image_path,
            'type': asset_type,
            'multi_angle_images': [],
        }

        # 1. 创建 InputAssetNode
        inp = InputAssetNode(
            asset,
            on_moved=move_cb,
            on_angle_changed=self._on_asset_angle_changed,
        )
        self._canvas_scene.addItem(inp)
        self._input_nodes.append(inp)

        chain_idx = len(self._chains)

        # 2. 创建4个管线节点
        stages = self._create_chain_stages(chain_idx, move_cb)

        def make_upstream_cb(ci=chain_idx):
            def cb(px):
                self._on_upstream_changed(ci, px)
            return cb

        chain = AssetPipelineChain(
            input_node=inp,
            stages=stages,
            ps_node=self._ps_node,
            asset_name=name,
            on_upstream_changed=make_upstream_cb(),
        )
        self._chains.append(chain)

        # 3. 在PS画布中添加图层
        if self._ps_node:
            self._ps_node.add_layer_from_pixmap(pixmap, name)

        # 4. 重新布局 + 重建连线
        self._auto_layout()
        self._build_connections()

        # 5. 预加载管线节点
        chain.preload_asset_image(pixmap)

        # 6. 持久化额外资产到数据库
        self._save_extra_asset(asset)
