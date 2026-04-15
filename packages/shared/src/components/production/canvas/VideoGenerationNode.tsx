/**
 * VideoGenerationNode — Video card with floating prompt editor panel.
 *
 * Card: shows video preview / first-frame image / placeholder + progress bar.
 * Panel: image gallery (stacked → expand on hover) + contentEditable prompt
 *        editor with inline image chips + bottom toolbar.
 * Executes via SSE to backend Seedance (映话全能视频S) endpoint.
 */

'use client';

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { type NodeProps, type Node, Handle, Position, useReactFlow } from '@xyflow/react';
import type { VideoGenerationNodeData, VideoImageRef } from '../../../types/canvas';
import { assembleVideoPrompt, buildImageRefsFromNodeData } from '../../../lib/videoPromptAssembly';
import { API_BASE_URL, normalizeStorageUrl } from '../../../lib/api';
import { buildVideoGenerationBadges } from '../../../lib/cardDisplayHelpers';
import { useCanvasStore } from '../../../stores/canvasStore';
import { MergedVideoPanel } from './MergedVideoPanel';

type VideoGenerationNode = Node<VideoGenerationNodeData, 'videoGeneration'>;

// ─── contentEditable helpers ───

/** Escape HTML special chars */
function esc(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Build HTML from plain text, replacing 图片N with inline image chip spans */
function buildEditorHtml(
  text: string,
  refs: VideoImageRef[],
  resolveUrl: (r: VideoImageRef) => string,
): string {
  const re = /图片(\d+)/g;
  let html = '';
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) html += esc(text.slice(last, m.index)).replace(/\n/g, '<br>');
    const idx = parseInt(m[1], 10) - 1;
    const ref = refs[idx];
    if (ref) {
      const url = resolveUrl(ref);
      html += `<span contenteditable="false" data-img-idx="${idx}" data-img-num="${idx + 1}" data-img-label="${esc(ref.label)}" style="display:inline-flex;align-items:center;gap:3px;padding:1px 5px 1px 2px;border-radius:4px;background:rgba(232,121,249,0.12);border:1px solid rgba(232,121,249,0.25);vertical-align:middle;cursor:default;user-select:none;"><img src="${url}" style="width:16px;height:16px;border-radius:3px;object-fit:cover;border:1px solid rgba(255,255,255,0.15);flex-shrink:0;pointer-events:none;" /><span style="font-size:11px;color:rgba(232,121,249,0.9);white-space:nowrap;pointer-events:none;">图片${idx + 1}</span></span>`;
    } else {
      html += esc(m[0]);
    }
    last = re.lastIndex;
  }
  if (last < text.length) html += esc(text.slice(last)).replace(/\n/g, '<br>');
  return html || '<br>'; // empty div needs <br> to be clickable
}

/** Walk DOM of contentEditable → extract plain text (chips → "图片N") */
function extractText(el: HTMLElement): string {
  let out = '';
  for (const node of el.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) {
      out += node.textContent || '';
    } else if (node instanceof HTMLElement) {
      const imgIdx = node.getAttribute('data-img-idx');
      if (imgIdx !== null) {
        out += `图片${parseInt(imgIdx, 10) + 1}`;
      } else if (node.tagName === 'BR') {
        out += '\n';
      } else if (node.tagName === 'DIV' || node.tagName === 'P') {
        // Some browsers wrap lines in <div>
        if (out.length > 0 && !out.endsWith('\n')) out += '\n';
        out += extractText(node);
      } else {
        out += extractText(node);
      }
    }
  }
  return out;
}

// ─── Merge Group Glow Frame (SVG orbit) ───

const GLOW_CARD_W = 300;
const GLOW_NODE_H = 200;  // ReactFlow node height (includes title bar)
const GLOW_SNAP_G = 6;
const GLOW_PAD = 8;
const GLOW_STROKE = 2;
const GLOW_LEN = 120;

function MergeGroupGlowFrame({ mergeGroupSize, groupId }: { mergeGroupSize: number; groupId: string }) {
  // Node-to-node step = NODE_H + SNAP_GAP = 206
  // Total from first node top to last node bottom = (N-1)*206 + 200
  const totalH = (mergeGroupSize - 1) * (GLOW_NODE_H + GLOW_SNAP_G) + GLOW_NODE_H;
  const frameW = GLOW_CARD_W + GLOW_PAD * 2;
  const frameH = totalH + GLOW_PAD * 2;
  const svgW = frameW + GLOW_STROKE * 2;
  const svgH = frameH + GLOW_STROKE * 2;
  const perimeter = 2 * (frameW + frameH);
  const animName = `mergeOrbit_${groupId.replace(/[^a-zA-Z0-9]/g, '')}`;

  return (
    <div style={{
      position: 'absolute',
      top: -GLOW_PAD,
      left: -GLOW_PAD,
      width: svgW,
      height: svgH,
      pointerEvents: 'none',
      zIndex: -1,
    }}>
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes ${animName} {
          from { stroke-dashoffset: 0; }
          to { stroke-dashoffset: -${perimeter}; }
        }
      `}} />
      <svg width={svgW} height={svgH} style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id={`glowGrad_${groupId}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(139,92,246,0)" />
            <stop offset="50%" stopColor="rgba(168,85,247,0.9)" />
            <stop offset="100%" stopColor="rgba(139,92,246,0)" />
          </linearGradient>
          <filter id={`glowBlur_${groupId}`}>
            <feGaussianBlur stdDeviation="3" />
          </filter>
        </defs>
        {/* 静态底框 */}
        <rect x={GLOW_STROKE} y={GLOW_STROKE}
          width={frameW} height={frameH} rx={16}
          fill="none" stroke="rgba(139,92,246,0.15)" strokeWidth={1} />
        {/* 发光层（模糊） */}
        <rect x={GLOW_STROKE} y={GLOW_STROKE}
          width={frameW} height={frameH} rx={16}
          fill="none" stroke={`url(#glowGrad_${groupId})`} strokeWidth={3}
          strokeDasharray={`${GLOW_LEN} ${perimeter - GLOW_LEN}`}
          filter={`url(#glowBlur_${groupId})`}
          style={{ animation: `${animName} 4s linear infinite` }} />
        {/* 清晰光带 */}
        <rect x={GLOW_STROKE} y={GLOW_STROKE}
          width={frameW} height={frameH} rx={16}
          fill="none" stroke={`url(#glowGrad_${groupId})`} strokeWidth={GLOW_STROKE}
          strokeDasharray={`${GLOW_LEN} ${perimeter - GLOW_LEN}`}
          style={{ animation: `${animName} 4s linear infinite` }} />
      </svg>
    </div>
  );
}

// ─── Component ───

function VideoGenerationNodeComponent({ id, data, selected }: NodeProps<VideoGenerationNode>) {
  const isMerged = !!(data.mergeGroupId && (data.mergeGroupSize ?? 0) > 1);
  const isFirstInGroup = isMerged && data.mergeGroupIndex === 0;
  const [hovered, setHovered] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [localImageRefs, setLocalImageRefs] = useState<VideoImageRef[]>([]);
  const [galleryHovered, setGalleryHovered] = useState(false);
  const [previewIdx, setPreviewIdx] = useState<number | null>(null);
  const [localRatio, setLocalRatio] = useState<'16:9' | '9:16' | '1:1'>(data.ratio || '16:9');
  const [localDuration, setLocalDuration] = useState<number>(data.durationSeconds || Math.round((data.durationMs || 5000) / 1000));
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Chip hover preview in editor
  const [chipPreview, setChipPreview] = useState<{ idx: number; top: number; left: number } | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const editorWrapRef = useRef<HTMLDivElement>(null);
  const reactFlow = useReactFlow();
  const abortRef = useRef<AbortController | null>(null);
  // Track whether we need to re-render chips (avoid doing it on every keystroke)
  const refsVersionRef = useRef(0);

  // Close panel when deselected (clicking blank area)
  const prevSelectedRef = useRef(selected);
  useEffect(() => {
    if (prevSelectedRef.current && !selected) {
      setPanelOpen(false);
    }
    prevSelectedRef.current = selected;
  }, [selected]);

  const inputImageUrl = data.inputImageUrl;
  const defaultDur = data.durationSeconds || Math.round((data.durationMs || 5000) / 1000);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(232,121,249,0.9)' : 'rgba(232,121,249,0.5)';
  const videoBadges = buildVideoGenerationBadges({ mode: data.mode, durationSeconds: defaultDur, videoUrl: data.videoUrl });

  // Direct store update — bypasses useDeferredValue for immediate feedback
  const updateNodeData = useCallback((patch: Record<string, unknown>) => {
    const s = useCanvasStore.getState();
    s.setNodes(s.nodes.map(n => n.id === id ? { ...n, data: { ...n.data, ...patch } } : n));
  }, [id]);

  // Resolve image URL for display
  const resolveUrl = useCallback((ref: VideoImageRef) => {
    if (!ref.url) {
      // Fallback to storageKey if URL is missing
      if (ref.storageKey) return `${API_BASE_URL}/uploads/${ref.storageKey}`;
      return '';
    }
    if (ref.url.startsWith('http') || ref.url.startsWith('data:')) return ref.url;
    // Might be a storage key like "assets/images/xxx.jpeg" — serve via /uploads/
    if (!ref.url.includes('/uploads/') && !ref.url.startsWith('/')) {
      return `${API_BASE_URL}/uploads/${ref.url}`;
    }
    return normalizeStorageUrl(ref.url);
  }, []);

  // Render chips into editor (imperative — avoids cursor destruction)
  const renderEditorHtml = useCallback((text: string, refs: VideoImageRef[]) => {
    if (!editorRef.current) return;
    editorRef.current.innerHTML = buildEditorHtml(text, refs, resolveUrl);
  }, [resolveUrl]);

  // Initialize panel content on first open
  const handleOpenPanel = useCallback(() => {
    if (!panelOpen) {
      const refs = data.imageRefs?.length ? data.imageRefs : buildImageRefsFromNodeData(data);
      setLocalImageRefs(refs);
      const prompt = data.assembledPrompt || assembleVideoPrompt(data);
      setPromptText(prompt);
      setLocalRatio(data.ratio || '16:9');
      setLocalDuration(data.durationSeconds || defaultDur);
      setErrorMsg(null);
      setChipPreview(null);
      refsVersionRef.current++;
      // Editor HTML will be set by useEffect below
    }
    setPanelOpen(!panelOpen);

    // Center viewport on card + panel
    const node = reactFlow.getNode(id);
    if (node) {
      const CARD_W = 300;
      const HEADER_H = 31;
      const CARD_BODY_H = Math.round(CARD_W * 9 / 16) + 28;
      const PANEL_H = 400;
      const totalH = HEADER_H + CARD_BODY_H + PANEL_H;
      const centerX = node.position.x + CARD_W / 2;
      const centerY = node.position.y + totalH / 2;
      const vpEl = document.querySelector('.react-flow') as HTMLElement | null;
      const vpH = vpEl?.clientHeight || 800;
      const vpW = vpEl?.clientWidth || 1200;
      const targetZoom = Math.min(vpH / (totalH * 1.15), vpW / (CARD_W * 1.3), 1.5);
      reactFlow.setCenter(centerX, centerY, { zoom: Math.max(targetZoom, 0.5), duration: 400 });
    }
  }, [panelOpen, data, id, reactFlow]);

  // Set editor HTML when panel opens or refs change
  useEffect(() => {
    if (panelOpen && editorRef.current) {
      renderEditorHtml(promptText, localImageRefs);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [panelOpen, refsVersionRef.current]);

  // Re-render chips when image refs change (e.g. user removes one in gallery)
  useEffect(() => {
    if (panelOpen && editorRef.current) {
      // Extract current text first (preserve edits), then re-render with new refs
      const current = extractText(editorRef.current);
      setPromptText(current);
      renderEditorHtml(current, localImageRefs);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localImageRefs]);

  // On editor input — just sync text to state (don't re-render chips)
  const handleEditorInput = useCallback(() => {
    if (!editorRef.current) return;
    setPromptText(extractText(editorRef.current));
  }, []);

  // On editor blur — re-render to pick up newly typed "图片N" as chips
  const handleEditorBlur = useCallback(() => {
    if (!editorRef.current) return;
    const text = extractText(editorRef.current);
    setPromptText(text);
    renderEditorHtml(text, localImageRefs);
  }, [localImageRefs, renderEditorHtml]);

  // Chip hover detection via event delegation
  const handleEditorMouseMove = useCallback((e: React.MouseEvent) => {
    const chip = (e.target as HTMLElement).closest('[data-img-idx]') as HTMLElement | null;
    if (chip && editorWrapRef.current) {
      const idx = parseInt(chip.getAttribute('data-img-idx')!, 10);
      const chipRect = chip.getBoundingClientRect();
      const wrapRect = editorWrapRef.current.getBoundingClientRect();
      setChipPreview({
        idx,
        top: chipRect.top - wrapRect.top,
        left: chipRect.left - wrapRect.left + chipRect.width / 2,
      });
    } else {
      if (chipPreview) setChipPreview(null);
    }
  }, [chipPreview]);

  const handleEditorMouseLeave = useCallback(() => {
    setChipPreview(null);
  }, []);

  // Remove image ref
  const handleRemoveRef = useCallback((refId: string) => {
    setLocalImageRefs(prev => prev.filter(r => r.id !== refId));
  }, []);

  // Get current prompt text (from editor if open, else from state)
  const getCurrentPrompt = useCallback(() => {
    if (editorRef.current) return extractText(editorRef.current);
    return promptText;
  }, [promptText]);

  // Execute video generation via SSE
  const handleExecute = useCallback(async () => {
    // Abort any previous in-flight request
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    setErrorMsg(null);
    const currentPrompt = getCurrentPrompt();
    setPromptText(currentPrompt);
    console.log('[VideoGen] handleExecute called, prompt length:', currentPrompt.length);

    // Prefer full URL (http) over storageKey — external API needs accessible URLs
    const filePaths = localImageRefs.map(r => r.url || r.storageKey || '').filter(Boolean);

    updateNodeData({ status: 'running', progress: 0, assembledPrompt: currentPrompt, imageRefs: localImageRefs, ratio: localRatio, durationSeconds: localDuration });

    const abortCtrl = new AbortController();
    abortRef.current = abortCtrl;

    try {
      const requestBody = {
        node_type: 'videoGeneration',
        content: { prompt: currentPrompt, file_paths: filePaths, ratio: localRatio, duration: localDuration },
      };
      console.log('[VideoGen] POST', `${API_BASE_URL}/api/canvas/nodes/${id}/execute`, 'file_paths:', filePaths.length, 'ratio:', localRatio, 'dur:', localDuration);
      const resp = await fetch(`${API_BASE_URL}/api/canvas/nodes/${id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
        signal: abortCtrl.signal,
      });
      console.log('[VideoGen] Response status:', resp.status);

      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`请求失败 (${resp.status}): ${errText}`);
      }

      const reader = resp.body?.getReader();
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
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'progress') {
              updateNodeData({ progress: evt.progress });
            } else if (evt.type === 'success') {
              updateNodeData({ status: 'success', progress: 100, videoUrl: evt.video_url, seedanceTaskId: evt.task_id });
              setPanelOpen(false);
            } else if (evt.type === 'error') {
              throw new Error(evt.message);
            }
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message !== line.slice(6)) throw parseErr;
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return;
      const msg = err instanceof Error ? err.message : String(err);
      console.error('[VideoGen] Error:', msg);
      setErrorMsg(msg);
      updateNodeData({ status: 'error', errorMessage: msg, progress: 0 });
    } finally {
      abortRef.current = null;
    }
  }, [id, getCurrentPrompt, localImageRefs, localRatio, localDuration, updateNodeData]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  const [scissorHovered, setScissorHovered] = useState(false);

  // 缝隙切开：从 mergeGroup 中移除该卡及其后的卡
  const handleSplit = useCallback(() => {
    if (!data.mergeGroupId || data.mergeGroupIndex == null) return;
    const s = useCanvasStore.getState();
    const groups = s.mergeGroups;
    const gIdx = groups.findIndex(g => g.groupId === data.mergeGroupId);
    if (gIdx < 0) return;
    const group = groups[gIdx];
    const splitAt = data.mergeGroupIndex;
    const keepIds = group.shotIds.slice(0, splitAt);
    const newGroups = [...groups];
    if (keepIds.length < 2) {
      // 剩余不足 2 个，解散整个组
      newGroups.splice(gIdx, 1);
    } else {
      newGroups[gIdx] = { ...group, shotIds: keepIds };
    }
    s.setMergeGroups(newGroups);
  }, [data.mergeGroupId, data.mergeGroupIndex]);

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} className="relative" style={{ width: 300 }}>
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* ✂️ 缝隙切开区域 — 磁吸组非首卡 */}
      {isMerged && (data.mergeGroupIndex ?? 0) > 0 && (
        <div
          onMouseEnter={() => setScissorHovered(true)}
          onMouseLeave={() => setScissorHovered(false)}
          onClick={(e) => { e.stopPropagation(); handleSplit(); }}
          style={{
            position: 'absolute', top: -6, left: 0, right: 0, height: 12,
            cursor: 'pointer', zIndex: 10,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: scissorHovered ? 'rgba(248,113,113,0.15)' : 'transparent',
            borderRadius: 4,
            transition: 'background 0.15s',
          }}
          title="点击拆开磁吸"
        >
          {scissorHovered && (
            <span style={{ fontSize: 10, color: 'rgba(248,113,113,0.8)' }}>✂️ 拆开</span>
          )}
        </div>
      )}

      {/* Title bar */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">▶</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>Video</span>
      </div>

      {/* 整组流光框 — 仅首卡渲染 */}
      {isFirstInGroup && data.mergeGroupId && (
        <MergeGroupGlowFrame
          mergeGroupSize={data.mergeGroupSize ?? 1}
          groupId={data.mergeGroupId}
        />
      )}

      {/* Main card */}
      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
        cursor: 'pointer',
      }} onClick={handleOpenPanel}>
        {/* Image area */}
        <div style={{
          width: '100%', minHeight: 100,
          backgroundColor: '#0c0e12',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {data.videoUrl ? (
            <video src={data.videoUrl} style={{ width: '100%', height: 'auto', display: 'block' }} muted loop playsInline
              onMouseEnter={(e) => { e.stopPropagation(); (e.target as HTMLVideoElement).play().catch(() => {}); }}
              onMouseLeave={(e) => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }} />
          ) : inputImageUrl ? (
            <img src={inputImageUrl} alt="源图" style={{ width: '100%', height: 'auto', display: 'block', opacity: 0.7 }} />
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>▶</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>{data.status === 'running' ? '生成中...' : '待生成'}</span>
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
            {videoBadges.map((b, i) => (
              <span key={i} style={{
                fontSize: 9, padding: '2px 6px', borderRadius: 4,
                backgroundColor: b.bgColor, color: b.textColor,
              }}>{b.text}</span>
            ))}
          </div>
          {data.status === 'error' && data.errorMessage && (
            <p style={{ fontSize: 10, color: 'rgba(248,113,113,0.6)', lineHeight: 1.4, marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.errorMessage}
            </p>
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

        {/* Progress bar */}
        {data.status === 'running' && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
            <div style={{ height: '100%', backgroundColor: 'rgba(232,121,249,0.6)', width: `${data.progress}%`, transition: 'width 0.3s' }} />
          </div>
        )}

        {/* 磁吸组标记 */}
        {isMerged && (
          <div style={{
            position: 'absolute', top: 10, left: 10, zIndex: 2,
            fontSize: 9, padding: '1px 6px', borderRadius: 4,
            background: isFirstInGroup ? 'rgba(139,92,246,0.3)' : 'rgba(139,92,246,0.15)',
            color: 'rgba(139,92,246,0.9)',
            border: '1px solid rgba(139,92,246,0.25)',
          }}>
            {isFirstInGroup ? `合并·${data.mergeGroupSize}镜` : `#${(data.mergeGroupIndex ?? 0) + 1}`}
          </div>
        )}
      </div>

      {/* ── Floating panel — 磁吸组用 MergedVideoPanel，独立卡用原有面板 ── */}
      {panelOpen && isMerged && (() => {
        // 计算浮空栏偏移：定位到组内最下方卡的下方
        const mgSize = data.mergeGroupSize ?? 1;
        const mgIdx = data.mergeGroupIndex ?? 0;
        const NODE_H = 200;
        const SNAP_G = 6;
        // 从当前卡到最下方卡的 Y 偏移
        const remainingCards = mgSize - 1 - mgIdx;
        const offsetY = remainingCards * (NODE_H + SNAP_G);

        const s = useCanvasStore.getState();
        const group = s.mergeGroups.find(mg => mg.groupId === data.mergeGroupId);

        return (
        <div style={{
          position: 'absolute', top: `calc(100% + ${offsetY}px)`, left: '50%',
          transform: 'translateX(-50%)', zIndex: 50, paddingTop: 4,
        }}>
          <MergedVideoPanel
            groupId={data.mergeGroupId!}
            shotIds={group?.shotIds ?? [data.shotId || id]}
            totalDuration={group?.totalDuration ?? (data.durationSeconds || 5)}
            driftRisk={(group?.driftRisk as 'low' | 'medium' | 'high') ?? 'low'}
            firstNodeId={(() => {
              const firstShotId = group?.shotIds[0];
              return firstShotId ? `video-${firstShotId}` : id;
            })()}
            onClose={() => setPanelOpen(false)}
          />
        </div>
        );
      })()}
      {panelOpen && !isMerged && (
        <div style={{
          position: 'absolute', top: '100%', left: '50%',
          transform: 'translateX(-50%)', zIndex: 50, paddingTop: 0,
        }}>
          <div
            className="nopan nodrag nowheel"
            style={{
              width: 460,
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
              onClick={(e) => { e.stopPropagation(); setPanelOpen(false); }}
              style={{
                position: 'absolute', top: 8, right: 8, border: 'none',
                background: 'rgba(255,255,255,0.06)', borderRadius: '50%',
                width: 22, height: 22, cursor: 'pointer',
                color: 'rgba(255,255,255,0.4)', fontSize: 11,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >×</button>

            {/* ── A. Image Gallery ── */}
            {localImageRefs.length > 0 && (
              <div
                style={{ marginBottom: 12 }}
                onMouseEnter={() => setGalleryHovered(true)}
                onMouseLeave={() => { setGalleryHovered(false); setPreviewIdx(null); }}
              >
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 6 }}>
                  图片引用 ({localImageRefs.length})
                </div>
                <div style={{
                  display: 'flex',
                  gap: galleryHovered ? 4 : 0,
                  alignItems: 'flex-end',
                  position: 'relative',
                  minHeight: 52,
                  transition: 'gap 0.2s',
                }}>
                  {localImageRefs.map((ref, i) => (
                    <div
                      key={ref.id}
                      style={{
                        position: galleryHovered ? 'relative' : 'absolute',
                        left: galleryHovered ? undefined : i * 12,
                        zIndex: galleryHovered ? 1 : localImageRefs.length - i,
                        flexShrink: 0,
                      }}
                      onMouseEnter={() => setPreviewIdx(i)}
                      onMouseLeave={() => setPreviewIdx(null)}
                    >
                      <div style={{
                        width: 48, height: 48, borderRadius: 8, overflow: 'hidden',
                        border: '2px solid rgba(255,255,255,0.12)',
                        position: 'relative',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                      }}>
                        <img src={resolveUrl(ref)} alt={ref.label}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        <span style={{
                          position: 'absolute', bottom: 1, left: 1,
                          fontSize: 8, padding: '0 3px', borderRadius: 3,
                          background: 'rgba(0,0,0,0.7)', color: 'rgba(255,255,255,0.7)',
                        }}>图{i + 1}</span>
                        {galleryHovered && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleRemoveRef(ref.id); }}
                            style={{
                              position: 'absolute', top: -4, right: -4,
                              width: 14, height: 14, borderRadius: '50%',
                              background: 'rgba(220,38,38,0.8)', border: 'none',
                              color: '#fff', fontSize: 8, cursor: 'pointer',
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}
                          >×</button>
                        )}
                      </div>
                      {galleryHovered && (
                        <div style={{
                          fontSize: 9, color: 'rgba(255,255,255,0.4)',
                          textAlign: 'center', marginTop: 2,
                          maxWidth: 48, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>{ref.label}</div>
                      )}
                      {previewIdx === i && (
                        <div style={{
                          position: 'absolute', bottom: '100%', left: '50%',
                          transform: 'translateX(-50%)',
                          marginBottom: 6, zIndex: 100,
                          borderRadius: 10, overflow: 'hidden',
                          border: '1px solid rgba(255,255,255,0.15)',
                          boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
                        }}>
                          <img src={resolveUrl(ref)} alt={ref.label}
                            style={{ width: 160, height: 'auto', display: 'block' }} />
                          <div style={{
                            background: 'rgba(0,0,0,0.75)', padding: '2px 6px',
                            fontSize: 10, color: 'rgba(255,255,255,0.7)', textAlign: 'center',
                          }}>图片{i + 1} · {ref.label}</div>
                        </div>
                      )}
                    </div>
                  ))}
                  {!galleryHovered && localImageRefs.length > 1 && (
                    <div style={{
                      position: 'absolute',
                      left: localImageRefs.length * 12 + 8, bottom: 0,
                      fontSize: 10, color: 'rgba(255,255,255,0.3)',
                    }}>+{localImageRefs.length}</div>
                  )}
                </div>
              </div>
            )}

            {/* ── B. Prompt Editor (contentEditable with inline image chips) ── */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>
                视频提示词
              </div>
              <div ref={editorWrapRef} style={{ position: 'relative' }}
                onMouseMove={handleEditorMouseMove}
                onMouseLeave={handleEditorMouseLeave}
              >
                <div
                  ref={editorRef}
                  contentEditable
                  suppressContentEditableWarning
                  onInput={handleEditorInput}
                  onBlur={handleEditorBlur}
                  style={{
                    width: '100%',
                    minHeight: 200,
                    maxHeight: 400,
                    overflowY: 'auto',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 10,
                    padding: 10,
                    color: 'rgba(255,255,255,0.85)',
                    fontSize: 12,
                    lineHeight: 1.8,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    outline: 'none',
                    caretColor: 'rgba(232,121,249,0.8)',
                  }}
                />
                {/* Chip hover preview popup */}
                {chipPreview && localImageRefs[chipPreview.idx] && (
                  <div style={{
                    position: 'absolute',
                    top: chipPreview.top - 6,
                    left: chipPreview.left,
                    transform: 'translate(-50%, -100%)',
                    zIndex: 200,
                    borderRadius: 8, overflow: 'hidden',
                    border: '1px solid rgba(255,255,255,0.15)',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
                    pointerEvents: 'none',
                  }}>
                    <img
                      src={resolveUrl(localImageRefs[chipPreview.idx])}
                      alt={localImageRefs[chipPreview.idx].label}
                      style={{ width: 160, height: 'auto', display: 'block' }}
                    />
                    <div style={{
                      background: 'rgba(0,0,0,0.8)', padding: '2px 6px',
                      fontSize: 10, color: 'rgba(255,255,255,0.7)', textAlign: 'center',
                    }}>
                      图片{chipPreview.idx + 1} · {localImageRefs[chipPreview.idx].label}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Error display */}
            {errorMsg && (
              <div style={{
                marginBottom: 8, padding: '6px 10px', borderRadius: 8,
                background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)',
                fontSize: 11, color: 'rgba(248,113,113,0.8)',
                wordBreak: 'break-all',
              }}>{errorMsg}</div>
            )}

            {/* ── C. Bottom Toolbar ── */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{
                fontSize: 9, fontFamily: 'monospace', padding: '2px 6px',
                borderRadius: 4, background: 'rgba(255,255,255,0.04)',
                color: 'rgba(255,255,255,0.3)',
              }}>seedance-2.0-fast</span>

              <div style={{ display: 'flex', gap: 2 }}>
                {(['16:9', '9:16', '1:1'] as const).map(r => (
                  <button key={r}
                    onClick={(e) => { e.stopPropagation(); setLocalRatio(r); }}
                    style={{
                      padding: '2px 8px', fontSize: 10, borderRadius: 4,
                      border: localRatio === r ? '1px solid rgba(232,121,249,0.4)' : '1px solid rgba(255,255,255,0.08)',
                      background: localRatio === r ? 'rgba(232,121,249,0.15)' : 'rgba(255,255,255,0.03)',
                      color: localRatio === r ? 'rgba(232,121,249,0.9)' : 'rgba(255,255,255,0.35)',
                      cursor: 'pointer',
                    }}
                  >{r}</button>
                ))}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>⏱</span>
                <input
                  type="number"
                  min={1} max={30} step={1}
                  value={localDuration}
                  onChange={(e) => setLocalDuration(Math.max(1, Math.min(30, parseInt(e.target.value) || 5)))}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    width: 32, padding: '2px 4px', fontSize: 10, textAlign: 'center',
                    borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)',
                    background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.6)',
                    outline: 'none',
                  }}
                />
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>s</span>
              </div>
              <div style={{ flex: 1 }} />

              <button
                onClick={(e) => { e.stopPropagation(); handleExecute(); }}
                disabled={!promptText.trim()}
                style={{
                  padding: '6px 16px', borderRadius: 8, border: 'none',
                  background: data.status === 'running'
                    ? 'rgba(255,255,255,0.06)'
                    : 'linear-gradient(135deg, rgba(168,85,247,0.8), rgba(232,121,249,0.8))',
                  color: data.status === 'running' ? 'rgba(255,255,255,0.3)' : '#fff',
                  fontSize: 12, fontWeight: 500,
                  cursor: data.status === 'running' ? 'not-allowed' : 'pointer',
                  transition: 'opacity 0.2s',
                }}
              >
                {data.status === 'running' ? `生成中 ${data.progress}%` : '视频生成 ▶'}
              </button>
            </div>

            {/* ── D. Reserved row ── */}
            <div style={{
              marginTop: 10, paddingTop: 8,
              borderTop: '1px solid rgba(255,255,255,0.04)',
              fontSize: 10, color: 'rgba(255,255,255,0.15)',
              textAlign: 'center',
            }}>
              展开式清单选取（预留）
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export const VideoGenerationNode = memo(VideoGenerationNodeComponent);
