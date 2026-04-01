'use client';

// ══════════════════════════════════════════════════════════════
// NodeFloatingToolbar.tsx — 节点选中时的浮动工具栏
//
// 场景卡片选中后：
//   上方第一行：流程操作按钮（生成分镜 → 提示词 → 生图 → 视频）
//   上方第二行：场景详情摘要（核心事件、角色、模块类型、时长）
//   下方：AI 指令输入框
// ══════════════════════════════════════════════════════════════

import { memo, useState, useCallback, useEffect, useRef } from 'react';
import { useReactFlow, useStore } from '@xyflow/react';
import { useCanvasStore } from '../../../stores/canvasStore';
import type { CanvasModuleType } from '../../../types/canvas';

interface NodeFloatingToolbarProps {
  nodeId: string;
}

const MODULE_LABELS: Record<string, { icon: string; label: string; color: string }> = {
  dialogue:  { icon: '💬', label: '对话', color: '#378ADD' },
  action:    { icon: '⚔️', label: '动作', color: '#D85A30' },
  suspense:  { icon: '🔍', label: '悬疑', color: '#534AB7' },
  landscape: { icon: '🏔', label: '转场', color: '#1D9E75' },
  emotion:   { icon: '💭', label: '情感', color: '#D4537E' },
};

function NodeFloatingToolbarComponent({ nodeId }: NodeFloatingToolbarProps) {
  const { getNode } = useReactFlow();
  // Subscribe to viewport so we re-render on every pan/zoom
  useStore((s) => s.transform);
  const [aiInput, setAiInput] = useState('');
  const [rect, setRect] = useState<{ cx: number; top: number; bottom: number; width: number } | null>(null);
  const rafRef = useRef(0);

  // Track the actual DOM element bounding rect of the selected node
  useEffect(() => {
    function update() {
      const el = document.querySelector(`[data-id="${nodeId}"]`) as HTMLElement | null;
      if (el) {
        const r = el.getBoundingClientRect();
        setRect({ cx: r.left + r.width / 2, top: r.top, bottom: r.bottom, width: r.width });
      }
      rafRef.current = requestAnimationFrame(update);
    }
    rafRef.current = requestAnimationFrame(update);
    return () => cancelAnimationFrame(rafRef.current);
  }, [nodeId]);

  const node = getNode(nodeId);

  const handleAiSubmit = useCallback(() => {
    if (!aiInput.trim()) return;
    const store = useCanvasStore.getState();
    store.setAIPanelOpen(true);
    store.addAIMessage({
      id: `u-${Date.now()}`,
      role: 'user',
      content: `[针对节点 ${nodeId}] ${aiInput}`,
      timestamp: Date.now(),
    });
    setAiInput('');
  }, [aiInput, nodeId]);

  if (!node || !rect) return null;

  const data = node.data as {
    heading?: string; description?: string; coreEvent?: string; emotionalPeak?: string;
    characterNames?: string[]; moduleType?: CanvasModuleType; nodeType?: string;
    shotCount?: number; location?: string; timeOfDay?: string;
    estimated_duration_s?: number;
  };

  const nodeType = data.nodeType || node.type || 'scene';

  const moduleInfo = data.moduleType ? MODULE_LABELS[data.moduleType] : null;
  const coreText = data.coreEvent || data.description || '';
  const characters = data.characterNames || [];

  return (
    <>
      {/* ══ 上方：流程操作 + 场景详情 ══ */}
      <div
        className="nodrag nopan"
        style={{
          position: 'fixed',
          left: rect.cx,
          top: rect.top - 8,
          transform: 'translate(-50%, -100%)',
          zIndex: 9999,
          pointerEvents: 'auto',
        }}
      >
        {/* 流程操作按钮 — 根据节点类型显示不同内容 */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 3,
          padding: '5px 8px', borderRadius: 12,
          background: 'rgba(20, 22, 30, 0.95)',
          border: '1px solid rgba(255,255,255,0.1)',
          backdropFilter: 'blur(12px)',
          boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
        }}>
          {nodeType === 'scene' && (
            <>
              <FlowBtn icon="▶" label="展开分镜" color="#3b82f6" />
              <FlowBtn icon="✦" label="提示词" color="#8b5cf6" />
              <FlowBtn icon="◧" label="生图" color="#22c55e" />
              <FlowBtn icon="▶" label="视频" color="#eab308" />
            </>
          )}
          {nodeType === 'shot' && (
            <>
              <FlowBtn icon="✦" label="生成提示词" color="#8b5cf6" />
              <FlowBtn icon="◧" label="生图" color="#22c55e" />
              <FlowBtn icon="▶" label="视频" color="#eab308" />
              <FlowBtn icon="✎" label="编辑" color="rgba(255,255,255,0.5)" />
            </>
          )}
          {nodeType === 'promptAssembly' && (
            <>
              <FlowBtn icon="✎" label="编辑提示词" color="#8b5cf6" />
              <FlowBtn icon="◧" label="生图" color="#22c55e" />
              <FlowBtn icon="⧉" label="复制" color="rgba(255,255,255,0.5)" />
            </>
          )}
          {nodeType === 'imageGeneration' && (
            <>
              <FlowBtn icon="▶" label="生视频" color="#eab308" />
              <FlowBtn icon="↻" label="重生成" color="#3b82f6" />
              <FlowBtn icon="✓" label="审核" color="#22c55e" />
            </>
          )}
          {nodeType === 'videoGeneration' && (
            <>
              <FlowBtn icon="↻" label="重生成" color="#3b82f6" />
              <FlowBtn icon="↓" label="下载" color="rgba(255,255,255,0.5)" />
            </>
          )}
          <FlowBtn icon="⋯" label="" color="rgba(255,255,255,0.3)" />
        </div>
      </div>

      {/* ══ 下方：AI 输入框 ══ */}
      <div
        className="nodrag nopan"
        style={{
          position: 'fixed',
          left: rect.cx,
          top: rect.bottom + 12,
          transform: 'translateX(-50%)',
          minWidth: 280,
          zIndex: 9999,
          pointerEvents: 'auto',
        }}
      >
        <div style={{
          borderRadius: 12,
          background: 'rgba(20, 22, 30, 0.95)',
          border: '1px solid rgba(255,255,255,0.1)',
          backdropFilter: 'blur(12px)',
          boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
          overflow: 'hidden',
        }}>
          <textarea
            value={aiInput}
            onChange={(e) => setAiInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAiSubmit(); } }}
            placeholder="描述任何你想要生成的内容..."
            rows={2}
            style={{
              width: '100%', background: 'transparent', border: 'none', outline: 'none', resize: 'none',
              fontSize: 12, color: 'rgba(255,255,255,0.7)', padding: '10px 12px', fontFamily: 'inherit',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', padding: '0 8px 6px' }}>
            <div
              onClick={handleAiSubmit}
              style={{
                width: 24, height: 24, borderRadius: '50%',
                background: aiInput.trim() ? '#6366f1' : 'rgba(255,255,255,0.05)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, color: aiInput.trim() ? '#fff' : 'rgba(255,255,255,0.15)',
                cursor: aiInput.trim() ? 'pointer' : 'default',
              }}
            >↑</div>
          </div>
        </div>
      </div>
    </>
  );
}

// ── 流程按钮 ──
function FlowBtn({ icon, label, color }: { icon: string; label: string; color: string }) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 4,
        padding: '4px 10px', borderRadius: 8,
        fontSize: 11, color, cursor: 'pointer',
        transition: 'background 0.1s',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >
      <span>{icon}</span>
      {label && <span>{label}</span>}
    </div>
  );
}

export const NodeFloatingToolbar = memo(NodeFloatingToolbarComponent);
