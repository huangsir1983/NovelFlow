/**
 * MergedVideoPanel — 磁吸合并组的统一浮空栏。
 *
 * 包含：图片引用画廊 + 合并 prompt 编辑器（inline image chips）+ 生成按钮
 */

'use client';

import { memo, useCallback, useMemo, useRef, useState } from 'react';
import { useCanvasStore } from '../../../stores/canvasStore';
import { API_BASE_URL, normalizeStorageUrl } from '../../../lib/api';
import { assembleMergedPromptFromNodes, buildMergedImageRefs } from '../../../lib/videoPromptAssembly';
import type { VideoGenerationNodeData, VideoImageRef } from '../../../types/canvas';

interface MergedVideoPanelProps {
  groupId: string;
  shotIds: string[];
  totalDuration: number;
  driftRisk: 'low' | 'medium' | 'high';
  firstNodeId: string;
  onClose: () => void;
}

const RISK_COLORS: Record<string, { bg: string; text: string }> = {
  low: { bg: 'rgba(52,211,153,0.15)', text: 'rgba(52,211,153,0.9)' },
  medium: { bg: 'rgba(251,191,36,0.15)', text: 'rgba(251,191,36,0.9)' },
  high: { bg: 'rgba(248,113,113,0.15)', text: 'rgba(248,113,113,0.9)' },
};

/** Escape HTML */
function esc(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Build HTML with inline image chips for 图片N references */
function buildEditorHtml(text: string, refs: VideoImageRef[], resolveUrl: (r: VideoImageRef) => string): string {
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
      html += `<span contenteditable="false" data-img-idx="${idx}" style="display:inline-flex;align-items:center;gap:3px;padding:1px 5px 1px 2px;border-radius:4px;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.25);vertical-align:middle;cursor:default;user-select:none;"><img src="${url}" style="width:16px;height:16px;border-radius:3px;object-fit:cover;border:1px solid rgba(255,255,255,0.15);flex-shrink:0;pointer-events:none;" /><span style="font-size:11px;color:rgba(139,92,246,0.9);white-space:nowrap;pointer-events:none;">图片${idx + 1}</span></span>`;
    } else {
      html += esc(m[0]);
    }
    last = re.lastIndex;
  }
  if (last < text.length) html += esc(text.slice(last)).replace(/\n/g, '<br>');
  return html || '<br>';
}

/** Extract plain text from contentEditable (chips → 图片N) */
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
        if (out.length > 0 && !out.endsWith('\n')) out += '\n';
        out += extractText(node);
      } else {
        out += extractText(node);
      }
    }
  }
  return out;
}

function MergedVideoPanelComponent({
  groupId,
  shotIds,
  totalDuration,
  driftRisk,
  firstNodeId,
  onClose,
}: MergedVideoPanelProps) {
  void groupId;

  // 从 store 找同组 Video 节点
  const videoNodes = useMemo(() => {
    const allNodes = useCanvasStore.getState().nodes;
    return shotIds
      .map(sid => allNodes.find(n => n.id === `video-${sid}`))
      .filter((n): n is NonNullable<typeof n> => !!n)
      .map(n => ({ data: n.data as Partial<VideoGenerationNodeData> }));
  }, [shotIds]);

  const initialPrompt = useMemo(() => assembleMergedPromptFromNodes(videoNodes), [videoNodes]);
  const imageRefs = useMemo(() => buildMergedImageRefs(videoNodes), [videoNodes]);

  const [prompt, setPrompt] = useState(initialPrompt);
  const [galleryHovered, setGalleryHovered] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const resolveUrl = useCallback((ref: VideoImageRef) => {
    if (!ref.url) {
      if (ref.storageKey) return `${API_BASE_URL}/uploads/${ref.storageKey}`;
      return '';
    }
    if (ref.url.startsWith('http') || ref.url.startsWith('data:')) return ref.url;
    if (!ref.url.includes('/uploads/') && !ref.url.startsWith('/')) {
      return `${API_BASE_URL}/uploads/${ref.url}`;
    }
    return normalizeStorageUrl(ref.url);
  }, []);

  const renderEditorHtml = useCallback((text: string, refs: VideoImageRef[]) => {
    if (!editorRef.current) return;
    editorRef.current.innerHTML = buildEditorHtml(text, refs, resolveUrl);
  }, [resolveUrl]);

  // Set editor HTML on mount
  const editorInitRef = useRef(false);
  if (!editorInitRef.current) {
    editorInitRef.current = true;
    // Will be set in useEffect below
  }

  // Render chips on mount
  const mountRef = useRef(false);
  useMemo(() => { mountRef.current = false; }, [initialPrompt, imageRefs]);

  const handleEditorRef = useCallback((el: HTMLDivElement | null) => {
    (editorRef as React.MutableRefObject<HTMLDivElement | null>).current = el;
    if (el && !mountRef.current) {
      mountRef.current = true;
      el.innerHTML = buildEditorHtml(prompt, imageRefs, resolveUrl);
    }
  }, [prompt, imageRefs, resolveUrl]);

  const handleEditorInput = useCallback(() => {
    if (!editorRef.current) return;
    setPrompt(extractText(editorRef.current));
  }, []);

  const handleEditorBlur = useCallback(() => {
    if (!editorRef.current) return;
    const text = extractText(editorRef.current);
    setPrompt(text);
    renderEditorHtml(text, imageRefs);
  }, [imageRefs, renderEditorHtml]);

  const updateNodeData = useCallback((patch: Record<string, unknown>) => {
    const s = useCanvasStore.getState();
    s.setNodes(s.nodes.map(n => n.id === firstNodeId ? { ...n, data: { ...n.data, ...patch } } : n));
  }, [firstNodeId]);

  const handleGenerate = useCallback(async () => {
    if (generating || !prompt.trim()) return;
    setGenerating(true);
    setProgress(0);
    setErrorMsg(null);
    updateNodeData({ status: 'running', progress: 0 });

    const abortCtrl = new AbortController();
    abortRef.current = abortCtrl;

    try {
      const resp = await fetch(`${API_BASE_URL}/api/canvas/nodes/${firstNodeId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_type: 'videoGeneration',
          content: { prompt, file_paths: imageRefs.map(r => r.url || r.storageKey || '').filter(Boolean), ratio: '16:9', duration: totalDuration },
        }),
        signal: abortCtrl.signal,
      });
      if (!resp.ok) throw new Error(`请求失败 (${resp.status})`);

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
              setProgress(evt.progress);
              updateNodeData({ progress: evt.progress });
            } else if (evt.type === 'success') {
              updateNodeData({ status: 'success', progress: 100, videoUrl: evt.video_url, mergedVideoUrl: evt.video_url });
              setGenerating(false);
              onClose();
            } else if (evt.type === 'error') {
              throw new Error(evt.message);
            }
          } catch (e) {
            if (e instanceof Error && e.message !== line.slice(6)) throw e;
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return;
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      updateNodeData({ status: 'error', errorMessage: msg, progress: 0 });
    } finally {
      setGenerating(false);
      abortRef.current = null;
    }
  }, [generating, prompt, totalDuration, firstNodeId, updateNodeData, onClose]);

  const risk = RISK_COLORS[driftRisk] || RISK_COLORS.low;

  return (
    <div
      className="nopan nodrag nowheel"
      style={{
        width: 460,
        background: 'rgba(20,22,28,0.95)',
        backdropFilter: 'blur(12px)',
        borderRadius: 16,
        border: '1px solid rgba(139,92,246,0.2)',
        padding: 16,
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        position: 'relative',
      }}
    >
      {/* Close */}
      <button onClick={onClose} style={{
        position: 'absolute', top: 8, right: 8, border: 'none',
        background: 'rgba(255,255,255,0.06)', borderRadius: '50%',
        width: 22, height: 22, cursor: 'pointer',
        color: 'rgba(255,255,255,0.4)', fontSize: 11,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>×</button>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'rgba(139,92,246,0.9)' }}>
          磁吸合并 · {shotIds.length}镜
        </span>
        <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.4)' }}>
          {totalDuration}s
        </span>
        <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: risk.bg, color: risk.text }}>
          漂移{driftRisk === 'low' ? '低' : driftRisk === 'medium' ? '中' : '高'}
        </span>
      </div>

      {/* Image gallery */}
      {imageRefs.length > 0 && (
        <div style={{ marginBottom: 12 }}
          onMouseEnter={() => setGalleryHovered(true)}
          onMouseLeave={() => setGalleryHovered(false)}
        >
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 6 }}>
            图片引用 ({imageRefs.length})
          </div>
          <div style={{
            display: 'flex', gap: galleryHovered ? 4 : 0,
            alignItems: 'flex-end', position: 'relative', minHeight: 52,
            transition: 'gap 0.2s',
          }}>
            {imageRefs.map((ref, i) => (
              <div key={ref.id} style={{
                position: galleryHovered ? 'relative' : 'absolute',
                left: galleryHovered ? undefined : i * 12,
                zIndex: galleryHovered ? 1 : imageRefs.length - i,
                flexShrink: 0,
              }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 8, overflow: 'hidden',
                  border: '2px solid rgba(139,92,246,0.2)',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                }}>
                  <img src={resolveUrl(ref)} alt={ref.label}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  <span style={{
                    position: 'absolute', bottom: 1, left: 1,
                    fontSize: 8, padding: '0 3px', borderRadius: 3,
                    background: 'rgba(0,0,0,0.7)', color: 'rgba(255,255,255,0.7)',
                  }}>图{i + 1}</span>
                </div>
                {galleryHovered && (
                  <div style={{
                    fontSize: 9, color: 'rgba(255,255,255,0.4)',
                    textAlign: 'center', marginTop: 2,
                    maxWidth: 48, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{ref.label}</div>
                )}
              </div>
            ))}
            {!galleryHovered && imageRefs.length > 1 && (
              <div style={{
                position: 'absolute', left: imageRefs.length * 12 + 8, bottom: 0,
                fontSize: 10, color: 'rgba(255,255,255,0.3)',
              }}>+{imageRefs.length}</div>
            )}
          </div>
        </div>
      )}

      {/* Prompt editor (contentEditable with inline image chips) */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>合并提示词</div>
        <div
          ref={handleEditorRef}
          contentEditable
          suppressContentEditableWarning
          onInput={handleEditorInput}
          onBlur={handleEditorBlur}
          style={{
            width: '100%', minHeight: 200, maxHeight: 400,
            overflowY: 'auto',
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 10, padding: 10,
            color: 'rgba(255,255,255,0.85)', fontSize: 12,
            lineHeight: 1.8, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
            outline: 'none', caretColor: 'rgba(139,92,246,0.8)',
          }}
        />
      </div>

      {/* Error */}
      {errorMsg && (
        <div style={{
          marginBottom: 8, padding: '6px 10px', borderRadius: 8,
          background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)',
          fontSize: 11, color: 'rgba(248,113,113,0.8)', wordBreak: 'break-all',
        }}>{errorMsg}</div>
      )}

      {/* Generate button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={handleGenerate}
          disabled={generating || !prompt.trim()}
          style={{
            padding: '6px 16px', borderRadius: 8, border: 'none',
            background: generating
              ? 'rgba(255,255,255,0.06)'
              : 'linear-gradient(135deg, rgba(139,92,246,0.8), rgba(168,85,247,0.8))',
            color: generating ? 'rgba(255,255,255,0.3)' : '#fff',
            fontSize: 12, fontWeight: 500,
            cursor: generating ? 'not-allowed' : 'pointer',
          }}
        >
          {generating ? `生成中 ${progress}%` : '合并生成 ▶'}
        </button>
      </div>
    </div>
  );
}

export const MergedVideoPanel = memo(MergedVideoPanelComponent);
export type { MergedVideoPanelProps };