'use client';
import { memo, useState, useCallback } from 'react';
import { type NodeProps, type Node, Handle, Position, useReactFlow } from '@xyflow/react';
import type { FinalHDNodeData } from '../../../types/canvas';
import { API_BASE_URL } from '../../../lib/api';
import { useCanvasStore } from '../../../stores/canvasStore';

type FinalHDNode = Node<FinalHDNodeData, 'finalHD'>;

const ACCENT = 'rgba(52,211,153,0.9)';
const ACCENT_DIM = 'rgba(52,211,153,0.5)';
const ACCENT_BG = 'rgba(52,211,153,0.06)';

function FinalHDNodeComponent({ id, data, selected }: NodeProps<FinalHDNode>) {
  const [hovered, setHovered] = useState(false);
  const [scaleFactor, setScaleFactor] = useState(data.scaleFactor || 2);
  const reactFlow = useReactFlow();

  const isRunning = data.status === 'running' || data.status === 'queued';
  const isSuccess = data.status === 'success';
  const hasInput = !!data.inputImageUrl;
  const displayUrl = data.outputImageUrl || data.inputImageUrl;

  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected
    ? 'rgba(255,255,255,0.16)'
    : hovered
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(255,255,255,0.06)';

  /* ── Update node data + propagate to downstream ── */
  const updateNodeData = useCallback((patch: Record<string, unknown>) => {
    const s = useCanvasStore.getState();
    s.setNodes(s.nodes.map(n =>
      n.id === id ? { ...n, data: { ...n.data, ...patch } } : n,
    ));
  }, [id]);

  const updateAndPropagate = useCallback((
    patch: Record<string, unknown>,
    outputUrl?: string,
    outputKey?: string,
  ) => {
    const store = useCanvasStore.getState();
    const edges = store.edges;
    const downstream = edges.filter(e => e.source === id);
    const targetIds = new Set(downstream.map(e => e.target));

    const updatedNodes = store.nodes.map(n => {
      if (n.id === id) {
        return { ...n, data: { ...n.data, ...patch } };
      }
      if (targetIds.has(n.id) && (outputUrl || outputKey)) {
        return {
          ...n,
          data: {
            ...n.data,
            inputImageUrl: outputUrl || (n.data as Record<string, unknown>).inputImageUrl,
            inputStorageKey: outputKey || (n.data as Record<string, unknown>).inputStorageKey,
          },
        };
      }
      return n;
    });

    store.setNodes(updatedNodes);
  }, [id, reactFlow]);

  /* ── Execute HD upscale via RunningHub ── */
  const handleExecute = useCallback(async () => {
    if (isRunning || !hasInput) return;

    updateNodeData({ scaleFactor, status: 'running', progress: 0 });

    try {
      const endpoint = `${API_BASE_URL}/api/canvas/nodes/${id}/execute`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_type: 'finalHD',
          content: {
            inputImageUrl: data.inputImageUrl,
            inputStorageKey: data.inputStorageKey,
            scaleFactor,
            imageSize: scaleFactor <= 2 ? '2K' : '4K',
          },
        }),
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        throw new Error(`API error: ${response.status} ${errText}`);
      }

      if (response.headers.get('content-type')?.includes('text/event-stream')) {
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event = JSON.parse(line.slice(6));
                if (event.progress !== undefined) updateNodeData({ progress: event.progress });
                if (event.status === 'completed' || event.status === 'success') {
                  const evtUrl = event.outputImageUrl || (event.outputStorageKey ? `${API_BASE_URL}/uploads/${event.outputStorageKey}` : undefined);
                  updateAndPropagate({
                    status: 'success', progress: 100,
                    ...(evtUrl ? { outputImageUrl: evtUrl } : {}),
                    ...(event.outputStorageKey ? { outputStorageKey: event.outputStorageKey } : {}),
                  }, evtUrl, event.outputStorageKey);
                }
                if (event.status === 'error') {
                  updateNodeData({ status: 'error', errorMessage: event.error || 'Unknown error' });
                }
              } catch { /* ignore parse errors */ }
            }
          }
        }
      } else {
        const result = await response.json();
        const output = result.result || {};
        let outUrl = output.outputImageUrl;
        if (!outUrl && output.outputStorageKey) {
          outUrl = `${API_BASE_URL}/uploads/${output.outputStorageKey}`;
        }
        updateAndPropagate({
          status: 'success', progress: 100,
          ...(outUrl ? { outputImageUrl: outUrl } : {}),
          ...(output.outputStorageKey ? { outputStorageKey: output.outputStorageKey } : {}),
        }, outUrl, output.outputStorageKey);
      }
    } catch (err) {
      updateNodeData({ status: 'error', errorMessage: String(err) });
    }
  }, [id, data.inputImageUrl, data.inputStorageKey, scaleFactor, isRunning, hasInput, updateNodeData, updateAndPropagate]);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative"
      style={{ width: 240 }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* Header */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span style={{ fontSize: 13 }}>⬆</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: selected ? ACCENT : ACCENT_DIM }}>
          终稿高清
        </span>
        {/* Status dot */}
        {isSuccess && (
          <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#34d399', marginLeft: 'auto' }} />
        )}
        {data.status === 'error' && (
          <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#f87171', marginLeft: 'auto' }} />
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
        <div style={{ position: 'relative', zIndex: 1, padding: 16 }}>
          {/* Scale factor badge */}
          <div style={{ marginBottom: 12 }}>
            <span
              style={{
                fontSize: 9,
                color: ACCENT_DIM,
                backgroundColor: ACCENT_BG,
                padding: '2px 10px',
                borderRadius: 99,
              }}
            >
              {scaleFactor}x 放大
            </span>
          </div>

          {/* Image preview */}
          <div
            style={{
              width: '100%',
              aspectRatio: '16 / 9',
              borderRadius: 10,
              backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 12,
            }}
          >
            {displayUrl ? (
              <img
                src={displayUrl}
                alt="终稿高清"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.18)' }}>等待上游图片...</span>
            )}
          </div>

          {/* Scale factor buttons */}
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 6 }}>放大倍率</div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
            {[2, 4].map(f => (
              <button
                key={f}
                onClick={(e) => { e.stopPropagation(); setScaleFactor(f); }}
                style={{
                  flex: 1,
                  border: scaleFactor === f ? '1px solid rgba(52,211,153,0.5)' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8, padding: '6px 0', fontSize: 13, fontWeight: 600,
                  background: scaleFactor === f ? 'rgba(52,211,153,0.15)' : 'rgba(255,255,255,0.04)',
                  color: scaleFactor === f ? ACCENT : 'rgba(255,255,255,0.5)',
                  cursor: 'pointer',
                }}
              >{f}x</button>
            ))}
          </div>

          {/* Execute button */}
          <button
            onClick={(e) => { e.stopPropagation(); handleExecute(); }}
            disabled={isRunning || !hasInput}
            style={{
              width: '100%',
              border: 'none',
              borderRadius: 8, padding: '8px 0', fontSize: 12, fontWeight: 600,
              background: ACCENT,
              color: '#fff',
              cursor: isRunning || !hasInput ? 'not-allowed' : 'pointer',
              opacity: isRunning || !hasInput ? 0.4 : 1,
              transition: 'opacity 0.2s',
            }}
          >
            {isRunning ? '处理中...' : '高清化'}
          </button>

          {/* Progress bar */}
          {isRunning && (
            <div style={{
              marginTop: 8,
              width: '100%', height: 4, borderRadius: 2,
              backgroundColor: 'rgba(255,255,255,0.06)',
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                backgroundColor: 'rgba(52,211,153,0.6)',
                borderRadius: 2,
                width: `${data.progress ?? 0}%`,
                transition: 'width 0.3s',
              }} />
            </div>
          )}

          {/* Error message */}
          {data.status === 'error' && data.errorMessage && (
            <div style={{ marginTop: 6, fontSize: 10, color: '#f87171', lineHeight: 1.3 }}>
              {data.errorMessage}
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

export const FinalHDNode = memo(FinalHDNodeComponent);
