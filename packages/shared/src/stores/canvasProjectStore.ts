'use client';

// ══════════════════════════════════════════════════════════════
// canvasProjectStore.ts — 画布项目资产与分镜链状态
// ══════════════════════════════════════════════════════════════

import { create } from 'zustand';
import type {
  CanvasProjectAsset,
  CanvasChapter,
  CanvasScene,
  CanvasStoryboardChain,
  CanvasExecutionPlan,
} from '../types/canvas';

interface CanvasProjectStore {
  projectId: string;
  projectName: string;
  novelTitle: string;

  assets: Map<string, CanvasProjectAsset>;
  characterIds: string[];
  sceneIds: string[];
  propIds: string[];

  chapters: CanvasChapter[];
  scenes: Map<string, CanvasScene>;

  chains: Map<string, CanvasStoryboardChain>;
  currentPlan: CanvasExecutionPlan | null;

  loadProjectData: (data: {
    projectId: string;
    projectName: string;
    novelTitle: string;
    assets: CanvasProjectAsset[];
    chapters: CanvasChapter[];
    scenes: CanvasScene[];
  }) => void;
  addAsset: (asset: CanvasProjectAsset) => void;
  updateChain: (chainId: string, patch: Partial<CanvasStoryboardChain>) => void;
  addChain: (chain: CanvasStoryboardChain) => void;
  setExecutionPlan: (plan: CanvasExecutionPlan | null) => void;
  getAssetsByType: (type: 'character' | 'scene' | 'prop') => CanvasProjectAsset[];
  getChainByStoryboardId: (storyboardId: string) => CanvasStoryboardChain | undefined;
  reset: () => void;
}

export const useCanvasProjectStore = create<CanvasProjectStore>((set, get) => ({
  projectId: '',
  projectName: '',
  novelTitle: '',
  assets: new Map(),
  characterIds: [],
  sceneIds: [],
  propIds: [],
  chapters: [],
  scenes: new Map(),
  chains: new Map(),
  currentPlan: null,

  loadProjectData: (data) => {
    const assets = new Map<string, CanvasProjectAsset>();
    const characterIds: string[] = [];
    const sceneIds: string[] = [];
    const propIds: string[] = [];
    for (const asset of data.assets) {
      assets.set(asset.id, asset);
      if (asset.type === 'character') characterIds.push(asset.id);
      else if (asset.type === 'scene') sceneIds.push(asset.id);
      else if (asset.type === 'prop') propIds.push(asset.id);
    }
    const scenes = new Map<string, CanvasScene>();
    for (const scene of data.scenes) scenes.set(scene.id, scene);

    set({
      projectId: data.projectId,
      projectName: data.projectName,
      novelTitle: data.novelTitle,
      assets,
      characterIds,
      sceneIds,
      propIds,
      chapters: data.chapters,
      scenes,
    });
  },

  addAsset: (asset) => set((state) => {
    const next = new Map(state.assets);
    next.set(asset.id, asset);
    return { assets: next };
  }),

  updateChain: (chainId, patch) => set((state) => {
    const chain = state.chains.get(chainId);
    if (!chain) return state;
    const next = new Map(state.chains);
    next.set(chainId, { ...chain, ...patch });
    return { chains: next };
  }),

  addChain: (chain) => set((state) => {
    const next = new Map(state.chains);
    next.set(chain.id, chain);
    return { chains: next };
  }),

  setExecutionPlan: (plan) => set({ currentPlan: plan }),

  getAssetsByType: (type) =>
    Array.from(get().assets.values()).filter((a) => a.type === type),

  getChainByStoryboardId: (storyboardId) =>
    Array.from(get().chains.values()).find((c) => c.nodeIds[0] === storyboardId),

  reset: () => set({
    projectId: '',
    projectName: '',
    novelTitle: '',
    assets: new Map(),
    characterIds: [],
    sceneIds: [],
    propIds: [],
    chapters: [],
    scenes: new Map(),
    chains: new Map(),
    currentPlan: null,
  }),
}));
