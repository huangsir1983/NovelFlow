'use client';

import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { HDUpscaleNodeData } from '../../../types/canvas';

type HDUpscaleNode = Node<HDUpscaleNodeData, 'hdUpscale'>;

function HDUpscaleNodeComponent({ data, selected }: NodeProps<HDUpscaleNode>) {
  const [hovered, setHovered] = useState(false);

  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accentColor = 'rgba(52,211,153,1)';
  const accentFaint = 'rgba(52,211,153,0.5)';
  const accentDim = 'rgba(52,211,153,0.15)';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ width: 240, position: 'relative' }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* label row */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">⬆</span>
        <span
          className="text-[12px] font-medium tracking-wide"
          style={{ color: selected ? accentColor : accentFaint }}
        >
          高清化
        </span>
      </div>

      {/* card */}
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
        <div className="relative z-[1] p-5">
          {/* scaleFactor badge */}
          <div className="flex items-center gap-2 mb-4">
            <span
              className="text-[10px] font-mono px-1.5 py-0.5 rounded"
              style={{ color: 'rgba(52,211,153,0.65)', backgroundColor: accentDim }}
            >
              x{data.scaleFactor ?? 2}
            </span>
            <span className="text-[10px] text-white/20">放大倍数</span>
          </div>

          {/* stub body */}
          <div
            className="w-full rounded-xl flex items-center justify-center"
            style={{ height: 72, backgroundColor: 'rgba(255,255,255,0.015)' }}
          >
            <span className="text-[11px] text-white/15">待开发</span>
          </div>

          {/* progress bar placeholder */}
          <div className="flex items-center gap-2 mt-3">
            <div className="h-1 flex-1 rounded-full overflow-hidden" style={{ backgroundColor: 'rgba(255,255,255,0.03)' }}>
              <div
                className="h-full rounded-full"
                style={{ width: `${data.progress ?? 0}%`, backgroundColor: 'rgba(52,211,153,0.35)' }}
              />
            </div>
            <span className="text-[10px] text-white/15">{data.progress ?? 0}%</span>
          </div>
        </div>

        <div className="absolute bottom-2 right-2 z-[1]">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}

export const HDUpscaleNode = memo(HDUpscaleNodeComponent);
