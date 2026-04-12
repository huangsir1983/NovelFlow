'use client';
import { memo, useState, useCallback, useMemo } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { BlendRefineNodeData } from '../../../types/canvas';
import { useNodeExecution } from '../../../hooks/useNodeExecution';
import { useCanvasStore } from '../../../stores/canvasStore';

type BlendRefineNode = Node<BlendRefineNodeData, 'blendRefine'>;

function BlendRefineNodeComponent({ id, data, selected }: NodeProps<BlendRefineNode>) {
  const [hovered, setHovered] = useState(false);
  const { runNode, propagateOutput } = useNodeExecution();

  // Dynamically collect input from upstream composite node
  const edges = useCanvasStore(s => s.edges);
  const allNodes = useCanvasStore(s => s.nodes);
  const upstreamImage = useMemo(() => {
    const incoming = edges.filter(e => e.target === id);
    for (const edge of incoming) {
      const src = allNodes.find(n => n.id === edge.source);
      const d = src?.data as Record<string, unknown> | undefined;
      if (!d) continue;
      // Only use outputImageUrl — do NOT fallback to inputImageUrl
      // (composite's inputImageUrl may be a matting result, not the actual composite output)
      const url = d.outputImageUrl as string | undefined;
      const storageKey = d.outputStorageKey as string | undefined;
      if (url || storageKey) return { url, storageKey };
    }
    return null;
  }, [edges, allNodes, id]);

  const inputUrl = data.inputImageUrl || upstreamImage?.url;
  const inputKey = data.inputStorageKey || upstreamImage?.storageKey;

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
  const hasInput = !!inputUrl;
  const isError = data.status === 'error';

  const handleRun = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    // Ensure inputImageUrl/inputStorageKey are set from upstream before running
    if (upstreamImage && (!data.inputImageUrl || !data.inputStorageKey)) {
      const nodes = useCanvasStore.getState().nodes;
      useCanvasStore.getState().setNodes(
        nodes.map(n =>
          n.id === id
            ? { ...n, data: { ...n.data, inputImageUrl: upstreamImage.url, inputStorageKey: upstreamImage.storageKey } }
            : n,
        ),
      );
    }
    runNode(id);
  }, [runNode, id, upstreamImage, data.inputImageUrl, data.inputStorageKey]);

  const handleConfirm = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    const previewUrl = data.previewImageUrl;
    const storageKey = data.outputStorageKey;
    if (!previewUrl) return;

    const nodes = useCanvasStore.getState().nodes;
    useCanvasStore.getState().setNodes(
      nodes.map(n =>
        n.id === id
          ? { ...n, data: { ...n.data, outputImageUrl: previewUrl, confirmed: true } }
          : n,
      ),
    );
    propagateOutput(id, previewUrl, storageKey);
  }, [id, data.previewImageUrl, data.outputStorageKey, propagateOutput]);

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
                src={inputUrl}
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

          {/* Error message */}
          {isError && (
            <div style={{ marginTop: 6 }}>
              <div style={{ fontSize: 10, color: '#f87171', textAlign: 'center' }}>
                {data.errorMessage || '融图失败'}
              </div>
            </div>
          )}

          {/* Show run button when not running and no preview pending */}
          {!isRunning && !hasPreview && !isConfirmed && (
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
                {isError ? '重试融图' : '开始融图'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export const BlendRefineNode = memo(BlendRefineNodeComponent);
