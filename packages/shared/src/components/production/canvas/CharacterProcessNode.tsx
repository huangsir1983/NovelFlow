'use client';

import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { CharacterProcessNodeData } from '../../../types/canvas';

type CharacterProcessNode = Node<CharacterProcessNodeData, 'characterProcess'>;

// Styles extracted to module level to avoid re-creation on each render
const outerStyle = { width: 180, position: 'relative' as const };
const imageContainerStyle = {
  width: '100%', height: 260,
  backgroundColor: '#0c0e12',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};
const placeholderIconStyle = { fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 };
const placeholderTextStyle = { fontSize: 10, color: 'rgba(255,255,255,0.15)' };
const overlayStyle = {
  position: 'absolute' as const, bottom: 0, left: 0, right: 0,
  background: 'linear-gradient(transparent, rgba(0,0,0,0.75))',
  padding: '24px 10px 10px',
  display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' as const,
};
const statusDotBase = {
  position: 'absolute' as const, top: 10, right: 10, width: 8, height: 8,
  borderRadius: '50%', zIndex: 2,
};

function CharacterProcessNodeComponent({ data, selected }: NodeProps<CharacterProcessNode>) {
  const [hovered, setHovered] = useState(false);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(167,139,250,0.9)' : 'rgba(167,139,250,0.5)';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={outerStyle}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">👤</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>
          {data.characterName || '角色'}
        </span>
      </div>

      {/* Portrait card */}
      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
      }}>
        <div style={imageContainerStyle}>
          {data.visualRefUrl ? (
            <img src={data.visualRefUrl} alt={data.characterName}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{ textAlign: 'center' }}>
              <span style={placeholderIconStyle}>👤</span>
              <span style={placeholderTextStyle}>选择角色图片</span>
            </div>
          )}
        </div>

        {/* Overlay: character name + badges at bottom */}
        <div style={overlayStyle}>
          <span style={{ fontSize: 11, fontWeight: 500, color: 'rgba(255,255,255,0.85)', width: '100%' }}>
            {data.characterName}
          </span>
          {data.selectedVariant && (
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(167,139,250,0.2)', color: 'rgba(167,139,250,0.8)',
            }}>
              {data.selectedVariant}
            </span>
          )}
          {data.visualRefUrl && (
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)',
            }}>
              图片已选
            </span>
          )}
        </div>

        {/* Status dot */}
        <div style={{
          ...statusDotBase,
          backgroundColor:
            data.status === 'running' ? '#60a5fa'
            : data.status === 'success' ? '#34d399'
            : data.status === 'error' ? '#f87171'
            : 'transparent',
        }} />
      </div>
    </div>
  );
}

export const CharacterProcessNode = memo(CharacterProcessNodeComponent);
