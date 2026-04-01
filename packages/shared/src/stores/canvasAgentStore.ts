'use client';

// ══════════════════════════════════════════════════════════════
// canvasAgentStore.ts — Agent 任务队列状态管理
// ══════════════════════════════════════════════════════════════

import { create } from 'zustand';
import type { CanvasAgentTask, CanvasAgentTaskType } from '../types/canvas';

interface CanvasAgentStore {
  tasks: CanvasAgentTask[];
  isAgentRunning: boolean;
  concurrentLimit: number;

  enqueueTask: (type: CanvasAgentTaskType, payload: Record<string, unknown>, nodeId?: string) => string;
  updateTask: (id: string, patch: Partial<CanvasAgentTask>) => void;
  clearCompletedTasks: () => void;
  getRunningTasks: () => CanvasAgentTask[];
  getQueuedTasks: () => CanvasAgentTask[];
  setAgentRunning: (v: boolean) => void;
  reset: () => void;
}

export const useCanvasAgentStore = create<CanvasAgentStore>((set, get) => ({
  tasks: [],
  isAgentRunning: false,
  concurrentLimit: 3,

  enqueueTask: (type, payload, nodeId) => {
    const id = `task_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const task: CanvasAgentTask = {
      id,
      type,
      status: 'queued',
      nodeId,
      payload,
      createdAt: Date.now(),
      retryCount: 0,
    };
    set((state) => ({ tasks: [...state.tasks, task] }));
    return id;
  },

  updateTask: (id, patch) => set((state) => ({
    tasks: state.tasks.map((t) => (t.id === id ? { ...t, ...patch } : t)),
  })),

  clearCompletedTasks: () => set((state) => ({
    tasks: state.tasks.filter((t) => t.status !== 'done'),
  })),

  getRunningTasks: () => get().tasks.filter((t) => t.status === 'running'),

  getQueuedTasks: () => get().tasks.filter((t) => t.status === 'queued'),

  setAgentRunning: (v) => set({ isAgentRunning: v }),

  reset: () => set({ tasks: [], isAgentRunning: false }),
}));
