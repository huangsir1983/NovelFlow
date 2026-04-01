'use client';

import { useEffect, useRef } from 'react';
import { useProjectStore } from '../stores/projectStore';
import { useBoardStore } from '../stores/boardStore';
import { useCanvasStore } from '../stores/canvasStore';
import { buildCanvasGraph, type SceneInput, type ShotInput } from '../lib/canvasLayout';

/**
 * Syncs domain data (scenes/shots from projectStore + production state from boardStore)
 * into React Flow nodes/edges in canvasStore.
 *
 * IMPORTANT: Only rebuilds when domain data actually changes (scene/shot IDs or run/artifact keys).
 * Does NOT re-run on canvas UI interactions (clicks, drags, selections).
 * Reads positionCache at build time via store.getState() to avoid re-triggering.
 */
export function useCanvasSync() {
  const scenes = useProjectStore((s) => s.scenes);
  const shots = useProjectStore((s) => s.shots);
  const nodeRunsByShotId = useBoardStore((s) => s.nodeRunsByShotId);
  const artifactsByShotId = useBoardStore((s) => s.artifactsByShotId);

  const prevHashRef = useRef('');
  const initializedRef = useRef(false);

  useEffect(() => {
    // Build a hash of domain data only — canvas UI state is excluded
    const hash = JSON.stringify({
      sceneCount: scenes.length,
      sceneIds: scenes.map((s) => s.id).join(','),
      shotCount: shots.length,
      shotIds: shots.map((s) => s.id).join(','),
      runKeys: Object.keys(nodeRunsByShotId).sort().join(','),
      artKeys: Object.keys(artifactsByShotId).sort().join(','),
    });

    if (hash === prevHashRef.current) return;
    prevHashRef.current = hash;

    // Read positionCache from store directly (not as a reactive dependency)
    const { positionCache, setNodes, setEdges } = useCanvasStore.getState();

    const sceneInputs: SceneInput[] = scenes.map((s) => ({
      id: s.id,
      heading: s.heading || '',
      location: s.location || '',
      timeOfDay: s.time_of_day || '',
      description: s.description || '',
      characterNames: (s.characters_present || []) as string[],
      order: s.order ?? 0,
    }));

    const shotInputs: ShotInput[] = shots.map((s) => ({
      id: s.id,
      sceneId: s.scene_id || '',
      shotNumber: s.shot_number || 0,
      framing: s.framing || '',
      cameraAngle: s.camera_angle || '',
      cameraMovement: s.camera_movement || '',
      description: s.description || '',
      thumbnailUrl: undefined,
      visualPrompt: s.visual_prompt || '',
    }));

    const { nodes, edges } = buildCanvasGraph(sceneInputs, shotInputs, {
      positionCache,
      artifactsByShotId: Object.fromEntries(
        Object.entries(artifactsByShotId).map(([k, v]) => [
          k,
          (v || []).map((a) => ({
            id: a.id || '',
            type: a.type || '',
            url: a.thumbnailText || undefined,
            status: a.status || 'draft',
          })),
        ]),
      ),
      nodeRunsByShotId: Object.fromEntries(
        Object.entries(nodeRunsByShotId).map(([k, v]) => [
          k,
          (v || []).map((r) => ({
            nodeKey: r.kind || '',
            status: r.status === 'succeeded' ? 'success' : r.status === 'failed' ? 'error' : r.status || 'idle',
            progress: undefined,
          })),
        ]),
      ),
    });

    setNodes(nodes);
    setEdges(edges);
    initializedRef.current = true;
  }, [scenes, shots, nodeRunsByShotId, artifactsByShotId]);
}
