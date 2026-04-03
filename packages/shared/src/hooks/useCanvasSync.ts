'use client';

import { useEffect, useRef } from 'react';
import type { Edge } from '@xyflow/react';
import { useProjectStore } from '../stores/projectStore';
import { useBoardStore } from '../stores/boardStore';
import { useCanvasStore } from '../stores/canvasStore';
import { buildCanvasGraph, type SceneInput, type ShotInput, shotNodeId, videoNodeId } from '../lib/canvasLayout';

/**
 * Apply disconnection state to raw edges: filter out broken segments, inject bypass edges.
 * Also merges in any user-created manual edges.
 */
function applyDisconnections(
  rawEdges: Edge[],
  manualEdges: Edge[],
  disconnectedSegments: Record<string, Set<string>>,
): Edge[] {
  const disconnectedShotIds = Object.keys(disconnectedSegments);

  // Start with raw pipeline edges, filtering out disconnected segments
  let result: Edge[];
  if (disconnectedShotIds.length === 0) {
    result = [...rawEdges];
  } else {
    result = rawEdges.filter((e) => {
      const edgeData = e.data as { shotId?: string; segment?: string } | undefined;
      if (!edgeData?.shotId || !edgeData?.segment) return true;
      const segs = disconnectedSegments[edgeData.shotId];
      return !segs || !segs.has(edgeData.segment);
    });

    // Add bypass dashed edges for disconnected shots
    for (const sid of disconnectedShotIds) {
      const segs = disconnectedSegments[sid];
      if (segs && segs.size > 0) {
        result.push({
          id: `bypass-${sid}`,
          source: shotNodeId(sid),
          target: videoNodeId(sid),
          type: 'bypass',
          data: { shotId: sid },
        });
      }
    }
  }

  // Append user-created manual edges
  for (const me of manualEdges) {
    if (!result.some((e) => e.id === me.id)) {
      result.push(me);
    }
  }

  return result;
}

/**
 * BFS: check if there's a directed path from `start` to `end` using
 * only non-bypass edges in the given edge list.
 */
function hasPath(edges: Edge[], start: string, end: string): boolean {
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (e.type === 'bypass') continue;
    const list = adj.get(e.source) || [];
    list.push(e.target);
    adj.set(e.source, list);
  }
  const visited = new Set<string>();
  const queue = [start];
  visited.add(start);
  while (queue.length > 0) {
    const node = queue.shift()!;
    if (node === end) return true;
    for (const next of adj.get(node) || []) {
      if (!visited.has(next)) {
        visited.add(next);
        queue.push(next);
      }
    }
  }
  return false;
}

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
  const locations = useProjectStore((s) => s.locations);
  const assetImages = useProjectStore((s) => s.assetImages);
  const assetImageKeys = useProjectStore((s) => s.assetImageKeys);
  const nodeRunsByShotId = useBoardStore((s) => s.nodeRunsByShotId);
  const artifactsByShotId = useBoardStore((s) => s.artifactsByShotId);
  const disconnectedSegments = useCanvasStore((s) => s.disconnectedSegments);
  const manualEdges = useCanvasStore((s) => s.manualEdges);

  const prevHashRef = useRef('');
  const rawEdgesRef = useRef<Edge[]>([]);
  const initializedRef = useRef(false);

  // Effect 1: rebuild graph when domain data changes
  useEffect(() => {
    const hash = JSON.stringify({
      sceneCount: scenes.length,
      sceneIds: scenes.map((s) => s.id).join(','),
      scenesWithScript: scenes.filter((s) => s.generated_script_json).length,
      shotCount: shots.length,
      shotIds: shots.map((s) => s.id).join(','),
      runKeys: Object.keys(nodeRunsByShotId).sort().join(','),
      artKeys: Object.keys(artifactsByShotId).sort().join(','),
      locPanorama: locations.map((l) => `${l.id}:${assetImages[l.id]?.['panorama'] ? '1' : '0'}`).join(','),
    });

    if (hash === prevHashRef.current) return;
    prevHashRef.current = hash;

    const { positionCache, setNodes, setEdges, disconnectedSegments: disc, manualEdges: me } = useCanvasStore.getState();

    const sceneInputs: SceneInput[] = scenes.map((s) => ({
      id: s.id,
      heading: s.heading || '',
      location: s.location || '',
      timeOfDay: s.time_of_day || '',
      description: s.description || '',
      characterNames: (s.characters_present || []) as string[],
      order: s.order ?? 0,
      coreEvent: s.core_event || '',
      emotionalPeak: s.emotional_peak || '',
      narrativeMode: s.narrative_mode || '',
      scriptJson: s.generated_script_json ? {
        beats: (s.generated_script_json.beats || []).map((b) => ({
          beat_id: b.beat_id || '',
          timestamp: b.timestamp || '',
          type: b.type || '',
          shots: (b.shots || []).map((sh) => ({
            shot_type: sh.shot_type || '',
            camera_move: sh.camera_move || '',
            angle: sh.angle || '',
            subject: sh.subject || '',
            action: sh.action || '',
            dialogue: sh.dialogue ? { character: sh.dialogue.character || '', line: sh.dialogue.line || '' } : null,
          })),
        })),
        duration_estimate_s: s.generated_script_json.duration_estimate_s,
        scene_summary: s.generated_script_json.scene_summary as unknown as SceneInput['scriptJson'] extends undefined ? never : NonNullable<SceneInput['scriptJson']>['scene_summary'],
      } : undefined,
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

    // Build location name → panorama URL/key map
    const locationPanoramaMap: Record<string, { panoramaUrl?: string; panoramaStorageKey?: string }> = {};
    for (const loc of locations) {
      const imgs = assetImages[loc.id];
      const keys = assetImageKeys[loc.id];
      const panoramaUrl = imgs?.['panorama'];
      const panoramaStorageKey = keys?.['panorama'];
      if (panoramaUrl || panoramaStorageKey) {
        locationPanoramaMap[loc.name] = { panoramaUrl, panoramaStorageKey };
      }
    }

    const { nodes, edges } = buildCanvasGraph(sceneInputs, shotInputs, {
      positionCache,
      locationPanoramaMap,
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

    rawEdgesRef.current = edges;
    setNodes(nodes);
    setEdges(applyDisconnections(edges, me, disc));
    initializedRef.current = true;
  }, [scenes, shots, nodeRunsByShotId, artifactsByShotId, locations, assetImages, assetImageKeys]);

  // Effect 2: re-apply edges when disconnectedSegments or manualEdges change
  useEffect(() => {
    if (!initializedRef.current) return;
    const { setEdges } = useCanvasStore.getState();
    const computed = applyDisconnections(rawEdgesRef.current, manualEdges, disconnectedSegments);
    setEdges(computed);

    // Auto-clear bypass: if shot→video has a complete path (through non-bypass edges),
    // remove the disconnection state for that shot → bypass disappears on next render.
    const disconnectedShotIds = Object.keys(disconnectedSegments);
    if (disconnectedShotIds.length === 0) return;

    const toReconnect: string[] = [];
    for (const shotId of disconnectedShotIds) {
      if (hasPath(computed, shotNodeId(shotId), videoNodeId(shotId))) {
        toReconnect.push(shotId);
      }
    }
    if (toReconnect.length > 0) {
      // Batch reconnect in next microtask to avoid set-during-render
      Promise.resolve().then(() => {
        const { reconnectAllEdges } = useCanvasStore.getState();
        for (const sid of toReconnect) {
          reconnectAllEdges(sid);
        }
      });
    }
  }, [disconnectedSegments, manualEdges]);
}
