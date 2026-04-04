'use client';

import { memo, useState, useCallback, useRef, useEffect } from 'react';
import { type NodeProps, type Node, Handle, Position, useReactFlow, NodeToolbar } from '@xyflow/react';
import type { ImageProcessNodeData, ImageProcessType } from '../../../types/canvas';
import { ViewAngleCanvas } from './ViewAngleCanvas';
import { angleToPrompt, AZIMUTH_PRESETS, ELEVATION_PRESETS, DISTANCE_PRESETS } from '../../../lib/viewAnglePrompt';
import { API_BASE_URL } from '../../../lib/api';
import { useCanvasStore } from '../../../stores/canvasStore';

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
const CARD_WIDTH_LANDSCAPE = 260; // landscape width for scene background hdUpscale
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

  // Sync local angle state when node data is restored from backend
  useEffect(() => {
    if (data.azimuth !== undefined && data.azimuth !== localAz) setLocalAz(data.azimuth);
    if (data.elevation !== undefined && data.elevation !== localEl) setLocalEl(data.elevation);
    if (data.distance !== undefined && data.distance !== localDist) setLocalDist(data.distance);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.azimuth, data.elevation, data.distance]);

  const cfg = PROCESS_CONFIG[data.processType] || PROCESS_CONFIG.viewAngle;
  const isMatting = data.processType === 'matting';
  const isLandscape = data.processType === 'hdUpscale' && id.endsWith('-bg');
  const cardWidth = isLandscape ? CARD_WIDTH_LANDSCAPE : CARD_WIDTH;
  const imgHeight = isLandscape ? Math.round(CARD_WIDTH_LANDSCAPE * 9 / 16) : IMG_HEIGHT;
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

  /* ── Update node data + optionally propagate to downstream ── */
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

    let updatedNodes = store.nodes.map(n => {
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

    // Upsert this node's layer into downstream composite nodes
    for (const targetId of targetIds) {
      const targetNode = updatedNodes.find(n => n.id === targetId);
      if (!targetNode || (targetNode.data as Record<string, unknown>).nodeType !== 'composite') continue;

      const compData = targetNode.data as Record<string, unknown>;
      const existingLayers = ((compData.layers || []) as Array<Record<string, unknown>>).slice();

      // Determine layer type for this source node
      const myData = updatedNodes.find(n => n.id === id)?.data as Record<string, unknown> | undefined;
      const processType = (myData?.processType || '') as string;
      const isBgUpscale = processType === 'hdUpscale'
        && edges.some(e => e.target === id && e.source.startsWith('scenebg-'));
      const layerType = isBgUpscale ? 'background' : 'character';
      const imgUrl = outputUrl || (myData?.outputPngUrl || myData?.outputImageUrl) as string | undefined;

      if (!imgUrl) continue;

      const layerIdx = existingLayers.findIndex(l => l.sourceNodeId === id);
      const newLayer = {
        id,
        type: layerType,
        sourceNodeId: id,
        imageUrl: imgUrl,
        x: layerType === 'background' ? 0 : (1920 - 600) / 2,
        y: 0,
        width: layerType === 'background' ? 1920 : 600,
        height: 1080,
        rotation: 0,
        zIndex: layerType === 'background' ? 0 : existingLayers.length,
        opacity: 1, visible: true, flipX: false,
      };

      if (layerIdx >= 0) {
        // Update only imageUrl, keep user adjustments
        existingLayers[layerIdx] = { ...existingLayers[layerIdx], imageUrl: imgUrl };
      } else {
        existingLayers.push(newLayer);
      }

      updatedNodes = updatedNodes.map(n =>
        n.id === targetId ? { ...n, data: { ...n.data, layers: existingLayers, outputImageUrl: undefined } } : n,
      );

      // Persist updated composite layers to backend
      useCanvasStore.getState().persistCompositeLayers(targetId, existingLayers);
    }

    useCanvasStore.getState().setNodes(updatedNodes);
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

  /* ── Card click → show toolbar + auto-open panel + animate viewport ── */
  const handleCardClick = useCallback(() => {
    setShowToolbar(true);
    if (activePanel === null && data.status !== 'running') {
      setActivePanel(data.processType || 'viewAngle');
    }

    // Animate viewport: pan card to center + zoom so bottom panel is visible
    const node = reactFlow.getNode(id);
    if (!node) return;
    const HEADER_H = 31; // header icon+label + margin
    const CARD_BODY_H = imgHeight + 28; // image + bottom overlay + border
    const PANEL_H = 300; // max panel height (viewAngle is tallest)
    const PANEL_OFFSET = 0;
    const totalH = HEADER_H + CARD_BODY_H + PANEL_OFFSET + PANEL_H;
    // Center point: midpoint of card top to panel bottom
    const centerX = node.position.x + cardWidth / 2;
    const centerY = node.position.y + totalH / 2;
    // Target zoom: fit totalH + padding in viewport
    const vpEl = document.querySelector('.react-flow') as HTMLElement | null;
    const vpH = vpEl?.clientHeight || 800;
    const vpW = vpEl?.clientWidth || 1200;
    const zoomH = vpH / (totalH * 1.15);
    const zoomW = vpW / (Math.max(cardWidth, 460) * 1.3); // 460 = viewAngle panel width
    const targetZoom = Math.min(zoomH, zoomW, 1.5); // cap at 1.5x
    reactFlow.setCenter(centerX, centerY, { zoom: Math.max(targetZoom, 0.5), duration: 400 });
  }, [activePanel, data.status, data.processType, id, reactFlow]);

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


    // Reset all downstream nodes' green dots before execution starts
    useCanvasStore.getState().resetDownstreamNodes(id);

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
      content.imageSize = scaleFactor <= 2 ? '2K' : '4K';
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
                  const evtUrl = event.outputImageUrl || (event.outputStorageKey ? `${API_BASE_URL}/uploads/${event.outputStorageKey}` : undefined);
                  updateAndPropagate({
                    status: 'success', progress: 100,
                    ...(evtUrl ? { outputImageUrl: evtUrl } : {}),
                    ...(event.outputStorageKey ? { outputStorageKey: event.outputStorageKey } : {}),
                    ...(event.outputPngUrl ? { outputPngUrl: event.outputPngUrl } : {}),
                  }, evtUrl, event.outputStorageKey);
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
        updateAndPropagate({
          status: 'success', progress: 100,
          ...(outUrl ? { outputImageUrl: outUrl } : {}),
          ...(output.outputStorageKey ? { outputStorageKey: output.outputStorageKey } : {}),
          ...(outPng ? { outputPngUrl: outPng } : {}),
          ...(output.runninghubTaskId ? { runninghubTaskId: output.runninghubTaskId } : {}),
        }, outUrl, output.outputStorageKey);
      }
    } catch (err) {
      updateNodeData({
        status: 'error',
        errorMessage: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      executingRef.current = false;
    }
  }, [id, data, activePanel, localAz, localEl, localDist, exprText, scaleFactor, updateNodeData, updateAndPropagate]);

  const isRunning = data.status === 'running';
  const borderColor = selected
    ? cfg.accent.replace('0.9', '0.4')
    : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ width: cardWidth, position: 'relative' }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '50%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '50%' }} />

      {/* ── Capsule toolbar via NodeToolbar (renders in portal, never clipped) ── */}
      <NodeToolbar isVisible={toolbarVisible} position={Position.Top} offset={8} align="start">
        <div style={{ position: 'relative', left: cardWidth / 2, transform: 'translateX(-50%)' }}>
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
          width: '100%', height: imgHeight,
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
                opacity: 1,
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
          {data.processType === 'viewAngle' && data.viewAnglePrompt && (
            <span style={{ fontSize: 8, padding: '2px 5px', borderRadius: 4, backgroundColor: PROCESS_CONFIG.viewAngle.accentBg, color: PROCESS_CONFIG.viewAngle.accent, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.viewAnglePrompt}
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

      {/* ── Floating panel — absolute positioned below card ── */}
      {activePanel !== null && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 50,
          paddingTop: 0,
        }}>
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
        </div>
      )}
    </div>
  );
}

export const ImageProcessNode = memo(ImageProcessNodeComponent);
