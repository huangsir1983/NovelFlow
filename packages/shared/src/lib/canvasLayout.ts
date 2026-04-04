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
  SceneBGNodeData,
  CharacterProcessNodeData,
  ImageProcessNodeData,
  CompositeNodeData,
  BlendRefineNodeData,
  LightingNodeData,
  FinalHDNodeData,
  VideoGenerationNodeData,
  CanvasNodeStatus,
  CharacterRefInfo,
} from '../types/canvas';
import { detectModuleType } from '../components/production/canvas/ModuleTemplates';

/* ── Layout constants ── */
/**
 * 9-column layout for the 12-node branching pipeline:
 *   Col 0 (0)    : Scene
 *   Col 1 (500)  : Shot
 *   Col 2 (1020) : SceneBG / CharacterProcess / PropProcess (branch split)
 *   Col 3 (1540) : ViewAngle / PropAngle
 *   Col 4 (2060) : Expression
 *   Col 5 (2580) : HDUpscale + Matting
 *   Col 6 (3100) : Composite (merge point)
 *   Col 7 (3620) : BlendRefine + Lighting
 *   Col 8 (4140) : FinalHD + VideoGeneration
 */
const COL_X = [0, 500, 1020, 1540, 2060, 2580, 3100, 3620, 4140];
const SCENE_PADDING = 400;  // vertical padding between scene groups
const SHOT_GAP = 420;       // vertical gap between shots within a scene
const BRANCH_GAP = 220;     // vertical gap between branches (sceneBG, characters, props)
const NODE_HEIGHT = 200;

/** Actual card widths per node type — must match the component's outer div width */
const NODE_WIDTHS: Record<string, number> = {
  scene: 320,
  shot: 260,
  promptAssembly: 260,
  imageGeneration: 260,
  videoGeneration: 290,
  sceneBG: 260,
  characterProcess: 180,
  viewAngle: 260,
  expression: 260,
  hdUpscale: 240,
  matting: 260,
  propProcess: 240,
  propAngle: 260,
  composite: 280,
  blendRefine: 240,
  lighting: 240,
  finalHD: 240,
  imageProcess: 260,
};
const DEFAULT_NODE_WIDTH = 280;

/** Per-node-type heights — only needed for nodes that differ from NODE_HEIGHT */
const NODE_HEIGHTS: Record<string, number> = {
  characterProcess: 310, // portrait card: label(~30) + 260 image + overlay
};

/** Build dimension props for a node — uses correct width/height per type */
function nodeDims(nodeType: string) {
  const w = NODE_WIDTHS[nodeType] || DEFAULT_NODE_WIDTH;
  const h = NODE_HEIGHTS[nodeType] || NODE_HEIGHT;
  return {
    width: w,
    height: h,
    initialWidth: w,
    initialHeight: h,
    style: { width: w },
    measured: { width: w, height: h },
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
// promptNodeId / imageNodeId removed — old linear pipeline nodes replaced by 12-node branching pipeline
export function videoNodeId(shotId: string) { return `video-${shotId}`; }

/* ── New 12-node pipeline ID helpers ── */
export function sceneBGNodeId(shotId: string) { return `scenebg-${shotId}`; }
export function charProcessNodeId(shotId: string, charName: string) { return `charproc-${shotId}-${charName}`; }
export function viewAngleNodeId(shotId: string, charName: string) { return `viewangle-${shotId}-${charName}`; }
export function expressionNodeId(shotId: string, charName: string) { return `expression-${shotId}-${charName}`; }
export function hdUpscaleNodeId(shotId: string, charName: string) { return `hdupscale-${shotId}-${charName}`; }
export function mattingNodeId(shotId: string, charName: string) { return `matting-${shotId}-${charName}`; }
export function propProcessNodeId(shotId: string, propIdx: number) { return `propproc-${shotId}-${propIdx}`; }
export function propAngleNodeId(shotId: string, propIdx: number) { return `propangle-${shotId}-${propIdx}`; }
export function compositeNodeId(shotId: string) { return `composite-${shotId}`; }
export function blendRefineNodeId(shotId: string) { return `blendrefine-${shotId}`; }
export function lightingNodeId(shotId: string) { return `lighting-${shotId}`; }
export function finalHDNodeId(shotId: string) { return `finalhd-${shotId}`; }
export function imageProcessNodeId(shotId: string, charName: string, processType: string) { return `imgproc-${processType}-${shotId}-${charName}`; }

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
  charactersInFrame?: string[];
  durationEstimate?: string;
  emotionTarget?: string;
  dialogueText?: string;
}

/** Character visual data keyed by character name */
export interface CharacterMapEntry {
  name: string;
  appearance?: { face?: string; body?: string; hair?: string; distinguishing_features?: string };
  costume?: { typical_outfit?: string };
  visualRefUrl?: string;
  visualRefStorageKey?: string;
  negativePrompt?: string;
}

/** Location visual data keyed by location name */
export interface LocationDetailEntry {
  visualDescription?: string;
  mood?: string;
  atmosphere?: string;
  lighting?: string;
  colorPalette?: string[];
  visualRefUrl?: string;
  visualRefStorageKey?: string;
  negativePrompt?: string;
}

export interface BuildGraphOptions {
  positionCache?: Record<string, { x: number; y: number }>;
  artifactsByShotId?: Record<string, Array<{ id: string; type: string; url?: string; status: string }>>;
  nodeRunsByShotId?: Record<string, Array<{ nodeKey: string; status: string; progress?: number }>>;
  /** {locationName: {panoramaUrl, panoramaStorageKey}} — for populating SceneNode panorama data */
  locationPanoramaMap?: Record<string, { panoramaUrl?: string; panoramaStorageKey?: string }>;
  /** {characterName: visual data} — for populating PromptAssembly characterRefs */
  characterMap?: Record<string, CharacterMapEntry>;
  /** {locationName: visual detail} — for populating PromptAssembly locationRef */
  locationDetailMap?: Record<string, LocationDetailEntry>;
}

/** Parse a duration string like "3s" / "5" into milliseconds. Returns 0 on failure. */
function parseDurationMs(raw?: string): number {
  if (!raw) return 0;
  const n = parseFloat(raw);
  if (Number.isNaN(n) || n <= 0) return 0;
  // If the string already looks like ms (> 500), keep it; otherwise treat as seconds
  return n > 500 ? Math.round(n) : Math.round(n * 1000);
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
        charactersInFrame: shot.subject ? [shot.subject] : [],
        dialogueText: shot.dialogue?.line || '',
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
  const {
    positionCache = {},
    artifactsByShotId = {},
    nodeRunsByShotId = {},
    locationPanoramaMap = {},
    characterMap = {},
  } = options;

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

    // Pre-compute per-shot Y positions based on actual branch counts
    const shotYPositions: number[] = [];
    {
      let nextY = baseY;
      for (const s of sceneShots) {
        shotYPositions.push(nextY);
        let charNames = s.charactersInFrame?.length ? s.charactersInFrame : scene.characterNames;
        if ((!charNames || charNames.length === 0) && Object.keys(characterMap).length > 0) {
          charNames = Object.keys(characterMap);
        }
        const branches = 1 + (charNames?.length || 0); // 1 sceneBG + N characters
        const branchHeight = (branches - 1) * BRANCH_GAP;
        nextY += Math.max(SHOT_GAP, branchHeight + 120);
      }
    }
    const shotsGroupHeight = shotYPositions.length > 1
      ? shotYPositions[shotYPositions.length - 1] - shotYPositions[0]
      : 0;
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
      const shotY = shotYPositions[shi];
      const artifacts = artifactsByShotId[shot.id] || [];
      const runs = nodeRunsByShotId[shot.id] || [];

      const shotStatus = (shot.status || 'idle') as CanvasNodeStatus;
      const videoRun = runs.find((r) => r.nodeKey === 'video');
      const videoArtifact = artifacts.find((a) => a.type === 'video');

      // ── Build character refs and location detail for this shot ──
      // Priority: shot-level characters > scene-level characters > all known characters
      let shotCharNames = shot.charactersInFrame?.length
        ? shot.charactersInFrame
        : scene.characterNames;

      // If still empty, use all characters in characterMap as fallback
      if ((!shotCharNames || shotCharNames.length === 0) && Object.keys(characterMap).length > 0) {
        shotCharNames = Object.keys(characterMap);
      }

      // Resolve character names: exact match first, then fuzzy (contains) match
      const allCharNames = Object.keys(characterMap);
      const resolveCharName = (name: string): CharacterMapEntry | undefined => {
        // Exact match
        if (characterMap[name]) return characterMap[name];
        // Fuzzy: characterMap key contains shot name, or shot name contains key
        return allCharNames
          .map((k) => characterMap[k])
          .find((c) => name.includes(c.name) || c.name.includes(name));
      };

      const characterRefs: CharacterRefInfo[] = shotCharNames
        .map(resolveCharName)
        .filter((c): c is CharacterMapEntry => !!c)
        // Deduplicate by name
        .filter((c, i, arr) => arr.findIndex((x) => x.name === c.name) === i)
        .map((c) => ({
          name: c.name,
          visualRefUrl: c.visualRefUrl,
          visualRefStorageKey: c.visualRefStorageKey,
          appearanceDesc: c.appearance
            ? [c.appearance.face, c.appearance.body, c.appearance.hair, c.appearance.distinguishing_features]
                .filter(Boolean).join(', ')
            : undefined,
          costumeDesc: c.costume?.typical_outfit,
          negativePrompt: c.negativePrompt,
        }));

      const locationPanorama2 = scene.location ? locationPanoramaMap[scene.location] : undefined;

      // Estimate duration
      const shotDurationMs = parseDurationMs(shot.durationEstimate)
        || (scene.scriptJson?.duration_estimate_s
          ? Math.round((scene.scriptJson.duration_estimate_s * 1000) / Math.max(1, sceneShots.length))
          : 0);

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // Shot node (Col 1)
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
          charactersInFrame: shot.charactersInFrame,
          durationEstimateMs: shotDurationMs || undefined,
          dialogueText: shot.dialogueText,
          emotionTarget: shot.emotionTarget,
        } satisfies ShotNodeData,
        ...nodeDims('shot'),
      });

      // ── Scene → Shot edge
      edges.push({ id: `e-${sId}-${shId}`, source: sId, target: shId, type: 'pipeline' });

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // Branch layout: sceneBG + N characters + M props stacked vertically
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      const charNames = characterRefs.map((c) => c.name);
      const numBranches = 1 + charNames.length + 0; // sceneBG + characters (props TBD)
      const branchTotalHeight = (numBranches - 1) * BRANCH_GAP;
      const branchBaseY = shotY - branchTotalHeight / 2;
      let branchIdx = 0;

      // All node IDs that feed into Composite
      const compositeSourceIds: string[] = [];

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // SceneBG node (Col 2) — VR panorama screenshot as background layer
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      const bgId = sceneBGNodeId(shot.id);
      const bgY = branchBaseY + branchIdx * BRANCH_GAP;
      branchIdx++;
      nodes.push({
        id: bgId,
        type: 'sceneBG',
        position: positionCache[bgId] ?? { x: COL_X[2], y: bgY },
        data: {
          label: '场景背景',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'sceneBG',
          panoramaUrl: locationPanorama2?.panoramaUrl,
          panoramaStorageKey: locationPanorama2?.panoramaStorageKey,
          screenshotUrl: undefined,
          viewAngle: { yaw: 0, pitch: 0 },
          progress: 0,
        } satisfies SceneBGNodeData,
        ...nodeDims('sceneBG'),
      });
      compositeSourceIds.push(bgId);
      edges.push({ id: `e-${shId}-${bgId}`, source: shId, target: bgId, type: 'pipeline', data: { shotId: shot.id, segment: 'shot-scenebg' } });

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // Character branches (Col 2-5): CharProcess → ViewAngle → Expression → HDUpscale + Matting
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      for (const charRef of characterRefs) {
        const cn = charRef.name;
        const charY = branchBaseY + branchIdx * BRANCH_GAP;
        branchIdx++;
        const charEntry = characterMap[cn];

        // CharacterProcess (Col 2) — carries the character's reference IMAGE
        const cpId = charProcessNodeId(shot.id, cn);
        // Gather all available image variants from asset library
        const charAssetImages = charEntry ? {
          visual_reference: charEntry.visualRefUrl,
          ...(charEntry.visualRefStorageKey ? { storageKey: charEntry.visualRefStorageKey } : {}),
        } : undefined;
        nodes.push({
          id: cpId,
          type: 'characterProcess',
          position: positionCache[cpId] ?? { x: COL_X[2], y: charY },
          data: {
            label: cn,
            status: 'idle' as CanvasNodeStatus,
            sceneId: scene.id,
            shotId: shot.id,
            nodeType: 'characterProcess',
            characterId: undefined,
            characterName: cn,
            visualRefUrl: charRef.visualRefUrl,
            visualRefStorageKey: charRef.visualRefStorageKey,
            availableImages: charAssetImages as Record<string, string> | undefined,
            selectedVariant: 'visual_reference',
          } satisfies CharacterProcessNodeData,
          ...nodeDims('characterProcess'),
        });
        edges.push({ id: `e-${shId}-${cpId}`, source: shId, target: cpId, type: 'pipeline', data: { shotId: shot.id, segment: `shot-char-${cn}` } });

        // ImageProcess: ViewAngle (Col 3)
        const vaId = imageProcessNodeId(shot.id, cn, 'viewAngle');
        nodes.push({
          id: vaId,
          type: 'imageProcess',
          position: positionCache[vaId] ?? { x: COL_X[3], y: charY },
          data: {
            label: '视角调整',
            status: 'idle' as CanvasNodeStatus,
            sceneId: scene.id,
            shotId: shot.id,
            nodeType: 'imageProcess',
            processType: 'viewAngle',
            inputImageUrl: charRef.visualRefUrl,
            inputStorageKey: charRef.visualRefStorageKey,
            targetAngle: shot.cameraAngle || 'front',
            progress: 0,
          } satisfies ImageProcessNodeData,
          ...nodeDims('imageProcess'),
        });
        edges.push({ id: `e-${cpId}-${vaId}`, source: cpId, target: vaId, type: 'pipeline', data: { shotId: shot.id, segment: `char-viewangle-${cn}` } });

        // ImageProcess: Expression (Col 4)
        const exId = imageProcessNodeId(shot.id, cn, 'expression');
        const expressionPrompt = [shot.emotionTarget, shot.dialogueText].filter(Boolean).join(' — ') || '';
        nodes.push({
          id: exId,
          type: 'imageProcess',
          position: positionCache[exId] ?? { x: COL_X[4], y: charY },
          data: {
            label: '表情动作',
            status: 'idle' as CanvasNodeStatus,
            sceneId: scene.id,
            shotId: shot.id,
            nodeType: 'imageProcess',
            processType: 'expression',
            expressionPrompt,
            emotion: shot.emotionTarget,
            action: shot.description,
            progress: 0,
          } satisfies ImageProcessNodeData,
          ...nodeDims('imageProcess'),
        });
        edges.push({ id: `e-${vaId}-${exId}`, source: vaId, target: exId, type: 'pipeline', data: { shotId: shot.id, segment: `viewangle-expression-${cn}` } });

        // ImageProcess: HDUpscale (Col 5, upper)
        const hdId = imageProcessNodeId(shot.id, cn, 'hdUpscale');
        nodes.push({
          id: hdId,
          type: 'imageProcess',
          position: positionCache[hdId] ?? { x: COL_X[5], y: charY - BRANCH_GAP / 4 },
          data: {
            label: '高清化',
            status: 'idle' as CanvasNodeStatus,
            sceneId: scene.id,
            shotId: shot.id,
            nodeType: 'imageProcess',
            processType: 'hdUpscale',
            scaleFactor: 2,
            progress: 0,
          } satisfies ImageProcessNodeData,
          ...nodeDims('imageProcess'),
        });
        edges.push({ id: `e-${exId}-${hdId}`, source: exId, target: hdId, type: 'pipeline', data: { shotId: shot.id, segment: `expression-hd-${cn}` } });

        // ImageProcess: Matting (Col 5, lower)
        const mtId = imageProcessNodeId(shot.id, cn, 'matting');
        nodes.push({
          id: mtId,
          type: 'imageProcess',
          position: positionCache[mtId] ?? { x: COL_X[5], y: charY + BRANCH_GAP / 4 },
          data: {
            label: '抠图',
            status: 'idle' as CanvasNodeStatus,
            sceneId: scene.id,
            shotId: shot.id,
            nodeType: 'imageProcess',
            processType: 'matting',
            progress: 0,
          } satisfies ImageProcessNodeData,
          ...nodeDims('imageProcess'),
        });
        edges.push({ id: `e-${hdId}-${mtId}`, source: hdId, target: mtId, type: 'pipeline', data: { shotId: shot.id, segment: `hd-matting-${cn}` } });
        compositeSourceIds.push(mtId);
      }

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // Composite node (Col 6) — merge point
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      const compId = compositeNodeId(shot.id);
      nodes.push({
        id: compId,
        type: 'composite',
        position: positionCache[compId] ?? { x: COL_X[6], y: shotY },
        data: {
          label: '合成',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'composite',
          layers: [],
          outputImageUrl: undefined,
          canvasWidth: 1920,
          canvasHeight: 1080,
          progress: 0,
        } satisfies CompositeNodeData,
        ...nodeDims('composite'),
      });
      // Connect all branch outputs → Composite
      for (const srcId of compositeSourceIds) {
        edges.push({ id: `e-${srcId}-${compId}`, source: srcId, target: compId, type: 'pipeline', data: { shotId: shot.id, segment: `branch-composite` } });
      }

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // Post-composite chain (Col 7-8): BlendRefine → Lighting → FinalHD → VideoGen
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

      // BlendRefine (Col 7, upper)
      const brId = blendRefineNodeId(shot.id);
      nodes.push({
        id: brId,
        type: 'blendRefine',
        position: positionCache[brId] ?? { x: COL_X[7], y: shotY - BRANCH_GAP / 4 },
        data: {
          label: '融合',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'blendRefine',
          inputImageUrl: undefined,
          outputImageUrl: undefined,
          progress: 0,
        } satisfies BlendRefineNodeData,
        ...nodeDims('blendRefine'),
      });
      edges.push({ id: `e-${compId}-${brId}`, source: compId, target: brId, type: 'pipeline', data: { shotId: shot.id, segment: 'composite-blend' } });

      // Lighting (Col 7, lower)
      const ltId = lightingNodeId(shot.id);
      nodes.push({
        id: ltId,
        type: 'lighting',
        position: positionCache[ltId] ?? { x: COL_X[7], y: shotY + BRANCH_GAP / 4 },
        data: {
          label: '光影',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'lighting',
          inputImageUrl: undefined,
          outputImageUrl: undefined,
          lightingPreset: 'auto',
          progress: 0,
        } satisfies LightingNodeData,
        ...nodeDims('lighting'),
      });
      edges.push({ id: `e-${brId}-${ltId}`, source: brId, target: ltId, type: 'pipeline', data: { shotId: shot.id, segment: 'blend-lighting' } });

      // FinalHD (Col 8, upper)
      const fhId = finalHDNodeId(shot.id);
      nodes.push({
        id: fhId,
        type: 'finalHD',
        position: positionCache[fhId] ?? { x: COL_X[8], y: shotY - BRANCH_GAP / 4 },
        data: {
          label: '终稿高清',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'finalHD',
          inputImageUrl: undefined,
          outputImageUrl: undefined,
          scaleFactor: 2,
          progress: 0,
        } satisfies FinalHDNodeData,
        ...nodeDims('finalHD'),
      });
      edges.push({ id: `e-${ltId}-${fhId}`, source: ltId, target: fhId, type: 'pipeline', data: { shotId: shot.id, segment: 'lighting-finalhd' } });

      // VideoGeneration (Col 8, lower)
      const viId = videoNodeId(shot.id);
      nodes.push({
        id: viId,
        type: 'videoGeneration',
        position: positionCache[viId] ?? { x: COL_X[8], y: shotY + BRANCH_GAP / 4 },
        data: {
          label: 'Video',
          status: (videoRun?.status as CanvasNodeStatus) || 'idle',
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'videoGeneration',
          sourceImageId: undefined,
          videoUrl: videoArtifact?.url,
          durationMs: shotDurationMs,
          progress: videoRun?.progress ?? 0,
          mode: 'image_to_video',
        } satisfies VideoGenerationNodeData,
        ...nodeDims('videoGeneration'),
      });
      edges.push({ id: `e-${fhId}-${viId}`, source: fhId, target: viId, type: 'pipeline', data: { shotId: shot.id, segment: 'finalhd-video' } });
    }

    // Advance Y: use pre-computed shot positions to determine total scene height
    const lastShotY = shotYPositions.length > 0 ? shotYPositions[shotYPositions.length - 1] : baseY;
    const lastShotBranches = sceneShots.length > 0 ? (() => {
      const s = sceneShots[sceneShots.length - 1];
      let cn = s.charactersInFrame?.length ? s.charactersInFrame : scene.characterNames;
      if ((!cn || cn.length === 0) && Object.keys(characterMap).length > 0) cn = Object.keys(characterMap);
      return 1 + (cn?.length || 0);
    })() : 1;
    const lastShotHeight = Math.max(NODE_HEIGHT, (lastShotBranches - 1) * BRANCH_GAP);
    currentY = lastShotY + lastShotHeight + SCENE_PADDING;
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

  const { positionCache = {} } = options;
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

    // Advance Y using dynamic per-shot branch heights
    {
      let nextY = 0;
      for (const s of sceneShots) {
        let cn = s.charactersInFrame?.length ? s.charactersInFrame : scene.characterNames;
        if ((!cn || cn.length === 0) && Object.keys(options.characterMap || {}).length > 0) cn = Object.keys(options.characterMap || {});
        const branches = 1 + (cn?.length || 0);
        const branchHeight = (branches - 1) * BRANCH_GAP;
        nextY += Math.max(SHOT_GAP, branchHeight + 120);
      }
      currentY += Math.max(NODE_HEIGHT, nextY) + SCENE_PADDING;
    }
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
