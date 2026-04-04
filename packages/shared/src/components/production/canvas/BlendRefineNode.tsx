'use client';
import { memo, useState, useCallback } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { BlendRefineNodeData } from '../../../types/canvas';
import { useNodeExecution } from '../../../hooks/useNodeExecution';

type BlendRefineNode = Node<BlendRefineNodeData, 'blendRefine'>;

function BlendRefineNodeComponent({ id, data, selected }: NodeProps<BlendRefineNode>) {
  const [hovered, setHovered] = useState(false);
  const { runNode, confirmBlendRefine } = useNodeExecution();

  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';
  const accentColor = selected ? 'rgba(45,212,191,0.9)' : 'rgba(45,212,191,0.5)';

  const isRunning = data.status === 'running' || data.status === 'queued';
  const hasPreview = data.status === 'success' && !!data.previewImageUrl && !data.confirmed;
  const isConfirmed = data.status === 'success' && !!data.confirmed;
  const hasInput = !!data.inputImageUrl;
  const isError = data.status === 'error';

  const handleRun = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    runNode(id);
  }, [runNode, id]);

  const handleConfirm = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    confirmBlendRefine(id);
  }, [confirmBlendRefine, id]);

  const imgBoxStyle: React.CSSProperties = {
    flex: 1,
    aspectRatio: '16 / 9',
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: 'rgba(255,255,255,0.02)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const btnBase: React.CSSProperties = {
    flex: 1,
    padding: '6px 0',
    borderRadius: 8,
    border: 'none',
    fontSize: 11,
    fontWeight: 500,
    cursor: 'pointer',
    letterSpacing: '0.03em',
    transition: 'opacity 0.15s',
  };

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative"
      style={{ width: 240 }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '50%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '50%' }} />

      {/* Header */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span style={{ fontSize: 13 }}>🔀</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: accentColor }}>
          融合
        </span>
        {isConfirmed && (
          <span style={{ fontSize: 10, color: '#4ade80', marginLeft: 'auto', marginRight: 4 }}>
            已确认
          </span>
        )}
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
        <div style={{ position: 'relative', zIndex: 1, padding: 12 }}>
          {/* Input image preview */}
          <div style={imgBoxStyle}>
            {hasInput ? (
              <img
                src={data.inputImageUrl}
                alt="合成图"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            ) : (
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>等待合成图</span>
            )}
          </div>

          {/* Running state — progress bar */}
          {isRunning && (
            <div style={{ marginTop: 10 }}>
              <div style={{
                height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.06)', overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%', borderRadius: 2,
                  backgroundColor: 'rgba(45,212,191,0.7)',
                  width: `${Math.max(data.progress || 0, 10)}%`,
                  transition: 'width 0.3s ease',
                }} />
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', textAlign: 'center', marginTop: 4 }}>
                融图中...
              </div>
            </div>
          )}

          {/* Preview state — show result + confirm/retry buttons */}
          {hasPreview && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginBottom: 4, textAlign: 'center' }}>
                融图预览
              </div>
              <div style={{ ...imgBoxStyle, aspectRatio: '16 / 9' }}>
                <img
                  src={data.previewImageUrl}
                  alt="融图预览"
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <button
                  onClick={handleConfirm}
                  style={{
                    ...btnBase,
                    backgroundColor: 'rgba(45,212,191,0.2)',
                    color: 'rgba(45,212,191,0.9)',
                  }}
                >
                  确认采用
                </button>
                <button
                  onClick={handleRun}
                  style={{
                    ...btnBase,
                    backgroundColor: 'rgba(255,255,255,0.06)',
                    color: 'rgba(255,255,255,0.5)',
                  }}
                >
                  重新生成
                </button>
              </div>
            </div>
          )}

          {/* Confirmed state — show output + re-blend button */}
          {isConfirmed && data.outputImageUrl && (
            <div style={{ marginTop: 10 }}>
              <div style={{ ...imgBoxStyle, aspectRatio: '16 / 9' }}>
                <img
                  src={data.outputImageUrl}
                  alt="融合结果"
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              </div>
              <button
                onClick={handleRun}
                style={{
                  ...btnBase,
                  width: '100%',
                  marginTop: 8,
                  backgroundColor: 'rgba(45,212,191,0.12)',
                  color: 'rgba(45,212,191,0.7)',
                }}
              >
                再次融图
              </button>
            </div>
          )}

          {/* Error state */}
          {isError && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 10, color: '#f87171', textAlign: 'center', marginBottom: 6 }}>
                {data.errorMessage || '融图失败'}
              </div>
              <button
                onClick={handleRun}
                style={{
                  ...btnBase,
                  width: '100%',
                  backgroundColor: 'rgba(248,113,113,0.15)',
                  color: '#f87171',
                }}
              >
                重试
              </button>
            </div>
          )}

          {/* Idle state with input — show run button */}
          {data.status === 'idle' && hasInput && (
            <div style={{ marginTop: 10 }}>
              <button
                onClick={handleRun}
                style={{
                  ...btnBase,
                  width: '100%',
                  backgroundColor: 'rgba(45,212,191,0.15)',
                  color: 'rgba(45,212,191,0.85)',
                }}
              >
                开始融图
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export const BlendRefineNode = memo(BlendRefineNodeComponent);
