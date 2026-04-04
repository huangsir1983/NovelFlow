'use client';

import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { ViewAngleNodeData } from '../../../types/canvas';

type ViewAngleNode = Node<ViewAngleNodeData, 'viewAngle'>;

function ViewAngleNodeComponent({ data, selected }: NodeProps<ViewAngleNode>) {
  const [hovered, setHovered] = useState(false);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(96,165,250,0.9)' : 'rgba(96,165,250,0.5)';

  // Show output if available, otherwise show input
  const displayUrl = data.outputImageUrl || data.inputImageUrl;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ width: 260, position: 'relative' }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">🔄</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>视角调整</span>
      </div>

      {/* Tapnow style: image fills card */}
      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
      }}>
        {/* Image */}
        <div style={{
          width: '100%', height: 150,
          backgroundColor: '#0c0e12',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {displayUrl ? (
            <img src={displayUrl} alt="view angle" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>🔄</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>等待输入图片</span>
            </div>
          )}
        </div>

        {/* Overlay: angle info + status */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'linear-gradient(transparent, rgba(0,0,0,0.7))',
          padding: '20px 12px 10px',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{
            fontSize: 9, padding: '2px 8px', borderRadius: 4,
            backgroundColor: 'rgba(96,165,250,0.2)', color: 'rgba(96,165,250,0.8)',
          }}>
            目标视角：{data.targetAngle}
          </span>
          {data.outputImageUrl && (
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)',
            }}>完成</span>
          )}
        </div>

        {/* Status dot */}
        <div style={{
          position: 'absolute', top: 10, right: 10, width: 8, height: 8,
          borderRadius: '50%', zIndex: 2,
          backgroundColor:
            data.status === 'running' ? '#60a5fa'
            : data.status === 'success' ? '#34d399'
            : data.status === 'error' ? '#f87171'
            : 'transparent',
        }} />

        {/* Progress */}
        {data.status === 'running' && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
            <div style={{ height: '100%', backgroundColor: 'rgba(96,165,250,0.6)', width: `${data.progress ?? 0}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}

export const ViewAngleNode = memo(ViewAngleNodeComponent);
