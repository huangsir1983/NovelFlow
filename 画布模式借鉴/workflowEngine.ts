// ============================================================
// workflowEngine.ts - 工作流执行引擎
// 负责调度图片合成步骤和视频生成任务
// ============================================================
import { NodeData, ImageContent, VideoContent, WorkflowStep } from '../types';

interface ImageWorkflowCallbacks {
  onStepUpdate: (stepId: string, status: string, resultUrl?: string) => void;
  onComplete: (resultUrl: string) => void;
  onError?: (err: Error) => void;
}

interface VideoGenerationCallbacks {
  onJobCreated: (jobId: string) => void;
  onProgress?: (progress: number) => void;
  onComplete: (videoUrl: string, thumbnailUrl: string) => void;
  onError?: (err: Error) => void;
}

// ---------------------------
// 图片工作流执行
// ---------------------------
async function runImageWorkflow(
  node: NodeData,
  callbacks: ImageWorkflowCallbacks
): Promise<void> {
  const content = node.content as ImageContent;
  const steps = content.workflowSteps;

  let lastResultUrl = '';

  for (const step of steps) {
    if (step.optional && !shouldRunOptionalStep(step, content)) {
      callbacks.onStepUpdate(step.id, 'done', lastResultUrl);
      continue;
    }

    callbacks.onStepUpdate(step.id, 'processing');

    try {
      const result = await executeWorkflowStep(step, content, lastResultUrl);
      lastResultUrl = result.resultUrl || lastResultUrl;
      callbacks.onStepUpdate(step.id, 'done', lastResultUrl);
    } catch (err) {
      callbacks.onStepUpdate(step.id, 'error');
      callbacks.onError?.(err as Error);
      throw err;
    }
  }

  callbacks.onComplete(lastResultUrl);
}

// 判断可选步骤是否需要执行
function shouldRunOptionalStep(step: WorkflowStep, content: ImageContent): boolean {
  // 例：只有当内容有道具时才执行 add-props 步骤
  if (step.type === 'add-props') {
    return true; // 可以根据具体业务逻辑扩展
  }
  return true;
}

// 执行单个工作流步骤
async function executeWorkflowStep(
  step: WorkflowStep,
  content: ImageContent,
  inputImageUrl: string
): Promise<{ resultUrl: string }> {

  // 根据步骤类型调用不同的API
  switch (step.type) {
    case 'generate-background':
      return callImageAPI('/api/workflow/generate-background', {
        params: step.defaultParams,
        sourceStoryboardId: content.sourceStoryboardId,
      });

    case 'generate-character':
      return callImageAPI('/api/workflow/generate-character', {
        inputUrl: inputImageUrl,
        params: step.defaultParams,
      });

    case 'remove-background':
      return callImageAPI('/api/workflow/remove-background', {
        inputUrl: inputImageUrl,
        params: step.defaultParams,
      });

    case 'composite-layers':
      return callImageAPI('/api/workflow/composite', {
        layers: content.intermediateUrls,
        params: step.defaultParams,
      });

    case 'apply-filter':
      return callImageAPI('/api/workflow/filter', {
        inputUrl: inputImageUrl,
        params: step.defaultParams,
      });

    case 'adjust-lighting':
      return callImageAPI('/api/workflow/lighting', {
        inputUrl: inputImageUrl,
        params: step.defaultParams,
      });

    case 'add-props':
      return callImageAPI('/api/workflow/add-props', {
        inputUrl: inputImageUrl,
        params: step.defaultParams,
      });

    case 'motion-blur':
      return callImageAPI('/api/workflow/motion-blur', {
        inputUrl: inputImageUrl,
        params: step.defaultParams,
      });

    case 'color-grade':
      return callImageAPI('/api/workflow/color-grade', {
        inputUrl: inputImageUrl,
        params: step.defaultParams,
      });

    default:
      throw new Error(`Unknown step type: ${step.type}`);
  }
}

// 通用图片API调用（对接你现有的后端）
async function callImageAPI(
  endpoint: string,
  payload: Record<string, unknown>
): Promise<{ resultUrl: string }> {
  const response = await fetch(`${process.env.REACT_APP_API_BASE_URL || ''}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`API call failed: ${endpoint} ${response.status}`);
  }

  return response.json();
}


// ---------------------------
// 视频生成
// ---------------------------
async function runVideoGeneration(
  node: NodeData,
  callbacks: VideoGenerationCallbacks
): Promise<void> {
  const content = node.content as VideoContent;

  const { jobId } = await createVideoJob(content);
  callbacks.onJobCreated(jobId);

  // 轮询任务状态
  await pollVideoJob(jobId, content.provider, {
    onProgress: callbacks.onProgress,
    onComplete: (videoUrl, thumbnailUrl) => {
      callbacks.onComplete(videoUrl, thumbnailUrl);
    },
    onError: callbacks.onError,
  });
}

async function createVideoJob(content: VideoContent): Promise<{ jobId: string }> {
  const endpoint = `/api/video/${content.provider}/create`;
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: content.videoPrompt,
      duration: content.duration,
      resolution: content.resolution,
      fps: content.fps,
    }),
  });

  if (!response.ok) throw new Error(`Failed to create video job: ${response.status}`);
  return response.json();
}

async function pollVideoJob(
  jobId: string,
  provider: string,
  callbacks: {
    onProgress?: (progress: number) => void;
    onComplete: (videoUrl: string, thumbnailUrl: string) => void;
    onError?: (err: Error) => void;
  },
  maxAttempts = 60,
  intervalMs = 5000
): Promise<void> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    await new Promise(resolve => setTimeout(resolve, intervalMs));

    const response = await fetch(`/api/video/${provider}/status/${jobId}`);
    if (!response.ok) continue;

    const data = await response.json();

    if (data.status === 'completed') {
      callbacks.onComplete(data.videoUrl, data.thumbnailUrl);
      return;
    } else if (data.status === 'failed') {
      callbacks.onError?.(new Error(data.error || 'Video generation failed'));
      return;
    } else if (data.progress) {
      callbacks.onProgress?.(data.progress);
    }
  }

  callbacks.onError?.(new Error('Video generation timed out'));
}


export const workflowEngine = {
  runImageWorkflow,
  runVideoGeneration,
};


// ============================================================
// ChainProgressPanel.tsx - 分镜链进度面板
// ============================================================
import React from 'react';
import { useCanvasStore } from '../store/canvasStore';
import { useProjectStore } from '../store/projectStore';

export const ChainProgressPanel: React.FC = () => {
  const nodes = useCanvasStore(s => s.nodes);
  const chapters = useProjectStore(s => s.chapters);

  // 按章节统计进度
  const chapterStats = chapters.map(chapter => {
    const chapterNodes = Array.from(nodes.values()).filter(n => n.chapterId === chapter.id);
    const done = chapterNodes.filter(n => n.status === 'done').length;
    const total = chapterNodes.length;
    return { chapter, done, total };
  });

  // 如果没有章节数据，按模块分组显示
  const moduleStats = React.useMemo(() => {
    const stats: Record<string, { done: number; total: number; color: string }> = {};
    const moduleColors: Record<string, string> = {
      dialogue: '#378ADD', action: '#D85A30',
      suspense: '#534AB7', landscape: '#1D9E75', emotion: '#D4537E',
    };
    const moduleLabels: Record<string, string> = {
      dialogue: '对话场景', action: '打斗动作',
      suspense: '悬疑揭秘', landscape: '环境转场', emotion: '情感内心',
    };

    nodes.forEach(node => {
      if (node.moduleType) {
        if (!stats[node.moduleType]) {
          stats[node.moduleType] = { done: 0, total: 0, color: moduleColors[node.moduleType] || '#888' };
        }
        stats[node.moduleType].total++;
        if (node.status === 'done') stats[node.moduleType].done++;
      }
    });

    return Object.entries(stats).map(([type, s]) => ({
      label: moduleLabels[type] || type,
      ...s,
    }));
  }, [nodes]);

  const displayItems = chapterStats.length > 0
    ? chapterStats.map(s => ({ label: s.chapter.title, done: s.done, total: s.total, color: '#378ADD' }))
    : moduleStats;

  if (displayItems.length === 0) return null;

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{
        fontSize: 11,
        color: 'var(--color-text-secondary)',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        marginBottom: 8,
      }}>
        分镜链进度
      </div>
      {displayItems.map((item, i) => (
        <ProgressRow key={i} {...item} />
      ))}
    </div>
  );
};

const ProgressRow: React.FC<{ label: string; done: number; total: number; color: string }> = ({
  label, done, total, color
}) => {
  if (total === 0) return null;
  const pct = Math.round((done / total) * 100);
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
        <span style={{ color: 'var(--color-text-primary)' }}>{label}</span>
        <span style={{ color }}>{done}/{total}</span>
      </div>
      <div style={{ height: 4, background: 'var(--color-border-tertiary)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.4s ease' }} />
      </div>
    </div>
  );
};
