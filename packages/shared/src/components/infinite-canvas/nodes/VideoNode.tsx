'use client';

// ══════════════════════════════════════════════════════════════
// VideoNode.tsx — 视频生成节点
// ══════════════════════════════════════════════════════════════

import React from 'react';
import { BaseNode } from './BaseNode';
import type { CanvasNodeData, VideoContent } from '../../../types/canvas';

const PROVIDER_LABELS: Record<string, string> = {
  jimeng: '即梦', kling: '可灵', runway: 'Runway', pika: 'Pika',
};

export const VideoNode: React.FC<{ node: CanvasNodeData }> = ({ node }) => {
  const content = node.content as VideoContent;

  return (
    <BaseNode node={node} headerColor="#eab308" icon="🎬">
      <div style={{
        width: '100%', height: 64, borderRadius: 6,
        background: content.thumbnailUrl ? undefined : 'rgba(234,179,8,0.06)',
        border: '0.5px solid rgba(255,255,255,0.06)',
        marginBottom: 6, overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        {content.thumbnailUrl ? (
          <>
            <img src={content.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} loading="lazy" />
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(0,0,0,0.15)',
            }}>
              <div style={{
                width: 24, height: 24, borderRadius: '50%',
                background: 'rgba(255,255,255,0.9)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10,
              }}>▶</div>
            </div>
          </>
        ) : (
          <span style={{ fontSize: 20, opacity: 0.4 }}>🎬</span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
        <Tag color="#eab308">{PROVIDER_LABELS[content.provider] || content.provider}</Tag>
        <Tag color="#6b7280">{content.duration}s</Tag>
        <Tag color="#6b7280">{content.resolution}</Tag>
      </div>

      {content.jobId && (
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          任务: {content.jobId}
        </div>
      )}
    </BaseNode>
  );
};

const Tag: React.FC<{ children: React.ReactNode; color: string }> = ({ children, color }) => (
  <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 4, background: color + '15', color }}>
    {children}
  </span>
);
