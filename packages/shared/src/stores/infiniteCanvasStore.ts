'use client';

// ══════════════════════════════════════════════════════════════
// infiniteCanvasStore.ts — 无限画布核心状态管理 (Zustand + Immer)
//
// 管理画布节点、连线、模块区域、视图变换、选择状态。
// 与现有 canvasStore.ts (基于 @xyflow/react) 独立，
// 服务于 Tapnow 式可执行无限画布工作台。
// ══════════════════════════════════════════════════════════════

import { create } from 'zustand';
import type {
  CanvasNodeData,
  CanvasConnection,
  CanvasModuleBlock,
  CanvasViewState,
  CanvasTransform,
  CanvasPoint,
  CanvasNodeStatus,
  CanvasModuleType,
  StoryboardContent,
  ImageContent,
  VideoContent,
} from '../types/canvas';

// ── Store 接口 ──

interface InfiniteCanvasStore {
  // 数据
  nodes: Map<string, CanvasNodeData>;
  connections: CanvasConnection[];
  modules: Map<string, CanvasModuleBlock>;

  // 视图状态
  view: CanvasViewState;

  // 选择
  selectedNodeIds: Set<string>;
  hoveredNodeId: string | null;

  // UI 状态
  isRunning: boolean;
  collapseAll: boolean;

  // ── 节点操作 ──
  addNode: (node: CanvasNodeData) => void;
  updateNode: (id: string, patch: Partial<CanvasNodeData>) => void;
  updateNodeContent: (id: string, content: Partial<StoryboardContent | ImageContent | VideoContent>) => void;
  updateNodeStatus: (id: string, status: CanvasNodeStatus) => void;
  removeNode: (id: string) => void;
  moveNode: (id: string, position: CanvasPoint) => void;

  // ── 批量节点操作 ──
  addNodes: (nodes: CanvasNodeData[]) => void;
  updateNodeStatuses: (updates: Array<{ id: string; status: CanvasNodeStatus }>) => void;
  markDownstreamOutdated: (nodeId: string) => void;

  // ── 连线操作 ──
  addConnection: (conn: CanvasConnection) => void;
  removeConnection: (id: string) => void;
  getNodeConnections: (nodeId: string) => CanvasConnection[];

  // ── 模块操作 ──
  addModule: (module: CanvasModuleBlock) => void;
  updateModule: (id: string, patch: Partial<CanvasModuleBlock>) => void;
  toggleModuleCollapse: (id: string) => void;
  assignNodeToModule: (nodeId: string, moduleId: string) => void;

  // ── 视图/变换 ──
  setTransform: (transform: CanvasTransform) => void;
  setZoom: (scale: number, pivot?: CanvasPoint) => void;
  panBy: (dx: number, dy: number) => void;
  fitToContent: () => void;
  setVisibleRect: (rect: { x: number; y: number; width: number; height: number }) => void;

  // ── 选择 ──
  selectNode: (id: string, multi?: boolean) => void;
  deselectAll: () => void;
  setHoveredNode: (id: string | null) => void;

  // ── 查询工具 ──
  getNode: (id: string) => CanvasNodeData | undefined;
  getNodesByModule: (moduleId: string) => CanvasNodeData[];
  getNodesByChapter: (chapterId: string) => CanvasNodeData[];
  getVisibleNodes: () => CanvasNodeData[];
  getChainNodes: (storyboardId: string) => CanvasNodeData[];

  // ── 执行状态 ──
  setRunning: (v: boolean) => void;
  toggleCollapseAll: () => void;

  // ── 重置 ──
  reset: () => void;
}

// ── 常量 ──

const VIEWPORT_PADDING = 200;

// ── Store 实现 ──

const initialView: CanvasViewState = {
  transform: { scale: 1, offsetX: 0, offsetY: 0 },
  selectedNodeIds: new Set(),
  hoveredNodeId: null,
  visibleRect: { x: 0, y: 0, width: 1920, height: 1080 },
};

export const useInfiniteCanvasStore = create<InfiniteCanvasStore>((set, get) => ({
  nodes: new Map(),
  connections: [],
  modules: new Map(),
  selectedNodeIds: new Set(),
  hoveredNodeId: null,
  isRunning: false,
  collapseAll: false,
  view: { ...initialView },

  // ── 节点操作 ──

  addNode: (node) => set((state) => {
    const next = new Map(state.nodes);
    next.set(node.id, node);
    return { nodes: next };
  }),

  updateNode: (id, patch) => set((state) => {
    const node = state.nodes.get(id);
    if (!node) return state;
    const next = new Map(state.nodes);
    next.set(id, { ...node, ...patch, updatedAt: Date.now() });
    return { nodes: next };
  }),

  updateNodeContent: (id, content) => set((state) => {
    const node = state.nodes.get(id);
    if (!node) return state;
    const next = new Map(state.nodes);
    next.set(id, {
      ...node,
      content: { ...node.content, ...content } as typeof node.content,
      updatedAt: Date.now(),
    });
    return { nodes: next };
  }),

  updateNodeStatus: (id, status) => set((state) => {
    const node = state.nodes.get(id);
    if (!node) return state;
    const next = new Map(state.nodes);
    next.set(id, { ...node, status, updatedAt: Date.now() });

    // 如果完成，检查下游节点是否可以变为 ready
    if (status === 'done') {
      for (const downId of node.downstreamIds) {
        const downNode = next.get(downId);
        if (!downNode || downNode.status !== 'idle') continue;
        const allUpDone = downNode.upstreamIds.every((upId) => {
          const up = next.get(upId);
          return up?.status === 'done';
        });
        if (allUpDone) {
          next.set(downId, { ...downNode, status: 'ready' });
        }
      }
    }
    return { nodes: next };
  }),

  removeNode: (id) => set((state) => {
    const next = new Map(state.nodes);
    next.delete(id);
    const nextSelected = new Set(state.selectedNodeIds);
    nextSelected.delete(id);
    return {
      nodes: next,
      connections: state.connections.filter((c) => c.fromNodeId !== id && c.toNodeId !== id),
      selectedNodeIds: nextSelected,
    };
  }),

  moveNode: (id, position) => set((state) => {
    const node = state.nodes.get(id);
    if (!node) return state;
    const next = new Map(state.nodes);
    next.set(id, { ...node, position });
    return { nodes: next };
  }),

  addNodes: (nodes) => set((state) => {
    const next = new Map(state.nodes);
    for (const n of nodes) next.set(n.id, n);
    return { nodes: next };
  }),

  updateNodeStatuses: (updates) => set((state) => {
    const next = new Map(state.nodes);
    for (const { id, status } of updates) {
      const node = next.get(id);
      if (node) next.set(id, { ...node, status });
    }
    return { nodes: next };
  }),

  markDownstreamOutdated: (nodeId) => set((state) => {
    const next = new Map(state.nodes);
    const queue = [nodeId];
    const visited = new Set<string>();
    while (queue.length > 0) {
      const current = queue.shift()!;
      if (visited.has(current)) continue;
      visited.add(current);
      const node = next.get(current);
      if (!node) continue;
      if (current !== nodeId) {
        next.set(current, { ...node, status: 'outdated' as CanvasNodeStatus });
      }
      queue.push(...node.downstreamIds);
    }
    return { nodes: next };
  }),

  // ── 连线 ──

  addConnection: (conn) => set((state) => {
    const exists = state.connections.some(
      (c) => c.fromNodeId === conn.fromNodeId && c.toNodeId === conn.toNodeId,
    );
    if (exists) return state;

    const next = new Map(state.nodes);
    const fromNode = next.get(conn.fromNodeId);
    const toNode = next.get(conn.toNodeId);
    if (fromNode && !fromNode.downstreamIds.includes(conn.toNodeId)) {
      next.set(fromNode.id, { ...fromNode, downstreamIds: [...fromNode.downstreamIds, conn.toNodeId] });
    }
    if (toNode && !toNode.upstreamIds.includes(conn.fromNodeId)) {
      next.set(toNode.id, { ...toNode, upstreamIds: [...toNode.upstreamIds, conn.fromNodeId] });
    }
    return { connections: [...state.connections, conn], nodes: next };
  }),

  removeConnection: (id) => set((state) => ({
    connections: state.connections.filter((c) => c.id !== id),
  })),

  getNodeConnections: (nodeId) => {
    return get().connections.filter((c) => c.fromNodeId === nodeId || c.toNodeId === nodeId);
  },

  // ── 模块 ──

  addModule: (module) => set((state) => {
    const next = new Map(state.modules);
    next.set(module.id, module);
    return { modules: next };
  }),

  updateModule: (id, patch) => set((state) => {
    const mod = state.modules.get(id);
    if (!mod) return state;
    const next = new Map(state.modules);
    next.set(id, { ...mod, ...patch });
    return { modules: next };
  }),

  toggleModuleCollapse: (id) => set((state) => {
    const mod = state.modules.get(id);
    if (!mod) return state;
    const next = new Map(state.modules);
    next.set(id, { ...mod, collapsed: !mod.collapsed });
    return { modules: next };
  }),

  assignNodeToModule: (nodeId, moduleId) => set((state) => {
    const node = state.nodes.get(nodeId);
    const mod = state.modules.get(moduleId);
    if (!node || !mod) return state;
    const nextNodes = new Map(state.nodes);
    nextNodes.set(nodeId, { ...node, moduleId });
    const nextModules = new Map(state.modules);
    if (!mod.nodeIds.includes(nodeId)) {
      nextModules.set(moduleId, { ...mod, nodeIds: [...mod.nodeIds, nodeId] });
    }
    return { nodes: nextNodes, modules: nextModules };
  }),

  // ── 视图变换 ──

  setTransform: (transform) => set((state) => ({
    view: { ...state.view, transform },
  })),

  setZoom: (scale, pivot) => set((state) => {
    const clampedScale = Math.min(3, Math.max(0.1, scale));
    if (pivot) {
      const { offsetX, offsetY, scale: oldScale } = state.view.transform;
      return {
        view: {
          ...state.view,
          transform: {
            scale: clampedScale,
            offsetX: pivot.x - (pivot.x - offsetX) * (clampedScale / oldScale),
            offsetY: pivot.y - (pivot.y - offsetY) * (clampedScale / oldScale),
          },
        },
      };
    }
    return {
      view: { ...state.view, transform: { ...state.view.transform, scale: clampedScale } },
    };
  }),

  panBy: (dx, dy) => set((state) => ({
    view: {
      ...state.view,
      transform: {
        ...state.view.transform,
        offsetX: state.view.transform.offsetX + dx,
        offsetY: state.view.transform.offsetY + dy,
      },
    },
  })),

  fitToContent: () => set((state) => {
    const nodes = Array.from(state.nodes.values());
    if (nodes.length === 0) return state;

    const minX = Math.min(...nodes.map((n) => n.position.x));
    const minY = Math.min(...nodes.map((n) => n.position.y));
    const maxX = Math.max(...nodes.map((n) => n.position.x + n.size.width));
    const maxY = Math.max(...nodes.map((n) => n.position.y + n.size.height));

    const contentW = maxX - minX + 120;
    const contentH = maxY - minY + 120;
    const viewW = state.view.visibleRect.width;
    const viewH = state.view.visibleRect.height;

    const scale = Math.min(viewW / contentW, viewH / contentH, 1);
    return {
      view: {
        ...state.view,
        transform: {
          scale,
          offsetX: (viewW - contentW * scale) / 2 - minX * scale + 60 * scale,
          offsetY: (viewH - contentH * scale) / 2 - minY * scale + 60 * scale,
        },
      },
    };
  }),

  setVisibleRect: (rect) => set((state) => ({
    view: { ...state.view, visibleRect: rect },
  })),

  // ── 选择 ──

  selectNode: (id, multi = false) => set((state) => {
    if (!multi) return { selectedNodeIds: new Set([id]) };
    const next = new Set(state.selectedNodeIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return { selectedNodeIds: next };
  }),

  deselectAll: () => set({ selectedNodeIds: new Set() }),

  setHoveredNode: (id) => set({ hoveredNodeId: id }),

  // ── 查询 ──

  getNode: (id) => get().nodes.get(id),

  getNodesByModule: (moduleId) =>
    Array.from(get().nodes.values()).filter((n) => n.moduleId === moduleId),

  getNodesByChapter: (chapterId) =>
    Array.from(get().nodes.values()).filter((n) => n.chapterId === chapterId),

  getVisibleNodes: () => {
    const { nodes, view } = get();
    const { transform, visibleRect } = view;
    const { scale, offsetX, offsetY } = transform;

    const padded = {
      x: (visibleRect.x - VIEWPORT_PADDING - offsetX) / scale,
      y: (visibleRect.y - VIEWPORT_PADDING - offsetY) / scale,
      width: (visibleRect.width + VIEWPORT_PADDING * 2) / scale,
      height: (visibleRect.height + VIEWPORT_PADDING * 2) / scale,
    };

    return Array.from(nodes.values()).filter((node) =>
      node.position.x < padded.x + padded.width &&
      node.position.x + node.size.width > padded.x &&
      node.position.y < padded.y + padded.height &&
      node.position.y + node.size.height > padded.y,
    );
  },

  getChainNodes: (storyboardId) => {
    const { nodes } = get();
    const result: CanvasNodeData[] = [];
    let current = nodes.get(storyboardId);
    if (!current) return result;
    result.push(current);
    while (current && current.downstreamIds.length > 0) {
      const nextId = current.downstreamIds[0];
      const next = nodes.get(nextId);
      if (!next) break;
      result.push(next);
      current = next;
    }
    return result;
  },

  // ── 执行 ──

  setRunning: (v) => set({ isRunning: v }),

  toggleCollapseAll: () => set((state) => {
    const nextCollapse = !state.collapseAll;
    const nextModules = new Map(state.modules);
    nextModules.forEach((mod, id) => {
      nextModules.set(id, { ...mod, collapsed: nextCollapse });
    });
    return { collapseAll: nextCollapse, modules: nextModules };
  }),

  // ── 重置 ──

  reset: () => set({
    nodes: new Map(),
    connections: [],
    modules: new Map(),
    selectedNodeIds: new Set(),
    hoveredNodeId: null,
    isRunning: false,
    collapseAll: false,
    view: { ...initialView },
  }),
}));
