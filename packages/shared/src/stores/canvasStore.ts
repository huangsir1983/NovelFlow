'use client';

import { create } from 'zustand';
import type { Node, Edge, Viewport, NodeChange, EdgeChange } from '@xyflow/react';
import type { SceneGroup, CanvasRenderMode } from '../types/chainWorkflow';
import { API_BASE_URL } from '../lib/api';

// Debounce timers for composite layer persistence (per node)
const _compositeLayerTimers = new Map<string, ReturnType<typeof setTimeout>>();

// Lazy-load to avoid SSR issues (React Flow requires browser environment)
function getXyflowHelpers() {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const xyflow = require('@xyflow/react') as typeof import('@xyflow/react');
  return { applyNodeChanges: xyflow.applyNodeChanges, applyEdgeChanges: xyflow.applyEdgeChanges };
}

interface AIMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  action?: string; // 'assign-modules' | 'analyze-storyboard' | etc.
}

interface CanvasStoreState {
  /* React Flow data */
  nodes: Node[];
  edges: Edge[];
  viewport: Viewport;

  /* Selection */
  selectedNodeIds: string[];
  inspectedNodeId: string | null;

  /* Panels */
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  promptBarExpanded: boolean;
  promptBarContent: string;
  promptBarMode: 'ai' | 'edit';

  /* AI Assistant Panel */
  aiPanelOpen: boolean;
  aiMessages: AIMessage[];
  aiProcessing: boolean;

  /* Navigation */
  focusedSceneId: string | null;

  /* Node position cache — keeps user-dragged positions across rebuilds */
  positionCache: Record<string, { x: number; y: number }>;

  /* Scene-level virtualization */
  sceneGroups: SceneGroup[];
  visibleSceneIds: Set<string>;
  renderMode: CanvasRenderMode;

  /* Edge disconnection — tracks broken pipeline segments per shot */
  disconnectedSegments: Record<string, Set<string>>;

  /* Manual edges — user-created connections via drag, survive graph rebuilds */
  manualEdges: Edge[];

  /* Grid snap & minimap & edge animation */
  snapToGrid: boolean;
  miniMapOpen: boolean;
  edgeFlowAnimation: boolean;

  /* Composite editor */
  compositeEditorOpen: boolean;
  compositeEditorShotId: string | null;

  /* Box selection */
  boxSelectActive: boolean;
  boxSelectRect: { x: number; y: number; w: number; h: number } | null;

  /* 3D Director Stage clipboard */
  stage3DClipboard: {
    sceneId: string;
    stageCharacters: Array<Record<string, unknown>>;
    cameraState?: Record<string, unknown>;
    screenshotBase64?: string;
    screenshotStorageKey?: string;
    characterScreenshots?: Array<Record<string, unknown>>;
  } | null;

  /* Actions */
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  setViewport: (viewport: Viewport) => void;
  selectNodes: (ids: string[]) => void;
  setInspectedNode: (id: string | null) => void;
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
  togglePromptBar: () => void;
  setPromptBarContent: (content: string) => void;
  setPromptBarMode: (mode: 'ai' | 'edit') => void;
  setFocusedSceneId: (sceneId: string | null) => void;
  cacheNodePosition: (nodeId: string, x: number, y: number) => void;
  getCachedPosition: (nodeId: string) => { x: number; y: number } | undefined;

  /* Virtualization actions */
  setSceneGroups: (groups: SceneGroup[]) => void;
  updateVisibleScenes: (visibleIds: Set<string>) => void;
  setRenderMode: (mode: CanvasRenderMode) => void;

  /* Edge disconnection actions */
  disconnectEdge: (shotId: string, segment: string) => void;
  reconnectEdge: (shotId: string, segment: string) => void;
  reconnectAllEdges: (shotId: string) => void;
  isSegmentDisconnected: (shotId: string, segment: string) => boolean;
  hasAnyDisconnected: (shotId: string) => boolean;

  /* Manual edge actions */
  addManualEdge: (edge: Edge) => void;
  removeManualEdge: (edgeId: string) => void;

  /* Grid snap & minimap & edge animation */
  setSnapToGrid: (snap: boolean) => void;
  toggleMiniMap: () => void;
  toggleEdgeFlowAnimation: () => void;

  /* Composite editor actions */
  openCompositeEditor: (shotId: string) => void;
  closeCompositeEditor: () => void;

  /* Downstream cascade reset */
  resetDownstreamNodes: (sourceNodeId: string) => void;

  /* Composite layer persistence */
  persistCompositeLayers: (nodeId: string, layers: Array<Record<string, unknown>>) => void;

  /* Box selection actions */
  setBoxSelectActive: (active: boolean) => void;
  setBoxSelectRect: (rect: { x: number; y: number; w: number; h: number } | null) => void;

  /* 3D Director Stage copy/paste actions */
  copyStage3D: (nodeId: string) => void;
  pasteStage3D: (targetNodeId: string) => boolean;

  /* AI Panel actions */
  toggleAIPanel: () => void;
  setAIPanelOpen: (open: boolean) => void;
  addAIMessage: (msg: AIMessage) => void;
  appendToLastAIMessage: (chunk: string) => void;
  setAIProcessing: (processing: boolean) => void;
  clearAIMessages: () => void;
}

export const useCanvasStore = create<CanvasStoreState>((set, get) => ({
  nodes: [],
  edges: [],
  viewport: { x: 0, y: 0, zoom: 1 },

  selectedNodeIds: [],
  inspectedNodeId: null,

  leftPanelOpen: false,
  rightPanelOpen: false,
  promptBarExpanded: false,
  promptBarContent: '',
  promptBarMode: 'ai',

  focusedSceneId: null,
  positionCache: {},

  sceneGroups: [],
  visibleSceneIds: new Set<string>(),
  renderMode: 'full' as CanvasRenderMode,
  disconnectedSegments: {},
  manualEdges: [],
  snapToGrid: false,
  miniMapOpen: true,
  edgeFlowAnimation: true,

  compositeEditorOpen: false,
  compositeEditorShotId: null,

  boxSelectActive: false,
  boxSelectRect: null,

  stage3DClipboard: null,

  aiPanelOpen: false,
  aiMessages: [],
  aiProcessing: false,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) => {
    const { applyNodeChanges } = getXyflowHelpers();
    const updated = applyNodeChanges(changes, get().nodes);
    // Cache position changes from drag
    for (const change of changes) {
      if (change.type === 'position' && change.position) {
        const cache = { ...get().positionCache };
        cache[change.id] = { x: change.position.x, y: change.position.y };
        set({ positionCache: cache });
      }
    }
    set({ nodes: updated });
  },

  onEdgesChange: (changes) => {
    const { applyEdgeChanges } = getXyflowHelpers();
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  setViewport: (viewport) => set({ viewport }),

  selectNodes: (ids) => set({ selectedNodeIds: ids }),

  setInspectedNode: (id) => set({ inspectedNodeId: id }),

  toggleLeftPanel: () => set((s) => ({ leftPanelOpen: !s.leftPanelOpen })),
  toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
  togglePromptBar: () => set((s) => ({ promptBarExpanded: !s.promptBarExpanded })),

  setPromptBarContent: (content) => set({ promptBarContent: content }),
  setPromptBarMode: (mode) => set({ promptBarMode: mode }),
  setFocusedSceneId: (sceneId) => set({ focusedSceneId: sceneId }),

  cacheNodePosition: (nodeId, x, y) =>
    set((s) => ({ positionCache: { ...s.positionCache, [nodeId]: { x, y } } })),

  getCachedPosition: (nodeId) => get().positionCache[nodeId],

  setSceneGroups: (sceneGroups) => set({ sceneGroups }),
  updateVisibleScenes: (visibleIds) => set({ visibleSceneIds: visibleIds }),
  setRenderMode: (renderMode) => set({ renderMode }),
  disconnectEdge: (shotId, segment) => set((s) => {
    const prev = s.disconnectedSegments[shotId] || new Set<string>();
    const next = new Set(prev);
    next.add(segment);
    return { disconnectedSegments: { ...s.disconnectedSegments, [shotId]: next } };
  }),
  reconnectEdge: (shotId, segment) => set((s) => {
    const prev = s.disconnectedSegments[shotId];
    if (!prev) return s;
    const next = new Set(prev);
    next.delete(segment);
    const updated = { ...s.disconnectedSegments };
    if (next.size === 0) {
      delete updated[shotId];
    } else {
      updated[shotId] = next;
    }
    return { disconnectedSegments: updated };
  }),
  reconnectAllEdges: (shotId) => set((s) => {
    const updated = { ...s.disconnectedSegments };
    delete updated[shotId];
    return { disconnectedSegments: updated };
  }),
  isSegmentDisconnected: (shotId, segment) => {
    const segs = get().disconnectedSegments[shotId];
    return segs ? segs.has(segment) : false;
  },
  hasAnyDisconnected: (shotId) => {
    const segs = get().disconnectedSegments[shotId];
    return segs ? segs.size > 0 : false;
  },

  addManualEdge: (edge) => set((s) => ({
    manualEdges: [...s.manualEdges, edge],
  })),
  removeManualEdge: (edgeId) => set((s) => ({
    manualEdges: s.manualEdges.filter((e) => e.id !== edgeId),
  })),

  setSnapToGrid: (snapToGrid) => set({ snapToGrid }),
  toggleMiniMap: () => set((s) => ({ miniMapOpen: !s.miniMapOpen })),
  toggleEdgeFlowAnimation: () => set((s) => ({ edgeFlowAnimation: !s.edgeFlowAnimation })),

  openCompositeEditor: (shotId) => set({ compositeEditorOpen: true, compositeEditorShotId: shotId }),
  closeCompositeEditor: () => set({ compositeEditorOpen: false, compositeEditorShotId: null }),

  resetDownstreamNodes: (sourceNodeId) => {
    const { nodes, edges } = get();
    // BFS: find all nodes reachable downstream from sourceNodeId
    const visited = new Set<string>();
    const queue: string[] = [];
    for (const e of edges) {
      if (e.source === sourceNodeId && e.type !== 'bypass') {
        if (!visited.has(e.target)) { visited.add(e.target); queue.push(e.target); }
      }
    }
    while (queue.length > 0) {
      const cur = queue.shift()!;
      for (const e of edges) {
        if (e.source === cur && e.type !== 'bypass' && !visited.has(e.target)) {
          visited.add(e.target);
          queue.push(e.target);
        }
      }
    }
    if (visited.size === 0) return;

    set({
      nodes: nodes.map(n => {
        if (!visited.has(n.id)) return n;
        const d = n.data as Record<string, unknown>;
        // Composite: keep layers intact, only reset status
        if (d.nodeType === 'composite') {
          return { ...n, data: { ...d, status: 'idle', progress: 0 } };
        }
        // Other nodes: reset status + clear output (they need re-run)
        return {
          ...n,
          data: {
            ...d,
            status: 'idle',
            progress: 0,
            outputImageUrl: undefined,
            outputPngUrl: undefined,
            outputStorageKey: undefined,
          },
        };
      }),
    });
  },

  persistCompositeLayers: (nodeId, layers) => {
    clearTimeout(_compositeLayerTimers.get(nodeId));
    _compositeLayerTimers.set(nodeId, setTimeout(() => {
      fetch(`${API_BASE_URL}/api/canvas/composite-layers/${nodeId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layers }),
      }).catch(() => {});
    }, 300));
  },

  setBoxSelectActive: (boxSelectActive) => set({ boxSelectActive }),
  setBoxSelectRect: (boxSelectRect) => set({ boxSelectRect }),

  copyStage3D: (nodeId) => {
    const { nodes } = get();
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    const d = node.data as Record<string, unknown>;
    if (d.nodeType !== 'directorStage3D') return;
    set({
      stage3DClipboard: {
        sceneId: d.sceneId as string,
        stageCharacters: JSON.parse(JSON.stringify(d.stageCharacters || [])),
        cameraState: d.cameraState ? JSON.parse(JSON.stringify(d.cameraState)) : undefined,
        screenshotBase64: d.screenshotBase64 as string | undefined,
        screenshotStorageKey: d.screenshotStorageKey as string | undefined,
        characterScreenshots: d.characterScreenshots
          ? JSON.parse(JSON.stringify(d.characterScreenshots))
          : undefined,
      },
    });
  },

  pasteStage3D: (targetNodeId) => {
    const { stage3DClipboard, nodes, edges } = get();
    if (!stage3DClipboard) return false;
    const targetNode = nodes.find(n => n.id === targetNodeId);
    if (!targetNode) return false;
    const td = targetNode.data as Record<string, unknown>;
    if ((td.sceneId as string) !== stage3DClipboard.sceneId) return false;

    // Find upstream CharacterProcess nodes for reference images
    const charProcessDatas: Array<Record<string, unknown>> = [];
    for (const e of edges) {
      if (e.target !== targetNodeId) continue;
      const upstream = nodes.find(n => n.id === e.source);
      if (upstream && (upstream.data as Record<string, unknown>).nodeType === 'characterProcess') {
        charProcessDatas.push(upstream.data as Record<string, unknown>);
      }
    }

    set({
      nodes: nodes.map(n => {
        if (n.id === targetNodeId) {
          const d = { ...n.data } as Record<string, unknown>;
          d.stageCharacters = JSON.parse(JSON.stringify(stage3DClipboard.stageCharacters));
          d.cameraState = stage3DClipboard.cameraState
            ? JSON.parse(JSON.stringify(stage3DClipboard.cameraState))
            : undefined;
          // Copy source screenshot as initial preview
          d.screenshotBase64 = stage3DClipboard.screenshotBase64;
          d.screenshotStorageKey = stage3DClipboard.screenshotStorageKey;
          d.characterScreenshots = stage3DClipboard.characterScreenshots
            ? JSON.parse(JSON.stringify(stage3DClipboard.characterScreenshots))
            : undefined;
          return { ...n, data: d };
        }

        // Propagate to downstream GeminiComposite nodes
        const downEdge = edges.find(e => e.source === targetNodeId && e.target === n.id);
        if (downEdge && (n.data as Record<string, unknown>).nodeType === 'geminiComposite'
            && stage3DClipboard.screenshotBase64) {
          const charScreenshots = (stage3DClipboard.characterScreenshots || []) as Array<Record<string, unknown>>;
          const mappings = charScreenshots.map(cs => {
            const cpData = charProcessDatas.find(
              cp => cp.characterName === cs.stageCharName,
            );
            return {
              stageCharId: cs.stageCharId,
              stageCharName: cs.stageCharName,
              color: cs.color,
              poseScreenshot: cs.screenshot,
              bbox: cs.bbox,
              referenceImageUrl: cpData?.visualRefUrl,
              referenceStorageKey: cpData?.visualRefStorageKey,
            };
          });
          return {
            ...n,
            data: {
              ...n.data,
              sceneScreenshotBase64: stage3DClipboard.screenshotBase64,
              characterMappings: mappings,
              status: 'idle',
            },
          };
        }

        return n;
      }),
    });
    return true;
  },

  toggleAIPanel: () => set((s) => ({ aiPanelOpen: !s.aiPanelOpen })),
  setAIPanelOpen: (open) => set({ aiPanelOpen: open }),
  addAIMessage: (msg) => set((s) => ({ aiMessages: [...s.aiMessages, msg] })),
  appendToLastAIMessage: (chunk) => set((s) => {
    const msgs = [...s.aiMessages];
    if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], content: msgs[msgs.length - 1].content + chunk };
    }
    return { aiMessages: msgs };
  }),
  setAIProcessing: (aiProcessing) => set({ aiProcessing }),
  clearAIMessages: () => set({ aiMessages: [] }),
}));
