'use client';
import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { PropProcessNodeData } from '../../../types/canvas';

type PropProcessNode = Node<PropProcessNodeData, 'propProcess'>;

function PropProcessNodeComponent({ data, selected }: NodeProps<PropProcessNode>) {
  const [hovered, setHovered] = useState(false);
  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';

  const accentColor = selected ? 'rgba(251,191,36,0.9)' : 'rgba(251,191,36,0.5)';

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
        <span style={{ fontSize: 13 }}>🎪</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: accentColor }}>
          {data.propName || '道具'}
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
          {/* Prop image or placeholder */}
          {data.visualRefUrl ? (
            <div
              style={{
                width: '100%',
                borderRadius: 10,
                overflow: 'hidden',
                aspectRatio: '1 / 1',
                backgroundColor: 'rgba(255,255,255,0.02)',
              }}
            >
              <img
                src={data.visualRefUrl}
                alt={data.propName}
                style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              />
            </div>
          ) : (
            <div
              style={{
                width: '100%',
                aspectRatio: '1 / 1',
                borderRadius: 10,
                backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)' }}>选择道具</span>
            </div>
          )}

          {/* Prop name badge */}
          {data.propName && (
            <div style={{ marginTop: 10 }}>
              <span
                style={{
                  fontSize: 10,
                  color: 'rgba(251,191,36,0.5)',
                  backgroundColor: 'rgba(251,191,36,0.06)',
                  padding: '2px 8px',
                  borderRadius: 99,
                }}
              >
                {data.propName}
              </span>
            </div>
          )}
        </div>

        {/* Resize grip decoration */}
        <div style={{ position: 'absolute', bottom: 6, right: 6, zIndex: 1 }}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}

export const PropProcessNode = memo(PropProcessNodeComponent);
