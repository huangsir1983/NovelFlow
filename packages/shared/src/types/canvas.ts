/* ══════════════════════════════════════════════════════════════
   Canvas Node Types — 无限画布完整类型系统
   ══════════════════════════════════════════════════════════════ */

// ── 基础几何 ──

export interface CanvasPoint {
  x: number;
  y: number;
}

export interface CanvasRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CanvasTransform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

// ── 节点状态 ──

export type CanvasNodeStatus =
  | 'idle'        // 未开始
  | 'ready'       // 就绪（上游均完成）
  | 'processing'  // 处理中
  | 'done'        // 完成
  | 'error'       // 失败
  | 'outdated';   // 上游已修改，需重新生成

// ── 节点类型枚举 ──

export type CanvasNodeType =
  | 'storyboard'  // 分镜文本
  | 'image'       // 图片合成
  | 'video'       // 视频生成
  | 'text-note'   // 文本注释
  | 'asset-ref';  // 资产引用

// ── 5 大工作流模块类型 ──

export type CanvasModuleType =
  | 'dialogue'    // 对话场景
  | 'action'      // 打斗动作
  | 'suspense'    // 悬疑揭秘
  | 'landscape'   // 环境转场
  | 'emotion';    // 情感内心

// ── 镜头类型 ──

export type CanvasShotType =
  | 'close-up'       // 特写
  | 'medium'         // 中景
  | 'wide'           // 远景
  | 'overhead'       // 俯视
  | 'low-angle'      // 仰视
  | 'pov'            // 主观视角
  | 'over-shoulder'; // 过肩

// ── 视频平台 ──

export type CanvasVideoProvider = 'jimeng' | 'kling' | 'runway' | 'pika';
export type CanvasVideoResolution = '720p' | '1080p' | '4k';

// ── 工作流步骤类型 ──

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

// ══════════════════════════════════════════════════════════════
// 节点数据
// ══════════════════════════════════════════════════════════════

export interface CanvasNodeData {
  id: string;
  type: CanvasNodeType;
  position: CanvasPoint;
  size: { width: number; height: number };
  status: CanvasNodeStatus;
  label: string;
  chapterId: string;
  sceneId: string;
  moduleType?: CanvasModuleType;
  moduleId?: string;

  content: StoryboardContent | ImageContent | VideoContent | TextNoteContent;

  upstreamIds: string[];
  downstreamIds: string[];

  createdAt: number;
  updatedAt: number;
  agentAssigned: boolean;
}

// ── 分镜文本节点内容 ──

export interface StoryboardContent {
  rawText: string;
  imagePrompt: string;
  videoPrompt: string;
  characterIds: string[];
  sceneAssetId?: string;
  propIds: string[];
  shotType: CanvasShotType;
  emotion: string;
  duration: number;
}

// ── 图片合成节点内容 ──

export interface ImageContent {
  workflowSteps: CanvasWorkflowStep[];
  resultImageUrl?: string;
  intermediateUrls: string[];
  width: number;
  height: number;
  sourceStoryboardId: string;
}

// ── 视频生成节点内容 ──

export interface VideoContent {
  provider: CanvasVideoProvider;
  videoPrompt: string;
  duration: number;
  fps: number;
  resolution: CanvasVideoResolution;
  resultVideoUrl?: string;
  thumbnailUrl?: string;
  sourceImageId: string;
  jobId?: string;
}

// ── 文本注释节点内容 ──

export interface TextNoteContent {
  text: string;
  color: string;
}

// ══════════════════════════════════════════════════════════════
// 工作流步骤
// ══════════════════════════════════════════════════════════════

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

// ══════════════════════════════════════════════════════════════
// 模块区域块
// ══════════════════════════════════════════════════════════════

export interface CanvasModuleBlock {
  id: string;
  type: CanvasModuleType;
  label: string;
  chapterId: string;
  position: CanvasPoint;
  size: { width: number; height: number };
  nodeIds: string[];
  collapsed: boolean;
  color: string;
  progress: { done: number; total: number };
}

// ══════════════════════════════════════════════════════════════
// 连线
// ══════════════════════════════════════════════════════════════

export interface CanvasConnection {
  id: string;
  fromNodeId: string;
  toNodeId: string;
  type: 'data-flow' | 'dependency';
}

// ══════════════════════════════════════════════════════════════
// 画布视图状态
// ══════════════════════════════════════════════════════════════

export interface CanvasViewState {
  transform: CanvasTransform;
  selectedNodeIds: Set<string>;
  hoveredNodeId: string | null;
  visibleRect: CanvasRect;
}

// ══════════════════════════════════════════════════════════════
// 项目资产（画布内部使用）
// ══════════════════════════════════════════════════════════════

export interface CanvasProjectAsset {
  id: string;
  type: 'character' | 'scene' | 'prop';
  name: string;
  imageUrl: string;
  thumbnailUrl: string;
  description: string;
  tags: string[];
  characterTraits?: string[];
  timeOfDay?: 'dawn' | 'morning' | 'afternoon' | 'evening' | 'night';
  propCategory?: string;
}

// ══════════════════════════════════════════════════════════════
// 分镜链
// ══════════════════════════════════════════════════════════════

export interface CanvasStoryboardChain {
  id: string;
  chapterId: string;
  sceneName: string;
  moduleType: CanvasModuleType;
  nodeIds: string[];        // [storyboardId, imageId, videoId]
  status: 'pending' | 'partial' | 'complete';
  estimatedCost?: number;
}

// ══════════════════════════════════════════════════════════════
// Agent 任务
// ══════════════════════════════════════════════════════════════

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

// ══════════════════════════════════════════════════════════════
// 执行计划
// ══════════════════════════════════════════════════════════════

export interface CanvasExecutionPlan {
  id: string;
  chains: CanvasStoryboardChain[];
  totalNodes: number;
  estimatedMinutes: number;
  estimatedApiCalls: number;
  parallelGroups: string[][];
}

// ══════════════════════════════════════════════════════════════
// 画布章节 / 场景结构（来自前置环节映射）
// ══════════════════════════════════════════════════════════════

export interface CanvasChapter {
  id: string;
  title: string;
  order: number;
  scenes: string[];
  plotLineId: string;
}

export interface CanvasScene {
  id: string;
  chapterId: string;
  title: string;
  order: number;
  rawScript: string;
  storyboards: string[];
  location: string;
  timeOfDay: string;
  characterIds: string[];
  mood: string;
}

// ══════════════════════════════════════════════════════════════
// 模块模板（用于 ModuleTemplates.ts）
// ══════════════════════════════════════════════════════════════

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

// ══════════════════════════════════════════════════════════════
// 工作流回写动作（Tapnow 式）
// ══════════════════════════════════════════════════════════════

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

// ══════════════════════════════════════════════════════════════
// Workflow JSON（持久化结构）
// ══════════════════════════════════════════════════════════════

export interface CanvasWorkflowData {
  id: string;
  projectId: string;
  name: string;
  status: 'draft' | 'active' | 'archived';
  templateId?: string;
  nodes: CanvasNodeData[];
  connections: CanvasConnection[];
  modules: CanvasModuleBlock[];
  viewport: CanvasTransform;
  writeBackActions: CanvasWriteBackAction[];
  createdAt: string;
  updatedAt: string;
}
