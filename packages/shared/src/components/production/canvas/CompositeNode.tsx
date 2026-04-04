'use client';
import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { CompositeNodeData } from '../../../types/canvas';

type CompositeNode = Node<CompositeNodeData, 'composite'>;

function CompositeNodeComponent({ data, selected }: NodeProps<CompositeNode>) {
  const [hovered, setHovered] = useState(false);
  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';

  const accentColor = selected ? 'rgba(129,140,248,0.9)' : 'rgba(129,140,248,0.5)';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative"
      style={{ width: 280 }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* Header label */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span style={{ fontSize: 13 }}>🎨</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: accentColor }}>
          合成
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
          {/* Top meta row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            {/* Layer count badge */}
            <span
              style={{
                fontSize: 9,
                color: 'rgba(129,140,248,0.55)',
                backgroundColor: 'rgba(129,140,248,0.08)',
                padding: '2px 8px',
                borderRadius: 99,
              }}
            >
              {data.layers.length} 图层
            </span>
            {/* Canvas dimensions */}
            <span
              style={{
                fontSize: 9,
                color: 'rgba(255,255,255,0.2)',
                backgroundColor: 'rgba(255,255,255,0.03)',
                padding: '2px 8px',
                borderRadius: 99,
              }}
            >
              {data.canvasWidth}x{data.canvasHeight}
            </span>
          </div>

          {/* Output image preview */}
          <div
            style={{
              width: '100%',
              borderRadius: 10,
              overflow: 'hidden',
              aspectRatio: '16 / 9',
              backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 12,
              position: 'relative',
            }}
          >
            {data.outputImageUrl ? (
              <img
                src={data.outputImageUrl}
                alt="合成预览"
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              />
            ) : (
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>打开编辑器</span>
            )}
          </div>

          {/* Open editor button */}
          <button
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%',
              padding: '7px 0',
              borderRadius: 8,
              border: '1px solid rgba(129,140,248,0.2)',
              backgroundColor: 'rgba(129,140,248,0.06)',
              color: 'rgba(129,140,248,0.7)',
              fontSize: 11,
              fontWeight: 500,
              cursor: 'pointer',
              letterSpacing: '0.02em',
              marginBottom: data.status === 'running' ? 12 : 0,
              transition: 'background-color 0.15s, border-color 0.15s',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(129,140,248,0.12)';
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(129,140,248,0.35)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'rgba(129,140,248,0.06)';
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(129,140,248,0.2)';
            }}
          >
            打开编辑器
          </button>

          {/* Progress bar */}
          {data.status === 'running' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  height: 4,
                  flex: 1,
                  borderRadius: 99,
                  backgroundColor: 'rgba(255,255,255,0.04)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${data.progress}%`,
                    backgroundColor: 'rgba(129,140,248,0.6)',
                    borderRadius: 99,
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>
              <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)' }}>{data.progress}%</span>
            </div>
          )}
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

export const CompositeNode = memo(CompositeNodeComponent);
