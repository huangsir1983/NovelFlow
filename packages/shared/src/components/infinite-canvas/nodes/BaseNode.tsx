'use client';

// ══════════════════════════════════════════════════════════════
// BaseNode.tsx — 节点基础容器：头部 + 状态 + 拖拽 + 选择
// ══════════════════════════════════════════════════════════════

import React, { useRef, useCallback } from 'react';
import { useInfiniteCanvasStore } from '../../../stores/infiniteCanvasStore';
import type { CanvasNodeData, CanvasNodeStatus, CanvasModuleType } from '../../../types/canvas';

// ── 状态视觉配置 ──

const STATUS_CONFIG: Record<CanvasNodeStatus, { color: string; bg: string; label: string }> = {
  idle:       { color: '#888780', bg: 'rgba(136,135,128,0.1)', label: '未开始' },
  ready:      { color: '#378ADD', bg: 'rgba(55,138,221,0.1)',  label: '就绪' },
  processing: { color: '#BA7517', bg: 'rgba(186,117,23,0.1)',  label: '处理中' },
  done:       { color: '#1D9E75', bg: 'rgba(29,158,117,0.1)',  label: '完成' },
  error:      { color: '#E24B4A', bg: 'rgba(226,75,74,0.1)',   label: '失败' },
  outdated:   { color: '#D85A30', bg: 'rgba(216,90,48,0.1)',   label: '需更新' },
};

const MODULE_COLORS: Record<CanvasModuleType, string> = {
  dialogue:  '#378ADD',
  action:    '#D85A30',
  suspense:  '#534AB7',
  landscape: '#1D9E75',
  emotion:   '#D4537E',
};

interface BaseNodeProps {
  node: CanvasNodeData;
  headerColor: string;
  icon: string;
  children: React.ReactNode;
}

export const BaseNode: React.FC<BaseNodeProps> = ({ node, headerColor, icon, children }) => {
  const { selectNode, moveNode, view, selectedNodeIds, hoveredNodeId, setHoveredNode } = useInfiniteCanvasStore();
  const { transform } = view;
  const dragRef = useRef<{ startX: number; startY: number; nodeX: number; nodeY: number } | null>(null);
  const isSelected = selectedNodeIds.has(node.id);
  const isHovered = hoveredNodeId === node.id;
  const sc = STATUS_CONFIG[node.status];

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    selectNode(node.id, e.shiftKey);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      nodeX: node.position.x,
      nodeY: node.position.y,
    };
    const onMove = (me: MouseEvent) => {
      if (!dragRef.current) return;
      const dx = (me.clientX - dragRef.current.startX) / transform.scale;
      const dy = (me.clientY - dragRef.current.startY) / transform.scale;
      moveNode(node.id, {
        x: dragRef.current.nodeX + dx,
        y: dragRef.current.nodeY + dy,
      });
    };
    const onUp = () => {
      dragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [node.id, node.position, transform.scale, selectNode, moveNode]);

  return (
    <div
      onMouseDown={onMouseDown}
      onMouseEnter={() => setHoveredNode(node.id)}
      onMouseLeave={() => setHoveredNode(null)}
      style={{
        background: '#12122a',
        border: `${isSelected ? 1.5 : 0.5}px solid ${isSelected ? '#6366f1' : isHovered ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)'}`,
        borderRadius: 12,
        cursor: 'pointer',
        transition: 'border-color 0.12s, box-shadow 0.12s',
        position: 'relative',
        overflow: 'visible',
        boxShadow: isSelected ? '0 0 0 2px rgba(99,102,241,0.3)' : '0 4px 24px rgba(0,0,0,0.4)',
      }}
    >
      {/* 节点头部 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '7px 10px 6px',
        borderBottom: '0.5px solid rgba(255,255,255,0.06)',
        background: headerColor + '18',
        borderRadius: '12px 12px 0 0',
      }}>
        <div style={{
          width: 18, height: 18, borderRadius: 4,
          background: headerColor + '33',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, flexShrink: 0,
        }}>
          {icon}
        </div>
        <span style={{
          fontSize: 11, fontWeight: 600, flex: 1,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          color: 'rgba(255,255,255,0.9)',
        }}>
          {node.label}
        </span>
        <div
          style={{ width: 6, height: 6, borderRadius: '50%', background: sc.color, flexShrink: 0 }}
          title={sc.label}
        />
      </div>

      {/* 节点体 */}
      <div style={{ padding: '8px 10px' }}>
        {children}

        {/* 底部标签行 */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
          <StatusPill status={node.status} />
          {node.moduleType && (
            <span style={{
              fontSize: 10, padding: '2px 6px', borderRadius: 4,
              background: MODULE_COLORS[node.moduleType] + '18',
              color: MODULE_COLORS[node.moduleType],
            }}>
              {node.agentAssigned && '🤖 '}{node.moduleType}
            </span>
          )}
        </div>
      </div>

      {/* Agent 分配徽章 */}
      {node.agentAssigned && (
        <div style={{
          position: 'absolute', top: -7, right: -7,
          width: 16, height: 16, borderRadius: '50%',
          background: '#1D9E75', border: '2px solid #12122a',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 8, color: '#fff', fontWeight: 700,
        }}>A</div>
      )}
    </div>
  );
};

export const StatusPill: React.FC<{ status: CanvasNodeStatus }> = ({ status }) => {
  const sc = STATUS_CONFIG[status];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 10, padding: '2px 7px', borderRadius: 99,
      background: sc.bg, color: sc.color, fontWeight: 500,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: sc.color }} />
      {sc.label}
    </span>
  );
};
