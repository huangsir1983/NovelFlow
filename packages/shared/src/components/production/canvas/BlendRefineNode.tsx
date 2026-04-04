'use client';
import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { BlendRefineNodeData } from '../../../types/canvas';

type BlendRefineNode = Node<BlendRefineNodeData, 'blendRefine'>;

function BlendRefineNodeComponent({ data, selected }: NodeProps<BlendRefineNode>) {
  const [hovered, setHovered] = useState(false);
  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';

  const accentColor = selected ? 'rgba(45,212,191,0.9)' : 'rgba(45,212,191,0.5)';

  const imgBoxStyle: React.CSSProperties = {
    flex: 1,
    aspectRatio: '1 / 1',
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative"
      style={{ width: 240 }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* Header label */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span style={{ fontSize: 13 }}>🔀</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: accentColor }}>
          融合
        </span>
      </div>

      {/* Card body */}
      <div
        className="canvas-card"
        style={{
          borderRadius: 16,
          position: 'relative',
          overflow: 'hidden',
          backgroundColor: cardBg,
          border: `1px solid ${cardBorder}`,
          transition: 'background-color 0.2s, border-color 0.2s',
        }}
      >
        <div style={{ position: 'relative', zIndex: 1, padding: 16 }}>
          {/* Input / Output image preview area */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14 }}>
            <div style={imgBoxStyle}>
              {data.inputImageUrl ? (
                <img
                  src={data.inputImageUrl}
                  alt="输入"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.12)' }}>输入</span>
              )}
            </div>
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.12)', flexShrink: 0 }}>→</span>
            <div style={imgBoxStyle}>
              {data.outputImageUrl ? (
                <img
                  src={data.outputImageUrl}
                  alt="输出"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.12)' }}>输出</span>
              )}
            </div>
          </div>

          {/* STUB label */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '10px 0',
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: 'rgba(255,255,255,0.18)',
                letterSpacing: '0.05em',
              }}
            >
              待开发
            </span>
          </div>
        </div>

        <div style={{ position: 'absolute', bottom: 6, right: 6, zIndex: 1 }}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}

export const BlendRefineNode = memo(BlendRefineNodeComponent);
