'use client';

import { useCallback } from 'react';
import { useCanvasStore } from '../stores/canvasStore';
import { useProjectStore } from '../stores/projectStore';
import { API_BASE_URL } from '../lib/api';

/**
 * Provides node execution capabilities for the canvas.
 * Calls backend APIs and updates node status via SSE events.
 * Supports imageProcess unified node type dispatching to RunningHub/Gemini.
 */
export function useNodeExecution() {
  const setNodes = useCanvasStore((s) => s.setNodes);
  const projectId = useProjectStore((s) => s.project?.id);

  /** Update a single node's data fields */
  const updateNode = useCallback((nodeId: string, patch: Record<string, unknown>) => {
    const nodes = useCanvasStore.getState().nodes;
    setNodes(
      nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n,
      ),
    );
  }, [setNodes]);

  /** Propagate output to downstream nodes along edges + auto-fill composite layers */
  const propagateOutput = useCallback((sourceNodeId: string, outputUrl?: string, outputKey?: string) => {
    if (!outputUrl && !outputKey) return;
    const { edges, nodes } = useCanvasStore.getState();
    const downstream = edges.filter(e => e.source === sourceNodeId);
    if (downstream.length === 0) return;

    const targetIds = new Set(downstream.map(e => e.target));
    let updatedNodes = nodes.map(n => {
      if (!targetIds.has(n.id)) return n;
      return {
        ...n,
        data: {
          ...n.data,
          inputImageUrl: outputUrl || (n.data as Record<string, unknown>).inputImageUrl,
          inputStorageKey: outputKey || (n.data as Record<string, unknown>).inputStorageKey,
        },
      };
    });

    // Upsert this source's layer into downstream composite nodes
    for (const targetId of targetIds) {
      const targetNode = updatedNodes.find(n => n.id === targetId);
      if (!targetNode || (targetNode.data as Record<string, unknown>).nodeType !== 'composite') continue;

      const compData = targetNode.data as Record<string, unknown>;
      const existingLayers = ((compData.layers || []) as Array<Record<string, unknown>>).slice();

      // Determine layer type for this source
      const srcNode = updatedNodes.find(n => n.id === sourceNodeId);
      const srcData = srcNode?.data as Record<string, unknown> | undefined;
      const nodeType = (srcData?.nodeType || '') as string;
      const processType = (srcData?.processType || '') as string;
      const isBgUpscale = nodeType === 'imageProcess' && processType === 'hdUpscale'
        && edges.some(e => e.target === sourceNodeId && e.source.startsWith('scenebg-'));
      const layerType = (nodeType === 'sceneBG' || isBgUpscale) ? 'background' : 'character';

      const imgUrl = outputUrl || (srcData?.outputPngUrl || srcData?.outputImageUrl) as string | undefined;
      if (!imgUrl) continue;

      const layerIdx = existingLayers.findIndex(l => l.sourceNodeId === sourceNodeId);
      const newLayer = {
        id: sourceNodeId,
        type: layerType,
        sourceNodeId,
        imageUrl: imgUrl,
        x: layerType === 'background' ? 0 : (1920 - 600) / 2,
        y: 0,
        width: layerType === 'background' ? 1920 : 600,
        height: 1080,
        rotation: 0,
        zIndex: layerType === 'background' ? 0 : existingLayers.length,
        opacity: 1,
        visible: true,
        flipX: false,
      };

      if (layerIdx >= 0) {
        // Update only imageUrl, keep user adjustments (position, size, etc.)
        existingLayers[layerIdx] = { ...existingLayers[layerIdx], imageUrl: imgUrl };
      } else {
        existingLayers.push(newLayer);
      }

      updatedNodes = updatedNodes.map(n =>
        n.id === targetId
          ? { ...n, data: { ...n.data, layers: existingLayers, outputImageUrl: undefined } }
          : n,
      );

      // Persist updated composite layers to backend
      useCanvasStore.getState().persistCompositeLayers(targetId, existingLayers);
    }

    setNodes(updatedNodes);
  }, [setNodes]);

  /** Run a single node by ID */
  const runNode = useCallback(
    async (nodeId: string) => {
      const nodes = useCanvasStore.getState().nodes;
      const node = nodes.find((n) => n.id === nodeId);
      if (!node || !projectId) return;

      const data = node.data as Record<string, unknown>;
      const nodeType = data.nodeType as string | undefined;
      if (!data.shotId) return;

      // Reset all downstream nodes' green dots before this node runs
      useCanvasStore.getState().resetDownstreamNodes(nodeId);

      // Set node status to queued
      updateNode(nodeId, { status: 'queued' });

      try {
        let endpoint = '';
        let body: Record<string, unknown> = {};

        if (nodeType === 'imageGeneration') {
          endpoint = `${API_BASE_URL}/api/projects/${projectId}/shots/${data.shotId}/generate/image`;
          body = { gen_type: 'image' };
        } else if (nodeType === 'videoGeneration') {
          endpoint = `${API_BASE_URL}/api/projects/${projectId}/shots/${data.shotId}/generate/video`;
          body = { gen_type: 'video' };
        } else if (nodeType === 'imageProcess') {
          endpoint = `${API_BASE_URL}/api/canvas/nodes/${nodeId}/execute`;
          body = {
            node_type: 'imageProcess',
            content: {
              processType: data.processType,
              inputStorageKey: data.inputStorageKey,
              inputImageUrl: data.inputImageUrl,
              targetAngle: data.targetAngle,
              azimuth: data.azimuth,
              elevation: data.elevation,
              distance: data.distance,
              expressionPrompt: data.expressionPrompt,
              emotion: data.emotion,
              action: data.action,
              scaleFactor: data.scaleFactor,
            },
          };
        } else if (nodeType && ['sceneBG', 'characterProcess', 'propProcess', 'composite',
            'blendRefine', 'lighting', 'finalHD'].includes(nodeType)) {
          endpoint = `${API_BASE_URL}/api/canvas/nodes/${nodeId}/execute`;
          body = {
            node_type: nodeType,
            content: {
              inputImageUrl: data.inputImageUrl,
              inputStorageKey: data.inputStorageKey,
            },
          };
        } else {
          // For unknown nodes, just mark as success
          updateNode(nodeId, { status: 'success' });
          return;
        }

        // Update to running
        updateNode(nodeId, { status: 'running', progress: 0 });

        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          const errText = await response.text().catch(() => '');
          throw new Error(`API error: ${response.status} ${errText}`);
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
                    updateNode(nodeId, { progress: event.progress });
                  }
                  if (event.status === 'completed' || event.status === 'success') {
                    updateNode(nodeId, { status: 'success', progress: 100 });
                  }
                } catch {
                  // Ignore malformed SSE data
                }
              }
            }
          }
        } else {
          // JSON response — extract output and update node
          const result = await response.json();
          const output = result.result || {};

          let outputUrl = output.outputImageUrl || output.outputImageBase64
            ? (output.outputImageBase64 ? `data:image/png;base64,${output.outputImageBase64}` : output.outputImageUrl)
            : undefined;
          const outputKey = output.outputStorageKey;
          // Construct display URL from storageKey when no direct URL returned
          if (!outputUrl && outputKey) {
            outputUrl = `${API_BASE_URL}/uploads/${outputKey}`;
          }
          const outputPng = output.outputPngUrl || (outputKey?.endsWith('.png')
            ? `${API_BASE_URL}/uploads/${outputKey}` : undefined);

          // BlendRefine: store result as preview — user must confirm before propagation
          if (nodeType === 'blendRefine') {
            updateNode(nodeId, {
              status: 'success',
              progress: 100,
              previewImageUrl: outputUrl,
              confirmed: false,
              ...(outputKey ? { outputStorageKey: outputKey } : {}),
              ...(output.runninghubTaskId ? { runninghubTaskId: output.runninghubTaskId } : {}),
            });
          } else {
            updateNode(nodeId, {
              status: 'success',
              progress: 100,
              ...(outputUrl ? { outputImageUrl: outputUrl } : {}),
              ...(outputKey ? { outputStorageKey: outputKey } : {}),
              ...(outputPng ? { outputPngUrl: outputPng } : {}),
              ...(output.runninghubTaskId ? { runninghubTaskId: output.runninghubTaskId } : {}),
            });

            // Propagate output to downstream nodes
            propagateOutput(nodeId, outputUrl, outputKey);
          }
        }
      } catch (err) {
        updateNode(nodeId, {
          status: 'error',
          errorMessage: err instanceof Error ? err.message : 'Unknown error',
        });
      }
    },
    [projectId, updateNode, propagateOutput],
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
      updateNode(nodeId, { status: 'idle', progress: 0 });
    },
    [updateNode],
  );

  return { runNode, runFromNode, cancelRun, propagateOutput };
}
