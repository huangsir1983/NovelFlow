'use client';
import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { PropAngleNodeData } from '../../../types/canvas';

type PropAngleNode = Node<PropAngleNodeData, 'propAngle'>;

function PropAngleNodeComponent({ data, selected }: NodeProps<PropAngleNode>) {
  const [hovered, setHovered] = useState(false);
  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';

  const accentColor = selected ? 'rgba(251,191,36,0.9)' : 'rgba(251,191,36,0.5)';

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
      style={{ width: 260 }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* Header label */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span style={{ fontSize: 13 }}>🔄</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: accentColor }}>
          道具视角
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
          {/* Target angle badge */}
          {data.targetAngle && (
            <div style={{ marginBottom: 10 }}>
              <span
                style={{
                  fontSize: 9,
                  color: 'rgba(251,191,36,0.4)',
                  backgroundColor: 'rgba(251,191,36,0.06)',
                  padding: '2px 8px',
                  borderRadius: 99,
                }}
              >
                {data.targetAngle}
              </span>
            </div>
          )}

          {/* Input → Output image comparison */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            {/* Input */}
            <div style={imgBoxStyle}>
              {data.inputImageUrl ? (
                <img
                  src={data.inputImageUrl}
                  alt="输入"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.15)' }}>输入</span>
              )}
            </div>

            {/* Arrow */}
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.15)', flexShrink: 0 }}>→</span>

            {/* Output */}
            <div style={imgBoxStyle}>
              {data.outputImageUrl ? (
                <img
                  src={data.outputImageUrl}
                  alt="输出"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.15)' }}>输出</span>
              )}
            </div>
          </div>

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
                    backgroundColor: 'rgba(251,191,36,0.55)',
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

export const PropAngleNode = memo(PropAngleNodeComponent);
