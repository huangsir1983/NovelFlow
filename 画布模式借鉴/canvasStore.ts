// ============================================================
// canvasStore.ts - 画布核心状态管理 (Zustand)
// ============================================================
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { subscribeWithSelector } from 'zustand/middleware';
import {
  NodeData, Connection, ModuleBlock, CanvasViewState,
  Transform, Point, NodeStatus, ModuleType, NodeType,
  StoryboardContent, ImageContent, VideoContent
} from '../types';

// ---------------------------
// Store 接口定义
// ---------------------------
interface CanvasStore {
  // 数据
  nodes: Map<string, NodeData>;
  connections: Connection[];
  modules: Map<string, ModuleBlock>;

  // 视图状态
  view: CanvasViewState;

  // 选择
  selectedNodeIds: Set<string>;
  hoveredNodeId: string | null;

  // UI状态
  isRunning: boolean;
  collapseAll: boolean;

  // ---- 节点操作 ----
  addNode: (node: NodeData) => void;
  updateNode: (id: string, patch: Partial<NodeData>) => void;
  updateNodeContent: (id: string, content: Partial<StoryboardContent | ImageContent | VideoContent>) => void;
  updateNodeStatus: (id: string, status: NodeStatus) => void;
  removeNode: (id: string) => void;
  moveNode: (id: string, position: Point) => void;

  // ---- 批量节点操作 ----
  addNodes: (nodes: NodeData[]) => void;
  updateNodeStatuses: (updates: Array<{ id: string; status: NodeStatus }>) => void;
  markDownstreamOutdated: (nodeId: string) => void;

  // ---- 连线操作 ----
  addConnection: (conn: Connection) => void;
  removeConnection: (id: string) => void;
  getNodeConnections: (nodeId: string) => Connection[];

  // ---- 模块操作 ----
  addModule: (module: ModuleBlock) => void;
  updateModule: (id: string, patch: Partial<ModuleBlock>) => void;
  toggleModuleCollapse: (id: string) => void;
  assignNodeToModule: (nodeId: string, moduleId: string) => void;

  // ---- 视图/变换操作 ----
  setTransform: (transform: Transform) => void;
  setZoom: (scale: number, pivot?: Point) => void;
  panBy: (dx: number, dy: number) => void;
  fitToContent: () => void;
  setVisibleRect: (rect: { x: number; y: number; width: number; height: number }) => void;

  // ---- 选择操作 ----
  selectNode: (id: string, multi?: boolean) => void;
  deselectAll: () => void;
  setHoveredNode: (id: string | null) => void;

  // ---- 查询工具 ----
  getNode: (id: string) => NodeData | undefined;
  getNodesByModule: (moduleId: string) => NodeData[];
  getNodesByChapter: (chapterId: string) => NodeData[];
  getVisibleNodes: () => NodeData[];
  getChainNodes: (storyboardId: string) => NodeData[];

  // ---- 执行状态 ----
  setRunning: (v: boolean) => void;
  toggleCollapseAll: () => void;
}

// ---------------------------
// 工具函数
// ---------------------------
function generateId(): string {
  return `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const VIEWPORT_PADDING = 200; // 懒加载：视口外多少px范围内的节点仍然渲染

// ---------------------------
// Store 实现
// ---------------------------
export const useCanvasStore = create<CanvasStore>()(
  subscribeWithSelector(
    immer((set, get) => ({
      nodes: new Map(),
      connections: [],
      modules: new Map(),
      selectedNodeIds: new Set(),
      hoveredNodeId: null,
      isRunning: false,
      collapseAll: false,

      view: {
        transform: { scale: 1, offsetX: 0, offsetY: 0 },
        selectedNodeIds: new Set(),
        hoveredNodeId: null,
        visibleRect: { x: 0, y: 0, width: 1920, height: 1080 },
      },

      // ---- 节点操作 ----
      addNode: (node) => set(state => {
        state.nodes.set(node.id, node);
      }),

      updateNode: (id, patch) => set(state => {
        const node = state.nodes.get(id);
        if (!node) return;
        Object.assign(node, patch, { updatedAt: Date.now() });
      }),

      updateNodeContent: (id, content) => set(state => {
        const node = state.nodes.get(id);
        if (!node) return;
        Object.assign(node.content, content);
        node.updatedAt = Date.now();
      }),

      updateNodeStatus: (id, status) => set(state => {
        const node = state.nodes.get(id);
        if (!node) return;
        node.status = status;
        node.updatedAt = Date.now();

        // 如果完成，检查下游节点是否可以变为 ready
        if (status === 'done') {
          node.downstreamIds.forEach(downId => {
            const downNode = state.nodes.get(downId);
            if (!downNode || downNode.status !== 'idle') return;
            // 检查所有上游都完成
            const allUpDone = downNode.upstreamIds.every(upId => {
              const up = state.nodes.get(upId);
              return up?.status === 'done';
            });
            if (allUpDone) {
              downNode.status = 'ready';
            }
          });
        }
      }),

      removeNode: (id) => set(state => {
        state.nodes.delete(id);
        state.connections = state.connections.filter(
          c => c.fromNodeId !== id && c.toNodeId !== id
        );
        state.selectedNodeIds.delete(id);
      }),

      moveNode: (id, position) => set(state => {
        const node = state.nodes.get(id);
        if (!node) return;
        node.position = position;
      }),

      addNodes: (nodes) => set(state => {
        nodes.forEach(n => state.nodes.set(n.id, n));
      }),

      updateNodeStatuses: (updates) => set(state => {
        updates.forEach(({ id, status }) => {
          const node = state.nodes.get(id);
          if (node) node.status = status;
        });
      }),

      markDownstreamOutdated: (nodeId) => set(state => {
        // BFS 标记所有下游为 outdated
        const queue = [nodeId];
        const visited = new Set<string>();
        while (queue.length > 0) {
          const current = queue.shift()!;
          if (visited.has(current)) continue;
          visited.add(current);
          const node = state.nodes.get(current);
          if (!node) continue;
          if (current !== nodeId) {
            node.status = 'outdated';
          }
          node.downstreamIds.forEach(id => queue.push(id));
        }
      }),

      // ---- 连线 ----
      addConnection: (conn) => set(state => {
        // 避免重复连线
        const exists = state.connections.some(
          c => c.fromNodeId === conn.fromNodeId && c.toNodeId === conn.toNodeId
        );
        if (!exists) {
          state.connections.push(conn);
          // 同步更新节点的上下游引用
          const fromNode = state.nodes.get(conn.fromNodeId);
          const toNode = state.nodes.get(conn.toNodeId);
          if (fromNode && !fromNode.downstreamIds.includes(conn.toNodeId)) {
            fromNode.downstreamIds.push(conn.toNodeId);
          }
          if (toNode && !toNode.upstreamIds.includes(conn.fromNodeId)) {
            toNode.upstreamIds.push(conn.fromNodeId);
          }
        }
      }),

      removeConnection: (id) => set(state => {
        state.connections = state.connections.filter(c => c.id !== id);
      }),

      getNodeConnections: (nodeId) => {
        return get().connections.filter(
          c => c.fromNodeId === nodeId || c.toNodeId === nodeId
        );
      },

      // ---- 模块 ----
      addModule: (module) => set(state => {
        state.modules.set(module.id, module);
      }),

      updateModule: (id, patch) => set(state => {
        const mod = state.modules.get(id);
        if (mod) Object.assign(mod, patch);
      }),

      toggleModuleCollapse: (id) => set(state => {
        const mod = state.modules.get(id);
        if (mod) mod.collapsed = !mod.collapsed;
      }),

      assignNodeToModule: (nodeId, moduleId) => set(state => {
        const node = state.nodes.get(nodeId);
        const mod = state.modules.get(moduleId);
        if (!node || !mod) return;
        node.moduleId = moduleId;
        if (!mod.nodeIds.includes(nodeId)) {
          mod.nodeIds.push(nodeId);
        }
      }),

      // ---- 视图变换 ----
      setTransform: (transform) => set(state => {
        state.view.transform = transform;
      }),

      setZoom: (scale, pivot) => set(state => {
        const clampedScale = Math.min(3, Math.max(0.1, scale));
        if (pivot) {
          const { offsetX, offsetY, scale: oldScale } = state.view.transform;
          state.view.transform = {
            scale: clampedScale,
            offsetX: pivot.x - (pivot.x - offsetX) * (clampedScale / oldScale),
            offsetY: pivot.y - (pivot.y - offsetY) * (clampedScale / oldScale),
          };
        } else {
          state.view.transform.scale = clampedScale;
        }
      }),

      panBy: (dx, dy) => set(state => {
        state.view.transform.offsetX += dx;
        state.view.transform.offsetY += dy;
      }),

      fitToContent: () => set(state => {
        const nodes = Array.from(state.nodes.values());
        if (nodes.length === 0) return;

        const minX = Math.min(...nodes.map(n => n.position.x));
        const minY = Math.min(...nodes.map(n => n.position.y));
        const maxX = Math.max(...nodes.map(n => n.position.x + n.size.width));
        const maxY = Math.max(...nodes.map(n => n.position.y + n.size.height));

        const contentW = maxX - minX + 120;
        const contentH = maxY - minY + 120;
        const viewW = state.view.visibleRect.width;
        const viewH = state.view.visibleRect.height;

        const scale = Math.min(viewW / contentW, viewH / contentH, 1);
        state.view.transform = {
          scale,
          offsetX: (viewW - contentW * scale) / 2 - minX * scale + 60 * scale,
          offsetY: (viewH - contentH * scale) / 2 - minY * scale + 60 * scale,
        };
      }),

      setVisibleRect: (rect) => set(state => {
        state.view.visibleRect = rect;
      }),

      // ---- 选择 ----
      selectNode: (id, multi = false) => set(state => {
        if (!multi) {
          state.selectedNodeIds = new Set([id]);
        } else {
          if (state.selectedNodeIds.has(id)) {
            state.selectedNodeIds.delete(id);
          } else {
            state.selectedNodeIds.add(id);
          }
        }
      }),

      deselectAll: () => set(state => {
        state.selectedNodeIds = new Set();
      }),

      setHoveredNode: (id) => set(state => {
        state.hoveredNodeId = id;
      }),

      // ---- 查询 ----
      getNode: (id) => get().nodes.get(id),

      getNodesByModule: (moduleId) => {
        return Array.from(get().nodes.values()).filter(n => n.moduleId === moduleId);
      },

      getNodesByChapter: (chapterId) => {
        return Array.from(get().nodes.values()).filter(n => n.chapterId === chapterId);
      },

      getVisibleNodes: () => {
        const { nodes, view } = get();
        const { transform, visibleRect } = view;
        const { scale, offsetX, offsetY } = transform;

        // 扩展视口范围用于预加载
        const padded = {
          x: (visibleRect.x - VIEWPORT_PADDING - offsetX) / scale,
          y: (visibleRect.y - VIEWPORT_PADDING - offsetY) / scale,
          width: (visibleRect.width + VIEWPORT_PADDING * 2) / scale,
          height: (visibleRect.height + VIEWPORT_PADDING * 2) / scale,
        };

        return Array.from(nodes.values()).filter(node => {
          return (
            node.position.x < padded.x + padded.width &&
            node.position.x + node.size.width > padded.x &&
            node.position.y < padded.y + padded.height &&
            node.position.y + node.size.height > padded.y
          );
        });
      },

      // 获取一个分镜节点的完整链路 [storyboard, image, video]
      getChainNodes: (storyboardId) => {
        const { nodes } = get();
        const result: NodeData[] = [];
        let current = nodes.get(storyboardId);
        if (!current) return result;
        result.push(current);

        // 顺着下游找图片、视频节点
        while (current && current.downstreamIds.length > 0) {
          const nextId = current.downstreamIds[0];
          const next = nodes.get(nextId);
          if (!next) break;
          result.push(next);
          current = next;
        }
        return result;
      },

      // ---- 执行 ----
      setRunning: (v) => set(state => { state.isRunning = v; }),

      toggleCollapseAll: () => set(state => {
        state.collapseAll = !state.collapseAll;
        state.modules.forEach(mod => { mod.collapsed = state.collapseAll; });
      }),
    }))
  )
);
