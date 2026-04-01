'use client';

// ══════════════════════════════════════════════════════════════
// Toolbar.tsx — 画布顶部工具栏
// ══════════════════════════════════════════════════════════════

import React from 'react';
import { useInfiniteCanvasStore } from '../../../stores/infiniteCanvasStore';

export type CanvasMode = 'select' | 'pan';

interface ToolbarProps {
  mode: CanvasMode;
  onModeChange: (mode: CanvasMode) => void;
  onRunBatch?: () => void;
  onRunAgentAssign?: () => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({ mode, onModeChange, onRunBatch, onRunAgentAssign }) => {
  const fitToContent = useInfiniteCanvasStore((s) => s.fitToContent);
  const toggleCollapseAll = useInfiniteCanvasStore((s) => s.toggleCollapseAll);
  const isRunning = useInfiniteCanvasStore((s) => s.isRunning);
  const nodes = useInfiniteCanvasStore((s) => s.nodes);

  const pendingCount = Array.from(nodes.values())
    .filter((n) => n.status === 'ready' || n.status === 'outdated').length;

  return (
    <div style={{
      position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 50,
      display: 'flex', gap: 6,
      background: '#12122a', border: '0.5px solid rgba(255,255,255,0.08)',
      borderRadius: 10, padding: '6px 10px', alignItems: 'center',
      boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
    }}>
      <TbBtn active={mode === 'select'} onClick={() => onModeChange('select')}>选择 V</TbBtn>
      <TbBtn active={mode === 'pan'} onClick={() => onModeChange('pan')}>平移 H</TbBtn>
      <TbSep />
      <TbBtn onClick={fitToContent}>适应画布 ⌘0</TbBtn>
      <TbBtn onClick={toggleCollapseAll}>折叠模块</TbBtn>
      <TbSep />
      <TbBtn onClick={onRunAgentAssign} disabled={isRunning}>Agent 自动分配</TbBtn>
      <TbSep />
      <TbBtn
        onClick={onRunBatch}
        disabled={isRunning || pendingCount === 0}
        style={{ color: pendingCount > 0 ? '#6366f1' : undefined }}
      >
        批量执行 {pendingCount > 0 ? `(${pendingCount})` : ''}
      </TbBtn>
    </div>
  );
};

const TbBtn: React.FC<{
  children: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}> = ({ children, active, disabled, onClick, style }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      padding: '5px 12px', fontSize: 12,
      border: `0.5px solid ${active ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.06)'}`,
      borderRadius: 6,
      background: active ? 'rgba(255,255,255,0.06)' : 'transparent',
      color: disabled ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.85)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      whiteSpace: 'nowrap',
      ...style,
    }}
  >
    {children}
  </button>
);

const TbSep: React.FC = () => (
  <div style={{ width: 0.5, height: 20, background: 'rgba(255,255,255,0.08)', margin: '0 4px' }} />
);
