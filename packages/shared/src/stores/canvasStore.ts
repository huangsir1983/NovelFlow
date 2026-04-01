'use client';

import { create } from 'zustand';
import type { Node, Edge, Viewport, NodeChange, EdgeChange } from '@xyflow/react';

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
