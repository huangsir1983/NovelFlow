/**
 * Canvas auto-layout: converts domain data (scenes, shots) into React Flow nodes + edges.
 *
 * Layout strategy: column-based
 *   Col 0 (x=0)    : SceneNode
 *   Col 1 (x=320)  : ShotNode(s)
 *   Col 2 (x=640)  : PromptAssemblyNode(s)
 *   Col 3 (x=960)  : ImageGenerationNode(s)
 *   Col 4 (x=1280) : VideoGenerationNode(s)
 *
 * Each scene group is vertically offset by SCENE_GAP.
 * Multiple shots within a scene are stacked vertically with SHOT_GAP.
 */

import type { Node, Edge } from '@xyflow/react';
import type {
  SceneNodeData,
  ShotNodeData,
  PromptAssemblyNodeData,
  ImageGenerationNodeData,
  VideoGenerationNodeData,
  CanvasNodeStatus,
} from '../types/canvas';

/* ── Layout constants ── */
const COL_X = [0, 320, 640, 960, 1280];
const SCENE_PADDING = 120;  // vertical padding between scene groups
const SHOT_GAP = 220;       // vertical gap between shots within a scene
const NODE_WIDTH = 260;
const NODE_HEIGHT = 180;

/* ── Helpers ── */
function sceneNodeId(sceneId: string) { return `scene-${sceneId}`; }
function shotNodeId(shotId: string) { return `shot-${shotId}`; }
function promptNodeId(shotId: string) { return `prompt-${shotId}`; }
function imageNodeId(shotId: string) { return `image-${shotId}`; }
function videoNodeId(shotId: string) { return `video-${shotId}`; }

export interface SceneInput {
  id: string;
  heading: string;
  location: string;
  timeOfDay: string;
  description: string;
  characterNames: string[];
  order: number;
}

export interface ShotInput {
  id: string;
  sceneId: string;
  shotNumber: number;
  framing: string;
  cameraAngle: string;
  cameraMovement: string;
  description: string;
  thumbnailUrl?: string;
  visualPrompt?: string;
  status?: CanvasNodeStatus;
}

export interface BuildGraphOptions {
  positionCache?: Record<string, { x: number; y: number }>;
  artifactsByShotId?: Record<string, Array<{ id: string; type: string; url?: string; status: string }>>;
  nodeRunsByShotId?: Record<string, Array<{ nodeKey: string; status: string; progress?: number }>>;
}

export function buildCanvasGraph(
  scenes: SceneInput[],
  shots: ShotInput[],
  options: BuildGraphOptions = {},
) {
  const { positionCache = {}, artifactsByShotId = {}, nodeRunsByShotId = {} } = options;

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  const sortedScenes = [...scenes].sort((a, b) => a.order - b.order);

  let currentY = 0; // Accumulated Y offset — grows dynamically

  for (let si = 0; si < sortedScenes.length; si++) {
    const scene = sortedScenes[si];
    const sceneShots = shots
      .filter((s) => s.sceneId === scene.id)
      .sort((a, b) => a.shotNumber - b.shotNumber);

    const baseY = currentY;
    const sId = sceneNodeId(scene.id);

    // Center scene node vertically relative to its shots group
    const shotsGroupHeight = Math.max(0, sceneShots.length - 1) * SHOT_GAP;
    const sceneCenterY = baseY + shotsGroupHeight / 2;

    // Scene node
    nodes.push({
      id: sId,
      type: 'scene',
      position: positionCache[sId] ?? { x: COL_X[0], y: sceneCenterY },
      data: {
        label: scene.heading || `Scene ${scene.order}`,
        status: 'idle' as CanvasNodeStatus,
        sceneId: scene.id,
        nodeType: 'scene',
        heading: scene.heading,
        location: scene.location,
        timeOfDay: scene.timeOfDay,
        description: scene.description,
        characterNames: scene.characterNames,
        order: scene.order,
        shotCount: sceneShots.length,
      } satisfies SceneNodeData,
      style: { width: NODE_WIDTH },
    });

    for (let shi = 0; shi < sceneShots.length; shi++) {
      const shot = sceneShots[shi];
      const shotY = baseY + shi * SHOT_GAP;
      const artifacts = artifactsByShotId[shot.id] || [];
      const runs = nodeRunsByShotId[shot.id] || [];

      const shotStatus = (shot.status || 'idle') as CanvasNodeStatus;
      const promptRun = runs.find((r) => r.nodeKey === 'prompt');
      const imageRun = runs.find((r) => r.nodeKey === 'image');
      const videoRun = runs.find((r) => r.nodeKey === 'video');

      const imageArtifacts = artifacts.filter((a) => a.type === 'image');
      const videoArtifact = artifacts.find((a) => a.type === 'video');

      // Shot node
      const shId = shotNodeId(shot.id);
      nodes.push({
        id: shId,
        type: 'shot',
        position: positionCache[shId] ?? { x: COL_X[1], y: shotY },
        data: {
          label: `Shot ${shot.shotNumber}`,
          status: shotStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'shot',
          shotNumber: shot.shotNumber,
          framing: shot.framing,
          cameraAngle: shot.cameraAngle,
          cameraMovement: shot.cameraMovement,
          description: shot.description,
          thumbnailUrl: shot.thumbnailUrl,
          specId: shot.id,
        } satisfies ShotNodeData,
        style: { width: NODE_WIDTH },
      });

      // Prompt assembly node
      const prId = promptNodeId(shot.id);
      nodes.push({
        id: prId,
        type: 'promptAssembly',
        position: positionCache[prId] ?? { x: COL_X[2], y: shotY },
        data: {
          label: 'Prompt',
          status: (promptRun?.status as CanvasNodeStatus) || 'idle',
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'promptAssembly',
          assembledPrompt: shot.visualPrompt || '',
          characterRefs: [],
          locationRef: scene.location,
          styleTemplate: undefined,
        } satisfies PromptAssemblyNodeData,
        style: { width: NODE_WIDTH },
      });

      // Image generation node
      const imId = imageNodeId(shot.id);
      nodes.push({
        id: imId,
        type: 'imageGeneration',
        position: positionCache[imId] ?? { x: COL_X[3], y: shotY },
        data: {
          label: 'Image',
          status: (imageRun?.status as CanvasNodeStatus) || 'idle',
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'imageGeneration',
          prompt: shot.visualPrompt || '',
          candidates: imageArtifacts.map((a) => ({
            id: a.id,
            url: a.url,
            status: a.status as 'draft' | 'approved' | 'rejected',
          })),
          selectedCandidateId: imageArtifacts.find((a) => a.status === 'approved')?.id,
          progress: imageRun?.progress ?? 0,
        } satisfies ImageGenerationNodeData,
        style: { width: NODE_WIDTH },
      });

      // Video generation node
      const viId = videoNodeId(shot.id);
      nodes.push({
        id: viId,
        type: 'videoGeneration',
        position: positionCache[viId] ?? { x: COL_X[4], y: shotY },
        data: {
          label: 'Video',
          status: (videoRun?.status as CanvasNodeStatus) || 'idle',
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'videoGeneration',
          sourceImageId: imageArtifacts.find((a) => a.status === 'approved')?.id,
          videoUrl: videoArtifact?.url,
          durationMs: 0,
          progress: videoRun?.progress ?? 0,
          mode: 'image_to_video',
        } satisfies VideoGenerationNodeData,
        style: { width: NODE_WIDTH },
      });

      // Edges: Scene → Shot → Prompt → Image → Video
      edges.push(
        { id: `e-${sId}-${shId}`, source: sId, target: shId, type: 'pipeline' },
        { id: `e-${shId}-${prId}`, source: shId, target: prId, type: 'pipeline' },
        { id: `e-${prId}-${imId}`, source: prId, target: imId, type: 'pipeline' },
        { id: `e-${imId}-${viId}`, source: imId, target: viId, type: 'pipeline' },
      );
    }

    // Advance Y for next scene group: scene node height + all shots height + padding
    const shotsHeight = Math.max(1, sceneShots.length) * SHOT_GAP;
    currentY += Math.max(NODE_HEIGHT, shotsHeight) + SCENE_PADDING;
  }

  return { nodes, edges };
}

/** Get all node IDs belonging to a scene */
export function getSceneNodeIds(sceneId: string, nodes: Node[]): string[] {
  return nodes.filter((n) => (n.data as { sceneId?: string })?.sceneId === sceneId).map((n) => n.id);
}

/** Get bounding box of nodes for fitView */
export function getSceneBounds(sceneId: string, nodes: Node[]) {
  const sceneNodes = nodes.filter((n) => (n.data as { sceneId?: string })?.sceneId === sceneId);
  if (sceneNodes.length === 0) return null;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of sceneNodes) {
    const w = (n.style?.width as number) || NODE_WIDTH;
    const h = NODE_HEIGHT;
    minX = Math.min(minX, n.position.x);
    minY = Math.min(minY, n.position.y);
    maxX = Math.max(maxX, n.position.x + w);
    maxY = Math.max(maxY, n.position.y + h);
  }
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}
