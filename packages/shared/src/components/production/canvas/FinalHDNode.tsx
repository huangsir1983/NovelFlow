'use client';
import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { FinalHDNodeData } from '../../../types/canvas';

type FinalHDNode = Node<FinalHDNodeData, 'finalHD'>;

function FinalHDNodeComponent({ data, selected }: NodeProps<FinalHDNode>) {
  const [hovered, setHovered] = useState(false);
  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';

  const accentColor = selected ? 'rgba(52,211,153,0.9)' : 'rgba(52,211,153,0.5)';

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
        <span style={{ fontSize: 13 }}>🖼</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: accentColor }}>
          终稿高清
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
          {/* Scale factor badge */}
          <div style={{ marginBottom: 12 }}>
            <span
              style={{
                fontSize: 9,
                color: 'rgba(52,211,153,0.5)',
                backgroundColor: 'rgba(52,211,153,0.06)',
                padding: '2px 10px',
                borderRadius: 99,
              }}
            >
              {data.scaleFactor}x 放大
            </span>
          </div>

          {/* Output image preview */}
          <div
            style={{
              width: '100%',
              aspectRatio: '4 / 3',
              borderRadius: 10,
              backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 12,
            }}
          >
            {data.outputImageUrl ? (
              <img
                src={data.outputImageUrl}
                alt="终稿"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : null}
          </div>

          {/* STUB label */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '6px 0',
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

export const FinalHDNode = memo(FinalHDNodeComponent);
