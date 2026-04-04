/* ══════════════════════════════════════════════════════════════
   Canvas Node Types
   ══════════════════════════════════════════════════════════════

   Section 1: 现有画布节点类型（React Flow production canvas）
   Section 2: 无限画布扩展类型（工作流模块、Agent、回写）
   ══════════════════════════════════════════════════════════════ */

// ═══════════════════════════════════════════════════════════════
// Section 1 — 现有 React Flow 画布节点
// ═══════════════════════════════════════════════════════════════

export type CanvasNodeStatus = 'idle' | 'queued' | 'running' | 'success' | 'error';

/* ---------- Base ---------- */
export interface BaseNodeData {
  [key: string]: unknown;
  label: string;
  status: CanvasNodeStatus;
  sceneId: string;
  shotId?: string;
  errorMessage?: string;
}

/* ---------- Scene ---------- */
export interface SceneNodeData extends BaseNodeData {
  nodeType: 'scene';
  heading: string;
  location: string;
  timeOfDay: string;
  description: string;
  characterNames: string[];
  order: number;
  shotCount: number;
  moduleType?: CanvasModuleType;
  coreEvent?: string;
  emotionalPeak?: string;
  narrativeMode?: string;
  panoramaStorageKey?: string;
  panoramaUrl?: string;
}

/* ---------- Character Reference (for prompt assembly) ---------- */
export interface CharacterRefInfo {
  name: string;
  visualRefUrl?: string;
  visualRefStorageKey?: string;
  appearanceDesc?: string;
  costumeDesc?: string;
  negativePrompt?: string;
}

/* ---------- Location Reference (for prompt assembly) ---------- */
export interface LocationRefInfo {
  name: string;
  visualRefUrl?: string;
  panoramaUrl?: string;
  visualDescription?: string;
  mood?: string;
  lighting?: string;
}

/* ---------- Shot ---------- */
export interface ShotNodeData extends BaseNodeData {
  nodeType: 'shot';
  shotNumber: number;
  framing: string;
  cameraAngle: string;
  cameraMovement: string;
  description: string;
  thumbnailUrl?: string;
  specId: string;
  moduleType?: CanvasModuleType;
  agentAssigned?: boolean;
  imagePrompt?: string;
  videoPrompt?: string;
  charactersInFrame?: string[];
  durationEstimateMs?: number;
  dialogueText?: string;
  emotionTarget?: string;
}

/* ---------- Prompt Assembly ---------- */
export interface PromptAssemblyNodeData extends BaseNodeData {
  nodeType: 'promptAssembly';
  assembledPrompt: string;
  characterRefs: CharacterRefInfo[];
  locationRef?: LocationRefInfo;
  styleTemplate?: string;
  emotionalContext?: string;
  narrativeMode?: string;
  timeOfDay?: string;
  negativePrompt?: string;
}

/* ---------- Image Generation ---------- */
export interface ImageCandidateItem {
  id: string;
  url?: string;
  status: 'draft' | 'approved' | 'rejected';
}

export interface ImageGenerationNodeData extends BaseNodeData {
  nodeType: 'imageGeneration';
  prompt: string;
  candidates: ImageCandidateItem[];
  selectedCandidateId?: string;
  progress: number;
  locationScreenshotUrl?: string;
  locationScreenshotStorageKey?: string;
  characterRefUrls?: string[];
  locationRefUrl?: string;
}

/* ---------- Video Generation ---------- */
export interface VideoGenerationNodeData extends BaseNodeData {
  nodeType: 'videoGeneration';
  sourceImageId?: string;
  videoUrl?: string;
  durationMs: number;
  progress: number;
  mode: 'text_to_video' | 'image_to_video' | 'scene_character_to_video';
}

/* ---------- Scene Background (VR panorama screenshot) ---------- */
export interface SceneBGNodeData extends BaseNodeData {
  nodeType: 'sceneBG';
  panoramaUrl?: string;
  panoramaStorageKey?: string;
  screenshotUrl?: string;
  viewAngle: { yaw: number; pitch: number };
  progress: number;
}

/* ---------- Character Process (asset image selection entry) ---------- */
export interface CharacterProcessNodeData extends BaseNodeData {
  nodeType: 'characterProcess';
  characterId?: string;
  characterName: string;
  /** Primary visual reference image URL (the image passed downstream) */
  visualRefUrl?: string;
  visualRefStorageKey?: string;
  /** All available image variants from asset library for user selection */
  availableImages?: Record<string, string>; // e.g. { front: url, side: url, full: url }
  /** Which variant the user selected as the pipeline input */
  selectedVariant?: string;
}

/* ---------- View Angle (RunningHub angle adjust) ---------- */
export interface ViewAngleNodeData extends BaseNodeData {
  nodeType: 'viewAngle';
  /** Input image URL (from CharacterProcess.visualRefUrl) */
  inputImageUrl?: string;
  inputStorageKey?: string;
  outputImageUrl?: string;
  outputStorageKey?: string;
  targetAngle: string;
  runninghubTaskId?: string;
  progress: number;
}

/* ---------- Expression (Gemini img2img — image-driven) ---------- */
export interface ExpressionNodeData extends BaseNodeData {
  nodeType: 'expression';
  /** Input image (from ViewAngle output — the angle-adjusted character image) */
  inputImageUrl?: string;
  inputStorageKey?: string;
  /** Output image after expression/action transform */
  outputImageUrl?: string;
  outputStorageKey?: string;
  /** Short instruction for Gemini (e.g. "angry shouting", "smiling gently") */
  expressionPrompt: string;
  emotion?: string;
  action?: string;
  negativePrompt?: string;
}

/* ---------- HD Upscale (stub) ---------- */
export interface HDUpscaleNodeData extends BaseNodeData {
  nodeType: 'hdUpscale';
  inputImageUrl?: string;
  outputImageUrl?: string;
  scaleFactor: number;
  progress: number;
}

/* ---------- Matting (RunningHub background removal) ---------- */
export interface MattingNodeData extends BaseNodeData {
  nodeType: 'matting';
  inputImageUrl?: string;
  outputPngUrl?: string;
  runninghubTaskId?: string;
  progress: number;
}

/* ---------- Prop Process (prop selection entry) ---------- */
export interface PropProcessNodeData extends BaseNodeData {
  nodeType: 'propProcess';
  propId?: string;
  propName: string;
  visualRefUrl?: string;
  visualRefStorageKey?: string;
}

/* ---------- Prop Angle (reuses viewAngle logic) ---------- */
export interface PropAngleNodeData extends BaseNodeData {
  nodeType: 'propAngle';
  inputImageUrl?: string;
  outputImageUrl?: string;
  targetAngle: string;
  runninghubTaskId?: string;
  progress: number;
}

/* ---------- Composite (PS-like layer editor) ---------- */
export interface CompositeLayerItem {
  id: string;
  type: 'background' | 'character' | 'prop';
  sourceNodeId: string;
  imageUrl?: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  zIndex: number;
  opacity: number;
  visible: boolean;
}

export interface CompositeNodeData extends BaseNodeData {
  nodeType: 'composite';
  layers: CompositeLayerItem[];
  outputImageUrl?: string;
  canvasWidth: number;
  canvasHeight: number;
  progress: number;
}

/* ---------- Blend Refine (stub) ---------- */
export interface BlendRefineNodeData extends BaseNodeData {
  nodeType: 'blendRefine';
  inputImageUrl?: string;
  outputImageUrl?: string;
  progress: number;
}

/* ---------- Lighting (stub) ---------- */
export interface LightingNodeData extends BaseNodeData {
  nodeType: 'lighting';
  inputImageUrl?: string;
  outputImageUrl?: string;
  lightingPreset: string;
  progress: number;
}

/* ---------- Final HD (stub) ---------- */
export interface FinalHDNodeData extends BaseNodeData {
  nodeType: 'finalHD';
  inputImageUrl?: string;
  outputImageUrl?: string;
  scaleFactor: number;
  progress: number;
}

/* ---------- Unified Image Process (replaces ViewAngle/Expression/HDUpscale/Matting) ---------- */
export type ImageProcessType = 'viewAngle' | 'expression' | 'hdUpscale' | 'matting';

export interface ImageProcessNodeData extends BaseNodeData {
  nodeType: 'imageProcess';
  processType: ImageProcessType;
  inputImageUrl?: string;
  inputStorageKey?: string;
  outputImageUrl?: string;
  outputStorageKey?: string;
  /** For matting: transparent PNG output */
  outputPngUrl?: string;
  /** viewAngle params */
  targetAngle?: string;
  azimuth?: number;      // -180 ~ +180, default 0
  elevation?: number;    // -30 ~ +60, default 0
  distance?: number;     // 0 ~ 10, default 5
  /** expression params */
  expressionPrompt?: string;
  emotion?: string;
  action?: string;
  /** hdUpscale params */
  scaleFactor?: number;
  /** RunningHub task tracking */
  runninghubTaskId?: string;
  progress: number;
}

/* ---------- Union ---------- */
export type CanvasNodeData =
  | SceneNodeData
  | ShotNodeData
  | PromptAssemblyNodeData
  | ImageGenerationNodeData
  | VideoGenerationNodeData
  | SceneBGNodeData
  | CharacterProcessNodeData
  | ViewAngleNodeData
  | ExpressionNodeData
  | HDUpscaleNodeData
  | MattingNodeData
  | PropProcessNodeData
  | PropAngleNodeData
  | CompositeNodeData
  | BlendRefineNodeData
  | LightingNodeData
  | FinalHDNodeData
  | ImageProcessNodeData;


// ═══════════════════════════════════════════════════════════════
// Section 2 — 无限画布扩展类型（5类模块、Agent、回写）
// ═══════════════════════════════════════════════════════════════

/* ── 5 大工作流模块类型 ── */

export type CanvasModuleType =
  | 'dialogue'    // 对话场景
  | 'action'      // 打斗动作
  | 'suspense'    // 悬疑揭秘
  | 'landscape'   // 环境转场
  | 'emotion';    // 情感内心

/* ── 视频平台 ── */

export type CanvasVideoProvider = 'jimeng' | 'kling' | 'runway' | 'pika';

/* ── 工作流步骤类型 ── */

export type CanvasWorkflowStepType =
  | 'generate-background'
  | 'generate-character'
  | 'remove-background'
  | 'composite-layers'
  | 'apply-filter'
  | 'adjust-lighting'
  | 'add-props'
  | 'motion-blur'
  | 'color-grade';

export interface CanvasWorkflowStep {
  id: string;
  name: string;
  type: CanvasWorkflowStepType;
  status: CanvasNodeStatus;
  params: Record<string, unknown>;
  resultUrl?: string;
  error?: string;
  optional?: boolean;
  defaultParams?: Record<string, unknown>;
}

/* ── 模块模板 ── */

export interface CanvasModuleStep {
  id: string;
  name: string;
  type: CanvasWorkflowStepType;
  description: string;
  defaultParams: Record<string, unknown>;
  optional: boolean;
}

export interface CanvasModuleTemplate {
  type: CanvasModuleType;
  label: string;
  description: string;
  icon: string;
  color: string;
  bgColor: string;
  steps: CanvasModuleStep[];
  defaultDuration: number;
  videoProvider: CanvasVideoProvider;
  detectionKeywords: string[];
}

/* ── Agent 任务 ── */

export type CanvasAgentTaskType =
  | 'analyze-storyboard'
  | 'assign-module'
  | 'generate-image-prompt'
  | 'generate-video-prompt'
  | 'review-composition'
  | 'batch-analyze-chapter';

export interface CanvasAgentTask {
  id: string;
  type: CanvasAgentTaskType;
  status: 'queued' | 'running' | 'done' | 'error';
  nodeId?: string;
  payload: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
  createdAt: number;
  startedAt?: number;
  completedAt?: number;
  retryCount: number;
}

/* ── 回写动作（Tapnow 式） ── */

export interface CanvasWriteBackAction {
  id: string;
  sourceNodeId: string;
  artifactId: string;
  targetType: 'beat' | 'scene' | 'shot' | 'asset';
  targetId: string;
  mode: 'append' | 'replace' | 'merge';
  status: 'pending' | 'confirmed' | 'rejected';
  diffPreview?: string;
}
