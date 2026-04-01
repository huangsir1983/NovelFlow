import type { Character, Location, Project, Prop, Scene, Shot } from '../types/project';
import type {
  AnimaticClipRef,
  AssetAnchor,
  AssetRequirement,
  BoardConsoleEntry,
  BoardReadinessSummary,
  SceneStoryboardReadinessReport,
  ShotNodeRun,
  ShotProductionProjection,
  ShotProductionSpec,
  ShotRuntimeArtifact,
  ShotStoryboardCheck,
  ShotVideoSequenceBundle,
  StoryboardChecklistItem,
  StoryboardReadinessStatus,
  StoryboardVideoMode,
  VideoModeDecision,
  WorkflowModule,
  WorkflowModuleCategory,
  WorkflowModuleNodeTemplate,
  WritebackPreview,
} from '../types/production';

const DEFAULT_DURATION_MS = 4000;

const PRODUCTION_NODE_CHAIN: WorkflowModuleNodeTemplate[] = [
  {
    id: 'story-input',
    kind: 'story_input',
    title: 'Story Input',
    description: 'Load the scene, beat, and shot story context for the current execution.',
    resultType: 'text',
    required: true,
  },
  {
    id: 'shot-check',
    kind: 'shot_check',
    title: 'Shot Check',
    description: 'Validate whether this shot is structurally sufficient for storyboard-video production.',
    resultType: 'text',
    required: true,
  },
  {
    id: 'mode-decision',
    kind: 'mode_decision',
    title: 'Mode Decision',
    description: 'Recommend the strongest available path across text, image, and scene-character modes.',
    resultType: 'text',
    required: true,
  },
  {
    id: 'character-anchor',
    kind: 'character_anchor',
    title: 'Character Anchor',
    description: 'Lock character references and consistency anchors for the active shot.',
    resultType: 'text',
    required: false,
  },
  {
    id: 'scene-anchor',
    kind: 'scene_anchor',
    title: 'Scene Anchor',
    description: 'Lock scene or location references when the selected mode depends on environment stability.',
    resultType: 'text',
    required: false,
  },
  {
    id: 'prompt-pack',
    kind: 'prompt_pack',
    title: 'Prompt Pack',
    description: 'Assemble story intent, visual goal, motion goal, and anchor constraints into one prompt pack.',
    resultType: 'text',
    required: true,
  },
  {
    id: 'initial-frame-generation',
    kind: 'initial_frame_generation',
    title: 'Initial Frame Generate',
    description: 'Generate initial frame candidates for the image-to-video path.',
    resultType: 'image',
    required: false,
  },
  {
    id: 'initial-frame-approval',
    kind: 'initial_frame_approval',
    title: 'Initial Frame Approval',
    description: 'Approve a single initial frame before motion generation continues.',
    resultType: 'image',
    required: false,
  },
  {
    id: 'storyboard-animatic-checkpoint',
    kind: 'storyboard_animatic_checkpoint',
    title: 'Storyboard Animatic Checkpoint',
    description: 'Preview rhythm and continuity using the shot card or approved frame before video generation.',
    resultType: 'image',
    required: true,
  },
  {
    id: 'video-generation',
    kind: 'video_generation',
    title: 'Video Generation',
    description: 'Generate the usable shot clip from the selected mode path.',
    resultType: 'video',
    required: true,
  },
  {
    id: 'video-compare',
    kind: 'video_compare',
    title: 'Video Compare / QA',
    description: 'Compare video takes for continuity, rhythm, and performance quality.',
    resultType: 'video',
    required: true,
  },
  {
    id: 'video-animatic-checkpoint',
    kind: 'video_animatic_checkpoint',
    title: 'Video Animatic Checkpoint',
    description: 'Check generated clips in sequence before approval and bundle output.',
    resultType: 'video',
    required: true,
  },
  {
    id: 'video-approval',
    kind: 'video_approval',
    title: 'Video Approval',
    description: 'Approve a single video take before the shot can enter the sequence bundle.',
    resultType: 'video',
    required: true,
  },
  {
    id: 'writeback',
    kind: 'writeback',
    title: 'Writeback + Bundle',
    description: 'Write approved outputs back to the shot and sequence bundle.',
    resultType: 'writeback',
    required: true,
  },
];

interface RawShotSeed {
  shotId: string;
  shotNumber: number;
  sceneId: string;
  sceneHeading?: string;
  sceneOrder: number;
  title: string;
  narrativeIntent: string;
  visualGoal: string;
  motionGoal?: string;
  charactersInFrame: string[];
  propNames: string[];
  locationName?: string;
  transitionHint?: string;
  estimatedDurationMs: number;
  order: number;
  subject?: string;
  action?: string;
  shotType?: string;
  framing?: string;
  cameraAngle?: string;
  cameraMove?: string;
  sceneContext?: string;
  promptSource?: string;
}

interface BuildProjectionInput {
  project: Project | null;
  scenes: Scene[];
  shots: Shot[];
  characters: Character[];
  locations: Location[];
  props: Prop[];
  assetImages: Record<string, Record<string, string>>;
  assetImageKeys: Record<string, Record<string, string>>;
  stylePreset?: string | null;
}

interface AssetWithPrompt {
  id: string;
  name: string;
  visual_reference?: string;
  visual_description?: string;
  description?: string;
  visual_prompt_negative?: string;
}

function nowIso() {
  return new Date().toISOString();
}

function toSlug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function normalizeText(value?: string | null) {
  return (value || '').trim();
}

function createChecklistItem(
  id: string,
  label: string,
  status: StoryboardChecklistItem['status'],
  detail: string,
  hardGate: boolean,
): StoryboardChecklistItem {
  return { id, label, status, detail, hardGate };
}

function createWorkflowModule(
  id: string,
  name: string,
  category: WorkflowModuleCategory,
  description: string,
  requiredAssets: Array<'character' | 'location' | 'prop' | 'style'>,
  optionalAssets: Array<'character' | 'location' | 'prop' | 'style'>,
  recommendedModelSet: string[],
  costProfile: 'low' | 'medium' | 'high',
  supportedVideoModes: StoryboardVideoMode[],
): WorkflowModule {
  return {
    id,
    name,
    category,
    description,
    inputContract: ['SceneStoryboardReadinessReport', 'ShotStoryboardCheck', 'AssetAnchor[]', 'VideoModeDecision'],
    outputContract: ['StoryboardAnimatic', 'VideoCandidates', 'ApprovedVideo', 'WritebackPreview'],
    requiredAssets,
    optionalAssets,
    nodeTemplate: PRODUCTION_NODE_CHAIN.map((node) => ({
      ...node,
      id: `${id}:${node.id}`,
    })),
    shareMode: 'team',
    version: 2,
    approvalGates: ['storyboard_animatic_checkpoint', 'video_animatic_checkpoint', 'video_approval'],
    costProfile,
    recommendedModelSet,
    supportedVideoModes,
    defaultVideoModePolicy: 'auto_recommend_override',
  };
}

function findBestReferenceKey(
  slotRecord: Record<string, string> | undefined,
  preferredKeys: string[],
) {
  if (!slotRecord) {
    return undefined;
  }

  for (const preferredKey of preferredKeys) {
    if (slotRecord[preferredKey]) {
      return preferredKey;
    }
  }

  return Object.keys(slotRecord)[0];
}

function parseDurationEstimate(rawValue?: string) {
  if (!rawValue) {
    return undefined;
  }

  const normalized = rawValue.trim().toLowerCase();
  const numeric = Number.parseFloat(normalized.replace(/[^0-9.]/g, ''));
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return undefined;
  }

  if (normalized.includes('ms')) {
    return numeric;
  }
  if (normalized.includes('min') || normalized.includes('m')) {
    return numeric * 60_000;
  }
  return numeric * 1000;
}

function sceneShotDurationMs(scene: Scene, totalShots: number) {
  const totalDurationMs =
    (scene.generated_script_json?.duration_estimate_s || scene.estimated_duration_s || 0) * 1000;
  if (totalDurationMs > 0 && totalShots > 0) {
    return Math.max(1200, Math.round(totalDurationMs / totalShots));
  }
  return scene.estimated_duration_s ? Math.max(1200, scene.estimated_duration_s * 1000) : DEFAULT_DURATION_MS;
}

function inferCharactersInFrame(
  subject: string | undefined,
  sceneCharacters: string[],
  dialogueCharacter?: string | null,
) {
  const subjectLower = normalizeText(subject).toLowerCase();
  const inferred = sceneCharacters.filter((name) => subjectLower.includes(name.toLowerCase()));
  if (dialogueCharacter && !inferred.includes(dialogueCharacter)) {
    inferred.push(dialogueCharacter);
  }
  return inferred.length > 0 ? inferred : sceneCharacters;
}

function buildGeneratedScriptSeeds(sortedScenes: Scene[]) {
  const seeds: RawShotSeed[] = [];

  sortedScenes.forEach((scene) => {
    const beats = scene.generated_script_json?.beats || [];
    if (beats.length === 0) {
      return;
    }

    const totalShots = beats.reduce((sum, beat) => sum + (beat.shots?.length || 0), 0);
    const durationMs = sceneShotDurationMs(scene, totalShots || 1);
    let sceneShotIndex = 0;

    beats.forEach((beat, beatIndex) => {
      (beat.shots || []).forEach((shot, shotIndex) => {
        sceneShotIndex += 1;
        const charactersInFrame = inferCharactersInFrame(
          shot.subject,
          scene.characters_present || [],
          shot.dialogue?.character || null,
        );
        const titleParts = [shot.shot_type, shot.subject || shot.action].filter(Boolean);
        seeds.push({
          shotId: `scene-${scene.id}-beat-${beatIndex + 1}-shot-${shotIndex + 1}`,
          shotNumber: sceneShotIndex,
          sceneId: scene.id,
          sceneHeading: scene.heading,
          sceneOrder: scene.order,
          title: titleParts.join(' · ') || `${scene.core_event || scene.heading || `Scene ${scene.order}`} Shot ${sceneShotIndex}`,
          narrativeIntent: normalizeText(shot.action) || normalizeText(scene.core_event) || normalizeText(scene.dramatic_purpose) || normalizeText(scene.heading),
          visualGoal: [shot.subject, shot.action, shot.shot_type].filter(Boolean).join(', ') || normalizeText(scene.visual_reference) || normalizeText(scene.description) || 'Build a usable storyboard shot',
          motionGoal: normalizeText(shot.camera_move) || normalizeText(scene.action) || normalizeText(scene.emotion_beat),
          charactersInFrame,
          propNames: scene.key_props || [],
          locationName: scene.location,
          transitionHint: shot.transition,
          estimatedDurationMs: durationMs,
          order: scene.order * 1000 + sceneShotIndex,
          subject: normalizeText(shot.subject),
          action: normalizeText(shot.action),
          shotType: normalizeText(shot.shot_type),
          framing: normalizeText(shot.shot_type),
          cameraAngle: normalizeText(shot.angle),
          cameraMove: normalizeText(shot.camera_move) || 'static',
          sceneContext: normalizeText(scene.heading) || normalizeText(scene.location),
          promptSource: normalizeText(shot.action) || normalizeText(scene.visual_reference),
        });
      });
    });
  });

  return seeds;
}

function buildRawShotSeeds(scenes: Scene[], shots: Shot[]): RawShotSeed[] {
  const sortedScenes = [...scenes].sort((left, right) => left.order - right.order);
  const sceneMap = new Map(sortedScenes.map((scene) => [scene.id, scene]));

  if (shots.length > 0) {
    return [...shots]
      .sort((left, right) => {
        const leftSceneOrder = sceneMap.get(left.scene_id)?.order ?? 0;
        const rightSceneOrder = sceneMap.get(right.scene_id)?.order ?? 0;
        if (leftSceneOrder !== rightSceneOrder) {
          return leftSceneOrder - rightSceneOrder;
        }
        return (left.order ?? left.shot_number) - (right.order ?? right.shot_number);
      })
      .map((shot, index) => {
        const scene = sceneMap.get(shot.scene_id);
        const subject = normalizeText(shot.characters_in_frame.join(', ')) || normalizeText(shot.goal);
        return {
          shotId: shot.id,
          shotNumber: shot.shot_number || index + 1,
          sceneId: shot.scene_id,
          sceneHeading: scene?.heading,
          sceneOrder: scene?.order ?? index,
          title: normalizeText(shot.goal) || normalizeText(scene?.heading) || `Shot ${index + 1}`,
          narrativeIntent: normalizeText(shot.goal) || normalizeText(scene?.core_event) || normalizeText(scene?.heading) || 'Clarify dramatic beat',
          visualGoal: normalizeText(shot.description) || normalizeText(shot.composition) || normalizeText(scene?.description) || normalizeText(scene?.visual_reference) || 'Build a usable shot keyframe',
          motionGoal: normalizeText(shot.camera_movement) || normalizeText(scene?.action) || normalizeText(scene?.emotion_beat),
          charactersInFrame: shot.characters_in_frame || scene?.characters_present || [],
          propNames: scene?.key_props || [],
          locationName: scene?.location,
          transitionHint: shot.transition_out || shot.transition_in,
          estimatedDurationMs:
            parseDurationEstimate(shot.duration_estimate) ||
            (scene?.estimated_duration_s ? scene.estimated_duration_s * 1000 : DEFAULT_DURATION_MS),
          order: index,
          subject,
          action: normalizeText(shot.description) || normalizeText(shot.goal),
          shotType: normalizeText(shot.composition),
          framing: normalizeText(shot.framing) || normalizeText(shot.composition),
          cameraAngle: normalizeText(shot.camera_angle),
          cameraMove: normalizeText(shot.camera_movement) || 'static',
          sceneContext: normalizeText(scene?.heading) || normalizeText(scene?.location),
          promptSource: normalizeText(shot.visual_prompt),
        };
      });
  }

  const generatedScriptSeeds = buildGeneratedScriptSeeds(sortedScenes);
  if (generatedScriptSeeds.length > 0) {
    return generatedScriptSeeds;
  }

  return sortedScenes.map((scene, index) => ({
    shotId: `scene-${scene.id}-shot-1`,
    shotNumber: 1,
    sceneId: scene.id,
    sceneHeading: scene.heading,
    sceneOrder: scene.order,
    title: normalizeText(scene.core_event) || normalizeText(scene.heading) || `Scene ${scene.order}`,
    narrativeIntent: normalizeText(scene.core_event) || normalizeText(scene.dramatic_purpose) || normalizeText(scene.heading) || 'Clarify the scene beat',
    visualGoal: normalizeText(scene.visual_reference) || normalizeText(scene.description) || normalizeText(scene.action) || 'Create a usable storyboard beat',
    motionGoal: normalizeText(scene.action) || normalizeText(scene.emotion_beat),
    charactersInFrame: scene.characters_present || [],
    propNames: scene.key_props || [],
    locationName: scene.location,
    transitionHint: undefined,
    estimatedDurationMs: (scene.estimated_duration_s || 4) * 1000,
    order: index,
    subject: normalizeText(scene.characters_present?.join(', ')),
    action: normalizeText(scene.action),
    shotType: normalizeText(scene.narrative_mode === 'action' ? 'wide shot' : 'medium shot'),
    framing: normalizeText(scene.narrative_mode === 'action' ? 'wide shot' : 'medium shot'),
    cameraAngle: '',
    cameraMove: 'static',
    sceneContext: normalizeText(scene.heading) || normalizeText(scene.location),
    promptSource: normalizeText(scene.visual_reference) || normalizeText(scene.description),
  }));
}

function buildAnchor(
  asset: AssetWithPrompt | undefined,
  assetType: AssetAnchor['assetType'],
  assetName: string,
  required: boolean,
  assetImages: Record<string, Record<string, string>>,
  assetImageKeys: Record<string, Record<string, string>>,
): AssetAnchor {
  if (!asset) {
    return {
      assetId: `${assetType}:${assetName}`,
      assetType,
      assetName,
      lockedImageSlots: {},
      status: 'missing',
      required,
      missingReason: `Missing ${assetType} anchor`,
    };
  }

  const slotRecord = assetImageKeys[asset.id] || assetImages[asset.id];
  const slotCount = Object.keys(slotRecord || {}).length;
  const hasTextReference = Boolean(asset.visual_reference || asset.visual_description || asset.description);

  let status: AssetAnchor['status'] = 'missing';
  if (slotCount >= 2 || (slotCount >= 1 && hasTextReference)) {
    status = 'ready';
  } else if (slotCount >= 1 || hasTextReference) {
    status = 'partial';
  }

  return {
    assetId: asset.id,
    assetType,
    assetName: asset.name,
    selectedReferenceKey: findBestReferenceKey(slotRecord, ['front_full', 'front', 'east', 'north']),
    lockedImageSlots: slotRecord || {},
    status,
    negativePrompt: asset.visual_prompt_negative,
    required,
    missingReason: status === 'ready' ? undefined : `Need stronger ${assetType} reference`,
  };
}

function buildStyleAnchor(stylePreset?: string | null): AssetAnchor {
  if (!stylePreset) {
    return {
      assetId: 'style:missing',
      assetType: 'style',
      assetName: 'Style preset',
      lockedImageSlots: {},
      status: 'missing',
      required: true,
      missingReason: 'Missing global style preset',
    };
  }

  return {
    assetId: `style:${stylePreset}`,
    assetType: 'style',
    assetName: stylePreset,
    selectedReferenceKey: stylePreset,
    lockedImageSlots: {},
    status: 'ready',
    required: true,
  };
}

function detectModuleCategory(seed: RawShotSeed, scene: Scene | undefined): WorkflowModuleCategory {
  const haystack = [
    seed.narrativeIntent,
    seed.visualGoal,
    seed.motionGoal,
    scene?.description,
    scene?.action,
    scene?.emotion_beat,
    scene?.key_dialogue,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  if (seed.shotNumber === 1 || /establish|opening|wide|全景|建立|环境/.test(haystack)) {
    return 'establishing';
  }
  if (/fight|battle|chase|run|追|打|冲突|搏斗/.test(haystack)) {
    return 'fight';
  }
  if (/follow|track|tracking|pan|跟拍|移动镜头|追踪/.test(haystack)) {
    return 'tracking_action';
  }
  if (/closeup|close-up|特写|emotion|泪|凝视|情绪/.test(haystack)) {
    return 'emotion_closeup';
  }
  if (/lyrical|memory|dream|montage|抒情|回忆|梦境|慢镜头/.test(haystack)) {
    return 'lyrical';
  }
  if (/transition|cutaway|match cut|转场|过渡/.test(haystack)) {
    return 'transition';
  }
  if ((scene?.dialogue?.length || 0) > 0 || scene?.narrative_mode === 'dialogue') {
    return 'dialogue';
  }
  return 'dialogue';
}

function evaluateSceneReadiness(scene: Scene, sceneSeeds: RawShotSeed[]): SceneStoryboardReadinessReport {
  const beatTotal = scene.generated_script_json?.beats?.length || 0;
  const coveredBeats = beatTotal > 0
    ? (scene.generated_script_json?.beats || []).filter((beat) => (beat.shots || []).length > 0).length
    : 0;

  const checklist: StoryboardChecklistItem[] = [
    createChecklistItem(
      'shot_coverage',
      'Shot coverage',
      sceneSeeds.length > 0 ? 'pass' : 'fail',
      sceneSeeds.length > 0 ? `Scene has ${sceneSeeds.length} storyboard shots.` : 'Scene has no usable storyboard shots.',
      true,
    ),
    createChecklistItem(
      'beat_coverage',
      'Beat coverage',
      beatTotal === 0 ? (sceneSeeds.length > 0 ? 'pass' : 'warn') : coveredBeats === beatTotal ? 'pass' : 'fail',
      beatTotal === 0
        ? sceneSeeds.length > 0
          ? 'No beat map was found, but explicit shot data is already available.'
          : 'No structured beat map was found; fallback logic will rely on scene or shot data.'
        : coveredBeats === beatTotal
          ? `All ${beatTotal} beats have at least one shot.`
          : `${beatTotal - coveredBeats} beats still lack shot coverage.`,
      beatTotal > 0,
    ),
    createChecklistItem(
      'narrative_goal',
      'Narrative goal',
      normalizeText(scene.core_event) || normalizeText(scene.dramatic_purpose) ? 'pass' : 'fail',
      normalizeText(scene.core_event) || normalizeText(scene.dramatic_purpose)
        ? 'Scene goal is explicit enough for storyboard-video planning.'
        : 'Scene is missing a clear core event or dramatic purpose.',
      true,
    ),
    createChecklistItem(
      'time_place',
      'Time and place',
      normalizeText(scene.location) && normalizeText(scene.time_of_day)
        ? 'pass'
        : normalizeText(scene.location) || normalizeText(scene.time_of_day)
          ? 'warn'
          : 'fail',
      normalizeText(scene.location) && normalizeText(scene.time_of_day)
        ? 'Scene location and time of day are both present.'
        : normalizeText(scene.location) || normalizeText(scene.time_of_day)
          ? 'One of location or time is missing.'
          : 'Scene is missing both location and time of day.',
      false,
    ),
    createChecklistItem(
      'characters',
      'Character presence',
      (scene.characters_present || []).length > 0 ? 'pass' : 'warn',
      (scene.characters_present || []).length > 0
        ? `${scene.characters_present?.length || 0} characters are attached to the scene.`
        : 'Scene has no explicit character list yet.',
      false,
    ),
    createChecklistItem(
      'visual_basis',
      'Visual basis',
      normalizeText(scene.visual_reference) || normalizeText(scene.description) || normalizeText(scene.action)
        ? 'pass'
        : 'warn',
      normalizeText(scene.visual_reference) || normalizeText(scene.description) || normalizeText(scene.action)
        ? 'Scene has enough visual basis to build storyboard intent.'
        : 'Scene lacks visual reference, description, and action detail.',
      false,
    ),
  ];

  const hardFails = checklist.filter((item) => item.hardGate && item.status === 'fail');
  const softIssues = checklist.filter((item) => !item.hardGate && item.status !== 'pass');
  const status: StoryboardReadinessStatus =
    hardFails.length > 0 ? 'blocked' : softIssues.length > 0 ? 'patchable' : 'ready';

  return {
    sceneId: scene.id,
    heading: scene.heading,
    order: scene.order,
    status,
    totalShotCount: sceneSeeds.length,
    readyShotIds: [],
    patchableShotIds: [],
    blockedShotIds: [],
    beatCoverage: { total: beatTotal, covered: coveredBeats },
    checklist,
    blockedReasons: hardFails.map((item) => item.detail),
    patchableReasons: softIssues.map((item) => item.detail),
  };
}

function getContinuityAnchorStatus(anchors: AssetAnchor[]): AssetAnchor['status'] {
  const readyCount = anchors.filter((anchor) => anchor.assetType !== 'style' && anchor.status === 'ready').length;
  const partialCount = anchors.filter((anchor) => anchor.assetType !== 'style' && anchor.status === 'partial').length;
  if (readyCount >= 2) {
    return 'ready';
  }
  if (readyCount >= 1 || partialCount >= 1) {
    return 'partial';
  }
  return 'missing';
}

function evaluatePromptCompleteness(seed: RawShotSeed) {
  const parts = [
    Boolean(normalizeText(seed.narrativeIntent)),
    Boolean(normalizeText(seed.visualGoal)),
    Boolean(normalizeText(seed.motionGoal) || normalizeText(seed.cameraMove)),
  ].filter(Boolean).length;

  if (parts >= 3) {
    return 'complete' as const;
  }
  if (parts >= 2) {
    return 'partial' as const;
  }
  return 'insufficient' as const;
}

function evaluateShotStoryboard(
  seed: RawShotSeed,
  continuityAnchorStatus: AssetAnchor['status'],
): ShotStoryboardCheck {
  const promptCompleteness = evaluatePromptCompleteness(seed);
  const hasDuration = seed.estimatedDurationMs > 0;
  const hasSceneContext = Boolean(normalizeText(seed.sceneContext) || normalizeText(seed.locationName));
  const checklist: StoryboardChecklistItem[] = [
    createChecklistItem(
      'subject',
      'Subject',
      normalizeText(seed.subject) || seed.charactersInFrame.length > 0 ? 'pass' : 'fail',
      normalizeText(seed.subject) || seed.charactersInFrame.length > 0
        ? 'Shot has a readable subject.'
        : 'Shot is missing a readable subject or main character.',
      true,
    ),
    createChecklistItem(
      'action',
      'Action',
      normalizeText(seed.action) ? 'pass' : 'fail',
      normalizeText(seed.action)
        ? 'Shot action is explicit.'
        : 'Shot is missing a concrete action description.',
      true,
    ),
    createChecklistItem(
      'framing',
      'Framing / shot type',
      normalizeText(seed.framing) || normalizeText(seed.shotType) ? 'pass' : 'fail',
      normalizeText(seed.framing) || normalizeText(seed.shotType)
        ? 'Shot framing or shot type is defined.'
        : 'Shot is missing framing or shot type.',
      true,
    ),
    createChecklistItem(
      'camera_angle',
      'Camera angle',
      normalizeText(seed.cameraAngle) ? 'pass' : 'fail',
      normalizeText(seed.cameraAngle)
        ? 'Camera angle is defined.'
        : 'Shot is missing a camera angle.',
      true,
    ),
    createChecklistItem(
      'camera_move',
      'Camera move',
      normalizeText(seed.cameraMove) && normalizeText(seed.cameraMove) !== 'static' ? 'pass' : 'warn',
      normalizeText(seed.cameraMove) && normalizeText(seed.cameraMove) !== 'static'
        ? 'Camera movement is defined.'
        : 'Camera move will fall back to static unless the user refines it.',
      false,
    ),
    createChecklistItem(
      'duration',
      'Duration',
      hasDuration ? 'pass' : 'fail',
      hasDuration ? `Shot duration is ${Math.round(seed.estimatedDurationMs / 100) / 10}s.` : 'Shot has no usable duration.',
      true,
    ),
    createChecklistItem(
      'scene_context',
      'Scene context',
      hasSceneContext ? 'pass' : 'fail',
      hasSceneContext ? 'Scene context is available.' : 'Shot is missing scene context.',
      true,
    ),
    createChecklistItem(
      'continuity_anchors',
      'Continuity anchors',
      continuityAnchorStatus === 'ready'
        ? 'pass'
        : continuityAnchorStatus === 'partial'
          ? 'warn'
          : 'fail',
      continuityAnchorStatus === 'ready'
        ? 'Continuity anchors are production-ready.'
        : continuityAnchorStatus === 'partial'
          ? 'Some continuity anchors are missing or weak.'
          : 'Continuity anchors are not ready yet.',
      false,
    ),
    createChecklistItem(
      'prompt_completeness',
      'Prompt completeness',
      promptCompleteness === 'complete'
        ? 'pass'
        : promptCompleteness === 'partial'
          ? 'warn'
          : 'fail',
      promptCompleteness === 'complete'
        ? 'Prompt ingredients are complete enough for strong generation control.'
        : promptCompleteness === 'partial'
          ? 'Prompt ingredients are usable but still thin.'
          : 'Prompt ingredients are too incomplete for stable generation.',
      false,
    ),
  ];

  const hardFails = checklist.filter((item) => item.hardGate && item.status === 'fail');
  const fallbackReasons = checklist
    .filter((item) => !item.hardGate && item.status !== 'pass')
    .map((item) => item.detail);
  const status =
    hardFails.length > 0
      ? 'blocked'
      : fallbackReasons.length > 0
        ? 'fallback_only'
        : 'ready';

  return {
    shotId: seed.shotId,
    sceneId: seed.sceneId,
    shotNumber: seed.shotNumber,
    status,
    promptCompleteness,
    continuityAnchorStatus,
    checklist,
    blockedReasons: hardFails.map((item) => item.detail),
    fallbackReasons,
  };
}

function buildVideoModeDecision(
  shotCheck: ShotStoryboardCheck,
  anchors: AssetAnchor[],
  hasStoryReadyScene: boolean,
): VideoModeDecision {
  const hasReadyCharacterAnchor = anchors.some(
    (anchor) => anchor.assetType === 'character' && anchor.status === 'ready',
  );
  const hasReadyLocationAnchor = anchors.some(
    (anchor) => anchor.assetType === 'location' && anchor.status === 'ready',
  );
  const hasReadyPrimaryVisualAnchor = hasReadyCharacterAnchor || hasReadyLocationAnchor;

  const blockedModes: Partial<Record<StoryboardVideoMode, string>> = {};
  const availableModes: StoryboardVideoMode[] = [];

  const canUseText =
    shotCheck.status !== 'blocked' &&
    shotCheck.promptCompleteness !== 'insufficient' &&
    hasStoryReadyScene;
  if (canUseText) {
    availableModes.push('text_to_video');
  } else {
    blockedModes.text_to_video =
      shotCheck.status === 'blocked'
        ? 'Shot checklist is blocked.'
        : 'Prompt ingredients are still insufficient for text-to-video.';
  }

  const canUseImage =
    shotCheck.status === 'ready' &&
    shotCheck.promptCompleteness === 'complete' &&
    hasReadyPrimaryVisualAnchor;
  if (canUseImage) {
    availableModes.push('image_to_video');
  } else {
    blockedModes.image_to_video =
      !hasReadyPrimaryVisualAnchor
        ? 'Image-to-video needs at least one ready character or location anchor.'
        : shotCheck.status !== 'ready'
          ? 'Image-to-video requires a fully ready storyboard shot.'
          : 'Prompt pack is not complete enough for a reliable initial frame.';
  }

  const canUseSceneCharacter =
    shotCheck.status !== 'blocked' &&
    shotCheck.promptCompleteness !== 'insufficient' &&
    hasReadyCharacterAnchor &&
    hasReadyLocationAnchor;
  if (canUseSceneCharacter) {
    availableModes.push('scene_character_to_video');
  } else {
    blockedModes.scene_character_to_video =
      !hasReadyCharacterAnchor || !hasReadyLocationAnchor
        ? 'Scene-character mode needs both ready character and location anchors.'
        : 'Storyboard shot is not stable enough yet.';
  }

  const recommendedMode = canUseImage
    ? 'image_to_video'
    : canUseSceneCharacter
      ? 'scene_character_to_video'
      : canUseText
        ? 'text_to_video'
        : undefined;

  const rationale = recommendedMode === 'image_to_video'
    ? 'Image-to-video is recommended because the shot is structurally ready and has a strong anchor for initial frame control.'
    : recommendedMode === 'scene_character_to_video'
      ? 'Scene-character mode is recommended because both scene and character anchors are ready while an initial frame path is weaker.'
      : recommendedMode === 'text_to_video'
        ? 'Text-to-video is the only safe fallback path right now and carries higher consistency risk.'
        : 'No video mode is currently available until the storyboard gate is fixed.';

  return {
    recommendedMode,
    selectedMode: recommendedMode,
    availableModes,
    blockedModes,
    defaultVideoModePolicy: 'auto_recommend_override',
    rationale,
  };
}

export function createDefaultWorkflowModules(): WorkflowModule[] {
  return [
    createWorkflowModule('establishing-module', '建立镜头模块', 'establishing', 'For location-first openings, geography setup, and atmosphere lock-in.', ['location', 'style'], ['character', 'prop'], ['Flux Kontext', 'Veo 2', 'Wan 2.1'], 'medium', ['image_to_video', 'text_to_video']),
    createWorkflowModule('dialogue-module', '对白镜头模块', 'dialogue', 'For shot-reverse-shot, coverage, and emotionally clear dialogue beats.', ['character', 'location', 'style'], ['prop'], ['Flux Kontext', 'Kling', 'Veo 2'], 'medium', ['image_to_video', 'scene_character_to_video', 'text_to_video']),
    createWorkflowModule('fight-module', '打斗镜头模块', 'fight', 'For action-heavy beats that need motion clarity and continuity control.', ['character', 'location', 'style'], ['prop'], ['Wan 2.1', 'Pika', 'Kling'], 'high', ['image_to_video', 'scene_character_to_video', 'text_to_video']),
    createWorkflowModule('lyrical-module', '抒情镜头模块', 'lyrical', 'For emotional montage, poetic motion, and mood-led beats.', ['character', 'style'], ['location', 'prop'], ['Flux Kontext', 'Hailuo', 'Veo 2'], 'medium', ['image_to_video', 'text_to_video']),
    createWorkflowModule('transition-module', '转场镜头模块', 'transition', 'For beat bridging, cutaways, and connective visual logic.', ['style'], ['character', 'location', 'prop'], ['Flux Kontext', 'Pika', 'Veo 2'], 'low', ['text_to_video', 'image_to_video']),
    createWorkflowModule('emotion-closeup-module', '情绪特写模块', 'emotion_closeup', 'For micro-expression, eye-line, and emotional punch-in shots.', ['character', 'style'], ['location'], ['Flux Kontext', 'Kling', 'Veo 2'], 'medium', ['image_to_video', 'text_to_video']),
    createWorkflowModule('tracking-action-module', '跟拍动作模块', 'tracking_action', 'For follow shots, chase shots, and camera-driven motion design.', ['character', 'location', 'style'], ['prop'], ['Wan 2.1', 'Kling', 'Pika'], 'high', ['image_to_video', 'scene_character_to_video', 'text_to_video']),
  ];
}

export function createInitialNodeRuns(spec: ShotProductionSpec, module: WorkflowModule): ShotNodeRun[] {
  return module.nodeTemplate.map((node) => {
    const baseStatus: ShotNodeRun['status'] =
      node.kind === 'story_input'
        ? 'succeeded'
        : node.kind === 'shot_check'
          ? spec.storyboardStatus === 'blocked'
            ? 'blocked'
            : 'succeeded'
          : node.kind === 'mode_decision'
            ? spec.videoModeDecision.availableModes.length > 0
              ? 'succeeded'
              : 'blocked'
            : spec.readiness === 'blocked'
              ? 'blocked'
              : 'idle';

    return {
      id: `${spec.shotId}:${node.id}`,
      shotId: spec.shotId,
      nodeId: node.id,
      kind: node.kind,
      label: node.title,
      status: baseStatus,
      updatedAt: nowIso(),
    };
  });
}

export function createEmptyWritebackPreview(spec: ShotProductionSpec): WritebackPreview {
  return {
    shotId: spec.shotId,
    reusableAnchorAssetIds: spec.anchors
      .filter((anchor) => anchor.status === 'ready' && anchor.assetType !== 'style')
      .map((anchor) => anchor.assetId),
    transitionHint: spec.transitionHint || 'cut',
    audioPlaceholder: `${spec.title} audio placeholder`,
    subtitlePlaceholder: `${spec.title} subtitle placeholder`,
  };
}

export function buildArtifactCandidates(
  spec: ShotProductionSpec,
  module: WorkflowModule,
  type: 'image' | 'video',
  existingArtifacts: ShotRuntimeArtifact[],
): ShotRuntimeArtifact[] {
  const selectedMode = spec.videoModeDecision.selectedMode;
  if (type === 'image' && selectedMode !== 'image_to_video') {
    return [];
  }

  const existingCount = existingArtifacts.filter((artifact) => artifact.type === type).length;
  const batchSize = type === 'image' ? 3 : 2;
  const nodeId = module.nodeTemplate.find((node) =>
    type === 'image'
      ? node.kind === 'initial_frame_generation'
      : node.kind === 'video_generation',
  )?.id;
  const promptSuffix =
    type === 'image'
      ? 'Generate a controllable initial frame for the selected shot.'
      : selectedMode === 'text_to_video'
        ? 'Generate the clip directly from the story prompt. High consistency risk.'
        : selectedMode === 'scene_character_to_video'
          ? 'Generate the clip from scene and character anchors plus the story prompt.'
          : 'Generate the clip from the approved initial frame.';

  return Array.from({ length: batchSize }, (_, index) => {
    const version = existingCount + index + 1;
    const safeSlug = toSlug(spec.title || spec.shotId) || spec.shotId;
    const riskTag = selectedMode === 'text_to_video' ? 'high_consistency_risk' : 'standard';

    return {
      id: `${spec.shotId}:${type}:${safeSlug}:${version}`,
      shotId: spec.shotId,
      nodeId: nodeId || `${module.id}:${type}`,
      type,
      label: `${type === 'image' ? '初始帧候选' : '视频候选'} ${version}`,
      status: 'draft',
      prompt: `${module.name} | ${spec.narrativeIntent}. ${spec.visualGoal}. ${promptSuffix}`,
      thumbnailText: `${module.name} · ${selectedMode || 'unassigned'} · v${version}`,
      version,
      durationMs: type === 'video' ? spec.estimatedDurationMs : undefined,
      costCredits: type === 'image' ? 1.4 + index * 0.3 : selectedMode === 'text_to_video' ? 6.8 + index * 0.7 : 7.5 + index * 0.9,
      createdAt: nowIso(),
      sourceAnchorKeys: spec.anchors
        .filter((anchor) => anchor.status !== 'missing')
        .map((anchor) => anchor.selectedReferenceKey || anchor.assetId),
      mode: selectedMode,
      riskTag,
    };
  });
}

export function getPreferredArtifact(
  artifacts: ShotRuntimeArtifact[],
  writeback: WritebackPreview | undefined,
  type: 'image' | 'video',
) {
  const preferredId = type === 'image' ? writeback?.recommendedImageArtifactId : writeback?.approvedVideoArtifactId;
  if (preferredId) {
    const preferredArtifact = artifacts.find((artifact) => artifact.id === preferredId);
    if (preferredArtifact) {
      return preferredArtifact;
    }
  }
  return artifacts.find((artifact) => artifact.type === type && artifact.status === 'approved');
}

export function getShotLifecycleState(
  spec: ShotProductionSpec,
  artifacts: ShotRuntimeArtifact[],
  writeback: WritebackPreview | undefined,
) {
  if (spec.readiness === 'blocked') {
    return 'blocked';
  }
  const approvedVideo = getPreferredArtifact(artifacts, writeback, 'video');
  if (approvedVideo) {
    return 'approved';
  }
  if (artifacts.some((artifact) => artifact.type === 'video')) {
    return 'video_review';
  }
  const approvedImage = getPreferredArtifact(artifacts, writeback, 'image');
  if (approvedImage) {
    return 'storyboard_ready';
  }
  if (artifacts.some((artifact) => artifact.type === 'image')) {
    return 'frame_review';
  }
  if (spec.storyboardAnimaticEligible) {
    return 'story_ready';
  }
  return 'ready';
}

export function buildShotProductionProjection({
  project,
  scenes,
  shots,
  characters,
  locations,
  props,
  assetImages,
  assetImageKeys,
  stylePreset,
}: BuildProjectionInput): ShotProductionProjection {
  const modules = createDefaultWorkflowModules();
  const moduleMap = new Map(modules.map((module) => [module.category, module]));
  const sceneMap = new Map(scenes.map((scene) => [scene.id, scene]));
  const characterMap = new Map(characters.map((character) => [character.name, character]));
  const locationMap = new Map(locations.map((location) => [location.name, location]));
  const propMap = new Map(props.map((prop) => [prop.name, prop]));
  const effectiveStylePreset = stylePreset || project?.style_preset || undefined;

  const rawSeeds = buildRawShotSeeds(scenes, shots);
  const sceneReports = [...scenes]
    .sort((left, right) => left.order - right.order)
    .map((scene) => evaluateSceneReadiness(scene, rawSeeds.filter((seed) => seed.sceneId === scene.id)));
  const sceneReportMap = new Map(sceneReports.map((report) => [report.sceneId, report]));

  const specs = rawSeeds.map((seed) => {
    const scene = sceneMap.get(seed.sceneId);
    const category = detectModuleCategory(seed, scene);
    const primaryModule = moduleMap.get(category) || modules[0];
    const alternateModules = modules
      .filter((module) => module.category !== category)
      .slice(0, 2)
      .map((module) => module.id);
    const anchors: AssetAnchor[] = [];

    seed.charactersInFrame.forEach((characterName) => {
      anchors.push(buildAnchor(characterMap.get(characterName), 'character', characterName, true, assetImages, assetImageKeys));
    });
    if (seed.locationName) {
      anchors.push(buildAnchor(locationMap.get(seed.locationName), 'location', seed.locationName, true, assetImages, assetImageKeys));
    }
    seed.propNames.forEach((propName) => {
      anchors.push(buildAnchor(propMap.get(propName), 'prop', propName, true, assetImages, assetImageKeys));
    });
    anchors.push(buildStyleAnchor(effectiveStylePreset));

    const continuityAnchorStatus = getContinuityAnchorStatus(anchors);
    const shotCheck = evaluateShotStoryboard(seed, continuityAnchorStatus);
    const sceneReport = sceneReportMap.get(seed.sceneId);
    const videoModeDecision = buildVideoModeDecision(
      shotCheck,
      anchors,
      (sceneReport?.status || 'blocked') !== 'blocked',
    );

    const blockedReasons = [
      ...((sceneReport?.status || 'blocked') === 'blocked'
        ? sceneReport?.blockedReasons || ['Scene storyboard readiness is blocked.']
        : []),
      ...shotCheck.blockedReasons,
      ...(videoModeDecision.availableModes.length === 0 ? ['No storyboard-video mode is currently available.'] : []),
    ];

    return {
      shotId: seed.shotId,
      shotNumber: seed.shotNumber,
      sceneId: seed.sceneId,
      sceneHeading: seed.sceneHeading,
      sceneOrder: seed.sceneOrder,
      title: seed.title,
      moduleId: primaryModule.id,
      recommendedModuleIds: [primaryModule.id, ...alternateModules],
      narrativeIntent: seed.narrativeIntent,
      visualGoal: seed.visualGoal,
      motionGoal: seed.motionGoal,
      anchors,
      stylePreset: effectiveStylePreset,
      readiness: blockedReasons.length === 0 ? 'ready' : 'blocked',
      blockedReasons,
      estimatedDurationMs: seed.estimatedDurationMs,
      transitionHint: seed.transitionHint,
      charactersInFrame: seed.charactersInFrame,
      storyboardStatus: shotCheck.status,
      storyboardChecklist: shotCheck.checklist,
      storyboardBlockedReasons: shotCheck.blockedReasons,
      storyboardFallbackReasons: shotCheck.fallbackReasons,
      storyboardAnimaticEligible: shotCheck.status !== 'blocked' && (sceneReport?.status || 'blocked') !== 'blocked',
      sceneReadinessStatus: sceneReport?.status || 'blocked',
      videoModeDecision,
    } satisfies ShotProductionSpec;
  });

  const reportState = new Map(sceneReports.map((report) => [report.sceneId, { ...report }]));
  specs.forEach((spec) => {
    const report = reportState.get(spec.sceneId);
    if (!report) {
      return;
    }
    if (spec.storyboardStatus === 'blocked' || spec.readiness === 'blocked') {
      report.blockedShotIds.push(spec.shotId);
    } else if (spec.storyboardStatus === 'fallback_only') {
      report.patchableShotIds.push(spec.shotId);
    } else {
      report.readyShotIds.push(spec.shotId);
    }
  });

  const finalizedSceneReports = Array.from(reportState.values()).sort((left, right) => left.order - right.order);

  const requirements = specs.flatMap((spec) =>
    spec.anchors
      .filter((anchor) => anchor.status !== 'ready')
      .map((anchor) => ({
        shotId: spec.shotId,
        shotTitle: spec.title,
        sceneId: spec.sceneId,
        assetId: anchor.assetId,
        assetType: anchor.assetType,
        assetName: anchor.assetName || anchor.assetId,
        status: anchor.status,
        reason: anchor.missingReason || 'Need stronger asset anchor',
        blocking: Boolean(anchor.required),
        recommendedModuleIds: spec.recommendedModuleIds,
      }) satisfies AssetRequirement),
  );

  const readiness = specs.reduce<BoardReadinessSummary>(
    (summary, spec) => {
      summary.totalShots += 1;
      if (spec.readiness === 'ready') {
        summary.readyShots += 1;
      } else {
        summary.blockedShots += 1;
      }

      spec.anchors.forEach((anchor) => {
        if (anchor.status === 'ready') {
          return;
        }
        if (anchor.assetType === 'character') {
          summary.missingCharacterAnchors += 1;
        } else if (anchor.assetType === 'location') {
          summary.missingLocationAnchors += 1;
        } else if (anchor.assetType === 'prop') {
          summary.missingPropAnchors += 1;
        } else if (anchor.assetType === 'style') {
          summary.missingStyleAnchors += 1;
        }
      });

      return summary;
    },
    {
      totalShots: 0,
      readyShots: 0,
      blockedShots: 0,
      missingCharacterAnchors: 0,
      missingLocationAnchors: 0,
      missingPropAnchors: 0,
      missingStyleAnchors: 0,
    },
  );

  return {
    sceneReports: finalizedSceneReports,
    specs,
    requirements,
    readiness,
    modules,
  };
}

export function buildAnimaticClips(
  specs: ShotProductionSpec[],
  artifactsByShotId: Record<string, ShotRuntimeArtifact[]>,
  writebacksByShotId: Record<string, WritebackPreview>,
  durationOverrides: Record<string, number> = {},
): AnimaticClipRef[] {
  return specs.flatMap((spec, index) => {
    const artifacts = artifactsByShotId[spec.shotId] || [];
    const writeback = writebacksByShotId[spec.shotId];
    const approvedVideo = getPreferredArtifact(artifacts, writeback, 'video');
    const approvedImage = getPreferredArtifact(artifacts, writeback, 'image');
    const transitionHint = writeback?.transitionHint || spec.transitionHint;
    const mode = spec.videoModeDecision.selectedMode;
    const storyboardDurationMs =
      durationOverrides[spec.shotId] || spec.estimatedDurationMs || DEFAULT_DURATION_MS;
    const videoDurationMs =
      durationOverrides[spec.shotId] ||
      approvedVideo?.durationMs ||
      spec.estimatedDurationMs ||
      DEFAULT_DURATION_MS;
    const clips: AnimaticClipRef[] = [];

    if (spec.storyboardAnimaticEligible) {
      let heat: AnimaticClipRef['heat'] = 'stable';
      let issueSummary: string | undefined;

      if (spec.storyboardStatus === 'fallback_only') {
        heat = 'watch';
        issueSummary = 'Storyboard is usable but still needs stronger continuity anchors or prompt detail.';
      }
      if (mode === 'text_to_video') {
        heat = heat === 'stable' ? 'watch' : 'conflict';
        issueSummary = issueSummary || 'Storyboard only supports text-to-video fallback, so consistency risk is elevated.';
      }
      if (!transitionHint && index > 0) {
        heat = heat === 'conflict' ? 'conflict' : 'watch';
        issueSummary = issueSummary || 'Transition hint is missing for this storyboard clip.';
      }

      clips.push({
        shotId: spec.shotId,
        sourceType: 'image',
        artifactId: approvedImage?.id || `storyboard:${spec.shotId}`,
        durationMs: storyboardDurationMs,
        transitionHint,
        cameraMove: spec.motionGoal,
        sourceNodeId: approvedImage?.nodeId || `${spec.moduleId}:storyboard-animatic-checkpoint`,
        sourceModuleId: spec.moduleId,
        sourceArtifactVersion: approvedImage?.version,
        heat,
        issueSummary,
        label: `${spec.title} · storyboard`,
        phase: 'storyboard',
        mode,
        riskTag: mode === 'text_to_video' ? 'high_consistency_risk' : 'standard',
      });
    }

    if (approvedVideo) {
      let heat: AnimaticClipRef['heat'] = 'stable';
      let issueSummary: string | undefined;

      if (videoDurationMs < 1200 || videoDurationMs > 9000) {
        heat = 'watch';
        issueSummary = 'Video duration looks outside the normal short-form rhythm range.';
      }
      if (mode === 'text_to_video') {
        heat = heat === 'stable' ? 'watch' : 'conflict';
        issueSummary = issueSummary || 'This approved video came from the text-to-video fallback path.';
      }

      clips.push({
        shotId: spec.shotId,
        sourceType: 'video',
        artifactId: approvedVideo.id,
        durationMs: videoDurationMs,
        transitionHint,
        cameraMove: spec.motionGoal,
        sourceNodeId: approvedVideo.nodeId,
        sourceModuleId: spec.moduleId,
        sourceArtifactVersion: approvedVideo.version,
        heat,
        issueSummary,
        label: `${spec.title} · video`,
        phase: 'video',
        mode,
        riskTag: approvedVideo.riskTag || (mode === 'text_to_video' ? 'high_consistency_risk' : 'standard'),
      });
    }

    return clips;
  });
}

export function buildSequenceBundle(
  projectId: string,
  specs: ShotProductionSpec[],
  artifactsByShotId: Record<string, ShotRuntimeArtifact[]>,
  writebacksByShotId: Record<string, WritebackPreview>,
  animaticClips: AnimaticClipRef[],
): ShotVideoSequenceBundle | null {
  if (!projectId) {
    return null;
  }

  const approvedShotPairs = specs.flatMap((spec) => {
    const artifact = getPreferredArtifact(
      artifactsByShotId[spec.shotId] || [],
      writebacksByShotId[spec.shotId],
      'video',
    );
    return artifact ? [[spec, artifact] as const] : [];
  });

  if (approvedShotPairs.length === 0) {
    return null;
  }

  return {
    id: `sequence:${projectId}`,
    projectId,
    shotIds: approvedShotPairs.map(([spec]) => spec.shotId),
    videoArtifactIds: approvedShotPairs.map(([, artifact]) => artifact.id),
    animaticBundleId: animaticClips.some((clip) => clip.phase === 'video')
      ? `animatic:video:${projectId}`
      : animaticClips.some((clip) => clip.phase === 'storyboard')
        ? `animatic:storyboard:${projectId}`
        : undefined,
    status: approvedShotPairs.length === specs.length ? 'approved' : 'draft',
    exportTarget: approvedShotPairs.length === specs.length ? 'jianying' : 'preview',
    shotOrder: approvedShotPairs.map(([spec]) => spec.shotId),
    transitionHints: approvedShotPairs.map(
      ([spec]) => writebacksByShotId[spec.shotId]?.transitionHint || spec.transitionHint || 'cut',
    ),
    audioPlaceholders: approvedShotPairs.map(
      ([spec]) => writebacksByShotId[spec.shotId]?.audioPlaceholder || `${spec.title} audio placeholder`,
    ),
    subtitlePlaceholders: approvedShotPairs.map(
      ([spec]) => writebacksByShotId[spec.shotId]?.subtitlePlaceholder || `${spec.title} subtitle placeholder`,
    ),
    createdAt: nowIso(),
    consistencyRiskShotIds: approvedShotPairs
      .filter(([spec]) => spec.videoModeDecision.selectedMode === 'text_to_video')
      .map(([spec]) => spec.shotId),
    videoModesByShot: Object.fromEntries(
      approvedShotPairs.map(([spec]) => [spec.shotId, spec.videoModeDecision.selectedMode]),
    ),
  };
}

export function createBoardConsoleEntry(
  shotId: string,
  message: string,
  level: BoardConsoleEntry['level'] = 'info',
): BoardConsoleEntry {
  return {
    id: `${shotId}:${level}:${Date.now()}`,
    shotId,
    level,
    message,
    createdAt: nowIso(),
  };
}
