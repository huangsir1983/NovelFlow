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
  DirectorStage3DNodeData,
  GeminiCompositeNodeData,
  FinalHDNodeData,
  VideoGenerationNodeData,
  CanvasNodeStatus,
  CharacterRefInfo,
} from '../types/canvas';
import { detectModuleType } from '../components/production/canvas/ModuleTemplates';

/* ── Layout constants ── */
/**
 * 10-column layout — new pipeline with DirectorStage3D + GeminiComposite:
 *   Col 0  (0)    : Scene
 *   Col 1  (500)  : Shot
 *   Col 2  (1020) : SceneBG / CharacterProcess / PropProcess (branch split)
 *   Col 3  (1540) : (reserved)
 *   Col 4  (2060) : DirectorStage3D (merge point)
 *   Col 5  (2580) : GeminiComposite
 *   Col 6  (3120) : PostExpression
 *   Col 7  (3720) : FinalHD
 *   Col 8  (4320) : VideoGeneration
 */
const COL_X = [0, 500, 1020, 1540, 2060, 2580, 3120, 3720, 4320];
const SCENE_PADDING = 600;  // vertical padding between scene groups
const SHOT_GAP = 800;       // vertical gap between shots within a scene
const BRANCH_GAP = 400;     // vertical gap between branches (sceneBG, characters, props)
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
  finalHD: 240,
  imageProcess: 260,
  pose3D: 260,
  directorStage3D: 320,
  geminiComposite: 280,
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
export function expressionNodeId(shotId: string, charName: string) { return `expression-${shotId}-${charName}`; }
export function hdUpscaleNodeId(shotId: string, charName: string) { return `hdupscale-${shotId}-${charName}`; }
export function mattingNodeId(shotId: string, charName: string) { return `matting-${shotId}-${charName}`; }
export function propProcessNodeId(shotId: string, propIdx: number) { return `propproc-${shotId}-${propIdx}`; }
export function propAngleNodeId(shotId: string, propIdx: number) { return `propangle-${shotId}-${propIdx}`; }
export function compositeNodeId(shotId: string) { return `composite-${shotId}`; }
export function blendRefineNodeId(shotId: string) { return `blendrefine-${shotId}`; }
export function postExpressionNodeId(shotId: string) { return `imgproc-expression-${shotId}-scene`; }
export function finalHDNodeId(shotId: string) { return `finalhd-${shotId}`; }
export function imageProcessNodeId(shotId: string, charName: string, processType: string) { return `imgproc-${processType}-${shotId}-${charName}`; }
export function pose3DNodeId(shotId: string, charName: string) { return `pose3d-${shotId}-${charName}`; }
export function directorStage3DNodeId(shotId: string) { return `dirstage-${shotId}`; }
export function geminiCompositeNodeId(shotId: string) { return `geminicomp-${shotId}`; }

/* ── Script JSON types (from generated_script_json) ── */
interface ScriptShotJson {
  shot_type: string;
  camera_move: string;
  angle: string;
  subject: string;
  action: string;
  dialogue: { character: string; line: string; subtext?: string; delivery?: string } | null;
  characters?: Array<{ name: string; expression?: string; action?: string; position?: string }>;
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
  subject?: string;
  /** Per-character structured expression/action from generated_script_json */
  characterActions?: Record<string, { expression?: string; action?: string; position?: string }>;
}

/** Character visual data keyed by character name */
export interface CharacterMapEntry {
  id?: string;
  name: string;
  appearance?: { face?: string; body?: string; hair?: string; distinguishing_features?: string };
  costume?: { typical_outfit?: string };
  visualRefUrl?: string;
  visualRefStorageKey?: string;
  negativePrompt?: string;
  allImages?: Record<string, string>;
  allImageKeys?: Record<string, string>;
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
  /** {locationName: {panoramaUrl, panoramaStorageKey, depthMapUrl, viewpoints?}} — for populating SceneNode panorama data */
  locationPanoramaMap?: Record<string, { locationId?: string; panoramaUrl?: string; panoramaStorageKey?: string; depthMapUrl?: string; depthMapStorageKey?: string; viewpoints?: import('../types/canvas').ViewPoint[] }>;
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
      // Extract character names from structured characters array + dialogue
      const mentionedChars: string[] = [];
      if (shot.characters?.length) {
        for (const c of shot.characters) {
          if (c.name && !mentionedChars.includes(c.name)) mentionedChars.push(c.name);
        }
      }
      if (shot.dialogue?.character && !mentionedChars.includes(shot.dialogue.character)) {
        mentionedChars.push(shot.dialogue.character);
      }
      // Build per-character action/expression map from structured data
      const characterActions: Record<string, { expression?: string; action?: string; position?: string }> = {};
      if (shot.characters?.length) {
        for (const c of shot.characters) {
          if (c.name) {
            characterActions[c.name] = {
              expression: c.expression,
              action: c.action,
              position: c.position,
            };
          }
        }
      }
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
        subject: shot.subject || '',
        charactersInFrame: mentionedChars,
        dialogueText: shot.dialogue?.line || '',
        emotionTarget: shot.dialogue?.subtext || shot.dialogue?.delivery || '',
        characterActions: Object.keys(characterActions).length > 0 ? characterActions : undefined,
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
    locationDetailMap = {},
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

    // Helper: resolve character names for a shot (same logic used for both Y calc and node creation)
    // Strategy: precise extraction, not broad fallback.
    //   1. shot.charactersInFrame (explicit, e.g. from dialogue character or Shot table)
    //   2. scan shot.subject + shot.description for mentions of known character names
    //   3. Only for explicit Shot-table shots (no subject field): fallback to scene.characterNames
    const allCharNamesForScene = Object.keys(characterMap);
    // Sort by name length desc so "陆姝仪婢女" is checked before "陆姝仪"
    const charNamesByLen = [...allCharNamesForScene].sort((a, b) => b.length - a.length);
    const resolveCharNamesForShot = (s: ShotInput): string[] => {
      const found = new Set<string>();

      // 1. Explicit charactersInFrame (dialogue characters or Shot-table data)
      if (s.charactersInFrame?.length) {
        for (const n of s.charactersInFrame) {
          if (characterMap[n]) { found.add(n); continue; }
          const fuzzy = allCharNamesForScene.find(k => n.includes(characterMap[k].name) || characterMap[k].name.includes(n));
          if (fuzzy) found.add(fuzzy);
        }
      }

      // 2. Scan subject + description for character name mentions
      const textToScan = [s.subject, s.description].filter(Boolean).join(' ');
      if (textToScan && charNamesByLen.length > 0) {
        for (const cn of charNamesByLen) {
          if (textToScan.includes(cn)) found.add(cn);
        }
      }

      // 3. Fallback to scene characters ONLY for Shot-table entries (no subject = explicit shot)
      if (found.size === 0 && !s.subject && scene.characterNames?.length) {
        for (const n of scene.characterNames) {
          if (characterMap[n]) found.add(n);
          else {
            const fuzzy = allCharNamesForScene.find(k => n.includes(characterMap[k].name) || characterMap[k].name.includes(n));
            if (fuzzy) found.add(fuzzy);
          }
        }
      }

      return [...found];
    };

    // Pre-compute per-shot Y positions based on actual branch counts
    // Each shot's branches fan out vertically centered on shotY.
    // Actual vertical span = branchTotalHeight + sub-node offsets (BRANCH_GAP/2 above & below)
    //                        + tallest node height + safety margin
    const shotYPositions: number[] = [];
    {
      let nextY = baseY;
      for (const s of sceneShots) {
        shotYPositions.push(nextY);
        const resolvedNames = resolveCharNamesForShot(s);
        const branches = 1 + resolvedNames.length; // 1 sceneBG + N characters
        const branchTotalHeight = (branches - 1) * BRANCH_GAP;
        // Branches centered on shotY → extend branchTotalHeight/2 above and below
        // Sub-nodes (hdUpscale/matting) add BRANCH_GAP/4 above/below each character branch
        // Plus node height itself + comfortable margin
        const maxNodeH = branches > 1 ? (NODE_HEIGHTS.characterProcess || NODE_HEIGHT) : NODE_HEIGHT;
        const actualSpan = branchTotalHeight + maxNodeH + 100;
        nextY += Math.max(SHOT_GAP, actualSpan);
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
      // ── Build character refs for this shot (uses shared resolveCharNamesForShot helper) ──
      const resolvedCharNames = resolveCharNamesForShot(shot);
      const characterRefs: CharacterRefInfo[] = resolvedCharNames
        .map(n => characterMap[n])
        .filter((c): c is CharacterMapEntry => !!c)
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
          charactersInFrame: characterRefs.length > 0 ? characterRefs.map(c => c.name) : shot.charactersInFrame,
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
      const locationDetail2 = scene.location ? locationDetailMap[scene.location] : undefined;
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
          viewAngle: { yaw: 0, pitch: 0, fov: 75 },
          viewpoints: (locationPanorama2?.viewpoints?.length ?? 0) > 0
            ? locationPanorama2!.viewpoints!
            : [
                { id: 'vp-default-up', label: '上', yaw: 0, pitch: 0, fov: 75, posX: 0, posZ: 400, posY: 0, correctionStrength: 0.5, isDefault: true },
                { id: 'vp-default-down', label: '下', yaw: 180, pitch: 0, fov: 75, posX: 0, posZ: -400, posY: 0, correctionStrength: 0.5, isDefault: false },
                { id: 'vp-default-left', label: '左', yaw: -90, pitch: 0, fov: 75, posX: 400, posZ: 0, posY: 0, correctionStrength: 0.5, isDefault: false },
                { id: 'vp-default-right', label: '右', yaw: 90, pitch: 0, fov: 75, posX: -400, posZ: 0, posY: 0, correctionStrength: 0.5, isDefault: false },
              ],
          activeViewpointId: locationPanorama2?.viewpoints?.find(v => v.isDefault)?.id ?? 'vp-default-up',
          progress: 0,
          locationId: locationPanorama2?.locationId,
          locationName: scene.location || undefined,
          locationDescription: locationDetail2?.visualDescription,
          mood: locationDetail2?.mood,
          lighting: locationDetail2?.lighting,
          colorPalette: locationDetail2?.colorPalette,
          visualRefUrl: locationDetail2?.visualRefUrl,
          depthMapUrl: locationPanorama2?.depthMapUrl,
          depthMapStorageKey: locationPanorama2?.depthMapStorageKey,
        } satisfies SceneBGNodeData,
        ...nodeDims('sceneBG'),
      });
      edges.push({ id: `e-${shId}-${bgId}`, source: shId, target: bgId, type: 'pipeline', data: { shotId: shot.id, segment: 'shot-scenebg' } });

      // SceneBG feeds directly into DirectorStage3D (no more HDUpscale-BG)
      compositeSourceIds.push(bgId);

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // Character branches (Col 2): CharProcess → DirectorStage3D
      // (No more Pose3D, Expression, Matting — those are replaced by 3D stage)
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      for (const charRef of characterRefs) {
        const cn = charRef.name;
        const charY = branchBaseY + branchIdx * BRANCH_GAP;
        branchIdx++;
        const charEntry = characterMap[cn];

        // CharacterProcess (Col 2) — carries the character's reference IMAGE
        const cpId = charProcessNodeId(shot.id, cn);
        const charAllImages: Record<string, string> = { ...(charEntry?.allImages || {}) };
        if (charRef.visualRefUrl && !charAllImages['visual_reference']) {
          charAllImages['visual_reference'] = charRef.visualRefUrl;
        }
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
            characterId: charEntry?.id,
            characterName: cn,
            visualRefUrl: charRef.visualRefUrl,
            visualRefStorageKey: charRef.visualRefStorageKey,
            availableImages: charAllImages,
            selectedVariant: 'visual_reference',
          } satisfies CharacterProcessNodeData,
          ...nodeDims('characterProcess'),
        });
        edges.push({ id: `e-${shId}-${cpId}`, source: shId, target: cpId, type: 'pipeline', data: { shotId: shot.id, segment: `shot-char-${cn}` } });
        compositeSourceIds.push(cpId);
      }

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // DirectorStage3D node (Col 4) — merge point (replaces old Composite)
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      const dsId = directorStage3DNodeId(shot.id);
      nodes.push({
        id: dsId,
        type: 'directorStage3D',
        position: positionCache[dsId] ?? { x: COL_X[4], y: shotY },
        data: {
          label: '3D导演台',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'directorStage3D',
          sceneDescription: shot.description,
          characterActions: shot.characterActions,
          progress: 0,
        } satisfies DirectorStage3DNodeData,
        ...nodeDims('directorStage3D'),
      });
      // Connect all branch outputs → DirectorStage3D
      for (const srcId of compositeSourceIds) {
        edges.push({ id: `e-${srcId}-${dsId}`, source: srcId, target: dsId, type: 'pipeline', data: { shotId: shot.id, segment: 'branch-dirstage' } });
      }

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // GeminiComposite node (Col 5) — screenshot → Gemini image generation
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      const gcId = geminiCompositeNodeId(shot.id);
      nodes.push({
        id: gcId,
        type: 'geminiComposite',
        position: positionCache[gcId] ?? { x: COL_X[5], y: shotY },
        data: {
          label: 'Gemini合成',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'geminiComposite',
          sceneDescription: shot.description,
          progress: 0,
        } satisfies GeminiCompositeNodeData,
        ...nodeDims('geminiComposite'),
      });
      edges.push({ id: `e-${dsId}-${gcId}`, source: dsId, target: gcId, type: 'pipeline', data: { shotId: shot.id, segment: 'dirstage-geminicomp' } });

      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      // Post-GeminiComposite chain (Col 6-8): PostExpression → FinalHD → VideoGen
      // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

      const videoRun = runs.find((r) => r.nodeKey === 'video');
      const videoArtifact = artifacts.find((a) => a.type === 'video');

      // Post-composite Expression (Col 6) — Gemini img2img for scene refinement
      const peId = postExpressionNodeId(shot.id);
      nodes.push({
        id: peId,
        type: 'imageProcess',
        position: positionCache[peId] ?? { x: COL_X[6], y: shotY },
        data: {
          label: '表情',
          status: 'idle' as CanvasNodeStatus,
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'imageProcess',
          processType: 'expression' as ImageProcessNodeData['processType'],
          expressionPrompt: '以背景光源和色调为基准，将角色的光影、色域、边缘融合到背景中，使人物看起来真实存在于场景中。修复背景中的AI畸变和不自然纹理。保持角色的姿势、表情、服装和构图不变。',
          inputImageUrl: undefined,
          inputStorageKey: undefined,
          outputImageUrl: undefined,
          outputStorageKey: undefined,
          progress: 0,
        } satisfies ImageProcessNodeData,
        ...nodeDims('imageProcess'),
      });
      edges.push({ id: `e-${gcId}-${peId}`, source: gcId, target: peId, type: 'pipeline', data: { shotId: shot.id, segment: 'geminicomp-expression' } });

      // FinalHD (Col 7)
      const fhId = finalHDNodeId(shot.id);
      nodes.push({
        id: fhId,
        type: 'finalHD',
        position: positionCache[fhId] ?? { x: COL_X[7], y: shotY },
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
      edges.push({ id: `e-${peId}-${fhId}`, source: peId, target: fhId, type: 'pipeline', data: { shotId: shot.id, segment: 'expression-finalhd' } });

      // VideoGeneration (Col 8)
      const viId = videoNodeId(shot.id);
      nodes.push({
        id: viId,
        type: 'videoGeneration',
        position: positionCache[viId] ?? { x: COL_X[8], y: shotY },
        data: {
          label: 'Video',
          status: (videoRun?.status as CanvasNodeStatus) || 'idle',
          sceneId: scene.id,
          shotId: shot.id,
          nodeType: 'videoGeneration',
          videoUrl: videoArtifact?.url,
          durationMs: shotDurationMs,
          progress: videoRun?.progress ?? 0,
          mode: 'image_to_video',
          durationSeconds: Math.round((shotDurationMs || 5000) / 1000),
          ratio: '16:9',
          shotDescription: shot.description,
          shotFraming: shot.framing,
          shotCameraAngle: shot.cameraAngle,
          shotCameraMovement: shot.cameraMovement,
          shotDialogue: shot.dialogueText,
          shotEmotionTarget: shot.emotionTarget,
          shotCharactersInFrame: characterRefs.map(c => c.name),
          shotCharacterActions: shot.characterActions,
          sceneLocation: scene.location,
          sceneTimeOfDay: scene.timeOfDay,
          sceneDescription: scene.description,
          characterRefs: characterRefs.map(c => ({
            name: c.name,
            visualRefUrl: c.visualRefUrl,
            visualRefStorageKey: c.visualRefStorageKey,
          })),
        } satisfies VideoGenerationNodeData,
        ...nodeDims('videoGeneration'),
      });
      edges.push({ id: `e-${fhId}-${viId}`, source: fhId, target: viId, type: 'pipeline', data: { shotId: shot.id, segment: 'finalhd-video' } });
    }

    // Advance Y: use pre-computed shot positions to determine total scene height
    const lastShotY = shotYPositions.length > 0 ? shotYPositions[shotYPositions.length - 1] : baseY;
    const lastShotBranches = sceneShots.length > 0 ? (() => {
      const s = sceneShots[sceneShots.length - 1];
      return 1 + resolveCharNamesForShot(s).length;
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
      const charMap = options.characterMap || {};
      const knownCharNames = Object.keys(charMap);
      const knownByLen = [...knownCharNames].sort((a, b) => b.length - a.length);
      for (const s of sceneShots) {
        // Same resolution logic as resolveCharNamesForShot in buildCanvasGraph
        const found = new Set<string>();
        if (s.charactersInFrame?.length) {
          for (const n of s.charactersInFrame) {
            if (charMap[n]) found.add(n);
            else { const f = knownCharNames.find(k => n.includes(charMap[k]?.name) || charMap[k]?.name.includes(n)); if (f) found.add(f); }
          }
        }
        const text = [s.subject, s.description].filter(Boolean).join(' ');
        if (text) { for (const cn of knownByLen) { if (text.includes(cn)) found.add(cn); } }
        if (found.size === 0 && !s.subject && scene.characterNames?.length) {
          for (const n of scene.characterNames) { if (charMap[n]) found.add(n); }
        }
        const branches = 1 + found.size;
        const branchTotalHeight = (branches - 1) * BRANCH_GAP;
        const maxNodeH = branches > 1 ? (NODE_HEIGHTS.characterProcess || NODE_HEIGHT) : NODE_HEIGHT;
        const actualSpan = branchTotalHeight + maxNodeH + 100;
        nextY += Math.max(SHOT_GAP, actualSpan);
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
    const h = (n.type ? NODE_HEIGHTS[n.type] : undefined) || NODE_HEIGHT;
    minX = Math.min(minX, n.position.x);
    minY = Math.min(minY, n.position.y);
    maxX = Math.max(maxX, n.position.x + w);
    maxY = Math.max(maxY, n.position.y + h);
  }
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
}
