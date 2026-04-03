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
}

/* ---------- Prompt Assembly ---------- */
export interface PromptAssemblyNodeData extends BaseNodeData {
  nodeType: 'promptAssembly';
  assembledPrompt: string;
  characterRefs: string[];
  locationRef?: string;
  styleTemplate?: string;
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

/* ---------- Union ---------- */
export type CanvasNodeData =
  | SceneNodeData
  | ShotNodeData
  | PromptAssemblyNodeData
  | ImageGenerationNodeData
  | VideoGenerationNodeData;


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
