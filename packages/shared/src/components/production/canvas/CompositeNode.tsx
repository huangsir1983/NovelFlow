'use client';
import { memo, useState, useCallback } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { CompositeNodeData } from '../../../types/canvas';
import { useCanvasStore } from '../../../stores/canvasStore';

type CompositeNode = Node<CompositeNodeData, 'composite'>;

function CompositeNodeComponent({ id, data, selected }: NodeProps<CompositeNode>) {
  const [hovered, setHovered] = useState(false);
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';

  const accentColor = selected ? 'rgba(129,140,248,0.9)' : 'rgba(129,140,248,0.5)';

  const handleCardClick = useCallback(() => {
    const shotId = id.replace('composite-', '');
    useCanvasStore.getState().openCompositeEditor(shotId);
  }, [id]);

  const hasPreview = data.outputImageUrl || data.layers.length > 0;

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
        {data.layers.length > 0 && (
          <span style={{
            fontSize: 9, color: 'rgba(129,140,248,0.55)',
            backgroundColor: 'rgba(129,140,248,0.08)',
            padding: '2px 8px', borderRadius: 99, marginLeft: 2,
          }}>
            {data.layers.length} 图层
          </span>
        )}
      </div>

      {/* Card body — click to open editor */}
      <div
        className="canvas-card"
        onClick={handleCardClick}
        style={{
          borderRadius: 16,
          position: 'relative',
          overflow: 'hidden',
          backgroundColor: '#0c0e12',
          border: `1px solid ${cardBorder}`,
          transition: 'border-color 0.2s',
          cursor: 'pointer',
        }}
      >
        {/* Preview area — edge-to-edge */}
        <div style={{
          width: '100%',
          aspectRatio: '16 / 9',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          {data.outputImageUrl ? (
            <img
              src={data.outputImageUrl}
              alt="合成预览"
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
            />
          ) : data.layers.length > 0 ? (
            <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
              {(() => {
                const cw = data.canvasWidth || 1920;
                const ch = data.canvasHeight || 1080;
                // Card preview size (280 width, 16:9 aspect)
                const pw = 280;
                const ph = pw * 9 / 16;
                const sx = pw / cw;
                const sy = ph / ch;
                return data.layers
                  .filter(l => l.visible && l.imageUrl)
                  .sort((a, b) => a.zIndex - b.zIndex)
                  .map(l => (
                    <img
                      key={l.id}
                      src={l.imageUrl}
                      alt={l.type}
                      style={{
                        position: 'absolute',
                        left: l.x * sx,
                        top: l.y * sy,
                        width: l.width * sx,
                        height: l.height * sy,
                        transform: `rotate(${l.rotation || 0}deg)${l.flipX ? ' scaleX(-1)' : ''}`,
                        transformOrigin: 'center center',
                        opacity: l.opacity,
                        objectFit: l.type === 'background' ? 'cover' : 'contain',
                      }}
                    />
                  ));
              })()}
            </div>
          ) : (
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>点击打开编辑器</span>
          )}
        </div>

        {/* Bottom overlay with info */}
        {hasPreview && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(transparent, rgba(0,0,0,0.6))',
            padding: '16px 10px 8px',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{
              fontSize: 9, padding: '2px 8px', borderRadius: 4,
              backgroundColor: 'rgba(129,140,248,0.2)', color: 'rgba(129,140,248,0.8)',
            }}>
              {data.canvasWidth}x{data.canvasHeight}
            </span>
          </div>
        )}

        {/* Status dot */}
        {data.status && data.status !== 'idle' && (
          <div style={{
            position: 'absolute', top: 8, right: 8, width: 8, height: 8,
            borderRadius: '50%', zIndex: 2,
            backgroundColor:
              data.status === 'running' ? '#60a5fa'
              : data.status === 'success' ? '#34d399'
              : data.status === 'error' ? '#f87171'
              : 'transparent',
          }} />
        )}

        {/* Progress bar */}
        {data.status === 'running' && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
            <div style={{ height: '100%', backgroundColor: 'rgba(129,140,248,0.6)', width: `${data.progress ?? 0}%`, transition: 'width 0.3s' }} />
          </div>
        )}
      </div>
    </div>
  );
}

export const CompositeNode = memo(CompositeNodeComponent);
