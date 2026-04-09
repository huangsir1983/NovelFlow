// ============================================================
// BoxSelectExecutor.tsx
// 框选批量执行系统
// 功能：
//   - 鼠标拖拽框选一行或多行分镜链
//   - 框选后顶部出现浮动执行栏
//   - 显示预估成本/时间/API次数
//   - 依赖顺序自动排序后批量执行
//   - 实时进度回显 + 断点续跑
// ============================================================

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { useWorkflow } from '../../hooks/useWorkflow';
import { NodeData } from '../../types';
import { templateStore } from './ChainTemplateSystem';

// ── 框选状态 ─────────────────────────────────────────────────
interface SelectionBox {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
}

// ── 主组件 ───────────────────────────────────────────────────
export const BoxSelectExecutor: React.FC = () => {
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionBox, setSelectionBox] = useState<SelectionBox | null>(null);
  const [showExecuteBar, setShowExecuteBar] = useState(false);
  const [executionPlan, setExecutionPlan] = useState<ExecutionPlanPreview | null>(null);

  const selRef = useRef<SelectionBox | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const { nodes, view, selectedNodeIds, selectNode, deselectAll } = useCanvasStore();
  const { runBatch } = useWorkflow();

  // 按住 Shift 时激活框选模式
  const [shiftHeld, setShiftHeld] = useState(false);
  useEffect(() => {
    const down = (e: KeyboardEvent) => { if (e.shiftKey) setShiftHeld(true); };
    const up = (e: KeyboardEvent) => { if (!e.shiftKey) setShiftHeld(false); };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (!shiftHeld || e.button !== 0) return;
    deselectAll();
    const rect = wrapRef.current!.getBoundingClientRect();
    const box = { startX: e.clientX - rect.left, startY: e.clientY - rect.top, endX: e.clientX - rect.left, endY: e.clientY - rect.top };
    selRef.current = box;
    setSelectionBox(box);
    setIsSelecting(true);
    setShowExecuteBar(false);
  }, [shiftHeld, deselectAll]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isSelecting || !selRef.current) return;
    const rect = wrapRef.current!.getBoundingClientRect();
    selRef.current = { ...selRef.current, endX: e.clientX - rect.left, endY: e.clientY - rect.top };
    setSelectionBox({ ...selRef.current });
  }, [isSelecting]);

  const onMouseUp = useCallback(() => {
    if (!isSelecting || !selRef.current) return;
    setIsSelecting(false);

    const box = selRef.current;
    const minX = Math.min(box.startX, box.endX);
    const maxX = Math.max(box.startX, box.endX);
    const minY = Math.min(box.startY, box.endY);
    const maxY = Math.max(box.startY, box.endY);

    // 将屏幕坐标转为世界坐标
    const { transform } = view;
    const worldMinX = (minX - transform.offsetX) / transform.scale;
    const worldMaxX = (maxX - transform.offsetX) / transform.scale;
    const worldMinY = (minY - transform.offsetY) / transform.scale;
    const worldMaxY = (maxY - transform.offsetY) / transform.scale;

    // 找出框内所有节点
    const selected: string[] = [];
    nodes.forEach(node => {
      const nx = node.position.x;
      const ny = node.position.y;
      const nw = node.size.width;
      const nh = node.size.height;
      if (nx + nw > worldMinX && nx < worldMaxX && ny + nh > worldMinY && ny < worldMaxY) {
        selected.push(node.id);
      }
    });

    if (selected.length > 0) {
      selected.forEach(id => selectNode(id, true));
      const plan = buildPlan(selected, nodes);
      setExecutionPlan(plan);
      setShowExecuteBar(true);
    }

    setSelectionBox(null);
  }, [isSelecting, view, nodes, selectNode]);

  return (
    <div
      ref={wrapRef}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      style={{ position: 'absolute', inset: 0, zIndex: shiftHeld ? 60 : -1, cursor: shiftHeld ? 'crosshair' : 'default' }}
    >
      {/* 框选蒙层 */}
      {selectionBox && (
        <SelectionRect box={selectionBox} />
      )}

      {/* 执行浮动条 */}
      {showExecuteBar && executionPlan && (
        <ExecuteFloatingBar
          plan={executionPlan}
          selectedCount={selectedNodeIds.size}
          onExecute={async () => {
            setShowExecuteBar(false);
            await runBatch();
          }}
          onCancel={() => { setShowExecuteBar(false); deselectAll(); }}
        />
      )}

      {/* Shift提示 */}
      {shiftHeld && !isSelecting && !showExecuteBar && (
        <div style={{
          position: 'absolute',
          top: 60,
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-secondary)',
          borderRadius: 8,
          padding: '6px 14px',
          fontSize: 12,
          color: 'var(--color-text-secondary)',
          pointerEvents: 'none',
        }}>
          拖拽框选分镜链
        </div>
      )}
    </div>
  );
};

// ── 框选矩形 ─────────────────────────────────────────────────
const SelectionRect: React.FC<{ box: SelectionBox }> = ({ box }) => {
  const x = Math.min(box.startX, box.endX);
  const y = Math.min(box.startY, box.endY);
  const w = Math.abs(box.endX - box.startX);
  const h = Math.abs(box.endY - box.startY);

  return (
    <div style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      border: '1.5px dashed #378ADD',
      background: 'rgba(59,138,221,0.06)',
      borderRadius: 4,
      pointerEvents: 'none',
    }} />
  );
};

// ── 执行计划预览 ─────────────────────────────────────────────
interface ExecutionPlanPreview {
  totalNodes: number;
  storyboardCount: number;
  imageCount: number;
  videoCount: number;
  estimatedMinutes: number;
  estimatedApiCalls: number;
  parallelGroups: string[][];
  hasUserConfirmSteps: boolean; // 是否有需要人工确认的步骤（如九宫格选帧）
}

function buildPlan(selectedIds: string[], nodes: Map<string, NodeData>): ExecutionPlanPreview {
  const selected = selectedIds.map(id => nodes.get(id)!).filter(Boolean);
  const storyboardCount = selected.filter(n => n.type === 'storyboard').length;
  const imageCount = selected.filter(n => n.type === 'image').length;
  const videoCount = selected.filter(n => n.type === 'video').length;

  // 检查是否有需要人工选帧的模板
  const hasUserConfirmSteps = selected.some(n => {
    if (n.type !== 'image') return false;
    const content = n.content as any;
    return content.workflowSteps?.some((s: any) => s.type === 'user-select-frame');
  });

  // 简单估算
  const estimatedMinutes = storyboardCount * 0.5 + imageCount * 4 + videoCount * 3;
  const estimatedApiCalls = storyboardCount * 2 + imageCount * 5 + videoCount * 2;

  // 拓扑排序分组
  const groups: string[][] = [];
  const remaining = new Set(selectedIds);
  const processed = new Set<string>();

  while (remaining.size > 0) {
    const group: string[] = [];
    remaining.forEach(id => {
      const node = nodes.get(id);
      if (!node) return;
      const depsInSet = node.upstreamIds.filter(upId => selectedIds.includes(upId));
      const allDepsDone = depsInSet.every(depId => processed.has(depId));
      if (allDepsDone) group.push(id);
    });
    if (group.length === 0) break;
    groups.push(group);
    group.forEach(id => { remaining.delete(id); processed.add(id); });
  }

  return {
    totalNodes: selected.length,
    storyboardCount,
    imageCount,
    videoCount,
    estimatedMinutes: Math.ceil(estimatedMinutes),
    estimatedApiCalls,
    parallelGroups: groups,
    hasUserConfirmSteps,
  };
}

// ── 执行浮动条 ────────────────────────────────────────────────
const ExecuteFloatingBar: React.FC<{
  plan: ExecutionPlanPreview;
  selectedCount: number;
  onExecute: () => void;
  onCancel: () => void;
}> = ({ plan, selectedCount, onExecute, onCancel }) => {
  const [showDetail, setShowDetail] = useState(false);
  const [templateId, setTemplateId] = useState('');
  const templates = templateStore.getAll();

  return (
    <div style={{
      position: 'absolute',
      top: 60,
      left: '50%',
      transform: 'translateX(-50%)',
      background: 'var(--color-background-primary)',
      border: '0.5px solid var(--color-border-secondary)',
      borderRadius: 12,
      padding: '10px 16px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.1)',
      zIndex: 150,
      minWidth: 460,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      {/* 顶行：节点统计 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)' }}>
          已选 {selectedCount} 个节点
        </span>
        <StatPill label="分镜" count={plan.storyboardCount} color="#378ADD" />
        <StatPill label="图片" count={plan.imageCount} color="#1D9E75" />
        <StatPill label="视频" count={plan.videoCount} color="#639922" />
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button onClick={() => setShowDetail(d => !d)} style={barBtnStyle}>
            {showDetail ? '收起' : '详情'}
          </button>
          <button onClick={onCancel} style={barBtnStyle}>取消</button>
          <button onClick={onExecute} style={{ ...barBtnStyle, background: '#378ADD', color: '#fff', border: 'none' }}>
            ▶ 执行
          </button>
        </div>
      </div>

      {/* 预估信息 */}
      <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--color-text-secondary)' }}>
        <span>预计 ~{plan.estimatedMinutes} 分钟</span>
        <span>API调用 ~{plan.estimatedApiCalls} 次</span>
        <span>{plan.parallelGroups.length} 个并行批次</span>
        {plan.hasUserConfirmSteps && (
          <span style={{ color: '#BA7517' }}>⚠ 含人工选帧步骤，将自动暂停</span>
        )}
      </div>

      {/* 快速套用模板 */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>套用链模板：</span>
        <select value={templateId} onChange={e => setTemplateId(e.target.value)}
          style={{ fontSize: 11, padding: '4px 6px', borderRadius: 6, border: '0.5px solid var(--color-border-tertiary)', background: 'var(--color-background-secondary)', color: 'var(--color-text-primary)', flex: 1 }}>
          <option value="">保持现有链</option>
          {templates.map(t => (
            <option key={t.id} value={t.id}>{t.name} (~{t.estimatedMinutes}m)</option>
          ))}
        </select>
      </div>

      {/* 展开：并行分组详情 */}
      {showDetail && (
        <div style={{ borderTop: '0.5px solid var(--color-border-tertiary)', paddingTop: 8 }}>
          <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 6 }}>执行顺序（并行批次）：</div>
          {plan.parallelGroups.map((group, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <div style={{ width: 20, height: 20, borderRadius: '50%', background: 'var(--color-background-secondary)', border: '0.5px solid var(--color-border-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: 'var(--color-text-secondary)', flexShrink: 0 }}>
                {i + 1}
              </div>
              <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', flex: 1 }}>
                {group.length} 个节点并行 → {group.slice(0, 3).join(', ')}{group.length > 3 ? '...' : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const StatPill: React.FC<{ label: string; count: number; color: string }> = ({ label, count, color }) => (
  <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 99, background: color + '15', color }}>
    {label} {count}
  </span>
);

const barBtnStyle: React.CSSProperties = {
  fontSize: 12,
  padding: '5px 12px',
  borderRadius: 6,
  border: '0.5px solid var(--color-border-tertiary)',
  background: 'transparent',
  color: 'var(--color-text-primary)',
  cursor: 'pointer',
};


// ============================================================
// AIStoryboardMerger.tsx
// AI分镜合并分析器
// 功能：
//   - 分析分镜文本 + 时长，决定 1分镜→1视频 还是 N分镜→1视频
//   - 考虑即梦15s上限（实际建议12s）
//   - 漂移风险评估
//   - 输出合并建议 + 重新排列节点
// ============================================================

import Anthropic from '@anthropic-ai/sdk';
import { NodeData, StoryboardContent } from '../../types';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

export interface MergeDecision {
  groupId: string;
  storyboardIds: string[];      // 合并到同一视频的分镜IDs
  totalDuration: number;        // 合并后预计总时长(秒)
  videoCount: number;           // 最终生成几个视频
  reason: string;               // 合并/不合并的原因
  driftRisk: 'low' | 'medium' | 'high'; // 漂移风险
  recommendedProvider: 'jimeng' | 'kling'; // 推荐视频平台
  splitPoints?: number[];       // 如需拆分，拆分位置(秒)
}

export interface MergeAnalysisResult {
  decisions: MergeDecision[];
  summary: string;
  totalVideos: number;
  totalDuration: number;
}

// ── 主分析函数 ───────────────────────────────────────────────
export async function analyzeStoryboardMerge(
  sceneId: string,
  storyboardNodes: NodeData[],
  onProgress?: (msg: string) => void
): Promise<MergeAnalysisResult> {

  const MAX_VIDEO_DURATION = 12;  // 实际建议上限（秒），留3秒缓冲
  const DRIFT_THRESHOLD = 8;       // 超过8秒开始有漂移风险

  const storyboards = storyboardNodes
    .sort((a, b) => a.position.x - b.position.x || a.position.y - b.position.y)
    .map(n => ({
      id: n.id,
      label: n.label,
      text: (n.content as StoryboardContent).rawText || '',
      emotion: (n.content as StoryboardContent).emotion || '',
      shotType: (n.content as StoryboardContent).shotType || 'medium',
      estimatedDuration: (n.content as StoryboardContent).duration || 5,
    }));

  onProgress?.(`分析 ${storyboards.length} 个分镜的合并策略...`);

  const systemPrompt = `你是视频分镜剪辑专家，负责分析分镜序列，决定哪些分镜应该合并为一个视频片段，哪些应该单独成片。

核心约束：
- AI视频生成（即梦/可灵）的实际可用时长上限为12秒（官方15秒但12秒以上易漂移）
- 镜头切换超过8秒建议独立成片
- 相同场景、相同角色、连续动作的分镜可以合并
- 跨场景、跨角色、大幅情绪跳跃的分镜必须独立

分析维度：
1. 场景连续性（同一物理空间？）
2. 时间连续性（时间是否流逝？）
3. 动作连续性（是否是同一个连续动作的不同阶段？）
4. 角色连续性（是否同样的角色组合？）
5. 情绪连续性（情绪是否跳跃？）
6. 总时长是否超过12秒限制

漂移风险判断：
- low：单个分镜≤6秒，动作简单，角色少
- medium：合并后6-10秒，或有复杂动作
- high：合并后>10秒，或有激烈动作变化

输出严格JSON格式：
{
  "decisions": [
    {
      "groupId": "g1",
      "storyboardIds": ["sb_id1", "sb_id2"],
      "totalDuration": 8,
      "videoCount": 1,
      "reason": "同场景连续对话，时长合计8秒，适合合并",
      "driftRisk": "low",
      "recommendedProvider": "kling",
      "splitPoints": null
    }
  ],
  "summary": "共X个分镜，合并为Y个视频，预计总时长Z秒",
  "totalVideos": 5,
  "totalDuration": 45
}`;

  const userContent = `请分析以下分镜序列（场景ID: ${sceneId}），给出合并建议：

${storyboards.map((sb, i) => `
分镜${i + 1}（ID: ${sb.id}，标签: ${sb.label}）
镜头类型：${sb.shotType}
预计时长：${sb.estimatedDuration}秒
情绪：${sb.emotion}
内容：${sb.text.slice(0, 120)}
`).join('\n---\n')}

总计 ${storyboards.reduce((s, sb) => s + sb.estimatedDuration, 0)} 秒素材，请给出最优合并方案。`;

  const response = await client.messages.create({
    model: 'claude-opus-4-6',
    max_tokens: 2000,
    system: systemPrompt,
    messages: [{ role: 'user', content: userContent }],
  });

  const text = response.content.map(b => b.type === 'text' ? b.text : '').join('');
  const cleaned = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();

  try {
    const result = JSON.parse(cleaned) as MergeAnalysisResult;
    onProgress?.(`分析完成：${storyboards.length} 个分镜 → ${result.totalVideos} 个视频`);
    return result;
  } catch {
    // 兜底：每个分镜独立成片
    onProgress?.('解析失败，使用默认策略（每分镜独立）');
    return {
      decisions: storyboards.map((sb, i) => ({
        groupId: `g${i + 1}`,
        storyboardIds: [sb.id],
        totalDuration: sb.estimatedDuration,
        videoCount: 1,
        reason: '默认独立成片',
        driftRisk: sb.estimatedDuration > 8 ? 'medium' : 'low',
        recommendedProvider: 'jimeng',
      })),
      summary: `${storyboards.length} 个分镜独立成片`,
      totalVideos: storyboards.length,
      totalDuration: storyboards.reduce((s, sb) => s + sb.estimatedDuration, 0),
    };
  }
}


// ── 合并分析结果UI ────────────────────────────────────────────
export const MergeAnalysisPanel: React.FC<{
  result: MergeAnalysisResult;
  onApply: (result: MergeAnalysisResult) => void;
  onClose: () => void;
}> = ({ result, onApply, onClose }) => {
  const DRIFT_COLORS = { low: '#1D9E75', medium: '#BA7517', high: '#E24B4A' };
  const DRIFT_LABELS = { low: '低风险', medium: '中等', high: '高风险' };

  return (
    <div style={{
      position: 'absolute',
      top: '50%',
      right: 280,
      transform: 'translateY(-50%)',
      background: 'var(--color-background-primary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 12,
      padding: 16,
      width: 340,
      maxHeight: '70vh',
      overflowY: 'auto',
      zIndex: 200,
      boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
    }}>
      <div style={{ fontWeight: 500, fontSize: 14, marginBottom: 4 }}>AI 分镜合并建议</div>
      <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 12 }}>{result.summary}</div>

      {/* 总览 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
        <MergeStat label="最终视频数" value={result.totalVideos} color="#378ADD" />
        <MergeStat label="总时长" value={`${result.totalDuration}s`} color="#639922" />
        <MergeStat label="漂移风险分镜" value={result.decisions.filter(d => d.driftRisk === 'high').length} color="#E24B4A" />
      </div>

      {/* 分镜组详情 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {result.decisions.map((dec, i) => (
          <div key={dec.groupId} style={{
            border: `0.5px solid ${DRIFT_COLORS[dec.driftRisk]}44`,
            borderRadius: 8,
            padding: '8px 10px',
            background: DRIFT_COLORS[dec.driftRisk] + '08',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--color-text-primary)' }}>
                视频 {i + 1}
              </span>
              <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 4, background: DRIFT_COLORS[dec.driftRisk] + '18', color: DRIFT_COLORS[dec.driftRisk] }}>
                {DRIFT_LABELS[dec.driftRisk]}
              </span>
              <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)', marginLeft: 'auto' }}>
                {dec.totalDuration}s · {dec.recommendedProvider}
              </span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-text-secondary)', marginBottom: 3 }}>
              {dec.storyboardIds.length} 个分镜合并 → {dec.videoCount} 个视频
            </div>
            <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', lineHeight: 1.4 }}>
              {dec.reason}
            </div>
            {dec.driftRisk === 'high' && (
              <div style={{ marginTop: 4, fontSize: 10, color: '#E24B4A', background: '#E24B4A10', borderRadius: 4, padding: '2px 6px' }}>
                建议拆分为更短的视频段
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button onClick={onClose} style={{ ...barBtnStyle, flex: 1 }}>取消</button>
        <button onClick={() => onApply(result)} style={{ ...barBtnStyle, flex: 2, background: '#378ADD', color: '#fff', border: 'none' }}>
          应用此方案
        </button>
      </div>
    </div>
  );
};

const MergeStat: React.FC<{ label: string; value: string | number; color: string }> = ({ label, value, color }) => (
  <div style={{ flex: 1, background: color + '10', borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
    <div style={{ fontSize: 16, fontWeight: 500, color }}>{value}</div>
    <div style={{ fontSize: 10, color: 'var(--color-text-secondary)' }}>{label}</div>
  </div>
);
