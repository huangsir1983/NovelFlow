'use client';

// ══════════════════════════════════════════════════════════════
// NodeInspector.tsx — 右侧节点详情面板
// ══════════════════════════════════════════════════════════════

import React from 'react';
import { useInfiniteCanvasStore } from '../../../stores/infiniteCanvasStore';
import type { StoryboardContent } from '../../../types/canvas';

interface NodeInspectorProps {
  nodeId: string;
  onRunNode?: (nodeId: string) => void;
  onEditPrompt?: (nodeId: string) => void;
  onViewChain?: (nodeId: string) => void;
}

export const NodeInspector: React.FC<NodeInspectorProps> = ({ nodeId, onRunNode, onEditPrompt, onViewChain }) => {
  const node = useInfiniteCanvasStore((s) => s.nodes.get(nodeId));

  if (!node) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{
        fontSize: 11, color: 'rgba(255,255,255,0.5)', fontWeight: 500,
        textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8,
      }}>
        选中节点
      </div>

      <div style={{
        background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 10, marginBottom: 8,
        border: '0.5px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 4, color: 'rgba(255,255,255,0.9)' }}>
          {node.label}
        </div>
        {node.type === 'storyboard' && (
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', lineHeight: 1.5 }}>
            {(node.content as StoryboardContent).rawText?.slice(0, 80)}...
          </div>
        )}
        <div style={{ marginTop: 6, display: 'flex', gap: 4 }}>
          <ActionBtn onClick={() => onRunNode?.(nodeId)}>执行</ActionBtn>
          <ActionBtn onClick={() => onEditPrompt?.(nodeId)}>编辑提示词</ActionBtn>
        </div>
        <ActionBtn style={{ marginTop: 6, width: '100%' }} onClick={() => onViewChain?.(nodeId)}>
          查看完整分镜链 →
        </ActionBtn>
      </div>
    </div>
  );
};

const ActionBtn: React.FC<{
  children: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}> = ({ children, onClick, style }) => (
  <button
    onClick={onClick}
    style={{
      fontSize: 11, padding: '5px 10px',
      border: '0.5px solid rgba(255,255,255,0.08)',
      borderRadius: 6, background: 'transparent',
      color: 'rgba(255,255,255,0.85)', cursor: 'pointer', flex: 1,
      ...style,
    }}
  >
    {children}
  </button>
);
