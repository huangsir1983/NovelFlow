'use client';

import { create } from 'zustand';
import type { DebugMetric, NodeExecution, PipelineRun, PipelineRunStatus } from '../types/pipeline';

interface PipelineStoreState {
  runs: Record<string, PipelineRun>;
  activeRunId: string | null;

  setActiveRunId: (runId: string | null) => void;
  upsertRun: (run: PipelineRun) => void;
  setRunStatus: (runId: string, status: PipelineRunStatus) => void;
  updateNodeExecution: (runId: string, node: NodeExecution) => void;
  appendDebugMetric: (runId: string, metric: DebugMetric) => void;
  reset: () => void;
}

const initialState = {
  runs: {},
  activeRunId: null,
};

export const usePipelineStore = create<PipelineStoreState>((set) => ({
  ...initialState,

  setActiveRunId: (activeRunId) => set({ activeRunId }),
  upsertRun: (run) =>
    set((state) => ({
      runs: {
        ...state.runs,
        [run.id]: run,
      },
    })),
  setRunStatus: (runId, status) =>
    set((state) => {
      const target = state.runs[runId];
      if (!target) {
        return state;
      }
      return {
        runs: {
          ...state.runs,
          [runId]: {
            ...target,
            status,
            updated_at: new Date().toISOString(),
          },
        },
      };
    }),
  updateNodeExecution: (runId, node) =>
    set((state) => {
      const target = state.runs[runId];
      if (!target) {
        return state;
      }
      const idx = target.nodes.findIndex((existing) => existing.node_id === node.node_id);
      const nextNodes =
        idx === -1
          ? [...target.nodes, node]
          : target.nodes.map((existing, i) => (i === idx ? node : existing));

      return {
        runs: {
          ...state.runs,
          [runId]: {
            ...target,
            nodes: nextNodes,
            updated_at: new Date().toISOString(),
          },
        },
      };
    }),
  appendDebugMetric: (runId, metric) =>
    set((state) => {
      const target = state.runs[runId];
      if (!target) {
        return state;
      }
      return {
        runs: {
          ...state.runs,
          [runId]: {
            ...target,
            debug_metrics: [...target.debug_metrics, metric],
            updated_at: new Date().toISOString(),
          },
        },
      };
    }),
  reset: () => set(initialState),
}));
