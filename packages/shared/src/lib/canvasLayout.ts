/**
 * Canvas auto-layout: converts domain data (scenes, shots) into React Flow nodes + edges.
 *
 * Layout strategy: column-based
 *   Col 0 (x=0)    : SceneNode
 *   Col 1 (x=500)  : ShotNode(s)
 *   Col 2 (x=1020) : PromptAssemblyNode(s)
 *   Col 3 (x=1540) : ImageGenerationNode(s)
 *   Col 4 (x=2060) : VideoGenerationNode(s)
 *
 * Data sources (in priority order):
 *   1. Explicit `shots` array (from Shot table)
 *   2. `scene.scriptJson.beats[].shots[]` (from generated_script_json)
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
import { detectModuleType } from '../components/production/canvas/ModuleTemplates';

/* ── Layout constants ── */
const COL_X = [0, 500, 1020, 1540, 2060];
const SCENE_PADDING = 400;  // vertical padding between scene groups
const SHOT_GAP = 420;       // vertical gap between shots within a scene
const NODE_HEIGHT = 200;

/** Actual card widths per node type — must match the component's outer div width */
const NODE_WIDTHS: Record<string, number> = {
  scene: 320,
  shot: 260,
  promptAssembly: 260,
  imageGeneration: 260,
  videoGeneration: 290,
};
const DEFAULT_NODE_WIDTH = 280;

/** Build dimension props for a node — uses correct width per type, no forced `measured` */
function nodeDims(nodeType: string) {
  const w = NODE_WIDTHS[nodeType] || DEFAULT_NODE_WIDTH;
  return {
    width: w,
    height: NODE_HEIGHT,
    initialWidth: w,
    initialHeight: NODE_HEIGHT,
    style: { width: w },
    measured: { width: w, height: NODE_HEIGHT },
  };
}

/**
 * Previously limited to 5 for performance. Now safe to expand all scenes
 * because scene-level virtualization (useCanvasVirtualization) only renders
 * visible scenes.
 */

/* ── Helpers ── */
function sceneNodeId(sceneId: string) { return `scene-${sceneId}`; }
export function shotNodeId(shotId: string) { return `shot-${shotId}`; }
function promptNodeId(shotId: string) { return `prompt-${shotId}`; }
function imageNodeId(shotId: string) { return `image-${shotId}`; }
export function videoNodeId(shotId: string) { return `video-${shotId}`; }

/* ── Script JSON types (from generated_script_json) ── */
interface ScriptShotJson {
  shot_type: string;
  camera_move: string;
  angle: string;
  subject: string;
  action: string;
  dialogue: { character: string; line: string; subtext?: string; delivery?: string } | null;
  sfx?: string;
  music?: string;
  close_up_target?: string;
  transition?: string;
}

interface ScriptBeatJson {
  beat_id: string;
  timestamp: string;
  type: string;
  shots: ScriptShotJson[];
}

export interface SceneInput {
  id: string;
  heading: string;
  location: string;
  timeOfDay: string;
  description: string;
  characterNames: string[];
  order: number;
  coreEvent?: string;
  emotionalPeak?: string;
  narrativeMode?: string;
  scriptJson?: {
    beats: ScriptBeatJson[];
    duration_estimate_s?: number;
    scene_summary?: { hook?: string; core_reversal?: string; sweet_spot?: string; cliffhanger?: string };
  };
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
  /** {locationName: {panoramaUrl, panoramaStorageKey}} — for populating SceneNode panorama data */
  locationPanoramaMap?: Record<string, { panoramaUrl?: string; panoramaStorageKey?: string }>;
}

/**
 * Flatten a scene's scriptJson beats into ShotInput[].
 * Used when Shot table is empty but generated_script_json has data.
 */
function extractShotsFromScriptJson(sceneId: string, scriptJson: SceneInput['scriptJson']): ShotInput[] {
  if (!scriptJson?.beats) return [];
  const result: ShotInput[] = [];
  let shotNumber = 1;
  for (const beat of scriptJson.beats) {
    for (const shot of beat.shots) {
      result.push({
        id: `${sceneId}_b${beat.beat_id}_s${shotNumber}`,
        sceneId,
        shotNumber,
        framing: shot.shot_type || '',
        cameraAngle: shot.angle || '',
        cameraMovement: shot.camera_move || '',
        description: shot.action || '',
        visualPrompt: '',
        status: 'idle',
      });
      shotNumber++;
    }
  }
  return result;
}

export function buildCanvasGraph(
  scenes: SceneInput[],
  shots: ShotInput[],
  options: BuildGraphOptions = {},
) {
  const { positionCache = {}, artifactsByShotId = {}, nodeRunsByShotId = {}, locationPanoramaMap = {} } = options;

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  const sortedScenes = [...scenes].sort((a, b) => a.order - b.order);

  let currentY = 0; // Accumulated Y offset — grows dynamically

  for (let si = 0; si < sortedScenes.length; si++) {
    const scene = sortedScenes[si];

    // Get shots: first from explicit shots array, fallback to scriptJson
    // Only auto-expand shots for the first N scenes (performance)
    let sceneShots: ShotInput[] = shots
      .filter((s) => s.sceneId === scene.id)
      .sort((a, b) => a.shotNumber - b.shotNumber);

    if (sceneShots.length === 0 && scene.scriptJson) {
      sceneShots = extractShotsFromScriptJson(scene.id, scene.scriptJson);
    }

    const baseY = currentY;
    const sId = sceneNodeId(scene.id);

    // Center scene node vertically relative to its shots group
    const shotsGroupHeight = Math.max(0, sceneShots.length - 1) * SHOT_GAP;
    const sceneCenterY = baseY + shotsGroupHeight / 2;

    // Scene node
    const sceneText = [scene.description, scene.coreEvent, scene.heading].filter(Boolean).join(' ');
    const sceneModuleType = detectModuleType(sceneText);
    const locationPanorama = scene.location ? locationPanoramaMap[scene.location] : undefined;
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
        moduleType: sceneModuleType ?? undefined,
        coreEvent: scene.coreEvent,
        emotionalPeak: scene.emotionalPeak,
        narrativeMode: scene.narrativeMode,
        panoramaUrl: locationPanorama?.panoramaUrl,
        panoramaStorageKey: locationPanorama?.panoramaStorageKey,
      } satisfies SceneNodeData,
      ...nodeDims('scene'),
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
      const detectedModule = detectModuleType(shot.description || '');
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
          moduleType: detectedModule ?? undefined,
          imagePrompt: shot.visualPrompt || undefined,
        } satisfies ShotNodeData,
        ...nodeDims('shot'),
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
        ...nodeDims('promptAssembly'),
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
        ...nodeDims('imageGeneration'),
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
        ...nodeDims('videoGeneration'),
      });

      // Edges: Scene → Shot → Prompt → Image → Video
      edges.push(
        { id: `e-${sId}-${shId}`, source: sId, target: shId, type: 'pipeline' },
        { id: `e-${shId}-${prId}`, source: shId, target: prId, type: 'pipeline', data: { shotId: shot.id, segment: 'shot-prompt' } },
        { id: `e-${prId}-${imId}`, source: prId, target: imId, type: 'pipeline', data: { shotId: shot.id, segment: 'prompt-image' } },
        { id: `e-${imId}-${viId}`, source: imId, target: viId, type: 'pipeline', data: { shotId: shot.id, segment: 'image-video' } },
      );
    }

    // Advance Y for next scene group: scene node height + all shots height + padding
    const shotsHeight = Math.max(1, sceneShots.length) * SHOT_GAP;
    currentY += Math.max(NODE_HEIGHT, shotsHeight) + SCENE_PADDING;
  }

  return { nodes, edges };
}

/**
 * Incremental graph build for scene-level virtualization.
 *
 * Only rebuilds nodes/edges for scenes in `visibleSceneIds`.
 * For non-visible scenes, retains existing nodes from `existingNodes`
 * to preserve positions (they won't render due to React Flow's
 * onlyRenderVisibleElements optimization, but maintain state).
 */
export function buildCanvasGraphIncremental(
  scenes: SceneInput[],
  shots: ShotInput[],
  visibleSceneIds: Set<string>,
  existingNodes: Node[],
  options: BuildGraphOptions = {},
): { nodes: Node[]; edges: Edge[] } {
  // If all scenes are visible or set is empty, fall back to full build
  if (visibleSceneIds.size === 0 || visibleSceneIds.size >= scenes.length) {
    return buildCanvasGraph(scenes, shots, options);
  }

  const { positionCache = {}, artifactsByShotId = {}, nodeRunsByShotId = {} } = options;
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Index existing nodes by sceneId for quick lookup
  const existingByScene = new Map<string, Node[]>();
  for (const n of existingNodes) {
    const sceneId = (n.data as { sceneId?: string })?.sceneId;
    if (sceneId) {
      const arr = existingByScene.get(sceneId) || [];
      arr.push(n);
      existingByScene.set(sceneId, arr);
    }
  }

  // Index existing edges by source scene
  const sortedScenes = [...scenes].sort((a, b) => a.order - b.order);

  // Track Y offset for scene placement
  let currentY = 0;

  for (let si = 0; si < sortedScenes.length; si++) {
    const scene = sortedScenes[si];
    const sceneShots = shots
      .filter((s) => s.sceneId === scene.id)
      .sort((a, b) => a.shotNumber - b.shotNumber);

    if (visibleSceneIds.has(scene.id)) {
      // Visible scene: full rebuild (reuse buildCanvasGraph logic inline)
      const sceneResult = buildCanvasGraph(
        [scene],
        sceneShots,
        { ...options, positionCache },
      );

      // Offset nodes to correct Y position
      for (const n of sceneResult.nodes) {
        if (!positionCache[n.id]) {
          n.position = { x: n.position.x, y: n.position.y + currentY };
        }
        nodes.push(n);
      }
      edges.push(...sceneResult.edges);
    } else {
      // Non-visible scene: keep existing nodes as-is
      const existing = existingByScene.get(scene.id) || [];
      if (existing.length > 0) {
        nodes.push(...existing);
      } else {
        // No existing nodes — create a minimal scene placeholder
        const sId = sceneNodeId(scene.id);
        nodes.push({
          id: sId,
          type: 'scene',
          position: positionCache[sId] ?? { x: COL_X[0], y: currentY },
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
          ...nodeDims('scene'),
        });
      }
    }

    // Advance Y for next scene
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
    const w = (n.style?.width as number) || DEFAULT_NODE_WIDTH;
    const h = NODE_HEIGHT;
    minX = Math.min(minX, n.position.x);
    minY = Math.min(minY, n.position.y);
    maxX = Math.max(maxX, n.position.x + w);
    maxY = Math.max(maxY, n.position.y + h);
  }
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}
