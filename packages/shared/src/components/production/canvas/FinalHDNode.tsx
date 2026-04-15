/**
 * FinalHDNode — HD upscale card (Tapnow style).
 *
 * Card: ExpressionNode-style display shell.
 * Click: opens floating panel with 2x/4x selector + execute button.
 */

'use client';

import { memo, useState, useCallback, useEffect, useRef } from 'react';
import { type NodeProps, type Node, Handle, Position, useReactFlow } from '@xyflow/react';
import type { FinalHDNodeData } from '../../../types/canvas';
import { API_BASE_URL } from '../../../lib/api';
import { useCanvasStore } from '../../../stores/canvasStore';
import {
  getFinalHDDisplayUrl,
  buildFinalHDBadges,
} from '../../../lib/cardDisplayHelpers';

type FinalHDNode = Node<FinalHDNodeData, 'finalHD'>;

function FinalHDNodeComponent({ id, data, selected }: NodeProps<FinalHDNode>) {
  const [hovered, setHovered] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [scaleFactor, setScaleFactor] = useState(data.scaleFactor || 2);
  const reactFlow = useReactFlow();

  // Close panel when deselected (clicking blank area)
  const prevSelectedRef = useRef(selected);
  useEffect(() => {
    if (prevSelectedRef.current && !selected) {
      setPanelOpen(false);
    }
    prevSelectedRef.current = selected;
  }, [selected]);

  const isRunning = data.status === 'running' || data.status === 'queued';
  const hasInput = !!data.inputImageUrl;
  const displayUrl = getFinalHDDisplayUrl(data);
  const badges = buildFinalHDBadges({ scaleFactor, outputImageUrl: data.outputImageUrl });

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(52,211,153,0.9)' : 'rgba(52,211,153,0.5)';

  /* ── Card click → open panel + center viewport ── */
  const handleCardClick = useCallback(() => {
    setPanelOpen(prev => !prev);
    const node = reactFlow.getNode(id);
    if (!node) return;
    const CARD_W = 300;
    const HEADER_H = 31;
    const CARD_BODY_H = Math.round(CARD_W * 9 / 16) + 28;
    const PANEL_H = 240;
    const totalH = HEADER_H + CARD_BODY_H + PANEL_H;
    const centerX = node.position.x + CARD_W / 2;
    const centerY = node.position.y + totalH / 2;
    const vpEl = document.querySelector('.react-flow') as HTMLElement | null;
    const vpH = vpEl?.clientHeight || 800;
    const vpW = vpEl?.clientWidth || 1200;
    const targetZoom = Math.min(vpH / (totalH * 1.15), vpW / (CARD_W * 1.3), 1.5);
    reactFlow.setCenter(centerX, centerY, { zoom: Math.max(targetZoom, 0.5), duration: 400 });
  }, [id, reactFlow]);

  /* ── Update node data + propagate to downstream ── */
  const updateNodeData = useCallback((patch: Record<string, unknown>) => {
    const s = useCanvasStore.getState();
    s.setNodes(s.nodes.map(n => n.id === id ? { ...n, data: { ...n.data, ...patch } } : n));
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
      if (n.id === id) return { ...n, data: { ...n.data, ...patch } };
      if (targetIds.has(n.id) && (outputUrl || outputKey)) {
        return { ...n, data: { ...n.data, inputImageUrl: outputUrl || (n.data as Record<string, unknown>).inputImageUrl, inputStorageKey: outputKey || (n.data as Record<string, unknown>).inputStorageKey } };
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
          content: { inputImageUrl: data.inputImageUrl, inputStorageKey: data.inputStorageKey, scaleFactor, imageSize: scaleFactor <= 2 ? '2K' : '4K' },
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
                  setPanelOpen(false);
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
        if (!outUrl && output.outputStorageKey) outUrl = `${API_BASE_URL}/uploads/${output.outputStorageKey}`;
        updateAndPropagate({
          status: 'success', progress: 100,
          ...(outUrl ? { outputImageUrl: outUrl } : {}),
          ...(output.outputStorageKey ? { outputStorageKey: output.outputStorageKey } : {}),
        }, outUrl, output.outputStorageKey);
        setPanelOpen(false);
      }
    } catch (err) {
      updateNodeData({ status: 'error', errorMessage: String(err) });
    }
  }, [id, data.inputImageUrl, data.inputStorageKey, scaleFactor, isRunning, hasInput, updateNodeData, updateAndPropagate]);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ width: 300, position: 'relative' }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* Title bar */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">⬆</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>终稿高清</span>
      </div>

      {/* Main card */}
      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
        cursor: 'pointer',
      }} onClick={handleCardClick}>
        {/* Image area */}
        <div style={{
          width: '100%', minHeight: 100,
          backgroundColor: '#0c0e12',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {displayUrl ? (
            <img src={displayUrl} alt="终稿高清" style={{ width: '100%', height: 'auto', display: 'block' }} />
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>⬆</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>等待上游图片</span>
            </div>
          )}
        </div>

        {/* Gradient overlay */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'linear-gradient(transparent, rgba(0,0,0,0.75))',
          padding: '24px 12px 10px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
            {badges.map((b, i) => (
              <span key={i} style={{
                fontSize: 9, padding: '2px 6px', borderRadius: 4,
                backgroundColor: b.bgColor, color: b.textColor,
              }}>{b.text}</span>
            ))}
          </div>
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

        {/* Progress bar */}
        {isRunning && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
            <div style={{ height: '100%', backgroundColor: 'rgba(52,211,153,0.6)', width: `${data.progress ?? 0}%`, transition: 'width 0.3s' }} />
          </div>
        )}
      </div>

      {/* ── Floating panel ── */}
      {panelOpen && (
        <div style={{
          position: 'absolute', top: '100%', left: '50%',
          transform: 'translateX(-50%)', zIndex: 50,
        }}>
          <div
            className="nopan nodrag nowheel"
            style={{
              width: 280,
              background: 'rgba(20,22,28,0.95)',
              backdropFilter: 'blur(12px)',
              borderRadius: 16,
              border: '1px solid rgba(255,255,255,0.08)',
              padding: 16,
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              position: 'relative',
            }}
          >
            {/* Close */}
            <button
              onClick={(e) => { e.stopPropagation(); setPanelOpen(false); }}
              style={{
                position: 'absolute', top: 8, right: 8, border: 'none',
                background: 'rgba(255,255,255,0.06)', borderRadius: '50%',
                width: 22, height: 22, cursor: 'pointer',
                color: 'rgba(255,255,255,0.4)', fontSize: 11,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >×</button>

            {/* Scale factor selector */}
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 6 }}>放大倍率</div>
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              {[2, 4].map(f => (
                <button
                  key={f}
                  onClick={(e) => { e.stopPropagation(); setScaleFactor(f); }}
                  style={{
                    flex: 1,
                    border: scaleFactor === f ? '1px solid rgba(52,211,153,0.5)' : '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 8, padding: '8px 0', fontSize: 14, fontWeight: 600,
                    background: scaleFactor === f ? 'rgba(52,211,153,0.15)' : 'rgba(255,255,255,0.04)',
                    color: scaleFactor === f ? 'rgba(52,211,153,0.9)' : 'rgba(255,255,255,0.5)',
                    cursor: 'pointer',
                  }}
                >{f}x</button>
              ))}
            </div>

            {/* Progress */}
            {isRunning && (
              <div style={{
                marginBottom: 10, width: '100%', height: 4, borderRadius: 2,
                backgroundColor: 'rgba(255,255,255,0.06)', overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%', backgroundColor: 'rgba(52,211,153,0.6)', borderRadius: 2,
                  width: `${data.progress ?? 0}%`, transition: 'width 0.3s',
                }} />
              </div>
            )}

            {/* Error */}
            {data.status === 'error' && data.errorMessage && (
              <div style={{
                marginBottom: 8, padding: '6px 10px', borderRadius: 8,
                background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)',
                fontSize: 11, color: 'rgba(248,113,113,0.8)', wordBreak: 'break-all',
              }}>{data.errorMessage}</div>
            )}

            {/* Execute button */}
            <button
              onClick={(e) => { e.stopPropagation(); handleExecute(); }}
              disabled={isRunning || !hasInput}
              style={{
                width: '100%', border: 'none', borderRadius: 8,
                padding: '8px 0', fontSize: 12, fontWeight: 600,
                background: isRunning
                  ? 'rgba(255,255,255,0.06)'
                  : 'rgba(52,211,153,0.9)',
                color: '#fff',
                cursor: isRunning || !hasInput ? 'not-allowed' : 'pointer',
                opacity: isRunning || !hasInput ? 0.4 : 1,
                transition: 'opacity 0.2s',
              }}
            >
              {isRunning ? '处理中...' : '高清化'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export const FinalHDNode = memo(FinalHDNodeComponent);
