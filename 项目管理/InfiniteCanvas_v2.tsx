// ============================================================
// InfiniteCanvas.tsx (更新版)
// 集成：SceneNavigatorWheel + ChainTemplateSidebar +
//        BoxSelectExecutor + MergeAnalysisPanel
// ============================================================

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { CanvasRenderer } from './CanvasRenderer';
import { ConnectionLayer } from './ConnectionLayer';
import { MiniMap } from './MiniMap';
import { Toolbar } from './Toolbar';
import { ModuleBlock } from '../Modules/ModuleBlock';
import { NodeInspector } from '../Nodes/NodeInspector';
import { ChainProgressPanel } from '../Panels/ChainProgressPanel';
import { SceneNavigatorWheel } from '../Navigator/SceneNavigatorWheel';
import { ChainTemplateSidebar } from '../ChainTemplate/ChainTemplateSystem';
import { BoxSelectExecutor } from '../ChainTemplate/BoxSelectExecutor';
import { MergeAnalysisPanel, analyzeStoryboardMerge, MergeAnalysisResult } from '../ChainTemplate/BoxSelectExecutor';
import { Point } from '../../types';

const ZOOM_SENSITIVITY = 0.001;
const MIN_SCALE = 0.08;   // 700+节点时允许缩得更小
const MAX_SCALE = 3.0;

type CanvasMode = 'select' | 'pan';

export const InfiniteCanvas: React.FC = () => {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<CanvasMode>('select');
  const [mergeResult, setMergeResult] = useState<MergeAnalysisResult | null>(null);
  const [mergeLoading, setMergeLoading] = useState(false);

  const { view, modules, selectedNodeIds, setTransform, setZoom, panBy, fitToContent, deselectAll, setVisibleRect, nodes } = useCanvasStore();
  const { transform } = view;

  const panState = useRef({ active: false, startX: 0, startY: 0, startOX: 0, startOY: 0 });
  const spaceHeld = useRef(false);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => setVisibleRect({ x: 0, y: 0, width: el.clientWidth, height: el.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [setVisibleRect]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') spaceHeld.current = true;
      if (e.key === 'Escape') deselectAll();
      if ((e.metaKey || e.ctrlKey) && e.key === '0') fitToContent();
      if ((e.metaKey || e.ctrlKey) && e.key === '=') setZoom(Math.min(MAX_SCALE, transform.scale * 1.2));
      if ((e.metaKey || e.ctrlKey) && e.key === '-') setZoom(Math.max(MIN_SCALE, transform.scale * 0.8));
    };
    const onKeyUp = (e: KeyboardEvent) => { if (e.code === 'Space') spaceHeld.current = false; };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => { window.removeEventListener('keydown', onKeyDown); window.removeEventListener('keyup', onKeyUp); };
  }, [transform.scale, fitToContent, deselectAll, setZoom]);

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      const delta = -e.deltaY * ZOOM_SENSITIVITY;
      const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, transform.scale * (1 + delta)));
      const rect = wrapRef.current!.getBoundingClientRect();
      setZoom(newScale, { x: e.clientX - rect.left, y: e.clientY - rect.top });
    } else {
      panBy(-e.deltaX, -e.deltaY);
    }
  }, [transform.scale, setZoom, panBy]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (mode === 'pan' || spaceHeld.current || e.button === 1) {
      panState.current = { active: true, startX: e.clientX, startY: e.clientY, startOX: transform.offsetX, startOY: transform.offsetY };
      e.preventDefault();
    }
  }, [mode, transform]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!panState.current.active) return;
    setTransform({ ...transform, offsetX: panState.current.startOX + e.clientX - panState.current.startX, offsetY: panState.current.startOY + e.clientY - panState.current.startY });
  }, [transform, setTransform]);

  const onMouseUp = useCallback(() => { panState.current.active = false; }, []);

  // AI 分镜合并分析（针对选中的场景）
  const runMergeAnalysis = useCallback(async () => {
    const sbNodes = Array.from(nodes.values()).filter(n => selectedNodeIds.has(n.id) && n.type === 'storyboard');
    if (sbNodes.length === 0) return;
    setMergeLoading(true);
    try {
      const sceneId = sbNodes[0].sceneId;
      const result = await analyzeStoryboardMerge(sceneId, sbNodes, (msg) => console.log(msg));
      setMergeResult(result);
    } finally {
      setMergeLoading(false);
    }
  }, [nodes, selectedNodeIds]);

  const cursor = (mode === 'pan' || spaceHeld.current) ? (panState.current.active ? 'grabbing' : 'grab') : 'default';

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', background: 'var(--color-background-tertiary)', position: 'relative', overflow: 'hidden' }}>

      {/* ── 场景导航盘（左侧半圆，层级高于画布） */}
      <SceneNavigatorWheel />

      {/* ── 链模板胶囊栏（导航盘右侧，不遮挡） */}
      <div style={{ position: 'absolute', left: 56, top: '50%', transform: 'translateY(-50%)', zIndex: 75 }}>
        <ChainTemplateSidebar />
      </div>

      {/* ── 主画布区域 */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <Toolbar mode={mode} onModeChange={setMode} onMergeAnalysis={runMergeAnalysis} mergeLoading={mergeLoading} />

        <div
          ref={wrapRef}
          style={{ position: 'absolute', inset: 0, cursor }}
          onWheel={onWheel}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          onClick={(e) => { if (e.target === e.currentTarget) deselectAll(); }}
        >
          {/* 网格背景 */}
          <GridBackground transform={transform} />

          {/* 框选执行层（Shift+拖拽触发） */}
          <BoxSelectExecutor />

          {/* SVG连线层 */}
          <ConnectionLayer />

          {/* 主画布变换层 */}
          <div style={{ position: 'absolute', transformOrigin: '0 0', transform: `translate(${transform.offsetX}px,${transform.offsetY}px) scale(${transform.scale})`, willChange: 'transform' }}>
            {Array.from(modules.values()).map(mod => <ModuleBlock key={mod.id} module={mod} />)}
            <CanvasRenderer />
          </div>
        </div>

        <MiniMap style={{ position: 'absolute', bottom: 16, left: 16 }} />
        <StatusBar transform={transform} selectedCount={selectedNodeIds.size} nodeCount={nodes.size} />

        {/* 合并分析结果面板 */}
        {mergeResult && (
          <MergeAnalysisPanel
            result={mergeResult}
            onApply={(r) => {
              // TODO: 根据合并方案重新组织节点
              console.log('Apply merge:', r);
              setMergeResult(null);
            }}
            onClose={() => setMergeResult(null)}
          />
        )}
      </div>

      {/* 右侧面板 */}
      <RightPanel />
    </div>
  );
};

const GridBackground: React.FC<{ transform: { scale: number; offsetX: number; offsetY: number } }> = ({ transform }) => {
  const gridSize = 40 * transform.scale;
  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
      <defs>
        <pattern id="grid-dot" x={transform.offsetX % gridSize} y={transform.offsetY % gridSize} width={gridSize} height={gridSize} patternUnits="userSpaceOnUse">
          <circle cx={0} cy={0} r={0.8} fill="var(--color-border-tertiary)" opacity={0.9} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid-dot)" />
    </svg>
  );
};

const StatusBar: React.FC<{ transform: { scale: number }; selectedCount: number; nodeCount: number }> = ({ transform, selectedCount, nodeCount }) => (
  <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 8, padding: '4px 14px', fontSize: 12, color: 'var(--color-text-secondary)', display: 'flex', gap: 12, alignItems: 'center', pointerEvents: 'none' }}>
  <span>{Math.round(transform.scale * 100)}%</span>
  <span style={{ opacity: 0.4 }}>·</span>
  <span>{nodeCount} 节点</span>
  {selectedCount > 0 && <><span style={{ opacity: 0.4 }}>·</span><span style={{ color: '#378ADD' }}>已选 {selectedCount} · Shift+拖拽框选 · 顶部执行</span></>}
  {selectedCount === 0 && <span style={{ opacity: 0.6 }}>· Shift+拖拽框选分镜链</span>}
  </div>
);

const RightPanel: React.FC = () => {
  const selectedNodeIds = useCanvasStore(s => s.selectedNodeIds);
  const firstSelected = Array.from(selectedNodeIds)[0];
  return (
    <div style={{ width: 268, flexShrink: 0, background: 'var(--color-background-primary)', borderLeft: '0.5px solid var(--color-border-tertiary)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '12px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)', fontWeight: 500, fontSize: 13 }}>场景资产 &amp; 工作流</div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        <ChainProgressPanel />
        {firstSelected && <NodeInspector nodeId={firstSelected} />}
      </div>
    </div>
  );
};


// ============================================================
// CLAUDE.md 更新内容（追加到现有文件末尾）
// ============================================================

export const CLAUDE_MD_ADDENDUM = `
---

## 新增功能（第二轮）的 Agent 说明

### 6. 场景导航盘定位逻辑
当用户在导航盘点击某个场景时，系统会：
1. 计算该场景下所有分镜节点的中心坐标
2. 执行平滑飞行动画（400ms ease-in-out）
3. 以 0.85 缩放比显示该场景
你无需介入这个过程，它是纯前端计算。

### 7. 链模板的执行顺序
当用户框选一行分镜链（分镜→图片→视频）并套用模板时：
- 分镜节点：由 Claude 生成提示词（你负责的部分）
- 图片节点：按模板 workflowSteps 顺序调用各 API
- 视频节点：使用模板指定的 provider 生成视频
如果模板中有 user-select-frame 步骤（九宫格选帧），系统会暂停并等待用户点击确认。

### 8. AI分镜合并分析（核心新增）
**触发条件**：用户框选一批分镜节点，点击工具栏"AI合并分析"按钮

**你的输入**：
- 每个分镜的文本内容
- 预计时长（estimatedDuration）
- 镜头类型（shotType）
- 情绪标签（emotion）

**你需要输出**（严格JSON）：
\`\`\`json
{
  "decisions": [
    {
      "groupId": "g1",
      "storyboardIds": ["sb_001", "sb_002"],
      "totalDuration": 8,
      "videoCount": 1,
      "reason": "同场景连续对话，合计8秒在安全范围",
      "driftRisk": "low",
      "recommendedProvider": "kling"
    }
  ],
  "summary": "6个分镜合并为4个视频，总时长32秒",
  "totalVideos": 4,
  "totalDuration": 32
}
\`\`\`

**关键决策规则**：
- 合并后总时长 ≤ 12秒（即梦实际安全上限，官方15秒但12+容易漂移）
- 打斗/快速动作：建议 4-6秒/段，用即梦
- 对话/情感：可以 8-10秒/段，用可灵（慢镜更稳）
- 环境转场：3-4秒，用即梦
- driftRisk=high 时，必须在 reason 中说明具体风险
`;
