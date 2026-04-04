'use client';

import { memo, useState, useCallback, useRef, useEffect } from 'react';
import { type NodeProps, type Node, Handle, Position, useReactFlow, NodeToolbar } from '@xyflow/react';
import type { ImageProcessNodeData, ImageProcessType } from '../../../types/canvas';
import { ViewAngleCanvas } from './ViewAngleCanvas';
import { angleToPrompt, AZIMUTH_PRESETS, ELEVATION_PRESETS, DISTANCE_PRESETS } from '../../../lib/viewAnglePrompt';
import { API_BASE_URL } from '../../../lib/api';

type ImageProcessNode = Node<ImageProcessNodeData, 'imageProcess'>;

/* ── Per-function config ── */
const PROCESS_CONFIG: Record<ImageProcessType, {
  icon: string; label: string; accent: string; accentBg: string;
}> = {
  viewAngle:  { icon: '🔄', label: '多视角', accent: 'rgba(96,165,250,0.9)',  accentBg: 'rgba(96,165,250,0.15)' },
  expression: { icon: '🎭', label: '表情',   accent: 'rgba(251,146,60,0.9)',  accentBg: 'rgba(251,146,60,0.15)' },
  hdUpscale:  { icon: '⬆',  label: '高清',   accent: 'rgba(52,211,153,0.9)',  accentBg: 'rgba(52,211,153,0.15)' },
  matting:    { icon: '✂',  label: '抠图',   accent: 'rgba(244,114,182,0.9)', accentBg: 'rgba(244,114,182,0.15)' },
};

const CAPSULE_ITEMS: ImageProcessType[] = ['viewAngle', 'expression', 'matting', 'hdUpscale'];

/* ── Checkerboard for matting ── */
const CHECKERBOARD_BG: React.CSSProperties = {
  backgroundImage: 'linear-gradient(45deg, #1a1a1a 25%, transparent 25%), linear-gradient(-45deg, #1a1a1a 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1a1a1a 75%), linear-gradient(-45deg, transparent 75%, #1a1a1a 75%)',
  backgroundSize: '14px 14px',
  backgroundPosition: '0 0, 0 7px, 7px -7px, -7px 0',
  backgroundColor: '#111',
};

/* ── Styles ── */
const CARD_WIDTH = 180; // portrait width to match character images
const IMG_HEIGHT = 240; // tall portrait image area

const statusDotBase: React.CSSProperties = {
  position: 'absolute', top: 8, right: 8, width: 8, height: 8,
  borderRadius: '50%', zIndex: 2,
};
const btnBase: React.CSSProperties = {
  border: 'none',
  borderRadius: 8,
  padding: '8px 20px',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: 12,
  letterSpacing: 0.5,
  transition: 'opacity 0.15s',
  width: '100%',
};
const progressBarOuter: React.CSSProperties = {
  height: 3, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 2, marginTop: 8,
};

function ImageProcessNodeComponent({ id, data, selected }: NodeProps<ImageProcessNode>) {
  const [hovered, setHovered] = useState(false);
  const [showToolbar, setShowToolbar] = useState(false);
  const [activePanel, setActivePanel] = useState<ImageProcessType | null>(null);
  const [exprText, setExprText] = useState(data.expressionPrompt || '保持人物一致性，保持视角一致，');
  const [scaleFactor, setScaleFactor] = useState(data.scaleFactor || 2);
  const [localAz, setLocalAz] = useState(data.azimuth ?? 0);
  const [localEl, setLocalEl] = useState(data.elevation ?? 0);
  const [localDist, setLocalDist] = useState(data.distance ?? 5);
  const executingRef = useRef(false);
  const reactFlow = useReactFlow();

  const cfg = PROCESS_CONFIG[data.processType] || PROCESS_CONFIG.viewAngle;
  const isMatting = data.processType === 'matting';
  const outputUrl = isMatting ? (data.outputPngUrl || data.outputImageUrl) : data.outputImageUrl;
  const displayUrl = outputUrl || data.inputImageUrl;

  // Show toolbar when selected OR when panel is open
  const toolbarVisible = selected || showToolbar || activePanel !== null;

  // Close everything only when selected transitions true → false (clicking blank area)
  const prevSelectedRef = useRef(selected);
  useEffect(() => {
    if (prevSelectedRef.current && !selected) {
      setShowToolbar(false);
      setActivePanel(null);
    }
    prevSelectedRef.current = selected;
  }, [selected, showToolbar]);

  /* ── Update node data helper ── */
  const updateNodeData = useCallback((patch: Record<string, unknown>) => {
    const allNodes = reactFlow.getNodes();
    reactFlow.setNodes(allNodes.map(n =>
      n.id === id ? { ...n, data: { ...n.data, ...patch } } : n,
    ));
  }, [id, reactFlow]);

  /* ── ViewAngle angle change ── */
  const handleAngleChange = useCallback((az: number, el: number, dist: number) => {
    setLocalAz(az);
    setLocalEl(el);
    setLocalDist(dist);
  }, []);

  /* ── Capsule button click ── */
  const handleCapsuleClick = useCallback((pt: ImageProcessType) => {
    setActivePanel(prev => prev === pt ? null : pt);
    setShowToolbar(true);
  }, []);

  /* ── Card click → show toolbar (no stopPropagation so React Flow selects the node) ── */
  const handleCardClick = useCallback(() => {
    setShowToolbar(true);
  }, []);

  /* ── Execute node ── */
  const handleExecute = useCallback(async () => {
    if (executingRef.current) return;
    executingRef.current = true;

    const execType = activePanel || data.processType;
    const content: Record<string, unknown> = {
      processType: execType,
      inputStorageKey: data.inputStorageKey,
      inputImageUrl: data.inputImageUrl,
    };

    if (execType === 'viewAngle') {
      content.azimuth = localAz;
      content.elevation = localEl;
      content.distance = localDist;
      content.targetAngle = angleToPrompt(localAz, localEl, localDist);
      updateNodeData({
        processType: execType,
        azimuth: localAz, elevation: localEl, distance: localDist,
        targetAngle: content.targetAngle as string,
        status: 'running', progress: 0,
      });
    } else if (execType === 'expression') {
      content.expressionPrompt = exprText;
      updateNodeData({ processType: execType, expressionPrompt: exprText, status: 'running', progress: 0 });
    } else if (execType === 'matting') {
      updateNodeData({ processType: execType, status: 'running', progress: 0 });
    } else if (execType === 'hdUpscale') {
      content.scaleFactor = scaleFactor;
      updateNodeData({ processType: execType, scaleFactor, status: 'running', progress: 0 });
    }

    try {
      const endpoint = `${API_BASE_URL}/api/canvas/nodes/${id}/execute`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_type: 'imageProcess', content }),
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
                  updateNodeData({
                    status: 'success', progress: 100,
                    ...(event.outputImageUrl ? { outputImageUrl: event.outputImageUrl } : {}),
                    ...(event.outputStorageKey ? { outputStorageKey: event.outputStorageKey } : {}),
                    ...(event.outputPngUrl ? { outputPngUrl: event.outputPngUrl } : {}),
                  });
                }
              } catch { /* ignore */ }
            }
          }
        }
      } else {
        const result = await response.json();
        const output = result.result || {};
        // Build display URL: prefer explicit outputImageUrl, then base64, then construct from storageKey
        let outUrl = output.outputImageUrl || (output.outputImageBase64
          ? `data:image/png;base64,${output.outputImageBase64}` : undefined);
        if (!outUrl && output.outputStorageKey) {
          outUrl = `${API_BASE_URL}/uploads/${output.outputStorageKey}`;
        }
        const outPng = output.outputPngUrl || (output.outputStorageKey?.endsWith('.png')
          ? `${API_BASE_URL}/uploads/${output.outputStorageKey}` : undefined);
        updateNodeData({
          status: 'success', progress: 100,
          ...(outUrl ? { outputImageUrl: outUrl } : {}),
          ...(output.outputStorageKey ? { outputStorageKey: output.outputStorageKey } : {}),
          ...(outPng ? { outputPngUrl: outPng } : {}),
          ...(output.runninghubTaskId ? { runninghubTaskId: output.runninghubTaskId } : {}),
        });
      }
    } catch (err) {
      updateNodeData({
        status: 'error',
        errorMessage: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      executingRef.current = false;
    }
  }, [id, data, activePanel, localAz, localEl, localDist, exprText, scaleFactor, updateNodeData]);

  const isRunning = data.status === 'running';
  const borderColor = selected
    ? cfg.accent.replace('0.9', '0.4')
    : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ width: CARD_WIDTH, position: 'relative' }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '50%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '50%' }} />

      {/* ── Capsule toolbar via NodeToolbar (renders in portal, never clipped) ── */}
      <NodeToolbar isVisible={toolbarVisible} position={Position.Top} offset={8}>
        <div
          className="nopan nodrag nowheel"
          style={{
            display: 'flex',
            gap: 0,
            background: 'rgba(20,22,28,0.95)',
            backdropFilter: 'blur(12px)',
            borderRadius: 22,
            padding: '3px 4px',
            border: '1px solid rgba(255,255,255,0.08)',
            whiteSpace: 'nowrap' as const,
          }}
        >
          {CAPSULE_ITEMS.map(pt => {
            const c = PROCESS_CONFIG[pt];
            const isActive = activePanel === pt;
            return (
              <button
                key={pt}
                onClick={(e) => { e.stopPropagation(); handleCapsuleClick(pt); }}
                style={{
                  border: 'none',
                  background: isActive ? 'rgba(255,255,255,0.08)' : 'transparent',
                  borderRadius: 18,
                  padding: '5px 12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'background 0.15s',
                }}
              >
                <span style={{ fontSize: 12 }}>{c.icon}</span>
                <span style={{
                  fontSize: 10,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? c.accent : 'rgba(255,255,255,0.4)',
                }}>{c.label}</span>
              </button>
            );
          })}
        </div>
      </NodeToolbar>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, paddingLeft: 4 }}>
        <span style={{ fontSize: 13 }}>{cfg.icon}</span>
        <span style={{ fontSize: 12, fontWeight: 500, color: cfg.accent, letterSpacing: 0.5 }}>{cfg.label}</span>
      </div>

      {/* ── Card body (portrait) ── */}
      <div
        onClick={handleCardClick}
        style={{
          borderRadius: 14, position: 'relative', overflow: 'hidden',
          border: `1px solid ${borderColor}`, transition: 'border-color 0.2s',
          background: 'rgba(12,14,18,0.9)',
          cursor: 'pointer',
        }}
      >
        {/* Portrait image area */}
        <div style={{
          width: '100%', height: IMG_HEIGHT,
          ...(isMatting ? CHECKERBOARD_BG : { backgroundColor: '#0c0e12' }),
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {displayUrl ? (
            <img
              src={displayUrl}
              alt={cfg.label}
              style={{
                width: '100%', height: '100%',
                objectFit: isMatting ? 'contain' : 'cover',
                opacity: outputUrl ? 1 : 0.5,
              }}
            />
          ) : (
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>{cfg.icon}</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>等待输入</span>
            </div>
          )}
        </div>

        {/* Bottom overlay badges */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'linear-gradient(transparent, rgba(0,0,0,0.7))',
          padding: '16px 8px 6px',
          display: 'flex', alignItems: 'center', gap: 3, flexWrap: 'wrap',
        }}>
          {data.processType === 'viewAngle' && data.targetAngle && (
            <span style={{ fontSize: 8, padding: '2px 5px', borderRadius: 4, backgroundColor: PROCESS_CONFIG.viewAngle.accentBg, color: PROCESS_CONFIG.viewAngle.accent }}>
              {data.targetAngle.replace('<sks> ', '')}
            </span>
          )}
          {data.processType === 'expression' && data.expressionPrompt && (
            <span style={{ fontSize: 8, padding: '2px 5px', borderRadius: 4, backgroundColor: PROCESS_CONFIG.expression.accentBg, color: PROCESS_CONFIG.expression.accent, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.expressionPrompt}
            </span>
          )}
          {data.processType === 'hdUpscale' && (
            <span style={{ fontSize: 8, padding: '2px 5px', borderRadius: 4, backgroundColor: PROCESS_CONFIG.hdUpscale.accentBg, color: PROCESS_CONFIG.hdUpscale.accent }}>
              {data.scaleFactor || 2}x
            </span>
          )}
          {data.processType === 'matting' && data.outputPngUrl && (
            <span style={{ fontSize: 8, padding: '2px 5px', borderRadius: 4, backgroundColor: PROCESS_CONFIG.matting.accentBg, color: PROCESS_CONFIG.matting.accent }}>PNG</span>
          )}
          {outputUrl && (
            <span style={{ fontSize: 8, padding: '2px 5px', borderRadius: 4, backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)' }}>完成</span>
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

        {/* Progress bar */}
        {isRunning && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
            <div style={{ height: '100%', backgroundColor: cfg.accent.replace('0.9', '0.6'), width: `${data.progress ?? 0}%`, transition: 'width 0.3s' }} />
          </div>
        )}
      </div>

      {/* ── Floating panel via NodeToolbar bottom (renders in portal) ── */}
      <NodeToolbar isVisible={activePanel !== null} position={Position.Bottom} offset={8}>
        <div
          className="nopan nodrag nowheel"
          style={{
            background: 'rgba(20,22,28,0.95)',
            backdropFilter: 'blur(12px)',
            borderRadius: 16,
            border: '1px solid rgba(255,255,255,0.08)',
            padding: 16,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            position: 'relative',
          }}
        >
          {/* Close button */}
          <button
            onClick={(e) => { e.stopPropagation(); setActivePanel(null); setShowToolbar(false); }}
            style={{
              position: 'absolute', top: 8, right: 8, border: 'none',
              background: 'rgba(255,255,255,0.06)', borderRadius: '50%',
              width: 22, height: 22, cursor: 'pointer',
              color: 'rgba(255,255,255,0.4)', fontSize: 11,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >×</button>

          {/* ── ViewAngle Panel ── */}
          {activePanel === 'viewAngle' && (
            <div style={{ display: 'flex', gap: 16, minWidth: 440 }}>
              <div style={{ flexShrink: 0 }}>
                <ViewAngleCanvas
                  width={200}
                  height={220}
                  azimuth={localAz}
                  elevation={localEl}
                  distance={localDist}
                  previewImageUrl={data.inputImageUrl}
                  onChange={handleAngleChange}
                />
                <div style={{ display: 'flex', justifyContent: 'center', marginTop: 4 }}>
                  <button
                    onClick={(e) => { e.stopPropagation(); setLocalAz(0); setLocalEl(0); setLocalDist(5); }}
                    style={{
                      border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
                      background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.5)',
                      fontSize: 10, padding: '3px 10px', cursor: 'pointer',
                    }}
                  >重置</button>
                </div>
              </div>

              <div style={{ flex: 1, minWidth: 170 }}>
                {/* Azimuth presets */}
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 5 }}>方位角 (H)</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                    {AZIMUTH_PRESETS.map(p => (
                      <button key={p.value} onClick={(e) => { e.stopPropagation(); setLocalAz(p.value); }}
                        style={{
                          border: localAz === p.value ? '1px solid rgba(96,165,250,0.5)' : '1px solid rgba(255,255,255,0.08)',
                          borderRadius: 5, padding: '2px 7px', fontSize: 9,
                          background: localAz === p.value ? 'rgba(96,165,250,0.15)' : 'rgba(255,255,255,0.04)',
                          color: localAz === p.value ? 'rgba(96,165,250,0.9)' : 'rgba(255,255,255,0.5)',
                          cursor: 'pointer',
                        }}
                      >{p.label}</button>
                    ))}
                  </div>
                </div>

                {/* Elevation presets */}
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 5 }}>俯仰角 (V)</div>
                  <div style={{ display: 'flex', gap: 3 }}>
                    {ELEVATION_PRESETS.map(p => (
                      <button key={p.value} onClick={(e) => { e.stopPropagation(); setLocalEl(p.value); }}
                        style={{
                          border: localEl === p.value ? '1px solid rgba(80,220,220,0.5)' : '1px solid rgba(255,255,255,0.08)',
                          borderRadius: 5, padding: '2px 7px', fontSize: 9,
                          background: localEl === p.value ? 'rgba(80,220,220,0.15)' : 'rgba(255,255,255,0.04)',
                          color: localEl === p.value ? 'rgba(80,220,220,0.9)' : 'rgba(255,255,255,0.5)',
                          cursor: 'pointer',
                        }}
                      >{p.label}</button>
                    ))}
                  </div>
                </div>

                {/* Distance presets */}
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 5 }}>距离 (Z)</div>
                  <div style={{ display: 'flex', gap: 3 }}>
                    {DISTANCE_PRESETS.map(p => (
                      <button key={p.value} onClick={(e) => { e.stopPropagation(); setLocalDist(p.value); }}
                        style={{
                          border: Math.abs(localDist - p.value) < 0.5 ? '1px solid rgba(240,200,80,0.5)' : '1px solid rgba(255,255,255,0.08)',
                          borderRadius: 5, padding: '2px 7px', fontSize: 9,
                          background: Math.abs(localDist - p.value) < 0.5 ? 'rgba(240,200,80,0.15)' : 'rgba(255,255,255,0.04)',
                          color: Math.abs(localDist - p.value) < 0.5 ? 'rgba(240,200,80,0.9)' : 'rgba(255,255,255,0.5)',
                          cursor: 'pointer',
                        }}
                      >{p.label}</button>
                    ))}
                  </div>
                </div>

                {/* Prompt preview */}
                <div style={{
                  fontSize: 9, color: 'rgba(255,255,255,0.4)',
                  padding: '5px 7px', borderRadius: 5,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  marginBottom: 10, wordBreak: 'break-all',
                }}>
                  {angleToPrompt(localAz, localEl, localDist)}
                </div>

                {/* Generate button */}
                <button
                  onClick={(e) => { e.stopPropagation(); handleExecute(); }}
                  disabled={isRunning || !data.inputImageUrl}
                  style={{
                    ...btnBase,
                    background: 'rgba(96,165,250,0.8)',
                    color: '#fff',
                    opacity: isRunning || !data.inputImageUrl ? 0.4 : 1,
                  }}
                >
                  {isRunning ? '生成中...' : '生成视角转换'}
                </button>
                {isRunning && (
                  <div style={progressBarOuter}>
                    <div style={{ height: '100%', backgroundColor: 'rgba(96,165,250,0.6)', borderRadius: 2, width: `${data.progress ?? 0}%`, transition: 'width 0.3s' }} />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Expression Panel ── */}
          {activePanel === 'expression' && (
            <div style={{ width: 260 }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>描述表情/动作变化</div>
              <textarea
                className="nopan nodrag nowheel"
                value={exprText}
                onChange={(e) => setExprText(e.target.value)}
                placeholder="保持人物一致性，保持视角一致，微笑..."
                style={{
                  width: '100%', height: 64, resize: 'vertical',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8, padding: 8,
                  color: 'rgba(255,255,255,0.8)', fontSize: 11,
                  outline: 'none', boxSizing: 'border-box',
                }}
                onClick={(e) => e.stopPropagation()}
              />
              <div style={{ fontSize: 8, color: 'rgba(255,255,255,0.3)', marginTop: 4, marginBottom: 10 }}>
                模型: gemini-3-pro-image-preview
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleExecute(); }}
                disabled={isRunning || !data.inputImageUrl}
                style={{
                  ...btnBase,
                  background: 'rgba(251,146,60,0.8)',
                  color: '#fff',
                  opacity: isRunning || !data.inputImageUrl ? 0.4 : 1,
                }}
              >
                {isRunning ? '生成中...' : '生成表情'}
              </button>
              {isRunning && (
                <div style={progressBarOuter}>
                  <div style={{ height: '100%', backgroundColor: 'rgba(251,146,60,0.6)', borderRadius: 2, width: `${data.progress ?? 0}%`, transition: 'width 0.3s' }} />
                </div>
              )}
            </div>
          )}

          {/* ── Matting Panel ── */}
          {activePanel === 'matting' && (
            <div style={{ width: 240 }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 6 }}>AI 智能抠图</div>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 14 }}>
                使用 RunningHub 去除背景，输出 PNG 透明通道图片
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleExecute(); }}
                disabled={isRunning || !data.inputImageUrl}
                style={{
                  ...btnBase,
                  background: 'rgba(244,114,182,0.8)',
                  color: '#fff',
                  opacity: isRunning || !data.inputImageUrl ? 0.4 : 1,
                }}
              >
                {isRunning ? '抠图中...' : 'AI 抠图'}
              </button>
              {isRunning && (
                <div style={progressBarOuter}>
                  <div style={{ height: '100%', backgroundColor: 'rgba(244,114,182,0.6)', borderRadius: 2, width: `${data.progress ?? 0}%`, transition: 'width 0.3s' }} />
                </div>
              )}
            </div>
          )}

          {/* ── HDUpscale Panel ── */}
          {activePanel === 'hdUpscale' && (
            <div style={{ width: 240 }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>放大倍率</div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                {[2, 4].map(f => (
                  <button
                    key={f}
                    onClick={(e) => { e.stopPropagation(); setScaleFactor(f); }}
                    style={{
                      flex: 1,
                      border: scaleFactor === f ? '1px solid rgba(52,211,153,0.5)' : '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 8, padding: '8px 0', fontSize: 13, fontWeight: 600,
                      background: scaleFactor === f ? 'rgba(52,211,153,0.15)' : 'rgba(255,255,255,0.04)',
                      color: scaleFactor === f ? 'rgba(52,211,153,0.9)' : 'rgba(255,255,255,0.5)',
                      cursor: 'pointer',
                    }}
                  >{f}x</button>
                ))}
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleExecute(); }}
                disabled={isRunning || !data.inputImageUrl}
                style={{
                  ...btnBase,
                  background: 'rgba(52,211,153,0.8)',
                  color: '#fff',
                  opacity: isRunning || !data.inputImageUrl ? 0.4 : 1,
                }}
              >
                {isRunning ? '处理中...' : '高清化'}
              </button>
              {isRunning && (
                <div style={progressBarOuter}>
                  <div style={{ height: '100%', backgroundColor: 'rgba(52,211,153,0.6)', borderRadius: 2, width: `${data.progress ?? 0}%`, transition: 'width 0.3s' }} />
                </div>
              )}
            </div>
          )}
        </div>
      </NodeToolbar>
    </div>
  );
}

export const ImageProcessNode = memo(ImageProcessNodeComponent);
