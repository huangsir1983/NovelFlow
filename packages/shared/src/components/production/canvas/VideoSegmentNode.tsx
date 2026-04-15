/**
 * VideoSegmentNode — Merged-shots video card (Tapnow style).
 *
 * Displays a merged video segment (multiple shots → single API call).
 * Shows shot list, drift risk, multi-shot prompt editor, and video preview.
 * Executes via same Seedance SSE endpoint as VideoGenerationNode.
 */

'use client';

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { type NodeProps, type Node, Handle, Position, useReactFlow } from '@xyflow/react';
import type { VideoSegmentNodeData, VideoImageRef } from '../../../types/canvas';
import { assembleSegmentPrompt, buildSegmentImageRefs } from '../../../lib/videoPromptAssembly';
import { API_BASE_URL, normalizeStorageUrl } from '../../../lib/api';
import { useCanvasStore } from '../../../stores/canvasStore';

type VideoSegmentNodeType = Node<VideoSegmentNodeData, 'videoSegment'>;

function VideoSegmentNodeComponent({ id, data, selected }: NodeProps<VideoSegmentNodeType>) {
  const [hovered, setHovered] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [localImageRefs, setLocalImageRefs] = useState<VideoImageRef[]>([]);
  const [localDuration, setLocalDuration] = useState(data.totalDurationSeconds || 12);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const reactFlow = useReactFlow();
  const abortRef = useRef<AbortController | null>(null);

  // Close panel when deselected
  const prevSelectedRef = useRef(selected);
  useEffect(() => {
    if (prevSelectedRef.current && !selected) setPanelOpen(false);
    prevSelectedRef.current = selected;
  }, [selected]);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(251,146,60,0.9)' : 'rgba(251,146,60,0.5)'; // orange for merged segments
  const isRunning = data.status === 'running' || data.status === 'queued';
  const shotCount = data.shots?.length || data.shotIds?.length || 0;

  const driftColor = data.driftRisk === 'high' ? '#f87171'
    : data.driftRisk === 'medium' ? '#fbbf24'
    : '#34d399';

  // Direct store update for immediate feedback
  const updateNodeData = useCallback((patch: Record<string, unknown>) => {
    const s = useCanvasStore.getState();
    s.setNodes(s.nodes.map(n => n.id === id ? { ...n, data: { ...n.data, ...patch } } : n));
  }, [id]);

  const resolveUrl = useCallback((ref: VideoImageRef) => {
    if (!ref.url) return ref.storageKey ? `${API_BASE_URL}/uploads/${ref.storageKey}` : '';
    if (ref.url.startsWith('http') || ref.url.startsWith('data:')) return ref.url;
    if (!ref.url.includes('/uploads/') && !ref.url.startsWith('/')) return `${API_BASE_URL}/uploads/${ref.url}`;
    return normalizeStorageUrl(ref.url);
  }, []);

  const handleOpenPanel = useCallback(() => {
    if (!panelOpen) {
      const refs = data.imageRefs?.length ? data.imageRefs : buildSegmentImageRefs(data);
      setLocalImageRefs(refs);
      const prompt = data.assembledPrompt || assembleSegmentPrompt(data);
      setPromptText(prompt);
      setLocalDuration(data.totalDurationSeconds || 12);
      setErrorMsg(null);
    }
    setPanelOpen(!panelOpen);

    const node = reactFlow.getNode(id);
    if (node) {
      const CARD_W = 300;
      const PANEL_H = 480;
      const totalH = 31 + Math.round(CARD_W * 9 / 16) + 28 + PANEL_H;
      const centerX = node.position.x + CARD_W / 2;
      const centerY = node.position.y + totalH / 2;
      const vpEl = document.querySelector('.react-flow') as HTMLElement | null;
      const vpH = vpEl?.clientHeight || 800;
      const vpW = vpEl?.clientWidth || 1200;
      const targetZoom = Math.min(vpH / (totalH * 1.15), vpW / (CARD_W * 1.3), 1.5);
      reactFlow.setCenter(centerX, centerY, { zoom: Math.max(targetZoom, 0.5), duration: 400 });
    }
  }, [panelOpen, data, id, reactFlow]);

  // Execute merged video generation via SSE
  const handleExecute = useCallback(async () => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    setErrorMsg(null);
    const filePaths = localImageRefs.map(r => r.url || r.storageKey || '').filter(Boolean);
    updateNodeData({ status: 'running', progress: 0, assembledPrompt: promptText, imageRefs: localImageRefs });

    const abortCtrl = new AbortController();
    abortRef.current = abortCtrl;

    try {
      const resp = await fetch(`${API_BASE_URL}/api/canvas/nodes/${id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_type: 'videoSegment',
          content: { prompt: promptText, file_paths: filePaths, ratio: data.ratio || '16:9', duration: localDuration },
        }),
        signal: abortCtrl.signal,
      });

      if (!resp.ok) throw new Error(`请求失败 (${resp.status}): ${await resp.text()}`);

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
            if (evt.type === 'progress') updateNodeData({ progress: evt.progress });
            else if (evt.type === 'success') {
              updateNodeData({ status: 'success', progress: 100, videoUrl: evt.video_url, seedanceTaskId: evt.task_id });
              setPanelOpen(false);
            } else if (evt.type === 'error') throw new Error(evt.message);
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message !== line.slice(6)) throw parseErr;
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return;
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      updateNodeData({ status: 'error', errorMessage: msg, progress: 0 });
    } finally {
      abortRef.current = null;
    }
  }, [id, promptText, localImageRefs, localDuration, data.ratio, updateNodeData]);

  useEffect(() => { return () => { abortRef.current?.abort(); }; }, []);

  // Dissolve merge group
  const handleDissolve = useCallback(async () => {
    if (!data.shotGroupId) return;
    try {
      await fetch(`${API_BASE_URL}/api/canvas/shot-groups/${data.shotGroupId}`, { method: 'DELETE' });
      const s = useCanvasStore.getState();
      s.setMergeGroups(s.mergeGroups.filter(g => g.groupId !== data.shotGroupId));
    } catch (err) {
      console.error('[VideoSegment] dissolve failed:', err);
    }
  }, [data.shotGroupId]);

  // Persist shot order/removal to backend + update canvasStore.mergeGroups
  const updateShotGroup = useCallback(async (newShotIds: string[]) => {
    if (!data.shotGroupId) return;
    try {
      await fetch(`${API_BASE_URL}/api/canvas/shot-groups/${data.shotGroupId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shot_ids: newShotIds }),
      });
      const s = useCanvasStore.getState();
      s.setMergeGroups(
        s.mergeGroups.map(g =>
          g.groupId === data.shotGroupId ? { ...g, shotIds: newShotIds } : g,
        ),
      );
    } catch (err) {
      console.error('[VideoSegment] update shot group failed:', err);
    }
  }, [data.shotGroupId]);

  // Reorder: move shot at `fromIdx` to `toIdx`
  const handleReorderShot = useCallback((fromIdx: number, toIdx: number) => {
    const shots = data.shots || [];
    if (fromIdx < 0 || fromIdx >= shots.length || toIdx < 0 || toIdx >= shots.length) return;
    const ids = shots.map(s => s.shotId);
    const [moved] = ids.splice(fromIdx, 1);
    ids.splice(toIdx, 0, moved);
    const reordered = ids.map(sid => shots.find(s => s.shotId === sid)!).filter(Boolean);
    updateNodeData({ shots: reordered, shotIds: ids });
    updateShotGroup(ids);
  }, [data.shots, updateNodeData, updateShotGroup]);

  // Remove a single shot from the group
  const handleRemoveShot = useCallback(async (shotId: string) => {
    const shots = data.shots || [];
    const remaining = shots.filter(s => s.shotId !== shotId);
    if (remaining.length < 2) {
      await handleDissolve();
      return;
    }
    const newIds = remaining.map(s => s.shotId);
    updateNodeData({
      shots: remaining,
      shotIds: newIds,
      totalDurationSeconds: remaining.reduce((sum, s) => sum + s.durationSeconds, 0),
    });
    updateShotGroup(newIds);
  }, [data.shots, updateNodeData, updateShotGroup, handleDissolve]);

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} className="relative" style={{ width: 300 }}>
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      {/* Title bar */}
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">🎬</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>
          视频段·{shotCount}镜合并
        </span>
      </div>

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
          ) : data.inputImageUrl ? (
            <img src={data.inputImageUrl} alt="首帧" style={{ width: '100%', height: 'auto', display: 'block', opacity: 0.7 }} />
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>🎬</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>{isRunning ? '生成中...' : '待生成'}</span>
            </div>
          )}
        </div>

        {/* Gradient overlay with badges */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'linear-gradient(transparent, rgba(0,0,0,0.75))',
          padding: '24px 12px 10px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, backgroundColor: 'rgba(251,146,60,0.15)', color: 'rgba(251,146,60,0.9)' }}>
              {shotCount}镜合并
            </span>
            <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.5)' }}>
              {data.totalDurationSeconds}s
            </span>
            <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, backgroundColor: `${driftColor}15`, color: driftColor }}>
              漂移:{data.driftRisk}
            </span>
            {data.recommendedProvider && (
              <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, backgroundColor: 'rgba(99,102,241,0.12)', color: 'rgba(129,140,248,0.8)' }}>
                {data.recommendedProvider}
              </span>
            )}
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
            <div style={{ height: '100%', backgroundColor: 'rgba(251,146,60,0.6)', width: `${data.progress}%`, transition: 'width 0.3s' }} />
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
              width: 340,
              background: 'rgba(20,22,28,0.95)',
              backdropFilter: 'blur(12px)',
              borderRadius: 16,
              border: '1px solid rgba(255,255,255,0.08)',
              padding: 16,
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              position: 'relative',
              maxHeight: 460,
              overflowY: 'auto',
            }}
          >
            {/* Close */}
            <button onClick={(e) => { e.stopPropagation(); setPanelOpen(false); }}
              style={{ position: 'absolute', top: 8, right: 8, border: 'none', background: 'rgba(255,255,255,0.06)', borderRadius: '50%', width: 22, height: 22, cursor: 'pointer', color: 'rgba(255,255,255,0.4)', fontSize: 11, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              ×
            </button>

            {/* Shot list */}
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 6 }}>
              合并分镜 ({shotCount})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 12 }}>
              {(data.shots || []).map((shot, i) => (
                <div key={shot.shotId} style={{
                  display: 'flex', alignItems: 'center', gap: 4, padding: '4px 6px',
                  borderRadius: 6, background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  {/* Reorder buttons */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0, flexShrink: 0 }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleReorderShot(i, i - 1); }}
                      disabled={i === 0}
                      style={{
                        border: 'none', background: 'transparent', padding: 0, cursor: i === 0 ? 'default' : 'pointer',
                        fontSize: 8, lineHeight: 1, color: i === 0 ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.35)',
                      }}
                    >▲</button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleReorderShot(i, i + 1); }}
                      disabled={i === (data.shots || []).length - 1}
                      style={{
                        border: 'none', background: 'transparent', padding: 0,
                        cursor: i === (data.shots || []).length - 1 ? 'default' : 'pointer',
                        fontSize: 8, lineHeight: 1,
                        color: i === (data.shots || []).length - 1 ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.35)',
                      }}
                    >▼</button>
                  </div>
                  <span style={{ fontSize: 10, color: 'rgba(251,146,60,0.8)', fontWeight: 600, minWidth: 20 }}>
                    镜{i + 1}
                  </span>
                  <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {shot.description || '—'}
                  </span>
                  <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>
                    {shot.durationSeconds}s · {shot.framing}
                  </span>
                  {/* Remove shot button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleRemoveShot(shot.shotId); }}
                    style={{
                      border: 'none', background: 'rgba(255,255,255,0.04)', borderRadius: '50%',
                      width: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', color: 'rgba(255,255,255,0.25)', fontSize: 10, flexShrink: 0,
                      padding: 0, lineHeight: 1,
                    }}
                    title="移除此分镜"
                  >×</button>
                </div>
              ))}
            </div>

            {/* Image refs */}
            {localImageRefs.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>图片引用</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {localImageRefs.map((ref, i) => (
                    <div key={ref.id} style={{
                      width: 36, height: 36, borderRadius: 6, overflow: 'hidden',
                      border: '1px solid rgba(255,255,255,0.1)', position: 'relative',
                    }}>
                      <img src={resolveUrl(ref)} alt={ref.label} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      <span style={{ position: 'absolute', bottom: 1, right: 2, fontSize: 8, color: 'rgba(251,146,60,0.9)' }}>
                        {i + 1}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Prompt editor */}
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginBottom: 4 }}>多镜头 Prompt</div>
            <textarea
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              style={{
                width: '100%', minHeight: 100, maxHeight: 200,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8, padding: 8,
                fontSize: 11, color: 'rgba(255,255,255,0.7)',
                lineHeight: 1.5, resize: 'vertical',
                outline: 'none',
              }}
            />

            {/* Duration slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>时长</span>
              <input
                type="range" min={2} max={15} step={1}
                value={localDuration}
                onChange={(e) => setLocalDuration(Number(e.target.value))}
                style={{ flex: 1, accentColor: '#fb923c' }}
              />
              <span style={{ fontSize: 11, color: 'rgba(251,146,60,0.8)', minWidth: 24, textAlign: 'right' }}>
                {localDuration}s
              </span>
            </div>

            {/* Duration warning */}
            {localDuration > 12 && (
              <div style={{
                padding: '4px 8px', borderRadius: 6, marginBottom: 8,
                background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)',
                fontSize: 10, color: 'rgba(248,113,113,0.8)',
              }}>
                ⚠ 超过12秒易产生画面漂移
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

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                onClick={(e) => { e.stopPropagation(); handleDissolve(); }}
                style={{
                  border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
                  padding: '6px 10px', fontSize: 11, background: 'rgba(255,255,255,0.04)',
                  color: 'rgba(255,255,255,0.4)', cursor: 'pointer', flexShrink: 0,
                }}
              >解散</button>
              <button
                onClick={(e) => { e.stopPropagation(); handleExecute(); }}
                disabled={isRunning || !data.inputImageUrl}
                style={{
                  flex: 1, border: 'none', borderRadius: 8,
                  padding: '8px 0', fontSize: 12, fontWeight: 600,
                  background: isRunning ? 'rgba(255,255,255,0.06)' : 'linear-gradient(135deg, rgba(251,146,60,0.8), rgba(249,115,22,0.8))',
                  color: isRunning ? 'rgba(255,255,255,0.3)' : '#fff',
                  cursor: isRunning || !data.inputImageUrl ? 'not-allowed' : 'pointer',
                  opacity: !data.inputImageUrl ? 0.4 : 1,
                }}
              >
                {isRunning ? '生成中...' : data.videoUrl ? '重新生成' : '生成合并视频'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export const VideoSegmentNode = memo(VideoSegmentNodeComponent);
