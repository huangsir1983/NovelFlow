/**
 * GeminiCompositeNode — Gemini image generation (Tapnow style).
 *
 * Card: ExpressionNode-style display shell.
 * Click: opens floating panel with generate button + character mappings.
 */

'use client';

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { Handle, Position, useEdges, useReactFlow, type NodeProps } from '@xyflow/react';
import type { GeminiCompositeNodeData } from '../../../types/canvas';
import { buildInterleavedParts, type StageScreenshots } from '../../panorama/stageScreenshot';
import { API_BASE_URL, normalizeStorageUrl } from '../../../lib/api';
import {
  getGeminiCompositeDisplayUrl,
  buildGeminiCompositeBadges,
} from '../../../lib/cardDisplayHelpers';

function GeminiCompositeNodeInner({ id, data, selected }: NodeProps) {
  const d = data as unknown as GeminiCompositeNodeData;
  const [hovered, setHovered] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const reactFlow = useReactFlow();
  const { setNodes } = reactFlow;
  const edges = useEdges();

  // Close panel when deselected (clicking blank area)
  const prevSelectedRef = useRef(selected);
  useEffect(() => {
    if (prevSelectedRef.current && !selected) {
      setPanelOpen(false);
    }
    prevSelectedRef.current = selected;
  }, [selected]);

  const hasOutput = !!d.outputImageUrl || !!d.outputImageBase64;
  const hasInput = !!d.sceneScreenshotBase64 || !!d.sceneScreenshotStorageKey;

  // ── Display ──
  const displayUrl = getGeminiCompositeDisplayUrl(d);
  const isInputOnly = !hasOutput && hasInput;
  const badges = buildGeminiCompositeBadges(d);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(168,85,247,0.9)' : 'rgba(168,85,247,0.5)';

  // ── Card click → open panel + center viewport ──
  const handleCardClick = useCallback(() => {
    setPanelOpen(prev => !prev);
    const node = reactFlow.getNode(id);
    if (!node) return;
    const CARD_W = 300;
    const HEADER_H = 31;
    const CARD_BODY_H = Math.round(CARD_W * 9 / 16) + 28;
    const PANEL_H = 280;
    const totalH = HEADER_H + CARD_BODY_H + PANEL_H;
    const centerX = node.position.x + CARD_W / 2;
    const centerY = node.position.y + totalH / 2;
    const vpEl = document.querySelector('.react-flow') as HTMLElement | null;
    const vpH = vpEl?.clientHeight || 800;
    const vpW = vpEl?.clientWidth || 1200;
    const targetZoom = Math.min(vpH / (totalH * 1.15), vpW / (CARD_W * 1.3), 1.5);
    reactFlow.setCenter(centerX, centerY, { zoom: Math.max(targetZoom, 0.5), duration: 400 });
  }, [id, reactFlow]);

  // ── Generate handler ──
  const handleGenerate = useCallback(async () => {
    if (!hasInput) return;

    const fetchAsBase64 = async (url: string): Promise<string> => {
      const resp = await fetch(url);
      if (!resp.ok) return '';
      const blob = await resp.blob();
      return new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const result = reader.result as string;
          resolve(result.includes(',') ? result.split(',')[1] : result);
        };
        reader.readAsDataURL(blob);
      });
    };

    setNodes(nds => nds.map(n => n.id === id ? { ...n, data: { ...n.data, status: 'running', progress: 0 } } : n));
    setErrorMsg(null);

    try {
      let sceneBase64 = d.sceneScreenshotBase64 || '';
      if (!sceneBase64 && d.sceneScreenshotStorageKey) {
        sceneBase64 = await fetchAsBase64(`${API_BASE_URL}/uploads/${d.sceneScreenshotStorageKey}`);
      }
      if (!sceneBase64) throw new Error('场景截图不可用');

      const mappings = d.characterMappings || [];
      const charScreenshots = await Promise.all(
        mappings.map(async m => {
          let pose = m.poseScreenshot || '';
          if (!pose && m.poseStorageKey) {
            pose = await fetchAsBase64(`${API_BASE_URL}/uploads/${m.poseStorageKey}`);
          }
          return { stageCharId: m.stageCharId, stageCharName: m.stageCharName, color: m.color, screenshot: pose };
        }),
      );

      const screenshots: StageScreenshots = { base: sceneBase64, characters: charScreenshots };

      const charDataPromises = mappings
        .filter((_m, i) => charScreenshots[i].screenshot)
        .map(async (m, i) => {
          let referenceBase64 = '';
          if (m.referenceImageUrl) {
            try {
              referenceBase64 = await fetchAsBase64(normalizeStorageUrl(m.referenceImageUrl));
            } catch { /* continue without reference */ }
          }
          return {
            stageCharId: m.stageCharId, referenceCharName: m.stageCharName,
            stageCharColor: m.color, poseScreenshot: charScreenshots[i].screenshot,
            referenceBase64, bbox: m.bbox,
          };
        });

      const charData = (await Promise.all(charDataPromises)).filter(cd => cd.referenceBase64);
      const parts = buildInterleavedParts(screenshots, charData, d.sceneDescription);

      const resp = await fetch(`${API_BASE_URL}/api/ai/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: '根据提供的图片生成高品质画面',
          interleaved_parts: parts.map(p => ({ type: p.type, content: p.content, mime_type: p.mime_type })),
          aspect_ratio: '16:9',
          image_size: '2K',
        }),
      });

      if (!resp.ok) {
        const errBody = await resp.text();
        throw new Error(`生成失败 (${resp.status}): ${errBody}`);
      }

      const result = await resp.json();
      const outputUrl = normalizeStorageUrl(result.storage_uri) || undefined;

      setNodes(nds =>
        nds.map(n => {
          if (n.id === id) {
            return { ...n, data: { ...n.data, outputImageBase64: result.image_base64, outputStorageKey: result.storage_key, outputImageUrl: outputUrl, status: 'success', progress: 100 } };
          }
          const downEdge = edges.find(e => e.source === id && e.target === n.id);
          if (downEdge && (n.data as Record<string, unknown>).nodeType === 'imageProcess') {
            return { ...n, data: { ...n.data, inputImageUrl: outputUrl || `data:image/jpeg;base64,${result.image_base64}`, inputStorageKey: result.storage_key, status: 'idle' } };
          }
          return n;
        }),
      );

      fetch(`${API_BASE_URL}/api/canvas/nodes/${id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_type: 'geminiComposite',
          content: {
            storage_key: result.storage_key, storage_uri: result.storage_uri,
            sceneScreenshotStorageKey: d.sceneScreenshotStorageKey,
            characterMappings: d.characterMappings?.map(m => ({
              stageCharId: m.stageCharId, stageCharName: m.stageCharName, color: m.color,
              poseStorageKey: m.poseStorageKey, referenceImageUrl: m.referenceImageUrl,
              referenceStorageKey: m.referenceStorageKey, bbox: m.bbox,
            })),
            sceneDescription: d.sceneDescription,
          },
        }),
      }).catch(() => {});

      setPanelOpen(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setNodes(nds => nds.map(n => n.id === id ? { ...n, data: { ...n.data, status: 'error', errorMessage: msg } } : n));
    }
  }, [hasInput, id, d, edges, setNodes]);

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
        <span className="text-[13px]">✨</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>Gemini合成</span>
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
            <img src={displayUrl} alt="Gemini合成" style={{ width: '100%', height: 'auto', display: 'block', opacity: isInputOnly ? 0.6 : 1 }} />
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>✨</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>等待3D导演台截图</span>
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
            {d.characterMappings?.map((m, i) => (
              <span key={`char-${i}`} style={{
                fontSize: 9, padding: '2px 6px', borderRadius: 4,
                backgroundColor: m.color, color: '#fff',
                maxWidth: 60, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{m.stageCharName}</span>
            ))}
          </div>
        </div>

        {/* Status dot */}
        <div style={{
          position: 'absolute', top: 10, right: 10, width: 8, height: 8,
          borderRadius: '50%', zIndex: 2,
          backgroundColor:
            d.status === 'running' ? '#60a5fa'
            : d.status === 'success' ? '#34d399'
            : d.status === 'error' ? '#f87171'
            : 'transparent',
        }} />

        {/* Progress bar */}
        {d.status === 'running' && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
            <div style={{ height: '100%', backgroundColor: 'rgba(168,85,247,0.6)', width: `${d.progress ?? 0}%` }} />
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
              width: 320,
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

            {/* Character mappings */}
            {d.characterMappings && d.characterMappings.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 6 }}>角色映射</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {d.characterMappings.map((m, i) => (
                    <span key={i} style={{
                      fontSize: 10, padding: '3px 8px', borderRadius: 6,
                      backgroundColor: m.color, color: '#fff',
                    }}>{m.stageCharName}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Error */}
            {errorMsg && (
              <div style={{
                marginBottom: 8, padding: '6px 10px', borderRadius: 8,
                background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)',
                fontSize: 11, color: 'rgba(248,113,113,0.8)', wordBreak: 'break-all',
              }}>{errorMsg}</div>
            )}

            {/* Generate button */}
            <button
              onClick={(e) => { e.stopPropagation(); handleGenerate(); }}
              disabled={d.status === 'running' || !hasInput}
              style={{
                width: '100%', border: 'none', borderRadius: 8,
                padding: '8px 0', fontSize: 12, fontWeight: 600,
                background: d.status === 'running'
                  ? 'rgba(255,255,255,0.06)'
                  : 'linear-gradient(135deg, rgba(168,85,247,0.8), rgba(192,132,252,0.8))',
                color: d.status === 'running' ? 'rgba(255,255,255,0.3)' : '#fff',
                cursor: d.status === 'running' || !hasInput ? 'not-allowed' : 'pointer',
                opacity: !hasInput ? 0.4 : 1,
              }}
            >
              {d.status === 'running' ? '生成中...' : hasOutput ? '重新生成' : '生成影视级画面'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export const GeminiCompositeNode = memo(GeminiCompositeNodeInner);
