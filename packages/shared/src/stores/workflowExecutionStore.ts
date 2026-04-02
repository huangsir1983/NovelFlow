'use client';

import { create } from 'zustand';
import type {
  WorkflowExecution,
  WorkflowSSEEvent,
  WorkflowExecutionStatus,
} from '../types/chainWorkflow';
import { fetchAPI } from '../lib/api';

interface WorkflowExecutionStoreState {
  executions: Record<string, WorkflowExecution>;
  activeExecutionId: string | null;

  startExecution: (
    projectId: string,
    workflowId: string,
    templateId: string,
    nodeIds: string[],
  ) => Promise<string>;
  cancelExecution: (executionId: string) => Promise<void>;
  retryExecution: (executionId: string) => Promise<void>;
  resumeExecution: (executionId: string) => Promise<void>;
  fetchExecution: (executionId: string) => Promise<void>;
  updateFromSSE: (event: WorkflowSSEEvent) => void;
  setActiveExecution: (executionId: string | null) => void;
  getExecutionProgress: (executionId: string) => number;
}

export const useWorkflowExecutionStore = create<WorkflowExecutionStoreState>(
  (set, get) => ({
    executions: {},
    activeExecutionId: null,

    startExecution: async (projectId, workflowId, templateId, nodeIds) => {
      const execution = await fetchAPI<WorkflowExecution>(
        `/api/projects/${projectId}/workflow-executions`,
        {
          method: 'POST',
          body: JSON.stringify({ workflowId, templateId, nodeIds }),
        },
      );
      set((s) => ({
        executions: { ...s.executions, [execution.id]: execution },
        activeExecutionId: execution.id,
      }));
      return execution.id;
    },

    cancelExecution: async (executionId) => {
      await fetchAPI(`/api/workflow-executions/${executionId}/cancel`, {
        method: 'POST',
      });
      set((s) => {
        const exec = s.executions[executionId];
        if (!exec) return s;
        return {
          executions: {
            ...s.executions,
            [executionId]: { ...exec, status: 'cancelled' as WorkflowExecutionStatus },
          },
        };
      });
    },

    retryExecution: async (executionId) => {
      const execution = await fetchAPI<WorkflowExecution>(
        `/api/workflow-executions/${executionId}/retry`,
        { method: 'POST' },
      );
      set((s) => ({
        executions: { ...s.executions, [executionId]: execution },
      }));
    },

    resumeExecution: async (executionId) => {
      const execution = await fetchAPI<WorkflowExecution>(
        `/api/workflow-executions/${executionId}/resume`,
        { method: 'POST' },
      );
      set((s) => ({
        executions: { ...s.executions, [executionId]: execution },
      }));
    },

    fetchExecution: async (executionId) => {
      const execution = await fetchAPI<WorkflowExecution>(
        `/api/workflow-executions/${executionId}`,
      );
      set((s) => ({
        executions: { ...s.executions, [executionId]: execution },
      }));
    },

    updateFromSSE: (event) => {
      set((s) => {
        const exec = s.executions[event.executionId];
        if (!exec) return s;

        const updated = { ...exec };

        if (event.status) {
          updated.status = event.status;
        }

        if (event.stepRunId && event.stepId) {
          updated.stepRuns = updated.stepRuns.map((sr) => {
            if (sr.id !== event.stepRunId) return sr;
            return {
              ...sr,
              status: event.status ?? sr.status,
              progress: event.progress ?? sr.progress,
              resultUrl: event.resultUrl ?? sr.resultUrl,
              errorMessage: event.errorMessage ?? sr.errorMessage,
            };
          });

          updated.completedSteps = updated.stepRuns.filter(
            (sr) => sr.status === 'success',
          ).length;
        }

        return { executions: { ...s.executions, [event.executionId]: updated } };
      });
    },

    setActiveExecution: (executionId) => set({ activeExecutionId: executionId }),

    getExecutionProgress: (executionId) => {
      const exec = get().executions[executionId];
      if (!exec || exec.totalSteps === 0) return 0;
      return Math.round((exec.completedSteps / exec.totalSteps) * 100);
    },
  }),
);
