'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useWorkflowExecutionStore } from '../stores/workflowExecutionStore';
import { useCanvasStore } from '../stores/canvasStore';
import type { WorkflowSSEEvent, WorkflowExecutionStatus } from '../types';

const API_BASE_URL = 'http://localhost:8000';

/**
 * Hook to subscribe to workflow execution SSE events and sync canvas node status.
 */
export function useWorkflowExecution(executionId: string | null) {
  const store = useWorkflowExecutionStore();
  const eventSourceRef = useRef<EventSource | null>(null);

  const execution = executionId ? store.executions[executionId] : null;
  const isRunning = execution?.status === 'running' || execution?.status === 'queued';
  const progress = executionId ? store.getExecutionProgress(executionId) : 0;

  // Connect / disconnect SSE
  useEffect(() => {
    if (!executionId || !isRunning) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    const es = new EventSource(
      `${API_BASE_URL}/api/workflow-executions/${executionId}/events`,
    );
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'progress' && data.execution) {
          // Full state update from polling SSE
          const exec = data.execution;
          const stepRuns = data.stepRuns || [];
          store.updateFromSSE({
            type: 'step_progress',
            executionId: exec.id,
            status: exec.status,
            timestamp: new Date().toISOString(),
          });

          // Sync canvas node statuses
          syncNodeStatuses(exec.targetNodeIds, exec.status, stepRuns);
        }

        if (data.type === 'done') {
          es.close();
          eventSourceRef.current = null;
          // Final fetch to get complete state
          store.fetchExecution(executionId);
        }
      } catch {
        // Ignore parse errors
      }
    };

    es.onerror = () => {
      // Reconnect on error — EventSource auto-reconnects, but close on terminal state
      if (eventSourceRef.current) {
        store.fetchExecution(executionId).then(() => {
          const exec = store.executions[executionId];
          if (exec && ['success', 'error', 'cancelled'].includes(exec.status)) {
            eventSourceRef.current?.close();
            eventSourceRef.current = null;
          }
        });
      }
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [executionId, isRunning]);

  const cancel = useCallback(async () => {
    if (executionId) await store.cancelExecution(executionId);
  }, [executionId, store]);

  const retry = useCallback(async () => {
    if (executionId) await store.retryExecution(executionId);
  }, [executionId, store]);

  const resume = useCallback(async () => {
    if (executionId) await store.resumeExecution(executionId);
  }, [executionId, store]);

  return {
    execution,
    stepRuns: execution?.stepRuns ?? [],
    progress,
    isRunning,
    isPaused: execution?.status === 'paused',
    isError: execution?.status === 'error',
    isSuccess: execution?.status === 'success',
    cancel,
    retry,
    resume,
  };
}

/**
 * Map execution status to canvas node status and update canvasStore.
 */
function syncNodeStatuses(
  targetNodeIds: string[] | undefined,
  executionStatus: WorkflowExecutionStatus,
  stepRuns: Array<{ status: string }>,
) {
  if (!targetNodeIds?.length) return;

  const canvasStore = useCanvasStore.getState();
  const nodes = canvasStore.nodes;
  let changed = false;

  const newNodes = nodes.map((node) => {
    if (!targetNodeIds.includes(node.id)) return node;

    let newStatus: string;
    switch (executionStatus) {
      case 'running':
      case 'queued':
        newStatus = 'running';
        break;
      case 'success':
        newStatus = 'success';
        break;
      case 'error':
        newStatus = 'error';
        break;
      case 'paused':
        newStatus = 'queued';
        break;
      default:
        return node;
    }

    const currentStatus = (node.data as Record<string, unknown>).status;
    if (currentStatus === newStatus) return node;

    changed = true;
    return {
      ...node,
      data: { ...node.data, status: newStatus },
    };
  });

  if (changed) {
    canvasStore.setNodes(newNodes);
  }
}
