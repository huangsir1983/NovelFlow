/* ══════════════════════════════════════════════════════════════
   Chain Workflow Types
   ══════════════════════════════════════════════════════════════
   链模板系统、工作流执行引擎、AI 分镜合并分析、场景级虚拟化
   ══════════════════════════════════════════════════════════════ */

import type { CanvasWorkflowStepType, CanvasVideoProvider, CanvasNodeStatus } from './canvas';

// ═══════════════════════════════════════════════════════════════
// Section 1 — 链步骤类型（扩展 CanvasWorkflowStepType）
// ═══════════════════════════════════════════════════════════════

export type ChainStepType =
  | CanvasWorkflowStepType
  | 'generate-grid9'           // 九宫格参考图
  | 'user-select-frame'        // 人工选帧门
  | 'grid9-to-video'           // 九宫格生视频
  | 'scene-angle-transform'    // 场景角度变换
  | 'character-pose-adjust'    // 角色姿态/表情/角度调整
  | 'blend-refine'             // 溶图优化
  | 'set-video-keyframe'       // 锁定视频首帧
  | 'generate-image-direct'    // 直接生图
  | 'generate-video-direct';   // 直接生视频

// ═══════════════════════════════════════════════════════════════
// Section 2 — 链模板
// ═══════════════════════════════════════════════════════════════

export interface ChainStep {
  id: string;
  name: string;
  type: ChainStepType;
  description: string;
  params: Record<string, unknown>;
  optional: boolean;
  uiHint?: string;
  dependsOn?: string[];        // step IDs this depends on
}

export interface ChainTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  tags: string[];
  isBuiltin: boolean;
  steps: ChainStep[];
  videoProvider: CanvasVideoProvider;
  estimatedMinutes: number;
  version: number;
  shareMode?: 'private' | 'project' | 'global';
  createdBy?: string;
  createdAt?: string;
  updatedAt?: string;
}

// ═══════════════════════════════════════════════════════════════
// Section 3 — 工作流执行
// ═══════════════════════════════════════════════════════════════

export type WorkflowExecutionStatus =
  | 'pending'
  | 'queued'
  | 'running'
  | 'paused'      // 人工门暂停
  | 'success'
  | 'error'
  | 'cancelled';

export interface WorkflowStepRun {
  id: string;
  executionId: string;
  stepId: string;
  stepType: ChainStepType;
  status: WorkflowExecutionStatus;
  startedAt?: string;
  completedAt?: string;
  resultUrl?: string;
  resultData?: Record<string, unknown>;
  errorMessage?: string;
  retryCount: number;
  progress: number;            // 0-100
  tokensUsed?: number;
  modelUsed?: string;
}

export interface WorkflowExecution {
  id: string;
  projectId: string;
  workflowId: string;          // canvas_workflow.id
  templateId: string;          // chain_template.id
  targetNodeIds: string[];     // 画布节点 IDs
  status: WorkflowExecutionStatus;
  stepRuns: WorkflowStepRun[];
  parallelGroups: string[][];  // step IDs grouped by dependency level
  currentGroupIndex: number;
  concurrencyLimit: number;
  startedAt?: string;
  completedAt?: string;
  totalSteps: number;
  completedSteps: number;
  errorMessage?: string;
}

// ═══════════════════════════════════════════════════════════════
// Section 4 — SSE 事件
// ═══════════════════════════════════════════════════════════════

export type WorkflowSSEEventType =
  | 'step_started'
  | 'step_progress'
  | 'step_completed'
  | 'step_error'
  | 'execution_completed'
  | 'execution_error'
  | 'execution_paused';

export interface WorkflowSSEEvent {
  type: WorkflowSSEEventType;
  executionId: string;
  stepRunId?: string;
  stepId?: string;
  progress?: number;
  status?: WorkflowExecutionStatus;
  resultUrl?: string;
  errorMessage?: string;
  timestamp: string;
}

// ═══════════════════════════════════════════════════════════════
// Section 5 — AI 分镜合并分析
// ═══════════════════════════════════════════════════════════════

export interface MergeDecision {
  groupId: string;
  shotNodeIds: string[];       // 画布节点 IDs
  totalDuration: number;       // 秒
  videoCount: number;
  reason: string;
  driftRisk: 'low' | 'medium' | 'high';
  recommendedProvider: CanvasVideoProvider;
  splitPoints?: number[];      // 拆分位置（秒）
}

export interface MergeAnalysisResult {
  decisions: MergeDecision[];
  summary: string;
  totalVideos: number;
  totalDuration: number;
}

export interface MergeAnalysisRequest {
  sceneId: string;
  storyboardNodes: Array<{
    id: string;
    label: string;
    text: string;
    emotion: string;
    shotType: string;
    estimatedDuration: number;
  }>;
}

// ═══════════════════════════════════════════════════════════════
// Section 6 — 场景级虚拟化
// ═══════════════════════════════════════════════════════════════

export interface SceneGroupBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface SceneGroup {
  sceneId: string;
  heading: string;
  order: number;
  nodeIds: string[];
  bounds: SceneGroupBounds;
  shotCount: number;
  completedCount: number;
  processingCount: number;
  errorCount: number;
}

export type CanvasRenderMode = 'full' | 'simplified' | 'collapsed';

// ═══════════════════════════════════════════════════════════════
// Section 7 — 框选执行计划预览
// ═══════════════════════════════════════════════════════════════

export interface ExecutionPlanPreview {
  totalNodes: number;
  shotCount: number;
  imageCount: number;
  videoCount: number;
  estimatedMinutes: number;
  estimatedApiCalls: number;
  parallelGroups: string[][];
  hasUserConfirmSteps: boolean;
}
