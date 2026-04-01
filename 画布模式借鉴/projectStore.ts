// ============================================================
// projectStore.ts - 项目资产 & 章节数据状态
// ============================================================
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { ProjectAsset, Chapter, Scene, StoryboardChain, ExecutionPlan } from '../types';

interface ProjectStore {
  // 项目基本信息
  projectId: string;
  projectName: string;
  novelTitle: string;

  // 资产库（来自前置环节）
  assets: Map<string, ProjectAsset>;
  characterIds: string[];
  sceneIds: string[];
  propIds: string[];

  // 结构数据（来自前置环节）
  chapters: Chapter[];
  scenes: Map<string, Scene>;

  // 分镜链
  chains: Map<string, StoryboardChain>;

  // 执行计划
  currentPlan: ExecutionPlan | null;

  // Actions
  loadProjectData: (data: {
    projectId: string;
    projectName: string;
    novelTitle: string;
    assets: ProjectAsset[];
    chapters: Chapter[];
    scenes: Scene[];
  }) => void;
  addAsset: (asset: ProjectAsset) => void;
  updateChain: (chainId: string, patch: Partial<StoryboardChain>) => void;
  addChain: (chain: StoryboardChain) => void;
  setExecutionPlan: (plan: ExecutionPlan | null) => void;
  getAssetsByType: (type: 'character' | 'scene' | 'prop') => ProjectAsset[];
  getChainByStoryboardId: (storyboardId: string) => StoryboardChain | undefined;
}

export const useProjectStore = create<ProjectStore>()(
  immer((set, get) => ({
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

    loadProjectData: (data) => set(state => {
      state.projectId = data.projectId;
      state.projectName = data.projectName;
      state.novelTitle = data.novelTitle;

      // 加载资产
      data.assets.forEach(asset => {
        state.assets.set(asset.id, asset);
        if (asset.type === 'character') state.characterIds.push(asset.id);
        else if (asset.type === 'scene') state.sceneIds.push(asset.id);
        else if (asset.type === 'prop') state.propIds.push(asset.id);
      });

      // 加载结构
      state.chapters = data.chapters;
      data.scenes.forEach(scene => state.scenes.set(scene.id, scene));
    }),

    addAsset: (asset) => set(state => {
      state.assets.set(asset.id, asset);
    }),

    updateChain: (chainId, patch) => set(state => {
      const chain = state.chains.get(chainId);
      if (chain) Object.assign(chain, patch);
    }),

    addChain: (chain) => set(state => {
      state.chains.set(chain.id, chain);
    }),

    setExecutionPlan: (plan) => set(state => {
      state.currentPlan = plan;
    }),

    getAssetsByType: (type) => {
      return Array.from(get().assets.values()).filter(a => a.type === type);
    },

    getChainByStoryboardId: (storyboardId) => {
      return Array.from(get().chains.values()).find(
        c => c.nodeIds[0] === storyboardId
      );
    },
  }))
);


// ============================================================
// agentStore.ts - Agent任务队列状态
// ============================================================
import { AgentTask, AgentTaskType } from '../types';

interface AgentStore {
  tasks: AgentTask[];
  isAgentRunning: boolean;
  concurrentLimit: number;  // 最大并发任务数

  // Actions
  enqueueTask: (type: AgentTaskType, payload: Record<string, unknown>, nodeId?: string) => string;
  updateTask: (id: string, patch: Partial<AgentTask>) => void;
  clearCompletedTasks: () => void;
  getRunningTasks: () => AgentTask[];
  getQueuedTasks: () => AgentTask[];
  setAgentRunning: (v: boolean) => void;
}

export const useAgentStore = create<AgentStore>()(
  immer((set, get) => ({
    tasks: [],
    isAgentRunning: false,
    concurrentLimit: 3,

    enqueueTask: (type, payload, nodeId) => {
      const id = `task_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
      const task: AgentTask = {
        id,
        type,
        status: 'queued',
        nodeId,
        payload,
        createdAt: Date.now(),
        retryCount: 0,
      };
      set(state => { state.tasks.push(task); });
      return id;
    },

    updateTask: (id, patch) => set(state => {
      const task = state.tasks.find(t => t.id === id);
      if (task) Object.assign(task, patch);
    }),

    clearCompletedTasks: () => set(state => {
      state.tasks = state.tasks.filter(t => t.status !== 'done');
    }),

    getRunningTasks: () => get().tasks.filter(t => t.status === 'running'),
    getQueuedTasks: () => get().tasks.filter(t => t.status === 'queued'),

    setAgentRunning: (v) => set(state => { state.isAgentRunning = v; }),
  }))
);
