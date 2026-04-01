'use client';

import { useCallback } from 'react';
import { useCanvasStore } from '../stores/canvasStore';
import { useBoardStore } from '../stores/boardStore';
import { useProjectStore } from '../stores/projectStore';

/**
 * Provides node execution capabilities for the canvas.
 * Calls backend APIs and updates node status via SSE events.
 */
export function useNodeExecution() {
  const nodes = useCanvasStore((s) => s.nodes);
  const setNodes = useCanvasStore((s) => s.setNodes);
  const projectId = useProjectStore((s) => s.project?.id);

  /** Run a single node by ID */
  const runNode = useCallback(
    async (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node || !projectId) return;

      const data = node.data as { shotId?: string; nodeType?: string };
      if (!data.shotId) return;

      // Set node status to queued
      setNodes(
        nodes.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, status: 'queued' } }
            : n,
        ),
      );

      try {
        // Map node type to API endpoint
        const nodeType = data.nodeType;
        let endpoint = '';
        let genType = '';

        if (nodeType === 'imageGeneration') {
          endpoint = `/api/projects/${projectId}/shots/${data.shotId}/generate/image`;
          genType = 'image';
        } else if (nodeType === 'videoGeneration') {
          endpoint = `/api/projects/${projectId}/shots/${data.shotId}/generate/video`;
          genType = 'video';
        } else {
          // For non-generation nodes, just mark as success
          setNodes(
            nodes.map((n) =>
              n.id === nodeId
                ? { ...n, data: { ...n.data, status: 'success' } }
                : n,
            ),
          );
          return;
        }

        // Update to running
        setNodes(
          nodes.map((n) =>
            n.id === nodeId
              ? { ...n, data: { ...n.data, status: 'running', progress: 0 } }
              : n,
          ),
        );

        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ gen_type: genType }),
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.status}`);
        }

        // Handle SSE stream
        if (response.headers.get('content-type')?.includes('text/event-stream')) {
          const reader = response.body?.getReader();
          if (!reader) throw new Error('No response body');

          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const event = JSON.parse(line.slice(6));
                  if (event.progress !== undefined) {
                    setNodes(
                      nodes.map((n) =>
                        n.id === nodeId
                          ? { ...n, data: { ...n.data, progress: event.progress } }
                          : n,
                      ),
                    );
                  }
                  if (event.status === 'completed' || event.status === 'success') {
                    setNodes(
                      nodes.map((n) =>
                        n.id === nodeId
                          ? { ...n, data: { ...n.data, status: 'success', progress: 100 } }
                          : n,
                      ),
                    );
                  }
                } catch {
                  // Ignore malformed SSE data
                }
              }
            }
          }
        } else {
          // Non-SSE response — mark as success
          setNodes(
            nodes.map((n) =>
              n.id === nodeId
                ? { ...n, data: { ...n.data, status: 'success', progress: 100 } }
                : n,
            ),
          );
        }
      } catch (err) {
        setNodes(
          nodes.map((n) =>
            n.id === nodeId
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    status: 'error',
                    errorMessage: err instanceof Error ? err.message : 'Unknown error',
                  },
                }
              : n,
          ),
        );
      }
    },
    [nodes, setNodes, projectId],
  );

  /** Run from a node forward (this node + all downstream) */
  const runFromNode = useCallback(
    async (nodeId: string) => {
      // TODO: topological sort + sequential execution
      await runNode(nodeId);
    },
    [runNode],
  );

  /** Cancel a running node */
  const cancelRun = useCallback(
    (nodeId: string) => {
      setNodes(
        nodes.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, status: 'idle', progress: 0 } }
            : n,
        ),
      );
    },
    [nodes, setNodes],
  );

  return { runNode, runFromNode, cancelRun };
}
