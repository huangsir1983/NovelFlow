// ============================================================
// 核心类型定义 - 无限画布小说到视频制作系统
// ============================================================

// ---------------------------
// 基础几何类型
// ---------------------------
export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Transform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

// ---------------------------
// 节点类型枚举
// ---------------------------
export type NodeType = 'storyboard' | 'image' | 'video' | 'text-note' | 'asset-ref';

export type NodeStatus =
  | 'idle'        // 未开始
  | 'ready'       // 就绪（依赖已满足）
  | 'processing'  // 处理中
  | 'done'        // 完成
  | 'error'       // 失败
  | 'outdated';   // 上游已修改，需重新生成

// ---------------------------
// 模块类型（5大工作流模块）
// ---------------------------
export type ModuleType =
  | 'dialogue'   // 对话场景模块
  | 'action'     // 打斗动作模块
  | 'suspense'   // 悬疑揭秘模块
  | 'landscape'  // 环境转场模块
  | 'emotion';   // 情感内心模块

// ---------------------------
// 节点数据
// ---------------------------
export interface NodeData {
  id: string;
  type: NodeType;
  position: Point;
  size: { width: number; height: number };
  status: NodeStatus;
  label: string;
  chapterId: string;        // 所属章节
  sceneId: string;          // 所属场景
  moduleType?: ModuleType;  // Agent分配的模块
  moduleId?: string;        // 所属模块区域ID

  // 节点内容（根据type填充不同字段）
  content: StoryboardContent | ImageContent | VideoContent | TextNoteContent;

  // 依赖链
  upstreamIds: string[];    // 上游节点ID
  downstreamIds: string[];  // 下游节点ID

  // 元数据
  createdAt: number;
  updatedAt: number;
  agentAssigned: boolean;   // 是否由Agent自动分配
}

// 分镜文本节点
export interface StoryboardContent {
  rawText: string;          // 原始分镜文本
  imagePrompt: string;      // 画面提示词（AI生成/人工修改）
  videoPrompt: string;      // 视频提示词
  characterIds: string[];   // 使用的角色ID
  sceneAssetId?: string;    // 使用的场景资产ID
  propIds: string[];        // 使用的道具ID
  shotType: ShotType;       // 镜头类型
  emotion: string;          // 情感基调
  duration: number;         // 预计视频时长(秒)
}

export type ShotType =
  | 'close-up'       // 特写
  | 'medium'         // 中景
  | 'wide'           // 远景
  | 'overhead'       // 俯视
  | 'low-angle'      // 仰视
  | 'pov'            // 主观视角
  | 'over-shoulder'; // 过肩

// 图片合成节点
export interface ImageContent {
  workflowSteps: WorkflowStep[];   // 合成步骤列表
  resultImageUrl?: string;         // 最终合成图URL
  intermediateUrls: string[];      // 中间步骤图URL
  width: number;
  height: number;
  sourceStoryboardId: string;      // 来源分镜节点ID
}

// 视频生成节点
export interface VideoContent {
  provider: VideoProvider;         // 使用哪个视频AI
  videoPrompt: string;             // 最终视频提示词
  duration: number;                // 时长
  fps: number;
  resolution: VideoResolution;
  resultVideoUrl?: string;
  thumbnailUrl?: string;
  sourceImageId: string;           // 来源图片节点ID
  jobId?: string;                  // 外部平台任务ID
}

export type VideoProvider = 'jimeng' | 'kling' | 'runway' | 'pika';
export type VideoResolution = '720p' | '1080p' | '4k';

// 文本注释节点
export interface TextNoteContent {
  text: string;
  color: string;
}

// ---------------------------
// 工作流步骤
// ---------------------------
export interface WorkflowStep {
  id: string;
  name: string;
  type: WorkflowStepType;
  status: NodeStatus;
  params: Record<string, unknown>;
  resultUrl?: string;
  error?: string;
}

export type WorkflowStepType =
  | 'generate-background'    // 生成背景
  | 'generate-character'     // 生成角色
  | 'remove-background'      // 背景移除（镂空）
  | 'composite-layers'       // 图层合成
  | 'apply-filter'           // 滤镜效果
  | 'adjust-lighting'        // 光线调整
  | 'add-props'              // 道具合成
  | 'motion-blur'            // 动态模糊
  | 'color-grade';           // 调色

// ---------------------------
// 模块区域
// ---------------------------
export interface ModuleBlock {
  id: string;
  type: ModuleType;
  label: string;            // e.g. "对话场景 · 第3章"
  chapterId: string;
  position: Point;
  size: { width: number; height: number };
  nodeIds: string[];        // 包含的节点ID
  collapsed: boolean;       // 是否折叠
  color: string;
  progress: { done: number; total: number };
}

// ---------------------------
// 连线
// ---------------------------
export interface Connection {
  id: string;
  fromNodeId: string;
  toNodeId: string;
  type: 'data-flow' | 'dependency';
}

// ---------------------------
// 项目资产
// ---------------------------
export interface ProjectAsset {
  id: string;
  type: 'character' | 'scene' | 'prop';
  name: string;
  imageUrl: string;
  thumbnailUrl: string;
  description: string;
  tags: string[];
  // 角色专属
  characterTraits?: string[];
  // 场景专属
  timeOfDay?: 'dawn' | 'morning' | 'afternoon' | 'evening' | 'night';
  // 道具专属
  propCategory?: string;
}

// ---------------------------
// 分镜链（一个完整的 文本→图→视频 链路）
// ---------------------------
export interface StoryboardChain {
  id: string;
  chapterId: string;
  sceneName: string;
  moduleType: ModuleType;
  nodeIds: string[];        // [storyboardId, imageId, videoId]
  status: 'pending' | 'partial' | 'complete';
  estimatedCost?: number;   // 预计API消耗（单位：次）
}

// ---------------------------
// Agent 任务
// ---------------------------
export interface AgentTask {
  id: string;
  type: AgentTaskType;
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

export type AgentTaskType =
  | 'analyze-storyboard'         // 分析分镜，生成image/video提示词
  | 'assign-module'              // 识别并分配模块类型
  | 'generate-image-prompt'      // 优化图片提示词
  | 'generate-video-prompt'      // 优化视频提示词
  | 'review-composition'         // 审查图片构图
  | 'batch-analyze-chapter';     // 批量分析整章

// ---------------------------
// 章节 / 场景结构（来自前置环节）
// ---------------------------
export interface Chapter {
  id: string;
  title: string;
  order: number;
  scenes: Scene[];
  plotLineId: string;
}

export interface Scene {
  id: string;
  chapterId: string;
  title: string;
  order: number;
  rawScript: string;        // 原始剧本文本
  storyboards: string[];    // 分镜ID列表（来自前置拆解环节）
  location: string;
  timeOfDay: string;
  characterIds: string[];
  mood: string;
}

// ---------------------------
// 画布视图状态
// ---------------------------
export interface CanvasViewState {
  transform: Transform;
  selectedNodeIds: Set<string>;
  hoveredNodeId: string | null;
  visibleRect: Rect;          // 当前视口对应的世界坐标矩形
}

// ---------------------------
// 批量执行计划
// ---------------------------
export interface ExecutionPlan {
  id: string;
  chains: StoryboardChain[];
  totalNodes: number;
  estimatedMinutes: number;
  estimatedApiCalls: number;
  parallelGroups: string[][];  // 可并行执行的节点组
}
