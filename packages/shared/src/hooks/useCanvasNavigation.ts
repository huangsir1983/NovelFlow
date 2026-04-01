'use client';

import { useCallback } from 'react';
import { useReactFlow } from '@xyflow/react';
import { useCanvasStore } from '../stores/canvasStore';
import { getSceneNodeIds } from '../lib/canvasLayout';

/**
 * Provides three-way navigation linking between the left scene panel,
 * the React Flow canvas, and the right video panel.
 */
export function useCanvasNavigation() {
  const reactFlow = useReactFlow();
  const nodes = useCanvasStore((s) => s.nodes);
  const setFocusedSceneId = useCanvasStore((s) => s.setFocusedSceneId);
  const setInspectedNode = useCanvasStore((s) => s.setInspectedNode);

  /** Navigate canvas + right panel to a scene's nodes */
  const navigateToScene = useCallback(
    (sceneId: string) => {
      setFocusedSceneId(sceneId);

      const sceneNodeIds = getSceneNodeIds(sceneId, nodes);
      if (sceneNodeIds.length === 0) return;

      const sceneNodes = nodes.filter((n) => sceneNodeIds.includes(n.id));
      reactFlow.fitView({
        nodes: sceneNodes,
        padding: 0.3,
        duration: 400,
      });
    },
    [nodes, reactFlow, setFocusedSceneId],
  );

  /** Navigate canvas to center on a specific node */
  const navigateToNode = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;

      setInspectedNode(nodeId);

      const sceneId = (node.data as { sceneId?: string })?.sceneId;
      if (sceneId) setFocusedSceneId(sceneId);

      reactFlow.fitView({
        nodes: [node],
        padding: 0.5,
        duration: 400,
      });
    },
    [nodes, reactFlow, setFocusedSceneId, setInspectedNode],
  );

  return { navigateToScene, navigateToNode };
}
