'use client';

import {
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
  memo,
} from 'react';
import type { Node, Edge } from '@xyflow/react';
import { useReactFlow } from '@xyflow/react';
import { useCanvasStore } from '../../../stores/canvasStore';
import { useProjectStore } from '../../../stores/projectStore';
import { useChainTemplateStore } from '../../../stores/chainTemplateStore';
import { useWorkflowExecutionStore } from '../../../stores/workflowExecutionStore';
import { fetchAPI } from '../../../lib/api';
import type {
  ExecutionPlanPreview,
  MergeAnalysisResult,
  MergeAnalysisRequest,
  ChainTemplate,
} from '../../../types';

/* ══════════════════════════════════════════════════════════════
   Helpers
   ══════════════════════════════════════════════════════════════ */

function getNodeBounds(node: Node) {
  return {
    x: node.position.x,
    y: node.position.y,
    w: node.measured?.width ?? 300,
    h: node.measured?.height ?? 200,
  };
}

function rectsOverlap(
  a: { x: number; y: number; w: number; h: number },
  b: { x: number; y: number; w: number; h: number },
) {
  return (
    a.x < b.x + b.w &&
    a.x + a.w > b.x &&
    a.y < b.y + b.h &&
    a.y + a.h > b.y
  );
}

function buildUpstreamMap(edges: Edge[]) {
  const map = new Map<string, string[]>();
  edges.forEach((e) => {
    const deps = map.get(e.target) || [];
    deps.push(e.source);
    map.set(e.target, deps);
  });
  return map;
}

function buildPlan(
  selectedIds: string[],
  nodes: Node[],
  edges: Edge[],
): ExecutionPlanPreview {
  const selected = nodes.filter((n) => selectedIds.includes(n.id));
  const getType = (n: Node) => (n.data as Record<string, unknown>).nodeType as string;
  const shotCount = selected.filter((n) => getType(n) === 'shot').length;
  const imageCount = selected.filter((n) => {
    const t = getType(n);
    return t === 'imageGeneration' || t === 'viewAngle' || t === 'expression'
      || t === 'matting' || t === 'composite' || t === 'sceneBG'
      || t === 'hdUpscale' || t === 'propAngle';
  }).length;
  const videoCount = selected.filter((n) => getType(n) === 'videoGeneration').length;

  // Topological sort into parallel groups
  const upstreamMap = buildUpstreamMap(edges);
  const groups: string[][] = [];
  const remaining = new Set(selectedIds);
  const processed = new Set<string>();

  while (remaining.size > 0) {
    const group: string[] = [];
    remaining.forEach((id) => {
      const deps = (upstreamMap.get(id) || []).filter((d) =>
        selectedIds.includes(d),
      );
      if (deps.every((d) => processed.has(d))) group.push(id);
    });
    if (group.length === 0) break; // circular dep guard
    groups.push(group);
    group.forEach((id) => {
      remaining.delete(id);
      processed.add(id);
    });
  }

  return {
    totalNodes: selected.length,
    shotCount,
    imageCount,
    videoCount,
    estimatedMinutes: Math.ceil(
      shotCount * 0.5 + imageCount * 4 + videoCount * 3,
    ),
    estimatedApiCalls: shotCount * 2 + imageCount * 5 + videoCount * 2,
    parallelGroups: groups,
    hasUserConfirmSteps: false,
  };
}

async function analyzeMerge(
  sceneId: string,
  nodes: Node[],
): Promise<MergeAnalysisResult> {
  const storyboardNodes = nodes
    .filter((n) => (n.data as Record<string, unknown>).nodeType === 'shot')
    .map((n) => {
      const d = n.data as Record<string, unknown>;
      return {
        id: n.id,
        label: (d.label as string) || '',
        text: (d.description as string) || '',
        emotion: (d.emotion as string) || '',
        shotType: (d.framing as string) || 'medium',
        estimatedDuration: 5,
      };
    });

  return fetchAPI<MergeAnalysisResult>(
    '/api/canvas/agent/merge-analysis',
    {
      method: 'POST',
      body: JSON.stringify({
        sceneId: sceneId,
        storyboardNodes: storyboardNodes,
      } satisfies MergeAnalysisRequest),
    },
  );
}

/* ══════════════════════════════════════════════════════════════
   ExecuteFloatingBar
   ══════════════════════════════════════════════════════════════ */

interface ExecuteFloatingBarProps {
  plan: ExecutionPlanPreview;
  nodes: Node[];
  templates: ChainTemplate[];
  selectedTemplateId: string | null;
  onSelectTemplate: (id: string) => void;
  onExecute: () => void;
  onCancel: () => void;
  onMergeAnalysis: () => void;
}

const ExecuteFloatingBar = memo(function ExecuteFloatingBar({
  plan,
  nodes,
  templates,
  selectedTemplateId,
  onSelectTemplate,
  onExecute,
  onCancel,
  onMergeAnalysis,
}: ExecuteFloatingBarProps) {
  const [detailOpen, setDetailOpen] = useState(false);

  return (
    <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[70] flex flex-col items-center gap-2 min-w-[480px] max-w-[640px]">
      {/* Main bar */}
      <div className="w-full flex flex-col rounded-xl bg-[#0a0f1a]/95 backdrop-blur-xl border border-white/[0.08] shadow-2xl">
        {/* Top row: stats capsules */}
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]">
          <span className="text-[11px] text-white/40 mr-1">框选节点</span>

          {plan.shotCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/20">
              分镜 {plan.shotCount}
            </span>
          )}
          {plan.imageCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-500/15 text-purple-300 border border-purple-500/20">
              图片 {plan.imageCount}
            </span>
          )}
          {plan.videoCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-300 border border-amber-500/20">
              视频 {plan.videoCount}
            </span>
          )}

          <div className="flex-1" />

          <span className="text-[10px] text-white/30">
            ~{plan.estimatedMinutes} 分钟
          </span>
          <span className="text-[10px] text-white/30">
            ~{plan.estimatedApiCalls} API
          </span>
          <span className="text-[10px] text-white/30">
            {plan.parallelGroups.length} 批次
          </span>
        </div>

        {/* Warning row */}
        {plan.hasUserConfirmSteps && (
          <div className="flex items-center gap-1.5 px-4 py-1.5 bg-amber-500/5 border-b border-white/[0.06]">
            <svg
              className="w-3.5 h-3.5 text-amber-400/80"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="text-[10px] text-amber-300/80">
              包含人工选帧步骤，执行过程将暂停等待确认
            </span>
          </div>
        )}

        {/* Template + actions row */}
        <div className="flex items-center gap-2 px-4 py-2.5">
          <select
            value={selectedTemplateId || ''}
            onChange={(e) => onSelectTemplate(e.target.value)}
            className="px-2 py-1 rounded-lg text-[11px] bg-white/5 text-white/70 border border-white/[0.08] outline-none hover:bg-white/8 transition-colors min-w-[140px]"
          >
            <option value="">选择模板...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.icon} {t.name}
              </option>
            ))}
          </select>

          <button
            onClick={onMergeAnalysis}
            className="px-2.5 py-1 rounded-lg text-[11px] font-medium bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25 border border-indigo-500/20 transition-colors"
          >
            AI 合并分析
          </button>

          <button
            onClick={() => setDetailOpen((v) => !v)}
            className="px-2 py-1 rounded-lg text-[11px] text-white/50 hover:text-white/70 hover:bg-white/5 transition-colors"
          >
            {detailOpen ? '收起' : '详情'}
          </button>

          <div className="flex-1" />

          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-white/5 text-white/60 hover:bg-white/10 transition-colors"
          >
            取消
          </button>
          <button
            onClick={onExecute}
            disabled={!selectedTemplateId}
            className="px-4 py-1.5 rounded-lg text-[11px] font-medium bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            执行
          </button>
        </div>

        {/* Detail expansion: parallel groups */}
        {detailOpen && (
          <div className="px-4 pb-3 pt-1 border-t border-white/[0.06]">
            <div className="text-[10px] text-white/40 mb-1.5">
              并行分组 ({plan.parallelGroups.length} 批)
            </div>
            <div className="flex flex-col gap-1 max-h-[160px] overflow-y-auto scrollbar-thin">
              {plan.parallelGroups.map((group, i) => (
                <div
                  key={i}
                  className="flex items-center gap-1.5 px-2 py-1 rounded bg-white/[0.03]"
                >
                  <span className="text-[10px] text-white/30 w-6 shrink-0">
                    #{i + 1}
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {group.map((nodeId) => {
                      const node = nodes.find((n) => n.id === nodeId);
                      const d = node?.data as Record<string, unknown> | undefined;
                      return (
                        <span
                          key={nodeId}
                          className="px-1.5 py-0.5 rounded text-[9px] bg-white/5 text-white/50"
                        >
                          {(d?.label as string) || nodeId.slice(0, 8)}
                        </span>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

/* ══════════════════════════════════════════════════════════════
   MergeAnalysisPanel
   ══════════════════════════════════════════════════════════════ */

interface MergeAnalysisPanelProps {
  result: MergeAnalysisResult;
  onApply: (result: MergeAnalysisResult) => void;
  onClose: () => void;
}

const driftColorMap: Record<string, string> = {
  low: 'text-green-400 bg-green-500/10 border-green-500/20',
  medium: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  high: 'text-red-400 bg-red-500/10 border-red-500/20',
};

function MergeAnalysisPanelComponent({
  result,
  onApply,
  onClose,
}: MergeAnalysisPanelProps) {
  return (
    <div className="fixed right-0 top-0 h-full w-[380px] z-[80] flex flex-col bg-[#0c1120]/98 backdrop-blur-2xl border-l border-white/[0.06] shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-indigo-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <span className="text-[13px] font-medium text-white/90">
            AI 合并分析
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-white/5 text-white/40 hover:text-white/70 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Summary */}
      <div className="px-4 py-3 border-b border-white/[0.06]">
        <p className="text-[11px] text-white/60 leading-relaxed mb-2">
          {result.summary}
        </p>
        <div className="flex gap-3">
          <div className="text-center">
            <div className="text-[16px] font-semibold text-cyan-300">
              {result.totalVideos}
            </div>
            <div className="text-[9px] text-white/30">输出视频</div>
          </div>
          <div className="text-center">
            <div className="text-[16px] font-semibold text-purple-300">
              {result.totalDuration}s
            </div>
            <div className="text-[9px] text-white/30">总时长</div>
          </div>
          <div className="text-center">
            <div className="text-[16px] font-semibold text-white/70">
              {result.decisions.length}
            </div>
            <div className="text-[9px] text-white/30">分镜组</div>
          </div>
        </div>
      </div>

      {/* Decision list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-2">
        {result.decisions.map((decision, i) => {
          const driftClasses =
            driftColorMap[decision.driftRisk] || driftColorMap.low;
          const isHighRisk = decision.driftRisk === 'high';

          return (
            <div
              key={decision.groupId}
              className="mb-3 rounded-lg border border-white/[0.06] bg-white/[0.02] overflow-hidden"
            >
              {/* Group header */}
              <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.04]">
                <span className="text-[10px] text-white/30">#{i + 1}</span>
                <span className="text-[11px] text-white/70 font-medium flex-1">
                  {decision.shotNodeIds.length} 个分镜
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-medium border ${driftClasses}`}
                >
                  {decision.driftRisk === 'low'
                    ? '低风险'
                    : decision.driftRisk === 'medium'
                      ? '中风险'
                      : '高风险'}
                </span>
              </div>

              {/* Details */}
              <div className="px-3 py-2 space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-white/40">时长</span>
                  <span className="text-white/60">
                    {decision.totalDuration}s
                  </span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-white/40">输出视频</span>
                  <span className="text-white/60">{decision.videoCount}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="text-white/40">推荐渲染</span>
                  <span className="text-white/60">
                    {decision.recommendedProvider}
                  </span>
                </div>
                <p className="text-[10px] text-white/50 leading-relaxed mt-1">
                  {decision.reason}
                </p>

                {/* High-risk split suggestions */}
                {isHighRisk && decision.splitPoints && decision.splitPoints.length > 0 && (
                  <div className="mt-2 px-2 py-1.5 rounded bg-red-500/5 border border-red-500/15">
                    <div className="text-[9px] text-red-400/90 font-medium mb-0.5">
                      建议拆分
                    </div>
                    <div className="text-[9px] text-red-300/70">
                      在 {decision.splitPoints.map((p) => `${p}s`).join(', ')}{' '}
                      处拆分以降低漂移风险
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer actions */}
      <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-white/[0.06]">
        <button
          onClick={onClose}
          className="px-4 py-1.5 rounded-lg text-[11px] font-medium bg-white/5 text-white/60 hover:bg-white/10 transition-colors"
        >
          取消
        </button>
        <button
          onClick={() => onApply(result)}
          className="px-4 py-1.5 rounded-lg text-[11px] font-medium bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 transition-colors"
        >
          应用方案
        </button>
      </div>
    </div>
  );
}

const MergeAnalysisPanel = memo(MergeAnalysisPanelComponent);

/* ══════════════════════════════════════════════════════════════
   BoxSelectExecutor (main)
   ══════════════════════════════════════════════════════════════ */

interface BoxSelectExecutorProps {
  projectId?: string;
  workflowId?: string;
}

function BoxSelectExecutorComponent({
  projectId: projectIdProp,
  workflowId: workflowIdProp,
}: BoxSelectExecutorProps) {
  const storeProjectId = useProjectStore((s) => s.project?.id);
  const projectId = projectIdProp || storeProjectId || '';
  const workflowId = workflowIdProp || '';
  const reactFlow = useReactFlow();
  const {
    nodes,
    edges,
    selectedNodeIds,
    selectNodes,
    boxSelectActive,
    setBoxSelectActive,
    boxSelectRect,
    setBoxSelectRect,
    focusedSceneId,
  } = useCanvasStore();

  const { templates } = useChainTemplateStore();
  const { startExecution } = useWorkflowExecutionStore();

  const [shiftHeld, setShiftHeld] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [showExecuteBar, setShowExecuteBar] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null,
  );
  const [mergeResult, setMergeResult] = useState<MergeAnalysisResult | null>(
    null,
  );
  const [mergeLoading, setMergeLoading] = useState(false);

  const dragStart = useRef<{ x: number; y: number } | null>(null);

  // ── Shift key tracking ──
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Shift') setShiftHeld(true);
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Shift') setShiftHeld(false);
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, []);

  // ── Build selection rectangle (world coords) from drag ──
  const normalizeRect = useCallback(
    (
      startX: number,
      startY: number,
      endX: number,
      endY: number,
    ): { x: number; y: number; w: number; h: number } => {
      return {
        x: Math.min(startX, endX),
        y: Math.min(startY, endY),
        w: Math.abs(endX - startX),
        h: Math.abs(endY - startY),
      };
    },
    [],
  );

  // ── Mouse handlers ──
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!shiftHeld) return;
      e.preventDefault();
      e.stopPropagation();

      const worldPos = reactFlow.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });
      dragStart.current = worldPos;
      setIsDragging(true);
      setBoxSelectActive(true);
      setBoxSelectRect(null);
      setShowExecuteBar(false);
    },
    [shiftHeld, reactFlow, setBoxSelectActive, setBoxSelectRect],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging || !dragStart.current) return;

      const worldPos = reactFlow.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });
      const rect = normalizeRect(
        dragStart.current.x,
        dragStart.current.y,
        worldPos.x,
        worldPos.y,
      );
      setBoxSelectRect(rect);
    },
    [isDragging, reactFlow, normalizeRect, setBoxSelectRect],
  );

  const handleMouseUp = useCallback(
    (_e: React.MouseEvent) => {
      if (!isDragging || !dragStart.current) return;

      setIsDragging(false);
      setBoxSelectActive(false);
      dragStart.current = null;

      const rect = boxSelectRect;
      if (!rect || rect.w < 5 || rect.h < 5) {
        setBoxSelectRect(null);
        return;
      }

      // Hit-test: find nodes overlapping the selection rect
      const hitIds: string[] = [];
      nodes.forEach((node) => {
        const nb = getNodeBounds(node);
        if (rectsOverlap(rect, nb)) {
          hitIds.push(node.id);
        }
      });

      setBoxSelectRect(null);

      if (hitIds.length > 0) {
        selectNodes(hitIds);
        setShowExecuteBar(true);
      }
    },
    [isDragging, boxSelectRect, nodes, selectNodes, setBoxSelectActive, setBoxSelectRect],
  );

  // ── Execution plan ──
  const plan = useMemo<ExecutionPlanPreview | null>(() => {
    if (!showExecuteBar || selectedNodeIds.length === 0) return null;
    return buildPlan(selectedNodeIds, nodes, edges);
  }, [showExecuteBar, selectedNodeIds, nodes, edges]);

  // ── Execute handler ──
  const handleExecute = useCallback(async () => {
    if (!selectedTemplateId) return;
    try {
      await startExecution(
        projectId,
        workflowId,
        selectedTemplateId,
        selectedNodeIds,
      );
      setShowExecuteBar(false);
      setSelectedTemplateId(null);
    } catch (err) {
      console.error('[BoxSelectExecutor] execution failed:', err);
    }
  }, [
    selectedTemplateId,
    projectId,
    workflowId,
    selectedNodeIds,
    startExecution,
  ]);

  // ── Cancel handler ──
  const handleCancel = useCallback(() => {
    setShowExecuteBar(false);
    selectNodes([]);
    setSelectedTemplateId(null);
  }, [selectNodes]);

  // ── Merge analysis handler ──
  const handleMergeAnalysis = useCallback(async () => {
    const sceneId = focusedSceneId || '';
    const selectedNodes = nodes.filter((n) =>
      selectedNodeIds.includes(n.id),
    );
    if (selectedNodes.length === 0) return;

    setMergeLoading(true);
    try {
      const result = await analyzeMerge(sceneId, selectedNodes);
      setMergeResult(result);
    } catch (err) {
      console.error('[BoxSelectExecutor] merge analysis failed:', err);
    } finally {
      setMergeLoading(false);
    }
  }, [focusedSceneId, nodes, selectedNodeIds]);

  const handleApplyMerge = useCallback(
    (_result: MergeAnalysisResult) => {
      // TODO: apply merge decisions to canvas nodes
      setMergeResult(null);
    },
    [],
  );

  // ── Render selection rectangle in screen space ──
  // We convert world-coord rect corners back to screen for the overlay div
  const screenRect = useMemo(() => {
    if (!boxSelectRect || !isDragging) return null;
    const topLeft = reactFlow.flowToScreenPosition({
      x: boxSelectRect.x,
      y: boxSelectRect.y,
    });
    const bottomRight = reactFlow.flowToScreenPosition({
      x: boxSelectRect.x + boxSelectRect.w,
      y: boxSelectRect.y + boxSelectRect.h,
    });
    return {
      left: topLeft.x,
      top: topLeft.y,
      width: bottomRight.x - topLeft.x,
      height: bottomRight.y - topLeft.y,
    };
  }, [boxSelectRect, isDragging, reactFlow]);

  return (
    <>
      {/* Full-canvas overlay for shift+drag box select */}
      <div
        className="absolute inset-0"
        style={{
          zIndex: shiftHeld || isDragging ? 60 : -1,
          cursor: shiftHeld ? 'crosshair' : 'default',
          pointerEvents: shiftHeld || isDragging ? 'auto' : 'none',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        {/* Selection rectangle (blue dashed) */}
        {screenRect && (
          <div
            className="absolute border-2 border-dashed border-cyan-400/60 bg-cyan-400/[0.06] rounded-sm pointer-events-none"
            style={{
              left: screenRect.left,
              top: screenRect.top,
              width: screenRect.width,
              height: screenRect.height,
            }}
          />
        )}
      </div>

      {/* Shift hint text */}
      {shiftHeld && !isDragging && !showExecuteBar && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[65] px-3 py-1.5 rounded-lg bg-[#0a0f1a]/90 backdrop-blur border border-white/[0.06]">
          <span className="text-[11px] text-white/50">
            按住 Shift 拖拽框选节点
          </span>
        </div>
      )}

      {/* Execute floating bar */}
      {showExecuteBar && plan && (
        <ExecuteFloatingBar
          plan={plan}
          nodes={nodes}
          templates={templates}
          selectedTemplateId={selectedTemplateId}
          onSelectTemplate={setSelectedTemplateId}
          onExecute={handleExecute}
          onCancel={handleCancel}
          onMergeAnalysis={handleMergeAnalysis}
        />
      )}

      {/* Merge analysis loading overlay */}
      {mergeLoading && (
        <div className="fixed inset-0 z-[75] flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-[#0a0f1a]/95 border border-white/[0.08]">
            <svg
              className="w-4 h-4 text-indigo-400 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            <span className="text-[12px] text-white/70">
              AI 正在分析分镜合并方案...
            </span>
          </div>
        </div>
      )}

      {/* Merge analysis panel */}
      {mergeResult && (
        <MergeAnalysisPanel
          result={mergeResult}
          onApply={handleApplyMerge}
          onClose={() => setMergeResult(null)}
        />
      )}
    </>
  );
}

const BoxSelectExecutor = memo(BoxSelectExecutorComponent);

export { BoxSelectExecutor, MergeAnalysisPanel };
