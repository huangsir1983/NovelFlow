'use client';

// ══════════════════════════════════════════════════════════════
// ImageNode.tsx — 图片合成节点
// ══════════════════════════════════════════════════════════════

import React from 'react';
import { BaseNode } from './BaseNode';
import type { CanvasNodeData, ImageContent } from '../../../types/canvas';

export const ImageNode: React.FC<{ node: CanvasNodeData }> = ({ node }) => {
  const content = node.content as ImageContent;
  const doneSteps = content.workflowSteps.filter((s) => s.status === 'done').length;
  const totalSteps = content.workflowSteps.length;
  const progress = totalSteps > 0 ? doneSteps / totalSteps : 0;

  return (
    <BaseNode node={node} headerColor="#22c55e" icon="🖼">
      <div style={{
        width: '100%', height: 72, borderRadius: 6,
        background: content.resultImageUrl ? undefined : 'rgba(255,255,255,0.03)',
        border: '0.5px solid rgba(255,255,255,0.06)',
        marginBottom: 6, overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        {content.resultImageUrl ? (
          <img src={content.resultImageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} loading="lazy" />
        ) : (
          <span style={{ fontSize: 22, opacity: 0.4 }}>🖼</span>
        )}
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, background: 'rgba(0,0,0,0.2)' }}>
          <div style={{ width: `${progress * 100}%`, height: '100%', background: '#22c55e', transition: 'width 0.4s ease' }} />
        </div>
      </div>

      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 4 }}>
        合成步骤 {doneSteps}/{totalSteps}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {content.workflowSteps.slice(0, 3).map((step) => (
          <WorkflowStepRow key={step.id} name={step.name} status={step.status} />
        ))}
        {content.workflowSteps.length > 3 && (
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>+{content.workflowSteps.length - 3} 步骤</div>
        )}
      </div>
    </BaseNode>
  );
};

const WorkflowStepRow: React.FC<{ name: string; status: string }> = ({ name, status }) => {
  const colors: Record<string, string> = { done: '#22c55e', processing: '#f59e0b', idle: '#6b7280', error: '#ef4444' };
  const icons: Record<string, string> = { done: '✓', processing: '⟳', idle: '○', error: '✗' };
  const color = colors[status] || '#6b7280';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10 }}>
      <span style={{ color, width: 12, textAlign: 'center' }}>{icons[status] || '○'}</span>
      <span style={{ color: 'rgba(255,255,255,0.5)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {name}
      </span>
    </div>
  );
};
