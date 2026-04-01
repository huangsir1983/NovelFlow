'use client';

// ══════════════════════════════════════════════════════════════
// StoryboardNode.tsx — 分镜文本节点
// ══════════════════════════════════════════════════════════════

import React from 'react';
import { BaseNode } from './BaseNode';
import type { CanvasNodeData, StoryboardContent } from '../../../types/canvas';

const SHOT_LABELS: Record<string, string> = {
  'close-up': '特写', 'medium': '中景', 'wide': '远景',
  'overhead': '俯视', 'low-angle': '仰视', 'pov': '主观', 'over-shoulder': '过肩',
};

export const StoryboardNode: React.FC<{ node: CanvasNodeData }> = ({ node }) => {
  const content = node.content as StoryboardContent;

  return (
    <BaseNode node={node} headerColor="#3b82f6" icon="📄">
      <div style={{
        fontSize: 11, color: 'rgba(255,255,255,0.6)', lineHeight: 1.5, marginBottom: 6,
        display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {content.rawText || '暂无分镜内容'}
      </div>

      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
        {content.shotType && <Tag color="#3b82f6">{SHOT_LABELS[content.shotType] || content.shotType}</Tag>}
        {content.emotion && <Tag color="#8b5cf6">{content.emotion}</Tag>}
        {content.duration > 0 && <Tag color="#6b7280">{content.duration}s</Tag>}
      </div>

      {content.characterIds.length > 0 && (
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>
          角色: {content.characterIds.length}
        </div>
      )}

      <div style={{ marginTop: 6, display: 'flex', gap: 4 }}>
        <PromptDot label="图" filled={!!content.imagePrompt} />
        <PromptDot label="视" filled={!!content.videoPrompt} />
      </div>
    </BaseNode>
  );
};

const Tag: React.FC<{ children: React.ReactNode; color: string }> = ({ children, color }) => (
  <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 4, background: color + '15', color }}>
    {children}
  </span>
);

const PromptDot: React.FC<{ label: string; filled: boolean }> = ({ label, filled }) => (
  <span style={{
    fontSize: 9, padding: '1px 5px', borderRadius: 3,
    background: filled ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.04)',
    color: filled ? '#22c55e' : 'rgba(255,255,255,0.3)',
    border: `0.5px solid ${filled ? 'rgba(34,197,94,0.25)' : 'rgba(255,255,255,0.06)'}`,
  }}>
    {label}提示词{filled ? '✓' : '?'}
  </span>
);
